"""设置 › 运行方式 顶部的三选一大卡片。切换逻辑来自 app.content.backend。"""
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QGraphicsOpacityEffect, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, IconWidget, StrongBodyLabel, isDarkTheme, qconfig

from app.content import backend
from app.content.settings_state import config_events
from app.overview.style import accent, text_color, tone, with_alpha
from app.overview.widgets import Pill
from module.localization import tr
from utils.desktop_twin import in_desktop_twin
from .style import solid
from .common import border_color, icon_of, is_evernight, secondary, surface_color

TAGS = {"local": ("仅 Windows", "可后台"), "cloud": ("Windows / macOS / Linux", "无窗口"),
        "adb": ("ADB", "部分任务")}
DETAILS = {"local": "在这台电脑上运行 PC 版游戏，支持全部任务。",
           "cloud": "在浏览器中运行云游戏，可以无窗口运行，也能用 Docker 部署。",
           "adb": "通过 ADB 连接手机或模拟器，支持清体力、每日实训、领奖和历战余响。"}
CONNECTION_KEYS = {"control_backend", "cloud_game_enable", "ui_profile"}


class ChoiceCard(QWidget):
    clicked = Signal(str)

    def __init__(self, option, parent=None):
        super().__init__(parent)
        self.option = option
        self._selected = False
        self._hover = False
        self.setMinimumHeight(116)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.iconWidget = IconWidget(icon_of(option.icon), self)
        self.iconWidget.setFixedSize(18, 18)
        self.titleLabel = StrongBodyLabel(option.name, self)
        self.descriptionLabel = secondary(CaptionLabel(tr(DETAILS[option.value]) if option.value in DETAILS
                                                       else option.description, self))
        self.descriptionLabel.setWordWrap(True)
        self.tags = []
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(self.iconWidget)
        top.addWidget(self.titleLabel)
        top.addStretch(1)
        top.addSpacing(24)
        tags = QHBoxLayout()
        tags.setSpacing(6)
        for text in TAGS.get(option.value, ()):
            pill = Pill(self, height=20)
            pill.setPill(tr(text), "neutral")
            self.tags.append(pill)
            tags.addWidget(pill)
        tags.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        layout.addLayout(top)
        layout.addWidget(self.descriptionLabel)
        layout.addStretch(1)
        layout.addLayout(tags)
        if not option.available:
            effect = QGraphicsOpacityEffect(self)
            effect.setOpacity(0.5)
            self.setGraphicsEffect(effect)
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setToolTip(tr("当前系统不支持这种运行方式"))

    def setSelected(self, selected):
        self._selected = bool(selected)
        self.update()

    def isSelected(self):
        return self._selected

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if (event.button() == Qt.MouseButton.LeftButton and self.option.available
                and self.rect().contains(event.position().toPoint())):
            self.clicked.emit(self.option.value)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        color = accent(is_evernight())
        if self._selected:
            gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            gradient.setColorAt(0, with_alpha(color, 0.16 if isDarkTheme() else 0.09))
            gradient.setColorAt(1, surface_color())
            painter.setBrush(gradient)
            painter.setPen(QPen(color, 2))
        else:
            painter.setBrush(surface_color(self._hover and self.option.available))
            painter.setPen(QPen(border_color(), 1))
        painter.drawRoundedRect(rect, 8, 8)
        center = QPointF(rect.right() - 20, rect.top() + 23)
        if self._selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(center, 9, 9)
            painter.setBrush(solid()[1] if isDarkTheme() else Qt.GlobalColor.white)
            painter.drawEllipse(center, 3.6, 3.6)
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(text_color(secondary=True), 1.2))
            painter.drawEllipse(center, 8.5, 8.5)


class RunModeChooser(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window_ = window
        self.cards = {}
        self.setDisabled(in_desktop_twin())
        row = QHBoxLayout()
        row.setSpacing(10)
        for option in backend.options():
            card = ChoiceCard(option, self)
            card.clicked.connect(self._choose)
            row.addWidget(card, 1)
            self.cards[option.value] = card
        self.errorLabel = CaptionLabel(self)
        self.errorLabel.setWordWrap(True)
        self.errorLabel.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(row)
        layout.addWidget(self.errorLabel)
        config_events().changed.connect(self._configChanged)
        qconfig.themeChanged.connect(self._themeChanged)
        self.refresh()

    def _configChanged(self, keys):
        if keys & CONNECTION_KEYS:
            self.refresh()

    def _themeChanged(self, *_):
        error = tone("error")[1]
        self.errorLabel.setTextColor(error, error)
        self.update()

    def refresh(self):
        connection = backend.current()
        for value, card in self.cards.items():
            card.setSelected(value == connection.control_backend and not connection.error)
        self.errorLabel.setVisible(bool(connection.error))
        if connection.error:
            self._themeChanged()
            self.errorLabel.setText(tr("当前配置无法识别：{error}。请重新选择运行方式。").format(error=connection.error))

    def _choose(self, value):
        try:
            backend.switch_backend(self.window_, value)
        finally:
            self.refresh()
