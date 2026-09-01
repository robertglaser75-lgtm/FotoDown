"""SQLite-based import history and duplicate tracking."""

from contextlib import contextmanager
from datetime import datetime
import hashlib
import os
from pathlib import Path
import sqlite3
from typing import Dict, Generator, List, Optional
from .exif_reader import MediaMetadata


def compute_file_hash(file_path: Path, fast_sample_threshold_mb: int = 50) -> str:
    """
    Computes a deterministic hash of the file.
    For files under threshold MB: full MD5.
    For very large video/raw files (> threshold MB): fast hash (head 1MB + tail 1MB + size).
    """
    size = file_path.stat().st_size
    threshold_bytes = fast_sample_threshold_mb * 1024 * 1024

    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        if size <= threshold_bytes:
            # Full hash in 64KB chunks
            while chunk := f.read(65536):
                hasher.update(chunk)
        else:
            # Fast sample hash: size + first 1MB + last 1MB
            hasher.update(str(size).encode("utf-8"))
            hasher.update(f.read(1024 * 1024))
            if size > 1024 * 1024:
                f.seek(max(0, size - 1024 * 1024))
                hasher.update(f.read(1024 * 1024))

    return hasher.hexdigest()


class ImportHistory:
    """Manages the database of already downloaded/imported media files."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            appdata = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
            if appdata:
                db_dir = Path(appdata) / "FotoDown"
            else:
                db_dir = Path.home() / ".fotodown"
            db_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = db_dir / "history.db"
        else:
            self.db_path = db_path

        self._init_db()

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initializes database schema and indexes."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS imported_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_hash TEXT NOT NULL,
                    orig_filename TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    date_taken TEXT,
                    destination_path TEXT,
                    import_timestamp TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON imported_files(file_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_orig_size ON imported_files(orig_filename, file_size)")
            conn.commit()

    def is_imported(self, file_path: Path, file_hash: Optional[str] = None) -> bool:
        """Checks if a file has already been imported."""
        if not file_path.exists():
            return False

        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        with self._connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM imported_files WHERE file_hash = ? LIMIT 1", (file_hash,))
            return cur.fetchone() is not None

    def record_import(
        self,
        file_path: Path,
        destination: Path,
        meta: MediaMetadata,
        file_hash: Optional[str] = None,
    ) -> None:
        """Records a successfully imported file into the history."""
        if file_hash is None:
            file_hash = compute_file_hash(file_path)

        now_iso = datetime.now().isoformat()
        date_taken_iso = meta.date_taken.isoformat() if meta.date_taken else ""

        with self._connection() as conn:
            conn.execute("""
                INSERT INTO imported_files (
                    file_hash, orig_filename, file_size, date_taken, destination_path, import_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                file_hash,
                file_path.name,
                meta.file_size,
                date_taken_iso,
                str(destination),
                now_iso,
            ))
            conn.commit()

    def get_count(self) -> int:
        """Returns the total number of imported files in history."""
        with self._connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM imported_files")
            res = cur.fetchone()
            return res[0] if res else 0

    def get_recent_imports(self, limit: int = 100) -> List[Dict]:
        """Returns the most recent imports."""
        with self._connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, orig_filename, file_size, date_taken, destination_path, import_timestamp
                FROM imported_files
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cur.fetchall()]

    def clear_all(self) -> None:
        """Deletes all history records."""
        with self._connection() as conn:
            conn.execute("DELETE FROM imported_files")
            conn.commit()
