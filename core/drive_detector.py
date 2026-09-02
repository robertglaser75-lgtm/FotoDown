"""Drive detector module to scan Windows drives for SD cards and DCIM folders, with ejection support."""

import os
import sys
from pathlib import Path
import subprocess
from typing import List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class DriveInfo:
    letter: str
    label: str
    path: Path
    has_dcim: bool
    dcim_path: Optional[Path] = None

    @property
    def display_name(self) -> str:
        tag = "[DCIM / Kamera-Fotos]" if self.has_dcim else "[Wechseldatenträger]"
        lbl = f" ({self.label})" if self.label else ""
        return f"{self.letter} {lbl} {tag}"


def detect_drives() -> List[DriveInfo]:
    """Detects available drives, identifying SD cards with DCIM folders."""
    drives = []
    if sys.platform != "win32":
        return drives

    try:
        import ctypes
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter_ascii in range(65, 91):  # A-Z
            if bitmask & (1 << (letter_ascii - 65)):
                drive_letter = f"{chr(letter_ascii)}:\\"
                drive_path = Path(drive_letter)

                try:
                    drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive_letter)
                    # 2: REMOVABLE, 3: FIXED (some SD card readers identify as fixed)
                    if drive_type in (2, 3):
                        volume_name_buf = ctypes.create_unicode_buffer(1024)
                        ctypes.windll.kernel32.GetVolumeInformationW(
                            drive_letter,
                            volume_name_buf,
                            1024,
                            None, None, None, None, 0
                        )
                        label = volume_name_buf.value

                        # Skip C: system drive
                        if drive_letter.upper().startswith("C:"):
                            continue

                        # Check DCIM
                        dcim = drive_path / "DCIM"
                        has_dcim = dcim.exists() and dcim.is_dir()

                        drives.append(DriveInfo(
                            letter=chr(letter_ascii) + ":",
                            label=label,
                            path=drive_path,
                            has_dcim=has_dcim,
                            dcim_path=dcim if has_dcim else None
                        ))
                except Exception:
                    continue
    except Exception:
        pass

    return drives


def eject_drive(drive_input: str | Path) -> Tuple[bool, str]:
    """Safely ejects a removable drive in Windows. Returns (success, message)."""
    path_str = str(drive_input).strip()
    if not path_str:
        return False, "Kein Pfad angegeben."

    drive_letter = ""
    if len(path_str) >= 2 and path_str[1] == ":":
        drive_letter = path_str[:2].upper()

    if not drive_letter:
        return False, f"Der Pfad '{path_str}' befindet sich auf keinem Laufwerk mit Laufwerksbuchstaben."

    # 1. Shell Application Verb "Eject" (standard Windows safe removal)
    try:
        ps_cmd = f'''
        $shell = New-Object -ComObject Shell.Application
        $drive = $shell.NameSpace(17).ParseName("{drive_letter}")
        if ($drive) {{
            $drive.InvokeVerb("Eject")
            Write-Output "SUCCESS"
        }} else {{
            Write-Output "NOT_FOUND"
        }}
        '''
        res = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True, timeout=5)
        if "SUCCESS" in res.stdout:
            return True, f"Speicherkarte / Laufwerk ({drive_letter}) wurde erfolgreich ausgehängt und kann sicher entfernt werden."
    except Exception:
        pass

    # 2. Win32 API Fallback (CreateFileW + FSCTL_LOCK_VOLUME + FSCTL_DISMOUNT_VOLUME + IOCTL_STORAGE_EJECT_MEDIA)
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            GENERIC_READ = 0x80000000
            GENERIC_WRITE = 0x40000000
            FILE_SHARE_READ = 0x00000001
            FILE_SHARE_WRITE = 0x00000002
            OPEN_EXISTING = 3

            FSCTL_LOCK_VOLUME = 0x00090018
            FSCTL_DISMOUNT_VOLUME = 0x00090020
            IOCTL_STORAGE_EJECT_MEDIA = 0x002d0808

            volume_path = f"\\\\.\\{drive_letter}"
            handle = ctypes.windll.kernel32.CreateFileW(
                volume_path,
                GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None,
                OPEN_EXISTING,
                0,
                None
            )

            if handle != -1 and handle != 0:
                dwBytesReturned = wintypes.DWORD()
                ctypes.windll.kernel32.DeviceIoControl(handle, FSCTL_LOCK_VOLUME, None, 0, None, 0, ctypes.byref(dwBytesReturned), None)
                ctypes.windll.kernel32.DeviceIoControl(handle, FSCTL_DISMOUNT_VOLUME, None, 0, None, 0, ctypes.byref(dwBytesReturned), None)
                ctypes.windll.kernel32.DeviceIoControl(handle, IOCTL_STORAGE_EJECT_MEDIA, None, 0, None, 0, ctypes.byref(dwBytesReturned), None)
                ctypes.windll.kernel32.CloseHandle(handle)
                return True, f"Speicherkarte / Laufwerk ({drive_letter}) wurde erfolgreich ausgehängt."
        except Exception:
            pass

    return False, f"Laufwerk {drive_letter} konnte nicht ausgehängt werden. Möglicherweise wird eine Datei noch verwendet."
