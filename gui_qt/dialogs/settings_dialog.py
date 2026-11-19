"""Preferences and settings dialog for Vitrina."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget
)

from core.config import AppConfig
from gui_qt.key_navigation import (
    DEFAULT_NAVIGATION_SCHEME, NAVIGATION_SCHEMES, get_nav_hint
)
from gui_qt.styles.icons import (
    get_culling_icon, get_folder_icon, get_gear_icon, get_import_icon, get_tag_icon, get_theme_icon
)
from gui_qt.styles.theme import (
    THEME_DARK, THEME_LIGHT, THEME_SYSTEM, theme_manager
)


class SettingsDialog(QDialog):
    """Central configuration dialog with categorized tabs including Single View display settings."""
    settings_saved = Signal()

    def __init__(self, config: AppConfig, parent=None, initial_tab: int = 0):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Vitrina - Einstellungen & Konfiguration")
        self.resize(740, 620)
        self.setMinimumSize(640, 520)
        self.setMaximumWidth(950)
        self.setMaximumHeight(850)

        self._setup_ui()
        self.load_from_config()
        if 0 <= initial_tab < self.tabs.count():
            self.tabs.setCurrentIndex(initial_tab)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 14)
        main_layout.setSpacing(12)

        # Header Title
        lbl_head = QLabel("Programmeinstellungen")
        lbl_head.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8;")
        main_layout.addWidget(lbl_head)

        # Tabs container
        self.tabs = QTabWidget()
        self.tabs.setIconSize(QSize(16, 16))

        # Add tabs
        self.tabs.addTab(self._create_single_view_tab(), get_culling_icon(), "Einzelansicht & Farbschema")
        self.tabs.addTab(self._create_import_tab(), get_import_icon(), "Import & Organisation")
        self.tabs.addTab(self._create_nas_album_tab(), get_folder_icon(), "NAS & Familienalbum")
        self.tabs.addTab(self._create_external_editors_tab(), get_gear_icon(), "Externe Editoren")
        self.tabs.addTab(self._create_iptc_tab(), get_tag_icon(), "IPTC & Copyright")

        main_layout.addWidget(self.tabs, stretch=1)

        # Bottom Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_reset_defaults = QPushButton("Standardwerte")
        self.btn_reset_defaults.setToolTip("Setzt die Optionen der Einzelansicht auf Standard zurück")
        self.btn_reset_defaults.clicked.connect(self._reset_single_view_defaults)
        btn_layout.addWidget(self.btn_reset_defaults)

        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Abbrechen")
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

        # Farbschema & Theme Box
        box_theme = QGroupBox("Farbschema & Darstellung")
        theme_vbox = QVBoxLayout(box_theme)
        theme_vbox.setContentsMargins(12, 10, 12, 10)
        theme_vbox.setSpacing(8)

        theme_row = QHBoxLayout()
        lbl_theme = QLabel("Erscheinungsbild / Modus:")
        lbl_theme.setStyleSheet("font-weight: 600;")
        theme_row.addWidget(lbl_theme)

        self.combo_theme = QComboBox()
        self.combo_theme.addItem(get_theme_icon("dark"), "Dunkel (Fluent Dark)", THEME_DARK)
        self.combo_theme.addItem(get_theme_icon("light"), "Hell (Fluent Light)", THEME_LIGHT)
        self.combo_theme.addItem(get_theme_icon("system"), "Automatisch (Wie Betriebssystem)", THEME_SYSTEM)
        theme_row.addWidget(self.combo_theme, 1)
        theme_vbox.addLayout(theme_row)

        self.chk_enforce_sidebar_min = QCheckBox("Mindestbreite für Seitenleisten erzwingen (verhindert Abschneiden von Buttons)")
        self.chk_enforce_sidebar_min.setToolTip(
            "Wenn aktiviert, können Seitenleisten nicht schmaler als ihre Steuerelemente gezogen werden. "
            "Deaktivieren, um Leisten beliebig schmal zu schieben."
        )
        theme_vbox.addWidget(self.chk_enforce_sidebar_min)

        layout.addWidget(box_theme)

        box_fields = QGroupBox("Sichtbare Informationen")
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
        self.frame_preview.setObjectName("settingsPreviewCard")
        preview_layout = QVBoxLayout(self.frame_preview)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        preview_layout.setSpacing(6)

        # Title row
        self.lbl_preview_title_row = QLabel("")
        self.lbl_preview_title_row.setStyleSheet("font-size: 13px; font-weight: bold; color: #38bdf8;")
        preview_layout.addWidget(self.lbl_preview_title_row)

        # Badges row
        self.lbl_preview_chips_row = QLabel("")
        self.lbl_preview_chips_row.setStyleSheet("font-size: 11px; line-height: 1.5;")
        self.lbl_preview_chips_row.setWordWrap(True)
        preview_layout.addWidget(self.lbl_preview_chips_row)

        layout.addWidget(self.frame_preview)

        # Tastatur & Weiterschalten Box
        box_nav = QGroupBox("Tastatur & Bild-Navigation (Weiterschalten)")
        nav_vbox = QVBoxLayout(box_nav)
        nav_vbox.setSpacing(6)

        nav_row = QHBoxLayout()
        lbl_nav = QLabel("Tastenbelegung zum Weiterschalten:")
        lbl_nav.setStyleSheet("color: #cbd5e1; font-weight: normal; font-size: 11px;")
        nav_row.addWidget(lbl_nav)

        self.combo_nav_scheme = QComboBox()
        for s_id, s_data in NAVIGATION_SCHEMES.items():
            self.combo_nav_scheme.addItem(s_data["name"], s_id)
        self.combo_nav_scheme.currentIndexChanged.connect(self._update_nav_hint)
        nav_row.addWidget(self.combo_nav_scheme)
        nav_row.addStretch()
        nav_vbox.addLayout(nav_row)

        self.lbl_nav_hint = QLabel("")
        self.lbl_nav_hint.setStyleSheet("color: #38bdf8; font-size: 11px; margin-left: 2px;")
        nav_vbox.addWidget(self.lbl_nav_hint)

        self.chk_nav_mouse_wheel = QCheckBox("Mausrad zum Weiterschalten nutzen (in Normalansicht ohne Zoom)")
        self.chk_nav_mouse_wheel.setStyleSheet("font-size: 11px;")
        nav_vbox.addWidget(self.chk_nav_mouse_wheel)

        layout.addWidget(box_nav)
        layout.addStretch()
        return w

    def _update_nav_hint(self):
        """Updates the description hint below the navigation scheme selector."""
        scheme_id = self.combo_nav_scheme.currentData() or DEFAULT_NAVIGATION_SCHEME
        self.lbl_nav_hint.setText(f"ℹ️ {get_nav_hint(scheme_id)}")

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

        from gui_qt.styles.theme import theme_manager
        is_light = (theme_manager.effective_theme == "light")
        title_color = "#0284c7" if is_light else "#38bdf8"
        self.lbl_preview_title_row.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {title_color};")
        self.lbl_preview_title_row.setText(title_text)

        # 2. Chips
        c_style = "background:#e2e8f0; color:#0f172a;" if is_light else "background:#1e293b; color:#cbd5e1;"

        chips = []
        if self.chk_sv_path.isChecked():
            chips.append(f"<span style='{c_style} padding:2px 6px; border-radius:3px;'>📁 D:\\Fotos\\2026\\04_Familie</span>")
        if self.chk_sv_ratings.isChecked():
            chips.append("<span style='background:#b45309; color:#fef3c7; padding:2px 6px; border-radius:3px; font-weight:bold;'>★★★★ [P] 📸 SOOC ok</span>")
        if self.chk_sv_cam_lens.isChecked():
            chips.append(f"<span style='{c_style} padding:2px 6px; border-radius:3px;'>📷 OM-1 • 12-40mm F2.8</span>")
        if self.chk_sv_exposure.isChecked():
            chips.append(f"<span style='{c_style} padding:2px 6px; border-radius:3px;'>ƒ/2.8 | 1/500s | ISO 200</span>")
        if self.chk_sv_date.isChecked():
            chips.append(f"<span style='{c_style} padding:2px 6px; border-radius:3px;'>📅 15.04.2026 14:32</span>")
        if self.chk_sv_filesize.isChecked():
            chips.append(f"<span style='{c_style} padding:2px 6px; border-radius:3px;'>💾 24.2 MB (RAW) • 20.4 MP</span>")

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
        idx_def = self.combo_nav_scheme.findData(DEFAULT_NAVIGATION_SCHEME)
        self.combo_nav_scheme.setCurrentIndex(max(0, idx_def))
        self.chk_nav_mouse_wheel.setChecked(False)
        self._update_live_preview()
        self._update_nav_hint()

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

        layout.addSpacing(12)

        # Abgleich-Methode (Sichern & Archivieren)
        lbl_reconcile = QLabel("🔍 Dateiabgleich-Methode (Sichern & Archivieren):")
        lbl_reconcile.setStyleSheet("font-weight: 600; color: #38bdf8;")
        layout.addWidget(lbl_reconcile)

        lbl_reconcile_hint = QLabel(
            "Legt fest, anhand welcher Kriterien festgestellt wird, ob ein Foto links (Quelle) "
            "bereits im rechten Zielordner (NAS/Archiv) vorhanden ist:"
        )
        lbl_reconcile_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(lbl_reconcile_hint)

        self.combo_reconcile_method = QComboBox()
        self.combo_reconcile_method.addItem("📁 Namensgleichheit (Dateiname: DSC001.JPG == DSC001.JPG, blitzschnell)", "filename")
        self.combo_reconcile_method.addItem("📅 EXIF-Aufnahmezeit (DateTimeOriginal, erkennt auch umbenannte Fotos)", "exif")
        self.combo_reconcile_method.addItem("🔒 SHA-256 Prüfsumme (Bit-genauer Dateiinhalt, 100% sicher)", "sha256")
        layout.addWidget(self.combo_reconcile_method)

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

        # 0. Farbschema & Theme
        curr_theme = getattr(c, "theme", THEME_DARK)
        idx_theme = self.combo_theme.findData(curr_theme)
        self.combo_theme.setCurrentIndex(max(0, idx_theme))
        self.chk_enforce_sidebar_min.setChecked(getattr(c, "enforce_sidebar_min_width", True))

        # 1. Einzelansicht
        self.chk_sv_filename.setChecked(c.single_view_show_filename)
        self.chk_sv_extension.setChecked(c.single_view_show_extension)
        self.chk_sv_ratings.setChecked(c.single_view_show_ratings)
        self.chk_sv_path.setChecked(c.single_view_show_path)
        self.chk_sv_cam_lens.setChecked(c.single_view_show_camera_lens)
        self.chk_sv_exposure.setChecked(c.single_view_show_exposure)
        self.chk_sv_date.setChecked(c.single_view_show_date)
        self.chk_sv_filesize.setChecked(c.single_view_show_filesize)
        scheme = getattr(c, "navigation_scheme", DEFAULT_NAVIGATION_SCHEME)
        idx_nav = self.combo_nav_scheme.findData(scheme)
        self.combo_nav_scheme.setCurrentIndex(max(0, idx_nav))
        self.chk_nav_mouse_wheel.setChecked(getattr(c, "navigation_enable_mouse_wheel", False))
        self._update_live_preview()
        self._update_nav_hint()

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
        idx_rec = self.combo_reconcile_method.findData(getattr(c, "transfer_reconcile_method", "filename"))
        self.combo_reconcile_method.setCurrentIndex(max(0, idx_rec))

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

        # 0. Farbschema & Theme
        selected_theme = self.combo_theme.currentData() or THEME_DARK
        c.theme = selected_theme
        theme_manager.apply_theme(selected_theme, config=c)
        c.enforce_sidebar_min_width = self.chk_enforce_sidebar_min.isChecked()

        # 1. Einzelansicht
        c.single_view_show_filename = self.chk_sv_filename.isChecked()
        c.single_view_show_extension = self.chk_sv_extension.isChecked()
        c.single_view_show_ratings = self.chk_sv_ratings.isChecked()
        c.single_view_show_path = self.chk_sv_path.isChecked()
        c.single_view_show_camera_lens = self.chk_sv_cam_lens.isChecked()
        c.single_view_show_exposure = self.chk_sv_exposure.isChecked()
        c.single_view_show_date = self.chk_sv_date.isChecked()
        c.single_view_show_filesize = self.chk_sv_filesize.isChecked()
        c.navigation_scheme = self.combo_nav_scheme.currentData() or DEFAULT_NAVIGATION_SCHEME
        c.navigation_enable_mouse_wheel = self.chk_nav_mouse_wheel.isChecked()

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
        c.transfer_reconcile_method = self.combo_reconcile_method.currentData() or "filename"

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

