"""Paints stub rows (method badge, URL, name, tags) in the stub list."""

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from api_tool.ui.theme import (
    ACCENT,
    ACCENT_SOFT_SOLID,
    BG_SUBTLE,
    METHOD_COLORS,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from api_tool.ui.widgets.common import STUB_INFO_ROLE


class StubItemDelegate(QStyledItemDelegate):
    """Draws a stub row: colored method badge, URL, then name and tags."""

    ROW_HEIGHT = 54

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), self.ROW_HEIGHT)

    def paint(self, painter, option, index):
        info = index.data(STUB_INFO_ROLE) or {}
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect.adjusted(6, 2, -6, -2)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(ACCENT_SOFT_SOLID))
            painter.drawRoundedRect(rect, 6, 6)
            painter.setBrush(QColor(ACCENT))
            painter.drawRoundedRect(QRect(rect.left(), rect.top() + 8, 3, rect.height() - 16), 1.5, 1.5)
        elif hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(BG_SUBTLE))
            painter.drawRoundedRect(rect, 6, 6)

        enabled = info.get("enabled", True)
        method = info.get("method", "ANY")
        color = QColor(METHOD_COLORS.get(method, METHOD_COLORS["ANY"]))
        if not enabled:
            color = QColor(TEXT_MUTED)
        badge_font = QFont(option.font)
        badge_font.setPointSizeF(7.5)
        badge_font.setBold(True)
        badge = QRect(rect.left() + 10, rect.top() + 8, 54, 18)
        fill = QColor(color)
        fill.setAlpha(28)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(badge, 4, 4)
        painter.setPen(color)
        painter.setFont(badge_font)
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, method)

        text_left = badge.right() + 10
        text_width = rect.right() - text_left - 8
        url_font = QFont("monospace")
        url_font.setStyleHint(QFont.StyleHint.Monospace)
        url_font.setPointSizeF(option.font.pointSizeF() * 0.95)
        painter.setFont(url_font)
        painter.setPen(QColor(TEXT_PRIMARY if enabled else TEXT_MUTED))
        url = QFontMetrics(url_font).elidedText(info.get("url", ""), Qt.TextElideMode.ElideRight, text_width)
        painter.drawText(QRect(text_left, rect.top() + 6, text_width, 22),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, url)

        name_font = QFont(option.font)
        name_font.setPointSizeF(option.font.pointSizeF() * 0.9)
        painter.setFont(name_font)
        subtitle = info.get("name", "")
        tags = list(info.get("tags", []))
        if not enabled:
            tags.insert(0, "off")
        if tags:
            subtitle += "  ·  " + " · ".join(tags)
        painter.setPen(QColor(TEXT_SECONDARY if enabled else TEXT_MUTED))
        subtitle = QFontMetrics(name_font).elidedText(subtitle, Qt.TextElideMode.ElideRight,
                                                       rect.right() - badge.left() - 8)
        painter.drawText(QRect(badge.left(), rect.top() + 29, rect.right() - badge.left() - 8, 18),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, subtitle)
        painter.restore()
