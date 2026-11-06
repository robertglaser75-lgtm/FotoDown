"""Configuration management for FotoDown."""

from dataclasses import dataclass, field, asdict
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

RAW_EXTENSIONS = {
    ".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".ori", ".rw2",
    ".pef", ".raf", ".srw", ".3fr", ".erf", ".kdc", ".mrw", ".nrw", ".raw"
}

DEFAULT_IMAGE_EXTENSIONS = [
    ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".heif",
    ".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".ori", ".rw2", ".pef", ".raf"
]

DEFAULT_VIDEO_EXTENSIONS = [
    ".mp4", ".mov", ".mts", ".m2ts", ".avi", ".mkv"
]

DEFAULT_PROFILES: Dict[str, dict] = {
    "Standard": {
        "type_folder_organization": "same",
        "file_pattern": "{YYYY}-{MM}-{DD}_{hh}-{mm}-{ss}_{camera}_{orig_name}",
        "folder_pattern": "{YYYY}/{YYYY}-{MM}-{DD}",
        "pair_raw_jpg": True,
        "sync_xmp_sidecars": True,
        "only_new_files": True,
        "verify_checksums": True,
        "separate_video_dir": False,
        "enable_dual_backup": False,
        "enable_iptc": False,
        "iptc_creator": "",
        "iptc_copyright": "© {YYYY} {creator}. Alle Rechte vorbehalten.",
        "iptc_keywords": "",
    },
    "Urlaub & Reise": {
        "type_folder_organization": "same",
        "file_pattern": "{YYYY}-{MM}-{DD}_Urlaub_{num:04d}_{orig_name}",
        "folder_pattern": "{YYYY}/{YYYY}-{MM}_Urlaub",
        "pair_raw_jpg": True,
        "sync_xmp_sidecars": True,
        "only_new_files": True,
        "verify_checksums": True,
        "separate_video_dir": False,
        "enable_dual_backup": False,
        "enable_iptc": False,
        "iptc_creator": "",
        "iptc_copyright": "© {YYYY} {creator}. Alle Rechte vorbehalten.",
        "iptc_keywords": "Urlaub, Reise",
    },
    "Studio & Shooting": {
        "type_folder_organization": "subfolders",
        "file_pattern": "{YYYY}-{MM}-{DD}_{camera}_{orig_name}",
        "folder_pattern": "{YYYY}/{YYYY}-{MM}-{DD}_Shooting",
        "pair_raw_jpg": True,
        "sync_xmp_sidecars": True,
        "only_new_files": True,
        "verify_checksums": True,
        "separate_video_dir": False,
        "enable_dual_backup": True,
        "enable_iptc": True,
        "iptc_creator": "",
        "iptc_copyright": "© {YYYY} {creator}. Alle Rechte vorbehalten.",
        "iptc_keywords": "Shooting, Studio",
    },
    "Drohne & Actioncam": {
        "type_folder_organization": "same",
        "file_pattern": "{YYYY}-{MM}-{DD}_{orig_name}",
        "folder_pattern": "{YYYY}/{YYYY}-{MM}-{DD}",
        "pair_raw_jpg": False,
        "sync_xmp_sidecars": False,
        "only_new_files": True,
        "verify_checksums": True,
        "separate_video_dir": True,
        "enable_dual_backup": False,
        "enable_iptc": False,
        "iptc_creator": "",
        "iptc_copyright": "© {YYYY} {creator}. Alle Rechte vorbehalten.",
        "iptc_keywords": "Action, Drohne",
    },
}


@dataclass
class AppConfig:
    source_dir: str = ""
    target_dir: str = str(Path.home() / "Pictures" / "FotoDown_Imports")
    separate_video_dir: bool = False
    video_target_dir: str = str(Path.home() / "Videos" / "FotoDown_Videos")
    enable_dual_backup: bool = False
    backup_target_dir: str = ""
    verify_checksums: bool = True
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
    pair_raw_jpg: bool = True
    sync_xmp_sidecars: bool = True
    auto_detect_drives: bool = True
    auto_scan_on_insert: bool = False
    active_profile: str = "Standard"
    profiles: Dict[str, dict] = field(default_factory=lambda: dict(DEFAULT_PROFILES))
    # IPTC & Copyright metadata injection
    enable_iptc: bool = False
    iptc_creator: str = ""
    iptc_copyright: str = "© {YYYY} {creator}. Alle Rechte vorbehalten."
    iptc_keywords: str = ""
    # Sichten & Culling (Phase 2 Workflow)
    culling_root_folder: str = ""
    culling_last_folder: str = ""
    reject_action: str = "move_folder"  # "move_folder", "trash", "flag_only"
    reject_folder_name: str = "_Abgelehnt"
    darktable_path: str = r"C:\Program Files\darktable\bin\darktable.exe"
    topaz_path: str = r"C:\Program Files\Topaz Labs LLC\Topaz Photo\Topaz Photo.exe"

    def apply_profile(self, name: str) -> bool:
        """Applies configuration settings from a profile by name."""
        if name not in self.profiles:
            return False
        p = self.profiles[name]
        self.active_profile = name
        for k, v in p.items():
            if hasattr(self, k):
                if k == "folder_pattern" and not v:
                    v = DEFAULT_PROFILES.get(name, DEFAULT_PROFILES["Standard"]).get("folder_pattern", "{YYYY}/{YYYY}-{MM}-{DD}")
                elif k == "file_pattern" and not v:
                    v = DEFAULT_PROFILES.get(name, DEFAULT_PROFILES["Standard"]).get("file_pattern", "{YYYY}-{MM}-{DD}_{hh}-{mm}-{ss}_{camera}_{orig_name}")
                setattr(self, k, v)
        return True

    def save_current_as_profile(self, name: str) -> None:
        """Saves current settings under given profile name."""
        self.active_profile = name
        f_pat = self.file_pattern or DEFAULT_PROFILES.get(name, DEFAULT_PROFILES["Standard"]).get("file_pattern", "{YYYY}-{MM}-{DD}_{hh}-{mm}-{ss}_{camera}_{orig_name}")
        d_pat = self.folder_pattern or DEFAULT_PROFILES.get(name, DEFAULT_PROFILES["Standard"]).get("folder_pattern", "{YYYY}/{YYYY}-{MM}-{DD}")
        self.profiles[name] = {
            "type_folder_organization": self.type_folder_organization,
            "file_pattern": f_pat,
            "folder_pattern": d_pat,
            "pair_raw_jpg": self.pair_raw_jpg,
            "sync_xmp_sidecars": self.sync_xmp_sidecars,
            "only_new_files": self.only_new_files,
            "verify_checksums": self.verify_checksums,
            "separate_video_dir": self.separate_video_dir,
            "enable_dual_backup": self.enable_dual_backup,
            "enable_iptc": self.enable_iptc,
            "iptc_creator": self.iptc_creator,
            "iptc_copyright": self.iptc_copyright,
            "iptc_keywords": self.iptc_keywords,
        }

    def delete_profile(self, name: str) -> bool:
        """Deletes a profile if more than one exists."""
        if name in self.profiles and len(self.profiles) > 1:
            del self.profiles[name]
            if self.active_profile == name:
                self.active_profile = next(iter(self.profiles.keys()))
                self.apply_profile(self.active_profile)
            return True
        return False

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
                cfg = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
                for p_name, p_data in DEFAULT_PROFILES.items():
                    if p_name not in cfg.profiles:
                        cfg.profiles[p_name] = dict(p_data)
                    else:
                        for k, v in p_data.items():
                            if k not in cfg.profiles[p_name] or cfg.profiles[p_name][k] is None:
                                cfg.profiles[p_name][k] = v

                default_std = DEFAULT_PROFILES["Standard"]
                for p_name, p_dict in cfg.profiles.items():
                    fallback_source = DEFAULT_PROFILES.get(p_name, default_std)
                    for k, v in fallback_source.items():
                        if k not in p_dict or p_dict[k] is None:
                            p_dict[k] = v
                    if not p_dict.get("file_pattern"):
                        p_dict["file_pattern"] = fallback_source.get("file_pattern", default_std["file_pattern"])
                    if not p_dict.get("folder_pattern"):
                        p_dict["folder_pattern"] = fallback_source.get("folder_pattern", default_std["folder_pattern"])

                if cfg.active_profile not in cfg.profiles:
                    cfg.active_profile = "Standard" if "Standard" in cfg.profiles else next(iter(cfg.profiles.keys()))
                cfg.apply_profile(cfg.active_profile)

                if not cfg.file_pattern:
                    cfg.file_pattern = default_std["file_pattern"]
                if not cfg.folder_pattern:
                    cfg.folder_pattern = default_std["folder_pattern"]

                return cfg
            except Exception as e:
                print(f"[Warnung] Konfigurationsdatei konnte nicht geladen werden: {e}")
        cfg = cls()
        cfg.apply_profile(cfg.active_profile)
        return cfg

    def save(self, path: Optional[Path] = None) -> None:
        """Saves current configuration to JSON file."""
        config_path = path or self.get_default_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
