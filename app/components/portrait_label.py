"""Portraits that blend with the card beneath them in dark mode."""
from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QLabel


class PortraitLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._render_key = None
        self._pattern = QPixmap()

    def setArtwork(self, foreground, texture):
        """Display prepared pixmaps; decoding and blending happen outside painting."""
        self.setPixmap(foreground)
        self._pattern = texture
        self.update()

    def paintEvent(self, event):
        portrait = self.pixmap()
        if self._pattern.isNull() or portrait.isNull():
            return super().paintEvent(event)

        # The original and foreground share the same full image rectangle.
        # The faint original colours leave the Mica/hover colour visible beneath.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setClipRect(self.contentsRect())
        rect = QRectF(self.contentsRect())
        # Downsample once with Qt's area filter. Directly minifying a large PNG
        # in drawPixmap can alias fine linework at 110 px, especially at 150% DPI.
        ratio = self.devicePixelRatioF()
        key = (portrait.cacheKey(), self._pattern.cacheKey(), rect.size(), ratio)
        if key != self._render_key:
            size = QSize(round(rect.width() * ratio), round(rect.height() * ratio))
            self._foreground = portrait.scaled(size, Qt.AspectRatioMode.IgnoreAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation)
            self._texture = self._pattern.scaled(size, Qt.AspectRatioMode.IgnoreAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation)
            self._render_key = key
        painter.setOpacity(.04)
        painter.drawPixmap(rect, self._texture, QRectF(self._texture.rect()))
        painter.setOpacity(1)
        painter.drawPixmap(rect, self._foreground, QRectF(self._foreground.rect()))
