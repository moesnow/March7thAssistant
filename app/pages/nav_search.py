"""侧栏顶部的搜索入口：展开时像一个搜索框，收起时只剩放大镜。点击打开全局搜索。"""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPen
from qfluentwidgets import FluentIcon, getFont, isDarkTheme
from qfluentwidgets.components.navigation.navigation_widget import NavigationWidget

from app.overview.style import text_color
from module.localization import tr


class NavigationSearchBox(NavigationWidget):
    def __init__(self, parent=None):
        super().__init__(isSelectable=False, parent=parent)
        self._text = tr("搜索功能、设置、帮助")
        self._short = tr("搜索")
        self._shortcut = "Ctrl K"
        self.setToolTip(tr("搜索（Ctrl+K）"))

    def setText(self, text):
        self._text = text
        self._short = tr("搜索")
        self.update()

    def text(self):
        return self._text

    def _rects(self):
        """搜索框、快捷键和文字的位置。"""
        box = QRectF(4, 1, self.width() - 8, self.height() - 2)
        key_width = QFontMetricsF(getFont(12)).horizontalAdvance(self._shortcut) + 12
        key = QRectF(box.right() - key_width - 6, box.center().y() - 9, key_width, 18)
        return box, key, QRectF(35, 0, key.left() - 41, self.height())

    def shownText(self):
        """放不下全文时只写「搜索」，不留半截文字。"""
        width = QFontMetricsF(getFont(13)).horizontalAdvance(self._text)
        return self._text if width <= self._rects()[2].width() else self._short

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
        rect, key_rect, text_rect = self._rects()
        painter.setPen(QPen(QColor(255, 255, 255, 22) if dark else QColor(0, 0, 0, 26), 1))
        painter.setBrush(QColor(255, 255, 255, 18 if self.isEnter else 11) if dark
                         else QColor(255, 255, 255, 230 if self.isEnter else 190))
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)
        secondary = text_color(secondary=True)
        FluentIcon.SEARCH.icon(color=secondary).paint(painter, 14, 11, 14, 14)
        painter.setFont(getFont(12))
        painter.setPen(QPen(QColor(255, 255, 255, 40) if dark else QColor(0, 0, 0, 40), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(key_rect, 4, 4)
        painter.setPen(secondary)
        painter.drawText(key_rect, Qt.AlignmentFlag.AlignCenter, self._shortcut)
        painter.setFont(getFont(13))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.shownText())
