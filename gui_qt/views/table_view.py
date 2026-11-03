"""Table view for media items with column sorting, quick preview and selection."""

from pathlib import Path
from typing import Optional
from PySide6.QtCore import QItemSelection, QItemSelectionModel, QModelIndex, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QKeyEvent
from PySide6.QtWidgets import QAbstractItemView, QApplication, QHeaderView, QTableView

from core.importer import ScanItem


class MediaTableView(QTableView):
    open_preview_requested = Signal(object)
    selection_toggled = Signal()

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

        self._last_clicked_row: Optional[int] = None

        self.clicked.connect(self._on_clicked)
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

    def _on_clicked(self, index: QModelIndex):
        if not index.isValid():
            return

        model = self.model()
        if not model:
            return

        modifiers = QApplication.keyboardModifiers()
        is_range = bool(modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier))

        if is_range and self._last_clicked_row is not None and 0 <= self._last_clicked_row < model.rowCount():
            start_row = min(self._last_clicked_row, index.row())
            end_row = max(self._last_clicked_row, index.row())
            for r in range(start_row, end_row + 1):
                idx = model.index(r, 0)
                item: ScanItem = idx.data(Qt.ItemDataRole.UserRole)
                if item:
                    item.selected = True

            top_idx = model.index(start_row, 0)
            bot_idx = model.index(end_row, model.columnCount() - 1)
            model.dataChanged.emit(top_idx, bot_idx)

            if self.selectionModel():
                sel = QItemSelection(top_idx, bot_idx)
                self.selectionModel().select(sel, QItemSelectionModel.SelectionFlag.Select)

            self.selection_toggled.emit()
            if hasattr(model, "sourceModel") and hasattr(model.sourceModel(), "selection_changed"):
                model.sourceModel().selection_changed.emit()
            self._last_clicked_row = index.row()
        else:
            self._last_clicked_row = index.row()

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
        elif event.key() == Qt.Key.Key_S:
            indexes = self.selectionModel().selectedRows()
            if indexes:
                any_unselected = any(not idx.data(Qt.ItemDataRole.UserRole).selected for idx in indexes if idx.data(Qt.ItemDataRole.UserRole))
                target_state = any_unselected
                for idx in indexes:
                    it: ScanItem = idx.data(Qt.ItemDataRole.UserRole)
                    if it:
                        it.selected = target_state
                self.model().dataChanged.emit(indexes[0], indexes[-1])
                self.selection_toggled.emit()
                if hasattr(self.model(), "sourceModel") and hasattr(self.model().sourceModel(), "selection_changed"):
                    self.model().sourceModel().selection_changed.emit()
                return
        super().keyPressEvent(event)
