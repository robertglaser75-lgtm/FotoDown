"""Directory Tree Widget for FotoDown (Tab 2: Sichten & Sortieren).

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
from typing import List, Optional

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QMenu, QPushButton, QSizePolicy, QTreeView, QVBoxLayout, QWidget
)

from core.config import AppConfig
from gui_qt.models.culling_model import count_folder_images


DUMMY_ITEM_TEXT = "..."


class CullingDirectoryTreeWidget(QWidget):
    """Hierarchical folder tree widget showing photo counts (Total, RAW, JPEG)."""
    folder_selected = Signal(Path)
    root_changed = Signal(Path)

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.root_path: Optional[Path] = None
        self._init_ui()
        self._init_default_root()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Header Card: Title, Einstiegspunkt, and Action Buttons
        card_header = QFrame()
        card_header.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        h_layout = QVBoxLayout(card_header)
        h_layout.setContentsMargins(6, 6, 6, 6)
        h_layout.setSpacing(6)

        title_row = QHBoxLayout()
        lbl_title = QLabel("📁 VERZEICHNISSE")
        lbl_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #94a3b8;")
        title_row.addWidget(lbl_title, stretch=1)

        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setFixedSize(26, 24)
        self.btn_refresh.setToolTip("Verzeichnisbaum aktualisieren")
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155;
                border-radius: 3px; font-size: 11px;
            }
            QPushButton:hover { background-color: #334155; }
        """)
        self.btn_refresh.clicked.connect(self.refresh)
        title_row.addWidget(self.btn_refresh)

        self.btn_expand_all = QPushButton("➕")
        self.btn_expand_all.setFixedSize(24, 24)
        self.btn_expand_all.setToolTip("Unterordner ausklappen")
        self.btn_expand_all.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155;
                border-radius: 3px; font-size: 11px;
            }
            QPushButton:hover { background-color: #334155; }
        """)
        self.btn_expand_all.clicked.connect(self._expand_two_levels)
        title_row.addWidget(self.btn_expand_all)

        self.btn_collapse_all = QPushButton("➖")
        self.btn_collapse_all.setFixedSize(24, 24)
        self.btn_collapse_all.setToolTip("Alle einklappen")
        self.btn_collapse_all.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155;
                border-radius: 3px; font-size: 11px;
            }
            QPushButton:hover { background-color: #334155; }
        """)
        self.btn_collapse_all.clicked.connect(self.tree_view.collapseAll if hasattr(self, 'tree_view') else lambda: None)
        title_row.addWidget(self.btn_collapse_all)

        h_layout.addLayout(title_row)

        # Path display & change button
        path_box = QHBoxLayout()
        path_box.setSpacing(4)

        self.btn_change_root = QPushButton("Einstiegspunkt...")
        self.btn_change_root.setToolTip("Neuen Einstiegspunkt (Hauptordner) für die Navigation auswählen")
        self.btn_change_root.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; color: #38bdf8; border: 1px solid #0284c7;
                border-radius: 4px; padding: 4px 8px; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background-color: #0369a1; color: white; }
        """)
        self.btn_change_root.clicked.connect(self._on_choose_root_clicked)
        path_box.addWidget(self.btn_change_root)

        self.lbl_root_path = QLabel("")
        self.lbl_root_path.setStyleSheet("color: #94a3b8; font-size: 10px;")
        self.lbl_root_path.setWordWrap(False)
        path_box.addWidget(self.lbl_root_path, stretch=1)
        h_layout.addLayout(path_box)

        layout.addWidget(card_header)

        # Tree View Setup
        self.model = QStandardItemModel(0, 4)
        self.model.setHorizontalHeaderLabels(["Ordner", "Bilder", "RAW", "JPG"])

        self.tree_view = QTreeView()
        self.tree_view.setModel(self.model)
        self.tree_view.setUniformRowHeights(True)
        self.tree_view.setAnimated(True)
        self.tree_view.setSortingEnabled(False)
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self._on_context_menu)
        self.tree_view.expanded.connect(self._on_node_expanded)
        self.tree_view.clicked.connect(self._on_item_clicked)

        # Connect collapse button now that tree_view exists
        self.btn_collapse_all.clicked.connect(self.tree_view.collapseAll)

        header = self.tree_view.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.tree_view.setColumnWidth(1, 48)
        self.tree_view.setColumnWidth(2, 44)
        self.tree_view.setColumnWidth(3, 44)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

        self.tree_view.setStyleSheet("""
            QTreeView {
                background-color: #090d16;
                border: 1px solid #1e293b;
                border-radius: 6px;
                color: #e2e8f0;
                font-size: 11px;
                outline: 0;
            }
            QTreeView::item {
                padding: 4px 2px;
                border-radius: 3px;
            }
            QTreeView::item:hover {
                background-color: #1e293b;
            }
            QTreeView::item:selected {
                background-color: #1e3a8a;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #0f172a;
                color: #94a3b8;
                padding: 4px 6px;
                border: none;
                border-right: 1px solid #1e293b;
                border-bottom: 1px solid #1e293b;
                font-size: 10px;
                font-weight: bold;
            }
        """)

        layout.addWidget(self.tree_view, stretch=1)

    def _init_default_root(self):
        """Resolves initial entry point from config or common photo directories."""
        chosen = None
        if self.config.culling_root_folder:
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
        self.config.culling_root_folder = str(path)
        try:
            self.config.save()
        except Exception:
            pass

        # Update label
        display_text = path.name if path.name else str(path)
        self.lbl_root_path.setText(f"📂 {display_text}")
        self.lbl_root_path.setToolTip(str(path.resolve()))

        self.refresh()
        self.root_changed.emit(path)

    def refresh(self):
        """Re-scans the directory tree from the root path."""
        self.model.removeRows(0, self.model.rowCount())
        if not self.root_path or not self.root_path.exists():
            return

        # Add root folder as the top-level node
        root_rows = self._build_folder_row(self.root_path)
        self.model.appendRow(root_rows)
        root_item = root_rows[0]

        # Scan immediate subdirectories under root
        self._populate_children(root_item, self.root_path)

        # Expand root item by default so user sees immediate contents
        root_idx = self.model.indexFromItem(root_item)
        self.tree_view.expand(root_idx)

    def _build_folder_row(self, folder: Path) -> List[QStandardItem]:
        """Creates the 4 items for a folder row: (Ordner, Bilder, RAW, JPG)."""
        total, raw, jpg = count_folder_images(folder)

        folder_name = folder.name if folder.name else str(folder)
        item_name = QStandardItem(f"📁 {folder_name}")
        item_name.setData(str(folder.resolve()), Qt.ItemDataRole.UserRole)
        item_name.setToolTip(f"{folder.resolve()}\nBilder: {total} | RAW: {raw} | JPG: {jpg}")
        item_name.setEditable(False)

        item_total = QStandardItem(str(total) if total > 0 else "0")
        item_total.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item_total.setEditable(False)
        item_total.setForeground(QColor("#f8fafc" if total > 0 else "#475569"))
        if total > 0:
            f = item_total.font()
            f.setBold(True)
            item_total.setFont(f)

        item_raw = QStandardItem(str(raw) if raw > 0 else "0")
        item_raw.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item_raw.setEditable(False)
        item_raw.setForeground(QColor("#f472b6" if raw > 0 else "#475569"))
        if raw > 0:
            f = item_raw.font()
            f.setBold(True)
            item_raw.setFont(f)

        item_jpg = QStandardItem(str(jpg) if jpg > 0 else "0")
        item_jpg.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item_jpg.setEditable(False)
        item_jpg.setForeground(QColor("#38bdf8" if jpg > 0 else "#475569"))
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
            subdirs.sort(key=lambda p: p.name.lower())
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
        """Finds and highlights the specified folder in the tree if present."""
        if not folder or not folder.exists():
            return False

        target_str = str(folder.resolve()).lower()

        def search_node(item: QStandardItem) -> Optional[QStandardItem]:
            val = item.data(Qt.ItemDataRole.UserRole)
            if val and Path(val).resolve() == Path(target_str):
                return item
            # Ensure children are loaded
            idx = self.model.indexFromItem(item)
            if item.rowCount() == 1 and item.child(0, 0) and item.child(0, 0).text() == DUMMY_ITEM_TEXT:
                self._on_node_expanded(idx)

            for r in range(item.rowCount()):
                child = item.child(r, 0)
                if child:
                    found = search_node(child)
                    if found:
                        return found
            return None

        if self.model.rowCount() > 0:
            root_item = self.model.item(0, 0)
            target_item = search_node(root_item)
            if target_item:
                idx = self.model.indexFromItem(target_item)
                self.tree_view.setCurrentIndex(idx)
                self.tree_view.scrollTo(idx)
                return True
        return False

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
        menu.setStyleSheet("""
            QMenu {
                background-color: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item:selected {
                background-color: #1e3a8a;
            }
        """)

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

            if t_item:
                t_item.setText(str(total) if total > 0 else "0")
                t_item.setForeground(QColor("#f8fafc" if total > 0 else "#475569"))
            if r_item:
                r_item.setText(str(raw) if raw > 0 else "0")
                r_item.setForeground(QColor("#f472b6" if raw > 0 else "#475569"))
            if j_item:
                j_item.setText(str(jpg) if jpg > 0 else "0")
                j_item.setForeground(QColor("#38bdf8" if jpg > 0 else "#475569"))
