from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QSpacerItem
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import SettingCardGroup, PushSettingCard, ScrollArea, InfoBar, InfoBarPosition, MessageBox
from .card.messagebox_custom import MessageBoxEditMultiple
from .card.pushsettingcard1 import PushSettingCardCode
from .common.style_sheet import StyleSheet
from utils.registry.star_rail_setting import get_game_fps, set_game_fps
import tasks.tool as tool


class ToolsInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.parent = parent
        self.scrollWidget = QWidget()
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)

        self.toolsLabel = QLabel(self.tr("工具箱"), self)

        self.ToolsGroup = SettingCardGroup(self.tr('工具箱'), self.scrollWidget)
        self.automaticPlotCard = PushSettingCard(
            self.tr('运行'),
            FIF.IMAGE_EXPORT,
            self.tr("自动对话"),
            ''
        )
        self.gameScreenshotCard = PushSettingCard(
            self.tr('捕获'),
            FIF.CLIPPING_TOOL,
            self.tr("游戏截图"),
            self.tr("检查程序获取的图像是否正确，支持OCR识别文字（可用于复制副本名称）")
        )
        self.unlockfpsCard = PushSettingCard(
            self.tr('解锁'),
            FIF.SPEED_HIGH,
            self.tr("解锁帧率"),
            self.tr("通过修改注册表解锁120帧率，如已解锁，再次点击将恢复60帧率（未测试国际服）")
        )
        self.redemptionCodeCard = PushSettingCardCode(
            self.tr('执行'),
            FIF.SPEED_HIGH,
            self.tr("兑换码"),
            "redemption_code"
        )

        self.__initWidget()

    def __initWidget(self):
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 80, 0, 20)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setObjectName('toolsInterface')

        self.scrollWidget.setObjectName('scrollWidget')
        self.toolsLabel.setObjectName('toolsLabel')
        StyleSheet.TOOLS_INTERFACE.apply(self)

        self.__initLayout()
        self.__connectSignalToSlot()

    def __initLayout(self):
        self.toolsLabel.move(36, 30)

        self.ToolsGroup.addSettingCard(self.automaticPlotCard)
        self.ToolsGroup.addSettingCard(self.gameScreenshotCard)
        self.ToolsGroup.addSettingCard(self.unlockfpsCard)
        self.ToolsGroup.addSettingCard(self.redemptionCodeCard)

        self.ToolsGroup.titleLabel.setHidden(True)

        self.vBoxLayout.setSpacing(28)
        self.vBoxLayout.setContentsMargins(36, 10, 36, 0)
        self.vBoxLayout.addWidget(self.ToolsGroup)

        for i in range(self.ToolsGroup.vBoxLayout.count()):
            item = self.ToolsGroup.vBoxLayout.itemAt(i)
            if isinstance(item, QSpacerItem):
                self.ToolsGroup.vBoxLayout.removeItem(item)
                break

    def __onUnlockfpsCardClicked(self):
        try:
            fps = get_game_fps()
            if fps == 120:
                set_game_fps(60)
                InfoBar.success(
                    title=self.tr('恢复60成功(＾∀＾●)'),
                    content="",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=1000,
                    parent=self
                )
            else:
                set_game_fps(120)
                InfoBar.success(
                    title=self.tr('解锁120成功(＾∀＾●)'),
                    content="",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=1000,
                    parent=self
                )
        except:
            InfoBar.warning(
                title=self.tr('解锁失败(╥╯﹏╰╥)'),
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )

    def __connectSignalToSlot(self):
        self.gameScreenshotCard.clicked.connect(lambda: tool.start("screenshot"))
        self.automaticPlotCard.clicked.connect(lambda: tool.start("plot"))
        self.unlockfpsCard.clicked.connect(self.__onUnlockfpsCardClicked)
