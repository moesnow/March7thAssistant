"""还没有保存账号时的说明。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, FluentIcon, PrimaryPushButton, SimpleCardWidget, TitleLabel, qconfig

from app.common.mascot import Mascot, load_mascot
from app.pages import style
from app.pages.common import is_evernight, secondary, style_primary
from module.localization import tr

MASCOT_HEIGHT = 200


class Step(QWidget):
    def __init__(self, number, parent=None):
        super().__init__(parent)
        self.numberLabel = QLabel(str(number), self)
        self.numberLabel.setFixedSize(24, 24)
        self.numberLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.textLabel = BodyLabel(self)
        self.textLabel.setWordWrap(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self.numberLabel, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.textLabel, 1)

    def restyle(self):
        background, foreground = style.status_colors("accent")
        self.numberLabel.setStyleSheet(
            f"background: rgba({background.red()}, {background.green()}, {background.blue()}, {background.alphaF():.3f});"
            f"color: {foreground.name()}; border-radius: 12px; font-weight: 600;")


class EmptyAccounts(QWidget):
    addClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.card = SimpleCardWidget(self)
        self.card.setBorderRadius(8)
        self.card.setMaximumWidth(860)
        self.mascot = QLabel(self.card)
        self.titleLabel = TitleLabel(self.card)
        self.titleLabel.setWordWrap(True)
        self.textLabel = secondary(BodyLabel(self.card))
        self.textLabel.setWordWrap(True)
        self.steps = [Step(index + 1, self.card) for index in range(3)]
        self.addButton = PrimaryPushButton(FluentIcon.ADD, "", self.card)
        self.addButton.clicked.connect(self.addClicked)
        column = QVBoxLayout()
        column.setSpacing(10)
        column.addStretch(1)
        column.addWidget(self.titleLabel)
        column.addWidget(self.textLabel)
        column.addSpacing(6)
        for step in self.steps:
            column.addWidget(step)
        column.addSpacing(8)
        column.addWidget(self.addButton, 0, Qt.AlignmentFlag.AlignLeft)
        column.addStretch(1)
        row = QHBoxLayout(self.card)
        row.setContentsMargins(44, 32, 44, 32)
        row.setSpacing(40)
        row.addWidget(self.mascot, 0, Qt.AlignmentFlag.AlignCenter)
        row.addLayout(column, 1)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 12, 24)
        outer.addStretch(1)
        outer.addWidget(self.card, 20)
        outer.addStretch(1)
        qconfig.themeChanged.connect(self.restyle)
        qconfig.themeColorChanged.connect(self.restyle)
        self.retranslateUi()
        self.restyle()

    @staticmethod
    def introduction():
        return tr("把登录保存下来，换号时不用重新登录；保存两个以上就可以按顺序轮流运行。只支持本地客户端。")

    def retranslateUi(self):
        self.titleLabel.setText(tr("还没有保存账号"))
        self.textLabel.setText(self.introduction())
        texts = (tr("启动游戏，登录要添加的账号，完全进入游戏（看到角色）"),
                 tr("回到这里点「添加账号」，保存它的登录"),
                 tr("在游戏里换一个账号，再添加一次；全部添加好后打开多账号轮流"))
        for step, text in zip(self.steps, texts):
            step.textLabel.setText(text)
        self.addButton.setText(tr("添加账号"))

    def restyle(self, *_):
        evernight = is_evernight()
        self.mascot.setPixmap(load_mascot(Mascot.OK, MASCOT_HEIGHT, self.devicePixelRatioF(), evernight=evernight))
        for step in self.steps:
            step.restyle()
        style_primary(self.addButton, evernight)
