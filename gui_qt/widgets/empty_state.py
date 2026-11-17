"""Empty state placeholder widget for when no media has been scanned yet."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QLabel, QPushButton, QVBoxLayout, QWidget
)

from gui_qt.styles.icons import get_camera_icon, get_search_icon, get_icon_color
from gui_qt.styles.theme import theme_manager


class EmptyStateWidget(QFrame):
    scan_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("emptyStateFrame")
        self._setup_ui()
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(14)
        layout.setContentsMargins(40, 40, 40, 40)

        # Large vector icon
        self.lbl_icon = QLabel()
        self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_icon.setPixmap(get_camera_icon(get_icon_color("accent"), 56).pixmap(56, 56))
        layout.addWidget(self.lbl_icon)

        # Title
        self.lbl_title = QLabel("Noch keine Fotos eingelesen")
        self.lbl_title.setObjectName("emptyStateTitle")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_title)

        # Description
        self.lbl_desc = QLabel(
            "Wählen Sie links Ihre Speicherkarte oder einen Quellordner aus\n"
            "und klicken Sie auf 'Scannen', um Fotos und Videos zu laden."
        )
        self.lbl_desc.setObjectName("emptyStateDesc")
        self.lbl_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_desc)

        layout.addSpacing(6)

        # Quick start Scan button
        self.btn_scan = QPushButton("Jetzt scannen")
        self.btn_scan.setObjectName("primaryBtn")
        self.btn_scan.setIcon(get_search_icon("#ffffff", 14))
        self.btn_scan.setFixedWidth(180)
        self.btn_scan.setStyleSheet("font-size: 13px; padding: 10px 18px;")
        self.btn_scan.clicked.connect(self.scan_requested.emit)
        layout.addWidget(self.btn_scan, alignment=Qt.AlignmentFlag.AlignCenter)

    def _on_theme_changed(self, theme_name: str):
        self.lbl_icon.setPixmap(get_camera_icon(get_icon_color("accent"), 56).pixmap(56, 56))

