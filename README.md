# FotoDown 📸

**FotoDown** ist ein intelligentes, schnelles Werkzeug zum automatischen Importieren, Umbenennen und Sortieren von Fotos und Videos direkt von Speicherkarten (SD-Karten, USB-Laufwerken) oder beliebigen Quellordnern.

Lauffähig unter **Windows** und **Linux**.

---

## ✨ Funktionen

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
  - Vertikaler Splitter durch Sidebar-Layout ersetzt: Steuer- und Konfigurationsleiste links, maximaler Raum für Fotobetrachtung rechts.
  - Stufenloser **Zoom-Slider** für Miniaturbilder in der Fotogalerie (`QListView` im `IconMode`).
  - Sortier- und filterbare Tabellenansicht (`QTableView` mit `ScanFilterProxyModel`).
  - Fluent Dark Design optimiert für Windows 11 und moderne Linux-Desktops (GNOME, KDE Plasma).
- ⚙️ **Kommandozeilen-Modus (CLI):** Voller CLI-Support für Scripting, Hintergrundjobs und Headless-Server.
- 🛡️ **Kollisionssicher:** Vorhandene Zieldateien werden bei Bedarf automatisch nummeriert (`_1`, `_2`), um Überschreiben zu verhindern.

---

## 🚀 Schnellstart

### Voraussetzungen
Python 3.10 oder neuer mit den Paketen aus `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 1. Unter Windows:
Einfach die Datei **`FotoDown.bat`** per Doppelklick starten oder die Desktop-Verknüpfung verwenden.

### 2. Unter Linux:
```bash
chmod +x fotodown.sh
./fotodown.sh
```

### 3. Starten über Python:
```bash
python fotodown.py
```

### 4. Starten im CLI-Modus (Kommandozeile):
```bash
# Windows
python fotodown.py --source E:\DCIM --target "D:\Meine Fotos"

# Linux
python fotodown.py --source /media/user/EOS_DIGITAL/DCIM --target /home/user/Pictures
```
Für einen reinen Trockenlauf (Vorschau ohne Kopieren):
```bash
python fotodown.py --source E:\DCIM --target "D:\Meine Fotos" --dry-run
```

---

## 🧩 Platzhalter für Dateinamen und Ordner

| Platzhalter | Bedeutung | Beispiel |
| :--- | :--- | :--- |
| `{YYYY}` | 4-stelliges Aufnahmejahr | `2026` |
| `{YY}` | 2-stelliges Aufnahmejahr | `26` |
| `{MM}` | 2-stelliger Aufnahmemonat | `08` |
| `{MONTH_NAME}` | Monatsname (Deutsch) | `August` |
| `{DD}` | 2-stelliger Aufnahmetag | `15` |
| `{hh}` | 2-stellige Aufnahmestunde (24h) | `14` |
| `{mm}` | 2-stellige Aufnahmeminute | `30` |
| `{ss}` | 2-stellige Aufnahmesekunde | `45` |
| `{camera}` | Erkannter Kameraname | `Sony_ILCE-7M4` |
| `{make}` | Kamerahersteller | `Sony` |
| `{model}` | Kameramodell | `ILCE-7M4` |
| `{orig_name}` | Originaler Dateiname ohne Endung | `DSC_0123` |
| `{num:04d}` | 4-stellige fortlaufende Nummer (0001, 0002...) | `0001` |
| `{num:03d}` | 3-stellige fortlaufende Nummer (001, 002...) | `001` |
| `{num:02d}` | 2-stellige fortlaufende Nummer (01, 02...) | `01` |
| `{num}` | Fortlaufende Nummer ohne führende Nullen | `1` |
| `{ext}` | Dateiendung | `jpg` |

---

## 🧪 Tests ausführen
```bash
python -m unittest discover tests
```
