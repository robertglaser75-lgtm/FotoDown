"""Item delegate to draw modern virtualized photo cards in Gallery view."""

from typing import Dict
from PySide6.QtCore import QRect, QSize, Qt, Signal, QObject
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetrics, QPainter,
    QPainterPath, QPen, QPixmap
)
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from core.importer import ScanItem


class GalleryDelegate(QStyledItemDelegate):
    DEFAULT_CARD_SIZE = QSize(180, 205)
    DEFAULT_THUMB_SIZE = QSize(160, 120)

    STATUS_COLORS = {
        "Neu": (QColor("#166534"), QColor("#4ade80")),          # bg, fg
        "Bereits importiert": (QColor("#334155"), QColor("#94a3b8")),
        "Existiert im Ziel": (QColor("#713f12"), QColor("#fde047")),
        "Fehler": (QColor("#7f1d1d"), QColor("#fca5a5")),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap_cache: Dict[str, QPixmap] = {}
        self.card_size = QSize(self.DEFAULT_CARD_SIZE)
        self.thumb_size = QSize(self.DEFAULT_THUMB_SIZE)

    def set_scale(self, width: int):
        """Adjusts thumbnail and card dimensions according to zoom slider."""
        thumb_w = max(110, min(340, width))
        thumb_h = int(thumb_w * 0.72)
        self.thumb_size = QSize(thumb_w, thumb_h)
        self.card_size = QSize(thumb_w + 20, thumb_h + 80)

    def set_pixmap(self, path_str: str, pixmap: QPixmap):
        self.pixmap_cache[path_str] = pixmap

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        return self.card_size

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        item: ScanItem = index.data(Qt.ItemDataRole.UserRole)
        if not item:
            painter.restore()
            return

        rect = option.rect.adjusted(4, 4, -4, -4)
        is_selected = item.selected
        is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        # 1. Background Card
        card_path = QPainterPath()
        card_path.addRoundedRect(rect, 8, 8)
        painter.fillPath(card_path, QBrush(QColor("#1e293b")))

        # Border
        border_color = QColor("#0284c7") if is_selected else (QColor("#475569") if is_hovered else QColor("#334155"))
        border_width = 2 if is_selected else 1
        painter.strokePath(card_path, QPen(border_color, border_width))

        # 2. Checkbox in top-left
        chk_rect = QRect(rect.left() + 8, rect.top() + 8, 18, 18)
        chk_path = QPainterPath()
        chk_path.addRoundedRect(chk_rect, 4, 4)
        if is_selected:
            painter.fillPath(chk_path, QBrush(QColor("#0284c7")))
            painter.setPen(QPen(Qt.GlobalColor.white, 2))
            painter.drawLine(chk_rect.left() + 4, chk_rect.top() + 9, chk_rect.left() + 7, chk_rect.top() + 13)
            painter.drawLine(chk_rect.left() + 7, chk_rect.top() + 13, chk_rect.left() + 14, chk_rect.top() + 5)
        else:
            painter.strokePath(chk_path, QPen(QColor("#64748b"), 1.5))

        # 3. Status Pill in top-right
        status_text = item.status
        bg_col, fg_col = self.STATUS_COLORS.get(status_text, (QColor("#334155"), QColor("#94a3b8")))
        pill_rect = QRect(rect.right() - 85, rect.top() + 7, 78, 18)
        pill_path = QPainterPath()
        pill_path.addRoundedRect(pill_rect, 9, 9)
        painter.fillPath(pill_path, QBrush(bg_col))

        font_status = QFont("Segoe UI", 8, QFont.Weight.Bold)
        painter.setFont(font_status)
        painter.setPen(fg_col)
        display_status = "Neu" if status_text == "Neu" else ("Importiert" if status_text == "Bereits importiert" else status_text)
        painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, display_status)

        # 4. Thumbnail Area
        thumb_rect = QRect(
            rect.left() + (rect.width() - self.thumb_size.width()) // 2,
            rect.top() + 32,
            self.thumb_size.width(),
            self.thumb_size.height()
        )
        path_str = str(item.source_path)
        pix = self.pixmap_cache.get(path_str)

        if pix and not pix.isNull():
            scaled = pix.scaled(
                thumb_rect.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            target_draw = QRect(
                thumb_rect.left() + (thumb_rect.width() - scaled.width()) // 2,
                thumb_rect.top() + (thumb_rect.height() - scaled.height()) // 2,
                scaled.width(), scaled.height()
            )
            t_path = QPainterPath()
            t_path.addRoundedRect(target_draw, 4, 4)
            painter.save()
            painter.setClipPath(t_path)
            painter.drawPixmap(target_draw.topLeft(), scaled)
            painter.restore()
        else:
            t_path = QPainterPath()
            t_path.addRoundedRect(thumb_rect, 6, 6)
            painter.fillPath(t_path, QBrush(QColor("#0f172a")))
            painter.setPen(QColor("#475569"))
            placeholder_text = "Video" if item.metadata.is_video else ("RAW" if item.metadata.is_raw else "Foto")
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, placeholder_text)

        # 4b. Badge for RAW+JPG pair / XMP
        if item.is_pair or item.sidecar_paths:
            badge_text = "RAW+JPG" if item.is_pair else ""
            if item.sidecar_paths:
                badge_text = f"{badge_text}+XMP" if badge_text else "XMP"

            badge_rect = QRect(thumb_rect.right() - 64, thumb_rect.bottom() - 19, 62, 17)
            b_path = QPainterPath()
            b_path.addRoundedRect(badge_rect, 4, 4)
            painter.fillPath(b_path, QBrush(QColor(15, 23, 42, 225)))
            painter.strokePath(b_path, QPen(QColor("#6366f1"), 1))
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.setPen(QColor("#a5b4fc"))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

        # 5. Filename & Details in footer
        name_rect = QRect(rect.left() + 8, rect.bottom() - 36, rect.width() - 16, 16)
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Medium))
        painter.setPen(QColor("#f8fafc"))
        metrics = QFontMetrics(painter.font())
        elided_name = metrics.elidedText(item.source_path.name, Qt.TextElideMode.ElideMiddle, name_rect.width())
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided_name)

        detail_rect = QRect(rect.left() + 8, rect.bottom() - 18, rect.width() - 16, 14)
        painter.setFont(QFont("Segoe UI", 7))
        painter.setPen(QColor("#94a3b8"))
        size_mb = item.total_size / (1024 * 1024)
        size_str = f"{size_mb:.1f} MB" if size_mb >= 1.0 else f"{item.total_size / 1024:.0f} KB"
        type_str = item.display_type
        painter.drawText(detail_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"{type_str} • {size_str}")

        painter.restore()
