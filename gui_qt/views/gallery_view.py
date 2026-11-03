"""Gallery view displaying media items in a responsive virtualized grid with quick preview."""

from pathlib import Path
from PySide6.QtCore import QModelIndex, QSize, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QKeyEvent
from PySide6.QtWidgets import QListView, QAbstractItemView

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
        item: ScanItem = index.data(Qt.ItemDataRole.UserRole)
        if item:
            item.selected = not item.selected
            self.model().dataChanged.emit(index, index)
            self.selection_toggled.emit()

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
