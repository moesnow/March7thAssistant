"""帮助正文用的富文本控件。

用 QTextDocument 自己排版和绘制，而不用 QLabel：这样才能在文字行里嵌入圆角的设置按钮和状态图标，
同时保留选择、复制和点链接。按钮和图标按屏幕像素密度画成图片资源，作为行内图片插入
（PySide6 6.11 里 Python 实现的 QTextObjectInterface 注册不上）。颜色写在格式和图片里，
主题变化时调用 restyle() 重新生成文档。
"""
import math

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, QUrl, Signal
from PySide6.QtGui import (QAbstractTextDocumentLayout, QColor, QFont, QFontMetrics, QFontMetricsF, QGuiApplication, QImage,
                           QKeySequence, QPainter, QPalette, QPen, QPolygonF, QTextBlockFormat, QTextCharFormat,
                           QTextCursor, QTextDocument, QTextFormat, QTextImageFormat, QTextOption)
from PySide6.QtWidgets import QApplication, QSizePolicy, QToolTip, QWidget
from qfluentwidgets import Action, FluentIcon, RoundMenu

from app.common.icon import UiIcon
from app.overview.style import text_color, with_alpha
from module.docs.model import Break, Image, Link, SettingPath, Status, Text
from module.localization import tr
from . import style


def _value(member):
    return int(getattr(member, "value", member))


P_TEXT = _value(QTextFormat.Property.UserProperty) + 1
P_VALUE = P_TEXT + 1
IMAGE_RESOURCE = _value(QTextDocument.ResourceType.ImageResource)
STATUS_SIZE = 16
FIXED_HEIGHT = _value(QTextBlockFormat.LineHeightTypes.FixedHeight)
DEMIBOLD = _value(QFont.Weight.DemiBold)
OBJECT_CHAR = "￼"
LINE_SEPARATOR = "\u2028"
CODE_PAD = " "
ALIGN = {"center": Qt.AlignmentFlag.AlignHCenter, "right": Qt.AlignmentFlag.AlignRight}
PILL_HEIGHT = 22
PILL_MARGIN = 3


def _wide(char):
    code = ord(char)
    return (0x2E80 <= code <= 0x9FFF or 0xF900 <= code <= 0xFAFF or 0xFF00 <= code <= 0xFFEF
            or 0x3000 <= code <= 0x303F or 0xAC00 <= code <= 0xD7AF)


def join_soft_breaks(text, before="", after=""):
    """Markdown 的软换行：两边都是中日韩文字时直接相连，否则换成空格，和网页显示一致。"""
    if "\n" not in text:
        return text
    pieces = text.split("\n")
    result = pieces[0]
    for piece in pieces[1:]:
        left = (result or before)[-1:]
        right = (piece or after)[:1]
        joined = not left or not right or (_wide(left) and _wide(right))
        result += ("" if joined else " ") + piece
    return result


def status_name(value):
    return {"yes": tr("是"), "no": tr("否"), "partial": tr("部分")}.get(value, "")


def path_text(labels):
    return " › ".join(tr(label) for label in labels)


class RichText(QWidget):
    """一段正文：可以选择、复制，点链接和设置按钮。spans 来自 module.docs.model。"""

    linkActivated = Signal(object)

    def __init__(self, spans=(), parent=None, *, size=style.BODY, weight=QFont.Weight.Normal, ratio=style.LINE,
                 color=None, align="left", padding=(0, 0, 0, 0), tokens=None, interactive=True, max_width=None):
        super().__init__(parent)
        self._spans = tuple(spans or ())
        self._tokens = tokens
        self._size, self._weight, self._ratio = size, weight, ratio
        self._color = color
        self._align = align
        self._padding = tuple(padding)
        self._maxWidth = max_width or style.READING_WIDTH
        self._links = {}
        self._hover = ""
        self._press = None
        self._pressHref = ""
        self._dragging = False
        self._heights = {}
        self._natural = None
        self._pills = {}
        self._extraBottom = 0
        self._doc = None
        self._cursor = None
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        if interactive:
            self.setMouseTracking(True)
            self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        else:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._build()

    # 内容 ---------------------------------------------------------------

    def setSpans(self, spans):
        self._spans = tuple(spans or ())
        self.restyle()

    def restyle(self):
        self._build()
        self.updateGeometry()
        self.update()

    def textColor(self):
        color = self._color
        if isinstance(color, QColor):
            return color
        if callable(color):
            return color()
        if color == "secondary":
            return text_color(secondary=True)
        if color == "muted":
            return style.muted()
        return text_color()

    def plainText(self):
        cursor = QTextCursor(self._doc)
        cursor.select(QTextCursor.SelectionType.Document)
        return self._text(cursor.selectionStart(), cursor.selectionEnd())

    def _build(self):
        previous = self._doc
        doc = QTextDocument(self)
        doc.setDocumentMargin(0)
        doc.setUndoRedoEnabled(False)
        code = self._tokens is not None
        base_font = style.mono(self._size) if code else style.font(self._size, self._weight)
        doc.setDefaultFont(base_font)
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        option.setAlignment(ALIGN.get(self._align, Qt.AlignmentFlag.AlignLeft))
        if code:
            option.setTabStopDistance(QFontMetricsF(base_font).horizontalAdvance(" ") * 4)
        doc.setDefaultTextOption(option)
        cursor = QTextCursor(doc)
        block = QTextBlockFormat()
        block.setLineHeight(style.line_height(self._size, self._ratio), FIXED_HEIGHT)
        block.setAlignment(ALIGN.get(self._align, Qt.AlignmentFlag.AlignLeft))
        cursor.setBlockFormat(block)
        base = QTextCharFormat()
        base.setForeground(self.textColor())
        self._links = {}
        self._pills = {}
        if code:
            for token in self._tokens:
                fmt = QTextCharFormat(base)
                fmt.setForeground(style.code_color(token.kind))
                cursor.insertText(token.text.replace("\r\n", "\n").replace("\n", LINE_SEPARATOR), fmt)
        else:
            for index, span in enumerate(self._spans):
                self._insert(doc, cursor, base, index)
        self._doc = doc
        self._cursor = QTextCursor(doc)
        # 胶囊比一行文字略高，最后一行的胶囊下边框会超出行框一点，给它留出位置。
        line = style.line_height(self._size, self._ratio)
        overhang = PILL_HEIGHT - self._pillBaseline() - 0.2 * line
        self._extraBottom = max(0, math.ceil(overhang)) if self._pills else 0
        self._heights.clear()
        self._natural = None
        if previous is not None:
            previous.deleteLater()

    def _neighbour(self, index, step):
        other = index + step
        if 0 <= other < len(self._spans) and isinstance(self._spans[other], Text):
            return self._spans[other].text
        return ""

    def _insert(self, doc, cursor, base, index):
        span = self._spans[index]
        if isinstance(span, Text):
            fmt = QTextCharFormat(base)
            if span.bold:
                fmt.setFontWeight(DEMIBOLD)
            if span.italic:
                fmt.setFontItalic(True)
            if span.strike:
                fmt.setFontStrikeOut(True)
            text = join_soft_breaks(span.text, self._neighbour(index, -1), self._neighbour(index, 1))
            if not span.code:
                # 段首、段尾和显式换行两侧的空白在网页上不显示，这里也去掉。
                if index == 0 or isinstance(self._spans[index - 1], Break):
                    text = text.lstrip()
                if index == len(self._spans) - 1 or isinstance(self._spans[index + 1], Break):
                    text = text.rstrip()
            if span.code:
                fmt.setFont(style.mono(self._size - 1),
                            QTextCharFormat.FontPropertiesInheritanceBehavior.FontPropertiesSpecifiedOnly)
                if span.bold:
                    fmt.setFontWeight(DEMIBOLD)
                fmt.setBackground(style.inline_code_background())
                text = CODE_PAD + text + CODE_PAD
            if span.link is not None:
                self._anchor(fmt, span.link)
            cursor.insertText(text, fmt)
        elif isinstance(span, SettingPath):
            text = path_text(span.labels)
            kind = span.target.partition(":")[0]
            width = self.pillWidth(text)
            body_font = style.font(self._size, self._weight)
            height = self._pillImageHeight(body_font)
            fmt = QTextImageFormat()
            fmt.merge(base)
            # Qt 按这个格式的字体摆放居中的行内图片，必须和正文同一字体，基线才算得准。
            fmt.setFont(body_font, QTextCharFormat.FontPropertiesInheritanceBehavior.FontPropertiesSpecifiedOnly)
            key = self._anchor(fmt, span, color=False)
            name = f"m7a-pill:{key}"
            self._pills[key] = (name, text, kind, width, height)
            doc.addResource(IMAGE_RESOURCE, QUrl(name), self._pillImage(text, kind, width, height, False))
            fmt.setName(name)
            fmt.setWidth(width)
            fmt.setHeight(height)
            fmt.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignMiddle)
            fmt.setProperty(P_TEXT, text)
            cursor.insertImage(fmt)
        elif isinstance(span, Status):
            name = f"m7a-status:{span.value}"
            if doc.resource(IMAGE_RESOURCE, QUrl(name)) is None:
                doc.addResource(IMAGE_RESOURCE, QUrl(name), self._statusImage(span.value))
            fmt = QTextImageFormat()
            fmt.merge(base)
            fmt.setName(name)
            fmt.setWidth(STATUS_SIZE)
            fmt.setHeight(STATUS_SIZE)
            fmt.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignMiddle)
            fmt.setToolTip(status_name(span.value))
            fmt.setProperty(P_VALUE, span.value)
            cursor.insertImage(fmt)
        elif isinstance(span, Break):
            cursor.insertText(LINE_SEPARATOR, base)
        elif isinstance(span, Image):
            fmt = QTextCharFormat(base)
            link = span.link
            if link is None and span.path is not None:
                link = Link("file", str(span.path))
            elif link is None and span.url:
                link = Link("external", span.url)
            if link is not None:
                self._anchor(fmt, link)
            cursor.insertText(span.alt or tr("图片"), fmt)

    def _anchor(self, fmt, target, color=True):
        key = str(len(self._links) + 1)
        self._links[key] = target
        fmt.setAnchor(True)
        fmt.setAnchorHref(key)
        if color:
            fmt.setForeground(style.link_color())
        return key

    # 尺寸 ---------------------------------------------------------------

    def _layout(self, width):
        inner = max(1, width - self._padding[0] - self._padding[2])
        if self._doc.textWidth() != inner:
            self._doc.setTextWidth(inner)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self._heights.get(width)
        if height is None:
            self._layout(width)
            height = math.ceil(self._doc.size().height()) + self._padding[1] + self._padding[3] + self._extraBottom
            if len(self._heights) > 16:
                self._heights.clear()
            self._heights[width] = height
        return height

    def naturalWidth(self):
        if self._natural is None:
            current = self._doc.textWidth()
            self._doc.setTextWidth(-1)
            self._natural = math.ceil(self._doc.idealWidth()) + self._padding[0] + self._padding[2] + 1
            self._doc.setTextWidth(current)
        return self._natural

    def sizeHint(self):
        width = max(1, min(self.naturalWidth(), self._maxWidth))
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self):
        return QSize(min(self.naturalWidth(), 48),
                     style.line_height(self._size, self._ratio) + self._padding[1] + self._padding[3] + self._extraBottom)

    def resizeEvent(self, event):
        self._layout(self.width())
        super().resizeEvent(event)

    # 绘制 ---------------------------------------------------------------

    def paintEvent(self, event):
        self._layout(self.width())
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        painter.translate(self._padding[0], self._padding[1])
        context = QAbstractTextDocumentLayout.PaintContext()
        palette = QPalette(self.palette())
        palette.setColor(QPalette.ColorRole.Text, self.textColor())
        context.palette = palette
        if self._cursor.hasSelection():
            selection = QAbstractTextDocumentLayout.Selection()
            selection.cursor = self._cursor
            fmt = QTextCharFormat()
            fmt.setBackground(style.selection_color())
            selection.format = fmt
            context.selections = [selection]
        self._doc.documentLayout().draw(painter, context)

    def _pixelRatio(self):
        screen = QGuiApplication.primaryScreen()
        ratio = max(self.devicePixelRatioF(), screen.devicePixelRatio() if screen is not None else 1.0)
        return max(1.0, ratio)

    def pillWidth(self, text):
        regular, strong = style.font(12), style.font(12, QFont.Weight.DemiBold)
        go = tr("前往") + " ›"
        width = (2 * PILL_MARGIN + 2 + 8 + 12 + 5 + QFontMetricsF(regular).horizontalAdvance(text) + 6
                 + QFontMetricsF(strong).horizontalAdvance(go) + 8)
        cap = self._maxWidth - self._padding[0] - self._padding[2]
        return max(80, math.ceil(min(width, cap)))

    def _canvas(self, width, height):
        ratio = self._pixelRatio()
        image = QImage(math.ceil(width * ratio), math.ceil(height * ratio), QImage.Format.Format_ARGB32_Premultiplied)
        image.setDevicePixelRatio(ratio)
        image.fill(QColor(0, 0, 0, 0))
        return image

    @staticmethod
    def _pillBaseline():
        """胶囊里文字的基线到胶囊顶边的距离：文字在胶囊里上下居中。"""
        metrics = QFontMetricsF(style.font(12))
        return PILL_HEIGHT / 2 + (metrics.ascent() - metrics.descent()) / 2

    def _pillImageHeight(self, font):
        """行内图片的高度。

        Qt 把居中对齐（AlignMiddle）的行内图片放在基线上方 (高度 + x 高度 / 2) / 2 处
        （QTextDocumentLayout::resizeInlineObject）。让这个值正好等于胶囊内文字的基线位置，
        胶囊里的文字就和两边正文落在同一条基线上；胶囊画在图片顶部，下面多出的部分透明。
        """
        half_x = QFontMetrics(font).xHeight() / 2
        return max(float(PILL_HEIGHT), 2 * self._pillBaseline() - half_x)

    def _pillImage(self, text, kind, width, height, hover):
        image = self._canvas(width, height)
        painter = QPainter(image)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        color = style.link_color()
        body = QRectF(PILL_MARGIN + 0.5, 0.5, width - 2 * PILL_MARGIN - 1, PILL_HEIGHT - 1)
        radius = body.height() / 2
        painter.setPen(QPen(with_alpha(color, 0.95 if hover else 0.72), 1))
        painter.setBrush(style.pill_background(hover))
        painter.drawRoundedRect(body, radius, radius)
        icon = UiIcon.CLIPBOARD_TASK if kind == "task" else FluentIcon.COMMAND_PROMPT if kind == "run" else FluentIcon.SETTING
        icon.icon(color=color).paint(painter, QRect(round(body.left() + 8), round(PILL_HEIGHT / 2 - 6), 12, 12))
        regular, strong = style.font(12), style.font(12, QFont.Weight.DemiBold)
        go = tr("前往") + " ›"
        go_width = QFontMetricsF(strong).horizontalAdvance(go)
        left = body.left() + 8 + 12 + 5
        space = max(0.0, body.right() - 8 - go_width - 6 - left)
        shown = QFontMetricsF(regular).elidedText(text, Qt.TextElideMode.ElideMiddle, space)
        baseline = self._pillBaseline()
        painter.setPen(color)
        painter.setFont(regular)
        painter.drawText(QPointF(left, baseline), shown)
        painter.setFont(strong)
        painter.drawText(QPointF(body.right() - 8 - go_width, baseline), go)
        painter.end()
        return image

    def _statusImage(self, value):
        image = self._canvas(STATUS_SIZE, STATUS_SIZE)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        x = y = STATUS_SIZE / 2
        if value == "yes":
            painter.setPen(QPen(style.success(), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                                Qt.PenJoinStyle.RoundJoin))
            painter.drawPolyline(QPolygonF([QPointF(x - 5, y + 0.5), QPointF(x - 1.5, y + 4), QPointF(x + 5.5, y - 4)]))
        elif value == "no":
            painter.setPen(QPen(style.muted(), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(x - 5, y), QPointF(x + 5, y))
        else:
            color = style.warning()
            painter.setPen(QPen(color, 1.4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(x, y), 5.5, 5.5)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawPie(QRectF(x - 5.5, y - 5.5, 11, 11), 90 * 16, 180 * 16)
        painter.end()
        return image

    def _renderPill(self, key, hover):
        pill = self._pills.get(key)
        if pill is not None:
            name, text, kind, width, height = pill
            self._doc.addResource(IMAGE_RESOURCE, QUrl(name), self._pillImage(text, kind, width, height, hover))

    # 交互 ---------------------------------------------------------------

    def _point(self, event):
        return event.position() - QPointF(self._padding[0], self._padding[1])

    def _hrefAt(self, point):
        return self._doc.documentLayout().anchorAt(point)

    def _hit(self, point):
        return max(0, self._doc.documentLayout().hitTest(point, Qt.HitTestAccuracy.FuzzyHit))

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        point = self._point(event)
        self._press = event.position()
        self._pressHref = self._hrefAt(point)
        self._dragging = False
        self._cursor.setPosition(self._hit(point))
        self.update()
        event.accept()

    def mouseMoveEvent(self, event):
        point = self._point(event)
        if self._press is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if not self._dragging and (event.position() - self._press).manhattanLength() > 4:
                self._dragging = True
            if self._dragging:
                self._cursor.setPosition(self._hit(point), QTextCursor.MoveMode.KeepAnchor)
                self.update()
        self._setHover(self._hrefAt(point), event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._press is not None:
            href = self._hrefAt(self._point(event))
            self._press = None
            if not self._dragging and href and href == self._pressHref:
                self._cursor.clearSelection()
                self.update()
                target = self._links.get(href)
                if target is not None:
                    self.linkActivated.emit(target)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._cursor.setPosition(self._hit(self._point(event)))
            self._cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            self.update()
            event.accept()

    def _setHover(self, href, event=None):
        if href == self._hover:
            return
        previous, self._hover = self._hover, href
        self._renderPill(previous, False)
        self._renderPill(href, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor if href else Qt.CursorShape.ArrowCursor)
        target = self._links.get(href)
        tip = ""
        if isinstance(target, SettingPath):
            tip = tr("前往：{path}").format(path=path_text(target.labels))
        elif isinstance(target, Link) and target.kind == "external":
            tip = target.target
        if tip and event is not None:
            QToolTip.showText(event.globalPosition().toPoint(), tip, self)
        else:
            QToolTip.hideText()
        self.update()

    def leaveEvent(self, event):
        self._setHover("")
        super().leaveEvent(event)

    def focusOutEvent(self, event):
        if event.reason() != Qt.FocusReason.PopupFocusReason and self._cursor.hasSelection():
            self._cursor.clearSelection()
            self.update()
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy) and self._cursor.hasSelection():
            self.copySelection()
            return
        if event.matches(QKeySequence.StandardKey.SelectAll):
            self._cursor.select(QTextCursor.SelectionType.Document)
            self.update()
            return
        super().keyPressEvent(event)

    def _text(self, start, end):
        probe = QTextCursor(self._doc)
        out = []
        for position in range(start, end):
            char = self._doc.characterAt(position)
            if char == OBJECT_CHAR:
                probe.setPosition(position + 1)
                fmt = probe.charFormat()
                out.append(fmt.stringProperty(P_TEXT) if fmt.hasProperty(P_TEXT)
                           else status_name(fmt.stringProperty(P_VALUE)))
            elif char in (LINE_SEPARATOR, "\u2029"):
                out.append("\n")
            elif char != CODE_PAD:
                out.append(char)
        return "".join(out)

    def selectedText(self):
        if not self._cursor.hasSelection():
            return ""
        return self._text(self._cursor.selectionStart(), self._cursor.selectionEnd())

    def copySelection(self):
        text = self.selectedText()
        if text:
            QApplication.clipboard().setText(text)

    def contextMenuEvent(self, event):
        menu = RoundMenu(parent=self)
        copy = Action(FluentIcon.COPY, tr("复制"), self)
        copy.setEnabled(self._cursor.hasSelection())
        copy.triggered.connect(self.copySelection)
        menu.addAction(copy)
        point = QPointF(event.pos()) - QPointF(self._padding[0], self._padding[1])
        target = self._links.get(self._hrefAt(point))
        if isinstance(target, Link) and target.kind == "external":
            link = Action(FluentIcon.LINK, tr("复制链接地址"), self)
            link.triggered.connect(lambda: QApplication.clipboard().setText(target.target))
            menu.addAction(link)
        menu.exec(event.globalPos())
