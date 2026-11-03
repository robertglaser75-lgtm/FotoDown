"""Thumbnail extraction and caching helper for images, videos, and RAW files."""

import io
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageOps


RAW_EXTENSIONS = {
    ".cr2", ".cr3", ".nef", ".arw", ".dng",
    ".rw2", ".orf", ".raf", ".pef"
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mts", ".m2ts", ".avi", ".mkv"
}


def extract_raw_embedded_jpeg(raw_path: Path) -> Optional[Image.Image]:
    """Extracts the highest-resolution embedded JPEG preview from camera RAW file safely."""
    # 0. Check companion JPEG file if present
    for comp_ext in [".jpg", ".jpeg", ".JPG", ".JPEG"]:
        comp = raw_path.with_suffix(comp_ext)
        if comp.exists() and comp != raw_path:
            try:
                with Image.open(comp) as img:
                    return ImageOps.exif_transpose(img).copy()
            except Exception:
                pass

    candidates = []

    # 1. Multi-page / SubIFD check via PIL (e.g. DNG or TIFF)
    try:
        with Image.open(raw_path) as img:
            frame_count = getattr(img, "n_frames", 1)
            for f_idx in range(min(frame_count, 5)):
                try:
                    img.seek(f_idx)
                    candidates.append((img.width * img.height, ImageOps.exif_transpose(img).copy()))
                except Exception:
                    pass
    except Exception:
        pass

    # 2. Binary scan for embedded JPEGs (up to first 24MB)
    try:
        with open(raw_path, "rb") as f:
            data = f.read(24 * 1024 * 1024)

        pos = 0
        scan_count = 0
        while pos < len(data) - 4 and scan_count < 8:
            start = data.find(b"\xff\xd8\xff", pos)
            if start == -1:
                break
            scan_count += 1
            search_end = min(len(data), start + 12 * 1024 * 1024)
            chunk = data[start:search_end]
            end = chunk.rfind(b"\xff\xd9")
            if end != -1 and end > 5000:
                jpeg_bytes = chunk[:end + 2]
                try:
                    with Image.open(io.BytesIO(jpeg_bytes)) as img:
                        img.load()
                        candidates.append((img.width * img.height, ImageOps.exif_transpose(img).copy()))
                except Exception:
                    pass
            pos = start + 4

    except Exception:
        pass

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
    return None


def generate_thumbnail(path: Path, max_size: Tuple[int, int] = (480, 480)) -> Optional[Image.Image]:
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
