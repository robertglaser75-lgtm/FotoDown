"""General application settings widget with JPG/RAW organization, pairing, and verification options."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QLabel, QVBoxLayout, QWidget
)

from core.config import AppConfig


class GeneralSettingsWidget(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        # 1. JPG & RAW Organization
        lbl_org = QLabel("JPG/RAW-Organisation:")
        lbl_org.setObjectName("sectionSubTitle")
        layout.addWidget(lbl_org)

        self.combo_org = QComboBox()
        self.combo_org.addItem("Alle Fotos gemeinsam in einem Ordner", "same")
        self.combo_org.addItem("Getrennte Unterordner (.../JPG und .../RAW)", "subfolders")
        self.combo_org.addItem("Getrennte Hauptordner (JPG/... und RAW/...)", "parent_folders")
        self.combo_org.currentIndexChanged.connect(lambda *args: self.changed.emit())
        layout.addWidget(self.combo_org)

        layout.addSpacing(4)

        # 2. Pairing & Sidecars
        self.chk_pair_raw = QCheckBox("🔗 RAW & JPG als logische Einheit koppeln")
        self.chk_pair_raw.setChecked(True)
        self.chk_pair_raw.toggled.connect(lambda *args: self.changed.emit())
        layout.addWidget(self.chk_pair_raw)

        self.chk_sync_xmp = QCheckBox("📄 XMP-Sidecars (.xmp) synchron mitführen")
        self.chk_sync_xmp.setChecked(True)
        self.chk_sync_xmp.toggled.connect(lambda *args: self.changed.emit())
        layout.addWidget(self.chk_sync_xmp)

        layout.addSpacing(4)

        # 3. Detection & Duplicate Safety
        self.chk_auto_detect = QCheckBox("⚡ SD-Karten automatisch beim Einstecken erkennen")
        self.chk_auto_detect.setChecked(True)
        self.chk_auto_detect.toggled.connect(lambda *args: self.changed.emit())
        layout.addWidget(self.chk_auto_detect)

        self.chk_only_new = QCheckBox("Nur neue Fotos && Videos importieren (Duplikate überspringen)")
        self.chk_only_new.setChecked(True)
        self.chk_only_new.toggled.connect(lambda *args: self.changed.emit())
        layout.addWidget(self.chk_only_new)

        self.chk_verify = QCheckBox("\u2714 Bit-genaue Integritätsprüfung (SHA-256 Hashes prüfen)")
        self.chk_verify.setChecked(True)
        self.chk_verify.toggled.connect(lambda *args: self.changed.emit())
        layout.addWidget(self.chk_verify)

    def get_type_org(self) -> str:
        return self.combo_org.currentData() or "same"

    def set_type_org(self, val: str):
        idx = self.combo_org.findData(val)
        if idx >= 0:
            self.combo_org.setCurrentIndex(idx)
        else:
            self.combo_org.setCurrentIndex(0)

    def load_config(self, config: AppConfig):
        self.set_type_org(config.type_folder_organization)
        self.chk_auto_detect.setChecked(config.auto_detect_drives)
        self.chk_pair_raw.setChecked(config.pair_raw_jpg)
        self.chk_sync_xmp.setChecked(config.sync_xmp_sidecars)
        self.chk_only_new.setChecked(config.only_new_files)
        self.chk_verify.setChecked(config.verify_checksums)

    def sync_to_config(self, config: AppConfig):
        config.type_folder_organization = self.get_type_org()
        config.auto_detect_drives = self.chk_auto_detect.isChecked()
        config.pair_raw_jpg = self.chk_pair_raw.isChecked()
        config.sync_xmp_sidecars = self.chk_sync_xmp.isChecked()
        config.only_new_files = self.chk_only_new.isChecked()
        config.verify_checksums = self.chk_verify.isChecked()
