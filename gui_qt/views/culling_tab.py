"""Culling and Review View (Tab 2 of Vitrina).

Features:
- Responsive full-screen / zoomable image canvas with 100% detail check.
- High-speed keyboard navigation and culling (<kbd>◀</kbd>/<kbd>▶</kbd>, <kbd>A</kbd>/<kbd>D</kbd>).
- Star rating (<kbd>1</kbd>-<kbd>5</kbd>, <kbd>0</kbd>), Color labels, Pick (<kbd>P</kbd>), Reject (<kbd>X</kbd>).
- RAW+JPEG synchronized display with <kbd>J</kbd>/<kbd>R</kbd> instant preview toggle.
- Synchronized XMP sidecar rating updates.
- One-click launch in Darktable (RAW only) and Topaz Photo (JPEG only).
- Configurable rejection execution (move to _Abgelehnt/ or trash).
"""

from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from PIL import Image

from PySide6.QtCore import Qt, Signal, QSize, QTimer, QEasingCurve, QPropertyAnimation, QThreadPool
from PySide6.QtGui import QColor, QFont, QImage, QKeyEvent, QPainter, QPainterPath, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QFileDialog, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSplitter, QVBoxLayout, QWidget
)

from core.config import AppConfig
from core.drive_detector import format_size
from core.external_tools import launch_darktable, launch_topaz_photo
from core.thumbnail import generate_thumbnail, load_preview_image
from core.xmp_sync import sync_pair_xmp
from gui_qt.key_navigation import (
    DEFAULT_NAVIGATION_SCHEME, get_nav_hint, get_nav_labels, is_nav_next, is_nav_prev
)
from gui_qt.models.culling_model import CullingItem, execute_reject_action, scan_culling_folder
from gui_qt.styles.icons import (
    get_collapse_panel_icon, get_expand_panel_icon, get_filmstrip_icon,
    get_folder_icon, get_refresh_icon, get_zoom_fit_icon, get_zoom_icon
)
from gui_qt.views.culling_filter import CullingFilterCriteria
from gui_qt.views.culling_left_dock import CullingLeftNavigationDock
from gui_qt.views.culling_tree import CullingDirectoryTreeWidget
from gui_qt.widgets.collapsible_box import CollapsibleBox
from gui_qt.workers.culling_worker import CullingScanWorker
from gui_qt.workers.thumb_worker import PreviewSignals, PreviewTask, ThumbnailSignals, ThumbnailTask


class CullingCanvasWidget(QScrollArea):
    """Viewport widget rendering the active photo with smooth scaling, 100% toggle, and pan."""
    toggle_zoom_requested = Signal()
    open_fullscreen_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cullingCanvas")
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_image = QLabel()
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setStyleSheet("background: transparent;")
        self.setWidget(self.lbl_image)

        self._pixmap: Optional[QPixmap] = None
        self._zoom_mode: str = "fit"  # "fit" or "actual"
        self.show_placeholder()

    def set_pixmap(self, pixmap: Optional[QPixmap], keep_zoom: bool = False):
        if pixmap is not None:
            self.hide_loading()
        self._pixmap = pixmap
        if not keep_zoom:
            self._zoom_mode = "fit"
        self.update_display()

    def show_placeholder(
        self,
        icon: str = "🖼️",
        title: str = "Kein Foto ausgewählt",
        subtitle: str = "Wählen Sie links einen Ordner oder ein Foto aus"
    ):
        """Displays a clean, styled placeholder banner on the canvas."""
        self._pixmap = None
        self.hide_loading()
        self.lbl_image.setPixmap(QPixmap())
        self.lbl_image.setText(
            f"<div style='text-align: center; padding: 24px;'>"
            f"<div style='font-size: 38px; line-height: 1.2; margin-bottom: 10px;'>{icon}</div>"
            f"<div style='color: #94a3b8; font-size: 14px; font-weight: 600;'>{title}</div>"
            f"<div style='color: #475569; font-size: 11px; margin-top: 5px;'>{subtitle}</div>"
            f"</div>"
        )
        self.lbl_image.setStyleSheet("background: transparent;")
        self.lbl_image.adjustSize()

    def show_loading(self, text: str = "Lade Fotos..."):
        self._pixmap = None
        self.lbl_image.setPixmap(QPixmap())
        self.lbl_image.setText(text)
        self.lbl_image.setStyleSheet("color: #38bdf8; font-size: 16px; font-weight: 600;")
        if not hasattr(self, "_canvas_loading_anim"):
            self._canvas_loading_effect = QGraphicsOpacityEffect(self.lbl_image)
            self.lbl_image.setGraphicsEffect(self._canvas_loading_effect)
            self._canvas_loading_anim = QPropertyAnimation(self._canvas_loading_effect, b"opacity")
            self._canvas_loading_anim.setDuration(1400)
            self._canvas_loading_anim.setStartValue(1.0)
            self._canvas_loading_anim.setKeyValueAt(0.5, 0.2)
            self._canvas_loading_anim.setEndValue(1.0)
            self._canvas_loading_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
            self._canvas_loading_anim.setLoopCount(-1)
        self._canvas_loading_effect.setOpacity(1.0)
        self._canvas_loading_anim.start()

    def hide_loading(self):
        if hasattr(self, "_canvas_loading_anim") and self._canvas_loading_anim.state() == QPropertyAnimation.State.Running:
            self._canvas_loading_anim.stop()
        if hasattr(self, "_canvas_loading_effect"):
            self._canvas_loading_effect.setOpacity(1.0)

    def toggle_zoom(self):
        self._zoom_mode = "actual" if self._zoom_mode == "fit" else "fit"
        self.update_display()
        return self._zoom_mode

    def update_display(self):
        if not self._pixmap or self._pixmap.isNull():
            self.show_placeholder()
            return

        self.lbl_image.setText("")
        if self._zoom_mode == "actual":
            self.lbl_image.setPixmap(self._pixmap)
            self.lbl_image.adjustSize()
        else:
            vp_size = self.viewport().size()
            dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
            target_w = max(10, int(vp_size.width() * dpr))
            target_h = max(10, int(vp_size.height() * dpr))
            scaled = self._pixmap.scaled(
                target_w, target_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            scaled.setDevicePixelRatio(dpr)
            self.lbl_image.setPixmap(scaled)
            self.lbl_image.resize(vp_size)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._zoom_mode == "fit":
            self.update_display()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_fullscreen_requested.emit()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        p = self.parent()
        scheme = DEFAULT_NAVIGATION_SCHEME
        if p and hasattr(p, "config") and p.config:
            scheme = getattr(p.config, "navigation_scheme", DEFAULT_NAVIGATION_SCHEME)
        if is_nav_prev(event.key(), scheme) or is_nav_next(event.key(), scheme):
            if p and hasattr(p, "keyPressEvent"):
                p.keyPressEvent(event)
                return
        super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        p = self.parent()
        cfg = getattr(p, "config", None) if p else None
        if cfg and getattr(cfg, "navigation_enable_mouse_wheel", False) and self._zoom_mode == "fit":
            delta = event.angleDelta().y()
            if delta > 0 and hasattr(p, "_prev_item"):
                p._prev_item()
                event.accept()
                return
            elif delta < 0 and hasattr(p, "_next_item"):
                p._next_item()
                event.accept()
                return
        super().wheelEvent(event)


class FilmstripBar(QScrollArea):
    """Horizontal filmstrip showing card thumbnails, star ratings, and rejection status."""
    item_clicked = Signal(int)
    item_double_clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cullingFilmstrip")
        self.setFixedHeight(120)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.container = QWidget()
        self.layout_strip = QHBoxLayout(self.container)
        self.layout_strip.setContentsMargins(8, 6, 8, 6)
        self.layout_strip.setSpacing(6)
        self.setWidget(self.container)

        self._item_cards: List[QFrame] = []
        self._thumb_cache: Dict[str, QPixmap] = {}
        self._thumb_label_map: Dict[str, List[QLabel]] = {}
        self._pending_thumb_tasks: Set[str] = set()
        self._thumb_signals = ThumbnailSignals()
        self._thumb_signals.thumbnail_ready.connect(self._on_thumbnail_ready)
        self.current_idx: int = -1

    def _on_thumbnail_ready(self, path_str: str, qimage: QImage):
        self._pending_thumb_tasks.discard(path_str)
        if qimage and not qimage.isNull():
            dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
            target_w = max(10, int(84 * dpr))
            target_h = max(10, int(56 * dpr))
            pix = QPixmap.fromImage(qimage).scaled(
                target_w, target_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            pix.setDevicePixelRatio(dpr)
            self._thumb_cache[path_str] = pix
            for lbl in self._thumb_label_map.pop(path_str, []):
                try:
                    lbl.setPixmap(pix)
                except RuntimeError:
                    pass

    def set_items(self, items: List[CullingItem], current_idx: int = 0):
        # Clear existing
        while self.layout_strip.count():
            w = self.layout_strip.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._item_cards.clear()
        self._thumb_label_map.clear()

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
            # Update rating text, reject status & workflow icon
            lbl_info: QLabel = card.findChild(QLabel, "lbl_card_info")
            if lbl_info:
                stars = "★" * item.rating if item.rating > 0 else ""
                rej_tag = " [X]" if item.is_rejected else ""
                _, _, wf_sym = item.workflow_status_info
                wf_display = f" {wf_sym}" if wf_sym != "⚪" else ""
                lbl_info.setText(f"{stars}{rej_tag}{wf_display}")
                if item.is_rejected:
                    lbl_info.setStyleSheet("color: #ef4444; font-size: 10px; font-weight: bold;")
                elif item.rating > 0:
                    lbl_info.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: bold;")
                else:
                    lbl_info.setStyleSheet("color: #64748b; font-size: 10px;")

    def _create_card(self, it: CullingItem, idx: int) -> QFrame:
        card = QFrame()
        card.setObjectName("filmstripCard")
        card.setFixedSize(92, 104)
        card.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        lbl_thumb = QLabel()
        lbl_thumb.setFixedSize(84, 56)
        lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_thumb.setStyleSheet("background-color: #0b1120; border-radius: 4px;")
        layout.addWidget(lbl_thumb)

        # Load or generate thumbnail asynchronously in thread pool
        p_str = str(it.current_display_path)
        if p_str in self._thumb_cache:
            lbl_thumb.setPixmap(self._thumb_cache[p_str])
        else:
            self._thumb_label_map.setdefault(p_str, []).append(lbl_thumb)
            if p_str not in self._pending_thumb_tasks:
                self._pending_thumb_tasks.add(p_str)
                task = ThumbnailTask(
                    path=it.current_display_path,
                    key_path=p_str,
                    signals=self._thumb_signals,
                    max_size=(168, 112)
                )
                QThreadPool.globalInstance().start(task)

        lbl_name = QLabel(it.primary_path.stem[:12])
        lbl_name.setStyleSheet("font-size: 9px; color: #cbd5e1; font-weight: 500;")
        lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_name)

        stars = "★" * it.rating if it.rating > 0 else ""
        rej_tag = " [X]" if it.is_rejected else ""
        _, _, wf_sym = it.workflow_status_info
        wf_display = f" {wf_sym}" if wf_sym != "⚪" else ""
        lbl_info = QLabel(f"{stars}{rej_tag}{wf_display}")
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
        card.mouseDoubleClickEvent = lambda e, i=idx: self.item_double_clicked.emit(i) if e.button() == Qt.MouseButton.LeftButton else None
        return card


class CullingTabView(QWidget):
    """Main view of Tab 2: Sichten & Sortieren."""
    navigate_to_import_requested = Signal()

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.items: List[CullingItem] = []
        self.filtered_items: List[CullingItem] = []
        self._current_filter: Optional[CullingFilterCriteria] = None
        self.current_idx: int = -1
        self.current_folder: Optional[Path] = None
        self._scan_worker: Optional[CullingScanWorker] = None

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # High-speed LRU preview cache & lookahead preloading
        self._preview_cache: OrderedDict[str, QPixmap] = OrderedDict()
        self._max_preview_cache_size: int = 24
        self._preview_signals = PreviewSignals()
        self._preview_signals.preview_ready.connect(self._on_preview_ready)
        self._prefetched_paths: Set[str] = set()

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(0)

        # Ultrawide Splitter: Left Sidebar for Controls, Right Workspace for Maximum Height Canvas
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        # -------------------------------------------------------------
        # PANE 1: LEFT NAVIGATION DOCK (Verzeichnisse & Filter)
        # -------------------------------------------------------------
        self.left_dock = CullingLeftNavigationDock(self.config, self)
        self.left_dock.folder_selected.connect(self._on_tree_folder_selected)
        self.left_dock.filter_changed.connect(self._on_filter_changed)
        self.left_dock.tree_view.root_changed.connect(self._on_tree_root_changed)
        self.splitter.addWidget(self.left_dock)
        self.dir_tree = self.left_dock.tree_view

        # -------------------------------------------------------------
        # PANE 2: CONTROLS SIDEBAR (Ratings, Editors, Stats)
        # -------------------------------------------------------------
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_scroll.setMinimumWidth(260)
        sidebar_scroll.setMaximumWidth(420)

        sidebar_content = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_content)
        sidebar_layout.setContentsMargins(4, 4, 6, 4)
        sidebar_layout.setSpacing(8)

        # 1. Compact Current Folder Bar
        card_folder = QFrame()
        card_folder.setObjectName("cullingSidebarCard")
        layout_folder = QVBoxLayout(card_folder)
        layout_folder.setContentsMargins(6, 6, 6, 6)
        layout_folder.setSpacing(4)

        folder_head = QHBoxLayout()
        lbl_sec_folder = QLabel("AKTUELLER ORDNER")
        lbl_sec_folder.setObjectName("sectionSubTitle")
        lbl_sec_folder.setStyleSheet("font-size: 10px; font-weight: bold;")
        folder_head.addWidget(lbl_sec_folder, stretch=1)

        self.btn_refresh = QPushButton()
        self.btn_refresh.setObjectName("compactToolBtn")
        self.btn_refresh.setIcon(get_refresh_icon(size=13))
        self.btn_refresh.setIconSize(QSize(13, 13))
        self.btn_refresh.setFixedSize(24, 22)
        self.btn_refresh.setToolTip("Ordner neu scannen")
        self.btn_refresh.clicked.connect(self.refresh_current_folder)
        folder_head.addWidget(self.btn_refresh)
        layout_folder.addLayout(folder_head)

        self.lbl_folder_path = QLabel("Kein Ordner ausgewählt")
        self.lbl_folder_path.setStyleSheet("color: #0284c7; font-size: 11px; font-weight: 500;")
        self.lbl_folder_path.setWordWrap(True)
        layout_folder.addWidget(self.lbl_folder_path)

        # Scanning Progress Frame
        self.progress_frame = QFrame()
        self.progress_frame.setObjectName("cullingScanFrame")
        prog_layout = QVBoxLayout(self.progress_frame)
        prog_layout.setContentsMargins(6, 4, 6, 4)
        prog_layout.setSpacing(4)

        prog_head = QHBoxLayout()
        self.lbl_scan_status = QLabel("Lese Fotos ein...")
        self.lbl_scan_status.setStyleSheet("color: #0284c7; font-weight: 600; font-size: 10px;")
        prog_head.addWidget(self.lbl_scan_status, stretch=1)

        self.btn_cancel_scan = QPushButton("✕")
        self.btn_cancel_scan.setFixedSize(20, 20)
        self.btn_cancel_scan.setToolTip("Scan abbrechen")
        self.btn_cancel_scan.setStyleSheet("background-color: #dc2626; color: white; border: none; border-radius: 3px; font-size: 10px; font-weight: bold;")
        self.btn_cancel_scan.clicked.connect(self._cancel_scan)
        prog_head.addWidget(self.btn_cancel_scan)
        prog_layout.addLayout(prog_head)

        self.scan_progress_bar = QProgressBar()
        self.scan_progress_bar.setObjectName("cullingScanProgress")
        self.scan_progress_bar.setFixedHeight(8)
        self.scan_progress_bar.setRange(0, 100)
        self.scan_progress_bar.setValue(0)
        self.scan_progress_bar.setTextVisible(False)
        prog_layout.addWidget(self.scan_progress_bar)
        self.progress_frame.setVisible(False)
        layout_folder.addWidget(self.progress_frame)

        self.btn_choose_folder = self.dir_tree.btn_change_root
        self.box_folder = card_folder
        sidebar_layout.addWidget(card_folder)

        # 2. Card: Active Photo & Navigation
        card_photo = QFrame()
        card_photo.setObjectName("cullingSidebarCard")
        layout_photo = QVBoxLayout(card_photo)
        layout_photo.setContentsMargins(6, 6, 6, 6)
        layout_photo.setSpacing(6)

        lbl_sec_photo = QLabel("📷 AKTIVES FOTO")
        lbl_sec_photo.setObjectName("sectionSubTitle")
        lbl_sec_photo.setStyleSheet("font-size: 11px; font-weight: bold;")
        layout_photo.addWidget(lbl_sec_photo)

        self.lbl_active_name = QLabel("Kein Foto ausgewählt")
        self.lbl_active_name.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 500;")
        self.lbl_active_name.setWordWrap(True)
        layout_photo.addWidget(self.lbl_active_name)

        self.lbl_active_path = QLabel("")
        self.lbl_active_path.setStyleSheet("color: #64748b; font-size: 10px;")
        self.lbl_active_path.setWordWrap(True)
        self.lbl_active_path.setVisible(False)
        layout_photo.addWidget(self.lbl_active_path)

        # Badges row
        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(6)
        self.lbl_pair_badge = QLabel("")
        self.lbl_pair_badge.setStyleSheet("background-color: #0284c7; color: white; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
        self.lbl_pair_badge.setVisible(False)
        badges_layout.addWidget(self.lbl_pair_badge)

        self.btn_toggle_raw_jpg = QPushButton("Ansicht: Auto")
        self.btn_toggle_raw_jpg.setObjectName("cullingToggleRawJpg")
        self.btn_toggle_raw_jpg.setToolTip("Zwischen JPEG und RAW Ansicht umschalten (Taste J oder R)")
        self.btn_toggle_raw_jpg.clicked.connect(self._toggle_raw_jpg_view)
        self.btn_toggle_raw_jpg.setVisible(False)
        badges_layout.addWidget(self.btn_toggle_raw_jpg)
        badges_layout.addStretch()
        layout_photo.addLayout(badges_layout)

        # Navigation row
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(4)
        _scheme = self.config.navigation_scheme if self.config else DEFAULT_NAVIGATION_SCHEME
        _prev_lbl, _next_lbl = get_nav_labels(_scheme)
        _hint = get_nav_hint(_scheme)
        self.btn_prev = QPushButton(_prev_lbl)
        self.btn_prev.setObjectName("cullingNavBtn")
        self.btn_prev.setToolTip(f"Vorheriges Foto ({_hint})")
        self.btn_prev.clicked.connect(self._prev_item)
        nav_layout.addWidget(self.btn_prev)

        self.btn_next = QPushButton(_next_lbl)
        self.btn_next.setObjectName("cullingNavBtn")
        self.btn_next.setToolTip(f"Nächstes Foto ({_hint})")
        self.btn_next.clicked.connect(self._next_item)
        nav_layout.addWidget(self.btn_next)
        layout_photo.addLayout(nav_layout)

        # Zoom Button
        self.btn_zoom = QPushButton("100% Schärfelupe [F]")
        self.btn_zoom.setObjectName("cullingZoomBtn")
        self.btn_zoom.setIcon(get_zoom_icon())
        self.btn_zoom.clicked.connect(self._toggle_canvas_zoom)
        layout_photo.addWidget(self.btn_zoom)

        sidebar_layout.addWidget(card_photo)

        # 3. Card: Rating & Culling
        card_rating = QFrame()
        card_rating.setObjectName("cullingSidebarCard")
        layout_rating = QVBoxLayout(card_rating)
        layout_rating.setContentsMargins(6, 6, 6, 6)
        layout_rating.setSpacing(6)

        lbl_sec_rating = QLabel("⭐ BEWERTUNG & CULLING")
        lbl_sec_rating.setObjectName("sectionSubTitle")
        lbl_sec_rating.setStyleSheet("font-size: 11px; font-weight: bold;")
        layout_rating.addWidget(lbl_sec_rating)

        # Stars row
        stars_layout = QHBoxLayout()
        stars_layout.setSpacing(4)
        self.star_buttons = []
        for s in range(1, 6):
            btn = QPushButton(f"{s}★")
            btn.setObjectName("cullingStarBtn")
            btn.setFixedHeight(26)
            btn.setToolTip(f"Mit {s} Stern(en) bewerten (Taste {s})")
            btn.clicked.connect(lambda _, val=s: self.set_current_rating(val))
            stars_layout.addWidget(btn)
            self.star_buttons.append(btn)

        self.btn_star_zero = QPushButton("0")
        self.btn_star_zero.setObjectName("cullingZeroBtn")
        self.btn_star_zero.setFixedSize(26, 26)
        self.btn_star_zero.setToolTip("Bewertung entfernen (Taste 0)")
        self.btn_star_zero.clicked.connect(lambda: self.set_current_rating(0))
        stars_layout.addWidget(self.btn_star_zero)
        layout_rating.addLayout(stars_layout)

        # Pick & Reject row
        pick_rej_layout = QHBoxLayout()
        pick_rej_layout.setSpacing(6)
        self.btn_pick = QPushButton("✔ Behalten [P]")
        self.btn_pick.setObjectName("cullingPickBtn")
        self.btn_pick.clicked.connect(self._toggle_pick)
        pick_rej_layout.addWidget(self.btn_pick)

        self.btn_reject = QPushButton("✖ Ablehnen [X]")
        self.btn_reject.setObjectName("cullingRejectBtn")
        self.btn_reject.clicked.connect(self._toggle_reject)
        pick_rej_layout.addWidget(self.btn_reject)
        layout_rating.addLayout(pick_rej_layout)

        sidebar_layout.addWidget(card_rating)

        # 3b. Card: Workflow & Editing Status
        card_wf = QFrame()
        card_wf.setObjectName("cullingSidebarCard")
        layout_wf = QVBoxLayout(card_wf)
        layout_wf.setContentsMargins(6, 6, 6, 6)
        layout_wf.setSpacing(6)

        wf_head = QHBoxLayout()
        lbl_sec_wf = QLabel("📋 WORKFLOW-STAND")
        lbl_sec_wf.setObjectName("sectionSubTitle")
        lbl_sec_wf.setStyleSheet("font-size: 11px; font-weight: bold;")
        wf_head.addWidget(lbl_sec_wf, stretch=1)

        self.lbl_wf_badge = QLabel("⚪ Ungeprüft")
        self.lbl_wf_badge.setObjectName("cullingWfBadge")
        wf_head.addWidget(self.lbl_wf_badge)
        layout_wf.addLayout(wf_head)

        wf_btn_layout = QHBoxLayout()
        wf_btn_layout.setSpacing(4)

        self.btn_wf_sooc = QPushButton("📸 SOOC [Q]")
        self.btn_wf_sooc.setObjectName("cullingWfBtn")
        self.btn_wf_sooc.setToolTip("Qualität passt direkt aus Kamera (Taste Q)")
        self.btn_wf_sooc.clicked.connect(lambda: self.set_workflow_status("SOOC_OK"))
        wf_btn_layout.addWidget(self.btn_wf_sooc)

        self.btn_wf_to_edit = QPushButton("🎨 Bearb. [B]")
        self.btn_wf_to_edit.setObjectName("cullingWfBtn")
        self.btn_wf_to_edit.setToolTip("Soll noch nachbearbeitet werden (Taste B)")
        self.btn_wf_to_edit.clicked.connect(lambda: self.set_workflow_status("TO_EDIT"))
        wf_btn_layout.addWidget(self.btn_wf_to_edit)

        self.btn_wf_done = QPushButton("✔ Fertig [E]")
        self.btn_wf_done.setObjectName("cullingWfBtn")
        self.btn_wf_done.setToolTip("Bearbeitung abgeschlossen / Exportiert (Taste E)")
        self.btn_wf_done.clicked.connect(lambda: self.set_workflow_status("EDITED"))
        wf_btn_layout.addWidget(self.btn_wf_done)

        layout_wf.addLayout(wf_btn_layout)
        sidebar_layout.addWidget(card_wf)

        # 4. Card: External Editors & Reject Processing
        card_external = QFrame()
        card_external.setObjectName("cullingSidebarCard")
        layout_ext = QVBoxLayout(card_external)
        layout_ext.setContentsMargins(6, 6, 6, 6)
        layout_ext.setSpacing(6)

        lbl_sec_ext = QLabel("🚀 EXTERNE EDITOREN")
        lbl_sec_ext.setObjectName("sectionSubTitle")
        lbl_sec_ext.setStyleSheet("font-size: 11px; font-weight: bold;")
        layout_ext.addWidget(lbl_sec_ext)

        self.btn_darktable = QPushButton("🎨 In Darktable öffnen (RAW) [Strg+D]")
        self.btn_darktable.setObjectName("cullingDarktableBtn")
        self.btn_darktable.setToolTip("Ausgewählte RAW-Dateien direkt an Darktable übergeben")
        self.btn_darktable.clicked.connect(self._launch_darktable)
        layout_ext.addWidget(self.btn_darktable)

        self.btn_topaz = QPushButton("✨ In Topaz Photo öffnen (JPEG) [Strg+T]")
        self.btn_topaz.setObjectName("cullingTopazBtn")
        self.btn_topaz.setToolTip("Ausgewählte JPEG-Dateien direkt an Topaz Photo zur KI-Optimierung übergeben")
        self.btn_topaz.clicked.connect(self._launch_topaz)
        layout_ext.addWidget(self.btn_topaz)

        self.btn_apply_reject = QPushButton("🗑️ Aussortierte verarbeiten")
        self.btn_apply_reject.setObjectName("cullingApplyRejectBtn")
        self.btn_apply_reject.setToolTip("Führt die konfigurierte Aktion für alle mit [X] abgelehnten Fotos aus")
        self.btn_apply_reject.clicked.connect(self._apply_reject_action)
        layout_ext.addWidget(self.btn_apply_reject)

        sidebar_layout.addWidget(card_external)

        # 5. Card: Statistics
        card_stats = QFrame()
        card_stats.setObjectName("cullingSidebarCard")
        layout_stats = QVBoxLayout(card_stats)
        layout_stats.setContentsMargins(6, 6, 6, 6)
        layout_stats.setSpacing(4)

        lbl_sec_stats = QLabel("📊 STATISTIK")
        lbl_sec_stats.setObjectName("sectionSubTitle")
        lbl_sec_stats.setStyleSheet("font-size: 11px; font-weight: bold;")
        layout_stats.addWidget(lbl_sec_stats)

        self.lbl_stats = QLabel("Kein Ordner geöffnet")
        self.lbl_stats.setStyleSheet("color: #64748b; font-size: 11px;")
        self.lbl_stats.setWordWrap(True)
        layout_stats.addWidget(self.lbl_stats)

        sidebar_layout.addWidget(card_stats)

        # 6. Card: Keyboard Shortcuts
        card_keys = QFrame()
        card_keys.setObjectName("cullingSidebarCard")
        layout_keys = QVBoxLayout(card_keys)
        layout_keys.setContentsMargins(6, 6, 6, 6)
        layout_keys.setSpacing(3)

        lbl_sec_keys = QLabel("⌨️ SCHNELLZUGRIFF")
        lbl_sec_keys.setObjectName("sectionSubTitle")
        lbl_sec_keys.setStyleSheet("font-size: 11px; font-weight: bold;")
        layout_keys.addWidget(lbl_sec_keys)

        shortcuts_text = (
            "<span style='color:#0284c7;'>A / D</span> Blättern &nbsp;|&nbsp; "
            "<span style='color:#0284c7;'>1 - 5</span> Sterne &nbsp;|&nbsp; "
            "<span style='color:#0284c7;'>0</span> Reset<br>"
            "<span style='color:#0284c7;'>Q</span> SOOC &nbsp;|&nbsp; "
            "<span style='color:#0284c7;'>B</span> Bearbeiten &nbsp;|&nbsp; "
            "<span style='color:#0284c7;'>E</span> Fertig<br>"
            "<span style='color:#0284c7;'>P</span> Behalten &nbsp;|&nbsp; "
            "<span style='color:#0284c7;'>X</span> Ablehnen &nbsp;|&nbsp; "
            "<span style='color:#0284c7;'>J / R</span> RAW/JPG<br>"
            "<span style='color:#0284c7;'>F</span> 100% Zoom &nbsp;|&nbsp; "
            "<span style='color:#0284c7;'>V</span> Baum &nbsp;|&nbsp; "
            "<span style='color:#0284c7;'>T</span> Filmstreifen &nbsp;|&nbsp; "
            "<span style='color:#0284c7;'>Strg+D/T</span> Editoren"
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

        # Minimal Top Toolbar on the image canvas (Filmstrip Toggle & Photo Details)
        top_strip = QFrame()
        top_strip.setObjectName("cullingCanvasTopStrip")
        strip_layout = QHBoxLayout(top_strip)
        strip_layout.setContentsMargins(4, 2, 4, 2)
        strip_layout.setSpacing(8)

        self.lbl_canvas_name = QLabel("Kein Foto ausgewählt")
        self.lbl_canvas_name.setStyleSheet("color: #64748b; font-weight: 500; font-size: 11px;")
        strip_layout.addWidget(self.lbl_canvas_name)

        self.lbl_canvas_path = QLabel("")
        self.lbl_canvas_path.setObjectName("cullingCanvasPathBadge")
        self.lbl_canvas_path.setVisible(False)
        strip_layout.addWidget(self.lbl_canvas_path)

        self.lbl_canvas_rating = QLabel("")
        self.lbl_canvas_rating.setStyleSheet("color: #d97706; font-size: 11px; font-weight: bold;")
        self.lbl_canvas_rating.setVisible(False)
        strip_layout.addWidget(self.lbl_canvas_rating)

        self.lbl_canvas_meta = QLabel("")
        self.lbl_canvas_meta.setStyleSheet("color: #64748b; font-size: 11px;")
        self.lbl_canvas_meta.setVisible(False)
        strip_layout.addWidget(self.lbl_canvas_meta)

        strip_layout.addStretch()

        is_strip_vis = getattr(self.config, "culling_show_filmstrip", True)
        self.btn_toggle_filmstrip = QPushButton("Filmstreifen ausblenden [T]" if is_strip_vis else "Filmstreifen einblenden [T]")
        self.btn_toggle_filmstrip.setObjectName("cullingToggleFilmstripBtn")
        self.btn_toggle_filmstrip.setIcon(get_filmstrip_icon(size=14))
        self.btn_toggle_filmstrip.setIconSize(QSize(14, 14))
        self.btn_toggle_filmstrip.clicked.connect(self._toggle_filmstrip)
        strip_layout.addWidget(self.btn_toggle_filmstrip)

        workspace_layout.addWidget(top_strip)

        # Canvas: Takes all remaining vertical height!
        self.canvas = CullingCanvasWidget(self)
        self.canvas.toggle_zoom_requested.connect(self._update_zoom_btn_text)
        self.canvas.open_fullscreen_requested.connect(self._open_fullscreen_preview)
        workspace_layout.addWidget(self.canvas, stretch=1)

        # Filmstrip Bar: Docked at bottom (can be collapsed with T)
        self.filmstrip = FilmstripBar(self)
        self.filmstrip.setVisible(is_strip_vis)
        self.filmstrip.item_clicked.connect(self._on_filmstrip_item_clicked)
        self.filmstrip.item_double_clicked.connect(self._open_fullscreen_preview_at_index)
        workspace_layout.addWidget(self.filmstrip)

        self.splitter.addWidget(workspace_container)

        # Splitter sizing: Directory tree ~280px, Controls ~320px, Right canvas gets rest
        if getattr(self.config, "culling_splitter_sizes", None) and len(self.config.culling_splitter_sizes) == 3:
            self.splitter.setSizes(self.config.culling_splitter_sizes)
        else:
            self.splitter.setSizes([280, 320, 1800])
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 1)

        main_layout.addWidget(self.splitter)
        self._set_photo_actions_enabled(False)

    def _set_photo_actions_enabled(self, enabled: bool):
        """Enables or disables photo-specific controls (culling, zoom, rating, workflow, editors)."""
        has_items = enabled and bool(self.filtered_items and 0 <= self.current_idx < len(self.filtered_items))
        self.btn_prev.setEnabled(has_items and self.current_idx > 0)
        self.btn_next.setEnabled(has_items and self.current_idx < len(self.filtered_items) - 1)
        self.btn_zoom.setEnabled(has_items)
        for btn in self.star_buttons:
            btn.setEnabled(has_items)
        if hasattr(self, "btn_star_zero"):
            self.btn_star_zero.setEnabled(has_items)
        self.btn_pick.setEnabled(has_items)
        self.btn_reject.setEnabled(has_items)
        self.btn_wf_sooc.setEnabled(has_items)
        self.btn_wf_to_edit.setEnabled(has_items)
        self.btn_wf_done.setEnabled(has_items)
        if hasattr(self, "btn_darktable"):
            self.btn_darktable.setEnabled(has_items)
        if hasattr(self, "btn_topaz"):
            self.btn_topaz.setEnabled(has_items)
        if hasattr(self, "btn_apply_reject"):
            self.btn_apply_reject.setEnabled(has_items)

    def _on_tree_root_changed(self, new_root: Path):
        self.config.culling_root_folder = str(new_root)
        try:
            self.config.save()
        except Exception:
            pass
        if not self.current_folder or not self.current_folder.exists() or not str(self.current_folder.resolve()).startswith(str(new_root.resolve())):
            self.load_folder(new_root)

    def load_folder(self, folder: Path):
        """Loads and scans photos from folder into the Culling workflow with progress display."""
        if not folder or not folder.exists() or not folder.is_dir():
            return

        self._cancel_scan()

        self.current_folder = folder
        self.lbl_folder_path.setText(str(folder))
        self.config.culling_last_folder = str(folder)
        self.config.save()
        if hasattr(self, "left_dock") and self.left_dock:
            self.left_dock.select_folder(folder)
        elif hasattr(self, "dir_tree") and self.dir_tree:
            self.dir_tree.select_folder(folder)

        # Display progress frame and disable folder buttons while scanning
        self._stop_bar_blinking()
        self.btn_choose_folder.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.scan_progress_bar.setValue(0)
        self.lbl_scan_status.setText("Lese Fotos ein...")
        self.progress_frame.setVisible(True)
        self.lbl_stats.setText("Lese Ordner ein...")
        self.lbl_active_name.setText("Fotos werden eingelesen...")
        self.lbl_active_name.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 500;")
        self.lbl_active_path.setVisible(False)
        self.btn_toggle_raw_jpg.setVisible(False)
        self._set_photo_actions_enabled(False)
        self.canvas.show_placeholder("📁", "Fotos werden eingelesen...", "Verzeichnis wird durchsucht und Metadaten werden eingelesen")

        self._scan_worker = CullingScanWorker(folder, family_album_dir=self.config.family_album_dir, parent=self)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.scan_finished.connect(self._on_scan_finished)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.start()

    def _start_bar_blinking(self):
        """Starts a pulsing/blinking animation on the progress bar while photos & preview load."""
        if not hasattr(self, "_bar_blink_anim"):
            self._bar_opacity_effect = QGraphicsOpacityEffect(self.scan_progress_bar)
            self.scan_progress_bar.setGraphicsEffect(self._bar_opacity_effect)
            self._bar_blink_anim = QPropertyAnimation(self._bar_opacity_effect, b"opacity")
            self._bar_blink_anim.setDuration(700)
            self._bar_blink_anim.setStartValue(1.0)
            self._bar_blink_anim.setKeyValueAt(0.5, 0.25)
            self._bar_blink_anim.setEndValue(1.0)
            self._bar_blink_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
            self._bar_blink_anim.setLoopCount(-1)
        self._bar_opacity_effect.setOpacity(1.0)
        self._bar_blink_anim.start()

    def _stop_bar_blinking(self):
        """Stops the progress bar blinking animation and restores full opacity."""
        if hasattr(self, "_bar_blink_anim") and self._bar_blink_anim.state() == QPropertyAnimation.State.Running:
            self._bar_blink_anim.stop()
        if hasattr(self, "_bar_opacity_effect"):
            self._bar_opacity_effect.setOpacity(1.0)

    def _on_scan_progress(self, cur: int, total: int, filename: str):
        pct = int(cur / total * 100) if total > 0 else 0
        self.scan_progress_bar.setValue(pct)
        self.lbl_scan_status.setText(f"Lese Fotos ein: {cur} von {total} ({pct}%) • {filename}")
        self.lbl_stats.setText(f"Lese Fotos ein: {cur}/{total} ({pct}%)")

    def _on_scan_finished(self, items: List[CullingItem]):
        self.items = items
        self._preview_cache.clear()
        self._prefetched_paths.clear()
        self.scan_progress_bar.setValue(100)
        self.lbl_scan_status.setText(f"Lese Fotos ein: {len(items)} Fotos gefunden – lade Vorschau...")
        self.lbl_stats.setText(f"{len(items)} Fotos gefunden – lade Vorschau...")
        self.canvas.show_placeholder("⏳", "Vorschau wird vorbereitet...", "Ansicht und erstes Foto werden geladen")
        self._start_bar_blinking()
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

        self.left_dock.update_folder_items(items)
        self._apply_filter(keep_current=False)

        self._stop_bar_blinking()
        self.progress_frame.setVisible(False)
        self.btn_choose_folder.setEnabled(True)
        self.btn_refresh.setEnabled(True)

    def _on_filter_changed(self, criteria: CullingFilterCriteria):
        self._current_filter = criteria
        self._apply_filter(keep_current=True)

    def _apply_filter(self, keep_current: bool = True):
        current_item = (
            self.filtered_items[self.current_idx]
            if (0 <= self.current_idx < len(self.filtered_items))
            else None
        )

        if self._current_filter and self._current_filter.is_active():
            self.filtered_items = [it for it in self.items if self._current_filter.matches(it)]
        else:
            self.filtered_items = list(self.items)

        self.left_dock.update_match_stats(len(self.filtered_items), len(self.items))
        self._update_stats_label()

        if self.filtered_items:
            new_idx = 0
            if keep_current and current_item and current_item in self.filtered_items:
                new_idx = self.filtered_items.index(current_item)
            self.filmstrip.set_items(self.filtered_items, new_idx)
            self.set_current_index(new_idx)
        else:
            self.current_idx = -1
            self.filmstrip.set_items([], -1)
            self.canvas.show_placeholder("🔍", "Keine Fotos entsprechen dem Filter", "Passen Sie die Filterkriterien im linken Dock an")
            self.lbl_active_name.setText("Keine Fotos entsprechen dem Filter")
            self.lbl_active_name.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 500;")
            self.lbl_active_path.setVisible(False)
            self.lbl_pair_badge.setVisible(False)
            self.btn_toggle_raw_jpg.setVisible(False)
            self.lbl_canvas_name.setText("Keine Fotos entsprechen dem Filter")
            self.lbl_canvas_name.setStyleSheet("color: #64748b; font-weight: 500; font-size: 11px;")
            self.lbl_canvas_path.setVisible(False)
            self.lbl_canvas_rating.setVisible(False)
            self.lbl_canvas_meta.setVisible(False)
            self._set_photo_actions_enabled(False)

    def _on_scan_error(self, err_msg: str):
        self._stop_bar_blinking()
        self.progress_frame.setVisible(False)
        self.btn_choose_folder.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        self.canvas.show_placeholder("⚠️", "Fehler beim Einlesen", err_msg)
        QMessageBox.critical(self, "Fehler beim Einlesen", f"Fehler beim Scannen des Ordners:\n{err_msg}")
        self.lbl_active_name.setText("Fehler beim Laden")
        self.lbl_stats.setText("Fehler beim Laden")

    def _cancel_scan(self):
        self._stop_bar_blinking()
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
        if hasattr(self, "left_dock") and self.left_dock:
            self.left_dock.toggle_collapse()

    def _on_choose_folder_clicked(self):
        start_dir = str(self.current_folder) if self.current_folder else self.config.target_dir
        folder = QFileDialog.getExistingDirectory(self, "Ordner zum Sichten wählen", start_dir)
        if folder:
            self.load_folder(Path(folder))

    def set_current_index(self, idx: int):
        if not self.filtered_items or not (0 <= idx < len(self.filtered_items)):
            self.current_idx = -1
            self.canvas.set_pixmap(None)
            return
        self.current_idx = idx
        self.filmstrip.set_current_index(idx)
        self._render_current_item()

    def apply_config(self):
        """Applies updated configuration options, navigation keys, and re-renders active photo."""
        scheme = self.config.navigation_scheme if self.config else DEFAULT_NAVIGATION_SCHEME
        prev_lbl, next_lbl = get_nav_labels(scheme)
        hint = get_nav_hint(scheme)
        self.btn_prev.setText(prev_lbl)
        self.btn_next.setText(next_lbl)
        self.btn_prev.setToolTip(f"Vorheriges Foto ({hint})")
        self.btn_next.setToolTip(f"Nächstes Foto ({hint})")
        self._render_current_item()

    def _render_current_item(self):
        if not self.filtered_items or not (0 <= self.current_idx < len(self.filtered_items)):
            self._set_photo_actions_enabled(False)
            return

        self._set_photo_actions_enabled(True)
        it = self.filtered_items[self.current_idx]

        # Display preferences from AppConfig
        cfg = self.config
        show_name = cfg.single_view_show_filename if cfg else True
        show_ext = cfg.single_view_show_extension if cfg else True
        show_ratings = cfg.single_view_show_ratings if cfg else True
        show_path = cfg.single_view_show_path if cfg else True
        show_cam = cfg.single_view_show_camera_lens if cfg else True
        show_exp = cfg.single_view_show_exposure if cfg else True

        if show_name and show_ext:
            disp_name = it.primary_path.name
        elif show_name:
            disp_name = it.primary_path.stem
        elif show_ext:
            disp_name = it.primary_path.suffix.upper()
        else:
            disp_name = ""

        filter_tag = " [Filter aktiv]" if (self._current_filter and self._current_filter.is_active()) else ""
        cnt_str = f"({self.current_idx + 1} von {len(self.filtered_items)})"
        self.lbl_active_name.setText(f"{disp_name} {cnt_str}{filter_tag}" if disp_name else f"{cnt_str}{filter_tag}")
        self.lbl_active_name.setStyleSheet("font-weight: bold; font-size: 12px; color: #f8fafc;")

        parent_dir = str(it.primary_path.parent)
        self.lbl_active_path.setText(f"📁 {parent_dir}")
        self.lbl_active_path.setVisible(show_path)

        # Canvas top strip updates
        self.lbl_canvas_name.setText(disp_name)
        self.lbl_canvas_name.setStyleSheet("color: #38bdf8; font-weight: 600; font-size: 12px;")
        self.lbl_canvas_name.setVisible(bool(disp_name))

        self.lbl_canvas_path.setText(f"📁 {parent_dir}")
        self.lbl_canvas_path.setToolTip(f"Speicherort:\n{it.primary_path}")
        self.lbl_canvas_path.setVisible(show_path)

        r_str = "★" * it.rating if it.rating > 0 else "0★"
        rej_str = " [X]" if it.is_rejected else ""
        _, _, wf_sym = it.workflow_status_info
        wf_display = f" {wf_sym}" if wf_sym != "⚪" else ""
        self.lbl_canvas_rating.setText(f"{r_str}{rej_str}{wf_display}".strip())
        self.lbl_canvas_rating.setVisible(show_ratings)

        cam_lens = []
        if it.metadata:
            cam = it.metadata.camera_name or it.metadata.camera_model
            lens = it.metadata.lens_model
            exp = it.metadata.formatted_exposure
            if show_cam and cam:
                cam_lens.append(f"📷 {cam}")
            if show_cam and lens:
                cam_lens.append(lens)
            if show_exp and exp:
                cam_lens.append(exp)
        self.lbl_canvas_meta.setText(" • ".join(cam_lens))
        self.lbl_canvas_meta.setVisible(bool(cam_lens))

        if it.is_pair:
            self.lbl_pair_badge.setText(f"RAW+JPG ({it.active_view_mode})")
            self.lbl_pair_badge.setVisible(True)
            self.btn_toggle_raw_jpg.setVisible(True)
            self.btn_toggle_raw_jpg.setText(f"Ansicht: {it.active_view_mode}")
        else:
            self.lbl_pair_badge.setVisible(False)
            self.btn_toggle_raw_jpg.setVisible(False)

        # Highlight current rating buttons (theme adaptive)
        from gui_qt.styles.theme import theme_manager
        is_light = (theme_manager.effective_theme == "light")
        inactive_bg = "#ffffff" if is_light else "#1e293b"
        inactive_border = "#cbd5e1" if is_light else "#334155"
        inactive_color = "#d97706" if is_light else "#fbbf24"
        inactive_text = "#475569" if is_light else "#94a3b8"

        for s_idx, btn in enumerate(self.star_buttons, 1):
            if s_idx <= it.rating:
                btn.setStyleSheet("background-color: #d97706; color: white; border: 1px solid #f59e0b; border-radius: 4px; font-weight: bold;")
            else:
                btn.setStyleSheet(f"background-color: {inactive_bg}; color: {inactive_color}; border: 1px solid {inactive_border}; border-radius: 4px; font-weight: bold;")

        # Workflow Status Badge & Buttons
        status_label, status_color, status_symbol = it.workflow_status_info
        if it.family_album_exported:
            self.lbl_wf_badge.setText(f"{status_symbol} Album-Export")
            self.lbl_wf_badge.setStyleSheet("background-color: #065f46; color: #a7f3d0; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
            self.lbl_wf_badge.setToolTip(f"Exportiert im Familienalbum:\n{it.family_album_path}")
        elif it.has_darktable_edit:
            self.lbl_wf_badge.setText(f"{status_symbol} {status_label} (Darktable)")
            self.lbl_wf_badge.setStyleSheet(f"background-color: {status_color}; color: white; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
            self.lbl_wf_badge.setToolTip("In Darktable bearbeitet (Darktable-History in XMP erkannt)")
        else:
            self.lbl_wf_badge.setText(f"{status_symbol} {status_label}")
            self.lbl_wf_badge.setStyleSheet(f"background-color: {status_color}; color: white; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;")
            self.lbl_wf_badge.setToolTip(f"Workflow-Status: {status_label}")

        wf = it.workflow_status
        self.btn_wf_sooc.setStyleSheet(
            "background-color: #0284c7; color: white; border: 1px solid #0369a1; border-radius: 4px; padding: 5px; font-weight: bold; font-size: 11px;"
            if wf == "SOOC_OK" else
            f"background-color: {inactive_bg}; color: {inactive_text}; border: 1px solid {inactive_border}; border-radius: 4px; padding: 5px; font-size: 11px;"
        )
        self.btn_wf_to_edit.setStyleSheet(
            "background-color: #d97706; color: white; border: 1px solid #f59e0b; border-radius: 4px; padding: 5px; font-weight: bold; font-size: 11px;"
            if wf == "TO_EDIT" else
            f"background-color: {inactive_bg}; color: {inactive_text}; border: 1px solid {inactive_border}; border-radius: 4px; padding: 5px; font-size: 11px;"
        )
        self.btn_wf_done.setStyleSheet(
            "background-color: #059669; color: white; border: 1px solid #10b981; border-radius: 4px; padding: 5px; font-weight: bold; font-size: 11px;"
            if wf == "EDITED" else
            f"background-color: {inactive_bg}; color: {inactive_text}; border: 1px solid {inactive_border}; border-radius: 4px; padding: 5px; font-size: 11px;"
        )

        # Pick / Reject buttons state
        if it.is_rejected:
            self.btn_reject.setStyleSheet("background-color: #dc2626; color: white; border: 1px solid #ef4444; border-radius: 4px; font-weight: bold;")
        else:
            rej_bg = "#fef2f2" if is_light else "#7f1d1d"
            rej_color = "#b91c1c" if is_light else "#fca5a5"
            rej_border = "#fca5a5" if is_light else "#b91c1c"
            self.btn_reject.setStyleSheet(f"background-color: {rej_bg}; color: {rej_color}; border: 1px solid {rej_border}; border-radius: 4px; font-weight: 600;")

        # Load Preview Image (LRU memory cache, low-res instant placeholder, lookahead prefetching)
        disp_path = it.current_display_path
        disp_key = str(disp_path)

        if disp_key in self._preview_cache:
            pix = self._preview_cache[disp_key]
            self._preview_cache.move_to_end(disp_key)
            self.canvas.set_pixmap(pix, keep_zoom=False)
        else:
            # Show filmstrip thumbnail immediately as low-res placeholder so canvas is never blank
            if hasattr(self, "filmstrip") and disp_key in self.filmstrip._thumb_cache:
                low_res = self.filmstrip._thumb_cache[disp_key]
                self.canvas.set_pixmap(low_res, keep_zoom=False)

            pil_img = load_preview_image(disp_path, max_dim=3840)
            if pil_img:
                if pil_img.mode != "RGB":
                    pil_img = pil_img.convert("RGB")
                data = pil_img.tobytes("raw", "RGB")
                qimg = QImage(data, pil_img.width, pil_img.height, pil_img.width * 3, QImage.Format.Format_RGB888)
                pix = QPixmap.fromImage(qimg)
                self._add_to_preview_cache(disp_key, pix)
                self.canvas.set_pixmap(pix, keep_zoom=False)
            else:
                self.canvas.set_pixmap(None)

        # Trigger background lookahead prefetching for adjacent images
        self._prefetch_adjacent_previews(self.current_idx)

    def _add_to_preview_cache(self, key: str, pix: QPixmap):
        self._preview_cache[key] = pix
        self._preview_cache.move_to_end(key)
        while len(self._preview_cache) > self._max_preview_cache_size:
            self._preview_cache.popitem(last=False)

    def _prefetch_adjacent_previews(self, current_idx: int):
        if not self.filtered_items:
            return
        # Prefetch next 2 items and previous 1 item
        for offset in (1, -1, 2):
            idx = current_idx + offset
            if 0 <= idx < len(self.filtered_items):
                target_it = self.filtered_items[idx]
                p_str = str(target_it.current_display_path)
                if p_str not in self._preview_cache and p_str not in self._prefetched_paths:
                    self._prefetched_paths.add(p_str)
                    task = PreviewTask(
                        path=target_it.current_display_path,
                        key_path=p_str,
                        signals=self._preview_signals,
                        max_dim=3840
                    )
                    QThreadPool.globalInstance().start(task)

    def _on_preview_ready(self, path_str: str, qimage: QImage):
        self._prefetched_paths.discard(path_str)
        if qimage and not qimage.isNull():
            pix = QPixmap.fromImage(qimage)
            self._add_to_preview_cache(path_str, pix)
            if 0 <= self.current_idx < len(self.filtered_items):
                cur_p = str(self.filtered_items[self.current_idx].current_display_path)
                if cur_p == path_str:
                    self.canvas.set_pixmap(pix, keep_zoom=True)

    def set_current_rating(self, stars: int):
        if not self.filtered_items or not (0 <= self.current_idx < len(self.filtered_items)):
            return
        it = self.filtered_items[self.current_idx]
        it.rating = stars
        if stars > 0:
            it.is_rejected = False
        sync_pair_xmp(it.primary_path, it.companion_path, rating=it.rating, label=it.color_label, is_rejected=it.is_rejected, workflow_status=it.workflow_status)
        self.filmstrip.update_card(self.current_idx, it)
        self._render_current_item()
        self._update_stats_label()

    def _toggle_pick(self):
        if not self.filtered_items or not (0 <= self.current_idx < len(self.filtered_items)):
            return
        it = self.filtered_items[self.current_idx]
        it.is_picked = not it.is_picked
        if it.is_picked:
            it.is_rejected = False
            if it.rating == 0:
                it.rating = 3
        sync_pair_xmp(it.primary_path, it.companion_path, rating=it.rating, label=it.color_label, is_rejected=it.is_rejected, workflow_status=it.workflow_status)
        self.filmstrip.update_card(self.current_idx, it)
        self._render_current_item()
        self._update_stats_label()

    def _toggle_reject(self):
        if not self.filtered_items or not (0 <= self.current_idx < len(self.filtered_items)):
            return
        it = self.filtered_items[self.current_idx]
        it.is_rejected = not it.is_rejected
        if it.is_rejected:
            it.is_picked = False
            it.rating = 0
        sync_pair_xmp(it.primary_path, it.companion_path, rating=it.rating, label=it.color_label, is_rejected=it.is_rejected, workflow_status=it.workflow_status)
        self.filmstrip.update_card(self.current_idx, it)
        self._render_current_item()
        self._update_stats_label()

    def set_workflow_status(self, status: str):
        if not self.filtered_items or not (0 <= self.current_idx < len(self.filtered_items)):
            return
        it = self.filtered_items[self.current_idx]
        # Toggle off back to UNCHECKED if clicking the same active status
        if it.workflow_status == status:
            it.workflow_status = "UNCHECKED"
        else:
            it.workflow_status = status

        sync_pair_xmp(
            it.primary_path,
            it.companion_path,
            rating=it.rating,
            label=it.color_label,
            is_rejected=it.is_rejected,
            workflow_status=it.workflow_status
        )
        self.filmstrip.update_card(self.current_idx, it)
        self._render_current_item()
        self._update_stats_label()

        if self._current_filter and self._current_filter.workflow_status != "ALL":
            self._apply_filter(keep_current=True)

    def _toggle_raw_jpg_view(self):
        if not self.filtered_items or not (0 <= self.current_idx < len(self.filtered_items)):
            return
        it = self.filtered_items[self.current_idx]
        if not it.is_pair:
            return

        order = ["AUTO", "RAW", "JPG"]
        next_mode = order[(order.index(it.active_view_mode) + 1) % len(order)]
        it.active_view_mode = next_mode
        self._render_current_item()

    def _toggle_canvas_zoom(self):
        mode = self.canvas.toggle_zoom()
        if mode == "actual":
            self.btn_zoom.setText("Einpassen [F]")
            self.btn_zoom.setIcon(get_zoom_fit_icon())
        else:
            self.btn_zoom.setText("100% Zoom [F]")
            self.btn_zoom.setIcon(get_zoom_icon())

    def _update_zoom_btn_text(self):
        mode = self.canvas._zoom_mode
        if mode == "actual":
            self.btn_zoom.setText("Einpassen [F]")
            self.btn_zoom.setIcon(get_zoom_fit_icon())
        else:
            self.btn_zoom.setText("100% Zoom [F]")
            self.btn_zoom.setIcon(get_zoom_icon())

    def _open_fullscreen_preview(self):
        self._open_fullscreen_preview_at_index(self.current_idx)

    def _open_fullscreen_preview_at_index(self, index: int):
        if not self.filtered_items or index < 0 or index >= len(self.filtered_items):
            return
        from gui_qt.dialogs.quick_preview_dialog import QuickPreviewDialog
        self.current_idx = index
        self.filmstrip.set_current_index(index)
        self._render_current_item()
        dlg = QuickPreviewDialog(
            items=self.filtered_items,
            start_index=index,
            parent=self,
            config=self.config,
            fullscreen=True
        )
        dlg.selection_changed.connect(self._on_fullscreen_selection_changed)
        dlg.exec()
        # Sync index when returning
        if 0 <= dlg.current_idx < len(self.filtered_items):
            self.current_idx = dlg.current_idx
            self.filmstrip.set_current_index(self.current_idx)
            self._render_current_item()

    def _on_fullscreen_selection_changed(self):
        if 0 <= self.current_idx < len(self.filtered_items):
            self.filmstrip.update_card(self.current_idx, self.filtered_items[self.current_idx])

    def _prev_item(self):
        if self.filtered_items and self.current_idx > 0:
            self.set_current_index(self.current_idx - 1)

    def _next_item(self):
        if self.filtered_items and self.current_idx < len(self.filtered_items) - 1:
            self.set_current_index(self.current_idx + 1)

    def _on_filmstrip_item_clicked(self, idx: int):
        self.set_current_index(idx)

    def _launch_darktable(self):
        """Passes RAW files of current selection (or all 3★+ picked) to Darktable."""
        pool = self.filtered_items if self.filtered_items else self.items
        if not pool:
            QMessageBox.information(self, "Keine Fotos", "Es sind keine Fotos zum Übergeben geladen.")
            return

        # Prefer 3+ star items or current item if none picked
        targets = [it for it in pool if it.rating >= 3 and not it.is_rejected]
        if not targets and 0 <= self.current_idx < len(self.filtered_items):
            targets = [self.filtered_items[self.current_idx]]

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
        pool = self.filtered_items if self.filtered_items else self.items
        if not pool:
            QMessageBox.information(self, "Keine Fotos", "Es sind keine Fotos zum Übergeben geladen.")
            return

        targets = [it for it in pool if it.rating >= 3 and not it.is_rejected]
        if not targets and 0 <= self.current_idx < len(self.filtered_items):
            targets = [self.filtered_items[self.current_idx]]

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
        filtered_cnt = len(self.filtered_items)
        rated = sum(1 for it in self.items if it.rating > 0)
        rejected = sum(1 for it in self.items if it.is_rejected)
        picked = sum(1 for it in self.items if it.is_picked or it.rating >= 3)
        sooc_cnt = sum(1 for it in self.items if it.workflow_status == "SOOC_OK")
        to_edit_cnt = sum(1 for it in self.items if it.workflow_status == "TO_EDIT")
        edited_cnt = sum(1 for it in self.items if it.workflow_status == "EDITED")

        wf_stat = f"📸 SOOC: {sooc_cnt} | 🎨 Bearb.: {to_edit_cnt} | ✔ Fertig: {edited_cnt}"
        if self._current_filter and self._current_filter.is_active():
            self.lbl_stats.setText(f"Filter: {filtered_cnt} von {total} Fotos | {wf_stat} | ★★★+: {picked} | [X]: {rejected}")
        else:
            self.lbl_stats.setText(f"Gesamt: {total} Fotos | {wf_stat} | ★★★+: {picked} | [X]: {rejected}")

    def _toggle_filmstrip(self):
        is_vis = not self.filmstrip.isVisible()
        self.filmstrip.setVisible(is_vis)
        self.btn_toggle_filmstrip.setText("Filmstreifen ausblenden [T]" if is_vis else "Filmstreifen einblenden [T]")
        self.btn_toggle_filmstrip.setIcon(get_filmstrip_icon("#38bdf8" if is_vis else "#94a3b8", 14))
        self.config.culling_show_filmstrip = is_vis
        try:
            self.config.save()
        except Exception:
            pass

    def save_state(self):
        """Persists current UI splitter and dock sizes."""
        if hasattr(self, "splitter") and self.splitter:
            sizes = self.splitter.sizes()
            if len(sizes) == 3 and not any(s == 0 for s in sizes):
                self.config.culling_splitter_sizes = sizes

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
        scheme = self.config.navigation_scheme if self.config else DEFAULT_NAVIGATION_SCHEME
        if is_nav_prev(key, scheme):
            self._prev_item()
            return
        elif is_nav_next(key, scheme):
            self._next_item()
            return
        # Rating 0-5
        elif key in (Qt.Key.Key_0, Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4, Qt.Key.Key_5):
            val = key - Qt.Key.Key_0
            self.set_current_rating(val)
            return
        # Workflow Status
        elif key == Qt.Key.Key_Q:
            self.set_workflow_status("SOOC_OK")
            return
        elif key == Qt.Key.Key_B:
            self.set_workflow_status("TO_EDIT")
            return
        elif key == Qt.Key.Key_E:
            self.set_workflow_status("EDITED")
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

