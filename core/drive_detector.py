"""Drive and memory card detector for Windows and cross-platform."""

import ctypes
from dataclasses import dataclass
import os
from pathlib import Path
import sys
from typing import List


@dataclass
class DriveInfo:
    path: str
    label: str
    drive_type: str
    is_removable: bool
    has_dcim: bool
    dcim_path: str

    @property
    def display_name(self) -> str:
        parts = [self.path]
        if self.label:
            parts.append(f"[{self.label}]")
        if self.has_dcim:
            parts.append("(DCIM gefunden - Speicherkarte)")
        elif self.is_removable:
            parts.append("(Wechseldatenträger)")
        return " ".join(parts)


def detect_drives() -> List[DriveInfo]:
    """Detects available system drives, especially removable memory cards."""
    results = []

    if sys.platform == "win32":
        try:
            kernel32 = ctypes.windll.kernel32
            # Get drive bitmask
            bitmask = kernel32.GetLogicalDrives()
            # DRIVE_REMOVABLE = 2, DRIVE_FIXED = 3, DRIVE_REMOTE = 4, DRIVE_CDROM = 5
            for letter_idx in range(26):
                if bitmask & (1 << letter_idx):
                    drive_letter = f"{chr(65 + letter_idx)}:\\"
                    drive_type_int = kernel32.GetDriveTypeW(drive_letter)
                    is_removable = (drive_type_int == 2)

                    # Get Volume Label
                    volume_name_buffer = ctypes.create_unicode_buffer(1024)
                    file_system_name_buffer = ctypes.create_unicode_buffer(1024)
                    kernel32.GetVolumeInformationW(
                        drive_letter,
                        volume_name_buffer,
                        ctypes.sizeof(volume_name_buffer),
                        None, None, None,
                        file_system_name_buffer,
                        ctypes.sizeof(file_system_name_buffer)
                    )
                    label = volume_name_buffer.value

                    # Check for DCIM folder
                    dcim_path = ""
                    has_dcim = False
                    p = Path(drive_letter)
                    try:
                        dcim_candidate = p / "DCIM"
                        if dcim_candidate.exists() and dcim_candidate.is_dir():
                            has_dcim = True
                            dcim_path = str(dcim_candidate)
                    except Exception:
                        pass

                    type_names = {
                        2: "Wechseldatenträger (Removable)",
                        3: "Lokaler Datenträger (Fixed)",
                        4: "Netzlaufwerk (Network)",
                        5: "CD/DVD-Laufwerk",
                        6: "RAM-Disk"
                    }
                    type_str = type_names.get(drive_type_int, "Unbekannt")

                    results.append(DriveInfo(
                        path=drive_letter,
                        label=label,
                        drive_type=type_str,
                        is_removable=is_removable,
                        has_dcim=has_dcim,
                        dcim_path=dcim_path
                    ))
        except Exception as e:
            print(f"[Warnung] Laufwerkserkennung fehlgeschlagen: {e}")
    else:
        # Fallback for Linux/macOS
        mount_points = ["/Volumes", "/media", "/mnt"]
        for mp in mount_points:
            p = Path(mp)
            if p.exists():
                for sub in p.iterdir():
                    if sub.is_dir():
                        dcim = sub / "DCIM"
                        has_dcim = dcim.exists() and dcim.is_dir()
                        results.append(DriveInfo(
                            path=str(sub),
                            label=sub.name,
                            drive_type="Mount",
                            is_removable=True,
                            has_dcim=has_dcim,
                            dcim_path=str(dcim) if has_dcim else ""
                        ))

    # Sort so that drives with DCIM or Removable come first
    results.sort(key=lambda d: (not d.has_dcim, not d.is_removable, d.path))
    return results
