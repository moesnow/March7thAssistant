"""把文档的块模型画成控件。每种块一个控件；列表、提示框、折叠块里的内容递归调用 build_blocks。"""
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, QUrl, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QGridLayout, QHBoxLayout, QPushButton, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, IconWidget, InfoBarIcon, isDarkTheme, setFont

from app.overview.style import text_color, with_alpha
from app.pages.common import Chevron, Divider, border_color, surface_color
from module.docs.model import (Callout, CodeBlock, CodeToken, Details, Divider as DividerBlock, Heading, Image,
                               Link, ListBlock, Paragraph, Table, Text, block_text)
from module.localization import tr
from module.logger import log
from . import style
from .richtext import RichText

HEADING_SIZES = {1: 28, 2: 20, 3: 16}
BOXES = (Table, Callout, CodeBlock, Image, Details, DividerBlock)
BULLETS = ("•", "◦", "▪")
CALLOUT_ICONS = {"info": InfoBarIcon.INFORMATION, "tip": InfoBarIcon.SUCCESS, "warning": InfoBarIcon.WARNING,
                 "danger": InfoBarIcon.ERROR, "declaration": FluentIcon.LANGUAGE}


class BlockContext:
    """一篇文档渲染时共用的东西：链接交给谁打开、锚点落在哪个控件上。"""

    def __init__(self, page):
        self.page = page
        self.anchors = {}

    def register(self, anchor, widget):
        if anchor and anchor not in self.anchors:
            self.anchors[anchor] = widget

    def connect(self, text):
        text.linkActivated.connect(self.page.activate)
        return text


def _gap(previous, block, compact):
    if compact:
        return 4 if isinstance(block, ListBlock) or isinstance(previous, ListBlock) else 6
    if isinstance(block, Heading):
        return {2: 30, 3: 20}.get(block.level, 16)
    if isinstance(previous, Heading):
        return 8 if previous.level <= 2 else 6
    if isinstance(block, BOXES) or isinstance(previous, BOXES):
        return 14
    return 10


def build_blocks(blocks, ctx, parent, layout, *, size=style.BODY, compact=False, depth=0, color=None):
    previous = None
    for block in blocks:
        try:
            widget = make_block(block, ctx, parent, size, depth, color)
        except Exception as exc:
            # 单个块画不出来时退成纯文本，不影响整篇。
            log.warning(f"帮助文档的一个块无法显示，已改用纯文本：{type(exc).__name__}: {exc}")
            widget = ctx.connect(RichText((Text(block_text(block)),), parent, size=size, color=color))
        if widget is None:
            continue
        if previous is not None:
            layout.addSpacing(_gap(previous, block, compact))
        layout.addWidget(widget)
        previous = block


def make_block(block, ctx, parent, size=style.BODY, depth=0, color=None):
    if isinstance(block, Heading):
        return HeadingView(block, ctx, parent)
    if isinstance(block, Paragraph):
        return ctx.connect(RichText(block.spans, parent, size=size, color=color))
    if isinstance(block, ListBlock):
        return ListView(block, ctx, parent, size, depth, color)
    if isinstance(block, Table):
        return TableView(block, ctx, parent)
    if isinstance(block, Callout):
        return CalloutView(block, ctx, parent)
    if isinstance(block, CodeBlock):
        return CodeView(block, ctx, parent)
    if isinstance(block, DividerBlock):
        return Divider(parent)
    if isinstance(block, Image):
        if block.path is not None and not QPixmap(str(block.path)).isNull():
            return ImageView(block, parent)
        link = block.link or (Link("external", block.url) if block.url else None)
        label = tr("图片：{name}").format(name=block.alt) if block.alt else tr("图片")
        return ctx.connect(RichText((Text(label, link=link),), parent, size=size, color="secondary"))
    if isinstance(block, Details):
        return DetailsView(block, ctx, parent, size)
    return None


class HashButton(QWidget):
    """标题旁的「#」：复制这一节的官网链接，方便发给别人。"""
    clicked = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tr("复制本节的官网链接"))
        self._hover = False

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
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        if self._hover:
            c = 255 if isDarkTheme() else 0
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(c, c, c, 18))
            painter.drawRoundedRect(QRectF(self.rect()), 5, 5)
        painter.setPen(style.link_color() if self._hover else style.muted())
        painter.setFont(style.font(16))
        painter.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, "#")


class HeadingView(QWidget):
    def __init__(self, block, ctx, parent):
        super().__init__(parent)
        self.block = block
        self.anchor = block.anchor
        size = HEADING_SIZES.get(block.level, 14)
        self.text = ctx.connect(RichText(block.spans, self, size=size, weight=QFont.Weight.DemiBold, ratio=1.45))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.text, 0)
        self.hash = None
        if block.level in (2, 3) and block.anchor:
            self.hash = HashButton(self)
            policy = self.hash.sizePolicy()
            policy.setRetainSizeWhenHidden(True)
            self.hash.setSizePolicy(policy)
            self.hash.hide()
            self.hash.clicked.connect(lambda: ctx.page.copySectionLink(self.anchor))
            layout.addWidget(self.hash, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch(1)
        self._flash = 0.0
        self._animation = None
        ctx.register(block.anchor, self)

    def flash(self):
        """跳到这一节时，标题行底色闪两下后淡出（约 1.2 秒）。"""
        if self._animation is not None:
            self._animation.stop()
        animation = QVariantAnimation(self)
        animation.setDuration(1200)
        animation.setStartValue(1.0)
        animation.setKeyValueAt(0.35, 0.25)
        animation.setKeyValueAt(0.65, 1.0)
        animation.setEndValue(0.0)
        animation.valueChanged.connect(self._setFlash)
        self._animation = animation
        animation.start()

    def _setFlash(self, value):
        self._flash = float(value)
        self.update()

    def paintEvent(self, event):
        if self._flash <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(with_alpha(style.link_color(), 0.16 * self._flash))
        painter.drawRoundedRect(QRectF(self.rect()), 6, 6)

    def enterEvent(self, event):
        if self.hash is not None:
            self.hash.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.hash is not None:
            self.hash.hide()
        super().leaveEvent(event)


class Marker(QWidget):
    """列表的项目符号或序号，基线和正文第一行对齐。"""

    def __init__(self, text, size, width, parent, ordered):
        super().__init__(parent)
        self._text, self._size, self._ordered = text, size, ordered
        self.setFixedSize(width, style.line_height(size))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(style.font(self._size))
        painter.setPen(text_color(secondary=True) if self._ordered else style.muted())
        # 正文按固定行高排版，Qt 把基线放在行高的 4/5 处。
        baseline = self.height() * 0.8
        width = QFontMetricsF(painter.font()).horizontalAdvance(self._text)
        x = self.width() - width - 2 if self._ordered else (self.width() - width) / 2
        painter.drawText(QPointF(x, baseline), self._text)


class ListView(QWidget):
    def __init__(self, block, ctx, parent, size, depth=0, color=None):
        super().__init__(parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(4)
        font = QFontMetricsF(style.font(size))
        last = block.start + max(0, len(block.items) - 1)
        width = round(font.horizontalAdvance(f"{last}.")) + 6 if block.ordered else 16
        for row, item in enumerate(block.items):
            text = f"{block.start + row}." if block.ordered else BULLETS[depth % len(BULLETS)]
            grid.addWidget(Marker(text, size, width, self, block.ordered), row, 0, Qt.AlignmentFlag.AlignTop)
            column = QWidget(self)
            layout = QVBoxLayout(column)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            build_blocks(item, ctx, column, layout, size=size, compact=True, depth=depth + 1, color=color)
            grid.addWidget(column, row, 1)
        grid.setColumnStretch(1, 1)


class TableView(QWidget):
    """圆角卡片表格：表头浅底，行间细线。

    列宽按内容分配：放得下时按比例撑满；放不下时短的列保持一行，只让内容长的列换行，
    避免每列都挤掉一点、出现单个字换行。
    """

    MIN_COLUMN = 56
    MAX_NATURAL = 360

    def __init__(self, block, ctx, parent):
        super().__init__(parent)
        rows = ([(block.header, True)] if block.header else []) + [(row, False) for row in block.rows]
        self._columns = max((len(cells) for cells, _ in rows), default=0)
        self._hasHeader = bool(block.header)
        self._rowTops = []
        self._cache = {}
        self._natural = []
        self.cells = []
        for cells, header in rows:
            line = []
            for c in range(self._columns):
                spans = cells[c] if c < len(cells) else ()
                align = block.align[c] if c < len(block.align) else "default"
                line.append(ctx.connect(RichText(
                    spans, self, size=style.SMALL, ratio=1.6, align=align,
                    weight=QFont.Weight.DemiBold if header else QFont.Weight.Normal,
                    padding=(14, 9, 14, 9) if header else (14, 8, 14, 8), max_width=self.MAX_NATURAL)))
            self.cells.append(line)
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.refresh()

    def refresh(self):
        """单元格重建（换主题）后重新量列宽。"""
        self._natural = [max((min(row[c].naturalWidth(), self.MAX_NATURAL) for row in self.cells), default=0)
                         for c in range(self._columns)]
        self._cache.clear()
        self.updateGeometry()
        self._place()

    def _widths(self, width):
        inner = max(0, width - 2)
        natural = [max(self.MIN_COLUMN, w) for w in self._natural]
        if not natural:
            return []
        total = sum(natural)
        if total <= inner:
            widths = [w + (inner - total) * w / total for w in natural]
        else:
            widths = [0.0] * len(natural)
            pending = list(range(len(natural)))
            remaining = float(inner)
            while pending:
                share = remaining / len(pending)
                fits = [c for c in pending if natural[c] <= share]
                if not fits:
                    break
                for c in fits:
                    widths[c] = natural[c]
                    remaining -= natural[c]
                    pending.remove(c)
            if pending:
                weight = sum(natural[c] for c in pending)
                for c in pending:
                    widths[c] = max(self.MIN_COLUMN, remaining * natural[c] / weight)
        result = [int(w) for w in widths]
        result[-1] = max(1, result[-1] + inner - sum(result))
        return result

    def _rows(self, width):
        cached = self._cache.get(width)
        if cached is None:
            widths = self._widths(width)
            heights = [max((row[c].heightForWidth(widths[c]) for c in range(self._columns)), default=0)
                       for row in self.cells]
            cached = (widths, heights)
            if len(self._cache) > 8:
                self._cache.clear()
            self._cache[width] = cached
        return cached

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return sum(self._rows(width)[1]) + 2

    def sizeHint(self):
        width = min(sum(max(self.MIN_COLUMN, w) for w in self._natural) + 2, style.READING_WIDTH)
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self):
        return QSize(min(self._columns * self.MIN_COLUMN + 2, style.READING_WIDTH), 40)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place()

    def _place(self):
        if not self.cells or self.width() <= 2:
            return
        widths, heights = self._rows(self.width())
        tops, y = [], 1
        for row, height in zip(self.cells, heights):
            tops.append(y)
            x = 1
            for c, cell in enumerate(row):
                cell.setGeometry(x, y, widths[c], height)
                x += widths[c]
            y += height
        tops.append(y)
        self._rowTops = tops
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        painter.fillPath(path, surface_color())
        tops = self._rowTops
        if self._hasHeader and len(tops) > 1:
            painter.save()
            painter.setClipPath(path)
            c = 255 if isDarkTheme() else 0
            painter.fillRect(QRectF(0, 0, self.width(), tops[1]), QColor(c, c, c, 10))
            painter.restore()
        painter.setPen(QPen(border_color(), 1))
        for y in tops[1:-1]:
            painter.drawLine(QPointF(1, y - 0.5), QPointF(self.width() - 1, y - 0.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)


class CalloutView(QWidget):
    def __init__(self, block, ctx, parent):
        super().__init__(parent)
        self.kind = block.kind
        notice = block.kind == "declaration"
        size = 12 if notice else style.SMALL
        icon_size = 14 if notice else 16
        layout = QHBoxLayout(self)
        layout.setContentsMargins(*((12, 8, 14, 8) if notice else (14, 11, 16, 12)))
        layout.setSpacing(10 if notice else 12)
        self.icon = IconWidget(CALLOUT_ICONS.get(block.kind, InfoBarIcon.INFORMATION), self)
        self.icon.setFixedSize(icon_size, icon_size)
        holder = QVBoxLayout()
        first_line = style.line_height(13, 1.6) if block.title else style.line_height(size)
        holder.setContentsMargins(0, max(0, (first_line - icon_size) // 2), 0, 0)
        holder.addWidget(self.icon)
        holder.addStretch(1)
        layout.addLayout(holder)
        column = QVBoxLayout()
        column.setSpacing(0)
        if block.title:
            title = ctx.connect(RichText(block.title, self, size=13, weight=QFont.Weight.DemiBold, ratio=1.6))
            column.addWidget(title)
            column.addSpacing(2)
        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        build_blocks(block.blocks, ctx, body, body_layout, size=size, compact=True,
                     color="secondary" if notice else None)
        column.addWidget(body)
        layout.addLayout(column, 1)

    def paintEvent(self, event):
        background, foreground = style.callout_colors(self.kind)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(with_alpha(foreground, 0.18), 1))
        painter.setBrush(background)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)


def _trim(tokens):
    tokens = list(tokens)
    while tokens and not tokens[-1].text.strip("\r\n"):
        tokens.pop()
    if tokens:
        tokens[-1] = CodeToken(tokens[-1].kind, tokens[-1].text.rstrip("\r\n"))
    return tuple(tokens)


class CopyButton(QPushButton):
    INK = "#c9c4d6"

    def __init__(self, parent, text):
        super().__init__(parent)
        self._text = text
        setFont(self, 12)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIconSize(QSize(12, 12))
        self.setStyleSheet(
            f"QPushButton {{ color: {self.INK}; background: transparent; border: 1px solid rgba(255, 255, 255, 0.16);"
            " border-radius: 4px; padding: 2px 8px; }"
            "QPushButton:hover { background: rgba(255, 255, 255, 0.08); }"
            "QPushButton:pressed { background: rgba(255, 255, 255, 0.14); }")
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(1600)
        self._timer.timeout.connect(self._reset)
        self.clicked.connect(self._copy)
        self._reset()

    def _show(self, text, icon):
        self.setText(text)
        self.setIcon(icon.icon(color=QColor(self.INK)))
        self.adjustSize()
        place = getattr(self.parentWidget(), "placeButton", None)
        if place is not None:
            place()

    def _reset(self):
        self._show(tr("复制"), FluentIcon.COPY)

    def _copy(self):
        QApplication.clipboard().setText(self._text.rstrip("\r\n"))
        self._show(tr("已复制"), FluentIcon.ACCEPT)
        self._timer.start()


class CodeView(QWidget):
    """深色代码块，右上角复制按钮；长行自动换行，不出现横向滚动条。"""

    def __init__(self, block, ctx, parent):
        super().__init__(parent)
        self.block = block
        self.copyButton = CopyButton(self, block.text)
        metrics = QFontMetricsF(style.font(12))
        reserve = round(max(metrics.horizontalAdvance(tr("复制")), metrics.horizontalAdvance(tr("已复制")))) + 60
        self.text = RichText(None, self, size=style.SMALL, ratio=1.7, tokens=_trim(block.tokens),
                             color=lambda: style.code_color("plain"), padding=(16, 12, reserve, 12))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.text)
        for anchor in block.anchors:
            ctx.register(anchor.anchor, self)
        self.copyButton.raise_()

    def placeButton(self):
        button = getattr(self, "copyButton", None)
        if button is not None:
            button.move(self.width() - button.width() - 10, 9)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.placeButton()

    def paintEvent(self, event):
        background, border = style.code_background()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(border, 1))
        painter.setBrush(background)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)


class ImageView(QWidget):
    """随包的本地图片：按阅读宽度缩小，点开用系统看图程序查看原图。"""

    MAX_HEIGHT = 520

    def __init__(self, block, parent):
        super().__init__(parent)
        self.path = block.path
        self.pixmap = QPixmap(str(block.path))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(block.alt or "")
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def _scaled(self, width):
        w, h = max(1, self.pixmap.width()), max(1, self.pixmap.height())
        scale = min(1.0, width / w, self.MAX_HEIGHT / h)
        return QSize(max(1, round(w * scale)), max(1, round(h * scale)))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._scaled(width).height()

    def sizeHint(self):
        size = self._scaled(style.READING_WIDTH)
        return QSize(size.width(), size.height())

    def paintEvent(self, event):
        size = self._scaled(self.width())
        target = QRectF(0, 0, size.width(), size.height())
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        path = QPainterPath()
        path.addRoundedRect(target.adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        painter.setClipPath(path)
        painter.drawPixmap(target.toRect(), self.pixmap)
        painter.setClipping(False)
        painter.setPen(QPen(border_color(), 1))
        painter.drawPath(path)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path)))


class _FoldRow(QWidget):
    clicked = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False

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
        painter.setBrush(QColor(c, c, c, 9))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 7, 7)


class DetailsView(QWidget):
    def __init__(self, block, ctx, parent, size):
        super().__init__(parent)
        self.header = _FoldRow(self)
        self.chevron = Chevron(self.header)
        summary = RichText(block.summary or (Text(tr("详细信息")),), self.header, size=size,
                           weight=QFont.Weight.DemiBold, interactive=False)
        row = QHBoxLayout(self.header)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(8)
        row.addWidget(self.chevron, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(summary, 1)
        self.body = QWidget(self)
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(36, 0, 16, 12)
        body_layout.setSpacing(0)
        build_blocks(block.blocks, ctx, self.body, body_layout, size=size, compact=True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.body)
        self.header.clicked.connect(lambda: self.setExpanded(not self.isExpanded()))
        self.setExpanded(block.opened)

    def isExpanded(self):
        return not self.body.isHidden()

    def setExpanded(self, expanded):
        self.body.setVisible(bool(expanded))
        self.chevron.setUp(bool(expanded))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(border_color(), 1))
        painter.setBrush(surface_color())
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
