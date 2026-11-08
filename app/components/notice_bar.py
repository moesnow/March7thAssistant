# coding: utf-8
"""嵌在布局里的提示条，配色与 Fluent InfoBar 一致并随主题切换。"""
from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, FluentIcon, InfoBarIcon, StrongBodyLabel, TransparentToolButton,
                            isDarkTheme, qconfig, themeColor)
from qfluentwidgets.common.icon import drawIcon

# (浅色, 深色)，取自 qfluentwidgets InfoBar 的配色
_BACKGROUND = {
    InfoBarIcon.INFORMATION: ((244, 244, 244), (39, 39, 39)),
    InfoBarIcon.SUCCESS: ((223, 246, 221), (57, 61, 27)),
    InfoBarIcon.WARNING: ((255, 244, 206), (67, 53, 25)),
    InfoBarIcon.ERROR: ((253, 231, 233), (68, 39, 38)),
}
_BORDER = ((229, 229, 229), (29, 29, 29))


class _NoticeIcon(QWidget):
    """InfoBar 图标；accent 时把底圆换成主题色，中间的符号仍按主题取黑白。"""

    def __init__(self, icon, parent=None, accent=False):
        super().__init__(parent)
        self._icon = icon
        self.accent = accent
        self.setFixedSize(16, 16)

    def setIcon(self, icon):
        self._icon = icon
        self.update()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect())
        if self.accent and isinstance(self._icon, InfoBarIcon):
            # InfoBar 的 SVG 第一段路径是底圆，第二段是符号
            self._icon.render(painter, rect, indexes=[0], fill=themeColor().name())
        else:
            drawIcon(self._icon, painter, rect)


class NoticeBar(QFrame):
    """常驻提示：文字按实际宽度换行，不像 InfoBar 那样浮在内容上或自动消失。"""

    closed = Signal()

    def __init__(self, icon=InfoBarIcon.INFORMATION, parent=None, *, closable=False, accent=False):
        super().__init__(parent)
        self._icon = icon
        self.iconWidget = _NoticeIcon(icon, self, accent)
        self.titleLabel = StrongBodyLabel(self)
        self.titleLabel.hide()
        self.contentLabel = BodyLabel(self)
        self.contentLabel.setWordWrap(True)
        self.contentLabel.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.closeButton = TransparentToolButton(FluentIcon.CLOSE, self)
        self.closeButton.setFixedSize(28, 28)
        self.closeButton.setIconSize(QSize(10, 10))
        self.closeButton.setVisible(closable)
        self.closeButton.clicked.connect(self._onCloseClicked)

        # 图标与第一行文字居中对齐
        iconLayout = QVBoxLayout()
        iconLayout.setContentsMargins(0, 2, 0, 0)
        iconLayout.addWidget(self.iconWidget)
        iconLayout.addStretch(1)

        textLayout = QVBoxLayout()
        textLayout.setContentsMargins(0, 0, 0, 0)
        textLayout.setSpacing(2)
        textLayout.addWidget(self.titleLabel)
        textLayout.addWidget(self.contentLabel)

        self.widgetLayout = QHBoxLayout()
        self.widgetLayout.setContentsMargins(0, 0, 0, 0)
        self.widgetLayout.setSpacing(8)

        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.setContentsMargins(16, 12, 12, 12)
        self.hBoxLayout.setSpacing(12)
        self.hBoxLayout.addLayout(iconLayout)
        self.hBoxLayout.addLayout(textLayout, 1)
        self.hBoxLayout.addLayout(self.widgetLayout)
        self.hBoxLayout.addWidget(self.closeButton, 0, Qt.AlignmentFlag.AlignTop)

        qconfig.themeChanged.connect(self._onThemeChanged)

    def setIcon(self, icon):
        self._icon = icon
        self.iconWidget.setIcon(icon)
        self.update()

    def setTitle(self, text: str):
        self.titleLabel.setText(text)
        self.titleLabel.setVisible(bool(text))

    def setContent(self, text: str):
        self.contentLabel.setText(text)
        self.contentLabel.setVisible(bool(text))

    def content(self) -> str:
        return self.contentLabel.text()

    def addWidget(self, widget, stretch=0):
        self.widgetLayout.addWidget(widget, stretch, Qt.AlignmentFlag.AlignVCenter)

    def _onCloseClicked(self):
        self.hide()
        self.closed.emit()

    def _onThemeChanged(self):
        self.update()
        self.iconWidget.update()

    def paintEvent(self, e):
        dark = isDarkTheme()
        background = _BACKGROUND.get(self._icon, _BACKGROUND[InfoBarIcon.INFORMATION])[dark]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(*_BORDER[dark]), 1))
        painter.setBrush(QColor(*background))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)
