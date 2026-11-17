"""Single photo / full-size image view widget integrated in the workspace."""

from collections import OrderedDict
from pathlib import Path
from typing import List, Optional
from PIL import Image

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QKeyEvent, QPainter, QPixmap, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget
)

from core.config import AppConfig
from core.drive_detector import format_size
from core.importer import ScanItem
from core.thumbnail import load_preview_image
from core.xmp_sync import read_xmp_workflow_info
from gui_qt.key_navigation import (
    DEFAULT_NAVIGATION_SCHEME, get_nav_hint, get_nav_labels, is_nav_next, is_nav_prev
)


class MediaSingleView(QWidget):
    selection_toggled = Signal()
    item_focused = Signal(object)
    open_quick_preview_requested = Signal(object)

    def __init__(self, config: Optional[AppConfig] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config = config
        self.items: List[ScanItem] = []
        self.current_idx: int = -1
        self._current_pixmap: Optional[QPixmap] = None
        self._zoom_mode: str = "fit"  # "fit" or "actual" (100%)
        self._preview_cache: OrderedDict[str, QPixmap] = OrderedDict()
        self._max_cache_size: int = 24

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

        # Storage location / folder path
        self.lbl_path = QLabel("")
        self.lbl_path.setObjectName("tagChip")
        self.lbl_path.setStyleSheet("color: #94a3b8; font-size: 11px; background-color: #1e293b; border: 1px solid #334155; border-radius: 4px; padding: 2px 6px;")
        top_layout.addWidget(self.lbl_path)

        # Sterne & Bewertungen
        self.lbl_ratings = QLabel("")
        self.lbl_ratings.setObjectName("tagChip")
        self.lbl_ratings.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: bold; background-color: #1e293b; border: 1px solid #334155; border-radius: 4px; padding: 2px 6px;")
        top_layout.addWidget(self.lbl_ratings)

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
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scroll_area.viewport().setFocusPolicy(Qt.FocusPolicy.NoFocus)
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

        self.lbl_hint = QLabel("Navigation: ◀ / ▶ oder A / D | Zoom: F oder Doppelklick | Vollbild: Leertaste")
        self.lbl_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        bottom_layout.addWidget(self.lbl_hint)

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

    def apply_config(self, config: Optional[AppConfig] = None):
        """Applies updated configuration options and refreshes visible fields and shortcuts."""
        if config:
            self.config = config
        cfg = self.config
        scheme = getattr(cfg, "navigation_scheme", DEFAULT_NAVIGATION_SCHEME) if cfg else DEFAULT_NAVIGATION_SCHEME
        prev_lbl, next_lbl = get_nav_labels(scheme)
        hint = get_nav_hint(scheme)
        self.btn_prev.setText(prev_lbl)
        self.btn_next.setText(next_lbl)
        self.btn_prev.setToolTip(f"Vorheriges Foto ({hint})")
        self.btn_next.setToolTip(f"Nächstes Foto ({hint})")
        if hasattr(self, "lbl_hint"):
            self.lbl_hint.setText(f"Navigation: {hint} | Zoom: F oder Doppelklick | Vollbild: Leertaste")
        self._render_current_item()

    def get_current_item(self) -> Optional[ScanItem]:
        if 0 <= self.current_idx < len(self.items):
            return self.items[self.current_idx]
        return None

    def _render_current_item(self):
        if not self.items or not (0 <= self.current_idx < len(self.items)):
            return

        item = self.items[self.current_idx]

        # Read display preferences from AppConfig
        cfg = self.config
        show_name = cfg.single_view_show_filename if cfg else True
        show_ext = cfg.single_view_show_extension if cfg else True
        show_ratings = cfg.single_view_show_ratings if cfg else True
        show_path = cfg.single_view_show_path if cfg else True
        show_cam = cfg.single_view_show_camera_lens if cfg else True
        show_exp = cfg.single_view_show_exposure if cfg else True
        show_date = cfg.single_view_show_date if cfg else True
        show_size = cfg.single_view_show_filesize if cfg else True

        # Name and Extension
        if show_name and show_ext:
            name_text = item.source_path.name
        elif show_name:
            name_text = item.source_path.stem
        elif show_ext:
            name_text = item.source_path.suffix.upper()
        else:
            name_text = ""

        self.lbl_title.setText(name_text)
        self.lbl_title.setVisible(bool(name_text))
        self.lbl_counter.setText(f"({self.current_idx + 1} von {len(self.items)})")

        self.btn_prev.setEnabled(self.current_idx > 0)
        self.btn_next.setEnabled(self.current_idx < len(self.items) - 1)

        # Storage location
        parent_dir = str(item.source_path.parent)
        self.lbl_path.setText(f"📁 {parent_dir}")
        self.lbl_path.setToolTip(f"Speicherort:\n{item.source_path}")
        self.lbl_path.setVisible(show_path)

        # Ratings & Evaluations
        wf = read_xmp_workflow_info(item.source_path)
        r_parts = []
        if wf.rating > 0:
            r_parts.append("★" * wf.rating)
        if wf.is_rejected:
            r_parts.append("[X]")
        if wf.workflow_status and wf.workflow_status != "UNCHECKED":
            r_parts.append(wf.workflow_status)
        if wf.label:
            r_parts.append(wf.label)

        if r_parts:
            self.lbl_ratings.setText(' '.join(r_parts))
            self.lbl_ratings.setStyleSheet("color: #fef08a; background-color: #854d0e; border: 1px solid #ca8a04; border-radius: 4px; padding: 2px 6px; font-size: 11px; font-weight: bold;")
        else:
            self.lbl_ratings.setText("0★")
            self.lbl_ratings.setStyleSheet("color: #94a3b8; background-color: #1e293b; border: 1px solid #334155; border-radius: 4px; padding: 2px 6px; font-size: 11px;")
        self.lbl_ratings.setVisible(show_ratings)

        # Selection checkbox
        self.chk_selected.blockSignals(True)
        self.chk_selected.setChecked(item.selected)
        self.chk_selected.blockSignals(False)

        # Metadata labels
        cam = item.metadata.camera_name or item.metadata.camera_model or "Kamera: Unbekannt"
        self.lbl_meta_cam.setText(f"📷 {cam}")
        self.lbl_meta_cam.setVisible(show_cam and bool(cam))

        exp = item.metadata.formatted_exposure
        self.lbl_meta_exp.setText(exp if exp else "")
        self.lbl_meta_exp.setVisible(show_exp and bool(exp))

        date_str = item.metadata.date_taken.strftime("%d.%m.%Y %H:%M:%S") if item.metadata.date_taken else "-"
        self.lbl_meta_date.setText(f"📅 {date_str}")
        self.lbl_meta_date.setVisible(show_date and bool(date_str))

        size_str = format_size(item.total_size)
        dims = item.metadata.formatted_dimensions
        dim_part = f" • {dims}" if dims else ""
        self.lbl_meta_size.setText(f"💾 {size_str} ({item.display_type}){dim_part}")
        self.lbl_meta_size.setVisible(show_size)

        self.lbl_meta_status.setText(f"Status: {item.status}")

        # Load image preview (from memory cache or disk)
        target_path = item.companion_path if (item.is_pair and item.companion_path and item.companion_path.exists()) else item.source_path
        target_key = str(target_path)

        if target_key in self._preview_cache:
            self._current_pixmap = self._preview_cache[target_key]
            self._preview_cache.move_to_end(target_key)
            self._update_display()
            self.item_focused.emit(item)
            return

        pil_img = load_preview_image(target_path, max_dim=3840)
        if pil_img:
            try:
                if pil_img.mode != "RGB":
                    pil_img = pil_img.convert("RGB")
                data = pil_img.tobytes("raw", "RGB")
                qimg = QImage(data, pil_img.width, pil_img.height, pil_img.width * 3, QImage.Format.Format_RGB888)
                self._current_pixmap = QPixmap.fromImage(qimg)
                self._preview_cache[target_key] = self._current_pixmap
                self._preview_cache.move_to_end(target_key)
                while len(self._preview_cache) > self._max_cache_size:
                    self._preview_cache.popitem(last=False)

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
            # Fit to scroll area viewport with High-DPI support
            vp_size = self.scroll_area.viewport().size()
            dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
            target_w = max(100, int((vp_size.width() - 20) * dpr))
            target_h = max(100, int((vp_size.height() - 20) * dpr))
            scaled = self._current_pixmap.scaled(
                target_w, target_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            scaled.setDevicePixelRatio(dpr)
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
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.get_current_item()
            if item:
                self.open_quick_preview_requested.emit(item)
                return
        super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        if self._zoom_mode == "fit":
            self._update_display()

    def wheelEvent(self, event: QWheelEvent):
        if self.config and getattr(self.config, "navigation_enable_mouse_wheel", False) and self._zoom_mode == "fit":
            delta = event.angleDelta().y()
            if delta > 0:
                self._prev_item()
                event.accept()
                return
            elif delta < 0:
                self._next_item()
                event.accept()
                return
        super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        scheme = getattr(self.config, "navigation_scheme", DEFAULT_NAVIGATION_SCHEME) if self.config else DEFAULT_NAVIGATION_SCHEME
        if is_nav_prev(key, scheme):
            self._prev_item()
        elif is_nav_next(key, scheme):
            self._next_item()
        elif key == Qt.Key.Key_S:
            self.chk_selected.setChecked(not self.chk_selected.isChecked())
        elif key == Qt.Key.Key_F:
            self._toggle_zoom()
        elif key == Qt.Key.Key_Space:
            self._on_fullscreen_clicked()
        else:
            super().keyPressEvent(event)

