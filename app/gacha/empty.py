"""没有抽卡记录时的空状态：Q 版三月七拿放大镜，加三步引导。"""
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QFont, QFontMetricsF, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, FluentIcon as FIF, PrimaryPushButton, PushButton, SimpleCardWidget, StrongBodyLabel, setFont

from app.common.design_tokens import PAGE_MARGIN
from app.common.icon import UiIcon
from app.common.mascot import Mascot, load_mascot
from app.overview.style import tone
from app.pages.common import is_evernight, secondary, style_primary
from module.localization import tr

MASCOT_HEIGHT = 230


class StepNumber(QWidget):
    def __init__(self, number, parent=None):
        super().__init__(parent)
        self._number = str(number)
        self._font = QFont(self.font())
        setFont(self, 12, QFont.Weight.DemiBold)
        self.setFixedSize(22, 22)

    def paintEvent(self, event):
        background, foreground = tone("accent", is_evernight())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawEllipse(QRectF(self.rect()))
        painter.setPen(foreground)
        painter.setFont(self.font())
        metrics = QFontMetricsF(self.font())
        painter.drawText(QPointF((self.width() - metrics.horizontalAdvance(self._number)) / 2,
                                 (self.height() + metrics.ascent() - metrics.descent()) / 2), self._number)


class EmptyState(QWidget):
    updateRequested = Signal()
    importRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._available = True
        self.card = SimpleCardWidget(self)
        self.card.setBorderRadius(12)
        self.card.setMaximumWidth(900)
        self.card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.mascot = QLabel(self.card)
        self.mascot.setFixedSize(QSize(196, MASCOT_HEIGHT + 6))
        self.mascot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.titleLabel = StrongBodyLabel(self.card)
        setFont(self.titleLabel, 22, QFont.Weight.DemiBold)
        self.subtitleLabel = secondary(BodyLabel(self.card))
        setFont(self.subtitleLabel, 13)
        self.subtitleLabel.setWordWrap(True)
        self.steps = []
        steps = QVBoxLayout()
        steps.setSpacing(10)
        for number in (1, 2, 3):
            row = QWidget(self.card)
            line = QHBoxLayout(row)
            line.setContentsMargins(0, 0, 0, 0)
            line.setSpacing(10)
            label = BodyLabel(row)
            setFont(label, 14)
            label.setWordWrap(True)
            line.addWidget(StepNumber(number, row), 0, Qt.AlignmentFlag.AlignTop)
            line.addWidget(label, 1)
            steps.addWidget(row)
            self.steps.append((row, label))
        self.updateButton = PrimaryPushButton(FIF.SYNC, "", self.card)
        self.updateButton.clicked.connect(self.updateRequested)
        self.importButton = PushButton(UiIcon.IMPORT, "", self.card)
        self.importButton.clicked.connect(self.importRequested)
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addWidget(self.updateButton)
        buttons.addWidget(self.importButton)
        buttons.addStretch(1)
        column = QVBoxLayout()
        column.setSpacing(0)
        column.addWidget(self.titleLabel)
        column.addSpacing(6)
        column.addWidget(self.subtitleLabel)
        column.addSpacing(16)
        column.addLayout(steps)
        column.addSpacing(22)
        column.addLayout(buttons)
        inner = QHBoxLayout(self.card)
        inner.setContentsMargins(36, 26, 40, 28)
        inner.setSpacing(30)
        inner.addWidget(self.mascot, 0, Qt.AlignmentFlag.AlignVCenter)
        inner.addLayout(column, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.card, 20)
        row.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAGE_MARGIN, 8, PAGE_MARGIN, 32)
        layout.addStretch(2)
        layout.addLayout(row)
        layout.addStretch(3)
        self.retranslateUi()
        self.restyle()

    def retranslateUi(self, available=None, reason=""):
        if available is not None:
            self._available = bool(available)
        self.titleLabel.setText(tr("还没有抽卡记录"))
        if self._available:
            self.subtitleLabel.setText(tr("小助手读取的是游戏里的跃迁记录页，不会改动游戏数据。三步就好："))
        else:
            self.subtitleLabel.setText(reason or tr("这台电脑上不能从游戏更新抽卡记录，可以导入其他工具导出的文件。"))
        texts = (tr("在游戏里打开「跃迁」→「查看详情」→「跃迁记录」，等记录页加载出来"),
                 tr("回到这里点「更新记录」，第一次会读取全部历史，可能需要一两分钟"),
                 tr("换过电脑？也可以导入其他工具导出的 UIGF / SRGF 文件"))
        for (row, label), text in zip(self.steps, texts):
            label.setText(text)
            row.setVisible(self._available)
        self.updateButton.setText(tr("更新记录"))
        self.updateButton.setVisible(self._available)
        self.importButton.setText(tr("导入 UIGF / SRGF 文件"))

    def setUpdateEnabled(self, enabled):
        self.updateButton.setEnabled(enabled)

    def restyle(self):
        evernight = is_evernight()
        style_primary(self.updateButton, evernight)
        ratio = self.devicePixelRatioF() or 1.0
        self.mascot.setPixmap(load_mascot(Mascot.SEARCH, MASCOT_HEIGHT, ratio, evernight=evernight))
        for row, label in self.steps:
            row.update()

    def showEvent(self, event):
        super().showEvent(event)
        if abs((self.mascot.pixmap().devicePixelRatio() if not self.mascot.pixmap().isNull() else 0)
               - (self.devicePixelRatioF() or 1.0)) > 0.01:
            self.restyle()
