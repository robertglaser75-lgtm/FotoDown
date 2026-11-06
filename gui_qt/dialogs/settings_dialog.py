"""Preferences and settings dialog for FotoDown."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget
)

from core.config import AppConfig


class SettingsDialog(QDialog):
    """Central configuration dialog with categorized tabs including Single View display settings."""
    settings_saved = Signal()

    def __init__(self, config: AppConfig, parent=None, initial_tab: int = 0):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("FotoDown - Einstellungen & Konfiguration")
        self.resize(740, 620)
        self.setMinimumSize(640, 520)

        self._setup_ui()
        self.load_from_config()
        if 0 <= initial_tab < self.tabs.count():
            self.tabs.setCurrentIndex(initial_tab)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 14)
        main_layout.setSpacing(12)

        # Header Title
        lbl_head = QLabel("⚙️ Programmeinstellungen")
        lbl_head.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8;")
        main_layout.addWidget(lbl_head)

        # Tabs container
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #334155;
                background-color: #0b1120;
                border-radius: 6px;
                padding: 10px;
            }
            QTabBar::tab {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 6px 14px;
                margin-right: 2px;
                font-weight: 600;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background-color: #0284c7;
                color: #ffffff;
                border-color: #38bdf8;
            }
            QTabBar::tab:hover:!selected {
                background-color: #334155;
                color: #f8fafc;
            }
        """)

        # Add tabs
        self.tabs.addTab(self._create_single_view_tab(), "👁️ Einzelansicht")
        self.tabs.addTab(self._create_import_tab(), "📥 Import & Organisation")
        self.tabs.addTab(self._create_nas_album_tab(), "🏠 NAS & Familienalbum")
        self.tabs.addTab(self._create_external_editors_tab(), "🎨 Externe Editoren")
        self.tabs.addTab(self._create_iptc_tab(), "✍️ IPTC & Copyright")

        main_layout.addWidget(self.tabs, stretch=1)

        # Bottom Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_reset_defaults = QPushButton("Standardwerte")
        self.btn_reset_defaults.setToolTip("Setzt die Optionen der Einzelansicht auf Standard zurück")
        self.btn_reset_defaults.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; color: #94a3b8; border: 1px solid #334155;
                border-radius: 4px; padding: 6px 14px; font-size: 11px;
            }
            QPushButton:hover { background-color: #334155; color: white; }
        """)
        self.btn_reset_defaults.clicked.connect(self._reset_single_view_defaults)
        btn_layout.addWidget(self.btn_reset_defaults)

        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155;
                border-radius: 4px; padding: 6px 16px; font-weight: 500;
            }
            QPushButton:hover { background-color: #334155; color: white; }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("✔ Speichern")
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #0284c7; color: white; border: 1px solid #38bdf8;
                border-radius: 4px; padding: 6px 20px; font-weight: bold;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)
        self.btn_save.clicked.connect(self._on_save_clicked)
        btn_layout.addWidget(self.btn_save)

        main_layout.addLayout(btn_layout)

    # -------------------------------------------------------------------------
    # TAB 1: EINZELANSICHT
    # -------------------------------------------------------------------------
    def _create_single_view_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        lbl_desc = QLabel(
            "Konfigurieren Sie hier, welche Datei- und Metadaten-Felder in der <b>Einzelansicht</b> "
            "(sowohl im Tab <i>1. Importieren</i> als auch im Fotobetrachter von Tab <i>2. Sichten</i>) "
            "eingeblendet werden sollen:"
        )
        lbl_desc.setStyleSheet("color: #cbd5e1; font-size: 12px; line-height: 1.4;")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        box_fields = QGroupBox("Sichtbare Informationen")
        box_fields.setStyleSheet("""
            QGroupBox {
                border: 1px solid #1e293b;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 14px;
                font-weight: bold;
                color: #38bdf8;
            }
        """)
        fields_layout = QGridLayout(box_fields)
        fields_layout.setHorizontalSpacing(20)
        fields_layout.setVerticalSpacing(8)

        self.chk_sv_filename = QCheckBox("Name des Bildes (Dateiname)")
        self.chk_sv_filename.toggled.connect(self._update_live_preview)
        fields_layout.addWidget(self.chk_sv_filename, 0, 0)

        self.chk_sv_extension = QCheckBox("Dateiendung anzeigen (.JPG, .ORF, .CR3...)")
        self.chk_sv_extension.toggled.connect(self._update_live_preview)
        fields_layout.addWidget(self.chk_sv_extension, 0, 1)

        self.chk_sv_ratings = QCheckBox("Sterne und sonstige Bewertungen (★, [P], [X], Workflow)")
        self.chk_sv_ratings.toggled.connect(self._update_live_preview)
        fields_layout.addWidget(self.chk_sv_ratings, 1, 0)

        self.chk_sv_path = QCheckBox("Speicherort (Ordnerpfad / Verzeichnis)")
        self.chk_sv_path.toggled.connect(self._update_live_preview)
        fields_layout.addWidget(self.chk_sv_path, 1, 1)

        self.chk_sv_cam_lens = QCheckBox("Kamera & Objektiv")
        self.chk_sv_cam_lens.toggled.connect(self._update_live_preview)
        fields_layout.addWidget(self.chk_sv_cam_lens, 2, 0)

        self.chk_sv_exposure = QCheckBox("Belichtungsdaten & ISO (Blende, Zeit, ISO, Brennweite)")
        self.chk_sv_exposure.toggled.connect(self._update_live_preview)
        fields_layout.addWidget(self.chk_sv_exposure, 2, 1)

        self.chk_sv_date = QCheckBox("Aufnahmedatum & Uhrzeit")
        self.chk_sv_date.toggled.connect(self._update_live_preview)
        fields_layout.addWidget(self.chk_sv_date, 3, 0)

        self.chk_sv_filesize = QCheckBox("Dateigröße & Dimensionen (Megapixel)")
        self.chk_sv_filesize.toggled.connect(self._update_live_preview)
        fields_layout.addWidget(self.chk_sv_filesize, 3, 1)

        layout.addWidget(box_fields)

        # Live Preview Box
        lbl_preview_title = QLabel("Vorschau der Einzelansicht-Kopfzeile:")
        lbl_preview_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #94a3b8; margin-top: 6px;")
        layout.addWidget(lbl_preview_title)

        self.frame_preview = QFrame()
        self.frame_preview.setStyleSheet("""
            QFrame {
                background-color: #070d1a;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 8px 12px;
            }
        """)
        preview_layout = QVBoxLayout(self.frame_preview)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        preview_layout.setSpacing(6)

        # Title row
        self.lbl_preview_title_row = QLabel("")
        self.lbl_preview_title_row.setStyleSheet("font-size: 13px; font-weight: bold; color: #38bdf8;")
        preview_layout.addWidget(self.lbl_preview_title_row)

        # Badges row
        self.lbl_preview_chips_row = QLabel("")
        self.lbl_preview_chips_row.setStyleSheet("font-size: 11px; color: #e2e8f0; line-height: 1.5;")
        self.lbl_preview_chips_row.setWordWrap(True)
        preview_layout.addWidget(self.lbl_preview_chips_row)

        layout.addWidget(self.frame_preview)
        layout.addStretch()
        return w

    def _update_live_preview(self):
        """Updates the interactive live preview banner according to checked boxes."""
        stem = "P1010042"
        ext = ".ORF"

        # 1. Filename & Extension
        show_name = self.chk_sv_filename.isChecked()
        show_ext = self.chk_sv_extension.isChecked()

        if show_name and show_ext:
            title_text = f"{stem}{ext}"
        elif show_name:
            title_text = stem
        elif show_ext:
            title_text = f"Format: {ext.upper()}"
        else:
            title_text = "<i>(Name und Endung ausgeblendet)</i>"

        self.lbl_preview_title_row.setText(title_text)

        # 2. Chips
        chips = []
        if self.chk_sv_path.isChecked():
            chips.append("<span style='background:#1e293b; padding:2px 6px; border-radius:3px;'>📁 D:\\Fotos\\2026\\04_Familie</span>")
        if self.chk_sv_ratings.isChecked():
            chips.append("<span style='background:#b45309; color:#fef3c7; padding:2px 6px; border-radius:3px; font-weight:bold;'>⭐⭐⭐⭐ [P] 📸 SOOC ok</span>")
        if self.chk_sv_cam_lens.isChecked():
            chips.append("<span style='background:#1e293b; padding:2px 6px; border-radius:3px;'>📷 OM-1 • 12-40mm F2.8</span>")
        if self.chk_sv_exposure.isChecked():
            chips.append("<span style='background:#1e293b; padding:2px 6px; border-radius:3px;'>⚙️ ƒ/2.8 | 1/500s | ISO 200</span>")
        if self.chk_sv_date.isChecked():
            chips.append("<span style='background:#1e293b; padding:2px 6px; border-radius:3px;'>📅 15.04.2026 14:32</span>")
        if self.chk_sv_filesize.isChecked():
            chips.append("<span style='background:#1e293b; padding:2px 6px; border-radius:3px;'>💾 24.2 MB (RAW) • 20.4 MP</span>")

        if chips:
            self.lbl_preview_chips_row.setText(" &nbsp; ".join(chips))
            self.lbl_preview_chips_row.setVisible(True)
        else:
            self.lbl_preview_chips_row.setText("<i style='color:#64748b;'>Keine weiteren Details aktiviert</i>")

    def _reset_single_view_defaults(self):
        self.chk_sv_filename.setChecked(True)
        self.chk_sv_extension.setChecked(True)
        self.chk_sv_ratings.setChecked(True)
        self.chk_sv_path.setChecked(True)
        self.chk_sv_cam_lens.setChecked(True)
        self.chk_sv_exposure.setChecked(True)
        self.chk_sv_date.setChecked(True)
        self.chk_sv_filesize.setChecked(True)
        self._update_live_preview()

    # -------------------------------------------------------------------------
    # TAB 2: IMPORT & ORGANISATION
    # -------------------------------------------------------------------------
    def _create_import_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        lbl_org = QLabel("JPG/RAW-Organisation:")
        lbl_org.setStyleSheet("font-weight: 600; color: #94a3b8;")
        layout.addWidget(lbl_org)

        self.combo_org = QComboBox()
        self.combo_org.addItem("Alle Fotos gemeinsam in einem Ordner", "same")
        self.combo_org.addItem("Getrennte Unterordner (.../JPG und .../RAW)", "subfolders")
        self.combo_org.addItem("Getrennte Hauptordner (JPG/... und RAW/...)", "parent_folders")
        layout.addWidget(self.combo_org)

        layout.addSpacing(6)

        self.chk_pair_raw = QCheckBox("🔗 RAW & JPG als logische Einheit koppeln")
        layout.addWidget(self.chk_pair_raw)

        self.chk_sync_xmp = QCheckBox("📄 XMP-Sidecars (.xmp) synchron mitführen")
        layout.addWidget(self.chk_sync_xmp)

        self.chk_auto_detect = QCheckBox("⚡ SD-Karten automatisch beim Einstecken erkennen")
        layout.addWidget(self.chk_auto_detect)

        self.chk_only_new = QCheckBox("Nur neue Fotos & Videos importieren (Duplikate überspringen)")
        layout.addWidget(self.chk_only_new)

        self.chk_verify = QCheckBox("✔ Bit-genaue Integritätsprüfung (SHA-256 Hashes prüfen)")
        layout.addWidget(self.chk_verify)

        layout.addStretch()
        return w

    # -------------------------------------------------------------------------
    # TAB 3: NAS & FAMILIENALBUM
    # -------------------------------------------------------------------------
    def _create_nas_album_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Family album
        lbl_fa = QLabel("🏠 Familienalbum-Zielverzeichnis:")
        lbl_fa.setStyleSheet("font-weight: 600; color: #38bdf8;")
        layout.addWidget(lbl_fa)

        lbl_fa_hint = QLabel("Struktur: 0001_Unsere_Fotos/{YYYY}/{MM} (wird zur automatischen Export-Erkennung genutzt)")
        lbl_fa_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(lbl_fa_hint)

        row_fa = QHBoxLayout()
        self.edit_family_album = QLineEdit()
        self.edit_family_album.setPlaceholderText("z.B. \\\\192.168.1.20\\Daten\\Fotos\\0001_Unsere_Fotos")
        row_fa.addWidget(self.edit_family_album, stretch=1)

        btn_browse_fa = QPushButton("📁 Durchsuchen")
        btn_browse_fa.clicked.connect(self._browse_family_album)
        row_fa.addWidget(btn_browse_fa)
        layout.addLayout(row_fa)

        layout.addSpacing(8)

        # NAS archive
        lbl_na = QLabel("💾 Allgemeines NAS-Archiv:")
        lbl_na.setStyleSheet("font-weight: 600; color: #38bdf8;")
        layout.addWidget(lbl_na)

        row_na = QHBoxLayout()
        self.edit_nas_archive = QLineEdit()
        self.edit_nas_archive.setPlaceholderText("z.B. \\\\192.168.1.20\\Daten\\Archiv")
        row_na.addWidget(self.edit_nas_archive, stretch=1)

        btn_browse_na = QPushButton("📁 Durchsuchen")
        btn_browse_na.clicked.connect(self._browse_nas_archive)
        row_na.addWidget(btn_browse_na)
        layout.addLayout(row_na)

        layout.addStretch()
        return w

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

    # -------------------------------------------------------------------------
    # TAB 4: EXTERNE EDITOREN & SIGHTING
    # -------------------------------------------------------------------------
    def _create_external_editors_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Darktable
        lbl_dt = QLabel("🎨 Darktable Programmdatei:")
        lbl_dt.setStyleSheet("font-weight: 600; color: #cbd5e1;")
        layout.addWidget(lbl_dt)

        row_dt = QHBoxLayout()
        self.edit_darktable = QLineEdit()
        self.edit_darktable.setPlaceholderText("Pfad zu darktable.exe...")
        row_dt.addWidget(self.edit_darktable, stretch=1)
        btn_browse_dt = QPushButton("📁 Durchsuchen")
        btn_browse_dt.clicked.connect(self._browse_darktable)
        row_dt.addWidget(btn_browse_dt)
        layout.addLayout(row_dt)

        # Topaz
        lbl_tp = QLabel("✨ Topaz Photo Programmdatei:")
        lbl_tp.setStyleSheet("font-weight: 600; color: #cbd5e1;")
        layout.addWidget(lbl_tp)

        row_tp = QHBoxLayout()
        self.edit_topaz = QLineEdit()
        self.edit_topaz.setPlaceholderText("Pfad zu Topaz Photo.exe...")
        row_tp.addWidget(self.edit_topaz, stretch=1)
        btn_browse_tp = QPushButton("📁 Durchsuchen")
        btn_browse_tp.clicked.connect(self._browse_topaz)
        row_tp.addWidget(btn_browse_tp)
        layout.addLayout(row_tp)

        layout.addSpacing(6)

        # Reject action
        lbl_rej = QLabel("🗑️ Aktion für abgelehnte Fotos [X]:")
        lbl_rej.setStyleSheet("font-weight: 600; color: #cbd5e1;")
        layout.addWidget(lbl_rej)

        self.combo_reject_action = QComboBox()
        self.combo_reject_action.addItem("In Unterordner verschieben (_Abgelehnt/)", "move_folder")
        self.combo_reject_action.addItem("In den Papierkorb / Löschen", "trash")
        self.combo_reject_action.addItem("Nur in Metadaten als abgelehnt markieren", "flag_only")
        layout.addWidget(self.combo_reject_action)

        layout.addStretch()
        return w

    def _browse_darktable(self):
        curr = self.edit_darktable.text().strip()
        f, _ = QFileDialog.getOpenFileName(self, "Darktable Programmdatei wählen", curr, "Programme (*.exe);;Alle Dateien (*)")
        if f:
            self.edit_darktable.setText(f)

    def _browse_topaz(self):
        curr = self.edit_topaz.text().strip()
        f, _ = QFileDialog.getOpenFileName(self, "Topaz Photo Programmdatei wählen", curr, "Programme (*.exe);;Alle Dateien (*)")
        if f:
            self.edit_topaz.setText(f)

    # -------------------------------------------------------------------------
    # TAB 5: IPTC & URHEBERRECHT
    # -------------------------------------------------------------------------
    def _create_iptc_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.chk_enable_iptc = QCheckBox("Urheberrecht & IPTC-Metadaten beim Importieren einbetten")
        self.chk_enable_iptc.toggled.connect(self._on_iptc_toggled)
        layout.addWidget(self.chk_enable_iptc)

        lbl_c = QLabel("Fotograf / Urheber:")
        lbl_c.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(lbl_c)
        self.edit_creator = QLineEdit()
        self.edit_creator.setPlaceholderText("z.B. Max Mustermann")
        layout.addWidget(self.edit_creator)

        lbl_cr = QLabel("Copyright-Vermerk:")
        lbl_cr.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(lbl_cr)
        self.edit_copyright = QLineEdit()
        self.edit_copyright.setPlaceholderText("z.B. © {YYYY} {creator}")
        layout.addWidget(self.edit_copyright)

        lbl_kw = QLabel("Standard-Schlagwörter:")
        lbl_kw.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(lbl_kw)
        self.edit_keywords = QLineEdit()
        self.edit_keywords.setPlaceholderText("z.B. Familie, Urlaub, Natur")
        layout.addWidget(self.edit_keywords)

        layout.addStretch()
        return w

    def _on_iptc_toggled(self, checked: bool):
        self.edit_creator.setEnabled(checked)
        self.edit_copyright.setEnabled(checked)
        self.edit_keywords.setEnabled(checked)

    # -------------------------------------------------------------------------
    # CONFIG SYNC
    # -------------------------------------------------------------------------
    def load_from_config(self):
        c = self.config

        # 1. Einzelansicht
        self.chk_sv_filename.setChecked(c.single_view_show_filename)
        self.chk_sv_extension.setChecked(c.single_view_show_extension)
        self.chk_sv_ratings.setChecked(c.single_view_show_ratings)
        self.chk_sv_path.setChecked(c.single_view_show_path)
        self.chk_sv_cam_lens.setChecked(c.single_view_show_camera_lens)
        self.chk_sv_exposure.setChecked(c.single_view_show_exposure)
        self.chk_sv_date.setChecked(c.single_view_show_date)
        self.chk_sv_filesize.setChecked(c.single_view_show_filesize)
        self._update_live_preview()

        # 2. Import & Org
        idx_org = self.combo_org.findData(c.type_folder_organization)
        self.combo_org.setCurrentIndex(max(0, idx_org))
        self.chk_pair_raw.setChecked(c.pair_raw_jpg)
        self.chk_sync_xmp.setChecked(c.sync_xmp_sidecars)
        self.chk_auto_detect.setChecked(c.auto_detect_drives)
        self.chk_only_new.setChecked(c.only_new_files)
        self.chk_verify.setChecked(c.verify_checksums)

        # 3. NAS
        self.edit_family_album.setText(c.family_album_dir)
        self.edit_nas_archive.setText(c.nas_archive_dir)

        # 4. External editors
        self.edit_darktable.setText(c.darktable_path)
        self.edit_topaz.setText(c.topaz_path)
        idx_rej = self.combo_reject_action.findData(c.reject_action)
        self.combo_reject_action.setCurrentIndex(max(0, idx_rej))

        # 5. IPTC
        self.chk_enable_iptc.setChecked(c.enable_iptc)
        self.edit_creator.setText(c.iptc_creator)
        self.edit_copyright.setText(c.iptc_copyright)
        self.edit_keywords.setText(c.iptc_keywords)
        self._on_iptc_toggled(c.enable_iptc)

    def save_to_config(self):
        c = self.config

        # 1. Einzelansicht
        c.single_view_show_filename = self.chk_sv_filename.isChecked()
        c.single_view_show_extension = self.chk_sv_extension.isChecked()
        c.single_view_show_ratings = self.chk_sv_ratings.isChecked()
        c.single_view_show_path = self.chk_sv_path.isChecked()
        c.single_view_show_camera_lens = self.chk_sv_cam_lens.isChecked()
        c.single_view_show_exposure = self.chk_sv_exposure.isChecked()
        c.single_view_show_date = self.chk_sv_date.isChecked()
        c.single_view_show_filesize = self.chk_sv_filesize.isChecked()

        # 2. Import & Org
        c.type_folder_organization = self.combo_org.currentData() or "same"
        c.pair_raw_jpg = self.chk_pair_raw.isChecked()
        c.sync_xmp_sidecars = self.chk_sync_xmp.isChecked()
        c.auto_detect_drives = self.chk_auto_detect.isChecked()
        c.only_new_files = self.chk_only_new.isChecked()
        c.verify_checksums = self.chk_verify.isChecked()

        # 3. NAS
        c.family_album_dir = self.edit_family_album.text().strip()
        c.nas_archive_dir = self.edit_nas_archive.text().strip()

        # 4. External editors
        c.darktable_path = self.edit_darktable.text().strip()
        c.topaz_path = self.edit_topaz.text().strip()
        c.reject_action = self.combo_reject_action.currentData() or "move_folder"

        # 5. IPTC
        c.enable_iptc = self.chk_enable_iptc.isChecked()
        c.iptc_creator = self.edit_creator.text().strip()
        c.iptc_copyright = self.edit_copyright.text().strip()
        c.iptc_keywords = self.edit_keywords.text().strip()

        c.save()
        self.settings_saved.emit()

    def _on_save_clicked(self):
        self.save_to_config()
        self.accept()
