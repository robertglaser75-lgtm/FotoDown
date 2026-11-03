"""Quick Look / Fullscreen Preview Dialog with keyboard navigation and EXIF inspector."""

from pathlib import Path
from typing import List, Optional
from PIL import Image, ImageOps

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QKeyEvent, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget
)

from core.drive_detector import format_size
from core.importer import ScanItem
from core.thumbnail import extract_raw_embedded_jpeg


class QuickPreviewDialog(QDialog):
    selection_changed = Signal()

    def __init__(self, items: List[ScanItem], start_index: int = 0, parent=None):
        super().__init__(parent)
        self.items = items
        self.current_idx = max(0, min(start_index, len(items) - 1)) if items else 0
        self._current_pixmap: Optional[QPixmap] = None

        self.setWindowTitle("FotoDown - Schnellvorschau")
        self.resize(1000, 720)
        self.setMinimumSize(640, 480)
        self.setModal(True)

        self._setup_ui()
        self._load_current_item()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # 1. Top Header Bar (Title, Index & Close)
        header = QHBoxLayout()
        header.setSpacing(12)

        self.lbl_filename = QLabel("")
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

        self.btn_close = QPushButton("\u2715 Schließen")
        self.btn_close.setObjectName("secondaryBtn")
        self.btn_close.clicked.connect(self.accept)
        header.addWidget(self.btn_close)

        layout.addLayout(header)

        # 2. Main Preview Viewport
        self.preview_frame = QFrame()
        self.preview_frame.setStyleSheet("""
            QFrame {
                background-color: #0b1120;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
        """)
        pf_layout = QVBoxLayout(self.preview_frame)
        pf_layout.setContentsMargins(8, 8, 8, 8)

        self.lbl_image = QLabel()
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        pf_layout.addWidget(self.lbl_image)

        layout.addWidget(self.preview_frame, stretch=1)

        # 3. Bottom Inspector & Selection Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(12)

        self.chk_selected = QCheckBox("Für Import ausgewählt [S]")
        self.chk_selected.setStyleSheet("font-weight: 600; font-size: 13px; color: #f8fafc;")
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

        lbl_hint = QLabel("Navigation: \u25C0 / \u25B6 | Schließen: Leertaste / Esc")
        lbl_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        bottom_bar.addWidget(lbl_hint)

        layout.addLayout(bottom_bar)

    def _load_current_item(self):
        if not self.items or self.current_idx < 0 or self.current_idx >= len(self.items):
            return

        item = self.items[self.current_idx]
        self.lbl_filename.setText(item.source_path.name)
        self.lbl_counter.setText(f"({self.current_idx + 1} von {len(self.items)})")

        self.btn_prev.setEnabled(self.current_idx > 0)
        self.btn_next.setEnabled(self.current_idx < len(self.items) - 1)

        # Update Selection checkbox without emitting loop
        self.chk_selected.blockSignals(True)
        self.chk_selected.setChecked(item.selected)
        self.chk_selected.blockSignals(False)

        # Metadata labels
        cam = item.metadata.camera_name or item.metadata.camera_model or "Kamera: Unbekannt"
        self.lbl_camera.setText(f"\U0001F4F7 {cam}")

        date_str = item.metadata.date_taken.strftime("%d.%m.%Y %H:%M:%S") if item.metadata.date_taken else "-"
        self.lbl_date.setText(f"\U0001F4C5 {date_str}")

        size_str = format_size(item.metadata.file_size)
        self.lbl_size.setText(f"\U0001F4BE {size_str} ({item.metadata.media_type})")

        self.lbl_status.setText(f"Status: {item.status}")

        # Load Preview Image
        self._load_image_preview(item.source_path, item.metadata.is_raw)

    def _load_image_preview(self, path: Path, is_raw: bool):
        pil_img = None
        if is_raw:
            pil_img = extract_raw_embedded_jpeg(path)

        if not pil_img:
            try:
                with Image.open(path) as img:
                    img = ImageOps.exif_transpose(img)
                    img.thumbnail((1600, 1200))
                    pil_img = img.copy()
            except Exception:
                pass

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

        # Fallback placeholder
        self._current_pixmap = None
        self.lbl_image.setText("\U0001F5BC Keine hochauflösende Vorschau verfügbar")
        self.lbl_image.setStyleSheet("color: #64748b; font-size: 16px;")

    def _scale_preview(self):
        if not self._current_pixmap or self._current_pixmap.isNull():
            return
        avail_size = self.preview_frame.size() - self.preview_frame.contentsMargins().toSize()
        scaled = self._current_pixmap.scaled(
            avail_size.width() - 16,
            avail_size.height() - 16,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
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
            self.items[self.current_idx].selected = checked
            self.selection_changed.emit()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key in (Qt.Key.Key_Space, Qt.Key.Key_Escape):
            self.accept()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_A):
            self._prev_item()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_D):
            self._next_item()
        elif key == Qt.Key.Key_S:
            self.chk_selected.setChecked(not self.chk_selected.isChecked())
        else:
            super().keyPressEvent(event)

