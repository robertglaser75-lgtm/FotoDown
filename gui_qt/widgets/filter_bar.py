"""Filter and view switcher toolbar with responsive layout."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLineEdit, QMenu, QPushButton,
    QSlider, QSizePolicy, QWidget
)

from gui_qt.styles.icons import (
    get_camera_icon, get_check_all_icon, get_clear_icon, get_files_icon,
    get_filmstrip_icon, get_folder_icon, get_grid_icon, get_grid_large_icon,
    get_info_icon, get_list_icon, get_search_icon, get_uncheck_all_icon, get_video_icon
)


class FilterBarWidget(QWidget):
    view_mode_changed = Signal(str)      # "table", "gallery", "tree"
    status_filter_changed = Signal(str)  # "all", "new_only", "duplicates_only"
    type_filter_changed = Signal(str)    # "all", "Fotos", "RAW", "Videos"
    search_changed = Signal(str)
    select_all_clicked = Signal()
    deselect_all_clicked = Signal()
    select_new_clicked = Signal()
    thumbnail_size_changed = Signal(int)
    toggle_exif_panel = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 4)
        layout.setSpacing(6)

        # 1. View Mode (Table vs Gallery vs Single vs Destination Tree)
        self.combo_view = QComboBox()
        self.combo_view.addItem(get_list_icon(size=13), "Tabelle", "table")
        self.combo_view.addItem(get_grid_icon(size=13), "Galerie", "gallery")
        self.combo_view.addItem(get_grid_large_icon(size=13), "Einzelansicht", "single")
        self.combo_view.addItem(get_folder_icon(size=13), "Ordnerstruktur", "tree")
        self.combo_view.setToolTip("Ansicht wechseln (Tabelle, Galerie, Einzelansicht oder Zielstruktur-Baum)")
        self.combo_view.currentIndexChanged.connect(self._on_view_changed)
        layout.addWidget(self.combo_view)

        # 1b. Zoom Slider (for Gallery mode)
        self.slider_zoom = QSlider(Qt.Orientation.Horizontal)
        self.slider_zoom.setRange(110, 320)
        self.slider_zoom.setValue(160)
        self.slider_zoom.setFixedWidth(70)
        self.slider_zoom.setToolTip("Größe der Vorschaubilder anpassen")
        self.slider_zoom.valueChanged.connect(self.thumbnail_size_changed.emit)
        self.slider_zoom.setVisible(False)
        layout.addWidget(self.slider_zoom)

        # 2. Filter Status
        self.combo_status = QComboBox()
        self.combo_status.addItem(get_files_icon(size=12), "Status: Alle", "all")
        self.combo_status.addItem(get_check_all_icon("#4ade80", 12), "Nur Neue", "new_only")
        self.combo_status.addItem(get_clear_icon("#fbbf24", 12), "Nur Duplikate", "duplicates_only")
        self.combo_status.currentIndexChanged.connect(
            lambda: self.status_filter_changed.emit(self.combo_status.currentData())
        )
        layout.addWidget(self.combo_status)

        # 3. Media Type
        self.combo_type = QComboBox()
        self.combo_type.addItem(get_files_icon(size=12), "Typ: Alle", "all")
        self.combo_type.addItem(get_camera_icon("#38bdf8", 12), "Fotos", "Fotos")
        self.combo_type.addItem(get_filmstrip_icon("#f43f5e", 12), "RAW", "RAW")
        self.combo_type.addItem(get_video_icon("#10b981", 12), "Videos", "Videos")
        self.combo_type.currentIndexChanged.connect(
            lambda: self.type_filter_changed.emit(self.combo_type.currentData())
        )
        layout.addWidget(self.combo_type)

        # 4. Search input (with priority stretch and leading vector icon)
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Suchen...")
        self.edit_search.addAction(get_search_icon("#94a3b8", 12), QLineEdit.ActionPosition.LeadingPosition)
        self.edit_search.setMinimumWidth(120)
        self.edit_search.textChanged.connect(self.search_changed.emit)
        layout.addWidget(self.edit_search, stretch=1)

        # 5. Compact Selection Dropdown Menu (bundles Alle / Keine / Neue)
        self.btn_selection_menu = QPushButton("Auswahl ▾")
        self.btn_selection_menu.setObjectName("chipBtn")
        self.btn_selection_menu.setIcon(get_check_all_icon(size=12))
        self.btn_selection_menu.setIconSize(QSize(12, 12))
        self.btn_selection_menu.setToolTip("Schnellauswahl (Alle, Keine, Nur Neue)")

        sel_menu = QMenu(self.btn_selection_menu)
        act_all = sel_menu.addAction(get_check_all_icon("#4ade80", 12), "Alle auswählen")
        act_all.triggered.connect(self.select_all_clicked.emit)
        act_none = sel_menu.addAction(get_uncheck_all_icon("#94a3b8", 12), "Auswahl aufheben")
        act_none.triggered.connect(self.deselect_all_clicked.emit)
        act_new = sel_menu.addAction(get_camera_icon("#38bdf8", 12), "Nur neue Fotos auswählen")
        act_new.triggered.connect(self.select_new_clicked.emit)
        self.btn_selection_menu.setMenu(sel_menu)
        layout.addWidget(self.btn_selection_menu)

        # Compatibility references for hidden direct buttons
        self.btn_select_all = QPushButton("Alle")
        self.btn_select_all.clicked.connect(self.select_all_clicked.emit)
        self.btn_select_none = QPushButton("Keine")
        self.btn_select_none.clicked.connect(self.deselect_all_clicked.emit)
        self.btn_select_new = QPushButton("Neue")
        self.btn_select_new.clicked.connect(self.select_new_clicked.emit)

        # 6. EXIF Inspector Toggle Button
        self.btn_toggle_exif = QPushButton("EXIF")
        self.btn_toggle_exif.setIcon(get_info_icon())
        self.btn_toggle_exif.setIconSize(QSize(13, 13))
        self.btn_toggle_exif.setCheckable(True)
        self.btn_toggle_exif.setObjectName("chipBtn")
        self.btn_toggle_exif.setToolTip("EXIF- & Metadaten-Inspektor ein-/ausblenden")
        self.btn_toggle_exif.toggled.connect(self.toggle_exif_panel.emit)
        layout.addWidget(self.btn_toggle_exif)

    def set_view_mode(self, mode: str):
        """Sets the active view mode in the combo box without losing sync."""
        idx = self.combo_view.findData(mode)
        if idx >= 0:
            self.combo_view.setCurrentIndex(idx)

    def _on_view_changed(self):
        mode = self.combo_view.currentData()
        is_gallery = (mode == "gallery")
        self.slider_zoom.setVisible(is_gallery)
        self.view_mode_changed.emit(mode)
