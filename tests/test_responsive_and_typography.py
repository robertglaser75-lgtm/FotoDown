"""Unit tests for responsive breakpoints, compact laptop modes, typography scale, and elided labels."""

import os
from pathlib import Path
import unittest

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QPaintEvent, QPixmap
from PySide6.QtWidgets import QApplication

from core.config import AppConfig
from gui_qt.main_window import MainWindow
from gui_qt.views.transfer_tab import TransferTabView
from gui_qt.widgets.elided_label import ElidedLabel
from gui_qt.widgets.header_banner import HeaderBanner


class TestElidedLabel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DISPLAY"):
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_elided_label_stores_and_returns_full_text(self):
        """ElidedLabel must preserve the full path in full_text() and tooltip."""
        long_path = "C:/Users/Photographer/Pictures/2026/Spring_Vacation_Spain/RAW/IMG_20260415_142359.CR3"
        lbl = ElidedLabel(long_path)
        self.assertEqual(lbl.full_text(), long_path)
        self.assertEqual(lbl.toolTip(), long_path)

        new_path = "/media/nas/archive/photos/2026/04/P1010042.ORF"
        lbl.setText(new_path)
        self.assertEqual(lbl.full_text(), new_path)
        self.assertEqual(lbl.toolTip(), new_path)

    def test_elided_label_rendering(self):
        """Paint event must execute cleanly on narrow widths without exceptions."""
        lbl = ElidedLabel("D:/Very/Long/Path/That/Will/Definitely/Exceed/Narrow/Width/IMG_0001.JPG")
        lbl.resize(80, 24)
        lbl.show()

        pix = QPixmap(80, 24)
        lbl.render(pix)
        self.assertFalse(pix.isNull())
        lbl.close()


class TestHeaderBannerCompactMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DISPLAY"):
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_compact_mode_toggle(self):
        """HeaderBanner must switch between concise laptop and full desktop button labels."""
        cfg = AppConfig()
        banner = HeaderBanner(cfg)

        # Standard desktop mode
        banner.set_compact_mode(False)
        self.assertEqual(banner.lbl_drive.text(), "Speicherkarte / Laufwerk:")
        self.assertEqual(banner.btn_tab_import.text(), "1. Importieren")
        self.assertEqual(banner.btn_refresh.text(), "Neu laden")
        self.assertEqual(banner.btn_help.text(), "Hilfe")

        # Compact laptop mode (< 1180px)
        banner.set_compact_mode(True)
        self.assertEqual(banner.lbl_drive.text(), "Quelle:")
        self.assertEqual(banner.btn_tab_import.text(), "1. Import")
        self.assertEqual(banner.btn_refresh.text(), "")
        self.assertEqual(banner.btn_help.text(), "")

        # Restore
        banner.set_compact_mode(False)
        self.assertEqual(banner.lbl_drive.text(), "Speicherkarte / Laufwerk:")
        self.assertEqual(banner.btn_tab_import.text(), "1. Importieren")
        banner.close()


class TestTransferTabCompactMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DISPLAY"):
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_transfer_tab_compact_mode(self):
        """TransferTabView must adapt central action buttons and search bars to compact widths."""
        cfg = AppConfig()
        tab = TransferTabView(cfg)

        # Standard mode
        tab.set_compact_mode(False)
        self.assertEqual(tab.btn_copy_sel.text(), "Kopieren")
        self.assertEqual(tab.btn_move_sel.text(), "Verschieben")
        self.assertEqual(tab.btn_copy_all.text(), "Alle kopieren")
        self.assertEqual(tab.pane_source.edit_search.placeholderText(), "Dateiname filtern...")

        # Compact laptop mode
        tab.set_compact_mode(True)
        self.assertEqual(tab.btn_copy_sel.text(), "")
        self.assertEqual(tab.btn_move_sel.text(), "")
        self.assertEqual(tab.btn_copy_all.text(), "")
        self.assertEqual(tab.pane_source.edit_search.placeholderText(), "Suchen...")
        self.assertEqual(tab.center_panel.width(), 46)

        # Restore
        tab.set_compact_mode(False)
        self.assertEqual(tab.btn_copy_sel.text(), "Kopieren")
        self.assertEqual(tab.pane_source.edit_search.placeholderText(), "Dateiname filtern...")
        tab.close()


class TestTypographyTokens(unittest.TestCase):
    def test_typography_classes_defined_in_stylesheets(self):
        """Both dark_fluent.qss and light_fluent.qss must define the 5-step typography scale."""
        styles_dir = Path(__file__).resolve().parent.parent / "gui_qt" / "styles"
        dark_qss = (styles_dir / "dark_fluent.qss").read_text(encoding="utf-8")
        light_qss = (styles_dir / "light_fluent.qss").read_text(encoding="utf-8")

        required_tokens = [
            ".microText",
            ".captionText",
            ".bodyText",
            ".subheadingText",
            ".titleText",
            ".textMuted",
            ".textAccent",
            ".textMono",
        ]

        for token in required_tokens:
            self.assertIn(token, dark_qss, f"Dark QSS missing token: {token}")
            self.assertIn(token, light_qss, f"Light QSS missing token: {token}")


if __name__ == "__main__":
    unittest.main()
