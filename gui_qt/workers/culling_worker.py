"""Background worker thread for asynchronous folder scanning in the Culling workflow."""

from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import QThread, Signal

from gui_qt.models.culling_model import CullingItem, scan_culling_folder


class CullingScanWorker(QThread):
    progress = Signal(int, int, str)       # cur, total, filename
    scan_finished = Signal(list)           # List[CullingItem]
    error = Signal(str)

    def __init__(self, folder_path: Path, parent=None):
        super().__init__(parent)
        self.folder_path = folder_path
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if not self.folder_path.exists() or not self.folder_path.is_dir():
                self.error.emit(f"Ordner '{self.folder_path}' existiert nicht.")
                return

            def on_progress(cur: int, total: int, msg: str):
                if not self._is_cancelled:
                    self.progress.emit(cur, total, msg)

            items = scan_culling_folder(
                self.folder_path,
                progress_callback=on_progress,
                cancel_check=lambda: self._is_cancelled
            )

            if not self._is_cancelled:
                self.scan_finished.emit(items)
        except Exception as e:
            self.error.emit(str(e))
