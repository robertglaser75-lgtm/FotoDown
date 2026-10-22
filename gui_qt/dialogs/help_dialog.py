"""Help and documentation dialog explaining placeholders and workflows."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton,
    QTextBrowser, QVBoxLayout
)

from core.version import __version__


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FotoDown - Hilfe & Anleitung")
        self.resize(720, 560)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QLabel(f"FotoDown v{__version__} • Dokumentation & Platzhalter")
        header.setObjectName("appTitle")
        layout.addWidget(header)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(f"""
        <style>
            body {{ font-family: 'Segoe UI', Ubuntu, sans-serif; font-size: 13px; line-height: 1.6; color: #e2e8f0; }}
            h2 {{ color: #38bdf8; border-bottom: 1px solid #334155; padding-bottom: 4px; margin-top: 16px; font-size: 16px; }}
            h3 {{ color: #7dd3fc; margin-top: 12px; font-size: 14px; }}
            table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
            th, td {{ border: 1px solid #334155; padding: 6px 10px; text-align: left; }}
            th {{ background-color: #1e293b; color: #94a3b8; font-weight: bold; }}
            code {{ background-color: #0f172a; color: #38bdf8; padding: 2px 6px; border-radius: 4px; font-family: monospace; }}
            ul {{ margin: 6px 0; padding-left: 20px; }}
            li {{ margin-bottom: 4px; }}
        </style>

        <h2>1. Platzhalter für Dateinamen und Ordner</h2>
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

        <h2>2. Intelligente Duplikaterkennung</h2>
        <p>FotoDown speichert bei jedem erfolgreichen Import den SHA-256-Hash der Datei in einer lokalen SQLite-Datenbank.
        Beim erneuten Einstecken derselben SD-Karte werden nur noch diejenigen Fotos geladen, die noch nicht importiert wurden.</p>

        <h2>3. Unterstützte Dateiformate</h2>
        <ul>
            <li><b>Standard-Fotos:</b> .jpg, .jpeg, .png, .heic, .heif, .tiff</li>
            <li><b>Kamera-RAW:</b> Canon (.cr2, .cr3), Nikon (.nef), Sony (.arw), Adobe (.dng), Panasonic (.rw2), Olympus (.orf), Fuji (.raf), Pentax (.pef)</li>
            <li><b>Videos:</b> .mp4, .mov, .mts, .m2ts, .avi, .mkv</li>
        </ul>

        <h2>4. Plattformunabhängigkeit (Windows & Linux)</h2>
        <p>FotoDown funktioniert vollständig und ohne Einschränkungen unter <b>Windows</b> und <b>Linux</b>.
        Speicherkarten und USB-Laufwerke werden unter Linux in <code>/media</code>, <code>/run/media</code> sowie <code>/mnt</code> automatisch gefunden.</p>
        """)
        layout.addWidget(browser)

        btn_close = QPushButton("Schließen")
        btn_close.setObjectName("primaryBtn")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)
