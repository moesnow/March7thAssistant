"""工具箱的卡片和三列分组排版。"""
from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, CardWidget, FluentIcon as FIF, PushButton, SimpleCardWidget,
                            StrongBodyLabel, isDarkTheme, qconfig, setFont)

from app.common.mascot import Mascot, load_mascot
from app.overview.star_track import paint_background, paint_star_track
from app.overview.widgets import IconTile
from app.pages.common import SECONDARY, is_evernight, secondary

RADIUS = 8
CARD_HEIGHT = 152


class ToolCard(SimpleCardWidget):
    """一个工具：图标、名称、说明，底部是操作。clicked 也用来从别处打开这个工具。"""
    wide = False

    def __init__(self, icon, parent=None):
        super().__init__(parent)
        self.setBorderRadius(RADIUS)
        self._icon = icon
        self.tile = IconTile(self, size=40, icon_size=20)
        self.titleLabel = BodyLabel(self)
        self.titleLabel.setWordWrap(True)
        setFont(self.titleLabel, 15, QFont.Weight.DemiBold)
        self.contentLabel = secondary(CaptionLabel(self))
        self.contentLabel.setWordWrap(True)
        self.button = PushButton(self)
        self.button.setMinimumWidth(96)
        self.button.clicked.connect(self.clicked)
        self.head = QHBoxLayout()
        self.head.setSpacing(12)
        self.head.addWidget(self.tile)
        self.head.addWidget(self.titleLabel, 1)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        self.actions.addWidget(self.button)
        self.actions.addStretch(1)
        self.column = QVBoxLayout()
        self.column.setContentsMargins(16, 14, 16, 14)
        self.column.setSpacing(10)
        self.column.addLayout(self.head)
        self.column.addWidget(self.contentLabel)
        self.column.addStretch(1)
        self.column.addLayout(self.actions)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(0)
        self.row.addLayout(self.column, 1)
        qconfig.themeChanged.connect(self.restyle)
        qconfig.themeColorChanged.connect(self.restyle)
        self.restyle()

    def setTexts(self, title, content, button=""):
        self.titleLabel.setText(title)
        self.contentLabel.setText(content)
        self.button.setText(button)

    def restyle(self, *_):
        enabled = self.isEnabled()
        self.tile.setIcon(self._icon, "accent" if enabled else "neutral", evernight=is_evernight())
        faint = (QColor(0, 0, 0, 92), QColor(255, 255, 255, 92))
        self.titleLabel.setTextColor(*((QColor(0, 0, 0), QColor(255, 255, 255)) if enabled else faint))
        self.contentLabel.setTextColor(*(SECONDARY if enabled else faint))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.EnabledChange and hasattr(self, "tile"):
            self.restyle()

    def mouseReleaseEvent(self, event):
        # 基类在卡片任意位置松开鼠标就发 clicked；这里只有按钮能触发工具。
        super(CardWidget, self).mouseReleaseEvent(event)


class ArtPanel(QWidget):
    """卡片右侧的插画：星轨底色从左往右浮现，小人站在底边上。"""

    def __init__(self, pose, parent=None, *, height=120):
        super().__init__(parent)
        self._pose, self._height = pose, height
        self.setMinimumWidth(170)
        self.setMaximumWidth(268)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

    def sizeHint(self):
        return QSize(268, CARD_HEIGHT)

    def paintEvent(self, event):
        ratio = self.devicePixelRatioF()
        rect = QRectF(self.rect())
        center = rect.width() / 2 + max(0.0, (rect.width() - 200) / 4)
        mode = "evernight" if is_evernight() else "dark" if isDarkTheme() else "light"
        layer = QImage(round(rect.width() * ratio), round(rect.height() * ratio),
                       QImage.Format.Format_ARGB32_Premultiplied)
        layer.setDevicePixelRatio(ratio)
        layer.fill(Qt.GlobalColor.transparent)
        path = QPainterPath()  # 右侧两个角跟卡片一样是圆角
        path.moveTo(0, 0)
        path.lineTo(rect.width() - RADIUS, 0)
        path.arcTo(rect.width() - RADIUS * 2, 0, RADIUS * 2, RADIUS * 2, 90, -90)
        path.lineTo(rect.width(), rect.height() - RADIUS)
        path.arcTo(rect.width() - RADIUS * 2, rect.height() - RADIUS * 2, RADIUS * 2, RADIUS * 2, 0, -90)
        path.lineTo(0, rect.height())
        path.closeSubpath()
        painter = QPainter(layer)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipPath(path)
        paint_background(painter, rect, mode)
        paint_star_track(painter, rect, mode, center)
        painter.setClipping(False)
        mask = QLinearGradient(QPointF(0, 0), QPointF(rect.width() * 0.45, 0))
        mask.setColorAt(0.0, QColor(0, 0, 0, 0))
        mask.setColorAt(1.0, QColor(0, 0, 0, 255))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.fillRect(rect, mask)
        painter.end()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if not self.isEnabled():
            painter.setOpacity(0.5)
        painter.drawImage(0, 0, layer)
        pixmap = load_mascot(self._pose, self._height, ratio, evernight=is_evernight())
        width, height = pixmap.width() / ratio, pixmap.height() / ratio
        painter.drawPixmap(QPointF(center - width / 2, rect.height() - height), pixmap)


class ScreenshotCard(ToolCard):
    """游戏截图：捕获窗口或选择图片，右边是举相机的小人。clicked 留给总览的快捷启动。"""
    captureClicked = Signal()
    fileClicked = Signal()
    wide = True

    def __init__(self, icon, parent=None):
        super().__init__(icon, parent)
        self.button.clicked.disconnect(self.clicked)
        self.button.setMinimumWidth(0)  # 让按钮按译文取宽，插画先收窄。
        self.button.setIcon(FIF.CAMERA)
        self.button.clicked.connect(self.captureClicked)
        self.fileButton = PushButton(FIF.PHOTO, "", self)
        self.fileButton.clicked.connect(self.fileClicked)
        self.actions.insertWidget(1, self.fileButton)
        self.row.addWidget(ArtPanel(Mascot.CAMERA, self))

    def setFileOnly(self, file_only):
        self.button.setHidden(file_only)


class ToolGrid(QWidget):
    """按组排成三列。隐藏的工具不占位置；beside 的组放得下时和上一组同一行、靠右。"""
    COLUMNS = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self.groups = []
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(8)
        for column in range(self.COLUMNS):
            self.grid.setColumnStretch(column, 1)

    def addGroup(self, *cards, beside=False):
        label = StrongBodyLabel(self)
        for card in cards:
            card.setParent(self)
        self.groups.append((label, cards, beside))
        return label

    def arrange(self):
        while self.grid.count():
            self.grid.takeAt(0)
        for row in range(self.grid.rowCount()):
            self.grid.setRowMinimumHeight(row, 0)
            self.grid.setRowStretch(row, 0)
        row, used = -3, self.COLUMNS
        for label, cards, beside in self.groups:
            shown = [card for card in cards if not card.isHidden()]
            label.setVisible(bool(shown))
            if not shown:
                continue
            spans = [self.COLUMNS - len(shown) + 1 if card.wide else 1 for card in shown]
            width = sum(spans)
            if beside and used + width <= self.COLUMNS:
                column = self.COLUMNS - width
            else:
                row, column = row + 3, 0
                self.grid.setRowMinimumHeight(row + 1, CARD_HEIGHT)
                if row:
                    self.grid.setRowMinimumHeight(row - 1, 8)
            self.grid.addWidget(label, row, column, 1, width)
            for card, span in zip(shown, spans):
                self.grid.addWidget(card, row + 1, column, 1, span)
                column += span
            used = column
        self.grid.setRowStretch(max(0, row + 2), 1)
