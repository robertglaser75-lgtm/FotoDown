"""Collapsible container widget with full-bar click support and clear toggle indicator."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLayout, QPushButton,
    QVBoxLayout, QWidget
)


class ClickableHeaderFrame(QFrame):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
        else:
            super().mousePressEvent(event)


class CollapsibleBox(QWidget):
    toggled = Signal(bool)

    def __init__(self, title: str, parent=None, is_expanded=True):
        super().__init__(parent)
        self.is_expanded = is_expanded

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        # 1. Full-width clickable header bar
        self.header = ClickableHeaderFrame()
        self.header.setObjectName("collapsibleHeader")
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header.setToolTip("Klicken zum Ein- oder Ausklappen")
        self.header.clicked.connect(self.toggle)

        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(10, 8, 10, 8)
        header_layout.setSpacing(8)

        # Leading chevron icon
        self.lbl_chevron = QLabel("\u25BC" if is_expanded else "\u25B6")
        self.lbl_chevron.setObjectName("chevronIcon")
        header_layout.addWidget(self.lbl_chevron)

        # Title
        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("sectionTitle")
        header_layout.addWidget(self.lbl_title)

        header_layout.addStretch()

        # Trailing action hint pill
        self.btn_toggle_hint = QPushButton("Einklappen \u25B2" if is_expanded else "Ausklappen \u25BC")
        self.btn_toggle_hint.setObjectName("toggleHint")
        self.btn_toggle_hint.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_hint.clicked.connect(self.toggle)
        header_layout.addWidget(self.btn_toggle_hint)

        main_layout.addWidget(self.header)

        # 2. Collapsible content area
        self.content_area = QFrame()
        self.content_area.setObjectName("collapsibleContent")
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(12, 10, 12, 10)
        self.content_layout.setSpacing(8)
        main_layout.addWidget(self.content_area)

        if not self.is_expanded:
            self.content_area.setVisible(False)

    def toggle(self):
        """Toggles between expanded and collapsed state."""
        self.set_expanded(not self.is_expanded)

    def set_expanded(self, expanded: bool):
        """Explicitly sets the expanded state and updates labels."""
        self.is_expanded = expanded
        self.content_area.setVisible(self.is_expanded)
        self.lbl_chevron.setText("\u25BC" if self.is_expanded else "\u25B6")
        self.btn_toggle_hint.setText("Einklappen \u25B2" if self.is_expanded else "Ausklappen \u25BC")
        self.toggled.emit(self.is_expanded)

    def set_content_widget(self, widget: QWidget):
        """Adds a widget to the collapsible content area."""
        self.content_layout.addWidget(widget)
