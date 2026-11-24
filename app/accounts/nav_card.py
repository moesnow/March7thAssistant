"""侧栏顶部的账号卡：显示正在查看的账号，点开可以切换。"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from qfluentwidgets import isDarkTheme
from qfluentwidgets.components.navigation.navigation_widget import NavigationWidget

from app.pages import style
from module.localization import tr
from .avatar import paint_avatar

HEIGHT = 52


class AccountNavCard(NavigationWidget):
    def __init__(self, parent=None):
        super().__init__(isSelectable=False, parent=parent)
        self._color, self._name, self._line = 0, "", ""
        self._kind = ""
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText("")

    def setCompacted(self, isCompacted):
        super().setCompacted(isCompacted)
        if not isCompacted:
            self.setFixedSize(self.EXPAND_WIDTH, HEIGHT)
        self.update()

    def setAccount(self, color, name, line, kind=""):
        """kind 为 error、warning 时第二行用对应的颜色。"""
        self._color, self._name, self._line, self._kind = color, name, line, kind
        self.setAccessibleName(f"{name} {line}".strip())
        self.setToolTip(f"{name}\n{line}" if line else name)
        self.update()

    def setSelected(self, isSelected):
        """显示账号页时高亮账号卡；点击只打开切换浮层，不直接切页。"""
        if self.isSelected != isSelected:
            self.isSelected = isSelected
            self.update()

    def setText(self, text):
        """主窗口换语言时统一调用；账号卡的文字由 setAccount 更新。"""

    def text(self):
        return self._name

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        dark = isDarkTheme()
        if self.isCompacted:
            paint_avatar(painter, QRectF(self.rect()).adjusted(6, 4, -6, -4), self._color, self._name)
            return
        rect = QRectF(4, 1, self.width() - 8, self.height() - 2)
        painter.setPen(QPen(QColor(255, 255, 255, 22) if dark else QColor(0, 0, 0, 26), 1))
        hot = self.isEnter or self.isPressed
        painter.setBrush(QColor(255, 255, 255, 22 if hot else 14) if dark else QColor(255, 255, 255, 245 if hot else 210))
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)
        center = rect.center().y()
        if self.isSelected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(style.link())
            painter.drawRoundedRect(QRectF(rect.left(), center - 9, 3, 18), 1.5, 1.5)
        paint_avatar(painter, QRectF(rect.left() + 9, center - 16, 32, 32), self._color, self._name)
        left = rect.left() + 51
        right = rect.right() - 26
        align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        width = int(right - left)
        painter.setFont(style.strong(13))
        painter.setPen(style.primary())
        name = painter.fontMetrics().elidedText(self._name, Qt.TextElideMode.ElideRight, width)
        painter.drawText(QRectF(left, center - 19, width, 20), align, name)
        painter.setFont(style.font(12))
        painter.setPen(style.status_line(self._kind) if self._kind else style.muted())
        line = painter.fontMetrics().elidedText(self._line, Qt.TextElideMode.ElideRight, width)
        painter.drawText(QRectF(left, center + 1, width, 18), align, line)
        painter.setPen(style.stroke(style.muted(), 1.3))
        x = rect.right() - 16
        painter.drawPolyline(QPolygonF([QPointF(x - 4, center - 2), QPointF(x, center + 2), QPointF(x + 4, center - 2)]))
