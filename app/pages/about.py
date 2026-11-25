"""「关于」页顶部：图标、版本、常用入口和小人。"""
import platform
import sys

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, FluentIcon as FIF, PrimaryPushButton, PushButton, TitleLabel, isDarkTheme, qconfig

from app.common.mascot import Mascot
from app.common.theme_assets import application_icon_path
from app.overview.greeting import MascotWidget
from app.overview.star_track import COLORS, paint_background, paint_star_track, rgba
from app.overview.widgets import LinkButton, Pill
from app.pages.common import is_evernight, secondary, style_primary
from module.localization import tr

LOGO = 60


class AboutHeader(QWidget):
    updateClicked = Signal()
    homeClicked = Signal()
    changelogClicked = Signal()

    def __init__(self, version, parent=None):
        super().__init__(parent)
        self.setFixedHeight(196)
        self._version = version
        self.logo = QLabel(self)
        self.titleLabel = TitleLabel(tr("三月七小助手"), self)
        self.versionPill = Pill(self, height=24, strong=True)
        self.textLabel = BodyLabel(tr("崩坏：星穹铁道自动化助手，免费开源"), self)
        self.textLabel.setWordWrap(True)
        self.environmentLabel = secondary(CaptionLabel(
            f"Python {sys.version.split()[0]} · {platform.system()} {platform.machine()}", self))
        self.updateButton = PrimaryPushButton(FIF.UPDATE, tr("检查更新"), self)
        self.homeButton = PushButton(FIF.GITHUB, tr("项目主页"), self)
        self.changelogButton = LinkButton(tr("更新日志") + " ›", self, size=14)
        self.updateButton.clicked.connect(self.updateClicked)
        self.homeButton.clicked.connect(self.homeClicked)
        self.changelogButton.clicked.connect(self.changelogClicked)
        title = QHBoxLayout()
        title.setSpacing(10)
        title.addWidget(self.titleLabel)
        title.addWidget(self.versionPill, 0, Qt.AlignmentFlag.AlignVCenter)
        title.addStretch(1)
        text = QVBoxLayout()
        text.setSpacing(1)
        text.addLayout(title)
        text.addWidget(self.textLabel)
        head = QHBoxLayout()
        head.setSpacing(16)
        head.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignVCenter)
        head.addLayout(text, 1)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.updateButton)
        actions.addWidget(self.homeButton)
        actions.addSpacing(4)
        actions.addWidget(self.changelogButton)
        actions.addStretch(1)
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(28, 22, 28, 22)
        self.vBoxLayout.setSpacing(0)
        self.vBoxLayout.addLayout(head)
        self.vBoxLayout.addSpacing(8)
        self.vBoxLayout.addWidget(self.environmentLabel)
        self.vBoxLayout.addStretch(1)
        self.vBoxLayout.addLayout(actions)
        self.mascot = MascotWidget(self)
        qconfig.themeChanged.connect(self.restyle)
        qconfig.themeColorChanged.connect(self.restyle)
        self.restyle()

    def restyle(self, *_):
        evernight = is_evernight()
        self.logo.setPixmap(QIcon(application_icon_path(evernight)).pixmap(QSize(LOGO, LOGO), self.devicePixelRatioF()))
        surface = QColor(0, 0, 0, 72) if isDarkTheme() or evernight else QColor(255, 255, 255, 235)
        self.versionPill.setPill(self._version, "accent", evernight=evernight, surface=surface)
        style_primary(self.updateButton, evernight)
        self.changelogButton.setEvernight(evernight)
        self.mascot.setPose(Mascot.FULL, evernight=evernight)
        self._place()
        self.update()

    def _place(self):
        image = self.mascot.imageRect()
        self.mascot.move(self.width() - 40 - image.width() - image.x(), self.height() - self.mascot.height())
        self.vBoxLayout.setContentsMargins(28, 22, image.width() + 64, 22)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect())
        mode = "evernight" if is_evernight() else "dark" if isDarkTheme() else "light"
        path = QPainterPath()
        path.addRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)
        painter.save()
        painter.setClipPath(path)
        paint_background(painter, rect, mode)
        paint_star_track(painter, rect, mode, self.mascot.x() + self.mascot.width() / 2,
                         fade_from=min(rect.width() * 0.5, 520))
        painter.restore()
        painter.setPen(QPen(rgba(COLORS[mode]["border"]), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
