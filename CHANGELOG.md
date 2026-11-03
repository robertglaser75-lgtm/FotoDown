# Changelog

Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.
Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/) und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

## [0.6.0] - 2026-11-03

### Hinzugefügt
- **Duales Backup / 2. Sicherungsziel (`core/importer.py`, `gui_qt/widgets/path_selector.py`):**
  - Option zum automatischen simultanen Kopieren auf ein zweites Ziel (z.B. NAS oder externe Backup-Festplatte) direkt während des Imports.
  - Eigener Füllstandsbalken mit Speicherplatzprüfung für das 2. Backup-Ziel.
  - Quelllöschung (sofern aktiviert) erfolgt erst nach erfolgreichem Schreiben und Verifizieren *beider* Ziele.
- **Bit-genaue Integritätsprüfung (SHA-256 Checksum Verification):**
  - Automatischer Vergleich der SHA-256 Prüfsummen nach dem Schreibvorgang zwischen Quell- und Zieldatei (sowie Backup-Datei).
  - Erkennt Übertragungsfehler oder Dateibeschädigungen sofort und schützt vor Datenverlust.

## [0.5.1] - 2026-11-03

### Behoben & Verbessert
- **Sidebar-Layout (Vertikales Form-Design):**
  - Umstellung der Quell- und Zielpfade auf ein vertikales Layout (Label oben, breites Eingabefeld mit Durchsuchen-Button darunter).
  - Beseitigung aller horizontalen Stauchungen und Textüberhänge.
  - JPG/RAW-Organisation als kompaktes, vollwertiges Dropdown-Menü (`QComboBox`) umgesetzt.
- **Speicherplatzbalken (`StorageBarWidget`):**
  - Entzerren von Titel und Speicherdetails (Prozentanzeige rechts oben, Füllstandsbalken und vollständige GB-Details vollflächig darunter).
- **Responsive Filterleiste (`FilterBarWidget`):**
  - Mindestbreite für das Suchfeld garantiert; kein Zusammenschrumpfen mehr auf `...`.
  - Kompakte Beschriftungen und Schaltflächen.
- **Empty-State-Platzhalter (`EmptyStateWidget`):**
  - Anstelle eines leeren schwarzen Tabellenfeldes wird vor dem ersten Scan ein elegantes Platzhalter-Widget mit Hilfetext und Direkt-Scan-Button angezeigt.

## [0.5.0] - 2026-11-03

### Hinzugefügt
- **Quick-Look / Vollbild-Schnellvorschau (`gui_qt/dialogs/quick_preview_dialog.py`):**
  - Schnelle Tastatur- und Mausvorschau für Fotos und RAWs per **Leertaste (Space)** oder **Doppelklick**.
  - Flüssiges Blättern mit den Pfeiltasten (Links/Rechts) und Schließen per Leertaste oder Escape.
  - Direkte Auswahl/Abwahl für den Import über die Taste `S` oder Checkbox direkt im Vorschaufenster.
  - Integrierter EXIF-Inspektor mit Kamera-Name, Aufnahmedatum, Dateigröße und Status.
  - Extrem schnelles Rendern von RAW-Dateien über eingebettete JPEG-Previews.
- **Echtzeit-Durchsatz (MB/s) & verbleibende Restzeit (ETA) beim Import:**
  - Während des Importvorgangs wird kontinuierlich die Übertragungsgeschwindigkeit und die verbleibende Restzeit berechnet und im Statusbalken visualisiert.

### Behoben
- **Kompakte Kopfzeile & Versionsanzeige:**
  - Vertikaler Platzbedarf der Titelleiste (`HeaderBanner`) und des Versionsabzeichens (`#versionBadge`) drastisch reduziert (von ~65px auf schlanke 42px).
  - Saubere vertikale Zentrierung von Logo, App-Titel, Versions-Badge und Aktions-Buttons.

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
