"""Single photo / full-size image view widget integrated in the workspace."""

from pathlib import Path
from typing import List, Optional
from PIL import Image

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QKeyEvent, QPainter, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget
)

from core.drive_detector import format_size
from core.importer import ScanItem
from core.thumbnail import load_preview_image


class MediaSingleView(QWidget):
    selection_toggled = Signal()
    item_focused = Signal(object)
    open_quick_preview_requested = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.items: List[ScanItem] = []
        self.current_idx: int = -1
        self._current_pixmap: Optional[QPixmap] = None
        self._zoom_mode: str = "fit"  # "fit" or "actual" (100%)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # 1. Navigation & Control Bar (Top)
        top_bar = QFrame()
        top_bar.setObjectName("singleViewHeader")
        top_bar.setStyleSheet("""
            #singleViewHeader {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 4px 8px;
            }
        """)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(4, 2, 4, 2)
        top_layout.setSpacing(8)

        # Previous Button
        self.btn_prev = QPushButton("◀ Vorheriges")
        self.btn_prev.setObjectName("chipBtn")
        self.btn_prev.setToolTip("Vorheriges Foto (Taste A oder Pfeil-Links)")
        self.btn_prev.clicked.connect(self._prev_item)
        top_layout.addWidget(self.btn_prev)

        # Next Button
        self.btn_next = QPushButton("Nächstes ▶")
        self.btn_next.setObjectName("chipBtn")
        self.btn_next.setToolTip("Nächstes Foto (Taste D oder Pfeil-Rechts)")
        self.btn_next.clicked.connect(self._next_item)
        top_layout.addWidget(self.btn_next)

        # Filename & Index Counter
        self.lbl_title = QLabel("Kein Medium ausgewählt")
        self.lbl_title.setStyleSheet("font-weight: 600; font-size: 13px; color: #38bdf8;")
        top_layout.addWidget(self.lbl_title)

        self.lbl_counter = QLabel("")
        self.lbl_counter.setStyleSheet("color: #94a3b8; font-size: 12px;")
        top_layout.addWidget(self.lbl_counter)

        top_layout.addStretch()

        # Selection Checkbox
        self.chk_selected = QCheckBox("Für Import ausgewählt [S]")
        self.chk_selected.setStyleSheet("font-weight: 600; font-size: 12px; color: #f8fafc;")
        self.chk_selected.toggled.connect(self._on_selection_toggled)
        top_layout.addWidget(self.chk_selected)

        # Zoom Mode Toggle Button (Fit vs 100%)
        self.btn_zoom = QPushButton("🔍 100% Zoom")
        self.btn_zoom.setObjectName("chipBtn")
        self.btn_zoom.setToolTip("Zwischen 'Einpassen' und '100% Originalgröße' umschalten (Taste F)")
        self.btn_zoom.clicked.connect(self._toggle_zoom)
        top_layout.addWidget(self.btn_zoom)

        # Fullscreen Dialog Button
        self.btn_fullscreen = QPushButton("⛶ Vollbild")
        self.btn_fullscreen.setObjectName("chipBtn")
        self.btn_fullscreen.setToolTip("In separater Vollbild-Vorschau öffnen (Leertaste)")
        self.btn_fullscreen.clicked.connect(self._on_fullscreen_clicked)
        top_layout.addWidget(self.btn_fullscreen)

        main_layout.addWidget(top_bar)

        # 2. Main Scrollable Image Viewport
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #0b1120;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
        """)

        self.img_container = QWidget()
        self.img_container_layout = QVBoxLayout(self.img_container)
        self.img_container_layout.setContentsMargins(4, 4, 4, 4)
        self.img_container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_image = QLabel()
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.lbl_image.setText("Keine Fotos geladen")
        self.lbl_image.setStyleSheet("color: #64748b; font-size: 15px;")
        self.img_container_layout.addWidget(self.lbl_image)

        self.scroll_area.setWidget(self.img_container)
        main_layout.addWidget(self.scroll_area, stretch=1)

        # 3. Bottom Metadata Info Bar
        bottom_bar = QFrame()
        bottom_bar.setObjectName("singleViewFooter")
        bottom_bar.setStyleSheet("""
            #singleViewFooter {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 4px 8px;
            }
        """)
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(6, 4, 6, 4)
        bottom_layout.setSpacing(10)

        self.lbl_meta_cam = QLabel("")
        self.lbl_meta_cam.setObjectName("tagChip")
        bottom_layout.addWidget(self.lbl_meta_cam)

        self.lbl_meta_exp = QLabel("")
        self.lbl_meta_exp.setObjectName("tagChip")
        bottom_layout.addWidget(self.lbl_meta_exp)

        self.lbl_meta_date = QLabel("")
        self.lbl_meta_date.setObjectName("tagChip")
        bottom_layout.addWidget(self.lbl_meta_date)

        self.lbl_meta_size = QLabel("")
        self.lbl_meta_size.setObjectName("tagChip")
        bottom_layout.addWidget(self.lbl_meta_size)

        self.lbl_meta_status = QLabel("")
        self.lbl_meta_status.setObjectName("tagChip")
        bottom_layout.addWidget(self.lbl_meta_status)

        bottom_layout.addStretch()

        lbl_hint = QLabel("Navigation: ◀ / ▶ oder A / D | Zoom: F oder Doppelklick | Vollbild: Leertaste")
        lbl_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        bottom_layout.addWidget(lbl_hint)

        main_layout.addWidget(bottom_bar)

    def set_items(self, items: List[ScanItem], current_item: Optional[ScanItem] = None):
        self.items = list(items) if items else []
        if not self.items:
            self.current_idx = -1
            self._current_pixmap = None
            self.lbl_title.setText("Keine Fotos vorhanden")
            self.lbl_counter.setText("")
            self.lbl_image.setPixmap(QPixmap())
            self.lbl_image.setText("Keine Fotos vorhanden")
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
            return

        if current_item and current_item in self.items:
            self.current_idx = self.items.index(current_item)
        elif self.current_idx < 0 or self.current_idx >= len(self.items):
            self.current_idx = 0

        self._render_current_item()

    def set_current_item(self, item: ScanItem):
        if not self.items or item not in self.items:
            return
        idx = self.items.index(item)
        if idx != self.current_idx:
            self.current_idx = idx
            self._render_current_item()

    def get_current_item(self) -> Optional[ScanItem]:
        if 0 <= self.current_idx < len(self.items):
            return self.items[self.current_idx]
        return None

    def _render_current_item(self):
        if not self.items or not (0 <= self.current_idx < len(self.items)):
            return

        item = self.items[self.current_idx]
        self.lbl_title.setText(item.source_path.name)
        self.lbl_counter.setText(f"({self.current_idx + 1} von {len(self.items)})")

        self.btn_prev.setEnabled(self.current_idx > 0)
        self.btn_next.setEnabled(self.current_idx < len(self.items) - 1)

        # Selection checkbox
        self.chk_selected.blockSignals(True)
        self.chk_selected.setChecked(item.selected)
        self.chk_selected.blockSignals(False)

        # Metadata labels
        cam = item.metadata.camera_name or item.metadata.camera_model or "Kamera: Unbekannt"
        self.lbl_meta_cam.setText(f"📷 {cam}")

        exp = item.metadata.formatted_exposure
        self.lbl_meta_exp.setText(f"⚙️ {exp}" if exp else "")
        self.lbl_meta_exp.setVisible(bool(exp))

        date_str = item.metadata.date_taken.strftime("%d.%m.%Y %H:%M:%S") if item.metadata.date_taken else "-"
        self.lbl_meta_date.setText(f"📅 {date_str}")

        size_str = format_size(item.total_size)
        dims = item.metadata.formatted_dimensions
        dim_part = f" • {dims}" if dims else ""
        self.lbl_meta_size.setText(f"💾 {size_str} ({item.display_type}){dim_part}")

        self.lbl_meta_status.setText(f"Status: {item.status}")

        # Load image preview
        target_path = item.companion_path if (item.is_pair and item.companion_path and item.companion_path.exists()) else item.source_path
        pil_img = load_preview_image(target_path, max_dim=2560)

        if pil_img:
            try:
                if pil_img.mode != "RGB":
                    pil_img = pil_img.convert("RGB")
                data = pil_img.tobytes("raw", "RGB")
                qimg = QImage(data, pil_img.width, pil_img.height, pil_img.width * 3, QImage.Format.Format_RGB888)
                self._current_pixmap = QPixmap.fromImage(qimg)
                self._update_display()
                self.item_focused.emit(item)
                return
            except Exception:
                pass

        self._current_pixmap = None
        self.lbl_image.setPixmap(QPixmap())
        self.lbl_image.setText("Keine Vorschau verfügbar")
        self.item_focused.emit(item)

    def _update_display(self):
        if not self._current_pixmap or self._current_pixmap.isNull():
            return

        if self._zoom_mode == "actual":
            # 1:1 original size
            self.lbl_image.setPixmap(self._current_pixmap)
            self.lbl_image.adjustSize()
            self.btn_zoom.setText("🔍 Einpassen")
        else:
            # Fit to scroll area viewport
            vp_size = self.scroll_area.viewport().size()
            target_w = max(100, vp_size.width() - 20)
            target_h = max(100, vp_size.height() - 20)
            scaled = self._current_pixmap.scaled(
                target_w, target_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_image.setPixmap(scaled)
            self.btn_zoom.setText("🔍 100% Zoom")

    def _toggle_zoom(self):
        self._zoom_mode = "actual" if self._zoom_mode == "fit" else "fit"
        self._update_display()

    def _prev_item(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self._render_current_item()

    def _next_item(self):
        if self.current_idx < len(self.items) - 1:
            self.current_idx += 1
            self._render_current_item()

    def _on_selection_toggled(self, checked: bool):
        if 0 <= self.current_idx < len(self.items):
            self.items[self.current_idx].selected = checked
            self.selection_toggled.emit()

    def _on_fullscreen_clicked(self):
        item = self.get_current_item()
        if item:
            self.open_quick_preview_requested.emit(item)

    def mouseDoubleClickEvent(self, event):
        self._toggle_zoom()
        super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        if self._zoom_mode == "fit":
            self._update_display()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_A):
            self._prev_item()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_D):
            self._next_item()
        elif key == Qt.Key.Key_S:
            self.chk_selected.setChecked(not self.chk_selected.isChecked())
        elif key == Qt.Key.Key_F:
            self._toggle_zoom()
        elif key == Qt.Key.Key_Space:
            self._on_fullscreen_clicked()
        else:
            super().keyPressEvent(event)

