"""Gallery view displaying media items in a responsive virtualized grid with quick preview."""

from pathlib import Path
from typing import Optional
from PySide6.QtCore import QItemSelection, QItemSelectionModel, QModelIndex, QSize, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QKeyEvent
from PySide6.QtWidgets import QAbstractItemView, QApplication, QListView

from core.importer import ScanItem
from .delegates import GalleryDelegate


class MediaGalleryView(QListView):
    selection_toggled = Signal()
    open_preview_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setWordWrap(True)
        self.setSpacing(8)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        self._last_index: Optional[QModelIndex] = None

        self.delegate = GalleryDelegate(self)
        self.setItemDelegate(self.delegate)
        self.setGridSize(self.delegate.card_size + QSize(8, 8))

        self.clicked.connect(self._on_clicked)
        self.doubleClicked.connect(self._on_double_clicked)

    def set_thumbnail_size(self, size: int):
        """Changes thumbnail size and reflows layout."""
        self.delegate.set_scale(size)
        self.setGridSize(self.delegate.card_size + QSize(8, 8))
        self.doItemsLayout()

    def _on_clicked(self, index: QModelIndex):
        if not index.isValid():
            return

        model = self.model()
        if not model:
            return

        modifiers = QApplication.keyboardModifiers()
        is_range = bool(modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier))

        if is_range and self._last_index and self._last_index.isValid() and 0 <= self._last_index.row() < model.rowCount():
            start_row = min(self._last_index.row(), index.row())
            end_row = max(self._last_index.row(), index.row())
            for r in range(start_row, end_row + 1):
                idx = model.index(r, 0)
                item: ScanItem = idx.data(Qt.ItemDataRole.UserRole)
                if item:
                    item.selected = True

            top_idx = model.index(start_row, 0)
            bot_idx = model.index(end_row, 0)
            model.dataChanged.emit(top_idx, bot_idx)

            if self.selectionModel():
                sel = QItemSelection(top_idx, bot_idx)
                self.selectionModel().select(sel, QItemSelectionModel.SelectionFlag.Select)

            self.selection_toggled.emit()
            self._last_index = index
        else:
            item: ScanItem = index.data(Qt.ItemDataRole.UserRole)
            if item:
                item.selected = not item.selected
                model.dataChanged.emit(index, index)
                self.selection_toggled.emit()
                self._last_index = index

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
            idx = self.currentIndex()
            if idx.isValid():
                self._on_clicked(idx)
                return
        super().keyPressEvent(event)
