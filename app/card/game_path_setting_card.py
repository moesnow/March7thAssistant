from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import QPushButton
from qfluentwidgets import ExpandSettingCard, SettingCard, ComboBox, CaptionLabel, FluentIcon as FIF

from module.localization import tr


class GamePathSettingCard(ExpandSettingCard):
    """游戏路径保留修改按钮，启动方式作为默认收起的子设置。"""

    clicked = Signal()
    expandStateChanged = Signal(bool)

    def __init__(self, parent=None):
        from module.config import cfg
        self.cfg = cfg
        super().__init__(FIF.GAME, tr("游戏路径"), cfg.game_path, parent)
        self.button = QPushButton(tr("修改"), self)
        self.button.setObjectName("pushButton")
        self.card.addWidget(self.button)
        self.button.clicked.connect(self.clicked.emit)

        self.launchMethodCard = SettingCard(FIF.GAME, tr("游戏启动方式"), parent=self.view)
        self.comboBox = ComboBox(self.launchMethodCard)
        self.comboBox.addItem(tr("直接启动"), userData="direct")
        self.comboBox.addItem(tr("通过 Epic 启动"), userData="epic")
        self.comboBox.setCurrentIndex(1 if cfg.get_value("game_launch_method", "direct") == "epic" else 0)
        self.launchMethodCard.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignmentFlag.AlignRight)
        self.launchMethodCard.hBoxLayout.addSpacing(16)
        self.viewLayout.addWidget(self.launchMethodCard)

        self.epicDescription = CaptionLabel(tr("请选择 Epic 渠道版 StarRail.exe，助手将通过 Epic 打开启动器并自动点击‘开始游戏’。需提前登录 Epic。"), self.view)
        self.epicDescription.setWordWrap(True)
        self.epicDescription.setContentsMargins(48, 0, 24, 12)
        self.viewLayout.addWidget(self.epicDescription)
        self.comboBox.currentIndexChanged.connect(self._onLaunchMethodChanged)
        self.expandAni.finished.connect(self._onExpandFinished)
        self._updateDescription()

    def setContent(self, content):
        self.card.setContent(content)

    def _onLaunchMethodChanged(self, index):
        self.cfg.set_value("game_launch_method", self.comboBox.itemData(index))
        self._updateDescription()

    def _updateDescription(self):
        self.epicDescription.setVisible(self.comboBox.currentData() == "epic")
        self.viewLayout.activate()
        self._adjustViewSize()
        if self.isExpand:
            self.expandStateChanged.emit(False)  # 子内容高度改变后让设置页重算高度

    def setExpand(self, isExpand):
        if self.isExpand == isExpand:
            return
        if isExpand:
            self.expandStateChanged.emit(True)
        super().setExpand(isExpand)

    def _onExpandFinished(self):
        if not self.isExpand:
            # 说明文字换行/显隐会在动画期间改变滚动范围，收尾以实际标题高度为准。
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
            self.setFixedHeight(self.card.height())
            self.expandStateChanged.emit(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "epicDescription"):
            QTimer.singleShot(0, self._updateDescription)
