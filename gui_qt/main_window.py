# -*- coding: utf-8 -*-
"""FotoDown Main Window implementation in PySide6 with professional layout and storage visualization."""

from pathlib import Path
import sys
from typing import List, Optional

from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFrame, QLabel, QMainWindow, QMessageBox,
    QScrollArea, QSplitter, QStackedWidget, QStatusBar,
    QVBoxLayout, QWidget
)

from core.config import AppConfig
from core.drive_detector import format_size
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
from .widgets.splash_screen import FotoDownSplashScreen
from .widgets.empty_state import EmptyStateWidget
from .workers.scan_worker import ScanWorker
from .workers.import_worker import ImportWorker
from .workers.thumb_worker import ThumbnailTask
from .dialogs.history_dialog import HistoryDialog
from .dialogs.help_dialog import HelpDialog
from .dialogs.quick_preview_dialog import QuickPreviewDialog


class MainWindow(QMainWindow):
    def __init__(self, splash: Optional[FotoDownSplashScreen] = None):
        super().__init__()
        self.setWindowTitle(f"FotoDown v{__version__} - Foto-Importeur & EXIF-Manager")
        self.resize(1280, 850)
        self.setMinimumSize(1000, 680)

        self._set_app_icon()

        if splash:
            splash.set_status("Lade Konfiguration & Historie...", 2, 5)

        # Core logic setup
        self.config = AppConfig.load()
        self.history = ImportHistory()
        self.engine = ImporterEngine(self.history)
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(4)

        # Worker references
        self._scan_worker: Optional[ScanWorker] = None
        self._import_worker: Optional[ImportWorker] = None

        if splash:
            splash.set_status("Initialisiere Datenmodelle...", 3, 5)

        # Data Models
        self.table_model = ScanTableModel()
        self.proxy_model = ScanFilterProxyModel()
        self.proxy_model.setSourceModel(self.table_model)

        if splash:
            splash.set_status("Erstelle Benutzeroberfläche...", 4, 5)

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

        # 2. Main Horizontal Splitter (Sidebar left, Workspace right)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setChildrenCollapsible(False)

        # Left Sidebar (Scrollable options and controls)
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_scroll.setMinimumWidth(380)

        sidebar_container = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(12, 10, 8, 10)
        sidebar_layout.setSpacing(10)

        # Collapsible Section 1: Paths & Storage
        self.box_paths = CollapsibleBox("1. Quell- und Zielordner festlegen", is_expanded=True)
        self.path_selector = PathSelectorWidget()
        self.box_paths.set_content_widget(self.path_selector)
        sidebar_layout.addWidget(self.box_paths)

        # Collapsible Section 2: Patterns & Tags
        self.box_patterns = CollapsibleBox("2. Namens- und Ordnerstruktur-Muster", is_expanded=False)
        self.pattern_editor = PatternEditorWidget()
        self.box_patterns.set_content_widget(self.pattern_editor)
        sidebar_layout.addWidget(self.box_patterns)

        # Action Buttons, Capacity Info & Progress
        self.action_bar = ActionBarWidget()
        sidebar_layout.addWidget(self.action_bar)
        sidebar_layout.addStretch()

        sidebar_scroll.setWidget(sidebar_container)
        main_splitter.addWidget(sidebar_scroll)

        # Right Section: Media Workspace (Filters + Views)
        workspace_container = QWidget()
        workspace_layout = QVBoxLayout(workspace_container)
        workspace_layout.setContentsMargins(8, 10, 12, 8)
        workspace_layout.setSpacing(8)

        # Filter Bar (with Zoom Slider for Gallery)
        self.filter_bar = FilterBarWidget()
        workspace_layout.addWidget(self.filter_bar)

        # View Stack (Empty State vs Table vs Gallery)
        self.view_stack = QStackedWidget()

        # View 0: Empty State
        self.empty_state = EmptyStateWidget()
        self.view_stack.addWidget(self.empty_state)

        # View 1: Table View
        self.table_view = MediaTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setup_column_widths()
        self.view_stack.addWidget(self.table_view)

        # View 2: Gallery View
        self.gallery_view = MediaGalleryView()
        self.gallery_view.setModel(self.proxy_model)
        self.view_stack.addWidget(self.gallery_view)

        workspace_layout.addWidget(self.view_stack)
        main_splitter.addWidget(workspace_container)

        # Splitter sizing: Left sidebar ~390px, Right workspace gets rest
        main_splitter.setSizes([390, 890])
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(main_splitter)

        # 3. Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.lbl_status_stats = QLabel("Bereit. Wählen Sie ein Quelllaufwerk und klicken Sie auf 'Scannen'.")
        self.status_bar.addWidget(self.lbl_status_stats, 1)

    def _connect_signals(self):
        # Header signals
        self.header_banner.drive_selected.connect(self._on_header_drive_selected)
        self.header_banner.open_history.connect(self._open_history_dialog)
        self.header_banner.open_help.connect(self._open_help_dialog)

        # Empty state scan button
        self.empty_state.scan_requested.connect(self._start_scan)

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
        self.filter_bar.thumbnail_size_changed.connect(self.gallery_view.set_thumbnail_size)

        # Quick Preview requests (Space or Double click)
        self.table_view.open_preview_requested.connect(self._open_quick_preview)
        self.gallery_view.open_preview_requested.connect(self._open_quick_preview)

        # Selection shortcuts
        self.filter_bar.select_all_clicked.connect(self.table_model.select_all)
        self.filter_bar.deselect_all_clicked.connect(self.table_model.deselect_all)
        self.filter_bar.select_new_clicked.connect(self.table_model.select_only_new)

        # Model changes update stats
        self.table_model.selection_changed.connect(self._update_stats_bar)
        self.gallery_view.selection_toggled.connect(self._update_stats_bar)

    def _open_quick_preview(self, index):
        if not index.isValid():
            return
        items = self.table_model.get_items()
        if not items:
            return

        target_item: Optional[ScanItem] = index.data(Qt.ItemDataRole.UserRole)
        start_idx = 0
        if target_item and target_item in items:
            start_idx = items.index(target_item)

        dlg = QuickPreviewDialog(items, start_index=start_idx, parent=self)
        dlg.selection_changed.connect(self._on_preview_selection_changed)
        dlg.exec()

    def _on_preview_selection_changed(self):
        self.table_model.layoutChanged.emit()
        self._update_stats_bar()

    def _on_header_drive_selected(self, path: str):
        self.path_selector.edit_source.setText(path)
        self.path_selector.source_storage_bar.set_path(path)

    def _load_config_to_ui(self):
        self.path_selector.load_config(self.config)
        self.pattern_editor.load_config(self.config)
        self.pattern_editor.update_preview(self.config.type_folder_organization)

    def _on_settings_changed(self):
        self.path_selector.sync_to_config(self.config)
        self.pattern_editor.sync_to_config(self.config)
        self.pattern_editor.update_preview(self.config.type_folder_organization)
        self.config.save()
        self._update_stats_bar()

    def _update_view_selection(self):
        items = self.table_model.get_items()
        if not items:
            self.view_stack.setCurrentWidget(self.empty_state)
            return

        mode = self.filter_bar.combo_view.currentData()
        if mode == "gallery":
            self.view_stack.setCurrentWidget(self.gallery_view)
            self._queue_thumbnails_for_visible()
        else:
            self.view_stack.setCurrentWidget(self.table_view)

    def _on_view_mode_changed(self, mode: str):
        self._update_view_selection()

    def _update_stats_bar(self):
        items = self.table_model.get_items()
        total = len(items)
        selected = sum(1 for it in items if it.selected)
        new_cnt = sum(1 for it in items if it.status == "Neu")
        dup_cnt = sum(1 for it in items if it.is_duplicate)
        total_bytes = sum(it.metadata.file_size for it in items if it.selected)

        # Check target capacity
        has_space, warning_msg = self.path_selector.check_capacity(total_bytes)

        # Update action bar button and message
        self.action_bar.update_selection_stats(
            selected,
            total_bytes,
            has_capacity=has_space,
            warning_msg=warning_msg,
        )

        total_str = format_size(total_bytes)
        self.lbl_status_stats.setText(
            f"Gefunden: {total} | Ausgewählt: {selected} ({total_str}) | Neu: {new_cnt} | Bereits importiert: {dup_cnt}"
        )

    def _start_scan(self):
        self._on_settings_changed()
        source_dir = Path(self.config.source_dir)
        if not self.config.source_dir or not source_dir.exists():
            QMessageBox.warning(
                self, "Ungültiger Quellordner",
                f"Der Quellordner '{self.config.source_dir}' existiert nicht."
            )
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
        self._update_view_selection()

        new_count = sum(1 for it in items if it.status == "Neu")
        self.action_bar.lbl_status.setText(
            f"Scan abgeschlossen: {len(items)} Dateien gefunden ({new_count} neu)."
        )

        if self.filter_bar.combo_view.currentData() == "gallery":
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

        total_bytes = sum(it.metadata.file_size for it in selected_items)
        has_space, warning_msg = self.path_selector.check_capacity(total_bytes)
        if not has_space:
            QMessageBox.critical(self, "Speicherplatz unzureichend", warning_msg)
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
        msg_lines = [
            "Import abgeschlossen!\n",
            f"✓ {stats.copied_success} Dateien kopiert ({mb:.1f} MB)"
        ]
        if stats.backup_success > 0:
            msg_lines.append(f"\U0001F6E1 {stats.backup_success} Dateien auf 2. Backup-Ziel gesichert")
        msg_lines.append(f"⚠️ {stats.duplicates_skipped} Duplikate übersprungen")
        if stats.failed > 0:
            msg_lines.append(f"✕ {stats.failed} Fehler")

        QMessageBox.information(self, "Import abgeschlossen", "\n".join(msg_lines))
        self.action_bar.lbl_status.setText(f"Fertig: {stats.copied_success} Dateien erfolgreich kopiert ({mb:.1f} MB).")
        self._start_scan()

    def _on_worker_error(self, err_msg: str):
        self.action_bar.set_busy(False)
        QMessageBox.critical(self, "Fehler", f"Ein Fehler ist aufgetreten:\n{err_msg}")
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
