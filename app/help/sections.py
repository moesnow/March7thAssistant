"""常见问题的问答卡片和更新日志的版本卡片。正文第一次展开时才建造，打开长文档不卡顿。"""
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import isDarkTheme

from app.overview.style import tone
from app.pages.common import Chevron, border_color, is_evernight, surface_color
from module.docs.formats import version_content
from module.docs.model import Text
from module.localization import tr
from module.logger import log
from . import style
from .blocks import build_blocks
from .richtext import RichText


class TagPill(QWidget):
    def __init__(self, text, kind, parent):
        super().__init__(parent)
        self._text, self._kind = text, kind
        self._font = style.font(12)
        width = QFontMetricsF(self._font).horizontalAdvance(text)
        self.setFixedSize(round(width) + 18, 22)

    def paintEvent(self, event):
        background, foreground = tone(self._kind, is_evernight())
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(QRectF(self.rect()), 11, 11)
        painter.setPen(foreground)
        painter.setFont(self._font)
        painter.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, self._text)


class QuestionMark(QWidget):
    """问答卡片前面的「Q」。"""

    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedSize(22, 22)

    def paintEvent(self, event):
        background, foreground = tone("accent", is_evernight())
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(QRectF(self.rect()), 6, 6)
        painter.setPen(foreground)
        painter.setFont(style.font(13, QFont.Weight.DemiBold))
        painter.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, "Q")


class FoldHeader(QWidget):
    clicked = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(16, 13, 14, 13)
        self.row.setSpacing(12)
        self.chevron = Chevron(self)

    def finish(self):
        self.row.addWidget(self.chevron, 0, Qt.AlignmentFlag.AlignVCenter)

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()

    def paintEvent(self, event):
        if not self._hover:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        c = 255 if isDarkTheme() else 0
        painter.setBrush(QColor(c, c, c, 8))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 7, 7)


class FoldCard(QWidget):
    toggled = Signal(bool)

    def __init__(self, parent, anchor):
        super().__init__(parent)
        self.anchor = anchor
        self._expanded = False
        self._built = False
        self.header = FoldHeader(self)
        self.header.clicked.connect(self.toggle)
        self.body = QWidget(self)
        self.bodyLayout = QVBoxLayout(self.body)
        self.bodyLayout.setContentsMargins(50, 0, 22, 16)
        self.bodyLayout.setSpacing(0)
        self.body.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.body)

    def populate(self):
        pass

    def isExpanded(self):
        return self._expanded

    def setExpanded(self, expanded):
        expanded = bool(expanded)
        if expanded and not self._built:
            self._built = True
            try:
                self.populate()
            except Exception as exc:
                log.warning(f"帮助文档的展开内容无法显示：{type(exc).__name__}: {exc}")
        changed = expanded != self._expanded
        self._expanded = expanded
        self.body.setVisible(expanded)
        self.header.chevron.setUp(expanded)
        if changed:
            self.toggled.emit(expanded)

    def toggle(self):
        self.setExpanded(not self._expanded)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(border_color(), 1))
        painter.setBrush(surface_color())
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)


class QuestionCard(FoldCard):
    def __init__(self, question, ctx, parent):
        super().__init__(parent, question.anchor)
        self.question, self.ctx = question, ctx
        self.mark = QuestionMark(self.header)
        self.title = RichText((Text(question.title),), self.header, size=style.BODY, weight=QFont.Weight.DemiBold,
                              ratio=1.55, interactive=False)
        self.header.row.addWidget(self.mark, 0, Qt.AlignmentFlag.AlignTop)
        self.header.row.addWidget(self.title, 1)
        self.header.finish()
        ctx.register(question.anchor, self)

    def populate(self):
        build_blocks(self.question.blocks, self.ctx, self.body, self.bodyLayout)


class VersionCard(FoldCard):
    def __init__(self, entry, history, ctx, parent, *, current=False):
        super().__init__(parent, entry.anchor)
        self.entry, self.history, self.ctx = entry, history, ctx
        self.bodyLayout.setContentsMargins(18, 0, 22, 18)
        self.title = RichText((Text(entry.version),), self.header, size=16, weight=QFont.Weight.DemiBold,
                              ratio=1.4, interactive=False)
        self.header.row.addWidget(self.title, 0)
        if current:
            self.header.row.addWidget(TagPill(tr("当前版本"), "accent", self.header))
        if entry.prerelease:
            self.header.row.addWidget(TagPill(tr("测试版"), "warning", self.header))
        self.header.row.addStretch(1)
        self.header.finish()
        ctx.register(entry.anchor, self)

    def populate(self):
        content = version_content(self.history, self.entry)
        if content is None:
            text = RichText((Text(tr("这个版本的说明暂时无法显示。")),), self.body, color="secondary")
            self.bodyLayout.addWidget(text)
            return
        build_blocks(content.blocks, self.ctx, self.body, self.bodyLayout)
