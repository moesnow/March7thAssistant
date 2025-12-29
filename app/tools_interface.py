from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QSpacerItem, QScroller, QScrollerProperties
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import SettingCardGroup, PushSettingCard, ScrollArea, InfoBar, InfoBarPosition
from .card.pushsettingcard1 import PushSettingCardCode
from .card.autoplot_setting_card import AutoPlotSettingCard
from .common.style_sheet import StyleSheet
from utils.registry.star_rail_setting import get_game_fps, set_game_fps, get_graphics_setting
import tasks.tool as tool
import base64
import subprocess
import pyperclip
from module.config import cfg
from tasks.base.tasks import start_task
import os


class ToolsInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.parent = parent
        self.scrollWidget = QWidget()
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)

        self.toolsLabel = QLabel("工具箱", self)

        self.ToolsGroup = SettingCardGroup('工具箱', self.scrollWidget)
        self.automaticPlotCard = AutoPlotSettingCard(
            FIF.IMAGE_EXPORT,
            "自动对话",
            "进入剧情页面后自动开始运行，支持大于等于 1920*1080 的 16:9 分辨率，不支持云·星穹铁道"
        )
        self.gameScreenshotCard = PushSettingCard(
            '捕获',
            FIF.CLIPPING_TOOL,
            "游戏截图",
            "检查程序获取的图像是否正确，支持OCR识别文字（可用于自行排查异常）"
        )
        self.unlockfpsCard = PushSettingCard(
            '解锁',
            FIF.SPEED_HIGH,
            "解锁帧率",
            "通过修改注册表解锁120帧率，如已解锁，再次点击将恢复60帧率（支持国服和国际服）"
        )
        self.redemptionCodeCard = PushSettingCardCode(
            '执行',
            FIF.BOOK_SHELF,
            "兑换码",
            "redemption_code",
            self
        )
        self.cloudTouchCard = PushSettingCard(
            '启动',
            FIF.CLOUD,
            "触屏模式【测试版】",
            "以云游戏移动端 UI 的方式启动游戏，可搭配 UU远程 平板触控模式，启动后会将命令复制到剪贴板内"
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

        QScroller.grabGesture(self.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)
        scroller = QScroller.scroller(self.viewport())
        scroller_props = scroller.scrollerProperties()
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootDragDistanceFactor, 0.05)
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootScrollDistanceFactor, 0.05)
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.DecelerationFactor, 0.5)
        scroller.setScrollerProperties(scroller_props)

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
                InfoBar.info(
                    title='恢复60成功 (＾∀＾●)',
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
                    title='解锁120成功 (＾∀＾●)',
                    content="",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=1000,
                    parent=self
                )
        except:
            InfoBar.warning(
                title='解锁失败',
                content="请将游戏图像质量修改为自定义后重试",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

    def __onCloudTouchCardClicked(self):
        exe_path = os.path.abspath(os.path.join(cfg.genshin_starRail_fps_unlocker_path, "unlocker.exe"))
        config_path = os.path.abspath(os.path.join(cfg.genshin_starRail_fps_unlocker_path, "hoyofps_config.ini"))
        game_path = os.path.abspath(cfg.game_path)
        try:
            if cfg.genshin_starRail_fps_unlocker_allow is False:
                from qfluentwidgets import MessageBox
                # 依次展示多次确认对话框，每次提示更严肃，任意一次取消即返回
                confirm_messages = [
                    ('此功能依赖第三方程序实现',
                     'https://github.com/winTEuser/Genshin_StarRail_fps_unlocker\n使用本功能产生的所有问题与本项目与开发者团队无关，是否继续？'),
                    ('再次确认：可能存在风险',
                     '工作原理是通过 WriteProcessMemory 把代码写进游戏，是否继续？'),
                    ('最终确认：请谨慎操作',
                     '确认继续并允许启用触屏模式？'),
                ]

                for title, message in confirm_messages:
                    from qfluentwidgets import MessageBox
                    step_confirm = MessageBox(title, message, self.window())
                    step_confirm.yesButton.setText('确认')
                    step_confirm.cancelButton.setText('取消')
                    if not step_confirm.exec():
                        return

                cfg.set_value("genshin_starRail_fps_unlocker_allow", True)

            if not game_path or not os.path.exists(game_path):
                InfoBar.warning(
                    title='游戏路径配置错误(╥╯﹏╰╥)',
                    content="请在“设置”-->“程序”中配置正确的游戏路径",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
                return

            if not os.path.exists(exe_path):
                start_task("mobileui_update")
                return

            config_dir = os.path.dirname(config_path)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)

            import configparser
            cp = configparser.ConfigParser()

            if os.path.exists(config_path):
                cp.read(config_path, encoding='utf-16')
                if 'Setting' not in cp:
                    cp['Setting'] = {}
                old_path = cp['Setting'].get('HKSRPath', '')
                if old_path != game_path:
                    cp['Setting']['HKSRPath'] = game_path
                    with open(config_path, 'w', encoding='utf-16') as f:
                        cp.write(f)
            else:
                cp['Setting'] = {'HKSRPath': game_path}
                with open(config_path, 'w', encoding='utf-16') as f:
                    cp.write(f)
            args = ["-HKSR", "-EnableMobileUI"]
            subprocess.Popen([exe_path] + args, cwd=config_dir)
            pyperclip.copy(f'cd "{config_dir}" && "{exe_path}" {" ".join(args)}')
            InfoBar.success(
                title='启动成功(＾∀＾●)',
                content="已将命令复制到剪贴板",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
        except Exception as e:
            InfoBar.warning(
                title='启动失败',
                content=str(e),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

    def __connectSignalToSlot(self):
        self.gameScreenshotCard.clicked.connect(lambda: tool.start("screenshot"))
        self.automaticPlotCard.switchChanged.connect(self.__onAutoPlotSwitchChanged)
        self.automaticPlotCard.optionsChanged.connect(self.__onAutoPlotOptionsChanged)
        self.unlockfpsCard.clicked.connect(self.__onUnlockfpsCardClicked)
        self.cloudTouchCard.clicked.connect(self.__onCloudTouchCardClicked)

    def __onAutoPlotSwitchChanged(self, isChecked: bool):
        """Handle auto plot switch state change"""
        if isChecked:
            # Update options first
            options = self.automaticPlotCard.getOptions()
            tool.update_plot_options(options)
            # Start auto plot
            tool.start("plot")
            InfoBar.success(
                title='自动对话已启动',
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )
        else:
            # Stop auto plot
            tool.stop_plot()
            InfoBar.info(
                title='自动对话已停止',
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )

    def __onAutoPlotOptionsChanged(self, options: dict):
        """Handle auto plot options change"""
        # Update options if auto plot is running
        if self.automaticPlotCard.getSwitchState():
            tool.update_plot_options(options)
