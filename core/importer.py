"""Scanning and importing orchestration engine with RAW+JPG pairing, XMP sidecars, and dual-backup."""

from dataclasses import dataclass, field
from datetime import datetime
import os
from pathlib import Path
import shutil
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple
from .config import AppConfig
from .exif_reader import MediaMetadata, extract_metadata
from .history import ImportHistory, compute_file_hash
from .metadata_writer import inject_metadata_sidecar
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
    # RAW+JPG Pairing & XMP Sidecars
    is_pair: bool = False
    companion_path: Optional[Path] = None
    companion_metadata: Optional[MediaMetadata] = None
    companion_target_path: Optional[Path] = None
    companion_hash: str = ""
    sidecar_paths: List[Path] = field(default_factory=list)

    @property
    def total_size(self) -> int:
        size = self.metadata.file_size
        if self.companion_metadata:
            size += self.companion_metadata.file_size
        for sc in self.sidecar_paths:
            try:
                size += sc.stat().st_size
            except Exception:
                pass
        return size

    @property
    def display_type(self) -> str:
        if self.is_pair:
            xmp = " + XMP" if self.sidecar_paths else ""
            return f"RAW+JPG{xmp}"
        t = self.metadata.media_type
        if self.sidecar_paths:
            return f"{t} + XMP"
        return t

    @property
    def target_filename(self) -> str:
        return self.target_path.name if self.target_path else ""


@dataclass
class ImportStats:
    total_found: int = 0
    new_files: int = 0
    duplicates_skipped: int = 0
    copied_success: int = 0
    backup_success: int = 0
    paired_count: int = 0
    sidecars_copied: int = 0
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

    def _find_xmp_sidecars(self, file_path: Path) -> List[Path]:
        """Looks for .xmp sidecar files matching the base file."""
        candidates = [
            file_path.with_suffix(".xmp"),
            file_path.with_suffix(".XMP"),
            Path(str(file_path) + ".xmp"),
            Path(str(file_path) + ".XMP"),
        ]
        found = []
        for c in candidates:
            if c.exists() and c.is_file() and c not in found:
                found.append(c)
        return found

    def scan(
        self,
        source_dir: Path,
        config: AppConfig,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> List[ScanItem]:
        """Scans the source directory and evaluates EXIF, pairing, and duplicate status."""
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

        # RAW + JPG Pairing step
        paired_scanned = []
        if config.pair_raw_jpg:
            # Group by (parent_dir, stem_lower)
            groups: Dict[Tuple[Path, str], List[dict]] = {}
            for item in raw_scanned:
                key = (item["path"].parent, item["path"].stem.lower())
                groups.setdefault(key, []).append(item)

            for key, items in groups.items():
                if len(items) >= 2:
                    raw_item = next((it for it in items if it["meta"].is_raw), None)
                    jpg_item = next((it for it in items if it["meta"].extension.lower() in (".jpg", ".jpeg")), None)

                    if raw_item and jpg_item and raw_item != jpg_item:
                        # Combine into paired entry
                        combined = dict(raw_item)
                        combined["is_pair"] = True
                        combined["companion"] = jpg_item
                        paired_scanned.append(combined)

                        # Add remaining items if any (rare edge cases)
                        for other in items:
                            if other not in (raw_item, jpg_item):
                                paired_scanned.append(other)
                        continue

                # Not a pair, add all normally
                for it in items:
                    paired_scanned.append(it)
        else:
            paired_scanned = raw_scanned

        # Sort chronologically by date_taken so sequential numbering matches capture time
        paired_scanned.sort(key=lambda x: (x["meta"].date_taken or datetime(1970, 1, 1), x["path"].name))

        items: List[ScanItem] = []
        for idx, entry in enumerate(paired_scanned):
            item_idx = idx + 1
            file_path = entry["path"]
            meta = entry["meta"]
            f_hash = entry["hash"]
            is_dup = entry["is_dup"]
            err = entry.get("error")
            is_pair = entry.get("is_pair", False)
            companion = entry.get("companion")

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

            # Primary destination
            target_dest = resolve_destination(
                Path(config.target_dir),
                config.folder_pattern,
                config.file_pattern,
                meta,
                index=item_idx,
                video_target_root=video_root,
                type_folder_organization=config.type_folder_organization,
            )

            # Companion destination (if paired)
            companion_dest = None
            if is_pair and companion:
                companion_dest = resolve_destination(
                    Path(config.target_dir),
                    config.folder_pattern,
                    config.file_pattern,
                    companion["meta"],
                    index=item_idx,
                    video_target_root=video_root,
                    type_folder_organization=config.type_folder_organization,
                )

            # Find XMP sidecars
            sidecars = []
            if config.sync_xmp_sidecars:
                sidecars = self._find_xmp_sidecars(file_path)
                if is_pair and companion:
                    for sc in self._find_xmp_sidecars(companion["path"]):
                        if sc not in sidecars:
                            sidecars.append(sc)

            if is_dup and (not companion or companion.get("is_dup", True)):
                status = "Bereits importiert"
            elif target_dest.exists() and (not companion_dest or companion_dest.exists()):
                status = "Existiert im Ziel"
            else:
                status = "Neu"

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
                is_pair=is_pair,
                companion_path=companion["path"] if companion else None,
                companion_metadata=companion["meta"] if companion else None,
                companion_target_path=companion_dest,
                companion_hash=companion["hash"] if companion else "",
                sidecar_paths=sidecars,
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
        """Copies items with companion files and XMP sidecars, verifying bit-exact integrity."""
        stats = ImportStats(total_found=len(items))

        to_process = [it for it in items if getattr(it, 'selected', True)]
        stats.new_files = len(to_process)
        stats.duplicates_skipped = len(items) - len(to_process)

        total_to_process = len(to_process)
        total_bytes_to_copy = sum(it.total_size for it in to_process)
        start_time = time.time()

        for idx, item in enumerate(to_process):
            if cancel_event and cancel_event.is_set():
                break

            # Calculate transfer speed and ETA
            elapsed = max(0.01, time.time() - start_time)
            speed_bytes_s = stats.bytes_copied / elapsed if stats.bytes_copied > 0 else 0
            remaining_bytes = max(0, total_bytes_to_copy - stats.bytes_copied)
            if speed_bytes_s > 0 and remaining_bytes > 0:
                eta_sec = int(remaining_bytes / speed_bytes_s)
                eta_str = f"noch {eta_sec // 60}m {eta_sec % 60}s" if eta_sec >= 60 else f"noch {eta_sec}s"
                speed_str = f"{speed_bytes_s / (1024 * 1024):.1f} MB/s"
                pair_tag = " [RAW+JPG]" if item.is_pair else ""
                status_msg = f"Kopiere ({idx+1}/{total_to_process}): {item.source_path.name}{pair_tag} [{speed_str}, {eta_str}]"
            else:
                status_msg = f"Kopiere ({idx+1}/{total_to_process}): {item.source_path.name}"

            if progress_callback:
                progress_callback(idx + 1, total_to_process, status_msg)

            try:
                dest = item.target_path

                # Collision handling for primary destination
                if dest.exists():
                    if config.collision_mode == "skip":
                        stats.duplicates_skipped += 1
                        continue
                    elif config.collision_mode == "rename":
                        dest = self._get_unique_target_path(dest)

                # 1. Primary Copy & Verify
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item.source_path, dest)
                stats.bytes_copied += item.metadata.file_size

                if config.verify_checksums:
                    dest_hash = compute_file_hash(dest)
                    if dest_hash != item.file_hash:
                        raise IOError(f"Prüfsummenfehler bei Ziel {dest.name}")

                # 2. Companion Copy (RAW+JPG Pair)
                if item.is_pair and item.companion_path and item.companion_target_path:
                    comp_dest = item.companion_target_path
                    if comp_dest.exists() and config.collision_mode == "rename":
                        comp_dest = self._get_unique_target_path(comp_dest)

                    comp_dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item.companion_path, comp_dest)
                    if item.companion_metadata:
                        stats.bytes_copied += item.companion_metadata.file_size
                    stats.paired_count += 1

                    if config.verify_checksums and item.companion_hash:
                        comp_hash = compute_file_hash(comp_dest)
                        if comp_hash != item.companion_hash:
                            raise IOError(f"Prüfsummenfehler beim gepaarten JPG {comp_dest.name}")

                # 3. Synchronize XMP Sidecar files
                for sc in item.sidecar_paths:
                    if sc.exists():
                        sc_dest = dest.with_suffix(".xmp")
                        shutil.copy2(sc, sc_dest)
                        stats.sidecars_copied += 1
                        try:
                            stats.bytes_copied += sc.stat().st_size
                        except Exception:
                            pass

                # 3b. Inject IPTC / Copyright Metadata (if enabled)
                if config.enable_iptc and (config.iptc_creator or config.iptc_copyright):
                    inject_metadata_sidecar(
                        target_path=dest,
                        creator=config.iptc_creator,
                        copyright_template=config.iptc_copyright,
                        keywords_str=config.iptc_keywords,
                        date_taken=item.metadata.date_taken,
                    )
                    if item.is_pair and item.companion_target_path:
                        inject_metadata_sidecar(
                            target_path=item.companion_target_path,
                            creator=config.iptc_creator,
                            copyright_template=config.iptc_copyright,
                            keywords_str=config.iptc_keywords,
                            date_taken=item.metadata.date_taken,
                        )

                # 4. Dual-Backup Copy
                if config.enable_dual_backup and config.backup_target_dir:
                    backup_root = Path(config.backup_target_dir)
                    backup_dest = resolve_destination(
                        backup_root,
                        config.folder_pattern,
                        config.file_pattern,
                        item.metadata,
                        index=item.index,
                        type_folder_organization=config.type_folder_organization,
                    )
                    if backup_dest.exists() and config.collision_mode == "rename":
                        backup_dest = self._get_unique_target_path(backup_dest)

                    backup_dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item.source_path, backup_dest)
                    stats.backup_success += 1

                    if config.verify_checksums:
                        bk_hash = compute_file_hash(backup_dest)
                        if bk_hash != item.file_hash:
                            raise IOError(f"Prüfsummenfehler bei Backup-Ziel {backup_dest.name}")

                    # Backup for paired companion
                    if item.is_pair and item.companion_path and item.companion_metadata:
                        comp_bk_dest = resolve_destination(
                            backup_root,
                            config.folder_pattern,
                            config.file_pattern,
                            item.companion_metadata,
                            index=item.index,
                            type_folder_organization=config.type_folder_organization,
                        )
                        comp_bk_dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item.companion_path, comp_bk_dest)

                    # Backup for sidecars
                    for sc in item.sidecar_paths:
                        if sc.exists():
                            sc_bk_dest = backup_dest.with_suffix(".xmp")
                            shutil.copy2(sc, sc_bk_dest)

                stats.copied_success += 1

                # Record primary in history
                self.history.record_import(
                    file_path=item.source_path,
                    destination=dest,
                    meta=item.metadata,
                    file_hash=item.file_hash,
                )
                if item.is_pair and item.companion_path and item.companion_metadata:
                    self.history.record_import(
                        file_path=item.companion_path,
                        destination=comp_dest,
                        meta=item.companion_metadata,
                        file_hash=item.companion_hash,
                    )

                # Delete sources only after successful transfer & verification
                if config.delete_source_after_import:
                    item.source_path.unlink(missing_ok=True)
                    if item.is_pair and item.companion_path:
                        item.companion_path.unlink(missing_ok=True)
                    for sc in item.sidecar_paths:
                        sc.unlink(missing_ok=True)

            except Exception as e:
                stats.failed += 1
                item.status = "Fehler"
                item.error_msg = str(e)

        return stats
