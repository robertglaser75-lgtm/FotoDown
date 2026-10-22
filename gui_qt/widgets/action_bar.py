"""Action buttons and progress status bar."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QVBoxLayout, QWidget
)


class ActionBarWidget(QWidget):
    scan_clicked = Signal()
    import_clicked = Signal()
    cancel_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)

        # Buttons row
        btn_box = QHBoxLayout()
        btn_box.setSpacing(12)

        self.btn_scan = QPushButton("\U0001F50D Speicherkarte / Ordner scannen")
        self.btn_scan.setObjectName("scanBtn")
        self.btn_scan.clicked.connect(self.scan_clicked.emit)

        self.btn_import = QPushButton("\u2B07 Importieren starten")
        self.btn_import.setObjectName("primaryBtn")
        self.btn_import.setEnabled(False)
        self.btn_import.clicked.connect(self.import_clicked.emit)

        self.btn_cancel = QPushButton("\u2715 Abbrechen")
        self.btn_cancel.setObjectName("dangerBtn")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self.cancel_clicked.emit)

        btn_box.addWidget(self.btn_scan)
        btn_box.addWidget(self.btn_import)
        btn_box.addWidget(self.btn_cancel)
        btn_box.addStretch()

        layout.addLayout(btn_box)

        # Progress row
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Bereit zum Scannen.")
        self.lbl_status.setObjectName("statusText")
        layout.addWidget(self.lbl_status)

    def set_busy(self, busy: bool, task_name: str = ""):
        self.btn_scan.setEnabled(not busy)
        self.btn_import.setEnabled(not busy)
        self.btn_cancel.setVisible(busy)
        self.progress_bar.setVisible(busy)
        if busy:
            self.lbl_status.setText(f"{task_name} läuft...")

    def update_progress(self, percent: float, msg: str):
        self.progress_bar.setValue(int(percent))
        self.lbl_status.setText(msg)
