"""Paired / Zero-Sum Column Resizing Header for QTableView and QTableWidget."""

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHeaderView, QWidget


class PairedHeaderView(QHeaderView):
    """A horizontal QHeaderView where dragging a section boundary resizes adjacent columns in a zero-sum manner.

    Dragging the right edge of column i to the right enlarges column i and shrinks column i+1.
    Dragging it to the left shrinks column i and enlarges column i+1.
    """

    def __init__(self, orientation: Qt.Orientation = Qt.Orientation.Horizontal, parent: Optional[QWidget] = None):
        super().__init__(orientation, parent)
        self._user_resizing: bool = False
        self._resizing_in_progress: bool = False
        self.sectionResized.connect(self._on_section_resized)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._user_resizing = True
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        self._user_resizing = False

    def _on_section_resized(self, logical_index: int, old_size: int, new_size: int):
        if not self._user_resizing or self._resizing_in_progress:
            return

        delta = new_size - old_size
        if delta == 0:
            return

        # Find the next visible section visually to the right of logical_index
        v_idx = self.visualIndex(logical_index)
        next_logical = -1
        for next_v in range(v_idx + 1, self.count()):
            log_i = self.logicalIndex(next_v)
            if not self.isSectionHidden(log_i):
                next_logical = log_i
                break

        if next_logical == -1:
            return

        self._resizing_in_progress = True
        try:
            next_size = self.sectionSize(next_logical)
            min_size = max(24, self.minimumSectionSize())
            # Clamped reduction or expansion for the adjacent column
            clamped_next_size = max(min_size, next_size - delta)
            actual_change = next_size - clamped_next_size
            if actual_change != delta:
                # If adjacent column could not provide full delta, clamp current section
                self.resizeSection(logical_index, old_size + actual_change)
            self.resizeSection(next_logical, clamped_next_size)
        finally:
            self._resizing_in_progress = False
