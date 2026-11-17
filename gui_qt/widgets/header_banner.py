"""Header banner widget with drive detection and action buttons."""

from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QMenu,
    QMessageBox, QPushButton, QSizePolicy, QWidget
)

from core.config import AppConfig
from core.drive_detector import detect_drives, DriveInfo, eject_drive
from core.version import __version__
from gui_qt.key_navigation import DEFAULT_NAVIGATION_SCHEME, NAVIGATION_SCHEMES
from gui_qt.styles.icons import (
    get_archive_icon,
    get_culling_icon,
    get_eject_icon,
    get_fullscreen_icon,
    get_gear_icon,
    get_help_icon,
    get_history_icon,
    get_import_icon,
    get_refresh_icon,
    get_theme_icon,
)
from gui_qt.styles.theme import (
    THEME_DARK,
    THEME_LIGHT,
    THEME_SYSTEM,
    theme_manager,
)


class HeaderBanner(QFrame):
    drive_selected = Signal(str)  # Emits chosen source folder path
    drive_ejected = Signal(str)   # Emits ejected drive path
    open_history = Signal()
    open_help = Signal()
    open_settings = Signal(int)   # Emits target tab index (0=Einzelansicht, 1=Import, 2=NAS, 3=Editoren, etc.)
    single_view_config_changed = Signal()
    tab_changed = Signal(int)     # Emits 0 for Import, 1 for Culling
    toggle_fullscreen_requested = Signal()

    def __init__(self, config: Optional[AppConfig] = None, parent=None):
        super().__init__(parent)
        self.config = config
        self.setObjectName("headerBanner")
        self.setMaximumHeight(42)
        self._drives: List[DriveInfo] = []
        self._setup_ui()
        if self.config:
            self.update_from_config(self.config)
        theme_manager.theme_changed.connect(lambda _: self.refresh_icons())
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

        # Main Workflow Tabs (1. Importieren | 2. Sichten & Sortieren | 3. Sichern & Archivieren)
        tabs_box = QHBoxLayout()
        tabs_box.setSpacing(4)

        self.btn_tab_import = QPushButton("1. Importieren")
        self.btn_tab_import.setObjectName("headerTabBtn")
        self.btn_tab_import.setIcon(get_import_icon())
        self.btn_tab_import.setIconSize(QSize(16, 16))
        self.btn_tab_import.setCheckable(True)
        self.btn_tab_import.setChecked(True)

        self.btn_tab_culling = QPushButton("2. Sichten & Sortieren")
        self.btn_tab_culling.setObjectName("headerTabBtn")
        self.btn_tab_culling.setIcon(get_culling_icon())
        self.btn_tab_culling.setIconSize(QSize(16, 16))
        self.btn_tab_culling.setCheckable(True)
        self.btn_tab_culling.setChecked(False)

        self.btn_tab_transfer = QPushButton("3. Sichern & Archivieren")
        self.btn_tab_transfer.setObjectName("headerTabBtn")
        self.btn_tab_transfer.setIcon(get_archive_icon())
        self.btn_tab_transfer.setIconSize(QSize(16, 16))
        self.btn_tab_transfer.setCheckable(True)
        self.btn_tab_transfer.setChecked(False)

        self.btn_tab_import.clicked.connect(lambda: self.switch_tab(0))
        self.btn_tab_culling.clicked.connect(lambda: self.switch_tab(1))
        self.btn_tab_transfer.clicked.connect(lambda: self.switch_tab(2))

        tabs_box.addWidget(self.btn_tab_import)
        tabs_box.addWidget(self.btn_tab_culling)
        tabs_box.addWidget(self.btn_tab_transfer)
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

        self.btn_refresh = QPushButton("Neu laden")
        self.btn_refresh.setObjectName("secondaryBtn")
        self.btn_refresh.setIcon(get_refresh_icon())
        self.btn_refresh.setIconSize(QSize(14, 14))
        self.btn_refresh.setToolTip("Laufwerke und Speicherkarten erneut scannen")
        self.btn_refresh.clicked.connect(self.refresh_drives)
        layout.addWidget(self.btn_refresh, 0, Qt.AlignmentFlag.AlignVCenter)

        self.btn_eject = QPushButton("Auswerfen")
        self.btn_eject.setObjectName("secondaryBtn")
        self.btn_eject.setIcon(get_eject_icon())
        self.btn_eject.setIconSize(QSize(14, 14))
        self.btn_eject.setToolTip("Ausgewähltes Wechsellaufwerk sicher entfernen")
        self.btn_eject.clicked.connect(self._on_eject_clicked)
        layout.addWidget(self.btn_eject, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addSpacing(10)

        # History & Help buttons
        self.btn_history = QPushButton("Historie")
        self.btn_history.setObjectName("secondaryBtn")
        self.btn_history.setIcon(get_history_icon())
        self.btn_history.setIconSize(QSize(14, 14))
        self.btn_history.clicked.connect(self.open_history.emit)
        layout.addWidget(self.btn_history, 0, Qt.AlignmentFlag.AlignVCenter)

        self.btn_help = QPushButton("Hilfe")
        self.btn_help.setObjectName("secondaryBtn")
        self.btn_help.setIcon(get_help_icon())
        self.btn_help.setIconSize(QSize(14, 14))
        self.btn_help.clicked.connect(self.open_help.emit)
        layout.addWidget(self.btn_help, 0, Qt.AlignmentFlag.AlignVCenter)

        # Settings Button with Gear Icon & Configuration Dropdown Menu
        self.btn_settings = QPushButton()
        self.btn_settings.setObjectName("secondaryBtn")
        self.btn_settings.setIcon(get_gear_icon())
        self.btn_settings.setIconSize(QSize(16, 16))
        self.btn_settings.setFixedSize(32, 26)
        self.btn_settings.setToolTip("Konfigurationsmenü & Einstellungen öffnen")

        self.settings_menu = QMenu(self)
        self.settings_menu.setObjectName("settingsMenu")

        act_all = self.settings_menu.addAction("Alle Einstellungen öffnen...")
        act_all.setIcon(get_gear_icon("#38bdf8", 14))
        act_all.triggered.connect(lambda: self.open_settings.emit(0))

        act_fs = self.settings_menu.addAction("Vollbildmodus (F11)")
        act_fs.setIcon(get_fullscreen_icon())
        act_fs.triggered.connect(self.toggle_fullscreen_requested.emit)

        self.settings_menu.addSeparator()

        lbl_theme = self.settings_menu.addAction("── Farbschema / Theme ──")
        lbl_theme.setEnabled(False)

        self.theme_action_group = QActionGroup(self)
        self.theme_action_group.setExclusive(True)

        self.act_theme_dark = self.settings_menu.addAction("Dunkel (Fluent Dark)")
        self.act_theme_dark.setIcon(get_theme_icon("dark"))
        self.act_theme_dark.setCheckable(True)
        self.theme_action_group.addAction(self.act_theme_dark)
        self.act_theme_dark.triggered.connect(lambda: self._on_theme_selected(THEME_DARK))

        self.act_theme_light = self.settings_menu.addAction("Hell (Fluent Light)")
        self.act_theme_light.setIcon(get_theme_icon("light"))
        self.act_theme_light.setCheckable(True)
        self.theme_action_group.addAction(self.act_theme_light)
        self.act_theme_light.triggered.connect(lambda: self._on_theme_selected(THEME_LIGHT))

        self.act_theme_system = self.settings_menu.addAction("Automatisch (System)")
        self.act_theme_system.setIcon(get_theme_icon("system"))
        self.act_theme_system.setCheckable(True)
        self.theme_action_group.addAction(self.act_theme_system)
        self.act_theme_system.triggered.connect(lambda: self._on_theme_selected(THEME_SYSTEM))

        self.settings_menu.addSeparator()

        lbl_sec = self.settings_menu.addAction("── 👁️ Einzelansicht: Anzeigen ──")
        lbl_sec.setEnabled(False)

        self.act_sv_filename = self.settings_menu.addAction("Name des Bildes (Dateiname)")
        self.act_sv_filename.setCheckable(True)
        self.act_sv_filename.toggled.connect(lambda chk: self._on_menu_sv_toggled("single_view_show_filename", chk))

        self.act_sv_extension = self.settings_menu.addAction("Dateiendung (.JPG, .ORF...)")
        self.act_sv_extension.setCheckable(True)
        self.act_sv_extension.toggled.connect(lambda chk: self._on_menu_sv_toggled("single_view_show_extension", chk))

        self.act_sv_ratings = self.settings_menu.addAction("Sterne & Bewertungen (★, [P], [X])")
        self.act_sv_ratings.setCheckable(True)
        self.act_sv_ratings.toggled.connect(lambda chk: self._on_menu_sv_toggled("single_view_show_ratings", chk))

        self.act_sv_path = self.settings_menu.addAction("Speicherort (Ordnerpfad)")
        self.act_sv_path.setCheckable(True)
        self.act_sv_path.toggled.connect(lambda chk: self._on_menu_sv_toggled("single_view_show_path", chk))

        self.act_sv_cam = self.settings_menu.addAction("Kamera & Objektiv")
        self.act_sv_cam.setCheckable(True)
        self.act_sv_cam.toggled.connect(lambda chk: self._on_menu_sv_toggled("single_view_show_camera_lens", chk))

        self.act_sv_exp = self.settings_menu.addAction("Belichtungsdaten & ISO")
        self.act_sv_exp.setCheckable(True)
        self.act_sv_exp.toggled.connect(lambda chk: self._on_menu_sv_toggled("single_view_show_exposure", chk))

        self.act_sv_date = self.settings_menu.addAction("Aufnahmedatum & Uhrzeit")
        self.act_sv_date.setCheckable(True)
        self.act_sv_date.toggled.connect(lambda chk: self._on_menu_sv_toggled("single_view_show_date", chk))

        self.act_sv_size = self.settings_menu.addAction("Dateigröße & Dimensionen")
        self.act_sv_size.setCheckable(True)
        self.act_sv_size.toggled.connect(lambda chk: self._on_menu_sv_toggled("single_view_show_filesize", chk))

        self.settings_menu.addSeparator()

        lbl_nav = self.settings_menu.addAction("── ⌨️ Bildwechsel / Navigation ──")
        lbl_nav.setEnabled(False)

        self.nav_action_group = QActionGroup(self)
        self.nav_action_group.setExclusive(True)
        self.nav_actions = {}

        for s_id, s_data in NAVIGATION_SCHEMES.items():
            act = self.settings_menu.addAction(s_data["short_name"])
            act.setCheckable(True)
            self.nav_action_group.addAction(act)
            act.triggered.connect(lambda checked=False, s=s_id: self._on_menu_nav_selected(s))
            self.nav_actions[s_id] = act

        self.settings_menu.addSeparator()

        act_nas = self.settings_menu.addAction("🏠 NAS & Familienalbum...")
        act_nas.triggered.connect(lambda: self.open_settings.emit(2))

        act_ext = self.settings_menu.addAction("🎨 Externe Editoren (Darktable/Topaz)...")
        act_ext.triggered.connect(lambda: self.open_settings.emit(3))

        self.btn_settings.setMenu(self.settings_menu)
        layout.addWidget(self.btn_settings, 0, Qt.AlignmentFlag.AlignVCenter)

    def update_from_config(self, config: AppConfig):
        """Synchronizes menu checkable actions with the current AppConfig."""
        self.config = config
        actions = [
            (self.act_sv_filename, config.single_view_show_filename),
            (self.act_sv_extension, config.single_view_show_extension),
            (self.act_sv_ratings, config.single_view_show_ratings),
            (self.act_sv_path, config.single_view_show_path),
            (self.act_sv_cam, config.single_view_show_camera_lens),
            (self.act_sv_exp, config.single_view_show_exposure),
            (self.act_sv_date, config.single_view_show_date),
            (self.act_sv_size, config.single_view_show_filesize),
        ]
        for act, val in actions:
            act.blockSignals(True)
            act.setChecked(val)
            act.blockSignals(False)

        curr_scheme = getattr(config, "navigation_scheme", DEFAULT_NAVIGATION_SCHEME)
        if curr_scheme in self.nav_actions:
            self.nav_actions[curr_scheme].blockSignals(True)
            self.nav_actions[curr_scheme].setChecked(True)
            self.nav_actions[curr_scheme].blockSignals(False)

        curr_theme = getattr(config, "theme", THEME_DARK)
        self.act_theme_dark.blockSignals(True)
        self.act_theme_light.blockSignals(True)
        self.act_theme_system.blockSignals(True)
        if curr_theme == THEME_LIGHT:
            self.act_theme_light.setChecked(True)
        elif curr_theme == THEME_SYSTEM:
            self.act_theme_system.setChecked(True)
        else:
            self.act_theme_dark.setChecked(True)
        self.act_theme_dark.blockSignals(False)
        self.act_theme_light.blockSignals(False)
        self.act_theme_system.blockSignals(False)

    def _on_theme_selected(self, theme_mode: str):
        theme_manager.apply_theme(theme_mode, config=self.config)
        if self.config:
            self.config.save()
        self.refresh_icons()

    def refresh_icons(self):
        """Refreshes all vector icons according to the active theme palette."""
        self.btn_tab_import.setIcon(get_import_icon())
        self.btn_tab_culling.setIcon(get_culling_icon())
        self.btn_tab_transfer.setIcon(get_archive_icon())
        self.btn_refresh.setIcon(get_refresh_icon())
        self.btn_eject.setIcon(get_eject_icon())
        self.btn_history.setIcon(get_history_icon())
        self.btn_help.setIcon(get_help_icon())
        self.btn_settings.setIcon(get_gear_icon())
        self.act_theme_dark.setIcon(get_theme_icon("dark"))
        self.act_theme_light.setIcon(get_theme_icon("light"))
        self.act_theme_system.setIcon(get_theme_icon("system"))

    def _on_menu_nav_selected(self, scheme_id: str):
        if self.config:
            self.config.navigation_scheme = scheme_id
            self.config.save()
            self.single_view_config_changed.emit()

    def _on_menu_sv_toggled(self, attr_name: str, checked: bool):
        if self.config:
            setattr(self.config, attr_name, checked)
            self.config.save()
            self.single_view_config_changed.emit()

    def switch_tab(self, tab_idx: int):
        self.btn_tab_import.setChecked(tab_idx == 0)
        self.btn_tab_culling.setChecked(tab_idx == 1)
        self.btn_tab_transfer.setChecked(tab_idx == 2)
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
