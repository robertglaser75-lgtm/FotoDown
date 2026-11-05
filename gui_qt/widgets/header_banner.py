"""Header banner widget with drive detection and action buttons."""

from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QSizePolicy, QWidget
)

from core.drive_detector import detect_drives, DriveInfo, eject_drive
from core.version import __version__


class HeaderBanner(QFrame):
    drive_selected = Signal(str)  # Emits chosen source folder path
    drive_ejected = Signal(str)   # Emits ejected drive path
    open_history = Signal()
    open_help = Signal()
    tab_changed = Signal(int)     # Emits 0 for Import, 1 for Culling

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("headerBanner")
        self.setMaximumHeight(42)
        self._drives: List[DriveInfo] = []
        self._setup_ui()
        self.refresh_drives()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(10)

        # Title & Version (compact and vertically centered)
        title_box = QHBoxLayout()
        title_box.setSpacing(6)
        title_box.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        lbl_logo = QLabel("\U0001F4F8")  # Camera emoji
        lbl_logo.setObjectName("logoIcon")
        lbl_title = QLabel("FotoDown")
        lbl_title.setObjectName("appTitle")

        lbl_version = QLabel(f"v{__version__}")
        lbl_version.setObjectName("versionBadge")
        lbl_version.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_box.addWidget(lbl_logo, 0, Qt.AlignmentFlag.AlignVCenter)
        title_box.addWidget(lbl_title, 0, Qt.AlignmentFlag.AlignVCenter)
        title_box.addWidget(lbl_version, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(title_box)

        layout.addSpacing(6)

        # Main Workflow Tabs (1. Importieren | 2. Sichten & Sortieren)
        tabs_box = QHBoxLayout()
        tabs_box.setSpacing(2)
        self.btn_tab_import = QPushButton("📥 1. Importieren")
        self.btn_tab_import.setCheckable(True)
        self.btn_tab_import.setChecked(True)
        self.btn_tab_import.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; color: #94a3b8; border: 1px solid #334155;
                border-radius: 4px; padding: 4px 10px; font-weight: 600; font-size: 11px;
            }
            QPushButton:checked {
                background-color: #0284c7; color: white; border: 1px solid #38bdf8;
            }
        """)

        self.btn_tab_culling = QPushButton("👁️ 2. Sichten & Sortieren")
        self.btn_tab_culling.setCheckable(True)
        self.btn_tab_culling.setChecked(False)
        self.btn_tab_culling.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; color: #94a3b8; border: 1px solid #334155;
                border-radius: 4px; padding: 4px 10px; font-weight: 600; font-size: 11px;
            }
            QPushButton:checked {
                background-color: #0284c7; color: white; border: 1px solid #38bdf8;
            }
        """)

        self.btn_tab_import.clicked.connect(lambda: self.switch_tab(0))
        self.btn_tab_culling.clicked.connect(lambda: self.switch_tab(1))
        tabs_box.addWidget(self.btn_tab_import)
        tabs_box.addWidget(self.btn_tab_culling)
        layout.addLayout(tabs_box)

        layout.addSpacing(6)

        # Drive selector section
        lbl_drive = QLabel("Speicherkarte / Laufwerk:")
        lbl_drive.setObjectName("subtleLabel")
        layout.addWidget(lbl_drive, 0, Qt.AlignmentFlag.AlignVCenter)

        self.combo_drives = QComboBox()
        self.combo_drives.setObjectName("driveCombo")
        self.combo_drives.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo_drives.currentIndexChanged.connect(self._on_drive_changed)
        layout.addWidget(self.combo_drives, stretch=1)

        self.btn_refresh = QPushButton("\u21BB Neu laden")
        self.btn_refresh.setObjectName("secondaryBtn")
        self.btn_refresh.setToolTip("Laufwerke und Speicherkarten erneut scannen")
        self.btn_refresh.clicked.connect(self.refresh_drives)
        layout.addWidget(self.btn_refresh, 0, Qt.AlignmentFlag.AlignVCenter)

        self.btn_eject = QPushButton("\u23CF Auswerfen")
        self.btn_eject.setObjectName("secondaryBtn")
        self.btn_eject.setToolTip("Ausgewähltes Wechsellaufwerk sicher entfernen")
        self.btn_eject.clicked.connect(self._on_eject_clicked)
        layout.addWidget(self.btn_eject, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addSpacing(10)

        # History & Help buttons
        self.btn_history = QPushButton("\U0001F4DC Historie")
        self.btn_history.setObjectName("secondaryBtn")
        self.btn_history.clicked.connect(self.open_history.emit)
        layout.addWidget(self.btn_history, 0, Qt.AlignmentFlag.AlignVCenter)

        self.btn_help = QPushButton("? Hilfe")
        self.btn_help.setObjectName("secondaryBtn")
        self.btn_help.clicked.connect(self.open_help.emit)
        layout.addWidget(self.btn_help, 0, Qt.AlignmentFlag.AlignVCenter)

    def switch_tab(self, tab_idx: int):
        self.btn_tab_import.setChecked(tab_idx == 0)
        self.btn_tab_culling.setChecked(tab_idx == 1)
        self.tab_changed.emit(tab_idx)

    def set_drives(self, drives: List[DriveInfo]):
        """Updates the dropdown list with a given set of drives, preserving selection if possible."""
        self.combo_drives.blockSignals(True)
        prev_data = self.combo_drives.currentData()
        self.combo_drives.clear()
        self._drives = drives

        if not self._drives:
            self.combo_drives.addItem("Keine Speicherkarten / Wechsellaufwerke gefunden", None)
            self.combo_drives.setEnabled(False)
            self.btn_eject.setEnabled(False)
        else:
            self.combo_drives.setEnabled(True)
            self.btn_eject.setEnabled(True)
            auto_select_idx = 0
            for idx, d in enumerate(self._drives):
                item_data = str(d.dcim_path or d.path)
                self.combo_drives.addItem(d.display_name, item_data)
                if prev_data and item_data == prev_data:
                    auto_select_idx = idx
                elif not prev_data and d.has_dcim:
                    auto_select_idx = idx

            self.combo_drives.setCurrentIndex(auto_select_idx)
            self.drive_selected.emit(self.combo_drives.currentData())

        self.combo_drives.blockSignals(False)

    def refresh_drives(self):
        """Scans system for drives and updates UI."""
        self.set_drives(detect_drives())

    def _on_drive_changed(self, index: int):
        path = self.combo_drives.currentData()
        if path:
            self.drive_selected.emit(path)

    def _on_eject_clicked(self):
        path = self.combo_drives.currentData()
        if not path:
            QMessageBox.information(self, "Auswerfen", "Kein aktives Wechsellaufwerk gewählt.")
            return

        ok, msg = eject_drive(path)
        if ok:
            self.drive_ejected.emit(str(path))
            QMessageBox.information(self, "Sicher entfernen", msg)
            self.refresh_drives()
        else:
            QMessageBox.warning(self, "Auswerfen fehlgeschlagen", msg)
