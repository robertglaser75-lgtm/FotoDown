# Changelog

Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.
Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/) und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

## [0.4.0] - 2026-11-03

### Hinzugefügt
- **Modernisierter Fluent Dark Splashscreen (`gui_qt/widgets/splash_screen.py`):**
  - Eleganter Startbildschirm beim App-Start mit Logo, Versionsanzeige und Ladefortschritt (`QSplashScreen`).
  - Asynchrone Statusanzeige während der Initialisierung von Ressourcen, Hardware-Erkennung und Datenmodellen.
- **Speicherplatz-Visualisierung (`gui_qt/widgets/storage_bar.py`):**
  - Dynamische Anzeige des belegten und freien Speichers für Quelllaufwerke (SD-Karten/Ordner) und Ziellaufwerke (Festplatten/Netzwerkfreigaben).
  - Farbcodierte Füllstandsbalken (Normal, Warnung bei >85%, Kritisch bei >95%).
  - **Pre-Flight-Speicherkapazitätsprüfung:** Automatische Vorab-Prüfung, ob auf der Zielfestplatte genügend freier Speicher für die ausgewählten Fotos vorhanden ist, mit visueller Warnung und Sperre bei Speicherengpässen.
- **Stufenloser Zoom-Slider für die Fotogalerie:**
  - Schieberegler in der Filterleiste zum Skalieren der Galerie-Vorschaubilder zwischen 110px und 320px.
  - Dynamische Anpassung des `GalleryDelegate`-Rasters und flüssiges Reflow.
- **Neues 2-Spalten-Layout (Sidebar links, Medienbereich rechts):**
  - Vertikaler Splitter durch horizontalen Splitter ersetzt: Einstellungen, Laufwerksauswahl und Aktionen befinden sich in einer scrollbaren Sidebar links, wodurch der Foto- und Tabellenbereich die maximale Fensterhöhe erhält.
- **Erweiterte Speicherplatz-Erkennung (`core/drive_detector.py`):**
  - Neues Datenmodell `DiskSpaceInfo` und Hilfsfunktionen `get_disk_space()` und `format_size()`.
  - Unterstützung für lokale Festplatten, Wechsellaufwerke und UNC-Netzwerkpfade.

## [0.3.2] - 2026-10-22

### Behoben
- **Encoding & Zeichensatz (Mojibake):**
  - Vollständige Bereinigung aller Quelltextdateien auf sauberes UTF-8 ohne BOM.
  - Alle deutschen Umlaute (ä, ö, ü, ß) und Symbole werden nun plattformübergreifend sauber dargestellt.
  - Behebung des Mnemonic-Verhaltens in Qt für Checkboxen (`&&`), sodass `Fotos & Videos` korrekt angezeigt wird.
  - Tabellenspalten-Header für die Auswahl auf ein sauberes Häkchen (`✓`) optimiert.

## [0.3.1] - 2026-10-22

### Behoben
- **Batch-Startdatei (`FotoDown.bat`):**
  - Behebung des Fehlers "kann den Pfad nicht finden" / "tle konnte nicht gefunden werden" durch bereinigte ASCII-Kodierung ohne BOM.
  - Robuste Pfadbehandlung für lokale Netzlaufwerke (`D:\`) und direkte UNC-Netzwerkpfade (`\\192.168.1.20\...`).
  - Automatische Erkennung des Python-Interpreters (`python` und `py`).
- **Signal- und Argument-Fehler in den Qt-Widgets:**
  - Behebung eines `TypeError` beim Aufruf von `generate_sample_preview` im `PatternEditorWidget`.
  - Korrektur der Argumentenübergabe bei `textChanged`-Signalverbindungen im `PathSelectorWidget`.

## [0.3.0] - 2026-10-22

### Hinzugefügt
- **Neues Qt GUI-Framework (PySide6):**
  - Vollständige Umstellung der Benutzeroberfläche auf modernes PySide6 (Qt 6.12) mit Fluent Dark Design.
  - Hochperformante, virtualisierte Fotogalerie (`QListView` im `IconMode` mit benutzerdefiniertem `GalleryDelegate`).
  - Sortierbare und filterbare Tabellenansicht (`QTableView` mit `ScanFilterProxyModel`).
  - Asynchrone Hintergrund-Generierung von RAW- und Bild-Thumbnails via `QThreadPool` und `QRunnable`.
  - Signal- & Slot-basierte Worker-Threads für unterbrechungsfreies Scannen und Importieren ohne Blockierung der GUI.
  - Durchsuchbarer Import-Historie-Dialog und integrierter Platzhalter-Hilfedialog.
- **Vollständige Linux-Kompatibilität:**
  - Automatische Erkennung eingehängter SD-Karten und Wechseldatenträger unter Linux in `/media`, `/run/media` und `/mnt` sowie `/proc/mounts`.
  - Sicheres Auswerfen von Laufwerken unter Linux via `udisksctl`, `gio mount`, `umount` und `eject`.
  - Startskript `fotodown.sh` für Linux.
- **Core-Modul `core/thumbnail.py`:**
  - Auslagerung der schnellen Miniaturbilderzeugung und Extraktion eingebetteter RAW-JPEGs aus der GUI in den Core.
- **Neues Testmodul `tests/test_qt_and_linux.py`:**
  - 5 neue Unit-Tests für Qt-Modelle, Filterung, Thumbnail-Generierung und Linux-Laufwerkserkennung.

### Geändert
- `requirements.txt` um `PySide6>=6.6.0` ergänzt.
- `fotodown.py` startet standardmäßig die neue Qt-GUI, bietet über `--gui tk` bei Bedarf aber weiterhin Fallback-Zugriff auf die Legacy-GUI.

## [0.2.5] - 2026-09-02
