"""Empty state placeholder widget for when no media has been scanned yet."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QLabel, QPushButton, QVBoxLayout, QWidget
)


class EmptyStateWidget(QFrame):
    scan_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("emptyStateFrame")
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            QFrame#emptyStateFrame {
                background-color: #0b1120;
                border: 1px dashed #334155;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(14)
        layout.setContentsMargins(40, 40, 40, 40)

        # Large icon
        lbl_icon = QLabel("\U0001F4F8")  # Camera emoji
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_icon.setStyleSheet("font-size: 54px; color: #38bdf8;")
        layout.addWidget(lbl_icon)

        # Title
        lbl_title = QLabel("Noch keine Fotos eingelesen")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #f8fafc;")
        layout.addWidget(lbl_title)

        # Description
        lbl_desc = QLabel(
            "Wählen Sie links Ihre Speicherkarte oder einen Quellordner aus\n"
            "und klicken Sie auf 'Scannen', um Fotos und Videos zu laden."
        )
        lbl_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_desc.setStyleSheet("font-size: 13px; color: #94a3b8; line-height: 1.4;")
        layout.addWidget(lbl_desc)

        layout.addSpacing(6)

        # Quick start Scan button
        self.btn_scan = QPushButton("\U0001F50D Jetzt scannen")
        self.btn_scan.setObjectName("primaryBtn")
        self.btn_scan.setFixedWidth(180)
        self.btn_scan.setStyleSheet("font-size: 13px; padding: 10px 18px;")
        self.btn_scan.clicked.connect(self.scan_requested.emit)
        layout.addWidget(self.btn_scan, alignment=Qt.AlignmentFlag.AlignCenter)
