"""EXIF and metadata extractor for photos and videos."""

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import struct
from typing import Optional
from PIL import Image, ExifTags


@dataclass
class MediaMetadata:
    file_path: Path
    orig_name: str
    extension: str
    file_size: int
    date_taken: datetime
    date_source: str
    camera_make: str = ""
    camera_model: str = ""
    camera_name: str = ""
    width: Optional[int] = None
    height: Optional[int] = None

    @property
    def is_video(self) -> bool:
        return self.extension.lower() in {".mp4", ".mov", ".mts", ".m2ts", ".avi", ".mkv", ".m4v", ".wmv", ".flv"}

    @property
    def is_raw(self) -> bool:
        return self.extension.lower() in {
            ".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2",
            ".pef", ".raf", ".srw", ".3fr", ".erf", ".kdc", ".mrw", ".nrw", ".raw"
        }

    @property
    def media_type(self) -> str:
        if self.is_video:
            return "VIDEO"
        if self.is_raw:
            return "RAW"
        if self.extension.lower() in {".jpg", ".jpeg"}:
            return "JPG"
        return self.extension.lstrip(".").upper() or "IMAGE"

    @property
    def formatted_camera(self) -> str:
        """Clean camera name safe for filenames."""
        cam = self.camera_name or self.camera_model or self.camera_make
        if not cam:
            return ""
        # Remove unwanted characters
        cam = re.sub(r'[\\/*?:"<>|]', "", cam)
        cam = re.sub(r"\s+", "_", cam.strip())
        return cam


def _clean_string(value: Optional[str]) -> str:
    if not value:
        return ""
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", errors="ignore")
        except Exception:
            value = str(value)
    return str(value).replace("\x00", "").strip()


def _parse_exif_date(date_str: str) -> Optional[datetime]:
    """Parses standard EXIF date format 'YYYY:MM:DD HH:MM:SS' or ISO formats."""
    if not date_str:
        return None
    cleaned = _clean_string(date_str)
    formats = [
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y:%m:%d %H:%M",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(cleaned[:19], fmt)
        except (ValueError, TypeError):
            continue
    return None


def _get_video_creation_date(file_path: Path) -> Optional[datetime]:
    """Reads creation date from MP4 / MOV header (mvhd atom)."""
    try:
        with open(file_path, "rb") as f:
            data = f.read(1024 * 1024)  # first 1MB should contain moov/mvhd
            mvhd_idx = data.find(b"mvhd")
            if mvhd_idx != -1 and mvhd_idx + 12 <= len(data):
                version = data[mvhd_idx + 4]
                if version == 0:
                    creation_time = struct.unpack(">I", data[mvhd_idx + 8 : mvhd_idx + 12])[0]
                elif version == 1 and mvhd_idx + 20 <= len(data):
                    creation_time = struct.unpack(">Q", data[mvhd_idx + 8 : mvhd_idx + 16])[0]
                else:
                    return None
                # QuickTime epoch is Jan 1, 1904 UTC
                if creation_time > 0:
                    epoch_offset = 2082844800
                    unix_timestamp = creation_time - epoch_offset
                    if 0 < unix_timestamp < 4102444800:
                        return datetime.fromtimestamp(unix_timestamp)
    except Exception:
        pass
    return None


def _get_file_system_date(file_path: Path) -> tuple[datetime, str]:
    """Fallback: get earliest available file system timestamp (mtime / ctime)."""
    stat = file_path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime)
    ctime = datetime.fromtimestamp(stat.st_ctime)
    # On Windows st_ctime is file creation time. Take the earlier of the two.
    if ctime.year > 1975 and ctime < mtime:
        return ctime, "File Creation Time"
    return mtime, "File Modification Time"


def extract_metadata(file_path: Path, unknown_camera_label: str = "UnknownCamera") -> MediaMetadata:
    """Extracts metadata and EXIF information from an image or video file."""
    path = Path(file_path)
    file_size = path.stat().st_size
    orig_name = path.stem
    extension = path.suffix.lower()

    date_taken: Optional[datetime] = None
    date_source = "Unknown"
    camera_make = ""
    camera_model = ""
    width = None
    height = None

    # Check if image
    video_exts = {".mp4", ".mov", ".mts", ".m2ts", ".avi", ".mkv", ".m4v"}
    if extension in video_exts:
        vid_date = _get_video_creation_date(path)
        if vid_date:
            date_taken = vid_date
            date_source = "Video Header (mvhd)"
    else:
        # Try reading with Pillow
        try:
            with Image.open(path) as img:
                width, height = img.size
                exif_data = img.getexif()
                if exif_data:
                    # 0x0110 = Model, 0x010F = Make
                    camera_make = _clean_string(exif_data.get(0x010F, ""))
                    camera_model = _clean_string(exif_data.get(0x0110, ""))

                    # DateTimeOriginal is usually inside Exif IFD (0x8769) or top-level 0x9003
                    # Top-level tags:
                    date_orig_str = exif_data.get(0x9003) or exif_data.get(0x9004) or exif_data.get(0x0132)

                    # Check Exif IFD if not found
                    if not date_orig_str:
                        try:
                            ifd_exif = exif_data.get_ifd(ExifTags.IFD.Exif)
                            if ifd_exif:
                                date_orig_str = (
                                    ifd_exif.get(0x9003)
                                    or ifd_exif.get(0x9004)
                                    or ifd_exif.get(0x0132)
                                )
                        except Exception:
                            pass

                    if date_orig_str:
                        parsed = _parse_exif_date(str(date_orig_str))
                        if parsed:
                            date_taken = parsed
                            date_source = "EXIF DateTimeOriginal"
        except Exception:
            # Not a readable image by Pillow or raw without standard Pillow decoder
            pass

    # Fallback to filesystem timestamps if no EXIF date found
    if date_taken is None:
        date_taken, date_source = _get_file_system_date(path)

    # Combine camera make and model nicely
    camera_name = ""
    if camera_make and camera_model:
        if camera_model.lower().startswith(camera_make.lower()):
            camera_name = camera_model
        else:
            camera_name = f"{camera_make} {camera_model}"
    elif camera_model:
        camera_name = camera_model
    elif camera_make:
        camera_name = camera_make
    else:
        camera_name = unknown_camera_label

    return MediaMetadata(
        file_path=path,
        orig_name=orig_name,
        extension=extension,
        file_size=file_size,
        date_taken=date_taken,
        date_source=date_source,
        camera_make=camera_make,
        camera_model=camera_model,
        camera_name=camera_name,
        width=width,
        height=height,
    )
