"""Dual-Pane Transfer & Archiving View (Tab 3 of FotoDown).

Enables seamless transfer, copying, and moving of photos between
the local working station (PC/Laptop) and network storage (NAS / Family Album).

Features:
- Dual-pane layout: Left (Source) & Right (Destination).
- Identical hierarchical directory tree selection as in Culling (Tab 2) with photo counts (Total, RAW, JPG).
- Powerful filtering: File types (RAW, JPG, Videos), XMP edits, ratings, and instant text search.
- Multi-selection tools: Checkboxes, Single select, Multi-select, Select All, None, Invert.
- View modes: Detailed list view or visual thumbnail grid with adjustable sizes (Small, Medium, Large).
- Safe transfer actions: Copy / Move Selection, Copy / Move All.
- Full companion sidecar synchronization (.xmp) during copy and move operations.
"""

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

from PySide6.QtCore import Qt, Signal, QSize, QThreadPool
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QProgressBar, QPushButton, QSizePolicy, QSplitter, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from core.config import AppConfig
from core.drive_detector import format_size
from core.xmp_sync import read_xmp_workflow_info
from gui_qt.styles.icons import get_folder_icon, get_refresh_icon
from gui_qt.views.culling_tree import CullingDirectoryTreeWidget
from gui_qt.workers.thumb_worker import ThumbnailSignals, ThumbnailTask
from gui_qt.workers.transfer_worker import TransferWorker

RAW_EXTENSIONS = {".orf", ".rw2", ".cr2", ".cr3", ".nef", ".arw", ".dng", ".raf", ".pef"}
JPEG_EXTENSIONS = {".jpg", ".jpeg", ".jpe", ".png", ".webp", ".tif", ".tiff", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v"}
ALL_MEDIA_EXTENSIONS = RAW_EXTENSIONS | JPEG_EXTENSIONS | VIDEO_EXTENSIONS


@dataclass
class TransferItem:
    """Represents a single media item in the transfer view."""
    path: Path
    name: str
    extension: str
    size: int
    mtime: float
    is_raw: bool
    is_jpeg: bool
    is_video: bool
    has_xmp: bool
    rating: int = 0
    workflow_status: str = ""

    @classmethod
    def from_path(cls, file_path: Path) -> "TransferItem":
        ext = file_path.suffix.lower()
        try:
            stat = file_path.stat()
            size = stat.st_size
            mtime = stat.st_mtime
        except OSError:
            size = 0
            mtime = 0.0

        is_raw = ext in RAW_EXTENSIONS
        is_jpeg = ext in JPEG_EXTENSIONS
        is_video = ext in VIDEO_EXTENSIONS

        # Sidecar and workflow status inspection
        has_xmp = False
        rating = 0
        wf_status = ""
        xmp_candidates = [
            file_path.with_name(f"{file_path.name}.xmp"),
            file_path.with_suffix(".xmp")
        ]
        for sc in xmp_candidates:
            if sc != file_path and sc.exists():
                has_xmp = True
                try:
                    info = read_xmp_workflow_info(file_path)
                    rating = info.rating
                    wf_status = info.workflow_status
                except Exception:
                    pass
                break

        return cls(
            path=file_path,
            name=file_path.name,
            extension=ext,
            size=size,
            mtime=mtime,
            is_raw=is_raw,
            is_jpeg=is_jpeg,
            is_video=is_video,
            has_xmp=has_xmp,
            rating=rating,
            workflow_status=wf_status
        )


class TransferPaneWidget(QWidget):
    """File browser pane with hierarchical directory tree, filtering, view modes, and selection tools."""

    folder_changed = Signal(str)
    selection_changed = Signal()

    THUMB_SIZES = {
        "Klein (80px)": 80,
        "Mittel (140px)": 140,
        "Groß (200px)": 200,
    }

    def __init__(self, title: str, is_source: bool, config: AppConfig, parent=None):
        super().__init__(parent)
        self.title_text = title
        self.is_source = is_source
        self.config = config
        self.current_folder: Optional[Path] = None
        self.all_items: List[TransferItem] = []
        self.filtered_items: List[TransferItem] = []
        self._checked_paths: Set[str] = set()
        self._thumb_cache: Dict[str, QPixmap] = {}

        self._thumb_signals = ThumbnailSignals()
        self._thumb_signals.thumbnail_ready.connect(self._on_thumbnail_ready)

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(4)

        # Vertical Splitter: Top = Verzeichnisbaum (Tree Widget), Bottom = Photo / File Content
        self.pane_splitter = QSplitter(Qt.Orientation.Vertical)
        self.pane_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #334155;
                height: 4px;
            }
        """)

        # 1. Directory Tree Widget (Identical to Culling / Tab 2)
        tree_title = f"VERZEICHNISSE ({'QUELLE' if self.is_source else 'ZIEL / NAS'})"
        root_key = "transfer_source_dir" if self.is_source else "transfer_target_dir"
        default_root = None
        if not self.is_source:
            if self.config.nas_archive_dir and Path(self.config.nas_archive_dir).exists():
                default_root = Path(self.config.nas_archive_dir)
            elif self.config.family_album_dir and Path(self.config.family_album_dir).exists():
                default_root = Path(self.config.family_album_dir)

        self.tree_widget = CullingDirectoryTreeWidget(
            config=self.config,
            parent=self,
            title=tree_title,
            config_root_key=root_key,
            default_root=default_root,
            show_collapse_btn=True
        )
        self.tree_widget.folder_selected.connect(self.load_folder)
        self.tree_widget.collapse_panel_requested.connect(self._toggle_tree_visibility)
        self.pane_splitter.addWidget(self.tree_widget)

        # 2. Bottom Content Container: Active Folder Bar + Filter Toolbar + View Stack
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(2, 2, 2, 2)
        content_layout.setSpacing(4)

        # Active Folder Header Card
        folder_card = QFrame()
        folder_card.setStyleSheet("background-color: #1e293b; border-radius: 6px; padding: 4px;")
        f_card_layout = QHBoxLayout(folder_card)
        f_card_layout.setContentsMargins(6, 4, 6, 4)
        f_card_layout.setSpacing(6)

        icon = "💻" if self.is_source else "💾"
        self.lbl_folder_header = QLabel(f"<b>{icon} Kein Ordner gewählt</b>")
        self.lbl_folder_header.setStyleSheet("color: #38bdf8; font-size: 11px;")
        f_card_layout.addWidget(self.lbl_folder_header, stretch=1)

        self.btn_toggle_tree = QPushButton("📂 Baum")
        self.btn_toggle_tree.setToolTip("Verzeichnisbaum oben ein- oder ausblenden")
        self.btn_toggle_tree.setCheckable(True)
        self.btn_toggle_tree.setChecked(True)
        self.btn_toggle_tree.setStyleSheet("""
            QPushButton {
                background-color: #0f172a; border: 1px solid #334155;
                border-radius: 4px; padding: 2px 8px; font-size: 10px; color: #94a3b8;
            }
            QPushButton:checked {
                background-color: #0284c7; color: white; border-color: #38bdf8;
            }
        """)
        self.btn_toggle_tree.clicked.connect(self._on_toggle_tree_clicked)
        f_card_layout.addWidget(self.btn_toggle_tree)

        self.btn_refresh = QPushButton()
        self.btn_refresh.setIcon(get_refresh_icon("#cbd5e1", 12))
        self.btn_refresh.setIconSize(QSize(12, 12))
        self.btn_refresh.setFixedSize(26, 24)
        self.btn_refresh.setToolTip("Ordnerinhalt neu laden")
        self.btn_refresh.clicked.connect(self.refresh)
        f_card_layout.addWidget(self.btn_refresh)

        # Quick access menu button
        self.btn_quick = QPushButton("⚡")
        self.btn_quick.setToolTip("Schnellzugriff auf bekannte Ordner")
        self.btn_quick.setFixedSize(26, 24)
        self.btn_quick.clicked.connect(self._show_quick_menu)
        f_card_layout.addWidget(self.btn_quick)

        content_layout.addWidget(folder_card)

        # Filter & View Toolbar
        filter_card = QFrame()
        filter_card.setStyleSheet("background-color: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 4px;")
        filter_layout = QVBoxLayout(filter_card)
        filter_layout.setContentsMargins(6, 4, 6, 4)
        filter_layout.setSpacing(4)

        # Row 1: Format & Status Filters + Search
        f_row1 = QHBoxLayout()
        f_row1.setSpacing(6)

        f_row1.addWidget(QLabel("Typ:"))
        self.combo_type = QComboBox()
        self.combo_type.addItems(["Alle Medien", "Nur RAW", "Nur JPG", "RAW + JPG", "Nur Videos", "Mit XMP / Bearbeitung"])
        self.combo_type.currentIndexChanged.connect(self.apply_filter)
        f_row1.addWidget(self.combo_type)

        f_row1.addWidget(QLabel("Status:"))
        self.combo_status = QComboBox()
        self.combo_status.addItems(["Alle Status", "Bearbeitet", "SOOC (Unbearb.)", "Bewertet (★+)"])
        self.combo_status.currentIndexChanged.connect(self.apply_filter)
        f_row1.addWidget(self.combo_status)

        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("🔍 Dateiname filtern...")
        self.edit_search.textChanged.connect(self.apply_filter)
        f_row1.addWidget(self.edit_search, 1)

        btn_clear_filter = QPushButton("✖")
        btn_clear_filter.setToolTip("Filter zurücksetzen")
        btn_clear_filter.setFixedWidth(24)
        btn_clear_filter.clicked.connect(self._clear_filters)
        f_row1.addWidget(btn_clear_filter)

        filter_layout.addLayout(f_row1)

        # Row 2: Selection tools & View Mode switcher
        f_row2 = QHBoxLayout()
        f_row2.setSpacing(6)

        btn_sel_all = QPushButton("☑ Alle")
        btn_sel_all.setToolTip("Alle sichtbaren Dateien auswählen")
        btn_sel_all.clicked.connect(self.select_all)
        f_row2.addWidget(btn_sel_all)

        btn_sel_none = QPushButton("☐ Keine")
        btn_sel_none.setToolTip("Auswahl aufheben")
        btn_sel_none.clicked.connect(self.select_none)
        f_row2.addWidget(btn_sel_none)

        btn_sel_inv = QPushButton("🔄 Invertieren")
        btn_sel_inv.setToolTip("Auswahl umkehren")
        btn_sel_inv.clicked.connect(self.invert_selection)
        f_row2.addWidget(btn_sel_inv)

        self.lbl_sel_count = QLabel("0 von 0 markiert (0 B)")
        self.lbl_sel_count.setStyleSheet("color: #94a3b8; font-size: 11px;")
        f_row2.addWidget(self.lbl_sel_count)

        f_row2.addStretch()

        # View Mode Toggle (List vs Grid)
        self.btn_view_list = QPushButton("📋 Liste")
        self.btn_view_list.setCheckable(True)
        self.btn_view_list.setChecked(True)
        self.btn_view_list.clicked.connect(lambda: self.set_view_mode("list"))
        f_row2.addWidget(self.btn_view_list)

        self.btn_view_grid = QPushButton("🖼️ Vorschau")
        self.btn_view_grid.setCheckable(True)
        self.btn_view_grid.setChecked(False)
        self.btn_view_grid.clicked.connect(lambda: self.set_view_mode("grid"))
        f_row2.addWidget(self.btn_view_grid)

        self.combo_thumb_size = QComboBox()
        self.combo_thumb_size.addItems(list(self.THUMB_SIZES.keys()))
        self.combo_thumb_size.setCurrentText("Mittel (140px)")
        self.combo_thumb_size.currentIndexChanged.connect(self._on_thumb_size_changed)
        f_row2.addWidget(self.combo_thumb_size)

        filter_layout.addLayout(f_row2)
        content_layout.addWidget(filter_card)

        # Stacked Views (List View vs Thumbnail Grid)
        self.view_stack = QStackedWidget()

        # Page 0: Detailed Table View
        self.table_view = QTableWidget()
        self.table_view.setColumnCount(6)
        self.table_view.setHorizontalHeaderLabels(["Markiert", "Dateiname", "Typ", "Größe", "Änderungsdatum", "Status / XMP"])
        self.table_view.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table_view.itemChanged.connect(self._on_table_item_changed)
        self.table_view.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.view_stack.addWidget(self.table_view)

        # Page 1: Thumbnail Grid (Icon Mode QListWidget)
        self.list_grid = QListWidget()
        self.list_grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_grid.setMovement(QListWidget.Movement.Static)
        self.list_grid.setSpacing(8)
        self.list_grid.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_grid.setStyleSheet("""
            QListWidget {
                background-color: #0b0f19;
                border: 1px solid #1e293b;
                border-radius: 4px;
            }
            QListWidget::item {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px;
                color: #e2e8f0;
            }
            QListWidget::item:selected {
                background-color: #0284c7;
                border: 1px solid #38bdf8;
            }
        """)
        self.list_grid.itemChanged.connect(self._on_grid_item_changed)
        self.list_grid.itemSelectionChanged.connect(self._on_grid_selection_changed)
        self._update_grid_item_size(140)
        self.view_stack.addWidget(self.list_grid)

        content_layout.addWidget(self.view_stack, 1)
        self.pane_splitter.addWidget(content_container)

        # Splitter sizing: ~220px tree at top, ~480px photo content below
        self.pane_splitter.setSizes([220, 480])
        self.pane_splitter.setStretchFactor(0, 0)
        self.pane_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(self.pane_splitter)

    def _toggle_tree_visibility(self):
        """Toggles tree view visibility via collapse button in tree header."""
        is_vis = not self.tree_widget.isVisible()
        self.tree_widget.setVisible(is_vis)
        self.btn_toggle_tree.setChecked(is_vis)

    def _on_toggle_tree_clicked(self):
        is_checked = self.btn_toggle_tree.isChecked()
        self.tree_widget.setVisible(is_checked)

    def _show_quick_menu(self):
        """Displays quick folder navigation shortcuts."""
        menu = QMenu(self)

        act_culling = menu.addAction("👁️ Letzter Culling-Ordner")
        act_import = menu.addAction("📥 Lokales Import-Ziel")
        menu.addSeparator()
        act_nas = menu.addAction("💾 NAS-Archiv")
        act_family = menu.addAction("👨‍👩‍👧‍👦 Familienalbum")
        menu.addSeparator()
        act_browse = menu.addAction("📁 Beliebigen Ordner öffnen...")
        act_new_folder = menu.addAction("➕ Neuen Unterordner erstellen...")

        action = menu.exec(self.btn_quick.mapToGlobal(self.btn_quick.rect().bottomLeft()))
        if action == act_culling and self.config.culling_last_folder:
            self.load_folder(Path(self.config.culling_last_folder))
        elif action == act_import and self.config.target_dir:
            self.load_folder(Path(self.config.target_dir))
        elif action == act_nas and self.config.nas_archive_dir:
            self.load_folder(Path(self.config.nas_archive_dir))
        elif action == act_family and self.config.family_album_dir:
            self.load_folder(Path(self.config.family_album_dir))
        elif action == act_browse:
            self._browse_folder()
        elif action == act_new_folder and self.current_folder:
            self._create_subfolder()

    def _browse_folder(self):
        start_dir = str(self.current_folder) if self.current_folder and self.current_folder.exists() else (
            self.config.target_dir or str(Path.home())
        )
        folder = QFileDialog.getExistingDirectory(self, f"{self.title_text}: Ordner wählen", start_dir)
        if folder:
            p = Path(folder)
            self.tree_widget.set_root_folder(p)
            self.load_folder(p)

    def _create_subfolder(self):
        """Creates a new subfolder in the current directory."""
        if not self.current_folder or not self.current_folder.exists():
            QMessageBox.warning(self, "Ordner erstellen", "Bitte wählen Sie zuerst einen existierenden Basis-Ordner aus.")
            return

        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Neuer Ordner", f"Neuer Unterordner in:\n{self.current_folder}\n\nName:")
        if ok and name.strip():
            target = self.current_folder / name.strip()
            try:
                target.mkdir(parents=True, exist_ok=True)
                self.tree_widget.refresh()
                self.load_folder(target)
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Ordner konnte nicht erstellt werden: {e}")

    def load_folder(self, folder: Path):
        """Scans the directory for media files and refreshes the views."""
        self.current_folder = Path(folder)
        icon = "💻" if self.is_source else "💾"
        self.lbl_folder_header.setText(f"<b>{icon} {self.current_folder.name}</b> <span style='color: #64748b;'>({self.current_folder})</span>")
        self.lbl_folder_header.setToolTip(str(self.current_folder))

        # Select corresponding node in directory tree
        self.tree_widget.select_folder(self.current_folder)

        self.refresh()
        self.folder_changed.emit(str(self.current_folder))

    def refresh(self):
        """Rescans current folder and updates views."""
        self.all_items.clear()
        if not self.current_folder or not self.current_folder.exists():
            self.filtered_items.clear()
            self._checked_paths.clear()
            self._populate_views()
            self._update_selection_counter()
            return

        try:
            with os.scandir(self.current_folder) as entries:
                for entry in entries:
                    if entry.is_file():
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in ALL_MEDIA_EXTENSIONS:
                            self.all_items.append(TransferItem.from_path(Path(entry.path)))
        except Exception as e:
            QMessageBox.warning(self, "Lesefehler", f"Konnte Ordner nicht lesen: {e}")

        # Sort naturally by name
        self.all_items.sort(key=lambda it: it.name.lower())
        self.apply_filter()

    def apply_filter(self):
        """Applies format, status, and text search filters."""
        query = self.edit_search.text().strip().lower()
        type_idx = self.combo_type.currentIndex()
        status_idx = self.combo_status.currentIndex()

        filtered: List[TransferItem] = []
        for it in self.all_items:
            # Text search
            if query and query not in it.name.lower():
                continue

            # Type filter
            if type_idx == 1 and not it.is_raw:  # Nur RAW
                continue
            elif type_idx == 2 and not it.is_jpeg:  # Nur JPG
                continue
            elif type_idx == 3 and not (it.is_raw or it.is_jpeg):  # RAW + JPG
                continue
            elif type_idx == 4 and not it.is_video:  # Nur Videos
                continue
            elif type_idx == 5 and not it.has_xmp:  # Mit XMP / Bearbeitung
                continue

            # Status filter
            if status_idx == 1 and not (it.has_xmp or it.workflow_status == "EDITED"):  # Bearbeitet
                continue
            elif status_idx == 2 and (it.has_xmp or it.workflow_status == "EDITED"):  # SOOC
                continue
            elif status_idx == 3 and it.rating < 1:  # Bewertet (★+)
                continue

            filtered.append(it)

        self.filtered_items = filtered
        self._populate_views()
        self._update_selection_counter()

    def _clear_filters(self):
        self.edit_search.clear()
        self.combo_type.setCurrentIndex(0)
        self.combo_status.setCurrentIndex(0)

    def set_view_mode(self, mode: str):
        """Toggles between 'list' and 'grid'."""
        if mode == "list":
            self.btn_view_list.setChecked(True)
            self.btn_view_grid.setChecked(False)
            self.view_stack.setCurrentIndex(0)
        else:
            self.btn_view_list.setChecked(False)
            self.btn_view_grid.setChecked(True)
            self.view_stack.setCurrentIndex(1)
            self._request_visible_thumbnails()

    def _on_thumb_size_changed(self):
        size_label = self.combo_thumb_size.currentText()
        thumb_size = self.THUMB_SIZES.get(size_label, 140)
        self._update_grid_item_size(thumb_size)
        if self.view_stack.currentIndex() == 1:
            self._request_visible_thumbnails()

    def _update_grid_item_size(self, thumb_size: int):
        self.list_grid.setIconSize(QSize(thumb_size, thumb_size))
        self.list_grid.setGridSize(QSize(thumb_size + 24, thumb_size + 48))

    def _populate_views(self):
        """Fills both QTableWidget and QListWidget with current filtered items."""
        # 1. Populate Table View
        self.table_view.blockSignals(True)
        self.table_view.setRowCount(len(self.filtered_items))

        for row, it in enumerate(self.filtered_items):
            is_checked = str(it.path) in self._checked_paths

            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            chk_item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
            chk_item.setData(Qt.ItemDataRole.UserRole, str(it.path))
            self.table_view.setItem(row, 0, chk_item)

            name_item = QTableWidgetItem(it.name)
            name_item.setData(Qt.ItemDataRole.UserRole, str(it.path))
            self.table_view.setItem(row, 1, name_item)

            typ_str = "RAW" if it.is_raw else ("JPEG" if it.is_jpeg else ("Video" if it.is_video else it.extension))
            self.table_view.setItem(row, 2, QTableWidgetItem(typ_str))

            self.table_view.setItem(row, 3, QTableWidgetItem(format_size(it.size)))

            dt_str = datetime.fromtimestamp(it.mtime).strftime("%d.%m.%Y %H:%M") if it.mtime else "-"
            self.table_view.setItem(row, 4, QTableWidgetItem(dt_str))

            status_parts = []
            if it.rating > 0:
                status_parts.append(f"{'★' * it.rating}")
            if it.has_xmp:
                status_parts.append("[XMP/Bearb.]")
            status_text = " ".join(status_parts) if status_parts else "SOOC"
            self.table_view.setItem(row, 5, QTableWidgetItem(status_text))

        self.table_view.blockSignals(False)

        # 2. Populate Grid View
        self.list_grid.blockSignals(True)
        self.list_grid.clear()

        default_icon = self._get_placeholder_icon()
        for it in self.filtered_items:
            is_checked = str(it.path) in self._checked_paths
            grid_item = QListWidgetItem()
            grid_item.setText(f"{it.name}\n{format_size(it.size)}")
            grid_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            grid_item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
            grid_item.setData(Qt.ItemDataRole.UserRole, str(it.path))

            # Cached icon or default placeholder
            if str(it.path) in self._thumb_cache:
                grid_item.setIcon(QIcon(self._thumb_cache[str(it.path)]))
            else:
                grid_item.setIcon(default_icon)

            self.list_grid.addItem(grid_item)

        self.list_grid.blockSignals(False)

        if self.view_stack.currentIndex() == 1:
            self._request_visible_thumbnails()

    def _get_placeholder_icon(self) -> QIcon:
        pix = QPixmap(140, 140)
        pix.fill(QColor("#1e293b"))
        return QIcon(pix)

    def _request_visible_thumbnails(self):
        """Asynchronously requests thumbnails for media items in filtered list."""
        size_label = self.combo_thumb_size.currentText()
        thumb_dim = self.THUMB_SIZES.get(size_label, 140)

        thread_pool = QThreadPool.globalInstance()
        for it in self.filtered_items[:150]:  # batch of visible / top items
            path_str = str(it.path)
            if path_str not in self._thumb_cache:
                task = ThumbnailTask(
                    path=it.path,
                    key_path=path_str,
                    signals=self._thumb_signals,
                    max_size=(thumb_dim, thumb_dim)
                )
                thread_pool.start(task)

    def _on_thumbnail_ready(self, path_str: str, qimage: QImage):
        """Callback when background thumbnail loader finishes an item."""
        pixmap = QPixmap.fromImage(qimage)
        self._thumb_cache[path_str] = pixmap

        for idx in range(self.list_grid.count()):
            item = self.list_grid.item(idx)
            if item.data(Qt.ItemDataRole.UserRole) == path_str:
                item.setIcon(QIcon(pixmap))
                break

    def _on_table_item_changed(self, item: QTableWidgetItem):
        if item.column() == 0:
            path_str = item.data(Qt.ItemDataRole.UserRole)
            if item.checkState() == Qt.CheckState.Checked:
                self._checked_paths.add(path_str)
            else:
                self._checked_paths.discard(path_str)
            self._sync_check_to_grid(path_str, item.checkState())
            self._update_selection_counter()

    def _on_grid_item_changed(self, item: QListWidgetItem):
        path_str = item.data(Qt.ItemDataRole.UserRole)
        if item.checkState() == Qt.CheckState.Checked:
            self._checked_paths.add(path_str)
        else:
            self._checked_paths.discard(path_str)
        self._sync_check_to_table(path_str, item.checkState())
        self._update_selection_counter()

    def _on_table_selection_changed(self):
        self.selection_changed.emit()

    def _on_grid_selection_changed(self):
        self.selection_changed.emit()

    def _sync_check_to_grid(self, path_str: str, state: Qt.CheckState):
        self.list_grid.blockSignals(True)
        for idx in range(self.list_grid.count()):
            item = self.list_grid.item(idx)
            if item.data(Qt.ItemDataRole.UserRole) == path_str:
                item.setCheckState(state)
                break
        self.list_grid.blockSignals(False)

    def _sync_check_to_table(self, path_str: str, state: Qt.CheckState):
        self.table_view.blockSignals(True)
        for row in range(self.table_view.rowCount()):
            item = self.table_view.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == path_str:
                item.setCheckState(state)
                break
        self.table_view.blockSignals(False)

    def select_all(self):
        """Marks all currently filtered items as checked."""
        for it in self.filtered_items:
            self._checked_paths.add(str(it.path))
        self._populate_views()
        self._update_selection_counter()

    def select_none(self):
        """Unchecks all items."""
        self._checked_paths.clear()
        self._populate_views()
        self._update_selection_counter()

    def invert_selection(self):
        """Inverts check state of all currently filtered items."""
        for it in self.filtered_items:
            p = str(it.path)
            if p in self._checked_paths:
                self._checked_paths.discard(p)
            else:
                self._checked_paths.add(p)
        self._populate_views()
        self._update_selection_counter()

    def _update_selection_counter(self):
        total_cnt = len(self.filtered_items)
        marked_items = [it for it in self.filtered_items if str(it.path) in self._checked_paths]
        marked_cnt = len(marked_items)
        marked_bytes = sum(it.size for it in marked_items)

        self.lbl_sel_count.setText(f"{marked_cnt} von {total_cnt} markiert ({format_size(marked_bytes)})")
        self.selection_changed.emit()

    def get_effective_selected_paths(self) -> List[Path]:
        """Returns explicitly checked items, or row-selected items if none checked."""
        if self._checked_paths:
            return [Path(p) for p in self._checked_paths if Path(p).exists()]

        # Fallback to visual selection in current view
        paths: List[Path] = []
        if self.view_stack.currentIndex() == 0:
            for item in self.table_view.selectedItems():
                if item.column() == 1:
                    p = item.data(Qt.ItemDataRole.UserRole)
                    if p and Path(p) not in paths:
                        paths.append(Path(p))
        else:
            for item in self.list_grid.selectedItems():
                p = item.data(Qt.ItemDataRole.UserRole)
                if p and Path(p) not in paths:
                    paths.append(Path(p))
        return paths

    def get_all_filtered_paths(self) -> List[Path]:
        """Returns all paths matching the current filter."""
        return [it.path for it in self.filtered_items if it.path.exists()]


class TransferTabView(QWidget):
    """Tab 3: Dual-Pane Sichern & Archivieren workflow view."""

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._active_worker: Optional[TransferWorker] = None
        self._init_ui()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #334155;
                width: 4px;
            }
        """)

        # Left Pane: Source (PC / Laptop)
        self.pane_source = TransferPaneWidget(
            title="Laptop / Lokale Bearbeitung (Quelle)",
            is_source=True,
            config=self.config
        )
        splitter.addWidget(self.pane_source)

        # Center Column: Action Controls and Progress
        self.center_panel = QFrame()
        self.center_panel.setObjectName("cardFrame")
        self.center_panel.setFixedWidth(200)
        self.center_panel.setStyleSheet("background-color: #0b0f19; border: 1px solid #1e293b; border-radius: 8px;")

        center_layout = QVBoxLayout(self.center_panel)
        center_layout.setContentsMargins(8, 16, 8, 16)
        center_layout.setSpacing(10)

        lbl_actions = QLabel("AKTIONEN")
        lbl_actions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_actions.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px; letter-spacing: 1px;")
        center_layout.addWidget(lbl_actions)

        # Action: Copy Selection
        self.btn_copy_sel = QPushButton("▶ Kopieren (Auswahl)")
        self.btn_copy_sel.setToolTip("Markierte Fotos von links nach rechts kopieren")
        self.btn_copy_sel.setStyleSheet("""
            QPushButton {
                background-color: #0284c7; color: white; font-weight: bold;
                border-radius: 5px; padding: 8px 6px; font-size: 11px;
            }
            QPushButton:hover { background-color: #0369a1; }
            QPushButton:disabled { background-color: #334155; color: #64748b; }
        """)
        self.btn_copy_sel.clicked.connect(self._transfer_selected_copy)
        center_layout.addWidget(self.btn_copy_sel)

        # Action: Move Selection
        self.btn_move_sel = QPushButton("➔ Verschieben (Auswahl)")
        self.btn_move_sel.setToolTip("Markierte Fotos verschieben (Quelle wird nach Transfer gelöscht)")
        self.btn_move_sel.setStyleSheet("""
            QPushButton {
                background-color: #0d9488; color: white; font-weight: bold;
                border-radius: 5px; padding: 8px 6px; font-size: 11px;
            }
            QPushButton:hover { background-color: #0f766e; }
            QPushButton:disabled { background-color: #334155; color: #64748b; }
        """)
        self.btn_move_sel.clicked.connect(self._transfer_selected_move)
        center_layout.addWidget(self.btn_move_sel)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #334155; margin: 4px 0;")
        center_layout.addWidget(sep)

        # Action: Copy All
        self.btn_copy_all = QPushButton("▶▶ Alle kopieren")
        self.btn_copy_all.setToolTip("Alle gefilterten Fotos von links nach rechts kopieren")
        self.btn_copy_all.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; color: #38bdf8; border: 1px solid #0284c7;
                font-weight: 600; border-radius: 5px; padding: 6px; font-size: 11px;
            }
            QPushButton:hover { background-color: #0284c7; color: white; }
            QPushButton:disabled { background-color: #1e293b; color: #475569; border-color: #334155; }
        """)
        self.btn_copy_all.clicked.connect(self._transfer_all_copy)
        center_layout.addWidget(self.btn_copy_all)

        # Action: Move All
        self.btn_move_all = QPushButton("➔➔ Alle verschieben")
        self.btn_move_all.setToolTip("Alle gefilterten Fotos verschieben (vom Laptop löschen)")
        self.btn_move_all.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; color: #2dd4bf; border: 1px solid #0d9488;
                font-weight: 600; border-radius: 5px; padding: 6px; font-size: 11px;
            }
            QPushButton:hover { background-color: #0d9488; color: white; }
            QPushButton:disabled { background-color: #1e293b; color: #475569; border-color: #334155; }
        """)
        self.btn_move_all.clicked.connect(self._transfer_all_move)
        center_layout.addWidget(self.btn_move_all)

        # Swap sides button
        self.btn_swap = QPushButton("⇄ Seiten tauschen")
        self.btn_swap.setToolTip("Tauscht die Ordner von Quelle und Ziel")
        self.btn_swap.setStyleSheet("background-color: #1e293b; color: #94a3b8; font-size: 10px; padding: 4px; border: 1px solid #334155;")
        self.btn_swap.clicked.connect(self._swap_folders)
        center_layout.addWidget(self.btn_swap)

        center_layout.addStretch()

        # Progress / Status Section (Visible during transfer)
        self.progress_frame = QFrame()
        self.progress_frame.setStyleSheet("background-color: #1e293b; border-radius: 6px; padding: 6px;")
        self.progress_frame.setVisible(False)
        p_layout = QVBoxLayout(self.progress_frame)
        p_layout.setContentsMargins(4, 4, 4, 4)
        p_layout.setSpacing(4)

        self.lbl_progress = QLabel("Übertrage...")
        self.lbl_progress.setWordWrap(True)
        self.lbl_progress.setStyleSheet("color: #38bdf8; font-size: 10px; font-weight: bold;")
        p_layout.addWidget(self.lbl_progress)

        self.bar_progress = QProgressBar()
        self.bar_progress.setFixedHeight(12)
        self.bar_progress.setTextVisible(False)
        self.bar_progress.setStyleSheet("""
            QProgressBar {
                background-color: #0b0f19; border: 1px solid #334155; border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #0284c7; border-radius: 2px;
            }
        """)
        p_layout.addWidget(self.bar_progress)

        self.btn_cancel_transfer = QPushButton("✕ Abbrechen")
        self.btn_cancel_transfer.setStyleSheet("background-color: #ef4444; color: white; font-size: 10px; padding: 3px;")
        self.btn_cancel_transfer.clicked.connect(self._cancel_transfer)
        p_layout.addWidget(self.btn_cancel_transfer)

        center_layout.addWidget(self.progress_frame)

        splitter.addWidget(self.center_panel)

        # Right Pane: Destination (NAS / Archive)
        self.pane_dest = TransferPaneWidget(
            title="Speicher (NAS / Archiv / Album)",
            is_source=False,
            config=self.config
        )
        splitter.addWidget(self.pane_dest)

        # Sizing: Source ~45%, Center ~10%, Dest ~45%
        splitter.setSizes([450, 180, 450])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setStretchFactor(2, 1)

        main_layout.addWidget(splitter)

        # Listen to selection changes to update button states
        self.pane_source.selection_changed.connect(self._update_action_states)
        self.pane_dest.selection_changed.connect(self._update_action_states)
        self._update_action_states()

    def refresh_defaults(self):
        """Loads default directories from configuration if not yet loaded."""
        if not self.pane_source.current_folder:
            src = Path(self.config.culling_last_folder) if (self.config.culling_last_folder and Path(self.config.culling_last_folder).exists()) else (
                Path(self.config.culling_root_folder) if (self.config.culling_root_folder and Path(self.config.culling_root_folder).exists()) else (
                    Path(self.config.target_dir) if (self.config.target_dir and Path(self.config.target_dir).exists()) else Path.home() / "Pictures"
                )
            )
            if src.exists():
                self.pane_source.load_folder(src)

        if not self.pane_dest.current_folder:
            dst = Path(self.config.nas_archive_dir) if (self.config.nas_archive_dir and Path(self.config.nas_archive_dir).exists()) else (
                Path(self.config.family_album_dir) if (self.config.family_album_dir and Path(self.config.family_album_dir).exists()) else None
            )
            if dst and dst.exists():
                self.pane_dest.load_folder(dst)

    def _swap_folders(self):
        """Swaps source and destination folder paths."""
        src = self.pane_source.current_folder
        dst = self.pane_dest.current_folder
        if src and dst:
            self.pane_source.load_folder(dst)
            self.pane_dest.load_folder(src)

    def _update_action_states(self):
        has_sel = len(self.pane_source.get_effective_selected_paths()) > 0
        has_filtered = len(self.pane_source.get_all_filtered_paths()) > 0
        has_dest = bool(self.pane_dest.current_folder and self.pane_dest.current_folder.exists())

        self.btn_copy_sel.setEnabled(has_sel and has_dest)
        self.btn_move_sel.setEnabled(has_sel and has_dest)
        self.btn_copy_all.setEnabled(has_filtered and has_dest)
        self.btn_move_all.setEnabled(has_filtered and has_dest)

    def _transfer_selected_copy(self):
        files = self.pane_source.get_effective_selected_paths()
        self._start_transfer(files, operation="copy")

    def _transfer_selected_move(self):
        files = self.pane_source.get_effective_selected_paths()
        if not files:
            return
        ret = QMessageBox.question(
            self,
            "Fotos verschieben",
            f"Möchten Sie {len(files)} Datei(en) wirklich nach:\n{self.pane_dest.current_folder}\n\nverschieben? "
            f"(Die Dateien werden nach erfolgreicher Sicherung vom Laptop gelöscht)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ret == QMessageBox.StandardButton.Yes:
            self._start_transfer(files, operation="move")

    def _transfer_all_copy(self):
        files = self.pane_source.get_all_filtered_paths()
        self._start_transfer(files, operation="copy")

    def _transfer_all_move(self):
        files = self.pane_source.get_all_filtered_paths()
        if not files:
            return
        ret = QMessageBox.question(
            self,
            "Alle gefilterten Fotos verschieben",
            f"Möchten Sie ALLE {len(files)} aktuell gefilterten Datei(en) nach:\n{self.pane_dest.current_folder}\n\nverschieben? "
            f"(Die Quelldateien am Laptop werden gelöscht!)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ret == QMessageBox.StandardButton.Yes:
            self._start_transfer(files, operation="move")

    def _start_transfer(self, files: List[Path], operation: str):
        if not files:
            QMessageBox.information(self, "Keine Auswahl", "Bitte wählen Sie zuerst Dateien zum Übertragen aus.")
            return

        dest = self.pane_dest.current_folder
        if not dest or not dest.exists():
            QMessageBox.warning(self, "Kein Zielordner", "Bitte wählen Sie auf der rechten Seite einen gültigen Zielordner aus.")
            return

        # Prepare UI for active transfer
        self._set_buttons_transferring(True)
        self.progress_frame.setVisible(True)
        self.bar_progress.setValue(0)
        self.bar_progress.setMaximum(len(files))
        op_text = "Kopiere" if operation == "copy" else "Verschiebe"
        self.lbl_progress.setText(f"{op_text} 0/{len(files)}...")

        self._active_worker = TransferWorker(
            files=files,
            destination_dir=dest,
            operation=operation,
            sync_sidecars=self.config.sync_xmp_sidecars
        )
        self._active_worker.progress.connect(self._on_transfer_progress)
        self._active_worker.transfer_finished.connect(self._on_transfer_finished)
        self._active_worker.error.connect(self._on_transfer_error)
        self._active_worker.start()

    def _on_transfer_progress(self, current: int, total: int, filename: str):
        self.bar_progress.setValue(current)
        self.lbl_progress.setText(f"{current}/{total}: {filename}")

    def _cancel_transfer(self):
        if self._active_worker and self._active_worker.isRunning():
            self._active_worker.cancel()
            self.lbl_progress.setText("Breche ab...")

    def _on_transfer_finished(self, success_cnt: int, error_cnt: int, total_bytes: int, errors: list):
        self.progress_frame.setVisible(False)
        self._set_buttons_transferring(False)

        # Refresh both panes to reflect new state
        self.pane_source.refresh()
        self.pane_dest.refresh()
        self.pane_source.tree_widget.refresh()
        self.pane_dest.tree_widget.refresh()

        if error_cnt == 0:
            QMessageBox.information(
                self,
                "Übertragung erfolgreich",
                f"{success_cnt} Datei(en) erfolgreich übertragen ({format_size(total_bytes)})."
            )
        else:
            err_sample = "\n".join(errors[:5])
            QMessageBox.warning(
                self,
                "Übertragung mit Fehlern abgeschlossen",
                f"{success_cnt} erfolgreich, {error_cnt} fehlgeschlagen.\n\nFehler:\n{err_sample}"
            )

    def _on_transfer_error(self, message: str):
        self.progress_frame.setVisible(False)
        self._set_buttons_transferring(False)
        QMessageBox.critical(self, "Übertragungsfehler", message)

    def _set_buttons_transferring(self, is_running: bool):
        self.btn_copy_sel.setEnabled(not is_running)
        self.btn_move_sel.setEnabled(not is_running)
        self.btn_copy_all.setEnabled(not is_running)
        self.btn_move_all.setEnabled(not is_running)
        self.btn_swap.setEnabled(not is_running)
        if not is_running:
            self._update_action_states()
