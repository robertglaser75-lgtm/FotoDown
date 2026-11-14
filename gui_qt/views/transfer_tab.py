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

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import hashlib
import os
from pathlib import Path
from typing import Counter as CounterType, Dict, List, Optional, Set, Tuple, Union

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
from core.exif_reader import extract_metadata
from core.xmp_sync import read_xmp_workflow_info
from gui_qt.styles.icons import (
    get_arrow_right_icon, get_check_all_icon, get_clear_icon, get_files_icon,
    get_folder_icon, get_gear_icon, get_grid_icon, get_invert_icon, get_list_icon,
    get_move_icon, get_quick_icon, get_refresh_icon, get_search_icon,
    get_sort_icon, get_swap_icon, get_uncheck_all_icon
)
from gui_qt.views.culling_tree import CullingDirectoryTreeWidget
from gui_qt.workers.thumb_worker import ThumbnailSignals, ThumbnailTask
from gui_qt.workers.transfer_worker import TransferWorker

RAW_EXTENSIONS = {".orf", ".rw2", ".cr2", ".cr3", ".nef", ".arw", ".dng", ".raf", ".pef"}
JPEG_EXTENSIONS = {".jpg", ".jpeg", ".jpe", ".png", ".webp", ".tif", ".tiff", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v"}
ALL_MEDIA_EXTENSIONS = RAW_EXTENSIONS | JPEG_EXTENSIONS | VIDEO_EXTENSIONS


def compute_file_sha256(file_path: Path, chunk_size: int = 65536) -> str:
    """Computes SHA-256 hash of a file for exact bit-level matching."""
    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""


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
        self._last_tree_width: int = 190
        self._last_files_width: int = 420
        self._show_files: bool = True

        self._thumb_signals = ThumbnailSignals()
        self._thumb_signals.thumbnail_ready.connect(self._on_thumbnail_ready)

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(4)

        # Top Active Folder Header Card (Always visible above splitter so Tree & Files toggles remain accessible)
        folder_card = QFrame()
        folder_card.setStyleSheet("background-color: #1e293b; border-radius: 6px; padding: 3px;")
        f_card_layout = QHBoxLayout(folder_card)
        f_card_layout.setContentsMargins(6, 3, 6, 3)
        f_card_layout.setSpacing(4)

        self.lbl_folder_header = QLabel("<b>Kein Ordner gewählt</b>")
        self.lbl_folder_header.setStyleSheet("color: #38bdf8; font-size: 11px;")
        f_card_layout.addWidget(self.lbl_folder_header, stretch=1)

        toggle_btn_style = """
            QPushButton {
                background-color: #0f172a; border: 1px solid #334155;
                border-radius: 4px; padding: 2px 7px; font-size: 10px; color: #94a3b8;
            }
            QPushButton:checked {
                background-color: #0284c7; color: white; border-color: #38bdf8;
            }
        """

        self.btn_toggle_tree = QPushButton("Baum")
        self.btn_toggle_tree.setIcon(get_folder_icon("#cbd5e1", 12))
        self.btn_toggle_tree.setIconSize(QSize(12, 12))
        self.btn_toggle_tree.setToolTip("Verzeichnisbaum links ein- oder ausblenden")
        self.btn_toggle_tree.setCheckable(True)
        self.btn_toggle_tree.setChecked(True)
        self.btn_toggle_tree.setStyleSheet(toggle_btn_style)
        self.btn_toggle_tree.clicked.connect(self._on_toggle_tree_clicked)
        f_card_layout.addWidget(self.btn_toggle_tree)

        self.btn_toggle_files = QPushButton("Dateien")
        self.btn_toggle_files.setIcon(get_files_icon("#cbd5e1", 12))
        self.btn_toggle_files.setIconSize(QSize(12, 12))
        self.btn_toggle_files.setToolTip("Anzeige der Dateien in den Ordnern ein- oder ausschalten")
        self.btn_toggle_files.setCheckable(True)
        self.btn_toggle_files.setChecked(True)
        self.btn_toggle_files.setStyleSheet(toggle_btn_style)
        self.btn_toggle_files.clicked.connect(self._on_toggle_files_clicked)
        f_card_layout.addWidget(self.btn_toggle_files)

        self.btn_refresh = QPushButton()
        self.btn_refresh.setIcon(get_refresh_icon("#cbd5e1", 13))
        self.btn_refresh.setIconSize(QSize(13, 13))
        self.btn_refresh.setFixedSize(26, 22)
        self.btn_refresh.setToolTip("Ordnerinhalt neu laden")
        self.btn_refresh.clicked.connect(self.refresh)
        f_card_layout.addWidget(self.btn_refresh)

        # Quick access menu button
        self.btn_quick = QPushButton()
        self.btn_quick.setIcon(get_quick_icon("#fbbf24", 13))
        self.btn_quick.setIconSize(QSize(13, 13))
        self.btn_quick.setToolTip("Schnellzugriff auf bekannte Ordner")
        self.btn_quick.setFixedSize(26, 22)
        self.btn_quick.clicked.connect(self._show_quick_menu)
        f_card_layout.addWidget(self.btn_quick)

        main_layout.addWidget(folder_card)

        # Horizontal Splitter: Left = Verzeichnisbaum (Tree Widget), Right = Photo / File Content
        self.pane_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.pane_splitter.setChildrenCollapsible(False)
        self.pane_splitter.setHandleWidth(6)
        self.pane_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #334155;
                border-radius: 2px;
            }
            QSplitter::handle:hover {
                background-color: #38bdf8;
            }
        """)
        self.pane_splitter.splitterMoved.connect(self._on_splitter_moved)

        # 1. Directory Tree Widget on Left side (Identical to Culling / Tab 2)
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
        self.tree_widget.setMinimumWidth(120)
        self.tree_widget.folder_selected.connect(self.load_folder)
        self.tree_widget.collapse_panel_requested.connect(self._toggle_tree_visibility)
        self.pane_splitter.addWidget(self.tree_widget)

        # 2. Files Container: Compact 2-Row Filter/Sort/View Toolbar + View Stack
        self.files_container = QWidget()
        self.files_container.setMinimumWidth(160)
        content_layout = QVBoxLayout(self.files_container)
        content_layout.setContentsMargins(2, 2, 2, 2)
        content_layout.setSpacing(4)

        filter_card = QFrame()
        filter_card.setStyleSheet("background-color: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 3px;")
        filter_layout = QVBoxLayout(filter_card)
        filter_layout.setContentsMargins(5, 4, 5, 4)
        filter_layout.setSpacing(4)

        # Row 1: Search, Type Filter, Status Filter, Clear
        f_row1 = QHBoxLayout()
        f_row1.setSpacing(4)

        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Dateiname filtern...")
        self.edit_search.textChanged.connect(self.apply_filter)
        f_row1.addWidget(self.edit_search, 1)

        self.combo_type = QComboBox()
        self.combo_type.setToolTip("Dateiformat filtern")
        self.combo_type.addItems(["Alle Medien", "Nur RAW", "Nur JPG", "RAW + JPG", "Nur Videos", "Mit XMP"])
        self.combo_type.currentIndexChanged.connect(self.apply_filter)
        f_row1.addWidget(self.combo_type)

        self.combo_status = QComboBox()
        self.combo_status.setToolTip("Bearbeitungsstatus filtern")
        self.combo_status.addItems(["Alle Status", "Bearbeitet", "SOOC", "Bewertet ★+"])
        self.combo_status.currentIndexChanged.connect(self.apply_filter)
        f_row1.addWidget(self.combo_status)

        btn_clear_filter = QPushButton()
        btn_clear_filter.setIcon(get_clear_icon("#94a3b8", 12))
        btn_clear_filter.setIconSize(QSize(12, 12))
        btn_clear_filter.setToolTip("Filter zurücksetzen")
        btn_clear_filter.setFixedSize(24, 22)
        btn_clear_filter.clicked.connect(self._clear_filters)
        f_row1.addWidget(btn_clear_filter)

        filter_layout.addLayout(f_row1)

        # Row 2: Compact Icon Selection Tools + Counter + Sort + View Mode Dropdown
        f_row2 = QHBoxLayout()
        f_row2.setSpacing(4)

        compact_tool_style = """
            QPushButton {
                background-color: #1e293b; border: 1px solid #334155;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #334155; border-color: #38bdf8; }
        """

        btn_sel_all = QPushButton()
        btn_sel_all.setIcon(get_check_all_icon("#38bdf8", 13))
        btn_sel_all.setIconSize(QSize(13, 13))
        btn_sel_all.setFixedSize(26, 22)
        btn_sel_all.setToolTip("Alle sichtbaren Dateien markieren")
        btn_sel_all.setStyleSheet(compact_tool_style)
        btn_sel_all.clicked.connect(self.select_all)
        f_row2.addWidget(btn_sel_all)

        btn_sel_none = QPushButton()
        btn_sel_none.setIcon(get_uncheck_all_icon("#94a3b8", 13))
        btn_sel_none.setIconSize(QSize(13, 13))
        btn_sel_none.setFixedSize(26, 22)
        btn_sel_none.setToolTip("Auswahl aufheben")
        btn_sel_none.setStyleSheet(compact_tool_style)
        btn_sel_none.clicked.connect(self.select_none)
        f_row2.addWidget(btn_sel_none)

        btn_sel_inv = QPushButton()
        btn_sel_inv.setIcon(get_invert_icon("#cbd5e1", 13))
        btn_sel_inv.setIconSize(QSize(13, 13))
        btn_sel_inv.setFixedSize(26, 22)
        btn_sel_inv.setToolTip("Auswahl umkehren")
        btn_sel_inv.setStyleSheet(compact_tool_style)
        btn_sel_inv.clicked.connect(self.invert_selection)
        f_row2.addWidget(btn_sel_inv)

        self.lbl_sel_count = QLabel("0/0 (0 B)")
        self.lbl_sel_count.setToolTip("0 von 0 markiert (0 B)")
        self.lbl_sel_count.setStyleSheet("color: #94a3b8; font-size: 10px;")
        f_row2.addWidget(self.lbl_sel_count, 1)

        self.combo_sort = QComboBox()
        self.combo_sort.setToolTip("Sortierkriterium wählen")
        self.combo_sort.addItem("Name", "name")
        self.combo_sort.addItem("Datum", "mtime")
        self.combo_sort.addItem("Größe", "size")
        self.combo_sort.addItem("Dateityp", "type")
        self.combo_sort.addItem("Bewertung", "rating")
        self.combo_sort.currentIndexChanged.connect(self.apply_filter)
        f_row2.addWidget(self.combo_sort)

        self.btn_sort_dir = QPushButton()
        self.btn_sort_dir.setIcon(get_sort_icon(False, "#cbd5e1", 13))
        self.btn_sort_dir.setIconSize(QSize(13, 13))
        self.btn_sort_dir.setFixedSize(26, 22)
        self.btn_sort_dir.setCheckable(True)
        self.btn_sort_dir.setChecked(False)
        self.btn_sort_dir.setToolTip("Sortierung: Aufsteigend (Klicken für Absteigend)")
        self.btn_sort_dir.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; border: 1px solid #334155; border-radius: 3px;
            }
            QPushButton:checked {
                background-color: #0284c7; border-color: #38bdf8;
            }
        """)
        self.btn_sort_dir.clicked.connect(self._on_sort_dir_toggled)
        f_row2.addWidget(self.btn_sort_dir)

        # Single Configurable Display Mode Dropdown (replaces multiple view/size buttons)
        self.combo_view_mode = QComboBox()
        self.combo_view_mode.setToolTip("Darstellungsart & Vorschaugröße wählen")
        self.combo_view_mode.addItem(get_list_icon("#cbd5e1", 13), "Liste", "list")
        self.combo_view_mode.addItem(get_grid_icon("#cbd5e1", 13), "Vorschau: Klein", "grid:80")
        self.combo_view_mode.addItem(get_grid_icon("#cbd5e1", 13), "Vorschau: Mittel", "grid:140")
        self.combo_view_mode.addItem(get_grid_icon("#cbd5e1", 13), "Vorschau: Groß", "grid:200")
        self.combo_view_mode.currentIndexChanged.connect(self._on_view_mode_combo_changed)
        f_row2.addWidget(self.combo_view_mode)

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
        self.table_view.horizontalHeader().sectionClicked.connect(self._on_table_header_clicked)
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
        self.pane_splitter.addWidget(self.files_container)

        # Splitter sizing: Left = ~190px tree on left side, Right = photo content gets remaining space
        self.pane_splitter.setSizes([190, 420])
        self.pane_splitter.setStretchFactor(0, 0)
        self.pane_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(self.pane_splitter, 1)

    def _on_splitter_moved(self, pos: int, index: int):
        """Stores valid non-zero widths and keeps toggle buttons synced."""
        sizes = self.pane_splitter.sizes()
        if len(sizes) >= 2:
            if sizes[0] > 0:
                self._last_tree_width = sizes[0]
            if sizes[1] > 0:
                self._last_files_width = sizes[1]
            self.btn_toggle_tree.setChecked(sizes[0] > 0 and not self.tree_widget.isHidden())
            self.btn_toggle_files.setChecked(sizes[1] > 0 and not self.files_container.isHidden())

    def _set_tree_visible(self, visible: bool):
        """Shows or hides the directory tree and ensures non-zero splitter sizing on restore."""
        if not visible:
            sizes = self.pane_splitter.sizes()
            if sizes and sizes[0] > 0:
                self._last_tree_width = sizes[0]
            self.tree_widget.setVisible(False)
            self.btn_toggle_tree.setChecked(False)
        else:
            self.tree_widget.setVisible(True)
            self.btn_toggle_tree.setChecked(True)
            restore_w = max(180, self._last_tree_width)
            files_w = max(180, self._last_files_width) if self._show_files else 0
            total_w = max(restore_w + files_w, sum(self.pane_splitter.sizes()), self.width())
            if self._show_files:
                self.pane_splitter.setSizes([restore_w, max(180, total_w - restore_w)])
            else:
                self.pane_splitter.setSizes([total_w, 0])

    def _toggle_tree_visibility(self):
        """Toggles tree view visibility via collapse button in tree header."""
        sizes = self.pane_splitter.sizes()
        currently_visible = (not self.tree_widget.isHidden()) and (not sizes or sizes[0] > 0)
        self._set_tree_visible(not currently_visible)

    def _on_toggle_tree_clicked(self):
        self._set_tree_visible(self.btn_toggle_tree.isChecked())

    def _set_files_visible(self, visible: bool):
        """Shows or hides the file listing/preview area for folders."""
        self._show_files = bool(visible)
        self.btn_toggle_files.setChecked(self._show_files)
        if not self._show_files:
            sizes = self.pane_splitter.sizes()
            if len(sizes) >= 2 and sizes[1] > 0:
                self._last_files_width = sizes[1]
            self.files_container.setVisible(False)
        else:
            self.files_container.setVisible(True)
            restore_files_w = max(220, self._last_files_width)
            tree_w = max(160, self._last_tree_width) if not self.tree_widget.isHidden() else 0
            total_w = max(tree_w + restore_files_w, sum(self.pane_splitter.sizes()), self.width())
            if not self.tree_widget.isHidden():
                self.pane_splitter.setSizes([max(140, total_w - restore_files_w), restore_files_w])
            else:
                self.pane_splitter.setSizes([0, total_w])
            self.refresh(force_scan=True)

    def _on_toggle_files_clicked(self):
        self._set_files_visible(self.btn_toggle_files.isChecked())

    def _on_sort_dir_toggled(self):
        """Updates sort direction icon/tooltip and re-sorts current items."""
        is_desc = self.btn_sort_dir.isChecked()
        self.btn_sort_dir.setIcon(get_sort_icon(is_desc, "#ffffff" if is_desc else "#cbd5e1", 13))
        if is_desc:
            self.btn_sort_dir.setToolTip("Sortierung: Absteigend (Klicken für Aufsteigend)")
        else:
            self.btn_sort_dir.setToolTip("Sortierung: Aufsteigend (Klicken für Absteigend)")
        self.apply_filter()

    def _on_table_header_clicked(self, column: int):
        """Allows sorting both list and preview views by clicking table column headers."""
        col_map = {1: "name", 2: "type", 3: "size", 4: "mtime", 5: "rating"}
        sort_key = col_map.get(column)
        if not sort_key:
            return
        if self.combo_sort.currentData() == sort_key:
            self.btn_sort_dir.setChecked(not self.btn_sort_dir.isChecked())
        else:
            idx = self.combo_sort.findData(sort_key)
            if idx >= 0:
                self.combo_sort.blockSignals(True)
                self.combo_sort.setCurrentIndex(idx)
                self.combo_sort.blockSignals(False)
            self.btn_sort_dir.setChecked(False)
        self._on_sort_dir_toggled()

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

    def refresh(self, force_scan: bool = False):
        """Rescans current folder and updates views (unless file display is turned off)."""
        self.all_items.clear()
        if not self.current_folder or not self.current_folder.exists():
            self.filtered_items.clear()
            self._checked_paths.clear()
            self._populate_views()
            self._update_selection_counter()
            return

        if not self._show_files and not force_scan:
            self.filtered_items.clear()
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

        self.apply_filter()

    def _sort_items(self, items: List[TransferItem]) -> List[TransferItem]:
        """Sorts filtered items according to selected sort field and direction."""
        sort_key = self.combo_sort.currentData() or "name"
        descending = self.btn_sort_dir.isChecked()

        if sort_key == "mtime":
            key_fn = lambda it: (it.mtime, it.name.lower())
        elif sort_key == "size":
            key_fn = lambda it: (it.size, it.name.lower())
        elif sort_key == "type":
            key_fn = lambda it: (it.extension.lower(), it.name.lower())
        elif sort_key == "rating":
            key_fn = lambda it: (it.rating, 1 if it.has_xmp else 0, it.name.lower())
        else:  # "name"
            key_fn = lambda it: it.name.lower()

        return sorted(items, key=key_fn, reverse=descending)

    def apply_filter(self):
        """Applies format, status, text search filters, and active sort order."""
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

        self.filtered_items = self._sort_items(filtered)
        self._populate_views()
        self._update_selection_counter()

    def _clear_filters(self):
        self.edit_search.clear()
        self.combo_type.setCurrentIndex(0)
        self.combo_status.setCurrentIndex(0)

    @staticmethod
    def _parse_view_mode_key(key: Optional[str]) -> tuple:
        if key and key.startswith("grid:"):
            try:
                return ("grid", int(key.split(":", 1)[1]))
            except ValueError:
                return ("grid", 140)
        return ("list", 0)

    def set_view_mode(self, mode: str, thumb_size: Optional[int] = None):
        """Sets display mode ('list' or 'grid') and optional thumbnail size, syncing the dropdown."""
        if mode == "list":
            self.combo_view_mode.blockSignals(True)
            self.combo_view_mode.setCurrentIndex(0)
            self.combo_view_mode.blockSignals(False)
            self.view_stack.setCurrentIndex(0)
        else:
            target_size = thumb_size or 140
            idx = self.combo_view_mode.findData(f"grid:{target_size}")
            if idx < 0:
                idx = 2  # Default: Vorschau Mittel (140px)
            self.combo_view_mode.blockSignals(True)
            self.combo_view_mode.setCurrentIndex(idx)
            self.combo_view_mode.blockSignals(False)
            self._update_grid_item_size(target_size)
            self.view_stack.setCurrentIndex(1)
            self._request_visible_thumbnails()

    def _on_view_mode_combo_changed(self):
        """Handles selection changes in the unified display mode dropdown."""
        mode, size = self._parse_view_mode_key(self.combo_view_mode.currentData())
        if mode == "list":
            self.view_stack.setCurrentIndex(0)
        else:
            self._update_grid_item_size(size)
            self.view_stack.setCurrentIndex(1)
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
        _, thumb_dim = self._parse_view_mode_key(self.combo_view_mode.currentData())
        if thumb_dim <= 0:
            thumb_dim = 140

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

        self.lbl_sel_count.setText(f"{marked_cnt}/{total_cnt} ({format_size(marked_bytes)})")
        self.lbl_sel_count.setToolTip(f"{marked_cnt} von {total_cnt} markiert ({format_size(marked_bytes)})")
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

    def get_all_filtered_paths(self, scan_if_hidden: bool = True) -> List[Path]:
        """Returns all paths matching the current filter (optionally scanning on demand when files view is hidden)."""
        if not self._show_files and scan_if_hidden and not self.all_items and self.current_folder and self.current_folder.exists():
            self.refresh(force_scan=True)
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
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #334155;
                border-radius: 2px;
            }
            QSplitter::handle:hover {
                background-color: #38bdf8;
            }
        """)

        # Left Pane: Source (PC / Laptop)
        self.pane_source = TransferPaneWidget(
            title="Laptop / Lokale Bearbeitung (Quelle)",
            is_source=True,
            config=self.config
        )
        self.pane_source.setMinimumWidth(260)
        splitter.addWidget(self.pane_source)

        # Center Column: Action Controls and Progress (compact width for laptop displays)
        self.center_panel = QFrame()
        self.center_panel.setObjectName("cardFrame")
        self.center_panel.setFixedWidth(156)
        self.center_panel.setStyleSheet("background-color: #0b0f19; border: 1px solid #1e293b; border-radius: 8px;")

        center_layout = QVBoxLayout(self.center_panel)
        center_layout.setContentsMargins(6, 12, 6, 12)
        center_layout.setSpacing(8)

        lbl_actions = QLabel("AKTIONEN")
        lbl_actions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_actions.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px; letter-spacing: 1px;")
        center_layout.addWidget(lbl_actions)

        # Abgleich (Reconcile / Check missing files on right side)
        self.btn_reconcile = QPushButton("Abgleich ▾")
        self.btn_reconcile.setIcon(get_search_icon("#fbbf24", 13))
        self.btn_reconcile.setIconSize(QSize(13, 13))
        self.btn_reconcile.setToolTip("Abgleich: Ermittelt welche Dateien links vorhanden sind, aber rechts noch fehlen, und markiert sie zum Kopieren.")
        self.btn_reconcile.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; color: #fbbf24; border: 1px solid #d97706;
                font-weight: bold; border-radius: 5px; padding: 7px 6px; font-size: 11px;
            }
            QPushButton:hover { background-color: #d97706; color: white; }
            QPushButton::menu-indicator { subcontrol-origin: padding; subcontrol-position: right center; width: 12px; }
        """)

        reconcile_menu = QMenu(self.btn_reconcile)
        reconcile_menu.setStyleSheet("""
            QMenu {
                background-color: #1e293b; color: #f1f5f9; border: 1px solid #334155;
                border-radius: 6px; padding: 4px;
            }
            QMenu::item {
                padding: 6px 14px; border-radius: 4px; font-size: 11px;
            }
            QMenu::item:selected {
                background-color: #0284c7; color: #ffffff;
            }
        """)

        act_missing_jpg = reconcile_menu.addAction("Fehlende JPGs markieren")
        act_missing_jpg.setIcon(get_search_icon("#38bdf8", 12))
        act_missing_jpg.setToolTip("Prüft welche JPGs links vorhanden sind und rechts fehlen, und markiert sie links.")
        act_missing_jpg.triggered.connect(self.reconcile_missing_jpg)

        act_missing_raw = reconcile_menu.addAction("Fehlende RAWs markieren")
        act_missing_raw.setIcon(get_search_icon("#f43f5e", 12))
        act_missing_raw.setToolTip("Prüft welche RAWs links vorhanden sind und rechts fehlen, und markiert sie links.")
        act_missing_raw.triggered.connect(self.reconcile_missing_raw)

        reconcile_menu.addSeparator()

        act_missing_both = reconcile_menu.addAction("Beides (RAW & JPG) markieren")
        act_missing_both.setIcon(get_search_icon("#fbbf24", 12))
        act_missing_both.setToolTip("Prüft alle RAW- und JPG-Dateien, die links vorhanden sind und rechts fehlen, und markiert sie links.")
        act_missing_both.triggered.connect(self.reconcile_missing_both)

        reconcile_menu.addSeparator()

        self.act_reconcile_settings = reconcile_menu.addAction("")
        self.act_reconcile_settings.setIcon(get_gear_icon("#94a3b8", 12))
        self.act_reconcile_settings.triggered.connect(self._open_reconcile_settings)
        self._update_reconcile_action_label()

        self.btn_reconcile.setMenu(reconcile_menu)
        self.btn_reconcile.clicked.connect(self.btn_reconcile.showMenu)
        center_layout.addWidget(self.btn_reconcile)

        self.lbl_reconcile_status = QLabel("")
        self.lbl_reconcile_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_reconcile_status.setWordWrap(True)
        self.lbl_reconcile_status.setStyleSheet("color: #94a3b8; font-size: 9px;")
        center_layout.addWidget(self.lbl_reconcile_status)

        # Separator line
        sep_rec = QFrame()
        sep_rec.setFrameShape(QFrame.Shape.HLine)
        sep_rec.setStyleSheet("color: #334155; margin: 2px 0;")
        center_layout.addWidget(sep_rec)

        # Action: Copy Selection
        self.btn_copy_sel = QPushButton("Kopieren")
        self.btn_copy_sel.setIcon(get_arrow_right_icon("#ffffff", 14, double=False))
        self.btn_copy_sel.setIconSize(QSize(14, 14))
        self.btn_copy_sel.setToolTip("Markierte Fotos von links nach rechts kopieren")
        self.btn_copy_sel.setStyleSheet("""
            QPushButton {
                background-color: #0284c7; color: white; font-weight: bold;
                border-radius: 5px; padding: 7px 6px; font-size: 11px;
            }
            QPushButton:hover { background-color: #0369a1; }
            QPushButton:disabled { background-color: #334155; color: #64748b; }
        """)
        self.btn_copy_sel.clicked.connect(self._transfer_selected_copy)
        center_layout.addWidget(self.btn_copy_sel)

        # Action: Move Selection
        self.btn_move_sel = QPushButton("Verschieben")
        self.btn_move_sel.setIcon(get_move_icon("#ffffff", 14, double=False))
        self.btn_move_sel.setIconSize(QSize(14, 14))
        self.btn_move_sel.setToolTip("Markierte Fotos verschieben (Quelle wird nach Transfer gelöscht)")
        self.btn_move_sel.setStyleSheet("""
            QPushButton {
                background-color: #0d9488; color: white; font-weight: bold;
                border-radius: 5px; padding: 7px 6px; font-size: 11px;
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
        self.btn_copy_all = QPushButton("Alle kopieren")
        self.btn_copy_all.setIcon(get_arrow_right_icon("#38bdf8", 14, double=True))
        self.btn_copy_all.setIconSize(QSize(14, 14))
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
        self.btn_move_all = QPushButton("Alle versch.")
        self.btn_move_all.setIcon(get_move_icon("#2dd4bf", 14, double=True))
        self.btn_move_all.setIconSize(QSize(14, 14))
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
        self.btn_swap = QPushButton("Tauschen")
        self.btn_swap.setIcon(get_swap_icon("#94a3b8", 13))
        self.btn_swap.setIconSize(QSize(13, 13))
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
        self.pane_dest.setMinimumWidth(260)
        splitter.addWidget(self.pane_dest)
        self.main_splitter = splitter

        # Sizing: Source ~45%, Center ~10%, Dest ~45%
        splitter.setSizes([580, 156, 580])
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
        has_filtered = (
            len(self.pane_source.get_all_filtered_paths(scan_if_hidden=False)) > 0
            or (not self.pane_source._show_files and bool(self.pane_source.current_folder and self.pane_source.current_folder.exists()))
        )
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
        self.btn_reconcile.setEnabled(not is_running)
        self.btn_copy_sel.setEnabled(not is_running)
        self.btn_move_sel.setEnabled(not is_running)
        self.btn_copy_all.setEnabled(not is_running)
        self.btn_move_all.setEnabled(not is_running)
        self.btn_swap.setEnabled(not is_running)
        if not is_running:
            self._update_action_states()

    def _update_reconcile_action_label(self):
        method = getattr(self.config, "transfer_reconcile_method", "filename").lower()
        method_names = {
            "filename": "Dateiname",
            "exif": "EXIF-Aufnahmezeit",
            "sha256": "SHA-256 Prüfsumme"
        }
        name = method_names.get(method, "Dateiname")
        if hasattr(self, "act_reconcile_settings"):
            self.act_reconcile_settings.setText(f"⚙️ Methode: {name}...")
            self.act_reconcile_settings.setToolTip(f"Aktive Abgleich-Methode: {name}. Klicken zum Anpassen in den Programmeinstellungen.")
        self.btn_reconcile.setToolTip(f"Abgleich (nach {name}): Ermittelt links vorhandene, rechts fehlende Dateien und markiert sie zum Kopieren.")

    def _open_reconcile_settings(self):
        from gui_qt.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self.config, parent=self, initial_tab=2)
        if dlg.exec():
            self._update_reconcile_action_label()

    def reconcile_missing_jpg(self) -> List[Path]:
        """Checks which JPG files in source are missing in destination and marks them for transfer."""
        return self.reconcile_missing_files("jpg")

    def reconcile_missing_raw(self) -> List[Path]:
        """Checks which RAW files in source are missing in destination and marks them for transfer."""
        return self.reconcile_missing_files("raw")

    def reconcile_missing_both(self) -> List[Path]:
        """Checks which RAW and JPG files in source are missing in destination and marks them for transfer."""
        return self.reconcile_missing_files("both")

    def reconcile_missing_files(self, mode: str = "both") -> List[Path]:
        """
        Reconciles source (left) with destination (right).
        Uses the comparison method defined in `self.config.transfer_reconcile_method`:
          - 'filename': identical filename comparison (case-insensitive)
          - 'exif': matching EXIF date_taken (DateTimeOriginal) and media category
          - 'sha256': exact bit-level SHA-256 file content hash
        Selected missing files are marked/checked in pane_source for immediate transfer.
        Returns the list of missing file Paths.
        """
        src_folder = self.pane_source.current_folder
        if not src_folder or not src_folder.exists():
            self.lbl_reconcile_status.setText("Kein Quellordner gewählt")
            self.lbl_reconcile_status.setStyleSheet("color: #f87171; font-size: 9px;")
            return []

        dest_folder = self.pane_dest.current_folder
        if not dest_folder or not dest_folder.exists():
            self.lbl_reconcile_status.setText("Kein Zielordner gewählt")
            self.lbl_reconcile_status.setStyleSheet("color: #f87171; font-size: 9px;")
            return []

        # Ensure source folder is scanned
        if not self.pane_source.all_items:
            self.pane_source.refresh(force_scan=True)

        mode_clean = mode.lower()
        candidate_items: List[TransferItem] = []
        for it in self.pane_source.all_items:
            if mode_clean == "jpg" and not it.is_jpeg:
                continue
            elif mode_clean == "raw" and not it.is_raw:
                continue
            elif mode_clean in ("both", "all") and not (it.is_raw or it.is_jpeg):
                continue
            candidate_items.append(it)

        method = getattr(self.config, "transfer_reconcile_method", "filename").lower()
        if method not in ("filename", "exif", "sha256"):
            method = "filename"

        missing_items: List[TransferItem] = []

        if method == "exif":
            # 1. EXIF DateTimeOriginal matching
            dest_exif_counts: CounterType[Tuple[str, str]] = Counter()
            dest_filenames: Set[str] = set()
            try:
                with os.scandir(dest_folder) as entries:
                    for entry in entries:
                        if entry.is_file():
                            dest_filenames.add(entry.name.lower())
                            p = Path(entry.path)
                            if p.suffix.lower() in ALL_MEDIA_EXTENSIONS:
                                try:
                                    meta = extract_metadata(p)
                                    if meta and meta.date_taken:
                                        d_str = meta.date_taken.strftime("%Y-%m-%d %H:%M:%S")
                                        type_key = "raw" if meta.is_raw else "jpg"
                                        dest_exif_counts[(d_str, type_key)] += 1
                                except Exception:
                                    pass
            except Exception as err:
                self.lbl_reconcile_status.setText(f"Zielfehler: {err}")
                self.lbl_reconcile_status.setStyleSheet("color: #f87171; font-size: 9px;")
                return []

            for it in candidate_items:
                try:
                    meta = extract_metadata(it.path)
                    if meta and meta.date_taken:
                        d_str = meta.date_taken.strftime("%Y-%m-%d %H:%M:%S")
                        type_key = "raw" if it.is_raw else "jpg"
                        k = (d_str, type_key)
                        if dest_exif_counts[k] > 0:
                            dest_exif_counts[k] -= 1
                        else:
                            missing_items.append(it)
                    else:
                        # Fallback to filename if file has no EXIF date
                        if it.name.lower() not in dest_filenames:
                            missing_items.append(it)
                except Exception:
                    if it.name.lower() not in dest_filenames:
                        missing_items.append(it)

        elif method == "sha256":
            # 2. Exact bit-level SHA-256 matching (with file size pre-filter)
            dest_by_size: Dict[int, List[Path]] = {}
            try:
                with os.scandir(dest_folder) as entries:
                    for entry in entries:
                        if entry.is_file():
                            try:
                                dest_by_size.setdefault(entry.stat().st_size, []).append(Path(entry.path))
                            except OSError:
                                pass
            except Exception as err:
                self.lbl_reconcile_status.setText(f"Zielfehler: {err}")
                self.lbl_reconcile_status.setStyleSheet("color: #f87171; font-size: 9px;")
                return []

            dest_hash_cache: Dict[Path, str] = {}
            for it in candidate_items:
                if it.size not in dest_by_size:
                    missing_items.append(it)
                    continue

                src_hash = compute_file_sha256(it.path)
                matched = False
                for dest_p in dest_by_size[it.size]:
                    if dest_p not in dest_hash_cache:
                        dest_hash_cache[dest_p] = compute_file_sha256(dest_p)
                    if dest_hash_cache[dest_p] == src_hash:
                        matched = True
                        break
                if not matched:
                    missing_items.append(it)

        else:
            # 3. Default: Filename equality
            dest_filenames = set()
            try:
                with os.scandir(dest_folder) as entries:
                    for entry in entries:
                        if entry.is_file():
                            dest_filenames.add(entry.name.lower())
            except Exception as err:
                self.lbl_reconcile_status.setText(f"Zielfehler: {err}")
                self.lbl_reconcile_status.setStyleSheet("color: #f87171; font-size: 9px;")
                return []

            for it in candidate_items:
                if it.name.lower() not in dest_filenames:
                    missing_items.append(it)

        # Clear existing selection and mark all missing items
        self.pane_source.select_none()
        for it in missing_items:
            self.pane_source._checked_paths.add(str(it.path))

        # Make sure files view is visible on source pane
        if not self.pane_source._show_files:
            self.pane_source.set_files_visible(True)

        # Reset conflicting type filter if active so user can see checked items
        if mode_clean == "jpg" and self.pane_source.combo_type.currentText() == "Nur RAW":
            self.pane_source.combo_type.setCurrentIndex(0)
        elif mode_clean == "raw" and self.pane_source.combo_type.currentText() == "Nur JPG":
            self.pane_source.combo_type.setCurrentIndex(0)

        self.pane_source._populate_views()
        self.pane_source._update_selection_counter()

        # Update feedback UI
        method_labels = {
            "filename": "Name",
            "exif": "EXIF-Zeit",
            "sha256": "SHA-256"
        }
        m_lbl = method_labels.get(method, "Name")
        labels = {"jpg": "JPGs", "raw": "RAWs", "both": "RAW & JPG", "all": "Dateien"}
        lbl = labels.get(mode_clean, "Dateien")
        count = len(missing_items)
        if count > 0:
            self.lbl_reconcile_status.setText(f"✓ {count} fehlende {lbl} markiert ({m_lbl})")
            self.lbl_reconcile_status.setStyleSheet("color: #4ade80; font-size: 9px; font-weight: bold;")
            self.lbl_reconcile_status.setToolTip(f"{count} {lbl} links gefunden, die im Zielordner fehlen (geprüft nach {m_lbl}). Zur Übertragung markiert.")
        else:
            self.lbl_reconcile_status.setText(f"✓ Ziel aktuell (0 {lbl} fehlen, {m_lbl})")
            self.lbl_reconcile_status.setStyleSheet("color: #38bdf8; font-size: 9px;")
            self.lbl_reconcile_status.setToolTip(f"Alle {lbl} aus dem Quellordner sind im Zielordner bereits vorhanden (geprüft nach {m_lbl}).")

        return [it.path for it in missing_items]

