# coding:utf-8
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QPainterPath, QImage
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QGraphicsDropShadowEffect

from qfluentwidgets import ScrollArea, FluentIcon

from .common.style_sheet import StyleSheet
from .components.link_card import LinkCardView
from .card.samplecardview1 import SampleCardView1

from managers.config import config

from PIL import Image
import numpy as np


class BannerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFixedHeight(320)

        self.vBoxLayout = QVBoxLayout(self)
        self.galleryLabel = QLabel(f'三月七小助手 {config.version}\nMarch7thAssistant', self)
        self.galleryLabel.setStyleSheet("color: white;font-size: 30px; font-weight: 600;")

        # 创建阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)  # 阴影模糊半径
        shadow.setColor(Qt.black)  # 阴影颜色
        shadow.setOffset(1.2, 1.2)     # 阴影偏移量

        # 将阴影效果应用于小部件
        self.galleryLabel.setGraphicsEffect(shadow)

        self.img = Image.open("./assets/app/images/bg37.jpg")
        self.banner = None
        self.path = None

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
            self.tr('喜欢就给个星星吧\n拜托求求你啦|･ω･)'),
            "https://github.com/moesnow/March7thAssistant",
        )

    def paintEvent(self, e):
        super().paintEvent(e)
        painter = QPainter(self)
        painter.setRenderHints(QPainter.SmoothPixmapTransform | QPainter.Antialiasing)

        if not self.banner or not self.path:
            image_height = self.img.width * self.height() // self.width()
            crop_area = (0, 0, self.img.width, image_height)  # (left, upper, right, lower)
            cropped_img = self.img.crop(crop_area)
            img_data = np.array(cropped_img)  # Convert PIL Image to numpy array
            height, width, channels = img_data.shape
            bytes_per_line = channels * width
            self.banner = QImage(img_data.data, width, height, bytes_per_line, QImage.Format_RGB888)

            path = QPainterPath()
            path.addRoundedRect(0, 0, width + 50, height + 50, 10, 10)  # 10 is the radius for corners
            self.path = path.simplified()

        painter.setClipPath(self.path)
        painter.drawImage(self.rect(), self.banner)


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

        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setSpacing(25)
        self.vBoxLayout.addWidget(self.banner)
        self.vBoxLayout.setAlignment(Qt.AlignTop)

    def loadSamples(self):
        basicInputView = SampleCardView1(
            self.tr("任务 >"), self.view)

        basicInputView.addSampleCard(
            icon="./assets/app/images/March7th.jpg",
            title="完整运行",
            action="main"
        )
        basicInputView.addSampleCard(
            icon="./assets/app/images/JingYuan.jpg",
            title="每日实训",
            action="daily"
        )
        basicInputView.addSampleCard(
            icon="./assets/app/images/Yanqing.jpg",
            title="清体力",
            action="power"
        )
        basicInputView.addSampleCard(
            icon="./assets/app/images/SilverWolf.jpg",
            title="锄大地",
            action={
                "快速启动": "fight",
                "原版运行": "fight_gui",
                "更新锄大地": "fight_update",
                "重置配置文件": "fight_reset"
            }
        )
        basicInputView.addSampleCard(
            icon="./assets/app/images/Herta.jpg",
            title="模拟宇宙",
            action={
                "快速启动": "universe",
                "原版运行": "universe_gui",
                "更新模拟宇宙": "universe_update",
                "重置配置文件": "universe_reset"
            }
        )
        basicInputView.addSampleCard(
            icon="./assets/app/images/Bronya.jpg",
            title="逐光捡金",
            action={
                "混沌回忆": "forgottenhall",
                "虚构叙事": "purefiction"
            }
        )

        self.vBoxLayout.addWidget(basicInputView)
