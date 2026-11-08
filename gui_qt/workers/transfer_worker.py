"""Background worker for copying and moving media items and sidecars (Tab 3: Transfer & Archive)."""

import os
from pathlib import Path
import shutil
from typing import List, Optional, Tuple

from PySide6.QtCore import QThread, Signal

from core.drive_detector import format_size


class TransferWorker(QThread):
    """Worker thread for non-blocking file copy/move operations between local PC and NAS/Archive."""
    
    # Signals
    progress = Signal(int, int, str)               # current (1-based), total, current file name
    file_completed = Signal(str, str, bool)         # src_path, dst_path, success
    transfer_finished = Signal(int, int, int, list) # success_count, error_count, total_bytes, error_list
    error = Signal(str)                             # critical error message

    def __init__(
        self,
        files: List[Path],
        destination_dir: Path,
        operation: str = "copy",  # "copy" or "move"
        sync_sidecars: bool = True,
        parent=None
    ):
        super().__init__(parent)
        self.files = [Path(f) for f in files]
        self.destination_dir = Path(destination_dir)
        self.operation = operation.lower()  # "copy" or "move"
        self.sync_sidecars = sync_sidecars
        self._is_cancelled = False

    def cancel(self):
        """Requests cancellation of the running transfer operation."""
        self._is_cancelled = True

    @staticmethod
    def find_sidecars(media_path: Path) -> List[Path]:
        """Finds any companion sidecar files (.xmp, .pp3, etc.) for a media file."""
        candidates = [
            media_path.with_name(f"{media_path.name}.xmp"),
            media_path.with_suffix(".xmp"),
            media_path.with_name(f"{media_path.name}.pp3"),
            media_path.with_suffix(".pp3"),
        ]
        seen = set()
        existing = []
        for c in candidates:
            if c != media_path and c.exists() and str(c) not in seen:
                seen.add(str(c))
                existing.append(c)
        return existing

    def run(self):
        """Executes the file transfer sequentially."""
        if not self.destination_dir:
            self.error.emit("Kein Zielverzeichnis angegeben.")
            return

        try:
            self.destination_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.error.emit(f"Zielverzeichnis konnte nicht erstellt werden: {e}")
            return

        total_files = len(self.files)
        success_count = 0
        error_count = 0
        total_transferred_bytes = 0
        errors: List[str] = []

        for idx, src_file in enumerate(self.files):
            if self._is_cancelled:
                break

            self.progress.emit(idx + 1, total_files, src_file.name)

            if not src_file.exists():
                err_msg = f"Quelldatei nicht gefunden: {src_file.name}"
                errors.append(err_msg)
                error_count += 1
                self.file_completed.emit(str(src_file), "", False)
                continue

            dest_file = self.destination_dir / src_file.name

            # Check if source and destination are the exact same path
            if src_file.resolve() == dest_file.resolve():
                err_msg = f"Quelle und Ziel sind identisch: {src_file.name}"
                errors.append(err_msg)
                error_count += 1
                self.file_completed.emit(str(src_file), str(dest_file), False)
                continue

            try:
                file_size = src_file.stat().st_size
                # Copy the main media file preserving metadata
                shutil.copy2(src_file, dest_file)

                # Verify copy
                if not dest_file.exists() or dest_file.stat().st_size != file_size:
                    raise IOError(f"Dateigröße nach Kopieren stimmt nicht überein für {src_file.name}")

                total_transferred_bytes += file_size

                # Handle companion sidecars (e.g. .xmp, .pp3)
                transferred_sidecars: List[Tuple[Path, Path]] = []
                if self.sync_sidecars:
                    sidecars = self.find_sidecars(src_file)
                    for sc in sidecars:
                        dest_sc = self.destination_dir / sc.name
                        shutil.copy2(sc, dest_sc)
                        if dest_sc.exists():
                            total_transferred_bytes += sc.stat().st_size
                            transferred_sidecars.append((sc, dest_sc))

                # If moving: safely remove the source files only after destination is verified
                if self.operation == "move":
                    src_file.unlink()
                    for sc, _ in transferred_sidecars:
                        if sc.exists():
                            try:
                                sc.unlink()
                            except OSError:
                                pass

                success_count += 1
                self.file_completed.emit(str(src_file), str(dest_file), True)

            except Exception as e:
                err_msg = f"Fehler bei {src_file.name}: {e}"
                errors.append(err_msg)
                error_count += 1
                self.file_completed.emit(str(src_file), str(dest_file), False)

        if not self._is_cancelled:
            self.transfer_finished.emit(success_count, error_count, total_transferred_bytes, errors)
