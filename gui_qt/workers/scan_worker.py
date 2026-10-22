"""Background worker for scanning media items."""

from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import QThread, Signal

from core.config import AppConfig
from core.importer import ImporterEngine, ScanItem


class ScanWorker(QThread):
    progress = Signal(int, int, str)
    scan_finished = Signal(list)
    error = Signal(str)

    def __init__(self, engine: ImporterEngine, source_dir: Path, config: AppConfig):
        super().__init__()
        self.engine = engine
        self.source_dir = source_dir
        self.config = config
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if not self.source_dir.exists():
                self.error.emit(f"Quellordner '{self.source_dir}' existiert nicht.")
                return

            def on_progress(cur: int, total: int, msg: str):
                if not self._is_cancelled:
                    self.progress.emit(cur, total, msg)

            items = self.engine.scan(self.source_dir, self.config, progress_callback=on_progress)
            if not self._is_cancelled:
                self.scan_finished.emit(items)
        except Exception as e:
            self.error.emit(str(e))
