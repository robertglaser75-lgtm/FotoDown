# FotoDown 📸

**FotoDown** ist ein intelligentes, schnelles Werkzeug zum automatischen Importieren, Umbenennen und Sortieren von Fotos und Videos direkt von Speicherkarten (SD-Karten, USB-Laufwerken) oder beliebigen Quellordnern.

Lauffähig unter **Windows** und **Linux**.

---

## ✨ Funktionen

- 💾 **3. Hauptfunktion: Sichern & Archivieren (NAS- & Speicher-Transfer):**
  - **Drei-Phasen-Workflow:** Bequemes Umschalten zwischen *„📥 1. Importieren“*, *„👁️ 2. Sichten & Sortieren“* und *„💾 3. Sichern & Archivieren“*.
  - **2-geteilte Benutzeroberfläche (Dual-Pane, Laptop-optimiert):**
    - **Identische Verzeichnisauswahl wie im Sichten-Tab:** Sowohl Quelle als auch Ziel verfügen über denselben interaktiven Verzeichnisbaum (`CullingDirectoryTreeWidget`) mit optional ein-/ausschaltbaren Bildzähler-Spalten (`Bilder`, `RAW`, `JPG`), Einstiegspunkt-Wahl und Klappfunktionen.
    - **Links (Quelle / PC / Laptop):** Verzeichnisbaum (`CullingDirectoryTreeWidget`) auf der linken Seite; rechts daneben die Quellbilder mit Filtern für Dateitypen (RAW, JPG, RAW+JPG, Videos, Bearbeitungen mit XMP) und Textsuchfeld.
    - **Rechts (Ziel / Speicher / NAS / Album):** Verzeichnisbaum auf der linken Seite der Sicherungshälfte; rechts daneben die Zielbilder mit identischen Filter- und Darstellungsoptionen.
    - **Mitte (Aktionsspalte):** Kompakte Richtungspfeil-Aktionen mit Vektor-Icons für *„Kopieren“*, *„Verschieben“*, *„Alle kopieren“*, *„Alle versch.“* und *„Tauschen“*.
  - **Flexible Anzeige, Sortierung & Markierungswerkzeuge:**
    - Ein- und ausschaltbare **Dateianzeige** (*„Dateien“*) sowie ein-/ausklappbarer Verzeichnisbaum (*„Baum“*) auf beiden Seiten.
    - Frei wählbare **Sortierreihenfolge** für Dateien (*Name*, *Datum*, *Größe*, *Dateityp*, *Bewertung*) sowie Auf-/Absteigend-Umschaltung – synchron für Listen- und Kachelansicht (inkl. Spaltenklick in der Tabelle) sowie Auf-/Absteigend-Sortierung im Verzeichnisbaum.
    - **Anzeigearten über kompakte Dropdown-Liste konfigurierbar:** Einfacher Wechsel zwischen *Liste* und *Vorschau: Klein (80px) / Mittel (140px) / Groß (200px)* ohne überladene Button-Leisten.
    - Platzsparende Icon-Werkzeuge für *Alle markieren*, *Keine*, *Invertieren* sowie Checkboxen mit Live-Zähler.
    - 🏷️ **Batch-Umbenennung auf beiden Seiten:** Markierte Dateien direkt in Quelle oder Ziel nach konfigurierbarem Namensmuster mit EXIF-Platzhaltern, Live-Vorschautabelle, Begleitdatei-Synchronisation und Kollisionsschutz umbenennen.
  - **Begleitdatei-Integrität & Sicherheit:**
    - Überträgt automatisch alle zugehörigen `.xmp`-Sidecars mit.
    - Sicheres Verschieben: Quelldateien werden erst nach verifizierter erfolgreicher Übertragung am Ziel gelöscht.
- 👁️ **2. Hauptfunktion: Sichten & Sortieren (Culling & Editor-Export):**
  - **Drei-Phasen-Workflow:** Bequemes Umschalten zwischen *„📥 1. Importieren“*, *„👁️ 2. Sichten & Sortieren“* und *„💾 3. Sichern & Archivieren“*.
  - **Interaktiver Verzeichnisbaum mit Bildzählern:**
    - Eigener Navigationsbaum mit flexibel wählbarem Einstiegspunkt (Root-Ordner).
    - Zeigt für jedes Verzeichnis übersichtlich getrennt: Gesamtzahl an Bildern (`Bilder`), Anzahl an Sensordaten (`RAW`) und Kompaktdateien (`JPEG`).
    - Schnelles Umschalten zwischen Aufnahme-Sessions und Ordnern per Klick oder Tastenkürzel (`V` zum Ein-/Ausblenden).
  - **Ultrawide-optimierte 3-Spalten-Workstation:** Maximale Bildhöhe für Fotos auf 21:9 und 32:9 Monitoren durch vertikale Bedienelemente links und einklappbaren Filmstreifen (`T`).
  - **Schneller Bildbetrachter:** Blitzschnelles Durchsehen mit Tastaturnavigation (`◀` / `▶` bzw. `A` / `D`), stufenlosem Zoom und 100%-Schärfelupe (`F`).
  - **RAW+JPEG Koppelung:** Anzeige als ein Paar mit sofortiger Umschaltung zwischen JPEG-Kameraansicht und RAW-Vorschau (`J` / `R`).
  - **XMP-Sterne- & Farbbewertung:** Vergabe von 1–5 Sternen (`1`–`5`), Pick (`P`) und Reject (`X`), die sofort in `.xmp`-Sidecars synchronisiert werden (voll kompatibel mit Darktable und Lightroom).
  - **Direkte Editor-Übergabe:**
    - 🎨 **Darktable (`Strg+D`):** Übergabe der ausgewählten Aufnahmen **ausschließlich als RAW-Dateien**.
    - ✨ **Topaz Photo (`Strg+T`):** Übergabe der ausgewählten Aufnahmen **ausschließlich als JPEG-Dateien**.
  - **Workflow-Status & Bearbeitungsverfolgung ([Q], [B], [E]):**
    - Klare Klassifizierung jedes Fotos: *📸 SOOC ok [Q]* (Kamera-Qualität passt), *🎨 Zu bearbeiten [B]* (Nachbearbeitung nötig) oder *✔ Bearbeitung fertig [E]*.
    - Automatische Erkennung bestehender Darktable-Bearbeitungen via XMP-Sidecar-Historie (`darktable:history_end`).
    - Automatische Erkennung bereits ins Familienalbum exportierter Bilder (`0001_Unsere_Fotos/{YYYY}/{MM}`).
    - Dauerhafte, standardkonforme Speicherung in `.xmp`-Sidecars (`fotodown:WorkflowStatus`).
  - **Umfassender Filter-Tab im linken Dock:**
    - Schnelle Filterung nach Workflow-Stand (z.B. nur noch „Zu bearbeiten“ anzeigen).
    - Filter nach Dateityp (RAW / JPEG), Bewertung (Sterne, Pick, Reject, Farblabels), Kamera, Objektiv, ISO-Bereich und Volltextsuche.
  - **Konfigurierbares Reject-Handling:** Aussortierte Bilder wahlweise in `_Abgelehnt/` verschieben, löschen oder nur kennzeichnen.
- 🎨 **Modernes Zwei-Farbschema (Dark Fluent & Light Fluent) & Vektor-Icons:**
  - **100% Durchgängige Vektor-Icons:** Vollständiger Verzicht auf instabile Plattform-Emojis. Alle Buttons, Tabs und Werkzeuge nutzen scharfe, skalierbare QPainter-Vektor-Icons (plattformstabil für Windows & Linux ohne fehlende Glyphen).
  - **Umschaltbares Farbschema:** Wahl zwischen *Dunkel (Fluent Dark)*, *Hell (Fluent Light)* und *Automatisch (System)*.
  - **Optimaler Kontrast:** Dunkler Modus mit schonendem Hintergrund für Farbkorrekturen; heller Modus mit hohem WCAG AAA-Kontrast (dunkle Schrift `#0f172a` auf hellen Flächen `#ffffff` / `#f8fafc`).
  - **Dauerhafte Speicherung:** Das gewählte Farbschema wird dauerhaft gespeichert und beim nächsten Start automatisch wiederhergestellt.
- ⚙️ **Zentrales Konfigurationsmenü & Zahnrad-Symbol rechts oben:**
  - Schnellzugriff per Zahnrad-Button `[ ⚙️ ]` in der oberen Leiste mit Dropdown-Menü.
  - Vollständiger Einstellungsdialog (`SettingsDialog`) mit Reitern für *Einzelansicht*, *Import & Organisation*, *NAS & Familienalbum*, *Externe Editoren* und *IPTC*.
  - **Granular anpassbare Einzelansicht:** Frei konfigurierbar, welche Informationen eingeblendet werden (Name des Bildes, Dateiendung, Sterne & Bewertungen, Speicherort/Pfad, Kamera & Objektiv, Belichtung, Aufnahmedatum, Dateigröße).
  - **Frei konfigurierbares Weiterschalten / Tastaturnavigation:** Auswahl zwischen *Nur Pfeiltasten*, *Pfeiltasten & A/D (Standard)*, *Pfeiltasten alle Richtungen*, *Nur A/D*, *Bild auf/ab* oder *Mausrad*. Schnellumschaltung direkt im Zahnrad-Menü oder in den Einstellungen.
- 🔍 **Integrierte Einzelansicht & Schärfebeurteilung:**
  - Neuer Ansichtsmodus *„🔍 Einzelansicht“* im Hauptarbeitsbereich.
  - Großformatige, gestochen scharfe Bildbetrachtung direkt im Anwendungsfenster (bis 2560px).
  - Schnelle Tastaturnavigation mit Pfeiltasten / `A` / `D`, Auswahl-Checkbox (`[S]`) und Bildzähler.
  - Schnelles Umschalten zwischen *Einpassen* und *100% Originalgröße* (`F` oder Doppelklick) zum exakten Prüfen von Fokus, Bildschärfe und Bilddetails.
- 📁 **Interaktive Zielstruktur-Baumvorschau:**
  - Zusätzlicher Ansichtsmodus *„📁 Ordnerstruktur“* neben Tabelle und Galerie.
  - Zeigt exakt vorab, welche Verzeichnisse und Unterordner auf der Zielfestplatte erstellt und wie viele Dateien pro Ordner abgelegt werden.
  - Aufklappbare Ordneräste, Größen-Badges und direkte Großbildvorschau per Doppelklick.
- ℹ️ **Integrierter EXIF-Detail-Inspector mit RGB-Histogramm & GPS:**
  - Seiten-Panel zur detaillierten Analyse des selektierten Mediums (`ℹ️ EXIF`).
  - Zeigt Kameramodell, Objektiv, Belichtungs-Chip (`ƒ/2.8 | 1/500s | ISO 200 | 50mm`), Megapixel und Status.
  - Live-berechnetes Antialiasing-Histogramm (RGB-Farbkanäle und Luminanz).
  - EXIF-Geodaten mit direktem Aufruf in OpenStreetMap (`📍 In OpenStreetMap öffnen ↗`).
- ✍️ **Automatische IPTC- & Copyright-Injektion beim Import:**
  - Schreibt Fotografenname, Copyright-Vermerk (`© {year} {creator}`) und Schlagwörter direkt beim Import in standardisierte `.xmp`-Sidecars.
- 🔄 **Automatische Foto-Rotation nach EXIF-Orientierung:**
  - Automatische Drehung (`ImageOps.exif_transpose`) in allen Ansichten – Fotos im Hochformat bleiben stets korrekt ausgerichtet.
- 📋 **Import-Profile & Voreinstellungen (Presets):**
  - Schnelles Umschalten zwischen Workflows (z.B. *Standard*, *Urlaub & Reise*, *Studio & Shooting*, *Drohne & Actioncam*).
  - Speichern eigener Profile mit benutzerdefinierten Pfaden, Ordnerstrukturen und Namensmustern.
- 📂 **Übersichtliche, interaktive Ein-/Ausklapp-Sektionen:**
  - *1. Quell- und Zielordner* (inkl. Speicherplatz-Füllstandsbalken)
  - *2. Namens- und Ordnerstruktur-Muster*
  - *3. Allgemeine Einstellungen & Optionen* (eigens ein- und ausklappbar)
  - Klar ersichtliche Klickziele mit Hover-Effekt, Zeiger-Cursor und deutlichem `[ Einklappen ▲ ]` / `[ Ausklappen ▼ ]`-Button.
- ⚡ **Automatische Speicherkartenerkennung bei Einstecken (Hotplug / Auto-Detect):**
  - Erkennt eingesteckte SD-Karten sofort im Hintergrund ohne manuelles Neuladen.
  - Zeigt ein dezentes Benachrichtigungsbanner mit Kamera-Label, Speicherplatz und einem **„🔍 Jetzt Fotos scannen“**-Button für einen nahtlosen 1-Klick-Workflow.
  - Entfernte Speicherkarten werden sauber ausgeblendet.
- 🔗 **RAW + JPG Kopplung als Einheit:**
  - Erkennt zusammengehörige RAW- und JPG-Aufnahmen desselben Motivs automatisch und behandelt sie als logische Einheit.
  - Gewährleistet exakt dieselbe Umbenennung und Nummerierung für beide Dateien, auch bei getrennter Ordnerablage (`.../RAW` und `.../JPG`).
  - Gemeinsame Auswahl, Vorschau und Duplikatserkennung.
- 📄 **XMP-Sidecar-Synchronisation:**
  - Automatische Mitführung und Umbenennung von `.xmp`-Metadatendateien (z.B. aus Kameras oder Raw-Entwicklern).
  - Sicheres Löschen von der Quellkarte erst nach erfolgreichem Kopieren aller zugehörigen Sidecars.
- 🛡️ **Duales Backup & Bit-genaue Verifikation:**
  - Gleichzeitiges Kopieren auf zwei Ziele (z.B. Arbeits-SSD und NAS-Archiv).
  - SHA-256 Checksum-Prüfung nach dem Schreiben garantiert 100%ige Datenintegrität.
- 💾 **Dual-Pane Sicherung & Archivierung (Tab 3):**
  - Direkter Transfer zwischen lokaler Arbeitsstation (PC/Laptop) und Langzeitspeicher (NAS / Familienalbum).
  - Parallele Verzeichnisbäume links (Quelle) und rechts (Ziel) mit vollständiger Pfadanzeige beim Einstiegspunkt.
  - Intelligenter, konfigurierbarer **Dateiabgleich**: Prüft und markiert automatisch fehlende JPGs, RAWs oder beide Dateitypen wahlweise über **Dateinamen**, **EXIF-Aufnahmezeit** (findet auch umbenannte Fotos) oder **SHA-256 Prüfsumme**.
  - Integrierte XMP-Sidecar-Mitführung, Sortierung und flexible Listen-/Kachel-Vorschau.
- 🚀 **Professioneller Fluent Dark Splashscreen:** Schneller, visuell ansprechender Start mit asynchroner Status- und Ladeanzeige.
- 🔍 **Quick-Look & Vollbildmodus:** Echtes Umschalten in den Vollbildmodus per **F11** sowie sofortige hochauflösende Schnellvorschau per **Leertaste** oder Doppelklick inklusive RAW-Unterstützung, Pfeiltasten-Navigation und EXIF-Inspektor.
- ⚡ **Echtzeit-Performance & Restzeit (ETA):** Live-Anzeige der Kopiergeschwindigkeit (MB/s) und der verbleibenden Restzeit während des Imports.
- 💾 **Echtzeit-Speicherplatz-Visualisierung & Pre-Flight Check:**
  - Übersichtliche Anzeige der Belegung und des freien Speichers für SD-Karten und Ziellaufwerke (Festplatten, NAS, Netzlaufwerke).
  - Automatische Vorab-Prüfung vor dem Kopieren: Warnt sofort bei Speichermangel und verhindert unvollständige Kopiervorgänge.
- 🔍 **Automatische Speicherkartenerkennung:** Erkennt eingesteckte SD-Karten und findet automatisch typische `DCIM`-Ordner (unter Windows via Win32-API, unter Linux via `/media`, `/run/media` und `/proc/mounts`).
- ⏏️ **Sicheres Auswerfen:** Ermöglicht das direkte und sichere Aushängen von Speicherkarten per Mausklick.
- 🧠 **Duplikaterkennung via Historie:** Merkt sich heruntergeladene Fotos (via SHA-256-Hash in einer SQLite-Datenbank). Speicherkarte erneut einstecken? Es werden **nur neue Fotos** geladen!
- 🏷️ **Flexible EXIF-Umbenennung:** Frei definierbare Muster mit Direkt-Vorschau und klickbaren Platzhalter-Chips.
- 📁 **Strukturierte Ordnerablage:** Automatische Sortierung in Zielordner (z.B. nach Jahr/Monat/Tag/Kamera).
- 🎥 **Eigener Ordner für Videos:** Option zur automatischen Trennung von Video-Dateien in einen separaten Zielordner.
- 🎞️ **JPG- & RAW-Organisation:** Wählbar zwischen:
  - *Alle Fotos gemeinsam in einem Ordner*
  - *Getrennte Unterordner für JPG und RAW (z.B. .../JPG/ und .../RAW/)*
  - *Getrennte Hauptordner für JPG und RAW (z.B. JPG/... und RAW/...)*
- 📷 **Umfassende Format-Unterstützung:**
  - Standardformate: `.jpg`, `.jpeg`, `.png`, `.heic`, `.heif`, `.tiff`
  - RAW-Formate: Canon (`.cr2`, `.cr3`), Nikon (`.nef`), Sony (`.arw`), Adobe (`.dng`), Panasonic (`.rw2`), Olympus (`.orf`), Fuji (`.raf`), Pentax (`.pef`)
  - Videoformate: `.mp4`, `.mov`, `.mts`, `.m2ts`, `.avi`, `.mkv`
- 🖥️ **Moderne 2-Spalten-Benutzeroberfläche (PySide6 / Qt 6):**
  - Sidebar-Layout links: Voreinstellungen, Pfade, Muster und Optionen; maximaler Raum für Fotobetrachtung rechts.
  - Stufenloser **Zoom-Slider** für Miniaturbilder in der Fotogalerie (`QListView` im `IconMode`).
  - Sortier- und filterbare Tabellenansicht (`QTableView` mit `ScanFilterProxyModel`).
  - Fluent Dark Design optimiert für Windows 11 und moderne Linux-Desktops (GNOME, KDE Plasma).
- ⚙️ **Kommandozeilen-Modus (CLI):** Voller CLI-Support für Scripting, Hintergrundjobs und Headless-Server.
- 🛡️ **Kollisionssicher:** Vorhandene Zieldateien werden bei Bedarf automatisch nummeriert (`_1`, `_2`), um Überschreiben zu verhindern.

---

## 🚀 Installation & Schnellstart

> Ausführliche Anleitungen und Troubleshooting für Windows und alle Linux-Systeme finden Sie in der **[INSTALL.md](INSTALL.md)**.

### 1. Unter Windows (10 / 11):
- **1-Klick-Installation:** Führen Sie einfach die Datei **`install_windows.bat`** per Doppelklick aus.
  - Richtet eine isolierte Umgebung ein, installiert alle Abhängigkeiten und erstellt ein Desktop-Icon.
- **Starten:** Danach einfach per Doppelklick auf die Desktop-Verknüpfung **`FotoDown`** oder **`FotoDown.bat`**.

### 2. Unter Linux (Arch Linux, Manjaro, EndeavourOS, Ubuntu, Fedora etc.):
- **1-Klick-Installation:**
  ```bash
  chmod +x install_linux.sh
  ./install_linux.sh
  ```
  - Installiert alle Abhängigkeiten, richtet `.venv` ein und integriert FotoDown in Ihr **Anwendungsmenü** (KDE, GNOME, etc.).
- **Nativ auf Arch Linux via Pacman (ohne venv):**
  ```bash
  sudo pacman -S --needed python python-pyside6 python-pillow qt6-base qt6-wayland
  ./fotodown.sh
  ```
- **Starten:** Über das Anwendungsmenü oder im Terminal via **`./fotodown.sh`**.
```

---

## ⌨️ Tastatur-Shortcuts

| Taste | Aktion |
| :--- | :--- |
| **Doppelklick (Linke Maustaste)** | Öffnet eine gestochen scharfe **Vollbildvorschau** in einem eigenen neuen Fenster |
| **Leertaste** | Öffnet die hochauflösende Schnellvorschau (Quick Look) |
| **F11 / Doppelklick im Vollbild** | Vollbildmodus umschalten / verlassen |
| **Pfeiltasten Links / Rechts (A / D)** | Im Vorschaumodus zum vorherigen / nächsten Foto blättern |
| **STRG + Klick / Shift + Klick** | Bereichsauswahl: Wählt alle Fotos zwischen erstem und zweitem Klick aus |
| **S** | Foto / markierte Zeilen für Import bzw. Transfer an- oder abwählen |
| **Leertaste / Escape** | Vorschaumodus schließen |

---

## 📄 Lizenz
MIT License.
