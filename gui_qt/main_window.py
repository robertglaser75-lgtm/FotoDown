"""Main application window uniting all GUI widgets and core business logic."""

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QScrollArea, QSizePolicy, QSplitter, QStackedWidget, QStatusBar,
    QVBoxLayout, QWidget
)

from core.config import AppConfig
from core.drive_detector import DriveInfo, format_size
from core.history import ImportHistory
from core.importer import ImporterEngine, ImportStats, ScanItem
from core.version import __version__

from .models.scan_model import ScanTableModel
from .models.filter_proxy import ScanFilterProxyModel
from .views.table_view import MediaTableView
from .views.gallery_view import MediaGalleryView
from .views.tree_view import MediaTreeView
from .widgets.header_banner import HeaderBanner
from .widgets.collapsible_box import CollapsibleBox
from .widgets.profile_bar import ProfileBarWidget
from .widgets.path_selector import PathSelectorWidget
from .widgets.pattern_editor import PatternEditorWidget
from .widgets.general_settings import GeneralSettingsWidget
from .widgets.action_bar import ActionBarWidget
from .widgets.filter_bar import FilterBarWidget
from .widgets.exif_inspector import ExifInspectorWidget
from .widgets.splash_screen import FotoDownSplashScreen
from .widgets.empty_state import EmptyStateWidget
from .widgets.card_notification import CardNotificationBanner
from .workers.scan_worker import ScanWorker
from .workers.import_worker import ImportWorker
from .workers.thumb_worker import ThumbnailTask
from .workers.drive_watcher import DriveWatcherThread
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
        self._is_loading_config = False
        self.config = AppConfig.load()
        self.history = ImportHistory()
        self.engine = ImporterEngine(self.history)
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(4)

        # Worker references
        self._scan_worker: Optional[ScanWorker] = None
        self._import_worker: Optional[ImportWorker] = None
        self._drive_watcher: Optional[DriveWatcherThread] = None

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
        self._init_drive_watcher()

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

        # 2. Hotplug Card Notification Banner
        self.card_notification = CardNotificationBanner()
        main_layout.addWidget(self.card_notification)

        # 3. Main Horizontal Splitter (Sidebar left, Workspace right)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setChildrenCollapsible(False)

        # Left Sidebar (Fixed Profile Bar at top, Scrollable Settings in middle, Fixed Action Bar at bottom)
        sidebar_container = QWidget()
        sidebar_container.setMinimumWidth(390)
        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(10, 8, 6, 8)
        sidebar_layout.setSpacing(6)

        # 1. Top Fixed: Profile / Preset Selection Bar
        self.profile_bar = ProfileBarWidget()
        sidebar_layout.addWidget(self.profile_bar)

        # 2. Middle Scrollable Area: Collapsible Settings Sections
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 4, 0)
        scroll_layout.setSpacing(8)

        # Collapsible Section 1: Paths & Storage
        self.box_paths = CollapsibleBox("1. Quell- und Zielordner", is_expanded=True)
        self.path_selector = PathSelectorWidget()
        self.box_paths.set_content_widget(self.path_selector)
        scroll_layout.addWidget(self.box_paths)

        # Collapsible Section 2: Patterns & Tags
        self.box_patterns = CollapsibleBox("2. Namens- und Ordnerstruktur-Muster", is_expanded=False)
        self.pattern_editor = PatternEditorWidget()
        self.box_patterns.set_content_widget(self.pattern_editor)
        scroll_layout.addWidget(self.box_patterns)

        # Collapsible Section 3: General Settings & Options (eigens ein-/ausklappbar)
        self.box_general = CollapsibleBox("3. Allgemeine Einstellungen & Optionen", is_expanded=False)
        self.general_settings = GeneralSettingsWidget()
        self.box_general.set_content_widget(self.general_settings)
        scroll_layout.addWidget(self.box_general)
        scroll_layout.addStretch()

        sidebar_scroll.setWidget(scroll_content)
        sidebar_layout.addWidget(sidebar_scroll, stretch=1)

        # 3. Bottom Fixed: Action Buttons, Capacity Info & Progress (always reachable!)
        self.action_bar = ActionBarWidget()
        sidebar_layout.addWidget(self.action_bar)

        main_splitter.addWidget(sidebar_container)

        # Right Section: Media Workspace (Filters + Views + EXIF Side Inspector)
        workspace_container = QWidget()
        workspace_layout = QVBoxLayout(workspace_container)
        workspace_layout.setContentsMargins(8, 10, 12, 8)
        workspace_layout.setSpacing(8)

        # Filter Bar (with Zoom Slider for Gallery & EXIF Inspector Toggle)
        self.filter_bar = FilterBarWidget()
        workspace_layout.addWidget(self.filter_bar, 0)

        # Workspace horizontal splitter: Left Views Stack, Right EXIF Inspector Panel
        self.workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.workspace_splitter.setChildrenCollapsible(False)
        self.workspace_splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # View Stack (Empty State vs Table vs Gallery vs Destination Tree)
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

        # View 3: Target Directory Simulation Tree View
        self.target_tree_view = MediaTreeView()
        self.view_stack.addWidget(self.target_tree_view)

        self.workspace_splitter.addWidget(self.view_stack)

        # EXIF Metadata & Histogram Inspector side panel (hidden by default)
        self.exif_inspector = ExifInspectorWidget()
        self.exif_inspector.setVisible(False)
        self.workspace_splitter.addWidget(self.exif_inspector)
        self.workspace_splitter.setStretchFactor(0, 1)
        self.workspace_splitter.setStretchFactor(1, 0)

        workspace_layout.addWidget(self.workspace_splitter, 1)
        main_splitter.addWidget(workspace_container)

        # Splitter sizing: Left sidebar ~420px, Right workspace gets rest
        main_splitter.setSizes([420, 860])
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(main_splitter)

        # 4. Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.lbl_status_stats = QLabel("Bereit. Wählen Sie ein Quelllaufwerk und klicken Sie auf 'Scannen'.")
        self.status_bar.addWidget(self.lbl_status_stats, 1)

    def _connect_signals(self):
        # Header signals
        self.header_banner.drive_selected.connect(self._on_header_drive_selected)
        self.header_banner.open_history.connect(self._open_history_dialog)
        self.header_banner.open_help.connect(self._open_help_dialog)

        # Notification banner signals
        self.card_notification.scan_requested.connect(self._on_card_scan_requested)

        # Empty state scan button
        self.empty_state.scan_requested.connect(self._start_scan)

        # Profile selection & management
        self.profile_bar.profile_selected.connect(self._on_profile_selected)
        self.profile_bar.profile_saved.connect(self._on_profile_saved)
        self.profile_bar.profile_created.connect(self._on_profile_created)
        self.profile_bar.profile_deleted.connect(self._on_profile_deleted)

        # Path, Pattern & General Settings changes
        self.path_selector.changed.connect(self._on_settings_changed)
        self.pattern_editor.changed.connect(self._on_settings_changed)
        self.general_settings.changed.connect(self._on_settings_changed)

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
        self.filter_bar.toggle_exif_panel.connect(self._toggle_exif_inspector)
        self.exif_inspector.close_requested.connect(lambda: self.filter_bar.btn_toggle_exif.setChecked(False))

        # Quick Preview requests (Space or Double click)
        self.table_view.open_preview_requested.connect(self._open_quick_preview)
        self.gallery_view.open_preview_requested.connect(self._open_quick_preview)
        self.target_tree_view.open_preview_requested.connect(self._open_quick_preview)

        # Item focus / selection -> EXIF inspector
        self.table_view.clicked.connect(self._on_item_focused)
        self.gallery_view.clicked.connect(self._on_item_focused)
        self.target_tree_view.item_selected.connect(self._on_item_focused)

        # Selection shortcuts
        self.filter_bar.select_all_clicked.connect(self.table_model.select_all)
        self.filter_bar.deselect_all_clicked.connect(self.table_model.deselect_all)
        self.filter_bar.select_new_clicked.connect(self.table_model.select_only_new)

        # Model changes update stats
        self.table_model.selection_changed.connect(self._update_stats_bar)
        self.gallery_view.selection_toggled.connect(self._update_stats_bar)

    def _init_drive_watcher(self):
        if self.config.auto_detect_drives and not self._drive_watcher:
            self._drive_watcher = DriveWatcherThread(interval_sec=2.0, parent=self)
            self._drive_watcher.drive_inserted.connect(self._on_drive_inserted)
            self._drive_watcher.drive_removed.connect(self._on_drive_removed)
            self._drive_watcher.drives_updated.connect(self.header_banner.set_drives)
            self._drive_watcher.start()

    def _on_drive_inserted(self, drive: DriveInfo):
        target_path = str(drive.dcim_path or drive.path)
        self.path_selector.edit_source.setText(target_path)
        if self.config.auto_scan_on_insert:
            self._start_scan()
        else:
            self.card_notification.show_card(drive)

    def _on_drive_removed(self, drive: DriveInfo):
        if self.card_notification.current_drive_path == str(drive.path):
            self.card_notification.hide_card()
        self.status_bar.showMessage(f"Laufwerk '{drive.letter}' wurde entfernt.", 4000)

    def _on_card_scan_requested(self, path: str):
        self.path_selector.edit_source.setText(path)
        self._start_scan()

    def _on_profile_selected(self, name: str):
        if getattr(self, "_is_loading_config", False):
            return
        if self.config.apply_profile(name):
            self._load_config_to_ui()
            self.config.save()
            self._update_stats_bar()

    def _on_profile_saved(self, name: str):
        self.path_selector.sync_to_config(self.config)
        self.pattern_editor.sync_to_config(self.config)
        self.general_settings.sync_to_config(self.config)
        self.config.save_current_as_profile(name)
        self.config.save()

    def _on_profile_created(self, name: str):
        self.path_selector.sync_to_config(self.config)
        self.pattern_editor.sync_to_config(self.config)
        self.general_settings.sync_to_config(self.config)
        self.config.save_current_as_profile(name)
        self.config.save()
        self.profile_bar.load_profiles(self.config)

    def _on_profile_deleted(self, name: str):
        if self.config.delete_profile(name):
            self.config.save()
            self._load_config_to_ui()
            self._update_stats_bar()

    def _open_quick_preview(self, target):
        items = self.table_model.get_items()
        if not items:
            return

        target_item: Optional[ScanItem] = None
        if isinstance(target, ScanItem):
            target_item = target
        elif hasattr(target, "data") and hasattr(target, "isValid"):
            if not target.isValid():
                return
            target_item = target.data(Qt.ItemDataRole.UserRole)

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
        self._is_loading_config = True
        try:
            self.profile_bar.load_profiles(self.config)
            self.path_selector.load_config(self.config)
            self.pattern_editor.load_config(self.config)
            self.general_settings.load_config(self.config)
            self.pattern_editor.update_preview(self.config.type_folder_organization)
        finally:
            self._is_loading_config = False

    def _on_settings_changed(self):
        if getattr(self, "_is_loading_config", False):
            return
        self.path_selector.sync_to_config(self.config)
        self.pattern_editor.sync_to_config(self.config)
        self.general_settings.sync_to_config(self.config)
        if self.config.active_profile in self.config.profiles:
            self.config.save_current_as_profile(self.config.active_profile)
        self.pattern_editor.update_preview(self.config.type_folder_organization)
        self.config.save()
        self._update_stats_bar()

        # Keep destination tree view in sync
        if self.table_model.get_items():
            self.target_tree_view.set_items(self.table_model.get_items(), self.config.target_dir)

        # Update drive watcher running state
        if self.config.auto_detect_drives:
            if not self._drive_watcher or not self._drive_watcher.isRunning():
                self._init_drive_watcher()
        else:
            if self._drive_watcher and self._drive_watcher.isRunning():
                self._drive_watcher.stop()
                self._drive_watcher = None

    def _update_view_selection(self):
        items = self.table_model.get_items()
        if not items:
            self.view_stack.setCurrentWidget(self.empty_state)
            return

        mode = self.filter_bar.combo_view.currentData()
        if mode == "gallery":
            self.view_stack.setCurrentWidget(self.gallery_view)
            self._queue_thumbnails_for_visible()
        elif mode == "tree":
            self.view_stack.setCurrentWidget(self.target_tree_view)
        else:
            self.view_stack.setCurrentWidget(self.table_view)

    def _on_view_mode_changed(self, mode: str):
        self._update_view_selection()

    def _toggle_exif_inspector(self, show: bool):
        self.exif_inspector.setVisible(show)
        if show and not self.exif_inspector._current_item:
            items = self.table_model.get_items()
            if items:
                self.exif_inspector.inspect_item(items[0])

    def _on_item_focused(self, index_or_item):
        target_item: Optional[ScanItem] = None
        if isinstance(index_or_item, ScanItem):
            target_item = index_or_item
        elif hasattr(index_or_item, "data"):
            target_item = index_or_item.data(Qt.ItemDataRole.UserRole)
        if target_item:
            self.exif_inspector.inspect_item(target_item)

    def _update_stats_bar(self):
        items = self.table_model.get_items()
        total = len(items)
        selected = sum(1 for it in items if it.selected)
        new_cnt = sum(1 for it in items if it.status == "Neu")
        dup_cnt = sum(1 for it in items if it.is_duplicate)
        total_bytes = sum(it.total_size for it in items if it.selected)

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
        self.target_tree_view.set_items(items, self.config.target_dir)
        self._update_stats_bar()
        self._update_view_selection()

        if items:
            self.exif_inspector.inspect_item(items[0])

        new_count = sum(1 for it in items if it.status == "Neu")
        self.action_bar.lbl_status.setText(
            f"Scan abgeschlossen: {len(items)} Einheiten gefunden ({new_count} neu)."
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
        if not self.config.target_dir or not target_dir.exists():
            QMessageBox.warning(
                self, "Ungültiger Zielordner",
                f"Der Zielordner '{self.config.target_dir}' existiert nicht."
            )
            return

        selected_items = [it for it in self.table_model.get_items() if it.selected]
        if not selected_items:
            QMessageBox.information(self, "Keine Auswahl", "Es wurden keine Dateien zum Importieren ausgewählt.")
            return

        total_bytes = sum(it.total_size for it in selected_items)
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
            f"✓ {stats.copied_success} Einheiten kopiert ({mb:.1f} MB)"
        ]
        if stats.paired_count > 0:
            msg_lines.append(f"🔗 {stats.paired_count} RAW+JPG Paare synchronisiert")
        if stats.sidecars_copied > 0:
            msg_lines.append(f"📄 {stats.sidecars_copied} XMP-Sidecars übertragen")
        if stats.backup_success > 0:
            msg_lines.append(f"🛡️ {stats.backup_success} Einheiten auf 2. Backup gesichert")
        msg_lines.append(f"⚠️ {stats.duplicates_skipped} Duplikate übersprungen")
        if stats.failed > 0:
            msg_lines.append(f"✕ {stats.failed} Fehler")

        QMessageBox.information(self, "Import abgeschlossen", "\n".join(msg_lines))
        self.action_bar.lbl_status.setText(f"Fertig: {stats.copied_success} Einheiten erfolgreich kopiert ({mb:.1f} MB).")
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
        if self._drive_watcher and self._drive_watcher.isRunning():
            self._drive_watcher.stop()
            self._drive_watcher.wait(1000)
        self._on_settings_changed()
        event.accept()
