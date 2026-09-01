#!/usr/bin/env python3
"""FotoDown - Foto-Importeur, EXIF-Umbenennung & Duplikaterkennung.

Startet standardmäßig die moderne grafische Benutzeroberfläche (GUI)
oder kann mit Argumenten als Kommandozeilenwerkzeug (CLI) betrieben werden.
"""

import argparse
from pathlib import Path
import sys

# Ensure project directory is in sys.path even when called via UNC path or another cwd
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from core.config import AppConfig
from core.history import ImportHistory
from core.importer import ImporterEngine
from gui.app import run_gui


def main_cli(args):
    """Executes FotoDown in Command Line Interface mode."""
    config = AppConfig.load()
    if args.source:
        config.source_dir = args.source
    if args.target:
        config.target_dir = args.target
    if args.video_target:
        config.separate_video_dir = True
        config.video_target_dir = args.video_target
    if args.type_org:
        config.type_folder_organization = args.type_org
    if args.file_pattern:
        config.file_pattern = args.file_pattern
    if args.folder_pattern:
        config.folder_pattern = args.folder_pattern

    if not config.source_dir or not Path(config.source_dir).exists():
        print(f"[Fehler] Quellordner '{config.source_dir}' existiert nicht.")
        sys.exit(1)

    print(f"=== FotoDown CLI ===")
    print(f"Quelle:         {config.source_dir}")
    print(f"Ziel Fotos:     {config.target_dir}")
    if config.separate_video_dir:
        print(f"Ziel Videos:    {config.video_target_dir}")
    print(f"Ablage-Modus:   {config.type_folder_organization}")
    print(f"Dateimuster:    {config.file_pattern}")
    print(f"Ordnermuster:   {config.folder_pattern}")
    print(f"Nur neue Fotos: {config.only_new_files}")
    print("--------------------------------------------------")

    history = ImportHistory()
    engine = ImporterEngine(history)

    print("Scanne Quellordner...")
    items = engine.scan(Path(config.source_dir), config)
    new_items = [it for it in items if not it.is_duplicate]

    print(f"Gefunden: {len(items)} Dateien | Neu: {len(new_items)} | Bereits importiert: {len(items) - len(new_items)}")

    if args.dry_run or args.scan_only:
        print("\n--- Vorschau der neuen Dateien ---")
        for it in new_items[:20]:
            print(f"  [{it.metadata.media_type}] {it.source_path.name} -> {it.target_path}")
        if len(new_items) > 20:
            print(f"  ... und {len(new_items) - 20} weitere")
        return

    if not new_items:
        print("Keine neuen Dateien zum Importieren vorhanden.")
        return

    print("\nStarte Import...")

    def on_progress(cur, total, msg):
        pct = (cur / total) * 100 if total > 0 else 0
        sys.stdout.write(f"\r[{pct:5.1f}%] {msg:<60}")
        sys.stdout.flush()

    stats = engine.execute_import(items, config, progress_callback=on_progress)
    print("\n--------------------------------------------------")
    mb = stats.bytes_copied / (1024 * 1024)
    print(f"Import abgeschlossen: {stats.copied_success} kopiert ({mb:.1f} MB), {stats.duplicates_skipped} übersprungen, {stats.failed} Fehler.")


def main():
    parser = argparse.ArgumentParser(description="FotoDown - Foto-Importeur & EXIF-Manager")
    parser.add_argument("--cli", action="store_true", help="Startet im Kommandozeilenmodus statt GUI")
    parser.add_argument("--source", "-s", type=str, help="Quellordner oder Speicherkarte")
    parser.add_argument("--target", "-t", type=str, help="Zielordner für sortierte Fotos")
    parser.add_argument("--video-target", "-v", type=str, help="Separater Zielordner für Videos")
    parser.add_argument("--type-org", choices=["same", "subfolders", "parent_folders"], default=None,
                        help="Organisation: 'same' (alle zusammen), 'subfolders' (.../JPG und .../RAW), 'parent_folders' (JPG/... und RAW/...)")
    parser.add_argument("--file-pattern", type=str, help="Namensmuster (z.B. '{YYYY}-{MM}-{DD}_{hh}-{mm}-{ss}_{camera}_{orig_name}')")
    parser.add_argument("--folder-pattern", type=str, help="Ordnermuster (z.B. '{YYYY}/{YYYY}-{MM}-{DD}')")
    parser.add_argument("--dry-run", "--scan-only", action="store_true", help="Nur scannen und Vorschau ausgeben")

    args = parser.parse_args()

    if args.cli or args.source or args.dry_run:
        main_cli(args)
    else:
        run_gui()


if __name__ == "__main__":
    main()
