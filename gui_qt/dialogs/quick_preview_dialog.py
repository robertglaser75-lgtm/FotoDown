"""Quick Look / Fullscreen Preview Dialog with keyboard navigation and EXIF inspector."""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image, ImageOps

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor, QFont, QIcon, QImage, QImageReader, QKeyEvent,
    QMouseEvent, QPixmap, QResizeEvent, QTransform, QWheelEvent
)
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget
)

from core.drive_detector import format_size
from core.config import AppConfig
from core.importer import ScanItem
from core.thumbnail import extract_raw_embedded_jpeg, load_preview_image
from core.xmp_sync import read_xmp_workflow_info, sync_pair_xmp
from gui_qt.key_navigation import DEFAULT_NAVIGATION_SCHEME, is_nav_next, is_nav_prev
from gui_qt.styles.icons import (
    get_clear_icon, get_folder_open_icon, get_minus_icon,
    get_plus_icon, get_refresh_icon, get_zoom_fit_icon, get_zoom_icon
)
from gui_qt.widgets.elided_label import ElidedLabel


class QuickPreviewDialog(QDialog):
    selection_changed = Signal()
    rating_changed = Signal()

    def __init__(self, items: List[Any], start_index: int = 0, parent=None, config: Optional[AppConfig] = None, fullscreen: bool = False):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.config = config
        self.items = items
        self.current_idx = max(0, min(start_index, len(items) - 1)) if items else 0
        self._current_pixmap: Optional[QPixmap] = None
        self._was_maximized_before_fullscreen: bool = False
        self._zoom_mode: str = "fit"  # "fit" or "manual"
        self._zoom_factor: float = 1.0
        self._rotation_deg: int = 0
        self._pan_active: bool = False
        self._pan_last_pos: Optional[QPoint] = None

        self.setWindowTitle("Vitrina - Integrierter Bildbetrachter")
        self.resize(1200, 800)
        self.setMinimumSize(640, 480)

        self._setup_ui()
        self._load_current_item()

        if fullscreen:
            self.showFullScreen()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # 1. Top Header Bar (Title, Index, Viewer Controls & Close)
        header = QHBoxLayout()
        header.setSpacing(6)

        self.lbl_filename = ElidedLabel("")
        self.lbl_filename.setMaximumWidth(340)
        self.lbl_filename.setStyleSheet("font-size: 14px; font-weight: bold; color: #38bdf8;")
        header.addWidget(self.lbl_filename)

        self.lbl_counter = QLabel("")
        self.lbl_counter.setStyleSheet("color: #94a3b8; font-size: 12px;")
        header.addWidget(self.lbl_counter)

        header.addStretch()

        # Built-in Viewer Zoom & Rotation Controls
        self.btn_zoom_out = QPushButton()
        self.btn_zoom_out.setObjectName("compactToolBtn")
        self.btn_zoom_out.setIcon(get_minus_icon(size=13))
        self.btn_zoom_out.setFixedSize(26, 26)
        self.btn_zoom_out.setToolTip("Verkleinern (-)")
        self.btn_zoom_out.clicked.connect(self._zoom_out)
        header.addWidget(self.btn_zoom_out)

        self.lbl_zoom = QLabel("Einpassen")
        self.lbl_zoom.setStyleSheet("color: #cbd5e1; font-size: 11px; min-width: 58px;")
        self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.lbl_zoom)

        self.btn_zoom_in = QPushButton()
        self.btn_zoom_in.setObjectName("compactToolBtn")
        self.btn_zoom_in.setIcon(get_plus_icon(size=13))
        self.btn_zoom_in.setFixedSize(26, 26)
        self.btn_zoom_in.setToolTip("Vergrößern (+)")
        self.btn_zoom_in.clicked.connect(self._zoom_in)
        header.addWidget(self.btn_zoom_in)

        self.btn_zoom_100 = QPushButton("1:1")
        self.btn_zoom_100.setObjectName("secondaryBtn")
        self.btn_zoom_100.setIcon(get_zoom_icon(size=12))
        self.btn_zoom_100.setIconSize(QSize(12, 12))
        self.btn_zoom_100.setToolTip("Originalgröße 100% (1)")
        self.btn_zoom_100.clicked.connect(self._zoom_actual)
        header.addWidget(self.btn_zoom_100)

        self.btn_zoom_fit = QPushButton("Einpassen")
        self.btn_zoom_fit.setObjectName("secondaryBtn")
        self.btn_zoom_fit.setIcon(get_zoom_fit_icon(size=12))
        self.btn_zoom_fit.setIconSize(QSize(12, 12))
        self.btn_zoom_fit.setToolTip("An Fenstergröße anpassen (0)")
        self.btn_zoom_fit.clicked.connect(self._zoom_fit)
        header.addWidget(self.btn_zoom_fit)

        self.btn_rotate_left = QPushButton("↺")
        self.btn_rotate_left.setObjectName("compactToolBtn")
        self.btn_rotate_left.setFixedSize(26, 26)
        self.btn_rotate_left.setToolTip("90° nach links drehen (L)")
        self.btn_rotate_left.clicked.connect(lambda: self._rotate_by(-90))
        header.addWidget(self.btn_rotate_left)

        self.btn_rotate_right = QPushButton("↻")
        self.btn_rotate_right.setObjectName("compactToolBtn")
        self.btn_rotate_right.setFixedSize(26, 26)
        self.btn_rotate_right.setToolTip("90° nach rechts drehen (R)")
        self.btn_rotate_right.clicked.connect(lambda: self._rotate_by(90))
        header.addWidget(self.btn_rotate_right)

        self.btn_prev = QPushButton("\u25C0 Vorheriges")
        self.btn_prev.setObjectName("secondaryBtn")
        self.btn_prev.clicked.connect(self._prev_item)
        header.addWidget(self.btn_prev)

        self.btn_next = QPushButton("Nächstes \u25B6")
        self.btn_next.setObjectName("secondaryBtn")
        self.btn_next.clicked.connect(self._next_item)
        header.addWidget(self.btn_next)

        self.btn_open_orig = QPushButton("Extern")
        self.btn_open_orig.setIcon(get_folder_open_icon())
        self.btn_open_orig.setIconSize(QSize(14, 14))
        self.btn_open_orig.setObjectName("secondaryBtn")
        self.btn_open_orig.setToolTip("Öffnet die Originaldatei im Standardprogramm des Betriebssystems")
        self.btn_open_orig.clicked.connect(self._open_current_original)
        header.addWidget(self.btn_open_orig)

        btn_close = QPushButton("Schließen")
        btn_close.setIcon(get_clear_icon())
        btn_close.setIconSize(QSize(13, 13))
        btn_close.setObjectName("secondaryBtn")
        btn_close.clicked.connect(self.accept)
        header.addWidget(btn_close)

        layout.addLayout(header)

        # 2. Main Image Preview Area (ScrollArea for smooth zooming & panning)
        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("photoCanvasArea")
        pf_layout = QVBoxLayout(self.preview_frame)
        pf_layout.setContentsMargins(4, 4, 4, 4)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("background: transparent;")

        self.lbl_image = QLabel()
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.lbl_image.mouseDoubleClickEvent = self._on_image_double_clicked
        self.lbl_image.mousePressEvent = self._on_image_mouse_press
        self.lbl_image.mouseMoveEvent = self._on_image_mouse_move
        self.lbl_image.mouseReleaseEvent = self._on_image_mouse_release
        self.scroll_area.setWidget(self.lbl_image)
        pf_layout.addWidget(self.scroll_area)

        # Floating Left-Bottom Image Metadata Overlay
        self.info_overlay = QFrame(self.preview_frame)
        self.info_overlay.setObjectName("viewerInfoOverlay")
        self.info_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.info_overlay.setStyleSheet(
            "QFrame#viewerInfoOverlay { background-color: rgba(15, 23, 42, 0.80); "
            "border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 6px; }"
        )
        overlay_layout = QVBoxLayout(self.info_overlay)
        overlay_layout.setContentsMargins(10, 6, 10, 6)
        overlay_layout.setSpacing(2)
        self.lbl_overlay_info = QLabel("")
        self.lbl_overlay_info.setStyleSheet("color: #e2e8f0; font-size: 11px; background: transparent;")
        self.lbl_overlay_info.setTextFormat(Qt.TextFormat.RichText)
        overlay_layout.addWidget(self.lbl_overlay_info)
        self.info_overlay.hide()

        layout.addWidget(self.preview_frame, stretch=1)

        # 3. Bottom Inspector & Selection Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(10)

        self.chk_selected = QCheckBox("Ausgewählt [S]")
        self.chk_selected.setStyleSheet("font-weight: 600; font-size: 13px;")
        self.chk_selected.toggled.connect(self._on_selection_toggled)
        bottom_bar.addWidget(self.chk_selected)

        # Interactive Star Rating Bar
        rating_row = QHBoxLayout()
        rating_row.setSpacing(2)
        lbl_rate = QLabel("Bewertung:")
        lbl_rate.setStyleSheet("color: #94a3b8; font-size: 11px; margin-right: 2px;")
        rating_row.addWidget(lbl_rate)
        self.star_buttons: List[QPushButton] = []
        for idx in range(1, 6):
            btn = QPushButton("☆")
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(f"{idx} Stern{'e' if idx > 1 else ''} vergeben (nochmal klicken zum Entfernen, Strg+{idx})")
            btn.clicked.connect(lambda _=False, s=idx: self._on_star_clicked(s))
            rating_row.addWidget(btn)
            self.star_buttons.append(btn)
        bottom_bar.addLayout(rating_row)

        # EXIF Metadata Chips (kept compact for status bar)
        self.lbl_camera = QLabel("")
        self.lbl_camera.setObjectName("tagChip")
        self.lbl_camera.hide()
        bottom_bar.addWidget(self.lbl_camera)

        self.lbl_date = QLabel("")
        self.lbl_date.setObjectName("tagChip")
        self.lbl_date.hide()
        bottom_bar.addWidget(self.lbl_date)

        self.lbl_size = QLabel("")
        self.lbl_size.setObjectName("tagChip")
        self.lbl_size.hide()
        bottom_bar.addWidget(self.lbl_size)

        self.lbl_status = QLabel("")
        self.lbl_status.setObjectName("tagChip")
        self.lbl_status.hide()
        bottom_bar.addWidget(self.lbl_status)

        bottom_bar.addStretch()

        lbl_hint = QLabel("Mausrad: Zoom | + / - / 0 / 1 | L / R: Drehen | Strg+0..5: Sterne | \u25C0 / \u25B6 | F11: Vollbild | Esc: Schließen")
        lbl_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        bottom_bar.addWidget(lbl_hint)

        layout.addLayout(bottom_bar)

    def _on_image_double_clicked(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_fullscreen()

    def _extract_item_info(self, item: Any) -> Dict[str, Any]:
        """Extracts display properties uniformly from ScanItem, CullingItem, TransferItem, or Path."""
        display_name = ""
        target_path: Optional[Path] = None
        primary_path: Optional[Path] = None
        companion_path: Optional[Path] = None
        is_selected = False
        camera = ""
        lens = ""
        exposure = ""
        date_str = "-"
        size_bytes = 0
        display_type = ""
        status_text = ""
        rating = 0
        is_rejected = False
        color_label = ""
        workflow_status = ""
        dimensions = ""

        def _extract_meta(meta):
            nonlocal camera, lens, exposure, date_str, dimensions
            if not meta:
                return
            camera = getattr(meta, "camera_name", None) or getattr(meta, "camera_model", "") or ""
            lens = getattr(meta, "lens_model", "") or ""
            if getattr(meta, "formatted_exposure", None):
                exposure = meta.formatted_exposure
            else:
                parts = []
                if getattr(meta, "focal_length", None):
                    parts.append(str(meta.focal_length))
                if getattr(meta, "aperture", None):
                    parts.append(str(meta.aperture))
                if getattr(meta, "shutter_speed", None):
                    parts.append(str(meta.shutter_speed))
                if getattr(meta, "iso", None):
                    parts.append(f"ISO {meta.iso}")
                exposure = " • ".join(parts)
            if getattr(meta, "date_taken", None):
                date_str = meta.date_taken.strftime("%d.%m.%Y %H:%M:%S")
            w = getattr(meta, "width", 0) or 0
            h = getattr(meta, "height", 0) or 0
            if w > 0 and h > 0:
                mp = (w * h) / 1_000_000.0
                dimensions = f"{w}×{h} ({mp:.1f} MP)"

        # ScanItem (Tab 1)
        if hasattr(item, "source_path"):
            display_name = item.source_path.name
            primary_path = item.source_path
            companion_path = getattr(item, "companion_path", None)
            target_path = (
                companion_path
                if (getattr(item, "is_pair", False) and companion_path and companion_path.exists())
                else item.source_path
            )
            is_selected = getattr(item, "selected", False)
            _extract_meta(getattr(item, "metadata", None))
            size_bytes = getattr(item, "total_size", 0)
            display_type = getattr(item, "display_type", item.source_path.suffix.upper())
            status_text = getattr(item, "status", "")
            rating = int(getattr(item, "rating", 0) or 0)

        # CullingItem (Tab 2)
        elif hasattr(item, "primary_path"):
            display_name = item.primary_path.name
            primary_path = item.primary_path
            companion_path = getattr(item, "companion_path", None)
            target_path = getattr(item, "current_display_path", None) or (
                companion_path
                if (companion_path and companion_path.exists())
                else item.primary_path
            )
            is_selected = getattr(item, "selected", False)
            _extract_meta(getattr(item, "metadata", None))
            try:
                size_bytes = item.primary_path.stat().st_size if item.primary_path.exists() else 0
            except OSError:
                size_bytes = 0
            display_type = getattr(item, "active_view_mode", item.primary_path.suffix.upper())
            if hasattr(item, "workflow_status_info"):
                status_text = item.workflow_status_info[0]
            elif hasattr(item, "workflow_status"):
                status_text = item.workflow_status
            rating = int(getattr(item, "rating", 0) or 0)
            is_rejected = bool(getattr(item, "is_rejected", False))
            color_label = getattr(item, "color_label", "") or ""
            workflow_status = getattr(item, "workflow_status", "") or ""

        # TransferItem (Tab 3)
        elif hasattr(item, "path") and hasattr(item, "is_raw"):
            display_name = item.name
            primary_path = item.path
            target_path = item.path
            is_selected = getattr(item, "selected", False)
            if getattr(item, "mtime", 0) > 0:
                try:
                    date_str = datetime.fromtimestamp(item.mtime).strftime("%d.%m.%Y %H:%M:%S")
                except Exception:
                    date_str = "-"
            size_bytes = getattr(item, "size", 0)
            display_type = item.extension.upper()
            status_text = item.workflow_status or ("Mit XMP" if item.has_xmp else "")
            rating = int(getattr(item, "rating", 0) or 0)
            workflow_status = getattr(item, "workflow_status", "") or ""

        # Path or str
        elif isinstance(item, (Path, str)):
            p = Path(item)
            display_name = p.name
            primary_path = p
            target_path = p
            display_type = p.suffix.upper()
            try:
                st = p.stat()
                size_bytes = st.st_size
                date_str = datetime.fromtimestamp(st.st_mtime).strftime("%d.%m.%Y %H:%M:%S")
            except OSError:
                size_bytes = 0
            try:
                xmp_info = read_xmp_workflow_info(p)
                rating = int(getattr(xmp_info, "rating", 0) or 0)
            except Exception:
                rating = 0

        return {
            "name": display_name,
            "stem": Path(display_name).stem if display_name else "",
            "ext": Path(display_name).suffix.upper().lstrip(".") if display_name else "",
            "target_path": target_path,
            "primary_path": primary_path,
            "companion_path": companion_path,
            "parent_dir": str(primary_path.parent) if primary_path else "",
            "selected": is_selected,
            "camera": camera,
            "lens": lens,
            "exposure": exposure,
            "date": date_str,
            "size": size_bytes,
            "dimensions": dimensions,
            "type": display_type,
            "status": status_text,
            "rating": rating,
            "is_rejected": is_rejected,
            "color_label": color_label,
            "workflow_status": workflow_status,
        }

    def _load_current_item(self):
        if not self.items or self.current_idx < 0 or self.current_idx >= len(self.items):
            return

        item = self.items[self.current_idx]
        info = self._extract_item_info(item)

        self.lbl_filename.setText(info["name"])
        self.lbl_counter.setText(f"({self.current_idx + 1} von {len(self.items)})")

        self.btn_prev.setEnabled(self.current_idx > 0)
        self.btn_next.setEnabled(self.current_idx < len(self.items) - 1)

        # Update Selection checkbox without emitting loop
        self.chk_selected.blockSignals(True)
        self.chk_selected.setChecked(info["selected"])
        self.chk_selected.blockSignals(False)

        self._update_star_buttons(info["rating"])

        # Metadata chips (kept updated for compatibility)
        cam = info["camera"] or "Kamera: Unbekannt"
        self.lbl_camera.setText(f"\U0001F4F7 {cam}")
        self.lbl_date.setText(f"\U0001F4C5 {info['date']}")
        size_str = format_size(info["size"])
        self.lbl_size.setText(f"\U0001F4BE {size_str} ({info['type']})")
        self.lbl_status.setText(f"Status: {info['status']}")

        # Load Preview Image (may also fill pixel dimensions from pixmap)
        self._load_image_preview(info["target_path"])
        self._update_info_overlay()

    def _resolve_initial_zoom(self):
        """Sets initial zoom mode and factor from config.viewer_initial_zoom."""
        mode_val = str(getattr(self.config, "viewer_initial_zoom", "fit") or "fit").strip().lower()
        if mode_val == "fit":
            self._zoom_mode = "fit"
            self._zoom_factor = 1.0
        else:
            try:
                pct = float(mode_val)
                self._zoom_mode = "manual"
                self._zoom_factor = max(0.1, min(5.0, pct / 100.0))
            except ValueError:
                self._zoom_mode = "fit"
                self._zoom_factor = 1.0

    def _load_image_preview(self, target_path: Optional[Path]):
        self._resolve_initial_zoom()
        self._rotation_deg = 0
        if not target_path or not target_path.exists():
            self._current_pixmap = None
            self.lbl_image.setPixmap(QPixmap())
            self.lbl_image.setText("\U0001F5BC Keine Vorschau verfügbar")
            self.lbl_image.setStyleSheet("color: #64748b; font-size: 16px;")
            self._update_zoom_controls()
            return

        # 1. Try high-resolution preview extractor (embedded JPEG in RAW or fast scaling up to 4K)
        pil_img = load_preview_image(target_path, max_dim=3840)

        # 2. Fallback: try opening full native image directly with PIL (relaxing DecompressionBomb limit)
        if pil_img is None:
            prev_max_px = Image.MAX_IMAGE_PIXELS
            try:
                Image.MAX_IMAGE_PIXELS = None
                with Image.open(target_path) as full_img:
                    pil_img = ImageOps.exif_transpose(full_img).copy()
            except Exception:
                pil_img = None
            finally:
                Image.MAX_IMAGE_PIXELS = prev_max_px

        pixmap: Optional[QPixmap] = None
        if pil_img:
            try:
                if pil_img.mode != "RGB":
                    pil_img = pil_img.convert("RGB")
                data = pil_img.tobytes("raw", "RGB")
                qimg = QImage(data, pil_img.width, pil_img.height, pil_img.width * 3, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg)
            except Exception:
                pixmap = None

        # 3. Fallback: Qt native QImageReader (SVG, ICO, TGA, WebP, BMP, GIF, PDF, TIFF variants, etc.)
        if (pixmap is None or pixmap.isNull()):
            try:
                reader = QImageReader(str(target_path))
                reader.setAutoTransform(True)
                qimg = reader.read()
                if not qimg.isNull():
                    pixmap = QPixmap.fromImage(qimg)
            except Exception:
                pixmap = None

        if pixmap and not pixmap.isNull():
            self._current_pixmap = pixmap
            self._scale_preview()
            return

        # 4. If file cannot be decoded as an image (e.g. video or unsupported format): open in system viewer
        self._current_pixmap = None
        self._update_zoom_controls()
        self._open_original_external(target_path)

    def _open_original_external(self, target_path: Path):
        """Automatically opens the original file with the system default viewer."""
        if not (os.environ.get("VITRINA_HEADLESS_TEST") or os.environ.get("FOTODOWN_HEADLESS_TEST")):
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            try:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(target_path.resolve())))
            except Exception:
                pass

        self.scroll_area.setWidgetResizable(True)
        self.lbl_image.setPixmap(QPixmap())
        self.lbl_image.setText(
            f"<div style='text-align: center; padding: 24px;'>"
            f"<div style='font-size: 42px; margin-bottom: 12px;'>📂</div>"
            f"<div style='color: #38bdf8; font-size: 16px; font-weight: bold;'>Originaldatei im Standardprogramm geöffnet</div>"
            f"<div style='color: #e2e8f0; font-size: 13px; margin-top: 6px;'>{target_path.name}</div>"
            f"<div style='color: #94a3b8; font-size: 11px; margin-top: 10px;'>"
            f"Keine interne Vorschau verfügbar. Das Original wurde extern geöffnet.</div>"
            f"</div>"
        )
        self.lbl_image.setStyleSheet("background: transparent;")

    def _open_current_original(self):
        """Opens the original file of the currently displayed item."""
        if not self.items or not (0 <= self.current_idx < len(self.items)):
            return
        info = self._extract_item_info(self.items[self.current_idx])
        p = info.get("target_path")
        if p and p.exists() and not (os.environ.get("VITRINA_HEADLESS_TEST") or os.environ.get("FOTODOWN_HEADLESS_TEST")):
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.resolve())))

    def _get_rotated_pixmap(self) -> Optional[QPixmap]:
        if not self._current_pixmap or self._current_pixmap.isNull():
            return None
        if self._rotation_deg % 360 == 0:
            return self._current_pixmap
        return self._current_pixmap.transformed(QTransform().rotate(self._rotation_deg), Qt.TransformationMode.SmoothTransformation)

    def _update_zoom_controls(self):
        has_img = bool(self._current_pixmap and not self._current_pixmap.isNull())
        for btn in (self.btn_zoom_out, self.btn_zoom_in, self.btn_zoom_100, self.btn_zoom_fit, self.btn_rotate_left, self.btn_rotate_right):
            btn.setEnabled(has_img)
        if not has_img:
            self.lbl_zoom.setText("—")
        elif self._zoom_mode == "fit":
            self.lbl_zoom.setText("Einpassen")
        else:
            self.lbl_zoom.setText(f"{int(round(self._zoom_factor * 100))}%")

    def _zoom_in(self):
        if not self._current_pixmap or self._current_pixmap.isNull():
            return
        if self._zoom_mode == "fit":
            self._zoom_factor = self._estimate_fit_scale()
            self._zoom_mode = "manual"
        self._zoom_factor = min(5.0, self._zoom_factor * 1.25)
        self._scale_preview()

    def _zoom_out(self):
        if not self._current_pixmap or self._current_pixmap.isNull():
            return
        if self._zoom_mode == "fit":
            self._zoom_factor = self._estimate_fit_scale()
            self._zoom_mode = "manual"
        self._zoom_factor = max(0.1, self._zoom_factor / 1.25)
        self._scale_preview()

    def _zoom_actual(self):
        if not self._current_pixmap or self._current_pixmap.isNull():
            return
        self._zoom_mode = "manual"
        self._zoom_factor = 1.0
        self._scale_preview()

    def _zoom_fit(self):
        self._zoom_mode = "fit"
        self._scale_preview()

    def _rotate_by(self, delta_deg: int):
        if not self._current_pixmap or self._current_pixmap.isNull():
            return
        self._rotation_deg = (self._rotation_deg + delta_deg) % 360
        self._scale_preview()

    def _estimate_fit_scale(self) -> float:
        src = self._get_rotated_pixmap()
        if not src or src.isNull():
            return 1.0
        vp = self.scroll_area.viewport().size()
        if vp.width() <= 0 or vp.height() <= 0:
            return 1.0
        return min(vp.width() / max(1, src.width()), vp.height() / max(1, src.height()))

    def _scale_preview(self):
        src = self._get_rotated_pixmap()
        if not src or src.isNull():
            self._update_zoom_controls()
            return
        dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
        if self._zoom_mode == "fit":
            self.scroll_area.setWidgetResizable(True)
            avail_size = self.scroll_area.viewport().size()
            target_w = max(10, int((avail_size.width() - 8) * dpr))
            target_h = max(10, int((avail_size.height() - 8) * dpr))
            scaled = src.scaled(
                target_w,
                target_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            scaled.setDevicePixelRatio(dpr)
            self.lbl_image.setPixmap(scaled)
            self.lbl_image.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.scroll_area.setWidgetResizable(False)
            disp_w = max(1, int(round(src.width() * self._zoom_factor)))
            disp_h = max(1, int(round(src.height() * self._zoom_factor)))
            scaled = src.scaled(
                int(disp_w * dpr),
                int(disp_h * dpr),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            scaled.setDevicePixelRatio(dpr)
            self.lbl_image.setPixmap(scaled)
            self.lbl_image.resize(disp_w, disp_h)
            self.lbl_image.setCursor(Qt.CursorShape.OpenHandCursor)
        self._update_zoom_controls()

    def wheelEvent(self, event: QWheelEvent):
        if self._current_pixmap and not self._current_pixmap.isNull():
            delta = event.angleDelta().y()
            if delta > 0:
                self._zoom_in()
                event.accept()
                return
            elif delta < 0:
                self._zoom_out()
                event.accept()
                return
        super().wheelEvent(event)

    def _on_image_mouse_press(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._zoom_mode == "manual":
            self._pan_active = True
            self._pan_last_pos = event.globalPosition().toPoint()
            self.lbl_image.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()

    def _on_image_mouse_move(self, event: QMouseEvent):
        if self._pan_active and self._pan_last_pos is not None:
            curr = event.globalPosition().toPoint()
            delta = curr - self._pan_last_pos
            self._pan_last_pos = curr
            hbar = self.scroll_area.horizontalScrollBar()
            vbar = self.scroll_area.verticalScrollBar()
            hbar.setValue(hbar.value() - delta.x())
            vbar.setValue(vbar.value() - delta.y())
            event.accept()

    def _on_image_mouse_release(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._pan_active:
            self._pan_active = False
            self._pan_last_pos = None
            if self._zoom_mode == "manual":
                self.lbl_image.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()

    def _update_star_buttons(self, rating: int):
        """Updates the 5-star rating buttons to reflect the active rating (0..5)."""
        for idx, btn in enumerate(self.star_buttons, start=1):
            filled = idx <= rating
            btn.setText("★" if filled else "☆")
            color = "#fbbf24" if filled else "#64748b"
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: none; color: {color}; "
                f"font-size: 16px; padding: 0px; }}"
                f"QPushButton:hover {{ color: #fde047; }}"
            )

    def _on_star_clicked(self, stars: int):
        """Sets or toggles the star rating on the current item and persists to XMP."""
        if not self.items or not (0 <= self.current_idx < len(self.items)):
            return
        it = self.items[self.current_idx]
        curr = int(getattr(it, "rating", 0) or 0)
        new_rating = 0 if curr == stars else stars

        if hasattr(it, "rating"):
            it.rating = new_rating
        if hasattr(it, "is_rejected") and new_rating > 0:
            it.is_rejected = False

        info = self._extract_item_info(it)
        p_path = info.get("primary_path")
        c_path = info.get("companion_path")
        if p_path and p_path.exists():
            try:
                sync_pair_xmp(
                    p_path,
                    c_path,
                    rating=new_rating,
                    label=info.get("color_label", ""),
                    is_rejected=bool(getattr(it, "is_rejected", False)),
                    workflow_status=info.get("workflow_status", ""),
                )
            except Exception:
                pass

        self._update_star_buttons(new_rating)
        self._update_info_overlay()
        self.rating_changed.emit()

    def _update_info_overlay(self):
        """Populates the left-bottom metadata overlay according to AppConfig single_view_show_* flags."""
        if not self.items or not (0 <= self.current_idx < len(self.items)):
            self.info_overlay.hide()
            return

        info = self._extract_item_info(self.items[self.current_idx])
        c = self.config
        show_fn = getattr(c, "single_view_show_filename", True)
        show_ext = getattr(c, "single_view_show_extension", True)
        show_ratings = getattr(c, "single_view_show_ratings", True)
        show_path = getattr(c, "single_view_show_path", True)
        show_cam = getattr(c, "single_view_show_camera_lens", True)
        show_exp = getattr(c, "single_view_show_exposure", True)
        show_date = getattr(c, "single_view_show_date", True)
        show_size = getattr(c, "single_view_show_filesize", True)

        lines: List[str] = []

        # Line 1: Filename + Extension + Rating/Status
        top_parts: List[str] = []
        if show_fn:
            name_txt = info["name"] if show_ext else info["stem"]
            if name_txt:
                top_parts.append(f"<b style='color:#38bdf8;'>{name_txt}</b>")
        elif show_ext and info["ext"]:
            top_parts.append(f"<b style='color:#38bdf8;'>.{info['ext']}</b>")

        if show_ratings:
            rating = info["rating"]
            stars_txt = ("★" * rating) + ("☆" * (5 - rating))
            top_parts.append(f"<span style='color:#fbbf24;'>{stars_txt}</span>")
            if info["status"]:
                top_parts.append(f"<span style='color:#94a3b8;'>[{info['status']}]</span>")
        if top_parts:
            lines.append(" &nbsp; ".join(top_parts))

        # Line 2: Camera & Lens + Exposure
        cam_parts: List[str] = []
        if show_cam:
            cam_txt = " • ".join(p for p in (info["camera"], info["lens"]) if p)
            if cam_txt:
                cam_parts.append(f"\U0001F4F7 {cam_txt}")
        if show_exp and info["exposure"]:
            cam_parts.append(info["exposure"])
        if cam_parts:
            lines.append(" &nbsp;|&nbsp; ".join(cam_parts))

        # Line 3: Date + File Size / Dimensions
        meta_parts: List[str] = []
        if show_date and info["date"] and info["date"] != "-":
            meta_parts.append(f"\U0001F4C5 {info['date']}")
        if show_size:
            size_txt = format_size(info["size"])
            dim_txt = info["dimensions"]
            if not dim_txt and self._current_pixmap and not self._current_pixmap.isNull():
                pw, ph = self._current_pixmap.width(), self._current_pixmap.height()
                dim_txt = f"{pw}×{ph}"
            size_full = f"{size_txt} ({dim_txt})" if dim_txt else size_txt
            meta_parts.append(f"\U0001F4BE {size_full}")
        if meta_parts:
            lines.append(" &nbsp;|&nbsp; ".join(meta_parts))

        # Line 4: Folder Path
        if show_path and info["parent_dir"]:
            lines.append(f"<span style='color:#94a3b8;'>\U0001F4C1 {info['parent_dir']}</span>")

        if not lines:
            self.info_overlay.hide()
            return

        self.lbl_overlay_info.setText("<br>".join(lines))
        self.info_overlay.adjustSize()
        self.info_overlay.show()
        self._position_info_overlay()

    def _position_info_overlay(self):
        if not self.info_overlay.isVisible():
            return
        self.info_overlay.adjustSize()
        h = self.info_overlay.height()
        y = max(10, self.preview_frame.height() - h - 14)
        self.info_overlay.move(14, y)
        self.info_overlay.raise_()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        if self._zoom_mode == "fit":
            self._scale_preview()
        self._position_info_overlay()

    def _prev_item(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self._load_current_item()

    def _next_item(self):
        if self.current_idx < len(self.items) - 1:
            self.current_idx += 1
            self._load_current_item()

    def _on_selection_toggled(self, checked: bool):
        if 0 <= self.current_idx < len(self.items):
            it = self.items[self.current_idx]
            if hasattr(it, "selected"):
                it.selected = checked
            self.selection_changed.emit()

    def toggle_fullscreen(self):
        """Toggles fullscreen mode for the preview dialog."""
        if self.isFullScreen():
            if getattr(self, "_was_maximized_before_fullscreen", False):
                self.showMaximized()
            else:
                self.showNormal()
        else:
            self._was_maximized_before_fullscreen = self.isMaximized()
            self.showFullScreen()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        mods = event.modifiers()
        scheme = self.config.navigation_scheme if self.config else DEFAULT_NAVIGATION_SCHEME
        if mods & Qt.KeyboardModifier.ControlModifier and Qt.Key.Key_0 <= key <= Qt.Key.Key_5:
            stars = int(key - Qt.Key.Key_0)
            if stars == 0:
                curr = int(getattr(self.items[self.current_idx], "rating", 0) or 0) if self.items else 0
                if curr > 0:
                    self._on_star_clicked(curr)
            else:
                self._on_star_clicked(stars)
            return
        if key in (Qt.Key.Key_Space, Qt.Key.Key_Escape):
            self.accept()
        elif key == Qt.Key.Key_F11:
            self.toggle_fullscreen()
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self._zoom_in()
        elif key == Qt.Key.Key_Minus:
            self._zoom_out()
        elif key == Qt.Key.Key_0:
            self._zoom_fit()
        elif key == Qt.Key.Key_1:
            self._zoom_actual()
        elif key == Qt.Key.Key_L:
            self._rotate_by(-90)
        elif key == Qt.Key.Key_R:
            self._rotate_by(90)
        elif is_nav_prev(key, scheme):
            self._prev_item()
        elif is_nav_next(key, scheme):
            self._next_item()
        elif key == Qt.Key.Key_S:
            self.chk_selected.setChecked(not self.chk_selected.isChecked())
        else:
            super().keyPressEvent(event)
