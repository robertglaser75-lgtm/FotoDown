"""Modern Fluent Dark Splash Screen for FotoDown."""

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar,
    QSplashScreen, QVBoxLayout, QWidget, QApplication
)

from core.version import __version__


class FotoDownSplashScreen(QSplashScreen):
    def __init__(self):
        # Create base pixmap with rounded fluent dark canvas
        width, height = 540, 300
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent)

        super().__init__(pixmap, Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(width, height)

        self._setup_ui()

    def _setup_ui(self):
        container = QFrame(self)
        container.setObjectName("splashCard")
        container.setGeometry(0, 0, self.width(), self.height())
        container.setStyleSheet("""
            QFrame#splashCard {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 12px;
            }
            QLabel {
                background: transparent;
                color: #f8fafc;
                font-family: 'Segoe UI', Ubuntu, sans-serif;
            }
            QProgressBar#splashBar {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 4px;
                height: 6px;
            }
            QProgressBar#splashBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
                border-radius: 3px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(12)

        # Header with Logo, Title & Version
        header = QHBoxLayout()
        header.setSpacing(16)

        lbl_icon = QLabel()
        icon_path = Path("assets") / "icon_256.png"
        if not icon_path.exists():
            icon_path = Path("assets") / "icon.png"
        if icon_path.exists():
            pix = QPixmap(str(icon_path)).scaled(
                64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            lbl_icon.setPixmap(pix)
        else:
            lbl_icon.setText("\U0001F4F8")
            lbl_icon.setStyleSheet("font-size: 48px;")

        header.addWidget(lbl_icon)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        lbl_title = QLabel("FotoDown")
        lbl_title.setStyleSheet("font-size: 26px; font-weight: 800; color: #38bdf8;")

        lbl_ver = QLabel(f"v{__version__}")
        lbl_ver.setStyleSheet(
            "background-color: #0369a1; color: #e0f2fe; font-size: 11px; "
            "font-weight: bold; padding: 2px 8px; border-radius: 8px;"
        )

        title_row.addWidget(lbl_title)
        title_row.addWidget(lbl_ver)
        title_row.addStretch()
        title_box.addLayout(title_row)

        lbl_subtitle = QLabel("Intelligenter Foto-Importeur & EXIF-Manager")
        lbl_subtitle.setStyleSheet("font-size: 13px; color: #94a3b8;")
        title_box.addWidget(lbl_subtitle)

        header.addLayout(title_box)
        layout.addLayout(header)

        layout.addStretch()

        # Loading status info
        self.lbl_status = QLabel("Initialisiere Anwendung...")
        self.lbl_status.setStyleSheet("font-size: 12px; color: #cbd5e1;")
        layout.addWidget(self.lbl_status)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("splashBar")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(10)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        layout.addWidget(self.progress_bar)

    def set_status(self, message: str, step: int, max_steps: int = 5):
        """Updates the splash progress and message, repainting immediately."""
        self.lbl_status.setText(message)
        pct = int((step / max_steps) * 100)
        self.progress_bar.setValue(pct)
        QApplication.processEvents()

