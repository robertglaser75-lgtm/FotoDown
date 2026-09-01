"""End-to-end integration test with real EXIF JPEG files."""

from datetime import datetime
import os
from pathlib import Path
import tempfile
import unittest
from PIL import Image, ExifTags

from core.config import AppConfig
from core.history import ImportHistory
from core.importer import ImporterEngine


def create_test_jpeg_with_exif(path: Path, camera_make: str, camera_model: str, date_str: str):
    """Creates a minimal valid JPEG with EXIF tags."""
    img = Image.new("RGB", (100, 100), color=(73, 109, 137))
    exif = img.getexif()
    # 0x010F = Make, 0x0110 = Model, 0x9003 = DateTimeOriginal
    exif[0x010F] = camera_make
    exif[0x0110] = camera_model
    exif[0x9003] = date_str
    img.save(path, exif=exif)


class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "sd_card" / "DCIM" / "100EOS_R"
        self.target = self.root / "My_Photos"
        self.source.mkdir(parents=True)
        self.target.mkdir(parents=True)

        self.db_path = self.root / "history.db"
        self.history = ImportHistory(self.db_path)
        self.engine = ImporterEngine(self.history)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_exif_import_pipeline(self):
        f1 = self.source / "IMG_0001.JPG"
        f2 = self.source / "IMG_0002.JPG"
        create_test_jpeg_with_exif(f1, "Canon", "EOS R6", "2026:05:18 10:30:00")
        create_test_jpeg_with_exif(f2, "Sony", "ILCE-7M4", "2026:06:20 18:45:12")

        cfg = AppConfig(
            source_dir=str(self.source),
            target_dir=str(self.target),
            file_pattern="{YYYY}-{MM}-{DD}_{hh}-{mm}-{ss}_{camera}_{orig_name}",
            folder_pattern="{YYYY}/{YYYY}-{MM}-{DD}",
            only_new_files=True,
        )

        # 1. Scan
        items = self.engine.scan(self.source, cfg)
        self.assertEqual(len(items), 2)

        # Check metadata extraction
        self.assertEqual(items[0].metadata.camera_make, "Canon")
        self.assertEqual(items[0].metadata.camera_model, "EOS R6")
        self.assertEqual(items[0].metadata.date_taken.strftime("%Y-%m-%d %H:%M:%S"), "2026-05-18 10:30:00")

        self.assertEqual(items[1].metadata.camera_make, "Sony")
        self.assertEqual(items[1].metadata.camera_model, "ILCE-7M4")
        self.assertEqual(items[1].metadata.date_taken.strftime("%Y-%m-%d %H:%M:%S"), "2026-06-20 18:45:12")

        # Check calculated destination names
        self.assertEqual(items[0].target_path.name, "2026-05-18_10-30-00_Canon_EOS_R6_IMG_0001.jpg")
        self.assertEqual(items[1].target_path.name, "2026-06-20_18-45-12_Sony_ILCE-7M4_IMG_0002.jpg")

        # 2. Execute Import
        stats = self.engine.execute_import(items, cfg)
        self.assertEqual(stats.copied_success, 2)

        # Verify files on disk
        dest1 = self.target / "2026" / "2026-05-18" / "2026-05-18_10-30-00_Canon_EOS_R6_IMG_0001.jpg"
        dest2 = self.target / "2026" / "2026-06-20" / "2026-06-20_18-45-12_Sony_ILCE-7M4_IMG_0002.jpg"
        self.assertTrue(dest1.exists())
        self.assertTrue(dest2.exists())

        # 3. Re-scan: All must be marked duplicate
        items_re = self.engine.scan(self.source, cfg)
        self.assertTrue(all(it.is_duplicate for it in items_re))

        # 4. Add a third new image
        f3 = self.source / "IMG_0003.JPG"
        create_test_jpeg_with_exif(f3, "Nikon", "Z8", "2026:07:01 12:00:00")

        items_with_new = self.engine.scan(self.source, cfg)
        self.assertEqual(len(items_with_new), 3)
        new_only = [it for it in items_with_new if not it.is_duplicate]
        self.assertEqual(len(new_only), 1)
        self.assertEqual(new_only[0].metadata.camera_model, "Z8")

        stats3 = self.engine.execute_import(items_with_new, cfg)
        self.assertEqual(stats3.copied_success, 1)
        self.assertEqual(stats3.duplicates_skipped, 2)


if __name__ == "__main__":
    unittest.main()
