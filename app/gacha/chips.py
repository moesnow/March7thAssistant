"""卡池分段和星级筛选用的胶囊按钮。"""
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QButtonGroup, QSizePolicy, QWidget
from qfluentwidgets import FlowLayout

from app.overview.style import tone, with_alpha
from module.gacha.pools import POOLS
from module.localization import tr

from . import style


class Chip(QAbstractButton):
    """圆角胶囊。主文字后面可以跟一段小字，例如数量或「已结束」。"""

    HEIGHT = 32
    PADDING = 14
    GAP = 6

    def __init__(self, text="", parent=None, *, soft=False):
        super().__init__(parent)
        self._soft = soft
        self._extra = ""
        self._muted = False
        self._hover = False
        self._font = style.font(14)
        self._small = style.font(12)
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def setLabel(self, text, extra=""):
        self.setText(text)
        self._extra = extra or ""
        self.setAccessibleName(f"{text} {self._extra}".strip())
        self.updateGeometry()
        self.update()

    def setMuted(self, muted):
        self._muted = bool(muted)
        self.update()

    def sizeHint(self):
        width = QFontMetricsF(self._font).horizontalAdvance(self.text()) + self.PADDING * 2
        if self._extra:
            width += self.GAP + QFontMetricsF(self._small).horizontalAdvance(self._extra)
        return QSize(int(width) + 2, self.HEIGHT)

    def minimumSizeHint(self):
        return self.sizeHint()

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = rect.height() / 2
        if self.isChecked() and self._soft:
            # 筛选用的胶囊：选中时浅色底加强调色文字，不和主按钮抢视线。
            background, foreground = tone("accent", style.evernight())
            if self._hover or self.isDown():
                background = with_alpha(foreground, background.alphaF() + 0.06)
            painter.setPen(QPen(with_alpha(foreground, 0.45), 1))
            painter.setBrush(background)
            extra = foreground
        elif self.isChecked():
            background, foreground = style.selected_colors()
            if self.isDown():
                background = background.darker(108)
            elif self._hover:
                background = background.lighter(106)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(background)
            extra = with_alpha(foreground, 0.8)
        else:
            painter.setPen(QPen(style.rule(), 1))
            painter.setBrush(style.chip_surface(self._hover or self.isDown()))
            foreground = style.faint() if self._muted else style.primary()
            extra = style.faint()
        painter.drawRoundedRect(rect, radius, radius)
        if self.hasFocus():
            painter.setPen(QPen(style.primary(), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1.5, 1.5, -1.5, -1.5), radius - 1.5, radius - 1.5)
        main = QFontMetricsF(self._font)
        baseline = (self.height() + main.ascent() - main.descent()) / 2
        painter.setFont(self._font)
        painter.setPen(foreground)
        painter.drawText(QPointF(self.PADDING, baseline), self.text())
        if self._extra:
            painter.setFont(self._small)
            painter.setPen(extra)
            painter.drawText(QPointF(self.PADDING + main.horizontalAdvance(self.text()) + self.GAP, baseline), self._extra)


class PoolBar(QWidget):
    """卡池分段：按卡池表的顺序，空的或已结束的卡池灰显。"""
    poolChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.flow = FlowLayout(self, needAni=False)
        self.flow.setContentsMargins(0, 0, 0, 0)
        self.flow.setHorizontalSpacing(8)
        self.flow.setVerticalSpacing(8)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.chips = {}
        for key in POOLS:
            chip = Chip(parent=self)
            chip.clicked.connect(lambda checked=False, key=key: self.poolChanged.emit(key))
            self.group.addButton(chip)
            self.flow.addWidget(chip)
            self.chips[key] = chip

    def setPools(self, pools, selected):
        for key, chip in self.chips.items():
            stats = pools.get(key)
            total = stats.total if stats is not None else 0
            extra = style.number(total)
            ended = stats is not None and stats.ended
            if ended:
                extra = tr("{count} · 已结束").format(count=extra)
            chip.setLabel(POOLS[key].label, extra)
            chip.setMuted(total == 0 or ended)
            chip.setChecked(key == selected)
        self.flow.invalidate()
        self.updateGeometry()

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.flow.heightForWidth(width)
