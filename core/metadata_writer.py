"""IPTC and Copyright metadata writer (XMP sidecar generation and EXIF tagging)."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union
import xml.etree.ElementTree as ET


def format_copyright_template(
    template: str,
    creator: str,
    date_taken: Optional[Union[datetime, int]] = None
) -> str:
    """Replaces {YYYY}, {year}, {creator}, and {author} placeholders in copyright template."""
    if isinstance(date_taken, datetime):
        year_str = str(date_taken.year)
    elif isinstance(date_taken, int):
        year_str = str(date_taken)
    else:
        year_str = str(datetime.now().year)

    res = template.replace("{YYYY}", year_str).replace("{year}", year_str).replace("{YEAR}", year_str)
    res = res.replace("{creator}", creator).replace("{CREATOR}", creator)
    res = res.replace("{author}", creator).replace("{AUTHOR}", creator)
    return res.strip()


def generate_xmp_content(
    creator: str = "",
    copyright_notice: str = "",
    keywords: Optional[List[str]] = None,
) -> str:
    """Generates standard Adobe XMP / Dublin Core XML string."""
    creator_tag = ""
    if creator:
        creator_tag = f"""      <dc:creator>
        <rdf:Seq>
          <rdf:li>{creator}</rdf:li>
        </rdf:Seq>
      </dc:creator>"""

    rights_tag = ""
    if copyright_notice:
        rights_tag = f"""      <dc:rights>
        <rdf:Alt>
          <rdf:li xml:lang="x-default">{copyright_notice}</rdf:li>
        </rdf:Alt>
      </dc:rights>
      <xmpRights:Marked>True</xmpRights:Marked>"""

    subject_tag = ""
    if keywords:
        kw_items = "\n".join(f"          <rdf:li>{k.strip()}</rdf:li>" for k in keywords if k.strip())
        if kw_items:
            subject_tag = f"""      <dc:subject>
        <rdf:Bag>
{kw_items}
        </rdf:Bag>
      </dc:subject>"""

    xmp = f"""<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
        xmlns:dc="http://purl.org/dc/elements/1.1/"
        xmlns:xmpRights="http://ns.adobe.com/xap/1.0/rights/">
{creator_tag}
{rights_tag}
{subject_tag}
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""
    return xmp


def inject_metadata_sidecar(
    target_path: Path,
    creator: str,
    copyright_template: str,
    keywords_str: str = "",
    date_taken: Optional[Union[datetime, int]] = None,
) -> Path:
    """Creates or updates a matching .xmp sidecar for the imported media file."""
    xmp_path = target_path.with_suffix(".xmp")
    copyright_notice = format_copyright_template(copyright_template, creator, date_taken)
    keywords_list = [k.strip() for k in keywords_str.split(",") if k.strip()]

    xmp_content = generate_xmp_content(
        creator=creator.strip(),
        copyright_notice=copyright_notice,
        keywords=keywords_list
    )
    xmp_path.write_text(xmp_content, encoding="utf-8")
    return xmp_path
