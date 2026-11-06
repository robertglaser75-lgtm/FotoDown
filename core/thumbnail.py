"""Thumbnail extraction and caching helper for images, videos, and RAW files."""

import io
from pathlib import Path
import struct
from typing import List, Optional, Tuple
from PIL import Image, ImageOps

try:
    import rawpy
    HAS_RAWPY = True
except ImportError:
    HAS_RAWPY = False


RAW_EXTENSIONS = {
    ".cr2", ".cr3", ".crw", ".nef", ".nrw", ".arw", ".srf", ".sr2",
    ".dng", ".rw2", ".raw", ".orf", ".ori", ".raf", ".pef", ".srw",
    ".3fr", ".fff", ".erf", ".kdc", ".dcr", ".mrw", ".iiq", ".x3f"
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mts", ".m2ts", ".avi", ".mkv"
}


def _extract_via_rawpy(raw_path: Path) -> Optional[Image.Image]:
    """Extracts embedded thumbnail or decodes raw sensor data via rawpy (LibRaw)."""
    if not HAS_RAWPY:
        return None
    for attempt in (1, 2):
        file_obj = None
        try:
            if attempt == 1:
                target = str(raw_path)
            else:
                file_obj = open(raw_path, "rb")
                target = file_obj
            with rawpy.imread(target) as raw:
                # 1. Try embedded camera preview / thumbnail
                try:
                    thumb = raw.extract_thumb()
                    if thumb.format == rawpy.ThumbFormat.JPEG:
                        with Image.open(io.BytesIO(thumb.data)) as img:
                            return ImageOps.exif_transpose(img).copy()
                    elif thumb.format == rawpy.ThumbFormat.BITMAP:
                        img = Image.fromarray(thumb.data)
                        return ImageOps.exif_transpose(img).copy()
                except Exception:
                    pass

                # 2. Fast half-size raw demosaicing fallback
                try:
                    rgb = raw.postprocess(half_size=True, use_camera_wb=True)
                    img = Image.fromarray(rgb)
                    return ImageOps.exif_transpose(img).copy()
                except Exception:
                    pass
            break
        except Exception:
            pass
        finally:
            if file_obj:
                try:
                    file_obj.close()
                except Exception:
                    pass
    return None


def _extract_fuji_raf(raw_path: Path) -> Optional[Image.Image]:
    """Extracts embedded JPEG preview from Fujifilm RAF header."""
    try:
        with open(raw_path, "rb") as f:
            header = f.read(120)
            if header.startswith(b"FUJIFILMCCD-RAW"):
                jpg_offset = struct.unpack(">I", header[84:88])[0]
                jpg_len = struct.unpack(">I", header[88:92])[0]
                if jpg_offset > 0 and jpg_len > 0:
                    f.seek(jpg_offset)
                    jpg_data = f.read(jpg_len)
                    with Image.open(io.BytesIO(jpg_data)) as img:
                        return ImageOps.exif_transpose(img).copy()
    except Exception:
        pass
    return None


def _extract_canon_cr3(raw_path: Path) -> Optional[Image.Image]:
    """Extracts embedded JPEG preview from Canon CR3 (ISOBMFF container)."""
    try:
        file_size = raw_path.stat().st_size
        read_len = min(file_size, 32 * 1024 * 1024)
        with open(raw_path, "rb") as f:
            data = f.read(read_len)

        for marker in (b"PRVW", b"thmb"):
            idx = data.find(marker)
            if idx != -1:
                soi_idx = data.find(b"\xff\xd8\xff", idx, idx + 200)
                if soi_idx != -1:
                    with Image.open(io.BytesIO(data[soi_idx:])) as img:
                        img.load()
                        return ImageOps.exif_transpose(img).copy()
    except Exception:
        pass
    return None


def _extract_tiff_raw_preview(raw_path: Path) -> Optional[Image.Image]:
    """Extracts embedded JPEG preview from TIFF-based RAW files (CR2, NEF, ARW, DNG, PEF, ORF, ORI)."""
    candidates: List[Tuple[int, Image.Image]] = []
    try:
        with open(raw_path, "rb") as f:
            header = f.read(8)
            if len(header) < 8:
                return None
            if header.startswith(b"II\x2a\x00") or header.startswith((b"IIRO", b"IIRS")):
                endian = "<"
            elif header.startswith(b"MM\x00\x2a") or header.startswith(b"MMOR"):
                endian = ">"
            else:
                return None

            first_ifd_offset = struct.unpack(endian + "I", header[4:8])[0]
            ifd_queue = [first_ifd_offset]
            visited = set()
            file_size = raw_path.stat().st_size

            while ifd_queue and len(visited) < 15:
                offset = ifd_queue.pop(0)
                if offset in visited or offset <= 0 or offset >= file_size - 18:
                    continue
                visited.add(offset)

                f.seek(offset)
                count_bytes = f.read(2)
                if len(count_bytes) < 2:
                    break
                entry_count = struct.unpack(endian + "H", count_bytes)[0]
                if entry_count > 500:
                    continue

                strip_offsets: List[int] = []
                strip_counts: List[int] = []
                jpeg_offset = None
                jpeg_length = None

                for _ in range(entry_count):
                    entry = f.read(12)
                    if len(entry) < 12:
                        break
                    tag, tag_type, count, val_or_off = struct.unpack(endian + "HHI I", entry)

                    if tag == 0x0111:  # StripOffsets
                        if count == 1:
                            strip_offsets = [val_or_off]
                        elif count > 1 and 0 < val_or_off < file_size:
                            cur_pos = f.tell()
                            f.seek(val_or_off)
                            fmt = (endian + ("I" * count)) if tag_type == 4 else (endian + ("H" * count))
                            size_needed = count * (4 if tag_type == 4 else 2)
                            off_bytes = f.read(size_needed)
                            if len(off_bytes) == size_needed:
                                strip_offsets = list(struct.unpack(fmt, off_bytes))
                            f.seek(cur_pos)
                    elif tag == 0x0117:  # StripByteCounts
                        if count == 1:
                            strip_counts = [val_or_off]
                        elif count > 1 and 0 < val_or_off < file_size:
                            cur_pos = f.tell()
                            f.seek(val_or_off)
                            fmt = (endian + ("I" * count)) if tag_type == 4 else (endian + ("H" * count))
                            size_needed = count * (4 if tag_type == 4 else 2)
                            cnt_bytes = f.read(size_needed)
                            if len(cnt_bytes) == size_needed:
                                strip_counts = list(struct.unpack(fmt, cnt_bytes))
                            f.seek(cur_pos)
                    elif tag == 0x0201:  # JPEGInterchangeFormat (SOI offset)
                        jpeg_offset = val_or_off
                    elif tag == 0x0202:  # JPEGInterchangeFormatLength
                        jpeg_length = val_or_off
                    elif tag in (0x014a, 0x8769, 0x927c):  # SubIFDs, ExifIFD, or Olympus MakerNotes
                        if count == 1 and val_or_off not in visited:
                            ifd_queue.append(val_or_off)
                        elif count > 1 and 0 < val_or_off < file_size:
                            cur_pos = f.tell()
                            f.seek(val_or_off)
                            sub_bytes = f.read(count * 4)
                            if len(sub_bytes) == count * 4:
                                for s_off in struct.unpack(endian + ("I" * count), sub_bytes):
                                    if s_off not in visited:
                                        ifd_queue.append(s_off)
                            f.seek(cur_pos)

                next_ifd_bytes = f.read(4)
                if len(next_ifd_bytes) == 4:
                    next_ifd = struct.unpack(endian + "I", next_ifd_bytes)[0]
                    if next_ifd > 0 and next_ifd not in visited:
                        ifd_queue.append(next_ifd)

                if jpeg_offset and jpeg_offset < file_size:
                    f.seek(jpeg_offset)
                    data = f.read(jpeg_length if (jpeg_length and jpeg_offset + jpeg_length <= file_size) else 16 * 1024 * 1024)
                    if data.startswith(b"\xff\xd8"):
                        try:
                            with Image.open(io.BytesIO(data)) as img:
                                img.load()
                                candidates.append((img.width * img.height, ImageOps.exif_transpose(img).copy()))
                        except Exception:
                            pass

                elif strip_offsets and strip_counts and len(strip_offsets) == 1:
                    off = strip_offsets[0]
                    length = strip_counts[0]
                    if 0 < off < file_size and length > 500:
                        f.seek(off)
                        data = f.read(min(length, 16 * 1024 * 1024))
                        if data.startswith(b"\xff\xd8"):
                            try:
                                with Image.open(io.BytesIO(data)) as img:
                                    img.load()
                                    candidates.append((img.width * img.height, ImageOps.exif_transpose(img).copy()))
                            except Exception:
                                pass
    except Exception:
        pass

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
    return None


def _extract_binary_scan_jpeg(raw_path: Path, max_scan_bytes: int = 48 * 1024 * 1024) -> Optional[Image.Image]:
    """Scans raw file bytes for embedded JPEG images and returns the highest resolution."""
    candidates: List[Tuple[int, Image.Image]] = []
    try:
        file_size = raw_path.stat().st_size
        read_len = min(file_size, max_scan_bytes)
        with open(raw_path, "rb") as f:
            data = f.read(read_len)

        pos = 0
        while pos < len(data) - 4:
            start = data.find(b"\xff\xd8\xff", pos)
            if start == -1:
                break
            try:
                with Image.open(io.BytesIO(data[start:])) as img:
                    img.load()
                    candidates.append((img.width * img.height, ImageOps.exif_transpose(img).copy()))
                    pos = start + max(img.width * img.height // 8, 4096)
            except Exception:
                pos = start + 4
    except Exception:
        pass

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
    return None


def extract_raw_embedded_jpeg(raw_path: Path) -> Optional[Image.Image]:
    """Extracts the highest-resolution embedded JPEG preview from camera RAW files safely."""
    # 0. Check companion JPEG file if present
    for comp_ext in [".jpg", ".jpeg", ".JPG", ".JPEG"]:
        comp = raw_path.with_suffix(comp_ext)
        if comp.exists() and comp != raw_path:
            try:
                with Image.open(comp) as img:
                    return ImageOps.exif_transpose(img).copy()
            except Exception:
                pass

    # 1. Format-specific direct container extractors (fastest)
    ext = raw_path.suffix.lower()
    if ext == ".raf":
        img = _extract_fuji_raf(raw_path)
        if img:
            return img

    if ext == ".cr3":
        img = _extract_canon_cr3(raw_path)
        if img:
            return img

    if ext in {".cr2", ".nef", ".arw", ".dng", ".orf", ".ori", ".pef", ".rw2", ".srw"}:
        img = _extract_tiff_raw_preview(raw_path)
        if img and img.width * img.height >= 480 * 320:
            return img

    # 2. Multi-page / SubIFD check via PIL
    try:
        with Image.open(raw_path) as img:
            frame_count = getattr(img, "n_frames", 1)
            candidates = []
            for f_idx in range(min(frame_count, 5)):
                try:
                    img.seek(f_idx)
                    img.load()
                    candidates.append((img.width * img.height, ImageOps.exif_transpose(img).copy()))
                except Exception:
                    pass
            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                return candidates[0][1]
    except Exception:
        pass

    # 3. rawpy (LibRaw) extraction
    if HAS_RAWPY:
        img = _extract_via_rawpy(raw_path)
        if img:
            return img

    # 4. Fallback: Pure-Python binary JPEG scan
    img = _extract_binary_scan_jpeg(raw_path)
    if img:
        return img

    return None


def generate_thumbnail(path: Path, max_size: Tuple[int, int] = (320, 320)) -> Optional[Image.Image]:
    """Generates a high-quality resized thumbnail for an image or RAW file."""
    ext = path.suffix.lower()

    if ext in VIDEO_EXTENSIONS:
        return None

    pil_img: Optional[Image.Image] = None

    if ext in RAW_EXTENSIONS:
        pil_img = extract_raw_embedded_jpeg(path)

    if pil_img is None:
        try:
            with Image.open(path) as img:
                pil_img = ImageOps.exif_transpose(img)
                pil_img.thumbnail(max_size, Image.Resampling.LANCZOS)
                return pil_img.copy()
        except Exception:
            return None

    try:
        pil_img = ImageOps.exif_transpose(pil_img)
        pil_img.thumbnail(max_size, Image.Resampling.LANCZOS)
        return pil_img
    except Exception:
        return None


def load_preview_image(path: Path, max_dim: int = 2560) -> Optional[Image.Image]:
    """Loads a high-resolution preview image for single-view or quick-look."""
    ext = path.suffix.lower()
    if ext in VIDEO_EXTENSIONS:
        return None

    pil_img: Optional[Image.Image] = None
    if ext in RAW_EXTENSIONS:
        pil_img = extract_raw_embedded_jpeg(path)

    if pil_img is None:
        try:
            with Image.open(path) as img:
                pil_img = ImageOps.exif_transpose(img)
                if max(pil_img.width, pil_img.height) > max_dim:
                    pil_img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                return pil_img.copy()
        except Exception:
            return None

    try:
        if max(pil_img.width, pil_img.height) > max_dim:
            pil_img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        return pil_img
    except Exception:
        return None
