"""Directory Tree Widget for Vitrina (Tab 2: Sichten & Sortieren).

Displays an interactive folder tree starting from a configurable entry point (Einstiegspunkt).
For each directory, shows:
- Total image count
- RAW file count
- JPEG file count

Supports lazy loading for high performance, smooth Ultrawide layout integration,
and one-click folder selection for culling.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional
import weakref

from PySide6.QtCore import QPoint, QSize, Qt, QTimer, Signal, QUrl
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QFont, QIcon, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QMenu, QPushButton, QSizePolicy, QTreeView, QVBoxLayout, QWidget
)

from core.config import AppConfig
from gui_qt.models.culling_model import count_folder_images
from gui_qt.styles.icons import (
    get_collapse_panel_icon, get_columns_icon, get_folder_icon,
    get_minus_icon, get_plus_icon, get_refresh_icon, get_sort_icon,
    get_icon_color
)
from gui_qt.styles.theme import theme_manager
from gui_qt.widgets.elided_label import ElidedLabel
from gui_qt.widgets.paired_header import PairedHeaderView


DUMMY_ITEM_TEXT = "..."


class CullingDirectoryTreeWidget(QWidget):
    """Hierarchical folder tree widget showing photo counts (Total, RAW, JPEG)."""
    folder_selected = Signal(Path)
    root_changed = Signal(Path)
    collapse_panel_requested = Signal()

    _instances: "weakref.WeakSet[CullingDirectoryTreeWidget]" = weakref.WeakSet()
    MIN_COL_WIDTHS: Dict[int, int] = {
        0: 110,  # Ordner
        1: 44,   # Bilder
        2: 40,   # RAW
        3: 40,   # JPG
    }

    def __init__(
        self,
        config: AppConfig,
        parent=None,
        title: str = "VERZEICHNISSE",
        config_root_key: Optional[str] = "culling_root_folder",
        default_root: Optional[Path] = None,
        show_collapse_btn: bool = True
    ):
        super().__init__(parent)
        self.config = config
        self.title_text = title
        self.config_root_key = config_root_key
        self.default_root = default_root
        self.show_collapse_btn = show_collapse_btn
        self.root_path: Optional[Path] = None
        self._sort_descending: bool = getattr(self.config, "tree_sort_descending", False)
        CullingDirectoryTreeWidget._instances.add(self)
        self._init_ui()
        self._init_default_root()
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Header Card: Title, Einstiegspunkt, and Action Buttons
        card_header = QFrame()
        self.card_header = card_header
        card_header.setObjectName("treeHeaderCard")
        h_layout = QVBoxLayout(card_header)
        h_layout.setContentsMargins(6, 6, 6, 6)
        h_layout.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setSpacing(2)
        lbl_title = ElidedLabel(self.title_text, Qt.TextElideMode.ElideRight)
        lbl_title.setObjectName("treeTitleLabel")
        title_row.addWidget(lbl_title, stretch=1)

        self.btn_columns = QPushButton()
        self.btn_columns.setObjectName("treeToolBtn")
        self.btn_columns.setIcon(get_columns_icon(get_icon_color("normal"), 13))
        self.btn_columns.setIconSize(QSize(13, 13))
        self.btn_columns.setFixedSize(24, 22)
        self.btn_columns.setToolTip("Spalten ein-/ausblenden (Bilder, RAW, JPG)")
        self.btn_columns.clicked.connect(lambda _=False: self._show_columns_menu())
        title_row.addWidget(self.btn_columns)

        self.btn_sort = QPushButton()
        self.btn_sort.setObjectName("treeToolBtn")
        self.btn_sort.setIcon(get_sort_icon(self._sort_descending, get_icon_color("normal"), 13))
        self.btn_sort.setIconSize(QSize(13, 13))
        self.btn_sort.setFixedSize(24, 22)
        self.btn_sort.setToolTip(
            "Ordner-Sortierung: Absteigend (Z–A) – Klicken für Aufsteigend"
            if self._sort_descending
            else "Ordner-Sortierung: Aufsteigend (A–Z) – Klicken für Absteigend"
        )
        self.btn_sort.clicked.connect(self._toggle_sort_order)
        title_row.addWidget(self.btn_sort)

        self.btn_refresh = QPushButton()
        self.btn_refresh.setObjectName("treeToolBtn")
        self.btn_refresh.setIcon(get_refresh_icon(get_icon_color("normal"), 13))
        self.btn_refresh.setIconSize(QSize(13, 13))
        self.btn_refresh.setFixedSize(24, 22)
        self.btn_refresh.setToolTip("Verzeichnisbaum aktualisieren")
        self.btn_refresh.clicked.connect(self.refresh)
        title_row.addWidget(self.btn_refresh)

        self.btn_expand_all = QPushButton()
        self.btn_expand_all.setObjectName("treeToolBtn")
        self.btn_expand_all.setIcon(get_plus_icon(get_icon_color("normal"), 13))
        self.btn_expand_all.setIconSize(QSize(13, 13))
        self.btn_expand_all.setFixedSize(24, 22)
        self.btn_expand_all.setToolTip("Unterordner ausklappen")
        self.btn_expand_all.clicked.connect(self._expand_two_levels)
        title_row.addWidget(self.btn_expand_all)

        self.btn_collapse_all = QPushButton()
        self.btn_collapse_all.setObjectName("treeToolBtn")
        self.btn_collapse_all.setIcon(get_minus_icon(get_icon_color("normal"), 13))
        self.btn_collapse_all.setIconSize(QSize(13, 13))
        self.btn_collapse_all.setFixedSize(24, 22)
        self.btn_collapse_all.setToolTip("Verzeichnisbaum einklappen (Alle Ordner schließen)")
        self.btn_collapse_all.clicked.connect(self.tree_view.collapseAll if hasattr(self, 'tree_view') else lambda: None)
        title_row.addWidget(self.btn_collapse_all)

        self.btn_collapse_panel = QPushButton()
        self.btn_collapse_panel.setObjectName("treeToolBtn")
        self.btn_collapse_panel.setIcon(get_collapse_panel_icon(get_icon_color("normal"), 13))
        self.btn_collapse_panel.setIconSize(QSize(13, 13))
        self.btn_collapse_panel.setFixedSize(24, 22)
        self.btn_collapse_panel.setToolTip("Verzeichnisbaum-Leiste einklappen [V]")
        self.btn_collapse_panel.setVisible(self.show_collapse_btn)
        self.btn_collapse_panel.clicked.connect(self.collapse_panel_requested.emit)
        title_row.addWidget(self.btn_collapse_panel)

        h_layout.addLayout(title_row)

        # Path display & change button
        path_box = QHBoxLayout()
        path_box.setSpacing(4)

        self.btn_change_root = QPushButton("Einstiegspunkt...")
        self.btn_change_root.setObjectName("btnChangeRoot")
        self.btn_change_root.setIcon(get_folder_icon(get_icon_color("accent"), 13))
        self.btn_change_root.setIconSize(QSize(13, 13))
        self.btn_change_root.setToolTip("Einstiegspunkt — Neuen Hauptordner für die Navigation auswählen")
        self.btn_change_root.clicked.connect(self._on_choose_root_clicked)
        path_box.addWidget(self.btn_change_root)

        self.lbl_root_path = QLabel("")
        self.lbl_root_path.setObjectName("treeRootPathLabel")
        self.lbl_root_path.setWordWrap(True)
        self.lbl_root_path.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_root_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_box.addWidget(self.lbl_root_path, stretch=1)
        h_layout.addLayout(path_box)

        layout.addWidget(card_header)

        # Tree View Setup
        self.model = QStandardItemModel(0, 4)
        self.model.setHorizontalHeaderLabels(["Ordner", "Bilder", "RAW", "JPG"])

        self.tree_view = QTreeView()
        self.tree_view.setObjectName("directoryTreeView")
        self.tree_view.setModel(self.model)
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setUniformRowHeights(True)
        self.tree_view.setAnimated(True)
        self.tree_view.setSortingEnabled(False)
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self._on_context_menu)
        self.tree_view.expanded.connect(self._on_node_expanded)
        self.tree_view.clicked.connect(self._on_item_clicked)

        # Connect collapse button now that tree_view exists
        self.btn_collapse_all.clicked.connect(self.tree_view.collapseAll)

        self.tree_view.setHeader(PairedHeaderView(Qt.Orientation.Horizontal, self.tree_view))
        header = self.tree_view.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.tree_view.setColumnWidth(1, 48)
        self.tree_view.setColumnWidth(2, 44)
        self.tree_view.setColumnWidth(3, 44)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(lambda pos: self._show_columns_menu(header.mapToGlobal(pos)))
        self._apply_column_visibility()

        layout.addWidget(self.tree_view, stretch=1)

    def _init_default_root(self):
        """Resolves initial entry point from config or common photo directories."""
        chosen = None

        # 1. Primary: saved entry point from configuration
        if self.config_root_key and hasattr(self.config, self.config_root_key):
            val = getattr(self.config, self.config_root_key)
            if val:
                p = Path(val)
                if p.exists() and p.is_dir():
                    chosen = p

        # 2. Secondary: default_root fallback (e.g. NAS archive or imported target)
        if not chosen and self.default_root and self.default_root.exists() and self.default_root.is_dir():
            chosen = self.default_root

        # 3. Third priority: culling root / last folder if applicable
        if not chosen and self.config.culling_root_folder:
            p = Path(self.config.culling_root_folder)
            if p.exists() and p.is_dir():
                chosen = p

        if not chosen and self.config.culling_last_folder:
            p = Path(self.config.culling_last_folder)
            if p.exists() and p.is_dir():
                chosen = p.parent if p.parent.exists() else p

        if not chosen and self.config.target_dir:
            p = Path(self.config.target_dir)
            if p.exists() and p.is_dir():
                chosen = p

        if not chosen:
            chosen = Path.home() / "Pictures"
            if not chosen.exists():
                chosen = Path.home()

        self.set_root_folder(chosen)

    def set_root_folder(self, path: Path):
        """Sets the root directory and builds the tree hierarchy."""
        if not path or not path.exists() or not path.is_dir():
            return

        self.root_path = path
        if self.config_root_key and hasattr(self.config, self.config_root_key):
            setattr(self.config, self.config_root_key, str(path))
            try:
                self.config.save()
            except Exception:
                pass

        # Update label with full path
        try:
            full_path_str = str(path.resolve())
        except Exception:
            full_path_str = str(path)
        self.lbl_root_path.setText(full_path_str)
        self.lbl_root_path.setToolTip(full_path_str)

        self.refresh()
        self.root_changed.emit(path)

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_column_visibility()
        QTimer.singleShot(0, self._recalculate_column_widths)

    def header_icon_min_width(self) -> int:
        """Minimum width needed to display all header icon buttons without clipping."""
        buttons = [
            self.btn_columns, self.btn_sort, self.btn_refresh,
            self.btn_expand_all, self.btn_collapse_all, self.btn_collapse_panel,
        ]
        visible_w = sum(b.width() or 24 for b in buttons if b.isVisible())
        return max(180, visible_w + 34)

    def _update_responsive_header(self):
        if not hasattr(self, "btn_change_root"):
            return
        compact = 0 < self.width() < 245
        if compact and self.btn_change_root.text() != "":
            self.btn_change_root.setObjectName("compactToolBtn")
            self.btn_change_root.setText("")
            self.btn_change_root.setFixedSize(28, 24)
            self.btn_change_root.style().unpolish(self.btn_change_root)
            self.btn_change_root.style().polish(self.btn_change_root)
        elif not compact and self.btn_change_root.text() == "":
            self.btn_change_root.setObjectName("btnChangeRoot")
            self.btn_change_root.setText("Einstiegspunkt...")
            self.btn_change_root.setMinimumSize(0, 0)
            self.btn_change_root.setMaximumSize(16777215, 16777215)
            self.btn_change_root.style().unpolish(self.btn_change_root)
            self.btn_change_root.style().polish(self.btn_change_root)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_responsive_header()
        self._recalculate_column_widths()

    def _apply_column_visibility(self):
        """Applies persisted column visibility flags for Bilder, RAW, and JPG."""
        self.tree_view.setColumnHidden(1, not bool(getattr(self.config, "tree_show_col_bilder", True)))
        self.tree_view.setColumnHidden(2, not bool(getattr(self.config, "tree_show_col_raw", True)))
        self.tree_view.setColumnHidden(3, not bool(getattr(self.config, "tree_show_col_jpg", True)))
        self._recalculate_column_widths()

    def _recalculate_column_widths(self):
        """Distributes available viewport width across visible columns, switching to scroll only below minimum widths."""
        available_w = self.tree_view.viewport().width()
        if available_w <= 0:
            return

        visible_cols = [c for c in range(4) if not self.tree_view.isColumnHidden(c)]
        if not visible_cols:
            return

        total_min = sum(self.MIN_COL_WIDTHS[c] for c in visible_cols)
        if available_w <= total_min:
            self.tree_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            for col in visible_cols:
                self.tree_view.setColumnWidth(col, self.MIN_COL_WIDTHS[col])
            return

        self.tree_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        extra = available_w - total_min
        count_cols = [c for c in visible_cols if c != 0]

        count_widths: Dict[int, int] = {}
        used_count_total = 0
        for c in count_cols:
            bonus = min(14, extra // max(1, len(count_cols) * 3))
            w = self.MIN_COL_WIDTHS[c] + bonus
            count_widths[c] = w
            used_count_total += w

        if 0 in visible_cols:
            col0_w = max(self.MIN_COL_WIDTHS[0], available_w - used_count_total)
            self.tree_view.setColumnWidth(0, col0_w)
        for c, w in count_widths.items():
            self.tree_view.setColumnWidth(c, w)

    def set_column_visibility(self, col_idx: int, visible: bool):
        """Shows or hides a count column (1=Bilder, 2=RAW, 3=JPG), syncs all trees, and saves config."""
        attr_map = {
            1: "tree_show_col_bilder",
            2: "tree_show_col_raw",
            3: "tree_show_col_jpg",
        }
        attr = attr_map.get(col_idx)
        if not attr:
            return
        setattr(self.config, attr, bool(visible))
        self.tree_view.setColumnHidden(col_idx, not visible)
        self._recalculate_column_widths()

        # Synchronize all other live directory trees sharing this config
        for inst in list(CullingDirectoryTreeWidget._instances):
            if inst is not self and inst.config is self.config:
                inst._apply_column_visibility()

        try:
            self.config.save()
        except Exception:
            pass

    def _show_columns_menu(self, global_pos=None):
        """Opens menu to toggle Bilder, RAW, and JPG columns on or off."""
        self._apply_column_visibility()
        menu = QMenu(self)
        col_defs = [
            (1, "Spalte „Bilder“ anzeigen", not self.tree_view.isColumnHidden(1)),
            (2, "Spalte „RAW“ anzeigen", not self.tree_view.isColumnHidden(2)),
            (3, "Spalte „JPG“ anzeigen", not self.tree_view.isColumnHidden(3)),
        ]
        actions = {}
        for col_idx, label, checked in col_defs:
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(checked)
            actions[act] = col_idx

        pos = (
            global_pos
            if isinstance(global_pos, QPoint)
            else self.btn_columns.mapToGlobal(self.btn_columns.rect().bottomLeft())
        )
        chosen = menu.exec(pos)
        if chosen in actions:
            self.set_column_visibility(actions[chosen], chosen.isChecked())

    def _toggle_sort_order(self):
        """Toggles ascending/descending directory sorting and rebuilds the tree."""
        self._sort_descending = not self._sort_descending
        self.config.tree_sort_descending = self._sort_descending
        try:
            self.config.save()
        except Exception:
            pass
        self.btn_sort.setIcon(get_sort_icon(self._sort_descending, "#cbd5e1", 13))
        if self._sort_descending:
            self.btn_sort.setToolTip("Ordner-Sortierung: Absteigend (Z–A) – Klicken für Aufsteigend")
        else:
            self.btn_sort.setToolTip("Ordner-Sortierung: Aufsteigend (A–Z) – Klicken für Absteigend")
        self.refresh()

    def refresh(self):
        """Re-scans the directory tree from the root path."""
        self.model.removeRows(0, self.model.rowCount())
        if not self.root_path or not self.root_path.exists():
            return

        # Add root folder as the top-level node with full path
        root_rows = self._build_folder_row(self.root_path, is_root=True)
        self.model.appendRow(root_rows)
        root_item = root_rows[0]

        # Scan immediate subdirectories under root
        self._populate_children(root_item, self.root_path)

        # Expand root item by default so user sees immediate contents
        root_idx = self.model.indexFromItem(root_item)
        self.tree_view.expand(root_idx)

    def _get_item_colors(self, total: int, raw: int, jpg: int):
        """Returns theme-compliant foreground colors for folder photo counts."""
        is_light = (theme_manager.effective_theme == "light")
        if is_light:
            c_tot = "#0f172a" if total > 0 else "#94a3b8"
            c_raw = "#be185d" if raw > 0 else "#94a3b8"
            c_jpg = "#0284c7" if jpg > 0 else "#94a3b8"
        else:
            c_tot = "#f8fafc" if total > 0 else "#475569"
            c_raw = "#f472b6" if raw > 0 else "#475569"
            c_jpg = "#38bdf8" if jpg > 0 else "#475569"
        return QBrush(QColor(c_tot)), QBrush(QColor(c_raw)), QBrush(QColor(c_jpg))

    def _on_theme_changed(self, theme_name: str):
        """Refreshes button icons and item colors when the theme switches."""
        self.btn_columns.setIcon(get_columns_icon(get_icon_color("normal"), 13))
        self.btn_sort.setIcon(get_sort_icon(self._sort_descending, get_icon_color("normal"), 13))
        self.btn_refresh.setIcon(get_refresh_icon(get_icon_color("normal"), 13))
        self.btn_expand_all.setIcon(get_plus_icon(get_icon_color("normal"), 13))
        self.btn_collapse_all.setIcon(get_minus_icon(get_icon_color("normal"), 13))
        self.btn_collapse_panel.setIcon(get_collapse_panel_icon(get_icon_color("normal"), 13))
        self.btn_change_root.setIcon(get_folder_icon(get_icon_color("accent"), 13))
        self._update_model_colors(self.model.invisibleRootItem())

    def _update_model_colors(self, parent_item: QStandardItem):
        """Recursively updates foreground colors for all items in the model."""
        if not parent_item:
            return
        row_count = parent_item.rowCount()
        for r in range(row_count):
            c0 = parent_item.child(r, 0)
            c1 = parent_item.child(r, 1)
            c2 = parent_item.child(r, 2)
            c3 = parent_item.child(r, 3)
            if c0:
                c0.setIcon(get_folder_icon(get_icon_color("accent"), 14))
            if c1 and c2 and c3:
                try:
                    tot = int(c1.text())
                    raw = int(c2.text())
                    jpg = int(c3.text())
                    col_tot, col_raw, col_jpg = self._get_item_colors(tot, raw, jpg)
                    c1.setForeground(col_tot)
                    c2.setForeground(col_raw)
                    c3.setForeground(col_jpg)
                except ValueError:
                    pass
            if c0 and c0.hasChildren():
                self._update_model_colors(c0)

    def _build_folder_row(self, folder: Path, is_root: bool = False) -> List[QStandardItem]:
        """Creates the 4 items for a folder row: (Ordner, Bilder, RAW, JPG)."""
        total, raw, jpg = count_folder_images(folder)

        if is_root:
            try:
                folder_name = str(folder.resolve())
            except Exception:
                folder_name = str(folder)
        else:
            folder_name = folder.name if folder.name else str(folder)
        item_name = QStandardItem(folder_name)
        item_name.setIcon(get_folder_icon(get_icon_color("accent"), 14))
        item_name.setData(str(folder.resolve()), Qt.ItemDataRole.UserRole)
        item_name.setToolTip(f"{folder.resolve()}\nBilder: {total} | RAW: {raw} | JPG: {jpg}")
        item_name.setEditable(False)

        col_tot, col_raw, col_jpg = self._get_item_colors(total, raw, jpg)

        item_total = QStandardItem(str(total) if total > 0 else "0")
        item_total.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item_total.setEditable(False)
        item_total.setForeground(col_tot)
        if total > 0:
            f = item_total.font()
            f.setBold(True)
            item_total.setFont(f)

        item_raw = QStandardItem(str(raw) if raw > 0 else "0")
        item_raw.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item_raw.setEditable(False)
        item_raw.setForeground(col_raw)
        if raw > 0:
            f = item_raw.font()
            f.setBold(True)
            item_raw.setFont(f)

        item_jpg = QStandardItem(str(jpg) if jpg > 0 else "0")
        item_jpg.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item_jpg.setEditable(False)
        item_jpg.setForeground(col_jpg)
        if jpg > 0:
            f = item_jpg.font()
            f.setBold(True)
            item_jpg.setFont(f)

        return [item_name, item_total, item_raw, item_jpg]

    def _has_subdirectories(self, folder: Path) -> bool:
        """Quick check if folder contains any valid non-hidden subdirectories."""
        try:
            with os.scandir(folder) as it:
                for entry in it:
                    if entry.name.startswith("."):
                        continue
                    try:
                        if entry.is_dir():
                            return True
                    except OSError:
                        continue
        except (PermissionError, OSError):
            return False
        return False

    def _populate_children(self, parent_item: QStandardItem, folder: Path):
        """Populates immediate subdirectories of folder under parent_item."""
        try:
            subdirs: List[Path] = []
            with os.scandir(folder) as it:
                for entry in it:
                    if entry.name.startswith("."):
                        continue
                    try:
                        if entry.is_dir():
                            subdirs.append(Path(entry.path))
                    except OSError:
                        continue
            subdirs.sort(key=lambda p: p.name.lower(), reverse=self._sort_descending)
        except (PermissionError, OSError):
            return

        for sub in subdirs:
            row_items = self._build_folder_row(sub)
            parent_item.appendRow(row_items)
            child_item = row_items[0]

            # If child itself has subdirectories, attach dummy item for lazy loading
            if self._has_subdirectories(sub):
                dummy = QStandardItem(DUMMY_ITEM_TEXT)
                dummy.setEditable(False)
                child_item.appendRow([dummy, QStandardItem(""), QStandardItem(""), QStandardItem("")])

    def _on_node_expanded(self, index):
        """Handles lazy loading when a tree node is expanded."""
        item = self.model.itemFromIndex(index)
        if not item or item.column() != 0:
            return

        # Check if first child is dummy item
        if item.rowCount() == 1:
            first_child = item.child(0, 0)
            if first_child and first_child.text() == DUMMY_ITEM_TEXT:
                item.removeRow(0)
                folder_str = item.data(Qt.ItemDataRole.UserRole)
                if folder_str:
                    self._populate_children(item, Path(folder_str))

    def _on_item_clicked(self, index):
        """Triggered when user clicks any column in a directory row."""
        # Normalize to column 0 where UserRole stores the folder path
        col0_idx = index.siblingAtColumn(0)
        item = self.model.itemFromIndex(col0_idx)
        if not item:
            return

        folder_str = item.data(Qt.ItemDataRole.UserRole)
        if folder_str:
            p = Path(folder_str)
            if p.exists() and p.is_dir():
                self.folder_selected.emit(p)

    def _on_choose_root_clicked(self):
        """Opens file dialog for user to choose a new root directory."""
        initial = str(self.root_path) if self.root_path and self.root_path.exists() else str(Path.home())
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Einstiegspunkt für Verzeichnisbaum wählen",
            initial
        )
        if chosen:
            self.set_root_folder(Path(chosen))

    def _expand_two_levels(self):
        """Expands top 2 levels for convenient quick browsing."""
        root_idx = self.model.index(0, 0)
        if root_idx.isValid():
            self.tree_view.expand(root_idx)
            root_item = self.model.itemFromIndex(root_idx)
            if root_item:
                for row in range(root_item.rowCount()):
                    child_idx = self.model.index(row, 0, root_idx)
                    self._on_node_expanded(child_idx)
                    self.tree_view.expand(child_idx)

    def select_folder(self, folder: Path) -> bool:
        """Finds and highlights the specified folder in the tree if present under root_path."""
        if not folder or not folder.exists() or not self.root_path:
            return False

        try:
            folder_res = folder.resolve()
            root_res = self.root_path.resolve()
            rel = folder_res.relative_to(root_res)
        except (ValueError, Exception):
            return False

        if self.model.rowCount() == 0:
            return False

        current_item = self.model.item(0, 0)
        if not current_item:
            return False

        if rel == Path("."):
            idx = self.model.indexFromItem(current_item)
            self.tree_view.setCurrentIndex(idx)
            self.tree_view.scrollTo(idx)
            return True

        parts = rel.parts
        for part in parts:
            idx = self.model.indexFromItem(current_item)
            if current_item.rowCount() == 1 and current_item.child(0, 0) and current_item.child(0, 0).text() == DUMMY_ITEM_TEXT:
                self._on_node_expanded(idx)

            matched_child = None
            for r in range(current_item.rowCount()):
                child = current_item.child(r, 0)
                if child:
                    child_path_str = child.data(Qt.ItemDataRole.UserRole)
                    if child_path_str and Path(child_path_str).name.lower() == part.lower():
                        matched_child = child
                        break

            if not matched_child:
                return False
            current_item = matched_child

        idx = self.model.indexFromItem(current_item)
        self.tree_view.setCurrentIndex(idx)
        self.tree_view.scrollTo(idx)
        return True

    def _on_context_menu(self, pos):
        """Right-click context menu on a folder."""
        idx = self.tree_view.indexAt(pos)
        if not idx.isValid():
            return

        col0_idx = idx.siblingAtColumn(0)
        item = self.model.itemFromIndex(col0_idx)
        if not item:
            return

        folder_str = item.data(Qt.ItemDataRole.UserRole)
        if not folder_str:
            return
        folder_p = Path(folder_str)

        menu = QMenu(self)

        act_open = menu.addAction("🔍 Diesen Ordner anzeigen")
        act_set_root = menu.addAction("📂 Als neuen Einstiegspunkt setzen")
        menu.addSeparator()
        act_explorer = menu.addAction("📁 Im Datei-Manager öffnen")
        act_refresh_node = menu.addAction("🔄 Diesen Ordner neu einlesen")

        action = menu.exec(self.tree_view.viewport().mapToGlobal(pos))
        if action == act_open:
            self.folder_selected.emit(folder_p)
        elif action == act_set_root:
            self.set_root_folder(folder_p)
        elif action == act_explorer:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder_p)))
        elif action == act_refresh_node:
            total, raw, jpg = count_folder_images(folder_p)
            row = item.row()
            parent = item.parent() or self.model
            t_item = parent.child(row, 1) if hasattr(parent, 'child') else self.model.item(row, 1)
            r_item = parent.child(row, 2) if hasattr(parent, 'child') else self.model.item(row, 2)
            j_item = parent.child(row, 3) if hasattr(parent, 'child') else self.model.item(row, 3)

            col_tot, col_raw, col_jpg = self._get_item_colors(total, raw, jpg)
            if t_item:
                t_item.setText(str(total) if total > 0 else "0")
                t_item.setForeground(col_tot)
            if r_item:
                r_item.setText(str(raw) if raw > 0 else "0")
                r_item.setForeground(col_raw)
            if j_item:
                j_item.setText(str(jpg) if jpg > 0 else "0")
                j_item.setForeground(col_jpg)
