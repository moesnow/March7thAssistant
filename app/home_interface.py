# coding:utf-8
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPainterPath, QImage, QAction
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGraphicsDropShadowEffect, QFileDialog

from qfluentwidgets import ScrollArea, FluentIcon, RoundMenu

from .common.style_sheet import StyleSheet
from .components.link_card import LinkCardView
from .card.samplecardview1 import SampleCardView1
from tasks.base.tasks import start_task

from module.config import cfg
from module.localization import tr

from PIL import Image
import numpy as np
import os
import sys


class BannerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.menu = RoundMenu(parent=self)
        self.menu.addAction(QAction(tr("更换背景图片"), self, triggered=lambda: on_change_banner_image()))

        self.default_banner_path = "./assets/app/images/bg37.jpg"
        banner_path = cfg.get_value("banner_path", self.default_banner_path)
        if not os.path.exists(banner_path):
            banner_path = self.default_banner_path
        if os.path.abspath(banner_path) != os.path.abspath(self.default_banner_path):
            self.menu.addAction(QAction(tr("恢复默认图片"), self, triggered=lambda: on_restore_default_banner_image()))
        self.banner_image = Image.open(banner_path)
        min_height = min(self.parent().parent().height() - 271 - 49, (self.parent().parent().width() - 73) * self.banner_image.height // self.banner_image.width)
        self.setFixedHeight(min_height)

        self.vBoxLayout = QVBoxLayout(self)
        if hasattr(cfg, 'ui_language_now') and cfg.ui_language_now not in ['zh_CN', 'zh_TW']:
            self.galleryLabel = QLabel(f'{tr("三月七小助手")} {cfg.version}', self)
        else:
            self.galleryLabel = QLabel(f'{tr("三月七小助手")} {cfg.version}\nMarch7thAssistant', self)
        self.galleryLabel.setStyleSheet("color: white;font-size: 30px; font-weight: 600;")

        # 创建阴影效果
        # 修复 PySide6 阴影不生效的问题参考了 “[PySide6 练习笔记] 添加阴影及动画效果”
        # https://medium.com/@benson890720/pyside6%E7%B7%B4%E7%BF%92%E7%AD%86%E8%A8%98-%E6%B7%BB%E5%8A%A0%E9%99%B0%E5%BD%B1%E5%8F%8A%E5%8B%95%E7%95%AB%E6%95%88%E6%9E%9C-83f1d2f888d
        self.galleryLabel.shadow = QGraphicsDropShadowEffect()
        self.galleryLabel.shadow.setBlurRadius(20)  # 阴影模糊半径
        self.galleryLabel.shadow.setColor(Qt.GlobalColor.black)  # 阴影颜色
        self.galleryLabel.shadow.setOffset(1.2, 1.2)     # 阴影偏移量

        # 将阴影效果应用于小部件
        self.galleryLabel.setGraphicsEffect(self.galleryLabel.shadow)
        # 设置手型光标以提示用户该标签可点击
        self.galleryLabel.setCursor(Qt.CursorShape.PointingHandCursor)

        self.banner = None
        self.path = None
        self.parent_height = 0
        self.parent_width = 0

        self.linkCardView = LinkCardView(self)
        self.linkCardView.setContentsMargins(0, 0, 0, 36)
        self.linkCardView.addCard(
            FluentIcon.GITHUB,
            'GitHub repo',
            # tr('喜欢就给个星星吧\n拜托求求你啦|･ω･)'),
            f"tr('喜欢就给个星星吧')\ntr('拜托求求你啦|･ω･)')",

            "https://github.com/moesnow/March7thAssistant",
        )
        self.linkCardView.setHidden(True)
        # self.vBoxLayout.setContentsMargins(0, 0, 0, 36)
        # self.vBoxLayout.setSpacing(40)

        # 点击标签可以选择新的背景图片
        def _on_gallery_label_clicked(event):
            self.menu.exec(event.globalPos(), ani=True)

        def on_change_banner_image():
            file_path, _ = QFileDialog.getOpenFileName(self, tr("选择图片"), os.getcwd(), "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)")
            if file_path:
                if os.path.abspath(file_path) != os.path.abspath(self.default_banner_path):
                    # 如果没有恢复默认按钮，添加一个
                    has_restore_action = any(action.text() == tr("恢复默认图片") for action in self.menu.actions())
                    if not has_restore_action:
                        self.menu.addAction(QAction(tr("恢复默认图片"), self, triggered=lambda: on_restore_default_banner_image()))
                try:
                    self.banner_image = Image.open(file_path)
                    cfg.set_value("banner_path", file_path)
                except Exception:
                    return
                self.banner = None
                self.path = None
                self.update()

        def on_restore_default_banner_image():
            try:
                self.banner_image = Image.open(self.default_banner_path)
                cfg.set_value("banner_path", self.default_banner_path)
            except Exception:
                return
            self.banner = None
            self.path = None
            # 移除恢复默认按钮
            for action in self.menu.actions():
                if action.text() == tr("恢复默认图片"):
                    self.menu.removeAction(action)
                    break
            self.update()

        self._on_gallery_label_clicked = _on_gallery_label_clicked
        self.galleryLabel.mousePressEvent = self._on_gallery_label_clicked

        self.galleryLabel.setObjectName('galleryLabel')

        self.vBoxLayout.setSpacing(0)
        self.vBoxLayout.setContentsMargins(0, 20, 0, 10)
        self.vBoxLayout.addWidget(self.galleryLabel)
        self.vBoxLayout.addStretch(1)  # 添加弹性空间，将 linkCardView 推到底部
        self.vBoxLayout.addWidget(self.linkCardView, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)

    def paintEvent(self, e):
        super().paintEvent(e)
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform | QPainter.RenderHint.Antialiasing)

        if not self.banner or not self.path or self.parent_height != self.parent().parent().height() or self.parent_width != self.parent().parent().width():
            self.parent_height = self.parent().parent().height()
            self.parent_width = self.parent().parent().width()
            min_height = min(self.parent().parent().height() - 271, self.width() * self.banner_image.height // self.banner_image.width)
            self.setFixedHeight(min_height)
            image_height = self.banner_image.width * self.height() // self.width()
            crop_area = (0, 0, self.banner_image.width, image_height)  # (left, upper, right, lower)
            cropped_img = self.banner_image.crop(crop_area).convert("RGB")
            img_data = np.array(cropped_img)  # Convert PIL Image to numpy array
            height, width, channels = img_data.shape
            bytes_per_line = channels * width
            self.banner = QImage(img_data.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)

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

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setSpacing(25)
        self.vBoxLayout.addWidget(self.banner)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignTop)

    def loadSamples(self):
        basicInputView = SampleCardView1(
            tr("任务 >"), self.view)

        basicInputView.addSampleCard(
            icon="./assets/app/images/March7th.jpg",
            title=tr("完整运行"),
            action=lambda: start_task("main")
        )
        basicInputView.addSampleCard(
            icon="./assets/app/images/JingYuan.jpg",
            title=tr("日常"),
            action={
                tr("每日实训"): lambda: start_task("daily"),
                tr("清体力"): lambda: start_task("power"),
            }
        )
        basicInputView.addSampleCard(
            icon="./assets/app/images/Yanqing.jpg",
            title=tr("货币战争"),
            action={
                tr("运行一次"): lambda: start_task("currencywars"),
                tr("循环运行"): lambda: start_task("currencywarsloop"),
                # "中途接管": lambda: start_task("currencywarstemp"),
            }
        )
        if sys.platform == 'win32':
            basicInputView.addSampleCard(
                icon="./assets/app/images/SilverWolf.jpg",
                title=tr("锄大地"),
                action={
                    tr("快速启动 ⭐"): lambda: start_task("fight"),
                    tr("原版运行"): lambda: start_task("fight_gui"),
                    tr("更新锄大地"): lambda: start_task("fight_update"),
                    tr("重置配置文件"): lambda: os.path.exists(os.path.join(cfg.fight_path, "config.json")) and os.remove(os.path.join(cfg.fight_path, "config.json")),
                    tr("打开程序目录"): lambda: os.startfile(cfg.fight_path),
                    tr("打开项目主页"): lambda: os.startfile("https://github.com/linruowuyin/Fhoe-Rail"),
                }
            )
            basicInputView.addSampleCard(
                icon="./assets/app/images/Herta.jpg",
                title=tr("差分宇宙"),
                action={
                    tr("快速启动 ⭐"): lambda: start_task("universe"),
                    tr("原版运行"): lambda: start_task("universe_gui"),
                    tr("更新模拟宇宙"): lambda: start_task("universe_update"),
                    tr("重置配置文件"): lambda: [os.remove(p) for p in map(lambda f: os.path.join(cfg.universe_path, f), ["info.yml", "info_old.yml"]) if os.path.exists(p)],
                    tr("打开程序目录"): lambda: os.startfile(cfg.universe_path),
                    tr("打开项目主页"): lambda: os.startfile("https://github.com/CHNZYX/Auto_Simulated_Universe"),
                }
            )
        else:
            basicInputView.addSampleCard(
                icon="./assets/app/images/SilverWolf.jpg",
                title=tr("锄大地"),
                action={
                    tr("暂不支持"): lambda: None,
                }
            )
            basicInputView.addSampleCard(
                icon="./assets/app/images/Herta.jpg",
                title=tr("差分宇宙"),
                action={
                    tr("暂不支持"): lambda: None,
                }
            )
        basicInputView.addSampleCard(
            icon="./assets/app/images/Bronya.jpg",
            title=tr("逐光捡金"),
            action={
                tr("混沌回忆"): lambda: start_task("forgottenhall"),
                tr("虚构叙事"): lambda: start_task("purefiction"),
                tr("末日幻影"): lambda: start_task("apocalyptic"),
            }
        )

        self.vBoxLayout.addWidget(basicInputView)
