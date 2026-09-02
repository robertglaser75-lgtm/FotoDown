"""Scanning and importing orchestration engine."""

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import shutil
import threading
from typing import Callable, List, Optional
from .config import AppConfig
from .exif_reader import MediaMetadata, extract_metadata
from .history import ImportHistory, compute_file_hash
from .naming import resolve_destination


@dataclass
class ScanItem:
    source_path: Path
    metadata: MediaMetadata
    target_path: Path
    is_duplicate: bool
    file_hash: str
    status: str  # "Neu", "Bereits importiert", "Existiert im Ziel", "Fehler"
    index: int = 1
    error_msg: str = ""
    selected: bool = True


@dataclass
class ImportStats:
    total_found: int = 0
    new_files: int = 0
    duplicates_skipped: int = 0
    copied_success: int = 0
    failed: int = 0
    bytes_copied: int = 0


class ImporterEngine:
    def __init__(self, history: Optional[ImportHistory] = None):
        self.history = history or ImportHistory()

    def get_candidate_files(self, source_dir: Path, config: AppConfig) -> List[Path]:
        """Collects all matching media files in source directory."""
        if not source_dir.exists():
            return []

        allowed_exts = {ext.lower() for ext in config.custom_extensions}
        candidates = []

        if config.recursive_scan:
            for root, _, files in os.walk(source_dir):
                for f in files:
                    p = Path(root) / f
                    if p.suffix.lower() in allowed_exts:
                        candidates.append(p)
        else:
            for p in source_dir.iterdir():
                if p.is_file() and p.suffix.lower() in allowed_exts:
                    candidates.append(p)

        return sorted(candidates)

    def scan(
        self,
        source_dir: Path,
        config: AppConfig,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> List[ScanItem]:
        """Scans the source directory and evaluates EXIF, target path, and duplicate status."""
        files = self.get_candidate_files(source_dir, config)
        total = len(files)
        raw_scanned = []

        for idx, file_path in enumerate(files):
            if cancel_event and cancel_event.is_set():
                break

            if progress_callback:
                progress_callback(idx + 1, total, f"Analysiere: {file_path.name}")

            try:
                meta = extract_metadata(file_path, config.unknown_camera_label)
                f_hash = compute_file_hash(file_path)
                is_dup = self.history.is_imported(file_path, file_hash=f_hash)

                raw_scanned.append({
                    "path": file_path,
                    "meta": meta,
                    "hash": f_hash,
                    "is_dup": is_dup,
                    "error": None
                })
            except Exception as e:
                raw_scanned.append({
                    "path": file_path,
                    "meta": MediaMetadata(
                        file_path=file_path,
                        orig_name=file_path.stem,
                        extension=file_path.suffix.lower(),
                        file_size=file_path.stat().st_size if file_path.exists() else 0,
                        date_taken=datetime(1970, 1, 1),
                        date_source="Error",
                    ),
                    "hash": "",
                    "is_dup": False,
                    "error": str(e)
                })

        # Sort chronologically by date_taken so sequential numbering matches time
        raw_scanned.sort(key=lambda x: (x["meta"].date_taken or datetime(1970, 1, 1), x["path"].name))

        items: List[ScanItem] = []
        for idx, entry in enumerate(raw_scanned):
            item_idx = idx + 1
            file_path = entry["path"]
            meta = entry["meta"]
            f_hash = entry["hash"]
            is_dup = entry["is_dup"]
            err = entry["error"]

            if err:
                items.append(ScanItem(
                    source_path=file_path,
                    metadata=meta,
                    target_path=Path(config.target_dir) / file_path.name,
                    is_duplicate=False,
                    file_hash="",
                    status="Fehler",
                    index=item_idx,
                    error_msg=err,
                    selected=False,
                ))
                continue

            video_root = Path(config.video_target_dir) if config.separate_video_dir and config.video_target_dir else None

            target_dest = resolve_destination(
                Path(config.target_dir),
                config.folder_pattern,
                config.file_pattern,
                meta,
                index=item_idx,
                video_target_root=video_root,
                type_folder_organization=config.type_folder_organization,
            )

            if is_dup:
                status = "Bereits importiert"
            elif target_dest.exists():
                status = "Existiert im Ziel"
            else:
                status = "Neu"

            # Default pre-selection (Vorauswahl): 'nur Neue' files selected
            is_selected = (status == "Neu")

            items.append(ScanItem(
                source_path=file_path,
                metadata=meta,
                target_path=target_dest,
                is_duplicate=is_dup,
                file_hash=f_hash,
                status=status,
                index=item_idx,
                selected=is_selected,
            ))

        return items

    def _get_unique_target_path(self, target: Path) -> Path:
        """Finds a collision-free target path by appending _1, _2 etc."""
        if not target.exists():
            return target

        parent = target.parent
        stem = target.stem
        suffix = target.suffix
        counter = 1
        while True:
            candidate = parent / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    def execute_import(
        self,
        items: List[ScanItem],
        config: AppConfig,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> ImportStats:
        """Copies/moves the scanned items to their designated targets and updates history."""
        stats = ImportStats(total_found=len(items))

        # Filter items that are selected for download
        to_process = [it for it in items if getattr(it, 'selected', True)]
        stats.new_files = len(to_process)
        stats.duplicates_skipped = len(items) - len(to_process)

        total_to_process = len(to_process)

        for idx, item in enumerate(to_process):
            if cancel_event and cancel_event.is_set():
                break

            if progress_callback:
                progress_callback(idx + 1, total_to_process, f"Kopiere: {item.source_path.name}")

            try:
                dest = item.target_path

                # Handle collisions
                if dest.exists():
                    if config.collision_mode == "skip":
                        stats.duplicates_skipped += 1
                        continue
                    elif config.collision_mode == "rename":
                        dest = self._get_unique_target_path(dest)

                # Ensure destination folder exists
                dest.parent.mkdir(parents=True, exist_ok=True)

                # Copy file preserving timestamp
                shutil.copy2(item.source_path, dest)
                stats.bytes_copied += item.metadata.file_size
                stats.copied_success += 1

                # Record in history
                self.history.record_import(
                    file_path=item.source_path,
                    destination=dest,
                    meta=item.metadata,
                    file_hash=item.file_hash,
                )

                # Optional: Delete from source if configured (e.g. Move)
                if config.delete_source_after_import:
                    item.source_path.unlink()

            except Exception as e:
                stats.failed += 1
                item.status = "Fehler"
                item.error_msg = str(e)

        return stats
