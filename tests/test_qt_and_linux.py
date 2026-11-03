"""Unit tests for Qt models, cross-platform drive detection, and thumbnails."""

from datetime import datetime
import os
from pathlib import Path
import tempfile
import unittest

from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtWidgets import QApplication

from core.drive_detector import (
    DriveInfo, DiskSpaceInfo, _detect_drives_linux,
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
from gui_qt.dialogs.quick_preview_dialog import QuickPreviewDialog


class TestVersion(unittest.TestCase):
    def test_version_format(self):
        parts = __version__.split(".")
        self.assertGreaterEqual(len(parts), 3)
        self.assertEqual(__version__, "0.6.0")


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


if __name__ == "__main__":
    unittest.main()
