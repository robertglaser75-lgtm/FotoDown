"""Quick Look / Fullscreen Preview Dialog with keyboard navigation and EXIF inspector."""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image, ImageOps

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QKeyEvent, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget
)

from core.drive_detector import format_size
from core.config import AppConfig
from core.importer import ScanItem
from core.thumbnail import extract_raw_embedded_jpeg, load_preview_image
from gui_qt.key_navigation import DEFAULT_NAVIGATION_SCHEME, is_nav_next, is_nav_prev
from gui_qt.styles.icons import get_clear_icon, get_folder_open_icon
from gui_qt.widgets.elided_label import ElidedLabel


class QuickPreviewDialog(QDialog):
    selection_changed = Signal()

    def __init__(self, items: List[Any], start_index: int = 0, parent=None, config: Optional[AppConfig] = None, fullscreen: bool = False):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.config = config
        self.items = items
        self.current_idx = max(0, min(start_index, len(items) - 1)) if items else 0
        self._current_pixmap: Optional[QPixmap] = None
        self._was_maximized_before_fullscreen: bool = False

        self.setWindowTitle("FotoDown - Vollbildvorschau")
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

        # 1. Top Header Bar (Title, Index & Close)
        header = QHBoxLayout()
        header.setSpacing(12)

        self.lbl_filename = ElidedLabel("")
        self.lbl_filename.setMaximumWidth(450)
        self.lbl_filename.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8;")
        header.addWidget(self.lbl_filename)

        self.lbl_counter = QLabel("")
        self.lbl_counter.setStyleSheet("color: #94a3b8; font-size: 13px;")
        header.addWidget(self.lbl_counter)

        header.addStretch()

        self.btn_prev = QPushButton("\u25C0 Vorheriges")
        self.btn_prev.setObjectName("secondaryBtn")
        self.btn_prev.clicked.connect(self._prev_item)
        header.addWidget(self.btn_prev)

        self.btn_next = QPushButton("Nächstes \u25B6")
        self.btn_next.setObjectName("secondaryBtn")
        self.btn_next.clicked.connect(self._next_item)
        header.addWidget(self.btn_next)

        self.btn_open_orig = QPushButton("Original öffnen")
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

        # 2. Main Image Preview Area
        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("photoCanvasArea")
        pf_layout = QVBoxLayout(self.preview_frame)
        pf_layout.setContentsMargins(8, 8, 8, 8)

        self.lbl_image = QLabel()
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.lbl_image.mouseDoubleClickEvent = self._on_image_double_clicked
        pf_layout.addWidget(self.lbl_image)

        layout.addWidget(self.preview_frame, stretch=1)

        # 3. Bottom Inspector & Selection Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(12)

        self.chk_selected = QCheckBox("Ausgewählt [S]")
        self.chk_selected.setStyleSheet("font-weight: 600; font-size: 13px;")
        self.chk_selected.toggled.connect(self._on_selection_toggled)
        bottom_bar.addWidget(self.chk_selected)

        bottom_bar.addSpacing(16)

        # EXIF Metadata Chips
        self.lbl_camera = QLabel("")
        self.lbl_camera.setObjectName("tagChip")
        bottom_bar.addWidget(self.lbl_camera)

        self.lbl_date = QLabel("")
        self.lbl_date.setObjectName("tagChip")
        bottom_bar.addWidget(self.lbl_date)

        self.lbl_size = QLabel("")
        self.lbl_size.setObjectName("tagChip")
        bottom_bar.addWidget(self.lbl_size)

        self.lbl_status = QLabel("")
        self.lbl_status.setObjectName("tagChip")
        bottom_bar.addWidget(self.lbl_status)

        bottom_bar.addStretch()

        lbl_hint = QLabel("Navigation: \u25C0 / \u25B6 | F11: Vollbild | Doppelklick: Umschalten | Schließen: Leertaste / Esc")
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
        is_selected = False
        camera = ""
        date_str = "-"
        size_bytes = 0
        display_type = ""
        status_text = ""

        # ScanItem (Tab 1)
        if hasattr(item, "source_path"):
            display_name = item.source_path.name
            target_path = (
                item.companion_path
                if (getattr(item, "is_pair", False) and item.companion_path and item.companion_path.exists())
                else item.source_path
            )
            is_selected = getattr(item, "selected", False)
            meta = getattr(item, "metadata", None)
            if meta:
                camera = getattr(meta, "camera_name", None) or getattr(meta, "camera_model", "")
                if getattr(meta, "date_taken", None):
                    date_str = meta.date_taken.strftime("%d.%m.%Y %H:%M:%S")
            size_bytes = getattr(item, "total_size", 0)
            display_type = getattr(item, "display_type", item.source_path.suffix.upper())
            status_text = getattr(item, "status", "")

        # CullingItem (Tab 2)
        elif hasattr(item, "primary_path"):
            display_name = item.primary_path.name
            target_path = getattr(item, "current_display_path", None) or (
                item.companion_path
                if (item.companion_path and item.companion_path.exists())
                else item.primary_path
            )
            is_selected = getattr(item, "selected", False)
            meta = getattr(item, "metadata", None)
            if meta:
                camera = getattr(meta, "camera_name", None) or getattr(meta, "camera_model", "")
                if getattr(meta, "date_taken", None):
                    date_str = meta.date_taken.strftime("%d.%m.%Y %H:%M:%S")
            try:
                size_bytes = item.primary_path.stat().st_size if item.primary_path.exists() else 0
            except OSError:
                size_bytes = 0
            display_type = getattr(item, "active_view_mode", item.primary_path.suffix.upper())
            if hasattr(item, "workflow_status_info"):
                status_text = item.workflow_status_info[0]
            elif hasattr(item, "workflow_status"):
                status_text = item.workflow_status

        # TransferItem (Tab 3)
        elif hasattr(item, "path") and hasattr(item, "is_raw"):
            display_name = item.name
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

        # Path or str
        elif isinstance(item, (Path, str)):
            p = Path(item)
            display_name = p.name
            target_path = p
            display_type = p.suffix.upper()
            try:
                st = p.stat()
                size_bytes = st.st_size
                date_str = datetime.fromtimestamp(st.st_mtime).strftime("%d.%m.%Y %H:%M:%S")
            except OSError:
                size_bytes = 0

        return {
            "name": display_name,
            "target_path": target_path,
            "selected": is_selected,
            "camera": camera,
            "date": date_str,
            "size": size_bytes,
            "type": display_type,
            "status": status_text,
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

        # Metadata labels
        cam = info["camera"] or "Kamera: Unbekannt"
        self.lbl_camera.setText(f"\U0001F4F7 {cam}")
        self.lbl_date.setText(f"\U0001F4C5 {info['date']}")
        size_str = format_size(info["size"])
        self.lbl_size.setText(f"\U0001F4BE {size_str} ({info['type']})")
        self.lbl_status.setText(f"Status: {info['status']}")

        # Load Preview Image
        self._load_image_preview(info["target_path"])

    def _load_image_preview(self, target_path: Optional[Path]):
        if not target_path or not target_path.exists():
            self._current_pixmap = None
            self.lbl_image.setText("\U0001F5BC Keine Vorschau verfügbar")
            self.lbl_image.setStyleSheet("color: #64748b; font-size: 16px;")
            return

        # 1. Try high-resolution preview extractor (embedded JPEG in RAW or fast scaling up to 4K)
        pil_img = load_preview_image(target_path, max_dim=3840)

        # 2. Fallback: try opening full native image directly with PIL
        if pil_img is None:
            try:
                with Image.open(target_path) as full_img:
                    pil_img = ImageOps.exif_transpose(full_img).copy()
            except Exception:
                pil_img = None

        if pil_img:
            try:
                if pil_img.mode != "RGB":
                    pil_img = pil_img.convert("RGB")
                data = pil_img.tobytes("raw", "RGB")
                qimg = QImage(data, pil_img.width, pil_img.height, pil_img.width * 3, QImage.Format.Format_RGB888)
                self._current_pixmap = QPixmap.fromImage(qimg)
                self._scale_preview()
                return
            except Exception:
                pass

        # 3. If no high-res preview can be generated: automatically open the original file with system viewer
        self._current_pixmap = None
        self._open_original_external(target_path)

    def _open_original_external(self, target_path: Path):
        """Automatically opens the original file with the system default viewer."""
        if not os.environ.get("FOTODOWN_HEADLESS_TEST"):
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            try:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(target_path.resolve())))
            except Exception:
                pass

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
        if p and p.exists() and not os.environ.get("FOTODOWN_HEADLESS_TEST"):
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.resolve())))

    def _scale_preview(self):
        if not self._current_pixmap or self._current_pixmap.isNull():
            return
        avail_size = self.preview_frame.size() - self.preview_frame.contentsMargins().toSize()
        dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
        target_w = max(10, int((avail_size.width() - 16) * dpr))
        target_h = max(10, int((avail_size.height() - 16) * dpr))
        scaled = self._current_pixmap.scaled(
            target_w,
            target_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(dpr)
        self.lbl_image.setPixmap(scaled)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._scale_preview()

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
        scheme = self.config.navigation_scheme if self.config else DEFAULT_NAVIGATION_SCHEME
        if key in (Qt.Key.Key_Space, Qt.Key.Key_Escape):
            self.accept()
        elif key == Qt.Key.Key_F11:
            self.toggle_fullscreen()
        elif is_nav_prev(key, scheme):
            self._prev_item()
        elif is_nav_next(key, scheme):
            self._next_item()
        elif key == Qt.Key.Key_S:
            self.chk_selected.setChecked(not self.chk_selected.isChecked())
        else:
            super().keyPressEvent(event)
