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
                # Convert PIL Image to QImage safely via memory PNG buffer
                bio = io.BytesIO()
                pil_img.save(bio, format="PNG")
                qimage = QImage()
                qimage.loadFromData(bio.getvalue())
                if not qimage.isNull():
                    self.signals.thumbnail_ready.emit(self.key_path, qimage)
        except Exception:
            pass
