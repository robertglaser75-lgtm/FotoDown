"""XMP sidecar reader and writer for ratings, color labels, and rejection flags.

Supports Adobe and Darktable compatible namespaces:
- xmp:Rating (0-5)
- xmp:Label (Red, Yellow, Green, Blue, Purple)
- Darktable specific tags / flags
"""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Optional, Tuple


DEFAULT_XMP_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Vitrina XMP Core">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/"
    xmlns:vitrina="http://vitrina.app/1.0/"
    xmlns:fotodown="http://fotodown.app/1.0/"
    xmp:Rating="{rating}"
    xmp:Label="{label}"
    vitrina:WorkflowStatus="{workflow_status}"
    fotodown:WorkflowStatus="{workflow_status}">
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
"""


@dataclass
class XMPWorkflowInfo:
    rating: int = 0
    label: str = ""
    is_rejected: bool = False
    workflow_status: str = "UNCHECKED"  # UNCHECKED, SOOC_OK, TO_EDIT, IN_PROGRESS, EDITED
    has_darktable_edit: bool = False


def get_sidecar_path(media_path: Path) -> Path:
    """Returns standard sidecar path (media_path.xmp)."""
    return media_path.with_name(f"{media_path.name}.xmp")


def read_xmp_workflow_info(media_path: Path) -> XMPWorkflowInfo:
    """Reads comprehensive rating, rejection, and workflow status from XMP sidecar."""
    sidecar = get_sidecar_path(media_path)
    if not sidecar.exists():
        alt_sidecar = media_path.with_suffix(".xmp")
        if alt_sidecar.exists():
            sidecar = alt_sidecar
        else:
            return XMPWorkflowInfo()

    try:
        content = sidecar.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return XMPWorkflowInfo()

    rating = 0
    label = ""
    is_rejected = False
    workflow_status = "UNCHECKED"
    has_darktable_edit = False

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

    # 4. Check for Darktable edit history
    if "darktable:history_end" in content or "darktable:operation" in content or "xmlns:darktable=" in content:
        # Check if there is actual editing beyond default raw import
        m_hist = re.search(r'darktable:history_end\s*=\s*["\'](\d+)["\']', content)
        if m_hist:
            try:
                if int(m_hist.group(1)) > 0:
                    has_darktable_edit = True
            except ValueError:
                pass
        else:
            has_darktable_edit = True

    # 5. Check vitrina:WorkflowStatus or fotodown:WorkflowStatus
    m_wf = re.search(r'(?:vitrina|fotodown):WorkflowStatus\s*=\s*["\']([^"\']+)["\']', content)
    if not m_wf:
        m_wf = re.search(r'<(?:vitrina|fotodown):WorkflowStatus>([^<]+)</(?:vitrina|fotodown):WorkflowStatus>', content)
    if m_wf:
        workflow_status = m_wf.group(1).strip().upper()
    elif has_darktable_edit:
        workflow_status = "IN_PROGRESS"

    return XMPWorkflowInfo(
        rating=rating,
        label=label,
        is_rejected=is_rejected,
        workflow_status=workflow_status,
        has_darktable_edit=has_darktable_edit
    )


def read_xmp_metadata(media_path: Path) -> Tuple[int, str, bool]:
    """Reads rating (0-5), color label ('', 'Red', etc.), and reject flag from sidecar."""
    info = read_xmp_workflow_info(media_path)
    return info.rating, info.label, info.is_rejected


def write_xmp_metadata(
    media_path: Path,
    rating: int = 0,
    label: str = "",
    is_rejected: bool = False,
    workflow_status: str = ""
) -> Path:
    """Writes rating, label, rejection status, and workflow status into the .xmp sidecar file."""
    sidecar = get_sidecar_path(media_path)
    rating_val = -1 if is_rejected else max(0, min(5, rating))

    if sidecar.exists():
        try:
            content = sidecar.read_text(encoding="utf-8", errors="ignore")

            # Ensure vitrina and fotodown namespaces exist
            if "xmlns:vitrina=" not in content and "<rdf:Description" in content:
                content = re.sub(
                    r'<rdf:Description',
                    '<rdf:Description xmlns:vitrina="http://vitrina.app/1.0/" xmlns:fotodown="http://fotodown.app/1.0/"',
                    content,
                    count=1
                )
            elif "xmlns:fotodown=" not in content and "<rdf:Description" in content:
                content = re.sub(
                    r'<rdf:Description',
                    '<rdf:Description xmlns:fotodown="http://fotodown.app/1.0/"',
                    content,
                    count=1
                )

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
                content = re.sub(r'\s*xmp:Label\s*=\s*["\'][^"\']*["\']', '', content)

            # Update or inject vitrina:WorkflowStatus and fotodown:WorkflowStatus
            if workflow_status:
                if re.search(r'vitrina:WorkflowStatus\s*=\s*["\'][^"\']*["\']', content):
                    content = re.sub(r'vitrina:WorkflowStatus\s*=\s*["\'][^"\']*["\']', f'vitrina:WorkflowStatus="{workflow_status}"', content)
                elif "<rdf:Description" in content:
                    content = re.sub(r'<rdf:Description', f'<rdf:Description vitrina:WorkflowStatus="{workflow_status}"', content, count=1)

                if re.search(r'fotodown:WorkflowStatus\s*=\s*["\'][^"\']*["\']', content):
                    content = re.sub(r'fotodown:WorkflowStatus\s*=\s*["\'][^"\']*["\']', f'fotodown:WorkflowStatus="{workflow_status}"', content)
                elif "<rdf:Description" in content:
                    content = re.sub(r'<rdf:Description', f'<rdf:Description fotodown:WorkflowStatus="{workflow_status}"', content, count=1)

            sidecar.write_text(content, encoding="utf-8")
            return sidecar
        except Exception:
            pass

    # New sidecar generation
    new_xml = DEFAULT_XMP_TEMPLATE.format(
        rating=rating_val,
        label=label,
        workflow_status=workflow_status
    )
    sidecar.write_text(new_xml, encoding="utf-8")
    return sidecar


def sync_pair_xmp(
    primary_path: Path,
    companion_path: Optional[Path],
    rating: int = 0,
    label: str = "",
    is_rejected: bool = False,
    workflow_status: str = ""
) -> None:
    """Synchronizes XMP rating, label, rejection, and workflow status for both files in a RAW+JPG pair."""
    write_xmp_metadata(primary_path, rating, label, is_rejected, workflow_status)
    if companion_path and companion_path.exists() and companion_path != primary_path:
        write_xmp_metadata(companion_path, rating, label, is_rejected, workflow_status)

