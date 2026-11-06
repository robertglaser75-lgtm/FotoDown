"""General application settings widget with JPG/RAW organization, pairing, and verification options."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget
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

        layout.addSpacing(6)

        # 4. IPTC & Copyright Injection
        lbl_iptc = QLabel("\U0001F4DD Urheberrecht & IPTC-Metadaten:")
        lbl_iptc.setObjectName("sectionSubTitle")
        layout.addWidget(lbl_iptc)

        self.chk_enable_iptc = QCheckBox("Metadaten beim Importieren einbetten")
        self.chk_enable_iptc.toggled.connect(self._on_iptc_toggled)
        layout.addWidget(self.chk_enable_iptc)

        self.edit_creator = QLineEdit()
        self.edit_creator.setPlaceholderText("Fotograf / Urheber (z.B. Max Mustermann)...")
        self.edit_creator.setEnabled(False)
        self.edit_creator.textChanged.connect(lambda *args: self.changed.emit())
        layout.addWidget(self.edit_creator)

        self.edit_copyright = QLineEdit()
        self.edit_copyright.setPlaceholderText("Copyright (z.B. © {YYYY} {creator})...")
        self.edit_copyright.setEnabled(False)
        self.edit_copyright.textChanged.connect(lambda *args: self.changed.emit())
        layout.addWidget(self.edit_copyright)

        self.edit_keywords = QLineEdit()
        self.edit_keywords.setPlaceholderText("Stichwörter (kommagetrennt, z.B. Urlaub, Natur)...")
        self.edit_keywords.setEnabled(False)
        self.edit_keywords.textChanged.connect(lambda *args: self.changed.emit())
        layout.addWidget(self.edit_keywords)

        layout.addSpacing(6)

        # 5. Culling & Reject Action Settings
        lbl_culling = QLabel("👁️ Sichten & Aussortieren:")
        lbl_culling.setObjectName("sectionSubTitle")
        layout.addWidget(lbl_culling)

        self.combo_reject_action = QComboBox()
        self.combo_reject_action.addItem("In Unterordner verschieben (_Abgelehnt/)", "move_folder")
        self.combo_reject_action.addItem("In den Papierkorb / Löschen", "trash")
        self.combo_reject_action.addItem("Nur in Metadaten als abgelehnt markieren", "flag_only")
        self.combo_reject_action.currentIndexChanged.connect(lambda *args: self.changed.emit())
        layout.addWidget(self.combo_reject_action)

        layout.addSpacing(6)

        # 6. NAS & Family Album Paths
        lbl_nas = QLabel("🏠 NAS-Archiv & Familienalbum:")
        lbl_nas.setObjectName("sectionSubTitle")
        layout.addWidget(lbl_nas)

        # Family Album
        lbl_fa = QLabel("Familienalbum-Zielpfad (0001_Unsere_Fotos/{YYYY}/{MM}):")
        lbl_fa.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(lbl_fa)

        row_fa = QHBoxLayout()
        row_fa.setSpacing(6)
        self.edit_family_album = QLineEdit()
        self.edit_family_album.setPlaceholderText("Pfad zum Familienalbum (z.B. \\\\192.168.1.20\\...\\0001_Unsere_Fotos)...")
        self.edit_family_album.textChanged.connect(lambda *args: self.changed.emit())
        row_fa.addWidget(self.edit_family_album, stretch=1)

        btn_browse_fa = QPushButton("📁 Durchsuchen")
        btn_browse_fa.setObjectName("secondaryBtn")
        btn_browse_fa.clicked.connect(self._browse_family_album)
        row_fa.addWidget(btn_browse_fa)
        layout.addLayout(row_fa)

        # NAS Archive
        lbl_na = QLabel("Allgemeines NAS-Archiv:")
        lbl_na.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(lbl_na)

        row_na = QHBoxLayout()
        row_na.setSpacing(6)
        self.edit_nas_archive = QLineEdit()
        self.edit_nas_archive.setPlaceholderText("Pfad zum NAS-Archiv (z.B. \\\\192.168.1.20\\...\\Archiv)...")
        self.edit_nas_archive.textChanged.connect(lambda *args: self.changed.emit())
        row_na.addWidget(self.edit_nas_archive, stretch=1)

        btn_browse_na = QPushButton("📁 Durchsuchen")
        btn_browse_na.setObjectName("secondaryBtn")
        btn_browse_na.clicked.connect(self._browse_nas_archive)
        row_na.addWidget(btn_browse_na)
        layout.addLayout(row_na)

    def _browse_family_album(self):
        curr = self.edit_family_album.text().strip()
        folder = QFileDialog.getExistingDirectory(self, "Familienalbum-Ordner wählen", curr)
        if folder:
            self.edit_family_album.setText(folder)

    def _browse_nas_archive(self):
        curr = self.edit_nas_archive.text().strip()
        folder = QFileDialog.getExistingDirectory(self, "NAS-Archiv-Ordner wählen", curr)
        if folder:
            self.edit_nas_archive.setText(folder)

    def _on_iptc_toggled(self, checked: bool):
        self.edit_creator.setEnabled(checked)
        self.edit_copyright.setEnabled(checked)
        self.edit_keywords.setEnabled(checked)
        self.changed.emit()

    def get_type_org(self) -> str:
        return self.combo_org.currentData() or "same"

    def set_type_org(self, val: str):
        idx = self.combo_org.findData(val)
        if idx >= 0:
            self.combo_org.setCurrentIndex(idx)
        else:
            self.combo_org.setCurrentIndex(0)

    def load_config(self, config: AppConfig):
        widgets = [
            self.combo_org, self.chk_auto_detect, self.chk_pair_raw,
            self.chk_sync_xmp, self.chk_only_new, self.chk_verify,
            self.chk_enable_iptc, self.edit_creator, self.edit_copyright, self.edit_keywords,
            self.combo_reject_action, self.edit_family_album, self.edit_nas_archive
        ]
        for w in widgets:
            w.blockSignals(True)
        try:
            self.set_type_org(config.type_folder_organization)
            self.chk_auto_detect.setChecked(config.auto_detect_drives)
            self.chk_pair_raw.setChecked(config.pair_raw_jpg)
            self.chk_sync_xmp.setChecked(config.sync_xmp_sidecars)
            self.chk_only_new.setChecked(config.only_new_files)
            self.chk_verify.setChecked(config.verify_checksums)
            self.chk_enable_iptc.setChecked(config.enable_iptc)
            self.edit_creator.setText(config.iptc_creator)
            self.edit_copyright.setText(config.iptc_copyright)
            self.edit_keywords.setText(config.iptc_keywords)
            self.edit_creator.setEnabled(config.enable_iptc)
            self.edit_copyright.setEnabled(config.enable_iptc)
            self.edit_keywords.setEnabled(config.enable_iptc)
            self.edit_family_album.setText(config.family_album_dir)
            self.edit_nas_archive.setText(config.nas_archive_dir)

            # Reject action
            idx_act = self.combo_reject_action.findData(config.reject_action)
            if idx_act >= 0:
                self.combo_reject_action.setCurrentIndex(idx_act)
            else:
                self.combo_reject_action.setCurrentIndex(0)
        finally:
            for w in widgets:
                w.blockSignals(False)

    def sync_to_config(self, config: AppConfig):
        config.type_folder_organization = self.get_type_org()
        config.auto_detect_drives = self.chk_auto_detect.isChecked()
        config.pair_raw_jpg = self.chk_pair_raw.isChecked()
        config.sync_xmp_sidecars = self.chk_sync_xmp.isChecked()
        config.only_new_files = self.chk_only_new.isChecked()
        config.verify_checksums = self.chk_verify.isChecked()
        config.enable_iptc = self.chk_enable_iptc.isChecked()
        config.iptc_creator = self.edit_creator.text().strip()
        config.iptc_copyright = self.edit_copyright.text().strip()
        config.iptc_keywords = self.edit_keywords.text().strip()
        config.reject_action = self.combo_reject_action.currentData() or "move_folder"
        config.family_album_dir = self.edit_family_album.text().strip()
        config.nas_archive_dir = self.edit_nas_archive.text().strip()
