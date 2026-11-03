"""Scan items table model with checkbox and sorting support."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor, QBrush

from core.importer import ScanItem


class ScanTableModel(QAbstractTableModel):
    selection_changed = Signal()

    COLUMNS = [
        "\u2713",  # Checkmark for column 0
        "Status",
        "Originalname",
        "Neuer Dateiname",
        "Aufnahmedatum",
        "Kamera",
        "Typ",
        "Größe"
    ]

    STATUS_COLORS = {
        "Neu": QColor("#4ade80"),
        "Bereits importiert": QColor("#94a3b8"),
        "Existiert im Ziel": QColor("#fbbf24"),
        "Fehler": QColor("#f87171"),
    }

    def __init__(self, items: Optional[List[ScanItem]] = None):
        super().__init__()
        self._items: List[ScanItem] = items or []

    def set_items(self, items: List[ScanItem]):
        self.beginResetModel()
        self._items = items
        self.endResetModel()
        self.selection_changed.emit()

    def get_items(self) -> List[ScanItem]:
        return self._items

    def get_item(self, row: int) -> Optional[ScanItem]:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._items)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == 0:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._items):
            return None

        item = self._items[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.CheckStateRole and col == 0:
            return Qt.CheckState.Checked if item.selected else Qt.CheckState.Unchecked

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return ""
            elif col == 1:
                return item.status
            elif col == 2:
                return item.source_path.name
            elif col == 3:
                return item.target_path.name
            elif col == 4:
                dt = item.metadata.date_taken
                return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "Unbekannt"
            elif col == 5:
                return item.metadata.formatted_camera or "-"
            elif col == 6:
                return item.display_type
            elif col == 7:
                size_mb = item.total_size / (1024 * 1024)
                if size_mb >= 1.0:
                    return f"{size_mb:.1f} MB"
                return f"{item.total_size / 1024:.0f} KB"

        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == 1:
                color = self.STATUS_COLORS.get(item.status)
                if color:
                    return QBrush(color)

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (0, 1, 6, 7):
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        elif role == Qt.ItemDataRole.UserRole:
            return item

        return None

    def setData(self, index: QModelIndex, value, role=Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid() or index.row() >= len(self._items):
            return False

        if index.column() == 0 and role == Qt.ItemDataRole.CheckStateRole:
            self._items[index.row()].selected = (value == Qt.CheckState.Checked)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            self.selection_changed.emit()
            return True

        return False

    def select_all(self):
        for item in self._items:
            item.selected = True
        if self._items:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._items) - 1, 0),
                [Qt.ItemDataRole.CheckStateRole]
            )
        self.selection_changed.emit()

    def deselect_all(self):
        for item in self._items:
            item.selected = False
        if self._items:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._items) - 1, 0),
                [Qt.ItemDataRole.CheckStateRole]
            )
        self.selection_changed.emit()

    def select_only_new(self):
        for item in self._items:
            item.selected = (item.status == "Neu")
        if self._items:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._items) - 1, 0),
                [Qt.ItemDataRole.CheckStateRole]
            )
        self.selection_changed.emit()
