"""Table view for media items with column sorting, quick preview and selection."""

from pathlib import Path
from PySide6.QtCore import QModelIndex, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QKeyEvent
from PySide6.QtWidgets import QTableView, QHeaderView, QAbstractItemView

from core.importer import ScanItem


class MediaTableView(QTableView):
    open_preview_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setHighlightSections(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.doubleClicked.connect(self._on_double_clicked)

    def setup_column_widths(self):
        h = self.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 50)  # Checkbox
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Status
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)       # Original
        self.setColumnWidth(2, 200)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)       # Target
        self.setColumnWidth(3, 240)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Date
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Camera
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Type
        h.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)  # Size

    def _on_double_clicked(self, index: QModelIndex):
        if not index.isValid():
            return
        self.open_preview_requested.emit(index)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Space:
            idx = self.currentIndex()
            if idx.isValid():
                self.open_preview_requested.emit(idx)
                return
        super().keyPressEvent(event)
