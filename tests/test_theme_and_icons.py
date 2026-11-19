"""Unit tests for Vitrina vector icons and theme management (Dark / Light Fluent)."""

import os
from pathlib import Path
import unittest

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from core.config import AppConfig
from gui_qt.styles.icons import (
    get_archive_icon,
    get_clear_icon,
    get_culling_icon,
    get_eject_icon,
    get_files_icon,
    get_filter_icon,
    get_folder_icon,
    get_folder_open_icon,
    get_fullscreen_exit_icon,
    get_fullscreen_icon,
    get_gear_icon,
    get_grid_icon,
    get_grid_large_icon,
    get_grid_small_icon,
    get_help_icon,
    get_history_icon,
    get_icon_color,
    get_import_icon,
    get_info_icon,
    get_plus_icon,
    get_refresh_icon,
    get_save_icon,
    get_search_icon,
    get_star_icon,
    get_tag_icon,
    get_theme_icon,
    get_trash_icon,
    get_video_icon,
    get_zoom_fit_icon,
    get_zoom_icon,
    set_icon_theme,
)
from gui_qt.styles.theme import (
    THEME_DARK,
    THEME_LIGHT,
    THEME_SYSTEM,
    detect_system_theme,
    get_effective_theme,
    theme_manager,
)


class TestVectorIcons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DISPLAY"):
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_all_vector_icons_render_valid_pixmaps(self):
        """Verifies that all new and updated vector icon generators return non-null, valid QIcons."""
        icon_factories = [
            ("import", lambda: get_import_icon(size=20)),
            ("culling", lambda: get_culling_icon(size=20)),
            ("archive", lambda: get_archive_icon(size=20)),
            ("tag", lambda: get_tag_icon(size=20)),
            ("fullscreen", lambda: get_fullscreen_icon(size=20)),
            ("fullscreen_exit", lambda: get_fullscreen_exit_icon(size=20)),
            ("zoom", lambda: get_zoom_icon(size=20)),
            ("zoom_fit", lambda: get_zoom_fit_icon(size=20)),
            ("info", lambda: get_info_icon(size=20)),
            ("save", lambda: get_save_icon(size=20)),
            ("trash", lambda: get_trash_icon(size=20)),
            ("folder_open", lambda: get_folder_open_icon(size=20)),
            ("theme_dark", lambda: get_theme_icon("dark", size=20)),
            ("theme_light", lambda: get_theme_icon("light", size=20)),
            ("theme_system", lambda: get_theme_icon("system", size=20)),
            ("eject", lambda: get_eject_icon(size=20)),
            ("history", lambda: get_history_icon(size=20)),
            ("help", lambda: get_help_icon(size=20)),
            ("star_filled", lambda: get_star_icon(filled=True, size=20)),
            ("star_outline", lambda: get_star_icon(filled=False, size=20)),
            ("refresh", lambda: get_refresh_icon(size=20)),
            ("clear", lambda: get_clear_icon(size=20)),
            ("search", lambda: get_search_icon(size=20)),
            ("folder", lambda: get_folder_icon(size=20)),
            ("filter", lambda: get_filter_icon(size=20)),
            ("gear", lambda: get_gear_icon(size=20)),
            ("plus", lambda: get_plus_icon(size=20)),
            ("files", lambda: get_files_icon(size=20)),
            ("grid_small", lambda: get_grid_small_icon(size=20)),
            ("grid_large", lambda: get_grid_large_icon(size=20)),
            ("video", lambda: get_video_icon(size=20)),
        ]

        for name, factory in icon_factories:
            icon = factory()
            self.assertIsInstance(icon, QIcon, f"Icon {name} must be a QIcon")
            self.assertFalse(icon.isNull(), f"Icon {name} must not be null")
            pix = icon.pixmap(QSize(20, 20), 1.0)
            self.assertFalse(pix.isNull(), f"Icon {name} pixmap must not be null")
            self.assertEqual(pix.width(), 20, f"Icon {name} width mismatch")
            self.assertEqual(pix.height(), 20, f"Icon {name} height mismatch")

            pix_hidpi = icon.pixmap(QSize(20, 20), 2.0)
            self.assertEqual(pix_hidpi.width(), 40, f"Icon {name} HiDPI 2x physical width mismatch")
            self.assertEqual(pix_hidpi.height(), 40, f"Icon {name} HiDPI 2x physical height mismatch")
            self.assertEqual(pix_hidpi.devicePixelRatio(), 2.0)

    def test_icon_theme_color_palette(self):
        """Verifies that switching icon theme changes the resolved palette colors."""
        set_icon_theme("dark")
        dark_normal = get_icon_color("normal")
        dark_accent = get_icon_color("accent")
        self.assertEqual(dark_normal, "#cbd5e1")
        self.assertEqual(dark_accent, "#38bdf8")

        set_icon_theme("light")
        light_normal = get_icon_color("normal")
        light_accent = get_icon_color("accent")
        self.assertEqual(light_normal, "#334155")
        self.assertEqual(light_accent, "#0284c7")

        # Reset back to dark
        set_icon_theme("dark")

    def test_dropdown_distinct_icons(self):
        """Verifies that dropdown menus use non-null, distinct icons for different settings."""
        from gui_qt.views.transfer_tab import TransferTabView
        tab = TransferTabView(AppConfig())

        # 1. combo_view_mode: Liste, Klein, Mittel, Groß must all have non-null icons
        view_mode_icons = []
        for i in range(tab.pane_source.combo_view_mode.count()):
            ico = tab.pane_source.combo_view_mode.itemIcon(i)
            self.assertFalse(ico.isNull(), f"View mode item {i} icon must not be null")
            pix = ico.pixmap(16, 16)
            self.assertFalse(pix.isNull())
            view_mode_icons.append(pix.toImage().bits().tobytes())

        # Ensure that Klein, Mittel and Groß have distinct icon pixel data
        self.assertNotEqual(view_mode_icons[1], view_mode_icons[2], "Klein and Mittel icons must differ")
        self.assertNotEqual(view_mode_icons[2], view_mode_icons[3], "Mittel and Groß icons must differ")
        self.assertNotEqual(view_mode_icons[1], view_mode_icons[3], "Klein and Groß icons must differ")

        # 2. combo_type: all formats must have icons
        for i in range(tab.pane_source.combo_type.count()):
            ico = tab.pane_source.combo_type.itemIcon(i)
            self.assertFalse(ico.isNull(), f"Type filter item {i} must have an icon")

        # 3. combo_sort: all sort items must have icons
        for i in range(tab.pane_source.combo_sort.count()):
            ico = tab.pane_source.combo_sort.itemIcon(i)
            self.assertFalse(ico.isNull(), f"Sort item {i} must have an icon")

        tab.close()


class TestThemeManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DISPLAY"):
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def test_detect_system_theme(self):
        """System theme detection should return either 'dark' or 'light'."""
        sys_theme = detect_system_theme()
        self.assertIn(sys_theme, [THEME_DARK, THEME_LIGHT])

    def test_get_effective_theme(self):
        """Resolves theme modes correctly."""
        self.assertEqual(get_effective_theme(THEME_DARK), THEME_DARK)
        self.assertEqual(get_effective_theme(THEME_LIGHT), THEME_LIGHT)
        self.assertIn(get_effective_theme(THEME_SYSTEM), [THEME_DARK, THEME_LIGHT])

    def test_theme_manager_apply_theme(self):
        """Tests applying themes and signal emission."""
        received = []
        theme_manager.theme_changed.connect(lambda eff: received.append(eff))

        cfg = AppConfig()
        eff_light = theme_manager.apply_theme(THEME_LIGHT, self.app, config=cfg)
        self.assertEqual(eff_light, THEME_LIGHT)
        self.assertEqual(cfg.theme, THEME_LIGHT)
        self.assertIn(THEME_LIGHT, received)

        eff_dark = theme_manager.apply_theme(THEME_DARK, self.app, config=cfg)
        self.assertEqual(eff_dark, THEME_DARK)
        self.assertEqual(cfg.theme, THEME_DARK)
        self.assertIn(THEME_DARK, received)

    def test_stylesheets_exist_and_meet_contrast_criteria(self):
        """Verifies that dark_fluent.qss and light_fluent.qss exist and define opposite contrasting color schemes."""
        styles_dir = Path(__file__).resolve().parent.parent / "gui_qt" / "styles"
        dark_path = styles_dir / "dark_fluent.qss"
        light_path = styles_dir / "light_fluent.qss"

        self.assertTrue(dark_path.exists(), "dark_fluent.qss must exist")
        self.assertTrue(light_path.exists(), "light_fluent.qss must exist")

        with open(dark_path, "r", encoding="utf-8") as f:
            dark_qss = f.read()

        with open(light_path, "r", encoding="utf-8") as f:
            light_qss = f.read()

        # Dark theme: dark background (#0f172a), bright text (#f8fafc)
        self.assertIn("#0f172a", dark_qss)
        self.assertIn("#f8fafc", dark_qss)

        # Light theme: bright background (#f8fafc / #ffffff), dark text (#0f172a)
        self.assertIn("#f8fafc", light_qss)
        self.assertIn("#ffffff", light_qss)
        self.assertIn("#0f172a", light_qss)

    def test_config_theme_persistence(self):
        """Tests that AppConfig preserves and serializes the theme setting."""
        cfg = AppConfig()
        self.assertEqual(cfg.theme, "dark")
        cfg.theme = "light"

        d = cfg.to_dict() if hasattr(cfg, "to_dict") else vars(cfg)
        self.assertEqual(d["theme"], "light")


if __name__ == "__main__":
    unittest.main()
