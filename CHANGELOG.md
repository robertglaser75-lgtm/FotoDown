# Changelog

Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.
Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/) und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

## [0.12.2] - 2026-11-03

### Behoben
- **Vorschau beim Auswerfen leeren (`gui_qt/widgets/header_banner.py`, `gui_qt/main_window.py`):**
  - Beim Klick auf „⏏ Auswerfen“ oder beim automatischen Entfernen eines Laufwerks werden alle geladenen Bilder und Vorschaudaten vollständig aus dem Arbeitsbereich entfernt:
    - Tabellenmodell, Galerieansicht und Einzelbildansicht werden geleert.
    - Die Zielordner-Vorschau (Ziel-Baum) wird zurückgesetzt.
    - Miniaturbild-Cache wird bereinigt und freigegeben.
    - EXIF-Inspektor wird geschlossen/zurückgesetzt.
    - Status- und Statistikleiste sowie Quellpfad werden auf den Ausgangszustand („Bereit“) zurückgesetzt.
    - Der Arbeitsbereich wechselt zurück auf die Willkommens- und Leeransicht („Noch keine Fotos eingelesen“).

## [0.12.1] - 2026-11-03

### Hinzugefügt
- **Umfassende Installationsanleitung & 1-Klick-Installer (`INSTALL.md`, `install_windows.bat`, `install_linux.sh`):**
  - **Detaillierte Installationsanleitung ([`INSTALL.md`](INSTALL.md)):** Strukturierte Anleitungen für Windows 10/11 und alle Linux-Systeme.
  - **Spezifischer Support für alle Arch Linux Varianten:** Arch Linux, Manjaro, EndeavourOS, Garuda Linux, ArcoLinux, CachyOS etc. inklusive Pacman-Direktinstallation (`python-pyside6`, `python-pillow`), PEP-668-konformer venv-Einrichtung, Wayland/X11-Support (`qt6-wayland`) und Speicherkarten-Berechtigungen (`udisks2`).
  - **1-Klick-Assistent für Linux (`install_linux.sh`):** Automatische Erkennung der Distribution, Einrichtung von `.venv`, Installation der Abhängigkeiten und Erstellung eines `.desktop`-Starters mit Icon für das Anwendungsmenü (KDE Plasma, GNOME, etc.).
  - **1-Klick-Assistent für Windows (`install_windows.bat`):** Automatische `.venv`-Erstellung, Paketinstallation und Anlegen einer Desktop-Verknüpfung mit Kamera-Icon.
  - **Starter-Optimierung (`FotoDown.bat`, `fotodown.sh`):** Erkennt und verwendet automatisch `.venv`, sofern vorhanden.

## [0.12.0] - 2026-11-03

### Hinzugefügt
- **Bereichsauswahl mit STRG / Shift (`gui_qt/views/gallery_view.py`, `gui_qt/views/table_view.py`, `gui_qt/main_window.py`):**
  - **Bereichsauswahl (Range Selection) in Galerie- und Tabellenansicht:** Durch Klicken auf ein erstes Bild und anschließendes Klicken auf ein zweites Bild bei gedrückter <kbd>STRG</kbd>- (oder <kbd>Umschalt</kbd>-)Taste werden automatisch alle dazwischen liegenden Fotos für den Import ausgewählt (`selected = True`).
  - Visuelle Aktualisierung aller Kärtchen (Checkboxen & Umrandung) und synchrone Neuberechnung der Statistik-Leiste (Anzahl und Gesamtgröße).
  - Synchronisation mit Qts `QItemSelectionModel`, sodass auch die Fokus- und Tastaturmarkierung für den gesamten Bereich gesetzt wird.
  - Shortcut <kbd>S</kbd> in der Tabellenansicht zum Umschalten aller markierten Zeilen ergänzt.

## [0.11.1] - 2026-11-03

### Behoben
- **Absturz beim Umschalten auf die Galerie-Ansicht behoben (`gui_qt/workers/thumb_worker.py`, `gui_qt/main_window.py`, `gui_qt/views/delegates.py`):**
  - **Thread-sichere Signal-Architektur:** Beseitigung eines kritischen Race-Conditions-/Dangling-Pointer-Absturzes in Qt/PySide6. Bisher wurde in `ThumbnailTask` (einem `QRunnable` mit `autoDelete=True`) ein ephemeres `ThumbnailSignals`-Objekt ohne festen Qt-Parent erstellt, das nach Beendigung des Worker-Threads in C++ zerstört wurde, während die Signal-Events noch in der Qt-Ereignisschleife des Hauptthreads verarbeitet wurden.
  - `MainWindow` verwaltet nun eine langlebige, threadsichere Instanz `thumb_signals`, die direkt und ohne fehleranfällige Lambda-Closures mit dem Galerie-Delegate kommuniziert.
  - **Sichere QImage-Konvertierung:** Thumbnails werden nun über einen In-Memory-PNG-Bytestrom via `QImage.loadFromData()` instanziiert, wodurch Puffer-Lebenszeitprobleme und Zugriffsverletzungen (Access Violation) bei asynchronen Threadpool-Ladevorgängen vollständig ausgeschlossen werden.
  - **Robuste Delegaten-Absicherung:** `GalleryDelegate.paint()` validiert `index.isValid()` und stellt sicher, dass nur skalierte Pixmaps mit positiven Dimensionen gezeichnet werden.

## [0.11.0] - 2026-11-03

### Hinzugefügt
- **Integrierte Einzelansicht (`gui_qt/views/single_view.py`, `gui_qt/widgets/filter_bar.py`, `gui_qt/main_window.py`):**
  - Neuer Ansichtsmodus *„🔍 Einzelansicht“* im Hauptarbeitsbereich.
  - Ermöglicht das Betrachten von Fotos in voller Pracht direkt im Hauptfenster mit bequemer Tastaturnavigation (`◀` / `▶` bzw. `A` / `D`), Bildzähler und Titelleiste.
  - Umschaltung per Klick oder Tastenkombination (`F` / Doppelklick) zwischen *„Einpassen“* (skaliert an Anzeigefläche) und *„100% Originalgröße“* (1:1 Pixeldarstellung mit Scrollbereich zur Schärfe- und Fokusbeurteilung).
  - Direkte Auswahl-Checkbox (`Für Import ausgewählt [S]`) sowie Schnell-Absprung in den Vollbild-Vorschaudialog (`Leertaste`).
  - Detaillierte Metadaten-Leiste am unteren Rand (Kameramodell, Objektiv, Belichtungswerte, Megapixel, Dateigröße, Datum).

### Behoben
- **Kristallklare Bilddarstellung & Schärfe-Optimierung (`core/thumbnail.py`, `gui_qt/workers/thumb_worker.py`, `gui_qt/views/delegates.py`, `gui_qt/dialogs/quick_preview_dialog.py`):**
  - **Erhöhte Thumbnail-Auflösung:** Vorschaubilder in der Galerie werden nun nativ in 480x480 Pixeln mit `Image.Resampling.LANCZOS` generiert (zuvor 160x160), wodurch Fotos auch bei hoher Zoomstufe und auf Windows-HiDPI-Displays gestochen scharf dargestellt werden.
  - **Glattes Rendering aktiviert:** `QPainter.RenderHint.SmoothPixmapTransform` in `GalleryDelegate` hinzugefügt, um Unschärfen und Moiré-Artefakte beim Zeichnen von Miniaturbildern zu verhindern.
  - **Verbesserte RAW-Vorschauextraktion:**
    - Behebung eines Problems, bei dem für RAW-Dateien fälschlicherweise das winzige 160x120-IFD0-Thumbnail verwendet wurde.
    - `extract_raw_embedded_jpeg` prüft nun vorrangig vorhandene Begleit-JPGs und durchsucht den RAW-Datenstrom (bis 24 MB) nach den hochauflösenden eingebetteten JPEG-Vorschaubildern der Kamera.
    - Sortierung aller gefundenen Bildkandidaten nach maximaler Auflösung (`width * height`), sodass stets die schärfste Vorschau gewählt wird.
  - **Zentrale Vorschau-Ladefunktion (`load_preview_image`):** Lädt Vorschauen für Einzelansicht und Quick Look in bis zu 2560px Auflösung mit automatischer EXIF-Ausrichtung.

## [0.10.5] - 2026-11-03

### Behoben
- **Profil-Persistenz & Muster-Synchronisation (`core/config.py`, `gui_qt/main_window.py`, `gui_qt/widgets/pattern_editor.py`, `gui_qt/widgets/path_selector.py`, `gui_qt/widgets/general_settings.py`):**
  - **Namens- und Ordnerstruktur-Muster werden zuverlässig im Profil gespeichert:**
    - Beim Wechseln oder Speichern von Profilen wurden zuvor Signale während des Ladens (`load_config`) ausgelöst, die noch unvollständige Formulareingaben zurück in die Konfiguration spiegelten und Muster mit leeren Strings überschreiben konnten.
    - `load_config` blockiert nun in allen Einstellungs-Widgets (`PatternEditorWidget`, `PathSelectorWidget`, `GeneralSettingsWidget`) vorübergehend die Signale, und `MainWindow` verhindert mit einem Lade-Guard (`_is_loading_config`) vorzeitiges oder zirkuläres Zurückschreiben in die Konfiguration während Profilwechseln.
    - Muster-Felder fallen bei leeren Eingaben automatisch auf gültige Standardmuster zurück (`{YYYY}/{YYYY}-{MM}-{DD}` bzw. `{YYYY}-{MM}-{DD}_{hh}-{mm}-{ss}_{camera}_{orig_name}`), sodass niemals ungültige oder leere Muster in Profilen gespeichert werden.
    - **Automatische Profil-Migration:** Bestehende Konfigurationen aus älteren Versionen werden beim Laden automatisch mit allen Profil-Schlüsseln (inklusive IPTC, Dual-Backup und Muster) abgeglichen und nachgepflegt.
    - Änderungen an Mustern oder allgemeinen Einstellungen im UI werden sofort im aktuell aktiven Profil hinterlegt und gesichert.

## [0.10.4] - 2026-11-03

### Behoben
- **Sidebar-Layout & Proportionen (`gui_qt/main_window.py`, `gui_qt/widgets/path_selector.py`, `gui_qt/widgets/pattern_editor.py`, `gui_qt/widgets/collapsible_box.py`):**
  - **Architektur der Seitenleiste optimiert:** Aufteilung in einen feststehenden Kopfbereich (Profil-Auswahl), einen flexiblen scrollbaren Mittelteil für die einklappbaren Konfigurationsblöcke (`QScrollArea` mit vertikalem Scrollbalken bei Bedarf) und eine fest am unteren Rand verankerte Aktionsleiste (`[Scannen]`, `[Importieren]`, Speicherwarnungen und Fortschrittsbalken). Dadurch sind die Hauptaktionen stets direkt erreichbar und werden nie verdeckt oder nach unten weggescrollt.
  - **Größen- und Abschneideprobleme behoben:**
    - `PatternEditorWidget`: Platzhalter-Chips wurden von einer 10-Elemente-Horizontalzeile (die über 640px Mindestbreite erzwang) in ein kompaktes 2-Zeilen-Raster (2x5) umorganisiert.
    - `PathSelectorWidget`: Text der 2. Backup-Checkbox gekürzt auf `🛡️ Gleichzeitig 2. Backup erstellen (NAS/Festplatte)` mit erklärendem Tooltip.
    - `CollapsibleBox`: Feste Layout-Größenbeschränkung (`SetMinimumSize`) verhindert, dass eingeklappte oder ausgeklappte Boxen auf wenige Pixel zusammengestaucht werden.
  - Die Mindestbreite und Initialaufteilung des Hauptsplitters (`420px / 860px`) sorgt dafür, dass alle Schaltflächen (`Durchsuchen`, `Einklappen`, `Ausklappen`, Profil-Buttons) und Labels vollständig ohne Abschneiden lesbar sind.

## [0.10.3] - 2026-11-03

### Behoben
- **Galerie-Ansicht Rendering (`gui_qt/views/delegates.py`):**
  - Behebung eines `AttributeError` in `GalleryDelegate.paint()`, bei dem `option.State_MouseOver` fälschlicherweise auf `QStyleOptionViewItem` statt auf `QStyle.StateFlag.State_MouseOver` referenziert wurde.
  - Dieser Laufzeitfehler führte dazu, dass Qt den Zeichenvorgang für jedes Galeriekärtchen abbrach und die Galerieansicht beim Umschalten vollständig leer blieb.
  - Unit-Test zur Absicherung des Rendering-Vorgangs der `MediaGalleryView` hinzugefügt.

## [0.10.2] - 2026-11-03

### Behoben
- **Layout-Aufteilung im rechten Arbeitsbereich (`gui_qt/main_window.py`, `gui_qt/widgets/filter_bar.py`):**
  - Korrektur der vertikalen Größenverteilung im Medien-Arbeitsbereich: Die Filterleiste war unbeabsichtigt vertikal auf ~380px expandiert und hatte den gesamten Ansichtsbereich mit Tabelle/Galerie/Baum bzw. den Leeren Zustand nach unten gedrückt.
  - `FilterBarWidget` erhält jetzt eine feste vertikale Größenpolitik (`QSizePolicy.Fixed`), und `workspace_splitter` erhält den vollen vertikalen Dehnungsfaktor (`stretch=1`).
  - Die Filterleiste sitzt nun wieder schlank und bündig oben (Höhe ~36px), während die Inhaltsansichten den gesamten verbleibenden vertikalen Raum einnehmen.

## [0.10.1] - 2026-11-03

### Behoben
- **Profil-Aktionsbuttons in der Profilleiste (`gui_qt/widgets/profile_bar.py`, `gui_qt/styles/dark_fluent.qss`):**
  - Behebung eines Darstellungsfehlers, durch den das Standard-Button-Padding (`padding: 6px 14px`) den Inhalt von kompakten 28x28-Buttons komplett abgeschnitten hatte und alle drei Buttons als leere graue Quadrate erschienen.
  - Spezifische Objekt-IDs (`profileBtnSave`, `profileBtnNew`, `profileBtnDelete`) mit `padding: 0px` und zentrierter Glyph-Darstellung (`Segoe UI Emoji` / `Segoe UI Symbol`).
  - Semantische Farbkodierung zur klaren visuellen Unterscheidung:
    - *Speichern* (`💾`): Blauer Akzentrahmen (`#0369a1`) und Icon-Farbe (`#38bdf8`) mit blauem Hover-Effekt.
    - *Neu anlegen* (`➕`): Grüner Akzentrahmen (`#047857`) und Icon-Farbe (`#34d399`) mit smaragdgrünem Hover-Effekt.
    - *Löschen* (`🗑️`): Roter Akzentrahmen (`#991b1b`) und Icon-Farbe (`#f87171`) mit rotem Danger-Hover-Effekt.
  - Eindeutige, informative Tooltips für jede Aktion.

## [0.10.0] - 2026-11-03

### Hinzugefügt
- **Interaktive Zielstruktur-Baumvorschau (`gui_qt/views/tree_view.py`):**
  - Neuer Ansichtsmodus *„📁 Ordnerstruktur“* in der Ansichts-Umschaltung der Filterleiste.
  - Hierarchische Baumdarstellung (`QTreeView`) aller geplanten Zielverzeichnisse und Dateien vor dem Kopiervorgang.
  - Zeigt exakte Ordnerhierarchien, Dateigrößen-Badges, RAW+JPG-Paar-Zuordnung und Status pro Datei an.
  - Doppelklick öffnet direkt die Großbild-Vorschau; Auswahl synchronisiert mit dem EXIF-Inspektor.
  - Komfort-Schaltflächen für *„➕ Alle ausklappen“* und *„➖ Alle einklappen“*.
- **IPTC- & Copyright-Metadaten-Injektion beim Import (`core/metadata_writer.py`, `core/config.py`, `core/importer.py`):**
  - Automatische Injektion von Urheberdaten (Fotografenname, Copyright-Hinweis mit `{year}` / `{creator}` Platzhaltern und Schlagwörtern / Keywords) während des Kopiervorgangs.
  - Erstellung und Anreicherung von Adobe-kompatiblen standardisierten XMP/Dublin-Core-Sidecars (`.xmp`) für Bilder und RAW-Dateien.
  - Konfigurierbar in den Allgemeinen Einstellungen sowie in Import-Profilen sicherbar.
- **Integrierter EXIF-Detail-Inspector als ausklappbares Seiten-Panel (`gui_qt/widgets/exif_inspector.py`):**
  - Schnelles Ein- und Ausblenden über die Filterleiste (`ℹ️ EXIF`).
  - Umfassende Anzeige aller technischen Aufnahmedaten (Kamera, Objektiv, Belichtungs-Chip `ƒ/2.8 | 1/500s | ISO 200 | 50mm`, Auflösung in Megapixeln, Dateigröße).
  - Integriertes, antialiastes RGB- und Luminanz-Histogramm (`HistogramWidget`).
  - GPS-Koordinaten-Anzeige mit Direkt-Button *„In OpenStreetMap öffnen ↗“*.
- **Automatische Foto-Rotation nach EXIF-Orientierung:**
  - Konsequente Anwendung von `ImageOps.exif_transpose` in allen Vorschaukomponenten (Gallery, Quick Preview, EXIF Inspector), sodass Hochformat- und gedrehte Fotos stets aufrecht dargestellt werden.
- **Vorbereitung für v1.0.0:**
  - Alle Kernfunktionen vollständig implementiert und mit 44 Unit-Tests abgesichert.

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
