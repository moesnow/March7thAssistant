"""设置页左侧的竖向分类列表。"""
from PySide6.QtCore import QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import getFont, isDarkTheme

from app.overview.style import accent, text_color
from .common import icon_of, is_evernight


class CategoryItem(QWidget):
    clicked = Signal(str)

    def __init__(self, key, icon, text, parent=None):
        super().__init__(parent)
        self.key = key
        self._icon = icon_of(icon)
        self._text = text
        self._hint = ""
        self._selected = False
        self._hover = False
        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def setText(self, text):
        self._text = text
        self.update()

    def text(self):
        return self._text

    def setHint(self, hint):
        self._hint = hint or ""
        self.update()

    def setSelected(self, selected):
        self._selected = bool(selected)
        self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.key)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        c = 255 if isDarkTheme() else 0
        if self._selected or self._hover:
            painter.setBrush(QColor(c, c, c, 16 if self._selected else 9))
            painter.drawRoundedRect(QRectF(self.rect()), 5, 5)
        if self._selected:
            painter.setBrush(accent(is_evernight()))
            painter.drawRoundedRect(QRectF(0, self.height() / 2 - 8, 3, 16), 1.5, 1.5)
        self._icon.icon(color=text_color()).paint(painter, QRect(14, (self.height() - 16) // 2, 16, 16))
        painter.setPen(text_color())
        painter.setFont(getFont(14, QFont.Weight.DemiBold if self._selected else QFont.Weight.Normal))
        hint_width = 0
        if self._hint:
            font = getFont(12)
            painter.save()
            painter.setFont(font)
            hint_width = painter.fontMetrics().horizontalAdvance(self._hint) + 12
            painter.setPen(text_color(secondary=True))
            painter.drawText(QRectF(0, 0, self.width() - 12, self.height()),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, self._hint)
            painter.restore()
        painter.drawText(QRectF(42, 0, self.width() - 42 - hint_width - 8, self.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._text)


class CategoryList(QWidget):
    currentChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = {}
        self._current = None
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setSpacing(2)

    def addCategory(self, key, icon, text):
        item = CategoryItem(key, icon, text, self)
        item.clicked.connect(self._clicked)
        self.items[key] = item
        self.vBoxLayout.addWidget(item)
        return item

    def _clicked(self, key):
        if key != self._current:
            self.setCurrent(key)
            self.currentChanged.emit(key)

    def current(self):
        return self._current

    def setCurrent(self, key):
        self._current = key
        for name, item in self.items.items():
            item.setSelected(name == key)

    def setHint(self, key, hint):
        if key in self.items:
            self.items[key].setHint(hint)
