"""Hierarchical Target Directory Tree View for simulating the resulting folder structure."""

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import Qt, Signal, QModelIndex
from PySide6.QtGui import QColor, QFont, QIcon, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QTreeView, QVBoxLayout, QWidget
)

from core.drive_detector import format_size
from core.importer import ScanItem


class MediaTreeView(QWidget):
    item_selected = Signal(object)  # Emits ScanItem when selected
    open_preview_requested = Signal(object)  # Emits ScanItem on double click

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: List[ScanItem] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header summary bar
        header = QHBoxLayout()
        header.setContentsMargins(4, 2, 4, 2)
        header.setSpacing(8)

        self.lbl_summary = QLabel("📁 Zielstruktur-Simulation")
        self.lbl_summary.setObjectName("sectionSubTitle")
        self.lbl_summary.setStyleSheet("font-weight: 600; color: #38bdf8;")
        header.addWidget(self.lbl_summary, stretch=1)

        btn_expand = QPushButton("➕ Alle ausklappen")
        btn_expand.setObjectName("secondaryBtn")
        btn_expand.clicked.connect(lambda: self.tree.expandAll())
        header.addWidget(btn_expand)

        btn_collapse = QPushButton("➖ Alle einklappen")
        btn_collapse.setObjectName("secondaryBtn")
        btn_collapse.clicked.connect(lambda: self.tree.collapseAll())
        header.addWidget(btn_collapse)

        layout.addLayout(header)

        # QTreeView with StandardItemModel
        self.tree = QTreeView()
        self.tree.setObjectName("targetTreeView")
        self.tree.setHeaderHidden(False)
        self.tree.setAnimated(True)
        self.tree.setIndentation(22)
        self.tree.setAlternatingRowColors(True)

        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Ziel-Ordner / Dateiname", "Status", "Typ", "Größe"])
        self.tree.setModel(self.model)

        self.tree.selectionModel().currentChanged.connect(self._on_current_changed)
        self.tree.doubleClicked.connect(self._on_double_clicked)

        layout.addWidget(self.tree)

    def set_items(self, items: List[ScanItem], target_root: Optional[str] = None):
        """Builds a hierarchical tree from the scanned items and their planned target paths."""
        self._items = items
        self.model.removeRows(0, self.model.rowCount())

        if not items:
            self.lbl_summary.setText("📁 Keine Dateien vorhanden. Bitte Quellordner scannen.")
            return

        # Group items by their planned target directory
        folders: Dict[Path, List[ScanItem]] = defaultdict(list)
        total_bytes = 0

        for it in items:
            folders[it.target_path.parent].append(it)
            total_bytes += it.total_size

        folder_count = len(folders)
        file_count = len(items)
        self.lbl_summary.setText(
            f"📁 Zielstruktur: {folder_count} Ziel-Ordner werden erstellt • {file_count} Dateien ({format_size(total_bytes)})"
        )

        # Sort folder paths
        sorted_folders = sorted(folders.keys())

        # Determine common root if possible
        for folder_path in sorted_folders:
            folder_items = folders[folder_path]
            folder_size = sum(it.total_size for it in folder_items)

            # Folder row
            folder_name_item = QStandardItem(f"📁 {folder_path.name or str(folder_path)}")
            folder_name_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            folder_name_item.setForeground(QColor("#38bdf8"))
            folder_name_item.setToolTip(str(folder_path))

            folder_status_item = QStandardItem(f"{len(folder_items)} Dateien")
            folder_status_item.setForeground(QColor("#94a3b8"))

            folder_type_item = QStandardItem("Verzeichnis")
            folder_type_item.setForeground(QColor("#64748b"))

            folder_size_item = QStandardItem(format_size(folder_size))
            folder_size_item.setForeground(QColor("#cbd5e1"))

            # Add child files under this folder
            for it in sorted(folder_items, key=lambda x: x.target_path.name):
                # File row
                file_icon = "📷" if it.metadata.is_raw else ("🎥" if it.metadata.is_video else "🖼️")
                file_name_item = QStandardItem(f"{file_icon} {it.target_path.name}")
                file_name_item.setData(it, Qt.ItemDataRole.UserRole)

                status_color = "#4ade80" if it.status == "Neu" else ("#fbbf24" if it.status == "Existiert im Ziel" else "#94a3b8")
                status_item = QStandardItem(it.status)
                status_item.setForeground(QColor(status_color))

                type_item = QStandardItem(it.display_type)
                type_item.setForeground(QColor("#cbd5e1"))

                size_item = QStandardItem(format_size(it.total_size))
                size_item.setForeground(QColor("#94a3b8"))

                folder_name_item.appendRow([file_name_item, status_item, type_item, size_item])

                # If paired companion has a distinct destination, also add companion
                if it.is_pair and it.companion_target_path and it.companion_target_path.parent == folder_path:
                    comp_name_item = QStandardItem(f"   ↳ 🖼️ {it.companion_target_path.name}")
                    comp_name_item.setData(it, Qt.ItemDataRole.UserRole)
                    comp_name_item.setForeground(QColor("#a5b4fc"))

                    comp_status = QStandardItem(it.status)
                    comp_status.setForeground(QColor(status_color))

                    comp_type = QStandardItem("JPG (Gepaart)")
                    comp_type.setForeground(QColor("#818cf8"))

                    comp_size = QStandardItem(format_size(it.companion_metadata.file_size if it.companion_metadata else 0))
                    comp_size.setForeground(QColor("#94a3b8"))

                    folder_name_item.appendRow([comp_name_item, comp_status, comp_type, comp_size])

            self.model.appendRow([folder_name_item, folder_status_item, folder_type_item, folder_size_item])

        self.tree.expandAll()
        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(1)
        self.tree.resizeColumnToContents(2)

    def _on_current_changed(self, current: QModelIndex, previous: QModelIndex):
        if not current.isValid():
            return
        item_data = current.data(Qt.ItemDataRole.UserRole)
        if isinstance(item_data, ScanItem):
            self.item_selected.emit(item_data)

    def _on_double_clicked(self, index: QModelIndex):
        if not index.isValid():
            return
        item_data = index.data(Qt.ItemDataRole.UserRole)
        if isinstance(item_data, ScanItem):
            self.open_preview_requested.emit(item_data)
