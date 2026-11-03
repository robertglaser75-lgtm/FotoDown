"""Drive detector module to scan Windows and Linux drives for SD cards and DCIM folders, with ejection support."""

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Callable, Dict, List, Optional, Tuple


@dataclass
class DiskSpaceInfo:
    total_bytes: int = 0
    used_bytes: int = 0
    free_bytes: int = 0

    @property
    def used_percent(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        return (self.used_bytes / self.total_bytes) * 100.0

    @property
    def free_percent(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        return (self.free_bytes / self.total_bytes) * 100.0

    @property
    def total_str(self) -> str:
        return format_size(self.total_bytes)

    @property
    def used_str(self) -> str:
        return format_size(self.used_bytes)

    @property
    def free_str(self) -> str:
        return format_size(self.free_bytes)


def format_size(size_bytes: int) -> str:
    """Formats bytes into human readable format (B, KB, MB, GB, TB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    num = float(size_bytes)
    for unit in ["KB", "MB", "GB", "TB", "PB"]:
        num /= 1024.0
        if num < 1024.0 or unit == "PB":
            return f"{num:.1f} {unit}"
    return f"{num:.1f} TB"


def get_disk_space(path_or_str: str | Path) -> Optional[DiskSpaceInfo]:
    """Retrieves disk usage for any local drive, folder, or UNC share."""
    if not path_or_str:
        return None
    try:
        p = Path(path_or_str)
        while not p.exists() and p != p.parent:
            p = p.parent
        if not p.exists():
            return None
        usage = shutil.disk_usage(p)
        return DiskSpaceInfo(
            total_bytes=usage.total,
            used_bytes=usage.used,
            free_bytes=usage.free,
        )
    except Exception:
        return None


@dataclass
class DriveInfo:
    letter: str
    label: str
    path: Path
    has_dcim: bool
    dcim_path: Optional[Path] = None
    space: Optional[DiskSpaceInfo] = None

    @property
    def display_name(self) -> str:
        tag = "[DCIM / Kamera-Fotos]" if self.has_dcim else "[Wechseldatenträger]"
        lbl = f" ({self.label})" if self.label and self.label != self.letter else ""
        space_info = f" [{self.space.free_str} frei von {self.space.total_str}]" if self.space and self.space.total_bytes > 0 else ""
        return f"{self.letter}{lbl} {tag}{space_info}"


def _detect_drives_windows() -> List[DriveInfo]:
    """Detects available drives on Windows, identifying SD cards with DCIM folders."""
    drives = []
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
                        space = get_disk_space(drive_path)

                        drives.append(DriveInfo(
                            letter=chr(letter_ascii) + ":",
                            label=label,
                            path=drive_path,
                            has_dcim=has_dcim,
                            dcim_path=dcim if has_dcim else None,
                            space=space,
                        ))
                except Exception:
                    continue
    except Exception:
        pass
    return drives


def _detect_drives_linux() -> List[DriveInfo]:
    """Detects mounted drives and external media on Linux."""
    drives: List[DriveInfo] = []
    checked_paths = set()
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""

    candidate_roots = [
        Path("/media") / user if user else None,
        Path("/run/media") / user if user else None,
        Path("/media"),
        Path("/mnt"),
    ]

    for root in candidate_roots:
        if root and root.exists() and root.is_dir():
            try:
                for entry in root.iterdir():
                    if entry.is_dir() and entry not in checked_paths:
                        checked_paths.add(entry)
                        dcim = entry / "DCIM"
                        if not dcim.exists():
                            dcim = entry / "dcim"
                        has_dcim = dcim.exists() and dcim.is_dir()
                        space = get_disk_space(entry)

                        drives.append(DriveInfo(
                            letter=entry.name,
                            label=entry.name,
                            path=entry,
                            has_dcim=has_dcim,
                            dcim_path=dcim if has_dcim else None,
                            space=space,
                        ))
            except Exception:
                continue

    proc_mounts = Path("/proc/mounts")
    if proc_mounts.exists():
        try:
            with open(proc_mounts, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        dev, mnt = parts[0], parts[1]
                        if any(k in dev for k in ["/dev/sd", "/dev/mmcblk", "/dev/nvme"]) or mnt.startswith(("/media", "/run/media", "/mnt")):
                            mnt_path = Path(mnt)
                            if mnt_path not in checked_paths and mnt_path.exists() and mnt not in ("/", "/boot", "/home", "/etc"):
                                checked_paths.add(mnt_path)
                                dcim = mnt_path / "DCIM"
                                if not dcim.exists():
                                    dcim = mnt_path / "dcim"
                                has_dcim = dcim.exists() and dcim.is_dir()
                                if has_dcim or mnt.startswith(("/media", "/run/media")):
                                    space = get_disk_space(mnt_path)
                                    drives.append(DriveInfo(
                                        letter=mnt_path.name or mnt,
                                        label=mnt_path.name or dev,
                                        path=mnt_path,
                                        has_dcim=has_dcim,
                                        dcim_path=dcim if has_dcim else None,
                                        space=space,
                                    ))
        except Exception:
            pass

    return drives


def detect_drives() -> List[DriveInfo]:
    """Detects available drives across Windows and Linux, identifying SD cards with DCIM folders."""
    if sys.platform == "win32":
        return _detect_drives_windows()
    return _detect_drives_linux()


class DriveMonitor:
    """Monitors drive changes across polling ticks."""

    def __init__(self, detector_func: Callable[[], List[DriveInfo]] = detect_drives):
        self._detector = detector_func
        self._known_drives: Dict[str, DriveInfo] = {}
        self.refresh()

    def refresh(self) -> List[DriveInfo]:
        """Performs a full scan and updates known drives."""
        drives = self._detector()
        self._known_drives = {str(d.path).rstrip("\\/").upper(): d for d in drives}
        return drives

    def check_changes(self) -> Tuple[List[DriveInfo], List[DriveInfo]]:
        """Checks for added and removed drives since last check. Returns (added, removed)."""
        current_list = self._detector()
        current_map = {str(d.path).rstrip("\\/").upper(): d for d in current_list}

        added = [d for p, d in current_map.items() if p not in self._known_drives]
        removed = [d for p, d in self._known_drives.items() if p not in current_map]

        self._known_drives = current_map
        return added, removed


def _eject_drive_windows(drive_input: str | Path) -> Tuple[bool, str]:
    path_str = str(drive_input).strip()
    drive_letter = ""
    if len(path_str) >= 2 and path_str[1] == ":":
        drive_letter = path_str[:2].upper()

    if not drive_letter:
        return False, f"Der Pfad '{path_str}' befindet sich auf keinem Laufwerk mit Laufwerksbuchstaben."

    # 1. Shell Application Verb 'Eject'
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

    # 2. Win32 API Fallback
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


def _eject_drive_linux(drive_input: str | Path) -> Tuple[bool, str]:
    path = Path(drive_input)
    # 1. Try udisksctl
    try:
        res = subprocess.run(["udisksctl", "unmount", "-p", str(path)], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return True, f"Laufwerk '{path.name}' erfolgreich ausgehängt (udisksctl)."
    except Exception:
        pass

    # 2. Try gio mount -u
    try:
        res = subprocess.run(["gio", "mount", "-u", str(path)], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return True, f"Laufwerk '{path.name}' erfolgreich ausgehängt (gio)."
    except Exception:
        pass

    # 3. Try umount
    try:
        res = subprocess.run(["umount", str(path)], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return True, f"Laufwerk '{path.name}' erfolgreich ausgehängt (umount)."
    except Exception:
        pass

    # 4. Try eject command
    try:
        res = subprocess.run(["eject", str(path)], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return True, f"Laufwerk '{path.name}' erfolgreich ausgeworfen (eject)."
    except Exception:
        pass

    return False, f"Laufwerk '{path}' konnte nicht ausgehängt werden. Möglicherweise wird eine Datei noch verwendet."


def eject_drive(drive_input: str | Path) -> Tuple[bool, str]:
    """Safely ejects a removable drive across Windows and Linux. Returns (success, message)."""
    path_str = str(drive_input).strip()
    if not path_str:
        return False, "Kein Pfad angegeben."

    if sys.platform == "win32":
        return _eject_drive_windows(drive_input)
    return _eject_drive_linux(drive_input)
