from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QSpacerItem
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import SettingCardGroup, PushSettingCard, ScrollArea
from .common.style_sheet import StyleSheet


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

        self.ToolsGroup.titleLabel.setHidden(True)

        self.vBoxLayout.setSpacing(28)
        self.vBoxLayout.setContentsMargins(36, 10, 36, 0)
        self.vBoxLayout.addWidget(self.ToolsGroup)

        for i in range(self.ToolsGroup.vBoxLayout.count()):
            item = self.ToolsGroup.vBoxLayout.itemAt(i)
            if isinstance(item, QSpacerItem):
                self.ToolsGroup.vBoxLayout.removeItem(item)
                break

    def __onGameScreenshotCardClicked(self):
        from tasks.tools.game_screenshot import game_screenshot
        game_screenshot()

    def __onAutomaticPlotCardClicked(self):
        from tasks.tools.automatic_plot import automatic_plot
        automatic_plot()

    def __connectSignalToSlot(self):
        self.gameScreenshotCard.clicked.connect(self.__onGameScreenshotCardClicked)
        self.automaticPlotCard.clicked.connect(self.__onAutomaticPlotCardClicked)
