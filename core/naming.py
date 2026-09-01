"""Filename and directory path formatting engine."""

from datetime import datetime
from pathlib import Path
import re
from typing import Dict, Optional
from .exif_reader import MediaMetadata

GERMAN_MONTHS = [
    "", "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember"
]


def sanitize_filename(name: str) -> str:
    """Removes invalid characters from filename and cleans up spaces/symbols."""
    # Replace illegal filename characters
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
    # Avoid consecutive underscores or leading/trailing dots/spaces
    cleaned = re.sub(r"_+", "_", cleaned)
    cleaned = cleaned.strip(" ._")
    return cleaned or "file"


def sanitize_path_segment(segment: str) -> str:
    """Sanitizes a single folder name segment."""
    cleaned = re.sub(r'[*?:"<>|]', "", segment)
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.strip(" ._") or "folder"


def _build_replacements(meta: MediaMetadata, index: int = 1) -> Dict[str, str]:
    """Builds a dictionary of all available template placeholders."""
    dt = meta.date_taken
    month_name = GERMAN_MONTHS[dt.month] if 1 <= dt.month <= 12 else ""
    cam = meta.formatted_camera or "UnknownCamera"
    make = re.sub(r'[\\/*?:"<>|\s]', "_", meta.camera_make.strip()) or "UnknownMake"
    model = re.sub(r'[\\/*?:"<>|\s]', "_", meta.camera_model.strip()) or "UnknownModel"

    ext_clean = meta.extension.lstrip(".").lower()
    m_type = meta.media_type

    return {
        "{YYYY}": f"{dt.year:04d}",
        "{YY}": f"{dt.year % 100:02d}",
        "{MM}": f"{dt.month:02d}",
        "{M}": f"{dt.month}",
        "{MONTH_NAME}": month_name,
        "{DD}": f"{dt.day:02d}",
        "{D}": f"{dt.day}",
        "{hh}": f"{dt.hour:02d}",
        "{mm}": f"{dt.minute:02d}",
        "{ss}": f"{dt.second:02d}",
        "{camera}": cam,
        "{make}": make,
        "{model}": model,
        "{orig_name}": meta.orig_name,
        "{ext}": ext_clean,
        "{type}": m_type,
        "{format}": m_type,
        # Sequential number tags
        "{num}": f"{index}",
        "{seq}": f"{index}",
        "{num_2}": f"{index:02d}",
        "{num:02d}": f"{index:02d}",
        "{num_3}": f"{index:03d}",
        "{num:03d}": f"{index:03d}",
        "{num_4}": f"{index:04d}",
        "{num:04d}": f"{index:04d}",
        "{num_5}": f"{index:05d}",
        "{num:05d}": f"{index:05d}",
    }


def _replace_custom_numeric_patterns(text: str, index: int) -> str:
    """Replaces custom numeric formatting like {num:06d} or {seq:04d}."""
    def repl(m):
        width_str = m.group(1)
        try:
            width = int(width_str)
            return f"{index:0{width}d}"
        except Exception:
            return m.group(0)

    # Matches {num:0X} or {seq:0X} or {num:X}
    text = re.sub(r"\{(?:num|seq):0?(\d+)d?\}", repl, text)
    return text


def format_filename(pattern: str, meta: MediaMetadata, index: int = 1) -> str:
    """Formats the target filename (with extension) using the pattern, metadata, and index."""
    replacements = _build_replacements(meta, index=index)
    result = pattern
    for key, val in replacements.items():
        result = result.replace(key, val)

    # Handle any remaining custom {num:0Xd} patterns
    result = _replace_custom_numeric_patterns(result, index=index)

    # Clean the filename part before adding extension
    clean_stem = sanitize_filename(result)
    ext = meta.extension if meta.extension.startswith(".") else f".{meta.extension}"
    return f"{clean_stem}{ext}"


def format_folder_path(pattern: str, meta: MediaMetadata, index: int = 1) -> Path:
    """Formats the relative folder path using the pattern, metadata, and index."""
    replacements = _build_replacements(meta, index=index)
    result = pattern
    for key, val in replacements.items():
        result = result.replace(key, val)

    result = _replace_custom_numeric_patterns(result, index=index)

    # Normalize slashes and sanitize segments
    normalized = result.replace("\\", "/")
    segments = [sanitize_path_segment(s) for s in normalized.split("/") if s.strip()]
    if not segments:
        return Path(".")
    return Path(*segments)


def resolve_destination(
    target_root: Path,
    folder_pattern: str,
    file_pattern: str,
    meta: MediaMetadata,
    index: int = 1,
    video_target_root: Optional[Path] = None,
    type_folder_organization: str = "same",
) -> Path:
    """Calculates full destination file path respecting video paths and RAW/JPG separation."""
    # Determine base directory
    if meta.is_video and video_target_root is not None:
        base_root = Path(video_target_root)
    else:
        base_root = Path(target_root)

    rel_folder = format_folder_path(folder_pattern, meta, index=index)

    # Apply RAW / JPG separation if not already handled by {type} tag in pattern
    if not meta.is_video and "{type}" not in folder_pattern and "{format}" not in folder_pattern:
        if type_folder_organization == "subfolders":
            rel_folder = rel_folder / meta.media_type
        elif type_folder_organization == "parent_folders":
            rel_folder = Path(meta.media_type) / rel_folder

    filename = format_filename(file_pattern, meta, index=index)
    return base_root / rel_folder / filename


def generate_sample_preview(
    file_pattern: str,
    folder_pattern: str,
    sample_meta: Optional[MediaMetadata] = None,
    sample_index: int = 1,
    type_folder_organization: str = "same",
) -> tuple[str, str]:
    """Generates preview strings for folder and filename based on patterns."""
    if sample_meta is None:
        sample_meta = MediaMetadata(
            file_path=Path("DSC_0123.JPG"),
            orig_name="DSC_0123",
            extension=".jpg",
            file_size=12582912,
            date_taken=datetime(2026, 8, 15, 14, 30, 45),
            date_source="EXIF DateTimeOriginal",
            camera_make="Sony",
            camera_model="ILCE-7M4",
            camera_name="Sony ILCE-7M4",
        )

    rel_folder = format_folder_path(folder_pattern, sample_meta, index=sample_index)
    if not sample_meta.is_video and "{type}" not in folder_pattern and "{format}" not in folder_pattern:
        if type_folder_organization == "subfolders":
            rel_folder = rel_folder / sample_meta.media_type
        elif type_folder_organization == "parent_folders":
            rel_folder = Path(sample_meta.media_type) / rel_folder

    filename = format_filename(file_pattern, sample_meta, index=sample_index)
    return str(rel_folder), filename
