"""Programmatic vector icon generators for FotoDown.

Guarantees 100% reliable, font-independent rendering on all platforms (Windows, Linux, macOS)
without missing glyphs, tofu boxes, or platform emoji differences.
"""

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

