# coding:utf-8
from qfluentwidgets import (SettingCardGroup, PushSettingCard, ScrollArea, ExpandLayout)
from qfluentwidgets import FluentIcon as FIF
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QLabel, QFileDialog

from .common.style_sheet import StyleSheet
from managers.config_manager import config
from .card.comboboxsettingcard1 import ComboBoxSettingCard1
from .card.switchsettingcard1 import SwitchSettingCard1
from .card.pushsettingcard1 import PushSettingCardStr, PushSettingCardEval, PushSettingCardDate
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
            self.tr('如果遇到问题请修改为DEBUG等级，可以显示更多信息'),
            texts=['INFO', 'DEBUG']
        )
        self.gameScreenshotCard = PushSettingCard(
            self.tr('捕获'),
            FIF.PHOTO,
            self.tr("游戏截图"),
            self.tr("检查程序获取的图像是否正确")
        )
        self.checkUpdateCard = SwitchSettingCard1(
            FIF.UPDATE,
            self.tr('启动时检测更新'),
            "新版本将更加稳定并拥有更多功能（建议启用）",
            "check_update"
        )
        self.autoExitCard = SwitchSettingCard1(
            FIF.CLOSE,
            self.tr('退出游戏'),
            self.tr('程序运行完后自动退出游戏'),
            "auto_exit"
        )
        self.neverStopCard = SwitchSettingCard1(
            FIF.SYNC,
            self.tr('循环运行'),
            self.tr('根据开拓力循环运行程序'),
            "never_stop"
        )
        self.powerLimitCard = PushSettingCardEval(
            self.tr('修改'),
            FIF.POWER_BUTTON,
            self.tr("再次运行所需开拓力"),
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
        self.instanceNameCard = PushSettingCardStr(
            self.tr('修改'),
            FIF.PALETTE,
            # self.tr("副本名称\n保证唯一即可，例如“孽兽之形”可以填写“兽之形”，低概率下复杂文字会识别错误"),
            self.tr("副本名称（不同副本类型需单独设置，除清体力外也会用于每日实训完成对应任务）               "),
            "instance_names"
        )
        self.powerNeedCard = PushSettingCardEval(
            self.tr('修改'),
            FIF.POWER_BUTTON,
            self.tr("副本所需开拓力"),
            "power_need"
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
            FIF.PEOPLE,
            self.tr('启用历战余响（每周体力优先完成三次「历战余响」）'),
            None,
            "echo_of_war_enable"
        )
        self.echoofwarRunTimeCard = PushSettingCardDate(
            self.tr('修改'),
            FIF.DATE_TIME,
            self.tr("上次完成三次「历战余响」的时间戳（每周运行）"),
            "echo_of_war_timestamp"
        )
        # self.borrowCharacterCard = SwitchSettingCard1(
        #     FIF.PEOPLE,
        #     self.tr('启用使用支援角色'),
        #     self.tr('建议四号位放无关紧要的角色避免练度导致翻车'),
        #     "borrow_character_enable"
        # )
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
            FIF.HELP,
            self.tr('启用领取支援奖励'),
            None,
            "assist_enable"
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

        self.FightGroup = SettingCardGroup(self.tr("锄大地"), self.scrollWidget)
        self.fightEnableCard = SwitchSettingCard1(
            FIF.BUS,
            self.tr('启用锄大地'),
            None,
            "fight_enable"
        )
        self.fightCommandCard = PushSettingCardStr(
            self.tr('修改'),
            FIF.COMMAND_PROMPT,
            self.tr("锄大地命令"),
            "fight_command"
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

        self.UniverseGroup = SettingCardGroup(self.tr("模拟宇宙"), self.scrollWidget)
        self.universeEnableCard = SwitchSettingCard1(
            FIF.VPN,
            self.tr('启用模拟宇宙'),
            None,
            "universe_enable"
        )
        self.universeCommandCard = PushSettingCardStr(
            self.tr('修改'),
            FIF.COMMAND_PROMPT,
            self.tr("模拟宇宙命令"),
            "universe_command"
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
        self.forgottenhallTeamInfoCard = PushSettingCard(
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
        self.programGroup.addSettingCard(self.autoExitCard)
        self.programGroup.addSettingCard(self.neverStopCard)
        self.programGroup.addSettingCard(self.powerLimitCard)

        self.GameGroup.addSettingCard(self.gamePathCard)

        self.PowerGroup.addSettingCard(self.instanceTypeCard)
        self.PowerGroup.addSettingCard(self.instanceNameCard)
        self.PowerGroup.addSettingCard(self.powerNeedCard)
        self.PowerGroup.addSettingCard(self.instanceTeamEnableCard)
        self.PowerGroup.addSettingCard(self.instanceTeamNumberCard)
        self.PowerGroup.addSettingCard(self.echoofwarEnableCard)
        self.PowerGroup.addSettingCard(self.echoofwarRunTimeCard)
        # self.PowerGroup.addSettingCard(self.borrowCharacterCard)
        # self.PowerGroup.addSettingCard(self.borrowForceCard)

        self.DailyGroup.addSettingCard(self.dispatchEnableCard)
        self.DailyGroup.addSettingCard(self.mailEnableCard)
        self.DailyGroup.addSettingCard(self.assistEnableCard)
        # self.DailyGroup.addSettingCard(self.photoEnableCard)
        # self.DailyGroup.addSettingCard(self.synthesisEnableCard)
        self.DailyGroup.addSettingCard(self.lastRunTimeCard)

        self.FightGroup.addSettingCard(self.fightEnableCard)
        self.FightGroup.addSettingCard(self.fightCommandCard)
        self.FightGroup.addSettingCard(self.fightTimeoutCard)
        self.FightGroup.addSettingCard(self.fightTeamEnableCard)
        self.FightGroup.addSettingCard(self.fightTeamNumberCard)
        self.FightGroup.addSettingCard(self.FightRunTimeCard)

        self.UniverseGroup.addSettingCard(self.universeEnableCard)
        self.UniverseGroup.addSettingCard(self.universeCommandCard)
        self.UniverseGroup.addSettingCard(self.universeTimeoutCard)
        self.UniverseGroup.addSettingCard(self.universeRunTimeCard)

        self.ForgottenhallGroup.addSettingCard(self.forgottenhallEnableCard)
        self.ForgottenhallGroup.addSettingCard(self.forgottenhallLevelCard)
        self.ForgottenhallGroup.addSettingCard(self.forgottenhallRetriesCard)
        self.ForgottenhallGroup.addSettingCard(self.forgottenhallTeamInfoCard)
        self.ForgottenhallGroup.addSettingCard(self.forgottenhallTeam1Card)
        self.ForgottenhallGroup.addSettingCard(self.forgottenhallTeam2Card)
        self.ForgottenhallGroup.addSettingCard(self.forgottenhallRunTimeCard)

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
        """ download folder card clicked slot """
        game_path, _ = QFileDialog.getOpenFileName(self, "选择游戏路径", "", "All Files (*)")
        if not game_path or config.game_path == game_path:
            return

        config.set_value("game_path", game_path)
        self.gamePathCard.setContent(game_path)

    def __onForgottenhallTeamInfoCardClicked(self):
        os.system("start /WAIT explorer .\\assets\\images\\character")

    def __connectSignalToSlot(self):
        """ connect signal to slot """

        # game settings
        self.gameScreenshotCard.clicked.connect(self.__onGameScreenshotCardClicked)
        self.gamePathCard.clicked.connect(self.__onGamePathCardClicked)
        self.forgottenhallTeamInfoCard.clicked.connect(self.__onForgottenhallTeamInfoCardClicked)
