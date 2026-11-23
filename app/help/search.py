"""帮助页内搜索的结果：命中的小节、所在位置和带关键词的摘要。"""
import html

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, ScrollArea, SubtitleLabel, isDarkTheme, setFont

from app.common.mascot import Mascot, load_mascot
from app.overview.style import accent, css, text_color
from app.overview.widgets import LinkButton
from app.pages.common import Divider, is_evernight, secondary
from module.localization import tr
from . import style


def marked(text, matches, color):
    """摘要里命中的片段加粗并用强调色。matches 是 Python 字符串上的半开区间。"""
    parts, position = [], 0
    for start, end in sorted(matches):
        if start < position or end <= start:
            continue
        parts.append(html.escape(text[position:start]))
        parts.append(f'<span style="color: {color}; font-weight: 600;">{html.escape(text[start:end])}</span>')
        position = end
    parts.append(html.escape(text[position:]))
    return "".join(parts)


class HitRow(QWidget):
    clicked = Signal(object)

    def __init__(self, hit, parent=None):
        super().__init__(parent)
        self.hit = hit
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.locationLabel = secondary(CaptionLabel(hit.section.location, self))
        self.titleLabel = QLabel(self)
        setFont(self.titleLabel, 15, QFont.Weight.DemiBold)
        self.snippetLabel = QLabel(self)
        setFont(self.snippetLabel, 13)
        self.snippetLabel.setWordWrap(True)
        self.snippetLabel.setTextFormat(Qt.TextFormat.RichText)
        for label in (self.locationLabel, self.titleLabel, self.snippetLabel):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(3)
        layout.addWidget(self.locationLabel)
        layout.addWidget(self.titleLabel)
        layout.addWidget(self.snippetLabel)
        self.restyle()

    def restyle(self):
        self.titleLabel.setText(self.hit.section.title)
        self.titleLabel.setStyleSheet(f"color: {css(text_color())}; background: transparent;")
        self.snippetLabel.setStyleSheet(f"color: {css(text_color(secondary=True))}; background: transparent;")
        self.snippetLabel.setText(marked(self.hit.snippet, self.hit.matches, css(accent(is_evernight()))))
        self.snippetLabel.setVisible(bool(self.hit.snippet))

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.hit)

    def paintEvent(self, event):
        if not self._hover:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        c = 255 if isDarkTheme() else 0
        painter.setBrush(QColor(c, c, c, 9))
        painter.drawRoundedRect(QRectF(self.rect()), 8, 8)


class EmptyState(QWidget):
    """搜不到时：拿放大镜的三月七和「换个说法试试」。"""

    suggestionClicked = Signal(str)
    MASCOT_HEIGHT = 200

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = None
        self.titleLabel = QLabel(self)
        setFont(self.titleLabel, 16, QFont.Weight.DemiBold)
        self.titleLabel.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.hintLabel = secondary(CaptionLabel(self))
        self.hintLabel.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.suggestionRow = QHBoxLayout()
        self.suggestionRow.setSpacing(14)
        self.buttons = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, self.MASCOT_HEIGHT + 24, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.titleLabel)
        layout.addWidget(self.hintLabel)
        layout.addSpacing(4)
        layout.addLayout(self.suggestionRow)

    def setContent(self, suggestions):
        self.titleLabel.setText(tr("没有找到相关内容"))
        self.titleLabel.setStyleSheet(f"color: {css(text_color())}; background: transparent;")
        self.hintLabel.setText(tr("换个说法试试：") if suggestions else tr("换个说法，或者少输入几个字试试。"))
        for button in self.buttons:
            self.suggestionRow.removeWidget(button)
            button.deleteLater()
        self.buttons = []
        while self.suggestionRow.count():
            self.suggestionRow.takeAt(0)
        self.suggestionRow.addStretch(1)
        for word in suggestions[:6]:
            button = LinkButton(word, self, size=13)
            button.setEvernight(is_evernight())
            button.clicked.connect(lambda checked=False, w=word: self.suggestionClicked.emit(w))
            self.suggestionRow.addWidget(button)
            self.buttons.append(button)
        self.suggestionRow.addStretch(1)
        self._pixmap = None
        self.update()

    def paintEvent(self, event):
        if self._pixmap is None:
            self._pixmap = load_mascot(Mascot.SEARCH, self.MASCOT_HEIGHT, self.devicePixelRatioF(),
                                       evernight=is_evernight())
        if self._pixmap is None or self._pixmap.isNull():
            return
        ratio = self._pixmap.devicePixelRatio() or 1
        width = self._pixmap.width() / ratio
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(round((self.width() - width) / 2), 8, self._pixmap)


class HelpSearchPage(ScrollArea):
    hitClicked = Signal(object)
    suggestionClicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view = QWidget()
        self.view.setObjectName("view")
        self.setWidget(self.view)
        self.view.setStyleSheet("#view{background: transparent}")
        outer = QHBoxLayout(self.view)
        outer.setContentsMargins(36, 22, 36, 36)
        outer.setSpacing(0)
        self.column = QWidget(self.view)
        self.column.setMaximumWidth(style.READING_WIDTH)
        outer.addStretch(1)
        outer.addWidget(self.column, 100)
        outer.addStretch(1)
        self.vBoxLayout = QVBoxLayout(self.column)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setSpacing(2)
        self.titleLabel = SubtitleLabel(self.column)
        self.countLabel = secondary(CaptionLabel(self.column))
        self.empty = EmptyState(self.column)
        self.empty.suggestionClicked.connect(self.suggestionClicked)
        self.vBoxLayout.addWidget(self.titleLabel)
        self.vBoxLayout.addWidget(self.countLabel)
        self.vBoxLayout.addSpacing(10)
        self.vBoxLayout.addWidget(self.empty)
        self.rows = []
        self.vBoxLayout.addStretch(1)
        self._query = ""
        self._results = None

    def setResults(self, query, results):
        self._query, self._results = query, results
        for row in self.rows:
            self.vBoxLayout.removeWidget(row)
            row.hide()
            row.deleteLater()
        self.rows = []
        hits = tuple(results.hits)
        self.titleLabel.setText(tr("搜索「{query}」").format(query=query))
        self.countLabel.setText(tr("找到 {count} 个相关小节").format(count=len(hits)) if hits else "")
        self.countLabel.setVisible(bool(hits))
        self.empty.setVisible(not hits)
        if not hits:
            self.empty.setContent(tuple(results.suggestions))
        index = self.vBoxLayout.indexOf(self.empty) + 1
        for hit in hits:
            row = HitRow(hit, self.column)
            row.clicked.connect(self.hitClicked)
            self.vBoxLayout.insertWidget(index, row)
            index += 1
            self.rows.append(row)
        self.verticalScrollBar().setValue(0)

    def restyle(self):
        for row in self.rows:
            row.restyle()
        if self._results is not None and not self._results.hits:
            self.empty.setContent(tuple(self._results.suggestions))
