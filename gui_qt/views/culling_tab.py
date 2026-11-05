"""Culling and Review View (Tab 2 of FotoDown).

Features:
- Responsive full-screen / zoomable image canvas with 100% detail check.
- High-speed keyboard navigation and culling (<kbd>◀</kbd>/<kbd>▶</kbd>, <kbd>A</kbd>/<kbd>D</kbd>).
- Star rating (<kbd>1</kbd>-<kbd>5</kbd>, <kbd>0</kbd>), Color labels, Pick (<kbd>P</kbd>), Reject (<kbd>X</kbd>).
- RAW+JPEG synchronized display with <kbd>J</kbd>/<kbd>R</kbd> instant preview toggle.
- Synchronized XMP sidecar rating updates.
- One-click launch in Darktable (RAW only) and Topaz Photo (JPEG only).
- Configurable rejection execution (move to _Abgelehnt/ or trash).
"""

from pathlib import Path
from typing import Dict, List, Optional
from PIL import Image

from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QKeyEvent, QPainter, QPainterPath, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSplitter, QVBoxLayout, QWidget
)

from core.config import AppConfig
from core.drive_detector import format_size
from core.external_tools import launch_darktable, launch_topaz_photo
from core.thumbnail import generate_thumbnail, load_preview_image
from core.xmp_sync import sync_pair_xmp
from gui_qt.models.culling_model import CullingItem, execute_reject_action, scan_culling_folder
from gui_qt.workers.culling_worker import CullingScanWorker


class CullingCanvasWidget(QScrollArea):
    """Viewport widget rendering the active photo with smooth scaling, 100% toggle, and pan."""
    toggle_zoom_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #0b0f19; border: none;")

        self.lbl_image = QLabel()
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setStyleSheet("background: transparent;")
        self.setWidget(self.lbl_image)

        self._pixmap: Optional[QPixmap] = None
        self._zoom_mode: str = "fit"  # "fit" or "actual"

    def set_pixmap(self, pixmap: Optional[QPixmap], keep_zoom: bool = False):
        self._pixmap = pixmap
        if not keep_zoom:
            self._zoom_mode = "fit"
        self.update_display()

    def toggle_zoom(self):
        self._zoom_mode = "actual" if self._zoom_mode == "fit" else "fit"
        self.update_display()
        return self._zoom_mode

    def update_display(self):
        if not self._pixmap or self._pixmap.isNull():
            self.lbl_image.setPixmap(QPixmap())
            self.lbl_image.setText("Kein Bild geladen")
            self.lbl_image.setStyleSheet("color: #64748b; font-size: 14px;")
            return

        self.lbl_image.setText("")
        if self._zoom_mode == "actual":
            self.lbl_image.setPixmap(self._pixmap)
            self.lbl_image.adjustSize()
        else:
            vp_size = self.viewport().size()
            scaled = self._pixmap.scaled(
                vp_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_image.setPixmap(scaled)
            self.lbl_image.resize(vp_size)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._zoom_mode == "fit":
            self.update_display()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_zoom()
            self.toggle_zoom_requested.emit()
        super().mouseDoubleClickEvent(event)


class FilmstripBar(QScrollArea):
    """Horizontal filmstrip showing card thumbnails, star ratings, and rejection status."""
    item_clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(120)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("""
            QScrollArea {
                background-color: #090d16;
                border-top: 1px solid #1e293b;
            }
        """)

        self.container = QWidget()
        self.layout_strip = QHBoxLayout(self.container)
        self.layout_strip.setContentsMargins(8, 6, 8, 6)
        self.layout_strip.setSpacing(6)
        self.setWidget(self.container)

        self._item_cards: List[QFrame] = []
        self._thumb_cache: Dict[str, QPixmap] = {}
        self.current_idx: int = -1

    def set_items(self, items: List[CullingItem], current_idx: int = 0):
        # Clear existing
        while self.layout_strip.count():
            w = self.layout_strip.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._item_cards.clear()

        for idx, it in enumerate(items):
            card = self._create_card(it, idx)
            self.layout_strip.addWidget(card)
            self._item_cards.append(card)

        self.layout_strip.addStretch()
        self.set_current_index(current_idx)

    def set_current_index(self, idx: int):
        self.current_idx = idx
        for i, card in enumerate(self._item_cards):
            is_active = (i == idx)
            card.setProperty("active", is_active)
            card.style().unpolish(card)
            card.style().polish(card)
            card.update()

        # Ensure active card is visible in scroll area
        if 0 <= idx < len(self._item_cards):
            card = self._item_cards[idx]
            self.ensureWidgetVisible(card, 100, 0)

    def update_card(self, idx: int, item: CullingItem):
        if 0 <= idx < len(self._item_cards):
            card = self._item_cards[idx]
            # Update rating text & reject status
            lbl_info: QLabel = card.findChild(QLabel, "lbl_card_info")
            if lbl_info:
                stars = "★" * item.rating if item.rating > 0 else ""
                rej_tag = " [X]" if item.is_rejected else ""
                lbl_info.setText(f"{stars}{rej_tag}")
                if item.is_rejected:
                    lbl_info.setStyleSheet("color: #ef4444; font-size: 10px; font-weight: bold;")
                elif item.rating > 0:
                    lbl_info.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: bold;")
                else:
                    lbl_info.setStyleSheet("color: #64748b; font-size: 10px;")

    def _create_card(self, it: CullingItem, idx: int) -> QFrame:
        card = QFrame()
        card.setFixedSize(92, 104)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
            }
            QFrame[active="true"] {
                border: 2px solid #38bdf8;
                background-color: #0f2744;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        lbl_thumb = QLabel()
        lbl_thumb.setFixedSize(84, 56)
        lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_thumb.setStyleSheet("background-color: #0b1120; border-radius: 4px;")
        layout.addWidget(lbl_thumb)

        # Load or generate thumbnail
        p_str = str(it.current_display_path)
        if p_str in self._thumb_cache:
            lbl_thumb.setPixmap(self._thumb_cache[p_str])
        else:
            QTimer.singleShot(idx * 20, lambda path=it.current_display_path, lbl=lbl_thumb, pstr=p_str: self._async_load_thumb(path, lbl, pstr))

        lbl_name = QLabel(it.primary_path.stem[:12])
        lbl_name.setStyleSheet("font-size: 9px; color: #cbd5e1; font-weight: 500;")
        lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_name)

        stars = "★" * it.rating if it.rating > 0 else ""
        rej_tag = " [X]" if it.is_rejected else ""
        lbl_info = QLabel(f"{stars}{rej_tag}")
        lbl_info.setObjectName("lbl_card_info")
        lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if it.is_rejected:
            lbl_info.setStyleSheet("color: #ef4444; font-size: 10px; font-weight: bold;")
        elif it.rating > 0:
            lbl_info.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: bold;")
        else:
            lbl_info.setStyleSheet("color: #64748b; font-size: 10px;")
        layout.addWidget(lbl_info)

        card.mousePressEvent = lambda e, i=idx: self.item_clicked.emit(i)
        return card

    def _async_load_thumb(self, path: Path, lbl: QLabel, key: str):
        try:
            pil_thumb = generate_thumbnail(path, max_size=(160, 110))
            if pil_thumb:
                if pil_thumb.mode != "RGB":
                    pil_thumb = pil_thumb.convert("RGB")
                data = pil_thumb.tobytes("raw", "RGB")
                qimg = QImage(data, pil_thumb.width, pil_thumb.height, pil_thumb.width * 3, QImage.Format.Format_RGB888)
                pix = QPixmap.fromImage(qimg).scaled(84, 56, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self._thumb_cache[key] = pix
                if lbl:
                    lbl.setPixmap(pix)
        except Exception:
            pass


class CullingTabView(QWidget):
    """Main view of Tab 2: Sichten & Sortieren."""
    navigate_to_import_requested = Signal()

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.items: List[CullingItem] = []
        self.filtered_items: List[CullingItem] = []
        self.current_idx: int = -1
        self.current_folder: Optional[Path] = None
        self._scan_worker: Optional[CullingScanWorker] = None

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # 1. Top Bar: Folder picker, Refresh & Target Info
        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #0f172a; border: 1px solid #1e293b; border-radius: 6px; padding: 4px;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(6, 4, 6, 4)
        top_layout.setSpacing(8)

        lbl_folder = QLabel("📁 Ordner:")
        lbl_folder.setStyleSheet("font-weight: 600; color: #94a3b8;")
        top_layout.addWidget(lbl_folder)

        self.btn_choose_folder = QPushButton("Ordner zum Sichten wählen...")
        self.btn_choose_folder.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; color: #f8fafc; border: 1px solid #334155;
                border-radius: 4px; padding: 5px 12px; font-weight: 500;
            }
            QPushButton:hover { background-color: #334155; }
        """)
        self.btn_choose_folder.clicked.connect(self._on_choose_folder_clicked)
        top_layout.addWidget(self.btn_choose_folder)

        self.lbl_folder_path = QLabel("Kein Ordner ausgewählt")
        self.lbl_folder_path.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: 500;")
        top_layout.addWidget(self.lbl_folder_path, stretch=1)

        self.btn_refresh = QPushButton("🔄 Neu laden")
        self.btn_refresh.setStyleSheet("background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155; border-radius: 4px; padding: 5px 10px;")
        self.btn_refresh.clicked.connect(self.refresh_current_folder)
        top_layout.addWidget(self.btn_refresh)

        main_layout.addWidget(top_bar)

        # 1b. Scanning Progress Frame (asynchronous progress bar while opening a folder)
        self.progress_frame = QFrame()
        self.progress_frame.setStyleSheet("""
            QFrame {
                background-color: #0b1329;
                border: 1px solid #1d4ed8;
                border-radius: 6px;
            }
        """)
        prog_layout = QHBoxLayout(self.progress_frame)
        prog_layout.setContentsMargins(10, 6, 10, 6)
        prog_layout.setSpacing(10)

        self.lbl_scan_status = QLabel("Lese Fotos ein...")
        self.lbl_scan_status.setStyleSheet("color: #38bdf8; font-weight: 600; font-size: 11px;")
        prog_layout.addWidget(self.lbl_scan_status)

        self.scan_progress_bar = QProgressBar()
        self.scan_progress_bar.setFixedHeight(12)
        self.scan_progress_bar.setRange(0, 100)
        self.scan_progress_bar.setValue(0)
        self.scan_progress_bar.setTextVisible(False)
        self.scan_progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
                border-radius: 3px;
            }
        """)
        prog_layout.addWidget(self.scan_progress_bar, stretch=1)

        self.btn_cancel_scan = QPushButton("✕ Abbrechen")
        self.btn_cancel_scan.setStyleSheet("""
            QPushButton {
                background-color: #7f1d1d; color: #fca5a5; border: 1px solid #b91c1c;
                border-radius: 4px; padding: 3px 10px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background-color: #991b1b; color: white; }
        """)
        self.btn_cancel_scan.clicked.connect(self._cancel_scan)
        prog_layout.addWidget(self.btn_cancel_scan)

        self.progress_frame.setVisible(False)
        main_layout.addWidget(self.progress_frame)

        # 2. Control & Rating Bar
        ctrl_bar = QFrame()
        ctrl_bar.setStyleSheet("background-color: #090d16; border: 1px solid #1e293b; border-radius: 6px; padding: 4px;")
        ctrl_layout = QHBoxLayout(ctrl_bar)
        ctrl_layout.setContentsMargins(6, 4, 6, 4)
        ctrl_layout.setSpacing(8)

        # Navigation Buttons
        self.btn_prev = QPushButton("◀ Vorheriges [A]")
        self.btn_prev.clicked.connect(self._prev_item)
        ctrl_layout.addWidget(self.btn_prev)

        self.btn_next = QPushButton("Nächstes ▶ [D]")
        self.btn_next.clicked.connect(self._next_item)
        ctrl_layout.addWidget(self.btn_next)

        # Filename & Pair Badge
        self.lbl_active_name = QLabel("Kein Foto geladen")
        self.lbl_active_name.setStyleSheet("font-weight: bold; font-size: 13px; color: #f8fafc;")
        ctrl_layout.addWidget(self.lbl_active_name)

        self.lbl_pair_badge = QLabel("")
        self.lbl_pair_badge.setStyleSheet("background-color: #0284c7; color: white; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
        self.lbl_pair_badge.setVisible(False)
        ctrl_layout.addWidget(self.lbl_pair_badge)

        # RAW vs JPG Toggle Switch (J/R)
        self.btn_toggle_raw_jpg = QPushButton("Ansicht: Auto")
        self.btn_toggle_raw_jpg.setToolTip("Zwischen JPEG und RAW Ansicht umschalten (Taste J oder R)")
        self.btn_toggle_raw_jpg.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; color: #38bdf8; border: 1px solid #0284c7;
                border-radius: 4px; padding: 4px 10px; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background-color: #0369a1; color: white; }
        """)
        self.btn_toggle_raw_jpg.clicked.connect(self._toggle_raw_jpg_view)
        ctrl_layout.addWidget(self.btn_toggle_raw_jpg)

        ctrl_layout.addStretch()

        # Star Rating Buttons (1 to 5)
        lbl_stars_title = QLabel("Bewertung:")
        lbl_stars_title.setStyleSheet("color: #94a3b8; font-size: 11px;")
        ctrl_layout.addWidget(lbl_stars_title)

        self.star_buttons = []
        for s in range(1, 6):
            btn = QPushButton(f"{s}★")
            btn.setFixedSize(30, 26)
            btn.setToolTip(f"Mit {s} Stern(en) bewerten (Taste {s})")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b; color: #fbbf24; border: 1px solid #334155;
                    border-radius: 4px; font-weight: bold; font-size: 11px;
                }
                QPushButton:hover { background-color: #d97706; color: white; }
            """)
            btn.clicked.connect(lambda _, val=s: self.set_current_rating(val))
            ctrl_layout.addWidget(btn)
            self.star_buttons.append(btn)

        # Clear Rating Button (0)
        btn_star_zero = QPushButton("0")
        btn_star_zero.setFixedSize(26, 26)
        btn_star_zero.setToolTip("Bewertung entfernen (Taste 0)")
        btn_star_zero.setStyleSheet("background-color: #1e293b; color: #94a3b8; border: 1px solid #334155; border-radius: 4px; font-size: 10px;")
        btn_star_zero.clicked.connect(lambda: self.set_current_rating(0))
        ctrl_layout.addWidget(btn_star_zero)

        ctrl_layout.addSpacing(10)

        # Pick (P) & Reject (X)
        self.btn_pick = QPushButton("✔ Behalten [P]")
        self.btn_pick.setStyleSheet("""
            QPushButton {
                background-color: #065f46; color: #a7f3d0; border: 1px solid #059669;
                border-radius: 4px; padding: 4px 10px; font-weight: 600; font-size: 11px;
            }
            QPushButton:hover { background-color: #047857; color: white; }
        """)
        self.btn_pick.clicked.connect(self._toggle_pick)
        ctrl_layout.addWidget(self.btn_pick)

        self.btn_reject = QPushButton("✖ Ablehnen [X]")
        self.btn_reject.setStyleSheet("""
            QPushButton {
                background-color: #7f1d1d; color: #fca5a5; border: 1px solid #b91c1c;
                border-radius: 4px; padding: 4px 10px; font-weight: 600; font-size: 11px;
            }
            QPushButton:hover { background-color: #991b1b; color: white; }
        """)
        self.btn_reject.clicked.connect(self._toggle_reject)
        ctrl_layout.addWidget(self.btn_reject)

        # Zoom Button (F)
        self.btn_zoom = QPushButton("🔍 100% Zoom [F]")
        self.btn_zoom.setStyleSheet("background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155; border-radius: 4px; padding: 4px 10px; font-size: 11px;")
        self.btn_zoom.clicked.connect(self._toggle_canvas_zoom)
        ctrl_layout.addWidget(self.btn_zoom)

        main_layout.addWidget(ctrl_bar)

        # 3. Central Canvas Viewer
        self.canvas = CullingCanvasWidget(self)
        self.canvas.toggle_zoom_requested.connect(self._update_zoom_btn_text)
        main_layout.addWidget(self.canvas, stretch=1)

        # 4. Filmstrip Bar (Thumbnails)
        self.filmstrip = FilmstripBar(self)
        self.filmstrip.item_clicked.connect(self._on_filmstrip_item_clicked)
        main_layout.addWidget(self.filmstrip)

        # 5. Bottom Action Bar: Darktable, Topaz, Reject Execution & Stats
        bottom_bar = QFrame()
        bottom_bar.setStyleSheet("background-color: #0f172a; border: 1px solid #1e293b; border-radius: 6px; padding: 4px;")
        b_layout = QHBoxLayout(bottom_bar)
        b_layout.setContentsMargins(6, 4, 6, 4)
        b_layout.setSpacing(10)

        # External Editor Buttons
        self.btn_darktable = QPushButton("🎨 In Darktable öffnen (RAW) [Strg+D]")
        self.btn_darktable.setToolTip("Ausgewählte RAW-Dateien direkt an Darktable übergeben")
        self.btn_darktable.setStyleSheet("""
            QPushButton {
                background-color: #831843; color: #fbcfe8; border: 1px solid #be185d;
                border-radius: 5px; padding: 6px 14px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #9d174d; color: white; }
        """)
        self.btn_darktable.clicked.connect(self._launch_darktable)
        b_layout.addWidget(self.btn_darktable)

        self.btn_topaz = QPushButton("✨ In Topaz Photo öffnen (JPEG) [Strg+T]")
        self.btn_topaz.setToolTip("Ausgewählte JPEG-Dateien direkt an Topaz Photo zur KI-Optimierung übergeben")
        self.btn_topaz.setStyleSheet("""
            QPushButton {
                background-color: #1e3a8a; color: #bfdbfe; border: 1px solid #2563eb;
                border-radius: 5px; padding: 6px 14px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #1d4ed8; color: white; }
        """)
        self.btn_topaz.clicked.connect(self._launch_topaz)
        b_layout.addWidget(self.btn_topaz)

        # Reject Action Button
        self.btn_apply_reject = QPushButton("🗑️ Aussortierte verarbeiten")
        self.btn_apply_reject.setToolTip("Führt die konfigurierte Aktion für alle mit [X] abgelehnten Fotos aus")
        self.btn_apply_reject.setStyleSheet("""
            QPushButton {
                background-color: #334155; color: #f87171; border: 1px solid #475569;
                border-radius: 5px; padding: 6px 12px; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background-color: #475569; color: white; }
        """)
        self.btn_apply_reject.clicked.connect(self._apply_reject_action)
        b_layout.addWidget(self.btn_apply_reject)

        b_layout.addStretch()

        # Stats Label
        self.lbl_stats = QLabel("0 Fotos geladen")
        self.lbl_stats.setStyleSheet("color: #94a3b8; font-size: 12px;")
        b_layout.addWidget(self.lbl_stats)

        main_layout.addWidget(bottom_bar)

    def load_folder(self, folder: Path):
        """Loads and scans photos from folder into the Culling workflow with progress display."""
        if not folder or not folder.exists() or not folder.is_dir():
            return

        self._cancel_scan()

        self.current_folder = folder
        self.lbl_folder_path.setText(str(folder))
        self.config.culling_last_folder = str(folder)
        self.config.save()

        # Display progress frame and disable folder buttons while scanning
        self.btn_choose_folder.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.scan_progress_bar.setValue(0)
        self.lbl_scan_status.setText("Durchsuche Verzeichnis nach Fotos & RAW-Dateien...")
        self.progress_frame.setVisible(True)

        self.canvas.set_pixmap(None)
        self.lbl_active_name.setText("Lade Fotos...")
        self.lbl_stats.setText("Lese Ordner ein...")

        self._scan_worker = CullingScanWorker(folder, parent=self)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.scan_finished.connect(self._on_scan_finished)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.start()

    def _on_scan_progress(self, cur: int, total: int, filename: str):
        pct = int(cur / total * 100) if total > 0 else 0
        self.scan_progress_bar.setValue(pct)
        self.lbl_scan_status.setText(f"Lese Fotos ein: {cur} von {total} ({pct}%) • {filename}")
        self.lbl_stats.setText(f"Scan läuft: {cur}/{total} ({pct}%)")

    def _on_scan_finished(self, items: List[CullingItem]):
        self.progress_frame.setVisible(False)
        self.btn_choose_folder.setEnabled(True)
        self.btn_refresh.setEnabled(True)

        self.items = items
        self.filtered_items = list(self.items)

        self._update_stats_label()
        if self.items:
            self.filmstrip.set_items(self.items, 0)
            self.set_current_index(0)
        else:
            self.filmstrip.set_items([], -1)
            self.canvas.set_pixmap(None)
            self.lbl_active_name.setText("Keine Fotos im Ordner gefunden")
            self.lbl_pair_badge.setVisible(False)

    def _on_scan_error(self, err_msg: str):
        self.progress_frame.setVisible(False)
        self.btn_choose_folder.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        QMessageBox.critical(self, "Fehler beim Einlesen", f"Fehler beim Scannen des Ordners:\n{err_msg}")
        self.lbl_active_name.setText("Fehler beim Laden")
        self.lbl_stats.setText("Fehler beim Laden")

    def _cancel_scan(self):
        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.cancel()
            self._scan_worker.wait(1000)
        self.progress_frame.setVisible(False)
        self.btn_choose_folder.setEnabled(True)
        self.btn_refresh.setEnabled(True)

    def refresh_current_folder(self):
        if self.current_folder:
            self.load_folder(self.current_folder)

    def _on_choose_folder_clicked(self):
        start_dir = str(self.current_folder) if self.current_folder else self.config.target_dir
        folder = QFileDialog.getExistingDirectory(self, "Ordner zum Sichten wählen", start_dir)
        if folder:
            self.load_folder(Path(folder))

    def set_current_index(self, idx: int):
        if not self.items or not (0 <= idx < len(self.items)):
            return
        self.current_idx = idx
        self.filmstrip.set_current_index(idx)
        self._render_current_item()

    def _render_current_item(self):
        if not self.items or not (0 <= self.current_idx < len(self.items)):
            return

        it = self.items[self.current_idx]
        self.lbl_active_name.setText(f"{it.primary_path.name} ({self.current_idx + 1} von {len(self.items)})")

        if it.is_pair:
            self.lbl_pair_badge.setText(f"RAW+JPG ({it.active_view_mode})")
            self.lbl_pair_badge.setVisible(True)
            self.btn_toggle_raw_jpg.setVisible(True)
            self.btn_toggle_raw_jpg.setText(f"Ansicht: {it.active_view_mode}")
        else:
            self.lbl_pair_badge.setVisible(False)
            self.btn_toggle_raw_jpg.setVisible(False)

        # Highlight current rating buttons
        for s_idx, btn in enumerate(self.star_buttons, 1):
            if s_idx <= it.rating:
                btn.setStyleSheet("background-color: #d97706; color: white; border: 1px solid #f59e0b; border-radius: 4px; font-weight: bold;")
            else:
                btn.setStyleSheet("background-color: #1e293b; color: #fbbf24; border: 1px solid #334155; border-radius: 4px; font-weight: bold;")

        # Pick / Reject buttons state
        if it.is_rejected:
            self.btn_reject.setStyleSheet("background-color: #dc2626; color: white; border: 1px solid #ef4444; border-radius: 4px; font-weight: bold;")
        else:
            self.btn_reject.setStyleSheet("background-color: #7f1d1d; color: #fca5a5; border: 1px solid #b91c1c; border-radius: 4px; font-weight: 600;")

        # Load Preview Image
        disp_path = it.current_display_path
        pil_img = load_preview_image(disp_path, max_dim=2560)
        if pil_img:
            if pil_img.mode != "RGB":
                pil_img = pil_img.convert("RGB")
            data = pil_img.tobytes("raw", "RGB")
            qimg = QImage(data, pil_img.width, pil_img.height, pil_img.width * 3, QImage.Format.Format_RGB888)
            pix = QPixmap.fromImage(qimg)
            self.canvas.set_pixmap(pix, keep_zoom=False)
        else:
            self.canvas.set_pixmap(None)

    def set_current_rating(self, stars: int):
        if not self.items or not (0 <= self.current_idx < len(self.items)):
            return
        it = self.items[self.current_idx]
        it.rating = stars
        if stars > 0:
            it.is_rejected = False
        sync_pair_xmp(it.primary_path, it.companion_path, rating=it.rating, label=it.color_label, is_rejected=it.is_rejected)
        self.filmstrip.update_card(self.current_idx, it)
        self._render_current_item()
        self._update_stats_label()

    def _toggle_pick(self):
        if not self.items or not (0 <= self.current_idx < len(self.items)):
            return
        it = self.items[self.current_idx]
        it.is_picked = not it.is_picked
        if it.is_picked:
            it.is_rejected = False
            if it.rating == 0:
                it.rating = 3
        sync_pair_xmp(it.primary_path, it.companion_path, rating=it.rating, label=it.color_label, is_rejected=it.is_rejected)
        self.filmstrip.update_card(self.current_idx, it)
        self._render_current_item()
        self._update_stats_label()

    def _toggle_reject(self):
        if not self.items or not (0 <= self.current_idx < len(self.items)):
            return
        it = self.items[self.current_idx]
        it.is_rejected = not it.is_rejected
        if it.is_rejected:
            it.is_picked = False
            it.rating = 0
        sync_pair_xmp(it.primary_path, it.companion_path, rating=it.rating, label=it.color_label, is_rejected=it.is_rejected)
        self.filmstrip.update_card(self.current_idx, it)
        self._render_current_item()
        self._update_stats_label()

    def _toggle_raw_jpg_view(self):
        if not self.items or not (0 <= self.current_idx < len(self.items)):
            return
        it = self.items[self.current_idx]
        if not it.is_pair:
            return

        order = ["AUTO", "RAW", "JPG"]
        next_mode = order[(order.index(it.active_view_mode) + 1) % len(order)]
        it.active_view_mode = next_mode
        self._render_current_item()

    def _toggle_canvas_zoom(self):
        mode = self.canvas.toggle_zoom()
        self.btn_zoom.setText("🔍 Einpassen [F]" if mode == "actual" else "🔍 100% Zoom [F]")

    def _update_zoom_btn_text(self):
        mode = self.canvas._zoom_mode
        self.btn_zoom.setText("🔍 Einpassen [F]" if mode == "actual" else "🔍 100% Zoom [F]")

    def _prev_item(self):
        if self.current_idx > 0:
            self.set_current_index(self.current_idx - 1)

    def _next_item(self):
        if self.current_idx < len(self.items) - 1:
            self.set_current_index(self.current_idx + 1)

    def _on_filmstrip_item_clicked(self, idx: int):
        self.set_current_index(idx)

    def _launch_darktable(self):
        """Passes RAW files of current selection (or all 3★+ picked) to Darktable."""
        if not self.items:
            QMessageBox.information(self, "Keine Fotos", "Es sind keine Fotos zum Übergeben geladen.")
            return

        # Prefer 3+ star items or current item if none picked
        targets = [it for it in self.items if it.rating >= 3 and not it.is_rejected]
        if not targets and 0 <= self.current_idx < len(self.items):
            targets = [self.items[self.current_idx]]

        raw_files = []
        for it in targets:
            if it.raw_path:
                raw_files.append(it.raw_path)

        if not raw_files:
            QMessageBox.warning(self, "Keine RAW-Dateien", "In der aktuellen Auswahl wurden keine RAW-Dateien gefunden.")
            return

        ok, msg = launch_darktable(raw_files, self.config.darktable_path)
        if ok:
            QMessageBox.information(self, "Darktable gestartet", msg)
        else:
            QMessageBox.critical(self, "Fehler beim Starten von Darktable", msg)

    def _launch_topaz(self):
        """Passes JPEG files of current selection (or all 3★+ picked) to Topaz Photo."""
        if not self.items:
            QMessageBox.information(self, "Keine Fotos", "Es sind keine Fotos zum Übergeben geladen.")
            return

        targets = [it for it in self.items if it.rating >= 3 and not it.is_rejected]
        if not targets and 0 <= self.current_idx < len(self.items):
            targets = [self.items[self.current_idx]]

        jpg_files = []
        for it in targets:
            if it.jpeg_path:
                jpg_files.append(it.jpeg_path)

        if not jpg_files:
            QMessageBox.warning(self, "Keine JPEG-Dateien", "In der aktuellen Auswahl wurden keine JPEG-Dateien gefunden.")
            return

        ok, msg = launch_topaz_photo(jpg_files, self.config.topaz_path)
        if ok:
            QMessageBox.information(self, "Topaz Photo gestartet", msg)
        else:
            QMessageBox.critical(self, "Fehler beim Starten von Topaz Photo", msg)

    def _apply_reject_action(self):
        """Executes the configured reject action."""
        rejected_count = sum(1 for it in self.items if it.is_rejected)
        if rejected_count == 0:
            QMessageBox.information(self, "Keine Ablehnungen", "Es sind aktuell keine Fotos als abgelehnt [X] markiert.")
            return

        action = self.config.reject_action
        folder_name = self.config.reject_folder_name
        action_desc = f"in den Unterordner '{folder_name}/' verschieben" if action == "move_folder" else "löschen"

        ret = QMessageBox.question(
            self,
            "Aussortierte Fotos verarbeiten",
            f"Möchten Sie {rejected_count} abgelehnte Foto-Einheiten wirklich {action_desc}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ret == QMessageBox.StandardButton.Yes:
            cnt, msg = execute_reject_action(self.items, action=action, folder_name=folder_name)
            QMessageBox.information(self, "Verarbeitung abgeschlossen", msg)
            self.refresh_current_folder()

    def _update_stats_label(self):
        total = len(self.items)
        rated = sum(1 for it in self.items if it.rating > 0)
        rejected = sum(1 for it in self.items if it.is_rejected)
        picked = sum(1 for it in self.items if it.is_picked or it.rating >= 3)
        self.lbl_stats.setText(f"Gesamt: {total} | Bewertet: {rated} | ★★★+ Behalten: {picked} | [X] Abgelehnt: {rejected}")

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        # Modifiers
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_D:
                self._launch_darktable()
                return
            elif key == Qt.Key.Key_T:
                self._launch_topaz()
                return

        # Navigation
        if key in (Qt.Key.Key_Left, Qt.Key.Key_A):
            self._prev_item()
            return
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_D):
            self._next_item()
            return
        # Rating 0-5
        elif key in (Qt.Key.Key_0, Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4, Qt.Key.Key_5):
            val = key - Qt.Key.Key_0
            self.set_current_rating(val)
            return
        # Pick & Reject
        elif key == Qt.Key.Key_P:
            self._toggle_pick()
            return
        elif key == Qt.Key.Key_X:
            self._toggle_reject()
            return
        # Raw / Jpg toggle
        elif key in (Qt.Key.Key_J, Qt.Key.Key_R):
            self._toggle_raw_jpg_view()
            return
        # Zoom toggle
        elif key == Qt.Key.Key_F:
            self._toggle_canvas_zoom()
            return

        super().keyPressEvent(event)

