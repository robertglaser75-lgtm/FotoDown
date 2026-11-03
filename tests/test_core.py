from core.drive_detector import eject_drive
"""Unit tests for FotoDown core modules."""

from datetime import datetime
import os
from pathlib import Path
import tempfile
import unittest
from PIL import Image

from core.config import AppConfig
from core.exif_reader import MediaMetadata, extract_metadata
from core.naming import (
    format_filename,
    format_folder_path,
    resolve_destination,
    generate_sample_preview,
    sanitize_filename
)
from core.history import ImportHistory, compute_file_hash
from core.importer import ImporterEngine, ScanItem
from core.metadata_writer import format_copyright_template, generate_xmp_content, inject_metadata_sidecar


class TestNaming(unittest.TestCase):
    def setUp(self):
        self.sample_meta = MediaMetadata(
            file_path=Path("DSC_4321.JPG"),
            orig_name="DSC_4321",
            extension=".jpg",
            file_size=5000000,
            date_taken=datetime(2026, 7, 24, 15, 30, 45),
            date_source="EXIF DateTimeOriginal",
            camera_make="Canon",
            camera_model="EOS R6",
            camera_name="Canon EOS R6",
        )

    def test_format_filename(self):
        pattern = "{YYYY}-{MM}-{DD}_{hh}-{mm}-{ss}_{camera}_{orig_name}"
        res = format_filename(pattern, self.sample_meta)
        self.assertEqual(res, "2026-07-24_15-30-45_Canon_EOS_R6_DSC_4321.jpg")

    def test_format_folder(self):
        pattern = "{YYYY}/{YYYY}-{MM}-{DD}"
        res = format_folder_path(pattern, self.sample_meta)
        self.assertEqual(res, Path("2026") / "2026-07-24")

    def test_sanitize_filename(self):
        bad_name = "test/name:with*illegal?chars|"
        cleaned = sanitize_filename(bad_name)
        self.assertEqual(cleaned, "testnamewithillegalchars")

    def test_sequential_numbering(self):
        pattern1 = "{YYYY}_{num:04d}_{orig_name}"
        res1 = format_filename(pattern1, self.sample_meta, index=42)
        self.assertEqual(res1, "2026_0042_DSC_4321.jpg")

        pattern2 = "Foto_{num}_{camera}"
        res2 = format_filename(pattern2, self.sample_meta, index=7)
        self.assertEqual(res2, "Foto_7_Canon_EOS_R6.jpg")

    def test_raw_jpg_separation(self):
        raw_meta = MediaMetadata(
            file_path=Path("DSC_4321.CR3"),
            orig_name="DSC_4321",
            extension=".cr3",
            file_size=30000000,
            date_taken=datetime(2026, 7, 24, 15, 30, 45),
            date_source="EXIF",
            camera_make="Canon",
            camera_model="EOS R6",
        )
        self.assertTrue(raw_meta.is_raw)
        self.assertEqual(raw_meta.media_type, "RAW")

        # Test subfolders
        dest_raw = resolve_destination(
            target_root=Path("/photos"),
            folder_pattern="{YYYY}/{MM}",
            file_pattern="{orig_name}",
            meta=raw_meta,
            type_folder_organization="subfolders",
        )
        self.assertEqual(dest_raw, Path("/photos/2026/07/RAW/DSC_4321.cr3"))

        dest_jpg = resolve_destination(
            target_root=Path("/photos"),
            folder_pattern="{YYYY}/{MM}",
            file_pattern="{orig_name}",
            meta=self.sample_meta,
            type_folder_organization="subfolders",
        )
        self.assertEqual(dest_jpg, Path("/photos/2026/07/JPG/DSC_4321.jpg"))

    def test_video_destination(self):
        vid_meta = MediaMetadata(
            file_path=Path("CLIP01.MP4"),
            orig_name="CLIP01",
            extension=".mp4",
            file_size=50000000,
            date_taken=datetime(2026, 7, 24, 15, 30, 45),
            date_source="Video",
        )
        self.assertTrue(vid_meta.is_video)
        self.assertEqual(vid_meta.media_type, "VIDEO")

        dest_vid = resolve_destination(
            target_root=Path("/photos"),
            folder_pattern="{YYYY}",
            file_pattern="{orig_name}",
            meta=vid_meta,
            video_target_root=Path("/videos"),
        )
        self.assertEqual(dest_vid, Path("/videos/2026/CLIP01.mp4"))

    def test_preview(self):
        f_folder, f_name = generate_sample_preview(
            file_pattern="{YYYY}_{orig_name}",
            folder_pattern="{YYYY}/{MONTH_NAME}"
        )
        self.assertIn("2026", f_folder)
        self.assertIn("DSC_0123.jpg", f_name)


class TestHistoryAndImport(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name)
        self.source_dir = self.root_path / "source"
        self.target_dir = self.root_path / "target"
        self.source_dir.mkdir()
        self.target_dir.mkdir()

        self.db_path = self.root_path / "test_history.db"
        self.history = ImportHistory(self.db_path)
        self.engine = ImporterEngine(self.history)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_dummy_image(self, filename: str, content: bytes = b"dummy content") -> Path:
        p = self.source_dir / filename
        p.write_bytes(content)
        return p

    def test_history_recording_and_duplicate_check(self):
        img_path = self._create_dummy_image("test1.jpg", b"image1_data")
        self.assertFalse(self.history.is_imported(img_path))

        meta = extract_metadata(img_path)
        dest_path = self.target_dir / "test1.jpg"
        self.history.record_import(img_path, dest_path, meta)

        self.assertTrue(self.history.is_imported(img_path))
        self.assertEqual(self.history.get_count(), 1)

    def test_scan_and_import(self):
        img1 = self._create_dummy_image("IMG_0001.JPG", b"data_1")
        img2 = self._create_dummy_image("IMG_0002.JPG", b"data_2")

        cfg = AppConfig(
            source_dir=str(self.source_dir),
            target_dir=str(self.target_dir),
            file_pattern="{orig_name}_custom",
            folder_pattern="Sorted/{YYYY}",
            only_new_files=True
        )

        # 1. Scan
        items = self.engine.scan(self.source_dir, cfg)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].status, "Neu")
        self.assertEqual(items[1].status, "Neu")
        self.assertTrue(items[0].selected)
        self.assertTrue(items[1].selected)

        # 2. Execute Import
        stats = self.engine.execute_import(items, cfg)
        self.assertEqual(stats.copied_success, 2)
        self.assertEqual(stats.duplicates_skipped, 0)

        # Verify files in target
        target_files = list(self.target_dir.glob("**/*.jpg"))
        self.assertEqual(len(target_files), 2)

        # 3. Second scan: should mark as duplicate and selected=False
        items_second = self.engine.scan(self.source_dir, cfg)
        self.assertEqual(len(items_second), 2)
        self.assertTrue(items_second[0].is_duplicate)
        self.assertTrue(items_second[1].is_duplicate)
        self.assertEqual(items_second[0].status, "Bereits importiert")
        self.assertFalse(items_second[0].selected)
        self.assertFalse(items_second[1].selected)

        # 4. Import second time: should skip duplicates
        stats2 = self.engine.execute_import(items_second, cfg)
        self.assertEqual(stats2.copied_success, 0)
        self.assertEqual(stats2.duplicates_skipped, 2)

    def test_selection_filtering(self):
        img1 = self._create_dummy_image("IMG_0010.JPG", b"data_10")
        img2 = self._create_dummy_image("IMG_0011.JPG", b"data_11")

        cfg = AppConfig(
            source_dir=str(self.source_dir),
            target_dir=str(self.target_dir),
        )

        items = self.engine.scan(self.source_dir, cfg)
        self.assertEqual(len(items), 2)

        # Deselect img1 manually
        items[0].selected = False

        stats = self.engine.execute_import(items, cfg)
        self.assertEqual(stats.copied_success, 1)
        self.assertEqual(stats.duplicates_skipped, 1)

    def test_item_filtering_predicates(self):
        now = datetime.now()
        meta_jpg = MediaMetadata(Path("IMG_100.JPG"), "IMG_100", ".jpg", 1000, now, "EXIF", camera_make="Sony", camera_model="A7IV", camera_name="Sony A7IV")
        meta_raw = MediaMetadata(Path("IMG_100.ARW"), "IMG_100", ".arw", 5000, now, "EXIF", camera_make="Sony", camera_model="A7IV", camera_name="Sony A7IV")
        meta_vid = MediaMetadata(Path("CLIP_001.MP4"), "CLIP_001", ".mp4", 20000, now, "Video", camera_make="Canon", camera_model="EOS R6", camera_name="Canon EOS R6")

        item1 = ScanItem(Path("IMG_100.JPG"), meta_jpg, Path("2026/IMG_100.jpg"), False, "hash1", "Neu")
        item2 = ScanItem(Path("IMG_100.ARW"), meta_raw, Path("2026/RAW/IMG_100.arw"), True, "hash2", "Bereits importiert")
        item3 = ScanItem(Path("CLIP_001.MP4"), meta_vid, Path("2026/CLIP_001.mp4"), False, "hash3", "Neu")

        items = [item1, item2, item3]

        # Filter by media type RAW
        raw_items = [it for it in items if it.metadata.media_type == "RAW"]
        self.assertEqual(len(raw_items), 1)
        self.assertEqual(raw_items[0].source_path.name, "IMG_100.ARW")

        # Filter by camera Canon_EOS_R6
        canon_items = [it for it in items if (it.metadata.formatted_camera or "") == "Canon_EOS_R6"]
        self.assertEqual(len(canon_items), 1)
        self.assertEqual(canon_items[0].source_path.name, "CLIP_001.MP4")

        # Filter by extension .jpg
        jpg_items = [it for it in items if it.source_path.suffix.lower() == ".jpg"]
        self.assertEqual(len(jpg_items), 1)
        self.assertEqual(jpg_items[0].source_path.name, "IMG_100.JPG")

    def test_eject_drive_empty(self):
        success, msg = eject_drive("")
        self.assertFalse(success)
        self.assertIn("Kein Pfad", msg)

    def test_eject_drive_invalid_path(self):
        success, msg = eject_drive("UNC_PATH_WITHOUT_LETTER")
        self.assertFalse(success)

    def test_dual_backup_and_checksum_verification(self):
        img = self._create_dummy_image("PHOTO_01.JPG", b"content_for_photo_01")
        with tempfile.TemporaryDirectory() as backup_dir:
            cfg = AppConfig(
                source_dir=str(self.source_dir),
                target_dir=str(self.target_dir),
                enable_dual_backup=True,
                backup_target_dir=str(backup_dir),
                verify_checksums=True,
            )
            items = self.engine.scan(self.source_dir, cfg)
            self.assertEqual(len(items), 1)

            stats = self.engine.execute_import(items, cfg)
            self.assertEqual(stats.copied_success, 1)
            self.assertEqual(stats.backup_success, 1)
            self.assertEqual(stats.failed, 0)

            target_files = list(Path(self.target_dir).rglob("*.jpg"))
            backup_files = list(Path(backup_dir).rglob("*.jpg"))
            self.assertEqual(len(target_files), 1)
            self.assertEqual(len(backup_files), 1)
            self.assertEqual(compute_file_hash(target_files[0]), items[0].file_hash)
            self.assertEqual(compute_file_hash(backup_files[0]), items[0].file_hash)

    def test_raw_jpg_pairing_scan_and_import(self):
        # Create paired files with identical stem: _DSC0001.ARW and _DSC0001.JPG
        raw_file = self._create_dummy_image("_DSC0001.ARW", b"raw_data_content_bytes")
        jpg_file = self._create_dummy_image("_DSC0001.JPG", b"jpg_data_content_bytes")
        solo_jpg = self._create_dummy_image("_DSC0002.JPG", b"solo_jpg_bytes")

        cfg = AppConfig(
            source_dir=str(self.source_dir),
            target_dir=str(self.target_dir),
            pair_raw_jpg=True,
            type_folder_organization="subfolders",
            verify_checksums=True,
        )

        items = self.engine.scan(self.source_dir, cfg)
        # Should be 2 items: paired entry and solo jpg
        self.assertEqual(len(items), 2)

        pair_item = next(it for it in items if it.source_path.name == "_DSC0001.ARW")
        self.assertTrue(pair_item.is_pair)
        self.assertIsNotNone(pair_item.companion_path)
        self.assertEqual(pair_item.companion_path.name, "_DSC0001.JPG")
        self.assertEqual(pair_item.display_type, "RAW+JPG")
        self.assertEqual(pair_item.total_size, len(b"raw_data_content_bytes") + len(b"jpg_data_content_bytes"))

        # Execute import
        stats = self.engine.execute_import(items, cfg)
        self.assertEqual(stats.copied_success, 2)
        self.assertEqual(stats.paired_count, 1)
        self.assertEqual(stats.failed, 0)

        # Check target folder structure: RAW in /RAW, JPG in /JPG
        raw_targets = list(Path(self.target_dir).rglob("*.arw"))
        jpg_targets = list(Path(self.target_dir).rglob("*.jpg"))
        self.assertEqual(len(raw_targets), 1)
        self.assertEqual(len(jpg_targets), 2)
        self.assertIn("RAW", str(raw_targets[0].parent))
        self.assertIn("JPG", str(jpg_targets[0].parent))

        # Check both RAW and companion JPG are recorded in history
        self.assertTrue(self.history.is_imported(raw_file))
        self.assertTrue(self.history.is_imported(jpg_file))

    def test_xmp_sidecar_synchronization(self):
        # Create RAW file with .xmp sidecar
        raw_file = self._create_dummy_image("_DSC0005.CR3", b"cr3_raw_data")
        xmp_file = self._create_dummy_image("_DSC0005.xmp", b"<x:xmpmeta>sidecar</x:xmpmeta>")

        cfg = AppConfig(
            source_dir=str(self.source_dir),
            target_dir=str(self.target_dir),
            sync_xmp_sidecars=True,
            delete_source_after_import=True,
        )

        items = self.engine.scan(self.source_dir, cfg)
        self.assertEqual(len(items), 1)
        self.assertEqual(len(items[0].sidecar_paths), 1)
        self.assertEqual(items[0].display_type, "RAW + XMP")

        stats = self.engine.execute_import(items, cfg)
        self.assertEqual(stats.copied_success, 1)
        self.assertEqual(stats.sidecars_copied, 1)

        # Check target sidecar exists
        xmp_targets = list(Path(self.target_dir).rglob("*.xmp"))
        self.assertEqual(len(xmp_targets), 1)
        self.assertEqual(xmp_targets[0].read_bytes(), b"<x:xmpmeta>sidecar</x:xmpmeta>")

        # Check sources deleted
        self.assertFalse(raw_file.exists())
        self.assertFalse(xmp_file.exists())


class TestMetadataWriter(unittest.TestCase):
    def test_copyright_template_formatting(self):
        s = format_copyright_template("© {year} {author}", "John Doe", 2026)
        self.assertEqual(s, "© 2026 John Doe")

    def test_generate_xmp_content(self):
        xmp = generate_xmp_content(
            creator="Jane Photographer",
            copyright_notice="© 2026 Jane Photographer. All rights reserved.",
            keywords=["Landscape", "Nature", "Munich"]
        )
        self.assertIn("Jane Photographer", xmp)
        self.assertIn("dc:creator", xmp)
        self.assertIn("Landscape", xmp)
        self.assertIn("Munich", xmp)

    def test_inject_metadata_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            img_path = Path(tmp_dir) / "IMG_1234.JPG"
            img_path.write_bytes(b"dummy_image_data")
            sidecar = inject_metadata_sidecar(
                target_path=img_path,
                creator="Test Creator",
                copyright_template="© {year} {creator}",
                keywords_str="Test, Sample",
                date_taken=2026,
            )
            self.assertTrue(sidecar.exists())
            self.assertEqual(sidecar.suffix, ".xmp")
            content = sidecar.read_text(encoding="utf-8")
            self.assertIn("Test Creator", content)
            self.assertIn("© 2026 Test Creator", content)


class TestExifShootingMetadata(unittest.TestCase):
    def test_formatted_exposure_and_gps(self):
        meta = MediaMetadata(
            file_path=Path("sample.jpg"),
            orig_name="sample",
            extension=".jpg",
            file_size=1024,
            date_taken=datetime(2026, 7, 24, 15, 30, 45),
            date_source="EXIF DateTimeOriginal",
            f_number=2.8,
            exposure_time=0.002,
            iso=400,
            focal_length=50.0,
            width=6000,
            height=4000,
            gps_lat=48.137154,
            gps_lon=11.576124,
        )
        self.assertEqual(meta.formatted_exposure, "ƒ/2.8 | 1/500s | ISO 400 | 50mm")
        self.assertEqual(meta.formatted_dimensions, "6000 × 4000 (24.0 MP)")
        self.assertIn("48.13715° N", meta.formatted_gps)
        self.assertIn("11.57612° E", meta.formatted_gps)


if __name__ == "__main__":
    unittest.main()
