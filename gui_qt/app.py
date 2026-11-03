"""Application entry point for FotoDown PySide6 Qt GUI."""

from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from core.version import __version__
from .main_window import MainWindow
from .widgets.splash_screen import FotoDownSplashScreen


def run_gui():
    """Initializes and runs the FotoDown Qt Application."""
    # High-DPI handling
    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    # Windows specific Taskbar Icon grouping
    if sys.platform == "win32":
        try:
            import ctypes
            app_id = f"RobertGlaser.FotoDown.App.{__version__}"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("FotoDown")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("RobertGlaser")

    # Load and apply dark fluent stylesheet
    qss_path = Path(__file__).resolve().parent / "styles" / "dark_fluent.qss"
    if qss_path.exists():
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
        except Exception:
            pass

    # Set Window Icon
    for icon_name in ["icon.png", "icon_64.png", "fotodown.ico", "icon.ico"]:
        icon_path = Path("assets") / icon_name
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
            break

    # Show Splash Screen
    splash = FotoDownSplashScreen()
    splash.show()
    splash.set_status("Lade Farbschema & Ressourcen...", 1, 5)

    window = MainWindow(splash=splash)
    splash.set_status("Bereit!", 5, 5)

    window.show()
    splash.finish(window)

    return app.exec()
