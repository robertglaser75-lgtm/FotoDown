"""Unit tests for Qt models, cross-platform drive detection, and thumbnails."""

from datetime import datetime
import os
from pathlib import Path
import tempfile
import unittest

from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtWidgets import QApplication

from core.drive_detector import DriveInfo, _detect_drives_linux, detect_drives
from core.exif_reader import MediaMetadata
from core.importer import ScanItem
from core.thumbnail import generate_thumbnail
from core.version import __version__
from gui_qt.models.scan_model import ScanTableModel
from gui_qt.models.filter_proxy import ScanFilterProxyModel


class TestVersion(unittest.TestCase):
    def test_version_format(self):
        parts = __version__.split(".")
        self.assertGreaterEqual(len(parts), 3)
        self.assertEqual(__version__, "0.3.2")


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
                dcim_path=dcim_dir
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
            file_hash="hash1",
            status="Neu",
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
            file_hash="hash2",
            status="Bereits importiert",
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
                date_source="FileHeader",
                camera_make="Sony",
                camera_model="ILCE-7M4",
                camera_name="Sony A7IV"
            ),
            target_path=Path("/out/2026-08-15_VID_0003.MP4"),
            is_duplicate=False,
            file_hash="hash3",
            status="Neu",
            selected=True
        )
        return [item1, item2, item3]

    def test_model_data_and_selection(self):
        items = self._create_sample_items()
        model = ScanTableModel(items)

        self.assertEqual(model.rowCount(), 3)
        self.assertEqual(model.columnCount(), len(ScanTableModel.COLUMNS))

        # Check column data
        idx_status = model.index(0, 1)
        self.assertEqual(model.data(idx_status, Qt.ItemDataRole.DisplayRole), "Neu")

        idx_chk = model.index(0, 0)
        self.assertEqual(model.data(idx_chk, Qt.ItemDataRole.CheckStateRole), Qt.CheckState.Checked)

        # Toggle selection
        model.setData(idx_chk, Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
        self.assertFalse(items[0].selected)

        # Bulk selection methods
        model.select_all()
        self.assertTrue(all(it.selected for it in items))

        model.deselect_all()
        self.assertTrue(all(not it.selected for it in items))

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


if __name__ == "__main__":
    unittest.main()
