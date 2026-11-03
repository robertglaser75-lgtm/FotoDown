"""Hotplug notification banner displayed when an SD card or camera drive is inserted."""

from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget
)

from core.drive_detector import DriveInfo


class CardNotificationBanner(QFrame):
    scan_requested = Signal(str)  # Emits path to scan
    dismissed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("cardNotification")
        self.current_drive_path: Optional[str] = None
        self._target_scan_path: Optional[str] = None
        self._setup_ui()
        self.hide()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(12)

        self.lbl_icon = QLabel("\U0001F4F8")  # Camera emoji
        self.lbl_icon.setStyleSheet("font-size: 18px;")
        layout.addWidget(self.lbl_icon)

        self.lbl_text = QLabel("Neue Speicherkarte erkannt.")
        self.lbl_text.setObjectName("cardNotificationLabel")
        self.lbl_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.lbl_text, stretch=1)

        self.btn_scan = QPushButton("\U0001F50D Jetzt Fotos scannen")
        self.btn_scan.setObjectName("btnCardScan")
        self.btn_scan.clicked.connect(self._on_scan_clicked)
        layout.addWidget(self.btn_scan)

        self.btn_dismiss = QPushButton("✕ Ausblenden")
        self.btn_dismiss.setObjectName("btnCardDismiss")
        self.btn_dismiss.clicked.connect(self.hide_card)
        layout.addWidget(self.btn_dismiss)

    def show_card(self, drive: DriveInfo):
        """Displays notification for the newly detected drive."""
        self.current_drive_path = str(drive.path)
        scan_target = drive.dcim_path if drive.has_dcim and drive.dcim_path else drive.path
        self._target_scan_path = str(scan_target)

        dcim_note = " (mit DCIM-Kamera-Ordner)" if drive.has_dcim else ""
        space_note = f" • {drive.space.free_str} frei" if drive.space and drive.space.total_bytes > 0 else ""
        label_txt = f" ({drive.label})" if drive.label and drive.label != drive.letter else ""

        self.lbl_text.setText(
            f"<b>Neue Speicherkarte erkannt:</b> {drive.letter}{label_txt}{space_note}{dcim_note}"
        )
        self.show()

    def hide_card(self):
        """Hides the notification banner."""
        self.hide()
        self.current_drive_path = None
        self._target_scan_path = None
        self.dismissed.emit()

    def _on_scan_clicked(self):
        target = self._target_scan_path or self.current_drive_path
        if target:
            self.scan_requested.emit(target)
        self.hide_card()

