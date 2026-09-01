# FotoDown 📸

**FotoDown** ist ein intelligentes, schnelles Werkzeug zum automatischen Importieren, Umbenennen und Sortieren von Fotos und Videos direkt von Speicherkarten (SD-Karten, USB-Laufwerken) oder beliebigen Quellordnern.

---

## ✨ Funktionen

- 🔍 **Automatische Speicherkartenerkennung:** Erkennt eingesteckte SD-Karten und findet automatisch typische `DCIM`-Ordner.
- 🧠 **Duplikaterkennung via Historie:** Merkt sich heruntergeladene Fotos (via Hash & Metadaten in einer SQLite-Datenbank). Speicherkarte erneut einstecken? Es werden **nur neue Fotos** geladen!
- 🏷️ **Flexible EXIF-Umbenennung:** Frei definierbare Muster mit Direkt-Vorschau.
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
- 🖥️ **Moderne Benutzeroberfläche & CLI:** Intuitive GUI (mit Fortschrittsbalken, Farbcodes & Vorschautabelle) sowie voller Kommandozeilensupport.
- 🛡️ **Kollisionssicher:** Vorhandene Zieldateien werden bei Bedarf automatisch nummeriert (`_1`, `_2`), um Überschreiben zu verhindern.

---

## 🚀 Schnellstart

### 1. Starten per Doppelklick:
Einfach die Datei **`FotoDown.bat`** doppelt anklicken.

### 2. Starten über die Konsole:
```bash
python fotodown.py
```

### 3. Starten im CLI-Modus (Kommandozeile):
```bash
python fotodown.py --source E:\DCIM --target "D:\Meine Fotos"
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

### Beispiel-Kombinationen:
- **Ordner-Schema:** `{YYYY}/{YYYY}-{MM}-{DD}`
- **Dateiname-Schema:** `{YYYY}-{MM}-{DD}_{hh}-{mm}-{ss}_{camera}_{orig_name}`
- **Ergebnis:** `2026/2026-08-15/2026-08-15_14-30-45_Sony_ILCE-7M4_DSC_0123.jpg`

---

## 🧪 Tests ausführen

```bash
python -m unittest discover tests
```
