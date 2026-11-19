"""Help and documentation dialog explaining placeholders, viewer controls, and workflows."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QLabel, QPushButton,
    QTextBrowser, QVBoxLayout
)

from core.version import __version__
from gui_qt.styles.theme import THEME_LIGHT, theme_manager


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vitrina - Hilfe & Anleitung")
        self.resize(820, 660)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QLabel(f"Vitrina v{__version__} • Dokumentation, Workflow & Tastaturkürzel")
        header.setObjectName("appTitle")
        layout.addWidget(header)

        is_light = theme_manager.effective_theme == THEME_LIGHT
        text_color = "#1e293b" if is_light else "#e2e8f0"
        muted_color = "#475569" if is_light else "#94a3b8"
        h2_color = "#0284c7" if is_light else "#38bdf8"
        h3_color = "#0369a1" if is_light else "#7dd3fc"
        border_color = "#cbd5e1" if is_light else "#334155"
        th_bg = "#e2e8f0" if is_light else "#1e293b"
        code_bg = "#f1f5f9" if is_light else "#0f172a"
        code_fg = "#0369a1" if is_light else "#38bdf8"

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(f"""
        <style>
            body {{ font-family: 'Segoe UI', Ubuntu, sans-serif; font-size: 13px; line-height: 1.6; color: {text_color}; }}
            h2 {{ color: {h2_color}; border-bottom: 1px solid {border_color}; padding-bottom: 4px; margin-top: 18px; font-size: 16px; }}
            h3 {{ color: {h3_color}; margin-top: 12px; font-size: 14px; }}
            p {{ margin: 6px 0; }}
            table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
            th, td {{ border: 1px solid {border_color}; padding: 6px 10px; text-align: left; }}
            th {{ background-color: {th_bg}; color: {muted_color}; font-weight: bold; }}
            code {{ background-color: {code_bg}; color: {code_fg}; padding: 2px 6px; border-radius: 4px; font-family: monospace; }}
            ul {{ margin: 6px 0; padding-left: 20px; }}
            li {{ margin-bottom: 4px; }}
        </style>

        <h2>1. Arbeitsbereiche (Tabs) im Überblick</h2>
        <ul>
            <li><b>1. Importieren:</b> Automatische Erkennung von SD-Karten &amp; Laufwerken, Profile/Presets, optionales gleichzeitiges 2. Backup (NAS/Festplatte), RAW+JPG-Kopplung, XMP-Sidecar-Synchronisation, SHA-256 Duplikat- und Integritätsprüfung sowie Tabellen-, Galerie- und Einzelansicht inkl. EXIF-Inspektor &amp; Histogramm.</li>
            <li><b>2. Sichten &amp; Sortieren:</b> Schnelles Culling direkt auf der Ordnerstruktur mit konfigurierbarem Verzeichnisbaum (Spalten <i>Bilder / RAW / JPG</i> über das Spalten-Icon oder Rechtsklick ein-/ausblendbar), 5-Sterne-Bewertung, Pick (<code>P</code>) / Verwerfen (<code>X</code>), Workflow-Status (<code>Ungeprüft</code>, <code>SOOC [Q]</code>, <code>Bearbeitet [B]</code>, <code>Fertig [W]</code> inkl. Darktable-History-Erkennung), 100%-Schärfelupe (<code>F</code>), Filmstreifen (<code>T</code>) sowie direktem Aufruf von <b>Darktable</b> (<code>Strg+D</code>) und <b>Topaz Photo AI</b> (<code>Strg+T</code>).</li>
            <li><b>3. Sichern &amp; Archivieren:</b> Dual-Pane-Dateimanager (Quelle links, Ziel / NAS rechts) zum Kopieren, Verschieben und Abgleichen (z. B. mit dem Familienalbum) inkl. automatischer <code>.xmp</code>-Sidecar-Mitnahme und Stapel-Umbenennung nach Muster. Bei schmaleren Ansichten schrumpfen Toolbar-Buttons sauber bis auf ihre Icons und zeigen den vollen Text per Tooltip.</li>
        </ul>

        <h2>2. Integrierter Bildbetrachter</h2>
        <p>Ein Doppelklick auf ein Foto (oder die <code>Leertaste</code>) öffnet den integrierten Bildbetrachter mit Unterstützung für gängige Foto-, RAW-Vorschau- und weitere Bildformate (inkl. WebP, SVG, TIFF, BMP, GIF, ICO und großer Panoramen):</p>
        <ul>
            <li><b>Zoom &amp; Verschieben:</b> Stufenlos per <code>Mausrad</code> oder <code>+</code> / <code>-</code>, <code>1</code> für <b>1:1 (100 %)</b>, <code>0</code> für <b>Einpassen</b>. Im gezoomten Zustand kann das Bild per Mausziehen verschoben (Panning) werden.</li>
            <li><b>Drehen &amp; Vollbild:</b> <code>L</code> / <code>R</code> dreht um 90° nach links/rechts; <code>F11</code> oder Doppelklick schaltet den Vollbildmodus um.</li>
            <li><b>Öffnungsgröße konfigurierbar:</b> In den <b>Einstellungen → Einzelansicht &amp; Farbschema</b> kann festgelegt werden, wie groß Bilder beim Öffnen dargestellt werden (<i>Einpassen</i>, <i>90 % / 75 % / 50 % der Fenstergröße</i> oder feste Zoomstufen <i>100 % / 150 % / 200 %</i>).</li>
            <li><b>Bilddaten-Overlay (unten links):</b> Zeigt Dateiname/Endung, Sterne/Status, Kamera &amp; Objektiv, Belichtungsdaten, Aufnahmedatum, Dateigröße/Dimensionen und Ordnerpfad – einzeln konfigurierbar in den Einstellungen.</li>
            <li><b>Sterne-Bewertung im Betrachter:</b> Direkt über die 5-Sterne-Leiste unten (oder per <code>Strg+0</code> bis <code>Strg+5</code>) änderbar; Änderungen werden sofort in die <code>.xmp</code>-Sidecar-Datei geschrieben und mit Sichten/Sichern synchronisiert.</li>
        </ul>

        <h2>3. Platzhalter für Dateinamen und Ordner</h2>
        <table>
            <tr><th>Platzhalter</th><th>Bedeutung</th><th>Beispiel</th></tr>
            <tr><td><code>{{YYYY}}</code></td><td>4-stelliges Aufnahmejahr</td><td>2026</td></tr>
            <tr><td><code>{{YY}}</code></td><td>2-stelliges Aufnahmejahr</td><td>26</td></tr>
            <tr><td><code>{{MM}}</code></td><td>2-stelliger Aufnahmemonat</td><td>08</td></tr>
            <tr><td><code>{{MONTH_NAME}}</code></td><td>Monatsname (Deutsch)</td><td>August</td></tr>
            <tr><td><code>{{DD}}</code></td><td>2-stelliger Aufnahmetag</td><td>15</td></tr>
            <tr><td><code>{{hh}}</code></td><td>2-stellige Aufnahmestunde (24h)</td><td>14</td></tr>
            <tr><td><code>{{mm}}</code></td><td>2-stellige Aufnahmeminute</td><td>30</td></tr>
            <tr><td><code>{{ss}}</code></td><td>2-stellige Aufnahmesekunde</td><td>45</td></tr>
            <tr><td><code>{{camera}}</code></td><td>Erkannter Kameraname</td><td>Sony_ILCE-7M4</td></tr>
            <tr><td><code>{{make}}</code></td><td>Kamerahersteller</td><td>Sony</td></tr>
            <tr><td><code>{{model}}</code></td><td>Kameramodell</td><td>ILCE-7M4</td></tr>
            <tr><td><code>{{orig_name}}</code></td><td>Originaler Dateiname ohne Endung</td><td>DSC_0123</td></tr>
            <tr><td><code>{{num:04d}}</code></td><td>4-stellige Nummer</td><td>0001</td></tr>
            <tr><td><code>{{ext}}</code></td><td>Dateiendung</td><td>jpg</td></tr>
        </table>

        <h2>4. Einstellungen &amp; Oberfläche anpassen</h2>
        <ul>
            <li><b>Farbschema:</b> <i>Dunkel (Fluent Dark)</i>, <i>Hell (Fluent Light)</i> oder <i>Automatisch</i> (folgt dem System).</li>
            <li><b>Mindestbreite für Seitenleisten:</b> Standardmäßig aktiviert, damit Buttons nicht abgeschnitten werden; bei Bedarf in den Einstellungen oder schnell über das Zahnrad-Menü deaktivierbar, um Leisten beliebig schmal zu schieben.</li>
            <li><b>Tastatur-Navigation:</b> In den Einstellungen zwischen verschiedenen Weiterschalt-Schemata (Pfeiltasten, <code>A</code>/<code>D</code>, <code>Bild ↑/↓</code>, optional Mausrad) wählbar.</li>
        </ul>

        <h2>5. Unterstützte Dateiformate &amp; Duplikaterkennung</h2>
        <ul>
            <li><b>Standard- &amp; Zusatz-Fotos:</b> .jpg, .jpeg, .png, .heic, .heif, .tiff/.tif, .webp, .bmp, .gif, .svg, .tga, .ico</li>
            <li><b>Kamera-RAW:</b> Canon (.cr2, .cr3), Nikon (.nef), Sony (.arw), Adobe (.dng), Panasonic (.rw2), Olympus (.orf, .ori), Fuji (.raf), Pentax (.pef)</li>
            <li><b>Videos:</b> .mp4, .mov, .mts, .m2ts, .avi, .mkv</li>
            <li><b>Duplikaterkennung:</b> Vitrina speichert bei jedem erfolgreichen Import den SHA-256-Hash in einer lokalen SQLite-Datenbank, sodass bereits importierte Dateien beim erneuten Einlegen der SD-Karte automatisch übersprungen werden können.</li>
        </ul>

        <h2>6. Wichtige Tastaturkürzel &amp; Navigation</h2>
        <table>
            <tr><th>Taste</th><th>Funktion</th><th>Bereich</th></tr>
            <tr><td><code>F11</code></td><td>Vollbildmodus ein- / ausschalten</td><td>Global &amp; Bildbetrachter</td></tr>
            <tr><td><code>Leertaste</code> / <code>Esc</code></td><td>Bildbetrachter öffnen bzw. schließen</td><td>Import, Sichten &amp; Sichern</td></tr>
            <tr><td><code>+</code> / <code>-</code> / <code>Mausrad</code></td><td>Hinein- / Herauszoomen</td><td>Bildbetrachter</td></tr>
            <tr><td><code>1</code> / <code>0</code></td><td>Originalgröße (1:1) / Einpassen</td><td>Bildbetrachter</td></tr>
            <tr><td><code>L</code> / <code>R</code></td><td>Bild um 90° nach links / rechts drehen</td><td>Bildbetrachter</td></tr>
            <tr><td><code>Strg+0</code> bis <code>Strg+5</code></td><td>Sterne-Bewertung direkt ändern (XMP-Sync)</td><td>Bildbetrachter</td></tr>
            <tr><td><code>S</code></td><td>Auswahl-Häkchen umschalten</td><td>Bildbetrachter</td></tr>
            <tr><td><code>1</code> bis <code>5</code> / <code>0</code></td><td>Sterne-Bewertung vergeben / zurücksetzen</td><td>Sichten &amp; Sortieren</td></tr>
            <tr><td><code>P</code> / <code>X</code></td><td>Bild behalten (Pick) / Verwerfen (Reject)</td><td>Sichten &amp; Sortieren</td></tr>
            <tr><td><code>Q</code> / <code>B</code> / <code>W</code></td><td>Workflow-Status: SOOC / Bearbeitet / Fertig</td><td>Sichten &amp; Sortieren</td></tr>
            <tr><td><code>J</code> / <code>R</code></td><td>Zwischen JPG- und RAW-Ansicht umschalten</td><td>Sichten &amp; Sortieren</td></tr>
            <tr><td><code>F</code></td><td>Zwischen Einpassen und 100%-Schärfelupe wechseln</td><td>Einzelansicht &amp; Sichten</td></tr>
            <tr><td><code>T</code> / <code>V</code></td><td>Filmstreifen / Verzeichnisbaum ein- oder ausblenden</td><td>Sichten &amp; Sortieren</td></tr>
            <tr><td><code>Strg+D</code> / <code>Strg+T</code></td><td>In Darktable / Topaz Photo AI öffnen</td><td>Sichten &amp; Sortieren</td></tr>
        </table>

        <h2>7. Plattformunabhängigkeit (Windows &amp; Linux)</h2>
        <p>Vitrina funktioniert vollständig unter <b>Windows</b> und <b>Linux</b>.
        Speicherkarten und USB-Laufwerke werden unter Linux in <code>/media</code>, <code>/run/media</code> sowie <code>/mnt</code> automatisch erkannt.</p>
        """)
        layout.addWidget(browser)

        btn_close = QPushButton("Schließen")
        btn_close.setObjectName("primaryBtn")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)
