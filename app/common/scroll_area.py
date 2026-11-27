"""主页面的滚动区域。"""
from PySide6.QtCore import QEasingCurve, QEvent, Qt, QVariantAnimation
from PySide6.QtWidgets import QApplication, QStyle
from qfluentwidgets import ScrollArea, SmoothMode


class PageScrollArea(ScrollArea):
    WHEEL_DURATION_MS = 80

    def __init__(self, parent=None):
        super().__init__(parent)
        # 离散滚轮由本页处理，其余竖向输入交还 Qt。
        self.setSmoothMode(SmoothMode.NO_SMOOTH, Qt.Orientation.Vertical)
        self._wheel_start = self._wheel_target = self._wheel_frame = 0
        self._wheel_animation = QVariantAnimation(self)
        self._wheel_animation.setDuration(self.WHEEL_DURATION_MS)
        self._wheel_animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._wheel_animation.setStartValue(0.0)
        self._wheel_animation.setEndValue(1.0)
        self._wheel_animation.valueChanged.connect(self._advance_wheel)
        self.verticalScrollBar().valueChanged.connect(self._stop_on_external_scroll)
        self.viewport().installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self.viewport():
            if event.type() == QEvent.Type.Wheel:
                if self._scroll_wheel(event):
                    event.accept()
                    return True
                self._wheel_animation.stop()
            elif event.type() == QEvent.Type.Hide:
                self._wheel_animation.stop()
        return super().eventFilter(watched, event)

    def _scroll_wheel(self, event):
        angle = event.angleDelta()
        if (angle.x() or not angle.y() or angle.y() % 120 or not event.pixelDelta().isNull()
                or event.phase() != Qt.ScrollPhase.NoScrollPhase
                or event.modifiers() != Qt.KeyboardModifier.NoModifier
                or not self.style().styleHint(QStyle.StyleHint.SH_Widget_Animate, None, self)):
            return False

        bar = self.verticalScrollBar()
        current = bar.value()
        # 与 Qt 普通滚轮的步长一致，单个事件最多移动一屏。
        distance = angle.y() // 120 * QApplication.wheelScrollLines() * bar.singleStep()
        distance = max(-bar.pageStep(), min(distance, bar.pageStep()))
        if bar.invertedControls():
            distance = -distance

        # 同方向沿用尚未到达的目标，反向从画面当前位置起步。
        remaining = self._wheel_target - current
        running = self._wheel_animation.state() == self._wheel_animation.State.Running
        base = self._wheel_target if running and remaining * distance > 0 else current
        target = max(bar.minimum(), min(base + distance, bar.maximum()))
        if target == current:
            return False
        if running and target == self._wheel_target:
            return True

        self._wheel_animation.stop()
        # 先走约五分之一，让首帧无需等动画计时器。
        travel = target - current
        first_step = max(1, abs(travel) // 5)
        self._wheel_start = current + (first_step if travel > 0 else -first_step)
        self._wheel_target = target
        self._set_wheel_frame(self._wheel_start)
        if self._wheel_start != target:
            self._wheel_animation.start()
        return True

    def _advance_wheel(self, progress):
        self._set_wheel_frame(round(self._wheel_start + (self._wheel_target - self._wheel_start) * progress))

    def _set_wheel_frame(self, position):
        self._wheel_frame = position
        self.verticalScrollBar().setValue(position)

    def _stop_on_external_scroll(self, position):
        if position != self._wheel_frame:
            self._wheel_animation.stop()
