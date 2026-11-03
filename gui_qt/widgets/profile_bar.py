"""Profile / Preset selection bar widget for quick switching, saving and creating presets."""

from typing import List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QInputDialog,
    QLabel, QMessageBox, QPushButton, QSizePolicy, QWidget
)

from core.config import AppConfig


class ProfileBarWidget(QFrame):
    profile_selected = Signal(str)
    profile_saved = Signal(str)
    profile_created = Signal(str)
    profile_deleted = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("profileBar")
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        lbl_icon = QLabel("\U0001F4CB")  # Clipboard / preset icon
        lbl_icon.setStyleSheet("font-size: 14px;")
        layout.addWidget(lbl_icon)

        lbl_title = QLabel("Profil:")
        lbl_title.setObjectName("sectionSubTitle")
        lbl_title.setStyleSheet("font-weight: 600; font-size: 12px; color: #38bdf8;")
        layout.addWidget(lbl_title)

        self.combo_profiles = QComboBox()
        self.combo_profiles.setObjectName("profileCombo")
        self.combo_profiles.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo_profiles.currentIndexChanged.connect(self._on_combo_changed)
        layout.addWidget(self.combo_profiles, stretch=1)

        self.btn_save = QPushButton("💾")
        self.btn_save.setObjectName("secondaryBtn")
        self.btn_save.setToolTip("Aktuelle Einstellungen im gewählten Profil speichern")
        self.btn_save.setFixedSize(28, 28)
        self.btn_save.clicked.connect(self._on_save_clicked)
        layout.addWidget(self.btn_save)

        self.btn_new = QPushButton("➕")
        self.btn_new.setObjectName("secondaryBtn")
        self.btn_new.setToolTip("Neues Profil mit den aktuellen Einstellungen erstellen")
        self.btn_new.setFixedSize(28, 28)
        self.btn_new.clicked.connect(self._on_new_clicked)
        layout.addWidget(self.btn_new)

        self.btn_delete = QPushButton("🗑️")
        self.btn_delete.setObjectName("secondaryBtn")
        self.btn_delete.setToolTip("Aktuelles Profil löschen")
        self.btn_delete.setFixedSize(28, 28)
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self.btn_delete)

    def load_profiles(self, config: AppConfig):
        """Populates the combo box from config and sets current active profile."""
        self.combo_profiles.blockSignals(True)
        self.combo_profiles.clear()

        names = sorted(config.profiles.keys())
        for name in names:
            self.combo_profiles.addItem(name)

        active = config.active_profile
        idx = self.combo_profiles.findText(active)
        if idx >= 0:
            self.combo_profiles.setCurrentIndex(idx)
        elif self.combo_profiles.count() > 0:
            self.combo_profiles.setCurrentIndex(0)

        self.btn_delete.setEnabled(self.combo_profiles.count() > 1)
        self.combo_profiles.blockSignals(False)

    def get_current_profile(self) -> str:
        return self.combo_profiles.currentText()

    def _on_combo_changed(self, index: int):
        profile_name = self.combo_profiles.currentText()
        if profile_name:
            self.profile_selected.emit(profile_name)

    def _on_save_clicked(self):
        name = self.combo_profiles.currentText()
        if name:
            self.profile_saved.emit(name)
            QMessageBox.information(
                self,
                "Profil gespeichert",
                f"Die aktuellen Einstellungen wurden im Profil '{name}' gespeichert."
            )

    def _on_new_clicked(self):
        name, ok = QInputDialog.getText(
            self,
            "Neues Profil anlegen",
            "Geben Sie einen Namen für das neue Import-Profil ein:",
        )
        name = name.strip()
        if ok and name:
            idx = self.combo_profiles.findText(name)
            if idx >= 0:
                QMessageBox.warning(self, "Name existiert bereits", f"Ein Profil namens '{name}' existiert bereits.")
                return
            self.profile_created.emit(name)

    def _on_delete_clicked(self):
        name = self.combo_profiles.currentText()
        if not name or self.combo_profiles.count() <= 1:
            return

        res = QMessageBox.question(
            self,
            "Profil löschen",
            f"Möchten Sie das Profil '{name}' wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if res == QMessageBox.StandardButton.Yes:
            self.profile_deleted.emit(name)
