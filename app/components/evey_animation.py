"""A transparent, input-pass-through Evey splash that floats above its owner."""
from math import pi, sin

from PySide6.QtCore import QEvent, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import QWidget

from module.localization import tr
from ..common.evernight import EVEY_ANIMATION


class EveyAnimation(QWidget):
    closed = Signal()
    midpointReached = Signal()
    DURATION_MS = 5200

    def __init__(self, parent):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowDoesNotAcceptFocus | Qt.WindowType.WindowTransparentForInput)
        self.setObjectName('eveyAnimation')
        self.setWindowTitle(tr('忆灵「长夜」'))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.sprite = QPixmap(EVEY_ANIMATION)
        self._progress = 0.0
        self._closing = False
        self.timeline = QVariantAnimation(self)
        self.timeline.setStartValue(0.0)
        self.timeline.setEndValue(1.0)
        self.timeline.setDuration(self.DURATION_MS)
        self.timeline.valueChanged.connect(self._advance)
        self.timeline.finished.connect(self.close)
        # The splash never takes focus: Escape belongs to the owner window.
        self._escape = QShortcut(QKeySequence('Escape'), parent)
        self._escape.activated.connect(self.close)
        self._escape.setEnabled(False)
        self._position_near_parent()
        parent.installEventFilter(self)

    def _position_near_parent(self):
        parent = self.parentWidget()
        screen = parent.screen().availableGeometry()
        width = min(620, screen.width())
        height = min(420, screen.height())
        center = parent.mapToGlobal(parent.rect().center())
        x = max(screen.left(), min(center.x() - width // 2, screen.right() - width + 1))
        y = max(screen.top(), min(center.y() - height // 2, screen.bottom() - height + 1))
        self.setGeometry(x, y, width, height)

    def play(self):
        self._escape.setEnabled(True)
        self.show()
        self.raise_()
        self.timeline.start()

    def _advance(self, value):
        previous = self._progress
        self._progress = float(value)
        if previous < 0.5 <= self._progress:
            self.midpointReached.emit()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        # Clear the previous position on the transparent Windows backing surface.
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        t = self._progress
        fade = max(0.0, min(1.0, t / 0.15, (1.0 - t) / 0.2))
        painter.setOpacity(fade * fade * (3 - 2 * fade))
        # Drift, bob, tilt and breathe without distorting the character's silhouette.
        painter.translate(self.width() * (0.45 + 0.1 * t), self.height() * 0.5 + 14 * sin(4 * pi * t))
        painter.rotate(3.5 * sin(2 * pi * t))
        breathe = 1 + 0.025 * sin(4 * pi * t)
        painter.scale(breathe, breathe)
        size = self.sprite.size().scaled(int(self.width() * 0.82), int(self.height() * 0.80),
                                         Qt.AspectRatioMode.KeepAspectRatio)
        target = QRectF(-size.width() / 2, -size.height() / 2, size.width(), size.height())
        painter.drawPixmap(target, self.sprite, QRectF(self.sprite.rect()))

    def eventFilter(self, watched, event):
        if watched is self.parentWidget():
            if event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
                self._position_near_parent()
            elif event.type() in (QEvent.Type.Hide, QEvent.Type.Close):
                self.close()
            elif event.type() == QEvent.Type.WindowStateChange and watched.isMinimized():
                self.close()
            elif event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self.close()
                return True
        return super().eventFilter(watched, event)

    def closeEvent(self, event):
        if not self._closing:
            self._closing = True
            self.timeline.stop()
            self._escape.setEnabled(False)
            self._escape.deleteLater()
            self.parentWidget().removeEventFilter(self)
            self.closed.emit()
        super().closeEvent(event)
