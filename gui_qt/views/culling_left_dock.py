"""Left collapsible navigation dock for Tab 2: Sichten & Sortieren.

Holds the interactive directory tree (Verzeichnisbaum) with image, RAW, and JPEG counts.
Can be smoothly collapsed "nach Links" into a slim 36px vertical dock bar,
giving 100% of the reclaimed width directly to the image canvas workspace
without creating any dead/unusable space in the layout.
"""

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QPushButton, QTabWidget, QVBoxLayout, QWidget
)

from core.config import AppConfig
from gui_qt.models.culling_model import CullingItem
from gui_qt.styles.icons import (
    get_expand_panel_icon, get_filter_icon, get_folder_icon, get_icon_color
)
from gui_qt.styles.theme import theme_manager
from gui_qt.views.culling_filter import CullingFilterCriteria, CullingFilterWidget
from gui_qt.views.culling_tree import CullingDirectoryTreeWidget


class CullingLeftNavigationDock(QWidget):
    """Collapsible Left Dock containing the 'Verzeichnisse' tree and 'Filter' panel."""
    folder_selected = Signal(Path)
    filter_changed = Signal(object)  # CullingFilterCriteria
    toggled = Signal(bool)

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.is_collapsed: bool = False
        self.expanded_width: int = 330

        self._init_ui()
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # -------------------------------------------------------------
        # 1. COLLAPSED STRIP (Slim 36px bar visible when collapsed to left)
        # -------------------------------------------------------------
        self.collapsed_strip = QFrame()
        self.collapsed_strip.setObjectName("cullingLeftDockStrip")
        self.collapsed_strip.setFixedWidth(36)
        strip_layout = QVBoxLayout(self.collapsed_strip)
        strip_layout.setContentsMargins(3, 6, 3, 6)
        strip_layout.setSpacing(8)
        strip_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.btn_strip_expand = QPushButton()
        self.btn_strip_expand.setObjectName("btnStripExpand")
        self.btn_strip_expand.setIcon(get_expand_panel_icon(get_icon_color("accent"), 14))
        self.btn_strip_expand.setIconSize(QSize(14, 14))
        self.btn_strip_expand.setFixedSize(28, 28)
        self.btn_strip_expand.setToolTip("Seitenleiste ausklappen [V]")
        self.btn_strip_expand.clicked.connect(self.expand_panel)
        strip_layout.addWidget(self.btn_strip_expand)

        # Separator line
        sep = QFrame()
        sep.setObjectName("stripSeparator")
        sep.setFixedHeight(1)
        strip_layout.addWidget(sep)

        # Folder button -> switch to Verzeichnisse & expand
        self.btn_strip_tree = QPushButton()
        self.btn_strip_tree.setObjectName("btnStripNav")
        self.btn_strip_tree.setIcon(get_folder_icon(get_icon_color("accent"), 16))
        self.btn_strip_tree.setIconSize(QSize(16, 16))
        self.btn_strip_tree.setFixedSize(28, 28)
        self.btn_strip_tree.setToolTip("Verzeichnisbaum öffnen (Klicken zum Ausklappen)")
        self.btn_strip_tree.clicked.connect(lambda: self.show_tab(0))
        strip_layout.addWidget(self.btn_strip_tree)

        # Filter button -> switch to Filter & expand
        self.btn_strip_filter = QPushButton()
        self.btn_strip_filter.setObjectName("btnStripNav")
        self.btn_strip_filter.setIcon(get_filter_icon(get_icon_color("accent"), 16))
        self.btn_strip_filter.setIconSize(QSize(16, 16))
        self.btn_strip_filter.setFixedSize(28, 28)
        self.btn_strip_filter.setToolTip("Bilder-Filter öffnen (Klicken zum Ausklappen)")
        self.btn_strip_filter.clicked.connect(lambda: self.show_tab(1))
        strip_layout.addWidget(self.btn_strip_filter)

        strip_layout.addStretch()
        self.collapsed_strip.setVisible(False)
        main_layout.addWidget(self.collapsed_strip)

        # -------------------------------------------------------------
        # 2. EXPANDED CONTAINER: Modern Tabs (Verzeichnisse / Filter)
        # -------------------------------------------------------------
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("cullingLeftDockTabs")

        # Tab 0: Verzeichnisbaum
        self.tree_view = CullingDirectoryTreeWidget(self.config, self)
        self.tree_view.folder_selected.connect(self.folder_selected.emit)
        self.tree_view.collapse_panel_requested.connect(self.collapse_panel)
        self.tab_widget.addTab(self.tree_view, "Verzeichnisse")
        self.tab_widget.setTabIcon(0, get_folder_icon(get_icon_color("accent"), 14))

        # Tab 1: Filter Panel
        self.filter_view = CullingFilterWidget(self)
        self.filter_view.filter_changed.connect(self._on_filter_changed)
        self.filter_view.collapse_panel_requested.connect(self.collapse_panel)
        self.tab_widget.addTab(self.filter_view, "Filter")
        self.tab_widget.setTabIcon(1, get_filter_icon(get_icon_color("accent"), 14))

        main_layout.addWidget(self.tab_widget)
        self.tab_widget.currentChanged.connect(self._on_dock_tab_changed)

        saved_tab = getattr(self.config, "culling_dock_tab", 0)
        if saved_tab in (0, 1):
            self.tab_widget.setCurrentIndex(saved_tab)

        self.apply_min_width_policy()
        self.setMaximumWidth(480)

    def apply_min_width_policy(self):
        """Sets dock minimum width based on enforce_sidebar_min_width config."""
        if self.is_collapsed:
            return
        enforce = bool(getattr(self.config, "enforce_sidebar_min_width", True))
        self.setMinimumWidth(260 if enforce else 60)

    def _on_theme_changed(self, theme_name: str):
        """Updates strip and tab icons when theme switches."""
        self.btn_strip_expand.setIcon(get_expand_panel_icon(get_icon_color("accent"), 14))
        self.btn_strip_tree.setIcon(get_folder_icon(get_icon_color("accent"), 16))
        self.btn_strip_filter.setIcon(get_filter_icon(get_icon_color("accent"), 16))
        self.tab_widget.setTabIcon(0, get_folder_icon(get_icon_color("accent"), 14))
        self.tab_widget.setTabIcon(1, get_filter_icon(get_icon_color("accent"), 14))

    def _on_dock_tab_changed(self, idx: int):
        self.config.culling_dock_tab = idx
        try:
            self.config.save()
        except Exception:
            pass

    def _on_filter_changed(self, criteria: CullingFilterCriteria):
        # Update collapsed strip icon styling if filter is active
        self.btn_strip_filter.setProperty("active", "true" if criteria.is_active() else "false")
        self.btn_strip_filter.style().unpolish(self.btn_strip_filter)
        self.btn_strip_filter.style().polish(self.btn_strip_filter)
        self.filter_changed.emit(criteria)

    def show_tab(self, index: int):
        """Switches to the designated tab and expands the panel."""
        self.tab_widget.setCurrentIndex(index)
        self.expand_panel()

    def collapse_panel(self):
        """Folds the panel completely to the left into the 36px dock strip."""
        if self.is_collapsed:
            return
        self.is_collapsed = True
        self.config.culling_dock_collapsed = True
        try:
            self.config.save()
        except Exception:
            pass
        self.expanded_width = self.width() if self.width() >= 260 else 330
        self.tab_widget.setVisible(False)
        self.collapsed_strip.setVisible(True)

        self.setMinimumWidth(36)
        self.setMaximumWidth(36)
        self.resize(36, self.height())

        parent = self.parentWidget()
        if parent and hasattr(parent, 'setSizes'):
            sizes = parent.sizes()
            if len(sizes) >= 3:
                diff = sizes[0] - 36
                parent.setSizes([36, sizes[1], sizes[2] + diff])

        self.toggled.emit(False)

    def expand_panel(self):
        """Expands the panel out from the left edge."""
        if not self.is_collapsed:
            return
        self.is_collapsed = False
        self.config.culling_dock_collapsed = False
        try:
            self.config.save()
        except Exception:
            pass
        self.collapsed_strip.setVisible(False)
        self.tab_widget.setVisible(True)

        self.apply_min_width_policy()
        self.setMaximumWidth(480)
        target_w = self.expanded_width if self.expanded_width >= 260 else 330

        parent = self.parentWidget()
        if parent and hasattr(parent, 'setSizes'):
            sizes = parent.sizes()
            if len(sizes) >= 3:
                diff = target_w - sizes[0]
                parent.setSizes([target_w, sizes[1], max(100, sizes[2] - diff)])

        self.toggled.emit(True)

    def toggle_collapse(self):
        if self.is_collapsed:
            self.expand_panel()
        else:
            self.collapse_panel()

    def select_folder(self, folder: Path):
        self.tree_view.select_folder(folder)

    def update_folder_items(self, items: List[CullingItem]):
        self.filter_view.update_folder_items(items)

    def update_match_stats(self, matched_count: int, total_count: int):
        self.filter_view.update_match_stats(matched_count, total_count)
