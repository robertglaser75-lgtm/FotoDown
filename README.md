# FotoDown 📸

**FotoDown** ist ein intelligentes, schnelles Werkzeug zum automatischen Importieren, Umbenennen und Sortieren von Fotos und Videos direkt von Speicherkarten (SD-Karten, USB-Laufwerken) oder beliebigen Quellordnern.

Lauffähig unter **Windows** und **Linux**.

---

## ✨ Funktionen

- 👁️ **2. Hauptfunktion: Sichten & Sortieren (Culling & Editor-Export):**
  - **Zwei-Phasen-Workflow:** Bequemes Umschalten zwischen *„📥 1. Importieren“* und *„👁️ 2. Sichten & Sortieren“*.
  - **Schneller Bildbetrachter:** Blitzschnelles Durchsehen mit Tastaturnavigation (`◀` / `▶` bzw. `A` / `D`), stufenlosem Zoom und 100%-Schärfelupe (`F`).
  - **RAW+JPEG Koppelung:** Anzeige als ein Paar mit sofortiger Umschaltung zwischen JPEG-Kameraansicht und RAW-Vorschau (`J` / `R`).
  - **XMP-Sterne- & Farbbewertung:** Vergabe von 1–5 Sternen (`1`–`5`), Pick (`P`) und Reject (`X`), die sofort in `.xmp`-Sidecars synchronisiert werden (voll kompatibel mit Darktable und Lightroom).
  - **Direkte Editor-Übergabe:**
    - 🎨 **Darktable (`Strg+D`):** Übergabe der ausgewählten Aufnahmen **ausschließlich als RAW-Dateien**.
    - ✨ **Topaz Photo (`Strg+T`):** Übergabe der ausgewählten Aufnahmen **ausschließlich als JPEG-Dateien**.
  - **Konfigurierbares Reject-Handling:** Aussortierte Bilder wahlweise in `_Abgelehnt/` verschieben, löschen oder nur kennzeichnen.
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
- 🚀 **Professioneller Fluent Dark Splashscreen:** Schneller, visuell ansprechender Start mit asynchroner Status- und Ladeanzeige.
- 🔍 **Quick-Look & Vollbild-Schnellvorschau:** Sofortige hochauflösende Schnellvorschau per **Leertaste** oder Doppelklick inklusive RAW-Unterstützung, Pfeiltasten-Navigation und EXIF-Inspektor.
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
| **Leertaste / Doppelklick** | Öffnet die hochauflösende Schnellvorschau (Quick Look) |
| **Pfeiltasten Links / Rechts** | Im Vorschaumodus zum vorherigen / nächsten Foto blättern |
| **STRG + Klick / Shift + Klick** | Bereichsauswahl: Wählt alle Fotos zwischen erstem und zweitem Klick aus |
| **S** | Foto / markierte Zeilen für Import an- oder abwählen |
| **Leertaste / Escape** | Vorschaumodus schließen |

---

## 📄 Lizenz
MIT License.
