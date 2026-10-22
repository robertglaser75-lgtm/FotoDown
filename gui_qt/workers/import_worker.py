"""Background worker for importing and renaming media items."""

from typing import List, Optional
from PySide6.QtCore import QThread, Signal

from core.config import AppConfig
from core.importer import ImporterEngine, ScanItem, ImportStats


class ImportWorker(QThread):
    progress = Signal(int, int, str)
    import_finished = Signal(object)
    error = Signal(str)

    def __init__(self, engine: ImporterEngine, items: List[ScanItem], config: AppConfig):
        super().__init__()
        self.engine = engine
        self.items = items
        self.config = config
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            def on_progress(cur: int, total: int, msg: str):
                if not self._is_cancelled:
                    self.progress.emit(cur, total, msg)

            stats = self.engine.execute_import(self.items, self.config, progress_callback=on_progress)
            if not self._is_cancelled:
                self.import_finished.emit(stats)
        except Exception as e:
            self.error.emit(str(e))
