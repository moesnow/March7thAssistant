"""任务链步骤条：一步一个圆点，放不下时横向滚动并让当前步骤居中。"""
from PySide6.QtCore import QEasingCurve, QEvent, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFontMetrics, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from app.overview.style import animations_enabled, with_alpha
from app.pages import style
from module.localization import tr

MIN_STEP, MAX_STEP = 96, 176
CIRCLE = 24

LOOK = {"success": ("success", "check"), "failed": ("error", "cross"), "skipped": ("neutral", "dash"),
        "interrupted": ("warning", "dash")}


def status_text(status):
    return {"pending": tr("待执行"), "running": tr("进行中"), "success": tr("已完成"), "failed": tr("失败"),
            "skipped": tr("跳过"), "interrupted": tr("中断")}.get(status, "")


class Stepper(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(68)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self._steps = ()
        self._offset = 0.0
        self._manual = False
        self._drag = None
        self._current = None
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(260)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self._setOffset)

    def setSteps(self, steps):
        self._steps = tuple(steps)
        running = next((i for i, step in enumerate(self._steps) if step.status == "running"), None)
        if running is None:
            done = [i for i, step in enumerate(self._steps) if step.status != "pending"]
            running = done[-1] if done else 0
        # 换到下一步时重新跟随；同一步里用户自己滚动过就不再拉回来。
        if running != self._current:
            self._manual = False
        self._current = running
        self.setAccessibleName("；".join(f"{step.name} {status_text(step.status)} {step.note}".strip() for step in self._steps))
        if not self._manual:
            self._follow()
        self.update()

    def count(self):
        return len(self._steps)

    # ---------- 布局 ----------

    def _width(self):
        count = max(1, len(self._steps))
        return max(MIN_STEP, min(MAX_STEP, self.width() / count))

    def _total(self):
        return self._width() * len(self._steps)

    def _limit(self):
        return max(0.0, self._total() - self.width())

    def _left(self):
        """内容比控件窄时居中。"""
        return max(0.0, (self.width() - self._total()) / 2) - self._offset

    def _center(self, index):
        return QPointF(self._left() + self._width() * (index + 0.5), CIRCLE / 2 + 2)

    def _follow(self):
        if not self._steps:
            return
        target = max(0.0, min(self._limit(), self._width() * (self._current + 0.5) - self.width() / 2))
        self.animation.stop()
        if not self.isVisible() or not animations_enabled():
            self._setOffset(target)
        elif abs(target - self._offset) > 1:
            self.animation.setStartValue(float(self._offset))
            self.animation.setEndValue(float(target))
            self.animation.start()

    def _setOffset(self, value):
        self._offset = max(0.0, min(self._limit(), float(value)))
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._manual:
            self._setOffset(self._offset)
        else:
            self._follow()

    # ---------- 交互 ----------

    def _scroll(self, delta):
        if self._limit() > 0:
            self._manual = True
            self.animation.stop()
            self._setOffset(self._offset + delta)
            return True
        return False

    def wheelEvent(self, event):
        delta = event.angleDelta()
        if not self._scroll(-(delta.x() or delta.y())):
            event.ignore()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._limit() > 0:
            self._drag = (event.position().x(), self._offset)

    def mouseMoveEvent(self, event):
        if self._drag is not None:
            self._manual = True
            self.animation.stop()
            self._setOffset(self._drag[1] + self._drag[0] - event.position().x())

    def mouseReleaseEvent(self, event):
        self._drag = None

    def _at(self, position):
        index = int((position.x() - self._left()) // self._width())
        return index if 0 <= index < len(self._steps) else None

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            index = self._at(QPointF(event.pos()))
            if index is not None:
                step = self._steps[index]
                QToolTip.showText(event.globalPos(), " · ".join(filter(None, (step.name, status_text(step.status), step.note))), self)
            return True
        return super().event(event)

    # ---------- 绘制 ----------

    def _paint(self, painter):
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        width = self._width()
        for index, step in enumerate(self._steps):
            center = self._center(index)
            if center.x() < -width or center.x() > self.width() + width:
                continue
            if index + 1 < len(self._steps):
                done = step.status in ("success", "skipped", "failed", "interrupted")
                color = style.status_line("success") if done else style.rule()
                painter.setPen(style.stroke(color, 2))
                painter.drawLine(QPointF(center.x() + CIRCLE / 2 + 6, center.y()),
                                 QPointF(center.x() + width - CIRCLE / 2 - 6, center.y()))
            circle = QRectF(center.x() - CIRCLE / 2, center.y() - CIRCLE / 2, CIRCLE, CIRCLE)
            painter.setPen(Qt.PenStyle.NoPen)
            if step.status == "running":
                background, foreground = style.solid()
                painter.setBrush(with_alpha(background, 0.22))
                painter.drawEllipse(circle.adjusted(-2.5, -2.5, 2.5, 2.5))
                painter.setBrush(background)
                painter.drawEllipse(circle.adjusted(1, 1, -1, -1))
                style.glyph(painter, "dot", circle.adjusted(3, 3, -3, -3), foreground)
            elif step.status in LOOK:
                tone, mark = LOOK[step.status]
                background, foreground = style.status_colors(tone)
                painter.setBrush(background)
                painter.drawEllipse(circle)
                style.glyph(painter, mark, circle.adjusted(6, 6, -6, -6), foreground, 1.6)
            else:
                painter.setBrush(style.inset_fill())
                painter.drawEllipse(circle)
                painter.setPen(style.muted())
                painter.setFont(style.font(12))
                painter.drawText(circle, Qt.AlignmentFlag.AlignCenter, str(index + 1))
            running = step.status == "running"
            text = QRectF(center.x() - width / 2 + 2, CIRCLE + 9, width - 4, 17)
            font = style.strong(13) if running else style.font(13)
            painter.setFont(font)
            painter.setPen(style.primary() if step.status != "pending" else style.muted())
            painter.drawText(text, Qt.AlignmentFlag.AlignCenter,
                             QFontMetrics(font).elidedText(step.name, Qt.TextElideMode.ElideRight, int(text.width())))
            note = step.note or (status_text(step.status) if step.status in ("failed", "interrupted", "skipped") else "")
            if note:
                small = style.font(12)
                painter.setFont(small)
                painter.setPen(style.link() if running else style.status_line("error") if step.status == "failed" else style.faint())
                painter.drawText(text.translated(0, 17), Qt.AlignmentFlag.AlignCenter,
                                 QFontMetrics(small).elidedText(note, Qt.TextElideMode.ElideRight, int(text.width())))

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._limit() <= 0:
            self._paint(painter)
            return
        # 内容超出时两端渐隐，提示可以滚动。
        ratio = self.devicePixelRatioF()
        buffer = QPixmap(self.size() * ratio)
        buffer.setDevicePixelRatio(ratio)
        buffer.fill(Qt.GlobalColor.transparent)
        inner = QPainter(buffer)
        self._paint(inner)
        inner.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        fade = 36 / max(1, self.width())
        gradient = QLinearGradient(0, 0, self.width(), 0)
        opaque, clear = QColor(0, 0, 0, 255), QColor(0, 0, 0, 0)
        gradient.setColorAt(0, clear if self._offset > 1 else opaque)
        gradient.setColorAt(fade, opaque)
        gradient.setColorAt(1 - fade, opaque)
        gradient.setColorAt(1, clear if self._offset < self._limit() - 1 else opaque)
        inner.fillRect(self.rect(), gradient)
        inner.end()
        painter.drawPixmap(0, 0, buffer)
