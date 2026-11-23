"""侧栏顶部的搜索入口：展开时像一个搜索框，收起时只剩放大镜。点击打开全局搜索。"""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from qfluentwidgets import FluentIcon, getFont, isDarkTheme
from qfluentwidgets.components.navigation.navigation_widget import NavigationWidget

from app.overview.style import text_color
from module.localization import tr


class NavigationSearchBox(NavigationWidget):
    def __init__(self, parent=None):
        super().__init__(isSelectable=False, parent=parent)
        self._text = tr("搜索功能、设置、帮助")
        self._shortcut = "Ctrl K"
        self.setToolTip(tr("搜索（Ctrl+K）"))

    def setText(self, text):
        self._text = text
        self.update()

    def text(self):
        return self._text

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        dark = isDarkTheme()
        c = 255 if dark else 0
        if self.isCompacted:
            if self.isEnter:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(c, c, c, 10))
                painter.drawRoundedRect(QRectF(self.rect()), 5, 5)
            FluentIcon.SEARCH.icon(color=text_color()).paint(painter, 12, 10, 16, 16)
            return
        rect = QRectF(4, 1, self.width() - 8, self.height() - 2)
        painter.setPen(QPen(QColor(255, 255, 255, 22) if dark else QColor(0, 0, 0, 26), 1))
        painter.setBrush(QColor(255, 255, 255, 18 if self.isEnter else 11) if dark
                         else QColor(255, 255, 255, 230 if self.isEnter else 190))
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)
        secondary = text_color(secondary=True)
        FluentIcon.SEARCH.icon(color=secondary).paint(painter, 14, 11, 14, 14)
        painter.setFont(getFont(12))
        key_width = painter.fontMetrics().horizontalAdvance(self._shortcut) + 12
        key_rect = QRectF(rect.right() - key_width - 6, rect.center().y() - 9, key_width, 18)
        painter.setPen(QPen(QColor(255, 255, 255, 40) if dark else QColor(0, 0, 0, 40), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(key_rect, 4, 4)
        painter.setPen(secondary)
        painter.drawText(key_rect, Qt.AlignmentFlag.AlignCenter, self._shortcut)
        painter.setFont(getFont(13))
        text_rect = QRectF(36, 0, key_rect.left() - 42, self.height())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         painter.fontMetrics().elidedText(self._text, Qt.TextElideMode.ElideRight, int(text_rect.width())))
