"""EXIF metadata inspector and histogram panel for the sidebar/workspace."""

from pathlib import Path
from typing import List, Optional
from PIL import Image, ImageOps

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import (
    QBrush, QColor, QDesktopServices, QFont, QImage,
    QPainter, QPainterPath, QPen, QPixmap
)
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget
)

from core.drive_detector import format_size
from core.importer import ScanItem
from core.thumbnail import extract_raw_embedded_jpeg


class HistogramWidget(QWidget):
    """Custom paint widget rendering RGB or Luminance histogram curves."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.setMaximumHeight(110)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._r_bins: List[float] = []
        self._g_bins: List[float] = []
        self._b_bins: List[float] = []
        self._l_bins: List[float] = []
        self._mode = "RGB"  # "RGB" or "LUMA"

    def set_image(self, pil_img: Optional[Image.Image]):
        """Calculates histogram bins from PIL Image thumbnail."""
        if pil_img is None:
            self._r_bins.clear()
            self._g_bins.clear()
            self._b_bins.clear()
            self._l_bins.clear()
            self.update()
            return

        try:
            # Resize image down for quick histogram computation
            thumb = pil_img.copy()
            thumb.thumbnail((160, 160))
            if thumb.mode != "RGB":
                thumb = thumb.convert("RGB")

            hist = thumb.histogram()
            if len(hist) >= 768:
                r = hist[0:256]
                g = hist[256:512]
                b = hist[512:768]
                max_val = max(max(r), max(g), max(b), 1)
                self._r_bins = [v / max_val for v in r]
                self._g_bins = [v / max_val for v in g]
                self._b_bins = [v / max_val for v in b]

                # Luminance: 0.299*R + 0.587*G + 0.114*B
                luma = [0.299 * r[i] + 0.587 * g[i] + 0.114 * b[i] for i in range(256)]
                max_luma = max(max(luma), 1)
                self._l_bins = [v / max_luma for v in luma]
            else:
                self._r_bins.clear()
                self._g_bins.clear()
                self._b_bins.clear()
                self._l_bins.clear()
        except Exception:
            self._r_bins.clear()
            self._g_bins.clear()
            self._b_bins.clear()
            self._l_bins.clear()

        self.update()

    def set_mode(self, mode: str):
        self._mode = mode
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Background
        painter.fillRect(0, 0, w, h, QColor("#090d16"))
        painter.setPen(QPen(QColor("#1e293b"), 1))
        painter.drawRect(0, 0, w - 1, h - 1)

        if not self._r_bins:
            painter.setPen(QColor("#475569"))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Keine Histogrammdaten")
            return

        # Grid lines (quarters)
        painter.setPen(QPen(QColor("#1e293b"), 1, Qt.PenStyle.DotLine))
        for i in range(1, 4):
            x = int(w * i / 4)
            painter.drawLine(x, 1, x, h - 2)

        def draw_channel(bins: List[float], fill_color: QColor, stroke_color: QColor):
            path = QPainterPath()
            path.moveTo(1, h - 2)
            n = len(bins)
            for i, val in enumerate(bins):
                x = 1 + (w - 2) * (i / (n - 1))
                y = (h - 2) - val * (h - 6)
                path.lineTo(x, y)
            path.lineTo(w - 2, h - 2)
            path.closeSubpath()

            painter.setBrush(QBrush(fill_color))
            painter.setPen(QPen(stroke_color, 1.2))
            painter.drawPath(path)

        if self._mode == "RGB":
            draw_channel(self._r_bins, QColor(239, 68, 68, 80), QColor(248, 113, 113, 200))
            draw_channel(self._g_bins, QColor(34, 197, 94, 80), QColor(74, 222, 128, 200))
            draw_channel(self._b_bins, QColor(59, 130, 246, 80), QColor(96, 165, 250, 200))
        else:
            draw_channel(self._l_bins, QColor(226, 232, 240, 100), QColor(241, 245, 249, 220))


class ExifInspectorWidget(QFrame):
    """Side panel displaying rich EXIF shooting data, preview, GPS and histogram."""

    close_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("exifInspector")
        self.setFixedWidth(320)
        self._current_item: Optional[ScanItem] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Header with close button
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        lbl_title = QLabel("ℹ️ EXIF-Inspektor")
        lbl_title.setStyleSheet("font-weight: 700; font-size: 13px; color: #38bdf8;")
        header.addWidget(lbl_title)
        header.addStretch()

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(22, 22)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94a3b8;
                border: none;
                font-size: 13px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #ef4444;
                color: white;
            }
        """)
        self.btn_close.setToolTip("Inspektor schließen")
        self.btn_close.clicked.connect(self.close_requested.emit)
        header.addWidget(self.btn_close)
        layout.addLayout(header)

        # Scroll area for metadata content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(0, 4, 0, 4)
        self.content_layout.setSpacing(8)

        # 1. Preview Box
        self.preview_frame = QFrame()
        self.preview_frame.setStyleSheet("""
            QFrame {
                background-color: #0b1120;
                border: 1px solid #1e293b;
                border-radius: 6px;
            }
        """)
        pf_layout = QVBoxLayout(self.preview_frame)
        pf_layout.setContentsMargins(4, 4, 4, 4)
        self.lbl_thumbnail = QLabel()
        self.lbl_thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_thumbnail.setMinimumHeight(130)
        self.lbl_thumbnail.setMaximumHeight(180)
        self.lbl_thumbnail.setText("Keine Datei gewählt")
        self.lbl_thumbnail.setStyleSheet("color: #64748b; font-size: 11px;")
        pf_layout.addWidget(self.lbl_thumbnail)
        self.content_layout.addWidget(self.preview_frame)

        # 2. File basic info
        self.lbl_filename = QLabel("-")
        self.lbl_filename.setWordWrap(True)
        self.lbl_filename.setStyleSheet("font-weight: 600; font-size: 12px; color: #f1f5f9;")
        self.content_layout.addWidget(self.lbl_filename)

        # Status badge row
        self.row_status = QHBoxLayout()
        self.lbl_status = QLabel("Bereit")
        self.lbl_status.setStyleSheet("""
            background-color: #0369a1;
            color: #f0f9ff;
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 11px;
            font-weight: 600;
        """)
        self.row_status.addWidget(self.lbl_status)
        self.lbl_size_type = QLabel("")
        self.lbl_size_type.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.row_status.addWidget(self.lbl_size_type)
        self.row_status.addStretch()
        self.content_layout.addLayout(self.row_status)

        # 3. Technical Exposure Box (Chips)
        self.box_shooting = QFrame()
        self.box_shooting.setStyleSheet("""
            QFrame {
                background: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        bs_layout = QVBoxLayout(self.box_shooting)
        bs_layout.setContentsMargins(6, 6, 6, 6)
        bs_layout.setSpacing(4)

        self.lbl_camera = QLabel("📷 Kamera: -")
        self.lbl_camera.setStyleSheet("font-weight: 600; font-size: 11px; color: #e2e8f0;")
        bs_layout.addWidget(self.lbl_camera)

        self.lbl_lens = QLabel("🔍 Objektiv: -")
        self.lbl_lens.setStyleSheet("font-size: 11px; color: #94a3b8;")
        bs_layout.addWidget(self.lbl_lens)

        self.lbl_exposure_chip = QLabel("ƒ/- | -s | ISO - | -mm")
        self.lbl_exposure_chip.setStyleSheet("""
            background-color: #1e293b;
            color: #38bdf8;
            font-weight: bold;
            font-size: 12px;
            border-radius: 4px;
            padding: 4px 8px;
        """)
        self.lbl_exposure_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bs_layout.addWidget(self.lbl_exposure_chip)

        self.lbl_dimensions = QLabel("📐 Auflösung: -")
        self.lbl_dimensions.setStyleSheet("font-size: 11px; color: #94a3b8;")
        bs_layout.addWidget(self.lbl_dimensions)

        self.lbl_datetime = QLabel("📅 Aufnahme: -")
        self.lbl_datetime.setStyleSheet("font-size: 11px; color: #94a3b8;")
        bs_layout.addWidget(self.lbl_datetime)

        self.content_layout.addWidget(self.box_shooting)

        # 4. Histogram Section
        lbl_hist_title = QLabel("📊 Histogramm (RGB)")
        lbl_hist_title.setStyleSheet("font-weight: 600; font-size: 11px; color: #cbd5e1;")
        self.content_layout.addWidget(lbl_hist_title)

        self.histogram_widget = HistogramWidget()
        self.content_layout.addWidget(self.histogram_widget)

        # 5. GPS Section
        self.box_gps = QFrame()
        self.box_gps.setStyleSheet("""
            QFrame {
                background: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        gps_layout = QVBoxLayout(self.box_gps)
        gps_layout.setContentsMargins(6, 6, 6, 6)
        gps_layout.setSpacing(4)

        self.lbl_gps_coords = QLabel("📍 GPS: Keine Geodaten")
        self.lbl_gps_coords.setStyleSheet("font-size: 11px; color: #94a3b8;")
        gps_layout.addWidget(self.lbl_gps_coords)

        self.btn_open_map = QPushButton("In OpenStreetMap öffnen ↗")
        self.btn_open_map.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: white;
            }
        """)
        self.btn_open_map.setVisible(False)
        self.btn_open_map.clicked.connect(self._open_map)
        gps_layout.addWidget(self.btn_open_map)
        self.content_layout.addWidget(self.box_gps)

        # 6. Destination & Sidecar Info
        self.lbl_target_info = QLabel("📁 Ziel: -")
        self.lbl_target_info.setStyleSheet("font-size: 10px; color: #64748b;")
        self.lbl_target_info.setWordWrap(True)
        self.content_layout.addWidget(self.lbl_target_info)

        self.content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def inspect_item(self, item: Optional[ScanItem]):
        """Populates inspector widgets with metadata from the selected ScanItem."""
        self._current_item = item

        if not item:
            self.lbl_filename.setText("Keine Auswahl")
            self.lbl_thumbnail.setText("Wählen Sie ein Foto aus")
            self.lbl_thumbnail.setPixmap(QPixmap())
            self.lbl_camera.setText("📷 Kamera: -")
            self.lbl_lens.setText("🔍 Objektiv: -")
            self.lbl_exposure_chip.setText("ƒ/- | -s | ISO - | -mm")
            self.lbl_dimensions.setText("📐 Auflösung: -")
            self.lbl_datetime.setText("📅 Aufnahme: -")
            self.lbl_gps_coords.setText("📍 GPS: Keine Geodaten")
            self.btn_open_map.setVisible(False)
            self.lbl_target_info.setText("📁 Ziel: -")
            self.histogram_widget.set_image(None)
            return

        # Basic Info
        self.lbl_filename.setText(item.source_path.name)
        self.lbl_size_type.setText(f"{format_size(item.total_size)} • {item.display_type}")
        self.lbl_status.setText(item.status)
        if item.is_duplicate:
            self.lbl_status.setStyleSheet("background-color: #854d0e; color: #fef08a; border-radius: 4px; padding: 2px 6px; font-size: 11px;")
        elif item.status == "Neu":
            self.lbl_status.setStyleSheet("background-color: #065f46; color: #a7f3d0; border-radius: 4px; padding: 2px 6px; font-size: 11px;")
        else:
            self.lbl_status.setStyleSheet("background-color: #0369a1; color: #f0f9ff; border-radius: 4px; padding: 2px 6px; font-size: 11px;")

        # Metadata
        meta = item.metadata
        cam = meta.camera_name or meta.camera_model or "Unbekannt"
        self.lbl_camera.setText(f"📷 {cam}")

        lens = meta.lens_model or "Standard / Keine Angabe"
        self.lbl_lens.setText(f"🔍 {lens}")

        self.lbl_exposure_chip.setText(meta.formatted_exposure)
        self.lbl_dimensions.setText(f"📐 {meta.formatted_dimensions}")

        date_str = meta.date_taken.strftime("%d.%m.%Y %H:%M:%S") if meta.date_taken else "Unbekannt"
        self.lbl_datetime.setText(f"📅 {date_str}")

        # GPS
        if meta.gps_lat is not None and meta.gps_lon is not None:
            self.lbl_gps_coords.setText(f"📍 {meta.formatted_gps}")
            self.btn_open_map.setVisible(True)
        else:
            self.lbl_gps_coords.setText("📍 GPS: Keine Geodaten")
            self.btn_open_map.setVisible(False)

        # Destination info
        dest_name = item.target_filename or item.source_path.name
        self.lbl_target_info.setText(f"📁 Zielname: {dest_name}")

        # Thumbnail & Histogram
        self._load_thumbnail_and_histogram(item)

    def _load_thumbnail_and_histogram(self, item: ScanItem):
        pil_img: Optional[Image.Image] = None

        # Paired companion JPG
        if item.is_pair and item.companion_path and item.companion_path.exists():
            try:
                with Image.open(item.companion_path) as img:
                    pil_img = ImageOps.exif_transpose(img)
                    pil_img.thumbnail((320, 240))
                    pil_img = pil_img.copy()
            except Exception:
                pass

        # Embedded RAW jpeg
        if not pil_img and item.metadata.is_raw:
            pil_img = extract_raw_embedded_jpeg(item.source_path)

        # Standard file
        if not pil_img:
            try:
                with Image.open(item.source_path) as img:
                    pil_img = ImageOps.exif_transpose(img)
                    pil_img.thumbnail((320, 240))
                    pil_img = pil_img.copy()
            except Exception:
                pass

        if pil_img:
            try:
                if pil_img.mode != "RGB":
                    conv_img = pil_img.convert("RGB")
                else:
                    conv_img = pil_img
                data = conv_img.tobytes("raw", "RGB")
                qimg = QImage(data, conv_img.width, conv_img.height, conv_img.width * 3, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg)
                scaled = pixmap.scaled(
                    260, 160,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.lbl_thumbnail.setPixmap(scaled)
                self.histogram_widget.set_image(pil_img)
                return
            except Exception:
                pass

        self.lbl_thumbnail.setText("Keine Bildvorschau")
        self.lbl_thumbnail.setPixmap(QPixmap())
        self.histogram_widget.set_image(None)

    def _open_map(self):
        if not self._current_item or not self._current_item.metadata:
            return
        meta = self._current_item.metadata
        if meta.gps_lat is not None and meta.gps_lon is not None:
            url_str = f"https://www.openstreetmap.org/?mlat={meta.gps_lat:.6f}&mlon={meta.gps_lon:.6f}#map=16/{meta.gps_lat:.6f}/{meta.gps_lon:.6f}"
            QDesktopServices.openUrl(QUrl(url_str))
