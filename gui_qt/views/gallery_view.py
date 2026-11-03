"""Gallery view displaying media items in a responsive virtualized grid."""

from pathlib import Path
from PySide6.QtCore import QSize, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QListView, QAbstractItemView

from core.importer import ScanItem
from .delegates import GalleryDelegate


class MediaGalleryView(QListView):
    selection_toggled = Signal()

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

    def _on_clicked(self, index):
        if not index.isValid():
            return
        item: ScanItem = index.data(Qt.ItemDataRole.UserRole)
        if item:
            item.selected = not item.selected
            self.model().dataChanged.emit(index, index)
            self.selection_toggled.emit()

    def _on_double_clicked(self, index):
        if not index.isValid():
            return
        item: ScanItem = index.data(Qt.ItemDataRole.UserRole)
        if item and item.source_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(item.source_path)))
