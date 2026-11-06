"""Filter tab and criteria engine for Tab 2: Sichten & Sortieren.

Allows filtering displayed photos by:
- RAW or JPEG file types (RAW, JPEG, RAW+JPEG pairs, standalone RAW/JPEG)
- Rating (Stars 1-5, unrated)
- Status / Tags (Picked [P], Rejected [X], Not Rejected)
- Color Labels
- Camera Make / Model (dynamically populated from current folder)
- Extended EXIF attributes (Lens, ISO, search query)
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget
)

from gui_qt.models.culling_model import CullingItem
from gui_qt.styles.icons import get_collapse_panel_icon, get_filter_icon, get_refresh_icon


@dataclass
class CullingFilterCriteria:
    file_type: str = "ALL"         # "ALL", "RAW_ANY", "JPEG_ANY", "PAIR_ONLY", "RAW_ONLY", "JPEG_ONLY"
    rating_mode: str = "ALL"       # "ALL", "MIN_1", "MIN_2", "MIN_3", "MIN_4", "EXACT_5", "UNRATED"
    status: str = "ALL"            # "ALL", "PICKED", "REJECTED", "NOT_REJECTED"
    color_label: str = "ALL"       # "ALL", "Red", "Yellow", "Green", "Blue", "Purple", "NONE"
    camera: str = "ALL"            # "ALL" or specific camera string
    lens: str = "ALL"              # "ALL" or specific lens string
    iso_range: str = "ALL"         # "ALL", "LOW", "MID", "HIGH", "VERY_HIGH"
    search_text: str = ""          # Case-insensitive substring query

    def is_active(self) -> bool:
        """Returns True if any non-default filter is currently active."""
        return (
            self.file_type != "ALL"
            or self.rating_mode != "ALL"
            or self.status != "ALL"
            or self.color_label != "ALL"
            or self.camera != "ALL"
            or self.lens != "ALL"
            or self.iso_range != "ALL"
            or bool(self.search_text.strip())
        )

    def matches(self, item: CullingItem) -> bool:
        """Evaluates whether an item fulfills all configured filter criteria."""
        # 1. File Type (RAW oder JPEG)
        has_raw = item.raw_path is not None
        has_jpeg = item.jpeg_path is not None

        if self.file_type == "RAW_ANY":
            if not has_raw:
                return False
        elif self.file_type == "JPEG_ANY":
            if not has_jpeg:
                return False
        elif self.file_type == "PAIR_ONLY":
            if not (has_raw and has_jpeg):
                return False
        elif self.file_type == "RAW_ONLY":
            if not (has_raw and not has_jpeg):
                return False
        elif self.file_type == "JPEG_ONLY":
            if not (has_jpeg and not has_raw):
                return False

        # 2. Rating
        if self.rating_mode == "MIN_1" and item.rating < 1:
            return False
        elif self.rating_mode == "MIN_2" and item.rating < 2:
            return False
        elif self.rating_mode == "MIN_3" and item.rating < 3:
            return False
        elif self.rating_mode == "MIN_4" and item.rating < 4:
            return False
        elif self.rating_mode == "EXACT_5" and item.rating != 5:
            return False
        elif self.rating_mode == "UNRATED" and item.rating != 0:
            return False

        # 3. Status (Picked / Rejected)
        if self.status == "PICKED" and not item.is_picked:
            return False
        elif self.status == "REJECTED" and not item.is_rejected:
            return False
        elif self.status == "NOT_REJECTED" and item.is_rejected:
            return False

        # 4. Color Label
        if self.color_label != "ALL":
            if self.color_label == "NONE" and item.color_label:
                return False
            elif self.color_label != "NONE" and item.color_label != self.color_label:
                return False

        # 5. Camera
        if self.camera != "ALL":
            cam = item.metadata.camera_name if item.metadata else ""
            if cam != self.camera:
                return False

        # 6. Lens (Extended EXIF)
        if self.lens != "ALL":
            lens = item.metadata.lens_model if item.metadata else ""
            if lens != self.lens:
                return False

        # 7. ISO Range (Extended EXIF)
        if self.iso_range != "ALL" and item.metadata:
            iso = item.metadata.iso
            if iso is None:
                return False
            if self.iso_range == "LOW" and iso > 400:
                return False
            elif self.iso_range == "MID" and not (400 < iso <= 1600):
                return False
            elif self.iso_range == "HIGH" and not (1600 < iso <= 6400):
                return False
            elif self.iso_range == "VERY_HIGH" and iso <= 6400:
                return False

        # 8. Text Search
        if self.search_text.strip():
            query = self.search_text.strip().lower()
            name = item.primary_path.name.lower()
            cam = (item.metadata.camera_name.lower() if item.metadata else "")
            lens = (item.metadata.lens_model.lower() if item.metadata else "")
            if query not in name and query not in cam and query not in lens:
                return False

        return True


class CullingFilterWidget(QWidget):
    """Filter configuration panel with instant reactive filtering."""
    filter_changed = Signal(object)  # CullingFilterCriteria
    collapse_panel_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._block_signals: bool = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # -------------------------------------------------------------
        # Header bar with Collapse button & Reset button
        # -------------------------------------------------------------
        head_frame = QFrame()
        head_frame.setStyleSheet("""
            QFrame {
                background-color: #0b1120;
                border-bottom: 1px solid #1e293b;
            }
        """)
        head_layout = QHBoxLayout(head_frame)
        head_layout.setContentsMargins(8, 6, 8, 6)
        head_layout.setSpacing(6)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(get_filter_icon("#38bdf8", 16).pixmap(16, 16))
        head_layout.addWidget(lbl_icon)

        lbl_title = QLabel("BILDER-FILTER")
        lbl_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #f8fafc; letter-spacing: 0.5px;")
        head_layout.addWidget(lbl_title, stretch=1)

        self.btn_reset = QPushButton("✕ Zurücksetzen")
        self.btn_reset.setToolTip("Alle aktiven Filter aufheben")
        self.btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; color: #94a3b8; border: 1px solid #334155;
                border-radius: 4px; padding: 2px 7px; font-size: 10px; font-weight: 500;
            }
            QPushButton:hover { background-color: #334155; color: #f8fafc; }
        """)
        self.btn_reset.clicked.connect(self.reset_filters)
        head_layout.addWidget(self.btn_reset)

        self.btn_collapse = QPushButton()
        self.btn_collapse.setIcon(get_collapse_panel_icon("#94a3b8", 14))
        self.btn_collapse.setIconSize(QSize(14, 14))
        self.btn_collapse.setFixedSize(24, 24)
        self.btn_collapse.setToolTip("Seitenleiste nach links einklappen [V]")
        self.btn_collapse.setStyleSheet("""
            QPushButton {
                background-color: transparent; border: 1px solid transparent;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1e293b; border-color: #334155; }
        """)
        self.btn_collapse.clicked.connect(self.collapse_panel_requested.emit)
        head_layout.addWidget(self.btn_collapse)

        layout.addWidget(head_frame)

        # -------------------------------------------------------------
        # Scrollable Filter Controls
        # -------------------------------------------------------------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background-color: #090d16;")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(6, 8, 6, 8)
        content_layout.setSpacing(10)

        card_style = """
            QFrame {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 6px;
            }
        """
        label_head_style = "font-size: 10px; font-weight: bold; color: #94a3b8; text-transform: uppercase;"
        combo_style = """
            QComboBox {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 11px;
            }
            QComboBox:hover { border-color: #38bdf8; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #0f172a;
                color: #f8fafc;
                selection-background-color: #0369a1;
                border: 1px solid #334155;
            }
        """

        # -------------------------------------------------------------
        # 1. DATEITYP (RAW oder JPEG)
        # -------------------------------------------------------------
        card_type = QFrame()
        card_type.setStyleSheet(card_style)
        lt_type = QVBoxLayout(card_type)
        lt_type.setContentsMargins(6, 6, 6, 6)
        lt_type.setSpacing(4)

        lbl_type = QLabel("📷 Dateityp (RAW / JPEG)")
        lbl_type.setStyleSheet(label_head_style)
        lt_type.addWidget(lbl_type)

        self.cmb_file_type = QComboBox()
        self.cmb_file_type.setStyleSheet(combo_style)
        self.cmb_file_type.addItem("Alle Formate", "ALL")
        self.cmb_file_type.addItem("Nur RAW (inkl. RAW+JPG)", "RAW_ANY")
        self.cmb_file_type.addItem("Nur JPEG (inkl. RAW+JPG)", "JPEG_ANY")
        self.cmb_file_type.addItem("Nur RAW+JPEG Paare", "PAIR_ONLY")
        self.cmb_file_type.addItem("Reine RAWs (ohne JPEG)", "RAW_ONLY")
        self.cmb_file_type.addItem("Reine JPEGs (ohne RAW)", "JPEG_ONLY")
        self.cmb_file_type.currentIndexChanged.connect(self._emit_change)
        lt_type.addWidget(self.cmb_file_type)

        content_layout.addWidget(card_type)

        # -------------------------------------------------------------
        # 2. TAG / BEWERTUNG & STATUS
        # -------------------------------------------------------------
        card_tags = QFrame()
        card_tags.setStyleSheet(card_style)
        lt_tags = QVBoxLayout(card_tags)
        lt_tags.setContentsMargins(6, 6, 6, 6)
        lt_tags.setSpacing(6)

        lbl_tags = QLabel("⭐ Bewertung & Status / Tags")
        lbl_tags.setStyleSheet(label_head_style)
        lt_tags.addWidget(lbl_tags)

        # Rating ComboBox
        self.cmb_rating = QComboBox()
        self.cmb_rating.setStyleSheet(combo_style)
        self.cmb_rating.addItem("Alle Bewertungen", "ALL")
        self.cmb_rating.addItem("★ 1+ Stern(e)", "MIN_1")
        self.cmb_rating.addItem("★★ 2+ Sterne", "MIN_2")
        self.cmb_rating.addItem("★★★ 3+ Sterne", "MIN_3")
        self.cmb_rating.addItem("★★★★ 4+ Sterne", "MIN_4")
        self.cmb_rating.addItem("★★★★★ 5 Sterne", "EXACT_5")
        self.cmb_rating.addItem("Ohne Bewertung (0★)", "UNRATED")
        self.cmb_rating.currentIndexChanged.connect(self._emit_change)
        lt_tags.addWidget(self.cmb_rating)

        # Status ComboBox (Picked, Rejected)
        self.cmb_status = QComboBox()
        self.cmb_status.setStyleSheet(combo_style)
        self.cmb_status.addItem("Alle Status", "ALL")
        self.cmb_status.addItem("✔ Nur Behalten [P]", "PICKED")
        self.cmb_status.addItem("✖ Nur Abgelehnt [X]", "REJECTED")
        self.cmb_status.addItem("Nicht abgelehnt (P & Normal)", "NOT_REJECTED")
        self.cmb_status.currentIndexChanged.connect(self._emit_change)
        lt_tags.addWidget(self.cmb_status)

        # Color Label ComboBox
        self.cmb_color = QComboBox()
        self.cmb_color.setStyleSheet(combo_style)
        self.cmb_color.addItem("Alle Farblabels", "ALL")
        self.cmb_color.addItem("🔴 Rot", "Red")
        self.cmb_color.addItem("🟡 Gelb", "Yellow")
        self.cmb_color.addItem("🟢 Grün", "Green")
        self.cmb_color.addItem("🔵 Blau", "Blue")
        self.cmb_color.addItem("🟣 Lila", "Purple")
        self.cmb_color.addItem("Ohne Farblabel", "NONE")
        self.cmb_color.currentIndexChanged.connect(self._emit_change)
        lt_tags.addWidget(self.cmb_color)

        content_layout.addWidget(card_tags)

        # -------------------------------------------------------------
        # 3. KAMERA (Camera)
        # -------------------------------------------------------------
        card_cam = QFrame()
        card_cam.setStyleSheet(card_style)
        lt_cam = QVBoxLayout(card_cam)
        lt_cam.setContentsMargins(6, 6, 6, 6)
        lt_cam.setSpacing(4)

        lbl_cam = QLabel("🎥 Kamera (Camera)")
        lbl_cam.setStyleSheet(label_head_style)
        lt_cam.addWidget(lbl_cam)

        self.cmb_camera = QComboBox()
        self.cmb_camera.setStyleSheet(combo_style)
        self.cmb_camera.addItem("Alle Kameras", "ALL")
        self.cmb_camera.currentIndexChanged.connect(self._emit_change)
        lt_cam.addWidget(self.cmb_camera)

        content_layout.addWidget(card_cam)

        # -------------------------------------------------------------
        # 4. ERWEITERTE EXIF-FILTER (Objektiv, ISO, Suche)
        # -------------------------------------------------------------
        card_exif = QFrame()
        card_exif.setStyleSheet(card_style)
        lt_exif = QVBoxLayout(card_exif)
        lt_exif.setContentsMargins(6, 6, 6, 6)
        lt_exif.setSpacing(6)

        lbl_exif = QLabel("🔍 Erweiterte EXIF & Suche")
        lbl_exif.setStyleSheet(label_head_style)
        lt_exif.addWidget(lbl_exif)

        # Search field
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Dateiname / Suche...")
        self.txt_search.setStyleSheet("""
            QLineEdit {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 11px;
            }
            QLineEdit:focus { border-color: #38bdf8; }
        """)
        self.txt_search.textChanged.connect(self._emit_change)
        lt_exif.addWidget(self.txt_search)

        # Lens ComboBox
        self.cmb_lens = QComboBox()
        self.cmb_lens.setStyleSheet(combo_style)
        self.cmb_lens.addItem("Alle Objektive", "ALL")
        self.cmb_lens.currentIndexChanged.connect(self._emit_change)
        lt_exif.addWidget(self.cmb_lens)

        # ISO Range ComboBox
        self.cmb_iso = QComboBox()
        self.cmb_iso.setStyleSheet(combo_style)
        self.cmb_iso.addItem("Alle ISO-Werte", "ALL")
        self.cmb_iso.addItem("ISO ≤ 400 (Niedrig)", "LOW")
        self.cmb_iso.addItem("ISO 400 - 1600 (Mittel)", "MID")
        self.cmb_iso.addItem("ISO 1600 - 6400 (Hoch)", "HIGH")
        self.cmb_iso.addItem("ISO > 6400 (Sehr hoch)", "VERY_HIGH")
        self.cmb_iso.currentIndexChanged.connect(self._emit_change)
        lt_exif.addWidget(self.cmb_iso)

        content_layout.addWidget(card_exif)

        # -------------------------------------------------------------
        # 5. ERGEBNIS-STATUS
        # -------------------------------------------------------------
        card_stats = QFrame()
        card_stats.setStyleSheet("""
            QFrame {
                background-color: #0b1329;
                border: 1px solid #1e3a8a;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        lt_stats = QVBoxLayout(card_stats)
        lt_stats.setContentsMargins(6, 6, 6, 6)
        lt_stats.setSpacing(2)

        self.lbl_filter_stats = QLabel("Filter: Inaktiv")
        self.lbl_filter_stats.setStyleSheet("font-size: 11px; font-weight: bold; color: #38bdf8;")
        lt_stats.addWidget(self.lbl_filter_stats)

        self.lbl_filter_sub = QLabel("Zeige alle Bilder")
        self.lbl_filter_sub.setStyleSheet("font-size: 10px; color: #94a3b8;")
        lt_stats.addWidget(self.lbl_filter_sub)

        content_layout.addWidget(card_stats)
        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _emit_change(self):
        if self._block_signals:
            return
        crit = self.get_criteria()
        self._update_status_display(crit)
        self.filter_changed.emit(crit)

    def _update_status_display(self, crit: CullingFilterCriteria):
        if crit.is_active():
            self.lbl_filter_stats.setText("● Filter aktiv")
            self.lbl_filter_stats.setStyleSheet("font-size: 11px; font-weight: bold; color: #38bdf8;")
            self.btn_reset.setEnabled(True)
        else:
            self.lbl_filter_stats.setText("Filter: Inaktiv")
            self.lbl_filter_stats.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748b;")
            self.btn_reset.setEnabled(False)

    def get_criteria(self) -> CullingFilterCriteria:
        """Returns the current filter criteria object."""
        return CullingFilterCriteria(
            file_type=self.cmb_file_type.currentData() or "ALL",
            rating_mode=self.cmb_rating.currentData() or "ALL",
            status=self.cmb_status.currentData() or "ALL",
            color_label=self.cmb_color.currentData() or "ALL",
            camera=self.cmb_camera.currentData() or "ALL",
            lens=self.cmb_lens.currentData() or "ALL",
            iso_range=self.cmb_iso.currentData() or "ALL",
            search_text=self.txt_search.text(),
        )

    def reset_filters(self):
        """Resets all filters to neutral / show all."""
        self._block_signals = True
        self.cmb_file_type.setCurrentIndex(0)
        self.cmb_rating.setCurrentIndex(0)
        self.cmb_status.setCurrentIndex(0)
        self.cmb_color.setCurrentIndex(0)
        self.cmb_camera.setCurrentIndex(0)
        self.cmb_lens.setCurrentIndex(0)
        self.cmb_iso.setCurrentIndex(0)
        self.txt_search.clear()
        self._block_signals = False

        self._emit_change()

    def update_folder_items(self, items: List[CullingItem]):
        """Populates dynamic dropdowns (Cameras, Lenses) from folder items."""
        prev_camera = self.cmb_camera.currentData() or "ALL"
        prev_lens = self.cmb_lens.currentData() or "ALL"

        camera_counts: Dict[str, int] = {}
        lens_counts: Dict[str, int] = {}

        for it in items:
            if it.metadata:
                cam = it.metadata.camera_name.strip()
                if cam:
                    camera_counts[cam] = camera_counts.get(cam, 0) + 1
                lens = it.metadata.lens_model.strip()
                if lens:
                    lens_counts[lens] = lens_counts.get(lens, 0) + 1

        self._block_signals = True

        # Update Camera ComboBox
        self.cmb_camera.clear()
        self.cmb_camera.addItem(f"Alle Kameras ({len(items)})", "ALL")
        target_cam_idx = 0
        for idx, (cam_name, cnt) in enumerate(sorted(camera_counts.items()), 1):
            self.cmb_camera.addItem(f"{cam_name} ({cnt})", cam_name)
            if cam_name == prev_camera:
                target_cam_idx = idx
        self.cmb_camera.setCurrentIndex(target_cam_idx)

        # Update Lens ComboBox
        self.cmb_lens.clear()
        self.cmb_lens.addItem("Alle Objektive", "ALL")
        target_lens_idx = 0
        for idx, (lens_name, cnt) in enumerate(sorted(lens_counts.items()), 1):
            self.cmb_lens.addItem(f"{lens_name} ({cnt})", lens_name)
            if lens_name == prev_lens:
                target_lens_idx = idx
        self.cmb_lens.setCurrentIndex(target_lens_idx)

        self._block_signals = False

    def update_match_stats(self, matched_count: int, total_count: int):
        """Updates the match counter in the bottom statistics card."""
        hidden = total_count - matched_count
        if hidden > 0:
            self.lbl_filter_sub.setText(f"Zeige {matched_count} von {total_count} Fotos ({hidden} ausgeblendet)")
        else:
            self.lbl_filter_sub.setText(f"Zeige alle {total_count} Fotos")
