"""Programmatic vector icon generators for FotoDown.

Guarantees 100% reliable, font-independent rendering on all platforms (Windows, Linux, macOS)
without missing glyphs, tofu boxes, or platform emoji differences.
"""

import math
from typing import Dict, Optional

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

_CURRENT_THEME = "dark"

PALETTES: Dict[str, Dict[str, str]] = {
    "dark": {
        "normal": "#cbd5e1",
        "accent": "#38bdf8",
        "muted": "#94a3b8",
        "success": "#4ade80",
        "danger": "#f87171",
        "warning": "#fbbf24",
        "white": "#ffffff",
        "contrast": "#f8fafc",
    },
    "light": {
        "normal": "#334155",
        "accent": "#0284c7",
        "muted": "#64748b",
        "success": "#16a34a",
        "danger": "#dc2626",
        "warning": "#d97706",
        "white": "#ffffff",
        "contrast": "#0f172a",
    },
}


def set_icon_theme(theme_name: str) -> None:
    """Sets the active icon theme ('dark' or 'light') for default icon colors."""
    global _CURRENT_THEME
    if theme_name in PALETTES:
        _CURRENT_THEME = theme_name


def get_icon_color(role: str = "normal") -> str:
    """Returns the appropriate hex color for active theme and role."""
    palette = PALETTES.get(_CURRENT_THEME, PALETTES["dark"])
    return palette.get(role, palette["normal"])


def get_refresh_icon(color: Optional[str] = None, size: int = 16) -> QIcon:
    """Renders a clean circular reload/refresh icon."""
    c = color or get_icon_color("normal")
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(c), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)

    # 270 degree arc
    rect = QRectF(2.5, 2.5, size - 5.0, size - 5.0)
    p.drawArc(rect, int(45 * 16), int(270 * 16))

    # Arrow head at top-right
    arrow_tip_x = size - 2.5
    arrow_tip_y = size * 0.45
    p.drawLine(QPointF(arrow_tip_x, arrow_tip_y), QPointF(arrow_tip_x - 3.5, arrow_tip_y - 3.5))
    p.drawLine(QPointF(arrow_tip_x, arrow_tip_y), QPointF(arrow_tip_x - 3.5, arrow_tip_y + 0.5))

    p.end()
    return QIcon(pix)


def get_plus_icon(color: str = "#cbd5e1", size: int = 16) -> QIcon:
    """Renders a crisp plus (+) icon for expanding."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)

    pad = size * 0.22
    mid = size / 2.0
    p.drawLine(QPointF(pad, mid), QPointF(size - pad, mid))
    p.drawLine(QPointF(mid, pad), QPointF(mid, size - pad))

    p.end()
    return QIcon(pix)


def get_minus_icon(color: str = "#cbd5e1", size: int = 16) -> QIcon:
    """Renders a crisp minus (−) icon for collapsing."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)

    pad = size * 0.22
    mid = size / 2.0
    p.drawLine(QPointF(pad, mid), QPointF(size - pad, mid))

    p.end()
    return QIcon(pix)


def get_collapse_panel_icon(color: str = "#cbd5e1", size: int = 16) -> QIcon:
    """Renders a left chevron (◀ / «) to collapse a side panel."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    mid_y = size / 2.0
    left_x = size * 0.3
    right_x = size * 0.7
    top_y = size * 0.25
    bottom_y = size * 0.75

    path = QPainterPath()
    path.moveTo(right_x, top_y)
    path.lineTo(left_x, mid_y)
    path.lineTo(right_x, bottom_y)
    p.drawPath(path)

    p.end()
    return QIcon(pix)


def get_expand_panel_icon(color: str = "#cbd5e1", size: int = 16) -> QIcon:
    """Renders a right chevron (▶ / ») to expand a side panel."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    mid_y = size / 2.0
    left_x = size * 0.3
    right_x = size * 0.7
    top_y = size * 0.25
    bottom_y = size * 0.75

    path = QPainterPath()
    path.moveTo(left_x, top_y)
    path.lineTo(right_x, mid_y)
    path.lineTo(left_x, bottom_y)
    p.drawPath(path)

    p.end()
    return QIcon(pix)


def get_folder_icon(color: str = "#38bdf8", size: int = 16) -> QIcon:
    """Renders a crisp Fluent-style directory folder icon."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(color)))

    # Tab at top-left
    tab_w = size * 0.45
    tab_h = size * 0.3
    p.drawRoundedRect(QRectF(1.0, 1.5, tab_w, tab_h), 1.0, 1.0)

    # Body
    body_y = size * 0.32
    body_h = size * 0.6
    p.drawRoundedRect(QRectF(1.0, body_y, size - 2.0, body_h), 1.5, 1.5)

    p.end()
    return QIcon(pix)


def get_filmstrip_icon(color: str = "#94a3b8", size: int = 16) -> QIcon:
    """Renders a crisp filmstrip icon."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Strip frame
    pen = QPen(QColor(color), 1.5)
    p.setPen(pen)
    p.drawRoundedRect(QRectF(1.5, 2.5, size - 3.0, size - 5.0), 1.5, 1.5)

    # Sprockets / frames inside
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(color)))
    for x in [3.5, 7.5, 11.5]:
        p.drawRect(QRectF(x, 4.0, 1.5, 2.0))
        p.drawRect(QRectF(x, size - 6.0, 1.5, 2.0))

    p.end()
    return QIcon(pix)


def get_filter_icon(color: str = "#38bdf8", size: int = 16) -> QIcon:
    """Renders a crisp vector funnel / filter icon."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    top_y = size * 0.22
    neck_top_y = size * 0.54
    neck_bot_y = size * 0.85
    left_x = size * 0.18
    right_x = size * 0.82
    mid_left_x = size * 0.40
    mid_right_x = size * 0.60

    path = QPainterPath()
    path.moveTo(left_x, top_y)
    path.lineTo(right_x, top_y)
    path.lineTo(mid_right_x, neck_top_y)
    path.lineTo(mid_right_x, neck_bot_y)
    path.lineTo(mid_left_x, neck_bot_y)
    path.lineTo(mid_left_x, neck_top_y)
    path.closeSubpath()

    p.drawPath(path)
    p.end()
    return QIcon(pix)


def get_gear_icon(color: str = "#cbd5e1", size: int = 16) -> QIcon:
    """Renders a crisp vector gear/cog settings icon."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(color)))

    cx, cy = size / 2.0, size / 2.0
    r_outer = size * 0.44
    r_teeth_in = size * 0.32
    r_hole = size * 0.16

    path = QPainterPath()
    num_teeth = 6
    teeth_width_deg = 24.0
    for i in range(num_teeth):
        mid_angle = i * (360.0 / num_teeth)
        a1 = (mid_angle - teeth_width_deg / 2) * math.pi / 180.0
        a2 = (mid_angle + teeth_width_deg / 2) * math.pi / 180.0
        p1 = QPointF(cx + r_teeth_in * math.cos(a1), cy + r_teeth_in * math.sin(a1))
        p2 = QPointF(cx + r_outer * math.cos(a1), cy + r_outer * math.sin(a1))
        p3 = QPointF(cx + r_outer * math.cos(a2), cy + r_outer * math.sin(a2))
        p4 = QPointF(cx + r_teeth_in * math.cos(a2), cy + r_teeth_in * math.sin(a2))
        if i == 0:
            path.moveTo(p1)
        else:
            path.lineTo(p1)
        path.lineTo(p2)
        path.lineTo(p3)
        path.lineTo(p4)

    path.closeSubpath()

    hole_path = QPainterPath()
    hole_path.addEllipse(QPointF(cx, cy), r_hole, r_hole)
    gear_path = path.subtracted(hole_path)

    p.drawPath(gear_path)
    p.end()
    return QIcon(pix)


def get_columns_icon(color: str = "#cbd5e1", size: int = 16) -> QIcon:
    """Renders a crisp 3-column layout icon for toggling table columns."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.drawRoundedRect(QRectF(1.5, 2.0, size - 3.0, size - 4.0), 1.5, 1.5)

    col_w = (size - 3.0) / 3.0
    p.drawLine(QPointF(1.5 + col_w, 2.0), QPointF(1.5 + col_w, size - 2.0))
    p.drawLine(QPointF(1.5 + col_w * 2, 2.0), QPointF(1.5 + col_w * 2, size - 2.0))

    p.end()
    return QIcon(pix)


def get_sort_icon(descending: bool = False, color: str = "#cbd5e1", size: int = 16) -> QIcon:
    """Renders a clean ascending or descending sort arrow icon with bars."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    # Vertical arrow shaft on left
    ax = size * 0.28
    p.drawLine(QPointF(ax, size * 0.2), QPointF(ax, size * 0.8))
    if descending:
        p.drawLine(QPointF(ax, size * 0.8), QPointF(ax - size * 0.14, size * 0.62))
        p.drawLine(QPointF(ax, size * 0.8), QPointF(ax + size * 0.14, size * 0.62))
        widths = [0.42, 0.30, 0.18]
    else:
        p.drawLine(QPointF(ax, size * 0.2), QPointF(ax - size * 0.14, size * 0.38))
        p.drawLine(QPointF(ax, size * 0.2), QPointF(ax + size * 0.14, size * 0.38))
        widths = [0.18, 0.30, 0.42]

    # Sort bars on right
    bx = size * 0.50
    for idx, w in enumerate(widths):
        by = size * (0.26 + idx * 0.24)
        p.drawLine(QPointF(bx, by), QPointF(bx + size * w, by))

    p.end()
    return QIcon(pix)


def get_files_icon(color: str = "#cbd5e1", size: int = 16) -> QIcon:
    """Renders a crisp document/photo sheet icon."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    path = QPainterPath()
    fold = size * 0.25
    l_x, t_y, r_x, b_y = size * 0.2, size * 0.12, size * 0.8, size * 0.88
    path.moveTo(l_x, t_y)
    path.lineTo(r_x - fold, t_y)
    path.lineTo(r_x, t_y + fold)
    path.lineTo(r_x, b_y)
    path.lineTo(l_x, b_y)
    path.closeSubpath()
    p.drawPath(path)

    # Lines inside document
    p.drawLine(QPointF(l_x + 2.5, size * 0.48), QPointF(r_x - 2.5, size * 0.48))
    p.drawLine(QPointF(l_x + 2.5, size * 0.68), QPointF(r_x - 2.5, size * 0.68))

    p.end()
    return QIcon(pix)


def get_list_icon(color: str = "#cbd5e1", size: int = 16) -> QIcon:
    """Renders a crisp bulleted list view icon."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    for idx in range(3):
        y = size * (0.25 + idx * 0.25)
        p.drawPoint(QPointF(size * 0.20, y))
        p.drawLine(QPointF(size * 0.36, y), QPointF(size * 0.84, y))

    p.end()
    return QIcon(pix)


def get_grid_icon(color: str = "#cbd5e1", size: int = 16) -> QIcon:
    """Renders a crisp 2x2 thumbnail grid icon."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.4)
    p.setPen(pen)
    p.setBrush(QBrush(QColor(color)))
    pad = size * 0.16
    cell = size * 0.28
    gap = size * 0.12
    for row in range(2):
        for col in range(2):
            x = pad + col * (cell + gap)
            y = pad + row * (cell + gap)
            p.drawRoundedRect(QRectF(x, y, cell, cell), 1.2, 1.2)

    p.end()
    return QIcon(pix)


def get_check_all_icon(color: str = "#38bdf8", size: int = 16) -> QIcon:
    """Renders a checked checkbox icon."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.drawRoundedRect(QRectF(2.0, 2.0, size - 4.0, size - 4.0), 2.0, 2.0)
    p.drawLine(QPointF(size * 0.28, size * 0.52), QPointF(size * 0.45, size * 0.70))
    p.drawLine(QPointF(size * 0.45, size * 0.70), QPointF(size * 0.74, size * 0.34))

    p.end()
    return QIcon(pix)


def get_uncheck_all_icon(color: str = "#94a3b8", size: int = 16) -> QIcon:
    """Renders an empty checkbox icon."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.drawRoundedRect(QRectF(2.0, 2.0, size - 4.0, size - 4.0), 2.0, 2.0)

    p.end()
    return QIcon(pix)


def get_invert_icon(color: str = "#cbd5e1", size: int = 16) -> QIcon:
    """Renders an invert-selection diagonal split box icon."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.drawRoundedRect(QRectF(2.0, 2.0, size - 4.0, size - 4.0), 2.0, 2.0)

    tri = QPainterPath()
    tri.moveTo(2.5, size - 2.5)
    tri.lineTo(size - 2.5, 2.5)
    tri.lineTo(size - 2.5, size - 2.5)
    tri.closeSubpath()
    p.fillPath(tri, QBrush(QColor(color)))

    p.end()
    return QIcon(pix)


def get_quick_icon(color: str = "#fbbf24", size: int = 16) -> QIcon:
    """Renders a crisp lightning bolt icon for quick access."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    path = QPainterPath()
    path.moveTo(size * 0.58, size * 0.10)
    path.lineTo(size * 0.24, size * 0.56)
    path.lineTo(size * 0.48, size * 0.56)
    path.lineTo(size * 0.40, size * 0.90)
    path.lineTo(size * 0.76, size * 0.44)
    path.lineTo(size * 0.52, size * 0.44)
    path.closeSubpath()
    p.fillPath(path, QBrush(QColor(color)))

    p.end()
    return QIcon(pix)


def get_clear_icon(color: str = "#94a3b8", size: int = 16) -> QIcon:
    """Renders a crisp X / clear icon."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    pad = size * 0.26
    p.drawLine(QPointF(pad, pad), QPointF(size - pad, size - pad))
    p.drawLine(QPointF(size - pad, pad), QPointF(pad, size - pad))

    p.end()
    return QIcon(pix)


def get_arrow_right_icon(color: str = "#ffffff", size: int = 16, double: bool = False) -> QIcon:
    """Renders single or double right-pointing chevron/arrow icons for Copy/Move."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    offsets = [size * 0.26, size * 0.54] if double else [size * 0.40]
    span = size * 0.22
    mid_y = size * 0.5
    top_y = size * 0.24
    bot_y = size * 0.76
    for ox in offsets:
        path = QPainterPath()
        path.moveTo(ox, top_y)
        path.lineTo(ox + span, mid_y)
        path.lineTo(ox, bot_y)
        p.drawPath(path)

    p.end()
    return QIcon(pix)


def get_move_icon(color: str = "#ffffff", size: int = 16, double: bool = False) -> QIcon:
    """Renders a move arrow icon (horizontal arrow shaft + tip)."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    mid_y = size * 0.5
    p.drawLine(QPointF(size * 0.14, mid_y), QPointF(size * 0.84, mid_y))
    tips = [size * 0.62, size * 0.86] if double else [size * 0.86]
    for tip_x in tips:
        p.drawLine(QPointF(tip_x - size * 0.22, mid_y - size * 0.22), QPointF(tip_x, mid_y))
        p.drawLine(QPointF(tip_x - size * 0.22, mid_y + size * 0.22), QPointF(tip_x, mid_y))

    p.end()
    return QIcon(pix)


def get_swap_icon(color: str = "#cbd5e1", size: int = 16) -> QIcon:
    """Renders left/right swap arrows icon."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    # Top arrow right
    y1 = size * 0.32
    p.drawLine(QPointF(size * 0.18, y1), QPointF(size * 0.82, y1))
    p.drawLine(QPointF(size * 0.64, y1 - size * 0.15), QPointF(size * 0.82, y1))
    p.drawLine(QPointF(size * 0.64, y1 + size * 0.15), QPointF(size * 0.82, y1))

    # Bottom arrow left
    y2 = size * 0.68
    p.drawLine(QPointF(size * 0.18, y2), QPointF(size * 0.82, y2))
    p.drawLine(QPointF(size * 0.36, y2 - size * 0.15), QPointF(size * 0.18, y2))
    p.drawLine(QPointF(size * 0.36, y2 + size * 0.15), QPointF(size * 0.18, y2))

    p.end()
    return QIcon(pix)


def get_search_icon(color: Optional[str] = None, size: int = 16) -> QIcon:
    """Renders a crisp magnifying glass (search/reconcile/compare) icon."""
    c = color or get_icon_color("normal")
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(c), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)

    # Circle (magnifying glass lens)
    radius = size * 0.28
    center_x = size * 0.42
    center_y = size * 0.42
    p.drawEllipse(QPointF(center_x, center_y), radius, radius)

    # Handle angled down-right
    start_x = center_x + radius * 0.707
    start_y = center_y + radius * 0.707
    end_x = size * 0.86
    end_y = size * 0.86
    p.drawLine(QPointF(start_x, start_y), QPointF(end_x, end_y))

    p.end()
    return QIcon(pix)


def get_import_icon(color: Optional[str] = None, size: int = 16) -> QIcon:
    """Renders a modern download / import tray vector icon."""
    c = color or get_icon_color("accent")
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(c), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    mid = size / 2.0
    bot = size - 2.5
    tray_top = size * 0.58

    # Tray
    tray = QPainterPath()
    tray.moveTo(size * 0.16, tray_top)
    tray.lineTo(size * 0.16, bot)
    tray.lineTo(size * 0.84, bot)
    tray.lineTo(size * 0.84, tray_top)
    p.drawPath(tray)

    # Downward arrow
    arrow_tip = size * 0.68
    p.drawLine(QPointF(mid, size * 0.16), QPointF(mid, arrow_tip))
    p.drawLine(QPointF(mid - size * 0.20, arrow_tip - size * 0.20), QPointF(mid, arrow_tip))
    p.drawLine(QPointF(mid + size * 0.20, arrow_tip - size * 0.20), QPointF(mid, arrow_tip))

    p.end()
    return QIcon(pix)


def get_culling_icon(color: Optional[str] = None, size: int = 16) -> QIcon:
    """Renders a clean modern eye / viewing loupe icon for visual culling."""
    c = color or get_icon_color("accent")
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(c), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    mid_y = size / 2.0
    mid_x = size / 2.0

    # Eye eyelids (two symmetric cubic bezier curves)
    path = QPainterPath()
    left_x = size * 0.12
    right_x = size * 0.88
    path.moveTo(left_x, mid_y)
    path.cubicTo(size * 0.32, size * 0.18, size * 0.68, size * 0.18, right_x, mid_y)
    path.cubicTo(size * 0.68, size * 0.82, size * 0.32, size * 0.82, left_x, mid_y)
    p.drawPath(path)

    # Pupil in center
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(c)))
    p.drawEllipse(QPointF(mid_x, mid_y), size * 0.18, size * 0.18)

    p.end()
    return QIcon(pix)


def get_archive_icon(color: Optional[str] = None, size: int = 16) -> QIcon:
    """Renders a reliable backup / archive 3.5-inch floppy disk vector icon."""
    c = color or get_icon_color("accent")
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(c), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    # Disk body with beveled top-right corner
    l_x, t_y = size * 0.16, size * 0.16
    r_x, b_y = size * 0.84, size * 0.84
    bevel = size * 0.18

    body = QPainterPath()
    body.moveTo(l_x, t_y)
    body.lineTo(r_x - bevel, t_y)
    body.lineTo(r_x, t_y + bevel)
    body.lineTo(r_x, b_y)
    body.lineTo(l_x, b_y)
    body.closeSubpath()
    p.drawPath(body)

    # Slider shutter at top
    p.drawRect(QRectF(size * 0.30, t_y, size * 0.38, size * 0.28))

    # Label area at bottom
    p.drawRoundedRect(QRectF(size * 0.26, size * 0.52, size * 0.48, size * 0.32), 1.0, 1.0)

    p.end()
    return QIcon(pix)


def get_tag_icon(color: Optional[str] = None, size: int = 16) -> QIcon:
    """Renders a crisp price tag / label vector icon for batch renaming."""
    c = color or get_icon_color("normal")
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(c), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    # Angled tag body
    mid_y = size / 2.0
    tip_x = size * 0.15
    notch_x = size * 0.42
    top_y = size * 0.22
    bot_y = size * 0.78
    right_x = size * 0.85

    tag = QPainterPath()
    tag.moveTo(tip_x, mid_y)
    tag.lineTo(notch_x, top_y)
    tag.lineTo(right_x, top_y)
    tag.lineTo(right_x, bot_y)
    tag.lineTo(notch_x, bot_y)
    tag.closeSubpath()
    p.drawPath(tag)

    # Small circular hole near the tip
    p.drawEllipse(QPointF(size * 0.32, mid_y), 1.6, 1.6)

    p.end()
    return QIcon(pix)


def get_fullscreen_icon(color: Optional[str] = None, size: int = 16) -> QIcon:
    """Renders 4 outward-pointing corner brackets for fullscreen toggle (F11)."""
    c = color or get_icon_color("normal")
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(c), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    pad = size * 0.18
    arm = size * 0.24
    end = size - pad

    # Top-Left ┌
    p.drawLine(QPointF(pad, pad + arm), QPointF(pad, pad))
    p.drawLine(QPointF(pad, pad), QPointF(pad + arm, pad))

    # Top-Right ┐
    p.drawLine(QPointF(end - arm, pad), QPointF(end, pad))
    p.drawLine(QPointF(end, pad), QPointF(end, pad + arm))

    # Bottom-Left └
    p.drawLine(QPointF(pad, end - arm), QPointF(pad, end))
    p.drawLine(QPointF(pad, end), QPointF(pad + arm, end))

    # Bottom-Right ┘
    p.drawLine(QPointF(end - arm, end), QPointF(end, end))
    p.drawLine(QPointF(end, end), QPointF(end, end - arm))

    p.end()
    return QIcon(pix)


def get_fullscreen_exit_icon(color: Optional[str] = None, size: int = 16) -> QIcon:
    """Renders 4 inward-pointing corner brackets for exiting fullscreen."""
    c = color or get_icon_color("normal")
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(c), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    center = size / 2.0
    gap = size * 0.12
    arm = size * 0.22

    # Top-Left pointing inward ┘
    p.drawLine(QPointF(center - gap - arm, center - gap), QPointF(center - gap, center - gap))
    p.drawLine(QPointF(center - gap, center - gap - arm), QPointF(center - gap, center - gap))

    # Top-Right pointing inward └
    p.drawLine(QPointF(center + gap + arm, center - gap), QPointF(center + gap, center - gap))
    p.drawLine(QPointF(center + gap, center - gap - arm), QPointF(center + gap, center - gap))

    # Bottom-Left pointing inward ┐
    p.drawLine(QPointF(center - gap - arm, center + gap), QPointF(center - gap, center + gap))
    p.drawLine(QPointF(center - gap, center + gap + arm), QPointF(center - gap, center + gap))

    # Bottom-Right pointing inward ┌
    p.drawLine(QPointF(center + gap + arm, center + gap), QPointF(center + gap, center + gap))
    p.drawLine(QPointF(center + gap, center + gap + arm), QPointF(center + gap, center + gap))

    p.end()
    return QIcon(pix)


def get_zoom_icon(color: Optional[str] = None, size: int = 16) -> QIcon:
    """Renders a magnifying glass with a plus (+) sign for 100% / zoom in."""
    c = color or get_icon_color("normal")
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(c), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)

    radius = size * 0.28
    cx, cy = size * 0.42, size * 0.42
    p.drawEllipse(QPointF(cx, cy), radius, radius)

    # Handle
    start_x = cx + radius * 0.707
    start_y = cy + radius * 0.707
    p.drawLine(QPointF(start_x, start_y), QPointF(size * 0.86, size * 0.86))

    # Plus sign inside lens
    arm = radius * 0.55
    p.drawLine(QPointF(cx - arm, cy), QPointF(cx + arm, cy))
    p.drawLine(QPointF(cx, cy - arm), QPointF(cx, cy + arm))

    p.end()
    return QIcon(pix)


def get_zoom_fit_icon(color: Optional[str] = None, size: int = 16) -> QIcon:
    """Renders a magnifying glass with a fit frame inside."""
    c = color or get_icon_color("normal")
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(c), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)

    radius = size * 0.28
    cx, cy = size * 0.42, size * 0.42
    p.drawEllipse(QPointF(cx, cy), radius, radius)

    # Handle
    start_x = cx + radius * 0.707
    start_y = cy + radius * 0.707
    p.drawLine(QPointF(start_x, start_y), QPointF(size * 0.86, size * 0.86))

    # Inner fit frame
    p.setPen(QPen(QColor(c), 1.3))
    p.drawRect(QRectF(cx - radius * 0.5, cy - radius * 0.5, radius, radius))

    p.end()
    return QIcon(pix)


def get_info_icon(color: Optional[str] = None, size: int = 16) -> QIcon:
    """Renders a crisp circle-information (EXIF) icon."""
    c = color or get_icon_color("accent")
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(c), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)

    mid = size / 2.0
    p.drawEllipse(QPointF(mid, mid), size * 0.42, size * 0.42)

    # Dot of the 'i'
    p.drawPoint(QPointF(mid, size * 0.32))

    # Stem of the 'i'
    p.drawLine(QPointF(mid, size * 0.46), QPointF(mid, size * 0.72))

    p.end()
    return QIcon(pix)


def get_save_icon(color: Optional[str] = None, size: int = 16) -> QIcon:
    """Renders a diskette / save icon."""
    return get_archive_icon(color or get_icon_color("normal"), size)


def get_trash_icon(color: Optional[str] = None, size: int = 16) -> QIcon:
    """Renders a wastebasket / delete icon."""
    c = color or get_icon_color("danger")
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(c), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    # Top handle
    p.drawLine(QPointF(size * 0.40, size * 0.18), QPointF(size * 0.60, size * 0.18))

    # Lid line
    p.drawLine(QPointF(size * 0.18, size * 0.28), QPointF(size * 0.82, size * 0.28))

    # Bin body
    body = QPainterPath()
    body.moveTo(size * 0.26, size * 0.32)
    body.lineTo(size * 0.32, size * 0.84)
    body.lineTo(size * 0.68, size * 0.84)
    body.lineTo(size * 0.74, size * 0.32)
    p.drawPath(body)

    # Vertical ribs
    p.drawLine(QPointF(size * 0.42, size * 0.42), QPointF(size * 0.42, size * 0.74))
    p.drawLine(QPointF(size * 0.58, size * 0.42), QPointF(size * 0.58, size * 0.74))

    p.end()
    return QIcon(pix)


def get_folder_open_icon(color: Optional[str] = None, size: int = 16) -> QIcon:
    """Renders an open folder icon."""
    c = color or get_icon_color("accent")
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(c), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    # Back folder body
    p.drawRoundedRect(QRectF(size * 0.12, size * 0.20, size * 0.50, size * 0.30), 1.0, 1.0)

    # Front open flap
    flap = QPainterPath()
    flap.moveTo(size * 0.10, size * 0.82)
    flap.lineTo(size * 0.26, size * 0.42)
    flap.lineTo(size * 0.90, size * 0.42)
    flap.lineTo(size * 0.74, size * 0.82)
    flap.closeSubpath()
    p.drawPath(flap)

    p.end()
    return QIcon(pix)


def get_eject_icon(color: Optional[str] = None, size: int = 16) -> QIcon:
    """Renders an eject symbol (upward triangle over horizontal bar)."""
    c = color or get_icon_color("normal")
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(c), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    mid = size / 2.0
    tri = QPainterPath()
    tri.moveTo(mid, size * 0.20)
    tri.lineTo(size * 0.80, size * 0.60)
    tri.lineTo(size * 0.20, size * 0.60)
    tri.closeSubpath()
    p.drawPath(tri)

    # Bar underneath
    p.drawLine(QPointF(size * 0.20, size * 0.78), QPointF(size * 0.80, size * 0.78))

    p.end()
    return QIcon(pix)


def get_history_icon(color: Optional[str] = None, size: int = 16) -> QIcon:
    """Renders a clock / history icon."""
    c = color or get_icon_color("normal")
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(c), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)

    mid = size / 2.0
    p.drawEllipse(QPointF(mid, mid), size * 0.40, size * 0.40)

    # Clock hands
    p.drawLine(QPointF(mid, mid), QPointF(mid, size * 0.26))
    p.drawLine(QPointF(mid, mid), QPointF(size * 0.72, mid))

    p.end()
    return QIcon(pix)


def get_help_icon(color: Optional[str] = None, size: int = 16) -> QIcon:
    """Renders a clean question mark / help vector icon."""
    c = color or get_icon_color("normal")
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(c), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)

    mid = size / 2.0
    p.drawEllipse(QPointF(mid, mid), size * 0.42, size * 0.42)

    # Question mark curve
    q = QPainterPath()
    q.moveTo(size * 0.38, size * 0.36)
    q.cubicTo(size * 0.38, size * 0.24, size * 0.62, size * 0.24, size * 0.62, size * 0.36)
    q.cubicTo(size * 0.62, size * 0.48, mid, size * 0.46, mid, size * 0.58)
    p.drawPath(q)

    # Dot of ?
    p.drawPoint(QPointF(mid, size * 0.72))

    p.end()
    return QIcon(pix)


def get_theme_icon(theme_mode: str = "dark", color: Optional[str] = None, size: int = 16) -> QIcon:
    """Renders a theme icon (crescent moon for dark, sun for light, monitor for system)."""
    c = color or get_icon_color("accent")
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    mid = size / 2.0

    if theme_mode == "light":
        # Sun with rays
        pen = QPen(QColor(c), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        r_inner = size * 0.22
        r_ray_in = size * 0.30
        r_ray_out = size * 0.44
        p.drawEllipse(QPointF(mid, mid), r_inner, r_inner)

        for i in range(8):
            ang = i * (math.pi / 4.0)
            p1 = QPointF(mid + r_ray_in * math.cos(ang), mid + r_ray_in * math.sin(ang))
            p2 = QPointF(mid + r_ray_out * math.cos(ang), mid + r_ray_out * math.sin(ang))
            p.drawLine(p1, p2)

    elif theme_mode == "system":
        # Monitor display
        pen = QPen(QColor(c), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        # Screen
        p.drawRoundedRect(QRectF(size * 0.16, size * 0.18, size * 0.68, size * 0.50), 1.5, 1.5)
        # Stand stem & foot
        p.drawLine(QPointF(mid, size * 0.68), QPointF(mid, size * 0.82))
        p.drawLine(QPointF(size * 0.32, size * 0.82), QPointF(size * 0.68, size * 0.82))

    else:
        # Crescent Moon
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(c)))

        outer = QPainterPath()
        outer.addEllipse(QRectF(size * 0.16, size * 0.16, size * 0.68, size * 0.68))

        inner = QPainterPath()
        inner.addEllipse(QRectF(size * 0.34, size * 0.10, size * 0.56, size * 0.56))

        crescent = outer.subtracted(inner)
        p.drawPath(crescent)

    p.end()
    return QIcon(pix)


def get_star_icon(filled: bool = True, color: Optional[str] = None, size: int = 16) -> QIcon:
    """Renders a 5-pointed star icon."""
    c = color or get_icon_color("warning")
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    cx, cy = size / 2.0, size / 2.0
    r_outer = size * 0.42
    r_inner = size * 0.19

    star = QPainterPath()
    for i in range(10):
        r = r_outer if i % 2 == 0 else r_inner
        ang = (i * 36 - 90) * math.pi / 180.0
        pt = QPointF(cx + r * math.cos(ang), cy + r * math.sin(ang))
        if i == 0:
            star.moveTo(pt)
        else:
            star.lineTo(pt)
    star.closeSubpath()

    if filled:
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(star, QBrush(QColor(c)))
    else:
        p.setPen(QPen(QColor(c), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(star)

    p.end()
    return QIcon(pix)





