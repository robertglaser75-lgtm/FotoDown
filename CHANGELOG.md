# Changelog

Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.
Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/) und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

## [0.9.0] - 2026-11-03

### Hinzugefügt
- **Import-Profile & Voreinstellungen (Presets) (`core/config.py`, `gui_qt/widgets/profile_bar.py`):**
  - Schnelles Umschalten zwischen vorkonfigurierten Profilen: *„Standard“*, *„Urlaub & Reise“*, *„Studio & Shooting“* und *„Drohne & Actioncam“*.
  - Jedes Profil sichert Zielordner, Video-Ablage, 2. Backup, Dateinamen-Muster, Ordnerstruktur, RAW+JPG-Organisation und Sicherheitsoptionen.
  - Profile können direkt über die Profil-Leiste gespeichert (`💾`), neu angelegt (`➕`) oder gelöscht (`🗑️`) werden.
- **Eigene einklappbare Sektion für Allgemeine Einstellungen (`gui_qt/widgets/general_settings.py`):**
  - Trennung der Konfiguration in logische Blöcke:
    - *1. Quell- und Zielordner* (Pfade & Speicherplatzbalken)
    - *2. Namens- und Ordnerstruktur-Muster* (Dateinamen, Ordner und Tags)
    - *3. Allgemeine Einstellungen & Optionen* (JPG/RAW-Organisation, RAW+JPG Kopplung, XMP-Sidecars, Hotplug-Erkennung, Duplikatsprüfung, Bit-Integritätsprüfung).
- **Interaktive, intuitive Ein-/Ausklapp-Balken (`gui_qt/widgets/collapsible_box.py`):**
  - Der gesamte Header-Balken ist jetzt klickbar und signalisiert die Interaktivität mit Hand-Cursor (`PointingHandCursor`) und deutlicher Hover-Hervorhebung.
  - Rechter Hand zeigt ein deutlicher Aktions-Button (`[ Einklappen ▲ ]` bzw. `[ Ausklappen ▼ ]`) unmissverständlich an, wo geklickt werden kann.
  - Visuelle Chevron-Icons (`▼` / `▶`) auf der linken Seite.

## [0.8.0] - 2026-11-03

### Hinzugefügt
- **Automatische Speicherkartenerkennung bei Einstecken (Hotplug / Auto-Detect):**
  - **Hintergrund-Laufwerksüberwachung (`DriveMonitor` & `DriveWatcherThread`):** Asynchrone Erkennung neu verbundener oder entfernter Wechsellaufwerke und SD-Karten in Echtzeit.
  - **Hotplug-Benachrichtigungsbanner (`CardNotificationBanner`):** Sobald eine SD-Karte (insb. mit `DCIM`-Kamera-Ordner) eingesteckt wird, erscheint am oberen Bildschirmrand ein dezentes, elegantes Banner mit Laufwerksbuchstaben, Label, freiem Speicherplatz und einem **„🔍 Jetzt Fotos scannen“**-Button.
  - **1-Klick-Scan:** Ein Klick auf das Banner übernimmt direkt den DCIM-Quellpfad und startet den Scanvorgang sofort.
  - **Automatisches Aushängen / Entfernen:** Beim Abziehen der Karte wird das Banner automatisch geschlossen und die Laufwerksauswahl aktualisiert.
  - **Konfigurierbar:** Option in den Einstellungen (`auto_detect_drives`) zum Aktivieren/Deaktivieren der automatischen Erkennung.

## [0.7.0] - 2026-11-03

### Hinzugefügt
- **RAW + JPG Kopplung als logische Einheit (`core/importer.py`, `core/config.py`):**
  - Beim Scannen werden RAW- und JPG-Dateien desselben Motivs (gleicher Stammname im selben Quellordner) automatisch zu einem einzelnen Eintrag (`is_pair=True`) gekoppelt.
  - Einheitliche Umbenennung: Beide Dateien erhalten exakt denselben neuen Namen und dieselbe fortlaufende Nummer.
  - Selektiert der Benutzer das Foto, werden stets RAW und JPG gemeinsam ausgewählt und importiert.
  - Vollständige Unterstützung für getrennte Unter- oder Hauptordner (`.../RAW` und `.../JPG`) bei simultaner Kopplung.
  - Beide Dateien werden in der Historie-Datenbank mit ihren SHA-256 Hashes erfasst, damit künftige Scans Duplikate lückenlos erkennen.
- **XMP-Sidecar-Synchronisation (`.xmp`):**
  - Vorhandene `.xmp`-Metadatendateien (z.B. von Lightroom, Capture One oder Kamera-Bewertungen) werden automatisch erkannt und mitkopiert.
  - Die `.xmp`-Dateien werden exakt synchron zum neuen Zieldateinamen umbenannt.
  - Beim optionalen Löschen von der Quelle nach erfolgreichem Import werden Sidecars erst dann gelöscht, wenn alle Kopiervorgänge und Prüfsummenvalidierungen erfolgreich waren.
- **UI-Integration für RAW+JPG & XMP:**
  - Neue Konfigurations-Checkboxen in der Seitenleiste: *„RAW & JPG als logische Einheit koppeln“* und *„XMP-Sidecars (.xmp) synchron mitführen“*.
  - Galerieansicht zeigt einen visuellen Badge (`RAW+JPG`, `RAW+JPG+XMP`, `+XMP`) auf den Fotokarten.
  - Tabellenansicht zeigt im Typfeld `RAW+JPG` sowie die kombinierte Gesamtdateigröße.
  - Schnellvorschau (`QuickPreviewDialog`) nutzt bei RAW+JPG-Paaren automatisch das Begleit-JPG für sofortigen, gestochen scharfen Bildaufbau.
  - Speicherkapazitätsprüfung berechnet das Gesamtdatenvolumen inklusive Begleitdateien und Sidecars.

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
