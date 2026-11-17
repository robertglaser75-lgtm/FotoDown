"""Data model and logic for the Culling & Review tab."""

from dataclasses import dataclass, field
from datetime import datetime
import os
from pathlib import Path
import shutil
from typing import Callable, Dict, List, Optional, Tuple
from core.exif_reader import extract_metadata, MediaMetadata
from core.thumbnail import RAW_EXTENSIONS
from core.xmp_sync import read_xmp_metadata, read_xmp_workflow_info, sync_pair_xmp, XMPWorkflowInfo


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
    workflow_status: str = "UNCHECKED" # "UNCHECKED", "SOOC_OK", "TO_EDIT", "IN_PROGRESS", "EDITED"
    has_darktable_edit: bool = False
    family_album_exported: bool = False
    family_album_path: Optional[Path] = None

    @property
    def workflow_status_info(self) -> Tuple[str, str, str]:
        """Returns (label_text, badge_bg_color, symbol_icon)."""
        if self.is_rejected:
            return ("Abgelehnt", "#dc2626", "✖")
        if self.workflow_status == "SOOC_OK":
            return ("Qualität passt (SOOC)", "#059669", "📸")
        if self.workflow_status == "TO_EDIT":
            return ("Zu bearbeiten", "#d97706", "🎨")
        if self.workflow_status == "IN_PROGRESS":
            return ("In Bearbeitung (Darktable)", "#7c3aed", "⚙️")
        if self.workflow_status == "EDITED":
            return ("Bearbeitung fertig", "#0284c7", "✔")
        return ("Ungeprüft", "#475569", "⚪")

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


def count_folder_images(folder: Path) -> Tuple[int, int, int]:
    """Counts images in folder non-recursively: (total_images, raw_count, jpeg_count)."""
    if not folder or not folder.exists() or not folder.is_dir():
        return (0, 0, 0)

    total = 0
    raw_count = 0
    jpeg_count = 0
    other_exts = {".png", ".tif", ".tiff", ".heic", ".heif", ".webp"}

    try:
        with os.scandir(folder) as it:
            for entry in it:
                if entry.name.startswith("."):
                    continue
                try:
                    if not entry.is_file():
                        continue
                except OSError:
                    continue
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in RAW_EXTENSIONS:
                    raw_count += 1
                    total += 1
                elif ext in {".jpg", ".jpeg"}:
                    jpeg_count += 1
                    total += 1
                elif ext in other_exts:
                    total += 1
    except (PermissionError, OSError):
        return (0, 0, 0)

    return (total, raw_count, jpeg_count)


def check_exported_file(
    primary_path: Path,
    family_album_dir: Optional[str] = None,
    date_taken: Optional[datetime] = None,
    existing_filenames: Optional[Set[str]] = None,
    existing_subdirs: Optional[Set[str]] = None,
    month_cache: Optional[Dict[Path, Set[str]]] = None
) -> Optional[Path]:
    """Checks whether an edited or exported version of this photo exists."""
    stem = primary_path.stem
    stem_lower = stem.lower()
    folder = primary_path.parent

    # 1. Fast check for local edit suffixes via in-memory set if provided
    local_edit_names = [
        f"{stem}_edit.jpg",
        f"{stem}_dt.jpg",
        f"{stem}_export.jpg",
    ]
    for name in local_edit_names:
        if existing_filenames is not None:
            if name.lower() in existing_filenames:
                return folder / name
        else:
            cand = folder / name
            if cand.exists():
                return cand

    # Subfolder checks (darktable_exported / export) only if subfolder exists
    subfolders_to_check = []
    if existing_subdirs is not None:
        if "darktable_exported" in existing_subdirs:
            subfolders_to_check.append("darktable_exported")
        if "export" in existing_subdirs:
            subfolders_to_check.append("export")
    else:
        subfolders_to_check = ["darktable_exported", "export"]

    for sub in subfolders_to_check:
        for ext in (".jpg", ".jpeg"):
            cand = folder / sub / f"{stem}{ext}"
            if cand.exists():
                return cand

    # 2. Check in configured Familienalbum folder with in-memory caching: 0001_Unsere_Fotos/{YYYY}/{MM}
    if family_album_dir and date_taken:
        fa_root = Path(family_album_dir)
        if fa_root.exists():
            month_folder = fa_root / f"{date_taken.year:04d}" / f"{date_taken.month:02d}"
            # Cache directory entries of month folder to avoid repetitive NAS network roundtrips
            if month_cache is not None:
                if month_folder not in month_cache:
                    if month_folder.exists():
                        try:
                            month_cache[month_folder] = {e.name.lower() for e in os.scandir(month_folder) if e.is_file()}
                        except OSError:
                            month_cache[month_folder] = set()
                    else:
                        month_cache[month_folder] = set()

                m_files = month_cache[month_folder]
                for comp_ext in (".jpg", ".jpeg"):
                    target_name = f"{stem_lower}{comp_ext}"
                    if target_name in m_files:
                        return month_folder / f"{stem}{comp_ext}"
                    target_edit_name = f"{stem_lower}_edit{comp_ext}"
                    if target_edit_name in m_files:
                        return month_folder / f"{stem}_edit{comp_ext}"
            else:
                if month_folder.exists():
                    for comp_ext in (".jpg", ".jpeg", ".JPG", ".JPEG"):
                        target = month_folder / f"{stem}{comp_ext}"
                        if target.exists():
                            return target
                        target_edit = month_folder / f"{stem}_edit{comp_ext}"
                        if target_edit.exists():
                            return target_edit

    return None


def scan_culling_folder(
    folder_path: Path,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    family_album_dir: Optional[str] = None
) -> List[CullingItem]:
    """Scans target folder and groups RAW+JPG into unified CullingItems with XMP ratings & workflow status."""
    if not folder_path or not folder_path.exists() or not folder_path.is_dir():
        return []

    image_exts = {
        ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".heif", ".webp"
    } | RAW_EXTENSIONS

    raw_entries: List[Path] = []
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
                raw_entries.append(entry)
            elif ext in {".jpg", ".jpeg"}:
                jpg_candidates[stem] = entry
            else:
                other_candidates.append(entry)

    raw_stems = {p.stem.lower() for p in raw_entries}
    total_units = len(raw_entries) + sum(1 for s in jpg_candidates if s not in raw_stems) + len(other_candidates)
    if total_units == 0:
        return []

    # Fast in-memory lookup sets to eliminate redundant filesystem / NAS checks
    existing_filenames = {e.name.lower() for e in entries if e.is_file()}
    existing_subdirs = {e.name.lower() for e in entries if e.is_dir()}
    month_cache: Dict[Path, Set[str]] = {}

    items: List[CullingItem] = []
    processed_stems = set()
    current_count = 0

    # Process RAW items (pairs and multi-RAW combinations like ORF + ORI)
    for raw_p in raw_entries:
        if cancel_check and cancel_check():
            return []
        current_count += 1
        if progress_callback:
            progress_callback(current_count, total_units, raw_p.name)

        stem = raw_p.stem.lower()
        processed_stems.add(stem)
        companion_p = jpg_candidates.get(stem)
        
        # Read XMP rating and workflow status from raw or jpg
        wf = read_xmp_workflow_info(raw_p)
        if wf.rating == 0 and not wf.label and not wf.is_rejected and companion_p:
            wf2 = read_xmp_workflow_info(companion_p)
            if wf2.rating > 0 or wf2.label or wf2.is_rejected or wf2.workflow_status != "UNCHECKED":
                wf = wf2

        meta = extract_metadata(companion_p if companion_p else raw_p)
        dt = meta.date_taken if meta else None
        exp_p = check_exported_file(
            raw_p,
            family_album_dir,
            dt,
            existing_filenames=existing_filenames,
            existing_subdirs=existing_subdirs,
            month_cache=month_cache
        )

        # Automatic status detection
        final_status = wf.workflow_status
        is_exported = False
        if exp_p:
            final_status = "EDITED"
            is_exported = True
        elif wf.has_darktable_edit and final_status in ("UNCHECKED", "TO_EDIT"):
            final_status = "IN_PROGRESS"

        items.append(CullingItem(
            primary_path=raw_p,
            companion_path=companion_p,
            metadata=meta,
            rating=wf.rating,
            color_label=wf.label,
            is_rejected=wf.is_rejected,
            is_picked=(wf.rating >= 3 and not wf.is_rejected),
            workflow_status=final_status,
            has_darktable_edit=wf.has_darktable_edit,
            family_album_exported=is_exported,
            family_album_path=exp_p
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

        wf = read_xmp_workflow_info(jpg_p)
        meta = extract_metadata(jpg_p)
        dt = meta.date_taken if meta else None
        exp_p = check_exported_file(
            jpg_p,
            family_album_dir,
            dt,
            existing_filenames=existing_filenames,
            existing_subdirs=existing_subdirs,
            month_cache=month_cache
        )

        final_status = wf.workflow_status
        is_exported = False
        if exp_p:
            final_status = "EDITED"
            is_exported = True

        items.append(CullingItem(
            primary_path=jpg_p,
            companion_path=None,
            metadata=meta,
            rating=wf.rating,
            color_label=wf.label,
            is_rejected=wf.is_rejected,
            is_picked=(wf.rating >= 3 and not wf.is_rejected),
            workflow_status=final_status,
            has_darktable_edit=wf.has_darktable_edit,
            family_album_exported=is_exported,
            family_album_path=exp_p
        ))

    # Process other formats (PNG, TIFF, etc.)
    for other_p in other_candidates:
        if cancel_check and cancel_check():
            return []
        current_count += 1
        if progress_callback:
            progress_callback(current_count, total_units, other_p.name)

        wf = read_xmp_workflow_info(other_p)
        meta = extract_metadata(other_p)
        items.append(CullingItem(
            primary_path=other_p,
            companion_path=None,
            metadata=meta,
            rating=wf.rating,
            color_label=wf.label,
            is_rejected=wf.is_rejected,
            workflow_status=wf.workflow_status,
            has_darktable_edit=wf.has_darktable_edit
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
