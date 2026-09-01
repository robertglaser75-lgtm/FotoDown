"""Configuration management for FotoDown."""

from dataclasses import dataclass, field, asdict
import json
import os
from pathlib import Path
from typing import List, Optional

RAW_EXTENSIONS = {
    ".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2",
    ".pef", ".raf", ".srw", ".3fr", ".erf", ".kdc", ".mrw", ".nrw", ".raw"
}

DEFAULT_IMAGE_EXTENSIONS = [
    ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".heif",
    ".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2", ".pef", ".raf"
]

DEFAULT_VIDEO_EXTENSIONS = [
    ".mp4", ".mov", ".mts", ".m2ts", ".avi", ".mkv"
]


@dataclass
class AppConfig:
    source_dir: str = ""
    target_dir: str = str(Path.home() / "Pictures" / "FotoDown_Imports")
    separate_video_dir: bool = False
    video_target_dir: str = str(Path.home() / "Videos" / "FotoDown_Videos")
    type_folder_organization: str = "same"  # "same", "subfolders" (.../JPG, .../RAW), "parent_folders" (JPG/..., RAW/...)
    file_pattern: str = "{YYYY}-{MM}-{DD}_{hh}-{mm}-{ss}_{camera}_{orig_name}"
    folder_pattern: str = "{YYYY}/{YYYY}-{MM}-{DD}"
    include_videos: bool = True
    only_new_files: bool = True
    recursive_scan: bool = True
    unknown_camera_label: str = "UnknownCamera"
    custom_extensions: List[str] = field(default_factory=lambda: list(DEFAULT_IMAGE_EXTENSIONS + DEFAULT_VIDEO_EXTENSIONS))
    delete_source_after_import: bool = False
    collision_mode: str = "rename"  # 'rename' (_1, _2), 'skip', 'overwrite'

    @classmethod
    def get_default_config_path(cls) -> Path:
        """Returns the default configuration file path."""
        appdata = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
        if appdata:
            config_dir = Path(appdata) / "FotoDown"
        else:
            config_dir = Path.home() / ".fotodown"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "config.json"

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "AppConfig":
        """Loads configuration from JSON file or returns defaults."""
        config_path = path or cls.get_default_config_path()
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except Exception as e:
                print(f"[Warnung] Konfigurationsdatei konnte nicht geladen werden: {e}")
        return cls()

    def save(self, path: Optional[Path] = None) -> None:
        """Saves current configuration to JSON file."""
        config_path = path or self.get_default_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
