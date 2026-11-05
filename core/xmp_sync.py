"""XMP sidecar reader and writer for ratings, color labels, and rejection flags.

Supports Adobe and Darktable compatible namespaces:
- xmp:Rating (0-5)
- xmp:Label (Red, Yellow, Green, Blue, Purple)
- Darktable specific tags / flags
"""

from pathlib import Path
import re
from typing import Optional, Tuple
import xml.etree.ElementTree as ET


DEFAULT_XMP_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="FotoDown XMP Core">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/"
    xmp:Rating="{rating}"
    xmp:Label="{label}">
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
"""


def get_sidecar_path(media_path: Path) -> Path:
    """Returns standard sidecar path (media_path.xmp)."""
    return media_path.with_name(f"{media_path.name}.xmp")


def read_xmp_metadata(media_path: Path) -> Tuple[int, str, bool]:
    """Reads rating (0-5), color label ('', 'Red', etc.), and reject flag from sidecar.
    
    Returns:
        (rating, label, is_rejected)
    """
    sidecar = get_sidecar_path(media_path)
    if not sidecar.exists():
        # Also check alternative sidecar naming without original extension (e.g. img.xmp instead of img.cr3.xmp)
        alt_sidecar = media_path.with_suffix(".xmp")
        if alt_sidecar.exists():
            sidecar = alt_sidecar
        else:
            return 0, "", False

    try:
        content = sidecar.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return 0, "", False

    rating = 0
    label = ""
    is_rejected = False

    # 1. Regex search for xmp:Rating
    m_rating = re.search(r'xmp:Rating\s*=\s*["\'](-?\d+)["\']', content)
    if not m_rating:
        m_rating = re.search(r'<xmp:Rating>(\d+)</xmp:Rating>', content)
    if m_rating:
        try:
            val = int(m_rating.group(1))
            if val == -1:
                is_rejected = True
                rating = 0
            else:
                rating = max(0, min(5, val))
        except ValueError:
            pass

    # 2. Regex search for xmp:Label
    m_label = re.search(r'xmp:Label\s*=\s*["\']([^"\']+)["\']', content)
    if not m_label:
        m_label = re.search(r'<xmp:Label>([^<]+)</xmp:Label>', content)
    if m_label:
        label = m_label.group(1).strip()

    # 3. Check for Reject indicators (Darktable / Lightroom)
    if "darktable:change_timestamp" in content and "reject" in content.lower():
        is_rejected = True

    return rating, label, is_rejected


def write_xmp_metadata(media_path: Path, rating: int = 0, label: str = "", is_rejected: bool = False) -> Path:
    """Writes rating, label, and rejection status into the .xmp sidecar file.
    
    If the sidecar already exists, updates attributes while preserving other metadata.
    """
    sidecar = get_sidecar_path(media_path)

    # Effective rating value: in Lightroom/standard XMP, -1 means Rejected
    rating_val = -1 if is_rejected else max(0, min(5, rating))

    if sidecar.exists():
        try:
            content = sidecar.read_text(encoding="utf-8", errors="ignore")
            # Update or inject xmp:Rating
            if re.search(r'xmp:Rating\s*=\s*["\']-?\d+["\']', content):
                content = re.sub(r'xmp:Rating\s*=\s*["\']-?\d+["\']', f'xmp:Rating="{rating_val}"', content)
            elif "<rdf:Description" in content:
                content = re.sub(r'<rdf:Description', f'<rdf:Description xmp:Rating="{rating_val}"', content, count=1)

            # Update or inject xmp:Label
            if label:
                if re.search(r'xmp:Label\s*=\s*["\'][^"\']*["\']', content):
                    content = re.sub(r'xmp:Label\s*=\s*["\'][^"\']*["\']', f'xmp:Label="{label}"', content)
                elif "<rdf:Description" in content:
                    content = re.sub(r'<rdf:Description', f'<rdf:Description xmp:Label="{label}"', content, count=1)
            else:
                # Remove label attribute if empty
                content = re.sub(r'\s*xmp:Label\s*=\s*["\'][^"\']*["\']', '', content)

            sidecar.write_text(content, encoding="utf-8")
            return sidecar
        except Exception:
            pass

    # New sidecar generation
    new_xml = DEFAULT_XMP_TEMPLATE.format(
        rating=rating_val,
        label=label
    )
    sidecar.write_text(new_xml, encoding="utf-8")
    return sidecar


def sync_pair_xmp(primary_path: Path, companion_path: Optional[Path], rating: int = 0, label: str = "", is_rejected: bool = False) -> None:
    """Synchronizes XMP rating, label, and rejection for both files in a RAW+JPG pair."""
    write_xmp_metadata(primary_path, rating, label, is_rejected)
    if companion_path and companion_path.exists() and companion_path != primary_path:
        write_xmp_metadata(companion_path, rating, label, is_rejected)

