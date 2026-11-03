"""Filter and view switcher toolbar with responsive layout."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSlider, QSizePolicy, QWidget
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
        self.combo_view.addItem("📋 Tabelle", "table")
        self.combo_view.addItem("🖼️ Galerie", "gallery")
        self.combo_view.addItem("🔍 Einzelansicht", "single")
        self.combo_view.addItem("📁 Ordnerstruktur", "tree")
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
        self.combo_status.addItem("Status: Alle", "all")
        self.combo_status.addItem("✨ Nur Neue", "new_only")
        self.combo_status.addItem("⚠️ Nur Duplikate", "duplicates_only")
        self.combo_status.currentIndexChanged.connect(
            lambda: self.status_filter_changed.emit(self.combo_status.currentData())
        )
        layout.addWidget(self.combo_status)

        # 3. Media Type
        self.combo_type = QComboBox()
        self.combo_type.addItem("Typ: Alle", "all")
        self.combo_type.addItem("📷 Fotos", "Fotos")
        self.combo_type.addItem("🎞️ RAW", "RAW")
        self.combo_type.addItem("🎥 Videos", "Videos")
        self.combo_type.currentIndexChanged.connect(
            lambda: self.type_filter_changed.emit(self.combo_type.currentData())
        )
        layout.addWidget(self.combo_type)

        # 4. Search input (with priority stretch and guaranteed minimum width)
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("🔍 Suchen...")
        self.edit_search.setMinimumWidth(130)
        self.edit_search.textChanged.connect(self.search_changed.emit)
        layout.addWidget(self.edit_search, stretch=1)

        # 5. Selection Buttons
        self.btn_select_all = QPushButton("Alle")
        self.btn_select_all.setObjectName("chipBtn")
        self.btn_select_all.setToolTip("Alle Elemente auswählen")
        self.btn_select_all.clicked.connect(self.select_all_clicked.emit)

        self.btn_select_none = QPushButton("Keine")
        self.btn_select_none.setObjectName("chipBtn")
        self.btn_select_none.setToolTip("Auswahl aufheben")
        self.btn_select_none.clicked.connect(self.deselect_all_clicked.emit)

        self.btn_select_new = QPushButton("Neue")
        self.btn_select_new.setObjectName("chipBtn")
        self.btn_select_new.setToolTip("Nur neue Fotos auswählen")
        self.btn_select_new.clicked.connect(self.select_new_clicked.emit)

        layout.addWidget(self.btn_select_all)
        layout.addWidget(self.btn_select_none)
        layout.addWidget(self.btn_select_new)

        # 6. EXIF Inspector Toggle Button
        self.btn_toggle_exif = QPushButton("ℹ️ EXIF")
        self.btn_toggle_exif.setCheckable(True)
        self.btn_toggle_exif.setObjectName("chipBtn")
        self.btn_toggle_exif.setToolTip("EXIF- & Metadaten-Inspektor ein-/ausblenden")
        self.btn_toggle_exif.toggled.connect(self.toggle_exif_panel.emit)
        layout.addWidget(self.btn_toggle_exif)

    def _on_view_changed(self):
        mode = self.combo_view.currentData()
        is_gallery = (mode == "gallery")
        self.slider_zoom.setVisible(is_gallery)
        self.view_mode_changed.emit(mode)
