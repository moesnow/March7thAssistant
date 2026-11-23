"""Mouse-transparent Evey artwork for the Long Night theme."""
import sys

from PySide6.QtCore import QEvent, QRectF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..common.evernight_artwork import evernight_artwork


class EveyDecoration(QWidget):
    def __init__(self, parent, image_name, opacity=1.0):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self._active = False
        self._opacity = opacity
        self._image_name = image_name
        self._sprite = None
        self.hide()

    def setActive(self, active):
        self._active = active
        if active and self._sprite is None:
            self._sprite = evernight_artwork()[self._image_name]
        self.setVisible(active)
        self.update()

    def paintEvent(self, event):
        if not self._active:
            return
        area = self.rect().adjusted(2, 2, -2, -2)
        if area.isEmpty():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setOpacity(self._opacity)
        size = self._sprite.size().scaled(area.size(), Qt.AspectRatioMode.KeepAspectRatio)
        x = area.center().x() - size.width() / 2
        y = area.center().y() - size.height() / 2
        painter.drawPixmap(QRectF(x, y, size.width(), size.height()), self._sprite, QRectF(self._sprite.rect()))


class EveyControlDecoration(EveyDecoration):
    """Paint behind a sibling control, allowing artwork outside its bounds."""

    def __init__(self, control, image_name, outsets, opacity=0.85):
        super().__init__(control.parentWidget(), image_name, opacity)
        self._control = control
        self._outsets = outsets
        control.installEventFilter(self)
        self._position()
        self.lower()  # Keep the original icon, text and hit area in front.

    def _position(self):
        self.setGeometry(self._control.geometry().adjusted(*self._outsets))

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            self._position()
        return super().eventFilter(watched, event)


class EveyTitleDecoration(EveyDecoration):
    def __init__(self, title_bar):
        super().__init__(title_bar, 'evey-decoration-folded.png', opacity=0.65)
        title_bar.installEventFilter(self)
        title_bar.minBtn.installEventFilter(self)
        self._position()
        self.lower()  # Window buttons paint and receive clicks above the artwork.

    def _position(self):
        title_bar = self.parentWidget()
        window = title_bar.window()
        if sys.platform == 'darwin' and window.isSystemButtonVisible():
            # Fluent positions the native controls separately from its hidden Qt buttons.
            left = window.systemTitleBarRect(title_bar.size()).left()
        else:
            left = title_bar.minBtn.x()
        self.setGeometry(left, 0, title_bar.width() - left, title_bar.height())

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            self._position()
        return super().eventFilter(watched, event)
