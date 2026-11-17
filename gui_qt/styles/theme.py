"""Theme manager and dynamic stylesheet loader for Vitrina.

Provides seamless switching between Dark Fluent, Light Fluent, and Auto (System) themes
with high contrast, synchronized vector icons, and cross-platform compatibility.
"""

from pathlib import Path
import sys
from typing import Optional

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from .icons import set_icon_theme

THEME_DARK = "dark"
THEME_LIGHT = "light"
THEME_SYSTEM = "system"


def detect_system_theme() -> str:
    """Detects whether the operating system uses dark or light mode."""
    # 1. Native Qt 6.5+ ColorScheme check
    try:
        app = QGuiApplication.instance()
        if app and hasattr(app, "styleHints"):
            hints = app.styleHints()
            if hasattr(hints, "colorScheme"):
                scheme = hints.colorScheme()
                if scheme == Qt.ColorScheme.Light:
                    return THEME_LIGHT
                if scheme == Qt.ColorScheme.Dark:
                    return THEME_DARK
    except Exception:
        pass

    # 2. Windows Registry check on win32
    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            if val == 1:
                return THEME_LIGHT
            return THEME_DARK
        except Exception:
            pass

    return THEME_DARK


def get_effective_theme(theme_mode: str) -> str:
    """Returns 'dark' or 'light' for given theme_mode ('dark', 'light', 'system')."""
    if theme_mode == THEME_SYSTEM:
        return detect_system_theme()
    return THEME_LIGHT if theme_mode == THEME_LIGHT else THEME_DARK


class ThemeManager(QObject):
    """Manages application stylesheet switching and icon theme synchronization."""

    theme_changed = Signal(str)  # emits effective theme: 'dark' or 'light'

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._current_mode = THEME_DARK
        self._effective_theme = THEME_DARK

    @property
    def current_mode(self) -> str:
        """Returns the configured theme mode ('dark', 'light', or 'system')."""
        return self._current_mode

    @property
    def effective_theme(self) -> str:
        """Returns the currently active visual theme ('dark' or 'light')."""
        return self._effective_theme

    def apply_theme(
        self,
        theme_mode: str,
        app: Optional[QApplication] = None,
        config=None,
    ) -> str:
        """Applies stylesheet and icon palette for the given theme mode."""
        app = app or QApplication.instance()
        self._current_mode = theme_mode
        eff = get_effective_theme(theme_mode)
        self._effective_theme = eff

        # Update icons palette
        set_icon_theme(eff)

        # Load QSS
        styles_dir = Path(__file__).resolve().parent
        qss_file = "light_fluent.qss" if eff == THEME_LIGHT else "dark_fluent.qss"
        qss_path = styles_dir / qss_file

        if qss_path.exists() and app:
            try:
                with open(qss_path, "r", encoding="utf-8") as f:
                    qss_content = f.read()
                app.setStyleSheet(qss_content)
            except Exception:
                pass

        if config is not None:
            config.theme = theme_mode

        self.theme_changed.emit(eff)
        return eff


# Global singleton instance
theme_manager = ThemeManager()
