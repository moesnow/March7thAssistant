from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QSpacerItem
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import SettingCardGroup, PushSettingCard, ScrollArea, InfoBar, InfoBarPosition, MessageBox
from .card.messagebox_custom import MessageBoxEditMultiple
from .card.pushsettingcard1 import PushSettingCardCode
from .common.style_sheet import StyleSheet
from utils.registry.star_rail_setting import get_game_fps, set_game_fps, get_graphics_setting
import tasks.tool as tool
import base64
import subprocess
import pyperclip
from module.config import cfg
import os


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
            self.tr("通过修改注册表解锁120帧率，如已解锁，再次点击将恢复60帧率（支持国服和国际服）（不支持云·星穹铁道）")
        )
        self.redemptionCodeCard = PushSettingCardCode(
            self.tr('执行'),
            FIF.BOOK_SHELF,
            self.tr("兑换码"),
            "redemption_code",
            self
        )
        self.cloudTouchCard = PushSettingCard(
            self.tr('启动'),
            FIF.CLOUD,
            self.tr("触屏模式（暂不可用）"),
            self.tr("以云游戏移动端 UI 的方式启动游戏，可搭配 Sunshine 和 Moonlight 使用，启动后会将命令复制到剪贴板内")
        )
        self.cloudTouchCard.setDisabled(True)

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
        self.ToolsGroup.addSettingCard(self.cloudTouchCard)

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
                    title=self.tr('恢复60成功 (＾∀＾●)'),
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
                    title=self.tr('解锁120成功 (＾∀＾●)'),
                    content="",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=1000,
                    parent=self
                )
        except:
            InfoBar.warning(
                title=self.tr('解锁失败'),
                content="请将游戏图像质量修改为自定义后重试",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

    def __onCloudTouchCardClicked(self):
        try:
            if not os.path.exists(cfg.game_path):
                InfoBar.warning(
                    title=self.tr('游戏路径配置错误(╥╯﹏╰╥)'),
                    content="请在“设置”-->“程序”中配置",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
                return
            graphics_setting = get_graphics_setting()
            if graphics_setting is None:
                raise Exception("请将游戏图像质量修改为自定义后重试")
            args = ["-is_cloud", "1", "-platform_type", "CLOUD_WEB_TOUCH", "-graphics_setting", base64.b64encode(graphics_setting).decode("utf-8")]
            subprocess.Popen([cfg.game_path] + args)
            pyperclip.copy(f'"{cfg.game_path}" {" ".join(args)}')
            InfoBar.success(
                title=self.tr('启动成功(＾∀＾●)'),
                content="已将命令复制到剪贴板",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
        except Exception as e:
            InfoBar.warning(
                title=self.tr('启动失败'),
                content=str(e),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

    def __connectSignalToSlot(self):
        self.gameScreenshotCard.clicked.connect(lambda: tool.start("screenshot"))
        self.automaticPlotCard.clicked.connect(lambda: tool.start("plot"))
        self.unlockfpsCard.clicked.connect(self.__onUnlockfpsCardClicked)
        self.cloudTouchCard.clicked.connect(self.__onCloudTouchCardClicked)
