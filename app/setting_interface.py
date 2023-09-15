# coding:utf-8
from qfluentwidgets import (SettingCardGroup, PushSettingCard, ScrollArea, ExpandLayout, PrimaryPushSettingCard)
from qfluentwidgets import FluentIcon as FIF
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWidgets import QWidget, QLabel, QFileDialog
from PyQt5.QtGui import QDesktopServices

from .common.style_sheet import StyleSheet
from managers.config_manager import config
from .card.comboboxsettingcard1 import ComboBoxSettingCard1
from .card.switchsettingcard1 import SwitchSettingCard1
from .card.pushsettingcard1 import PushSettingCardStr, PushSettingCardEval, PushSettingCardDate

from .tools.check_update import checkUpdate

import sys
import os


class SettingInterface(ScrollArea):
    """ Setting interface """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.parent = parent
        self.scrollWidget = QWidget()
        self.expandLayout = ExpandLayout(self.scrollWidget)

        # setting label
        self.settingLabel = QLabel(self.tr("设置"), self)

        # program group
        self.programGroup = SettingCardGroup(self.tr('程序设置'), self.scrollWidget)
        self.logLevelCard = ComboBoxSettingCard1(
            "log_level",
            FIF.TAG,
            self.tr('日志等级'),
            self.tr('如果遇到异常请修改为DEBUG等级（可以显示更多信息）'),
            texts=['INFO', 'DEBUG']
        )
        self.gameScreenshotCard = PushSettingCard(
            self.tr('捕获'),
            FIF.PHOTO,
            self.tr("游戏截图"),
            self.tr("检查程序获取的图像是否正确，支持OCR识别文字（可用于复制副本名称）")
        )
        self.checkUpdateCard = SwitchSettingCard1(
            FIF.UPDATE,
            self.tr('启动时检测更新'),
            "新版本将更加稳定并拥有更多功能（建议启用）",
            "check_update"
        )
        self.pipMirrorCard = PushSettingCardStr(
            self.tr('修改'),
            FIF.SEARCH_MIRROR,
            self.tr("PyPI 镜像"),
            "pip_mirror"
        )
        self.githubMirrorCard = PushSettingCardStr(
            self.tr('修改'),
            FIF.GITHUB,
            self.tr("GitHub 镜像（留空代表不启用）"),
            "github_mirror"
        )
        self.autoExitCard = SwitchSettingCard1(
            FIF.POWER_BUTTON,
            self.tr('退出游戏'),
            self.tr('程序运行完后自动退出游戏（仅限完整运行生效）'),
            "auto_exit"
        )
        self.neverStopCard = SwitchSettingCard1(
            FIF.SYNC,
            self.tr('循环运行'),
            self.tr('保持命令行窗口开启，根据开拓力7×24小时无人值守循环运行程序（仅限完整运行生效）'),
            "never_stop"
        )
        self.powerLimitCard = PushSettingCardEval(
            self.tr('修改'),
            FIF.HEART,
            self.tr("循环运行再次启动所需开拓力（凌晨四点优先级更高）"),
            "power_limit"
        )

        self.GameGroup = SettingCardGroup(self.tr("游戏设置"), self.scrollWidget)

        self.gamePathCard = PushSettingCard(
            self.tr('修改'),
            FIF.GAME,
            self.tr("游戏路径"),
            config.game_path
        )

        self.PowerGroup = SettingCardGroup(self.tr("体力设置"), self.scrollWidget)

        self.instanceTypeCard = ComboBoxSettingCard1(
            "instance_type",
            FIF.ALIGNMENT,
            self.tr('副本类型'),
            None,
            texts=['侵蚀隧洞', '凝滞虚影', '拟造花萼（金）', '拟造花萼（赤）']
        )
        self.instanceNameCard = PushSettingCardEval(
            self.tr('修改'),
            FIF.PALETTE,
            # self.tr("副本名称\n保证唯一即可，例如“孽兽之形”可以填写“兽之形”，低概率下复杂文字会识别错误"),
            self.tr("副本名称（不同副本类型需单独设置，同时也会用于完成每日实训，“无”代表不启用）               "),
            "instance_names"
        )
        # self.powerNeedCard = PushSettingCardEval(
        #     self.tr('修改'),
        #     FIF.HEART,
        #     self.tr("副本所需开拓力（其中“拟造花萼”设置为60代表每次刷6轮）               "),
        #     "power_needs"
        # )
        self.borrowCharacterEnableCard = SwitchSettingCard1(
            FIF.PEOPLE,
            self.tr('启用使用支援角色'),
            self.tr('无论何时都要使用支援角色，即使日常实训中没有要求'),
            "borrow_character_enable"
        )
        self.borrowCharacterCard = PushSettingCardEval(
            self.tr('修改'),
            FIF.ARROW_DOWN,
            self.tr("支援角色优先级从高到低"),
            "borrow_character"
        )
        self.instanceTeamEnableCard = SwitchSettingCard1(
            FIF.EDIT,
            self.tr('启用自动切换队伍'),
            None,
            "instance_team_enable"
        )
        self.instanceTeamNumberCard = ComboBoxSettingCard1(
            "instance_team_number",
            FIF.FLAG,
            self.tr('打副本使用的队伍编号'),
            None,
            texts=['1', '2', '3', '4', '5', '6']
        )
        self.echoofwarEnableCard = SwitchSettingCard1(
            FIF.ROBOT,
            self.tr('启用历战余响'),
            "每周体力优先完成三次「历战余响」",
            "echo_of_war_enable"
        )
        self.echoofwarRunTimeCard = PushSettingCardDate(
            self.tr('修改'),
            FIF.DATE_TIME,
            self.tr("上次完成历战余响的时间（每周运行）"),
            "echo_of_war_timestamp"
        )
        # self.borrowForceCard = SwitchSettingCard1(
        #     FIF.CALORIES,
        #     self.tr('强制使用支援角色'),
        #     self.tr('无论何时都要使用支援角色，即使设置的角色都没找到'),
        #     "borrow_force"
        # )

        self.DailyGroup = SettingCardGroup(self.tr("日常"), self.scrollWidget)

        self.dispatchEnableCard = SwitchSettingCard1(
            FIF.STOP_WATCH,
            self.tr('启用领取派遣奖励'),
            None,
            "dispatch_enable"
        )
        self.mailEnableCard = SwitchSettingCard1(
            FIF.MAIL,
            self.tr('启用领取邮件奖励'),
            None,
            "mail_enable"
        )
        self.assistEnableCard = SwitchSettingCard1(
            FIF.BRUSH,
            self.tr('启用领取支援奖励'),
            None,
            "assist_enable"
        )
        self.srpassEnableCard = SwitchSettingCard1(
            FIF.RINGER,
            self.tr('启用领取无名勋礼奖励'),
            "此设置不会影响领取无名勋礼经验，大月卡玩家请不要开启此功能",
            "srpass_enable"
        )
        # self.photoEnableCard = SwitchSettingCard1(
        #     FIF.PHOTO,
        #     self.tr('启用每日拍照'),
        #     None,
        #     "photo_enable"
        # )
        # self.synthesisEnableCard = SwitchSettingCard1(
        #     FIF.ASTERISK,
        #     self.tr('启用每日合成/使用 材料/消耗品'),
        #     None,
        #     "synthesis_enable"
        # )
        self.lastRunTimeCard = PushSettingCardDate(
            self.tr('修改'),
            FIF.DATE_TIME,
            self.tr("上次运行日常的时间（每天运行）"),
            "last_run_timestamp"
        )

        self.FightGroup = SettingCardGroup(self.tr("锄大地 (Fhoe-Rail)"), self.scrollWidget)
        self.fightEnableCard = SwitchSettingCard1(
            FIF.BUS,
            self.tr('启用锄大地'),
            None,
            "fight_enable"
        )
        self.fightPathCard = PushSettingCardStr(
            self.tr('修改'),
            FIF.COMMAND_PROMPT,
            self.tr("锄大地路径"),
            "fight_path"
        )
        self.fightTimeoutCard = PushSettingCardEval(
            self.tr('修改'),
            FIF.HISTORY,
            self.tr("锄大地超时（单位小时）"),
            "fight_timeout"
        )
        self.fightTeamEnableCard = SwitchSettingCard1(
            FIF.EDIT,
            self.tr('启用自动切换队伍'),
            None,
            "fight_team_enable"
        )
        self.fightTeamNumberCard = ComboBoxSettingCard1(
            "fight_team_number",
            FIF.FLAG,
            self.tr('锄大地使用的队伍编号'),
            None,
            texts=['1', '2', '3', '4', '5', '6']
        )
        self.FightRunTimeCard = PushSettingCardDate(
            self.tr('修改'),
            FIF.DATE_TIME,
            self.tr("上次运行锄大地的时间（每天运行）"),
            "fight_timestamp"
        )
        self.guiFightCard = PrimaryPushSettingCard(
            self.tr('启动'),
            FIF.SETTING,
            self.tr('原版运行'),
            self.tr('启动调试模式，可以选择指定地图继续锄大地'),
        )

        self.UniverseGroup = SettingCardGroup(self.tr("模拟宇宙 (Auto_Simulated_Universe)"), self.scrollWidget)
        self.universeEnableCard = SwitchSettingCard1(
            FIF.VPN,
            self.tr('启用模拟宇宙'),
            None,
            "universe_enable"
        )
        self.universeBonusEnableCard = SwitchSettingCard1(
            FIF.IOT,
            self.tr('启用领取沉浸奖励'),
            None,
            "universe_bonus_enable"
        )
        self.universePathCard = PushSettingCardStr(
            self.tr('修改'),
            FIF.COMMAND_PROMPT,
            self.tr("模拟宇宙路径"),
            "universe_path"
        )
        self.universeTimeoutCard = PushSettingCardEval(
            self.tr('修改'),
            FIF.HISTORY,
            self.tr("模拟宇宙超时（单位小时）"),
            "universe_timeout"
        )
        self.universeRunTimeCard = PushSettingCardDate(
            self.tr('修改'),
            FIF.DATE_TIME,
            self.tr("上次运行模拟宇宙的时间（每周运行）"),
            "universe_timestamp"
        )
        self.guiUniverseCard = PrimaryPushSettingCard(
            self.tr('启动'),
            FIF.SETTING,
            self.tr('原版运行'),
            self.tr('启动后可以修改命途和难度等'),
        )
        self.updateUniverseCard = PrimaryPushSettingCard(
            self.tr('更新'),
            FIF.UPDATE,
            self.tr('更新模拟宇宙'),
            None
        )

        self.ForgottenhallGroup = SettingCardGroup(self.tr("忘却之庭"), self.scrollWidget)
        self.forgottenhallEnableCard = SwitchSettingCard1(
            FIF.TILES,
            self.tr('启用忘却之庭'),
            None,
            "forgottenhall_enable"
        )
        self.forgottenhallLevelCard = PushSettingCardEval(
            self.tr('修改'),
            FIF.MINIMIZE,
            self.tr("混沌回忆关卡范围"),
            "forgottenhall_level"
        )
        self.forgottenhallRetriesCard = PushSettingCardEval(
            self.tr('修改'),
            FIF.REMOVE_FROM,
            self.tr("混沌回忆挑战失败后的重试次数"),
            "forgottenhall_retries"
        )
        self.forgottenhallTeamInfoCard = PrimaryPushSettingCard(
            self.tr('打开角色文件夹'),
            FIF.INFO,
            self.tr("↓↓混沌回忆队伍↓↓"),
            self.tr("数字代表秘技使用次数，其中 -1 代表最后一个放秘技和普攻的角色\n角色对应的英文名字可以在 \"March7thAssistant\\assets\\images\\character\" 中查看")
        )
        self.forgottenhallTeam1Card = PushSettingCardEval(
            self.tr('修改'),
            FIF.FLAG,
            self.tr("混沌回忆队伍1"),
            "forgottenhall_team1"
        )
        self.forgottenhallTeam2Card = PushSettingCardEval(
            self.tr('修改'),
            FIF.FLAG,
            self.tr("混沌回忆队伍2"),
            "forgottenhall_team2"
        )
        self.forgottenhallRunTimeCard = PushSettingCardDate(
            self.tr('修改'),
            FIF.DATE_TIME,
            self.tr("上次运行混沌回忆的时间（每周运行，如已经满星则跳过）"),
            "forgottenhall_timestamp"
        )

        self.KeybindingGroup = SettingCardGroup(self.tr("按键绑定"), self.scrollWidget)
        self.keybindingTechnique = PushSettingCardStr(
            self.tr('修改'),
            FIF.TILES,
            self.tr("游戏内设置的秘技按键"),
            "hotkey_technique"
        )

        self.aboutGroup = SettingCardGroup(self.tr('关于'), self.scrollWidget)
        self.githubCard = PrimaryPushSettingCard(
            self.tr('项目主页'),
            FIF.GITHUB,
            self.tr('项目主页'),
            "https://github.com/moesnow/March7thAssistant"
        )
        self.qqGroupCard = PrimaryPushSettingCard(
            self.tr('加入群聊'),
            FIF.EXPRESSIVE_INPUT_ENTRY,
            self.tr('QQ群'),
            "855392201"
        )
        self.feedbackCard = PrimaryPushSettingCard(
            self.tr('提供反馈'),
            FIF.FEEDBACK,
            self.tr('提供反馈'),
            self.tr('帮助我们改进 March7thAssistant')
        )
        self.aboutCard = PrimaryPushSettingCard(
            self.tr('检查更新'),
            FIF.INFO,
            self.tr('关于'),
            self.tr('当前版本：') + " " + config.version
        )

        self.__initWidget()

    def __initWidget(self):
        self.resize(1000, 800)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 80, 0, 20)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setObjectName('settingInterface')

        # initialize style sheet
        self.scrollWidget.setObjectName('scrollWidget')
        self.settingLabel.setObjectName('settingLabel')
        StyleSheet.SETTING_INTERFACE.apply(self)

        self.__initLayout()
        self.__connectSignalToSlot()

    def __initLayout(self):
        self.settingLabel.move(36, 30)
        # add cards to group
        self.programGroup.addSettingCard(self.logLevelCard)
        self.programGroup.addSettingCard(self.gameScreenshotCard)
        self.programGroup.addSettingCard(self.checkUpdateCard)
        self.programGroup.addSettingCard(self.pipMirrorCard)
        self.programGroup.addSettingCard(self.githubMirrorCard)
        self.programGroup.addSettingCard(self.autoExitCard)
        self.programGroup.addSettingCard(self.neverStopCard)
        self.programGroup.addSettingCard(self.powerLimitCard)

        self.GameGroup.addSettingCard(self.gamePathCard)

        self.PowerGroup.addSettingCard(self.instanceTypeCard)
        self.PowerGroup.addSettingCard(self.instanceNameCard)
        # self.PowerGroup.addSettingCard(self.powerNeedCard)
        self.PowerGroup.addSettingCard(self.borrowCharacterEnableCard)
        self.PowerGroup.addSettingCard(self.borrowCharacterCard)
        self.PowerGroup.addSettingCard(self.instanceTeamEnableCard)
        self.PowerGroup.addSettingCard(self.instanceTeamNumberCard)
        self.PowerGroup.addSettingCard(self.echoofwarEnableCard)
        self.PowerGroup.addSettingCard(self.echoofwarRunTimeCard)
        # self.PowerGroup.addSettingCard(self.borrowForceCard)

        self.DailyGroup.addSettingCard(self.dispatchEnableCard)
        self.DailyGroup.addSettingCard(self.mailEnableCard)
        self.DailyGroup.addSettingCard(self.assistEnableCard)
        self.DailyGroup.addSettingCard(self.srpassEnableCard)
        # self.DailyGroup.addSettingCard(self.photoEnableCard)
        # self.DailyGroup.addSettingCard(self.synthesisEnableCard)
        self.DailyGroup.addSettingCard(self.lastRunTimeCard)

        self.FightGroup.addSettingCard(self.fightEnableCard)
        self.FightGroup.addSettingCard(self.fightPathCard)
        self.FightGroup.addSettingCard(self.fightTimeoutCard)
        self.FightGroup.addSettingCard(self.fightTeamEnableCard)
        self.FightGroup.addSettingCard(self.fightTeamNumberCard)
        self.FightGroup.addSettingCard(self.FightRunTimeCard)
        self.FightGroup.addSettingCard(self.guiFightCard)

        self.UniverseGroup.addSettingCard(self.universeEnableCard)
        self.UniverseGroup.addSettingCard(self.universeBonusEnableCard)
        self.UniverseGroup.addSettingCard(self.universePathCard)
        self.UniverseGroup.addSettingCard(self.universeTimeoutCard)
        self.UniverseGroup.addSettingCard(self.universeRunTimeCard)
        self.UniverseGroup.addSettingCard(self.guiUniverseCard)
        self.UniverseGroup.addSettingCard(self.updateUniverseCard)

        self.ForgottenhallGroup.addSettingCard(self.forgottenhallEnableCard)
        self.ForgottenhallGroup.addSettingCard(self.forgottenhallLevelCard)
        self.ForgottenhallGroup.addSettingCard(self.forgottenhallRetriesCard)
        self.ForgottenhallGroup.addSettingCard(self.forgottenhallTeamInfoCard)
        self.ForgottenhallGroup.addSettingCard(self.forgottenhallTeam1Card)
        self.ForgottenhallGroup.addSettingCard(self.forgottenhallTeam2Card)
        self.ForgottenhallGroup.addSettingCard(self.forgottenhallRunTimeCard)

        self.KeybindingGroup.addSettingCard(self.keybindingTechnique)

        self.aboutGroup.addSettingCard(self.githubCard)
        self.aboutGroup.addSettingCard(self.qqGroupCard)
        self.aboutGroup.addSettingCard(self.feedbackCard)
        self.aboutGroup.addSettingCard(self.aboutCard)

        # add setting card group to layout
        self.expandLayout.setSpacing(28)
        self.expandLayout.setContentsMargins(36, 10, 36, 0)
        self.expandLayout.addWidget(self.programGroup)
        self.expandLayout.addWidget(self.GameGroup)
        self.expandLayout.addWidget(self.PowerGroup)
        self.expandLayout.addWidget(self.DailyGroup)
        self.expandLayout.addWidget(self.FightGroup)
        self.expandLayout.addWidget(self.UniverseGroup)
        self.expandLayout.addWidget(self.ForgottenhallGroup)
        self.expandLayout.addWidget(self.KeybindingGroup)
        self.expandLayout.addWidget(self.aboutGroup)

    def __onGameScreenshotCardClicked(self):
        from tasks.base.windowswitcher import WindowSwitcher
        from module.automation.screenshot import Screenshot
        if WindowSwitcher.check_and_switch(config.game_title_name):
            result = Screenshot.take_screenshot(config.game_title_name)
            if result:
                # if not os.path.exists("screenshots"):
                #     os.makedirs("screenshots")
                # screenshot_path = os.path.abspath("screenshots\screenshot.png")
                # result[0].save(screenshot_path)
                # os.startfile(os.path.dirname(screenshot_path))

                import tkinter as tk
                from .tools.screenshot import ScreenshotApp

                root = tk.Tk()
                app = ScreenshotApp(root, result[0])
                root.mainloop()

    def __onGamePathCardClicked(self):
        game_path, _ = QFileDialog.getOpenFileName(self, "选择游戏路径", "", "All Files (*)")
        if not game_path or config.game_path == game_path:
            return

        config.set_value("game_path", game_path)
        self.gamePathCard.setContent(game_path)

    def __onGuiUniverseCardClicked(self):
        script_path = sys.argv[0]
        script_filename = os.path.basename(script_path)

        if script_filename.endswith(".exe"):
            os.system(f"start ./\"March7th Assistant/March7th Assistant.exe\" universe_gui")
        else:
            os.system(f"start python main.py universe_gui")

    def __onGuiFightCardClicked(self):
        script_path = sys.argv[0]
        script_filename = os.path.basename(script_path)

        if script_filename.endswith(".exe"):
            os.system(f"start ./\"March7th Assistant/March7th Assistant.exe\" fight_gui")
        else:
            os.system(f"start python main.py fight_gui")

    def __onUpdateUniverseCardClicked(self):
        script_path = sys.argv[0]
        script_filename = os.path.basename(script_path)

        if script_filename.endswith(".exe"):
            os.system(f"start ./\"March7th Assistant/March7th Assistant.exe\" universe_update")
        else:
            os.system(f"start python main.py universe_update")

    def __connectSignalToSlot(self):
        """ connect signal to slot """

        self.gameScreenshotCard.clicked.connect(self.__onGameScreenshotCardClicked)
        self.gamePathCard.clicked.connect(self.__onGamePathCardClicked)
        self.forgottenhallTeamInfoCard.clicked.connect(lambda: os.system("start /WAIT explorer .\\assets\\images\\character"))
        self.guiFightCard.clicked.connect(self.__onGuiFightCardClicked)
        self.guiUniverseCard.clicked.connect(self.__onGuiUniverseCardClicked)
        self.updateUniverseCard.clicked.connect(self.__onUpdateUniverseCardClicked)
        self.githubCard.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/moesnow/March7thAssistant")))
        self.qqGroupCard.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://qm.qq.com/q/9gFqUrUGVq")))
        self.feedbackCard.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/moesnow/March7thAssistant/issues")))
        self.aboutCard.clicked.connect(lambda: checkUpdate(self))
