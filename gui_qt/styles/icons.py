"""Programmatic vector icon generators for FotoDown.

Guarantees 100% reliable, font-independent rendering on all platforms (Windows, Linux, macOS)
without missing glyphs, tofu boxes, or platform emoji differences.
"""

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def get_refresh_icon(color: str = "#cbd5e1", size: int = 16) -> QIcon:
    """Renders a clean circular reload/refresh icon."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
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



