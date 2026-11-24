"""账号头像：首字加渐变底色，不使用游戏头像。颜色编号在添加账号时定下，不随顺序变化。"""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget

from app.pages import style

GRADIENTS = (("#d6739f", "#6f93dc"), ("#7c6be0", "#4fb3c6"), ("#e08a3c", "#d9546b"),
             ("#4fae8a", "#4a86cf"), ("#a772dc", "#d974a3"), ("#c2912f", "#5fa25a"))


def initial(name):
    """「开拓者 · 主号」取「主」，没有分隔点就取第一个字。"""
    name = (name or "").strip()
    tail = name.replace("・", "·").rsplit("·", 1)[-1].strip() or name
    return tail[:1].upper() or "?"


def paint_avatar(painter, rect, color, name, *, faded=False):
    rect = QRectF(rect)
    start, end = GRADIENTS[int(color or 0) % len(GRADIENTS)]
    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradient.setColorAt(0, QColor(start))
    gradient.setColorAt(1, QColor(end))
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if faded:
        painter.setOpacity(0.55)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawEllipse(rect)
    painter.setPen(QColor(255, 255, 255))
    painter.setFont(style.strong(max(10, round(rect.height() * 0.42))))
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, initial(name))
    painter.restore()


class Avatar(QWidget):
    def __init__(self, size=32, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._color, self._name, self._faded = 0, "", False

    def setAccount(self, color, name, *, faded=False):
        self._color, self._name, self._faded = color, name, faded
        self.update()

    def paintEvent(self, event):
        paint_avatar(QPainter(self), QRectF(self.rect()), self._color, self._name, faded=self._faded)
