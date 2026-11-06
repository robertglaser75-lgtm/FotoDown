"""Left collapsible navigation dock for Tab 2: Sichten & Sortieren.

Holds two navigation tabs:
1. "Verzeichnisse" (Hierarchical folder tree with Total, RAW, and JPEG counts)
2. "Ordner & Quellverzeichnis" (Direct folder picker with live scan progress)

Can be smoothly collapsed "nach Links" into a slim 36px vertical dock bar,
preserving maximum width for the image canvas on Ultrawide and standard screens.
"""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget
)

from core.config import AppConfig
from gui_qt.styles.icons import (
    get_collapse_panel_icon, get_expand_panel_icon, get_folder_icon, get_refresh_icon
)
from gui_qt.views.culling_tree import CullingDirectoryTreeWidget


class CullingFolderSourceWidget(QWidget):
    """Direct folder selector view with scan progress display."""
    folder_selected = Signal(Path)
    refresh_requested = Signal()
    cancel_scan_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_folder: Optional[Path] = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(8, 8, 8, 8)
        c_layout.setSpacing(8)

        lbl_head = QLabel("ORDNER & QUELLVERZEICHNIS")
        lbl_head.setStyleSheet("font-size: 11px; font-weight: bold; color: #94a3b8;")
        c_layout.addWidget(lbl_head)

        btns_layout = QHBoxLayout()
        btns_layout.setSpacing(6)

        self.btn_choose_folder = QPushButton("Ordner wählen...")
        self.btn_choose_folder.setIcon(get_folder_icon("#38bdf8", 14))
        self.btn_choose_folder.setIconSize(QSize(14, 14))
        self.btn_choose_folder.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; color: #f8fafc; border: 1px solid #334155;
                border-radius: 4px; padding: 6px 12px; font-weight: 500; font-size: 12px;
            }
            QPushButton:hover { background-color: #334155; }
        """)
        self.btn_choose_folder.clicked.connect(self._on_choose_clicked)
        btns_layout.addWidget(self.btn_choose_folder, stretch=1)

        self.btn_refresh = QPushButton()
        self.btn_refresh.setIcon(get_refresh_icon("#cbd5e1", 14))
        self.btn_refresh.setIconSize(QSize(14, 14))
        self.btn_refresh.setFixedSize(30, 30)
        self.btn_refresh.setToolTip("Ordner neu scannen")
        self.btn_refresh.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 4px;")
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        btns_layout.addWidget(self.btn_refresh)
        c_layout.addLayout(btns_layout)

        self.lbl_folder_path = QLabel("Kein Ordner ausgewählt")
        self.lbl_folder_path.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 500;")
        self.lbl_folder_path.setWordWrap(True)
        c_layout.addWidget(self.lbl_folder_path)

        # Scanning Progress Frame
        self.progress_frame = QFrame()
        self.progress_frame.setStyleSheet("""
            QFrame {
                background-color: #0b1329;
                border: 1px solid #1d4ed8;
                border-radius: 6px;
                padding: 6px 8px;
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
        self.btn_cancel_scan.clicked.connect(self.cancel_scan_requested.emit)
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
        c_layout.addWidget(self.progress_frame)

        c_layout.addStretch()
        layout.addWidget(card)

    def _on_choose_clicked(self):
        initial = str(self.current_folder) if self.current_folder else str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Ordner zum Sichten wählen", initial)
        if chosen:
            p = Path(chosen)
            self.set_folder_path(p)
            self.folder_selected.emit(p)

    def set_folder_path(self, folder: Path):
        self.current_folder = folder
        self.lbl_folder_path.setText(str(folder))

    def set_progress(self, cur: int, total: int, filename: str):
        pct = int(cur / total * 100) if total > 0 else 0
        self.scan_progress_bar.setValue(pct)
        self.lbl_scan_status.setText(f"Lese Fotos ein: {cur} von {total} ({pct}%) • {filename}")

    def show_progress(self, visible: bool):
        self.progress_frame.setVisible(visible)
        self.btn_choose_folder.setEnabled(not visible)
        self.btn_refresh.setEnabled(not visible)


class CullingLeftNavigationDock(QWidget):
    """Collapsible Left Dock containing 'Verzeichnisse' tree and 'Ordner & Quellverzeichnis'."""
    folder_selected = Signal(Path)
    toggled = Signal(bool)

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.is_collapsed: bool = False
        self.expanded_width: int = 320

        self._init_ui()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # -------------------------------------------------------------
        # 1. COLLAPSED STRIP (Slim 36px bar visible when collapsed to left)
        # -------------------------------------------------------------
        self.collapsed_strip = QFrame()
        self.collapsed_strip.setStyleSheet("""
            QFrame {
                background-color: #090d16;
                border-right: 1px solid #1e293b;
            }
        """)
        self.collapsed_strip.setFixedWidth(36)
        strip_layout = QVBoxLayout(self.collapsed_strip)
        strip_layout.setContentsMargins(3, 6, 3, 6)
        strip_layout.setSpacing(8)
        strip_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.btn_strip_expand = QPushButton()
        self.btn_strip_expand.setIcon(get_expand_panel_icon("#38bdf8", 14))
        self.btn_strip_expand.setIconSize(QSize(14, 14))
        self.btn_strip_expand.setFixedSize(28, 28)
        self.btn_strip_expand.setToolTip("Verzeichnis-Panel nach rechts ausklappen [V]")
        self.btn_strip_expand.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; border: 1px solid #38bdf8;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)
        self.btn_strip_expand.clicked.connect(self.expand_panel)
        strip_layout.addWidget(self.btn_strip_expand)

        # Separator line
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #1e293b;")
        strip_layout.addWidget(sep)

        # Icon button for Tab 0: Tree
        self.btn_strip_tree = QPushButton()
        self.btn_strip_tree.setIcon(get_folder_icon("#38bdf8", 16))
        self.btn_strip_tree.setIconSize(QSize(16, 16))
        self.btn_strip_tree.setFixedSize(28, 28)
        self.btn_strip_tree.setToolTip("Verzeichnisbaum öffnen (Klicken zum Ausklappen)")
        self.btn_strip_tree.setStyleSheet("""
            QPushButton {
                background-color: transparent; border: 1px solid transparent;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1e293b; border-color: #334155; }
        """)
        self.btn_strip_tree.clicked.connect(lambda: self.expand_and_switch_tab(0))
        strip_layout.addWidget(self.btn_strip_tree)

        # Icon button for Tab 1: Direct Folder Source
        self.btn_strip_folder = QPushButton()
        self.btn_strip_folder.setIcon(get_folder_icon("#94a3b8", 16))
        self.btn_strip_folder.setIconSize(QSize(16, 16))
        self.btn_strip_folder.setFixedSize(28, 28)
        self.btn_strip_folder.setToolTip("Ordner & Quellverzeichnis öffnen (Klicken zum Ausklappen)")
        self.btn_strip_folder.setStyleSheet("""
            QPushButton {
                background-color: transparent; border: 1px solid transparent;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1e293b; border-color: #334155; }
        """)
        self.btn_strip_folder.clicked.connect(lambda: self.expand_and_switch_tab(1))
        strip_layout.addWidget(self.btn_strip_folder)

        strip_layout.addStretch()
        self.collapsed_strip.setVisible(False)
        main_layout.addWidget(self.collapsed_strip)

        # -------------------------------------------------------------
        # 2. EXPANDED CONTAINER (Full width panel with Tabs & Views)
        # -------------------------------------------------------------
        self.expanded_container = QWidget()
        exp_layout = QVBoxLayout(self.expanded_container)
        exp_layout.setContentsMargins(0, 0, 0, 0)
        exp_layout.setSpacing(4)

        # Top Tab Bar & Collapse Button
        header_bar = QFrame()
        header_bar.setStyleSheet("""
            QFrame {
                background-color: #070a12;
                border-bottom: 1px solid #1e293b;
                padding: 2px 4px;
            }
        """)
        h_layout = QHBoxLayout(header_bar)
        h_layout.setContentsMargins(4, 3, 4, 3)
        h_layout.setSpacing(4)

        self.btn_tab_tree = QPushButton("Verzeichnisse")
        self.btn_tab_tree.setIcon(get_folder_icon("#38bdf8", 13))
        self.btn_tab_tree.setIconSize(QSize(13, 13))
        self.btn_tab_tree.setCheckable(True)
        self.btn_tab_tree.setChecked(True)
        self.btn_tab_tree.setToolTip("Interaktiver Verzeichnisbaum mit Zählern")
        self.btn_tab_tree.clicked.connect(lambda: self.switch_tab(0))
        h_layout.addWidget(self.btn_tab_tree)

        self.btn_tab_folder = QPushButton("Quellordner")
        self.btn_tab_folder.setIcon(get_folder_icon("#94a3b8", 13))
        self.btn_tab_folder.setIconSize(QSize(13, 13))
        self.btn_tab_folder.setCheckable(True)
        self.btn_tab_folder.setChecked(False)
        self.btn_tab_folder.setToolTip("Ordner & Quellverzeichnis direkt wählen")
        self.btn_tab_folder.clicked.connect(lambda: self.switch_tab(1))
        h_layout.addWidget(self.btn_tab_folder)

        self.tab_group = QButtonGroup(self)
        self.tab_group.addButton(self.btn_tab_tree, 0)
        self.tab_group.addButton(self.btn_tab_folder, 1)

        h_layout.addStretch()

        # Collapse Button: Folds this panel left
        self.btn_collapse = QPushButton()
        self.btn_collapse.setIcon(get_collapse_panel_icon("#cbd5e1", 14))
        self.btn_collapse.setIconSize(QSize(14, 14))
        self.btn_collapse.setFixedSize(26, 24)
        self.btn_collapse.setToolTip("Nach links zusammenklappen [V]")
        self.btn_collapse.setStyleSheet("""
            QPushButton {
                background-color: #1e293b; border: 1px solid #334155;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #334155; }
        """)
        self.btn_collapse.clicked.connect(self.collapse_panel)
        h_layout.addWidget(self.btn_collapse)

        exp_layout.addWidget(header_bar)

        # Stacked Views
        self.stack = QStackedWidget()

        # Tab 0: Directory Tree
        self.tree_view = CullingDirectoryTreeWidget(self.config, self)
        self.tree_view.folder_selected.connect(self.folder_selected.emit)
        self.tree_view.collapse_panel_requested.connect(self.collapse_panel)
        self.stack.addWidget(self.tree_view)

        # Tab 1: Folder & Source Chooser
        self.folder_view = CullingFolderSourceWidget(self)
        self.folder_view.folder_selected.connect(self.folder_selected.emit)
        self.stack.addWidget(self.folder_view)

        self._update_tab_styles()

        exp_layout.addWidget(self.stack, stretch=1)
        main_layout.addWidget(self.expanded_container)

        self.setMinimumWidth(260)
        self.setMaximumWidth(480)

    def _update_tab_styles(self):
        style_active = """
            QPushButton {
                background-color: #1e293b; color: #38bdf8; border: 1px solid #0284c7;
                border-radius: 4px; padding: 4px 8px; font-size: 11px; font-weight: 600;
            }
        """
        style_inactive = """
            QPushButton {
                background-color: transparent; color: #94a3b8; border: 1px solid transparent;
                border-radius: 4px; padding: 4px 8px; font-size: 11px; font-weight: 500;
            }
            QPushButton:hover { background-color: #1e293b; }
        """
        self.btn_tab_tree.setStyleSheet(style_active if self.stack.currentIndex() == 0 else style_inactive)
        self.btn_tab_folder.setStyleSheet(style_active if self.stack.currentIndex() == 1 else style_inactive)

    def switch_tab(self, idx: int):
        self.stack.setCurrentIndex(idx)
        self.btn_tab_tree.setChecked(idx == 0)
        self.btn_tab_folder.setChecked(idx == 1)
        self._update_tab_styles()

    def expand_and_switch_tab(self, idx: int):
        self.switch_tab(idx)
        self.expand_panel()

    def collapse_panel(self):
        """Folds the panel completely to the left into the 36px dock strip."""
        if self.is_collapsed:
            return
        self.is_collapsed = True
        self.expanded_width = self.width() if self.width() > 100 else 320
        self.expanded_container.setVisible(False)
        self.collapsed_strip.setVisible(True)

        self.setMinimumWidth(36)
        self.setMaximumWidth(36)
        self.resize(36, self.height())

        parent = self.parentWidget()
        if parent and hasattr(parent, 'setSizes'):
            sizes = parent.sizes()
            if len(sizes) >= 3:
                parent.setSizes([36, sizes[1] + (self.expanded_width - 36), sizes[2]])

        self.toggled.emit(False)

    def expand_panel(self):
        """Expands the panel out from the left edge."""
        if not self.is_collapsed:
            return
        self.is_collapsed = False
        self.collapsed_strip.setVisible(False)
        self.expanded_container.setVisible(True)

        self.setMinimumWidth(260)
        self.setMaximumWidth(480)
        target_w = self.expanded_width if self.expanded_width >= 260 else 320

        parent = self.parentWidget()
        if parent and hasattr(parent, 'setSizes'):
            sizes = parent.sizes()
            if len(sizes) >= 3:
                parent.setSizes([target_w, sizes[1], sizes[2]])

        self.toggled.emit(True)

    def toggle_collapse(self):
        if self.is_collapsed:
            self.expand_panel()
        else:
            self.collapse_panel()

    def select_folder(self, folder: Path):
        self.tree_view.select_folder(folder)
        self.folder_view.set_folder_path(folder)

    def set_scan_progress(self, cur: int, total: int, filename: str):
        self.folder_view.set_progress(cur, total, filename)

    def show_scan_progress(self, visible: bool):
        self.folder_view.show_progress(visible)
