"""Filter and view switcher toolbar."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSlider, QSizePolicy, QWidget
)


class FilterBarWidget(QWidget):
    view_mode_changed = Signal(str)      # "table", "gallery"
    status_filter_changed = Signal(str)  # "all", "new_only", "duplicates_only"
    type_filter_changed = Signal(str)    # "all", "Fotos", "RAW", "Videos"
    search_changed = Signal(str)
    select_all_clicked = Signal()
    deselect_all_clicked = Signal()
    select_new_clicked = Signal()
    thumbnail_size_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)

        # 1. View Mode (Table vs Gallery)
        lbl_view = QLabel("Ansicht:")
        lbl_view.setObjectName("subtleLabel")
        self.combo_view = QComboBox()
        self.combo_view.addItem("\U0001F4CB Tabelle", "table")
        self.combo_view.addItem("\U0001F5BC Galerie", "gallery")
        self.combo_view.currentIndexChanged.connect(self._on_view_changed)
        layout.addWidget(lbl_view)
        layout.addWidget(self.combo_view)

        # 1b. Zoom Slider (for Gallery mode)
        self.lbl_zoom = QLabel("\U0001F50D")
        self.lbl_zoom.setObjectName("subtleLabel")
        self.lbl_zoom.setToolTip("Größe der Vorschaubilder")
        self.slider_zoom = QSlider(Qt.Orientation.Horizontal)
        self.slider_zoom.setRange(110, 320)
        self.slider_zoom.setValue(160)
        self.slider_zoom.setFixedWidth(80)
        self.slider_zoom.setToolTip("Vorschaugröße anpassen")
        self.slider_zoom.valueChanged.connect(self.thumbnail_size_changed.emit)

        self.lbl_zoom.setVisible(False)
        self.slider_zoom.setVisible(False)
        layout.addWidget(self.lbl_zoom)
        layout.addWidget(self.slider_zoom)

        layout.addSpacing(6)

        # 2. Filter Status
        lbl_filter = QLabel("Filter:")
        lbl_filter.setObjectName("subtleLabel")
        self.combo_status = QComboBox()
        self.combo_status.addItem("Alle Status", "all")
        self.combo_status.addItem("\u2728 Nur neue Fotos", "new_only")
        self.combo_status.addItem("\u26A0 Nur Duplikate", "duplicates_only")
        self.combo_status.currentIndexChanged.connect(
            lambda: self.status_filter_changed.emit(self.combo_status.currentData())
        )
        layout.addWidget(lbl_filter)
        layout.addWidget(self.combo_status)

        # 3. Media Type
        self.combo_type = QComboBox()
        self.combo_type.addItem("Alle Medien", "all")
        self.combo_type.addItem("\U0001F4F8 Fotos", "Fotos")
        self.combo_type.addItem("\U0001F39E RAW-Formate", "RAW")
        self.combo_type.addItem("\U0001F3A5 Videos", "Videos")
        self.combo_type.currentIndexChanged.connect(
            lambda: self.type_filter_changed.emit(self.combo_type.currentData())
        )
        layout.addWidget(self.combo_type)

        # 4. Search input
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("\U0001F50D Suche nach Name, Kamera...")
        self.edit_search.textChanged.connect(self.search_changed.emit)
        layout.addWidget(self.edit_search, stretch=1)

        # 5. Selection Buttons
        self.btn_select_all = QPushButton("Alle")
        self.btn_select_all.setObjectName("chipBtn")
        self.btn_select_all.clicked.connect(self.select_all_clicked.emit)

        self.btn_select_none = QPushButton("Keine")
        self.btn_select_none.setObjectName("chipBtn")
        self.btn_select_none.clicked.connect(self.deselect_all_clicked.emit)

        self.btn_select_new = QPushButton("Nur neue")
        self.btn_select_new.setObjectName("chipBtn")
        self.btn_select_new.clicked.connect(self.select_new_clicked.emit)

        layout.addWidget(self.btn_select_all)
        layout.addWidget(self.btn_select_none)
        layout.addWidget(self.btn_select_new)

    def _on_view_changed(self):
        mode = self.combo_view.currentData()
        is_gallery = (mode == "gallery")
        self.lbl_zoom.setVisible(is_gallery)
        self.slider_zoom.setVisible(is_gallery)
        self.view_mode_changed.emit(mode)
