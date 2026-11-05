"""Data model and logic for the Culling & Review tab."""

from dataclasses import dataclass, field
from datetime import datetime
import os
from pathlib import Path
import shutil
from typing import Callable, Dict, List, Optional, Tuple
from core.exif_reader import extract_metadata, MediaMetadata
from core.thumbnail import RAW_EXTENSIONS
from core.xmp_sync import read_xmp_metadata, sync_pair_xmp


@dataclass
class CullingItem:
    """Represents a logical photo entity in the culling workflow (can be RAW+JPG pair)."""
    primary_path: Path
    companion_path: Optional[Path] = None
    sidecar_path: Optional[Path] = None
    metadata: Optional[MediaMetadata] = None
    rating: int = 0                  # 0 to 5 stars
    color_label: str = ""            # '', 'Red', 'Yellow', 'Green', 'Blue', 'Purple'
    is_rejected: bool = False        # Rejected (X)
    is_picked: bool = False          # Picked (P)
    selected: bool = False           # UI checkbox / selection
    active_view_mode: str = "AUTO"   # "AUTO" (prefers JPG for display speed), "RAW", "JPG"

    @property
    def display_name(self) -> str:
        return self.primary_path.name

    @property
    def is_pair(self) -> bool:
        return self.companion_path is not None and self.companion_path.exists()

    @property
    def raw_path(self) -> Optional[Path]:
        if self.primary_path.suffix.lower() in RAW_EXTENSIONS:
            return self.primary_path
        if self.companion_path and self.companion_path.suffix.lower() in RAW_EXTENSIONS:
            return self.companion_path
        return None

    @property
    def jpeg_path(self) -> Optional[Path]:
        if self.primary_path.suffix.lower() in {".jpg", ".jpeg"}:
            return self.primary_path
        if self.companion_path and self.companion_path.suffix.lower() in {".jpg", ".jpeg"}:
            return self.companion_path
        return None

    @property
    def current_display_path(self) -> Path:
        """Determines which file to display based on active view mode."""
        if self.active_view_mode == "RAW" and self.raw_path:
            return self.raw_path
        if self.active_view_mode == "JPG" and self.jpeg_path:
            return self.jpeg_path
        # Auto mode: Prefer companion JPG if available for instant display, else primary
        if self.jpeg_path:
            return self.jpeg_path
        return self.primary_path

    @property
    def all_files(self) -> List[Path]:
        """Returns all files belonging to this logical unit (primary, companion, sidecar)."""
        files = [self.primary_path]
        if self.companion_path and self.companion_path.exists():
            files.append(self.companion_path)
        # Check standard sidecars
        for p in (self.primary_path, self.companion_path):
            if p:
                sc1 = p.with_name(f"{p.name}.xmp")
                if sc1.exists() and sc1 not in files:
                    files.append(sc1)
                sc2 = p.with_suffix(".xmp")
                if sc2.exists() and sc2 not in files:
                    files.append(sc2)
        return files


def scan_culling_folder(
    folder_path: Path,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None
) -> List[CullingItem]:
    """Scans target folder and groups RAW+JPG into unified CullingItems with XMP ratings."""
    if not folder_path or not folder_path.exists() or not folder_path.is_dir():
        return []

    image_exts = {
        ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".heif",
        ".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2", ".pef", ".raf", ".srw"
    }

    raw_candidates: Dict[str, Path] = {}
    jpg_candidates: Dict[str, Path] = {}
    other_candidates: List[Path] = []

    try:
        entries = sorted(list(folder_path.iterdir()), key=lambda p: p.name.lower())
    except Exception:
        return []

    for entry in entries:
        if cancel_check and cancel_check():
            return []
        if not entry.is_file():
            continue
        ext = entry.suffix.lower()
        if ext in image_exts:
            stem = entry.stem.lower()
            if ext in RAW_EXTENSIONS:
                raw_candidates[stem] = entry
            elif ext in {".jpg", ".jpeg"}:
                jpg_candidates[stem] = entry
            else:
                other_candidates.append(entry)

    total_units = len(raw_candidates) + sum(1 for s in jpg_candidates if s not in raw_candidates) + len(other_candidates)
    if total_units == 0:
        return []

    items: List[CullingItem] = []
    processed_stems = set()
    current_count = 0

    # Process pairs first
    for stem, raw_p in raw_candidates.items():
        if cancel_check and cancel_check():
            return []
        current_count += 1
        if progress_callback:
            progress_callback(current_count, total_units, raw_p.name)

        processed_stems.add(stem)
        companion_p = jpg_candidates.get(stem)
        
        # Read XMP rating from raw or jpg
        rating, label, is_rejected = read_xmp_metadata(raw_p)
        if rating == 0 and not label and not is_rejected and companion_p:
            r2, l2, rej2 = read_xmp_metadata(companion_p)
            if r2 > 0 or l2 or rej2:
                rating, label, is_rejected = r2, l2, rej2

        meta = extract_metadata(companion_p if companion_p else raw_p)
        items.append(CullingItem(
            primary_path=raw_p,
            companion_path=companion_p,
            metadata=meta,
            rating=rating,
            color_label=label,
            is_rejected=is_rejected,
            is_picked=(rating >= 3 and not is_rejected)
        ))

    # Process standalone JPEGs
    for stem, jpg_p in jpg_candidates.items():
        if stem in processed_stems:
            continue
        if cancel_check and cancel_check():
            return []
        current_count += 1
        if progress_callback:
            progress_callback(current_count, total_units, jpg_p.name)

        rating, label, is_rejected = read_xmp_metadata(jpg_p)
        meta = extract_metadata(jpg_p)
        items.append(CullingItem(
            primary_path=jpg_p,
            companion_path=None,
            metadata=meta,
            rating=rating,
            color_label=label,
            is_rejected=is_rejected,
            is_picked=(rating >= 3 and not is_rejected)
        ))

    # Process other formats (PNG, TIFF, etc.)
    for other_p in other_candidates:
        if cancel_check and cancel_check():
            return []
        current_count += 1
        if progress_callback:
            progress_callback(current_count, total_units, other_p.name)

        rating, label, is_rejected = read_xmp_metadata(other_p)
        meta = extract_metadata(other_p)
        items.append(CullingItem(
            primary_path=other_p,
            companion_path=None,
            metadata=meta,
            rating=rating,
            color_label=label,
            is_rejected=is_rejected
        ))

    # Sort by date taken or filename
    items.sort(key=lambda it: (it.metadata.date_taken if (it.metadata and it.metadata.date_taken) else datetime.min, it.primary_path.name))
    return items


def execute_reject_action(items: List[CullingItem], action: str = "move_folder", folder_name: str = "_Abgelehnt") -> Tuple[int, str]:
    """Executes configured reject action on all rejected items.
    
    Actions:
    - 'move_folder': Moves all related files into folder_name subfolder
    - 'trash': Sends files to system recycle bin or deletes them
    - 'flag_only': No disk changes, already marked in XMP
    """
    rejected_items = [it for it in items if it.is_rejected]
    if not rejected_items:
        return 0, "Keine abgelehnten Fotos vorhanden."

    if action == "flag_only":
        return len(rejected_items), f"{len(rejected_items)} Foto(s) in Metadaten als abgelehnt markiert."

    count = 0
    errors = []

    if action == "move_folder":
        for it in rejected_items:
            parent = it.primary_path.parent
            dest_dir = parent / folder_name
            dest_dir.mkdir(parents=True, exist_ok=True)
            for f in it.all_files:
                if f.exists():
                    try:
                        shutil.move(str(f), str(dest_dir / f.name))
                    except Exception as e:
                        errors.append(f"{f.name}: {e}")
            count += 1
        msg = f"{count} abgelehnte Foto-Einheiten nach '{folder_name}/' verschoben."
        if errors:
            msg += f"\nFehler bei {len(errors)} Datei(en)."
        return count, msg

    if action == "trash":
        try:
            # Optional send2trash if available, else permanent delete
            from send2trash import send2trash
            has_send2trash = True
        except ImportError:
            has_send2trash = False

        for it in rejected_items:
            for f in it.all_files:
                if f.exists():
                    try:
                        if has_send2trash:
                            send2trash(str(f))
                        else:
                            f.unlink()
                    except Exception as e:
                        errors.append(f"{f.name}: {e}")
            count += 1
        msg = f"{count} abgelehnte Foto-Einheiten gelöscht."
        if errors:
            msg += f"\nFehler bei {len(errors)} Datei(en)."
        return count, msg

    return 0, "Unbekannte Aktion."
