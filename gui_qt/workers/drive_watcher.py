"""Background worker for detecting hardware hotplug events (SD cards, USB drives)."""

import time
from typing import List, Optional
from PySide6.QtCore import QThread, Signal

from core.drive_detector import DriveInfo, DriveMonitor, detect_drives


class DriveWatcherThread(QThread):
    drive_inserted = Signal(object)  # DriveInfo
    drive_removed = Signal(object)   # DriveInfo
    drives_updated = Signal(list)    # List[DriveInfo]

    def __init__(self, interval_sec: float = 2.0, parent=None):
        super().__init__(parent)
        self.interval_sec = max(0.5, interval_sec)
        self.monitor = DriveMonitor(detect_drives)
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        while self._running:
            try:
                added, removed = self.monitor.check_changes()
                if added or removed:
                    for d in added:
                        self.drive_inserted.emit(d)
                    for d in removed:
                        self.drive_removed.emit(d)
                    current_drives = list(self.monitor._known_drives.values())
                    self.drives_updated.emit(current_drives)
            except Exception:
                pass

            # Responsive sleep loop
            steps = int(self.interval_sec * 10)
            for _ in range(steps):
                if not self._running:
                    break
                time.sleep(0.1)
