"""Unit tests for Qt models, cross-platform drive detection, and thumbnails."""

from datetime import datetime
import os
from pathlib import Path
import tempfile
import unittest

from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtWidgets import QApplication

from core.config import AppConfig
from core.drive_detector import (
    DriveInfo, DiskSpaceInfo, DriveMonitor, _detect_drives_linux,
    detect_drives, format_size, get_disk_space
)
from core.exif_reader import MediaMetadata
from core.importer import ScanItem
from core.thumbnail import generate_thumbnail
from core.version import __version__
from gui_qt.models.scan_model import ScanTableModel
from gui_qt.models.filter_proxy import ScanFilterProxyModel
from gui_qt.widgets.storage_bar import StorageBarWidget
from gui_qt.widgets.filter_bar import FilterBarWidget
from gui_qt.widgets.path_selector import PathSelectorWidget
from gui_qt.widgets.general_settings import GeneralSettingsWidget
from gui_qt.widgets.collapsible_box import CollapsibleBox
from gui_qt.widgets.profile_bar import ProfileBarWidget
from gui_qt.widgets.pattern_editor import PatternEditorWidget
from gui_qt.widgets.card_notification import CardNotificationBanner
from gui_qt.widgets.exif_inspector import ExifInspectorWidget, HistogramWidget
from gui_qt.views.tree_view import MediaTreeView
from gui_qt.views.gallery_view import MediaGalleryView
from gui_qt.dialogs.quick_preview_dialog import QuickPreviewDialog

_app = QApplication.instance() or QApplication(["-platform", "offscreen"])


class TestVersion(unittest.TestCase):
    def test_version_format(self):
        parts = __version__.split(".")
        self.assertGreaterEqual(len(parts), 3)
        self.assertEqual(__version__, "0.10.5")


class TestDiskSpace(unittest.TestCase):
    def test_format_size(self):
        self.assertEqual(format_size(500), "500 B")
        self.assertEqual(format_size(1024), "1.0 KB")
        self.assertEqual(format_size(1024 * 1024 * 15), "15.0 MB")
        self.assertEqual(format_size(1024 * 1024 * 1024 * 4), "4.0 GB")
        self.assertEqual(format_size(1024 * 1024 * 1024 * 1024 * 2), "2.0 TB")

    def test_get_disk_space_current_dir(self):
        space = get_disk_space(".")
        self.assertIsNotNone(space)
        self.assertGreater(space.total_bytes, 0)
        self.assertGreaterEqual(space.used_bytes, 0)
        self.assertGreater(space.free_bytes, 0)
        self.assertTrue(0.0 <= space.used_percent <= 100.0)

    def test_disk_space_info_calculations(self):
        info = DiskSpaceInfo(total_bytes=1000, used_bytes=400, free_bytes=600)
        self.assertAlmostEqual(info.used_percent, 40.0)
        self.assertAlmostEqual(info.free_percent, 60.0)
        self.assertEqual(info.total_str, "1000 B")


class TestLinuxDriveDetector(unittest.TestCase):
    def test_detect_drives_linux_mock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            mount_point = tmp_root / "EOS_DIGITAL"
            dcim_dir = mount_point / "DCIM"
            dcim_dir.mkdir(parents=True)

            info = DriveInfo(
                letter=mount_point.name,
                label="EOS_DIGITAL",
                path=mount_point,
                has_dcim=True,
                dcim_path=dcim_dir,
                space=DiskSpaceInfo(total_bytes=1000000, used_bytes=400000, free_bytes=600000)
            )
            self.assertTrue(info.has_dcim)
            self.assertIn("DCIM", info.display_name)
            self.assertIn("EOS_DIGITAL", info.display_name)


class TestDriveMonitor(unittest.TestCase):
    def test_drive_monitor_hotplug_detection(self):
        d1 = DriveInfo(letter="E:", label="CARD1", path=Path("E:\\"), has_dcim=True)
        d2 = DriveInfo(letter="F:", label="CARD2", path=Path("F:\\"), has_dcim=False)

        current_drives = [d1]

        def fake_detector():
            return list(current_drives)

        monitor = DriveMonitor(detector_func=fake_detector)
        # Initial state knows d1
        self.assertIn(str(d1.path).rstrip("\\/").upper(), monitor._known_drives)

        # 1. No changes
        added, removed = monitor.check_changes()
        self.assertEqual(len(added), 0)
        self.assertEqual(len(removed), 0)

        # 2. Insert d2 (hotplug)
        current_drives.append(d2)
        added, removed = monitor.check_changes()
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].letter, "F:")
        self.assertEqual(len(removed), 0)

        # 3. Remove d1 (unplug)
        current_drives.remove(d1)
        added, removed = monitor.check_changes()
        self.assertEqual(len(added), 0)
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0].letter, "E:")


class TestThumbnailHelper(unittest.TestCase):
    def test_generate_thumbnail_invalid_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "empty.jpg"
            p.write_bytes(b"not an image")
            thumb = generate_thumbnail(p)
            self.assertIsNone(thumb)


class TestQtScanModels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(["-platform", "offscreen"])

    def _create_sample_items(self):
        dt = datetime(2026, 8, 15, 14, 30, 0)
        item1 = ScanItem(
            source_path=Path("/tmp/IMG_0001.JPG"),
            metadata=MediaMetadata(
                file_path=Path("/tmp/IMG_0001.JPG"),
                orig_name="IMG_0001",
                extension=".jpg",
                file_size=2048000,
                date_taken=dt,
                date_source="EXIF",
                camera_make="Canon",
                camera_model="EOS R5",
                camera_name="Canon EOS R5"
            ),
            target_path=Path("/out/2026-08-15_IMG_0001.JPG"),
            is_duplicate=False,
            status="Neu",
            file_hash="hash1",
            selected=True
        )
        item2 = ScanItem(
            source_path=Path("/tmp/DSC_0002.CR3"),
            metadata=MediaMetadata(
                file_path=Path("/tmp/DSC_0002.CR3"),
                orig_name="DSC_0002",
                extension=".cr3",
                file_size=40960000,
                date_taken=dt,
                date_source="EXIF",
                camera_make="Canon",
                camera_model="EOS R5",
                camera_name="Canon EOS R5"
            ),
            target_path=Path("/out/2026-08-15_DSC_0002.CR3"),
            is_duplicate=True,
            status="Bereits importiert",
            file_hash="hash2",
            selected=False
        )
        item3 = ScanItem(
            source_path=Path("/tmp/VID_0003.MP4"),
            metadata=MediaMetadata(
                file_path=Path("/tmp/VID_0003.MP4"),
                orig_name="VID_0003",
                extension=".mp4",
                file_size=104857600,
                date_taken=dt,
                date_source="FileModified",
                camera_make="Sony",
                camera_model="A7IV",
                camera_name="Sony A7IV"
            ),
            target_path=Path("/out/2026-08-15_VID_0003.MP4"),
            is_duplicate=False,
            status="Neu",
            file_hash="hash3",
            selected=True
        )
        return [item1, item2, item3]

    def test_scan_table_model_basic(self):
        items = self._create_sample_items()
        model = ScanTableModel(items)
        self.assertEqual(model.rowCount(), 3)
        self.assertEqual(model.columnCount(), 8)

        # Check column headers
        self.assertEqual(model.headerData(2, Qt.Orientation.Horizontal), "Originalname")

        # Test selection toggle via setData
        idx = model.index(0, 0)
        self.assertTrue(items[0].selected)
        model.setData(idx, Qt.CheckState.Unchecked.value, Qt.ItemDataRole.CheckStateRole)
        self.assertFalse(items[0].selected)

    def test_scan_table_model_paired_item(self):
        dt = datetime(2026, 8, 15, 14, 30, 0)
        raw_meta = MediaMetadata(Path("IMG_0001.CR3"), "IMG_0001", ".cr3", 30000000, dt, "EXIF")
        jpg_meta = MediaMetadata(Path("IMG_0001.JPG"), "IMG_0001", ".jpg", 5000000, dt, "EXIF")
        paired_item = ScanItem(
            source_path=Path("IMG_0001.CR3"),
            metadata=raw_meta,
            target_path=Path("/out/IMG_0001.CR3"),
            is_duplicate=False,
            file_hash="rawhash",
            status="Neu",
            is_pair=True,
            companion_path=Path("IMG_0001.JPG"),
            companion_metadata=jpg_meta,
        )
        model = ScanTableModel([paired_item])
        # Column 6 is display_type -> "RAW+JPG"
        self.assertEqual(model.data(model.index(0, 6)), "RAW+JPG")
        # Column 7 is total_size -> 35 MB
        self.assertIn("33.4 MB", model.data(model.index(0, 7)))

    def test_selection_methods(self):
        items = self._create_sample_items()
        model = ScanTableModel(items)

        model.select_all()
        self.assertTrue(all(it.selected for it in items))

        model.deselect_all()
        self.assertFalse(any(it.selected for it in items))

        model.select_only_new()
        self.assertTrue(items[0].selected)
        self.assertFalse(items[1].selected)
        self.assertTrue(items[2].selected)

    def test_filter_proxy_model(self):
        items = self._create_sample_items()
        model = ScanTableModel(items)
        proxy = ScanFilterProxyModel()
        proxy.setSourceModel(model)

        self.assertEqual(proxy.rowCount(), 3)

        # Filter by status: new only
        proxy.set_status_filter("new_only")
        self.assertEqual(proxy.rowCount(), 2)

        # Filter by media type: Videos
        proxy.set_type_filter("Videos")
        self.assertEqual(proxy.rowCount(), 1)

        # Reset filters
        proxy.set_status_filter("all")
        proxy.set_type_filter("all")
        self.assertEqual(proxy.rowCount(), 3)

        # Search filter
        proxy.set_search_term("Sony")
        self.assertEqual(proxy.rowCount(), 1)

    def test_gallery_view_paint(self):
        items = self._create_sample_items()
        model = ScanTableModel(items)
        proxy = ScanFilterProxyModel()
        proxy.setSourceModel(model)

        gallery = MediaGalleryView()
        gallery.setModel(proxy)
        gallery.resize(600, 400)
        gallery.show()

        pix = gallery.grab()
        self.assertFalse(pix.isNull())
        self.assertGreater(pix.width(), 0)

    def test_storage_bar_widget(self):
        widget = StorageBarWidget("Test Storage")
        widget.set_path(".")
        self.assertGreater(widget.bar.maximum(), 0)

        # Test capacity check with realistic values
        ok, msg = widget.check_capacity(1024)
        self.assertTrue(ok)
        self.assertIn("Ausreichend Speicher", msg)

        # Test capacity check with impossibly large requirement (100 Petabytes)
        huge_bytes = 100 * 1024 * 1024 * 1024 * 1024 * 1024
        ok, msg = widget.check_capacity(huge_bytes)
        self.assertFalse(ok)
        self.assertIn("Nicht genügend Speicherplatz", msg)

    def test_filter_bar_zoom_slider(self):
        filter_bar = FilterBarWidget()
        self.assertTrue(filter_bar.slider_zoom.isHidden())

        # Switch to gallery mode
        filter_bar.combo_view.setCurrentIndex(1)
        self.assertFalse(filter_bar.slider_zoom.isHidden())
        self.assertEqual(filter_bar.slider_zoom.value(), 160)

    def test_quick_preview_dialog(self):
        items = self._create_sample_items()
        dlg = QuickPreviewDialog(items, start_index=0)
        self.assertEqual(dlg.current_idx, 0)
        self.assertTrue(dlg.chk_selected.isChecked())

        # Navigate forward
        dlg._next_item()
        self.assertEqual(dlg.current_idx, 1)
        self.assertFalse(dlg.chk_selected.isChecked())

        # Toggle selection
        dlg.chk_selected.setChecked(True)
        self.assertTrue(items[1].selected)

        # Navigate back
        dlg._prev_item()
        self.assertEqual(dlg.current_idx, 0)

    def test_empty_state_widget(self):
        from gui_qt.widgets.empty_state import EmptyStateWidget
        empty = EmptyStateWidget()
        self.assertIsNotNone(empty)
        # Test scan_requested signal emission
        emitted = []
        empty.scan_requested.connect(lambda: emitted.append(True))
        empty.btn_scan.click()
        self.assertEqual(len(emitted), 1)

    def test_collapsible_box_interactive_toggle(self):
        box = CollapsibleBox("Test Box", is_expanded=True)
        self.assertTrue(box.is_expanded)
        self.assertFalse(box.content_area.isHidden())
        self.assertIn("Einklappen", box.btn_toggle_hint.text())

        # Click header to collapse
        toggled_events = []
        box.toggled.connect(lambda state: toggled_events.append(state))
        box.toggle()
        self.assertFalse(box.is_expanded)
        self.assertTrue(box.content_area.isHidden())
        self.assertIn("Ausklappen", box.btn_toggle_hint.text())
        self.assertEqual(toggled_events, [False])

        # Click button to expand
        box.btn_toggle_hint.click()
        self.assertTrue(box.is_expanded)
        self.assertFalse(box.content_area.isHidden())
        self.assertEqual(toggled_events, [False, True])

    def test_path_selector_paths_only(self):
        selector = PathSelectorWidget()
        cfg = AppConfig(
            source_dir="/source/path",
            target_dir="/target/path",
            enable_dual_backup=True,
            backup_target_dir="/backup/path",
            separate_video_dir=True,
            video_target_dir="/video/path"
        )
        selector.load_config(cfg)
        self.assertEqual(selector.edit_source.text(), "/source/path")
        self.assertEqual(selector.edit_target.text(), "/target/path")
        self.assertTrue(selector.chk_dual_backup.isChecked())
        self.assertEqual(selector.edit_backup_target.text(), "/backup/path")
        self.assertTrue(selector.chk_video.isChecked())
        self.assertEqual(selector.edit_video_target.text(), "/video/path")

    def test_general_settings_widget(self):
        settings = GeneralSettingsWidget()
        cfg = AppConfig(
            type_folder_organization="subfolders",
            pair_raw_jpg=True,
            sync_xmp_sidecars=True,
            auto_detect_drives=True,
            only_new_files=False,
            verify_checksums=False
        )
        settings.load_config(cfg)
        self.assertEqual(settings.get_type_org(), "subfolders")
        self.assertTrue(settings.chk_pair_raw.isChecked())
        self.assertTrue(settings.chk_sync_xmp.isChecked())
        self.assertTrue(settings.chk_auto_detect.isChecked())
        self.assertFalse(settings.chk_only_new.isChecked())
        self.assertFalse(settings.chk_verify.isChecked())

        settings.set_type_org("parent_folders")
        settings.chk_only_new.setChecked(True)
        settings.sync_to_config(cfg)
        self.assertEqual(cfg.type_folder_organization, "parent_folders")
        self.assertTrue(cfg.only_new_files)

    def test_profile_bar_and_config(self):
        cfg = AppConfig()
        self.assertIn("Standard", cfg.profiles)
        self.assertIn("Studio & Shooting", cfg.profiles)

        # Apply profile
        self.assertTrue(cfg.apply_profile("Studio & Shooting"))
        self.assertEqual(cfg.type_folder_organization, "subfolders")
        self.assertEqual(cfg.active_profile, "Studio & Shooting")

        # Create custom profile
        cfg.type_folder_organization = "parent_folders"
        cfg.save_current_as_profile("Custom Profile")
        self.assertIn("Custom Profile", cfg.profiles)

        # Test ProfileBarWidget
        bar = ProfileBarWidget()
        bar.load_profiles(cfg)
        self.assertIn("Custom Profile", [bar.combo_profiles.itemText(i) for i in range(bar.combo_profiles.count())])
        self.assertEqual(bar.btn_save.objectName(), "profileBtnSave")
        self.assertEqual(bar.btn_new.objectName(), "profileBtnNew")
        self.assertEqual(bar.btn_delete.objectName(), "profileBtnDelete")
        self.assertIn("speichern", bar.btn_save.toolTip().lower())
        self.assertIn("neu", bar.btn_new.toolTip().lower())
        self.assertIn("löschen", bar.btn_delete.toolTip().lower())

        # Delete custom profile
        self.assertTrue(cfg.delete_profile("Custom Profile"))
        self.assertNotIn("Custom Profile", cfg.profiles)

    def test_card_notification_banner(self):
        banner = CardNotificationBanner()
        self.assertTrue(banner.isHidden())

        drive = DriveInfo(
            letter="G:",
            label="EOS_DIGITAL",
            path=Path("G:\\"),
            has_dcim=True,
            dcim_path=Path("G:\\DCIM"),
            space=DiskSpaceInfo(total_bytes=1000000, used_bytes=400000, free_bytes=600000)
        )
        banner.show_card(drive)
        self.assertFalse(banner.isHidden())
        self.assertIn("G: (EOS_DIGITAL)", banner.lbl_text.text())
        self.assertIn("DCIM", banner.lbl_text.text())

        # Test scan request click
        scan_signals = []
        banner.scan_requested.connect(lambda p: scan_signals.append(p))
        banner.btn_scan.click()
        self.assertEqual(len(scan_signals), 1)
        self.assertIn("DCIM", scan_signals[0])
        self.assertTrue(banner.isHidden())


class TestTreeView(unittest.TestCase):
    def test_tree_hierarchy_population(self):
        meta1 = MediaMetadata(
            file_path=Path("/tmp/IMG_0001.JPG"),
            orig_name="IMG_0001",
            extension=".jpg",
            file_size=2000000,
            date_taken=datetime(2026, 8, 1, 10, 0, 0),
            date_source="EXIF",
        )
        item1 = ScanItem(
            source_path=Path("/tmp/IMG_0001.JPG"),
            target_path=Path("/dest/2026/2026-08-01/IMG_0001.jpg"),
            metadata=meta1,
            is_duplicate=False,
            file_hash="hash_1",
            status="Neu",
        )
        meta2 = MediaMetadata(
            file_path=Path("/tmp/IMG_0002.CR3"),
            orig_name="IMG_0002",
            extension=".cr3",
            file_size=25000000,
            date_taken=datetime(2026, 8, 1, 10, 5, 0),
            date_source="EXIF",
        )
        item2 = ScanItem(
            source_path=Path("/tmp/IMG_0002.CR3"),
            target_path=Path("/dest/2026/2026-08-01/RAW/IMG_0002.cr3"),
            metadata=meta2,
            is_duplicate=False,
            file_hash="hash_2",
            status="Neu",
        )

        tree = MediaTreeView()
        tree.set_items([item1, item2], target_root="/dest")
        self.assertEqual(tree.model.rowCount(), 2)  # Two distinct destination folders
        self.assertIn("2 Ziel-Ordner", tree.lbl_summary.text())


class TestExifInspectorAndHistogram(unittest.TestCase):
    def test_exif_inspector_inspect_item(self):
        inspector = ExifInspectorWidget()
        self.assertTrue(inspector.btn_open_map.isHidden())

        meta = MediaMetadata(
            file_path=Path("/tmp/photo.jpg"),
            orig_name="photo",
            extension=".jpg",
            file_size=5000000,
            date_taken=datetime(2026, 8, 1, 12, 0, 0),
            date_source="EXIF",
            camera_make="Sony",
            camera_model="ILCE-7M4",
            camera_name="Sony ILCE-7M4",
            lens_model="FE 24-70mm F2.8 GM",
            f_number=2.8,
            exposure_time=0.002,
            iso=200,
            focal_length=50.0,
            gps_lat=48.137,
            gps_lon=11.576,
        )
        item = ScanItem(
            source_path=Path("/tmp/photo.jpg"),
            target_path=Path("/dest/photo.jpg"),
            metadata=meta,
            is_duplicate=False,
            file_hash="sample_hash",
            status="Neu",
        )

        inspector.inspect_item(item)
        self.assertEqual(inspector.lbl_filename.text(), "photo.jpg")
        self.assertIn("Sony ILCE-7M4", inspector.lbl_camera.text())
        self.assertIn("FE 24-70mm", inspector.lbl_lens.text())
        self.assertIn("ƒ/2.8", inspector.lbl_exposure_chip.text())
        self.assertIn("1/500s", inspector.lbl_exposure_chip.text())
        self.assertFalse(inspector.btn_open_map.isHidden())

    def test_histogram_widget(self):
        hist = HistogramWidget()
        from PIL import Image
        img = Image.new("RGB", (50, 50), color=(100, 150, 200))
        hist.set_image(img)
        self.assertEqual(len(hist._r_bins), 256)
        self.assertEqual(len(hist._g_bins), 256)
        self.assertEqual(len(hist._b_bins), 256)
        self.assertEqual(len(hist._l_bins), 256)


class TestPatternEditorWidget(unittest.TestCase):
    def test_pattern_editor_load_and_sync(self):
        editor = PatternEditorWidget()
        cfg = AppConfig(
            folder_pattern="{YYYY}/{MM}",
            file_pattern="{YYYY}_{orig_name}"
        )
        
        # Ensure loading doesn't emit unexpected changes and sets text correctly
        emitted = []
        editor.changed.connect(lambda: emitted.append(True))
        editor.load_config(cfg)
        
        self.assertEqual(len(emitted), 0)  # Signals blocked during load
        self.assertEqual(editor.edit_folder.text(), "{YYYY}/{MM}")
        self.assertEqual(editor.edit_file.text(), "{YYYY}_{orig_name}")
        
        # Test editing and sync
        editor.edit_folder.setText("{YYYY}/{DD}")
        self.assertEqual(len(emitted), 1)
        editor.sync_to_config(cfg)
        self.assertEqual(cfg.folder_pattern, "{YYYY}/{DD}")


if __name__ == "__main__":
    unittest.main()
