"""总览页的小控件：胶囊、文字链接、进度条、图标底块、可省略的文字和运行阶段条。"""
from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QLabel, QPushButton, QSizePolicy, QWidget
from qfluentwidgets import BodyLabel, TitleLabel, getFont, isDarkTheme, setFont

from .style import accent, bar_success, css, text_color, tone, track_color, with_alpha

PHASES = ("prepare", "launch", "execute", "finish")


class Pill(QWidget):
    """圆角胶囊标签，可带一个状态圆点。"""

    def __init__(self, parent=None, *, dot=False, strong=False, height=22):
        super().__init__(parent)
        self._text = ""
        self._kind = "neutral"
        self._dot = dot
        self._evernight = False
        self._surface = None
        self._font = getFont(12, QFont.Weight.DemiBold if strong else QFont.Weight.Normal)
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def setPill(self, text, kind="neutral", *, evernight=False, surface=None):
        self._text, self._kind, self._evernight, self._surface = text or "", kind, evernight, surface
        self.setFixedWidth(self.sizeHint().width())
        self.update()

    def text(self):
        return self._text

    def _padding(self):
        return 10 if self.height() <= 22 else 12

    def sizeHint(self):
        width = QFontMetrics(self._font).horizontalAdvance(self._text) + self._padding() * 2 + (12 if self._dot else 0)
        return QSize(width, self.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        background, foreground = tone(self._kind, self._evernight)
        if self._surface is not None:
            background = self._surface
        rect = QRectF(self.rect())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        x = self._padding()
        if self._dot:
            painter.setBrush(foreground)
            painter.drawEllipse(QPointF(x + 3, rect.center().y()), 3.2, 3.2)
            x += 12
        painter.setPen(foreground)
        painter.setFont(self._font)
        painter.drawText(QRectF(x, 0, rect.width() - x, rect.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._text)


class RecoveryBadge(QWidget):
    """开拓力恢复：圆环随时间填满，旁边是下一点的倒计时；回满后换成状态文字。"""

    RING = 12

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""
        self._fraction = None
        self._evernight = False
        self._font = getFont(12)
        self.setFixedHeight(22)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def setCountdown(self, seconds, fraction, *, evernight=False):
        self._show(f"+1 · {seconds // 60}:{seconds % 60:02d}", max(0.0, min(1.0, fraction)), evernight)

    def setFull(self, text, *, evernight=False):
        self._show(text, None, evernight)

    def _show(self, text, fraction, evernight):
        self._text, self._fraction, self._evernight = text, fraction, evernight
        self.setFixedWidth(self.sizeHint().width())
        self.update()

    def text(self):
        return self._text

    def sizeHint(self):
        width = QFontMetrics(self._font).horizontalAdvance(self._text) + 20
        return QSize(width if self._fraction is None else width + self.RING + 4, self.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        background, foreground = tone("success" if self._fraction is None else "accent", self._evernight)
        rect = QRectF(self.rect())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        x = 10.0
        if self._fraction is not None:
            ring = QRectF(9, rect.center().y() - self.RING / 2, self.RING, self.RING).adjusted(1, 1, -1, -1)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(with_alpha(foreground, 0.28), 2))
            painter.drawEllipse(ring)
            painter.setPen(QPen(foreground, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawArc(ring, 90 * 16, -round(self._fraction * 360 * 16))
            x += self.RING + 4
        painter.setPen(foreground)
        painter.setFont(self._font)
        painter.drawText(QRectF(x, 0, rect.width() - x, rect.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._text)


class LinkButton(QPushButton):
    """强调色的文字链接。"""

    def __init__(self, text="", parent=None, *, size=13):
        super().__init__(text, parent)
        self._evernight = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        setFont(self, size)
        self.refreshStyle()

    def setEvernight(self, evernight):
        self._evernight = evernight
        self.refreshStyle()

    def refreshStyle(self):
        color = accent(self._evernight)
        self.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; padding: 0px; color: {css(color)}; }}"
            f"QPushButton:hover {{ text-decoration: underline; }}"
            f"QPushButton:pressed {{ color: {css(with_alpha(color, 0.7))}; }}")


class MeterBar(QWidget):
    """细进度条；也可以按段显示，每段一项。"""

    def __init__(self, parent=None, height=6):
        super().__init__(parent)
        self.setFixedHeight(height)
        self._fraction = 0.0
        self._segments = None
        self._blank = False
        self._color = QColor()

    def setBlank(self):
        """不画进度条，只占位，让同一排卡片的内容对齐。"""
        self._blank = True
        self.update()

    def setFraction(self, fraction, color):
        self._blank = False
        self._segments = None
        self._fraction = max(0.0, min(1.0, float(fraction)))
        self._color = QColor(color)
        self.update()

    def setSegments(self, segments, color):
        self._blank = False
        self._segments = tuple(bool(done) for done in segments)
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):
        if self._blank:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        if self._segments is None:
            painter.setBrush(track_color())
            painter.drawRoundedRect(rect, radius, radius)
            if self._fraction > 0:
                painter.setBrush(self._color)
                width = max(rect.height(), rect.width() * self._fraction)
                painter.drawRoundedRect(QRectF(rect.x(), rect.y(), width, rect.height()), radius, radius)
            return
        segments = self._segments or (False,)
        gap = 3.0
        width = (rect.width() - gap * (len(segments) - 1)) / len(segments)
        for index, done in enumerate(segments):
            painter.setBrush(self._color if done else track_color())
            painter.drawRoundedRect(QRectF(rect.x() + index * (width + gap), rect.y(), width, rect.height()),
                                    radius, radius)


class IconTile(QWidget):
    """清单行前面的圆角图标底块。"""

    def __init__(self, parent=None, *, size=28, icon_size=16):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._icon_size = icon_size
        self._icon = None
        self._kind = "neutral"
        self._evernight = False

    def setIcon(self, icon, kind="neutral", *, evernight=False):
        self._icon, self._kind, self._evernight = icon, kind, evernight
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        painter.setPen(Qt.PenStyle.NoPen)
        if self._kind == "accent":
            color = accent(self._evernight)
            painter.setBrush(with_alpha(color, 0.18 if isDarkTheme() else 0.10))
        else:
            color = text_color(secondary=True)
            painter.setBrush(QColor(255, 255, 255, 16) if isDarkTheme() else QColor(0, 0, 0, 10))
        painter.drawRoundedRect(QRectF(self.rect()), 6, 6)
        if self._icon is not None:
            offset = (self.width() - self._icon_size) // 2
            self._icon.icon(color=color).paint(painter, QRect(offset, offset, self._icon_size, self._icon_size))


class _Elided:
    """放不下时在末尾省略，完整文字放进提示。"""

    def _init_elide(self):
        self._full = ""
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    def setFullText(self, text):
        self._full = text or ""
        self.updateGeometry()
        self._elide()

    def fullText(self):
        return self._full

    def sizeHint(self):
        hint = super().sizeHint()
        return QSize(self.fontMetrics().horizontalAdvance(self._full) + 2, hint.height())

    def minimumSizeHint(self):
        return QSize(24, super().minimumSizeHint().height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()

    def _elide(self):
        shown = self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideRight, max(0, self.width()))
        QLabel.setText(self, shown)
        self.setToolTip(self._full if shown != self._full else "")


class ElidedLabel(_Elided, BodyLabel):
    def __init__(self, parent=None, *, size=13):
        super().__init__(parent)
        setFont(self, size)
        self._init_elide()


class ElidedTitleLabel(_Elided, TitleLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_elide()


class PhaseProgress(QWidget):
    """运行中的四段进度：准备、启动游戏、执行任务、收尾。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self._labels = ("", "", "", "")
        self._current = -1
        self._evernight = False
        self._font = getFont(12)
        self._strong = getFont(12, QFont.Weight.DemiBold)

    def setPhase(self, phase, labels, *, evernight=False):
        self._current = PHASES.index(phase) if phase in PHASES else -1
        self._labels = tuple(labels)
        self._evernight = evernight
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gap = 8.0
        width = (self.width() - gap * 3) / 4
        for index in range(4):
            x = index * (width + gap)
            current = index == self._current
            if index < self._current:
                color = bar_success()
            elif current:
                color = accent(self._evernight)
            else:
                color = track_color()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(x, 0, width, 4), 2, 2)
            painter.setFont(self._strong if current else self._font)
            painter.setPen(accent(self._evernight) if current else text_color(secondary=True))
            label = self._labels[index] if index < len(self._labels) else ""
            painter.drawText(QRectF(x, 8, width, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
