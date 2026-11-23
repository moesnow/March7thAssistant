"""帮助页左侧：文档列表、本页目录和「没找到答案？」卡片。"""
import html

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import isDarkTheme, setFont

from app.common.mascot import Mascot, load_mascot
from app.overview.style import accent, brand, css, text_color, tone, with_alpha
from app.overview.widgets import LinkButton
from app.pages.common import border_color, icon_of, is_evernight
from module.localization import tr
from . import style


class SidePanel(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(QRect(self.width() - 1, 0, 1, self.height()), border_color())


class DocItem(QWidget):
    clicked = Signal(str)

    def __init__(self, manual, parent=None):
        super().__init__(parent)
        self.key = manual.id
        self.manual = manual
        self._icon = icon_of(manual.icon)
        self._text = tr(manual.name)
        self._badge = ""
        self._selected = False
        self._hover = False
        self.setFixedHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def retranslate(self):
        self._text = tr(self.manual.name)
        self.update()

    def setBadge(self, text):
        self._badge = text or ""
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
        evernight = is_evernight()
        if self._selected or self._hover:
            painter.setBrush(QColor(c, c, c, 16 if self._selected else 9))
            painter.drawRoundedRect(QRectF(self.rect()), 5, 5)
        if self._selected:
            painter.setBrush(accent(evernight))
            painter.drawRoundedRect(QRectF(0, self.height() / 2 - 8, 3, 16), 1.5, 1.5)
        self._icon.icon(color=text_color()).paint(painter, QRect(12, (self.height() - 16) // 2, 16, 16))
        badge_width = 0
        if self._badge:
            font = style.font(11, QFont.Weight.DemiBold)
            badge_width = round(QFontMetricsF(font).horizontalAdvance(self._badge)) + 14
            rect = QRectF(self.width() - badge_width - 8, (self.height() - 18) / 2, badge_width, 18)
            background, foreground = tone("accent", evernight)
            painter.setBrush(background)
            painter.drawRoundedRect(rect, 9, 9)
            painter.setPen(foreground)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._badge)
            badge_width += 8
        painter.setPen(text_color())
        painter.setFont(style.font(14, QFont.Weight.DemiBold if self._selected else QFont.Weight.Normal))
        rect = QRectF(40, 0, self.width() - 40 - badge_width - 8, self.height())
        text = painter.fontMetrics().elidedText(self._text, Qt.TextElideMode.ElideRight, round(rect.width()))
        painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)


class DocList(QWidget):
    currentChanged = Signal(str)

    def __init__(self, manuals, parent=None):
        super().__init__(parent)
        self.items = {}
        self._current = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        for manual in manuals:
            item = DocItem(manual, self)
            item.clicked.connect(self._clicked)
            self.items[manual.id] = item
            layout.addWidget(item)

    def _clicked(self, key):
        self.setCurrent(key)
        self.currentChanged.emit(key)

    def current(self):
        return self._current

    def setCurrent(self, key):
        self._current = key if key in self.items else None
        for name, item in self.items.items():
            item.setSelected(name == self._current)

    def setBadge(self, key, text):
        if key in self.items:
            self.items[key].setBadge(text)

    def retranslate(self):
        for item in self.items.values():
            item.retranslate()


class TocView(QWidget):
    """本页目录：二级标题顶格，三级标题缩进；当前小节用强调色和左侧指示条标出。"""

    entryClicked = Signal(str)
    currentMoved = Signal(int, int)
    ROW = 26

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries = []
        self._current = ""
        self._hover = -1
        self.setMouseTracking(True)
        self.setFixedHeight(0)

    def setEntries(self, anchors):
        levels = [a.level for a in anchors]
        top = min(levels) if levels else 2
        self._entries = [(min(2, a.level - top), a.title, a.anchor) for a in anchors]
        self._current = self._entries[0][2] if self._entries else ""
        self._hover = -1
        self.setFixedHeight(len(self._entries) * self.ROW + (6 if self._entries else 0))
        self.update()
        self.currentMoved.emit(0, self.ROW)

    def entries(self):
        return list(self._entries)

    def current(self):
        return self._current

    def setCurrent(self, anchor):
        if anchor == self._current or not any(e[2] == anchor for e in self._entries):
            return
        self._current = anchor
        self.update()
        index = next(i for i, e in enumerate(self._entries) if e[2] == anchor)
        self.currentMoved.emit(index * self.ROW, self.ROW)

    def _index(self, y):
        index = int(y // self.ROW)
        return index if 0 <= index < len(self._entries) else -1

    def mouseMoveEvent(self, event):
        index = self._index(event.position().y())
        if index != self._hover:
            self._hover = index
            self.setCursor(Qt.CursorShape.PointingHandCursor if index >= 0 else Qt.CursorShape.ArrowCursor)
            self.setToolTip(self._entries[index][1] if index >= 0 else "")
            self.update()

    def leaveEvent(self, event):
        self._hover = -1
        self.update()

    def mouseReleaseEvent(self, event):
        index = self._index(event.position().y())
        if event.button() == Qt.MouseButton.LeftButton and index >= 0:
            self.entryClicked.emit(self._entries[index][2])

    def paintEvent(self, event):
        if not self._entries:
            return
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        line_x = 10.5
        painter.setPen(QPen(border_color(), 1))
        painter.drawLine(QPointF(line_x, 2), QPointF(line_x, self.height() - 2))
        evernight = is_evernight()
        for index, (depth, title, anchor) in enumerate(self._entries):
            top = index * self.ROW
            current = anchor == self._current
            if current:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(brand(evernight))
                painter.drawRoundedRect(QRectF(line_x - 1, top + 5, 2.5, self.ROW - 10), 1.2, 1.2)
            size = 13 if depth == 0 else 12
            weight = QFont.Weight.DemiBold if current else QFont.Weight.Normal
            font = style.font(size, weight)
            painter.setFont(font)
            if current:
                painter.setPen(accent(evernight))
            elif index == self._hover:
                painter.setPen(text_color())
            else:
                painter.setPen(text_color(secondary=True) if depth == 0 else style.muted())
            left = 22 + depth * 12
            rect = QRectF(left, top, self.width() - left - 4, self.ROW)
            text = painter.fontMetrics().elidedText(title, Qt.TextElideMode.ElideRight, round(rect.width()))
            painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)


class SupportCard(QWidget):
    """「没找到答案？」：认真姿势的三月七，引导去常见问题，或带上日志去 QQ 群提问。"""

    faqClicked = Signal()
    qqClicked = Signal()
    logsClicked = Signal()
    MASCOT_HEIGHT = 100
    TEXT_LEFT = 84

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = None
        self.titleLabel = QLabel(self)
        setFont(self.titleLabel, 13, QFont.Weight.DemiBold)
        self.bodyLabel = QLabel(self)
        setFont(self.bodyLabel, 12)
        self.bodyLabel.setWordWrap(True)
        self.bodyLabel.setTextFormat(Qt.TextFormat.RichText)
        self.bodyLabel.linkActivated.connect(self._link)
        self.faqButton = LinkButton("", self, size=12)
        self.faqButton.clicked.connect(self.faqClicked)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.TEXT_LEFT, 12, 10, 12)
        layout.setSpacing(3)
        layout.addWidget(self.titleLabel)
        layout.addWidget(self.bodyLabel)
        layout.addWidget(self.faqButton, 0, Qt.AlignmentFlag.AlignLeft)
        self.setMinimumHeight(self.MASCOT_HEIGHT + 4)
        self.retranslate()

    def retranslate(self):
        self.titleLabel.setText(tr("没找到答案？"))
        self.faqButton.setText(tr("打开常见问题") + " ›")
        self.restyle()

    def restyle(self):
        evernight = is_evernight()
        color = css(accent(evernight))
        self.titleLabel.setStyleSheet(f"color: {css(text_color())}; background: transparent;")
        self.bodyLabel.setStyleSheet(f"color: {css(text_color(secondary=True))}; background: transparent;")
        text = html.escape(tr("换个说法搜索，或带上日志去 QQ 群提问"))
        # 「日志」「QQ 群」做成链接；译文里找不到对应词时只显示文字。
        for key, word in (("log-folder", tr("日志")), ("qq", tr("QQ 群"))):
            escaped = html.escape(word)
            if escaped and escaped in text:
                text = text.replace(escaped, f'<a href="{key}" style="color: {color}; text-decoration: none;">{escaped}</a>', 1)
        self.bodyLabel.setText(text)
        self.faqButton.setEvernight(evernight)
        self._pixmap = None
        self.update()

    def _link(self, key):
        (self.logsClicked if key == "log-folder" else self.qqClicked).emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        evernight = is_evernight()
        dark = isDarkTheme()
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        pink = with_alpha(brand(evernight), 0.16 if dark else 0.16)
        sky = QColor(124, 195, 242, 34) if dark else QColor(100, 181, 236, 40)
        gradient.setColorAt(0, pink)
        gradient.setColorAt(1, sky)
        painter.fillPath(path, gradient)
        if self._pixmap is None:
            self._pixmap = load_mascot(Mascot.SERIOUS, self.MASCOT_HEIGHT, self.devicePixelRatioF(), evernight=evernight)
        if self._pixmap is not None and not self._pixmap.isNull():
            ratio = self._pixmap.devicePixelRatio() or 1
            width = self._pixmap.width() / ratio
            height = self._pixmap.height() / ratio
            painter.save()
            painter.setClipPath(path)
            x = max(0.0, (self.TEXT_LEFT - width) / 2)
            painter.drawPixmap(QPointF(x, rect.height() - height + 2), self._pixmap)
            painter.restore()
