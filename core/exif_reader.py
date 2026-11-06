"""EXIF and metadata extractor for photos and videos."""

from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
import os
from pathlib import Path
import re
import struct
from typing import Optional, Tuple
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
    # Technical shooting parameters
    f_number: Optional[float] = None
    exposure_time: Optional[str] = None
    iso: Optional[int] = None
    focal_length: Optional[float] = None
    lens_model: str = ""
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    orientation: int = 1

    @property
    def is_video(self) -> bool:
        return self.extension.lower() in {".mp4", ".mov", ".mts", ".m2ts", ".avi", ".mkv", ".m4v", ".wmv", ".flv"}

    @property
    def is_raw(self) -> bool:
        return self.extension.lower() in {
            ".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".ori", ".rw2",
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
        cam = re.sub(r'[\\/*?:"<>|]', "", cam)
        cam = re.sub(r"\s+", "_", cam.strip())
        return cam

    @property
    def formatted_exposure(self) -> str:
        parts = []
        if self.f_number:
            parts.append(f"ƒ/{self.f_number:.1f}")
        if self.exposure_time:
            if isinstance(self.exposure_time, (int, float)):
                if 0 < self.exposure_time < 1:
                    denom = round(1.0 / self.exposure_time)
                    parts.append(f"1/{denom}s")
                else:
                    sec = f"{self.exposure_time:.1f}" if self.exposure_time % 1 else f"{int(self.exposure_time)}"
                    parts.append(f"{sec}s")
            else:
                parts.append(f"{self.exposure_time}s")
        if self.iso:
            parts.append(f"ISO {self.iso}")
        if self.focal_length:
            parts.append(f"{self.focal_length:.0f}mm")
        return " | ".join(parts) if parts else "-"

    @property
    def formatted_dimensions(self) -> str:
        if self.width and self.height:
            mp = (self.width * self.height) / 1_000_000
            return f"{self.width} × {self.height} ({mp:.1f} MP)"
        return "-"

    @property
    def formatted_gps(self) -> str:
        if self.gps_lat is not None and self.gps_lon is not None:
            lat_dir = "N" if self.gps_lat >= 0 else "S"
            lon_dir = "E" if self.gps_lon >= 0 else "W"
            return f"{abs(self.gps_lat):.5f}° {lat_dir}, {abs(self.gps_lon):.5f}° {lon_dir}"
        return ""


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


def _format_exposure_time(val) -> Optional[str]:
    """Formats exposure time into human-friendly string like '1/250' or '2.5'."""
    try:
        f_val = float(val)
        if f_val <= 0:
            return None
        if f_val < 0.5:
            reciprocal = round(1.0 / f_val)
            return f"1/{reciprocal}"
        if f_val.is_integer():
            return f"{int(f_val)}"
        return f"{f_val:.1f}"
    except Exception:
        return str(val) if val else None


def _convert_gps_coordinate(coord_tuple, ref_str: str) -> Optional[float]:
    """Converts EXIF GPS coordinate tuple (degrees, minutes, seconds) to decimal float."""
    try:
        d = float(coord_tuple[0])
        m = float(coord_tuple[1])
        s = float(coord_tuple[2])
        dec = d + (m / 60.0) + (s / 3600.0)
        if ref_str and ref_str.upper() in ("S", "W"):
            dec = -dec
        return dec
    except Exception:
        return None


def _get_video_creation_date(file_path: Path) -> Optional[datetime]:
    """Reads creation date from MP4 / MOV header (mvhd atom)."""
    try:
        with open(file_path, "rb") as f:
            data = f.read(1024 * 1024)
            mvhd_idx = data.find(b"mvhd")
            if mvhd_idx != -1 and mvhd_idx + 12 <= len(data):
                version = data[mvhd_idx + 4]
                if version == 0:
                    creation_time = struct.unpack(">I", data[mvhd_idx + 8 : mvhd_idx + 12])[0]
                elif version == 1 and mvhd_idx + 20 <= len(data):
                    creation_time = struct.unpack(">Q", data[mvhd_idx + 8 : mvhd_idx + 16])[0]
                else:
                    return None
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
    f_number = None
    exposure_time = None
    iso = None
    focal_length = None
    lens_model = ""
    gps_lat = None
    gps_lon = None
    orientation = 1

    video_exts = {".mp4", ".mov", ".mts", ".m2ts", ".avi", ".mkv", ".m4v"}
    if extension in video_exts:
        vid_date = _get_video_creation_date(path)
        if vid_date:
            date_taken = vid_date
            date_source = "Video Header (mvhd)"
    else:
        try:
            with Image.open(path) as img:
                width, height = img.size
                exif_data = img.getexif()
                if exif_data:
                    camera_make = _clean_string(exif_data.get(0x010F, ""))
                    camera_model = _clean_string(exif_data.get(0x0110, ""))
                    orientation = int(exif_data.get(0x0112, 1) or 1)

                    date_orig_str = exif_data.get(0x9003) or exif_data.get(0x9004) or exif_data.get(0x0132)

                    # Inspect Exif IFD for detailed shooting tags
                    try:
                        ifd_exif = exif_data.get_ifd(ExifTags.IFD.Exif)
                        if ifd_exif:
                            if not date_orig_str:
                                date_orig_str = (
                                    ifd_exif.get(0x9003)
                                    or ifd_exif.get(0x9004)
                                    or ifd_exif.get(0x0132)
                                )

                            # FNumber (0x829D)
                            raw_f = ifd_exif.get(0x829D)
                            if raw_f:
                                f_number = float(raw_f)

                            # ExposureTime (0x829A)
                            raw_exp = ifd_exif.get(0x829A)
                            if raw_exp:
                                exposure_time = _format_exposure_time(raw_exp)

                            # ISOSpeedRatings (0x8827)
                            raw_iso = ifd_exif.get(0x8827)
                            if raw_iso:
                                iso = int(raw_iso) if isinstance(raw_iso, (int, float)) else int(raw_iso[0])

                            # FocalLength (0x920A)
                            raw_fl = ifd_exif.get(0x920A)
                            if raw_fl:
                                focal_length = float(raw_fl)

                            # LensModel (0xA434)
                            lens_model = _clean_string(ifd_exif.get(0xA434, ""))
                    except Exception:
                        pass

                    # Inspect GPS IFD
                    try:
                        ifd_gps = exif_data.get_ifd(ExifTags.IFD.GPSInfo)
                        if ifd_gps:
                            lat_tuple = ifd_gps.get(2)
                            lat_ref = ifd_gps.get(1, "N")
                            lon_tuple = ifd_gps.get(4)
                            lon_ref = ifd_gps.get(3, "E")
                            if lat_tuple and lon_tuple:
                                gps_lat = _convert_gps_coordinate(lat_tuple, str(lat_ref))
                                gps_lon = _convert_gps_coordinate(lon_tuple, str(lon_ref))
                    except Exception:
                        pass

                    if date_orig_str:
                        parsed = _parse_exif_date(str(date_orig_str))
                        if parsed:
                            date_taken = parsed
                            date_source = "EXIF DateTimeOriginal"
        except Exception:
            pass

    if date_taken is None:
        date_taken, date_source = _get_file_system_date(path)

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
        f_number=f_number,
        exposure_time=exposure_time,
        iso=iso,
        focal_length=focal_length,
        lens_model=lens_model,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        orientation=orientation,
    )
