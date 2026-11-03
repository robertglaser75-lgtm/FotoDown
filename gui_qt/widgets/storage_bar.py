"""Storage usage bar widget for source and target drives in Fluent Dark style."""

from pathlib import Path
from typing import Optional, Tuple
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar,
    QVBoxLayout, QWidget
)

from core.drive_detector import DiskSpaceInfo, format_size, get_disk_space


class StorageBarWidget(QFrame):
    def __init__(self, title: str = "Speicherplatz", parent=None):
        super().__init__(parent)
        self.default_title = title
        self._current_space: Optional[DiskSpaceInfo] = None
        self._current_path: Optional[Path] = None
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("storageCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Header: Title & Info
        header = QHBoxLayout()
        header.setSpacing(8)

        self.lbl_title = QLabel(self.default_title)
        self.lbl_title.setObjectName("storageTitle")

        self.lbl_info = QLabel("Kein Laufwerk gewählt")
        self.lbl_info.setObjectName("storageInfo")
        self.lbl_info.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        header.addWidget(self.lbl_title)
        header.addWidget(self.lbl_info)
        layout.addLayout(header)

        # Usage Bar
        self.bar = QProgressBar()
        self.bar.setObjectName("storageBar")
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        layout.addWidget(self.bar)

        # Warning / Capacity check note
        self.lbl_warning = QLabel("")
        self.lbl_warning.setObjectName("storageWarning")
        self.lbl_warning.setVisible(False)
        layout.addWidget(self.lbl_warning)

    def set_path(self, path_or_str: str | Path, custom_title: Optional[str] = None):
        """Updates storage data from the provided folder or drive path."""
        path_str = str(path_or_str).strip()
        if custom_title:
            self.lbl_title.setText(custom_title)
        else:
            self.lbl_title.setText(self.default_title)

        if not path_str:
            self._current_space = None
            self._current_path = None
            self.lbl_info.setText("Kein Pfad festgelegt")
            self.bar.setValue(0)
            self._apply_bar_style(0)
            self.setToolTip("")
            self.lbl_warning.setVisible(False)
            return

        self._current_path = Path(path_str)
        space = get_disk_space(self._current_path)
        self._current_space = space

        if not space or space.total_bytes <= 0:
            self.lbl_info.setText("Speicherstatus nicht verfügbar")
            self.bar.setValue(0)
            self._apply_bar_style(0)
            self.setToolTip(f"Pfad: {path_str}")
            self.lbl_warning.setVisible(False)
            return

        used_pct = space.used_percent
        self.bar.setValue(int(used_pct))
        self._apply_bar_style(used_pct)

        self.lbl_info.setText(
            f"{space.free_str} frei von {space.total_str} ({used_pct:.0f}% belegt)"
        )
        self.setToolTip(
            f"Laufwerk: {path_str}\n"
            f"Gesamt: {space.total_str}\n"
            f"Belegt: {space.used_str} ({used_pct:.1f}%)\n"
            f"Frei: {space.free_str}"
        )
        self.lbl_warning.setVisible(False)

    def check_capacity(self, required_bytes: int) -> Tuple[bool, str]:
        """Validates if target has enough free space for the import."""
        if not self._current_space or self._current_space.total_bytes <= 0:
            self.lbl_warning.setVisible(False)
            return True, ""

        if required_bytes <= 0:
            self.lbl_warning.setVisible(False)
            return True, ""

        req_str = format_size(required_bytes)
        free_bytes = self._current_space.free_bytes

        if required_bytes > free_bytes:
            msg = f"\u26A0 Nicht genügend Speicherplatz! Benötigt: {req_str}, Frei: {self._current_space.free_str}"
            self.lbl_warning.setText(msg)
            self.lbl_warning.setStyleSheet("color: #f87171; font-weight: bold; font-size: 11px;")
            self.lbl_warning.setVisible(True)
            self._apply_bar_style(100, is_error=True)
            return False, msg

        remaining_after = free_bytes - required_bytes
        remaining_str = format_size(remaining_after)
        msg = f"\u2713 Ausreichend Speicher: {req_str} benötigt ({remaining_str} verbleiben)"
        self.lbl_warning.setText(msg)
        self.lbl_warning.setStyleSheet("color: #4ade80; font-size: 11px;")
        self.lbl_warning.setVisible(True)
        self._apply_bar_style(self._current_space.used_percent)
        return True, msg

    def _apply_bar_style(self, used_percent: float, is_error: bool = False):
        if is_error or used_percent >= 95:
            color_stop = "#ef4444"
            color_start = "#dc2626"
        elif used_percent >= 85:
            color_stop = "#fbbf24"
            color_start = "#d97706"
        else:
            color_stop = "#38bdf8"
            color_start = "#0284c7"

        self.bar.setStyleSheet(f"""
            QProgressBar#storageBar {{
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 4px;
            }}
            QProgressBar#storageBar::chunk {{
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {color_start}, stop:1 {color_stop});
                border-radius: 3px;
            }}
        """)
