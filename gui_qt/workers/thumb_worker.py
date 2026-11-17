"""Asynchronous thumbnail loader using QThreadPool and QRunnable."""

import io
from pathlib import Path
from typing import Optional
from PIL import Image

from PySide6.QtCore import QObject, QRunnable, Signal
from PySide6.QtGui import QImage

from core.thumbnail import generate_thumbnail


class ThumbnailSignals(QObject):
    thumbnail_ready = Signal(str, QImage)  # path_str, QImage


class PreviewSignals(QObject):
    preview_ready = Signal(str, QImage)  # path_str, QImage


class ThumbnailTask(QRunnable):
    def __init__(self, path: Path, key_path: Optional[str] = None, signals: Optional[ThumbnailSignals] = None, max_size=(320, 320)):
        super().__init__()
        self.path = path
        self.key_path = str(key_path or path)
        self.signals = signals or ThumbnailSignals()
        self.max_size = max_size
        self.setAutoDelete(True)

    def run(self):
        try:
            pil_img = generate_thumbnail(self.path, self.max_size)
            if pil_img:
                # Fast direct memory conversion (7.5x faster than PNG serialization)
                if pil_img.mode != "RGBA":
                    pil_img = pil_img.convert("RGBA")
                raw_bytes = pil_img.tobytes("raw", "RGBA")
                qimage = QImage(
                    raw_bytes,
                    pil_img.width,
                    pil_img.height,
                    pil_img.width * 4,
                    QImage.Format.Format_RGBA8888
                ).copy()
                if not qimage.isNull():
                    self.signals.thumbnail_ready.emit(self.key_path, qimage)
        except Exception:
            pass


class PreviewTask(QRunnable):
    """Loads a high-resolution preview image asynchronously in the background for prefetching and smooth culling."""
    def __init__(self, path: Path, key_path: Optional[str] = None, signals: Optional[PreviewSignals] = None, max_dim: int = 3840):
        super().__init__()
        self.path = path
        self.key_path = str(key_path or path)
        self.signals = signals or PreviewSignals()
        self.max_dim = max_dim
        self.setAutoDelete(True)

    def run(self):
        try:
            from core.thumbnail import load_preview_image
            pil_img = load_preview_image(self.path, max_dim=self.max_dim)
            if pil_img:
                if pil_img.mode != "RGB":
                    pil_img = pil_img.convert("RGB")
                raw_bytes = pil_img.tobytes("raw", "RGB")
                qimage = QImage(
                    raw_bytes,
                    pil_img.width,
                    pil_img.height,
                    pil_img.width * 3,
                    QImage.Format.Format_RGB888
                ).copy()
                if not qimage.isNull():
                    self.signals.preview_ready.emit(self.key_path, qimage)
        except Exception:
            pass
