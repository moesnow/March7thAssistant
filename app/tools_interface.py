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

        self.toolsLabel = QLabel("도구 상자", self)

        self.ToolsGroup = SettingCardGroup('도구 상자', self.scrollWidget)
        self.automaticPlotCard = AutoPlotSettingCard(
            FIF.IMAGE_EXPORT,
            "자동 대화",
            "스토리 화면 진입 후 자동으로 시작됩니다. 1920*1080 이상의 16:9 해상도를 지원하며, 클라우드·붕괴: 스타레일은 지원하지 않습니다."
        )
        self.gameScreenshotCard = PushSettingCard(
            '캡처',
            FIF.CLIPPING_TOOL,
            "게임 스크린샷",
            "프로그램이 획득한 이미지가 올바른지 확인하며, OCR 문자 인식을 지원합니다. (이상 확인용)"
        )
        self.unlockfpsCard = PushSettingCard(
            '잠금 해제',
            FIF.SPEED_HIGH,
            "프레임 잠금 해제",
            "레지스트리를 수정하여 120 프레임을 잠금 해제합니다. 이미 해제된 경우 다시 클릭하면 60 프레임으로 복구됩니다. (국제 서버 및 중국 서버 지원)"
        )
        self.redemptionCodeCard = PushSettingCardCode(
            '실행',
            FIF.BOOK_SHELF,
            "리딤코드",
            "redemption_code",
            self
        )
        self.cloudTouchCard = PushSettingCard(
            '시작',
            FIF.CLOUD,
            "터치스크린 모드 [베타]",
            "클라우드 게임 모바일 UI 방식으로 게임을 시작합니다. UU 원격 태블릿 터치 모드와 함께 사용할 수 있으며, 시작 후 명령어가 클립보드에 복사됩니다."
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
                    title='60프레임 복구 성공 (＾∀＾●)',
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
                    title='120프레임 잠금 해제 성공 (＾∀＾●)',
                    content="",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=1000,
                    parent=self
                )
        except:
            InfoBar.warning(
                title='잠금 해제 실패',
                content="게임 화질 설정을 '사용자 정의'로 변경 후 다시 시도해주세요",
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
                # 여러 번의 확인 대화 상자를 순차적으로 표시하여 경고를 강화합니다. 하나라도 취소하면 반환합니다.
                confirm_messages = [
                    ('이 기능은 타사 프로그램에 의존합니다',
                     'https://github.com/winTEuser/Genshin_StarRail_fps_unlocker\n이 기능을 사용하여 발생하는 모든 문제는 본 프로젝트 및 개발팀과 무관합니다. 계속하시겠습니까?'),
                    ('재확인: 위험이 있을 수 있습니다',
                     '작동 원리는 WriteProcessMemory를 통해 게임 내에 코드를 작성하는 것입니다. 계속하시겠습니까?'),
                    ('최종 확인: 신중하게 조작해주세요',
                     '계속 진행하고 터치스크린 모드를 활성화하시겠습니까?'),
                ]

                for title, message in confirm_messages:
                    from qfluentwidgets import MessageBox
                    step_confirm = MessageBox(title, message, self.window())
                    step_confirm.yesButton.setText('확인')
                    step_confirm.cancelButton.setText('취소')
                    if not step_confirm.exec():
                        return

                cfg.set_value("genshin_starRail_fps_unlocker_allow", True)

            if not game_path or not os.path.exists(game_path):
                InfoBar.warning(
                    title='게임 경로 설정 오류 (╥╯﹏╰╥)',
                    content="설정 -> 프로그램 에서 올바른 게임 경로를 설정해주세요",
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
                title='시작 성공 (＾∀＾●)',
                content="명령어가 클립보드에 복사되었습니다",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
        except Exception as e:
            InfoBar.warning(
                title='시작 실패',
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
                title='자동 대화 시작됨',
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
                title='자동 대화 중지됨',
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