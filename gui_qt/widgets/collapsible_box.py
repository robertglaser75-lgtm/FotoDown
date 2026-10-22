"""Collapsible container widget with clean toggle header."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget
)


class CollapsibleBox(QWidget):
    def __init__(self, title: str, parent=None, is_expanded=True):
        super().__init__(parent)
        self.is_expanded = is_expanded

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header bar
        self.header = QFrame()
        self.header.setObjectName("collapsibleHeader")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(8, 6, 8, 6)

        self.btn_toggle = QPushButton("\u25BC" if is_expanded else "\u25B6")
        self.btn_toggle.setFixedSize(24, 24)
        self.btn_toggle.setObjectName("toggleBtn")
        self.btn_toggle.clicked.connect(self.toggle)

        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("sectionTitle")

        header_layout.addWidget(self.btn_toggle)
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()

        main_layout.addWidget(self.header)

        # Content area
        self.content_area = QFrame()
        self.content_area.setObjectName("collapsibleContent")
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.addWidget(self.content_area)

        if not self.is_expanded:
            self.content_area.setVisible(False)

    def toggle(self):
        self.is_expanded = not self.is_expanded
        self.content_area.setVisible(self.is_expanded)
        self.btn_toggle.setText("\u25BC" if self.is_expanded else "\u25B6")

    def set_content_widget(self, widget: QWidget):
        self.content_layout.addWidget(widget)
