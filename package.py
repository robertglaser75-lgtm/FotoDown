#!/usr/bin/env python3
"""Build script for Vitrina installation packages (Windows ZIP & Linux TAR.GZ)."""

import hashlib
import os
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path

# Add project root to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from core.version import __version__


def get_sha256(file_path: Path) -> str:
    """Computes SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def collect_project_files() -> list:
    """Collects all source files and assets to include in distribution packages."""
    included_files = []
    
    # Root files
    root_patterns = [
        "vitrina.py",
        "Vitrina.bat",
        "vitrina.sh",
        "fotodown.py",
        "FotoDown.bat",
        "fotodown.sh",
        "run_tests.py",
        "requirements.txt",
        "README.md",
        "INSTALL.md",
        "LICENSE",
        "CHANGELOG.md",
        "install_windows.bat",
        "install_linux.sh",
    ]
    for pattern in root_patterns:
        p = SCRIPT_DIR / pattern
        if p.exists():
            included_files.append((p, Path(pattern)))

    # Core package
    core_dir = SCRIPT_DIR / "core"
    for p in core_dir.rglob("*.py"):
        rel = p.relative_to(SCRIPT_DIR)
        included_files.append((p, rel))

    # GUI Qt package (includes Python sources and .qss stylesheets)
    gui_qt_dir = SCRIPT_DIR / "gui_qt"
    if gui_qt_dir.exists():
        for p in gui_qt_dir.rglob("*"):
            if p.is_file() and not p.name.startswith(".") and "__pycache__" not in p.parts and p.suffix != ".pyc":
                rel = p.relative_to(SCRIPT_DIR)
                included_files.append((p, rel))

    # GUI Tk fallback package
    gui_dir = SCRIPT_DIR / "gui"
    if gui_dir.exists():
        for p in gui_dir.rglob("*.py"):
            rel = p.relative_to(SCRIPT_DIR)
            included_files.append((p, rel))

    # Assets
    assets_dir = SCRIPT_DIR / "assets"
    if assets_dir.exists():
        for p in assets_dir.rglob("*"):
            if p.is_file() and not p.name.startswith("."):
                rel = p.relative_to(SCRIPT_DIR)
                included_files.append((p, rel))

    return included_files


def build_windows_package(dist_dir: Path, version: str, files: list) -> Path:
    """Builds Windows installation ZIP archive."""
    pkg_name = f"Vitrina-v{version}-Windows"
    zip_path = dist_dir / f"{pkg_name}.zip"
    
    if zip_path.exists():
        zip_path.unlink()

    print(f"Erstelle Windows-Installationspaket: {zip_path.name}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for src, rel in files:
            # Exclude linux shell scripts from windows zip if preferred, or keep for universal extract
            archive_name = Path(pkg_name) / rel
            zf.write(src, str(archive_name))

    return zip_path


def build_linux_package(dist_dir: Path, version: str, files: list) -> Path:
    """Builds Linux installation TAR.GZ archive with preserved executable permissions."""
    pkg_name = f"Vitrina-v{version}-Linux"
    tar_path = dist_dir / f"{pkg_name}.tar.gz"
    
    if tar_path.exists():
        tar_path.unlink()

    print(f"Erstelle Linux-Installationspaket: {tar_path.name}...")
    with tarfile.open(tar_path, "w:gz") as tf:
        for src, rel in files:
            archive_name = Path(pkg_name) / rel
            tar_info = tf.gettarinfo(str(src), arcname=str(archive_name))
            # Set executable bits for scripts
            if rel.suffix in (".sh", ".py") or rel.name in ("vitrina.sh", "install_linux.sh", "vitrina.py", "fotodown.sh", "fotodown.py"):
                tar_info.mode = 0o755
            else:
                tar_info.mode = 0o644
            
            with open(src, "rb") as f:
                tf.addfile(tar_info, f)

    return tar_path


def main():
    dist_dir = SCRIPT_DIR / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    version = __version__

    print(f"=== Vitrina Packaging Suite v{version} ===")
    files = collect_project_files()
    print(f"Gefundene Projektdateien: {len(files)} Dateien.")

    # 1. Windows Package
    win_pkg = build_windows_package(dist_dir, version, files)
    win_sha = get_sha256(win_pkg)
    win_size_mb = win_pkg.stat().st_size / (1024 * 1024)
    print(f"✓ {win_pkg.name} ({win_size_mb:.2f} MB)")
    print(f"  SHA-256: {win_sha}")

    # 2. Linux Package
    linux_pkg = build_linux_package(dist_dir, version, files)
    linux_sha = get_sha256(linux_pkg)
    linux_size_mb = linux_pkg.stat().st_size / (1024 * 1024)
    print(f"✓ {linux_pkg.name} ({linux_size_mb:.2f} MB)")
    print(f"  SHA-256: {linux_sha}")

    # Write checksums file
    checksum_file = dist_dir / f"SHA256SUMS-v{version}.txt"
    with open(checksum_file, "w", encoding="utf-8") as f:
        f.write(f"{win_sha}  {win_pkg.name}\n")
        f.write(f"{linux_sha}  {linux_pkg.name}\n")
    print(f"✓ Prüfsummendatei erstellt: {checksum_file.name}")
    print("\nErstellung aller Installationspakete erfolgreich abgeschlossen!")


if __name__ == "__main__":
    main()
