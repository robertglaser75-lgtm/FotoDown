"""External application detection and launch helper for Darktable and Topaz Photo."""

import os
from pathlib import Path
import platform
import shutil
import subprocess
from typing import List, Optional, Tuple


def find_darktable() -> Optional[Path]:
    """Finds Darktable executable on Windows or Linux."""
    system = platform.system().lower()
    if system == "windows":
        candidates = [
            Path(r"C:\Program Files\darktable\bin\darktable.exe"),
            Path(r"C:\Program Files (x86)\darktable\bin\darktable.exe"),
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "darktable" / "bin" / "darktable.exe",
        ]
        for c in candidates:
            if c.exists():
                return c
        # Search PATH
        which = shutil.which("darktable")
        if which:
            return Path(which)
    else:
        # Linux
        which = shutil.which("darktable")
        if which:
            return Path(which)
        candidates = [
            Path("/usr/bin/darktable"),
            Path("/usr/local/bin/darktable"),
            Path("/var/lib/flatpak/exports/bin/org.darktable.Darktable"),
        ]
        for c in candidates:
            if c.exists():
                return c
    return None


def find_topaz_photo() -> Optional[Path]:
    """Finds Topaz Photo executable on Windows or Linux."""
    system = platform.system().lower()
    if system == "windows":
        candidates = [
            Path(r"C:\Program Files\Topaz Labs LLC\Topaz Photo\Topaz Photo.exe"),
            Path(r"C:\Program Files\Topaz Labs LLC\Topaz Photo AI\Topaz Photo AI.exe"),
            Path(r"C:\Program Files\Topaz Labs LLC\Topaz Photo\tpai.exe"),
        ]
        for c in candidates:
            if c.exists():
                return c
        which = shutil.which("Topaz Photo") or shutil.which("tpai")
        if which:
            return Path(which)
    else:
        which = shutil.which("topazphoto") or shutil.which("tpai")
        if which:
            return Path(which)
    return None


def launch_darktable(raw_paths: List[Path], custom_exe: Optional[str] = None) -> Tuple[bool, str]:
    """Launches Darktable with the specified RAW image files.
    
    Filters list to ensure only RAW files are passed.
    """
    if not raw_paths:
        return False, "Keine RAW-Dateien zum Übergeben ausgewählt."

    exe_path = Path(custom_exe) if (custom_exe and Path(custom_exe).exists()) else find_darktable()
    if not exe_path or not exe_path.exists():
        return False, "Darktable konnte nicht gefunden werden. Bitte Installationspfad in den Einstellungen prüfen."

    # Filter to only existing RAW files
    from core.thumbnail import RAW_EXTENSIONS
    valid_raws = [p for p in raw_paths if p.suffix.lower() in RAW_EXTENSIONS and p.exists()]
    if not valid_raws:
        return False, "Keine gültigen RAW-Dateien in der Auswahl gefunden."

    cmd = [str(exe_path)] + [str(p) for p in valid_raws]
    try:
        # Launch detached from current process
        if platform.system().lower() == "windows":
            subprocess.Popen(cmd, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            subprocess.Popen(cmd, start_new_session=True)
        return True, f"Darktable mit {len(valid_raws)} RAW-Datei(en) gestartet."
    except Exception as e:
        return False, f"Fehler beim Starten von Darktable: {e}"


def launch_topaz_photo(jpeg_paths: List[Path], custom_exe: Optional[str] = None) -> Tuple[bool, str]:
    """Launches Topaz Photo with the specified JPEG image files.
    
    Filters list to ensure only JPEG files are passed.
    """
    if not jpeg_paths:
        return False, "Keine JPEG-Dateien zum Übergeben ausgewählt."

    exe_path = Path(custom_exe) if (custom_exe and Path(custom_exe).exists()) else find_topaz_photo()
    if not exe_path or not exe_path.exists():
        return False, "Topaz Photo konnte nicht gefunden werden. Bitte Installationspfad in den Einstellungen prüfen."

    # Filter to only existing JPEG files
    valid_jpegs = [p for p in jpeg_paths if p.suffix.lower() in {".jpg", ".jpeg"} and p.exists()]
    if not valid_jpegs:
        return False, "Keine gültigen JPEG-Dateien in der Auswahl gefunden."

    cmd = [str(exe_path)] + [str(p) for p in valid_jpegs]
    try:
        if platform.system().lower() == "windows":
            subprocess.Popen(cmd, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            subprocess.Popen(cmd, start_new_session=True)
        return True, f"Topaz Photo mit {len(valid_jpegs)} JPEG-Datei(en) gestartet."
    except Exception as e:
        return False, f"Fehler beim Starten von Topaz Photo: {e}"
