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
    """Extracts embedded JPEG preview thumbnail from camera RAW file safely."""
    # 1. Direct PIL open (works for TIFF-based RAWs or DNG)
    try:
        with Image.open(raw_path) as img:
            img.load()
            return img.copy()
    except Exception:
        pass

    # 2. Bounded binary scan for embedded JPEGs (first 6MB)
    try:
        with open(raw_path, "rb") as f:
            data = f.read(6 * 1024 * 1024)

        pos = 0
        candidates = []
        for _ in range(5):
            start = data.find(b"\xff\xd8\xff", pos)
            if start == -1:
                break

            chunk = data[start:start + 2000000]
            end = chunk.rfind(b"\xff\xd9")
            if end != -1 and end > 500:
                jpeg_bytes = chunk[:end + 2]
                try:
                    with Image.open(io.BytesIO(jpeg_bytes)) as img:
                        img.load()
                        candidates.append((img.width * img.height, img.copy()))
                except Exception:
                    pass
            pos = start + 4

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
    except Exception:
        pass
    return None


def generate_thumbnail(path: Path, max_size: Tuple[int, int] = (160, 160)) -> Optional[Image.Image]:
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
