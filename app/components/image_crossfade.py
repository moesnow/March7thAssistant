"""Cross-fade cached artwork without capturing or fading the surrounding UI."""
from PySide6.QtCore import QEvent, QEasingCurve, Qt, QVariantAnimation
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget


class ImageCrossFade(QWidget):
    DURATION_MS = 600

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._previous = None
        self._clip = None
        self.animation = QVariantAnimation(self)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setDuration(self.DURATION_MS)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.animation.valueChanged.connect(lambda _: self.update())
        self.animation.finished.connect(self.finish)
        parent.installEventFilter(self)
        self.hide()

    def play(self, previous, clip=None):
        self.finish()
        if previous is None or previous.isNull() or not self.parentWidget().isVisible():
            return
        # Keep the old decoded pixels above the new image, below titles/controls.
        self._previous = previous
        self._clip = clip
        self.setGeometry(self.parentWidget().rect())
        self.lower()
        self.show()
        self.animation.start()

    def finish(self):
        self.animation.stop()
        self.hide()
        self._previous = None
        self._clip = None

    def paintEvent(self, event):
        if self._previous is None:
            return
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform | QPainter.RenderHint.Antialiasing)
        if self._clip is not None:
            painter.setClipPath(self._clip)
        painter.setOpacity(1.0 - self.animation.currentValue())
        painter.drawImage(self.rect(), self._previous)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize:
            self.setGeometry(watched.rect())
        elif event.type() == QEvent.Type.Hide:
            self.finish()
        return super().eventFilter(watched, event)
