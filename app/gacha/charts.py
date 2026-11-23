"""自绘的数字行、保底条、五星出货分布图和五星记录。"""
import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QFontMetricsF, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from module.localization import tr

from . import style


def _top_rounded(rect, radius):
    """只有顶端两角是圆角的柱子，底边贴着基线。"""
    radius = min(radius, rect.width() / 2, rect.height())
    path = QPainterPath()
    path.moveTo(rect.left(), rect.bottom())
    path.lineTo(rect.left(), rect.top() + radius)
    path.quadTo(rect.left(), rect.top(), rect.left() + radius, rect.top())
    path.lineTo(rect.right() - radius, rect.top())
    path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + radius)
    path.lineTo(rect.right(), rect.bottom())
    path.closeSubpath()
    return path


class ValueText(QWidget):
    """大号数值后接小号单位，两段文字共用一条基线。"""

    def __init__(self, size=26, parent=None, *, unit_size=13):
        super().__init__(parent)
        self._value_font = style.strong(size)
        self._unit_font = style.font(unit_size)
        self._value = ""
        self._unit = ""
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def setParts(self, value, unit=""):
        self._value, self._unit = value or "", unit or ""
        self.setAccessibleName(f"{self._value} {self._unit}".strip())
        self.updateGeometry()
        self.update()

    def parts(self):
        return self._value, self._unit

    def sizeHint(self):
        value = QFontMetricsF(self._value_font)
        width = value.horizontalAdvance(self._value)
        if self._unit:
            width += 6 + QFontMetricsF(self._unit_font).horizontalAdvance(self._unit)
        return QSize(math.ceil(width) + 1, math.ceil(value.ascent() + value.descent()))

    def minimumSizeHint(self):
        return QSize(0, self.sizeHint().height())

    def paintEvent(self, event):
        value = QFontMetricsF(self._value_font)
        unit = QFontMetricsF(self._unit_font)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        baseline = value.ascent()
        painter.setFont(self._value_font)
        painter.setPen(style.primary())
        painter.drawText(QPointF(0, baseline), self._value)
        if self._unit:
            x = value.horizontalAdvance(self._value) + 6
            painter.setFont(self._unit_font)
            painter.setPen(style.muted())
            painter.drawText(QPointF(x, baseline),
                             unit.elidedText(self._unit, Qt.TextElideMode.ElideRight, max(0.0, self.width() - x)))


class PityBar(QWidget):
    """当前保底的进度：已垫抽数、概率提升起点和保底点。"""
    BAR = 8
    TOP = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._limit = 90
        self._soft = None
        self._font = style.font(12)
        self.setFixedHeight(38)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def setData(self, value, limit, soft):
        self._value, self._limit, self._soft = max(0, value), max(1, limit), soft
        if soft:
            tip = tr("第 {soft} 抽起五星概率提升，第 {limit} 抽必定获得五星").format(soft=soft, limit=limit)
        else:
            tip = tr("{limit} 抽内必定获得一个五星").format(limit=limit)
        self.setToolTip(tip)
        self.update()

    def soft_x(self):
        return round(self.width() * self._soft / self._limit) + 0.5 if self._soft else None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = self.width()
        radius = self.BAR / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(style.series_track())
        painter.drawRoundedRect(QRectF(0, self.TOP, width, self.BAR), radius, radius)
        fraction = min(1.0, self._value / self._limit)
        if fraction > 0:
            painter.setBrush(style.series())
            painter.drawRoundedRect(QRectF(0, self.TOP, max(self.BAR, width * fraction), self.BAR), radius, radius)
        metrics = QFontMetricsF(self._font)
        baseline = self.TOP + self.BAR + 8 + metrics.ascent()
        painter.setFont(self._font)
        limit = str(self._limit)
        limit_width = metrics.horizontalAdvance(limit)
        painter.setPen(style.muted())
        painter.drawText(QPointF(width - limit_width, baseline), limit)
        x = self.soft_x()
        if x is not None:
            painter.setPen(QPen(style.marker(), 1.2))
            painter.drawLine(QPointF(x, self.TOP - 4), QPointF(x, self.TOP + self.BAR + 4))
            label = tr("{pulls} 概率提升").format(pulls=self._soft)
            label_width = metrics.horizontalAdvance(label)
            left = min(max(0.0, x - label_width / 2), width - limit_width - 10 - label_width)
            painter.setPen(style.muted())
            painter.drawText(QPointF(left, baseline), label)


class DistributionChart(QWidget):
    """五星出货分布：每 10 抽一段的柱状图，单一颜色，悬停显示数值。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buckets = ()
        self._hover = -1
        self._font = style.font(12)
        self._strong = style.strong(12)
        self.setMouseTracking(True)
        self.setMinimumHeight(168)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def setBuckets(self, buckets):
        self._buckets = tuple(buckets)
        self._hover = -1
        self.setAccessibleDescription("; ".join(
            tr("{first}～{last} 抽：{count} 个五星").format(first=b.first, last=b.last, count=b.count)
            for b in self._buckets if b.count))
        self.update()

    def sizeHint(self):
        return QSize(360, 180)

    def _scale(self):
        top = max((bucket.count for bucket in self._buckets), default=0)
        for step in (1, 2, 5, 10, 20, 50, 100):
            if top <= step * 4:
                break
        else:
            step = math.ceil(top / 400) * 100
        return top, step, max(step, math.ceil(top / step) * step)

    def _plot(self):
        metrics = QFontMetricsF(self._font)
        top, step, ceiling = self._scale()
        left = metrics.horizontalAdvance(str(ceiling)) + 10
        return QRectF(left, metrics.height() + 6, max(1.0, self.width() - left),
                      max(1.0, self.height() - metrics.height() * 2 - 14))

    def _slot(self, plot):
        return plot.width() / max(1, len(self._buckets))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        metrics = QFontMetricsF(self._font)
        top, step, ceiling = self._scale()
        plot = self._plot()
        painter.setFont(self._font)
        for value in range(0, ceiling + 1, step):
            y = round(plot.bottom() - plot.height() * value / ceiling) + 0.5
            painter.setPen(QPen(style.rule() if value == 0 else style.grid(), 1))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(style.faint())
            text = str(value)
            painter.drawText(QPointF(plot.left() - 10 - metrics.horizontalAdvance(text),
                                     y + (metrics.ascent() - metrics.descent()) / 2), text)
        if not self._buckets:
            return
        slot = self._slot(plot)
        width = min(28.0, slot * 0.56)
        for index, bucket in enumerate(self._buckets):
            center = plot.left() + slot * (index + 0.5)
            if index == self._hover:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(style.hover_fill())
                painter.drawRoundedRect(QRectF(plot.left() + slot * index + 2, plot.top(), slot - 4, plot.height()), 4, 4)
            if bucket.count:
                height = plot.height() * bucket.count / ceiling
                painter.fillPath(_top_rounded(QRectF(center - width / 2, plot.bottom() - height, width, height), 4),
                                 style.series())
                if bucket.count == top or index == self._hover:
                    painter.setFont(self._strong)
                    painter.setPen(style.primary())
                    label = str(bucket.count)
                    painter.drawText(QPointF(center - QFontMetricsF(self._strong).horizontalAdvance(label) / 2,
                                             plot.bottom() - height - 5), label)
                    painter.setFont(self._font)
            painter.setPen(style.muted())
            label = str(bucket.last)
            painter.drawText(QPointF(center - metrics.horizontalAdvance(label) / 2, plot.bottom() + 8 + metrics.ascent()), label)
        if not top:
            painter.setPen(style.muted())
            painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, tr("还没有五星"))

    def _index_at(self, position):
        plot = self._plot()
        if not self._buckets or not plot.adjusted(0, -20, 0, 24).contains(position):
            return -1
        return min(len(self._buckets) - 1, max(0, int((position.x() - plot.left()) // self._slot(plot))))

    def mouseMoveEvent(self, event):
        index = self._index_at(event.position())
        if index != self._hover:
            self._hover = index
            self.update()
        if index < 0:
            QToolTip.hideText()
            return
        bucket = self._buckets[index]
        QToolTip.showText(event.globalPosition().toPoint(),
                          tr("{first}～{last} 抽：{count} 个五星").format(first=bucket.first, last=bucket.last,
                                                                        count=bucket.count), self)

    def leaveEvent(self, event):
        self._hover = -1
        QToolTip.hideText()
        self.update()
        super().leaveEvent(event)


class FiveList(QWidget):
    """五星记录：每个五星一行，条长表示用了多少抽，竖线标出概率提升起点。只画放得下的行。"""
    capacityChanged = Signal()
    HEADER = 30
    ROW = 37
    BAR = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = ()
        self._limit = 90
        self._soft = None
        self._now = None
        self._hover = -1
        self._capacity = -1
        self._name = style.font(14)
        self._number = style.strong(14)
        self._date = style.font(13)
        self._head = style.font(12)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def setRows(self, rows, limit, soft, now=None):
        self._rows, self._limit, self._soft, self._now = tuple(rows), max(1, limit), soft, now
        self._hover = -1
        self.update()

    def capacity(self):
        return max(0, int((self.height() - self.HEADER) // self.ROW))

    def shown(self):
        return min(len(self._rows), self.capacity())

    def sizeHint(self):
        return QSize(360, self.HEADER + self.ROW * 3)

    def minimumSizeHint(self):
        return QSize(240, self.HEADER + self.ROW * 3)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        capacity = self.capacity()
        if capacity != self._capacity:
            self._capacity = capacity
            self.capacityChanged.emit()

    def _columns(self):
        name = QFontMetricsF(self._name)
        date = QFontMetricsF(self._date)
        head = QFontMetricsF(self._head)
        rows = self._rows[:max(1, self.shown())]
        name_width = max([name.horizontalAdvance(row.name) for row in rows] + [head.horizontalAdvance(tr("名称"))])
        name_width = min(160.0, max(72.0, name_width + 18))
        date_width = max([date.horizontalAdvance(style.short_date(row.time, self._now)) for row in rows]
                         + [head.horizontalAdvance(tr("日期"))])
        number_width = max(QFontMetricsF(self._number).horizontalAdvance("000"), head.horizontalAdvance(tr("抽数")))
        right = self.width()
        date_left = right - date_width
        number_right = date_left - 20
        number_left = number_right - number_width
        bar_left = name_width
        bar_width = max(10.0, number_left - 20 - bar_left)
        return name_width, bar_left, bar_width, number_right, right

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        name_width, bar_left, bar_width, number_right, right = self._columns()
        if not self._rows:
            painter.setPen(style.muted())
            painter.setFont(self._date)
            painter.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, tr("还没有五星"))
            return
        head = QFontMetricsF(self._head)
        baseline = (self.HEADER + head.ascent() - head.descent()) / 2 - 2
        painter.setFont(self._head)
        painter.setPen(style.muted())
        painter.drawText(QPointF(0, baseline), tr("名称"))
        caption = (tr("用了多少抽（竖线为 {pulls} 抽）").format(pulls=self._soft) if self._soft else tr("用了多少抽"))
        painter.drawText(QPointF(bar_left, baseline), head.elidedText(caption, Qt.TextElideMode.ElideRight, bar_width))
        text = tr("抽数")
        painter.drawText(QPointF(number_right - head.horizontalAdvance(text), baseline), text)
        text = tr("日期")
        painter.drawText(QPointF(right - head.horizontalAdvance(text), baseline), text)
        painter.setPen(QPen(style.rule(), 1))
        painter.drawLine(QPointF(0, self.HEADER - 0.5), QPointF(right, self.HEADER - 0.5))
        shown = self.shown()
        name = QFontMetricsF(self._name)
        number = QFontMetricsF(self._number)
        date = QFontMetricsF(self._date)
        for index, row in enumerate(self._rows[:shown]):
            top = self.HEADER + index * self.ROW
            if index == self._hover:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(style.hover_fill())
                painter.drawRoundedRect(QRectF(-6, top + 2, right + 12, self.ROW - 4), 4, 4)
            middle = top + self.ROW / 2
            painter.setFont(self._name)
            painter.setPen(style.primary())
            painter.drawText(QPointF(0, middle + (name.ascent() - name.descent()) / 2),
                             name.elidedText(row.name, Qt.TextElideMode.ElideRight, name_width - 12))
            length = max(self.BAR, bar_width * min(1.0, row.pity / self._limit))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(style.series())
            painter.drawRoundedRect(QRectF(bar_left, middle - self.BAR / 2, length, self.BAR), self.BAR / 2, self.BAR / 2)
            painter.setFont(self._number)
            painter.setPen(style.primary())
            text = str(row.pity)
            painter.drawText(QPointF(number_right - number.horizontalAdvance(text),
                                     middle + (number.ascent() - number.descent()) / 2), text)
            painter.setFont(self._date)
            painter.setPen(style.muted())
            text = style.short_date(row.time, self._now)
            painter.drawText(QPointF(right - date.horizontalAdvance(text), middle + (date.ascent() - date.descent()) / 2), text)
            if index < shown - 1:
                painter.setPen(QPen(style.rule(), 1))
                painter.drawLine(QPointF(0, top + self.ROW - 0.5), QPointF(right, top + self.ROW - 0.5))
        if self._soft and shown:
            x = round(bar_left + bar_width * self._soft / self._limit) + 0.5
            painter.setPen(QPen(style.marker(), 1))
            painter.drawLine(QPointF(x, self.HEADER + 4), QPointF(x, self.HEADER + shown * self.ROW - 4))

    def _row_at(self, position):
        if position.y() < self.HEADER:
            return -1
        index = int((position.y() - self.HEADER) // self.ROW)
        return index if 0 <= index < self.shown() else -1

    def mouseMoveEvent(self, event):
        index = self._row_at(event.position())
        if index != self._hover:
            self._hover = index
            self.update()
        if index < 0:
            QToolTip.hideText()
            return
        row = self._rows[index]
        QToolTip.showText(event.globalPosition().toPoint(),
                          tr("{name}：用了 {pulls} 抽，{time}").format(name=row.name, pulls=row.pity, time=row.time), self)

    def leaveEvent(self, event):
        self._hover = -1
        QToolTip.hideText()
        self.update()
        super().leaveEvent(event)
