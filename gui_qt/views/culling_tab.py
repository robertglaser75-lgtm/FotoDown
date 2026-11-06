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
from gui_qt.styles.icons import (
    get_collapse_panel_icon, get_expand_panel_icon, get_filmstrip_icon,
    get_folder_icon, get_refresh_icon
)
from gui_qt.views.culling_tree import CullingDirectoryTreeWidget
from gui_qt.widgets.collapsible_box import CollapsibleBox
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
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(0)

        # Ultrawide Splitter: Left Sidebar for Controls, Right Workspace for Maximum Height Canvas
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        # -------------------------------------------------------------
        # PANE 1: DIRECTORY TREE (Verzeichnisbaum mit Zählern)
        # -------------------------------------------------------------
        self.dir_tree = CullingDirectoryTreeWidget(self.config, self)
        self.dir_tree.setMinimumWidth(280)
        self.dir_tree.setMaximumWidth(480)
        self.dir_tree.folder_selected.connect(self._on_tree_folder_selected)
        self.dir_tree.collapse_panel_requested.connect(self._toggle_dir_tree)
        self.splitter.addWidget(self.dir_tree)

        # -------------------------------------------------------------
        # PANE 2: CONTROLS SIDEBAR (Ratings, Folders, Editors, Stats)
        # -------------------------------------------------------------
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_scroll.setMinimumWidth(320)
        sidebar_scroll.setMaximumWidth(420)

        sidebar_content = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_content)
        sidebar_layout.setContentsMargins(4, 4, 6, 4)
        sidebar_layout.setSpacing(8)

        card_style = """
            QFrame {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 6px;
            }
        """

        # 1. Collapsible Section: Folder Selection & Scan Progress
        self.box_folder = CollapsibleBox("Ordner & Quellverzeichnis", is_expanded=True)
        content_folder = QWidget()
        layout_folder = QVBoxLayout(content_folder)
        layout_folder.setContentsMargins(2, 4, 2, 4)
        layout_folder.setSpacing(6)

        folder_btns_layout = QHBoxLayout()
        folder_btns_layout.setSpacing(6)

        self.btn_choose_folder = QPushButton("Ordner wählen...")
        self.btn_choose_folder.setIcon(get_folder_icon("#38bdf8", 14))
        self.btn_choose_folder.setIconSize(QSize(14, 14))
        self.btn_choose_folder.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; color: #f8fafc; border: 1px solid #334155;
                border-radius: 4px; padding: 5px 12px; font-weight: 500; font-size: 12px;
            }
            QPushButton:hover { background-color: #334155; }
        """)
        self.btn_choose_folder.clicked.connect(self._on_choose_folder_clicked)
        folder_btns_layout.addWidget(self.btn_choose_folder, stretch=1)

        self.btn_refresh = QPushButton()
        self.btn_refresh.setIcon(get_refresh_icon("#cbd5e1", 14))
        self.btn_refresh.setIconSize(QSize(14, 14))
        self.btn_refresh.setFixedSize(30, 28)
        self.btn_refresh.setToolTip("Ordner neu scannen")
        self.btn_refresh.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 4px;")
        self.btn_refresh.clicked.connect(self.refresh_current_folder)
        folder_btns_layout.addWidget(self.btn_refresh)
        layout_folder.addLayout(folder_btns_layout)

        self.lbl_folder_path = QLabel("Kein Ordner ausgewählt")
        self.lbl_folder_path.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 500;")
        self.lbl_folder_path.setWordWrap(True)
        layout_folder.addWidget(self.lbl_folder_path)

        # Scanning Progress Frame
        self.progress_frame = QFrame()
        self.progress_frame.setStyleSheet("""
            QFrame {
                background-color: #0b1329;
                border: 1px solid #1d4ed8;
                border-radius: 6px;
                padding: 4px 6px;
            }
        """)
        prog_layout = QVBoxLayout(self.progress_frame)
        prog_layout.setContentsMargins(6, 4, 6, 4)
        prog_layout.setSpacing(4)

        prog_head = QHBoxLayout()
        self.lbl_scan_status = QLabel("Lese Fotos ein...")
        self.lbl_scan_status.setStyleSheet("color: #38bdf8; font-weight: 600; font-size: 10px;")
        prog_head.addWidget(self.lbl_scan_status, stretch=1)

        self.btn_cancel_scan = QPushButton("✕")
        self.btn_cancel_scan.setFixedSize(20, 20)
        self.btn_cancel_scan.setToolTip("Scan abbrechen")
        self.btn_cancel_scan.setStyleSheet("background-color: #7f1d1d; color: white; border: none; border-radius: 3px; font-size: 10px; font-weight: bold;")
        self.btn_cancel_scan.clicked.connect(self._cancel_scan)
        prog_head.addWidget(self.btn_cancel_scan)
        prog_layout.addLayout(prog_head)

        self.scan_progress_bar = QProgressBar()
        self.scan_progress_bar.setFixedHeight(8)
        self.scan_progress_bar.setRange(0, 100)
        self.scan_progress_bar.setValue(0)
        self.scan_progress_bar.setTextVisible(False)
        self.scan_progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
                border-radius: 2px;
            }
        """)
        prog_layout.addWidget(self.scan_progress_bar)
        self.progress_frame.setVisible(False)
        layout_folder.addWidget(self.progress_frame)

        self.box_folder.set_content_widget(content_folder)
        sidebar_layout.addWidget(self.box_folder)

        # 2. Card: Active Photo & Navigation
        card_photo = QFrame()
        card_photo.setStyleSheet(card_style)
        layout_photo = QVBoxLayout(card_photo)
        layout_photo.setContentsMargins(6, 6, 6, 6)
        layout_photo.setSpacing(6)

        lbl_sec_photo = QLabel("📷 AKTIVES FOTO")
        lbl_sec_photo.setStyleSheet("font-size: 11px; font-weight: bold; color: #94a3b8;")
        layout_photo.addWidget(lbl_sec_photo)

        self.lbl_active_name = QLabel("Kein Foto geladen")
        self.lbl_active_name.setStyleSheet("font-weight: bold; font-size: 12px; color: #f8fafc;")
        self.lbl_active_name.setWordWrap(True)
        layout_photo.addWidget(self.lbl_active_name)

        # Badges row
        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(6)
        self.lbl_pair_badge = QLabel("")
        self.lbl_pair_badge.setStyleSheet("background-color: #0284c7; color: white; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
        self.lbl_pair_badge.setVisible(False)
        badges_layout.addWidget(self.lbl_pair_badge)

        self.btn_toggle_raw_jpg = QPushButton("Ansicht: Auto")
        self.btn_toggle_raw_jpg.setToolTip("Zwischen JPEG und RAW Ansicht umschalten (Taste J oder R)")
        self.btn_toggle_raw_jpg.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; color: #38bdf8; border: 1px solid #0284c7;
                border-radius: 4px; padding: 3px 8px; font-size: 10px; font-weight: 600;
            }
            QPushButton:hover { background-color: #0369a1; color: white; }
        """)
        self.btn_toggle_raw_jpg.clicked.connect(self._toggle_raw_jpg_view)
        badges_layout.addWidget(self.btn_toggle_raw_jpg)
        badges_layout.addStretch()
        layout_photo.addLayout(badges_layout)

        # Navigation row
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(6)
        self.btn_prev = QPushButton("◀ Vorheriges [A]")
        self.btn_prev.setStyleSheet("background-color: #1e293b; color: #f8fafc; border: 1px solid #334155; border-radius: 4px; padding: 5px;")
        self.btn_prev.clicked.connect(self._prev_item)
        nav_layout.addWidget(self.btn_prev)

        self.btn_next = QPushButton("Nächstes ▶ [D]")
        self.btn_next.setStyleSheet("background-color: #1e293b; color: #f8fafc; border: 1px solid #334155; border-radius: 4px; padding: 5px;")
        self.btn_next.clicked.connect(self._next_item)
        nav_layout.addWidget(self.btn_next)
        layout_photo.addLayout(nav_layout)

        # Zoom Button
        self.btn_zoom = QPushButton("🔍 100% Schärfelupe [F]")
        self.btn_zoom.setStyleSheet("background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155; border-radius: 4px; padding: 4px; font-size: 11px;")
        self.btn_zoom.clicked.connect(self._toggle_canvas_zoom)
        layout_photo.addWidget(self.btn_zoom)

        sidebar_layout.addWidget(card_photo)

        # 3. Card: Rating & Culling
        card_rating = QFrame()
        card_rating.setStyleSheet(card_style)
        layout_rating = QVBoxLayout(card_rating)
        layout_rating.setContentsMargins(6, 6, 6, 6)
        layout_rating.setSpacing(6)

        lbl_sec_rating = QLabel("⭐ BEWERTUNG & CULLING")
        lbl_sec_rating.setStyleSheet("font-size: 11px; font-weight: bold; color: #94a3b8;")
        layout_rating.addWidget(lbl_sec_rating)

        # Stars row
        stars_layout = QHBoxLayout()
        stars_layout.setSpacing(4)
        self.star_buttons = []
        for s in range(1, 6):
            btn = QPushButton(f"{s}★")
            btn.setFixedHeight(26)
            btn.setToolTip(f"Mit {s} Stern(en) bewerten (Taste {s})")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b; color: #fbbf24; border: 1px solid #334155;
                    border-radius: 4px; font-weight: bold; font-size: 11px;
                }
                QPushButton:hover { background-color: #d97706; color: white; }
            """)
            btn.clicked.connect(lambda _, val=s: self.set_current_rating(val))
            stars_layout.addWidget(btn)
            self.star_buttons.append(btn)

        btn_star_zero = QPushButton("0")
        btn_star_zero.setFixedSize(26, 26)
        btn_star_zero.setToolTip("Bewertung entfernen (Taste 0)")
        btn_star_zero.setStyleSheet("background-color: #1e293b; color: #94a3b8; border: 1px solid #334155; border-radius: 4px; font-size: 10px;")
        btn_star_zero.clicked.connect(lambda: self.set_current_rating(0))
        stars_layout.addWidget(btn_star_zero)
        layout_rating.addLayout(stars_layout)

        # Pick & Reject row
        pick_rej_layout = QHBoxLayout()
        pick_rej_layout.setSpacing(6)
        self.btn_pick = QPushButton("✔ Behalten [P]")
        self.btn_pick.setStyleSheet("""
            QPushButton {
                background-color: #065f46; color: #a7f3d0; border: 1px solid #059669;
                border-radius: 4px; padding: 5px; font-weight: 600; font-size: 11px;
            }
            QPushButton:hover { background-color: #047857; color: white; }
        """)
        self.btn_pick.clicked.connect(self._toggle_pick)
        pick_rej_layout.addWidget(self.btn_pick)

        self.btn_reject = QPushButton("✖ Ablehnen [X]")
        self.btn_reject.setStyleSheet("""
            QPushButton {
                background-color: #7f1d1d; color: #fca5a5; border: 1px solid #b91c1c;
                border-radius: 4px; padding: 5px; font-weight: 600; font-size: 11px;
            }
            QPushButton:hover { background-color: #991b1b; color: white; }
        """)
        self.btn_reject.clicked.connect(self._toggle_reject)
        pick_rej_layout.addWidget(self.btn_reject)
        layout_rating.addLayout(pick_rej_layout)

        sidebar_layout.addWidget(card_rating)

        # 4. Card: External Editors & Reject Processing
        card_external = QFrame()
        card_external.setStyleSheet(card_style)
        layout_ext = QVBoxLayout(card_external)
        layout_ext.setContentsMargins(6, 6, 6, 6)
        layout_ext.setSpacing(6)

        lbl_sec_ext = QLabel("🚀 EXTERNE EDITOREN")
        lbl_sec_ext.setStyleSheet("font-size: 11px; font-weight: bold; color: #94a3b8;")
        layout_ext.addWidget(lbl_sec_ext)

        self.btn_darktable = QPushButton("🎨 In Darktable öffnen (RAW) [Strg+D]")
        self.btn_darktable.setToolTip("Ausgewählte RAW-Dateien direkt an Darktable übergeben")
        self.btn_darktable.setStyleSheet("""
            QPushButton {
                background-color: #831843; color: #fbcfe8; border: 1px solid #be185d;
                border-radius: 4px; padding: 6px 10px; font-weight: bold; font-size: 11px; text-align: left;
            }
            QPushButton:hover { background-color: #9d174d; color: white; }
        """)
        self.btn_darktable.clicked.connect(self._launch_darktable)
        layout_ext.addWidget(self.btn_darktable)

        self.btn_topaz = QPushButton("✨ In Topaz Photo öffnen (JPEG) [Strg+T]")
        self.btn_topaz.setToolTip("Ausgewählte JPEG-Dateien direkt an Topaz Photo zur KI-Optimierung übergeben")
        self.btn_topaz.setStyleSheet("""
            QPushButton {
                background-color: #1e3a8a; color: #bfdbfe; border: 1px solid #2563eb;
                border-radius: 4px; padding: 6px 10px; font-weight: bold; font-size: 11px; text-align: left;
            }
            QPushButton:hover { background-color: #1d4ed8; color: white; }
        """)
        self.btn_topaz.clicked.connect(self._launch_topaz)
        layout_ext.addWidget(self.btn_topaz)

        self.btn_apply_reject = QPushButton("🗑️ Aussortierte verarbeiten")
        self.btn_apply_reject.setToolTip("Führt die konfigurierte Aktion für alle mit [X] abgelehnten Fotos aus")
        self.btn_apply_reject.setStyleSheet("""
            QPushButton {
                background-color: #334155; color: #f87171; border: 1px solid #475569;
                border-radius: 4px; padding: 5px 10px; font-size: 11px; font-weight: 600; text-align: left;
            }
            QPushButton:hover { background-color: #475569; color: white; }
        """)
        self.btn_apply_reject.clicked.connect(self._apply_reject_action)
        layout_ext.addWidget(self.btn_apply_reject)

        sidebar_layout.addWidget(card_external)

        # 5. Card: Statistics
        card_stats = QFrame()
        card_stats.setStyleSheet(card_style)
        layout_stats = QVBoxLayout(card_stats)
        layout_stats.setContentsMargins(6, 6, 6, 6)
        layout_stats.setSpacing(4)

        lbl_sec_stats = QLabel("📊 STATISTIK")
        lbl_sec_stats.setStyleSheet("font-size: 11px; font-weight: bold; color: #94a3b8;")
        layout_stats.addWidget(lbl_sec_stats)

        self.lbl_stats = QLabel("0 Fotos geladen")
        self.lbl_stats.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.lbl_stats.setWordWrap(True)
        layout_stats.addWidget(self.lbl_stats)

        sidebar_layout.addWidget(card_stats)

        # 6. Card: Keyboard Shortcuts
        card_keys = QFrame()
        card_keys.setStyleSheet(card_style)
        layout_keys = QVBoxLayout(card_keys)
        layout_keys.setContentsMargins(6, 6, 6, 6)
        layout_keys.setSpacing(3)

        lbl_sec_keys = QLabel("⌨️ SCHNELLZUGRIFF")
        lbl_sec_keys.setStyleSheet("font-size: 11px; font-weight: bold; color: #94a3b8;")
        layout_keys.addWidget(lbl_sec_keys)

        shortcuts_text = (
            "<span style='color:#38bdf8;'>A / D</span> Blättern &nbsp;|&nbsp; "
            "<span style='color:#38bdf8;'>1 - 5</span> Sterne &nbsp;|&nbsp; "
            "<span style='color:#38bdf8;'>0</span> Reset<br>"
            "<span style='color:#38bdf8;'>P</span> Behalten &nbsp;|&nbsp; "
            "<span style='color:#38bdf8;'>X</span> Ablehnen &nbsp;|&nbsp; "
            "<span style='color:#38bdf8;'>J / R</span> RAW/JPG<br>"
            "<span style='color:#38bdf8;'>F</span> 100% Zoom &nbsp;|&nbsp; "
            "<span style='color:#38bdf8;'>V</span> Baum &nbsp;|&nbsp; "
            "<span style='color:#38bdf8;'>T</span> Filmstreifen &nbsp;|&nbsp; "
            "<span style='color:#38bdf8;'>Strg+D/T</span> Editoren"
        )
        lbl_keys_desc = QLabel(shortcuts_text)
        lbl_keys_desc.setStyleSheet("color: #64748b; font-size: 10px; line-height: 1.4;")
        layout_keys.addWidget(lbl_keys_desc)

        sidebar_layout.addWidget(card_keys)
        sidebar_layout.addStretch()

        sidebar_scroll.setWidget(sidebar_content)
        self.splitter.addWidget(sidebar_scroll)

        # -------------------------------------------------------------
        # RIGHT WORKSPACE: Maximal Height Canvas & Optional Filmstrip
        # -------------------------------------------------------------
        workspace_container = QWidget()
        workspace_layout = QVBoxLayout(workspace_container)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(2)

        # Minimal Top Toolbar on the image canvas (Tree and Filmstrip Toggles)
        top_strip = QFrame()
        top_strip.setStyleSheet("background-color: #070a12; border-bottom: 1px solid #1e293b; padding: 2px 6px;")
        strip_layout = QHBoxLayout(top_strip)
        strip_layout.setContentsMargins(4, 2, 4, 2)
        strip_layout.setSpacing(8)

        self.btn_toggle_tree = QPushButton("Verzeichnisbaum ausblenden [V]")
        self.btn_toggle_tree.setIcon(get_folder_icon("#38bdf8", 14))
        self.btn_toggle_tree.setIconSize(QSize(14, 14))
        self.btn_toggle_tree.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; color: #94a3b8; border: 1px solid #334155;
                border-radius: 4px; padding: 3px 10px; font-size: 11px; font-weight: 500;
            }
            QPushButton:hover { background-color: #334155; color: white; }
        """)
        self.btn_toggle_tree.clicked.connect(self._toggle_dir_tree)
        strip_layout.addWidget(self.btn_toggle_tree)

        strip_layout.addStretch()

        self.btn_toggle_filmstrip = QPushButton("Filmstreifen ausblenden [T]")
        self.btn_toggle_filmstrip.setIcon(get_filmstrip_icon("#94a3b8", 14))
        self.btn_toggle_filmstrip.setIconSize(QSize(14, 14))
        self.btn_toggle_filmstrip.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; color: #94a3b8; border: 1px solid #334155;
                border-radius: 4px; padding: 3px 10px; font-size: 11px; font-weight: 500;
            }
            QPushButton:hover { background-color: #334155; color: white; }
        """)
        self.btn_toggle_filmstrip.clicked.connect(self._toggle_filmstrip)
        strip_layout.addWidget(self.btn_toggle_filmstrip)

        workspace_layout.addWidget(top_strip)

        # Canvas: Takes all remaining vertical height!
        self.canvas = CullingCanvasWidget(self)
        self.canvas.toggle_zoom_requested.connect(self._update_zoom_btn_text)
        workspace_layout.addWidget(self.canvas, stretch=1)

        # Filmstrip Bar: Docked at bottom (can be collapsed with T)
        self.filmstrip = FilmstripBar(self)
        self.filmstrip.item_clicked.connect(self._on_filmstrip_item_clicked)
        workspace_layout.addWidget(self.filmstrip)

        self.splitter.addWidget(workspace_container)

        # Splitter sizing: Directory tree ~280px, Controls ~320px, Right canvas gets rest
        self.splitter.setSizes([280, 320, 1800])
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 1)

        main_layout.addWidget(self.splitter)

    def load_folder(self, folder: Path):
        """Loads and scans photos from folder into the Culling workflow with progress display."""
        if not folder or not folder.exists() or not folder.is_dir():
            return

        self._cancel_scan()

        self.current_folder = folder
        self.lbl_folder_path.setText(str(folder))
        self.config.culling_last_folder = str(folder)
        self.config.save()
        if hasattr(self, "dir_tree") and self.dir_tree:
            self.dir_tree.select_folder(folder)

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

    def _on_tree_folder_selected(self, folder: Path):
        if self.current_folder and self.current_folder.resolve() == folder.resolve():
            return
        self.load_folder(folder)

    def _toggle_dir_tree(self):
        is_vis = not self.dir_tree.isVisible()
        self.dir_tree.setVisible(is_vis)
        self.btn_toggle_tree.setText("Verzeichnisbaum ausblenden [V]" if is_vis else "Verzeichnisbaum einblenden [V]")
        self.btn_toggle_tree.setIcon(get_folder_icon("#38bdf8" if is_vis else "#94a3b8", 14))

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

    def _toggle_filmstrip(self):
        is_vis = not self.filmstrip.isVisible()
        self.filmstrip.setVisible(is_vis)
        self.btn_toggle_filmstrip.setText("Filmstreifen ausblenden [T]" if is_vis else "Filmstreifen einblenden [T]")
        self.btn_toggle_filmstrip.setIcon(get_filmstrip_icon("#38bdf8" if is_vis else "#94a3b8", 14))

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
        # Directory tree toggle
        elif key == Qt.Key.Key_V:
            self._toggle_dir_tree()
            return
        # Filmstrip toggle
        elif key == Qt.Key.Key_T:
            self._toggle_filmstrip()
            return

        super().keyPressEvent(event)

