# coding:utf-8
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPixmap, QPainter, QBrush, QPainterPath
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QGraphicsDropShadowEffect

from qfluentwidgets import ScrollArea, FluentIcon

from .common.style_sheet import StyleSheet
from .components.link_card import LinkCardView
from .card.samplecardview1 import SampleCardView1

from managers.config_manager import config


class BannerWidget(QWidget):
    """ Banner widget """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFixedHeight(350)

        self.vBoxLayout = QVBoxLayout(self)
        self.galleryLabel = QLabel(f'三月七小助手 {config.version}\nMarch7thAssistant', self)
        self.galleryLabel.setStyleSheet("color: white;font-size: 32px; font-weight: 600;")

        # 创建阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)  # 阴影模糊半径
        shadow.setColor(Qt.black)  # 阴影颜色
        shadow.setOffset(1.2, 1.2)     # 阴影偏移量

        # 将阴影效果应用于小部件
        self.galleryLabel.setGraphicsEffect(shadow)

        self.banner = QPixmap('./assets/app/images/bg37.jpg')

        self.linkCardView = LinkCardView(self)

        self.linkCardView.setContentsMargins(0, 0, 0, 36)
        # self.vBoxLayout.setContentsMargins(0, 0, 0, 36)
        # self.vBoxLayout.setSpacing(40)

        self.galleryLabel.setObjectName('galleryLabel')

        # Create a horizontal layout for the linkCardView with bottom alignment and margin
        linkCardLayout = QHBoxLayout()
        linkCardLayout.addWidget(self.linkCardView)
        # linkCardLayout.setContentsMargins(0, 0, 0, 0)  # Add bottom margin of 20 units
        linkCardLayout.setAlignment(Qt.AlignBottom)

        self.vBoxLayout.setSpacing(0)
        self.vBoxLayout.setContentsMargins(0, 20, 0, 0)
        self.vBoxLayout.addWidget(self.galleryLabel)
        # self.vBoxLayout.addWidget(self.linkCardView, 1, Qt.AlignBottom)
        self.vBoxLayout.addLayout(linkCardLayout)
        self.vBoxLayout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.linkCardView.addCard(
            FluentIcon.GITHUB,
            self.tr('GitHub repo'),
            self.tr(
                '喜欢就给个星星吧\n拜托求求你啦|･ω･)'),
            "https://github.com/moesnow/March7thAssistant",
        )

    def paintEvent(self, e):
        super().paintEvent(e)
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.SmoothPixmapTransform | QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)
        w, h = self.width(), 200
        path.addRoundedRect(QRectF(0, 0, w, h), 10, 10)
        path.addRect(QRectF(0, h - 50, 50, 50))
        path.addRect(QRectF(w - 50, 0, 50, 50))
        path.addRect(QRectF(w - 50, h - 50, 50, 50))
        path = path.simplified()

        # Calculate the required height for maintaining image aspect ratio
        image_height = self.width() * self.banner.height() // self.banner.width()

        # draw banner image with aspect ratio preservation
        pixmap = self.banner.scaled(self.width(), image_height, aspectRatioMode=Qt.KeepAspectRatio, transformMode=Qt.SmoothTransformation)
        path.addRect(QRectF(0, h, w, self.height() - h))
        painter.fillPath(path, QBrush(pixmap))


class HomeInterface(ScrollArea):
    """ Home interface """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.banner = BannerWidget(self)
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)

        self.__initWidget()
        self.loadSamples()

    def __initWidget(self):
        self.view.setObjectName('view')
        self.setObjectName('homeInterface')
        StyleSheet.HOME_INTERFACE.apply(self)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.vBoxLayout.setContentsMargins(0, 0, 0, 36)
        self.vBoxLayout.setSpacing(40)
        self.vBoxLayout.addWidget(self.banner)
        self.vBoxLayout.setAlignment(Qt.AlignTop)

    def loadSamples(self):
        """ load samples """

        basicInputView = SampleCardView1(
            self.tr("任务 >"), self.view)

        basicInputView.addSampleCard(
            icon="./assets/app/images/March7th.jpg",
            title="完整运行",
            action="main"
        )
        basicInputView.addSampleCard(
            icon="./assets/app/images/SilverWolf.jpg",
            title="锄大地",
            action="fight"
        )
        basicInputView.addSampleCard(
            icon="./assets/app/images/Herta.jpg",
            title="模拟宇宙",
            action="universe"
        )
        basicInputView.addSampleCard(
            icon="./assets/app/images/Bronya.jpg",
            title="忘却之庭",
            action="forgottenhall"
        )

        self.vBoxLayout.addWidget(basicInputView)
