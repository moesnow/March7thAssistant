"""搜索结果行：全局搜索弹窗和设置页内搜索共用。"""
import html

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, getFont, isDarkTheme

from app.overview.style import accent, css, text_color
from app.overview.widgets import ElidedLabel, IconTile
from module.search import normalize
from .common import icon_of, is_evernight, secondary


def highlight(text, query, color):
    """把查询词在名称里出现的位置标成强调色。"""
    terms = [t for t in normalize(query).split() if t]
    folded = normalize(text) if len(normalize(text)) == len(text) else None
    if not terms or folded is None:
        return html.escape(text)
    marks = [False] * len(text)
    for term in terms:
        start = folded.find(term)
        while start >= 0:
            for index in range(start, start + len(term)):
                marks[index] = True
            start = folded.find(term, start + len(term))
    parts, run, current = [], "", False
    for char, marked in zip(text, marks):
        if marked != current and run:
            parts.append(f'<span style="color:{color}">{html.escape(run)}</span>' if current else html.escape(run))
            run = ""
        run += char
        current = marked
    if run:
        parts.append(f'<span style="color:{color}">{html.escape(run)}</span>' if current else html.escape(run))
    return "".join(parts)


class ResultRow(QWidget):
    clicked = Signal(object)

    def __init__(self, result, query, parent=None):
        super().__init__(parent)
        self.result = result
        self._query = query
        self._selected = False
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(56)
        self.tile = IconTile(self, size=32, icon_size=16)
        self.nameLabel = QLabel(self)
        self.nameLabel.setTextFormat(Qt.TextFormat.RichText)
        self.nameLabel.setFont(getFont(14, QFont.Weight.DemiBold))
        self.nameLabel.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.detailLabel = secondary(ElidedLabel(self, size=12))
        detail = result.location
        if result.description:
            detail = f"{detail}    {result.description}" if detail else result.description
        self.detailLabel.setFullText(detail)
        self.valueLabel = secondary(CaptionLabel(result.value or "", self))
        self.valueLabel.setVisible(bool(result.value))
        column = QVBoxLayout()
        column.setSpacing(2)
        column.addWidget(self.nameLabel)
        column.addWidget(self.detailLabel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 16, 6)
        layout.setSpacing(12)
        layout.addWidget(self.tile)
        layout.addLayout(column, 1)
        layout.addWidget(self.valueLabel)
        self.restyle()

    def restyle(self):
        evernight = is_evernight()
        self.tile.setIcon(icon_of(self.result.icon), "accent" if self._selected else "neutral", evernight=evernight)
        self.nameLabel.setText(f'<span style="color:{css(text_color())}">'
                               f'{highlight(self.result.name, self._query, css(accent(evernight)))}</span>')

    def setSelected(self, selected):
        if self._selected != bool(selected):
            self._selected = bool(selected)
            self.restyle()
            self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.result)

    def paintEvent(self, event):
        if not (self._selected or self._hover):
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        c = 255 if isDarkTheme() else 0
        painter.setBrush(QColor(c, c, c, 14 if self._selected else 8))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(4, 1, -4, -1), 6, 6)
        if self._selected:
            painter.setBrush(accent(is_evernight()))
            painter.drawRoundedRect(QRectF(4, self.height() / 2 - 9, 3, 18), 1.5, 1.5)
