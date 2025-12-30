# coding:utf-8
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QPainterPath, QImage
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QGraphicsDropShadowEffect

from qfluentwidgets import ScrollArea, FluentIcon

from .common.style_sheet import StyleSheet
from .components.link_card import LinkCardView
from .card.samplecardview1 import SampleCardView1
from tasks.base.tasks import start_task

from module.config import cfg

from PIL import Image
import numpy as np
import os


class BannerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFixedHeight(320)

        self.vBoxLayout = QVBoxLayout(self)
        self.galleryLabel = QLabel(f'March 7th Assistant {cfg.version}\n붕괴: 스타레일 자동화 도구', self)
        self.galleryLabel.setStyleSheet("color: white;font-size: 30px; font-weight: 600;")

        # 그림자 효과 생성
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)  # 그림자 흐림 반경
        shadow.setColor(Qt.black)  # 그림자 색상
        shadow.setOffset(1.2, 1.2)     # 그림자 오프셋

        # 위젯에 그림자 효과 적용
        self.galleryLabel.setGraphicsEffect(shadow)

        self.img = Image.open("./assets/app/images/bg37.jpg")
        self.banner = None
        self.path = None

        self.linkCardView = LinkCardView(self)

        self.linkCardView.setContentsMargins(0, 0, 0, 36)
        # self.vBoxLayout.setContentsMargins(0, 0, 0, 36)
        # self.vBoxLayout.setSpacing(40)

        self.galleryLabel.setObjectName('galleryLabel')

        # LinkCardView를 위한 수평 레이아웃 생성 (하단 정렬 및 여백 포함)
        linkCardLayout = QHBoxLayout()
        linkCardLayout.addWidget(self.linkCardView)
        # linkCardLayout.setContentsMargins(0, 0, 0, 0)  # 20 단위 하단 여백 추가
        linkCardLayout.setAlignment(Qt.AlignBottom)

        self.vBoxLayout.setSpacing(0)
        self.vBoxLayout.setContentsMargins(0, 20, 0, 0)
        self.vBoxLayout.addWidget(self.galleryLabel)
        # self.vBoxLayout.addWidget(self.linkCardView, 1, Qt.AlignBottom)
        self.vBoxLayout.addLayout(linkCardLayout)
        self.vBoxLayout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.linkCardView.addCard(
            FluentIcon.GITHUB,
            'GitHub 저장소',
            '마음에 드신다면 Star를 눌러주세요\n부탁드립니다 제발요 |･ω･)',
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
            img_data = np.array(cropped_img)  # PIL 이미지를 numpy 배열로 변환
            height, width, channels = img_data.shape
            bytes_per_line = channels * width
            self.banner = QImage(img_data.data, width, height, bytes_per_line, QImage.Format_RGB888)

            path = QPainterPath()
            path.addRoundedRect(0, 0, width + 50, height + 50, 10, 10)  # 10은 모서리 반경
            self.path = path.simplified()

        painter.setClipPath(self.path)
        painter.drawImage(self.rect(), self.banner)


class HomeInterface(ScrollArea):
    """ 홈 인터페이스 """

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
            "작업 >", self.view)

        basicInputView.addSampleCard(
            icon="./assets/app/images/March7th.jpg",
            title="전체 실행",
            action=lambda: start_task("main")
        )
        basicInputView.addSampleCard(
            icon="./assets/app/images/JingYuan.jpg",
            title="일일",
            action={
                "일일 훈련": lambda: start_task("daily"),
                "개척력 소모": lambda: start_task("power"),
            }
        )
        basicInputView.addSampleCard(
            icon="./assets/app/images/Yanqing.jpg",
            title="화폐 전쟁",
            action={
                "1회 실행": lambda: start_task("currencywars"),
                "반복 실행": lambda: start_task("currencywarsloop"),
                # "중도 실행": lambda: start_task("currencywarstemp"),
            }
        )
        basicInputView.addSampleCard(
            icon="./assets/app/images/SilverWolf.jpg",
            title="필드 토벌",
            action={
                "빠른 실행 ⭐": lambda: start_task("fight"),
                "원본 실행": lambda: start_task("fight_gui"),
                "토벌런 업데이트": lambda: start_task("fight_update"),
                "설정 파일 초기화": lambda: os.path.exists(os.path.join(cfg.fight_path, "config.json")) and os.remove(os.path.join(cfg.fight_path, "config.json")),
                "프로그램 폴더 열기": lambda: os.startfile(cfg.fight_path),
                "프로젝트 홈페이지 열기": lambda: os.startfile("https://github.com/linruowuyin/Fhoe-Rail"),
            }
        )
        basicInputView.addSampleCard(
            icon="./assets/app/images/Herta.jpg",
            title="차분화 우주",
            action={
                "빠른 실행 ⭐": lambda: start_task("universe"),
                "원본 실행": lambda: start_task("universe_gui"),
                "시뮬레이션 우주 업데이트": lambda: start_task("universe_update"),
                "설정 파일 초기화": lambda: [os.remove(p) for p in map(lambda f: os.path.join(cfg.universe_path, f), ["info.yml", "info_old.yml"]) if os.path.exists(p)],
                "프로그램 폴더 열기": lambda: os.startfile(cfg.universe_path),
                "프로젝트 홈페이지 열기": lambda: os.startfile("https://github.com/CHNZYX/Auto_Simulated_Universe"),
            }
        )
        basicInputView.addSampleCard(
            icon="./assets/app/images/Bronya.jpg",
            title="빛 따라 금 찾아",
            action={
                "혼돈의 기억": lambda: start_task("forgottenhall"),
                "허구 이야기": lambda: start_task("purefiction"),
                "종말의 환영": lambda: start_task("apocalyptic"),
            }
        )

        self.vBoxLayout.addWidget(basicInputView)