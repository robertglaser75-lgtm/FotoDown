"""Application entry point for Vitrina PySide6 Qt GUI."""

from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from core.version import __version__
from .main_window import MainWindow
from .widgets.splash_screen import VitrinaSplashScreen, FotoDownSplashScreen


def run_gui():
    """Initializes and runs the Vitrina Qt Application."""
    # High-DPI handling
    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    # Windows specific Taskbar Icon grouping
    if sys.platform == "win32":
        try:
            import ctypes
            app_id = f"RobertGlaser.Vitrina.App.{__version__}"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("Vitrina")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("RobertGlaser")

    # Initialize theme engine with default dark theme (MainWindow synchronizes with config)
    from .styles.theme import theme_manager
    theme_manager.apply_theme("dark", app)

    # Set Multi-Resolution Window Icon
    app_icon = QIcon()
    for size_name in ["icon_16.png", "icon_32.png", "icon_48.png", "icon_64.png", "icon_128.png", "icon_256.png", "icon_512.png", "vitrina.png"]:
        p = Path("assets") / size_name
        if p.exists():
            app_icon.addFile(str(p))
    for ico_name in ["vitrina.ico", "icon.ico", "fotodown.ico"]:
        p = Path("assets") / ico_name
        if p.exists():
            app_icon.addFile(str(p))
            break
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    # Show Splash Screen
    splash = VitrinaSplashScreen()
    splash.show()
    splash.set_status("Lade Farbschema & Ressourcen...", 1, 5)

    window = MainWindow(splash=splash)
    splash.set_status("Bereit!", 5, 5)

    window.show()
    splash.finish(window)

    return app.exec()
