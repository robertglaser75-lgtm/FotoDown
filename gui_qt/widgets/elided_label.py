"""Reusable QLabel subclass supporting automatic text eliding (Middle, Right, Left).

Prevents layout breakage and awkward clipping of long file paths and names
on small laptop viewports and narrow splitters, while preserving tooltip inspection.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics, QPaintEvent, QPainter
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget


class ElidedLabel(QLabel):
    """A QLabel that automatically truncates its displayed text with an ellipsis (...)

    using the configured Qt.TextElideMode (default: ElideMiddle for file paths)
    whenever the container is too narrow, while preserving the full text in tooltips.
    """

    def __init__(
        self,
        text: str = "",
        elide_mode: Qt.TextElideMode = Qt.TextElideMode.ElideMiddle,
        parent: QWidget = None,
    ):
        super().__init__(text, parent)
        self._full_text = text
        self._elide_mode = elide_mode
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setToolTip(text)

    def set_full_text(self, text: str) -> None:
        """Sets new full text and automatically refreshes display and tooltip."""
        self._full_text = text or ""
        self.setToolTip(self._full_text)
        super().setText(self._full_text)
        self.update()

    def setText(self, text: str) -> None:
        """Overrides setText to maintain full text."""
        self._full_text = text or ""
        self.setToolTip(self._full_text)
        super().setText(self._full_text)
        self.update()

    def text(self) -> str:
        """Returns the untruncated original text string."""
        return self._full_text

    def full_text(self) -> str:
        """Returns the untruncated original text string."""
        return self._full_text

    def set_elide_mode(self, mode: Qt.TextElideMode) -> None:
        """Sets the eliding mode (ElideMiddle, ElideRight, ElideLeft)."""
        self._elide_mode = mode
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Custom paint event that elides the string based on the current label width."""
        painter = QPainter(self)
        metrics = QFontMetrics(self.font())
        available_width = max(0, self.width() - 4)

        elided = metrics.elidedText(self._full_text, self._elide_mode, available_width)

        # Draw elided text with alignment
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.setFont(self.font())
        painter.drawText(
            self.rect().adjusted(2, 0, -2, 0),
            int(self.alignment()),
            elided,
        )
        painter.end()
