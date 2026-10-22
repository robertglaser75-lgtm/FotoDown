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


class ThumbnailTask(QRunnable):
    def __init__(self, path: Path, max_size=(160, 160)):
        super().__init__()
        self.path = path
        self.max_size = max_size
        self.signals = ThumbnailSignals()

    def run(self):
        try:
            pil_img = generate_thumbnail(self.path, self.max_size)
            if pil_img:
                # Convert PIL Image to QImage via bytes
                pil_img = pil_img.convert("RGBA")
                data = pil_img.tobytes("raw", "RGBA")
                qimage = QImage(data, pil_img.width, pil_img.height, QImage.Format.Format_RGBA8888)
                self.signals.thumbnail_ready.emit(str(self.path), qimage.copy())
        except Exception:
            pass
