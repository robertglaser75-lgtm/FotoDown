# -*- coding: utf-8 -*-
"""FotoDown Main Window implementation in PySide6."""

from pathlib import Path
import sys
from typing import List, Optional

from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QLabel, QMainWindow, QMessageBox,
    QScrollArea, QSplitter, QStackedWidget, QStatusBar,
    QVBoxLayout, QWidget
)

from core.config import AppConfig
from core.history import ImportHistory
from core.importer import ImporterEngine, ScanItem, ImportStats
from core.version import __version__

from .models.scan_model import ScanTableModel
from .models.filter_proxy import ScanFilterProxyModel
from .views.table_view import MediaTableView
from .views.gallery_view import MediaGalleryView
from .widgets.header_banner import HeaderBanner
from .widgets.collapsible_box import CollapsibleBox
from .widgets.path_selector import PathSelectorWidget
from .widgets.pattern_editor import PatternEditorWidget
from .widgets.action_bar import ActionBarWidget
from .widgets.filter_bar import FilterBarWidget
from .workers.scan_worker import ScanWorker
from .workers.import_worker import ImportWorker
from .workers.thumb_worker import ThumbnailTask
from .dialogs.history_dialog import HistoryDialog
from .dialogs.help_dialog import HelpDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"FotoDown v{__version__} - Foto-Importeur & EXIF-Manager")
        self.resize(1200, 850)
        self.setMinimumSize(950, 650)

        self._set_app_icon()

        # Core logic setup
        self.config = AppConfig.load()
        self.history = ImportHistory()
        self.engine = ImporterEngine(self.history)
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(4)

        # Worker references
        self._scan_worker: Optional[ScanWorker] = None
        self._import_worker: Optional[ImportWorker] = None

        # Data Models
        self.table_model = ScanTableModel()
        self.proxy_model = ScanFilterProxyModel()
        self.proxy_model.setSourceModel(self.table_model)

        self._setup_ui()
        self._connect_signals()
        self._load_config_to_ui()

    def _set_app_icon(self):
        for icon_name in ["icon.png", "icon_64.png", "icon_256.png", "fotodown.ico", "icon.ico"]:
            p = Path("assets") / icon_name
            if p.exists():
                self.setWindowIcon(QIcon(str(p)))
                break

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Header Banner
        self.header_banner = HeaderBanner()
        main_layout.addWidget(self.header_banner)

        # Splitter between Configuration/Controls and Item Views
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        # Top Section Container
        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(12, 10, 12, 6)
        top_layout.setSpacing(8)

        # Collapsible Section 1: Paths & Organization
        self.box_paths = CollapsibleBox("1. Quell- und Zielordner festlegen", is_expanded=True)
        self.path_selector = PathSelectorWidget()
        self.box_paths.set_content_widget(self.path_selector)
        top_layout.addWidget(self.box_paths)

        # Collapsible Section 2: Patterns & Tags
        self.box_patterns = CollapsibleBox("2. Dateinamen- und Ordnerstruktur-Muster", is_expanded=False)
        self.pattern_editor = PatternEditorWidget()
        self.box_patterns.set_content_widget(self.pattern_editor)
        top_layout.addWidget(self.box_patterns)

        # Action Buttons & Progress
        self.action_bar = ActionBarWidget()
        top_layout.addWidget(self.action_bar)

        # Filter Bar
        self.filter_bar = FilterBarWidget()
        top_layout.addWidget(self.filter_bar)

        splitter.addWidget(top_container)

        # Bottom Section: Views Stack (Table vs Gallery)
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(12, 0, 12, 8)
        bottom_layout.setSpacing(0)

        self.view_stack = QStackedWidget()

        # View 0: Table View
        self.table_view = MediaTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setup_column_widths()
        self.view_stack.addWidget(self.table_view)

        # View 1: Gallery View
        self.gallery_view = MediaGalleryView()
        self.gallery_view.setModel(self.proxy_model)
        self.view_stack.addWidget(self.gallery_view)

        bottom_layout.addWidget(self.view_stack)
        splitter.addWidget(bottom_container)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.lbl_status_stats = QLabel("Bereit. Wählen Sie ein Quelllaufwerk und klicken Sie auf 'Scannen'.")
        self.status_bar.addWidget(self.lbl_status_stats, 1)

    def _connect_signals(self):
        # Header signals
        self.header_banner.drive_selected.connect(self.path_selector.edit_source.setText)
        self.header_banner.open_history.connect(self._open_history_dialog)
        self.header_banner.open_help.connect(self._open_help_dialog)

        # Path & Pattern changes
        self.path_selector.changed.connect(self._on_settings_changed)
        self.pattern_editor.changed.connect(self._on_settings_changed)

        # Actions
        self.action_bar.scan_clicked.connect(self._start_scan)
        self.action_bar.import_clicked.connect(self._start_import)
        self.action_bar.cancel_clicked.connect(self._cancel_task)

        # Filters & View modes
        self.filter_bar.view_mode_changed.connect(self._on_view_mode_changed)
        self.filter_bar.status_filter_changed.connect(self.proxy_model.set_status_filter)
        self.filter_bar.type_filter_changed.connect(self.proxy_model.set_type_filter)
        self.filter_bar.search_changed.connect(self.proxy_model.set_search_term)

        # Selection shortcuts
        self.filter_bar.select_all_clicked.connect(self.table_model.select_all)
        self.filter_bar.deselect_all_clicked.connect(self.table_model.deselect_all)
        self.filter_bar.select_new_clicked.connect(self.table_model.select_only_new)

        # Model changes update stats
        self.table_model.selection_changed.connect(self._update_stats_bar)
        self.gallery_view.selection_toggled.connect(self._update_stats_bar)

    def _load_config_to_ui(self):
        self.path_selector.load_config(self.config)
        self.pattern_editor.load_config(self.config)
        self.pattern_editor.update_preview(self.config.type_folder_organization)

    def _on_settings_changed(self):
        self.path_selector.sync_to_config(self.config)
        self.pattern_editor.sync_to_config(self.config)
        self.pattern_editor.update_preview(self.config.type_folder_organization)
        self.config.save()

    def _on_view_mode_changed(self, mode: str):
        if mode == "gallery":
            self.view_stack.setCurrentIndex(1)
            self._queue_thumbnails_for_visible()
        else:
            self.view_stack.setCurrentIndex(0)

    def _update_stats_bar(self):
        items = self.table_model.get_items()
        total = len(items)
        selected = sum(1 for it in items if it.selected)
        new_cnt = sum(1 for it in items if it.status == "Neu")
        dup_cnt = sum(1 for it in items if it.is_duplicate)
        total_bytes = sum(it.metadata.file_size for it in items if it.selected)
        mb = total_bytes / (1024 * 1024)

        self.lbl_status_stats.setText(
            f"Gefunden: {total} | Ausgewählt: {selected} ({mb:.1f} MB) | Neu: {new_cnt} | Bereits importiert: {dup_cnt}"
        )
        self.action_bar.btn_import.setEnabled(selected > 0)

    def _start_scan(self):
        self._on_settings_changed()
        source_dir = Path(self.config.source_dir)
        if not self.config.source_dir or not source_dir.exists():
            QMessageBox.warning(self, "Ungültiger Quellordner", f"Der Quellordner '{self.config.source_dir}' existiert nicht.")
            return

        self.action_bar.set_busy(True, "Scannen")
        self.action_bar.lbl_status.setText("Durchsuche Quellverzeichnis...")

        self._scan_worker = ScanWorker(self.engine, source_dir, self.config)
        self._scan_worker.progress.connect(self._on_worker_progress)
        self._scan_worker.scan_finished.connect(self._on_scan_finished)
        self._scan_worker.error.connect(self._on_worker_error)
        self._scan_worker.start()

    def _on_worker_progress(self, cur: int, total: int, msg: str):
        pct = (cur / total * 100) if total > 0 else 0
        self.action_bar.update_progress(pct, msg)

    def _on_scan_finished(self, items: List[ScanItem]):
        self.action_bar.set_busy(False)
        self.table_model.set_items(items)
        self._update_stats_bar()

        new_count = sum(1 for it in items if it.status == "Neu")
        self.action_bar.lbl_status.setText(
            f"Scan abgeschlossen: {len(items)} Dateien gefunden ({new_count} neu)."
        )

        self._queue_thumbnails_for_visible()

    def _queue_thumbnails_for_visible(self):
        items = self.table_model.get_items()
        for item in items:
            path_str = str(item.source_path)
            if path_str not in self.gallery_view.delegate.pixmap_cache:
                task = ThumbnailTask(item.source_path)
                task.signals.thumbnail_ready.connect(self._on_thumbnail_ready)
                self.thread_pool.start(task)

    def _on_thumbnail_ready(self, path_str: str, qimage):
        pixmap = QPixmap.fromImage(qimage)
        self.gallery_view.delegate.set_pixmap(path_str, pixmap)
        self.gallery_view.viewport().update()

    def _start_import(self):
        self._on_settings_changed()
        target_dir = Path(self.config.target_dir)
        if not self.config.target_dir:
            QMessageBox.warning(self, "Ungültiger Zielordner", "Bitte wählen Sie einen Zielordner für die Fotos aus.")
            return

        selected_items = [it for it in self.table_model.get_items() if it.selected]
        if not selected_items:
            QMessageBox.information(self, "Keine Auswahl", "Es wurden keine Dateien zum Importieren ausgewählt.")
            return

        self.action_bar.set_busy(True, "Importieren")
        self._import_worker = ImportWorker(self.engine, selected_items, self.config)
        self._import_worker.progress.connect(self._on_worker_progress)
        self._import_worker.import_finished.connect(self._on_import_finished)
        self._import_worker.error.connect(self._on_worker_error)
        self._import_worker.start()

    def _on_import_finished(self, stats: ImportStats):
        self.action_bar.set_busy(False)
        mb = stats.bytes_copied / (1024 * 1024)
        msg = f"Import abgeschlossen!\\n\\n✓ {stats.copied_success} Dateien kopiert ({mb:.1f} MB)\\n⚠️ {stats.duplicates_skipped} Duplikate übersprungen\\n✕ {stats.failed} Fehler"
        QMessageBox.information(self, "Import abgeschlossen", msg)
        self.action_bar.lbl_status.setText(f"Fertig: {stats.copied_success} Dateien erfolgreich kopiert ({mb:.1f} MB).")
        self._start_scan()

    def _on_worker_error(self, err_msg: str):
        self.action_bar.set_busy(False)
        QMessageBox.critical(self, "Fehler", f"Ein Fehler ist aufgetreten:\\n{err_msg}")
        self.action_bar.lbl_status.setText("Vorgang mit Fehler abgebrochen.")

    def _cancel_task(self):
        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.cancel()
        if self._import_worker and self._import_worker.isRunning():
            self._import_worker.cancel()
        self.action_bar.set_busy(False)
        self.action_bar.lbl_status.setText("Vorgang abgebrochen.")

    def _open_history_dialog(self):
        dlg = HistoryDialog(self.history, self)
        dlg.exec()

    def _open_help_dialog(self):
        dlg = HelpDialog(self)
        dlg.exec()

    def closeEvent(self, event):
        self._cancel_task()
        self._on_settings_changed()
        event.accept()
