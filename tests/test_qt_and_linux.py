"""Unit tests for Qt models, cross-platform drive detection, and thumbnails."""

from datetime import datetime
import os
from pathlib import Path
import shutil
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
from core.thumbnail import generate_thumbnail, load_preview_image
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
from gui_qt.views.table_view import MediaTableView
from gui_qt.views.tree_view import MediaTreeView
from gui_qt.views.gallery_view import MediaGalleryView
from gui_qt.views.single_view import MediaSingleView
from gui_qt.dialogs.quick_preview_dialog import QuickPreviewDialog
from gui_qt.workers.thumb_worker import ThumbnailSignals, ThumbnailTask

os.environ["FOTODOWN_HEADLESS_TEST"] = "1"
_app = QApplication.instance() or (
    QApplication([]) if os.environ.get("DISPLAY") else QApplication(["-platform", "offscreen"])
)


class TestVersion(unittest.TestCase):
    def test_version_format(self):
        parts = __version__.split(".")
        self.assertGreaterEqual(len(parts), 3)
        self.assertEqual(__version__, "0.33.0")


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


class TestMediaSingleView(unittest.TestCase):
    def test_single_view_navigation_and_selection(self):
        view = MediaSingleView()
        with tempfile.TemporaryDirectory() as tmp_dir:
            from PIL import Image
            img1 = Image.new("RGB", (800, 600), color=(200, 50, 50))
            p1 = Path(tmp_dir) / "test1.jpg"
            img1.save(p1)

            img2 = Image.new("RGB", (800, 600), color=(50, 200, 50))
            p2 = Path(tmp_dir) / "test2.jpg"
            img2.save(p2)

            meta1 = MediaMetadata(file_path=p1, orig_name="test1", extension=".jpg", file_size=1000, date_taken=datetime(2026, 7, 24, 12, 0, 0), date_source="EXIF")
            meta2 = MediaMetadata(file_path=p2, orig_name="test2", extension=".jpg", file_size=1000, date_taken=datetime(2026, 7, 24, 12, 0, 0), date_source="EXIF")

            item1 = ScanItem(source_path=p1, target_path=p1, metadata=meta1, status="Neu", is_duplicate=False, file_hash="hash1", selected=True)
            item2 = ScanItem(source_path=p2, target_path=p2, metadata=meta2, status="Neu", is_duplicate=False, file_hash="hash2", selected=False)

            view.set_items([item1, item2], item1)
            self.assertEqual(view.get_current_item(), item1)
            self.assertEqual(view.lbl_title.text(), "test1.jpg")
            self.assertTrue(view.chk_selected.isChecked())

            # Navigate next
            view._next_item()
            self.assertEqual(view.get_current_item(), item2)
            self.assertEqual(view.lbl_title.text(), "test2.jpg")
            self.assertFalse(view.chk_selected.isChecked())

            # Toggle selection
            view.chk_selected.setChecked(True)
            self.assertTrue(item2.selected)

            # Zoom mode toggle
            self.assertEqual(view._zoom_mode, "fit")
            view._toggle_zoom()
            self.assertEqual(view._zoom_mode, "actual")
            view._toggle_zoom()
            self.assertEqual(view._zoom_mode, "fit")


class TestHighResPreviews(unittest.TestCase):
    def test_load_preview_image_downscaling(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            from PIL import Image
            img = Image.new("RGB", (3000, 2000), color=(50, 100, 150))
            p = Path(tmp_dir) / "large.jpg"
            img.save(p)

            loaded = load_preview_image(p, max_dim=1000)
            self.assertIsNotNone(loaded)
            self.assertLessEqual(max(loaded.width, loaded.height), 1000)


class TestThumbnailWorker(unittest.TestCase):
    def test_thumbnail_task_execution_and_signal(self):
        signals = ThumbnailSignals()
        received = []
        signals.thumbnail_ready.connect(lambda k, qimg: received.append((k, qimg)))

        with tempfile.TemporaryDirectory() as tmp_dir:
            from PIL import Image
            img = Image.new("RGB", (500, 500), color=(100, 150, 200))
            p = Path(tmp_dir) / "thumb_test.jpg"
            img.save(p)

            task = ThumbnailTask(path=p, key_path=str(p), signals=signals, max_size=(320, 320))
            task.run()

            self.assertEqual(len(received), 1)
            key, qimage = received[0]
            self.assertEqual(key, str(p))
            self.assertFalse(qimage.isNull())
            self.assertLessEqual(qimage.width(), 320)
            self.assertLessEqual(qimage.height(), 320)


class TestRangeSelection(unittest.TestCase):
    def test_gallery_range_selection(self):
        gv = MediaGalleryView()
        model = ScanTableModel()
        gv.setModel(model)

        items = []
        for i in range(10):
            meta = MediaMetadata(file_path=Path(f"p{i}.jpg"), orig_name=f"p{i}", extension=".jpg", file_size=1000, date_taken=datetime(2026, 7, 24, 12, 0, 0), date_source="test")
            items.append(ScanItem(source_path=Path(f"p{i}.jpg"), target_path=Path(f"p{i}.jpg"), metadata=meta, status="Neu", is_duplicate=False, file_hash=f"h{i}", selected=False))

        model.set_items(items)

        # 1. Click row 2 without modifiers
        idx2 = model.index(2, 0)
        gv._on_clicked(idx2)
        self.assertTrue(items[2].selected)
        self.assertEqual(gv._last_index.row(), 2)

        # 2. Simulate range click to row 6 (mocking range modifier)
        from unittest.mock import patch
        with patch("PySide6.QtWidgets.QApplication.keyboardModifiers", return_value=Qt.KeyboardModifier.ControlModifier):
            idx6 = model.index(6, 0)
            gv._on_clicked(idx6)

        # Rows 2 to 6 must all be selected
        for r in range(2, 7):
            self.assertTrue(items[r].selected, f"Row {r} should be selected")
        # Rows 0, 1 and 7, 8, 9 must remain unselected
        for r in [0, 1, 7, 8, 9]:
            self.assertFalse(items[r].selected, f"Row {r} should not be selected")

    def test_table_range_selection(self):
        tv = MediaTableView()
        model = ScanTableModel()
        tv.setModel(model)

        items = []
        for i in range(10):
            meta = MediaMetadata(file_path=Path(f"p{i}.jpg"), orig_name=f"p{i}", extension=".jpg", file_size=1000, date_taken=datetime(2026, 7, 24, 12, 0, 0), date_source="test")
            items.append(ScanItem(source_path=Path(f"p{i}.jpg"), target_path=Path(f"p{i}.jpg"), metadata=meta, status="Neu", is_duplicate=False, file_hash=f"h{i}", selected=False))

        model.set_items(items)

        # Click row 1
        idx1 = model.index(1, 0)
        tv._on_clicked(idx1)
        self.assertEqual(tv._last_clicked_row, 1)

        # Click row 4 with ControlModifier
        from unittest.mock import patch
        with patch("PySide6.QtWidgets.QApplication.keyboardModifiers", return_value=Qt.KeyboardModifier.ControlModifier):
            idx4 = model.index(4, 0)
            tv._on_clicked(idx4)

        for r in range(1, 5):
            self.assertTrue(items[r].selected, f"Row {r} should be selected")
        for r in [0, 5, 6, 7, 8, 9]:
            self.assertFalse(items[r].selected, f"Row {r} should not be selected")


class TestDriveEjectionClearPreview(unittest.TestCase):
    def test_clear_preview_on_eject(self):
        from gui_qt.main_window import MainWindow
        win = MainWindow()

        # Simulate items loaded
        meta = MediaMetadata(file_path=Path("test.jpg"), orig_name="test", extension=".jpg", file_size=5000, date_taken=datetime(2026, 7, 24, 12, 0, 0), date_source="test")
        item = ScanItem(source_path=Path("test.jpg"), target_path=Path("test.jpg"), metadata=meta, status="Neu", is_duplicate=False, file_hash="hash1", selected=True)
        win.table_model.set_items([item])
        win.single_view.set_items([item], item)
        win.exif_inspector.inspect_item(item)
        win.path_selector.edit_source.setText("E:\\DCIM")

        self.assertEqual(len(win.table_model.get_items()), 1)
        self.assertIsNotNone(win.exif_inspector._current_item)

        # Trigger drive ejection handler
        win._on_drive_ejected("E:\\")

        # Verify preview is cleared
        self.assertEqual(len(win.table_model.get_items()), 0)
        self.assertEqual(len(win.single_view.items), 0)
        self.assertIsNone(win.exif_inspector._current_item)
        self.assertEqual(win.path_selector.edit_source.text(), "")
        self.assertEqual(win.view_stack.currentWidget(), win.empty_state)

        # Cleanup
        if win._drive_watcher and win._drive_watcher.isRunning():
            win._drive_watcher.stop()
        win.close()


class TestRawPreviewExtraction(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

        # Helper to generate a dummy JPEG bytes payload
        from PIL import Image
        import io
        img = Image.new("RGB", (640, 480), "blue")
        bio = io.BytesIO()
        img.save(bio, "JPEG")
        self.sample_jpg = bio.getvalue()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_extract_fuji_raf(self):
        import struct
        header = bytearray(120)
        header[0:15] = b"FUJIFILMCCD-RAW"
        header[84:88] = struct.pack(">I", 120)
        header[88:92] = struct.pack(">I", len(self.sample_jpg))
        raf_file = self.dir_path / "sample.raf"
        raf_file.write_bytes(bytes(header) + self.sample_jpg)

        from core.thumbnail import extract_raw_embedded_jpeg, generate_thumbnail, load_preview_image
        img = extract_raw_embedded_jpeg(raf_file)
        self.assertIsNotNone(img)
        self.assertEqual(img.size, (640, 480))

        thumb = generate_thumbnail(raf_file, max_size=(160, 120))
        self.assertIsNotNone(thumb)
        self.assertLessEqual(thumb.width, 160)
        self.assertLessEqual(thumb.height, 120)

        preview = load_preview_image(raf_file, max_dim=1024)
        self.assertIsNotNone(preview)
        self.assertEqual(preview.size, (640, 480))

    def test_extract_canon_cr3(self):
        import struct
        box_size = 8 + 12 + len(self.sample_jpg)
        box = struct.pack(">I", box_size) + b"PRVW" + b"\x00\x00\x00\x00" + struct.pack(">HH", 640, 480) + b"\x00\x00\x00\x00" + self.sample_jpg
        cr3_file = self.dir_path / "sample.cr3"
        cr3_file.write_bytes(b"ftypcrx \x00\x00\x00\x00" + box)

        from core.thumbnail import extract_raw_embedded_jpeg
        img = extract_raw_embedded_jpeg(cr3_file)
        self.assertIsNotNone(img)
        self.assertEqual(img.size, (640, 480))

    def test_extract_tiff_raw(self):
        import struct
        hdr = b"II\x2a\x00\x08\x00\x00\x00"
        jpg_offset = 8 + 2 + 12 * 2 + 4
        e1 = struct.pack("<HHI I", 0x0201, 4, 1, jpg_offset)
        e2 = struct.pack("<HHI I", 0x0202, 4, 1, len(self.sample_jpg))
        next_ifd = struct.pack("<I", 0)
        tiff_raw = hdr + struct.pack("<H", 2) + e1 + e2 + next_ifd + self.sample_jpg

        cr2_file = self.dir_path / "sample.cr2"
        cr2_file.write_bytes(tiff_raw)

        from core.thumbnail import extract_raw_embedded_jpeg
        img = extract_raw_embedded_jpeg(cr2_file)
        self.assertIsNotNone(img)
        self.assertEqual(img.size, (640, 480))

    def test_binary_scan_fallback(self):
        # File with random header followed by JPEG SOI
        raw_file = self.dir_path / "unknown.nef"
        raw_file.write_bytes(b"PADDING_HEADER_DATA_1234567890" + self.sample_jpg + b"TRAILING")

        from core.thumbnail import extract_raw_embedded_jpeg
        img = extract_raw_embedded_jpeg(raw_file)
        self.assertIsNotNone(img)
        self.assertEqual(img.size, (640, 480))


class TestCullingAndExternalTools(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

        # Create dummy JPG and RAW pair
        self.raw_file = self.dir_path / "IMG_1001.CR3"
        self.raw_file.write_bytes(b"DUMMY_RAW_BYTES")

        self.jpg_file = self.dir_path / "IMG_1001.JPG"
        from PIL import Image
        im = Image.new("RGB", (400, 300), "red")
        im.save(str(self.jpg_file), "JPEG")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_xmp_metadata_sync(self):
        from core.xmp_sync import write_xmp_metadata, read_xmp_metadata, sync_pair_xmp

        # Write rating 4 and label Red
        sync_pair_xmp(self.raw_file, self.jpg_file, rating=4, label="Red", is_rejected=False)

        r_raw, l_raw, rej_raw = read_xmp_metadata(self.raw_file)
        self.assertEqual(r_raw, 4)
        self.assertEqual(l_raw, "Red")
        self.assertFalse(rej_raw)

        r_jpg, l_jpg, rej_jpg = read_xmp_metadata(self.jpg_file)
        self.assertEqual(r_jpg, 4)
        self.assertEqual(l_jpg, "Red")
        self.assertFalse(rej_jpg)

        # Update to rejected
        sync_pair_xmp(self.raw_file, self.jpg_file, rating=0, label="", is_rejected=True)
        r_raw2, _, rej_raw2 = read_xmp_metadata(self.raw_file)
        self.assertTrue(rej_raw2)

    def test_scan_culling_folder_and_reject(self):
        from gui_qt.models.culling_model import scan_culling_folder, execute_reject_action

        # Initial scan groups pair
        items = scan_culling_folder(self.dir_path)
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertTrue(it.is_pair)
        self.assertEqual(it.raw_path, self.raw_file)
        self.assertEqual(it.jpeg_path, self.jpg_file)

        # Reject and move to subfolder
        it.is_rejected = True
        cnt, msg = execute_reject_action(items, action="move_folder", folder_name="_Abgelehnt")
        self.assertEqual(cnt, 1)

        # Check files moved
        self.assertFalse(self.raw_file.exists())
        self.assertFalse(self.jpg_file.exists())
        rej_folder = self.dir_path / "_Abgelehnt"
        self.assertTrue((rej_folder / "IMG_1001.CR3").exists())
        self.assertTrue((rej_folder / "IMG_1001.JPG").exists())

    def test_external_launch_filters(self):
        from core.external_tools import launch_darktable, launch_topaz_photo

        # Darktable rejects non-RAW
        ok_d, msg_d = launch_darktable([self.jpg_file])
        self.assertFalse(ok_d)
        self.assertIn("Keine", msg_d)

        # Topaz rejects non-JPEG
        ok_t, msg_t = launch_topaz_photo([self.raw_file])
        self.assertFalse(ok_t)
        self.assertIn("Keine", msg_t)

    def test_culling_scan_worker_progress(self):
        from gui_qt.workers.culling_worker import CullingScanWorker

        progress_events = []
        finished_items = []

        worker = CullingScanWorker(self.dir_path)
        worker.progress.connect(lambda cur, total, msg: progress_events.append((cur, total, msg)))
        worker.scan_finished.connect(lambda items: finished_items.extend(items))

        worker.run()

        self.assertGreater(len(progress_events), 0)
        self.assertEqual(len(finished_items), 1)
        cur, total, msg = progress_events[0]
        self.assertEqual(cur, 1)
        self.assertEqual(total, 1)

    def test_count_folder_images(self):
        from gui_qt.models.culling_model import count_folder_images

        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "IMG_0001.CR3").write_bytes(b"raw1")
            (p / "IMG_0002.NEF").write_bytes(b"raw2")
            (p / "IMG_0001.JPG").write_bytes(b"jpg1")
            (p / "IMG_0002.JPEG").write_bytes(b"jpg2")
            (p / "IMG_0003.PNG").write_bytes(b"png1")
            (p / "readme.txt").write_text("info")

            total, raw, jpg = count_folder_images(p)
            self.assertEqual(total, 5)
            self.assertEqual(raw, 2)
            self.assertEqual(jpg, 2)

    def test_olympus_ori_support_and_high_res_triplet(self):
        from gui_qt.models.culling_model import scan_culling_folder, count_folder_images
        from core.exif_reader import MediaMetadata, extract_metadata
        from core.thumbnail import RAW_EXTENSIONS
        import io, struct
        from PIL import Image

        self.assertIn(".ori", RAW_EXTENSIONS)

        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            # Create Olympus High Res Shot triplet: .ORF (composite) + .ORI (baseline frame) + .JPG
            orf_file = p / "P1010001.ORF"
            ori_file = p / "P1010001.ORI"
            jpg_file = p / "P1010001.JPG"

            orf_file.write_bytes(b"IIRO_DUMMY_ORF")
            ori_file.write_bytes(b"IIRO_DUMMY_ORI")

            im = Image.new("RGB", (300, 200), "blue")
            im.save(str(jpg_file), "JPEG")

            # Check image counting
            total, raw, jpg = count_folder_images(p)
            self.assertEqual(total, 3)
            self.assertEqual(raw, 2)
            self.assertEqual(jpg, 1)

            # Scan culling folder: both RAW files must be preserved!
            items = scan_culling_folder(p)
            self.assertEqual(len(items), 2)

            raw_paths = {it.raw_path.name for it in items if it.raw_path}
            self.assertIn("P1010001.ORF", raw_paths)
            self.assertIn("P1010001.ORI", raw_paths)

            # Both pair with the companion JPG
            for it in items:
                self.assertTrue(it.is_pair)
                self.assertEqual(it.companion_path.name, "P1010001.JPG")

            # Check metadata classification
            meta = extract_metadata(ori_file)
            self.assertTrue(meta.is_raw)
            self.assertEqual(meta.media_type, "RAW")

    def test_olympus_ori_preview_extraction(self):
        from core.thumbnail import extract_raw_embedded_jpeg, load_preview_image, generate_thumbnail
        import io, struct
        from PIL import Image

        # Create valid embedded JPEG
        buf = io.BytesIO()
        test_img = Image.new("RGB", (640, 480), color=(255, 100, 50))
        test_img.save(buf, format="JPEG")
        jpeg_bytes = buf.getvalue()

        # Construct Olympus IIRO raw container
        header = b"IIRO" + struct.pack("<I", 8)
        num_entries = 2
        entry1 = struct.pack("<HHI I", 0x0111, 4, 1, 38)
        entry2 = struct.pack("<HHI I", 0x0117, 4, 1, len(jpeg_bytes))
        ifd = struct.pack("<H", num_entries) + entry1 + entry2 + struct.pack("<I", 0)
        full_ori_data = header + ifd + jpeg_bytes

        with tempfile.TemporaryDirectory() as tmpdir:
            ori_path = Path(tmpdir) / "TEST_OLYMPUS.ORI"
            ori_path.write_bytes(full_ori_data)

            # 1. Direct raw preview extraction
            extracted = extract_raw_embedded_jpeg(ori_path)
            self.assertIsNotNone(extracted)
            self.assertEqual(extracted.size, (640, 480))

            # 2. High-res preview loader
            preview = load_preview_image(ori_path)
            self.assertIsNotNone(preview)
            self.assertEqual(preview.size, (640, 480))

            # 3. Resized thumbnail generator
            thumb = generate_thumbnail(ori_path, max_size=(160, 160))
            self.assertIsNotNone(thumb)
            self.assertLessEqual(thumb.width, 160)
            self.assertLessEqual(thumb.height, 160)

    def test_culling_tree_widget(self):
        from gui_qt.views.culling_tree import CullingDirectoryTreeWidget
        from core.config import AppConfig

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sub1 = root / "Urlaub_2026"
            sub1.mkdir()
            (sub1 / "IMG_01.CR3").write_bytes(b"raw")
            (sub1 / "IMG_01.JPG").write_bytes(b"jpg")

            cfg = AppConfig(culling_root_folder=str(root))
            tree_widget = CullingDirectoryTreeWidget(cfg)
            tree_widget.show()

            self.assertIsNotNone(tree_widget.model)
            self.assertEqual(tree_widget.model.columnCount(), 4)
            self.assertGreaterEqual(tree_widget.model.rowCount(), 1)

            # Test folder selection signal
            emitted_paths = []
            tree_widget.folder_selected.connect(lambda p: emitted_paths.append(p))
            tree_widget.select_folder(sub1)

            # Simulate item click on sub1
            root_item = tree_widget.model.item(0, 0)
            self.assertIsNotNone(root_item)
            child_item = root_item.child(0, 0)
            self.assertIsNotNone(child_item)
            self.assertIn("Urlaub_2026", child_item.text())

            # Check sub1 image counts in model
            sub1_total_item = root_item.child(0, 1)
            sub1_raw_item = root_item.child(0, 2)
            sub1_jpg_item = root_item.child(0, 3)
            self.assertEqual(sub1_total_item.text(), "2")
            self.assertEqual(sub1_raw_item.text(), "1")
            self.assertEqual(sub1_jpg_item.text(), "1")

            # Check vector icons on tree action buttons
            self.assertFalse(tree_widget.btn_refresh.icon().isNull())
            self.assertFalse(tree_widget.btn_expand_all.icon().isNull())
            self.assertFalse(tree_widget.btn_collapse_all.icon().isNull())
            self.assertFalse(tree_widget.btn_collapse_panel.icon().isNull())

            tree_widget._on_item_clicked(tree_widget.model.indexFromItem(child_item))
            self.assertEqual(len(emitted_paths), 1)
            self.assertEqual(emitted_paths[0].resolve(), sub1.resolve())

            tree_widget.close()

    def test_culling_tab_ultrawide_layout(self):
        from gui_qt.views.culling_tab import CullingTabView
        from gui_qt.views.culling_left_dock import CullingLeftNavigationDock
        from core.config import AppConfig

        cfg = AppConfig()
        tab = CullingTabView(cfg)
        tab.show()

        # Check 3-pane splitter layout (Left Dock, Sidebar Controls, Canvas Workspace)
        self.assertIsNotNone(tab.splitter)
        self.assertEqual(tab.splitter.count(), 3)
        self.assertIsInstance(tab.left_dock, CullingLeftNavigationDock)

        # Check collapsing left dock to 36px
        self.assertFalse(tab.left_dock.is_collapsed)
        initial_canvas_w = tab.splitter.sizes()[2]
        tab.left_dock.collapse_panel()
        self.assertTrue(tab.left_dock.is_collapsed)
        self.assertEqual(tab.left_dock.width(), 36)
        self.assertTrue(tab.left_dock.collapsed_strip.isVisible())
        self.assertFalse(tab.left_dock.tab_widget.isVisible())
        # Canvas should have received the extra width without gap
        self.assertGreater(tab.splitter.sizes()[2], initial_canvas_w)

        # Check expanding left dock back out
        tab.left_dock.expand_panel()
        self.assertFalse(tab.left_dock.is_collapsed)
        self.assertGreaterEqual(tab.left_dock.width(), 260)
        self.assertFalse(tab.left_dock.collapsed_strip.isVisible())
        self.assertTrue(tab.left_dock.tab_widget.isVisible())

        # Check tabs in Left Dock (Verzeichnisse & Filter)
        self.assertEqual(tab.left_dock.tab_widget.count(), 2)
        self.assertEqual(tab.left_dock.tab_widget.tabText(0), "Verzeichnisse")
        self.assertEqual(tab.left_dock.tab_widget.tabText(1), "Filter")

        # Check filmstrip toggle
        self.assertTrue(tab.filmstrip.isVisible())
        tab._toggle_filmstrip()
        self.assertFalse(tab.filmstrip.isVisible())
        self.assertIn("einblenden", tab.btn_toggle_filmstrip.text())
        tab._toggle_filmstrip()
        self.assertTrue(tab.filmstrip.isVisible())
        self.assertIn("ausblenden", tab.btn_toggle_filmstrip.text())

        tab.close()


class TestCullingFilter(unittest.TestCase):
    def setUp(self):
        from gui_qt.models.culling_model import CullingItem
        from core.exif_reader import MediaMetadata

        self.item_raw_only = CullingItem(
            primary_path=Path("IMG_001.CR3"),
            companion_path=None,
            metadata=MediaMetadata(
                file_path=Path("IMG_001.CR3"),
                orig_name="IMG_001",
                extension=".cr3",
                file_size=20000000,
                date_taken=datetime(2026, 5, 1, 10, 0),
                date_source="EXIF",
                camera_make="Canon",
                camera_model="EOS R6",
                camera_name="Canon EOS R6",
                iso=200,
                lens_model="RF 24-70mm F2.8L"
            ),
            rating=5,
            is_picked=True
        )
        self.item_pair = CullingItem(
            primary_path=Path("P101.ORF"),
            companion_path=Path("P101.JPG"),
            metadata=MediaMetadata(
                file_path=Path("P101.JPG"),
                orig_name="P101",
                extension=".jpg",
                file_size=8000000,
                date_taken=datetime(2026, 5, 2, 11, 0),
                date_source="EXIF",
                camera_make="OM Digital Solutions",
                camera_model="OM-1",
                camera_name="OM System OM-1",
                iso=800,
                lens_model="M.12-40mm F2.8"
            ),
            rating=3,
            is_picked=False
        )
        self.item_jpg_only = CullingItem(
            primary_path=Path("DSC_500.JPG"),
            companion_path=None,
            metadata=MediaMetadata(
                file_path=Path("DSC_500.JPG"),
                orig_name="DSC_500",
                extension=".jpg",
                file_size=5000000,
                date_taken=datetime(2026, 5, 3, 12, 0),
                date_source="EXIF",
                camera_make="Sony",
                camera_model="ILCE-7M4",
                camera_name="Sony ILCE-7M4",
                iso=3200,
                lens_model="FE 35mm F1.4 GM"
            ),
            rating=0,
            is_rejected=True
        )
        self.items = [self.item_raw_only, self.item_pair, self.item_jpg_only]

    def test_filter_by_type(self):
        from gui_qt.views.culling_filter import CullingFilterCriteria

        # All formats
        crit_all = CullingFilterCriteria(file_type="ALL")
        self.assertEqual(len([it for it in self.items if crit_all.matches(it)]), 3)

        # Any RAW
        crit_raw_any = CullingFilterCriteria(file_type="RAW_ANY")
        res_raw = [it for it in self.items if crit_raw_any.matches(it)]
        self.assertEqual(len(res_raw), 2)
        self.assertIn(self.item_raw_only, res_raw)
        self.assertIn(self.item_pair, res_raw)

        # Any JPEG
        crit_jpg_any = CullingFilterCriteria(file_type="JPEG_ANY")
        res_jpg = [it for it in self.items if crit_jpg_any.matches(it)]
        self.assertEqual(len(res_jpg), 2)
        self.assertIn(self.item_pair, res_jpg)
        self.assertIn(self.item_jpg_only, res_jpg)

        # Pairs only
        crit_pair = CullingFilterCriteria(file_type="PAIR_ONLY")
        res_pair = [it for it in self.items if crit_pair.matches(it)]
        self.assertEqual(res_pair, [self.item_pair])

        # Standalone RAW only
        crit_raw_only = CullingFilterCriteria(file_type="RAW_ONLY")
        self.assertEqual([it for it in self.items if crit_raw_only.matches(it)], [self.item_raw_only])

        # Standalone JPEG only
        crit_jpg_only = CullingFilterCriteria(file_type="JPEG_ONLY")
        self.assertEqual([it for it in self.items if crit_jpg_only.matches(it)], [self.item_jpg_only])

    def test_filter_by_rating_and_status(self):
        from gui_qt.views.culling_filter import CullingFilterCriteria

        # Min 4 stars
        crit_4 = CullingFilterCriteria(rating_mode="MIN_4")
        self.assertEqual([it for it in self.items if crit_4.matches(it)], [self.item_raw_only])

        # Status: Picked
        crit_pick = CullingFilterCriteria(status="PICKED")
        self.assertEqual([it for it in self.items if crit_pick.matches(it)], [self.item_raw_only])

        # Status: Rejected
        crit_rej = CullingFilterCriteria(status="REJECTED")
        self.assertEqual([it for it in self.items if crit_rej.matches(it)], [self.item_jpg_only])

        # Status: Not rejected
        crit_not_rej = CullingFilterCriteria(status="NOT_REJECTED")
        res = [it for it in self.items if crit_not_rej.matches(it)]
        self.assertEqual(len(res), 2)
        self.assertNotIn(self.item_jpg_only, res)

    def test_filter_by_camera_and_exif(self):
        from gui_qt.views.culling_filter import CullingFilterCriteria

        crit_canon = CullingFilterCriteria(camera="Canon EOS R6")
        self.assertEqual([it for it in self.items if crit_canon.matches(it)], [self.item_raw_only])

        crit_om = CullingFilterCriteria(camera="OM System OM-1")
        self.assertEqual([it for it in self.items if crit_om.matches(it)], [self.item_pair])

        crit_iso_low = CullingFilterCriteria(iso_range="LOW")  # <= 400
        self.assertEqual([it for it in self.items if crit_iso_low.matches(it)], [self.item_raw_only])

        crit_search = CullingFilterCriteria(search_text="35mm")
        self.assertEqual([it for it in self.items if crit_search.matches(it)], [self.item_jpg_only])

    def test_culling_filter_widget_ui_and_tab_integration(self):
        from gui_qt.views.culling_filter import CullingFilterWidget, CullingFilterCriteria
        from gui_qt.views.culling_tab import CullingTabView
        from core.config import AppConfig

        widget = CullingFilterWidget()
        widget.show()

        # Update folder items populates cameras and lenses
        widget.update_folder_items(self.items)
        self.assertGreaterEqual(widget.cmb_camera.count(), 4)  # "Alle Kameras" + 3 cameras
        self.assertGreaterEqual(widget.cmb_lens.count(), 4)    # "Alle Objektive" + 3 lenses

        # Change filter and check signal
        emitted = []
        widget.filter_changed.connect(lambda crit: emitted.append(crit))
        widget.cmb_file_type.setCurrentIndex(1)  # RAW_ANY
        self.assertGreater(len(emitted), 0)
        self.assertEqual(emitted[-1].file_type, "RAW_ANY")
        self.assertTrue(emitted[-1].is_active())

        # Reset filters
        widget.reset_filters()
        self.assertEqual(widget.cmb_file_type.currentIndex(), 0)
        self.assertFalse(widget.get_criteria().is_active())

        widget.close()

        # Test integration in CullingTabView
        cfg = AppConfig()
        tab = CullingTabView(cfg)
        tab.show()
        tab._on_scan_finished(self.items)
        self.assertEqual(len(tab.items), 3)
        self.assertEqual(len(tab.filtered_items), 3)

        # Trigger filter in tab: Only RAW
        crit_raw = CullingFilterCriteria(file_type="RAW_ONLY")
        tab._on_filter_changed(crit_raw)
        self.assertEqual(len(tab.filtered_items), 1)
        self.assertEqual(tab.filtered_items[0], self.item_raw_only)
        self.assertIn("Filter aktiv", tab.lbl_active_name.text())

        # Reset filter: back to 3
        crit_reset = CullingFilterCriteria()
        tab._on_filter_changed(crit_reset)
        self.assertEqual(len(tab.filtered_items), 3)

        tab.close()


class TestWorkflowStatusTracking(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.dir_path = Path(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_xmp_workflow_status_read_write(self):
        from core.xmp_sync import write_xmp_metadata, read_xmp_workflow_info

        media_file = self.dir_path / "IMG_1234.JPG"
        media_file.write_text("dummy", encoding="utf-8")
        sidecar = write_xmp_metadata(media_file, rating=4, label="Blue", is_rejected=False, workflow_status="SOOC_OK")
        self.assertTrue(sidecar.exists())

        info = read_xmp_workflow_info(media_file)
        self.assertEqual(info.rating, 4)
        self.assertEqual(info.label, "Blue")
        self.assertFalse(info.is_rejected)
        self.assertEqual(info.workflow_status, "SOOC_OK")
        self.assertFalse(info.has_darktable_edit)

        # Update to TO_EDIT
        write_xmp_metadata(media_file, rating=5, label="Green", is_rejected=False, workflow_status="TO_EDIT")
        info2 = read_xmp_workflow_info(media_file)
        self.assertEqual(info2.rating, 5)
        self.assertEqual(info2.workflow_status, "TO_EDIT")

    def test_xmp_darktable_history_detection(self):
        from core.xmp_sync import read_xmp_workflow_info

        media_file = self.dir_path / "RAW_DT.ORF"
        xmp_file = self.dir_path / "RAW_DT.ORF.xmp"
        xmp_content = """<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:darktable="http://darktable.sf.net/"
   xmp:Rating="3"
   darktable:history_end="5">
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
"""
        xmp_file.write_text(xmp_content, encoding="utf-8")
        info = read_xmp_workflow_info(media_file)
        self.assertEqual(info.rating, 3)
        self.assertTrue(info.has_darktable_edit)
        # Default workflow status should be inferred as IN_PROGRESS if darktable history is present and status was not explicit
        self.assertEqual(info.workflow_status, "IN_PROGRESS")

    def test_check_exported_file_family_album_and_local(self):
        from gui_qt.models.culling_model import check_exported_file

        raw_file = self.dir_path / "P1010001.ORF"
        raw_file.write_text("fake_raw", encoding="utf-8")

        # 1. No export initially
        exp_p = check_exported_file(raw_file)
        self.assertIsNone(exp_p)

        # 2. Local _edit.jpg
        local_edit = self.dir_path / "P1010001_edit.jpg"
        local_edit.write_text("fake_edit", encoding="utf-8")
        exp_p2 = check_exported_file(raw_file)
        self.assertEqual(exp_p2, local_edit)
        local_edit.unlink()

        # 3. Family album structure: album_dir / 2026 / 04 / P1010001*.jpg
        album_dir = self.dir_path / "FamilyAlbum"
        month_dir = album_dir / "2026" / "04"
        month_dir.mkdir(parents=True)
        album_export = month_dir / "P1010001.jpg"
        album_export.write_text("fake_album_export", encoding="utf-8")

        exp_p3 = check_exported_file(
            raw_file,
            family_album_dir=str(album_dir),
            date_taken=datetime(2026, 4, 15, 10, 30)
        )
        self.assertEqual(exp_p3, album_export)

    def test_filter_criteria_workflow_status(self):
        from gui_qt.models.culling_model import CullingItem
        from gui_qt.views.culling_filter import CullingFilterCriteria

        it1 = CullingItem(primary_path=self.dir_path / "A.JPG", workflow_status="SOOC_OK")
        it2 = CullingItem(primary_path=self.dir_path / "B.JPG", workflow_status="TO_EDIT")
        it3 = CullingItem(primary_path=self.dir_path / "C.JPG", workflow_status="EDITED")
        it4 = CullingItem(primary_path=self.dir_path / "D.JPG", workflow_status="UNCHECKED")
        items = [it1, it2, it3, it4]

        crit_all = CullingFilterCriteria(workflow_status="ALL")
        self.assertEqual(len([it for it in items if crit_all.matches(it)]), 4)

        crit_sooc = CullingFilterCriteria(workflow_status="SOOC_OK")
        self.assertEqual([it for it in items if crit_sooc.matches(it)], [it1])

        crit_to_edit = CullingFilterCriteria(workflow_status="TO_EDIT")
        self.assertEqual([it for it in items if crit_to_edit.matches(it)], [it2])

        crit_edited = CullingFilterCriteria(workflow_status="EDITED")
        self.assertEqual([it for it in items if crit_edited.matches(it)], [it3])

        crit_uncheck = CullingFilterCriteria(workflow_status="UNCHECKED")
        self.assertEqual([it for it in items if crit_uncheck.matches(it)], [it4])

    def test_culling_tab_workflow_status_ui_and_shortcuts(self):
        from gui_qt.models.culling_model import CullingItem
        from gui_qt.views.culling_tab import CullingTabView
        from core.config import AppConfig
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent, Qt

        cfg = AppConfig()
        tab = CullingTabView(cfg)
        tab.show()

        it = CullingItem(primary_path=self.dir_path / "Test.JPG", workflow_status="UNCHECKED")
        tab._on_scan_finished([it])
        self.assertEqual(tab.current_idx, 0)
        self.assertEqual(it.workflow_status, "UNCHECKED")

        # Set status to SOOC_OK
        tab.set_workflow_status("SOOC_OK")
        self.assertEqual(it.workflow_status, "SOOC_OK")
        self.assertIn("SOOC", tab.lbl_wf_badge.text())

        # Clicking same status toggles back to UNCHECKED
        tab.set_workflow_status("SOOC_OK")
        self.assertEqual(it.workflow_status, "UNCHECKED")

        # Shortcut B -> TO_EDIT
        ev_b = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_B, Qt.KeyboardModifier.NoModifier)
        tab.keyPressEvent(ev_b)
        self.assertEqual(it.workflow_status, "TO_EDIT")
        self.assertIn("Zu bearbeiten", tab.lbl_wf_badge.text())

        # Shortcut E -> EDITED
        ev_e = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_E, Qt.KeyboardModifier.NoModifier)
        tab.keyPressEvent(ev_e)
        self.assertEqual(it.workflow_status, "EDITED")
        self.assertIn("fertig", tab.lbl_wf_badge.text())

        # Shortcut Q -> SOOC_OK
        ev_q = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Q, Qt.KeyboardModifier.NoModifier)
        tab.keyPressEvent(ev_q)
        self.assertEqual(it.workflow_status, "SOOC_OK")

        tab.close()

    def test_general_settings_nas_and_family_album(self):
        from gui_qt.widgets.general_settings import GeneralSettingsWidget
        from core.config import AppConfig

        cfg = AppConfig()
        cfg.family_album_dir = "//nas/photos/0001_Unsere_Fotos"
        cfg.nas_archive_dir = "//nas/archive"

        widget = GeneralSettingsWidget()
        widget.load_config(cfg)

        self.assertEqual(widget.edit_family_album.text(), "//nas/photos/0001_Unsere_Fotos")
        self.assertEqual(widget.edit_nas_archive.text(), "//nas/archive")

        widget.edit_family_album.setText("//new_nas/0001_Unsere_Fotos")
        widget.edit_nas_archive.setText("//new_nas/archive")

        cfg_new = AppConfig()
        widget.sync_to_config(cfg_new)
        self.assertEqual(cfg_new.family_album_dir, "//new_nas/0001_Unsere_Fotos")
        self.assertEqual(cfg_new.nas_archive_dir, "//new_nas/archive")


class TestSettingsAndSingleViewConfig(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.dir_path = Path(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_settings_dialog_tabs_and_single_view_options(self):
        from gui_qt.dialogs.settings_dialog import SettingsDialog
        from core.config import AppConfig

        cfg = AppConfig()
        cfg.single_view_show_filename = True
        cfg.single_view_show_extension = True
        cfg.single_view_show_ratings = True
        cfg.single_view_show_path = True

        dlg = SettingsDialog(cfg)
        dlg.show()
        self.assertEqual(dlg.tabs.count(), 5)
        self.assertTrue(dlg.chk_sv_filename.isChecked())
        self.assertTrue(dlg.chk_sv_extension.isChecked())

        # Uncheck extension and ratings
        dlg.chk_sv_extension.setChecked(False)
        dlg.chk_sv_ratings.setChecked(False)
        self.assertIn("P1010042", dlg.lbl_preview_title_row.text())
        self.assertNotIn(".ORF", dlg.lbl_preview_title_row.text())

        # Click save
        dlg._on_save_clicked()
        self.assertFalse(cfg.single_view_show_extension)
        self.assertFalse(cfg.single_view_show_ratings)

        # Reset to defaults
        dlg._reset_single_view_defaults()
        self.assertTrue(dlg.chk_sv_extension.isChecked())
        self.assertTrue(dlg.chk_sv_ratings.isChecked())

        dlg.close()

    def test_header_banner_gear_button_and_menu(self):
        from gui_qt.widgets.header_banner import HeaderBanner
        from core.config import AppConfig

        cfg = AppConfig()
        cfg.single_view_show_path = True
        banner = HeaderBanner(config=cfg)
        banner.show()

        self.assertTrue(hasattr(banner, "btn_settings"))
        self.assertTrue(hasattr(banner, "settings_menu"))
        self.assertTrue(banner.act_sv_path.isChecked())

        # Toggling an action in the menu updates config & emits signal
        emitted = []
        banner.single_view_config_changed.connect(lambda: emitted.append(True))
        banner.act_sv_path.setChecked(False)
        self.assertFalse(cfg.single_view_show_path)
        self.assertGreater(len(emitted), 0)

        # Test open settings signal
        settings_opened = []
        banner.open_settings.connect(lambda tab: settings_opened.append(tab))
        banner.settings_menu.actions()[0].trigger()
        self.assertIn(0, settings_opened)

        banner.close()

    def test_media_single_view_display_preferences(self):
        from gui_qt.views.single_view import MediaSingleView
        from core.importer import ScanItem
        from core.exif_reader import MediaMetadata
        from core.config import AppConfig

        cfg = AppConfig()
        cfg.single_view_show_filename = True
        cfg.single_view_show_extension = True
        cfg.single_view_show_path = True
        cfg.single_view_show_ratings = True

        view = MediaSingleView(config=cfg)
        view.show()

        dummy_path = self.dir_path / "DSC_9999.JPG"
        dummy_path.write_text("img", encoding="utf-8")
        meta = MediaMetadata(file_path=dummy_path, orig_name="DSC_9999", extension=".jpg", file_size=100, date_taken=datetime(2026, 4, 15), date_source="exif")
        item = ScanItem(source_path=dummy_path, metadata=meta, target_path=dummy_path, is_duplicate=False, file_hash="h", status="Neu")

        view.set_items([item])
        self.assertEqual(view.lbl_title.text(), "DSC_9999.JPG")
        self.assertTrue(view.lbl_title.isVisible())
        self.assertTrue(view.lbl_path.isVisible())
        self.assertIn(str(self.dir_path), view.lbl_path.text())
        self.assertTrue(view.lbl_ratings.isVisible())

        # Hide extension
        cfg.single_view_show_extension = False
        view.apply_config(cfg)
        self.assertEqual(view.lbl_title.text(), "DSC_9999")

        # Hide path and ratings
        cfg.single_view_show_path = False
        cfg.single_view_show_ratings = False
        view.apply_config(cfg)
        self.assertFalse(view.lbl_path.isVisible())
        self.assertFalse(view.lbl_ratings.isVisible())

        # Hide filename entirely
        cfg.single_view_show_filename = False
        view.apply_config(cfg)
        self.assertFalse(view.lbl_title.isVisible())

        view.close()

    def test_culling_tab_display_preferences(self):
        from gui_qt.views.culling_tab import CullingTabView
        from gui_qt.models.culling_model import CullingItem
        from core.config import AppConfig

        cfg = AppConfig()
        cfg.single_view_show_filename = True
        cfg.single_view_show_extension = True
        cfg.single_view_show_path = True

        tab = CullingTabView(cfg)
        tab.show()

        it = CullingItem(primary_path=self.dir_path / "RAW_99.ORF")
        tab._on_scan_finished([it])

        self.assertIn("RAW_99.ORF", tab.lbl_canvas_name.text())
        self.assertTrue(tab.lbl_canvas_path.isVisible())

        # Hide extension
        cfg.single_view_show_extension = False
        tab.apply_config()
        self.assertEqual(tab.lbl_canvas_name.text(), "RAW_99")

        # Hide path
        cfg.single_view_show_path = False
        tab.apply_config()
        self.assertFalse(tab.lbl_canvas_path.isVisible())

        tab.close()

    def test_culling_scan_progress_feedback_no_separate_loading_text(self):
        from gui_qt.views.culling_tab import CullingTabView
        from gui_qt.models.culling_model import CullingItem
        from core.config import AppConfig
        from pathlib import Path

        cfg = AppConfig()
        tab = CullingTabView(cfg)
        tab.show()

        # Initial state before any folder or photos are loaded
        self.assertFalse(tab.progress_frame.isVisible())
        self.assertFalse(tab.btn_prev.isEnabled())
        self.assertFalse(tab.btn_next.isEnabled())
        self.assertFalse(tab.btn_zoom.isEnabled())
        self.assertFalse(tab.btn_toggle_raw_jpg.isVisible())
        self.assertEqual(tab.lbl_active_name.text(), "Kein Foto ausgewählt")
        self.assertEqual(tab.lbl_stats.text(), "Kein Ordner geöffnet")
        self.assertIn("Kein Foto ausgewählt", tab.canvas.lbl_image.text())

        # Simulate scan progress
        tab.progress_frame.setVisible(True)
        tab._on_scan_progress(10, 50, "P101.JPG")
        self.assertTrue(tab.progress_frame.isVisible())
        self.assertEqual(tab.scan_progress_bar.value(), 20)
        self.assertIn("Lese Fotos ein: 10 von 50", tab.lbl_scan_status.text())

        # No separate "Lade Fotos..." on active photo label or canvas during scan
        self.assertNotEqual(tab.lbl_active_name.text(), "Lade Fotos...")
        self.assertNotEqual(tab.canvas.lbl_image.text(), "Lade Fotos...")

        # Test blinking animation on the progress bar
        tab._start_bar_blinking()
        from PySide6.QtCore import QPropertyAnimation
        self.assertEqual(tab._bar_blink_anim.state(), QPropertyAnimation.State.Running)
        self.assertGreaterEqual(tab._bar_blink_anim.duration(), 500)

        tab._stop_bar_blinking()
        self.assertEqual(tab._bar_blink_anim.state(), QPropertyAnimation.State.Stopped)
        self.assertEqual(tab._bar_opacity_effect.opacity(), 1.0)

        # Scan finishes
        it = CullingItem(primary_path=Path("P101.JPG"))
        tab._on_scan_finished([it])
        self.assertFalse(tab.progress_frame.isVisible())

        tab.close()


class TestKeyNavigationAndImageSwitching(unittest.TestCase):
    def test_navigation_schemes_and_key_matching(self):
        from gui_qt.key_navigation import (
            DEFAULT_NAVIGATION_SCHEME, NAVIGATION_SCHEMES,
            get_nav_hint, get_nav_labels, is_nav_next, is_nav_prev
        )
        from PySide6.QtCore import Qt

        self.assertEqual(DEFAULT_NAVIGATION_SCHEME, "arrows_ad")
        self.assertIn("arrows", NAVIGATION_SCHEMES)
        self.assertIn("arrows_ad", NAVIGATION_SCHEMES)
        self.assertIn("arrows_all", NAVIGATION_SCHEMES)
        self.assertIn("ad_only", NAVIGATION_SCHEMES)
        self.assertIn("page_keys", NAVIGATION_SCHEMES)
        self.assertIn("all", NAVIGATION_SCHEMES)

        # 1. Arrows only
        self.assertTrue(is_nav_prev(Qt.Key.Key_Left, "arrows"))
        self.assertTrue(is_nav_next(Qt.Key.Key_Right, "arrows"))
        self.assertFalse(is_nav_prev(Qt.Key.Key_A, "arrows"))
        self.assertFalse(is_nav_next(Qt.Key.Key_D, "arrows"))

        # 2. Arrows & A/D
        self.assertTrue(is_nav_prev(Qt.Key.Key_Left, "arrows_ad"))
        self.assertTrue(is_nav_prev(Qt.Key.Key_A, "arrows_ad"))
        self.assertTrue(is_nav_next(Qt.Key.Key_Right, "arrows_ad"))
        self.assertTrue(is_nav_next(Qt.Key.Key_D, "arrows_ad"))

        # 3. A/D only
        self.assertTrue(is_nav_prev(Qt.Key.Key_A, "ad_only"))
        self.assertTrue(is_nav_next(Qt.Key.Key_D, "ad_only"))
        self.assertFalse(is_nav_prev(Qt.Key.Key_Left, "ad_only"))
        self.assertFalse(is_nav_next(Qt.Key.Key_Right, "ad_only"))

        # 4. Page Up / Page Down
        self.assertTrue(is_nav_prev(Qt.Key.Key_PageUp, "page_keys"))
        self.assertTrue(is_nav_next(Qt.Key.Key_PageDown, "page_keys"))

        # Labels & Hints
        prev_lbl, next_lbl = get_nav_labels("arrows")
        self.assertIn("←", prev_lbl)
        self.assertIn("→", next_lbl)
        self.assertIn("←", get_nav_hint("arrows"))

    def test_settings_dialog_navigation_sync(self):
        from core.config import AppConfig
        from gui_qt.dialogs.settings_dialog import SettingsDialog

        cfg = AppConfig()
        cfg.navigation_scheme = "arrows_ad"
        cfg.navigation_enable_mouse_wheel = False

        dlg = SettingsDialog(cfg)
        self.assertEqual(dlg.combo_nav_scheme.currentData(), "arrows_ad")
        self.assertFalse(dlg.chk_nav_mouse_wheel.isChecked())

        # Change scheme to "arrows"
        idx_arrows = dlg.combo_nav_scheme.findData("arrows")
        dlg.combo_nav_scheme.setCurrentIndex(idx_arrows)
        dlg.chk_nav_mouse_wheel.setChecked(True)
        dlg.save_to_config()

        self.assertEqual(cfg.navigation_scheme, "arrows")
        self.assertTrue(cfg.navigation_enable_mouse_wheel)

        # Reset defaults
        dlg._reset_single_view_defaults()
        self.assertEqual(dlg.combo_nav_scheme.currentData(), "arrows_ad")
        self.assertFalse(dlg.chk_nav_mouse_wheel.isChecked())

        dlg.close()

    def test_header_banner_navigation_menu(self):
        from core.config import AppConfig
        from gui_qt.widgets.header_banner import HeaderBanner

        cfg = AppConfig()
        cfg.navigation_scheme = "arrows_ad"
        banner = HeaderBanner(cfg)

        self.assertIn("arrows", banner.nav_actions)
        self.assertIn("arrows_ad", banner.nav_actions)
        self.assertTrue(banner.nav_actions["arrows_ad"].isChecked())

        # Select "arrows" via menu action
        signal_emitted = []
        banner.single_view_config_changed.connect(lambda: signal_emitted.append(True))
        banner.nav_actions["arrows"].trigger()

        self.assertEqual(cfg.navigation_scheme, "arrows")
        self.assertTrue(banner.nav_actions["arrows"].isChecked())
        self.assertTrue(signal_emitted)

        banner.close()

    def test_media_single_view_navigation_labels_and_switching(self):
        from core.config import AppConfig
        from core.importer import ScanItem
        from gui_qt.views.single_view import MediaSingleView
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent, Qt
        from pathlib import Path

        cfg = AppConfig()
        cfg.navigation_scheme = "arrows"
        view = MediaSingleView(cfg)
        view.show()

        # Check button label updated to arrow
        view.apply_config(cfg)
        self.assertIn("[←]", view.btn_prev.text())
        self.assertIn("[→]", view.btn_next.text())

        # Mock 2 items
        from datetime import datetime
        from core.exif_reader import MediaMetadata
        m1 = MediaMetadata(file_path=Path("img1.jpg"), orig_name="img1", extension=".jpg", file_size=100, date_taken=datetime(2026, 1, 1), date_source="exif")
        m2 = MediaMetadata(file_path=Path("img2.jpg"), orig_name="img2", extension=".jpg", file_size=100, date_taken=datetime(2026, 1, 1), date_source="exif")
        it1 = ScanItem(source_path=Path("img1.jpg"), metadata=m1, target_path=Path("img1.jpg"), is_duplicate=False, file_hash="h1", status="Neu")
        it2 = ScanItem(source_path=Path("img2.jpg"), metadata=m2, target_path=Path("img2.jpg"), is_duplicate=False, file_hash="h2", status="Neu")
        view.set_items([it1, it2], it1)
        self.assertEqual(view.current_idx, 0)

        # Press 'D' - with "arrows" scheme, D must NOT advance
        ev_d = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_D, Qt.KeyboardModifier.NoModifier)
        view.keyPressEvent(ev_d)
        self.assertEqual(view.current_idx, 0)

        # Press Right Arrow - must advance to index 1
        ev_right = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
        view.keyPressEvent(ev_right)
        self.assertEqual(view.current_idx, 1)

        # Press Left Arrow - must return to index 0
        ev_left = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Left, Qt.KeyboardModifier.NoModifier)
        view.keyPressEvent(ev_left)
        self.assertEqual(view.current_idx, 0)

        view.close()

    def test_culling_view_navigation_labels_and_switching(self):
        from core.config import AppConfig
        from gui_qt.views.culling_tab import CullingTabView
        from gui_qt.models.culling_model import CullingItem
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent, Qt
        from pathlib import Path

        cfg = AppConfig()
        cfg.navigation_scheme = "arrows"
        tab = CullingTabView(cfg)
        tab.show()

        tab.apply_config()
        self.assertIn("[←]", tab.btn_prev.text())
        self.assertIn("[→]", tab.btn_next.text())

        it1 = CullingItem(primary_path=Path("p1.orf"))
        it2 = CullingItem(primary_path=Path("p2.orf"))
        tab._on_scan_finished([it1, it2])
        self.assertEqual(tab.current_idx, 0)

        # Press 'D' - should not advance when scheme is "arrows"
        ev_d = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_D, Qt.KeyboardModifier.NoModifier)
        tab.keyPressEvent(ev_d)
        self.assertEqual(tab.current_idx, 0)

        # Press Right Arrow - advances
        ev_right = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
        tab.keyPressEvent(ev_right)
        self.assertEqual(tab.current_idx, 1)

        # Switch scheme to "arrows_ad"
        cfg.navigation_scheme = "arrows_ad"
        tab.apply_config()
        self.assertIn("[← / A]", tab.btn_prev.text())
        self.assertIn("[→ / D]", tab.btn_next.text())

        # Press 'A' - returns to 0
        ev_a = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier)
        tab.keyPressEvent(ev_a)
        self.assertEqual(tab.current_idx, 0)

        tab.close()

    def test_transfer_worker_copy_and_move(self):
        import tempfile
        from pathlib import Path
        from gui_qt.workers.transfer_worker import TransferWorker

        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "source"
            dst_dir = Path(tmpdir) / "dest"
            src_dir.mkdir()
            dst_dir.mkdir()

            # Create test files
            f1 = src_dir / "test1.jpg"
            f1.write_text("image-data-1")
            sc1 = src_dir / "test1.jpg.xmp"
            sc1.write_text("xmp-sidecar-1")

            f2 = src_dir / "test2.raw"
            f2.write_text("raw-data-2")

            # 1. Test Copy
            worker_copy = TransferWorker(
                files=[f1, f2],
                destination_dir=dst_dir,
                operation="copy",
                sync_sidecars=True
            )
            finished_results = []
            worker_copy.transfer_finished.connect(lambda s, e, b, errs: finished_results.append((s, e, b, errs)))
            worker_copy.run()

            self.assertEqual(len(finished_results), 1)
            succ, errs_cnt, b_trans, err_list = finished_results[0]
            self.assertEqual(succ, 2)
            self.assertEqual(errs_cnt, 0)
            self.assertTrue((dst_dir / "test1.jpg").exists())
            self.assertTrue((dst_dir / "test1.jpg.xmp").exists())
            self.assertTrue((dst_dir / "test2.raw").exists())
            # Source files must still exist after copy
            self.assertTrue(f1.exists())
            self.assertTrue(sc1.exists())

            # 2. Test Move
            dst_move = Path(tmpdir) / "dest_move"
            worker_move = TransferWorker(
                files=[f1, f2],
                destination_dir=dst_move,
                operation="move",
                sync_sidecars=True
            )
            move_results = []
            worker_move.transfer_finished.connect(lambda s, e, b, errs: move_results.append((s, e, b, errs)))
            worker_move.run()

            self.assertEqual(len(move_results), 1)
            succ_m, err_m, b_m, err_list_m = move_results[0]
            self.assertEqual(succ_m, 2)
            self.assertEqual(err_m, 0)
            self.assertTrue((dst_move / "test1.jpg").exists())
            self.assertTrue((dst_move / "test1.jpg.xmp").exists())
            self.assertTrue((dst_move / "test2.raw").exists())
            # Source files must be deleted after move
            self.assertFalse(f1.exists())
            self.assertFalse(sc1.exists())
            self.assertFalse(f2.exists())

    def test_transfer_pane_widget_and_filtering(self):
        import tempfile
        from pathlib import Path
        from core.config import AppConfig
        from gui_qt.views.transfer_tab import TransferPaneWidget

        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            (test_dir / "pic1.jpg").write_text("jpg1")                 # 4 bytes
            (test_dir / "pic2.orf").write_text("raw2_longer")          # 11 bytes
            (test_dir / "pic2.orf.xmp").write_text("xmp2")
            (test_dir / "movie.mp4").write_text("video_much_longer")   # 17 bytes
            (test_dir / "notes.txt").write_text("text")

            cfg = AppConfig()
            pane = TransferPaneWidget("Test Quelle", is_source=True, config=cfg)
            pane.load_folder(test_dir)

            # Verzeichnisbaum must be present on the left side (horizontal splitter) and non-collapsible
            self.assertIsNotNone(pane.tree_widget)
            self.assertTrue(hasattr(pane.tree_widget, "folder_selected"))
            self.assertEqual(pane.pane_splitter.orientation(), Qt.Orientation.Horizontal)
            self.assertFalse(pane.pane_splitter.childrenCollapsible())

            # Toggle tree hidden and restore -> must bring tree back with non-zero width
            pane.resize(800, 600)
            pane.show()
            pane._set_tree_visible(False)
            self.assertFalse(pane.tree_widget.isVisible())
            self.assertFalse(pane.btn_toggle_tree.isChecked())
            pane._set_tree_visible(True)
            self.assertTrue(pane.tree_widget.isVisible())
            self.assertTrue(pane.btn_toggle_tree.isChecked())
            self.assertGreater(pane.pane_splitter.sizes()[0], 0)

            # Toggle file display OFF and ON -> must hide/show files_container & preserve tree
            pane._set_files_visible(False)
            self.assertFalse(pane.files_container.isVisible())
            self.assertFalse(pane.btn_toggle_files.isChecked())
            self.assertFalse(pane._show_files)
            # Even when hidden, get_all_filtered_paths can resolve files on demand
            self.assertEqual(len(pane.get_all_filtered_paths(scan_if_hidden=True)), 3)

            pane._set_files_visible(True)
            self.assertTrue(pane.files_container.isVisible())
            self.assertTrue(pane.btn_toggle_files.isChecked())
            self.assertTrue(pane._show_files)

            # Only media files should be listed (pic1.jpg, pic2.orf, movie.mp4) - not notes.txt or xmp
            self.assertEqual(len(pane.all_items), 3)

            # Test sorting by name ascending / descending
            self.assertEqual([it.name for it in pane.filtered_items], ["movie.mp4", "pic1.jpg", "pic2.orf"])
            pane.btn_sort_dir.setChecked(True)
            pane._on_sort_dir_toggled()
            self.assertEqual([it.name for it in pane.filtered_items], ["pic2.orf", "pic1.jpg", "movie.mp4"])

            # Test sorting by size ascending via header click (column 3 = Größe)
            pane._on_table_header_clicked(3)
            self.assertEqual(pane.combo_sort.currentData(), "size")
            self.assertFalse(pane.btn_sort_dir.isChecked())
            self.assertEqual([it.name for it in pane.filtered_items], ["pic1.jpg", "pic2.orf", "movie.mp4"])

            # Reset sort to Name ascending
            pane._on_table_header_clicked(1)

            # Test search filter
            pane.edit_search.setText("pic1")
            self.assertEqual(len(pane.filtered_items), 1)
            self.assertEqual(pane.filtered_items[0].name, "pic1.jpg")
            pane.edit_search.clear()

            # Test RAW filter
            pane.combo_type.setCurrentIndex(1)  # Nur RAW
            self.assertEqual(len(pane.filtered_items), 1)
            self.assertEqual(pane.filtered_items[0].name, "pic2.orf")

            # Reset filter
            pane.combo_type.setCurrentIndex(0)
            self.assertEqual(len(pane.filtered_items), 3)

            # Test selection tools: select_all, select_none, invert
            pane.select_all()
            self.assertEqual(len(pane.get_effective_selected_paths()), 3)

            pane.select_none()
            self.assertEqual(len(pane.get_effective_selected_paths()), 0)

            pane.invert_selection()
            self.assertEqual(len(pane.get_effective_selected_paths()), 3)

            # Test view mode switching via dropdown list (combo_view_mode)
            pane.set_view_mode("grid", 80)
            self.assertEqual(pane.view_stack.currentIndex(), 1)
            self.assertEqual(pane.combo_view_mode.currentData(), "grid:80")
            pane.combo_view_mode.setCurrentIndex(3)  # Vorschau: Groß (200px)
            self.assertEqual(pane.list_grid.iconSize().width(), 200)
            pane.set_view_mode("list")
            self.assertEqual(pane.view_stack.currentIndex(), 0)
            self.assertEqual(pane.combo_view_mode.currentIndex(), 0)

            from PySide6.QtCore import QThreadPool
            QThreadPool.globalInstance().waitForDone(2000)
            pane.close()
            pane.deleteLater()
            _app.processEvents()

    def test_transfer_tab_and_main_window_integration(self):
        from gui_qt.main_window import MainWindow

        win = MainWindow()
        win.show()

        # Check that main_workflow_stack has 3 pages: 0 (Import), 1 (Culling), 2 (Transfer)
        self.assertEqual(win.main_workflow_stack.count(), 3)
        self.assertEqual(win.header_banner.btn_tab_import.isChecked(), True)
        self.assertEqual(win.header_banner.btn_tab_culling.isChecked(), False)
        self.assertEqual(win.header_banner.btn_tab_transfer.isChecked(), False)

        # Switch to tab 2 (Transfer & Archive)
        win.header_banner.switch_tab(2)
        self.assertEqual(win.main_workflow_stack.currentIndex(), 2)
        self.assertTrue(win.header_banner.btn_tab_transfer.isChecked())
        self.assertFalse(win.header_banner.btn_tab_import.isChecked())
        self.assertFalse(win.header_banner.btn_tab_culling.isChecked())

        # Test helper method
        win.open_transfer_tab()
        self.assertEqual(win.main_workflow_stack.currentIndex(), 2)
        self.assertFalse(win.transfer_tab_view.main_splitter.childrenCollapsible())

        if win._drive_watcher:
            win._drive_watcher.stop()
            win._drive_watcher.wait(1000)
        win.close()
        win.deleteLater()
        _app.processEvents()

    def test_culling_directory_tree_sorting(self):
        import tempfile
        from pathlib import Path
        from core.config import AppConfig
        from gui_qt.views.culling_tree import CullingDirectoryTreeWidget

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "2024_Alpha").mkdir()
            (root / "2025_Beta").mkdir()
            (root / "2026_Gamma").mkdir()

            cfg = AppConfig()
            tree = CullingDirectoryTreeWidget(cfg, config_root_key=None, default_root=root)

            root_item = tree.model.item(0, 0)
            names_asc = [root_item.child(r, 0).text() for r in range(root_item.rowCount())]
            self.assertEqual(names_asc, ["2024_Alpha", "2025_Beta", "2026_Gamma"])
            self.assertFalse(tree._sort_descending)
            self.assertFalse(tree.btn_sort.icon().isNull())

            # Toggle sort to descending
            tree._toggle_sort_order()
            root_item_desc = tree.model.item(0, 0)
            names_desc = [root_item_desc.child(r, 0).text() for r in range(root_item_desc.rowCount())]
            self.assertEqual(names_desc, ["2026_Gamma", "2025_Beta", "2024_Alpha"])
            self.assertTrue(tree._sort_descending)

            # Test toggling Bilder, RAW, JPG columns on/off
            self.assertFalse(tree.tree_view.isColumnHidden(1))
            self.assertFalse(tree.tree_view.isColumnHidden(2))
            self.assertFalse(tree.tree_view.isColumnHidden(3))

            tree.set_column_visibility(1, False)
            tree.set_column_visibility(2, False)
            tree.set_column_visibility(3, False)
            self.assertTrue(tree.tree_view.isColumnHidden(1))
            self.assertTrue(tree.tree_view.isColumnHidden(2))
            self.assertTrue(tree.tree_view.isColumnHidden(3))
            self.assertFalse(cfg.tree_show_col_bilder)
            self.assertFalse(cfg.tree_show_col_raw)
            self.assertFalse(cfg.tree_show_col_jpg)

            tree.set_column_visibility(2, True)
            self.assertFalse(tree.tree_view.isColumnHidden(2))
            self.assertTrue(cfg.tree_show_col_raw)

            tree.close()
            tree.deleteLater()
            _app.processEvents()

    def test_transfer_tab_reconciliation(self):
        """Verifies missing files reconciliation (JPG, RAW, both) in TransferTabView."""
        import tempfile
        from pathlib import Path
        from core.config import AppConfig
        from gui_qt.views.transfer_tab import TransferTabView
        from PySide6.QtCore import QThreadPool

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            src = tmp / "Quelle"
            dst = tmp / "Ziel"
            src.mkdir()
            dst.mkdir()

            # Source has: img1.jpg, img2.jpg, raw1.orf, raw2.orf, vid1.mp4
            (src / "img1.jpg").write_text("jpg1")
            (src / "img2.jpg").write_text("jpg2")
            (src / "raw1.orf").write_text("raw1")
            (src / "raw2.orf").write_text("raw2")
            (src / "vid1.mp4").write_text("vid1")

            # Destination already has: img1.jpg and raw1.orf
            (dst / "img1.jpg").write_text("jpg1")
            (dst / "raw1.orf").write_text("raw1")

            cfg = AppConfig()
            view = TransferTabView(cfg)
            view.pane_source.load_folder(src)
            view.pane_dest.load_folder(dst)
            _app.processEvents()

            # 1. Test reconcile JPG (only img2.jpg is missing)
            missing_jpgs = view.reconcile_missing_jpg()
            self.assertEqual(len(missing_jpgs), 1)
            self.assertEqual(missing_jpgs[0].name, "img2.jpg")
            self.assertIn(str(src / "img2.jpg"), view.pane_source._checked_paths)
            self.assertNotIn(str(src / "img1.jpg"), view.pane_source._checked_paths)
            self.assertIn("1 fehlende JPGs markiert", view.lbl_reconcile_status.text())

            # 2. Test reconcile RAW (only raw2.orf is missing)
            missing_raws = view.reconcile_missing_raw()
            self.assertEqual(len(missing_raws), 1)
            self.assertEqual(missing_raws[0].name, "raw2.orf")
            self.assertIn(str(src / "raw2.orf"), view.pane_source._checked_paths)
            self.assertNotIn(str(src / "raw1.orf"), view.pane_source._checked_paths)
            self.assertNotIn(str(src / "img2.jpg"), view.pane_source._checked_paths)
            self.assertIn("1 fehlende RAWs markiert", view.lbl_reconcile_status.text())

            # 3. Test reconcile both (RAW & JPG -> img2.jpg and raw2.orf)
            missing_both = view.reconcile_missing_both()
            self.assertEqual(len(missing_both), 2)
            missing_names = {p.name for p in missing_both}
            self.assertEqual(missing_names, {"img2.jpg", "raw2.orf"})
            self.assertIn(str(src / "img2.jpg"), view.pane_source._checked_paths)
            self.assertIn(str(src / "raw2.orf"), view.pane_source._checked_paths)
            self.assertIn("2 fehlende RAW & JPG markiert", view.lbl_reconcile_status.text())

            # 4. Copy missing files to destination and re-check -> should report Ziel aktuell
            (dst / "img2.jpg").write_text("jpg2")
            (dst / "raw2.orf").write_text("raw2")
            missing_none = view.reconcile_missing_both()
            self.assertEqual(len(missing_none), 0)
            self.assertEqual(len(view.pane_source._checked_paths), 0)
            self.assertIn("Ziel aktuell", view.lbl_reconcile_status.text())

            # Clean up widgets
            QThreadPool.globalInstance().waitForDone(2000)
            view.close()
            view.deleteLater()
            _app.processEvents()

    def test_transfer_tab_reconciliation_exif(self):
        """Verifies EXIF date_taken reconciliation even when files are renamed."""
        import tempfile
        from pathlib import Path
        from PIL import Image
        from core.config import AppConfig
        from gui_qt.views.transfer_tab import TransferTabView
        from PySide6.QtCore import QThreadPool

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            src = tmp / "Quelle"
            dst = tmp / "Ziel"
            src.mkdir()
            dst.mkdir()

            # Create test JPGs with EXIF dates
            img = Image.new("RGB", (20, 20), color="blue")

            # Source: DSC_0001.jpg (2026:05:20 14:00:00) and DSC_0002.jpg (2026:05:20 14:15:00)
            exif1 = img.getexif()
            exif1[36867] = "2026:05:20 14:00:00"
            img.save(src / "DSC_0001.jpg", exif=exif1)

            exif2 = img.getexif()
            exif2[36867] = "2026:05:20 14:15:00"
            img.save(src / "DSC_0002.jpg", exif=exif2)

            # Destination: Foto_Renamed.jpg with SAME EXIF as DSC_0001.jpg
            exif_dst = img.getexif()
            exif_dst[36867] = "2026:05:20 14:00:00"
            img.save(dst / "Foto_Renamed.jpg", exif=exif_dst)

            cfg = AppConfig(transfer_reconcile_method="exif")
            view = TransferTabView(cfg)
            view.pane_source.load_folder(src)
            view.pane_dest.load_folder(dst)
            _app.processEvents()

            # Reconcile JPG: DSC_0001.jpg should be recognized as existing, DSC_0002.jpg missing
            missing = view.reconcile_missing_jpg()
            self.assertEqual(len(missing), 1)
            self.assertEqual(missing[0].name, "DSC_0002.jpg")
            self.assertIn("EXIF-Zeit", view.lbl_reconcile_status.text())

            QThreadPool.globalInstance().waitForDone(2000)
            view.close()
            view.deleteLater()
            _app.processEvents()

    def test_transfer_tab_reconciliation_sha256(self):
        """Verifies bit-exact SHA-256 reconciliation."""
        import tempfile
        from pathlib import Path
        from core.config import AppConfig
        from gui_qt.views.transfer_tab import TransferTabView
        from PySide6.QtCore import QThreadPool

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            src = tmp / "Quelle"
            dst = tmp / "Ziel"
            src.mkdir()
            dst.mkdir()

            # Source: pic_a.jpg and pic_b.jpg
            (src / "pic_a.jpg").write_bytes(b"content_alpha_123456789")
            (src / "pic_b.jpg").write_bytes(b"content_beta_987654321")

            # Destination: different filename, but identical content to pic_a.jpg
            (dst / "archived_pic.jpg").write_bytes(b"content_alpha_123456789")

            cfg = AppConfig(transfer_reconcile_method="sha256")
            view = TransferTabView(cfg)
            view.pane_source.load_folder(src)
            view.pane_dest.load_folder(dst)
            _app.processEvents()

            # Reconcile: pic_a.jpg matches destination content; pic_b.jpg is missing
            missing = view.reconcile_missing_both()
            self.assertEqual(len(missing), 1)
            self.assertEqual(missing[0].name, "pic_b.jpg")
            self.assertIn("SHA-256", view.lbl_reconcile_status.text())

            QThreadPool.globalInstance().waitForDone(2000)
            view.close()
            view.deleteLater()
            _app.processEvents()

    def test_settings_dialog_reconcile_method(self):
        """Verifies that SettingsDialog loads and saves the transfer_reconcile_method."""
        from core.config import AppConfig
        from gui_qt.dialogs.settings_dialog import SettingsDialog

        cfg = AppConfig(transfer_reconcile_method="filename")
        dlg = SettingsDialog(cfg, initial_tab=2)

        # Check default value in combo box
        self.assertEqual(dlg.combo_reconcile_method.currentData(), "filename")

        # Change to exif
        idx_exif = dlg.combo_reconcile_method.findData("exif")
        dlg.combo_reconcile_method.setCurrentIndex(idx_exif)
        dlg.save_to_config()

        self.assertEqual(cfg.transfer_reconcile_method, "exif")

        # Change to sha256
        idx_sha = dlg.combo_reconcile_method.findData("sha256")
        dlg.combo_reconcile_method.setCurrentIndex(idx_sha)
        dlg.save_to_config()

        self.assertEqual(cfg.transfer_reconcile_method, "sha256")

        dlg.close()
        dlg.deleteLater()
        _app.processEvents()

    def test_thumbnail_and_preview_tasks(self):
        """Verifies fast ThumbnailTask and PreviewTask background execution and signals."""
        import tempfile
        from pathlib import Path
        from PIL import Image
        from PySide6.QtCore import QThreadPool
        from PySide6.QtGui import QImage
        from gui_qt.workers.thumb_worker import ThumbnailSignals, ThumbnailTask, PreviewSignals, PreviewTask

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            img_path = tmp / "test_photo.jpg"
            img = Image.new("RGB", (600, 400), color="purple")
            img.save(img_path)

            # Test ThumbnailTask
            thumb_result = {}
            t_signals = ThumbnailSignals()
            t_signals.thumbnail_ready.connect(lambda k, qimg: thumb_result.update({"key": k, "qimg": qimg}))

            t_task = ThumbnailTask(path=img_path, key_path=str(img_path), signals=t_signals, max_size=(160, 120))
            QThreadPool.globalInstance().start(t_task)
            QThreadPool.globalInstance().waitForDone(2000)
            _app.processEvents()

            self.assertIn("key", thumb_result)
            self.assertEqual(thumb_result["key"], str(img_path))
            self.assertIsInstance(thumb_result["qimg"], QImage)
            self.assertFalse(thumb_result["qimg"].isNull())
            self.assertLessEqual(thumb_result["qimg"].width(), 160)

            # Test PreviewTask
            preview_result = {}
            p_signals = PreviewSignals()
            p_signals.preview_ready.connect(lambda k, qimg: preview_result.update({"key": k, "qimg": qimg}))

            p_task = PreviewTask(path=img_path, key_path=str(img_path), signals=p_signals, max_dim=3840)
            QThreadPool.globalInstance().start(p_task)
            QThreadPool.globalInstance().waitForDone(2000)
            _app.processEvents()

            self.assertIn("key", preview_result)
            self.assertEqual(preview_result["key"], str(img_path))
            self.assertIsInstance(preview_result["qimg"], QImage)
            self.assertFalse(preview_result["qimg"].isNull())

    def test_check_exported_file_in_memory_optimization(self):
        """Verifies in-memory set and month_cache acceleration in check_exported_file."""
        import tempfile
        from datetime import datetime
        from pathlib import Path
        from gui_qt.models.culling_model import check_exported_file

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            photo = tmp / "DSC_0001.JPG"
            photo.write_text("dummy")

            # Local edit file exists
            edit_file = tmp / "DSC_0001_edit.jpg"
            edit_file.write_text("edit")

            existing_files = {photo.name.lower(), edit_file.name.lower()}
            existing_subdirs = set()

            res = check_exported_file(
                photo,
                existing_filenames=existing_files,
                existing_subdirs=existing_subdirs
            )
            self.assertIsNotNone(res)
            self.assertEqual(res.name, "DSC_0001_edit.jpg")

            # Test month cache with family album dir
            fa_dir = tmp / "Familienalbum"
            month_dir = fa_dir / "2026" / "05"
            month_dir.mkdir(parents=True)
            fa_export = month_dir / "DSC_0002.jpg"
            fa_export.write_text("fa")

            photo2 = tmp / "DSC_0002.JPG"
            photo2.write_text("dummy")

            month_cache = {}
            dt = datetime(2026, 5, 10, 12, 0, 0)
            res2 = check_exported_file(
                photo2,
                family_album_dir=str(fa_dir),
                date_taken=dt,
                existing_filenames={photo2.name.lower()},
                existing_subdirs=set(),
                month_cache=month_cache
            )
            self.assertIsNotNone(res2)
            self.assertEqual(res2.name, "DSC_0002.jpg")
            self.assertIn(month_dir, month_cache)

    def test_culling_directory_tree_entry_point_full_path(self):
        """Verifies that the full path is displayed at the entry point (header label and tree root node)."""
        import tempfile
        from pathlib import Path
        from core.config import AppConfig
        from gui_qt.views.culling_tree import CullingDirectoryTreeWidget

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sub = root / "Urlaub"
            sub.mkdir()

            cfg = AppConfig(culling_root_folder=str(root))
            tree = CullingDirectoryTreeWidget(cfg)

            # Check header label shows the full resolved path
            self.assertEqual(tree.lbl_root_path.text(), str(root.resolve()))
            self.assertEqual(tree.lbl_root_path.toolTip(), str(root.resolve()))

            # Check tree root item displays full resolved path
            root_item = tree.model.item(0, 0)
            self.assertIsNotNone(root_item)
            self.assertEqual(root_item.text(), str(root.resolve()))

            # Check child item displays only directory name
            child_item = root_item.child(0, 0)
            self.assertIsNotNone(child_item)
            self.assertEqual(child_item.text(), "Urlaub")

            # Update entry point and verify full path is updated everywhere
            tree.set_root_folder(sub)
            self.assertEqual(tree.lbl_root_path.text(), str(sub.resolve()))
            new_root_item = tree.model.item(0, 0)
            self.assertIsNotNone(new_root_item)
            self.assertEqual(new_root_item.text(), str(sub.resolve()))

            tree.close()
            tree.deleteLater()
            _app.processEvents()

    def test_transfer_tab_reconciliation(self):
        """Verifies missing files reconciliation (JPG, RAW, both) in TransferTabView."""
        import tempfile
        from pathlib import Path
        from core.config import AppConfig
        from gui_qt.views.transfer_tab import TransferTabView
        from PySide6.QtCore import QThreadPool

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            src = tmp / "Quelle"
            dst = tmp / "Ziel"
            src.mkdir()
            dst.mkdir()

            # Source has: img1.jpg, img2.jpg, raw1.orf, raw2.orf, vid1.mp4
            (src / "img1.jpg").write_text("jpg1")
            (src / "img2.jpg").write_text("jpg2")
            (src / "raw1.orf").write_text("raw1")
            (src / "raw2.orf").write_text("raw2")
            (src / "vid1.mp4").write_text("vid1")

            # Destination already has: img1.jpg and raw1.orf
            (dst / "img1.jpg").write_text("jpg1")
            (dst / "raw1.orf").write_text("raw1")

            cfg = AppConfig()
            view = TransferTabView(cfg)
            view.pane_source.load_folder(src)
            view.pane_dest.load_folder(dst)
            _app.processEvents()

            # 1. Test reconcile JPG (only img2.jpg is missing)
            missing_jpgs = view.reconcile_missing_jpg()
            self.assertEqual(len(missing_jpgs), 1)
            self.assertEqual(missing_jpgs[0].name, "img2.jpg")
            self.assertIn(str(src / "img2.jpg"), view.pane_source._checked_paths)
            self.assertNotIn(str(src / "img1.jpg"), view.pane_source._checked_paths)
            self.assertIn("1 fehlende JPGs markiert", view.lbl_reconcile_status.text())

            # 2. Test reconcile RAW (only raw2.orf is missing)
            missing_raws = view.reconcile_missing_raw()
            self.assertEqual(len(missing_raws), 1)
            self.assertEqual(missing_raws[0].name, "raw2.orf")
            self.assertIn(str(src / "raw2.orf"), view.pane_source._checked_paths)
            self.assertNotIn(str(src / "raw1.orf"), view.pane_source._checked_paths)
            self.assertNotIn(str(src / "img2.jpg"), view.pane_source._checked_paths)
            self.assertIn("1 fehlende RAWs markiert", view.lbl_reconcile_status.text())

            # 3. Test reconcile both (RAW & JPG -> img2.jpg and raw2.orf)
            missing_both = view.reconcile_missing_both()
            self.assertEqual(len(missing_both), 2)
            missing_names = {p.name for p in missing_both}
            self.assertEqual(missing_names, {"img2.jpg", "raw2.orf"})
            self.assertIn(str(src / "img2.jpg"), view.pane_source._checked_paths)
            self.assertIn(str(src / "raw2.orf"), view.pane_source._checked_paths)
            self.assertIn("2 fehlende RAW & JPG markiert", view.lbl_reconcile_status.text())

            # 4. Copy missing files to destination and re-check -> should report Ziel aktuell
            (dst / "img2.jpg").write_text("jpg2")
            (dst / "raw2.orf").write_text("raw2")
            missing_none = view.reconcile_missing_both()
            self.assertEqual(len(missing_none), 0)
            self.assertEqual(len(view.pane_source._checked_paths), 0)
            self.assertIn("Ziel aktuell", view.lbl_reconcile_status.text())

            # Clean up widgets
            QThreadPool.globalInstance().waitForDone(2000)
            view.close()
            view.deleteLater()
            _app.processEvents()

    def test_transfer_tab_reconciliation_exif(self):
        """Verifies EXIF date_taken reconciliation even when files are renamed."""
        import tempfile
        from pathlib import Path
        from PIL import Image
        from core.config import AppConfig
        from gui_qt.views.transfer_tab import TransferTabView
        from PySide6.QtCore import QThreadPool

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            src = tmp / "Quelle"
            dst = tmp / "Ziel"
            src.mkdir()
            dst.mkdir()

            # Create test JPGs with EXIF dates
            img = Image.new("RGB", (20, 20), color="blue")

            # Source: DSC_0001.jpg (2026:05:20 14:00:00) and DSC_0002.jpg (2026:05:20 14:15:00)
            exif1 = img.getexif()
            exif1[36867] = "2026:05:20 14:00:00"
            img.save(src / "DSC_0001.jpg", exif=exif1)

            exif2 = img.getexif()
            exif2[36867] = "2026:05:20 14:15:00"
            img.save(src / "DSC_0002.jpg", exif=exif2)

            # Destination: Foto_Renamed.jpg with SAME EXIF as DSC_0001.jpg
            exif_dst = img.getexif()
            exif_dst[36867] = "2026:05:20 14:00:00"
            img.save(dst / "Foto_Renamed.jpg", exif=exif_dst)

            cfg = AppConfig(transfer_reconcile_method="exif")
            view = TransferTabView(cfg)
            view.pane_source.load_folder(src)
            view.pane_dest.load_folder(dst)
            _app.processEvents()

            # Reconcile JPG: DSC_0001.jpg should be recognized as existing, DSC_0002.jpg missing
            missing = view.reconcile_missing_jpg()
            self.assertEqual(len(missing), 1)
            self.assertEqual(missing[0].name, "DSC_0002.jpg")
            self.assertIn("EXIF-Zeit", view.lbl_reconcile_status.text())

            QThreadPool.globalInstance().waitForDone(2000)
            view.close()
            view.deleteLater()
            _app.processEvents()

    def test_transfer_tab_reconciliation_sha256(self):
        """Verifies bit-exact SHA-256 reconciliation."""
        import tempfile
        from pathlib import Path
        from core.config import AppConfig
        from gui_qt.views.transfer_tab import TransferTabView
        from PySide6.QtCore import QThreadPool

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            src = tmp / "Quelle"
            dst = tmp / "Ziel"
            src.mkdir()
            dst.mkdir()

            # Source: pic_a.jpg and pic_b.jpg
            (src / "pic_a.jpg").write_bytes(b"content_alpha_123456789")
            (src / "pic_b.jpg").write_bytes(b"content_beta_987654321")

            # Destination: different filename, but identical content to pic_a.jpg
            (dst / "archived_pic.jpg").write_bytes(b"content_alpha_123456789")

            cfg = AppConfig(transfer_reconcile_method="sha256")
            view = TransferTabView(cfg)
            view.pane_source.load_folder(src)
            view.pane_dest.load_folder(dst)
            _app.processEvents()

            # Reconcile: pic_a.jpg matches destination content; pic_b.jpg is missing
            missing = view.reconcile_missing_both()
            self.assertEqual(len(missing), 1)
            self.assertEqual(missing[0].name, "pic_b.jpg")
            self.assertIn("SHA-256", view.lbl_reconcile_status.text())

            QThreadPool.globalInstance().waitForDone(2000)
            view.close()
            view.deleteLater()
            _app.processEvents()

    def test_settings_dialog_reconcile_method(self):
        """Verifies that SettingsDialog loads and saves the transfer_reconcile_method."""
        from core.config import AppConfig
        from gui_qt.dialogs.settings_dialog import SettingsDialog

        cfg = AppConfig(transfer_reconcile_method="filename")
        dlg = SettingsDialog(cfg, initial_tab=2)

        # Check default value in combo box
        self.assertEqual(dlg.combo_reconcile_method.currentData(), "filename")

        # Change to exif
        idx_exif = dlg.combo_reconcile_method.findData("exif")
        dlg.combo_reconcile_method.setCurrentIndex(idx_exif)
        dlg.save_to_config()

        self.assertEqual(cfg.transfer_reconcile_method, "exif")

        # Change to sha256
        idx_sha = dlg.combo_reconcile_method.findData("sha256")
        dlg.combo_reconcile_method.setCurrentIndex(idx_sha)
        dlg.save_to_config()

        self.assertEqual(cfg.transfer_reconcile_method, "sha256")

        dlg.close()
        dlg.deleteLater()
        _app.processEvents()

    def test_thumbnail_and_preview_tasks(self):
        """Verifies fast ThumbnailTask and PreviewTask background execution and signals."""
        import tempfile
        from pathlib import Path
        from PIL import Image
        from PySide6.QtCore import QThreadPool
        from PySide6.QtGui import QImage
        from gui_qt.workers.thumb_worker import ThumbnailSignals, ThumbnailTask, PreviewSignals, PreviewTask

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            img_path = tmp / "test_photo.jpg"
            img = Image.new("RGB", (600, 400), color="purple")
            img.save(img_path)

            # Test ThumbnailTask
            thumb_result = {}
            t_signals = ThumbnailSignals()
            t_signals.thumbnail_ready.connect(lambda k, qimg: thumb_result.update({"key": k, "qimg": qimg}))

            t_task = ThumbnailTask(path=img_path, key_path=str(img_path), signals=t_signals, max_size=(160, 120))
            QThreadPool.globalInstance().start(t_task)
            QThreadPool.globalInstance().waitForDone(2000)
            _app.processEvents()

            self.assertIn("key", thumb_result)
            self.assertEqual(thumb_result["key"], str(img_path))
            self.assertIsInstance(thumb_result["qimg"], QImage)
            self.assertFalse(thumb_result["qimg"].isNull())
            self.assertLessEqual(thumb_result["qimg"].width(), 160)

            # Test PreviewTask
            preview_result = {}
            p_signals = PreviewSignals()
            p_signals.preview_ready.connect(lambda k, qimg: preview_result.update({"key": k, "qimg": qimg}))

            p_task = PreviewTask(path=img_path, key_path=str(img_path), signals=p_signals, max_dim=3840)
            QThreadPool.globalInstance().start(p_task)
            QThreadPool.globalInstance().waitForDone(2000)
            _app.processEvents()

            self.assertIn("key", preview_result)
            self.assertEqual(preview_result["key"], str(img_path))
            self.assertIsInstance(preview_result["qimg"], QImage)
            self.assertFalse(preview_result["qimg"].isNull())

    def test_check_exported_file_in_memory_optimization(self):
        """Verifies in-memory set and month_cache acceleration in check_exported_file."""
        import tempfile
        from datetime import datetime
        from pathlib import Path
        from gui_qt.models.culling_model import check_exported_file

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            photo = tmp / "DSC_0001.JPG"
            photo.write_text("dummy")

            # Local edit file exists
            edit_file = tmp / "DSC_0001_edit.jpg"
            edit_file.write_text("edit")

            existing_files = {photo.name.lower(), edit_file.name.lower()}
            existing_subdirs = set()

            res = check_exported_file(
                photo,
                existing_filenames=existing_files,
                existing_subdirs=existing_subdirs
            )
            self.assertIsNotNone(res)
            self.assertEqual(res.name, "DSC_0001_edit.jpg")

            # Test month cache with family album dir
            fa_dir = tmp / "Familienalbum"
            month_dir = fa_dir / "2026" / "05"
            month_dir.mkdir(parents=True)
            fa_export = month_dir / "DSC_0002.jpg"
            fa_export.write_text("fa")

            photo2 = tmp / "DSC_0002.JPG"
            photo2.write_text("dummy")

            month_cache = {}
            dt = datetime(2026, 5, 10, 12, 0, 0)
            res2 = check_exported_file(
                photo2,
                family_album_dir=str(fa_dir),
                date_taken=dt,
                existing_filenames={photo2.name.lower()},
                existing_subdirs=set(),
                month_cache=month_cache
            )
            self.assertIsNotNone(res2)
            self.assertEqual(res2.name, "DSC_0002.jpg")
            self.assertIn(month_dir, month_cache)


class TestFullscreenMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def test_mainwindow_fullscreen_toggle(self):
        from gui_qt.main_window import MainWindow
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import Qt, QEvent

        win = MainWindow()
        self.assertFalse(win.isFullScreen())

        # Test toggle_fullscreen to fullscreen
        win.toggle_fullscreen()
        self.assertTrue(win.isFullScreen())
        self.assertIn("aktiviert", win.status_bar.currentMessage())

        # Test toggle_fullscreen back
        win.toggle_fullscreen()
        self.assertFalse(win.isFullScreen())
        self.assertIn("beendet", win.status_bar.currentMessage())

        # Verify QShortcut for F11
        self.assertEqual(win._fullscreen_shortcut.key().toString(), "F11")

        # Test keyPressEvent with F11
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_F11, Qt.KeyboardModifier.NoModifier)
        win.keyPressEvent(event)
        self.assertTrue(win.isFullScreen())
        win.keyPressEvent(event)
        self.assertFalse(win.isFullScreen())

        # Test header banner toggle signal connection
        win.header_banner.toggle_fullscreen_requested.emit()
        self.assertTrue(win.isFullScreen())
        win.header_banner.toggle_fullscreen_requested.emit()
        self.assertFalse(win.isFullScreen())
        win.close()
        win.deleteLater()
        _app.processEvents()

    def test_quick_preview_dialog_fullscreen_toggle(self):
        from gui_qt.dialogs.quick_preview_dialog import QuickPreviewDialog
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import Qt, QEvent

        dlg = QuickPreviewDialog(items=[])
        self.assertFalse(dlg.isFullScreen())
        dlg.toggle_fullscreen()
        self.assertTrue(dlg.isFullScreen())
        dlg.toggle_fullscreen()
        self.assertFalse(dlg.isFullScreen())

        # Test keyPressEvent F11
        ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_F11, Qt.KeyboardModifier.NoModifier)
        dlg.keyPressEvent(ev)
        self.assertTrue(dlg.isFullScreen())
        dlg.keyPressEvent(ev)
        self.assertFalse(dlg.isFullScreen())


class TestEntryPointsPersistence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def test_tree_init_prioritizes_saved_config_over_default_root(self):
        import tempfile
        from gui_qt.views.culling_tree import CullingDirectoryTreeWidget
        from core.config import AppConfig

        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            saved_dir = Path(tmp1) / "SavedRoot"
            saved_dir.mkdir()
            default_dir = Path(tmp2) / "DefaultRoot"
            default_dir.mkdir()

            cfg = AppConfig()
            cfg.transfer_target_dir = str(saved_dir)

            # default_root is passed, BUT config has a saved entry point
            tree = CullingDirectoryTreeWidget(
                config=cfg,
                config_root_key="transfer_target_dir",
                default_root=default_dir
            )

            # Saved root must take priority!
            self.assertEqual(tree.root_path.resolve(), saved_dir.resolve())
            self.assertEqual(cfg.transfer_target_dir, str(saved_dir))

    def test_tree_set_root_folder_persists_to_config(self):
        import tempfile
        from gui_qt.views.culling_tree import CullingDirectoryTreeWidget
        from core.config import AppConfig

        with tempfile.TemporaryDirectory() as tmp:
            new_root = Path(tmp) / "MyCustomEntry"
            new_root.mkdir()

            cfg = AppConfig()
            cfg.culling_root_folder = ""

            tree = CullingDirectoryTreeWidget(
                config=cfg,
                config_root_key="culling_root_folder"
            )

            tree.set_root_folder(new_root)
            self.assertEqual(tree.root_path.resolve(), new_root.resolve())
            self.assertEqual(cfg.culling_root_folder, str(new_root))

    def test_transfer_tab_refresh_defaults_restores_entry_points(self):
        import tempfile
        from gui_qt.views.transfer_tab import TransferTabView
        from core.config import AppConfig

        with tempfile.TemporaryDirectory() as tmp:
            src_root = Path(tmp) / "SourcePhotos"
            src_root.mkdir()
            dst_root = Path(tmp) / "DestNAS"
            dst_root.mkdir()

            cfg = AppConfig()
            cfg.transfer_source_dir = str(src_root)
            cfg.transfer_target_dir = str(dst_root)

            tab = TransferTabView(config=cfg)
            tab.refresh_defaults()

            self.assertEqual(tab.pane_source.current_folder.resolve(), src_root.resolve())
            self.assertEqual(tab.pane_dest.current_folder.resolve(), dst_root.resolve())


class TestAllSettingsPersistence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def test_mainwindow_restores_view_mode_and_boxes_and_tab(self):
        from gui_qt.main_window import MainWindow
        from core.config import AppConfig

        cfg = AppConfig()
        cfg.active_tab = 1
        cfg.import_view_mode = "gallery"
        cfg.import_gallery_thumb_size = 240
        cfg.import_show_exif_inspector = True
        cfg.import_sidebar_paths_expanded = False
        cfg.import_sidebar_patterns_expanded = True
        cfg.import_sidebar_general_expanded = True
        cfg.window_width = 1400
        cfg.window_height = 900

        win = MainWindow()
        win.config = cfg
        win._load_config_to_ui()

        # Check Tab 1 restored view states
        self.assertEqual(win.filter_bar.combo_view.currentData(), "gallery")
        self.assertEqual(win.filter_bar.slider_zoom.value(), 240)
        self.assertTrue(win.filter_bar.btn_toggle_exif.isChecked())
        self.assertFalse(win.box_paths.is_expanded)
        self.assertTrue(win.box_patterns.is_expanded)
        self.assertTrue(win.box_general.is_expanded)

        # Check active tab restored
        self.assertEqual(win.main_workflow_stack.currentIndex(), 1)
        self.assertTrue(win.header_banner.btn_tab_culling.isChecked())
        win.close()
        win.deleteLater()
        _app.processEvents()

    def test_culling_tab_restores_filmstrip_and_dock_state(self):
        from gui_qt.views.culling_tab import CullingTabView
        from core.config import AppConfig

        cfg = AppConfig()
        cfg.culling_show_filmstrip = False
        cfg.culling_dock_tab = 1

        tab = CullingTabView(config=cfg)
        self.assertTrue(tab.filmstrip.isHidden())
        self.assertEqual(tab.left_dock.tab_widget.currentIndex(), 1)

        # Toggle filmstrip and verify config update
        tab._toggle_filmstrip()
        self.assertFalse(tab.filmstrip.isHidden())
        self.assertTrue(cfg.culling_show_filmstrip)

    def test_transfer_pane_restores_view_mode_and_files_toggle(self):
        from gui_qt.views.transfer_tab import TransferPaneWidget
        from core.config import AppConfig

        cfg = AppConfig()
        cfg.transfer_source_show_files = False
        cfg.transfer_source_view_mode = "grid:200"
        cfg.transfer_source_sort_key = "size"
        cfg.transfer_source_sort_descending = True

        pane = TransferPaneWidget(title="Quelle", is_source=True, config=cfg)
        self.assertFalse(pane._show_files)
        self.assertFalse(pane.files_container.isVisible())
        self.assertEqual(pane.combo_view_mode.currentData(), "grid:200")
        self.assertEqual(pane.combo_sort.currentData(), "size")
        self.assertTrue(pane.btn_sort_dir.isChecked())

    def test_paired_header_view_zero_sum_resizing(self):
        from PySide6.QtWidgets import QTableView, QHeaderView
        from PySide6.QtGui import QStandardItemModel
        from gui_qt.widgets.paired_header import PairedHeaderView

        table = QTableView()
        header = PairedHeaderView(Qt.Orientation.Horizontal, table)
        table.setHorizontalHeader(header)
        model = QStandardItemModel(5, 3)
        table.setModel(model)
        for c in range(3):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
            table.setColumnWidth(c, 100)

        self.assertEqual(header.sectionSize(0), 100)
        self.assertEqual(header.sectionSize(1), 100)
        self.assertEqual(header.sectionSize(2), 100)

        # Simulate user drag expanding column 0
        header._user_resizing = True
        header.resizeSection(0, 140)
        self.assertEqual(header.sectionSize(0), 140)
        self.assertEqual(header.sectionSize(1), 60)
        self.assertEqual(header.sectionSize(2), 100)

        # Simulate user drag shrinking column 0
        header.resizeSection(0, 80)
        self.assertEqual(header.sectionSize(0), 80)
        self.assertEqual(header.sectionSize(1), 120)
        self.assertEqual(header.sectionSize(2), 100)
        header._user_resizing = False

    def test_quick_preview_dialog_polymorphic_items_and_fullscreen(self):
        from gui_qt.dialogs.quick_preview_dialog import QuickPreviewDialog
        from gui_qt.models.culling_model import CullingItem
        from gui_qt.views.transfer_tab import TransferItem

        # Test with CullingItem
        c_item = CullingItem(primary_path=Path("sample.jpg"), rating=4)
        c_item.selected = True
        dlg_culling = QuickPreviewDialog(items=[c_item], start_index=0, fullscreen=False)
        self.assertEqual(dlg_culling.lbl_filename.text(), "sample.jpg")
        self.assertTrue(dlg_culling.chk_selected.isChecked())
        dlg_culling.close()

        # Test with TransferItem
        t_item = TransferItem.from_path(Path("requirements.txt"))
        t_item.selected = True
        dlg_transfer = QuickPreviewDialog(items=[t_item], start_index=0, fullscreen=False)
        self.assertEqual(dlg_transfer.lbl_filename.text(), "requirements.txt")
        self.assertTrue(dlg_transfer.chk_selected.isChecked())
        dlg_transfer.close()

    def test_single_view_double_click_signal(self):
        from gui_qt.views.single_view import MediaSingleView
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QMouseEvent
        from core.config import AppConfig
        from core.importer import ScanItem, MediaMetadata

        dt = datetime(2026, 8, 15, 14, 30, 0)
        meta = MediaMetadata(file_path=Path("IMG_0001.JPG"), orig_name="IMG_0001", extension=".jpg", file_size=1024, date_taken=dt, date_source="EXIF")
        item = ScanItem(source_path=Path("IMG_0001.JPG"), metadata=meta, target_path=Path("IMG_0001.JPG"), status="Neu", is_duplicate=False, file_hash="h1")

        sv = MediaSingleView(config=AppConfig())
        sv.set_items([item], current_item=item)

        emitted = []
        sv.open_quick_preview_requested.connect(lambda it: emitted.append(it))

        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonDblClick,
            QPointF(100.0, 100.0),
            QPointF(100.0, 100.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        sv.mouseDoubleClickEvent(event)
        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0].source_path.name, "IMG_0001.JPG")

    def test_config_candidates_and_version_tracking(self):
        from core.config import AppConfig
        from core.version import __version__

        candidates = AppConfig.get_candidate_config_paths()
        self.assertGreater(len(candidates), 0)
        self.assertIn(AppConfig.get_default_config_path(), candidates)

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cfg_path = Path(tmpdir) / "old_config.json"
            cfg = AppConfig()
            cfg.culling_root_folder = "/custom/photos"
            cfg.file_pattern = "{YYYY}_custom_{orig_name}"
            cfg.save(old_cfg_path)

            loaded = AppConfig.load(old_cfg_path)
            self.assertEqual(loaded.culling_root_folder, "/custom/photos")
            self.assertEqual(loaded.file_pattern, "{YYYY}_custom_{orig_name}")
            self.assertEqual(loaded.last_known_version, __version__)

    def test_quick_preview_opens_original_when_no_preview(self):
        from gui_qt.dialogs.quick_preview_dialog import QuickPreviewDialog

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "video_clip.mp4"
            test_file.write_bytes(b"dummy video data")

            opened = []
            dlg = QuickPreviewDialog(items=[test_file], start_index=0, fullscreen=False)
            # Patch _open_original_external to verify it is called for unrenderable video
            dlg._open_original_external = lambda p: opened.append(p)
            dlg._load_image_preview(test_file)
            self.assertEqual(len(opened), 1)
            self.assertEqual(opened[0].name, "video_clip.mp4")
            dlg.close()

    def test_batch_rename_dialog_plan_and_execution(self):
        from gui_qt.dialogs.rename_dialog import BatchRenameDialog
        from gui_qt.views.transfer_tab import TransferItem
        from core.config import AppConfig

        with tempfile.TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)
            f1 = dir_path / "DSC_0010.JPG"
            f1.write_bytes(b"image data 1")
            sc1 = dir_path / "DSC_0010.xmp"
            sc1.write_bytes(b"xmp sidecar")
            f2 = dir_path / "DSC_0011.JPG"
            f2.write_bytes(b"image data 2")

            item1 = TransferItem.from_path(f1)
            item2 = TransferItem.from_path(f2)

            cfg = AppConfig()
            cfg.rename_file_pattern = "Test_{num:02d}_{orig_name}"

            dlg = BatchRenameDialog(
                items=[item1, item2],
                folder_path=dir_path,
                config=cfg
            )
            dlg.edit_pattern.setText("Pic_{num:02d}_{orig_name}")
            dlg.spin_start_num.setValue(1)

            plan = dlg._calculate_plan()
            self.assertEqual(len(plan), 2)
            self.assertEqual(plan[0].new_filename, "Pic_01_DSC_0010.JPG")
            self.assertEqual(plan[1].new_filename, "Pic_02_DSC_0011.JPG")
            self.assertEqual(len(plan[0].companions), 1)  # XMP companion detected

            # Execute rename
            dlg._execute_rename()

            self.assertTrue((dir_path / "Pic_01_DSC_0010.JPG").exists())
            self.assertTrue((dir_path / "Pic_01_DSC_0010.xmp").exists())
            self.assertTrue((dir_path / "Pic_02_DSC_0011.JPG").exists())
            self.assertFalse(f1.exists())
            self.assertFalse(sc1.exists())
            self.assertFalse(f2.exists())
            dlg.close()

    def test_light_mode_tree_and_panel_adaptivity(self):
        from gui_qt.styles.theme import theme_manager
        from gui_qt.views.culling_tree import CullingDirectoryTreeWidget
        from gui_qt.views.culling_left_dock import CullingLeftNavigationDock
        from gui_qt.widgets.empty_state import EmptyStateWidget
        from gui_qt.styles.icons import get_camera_icon

        cfg = AppConfig()

        # 1. Light Mode Verification
        theme_manager.apply_theme("light")
        self.assertEqual(theme_manager.effective_theme, "light")

        tree = CullingDirectoryTreeWidget(cfg)
        # Verify tree_view has NO hardcoded dark inline style
        self.assertNotIn("#090d16", tree.tree_view.styleSheet())
        self.assertNotIn("#0f172a", tree.tree_view.styleSheet())

        # Check total / raw / jpg item colors for Light mode
        c_tot, c_raw, c_jpg = tree._get_item_colors(10, 5, 5)
        self.assertEqual(c_tot.color().name(), "#0f172a")  # Dark slate for contrast on white
        self.assertEqual(c_raw.color().name(), "#be185d")  # Deep rose for contrast on white
        self.assertEqual(c_jpg.color().name(), "#0284c7")  # Deep sky blue for contrast on white

        # 2. Dark Mode Verification
        theme_manager.apply_theme("dark")
        self.assertEqual(theme_manager.effective_theme, "dark")
        c_tot_d, c_raw_d, c_jpg_d = tree._get_item_colors(10, 5, 5)
        self.assertEqual(c_tot_d.color().name(), "#f8fafc")  # White/light for contrast on dark
        self.assertEqual(c_raw_d.color().name(), "#f472b6")  # Light pink on dark
        self.assertEqual(c_jpg_d.color().name(), "#38bdf8")  # Sky blue on dark

        # 3. Dock & Empty State inline styles clean check
        dock = CullingLeftNavigationDock(cfg)
        self.assertNotIn("#090d16", dock.collapsed_strip.styleSheet())
        self.assertNotIn("#090d16", dock.tab_widget.styleSheet())

        empty = EmptyStateWidget()
        self.assertNotIn("#0b1120", empty.styleSheet())

        # 4. Vector camera icon check
        cam_icon = get_camera_icon("#0284c7", 32)
        self.assertFalse(cam_icon.isNull())

        tree.close()
        dock.close()
        empty.close()

    def test_light_mode_soft_palette_and_buttons(self):
        from pathlib import Path
        from gui_qt.styles.theme import theme_manager
        from gui_qt.styles.icons import get_icon_color, get_plus_icon, get_minus_icon, get_files_icon
        from gui_qt.views.transfer_tab import TransferTabView
        from gui_qt.views.culling_tab import CullingTabView

        cfg = AppConfig()

        # 1. Light stylesheet verification: non-glare slate neutral background
        qss_path = Path(__file__).resolve().parent.parent / "gui_qt" / "styles" / "light_fluent.qss"
        self.assertTrue(qss_path.exists())
        with open(qss_path, "r", encoding="utf-8") as fp:
            light_qss = fp.read()

        self.assertIn("QMainWindow, QWidget#centralWidget", light_qss)
        self.assertIn("#f1f5f9", light_qss)  # Soft non-glare background
        self.assertIn("QPushButton#btnReconcile", light_qss)
        self.assertIn("QPushButton#btnCopyAll", light_qss)
        self.assertIn("QPushButton#btnMoveAll", light_qss)
        self.assertIn("#cullingSidebarCard", light_qss)
        self.assertIn("QPushButton#cullingNavBtn", light_qss)
        self.assertIn("QPushButton#cullingZoomBtn", light_qss)
        self.assertIn("QPushButton#cullingStarBtn", light_qss)
        self.assertIn("QPushButton#cullingPickBtn", light_qss)
        self.assertIn("QPushButton#cullingRejectBtn", light_qss)
        self.assertIn("QPushButton#cullingWfBtn", light_qss)
        self.assertIn("QFrame#filmstripCard", light_qss)

        # 2. Check icon palette adaptation
        theme_manager.apply_theme("light")
        self.assertEqual(get_icon_color("normal"), "#334155")
        self.assertEqual(get_icon_color("accent"), "#0284c7")
        self.assertFalse(get_plus_icon().isNull())
        self.assertFalse(get_minus_icon().isNull())
        self.assertFalse(get_files_icon().isNull())

        # 3. TransferTabView buttons check: no dark background inline stylesheets
        transfer = TransferTabView(cfg)
        self.assertEqual(transfer.btn_reconcile.objectName(), "btnReconcile")
        self.assertEqual(transfer.btn_copy_all.objectName(), "btnCopyAll")
        self.assertEqual(transfer.btn_move_all.objectName(), "btnMoveAll")
        self.assertNotIn("#1e293b", transfer.btn_reconcile.styleSheet())
        self.assertNotIn("#1e293b", transfer.btn_copy_all.styleSheet())
        self.assertNotIn("#1e293b", transfer.btn_move_all.styleSheet())
        transfer.close()

        # 4. CullingTabView buttons & cards check: no dark background inline stylesheets
        culling = CullingTabView(cfg)
        self.assertEqual(culling.btn_refresh.objectName(), "compactToolBtn")
        self.assertEqual(culling.btn_prev.objectName(), "cullingNavBtn")
        self.assertEqual(culling.btn_next.objectName(), "cullingNavBtn")
        self.assertEqual(culling.btn_zoom.objectName(), "cullingZoomBtn")
        self.assertEqual(culling.btn_pick.objectName(), "cullingPickBtn")
        self.assertEqual(culling.btn_reject.objectName(), "cullingRejectBtn")
        self.assertEqual(culling.btn_wf_sooc.objectName(), "cullingWfBtn")
        self.assertNotIn("#1e293b", culling.btn_prev.styleSheet())
        self.assertNotIn("#1e293b", culling.btn_next.styleSheet())
        self.assertNotIn("#1e293b", culling.btn_zoom.styleSheet())
        culling.close()

    def test_alternating_row_colors_and_styles(self):
        """Verifies alternating zebra striping colors in directory trees, table views, and QSS."""
        from gui_qt.views.culling_tree import CullingDirectoryTreeWidget
        from gui_qt.views.table_view import MediaTableView
        from gui_qt.views.tree_view import MediaTreeView
        from gui_qt.views.transfer_tab import TransferPaneWidget

        app = QApplication.instance() or QApplication(sys.argv)
        cfg = AppConfig()

        # 1. Directory Tree View in Culling (and Transfer)
        tree_w = CullingDirectoryTreeWidget(cfg)
        self.assertTrue(tree_w.tree_view.alternatingRowColors(), "CullingDirectoryTreeWidget must have alternatingRowColors enabled")
        tree_w.close()

        # 2. MediaTableView (Import Tab)
        table_v = MediaTableView()
        self.assertTrue(table_v.alternatingRowColors(), "MediaTableView must have alternatingRowColors enabled")
        table_v.close()

        # 3. MediaTreeView (Import Tab)
        target_t = MediaTreeView()
        self.assertTrue(target_t.tree.alternatingRowColors(), "MediaTreeView must have alternatingRowColors enabled")
        target_t.close()

        # 4. TransferPaneWidget Table (Transfer Tab source & target)
        pane_w = TransferPaneWidget(title="Quelle", is_source=True, config=cfg)
        self.assertTrue(pane_w.table_view.alternatingRowColors(), "TransferPaneWidget table must have alternatingRowColors enabled")
        self.assertTrue(pane_w.tree_widget.tree_view.alternatingRowColors(), "TransferPaneWidget tree must have alternatingRowColors enabled")
        pane_w.close()

        # 5. Check QSS definitions for alternating zebra colors
        light_path = Path(__file__).parent.parent / "gui_qt" / "styles" / "light_fluent.qss"
        dark_path = Path(__file__).parent.parent / "gui_qt" / "styles" / "dark_fluent.qss"
        light_qss = light_path.read_text(encoding="utf-8")
        dark_qss = dark_path.read_text(encoding="utf-8")

        self.assertIn("alternate-background-color: #f1f5f9;", light_qss)
        self.assertIn("alternate-background-color: #162032;", dark_qss)


class TestPackagingSuite(unittest.TestCase):
    def test_collect_project_files_includes_stylesheets_and_fallbacks(self):
        """Verifies package.py collects all required project files including QSS stylesheets."""
        from package import collect_project_files
        files = collect_project_files()
        rel_paths = [str(rel).replace("\\", "/") for _, rel in files]

        self.assertIn("gui_qt/styles/dark_fluent.qss", rel_paths)
        self.assertIn("gui_qt/styles/light_fluent.qss", rel_paths)
        self.assertIn("vitrina.py", rel_paths)
        self.assertIn("Vitrina.bat", rel_paths)
        self.assertIn("vitrina.sh", rel_paths)
        self.assertIn("fotodown.py", rel_paths)
        self.assertIn("FotoDown.bat", rel_paths)
        self.assertIn("fotodown.sh", rel_paths)
        self.assertIn("requirements.txt", rel_paths)
        self.assertIn("gui/app.py", rel_paths)

    def test_culling_model_import_and_type_annotations(self):
        """Ensures culling_model imports without NameError on Python 3.11+."""
        import gui_qt.models.culling_model as cm
        self.assertTrue(hasattr(cm, "check_exported_file"))
        self.assertTrue(hasattr(cm, "count_folder_images"))


if __name__ == "__main__":
    unittest.main()
