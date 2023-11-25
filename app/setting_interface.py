# coding:utf-8
from qfluentwidgets import (SettingCardGroup, PushSettingCard, ScrollArea, InfoBar, PrimaryPushSettingCard, Pivot, qrouter)
from qfluentwidgets import FluentIcon as FIF
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWidgets import QWidget, QLabel, QFileDialog, QVBoxLayout, QStackedWidget
from PyQt5.QtGui import QDesktopServices

from .common.style_sheet import StyleSheet
from managers.config_manager import config
from .card.comboboxsettingcard1 import ComboBoxSettingCard1
from .card.comboboxsettingcard2 import ComboBoxSettingCard2
from .card.switchsettingcard1 import SwitchSettingCard1
from .card.rangesettingcard1 import RangeSettingCard1
from .card.pushsettingcard1 import PushSettingCardDictInstanceNames, PushSettingCardEval, PushSettingCardDate, PushSettingCardKey, PushSettingCardDictStr, PushSettingCardDictBool

from .tools.check_update import checkUpdate
from tasks.base.command import start_task

import subprocess


class SettingInterface(ScrollArea):
    """ Setting interface """

    Nav = Pivot

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.parent = parent
        self.scrollWidget = QWidget()
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)

        self.pivot = self.Nav(self)
        self.stackedWidget = QStackedWidget(self)

        # setting label
        self.settingLabel = QLabel(self.tr("设置"), self)

        # program group
        self.ProgramGroup = SettingCardGroup(self.tr('程序设置'), self.scrollWidget)
        self.logLevelCard = ComboBoxSettingCard2(
            "log_level",
            FIF.TAG,
            self.tr('日志等级'),
            # self.tr('如果遇到异常和错误请修改为详细'),
            "",
            texts={'简洁': 'INFO', '详细': 'DEBUG'}
        )
        self.importConfigCard = PushSettingCard(
            self.tr('导入'),
            FIF.ADD_TO,
            self.tr('导入配置'),
            self.tr('选择需要导入的 config.yaml 文件（重启后生效）')
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
        self.afterFinishCard = ComboBoxSettingCard2(
            "after_finish",
            FIF.POWER_BUTTON,
            self.tr('任务完成后'),
            self.tr('其中“退出”指退出游戏，“循环”指根据开拓力7×24小时无人值守循环运行程序（仅限完整运行生效）'),
            texts={'无': 'None', '退出': 'Exit', '循环': 'Loop', '关机': 'Shutdown', '休眠': 'Hibernate', '睡眠': 'Sleep'}
        )
        self.playAudioCard = SwitchSettingCard1(
            FIF.ALBUM,
            self.tr('声音提示'),
            self.tr('任务完成后列车长唱歌提示帕！'),
            "play_audio"
        )
        # self.powerLimitCard = PushSettingCardEval(
        #     self.tr('修改'),
        #     FIF.HEART,
        #     self.tr("循环运行再次启动所需开拓力（凌晨四点优先级更高）"),
        #     "power_limit"
        # )
        self.powerLimitCard = RangeSettingCard1(
            "power_limit",
            [10, 240],
            FIF.HEART,
            self.tr("循环运行再次启动所需开拓力（凌晨四点优先级更高）"),
        )
        self.gamePathCard = PushSettingCard(
            self.tr('修改'),
            FIF.GAME,
            self.tr("游戏路径"),
            config.game_path
        )
        # self.useWindowsTerminalCard = SwitchSettingCard1(
        #     FIF.COMMAND_PROMPT,
        #     self.tr('优先使用 Windows 终端'),
        #     self.tr('界面更好看且支持显示Emoji表情'),
        #     "use_windows_terminal"
        # )

        # self.GameGroup = SettingCardGroup(self.tr("游戏设置"), self.scrollWidget)
        # self.gamePathCard = PushSettingCard(
        #     self.tr('修改'),
        #     FIF.GAME,
        #     self.tr("游戏路径"),
        #     config.game_path
        # )

        self.PowerGroup = SettingCardGroup(self.tr("体力设置"), self.scrollWidget)

        self.instanceTypeCard = ComboBoxSettingCard1(
            "instance_type",
            FIF.ALIGNMENT,
            self.tr('副本类型'),
            None,
            texts=['拟造花萼（金）', '拟造花萼（赤）', '凝滞虚影', '侵蚀隧洞']
        )
        self.instanceNameCard = PushSettingCardDictInstanceNames(
            self.tr('修改'),
            FIF.PALETTE,
            # self.tr("副本名称\n保证唯一即可，例如“孽兽之形”可以填写“兽之形”，低概率下复杂文字会识别错误"),
            # self.tr("副本名称（也会用于完成每日实训，“无”代表不启用）"),
            self.tr("副本名称"),
            "instance_names"
        )
        self.instanceTeamEnableCard = SwitchSettingCard1(
            FIF.EDIT,
            self.tr('自动切换队伍'),
            None,
            "instance_team_enable"
        )
        self.instanceTeamNumberCard = ComboBoxSettingCard1(
            "instance_team_number",
            FIF.FLAG,
            self.tr('队伍编号'),
            None,
            texts=['1', '2', '3', '4', '5', '6']
        )
        self.useReservedTrailblazePowerEnableCard = SwitchSettingCard1(
            FIF.HEART,
            self.tr('使用后备开拓力'),
            "",
            "use_reserved_trailblaze_power"
        )
        self.useFuelEnableCard = SwitchSettingCard1(
            FIF.CAFE,
            self.tr('使用燃料'),
            "",
            "use_fuel"
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
            self.tr("上次完成历战余响的时间"),
            "echo_of_war_timestamp"
        )

        self.BorrowGroup = SettingCardGroup(self.tr("支援设置"), self.scrollWidget)
        self.borrowCharacterEnableCard = SwitchSettingCard1(
            FIF.PEOPLE,
            self.tr('启用使用支援角色'),
            self.tr('无论何时都要使用支援角色，即使日常实训中没有要求'),
            "borrow_character_enable"
        )
        self.borrowCharacterFromCard = PushSettingCardEval(
            self.tr('修改'),
            FIF.VIEW,
            self.tr("指定好友的支援角色（如存在则优先使用）"),
            "borrow_character_from"
        )
        self.borrowCharacterCard = PushSettingCardEval(
            self.tr('修改'),
            FIF.ARROW_DOWN,
            self.tr("支援角色优先级（从高到低）"),
            "borrow_character"
        )

        self.DailyGroup = SettingCardGroup(self.tr("日常设置"), self.scrollWidget)

        self.dispatchEnableCard = SwitchSettingCard1(
            FIF.STOP_WATCH,
            self.tr('领取委托奖励'),
            None,
            "dispatch_enable"
        )
        self.mailEnableCard = SwitchSettingCard1(
            FIF.MAIL,
            self.tr('领取邮件奖励'),
            None,
            "mail_enable"
        )
        self.assistEnableCard = SwitchSettingCard1(
            FIF.BRUSH,
            self.tr('领取支援奖励'),
            None,
            "assist_enable"
        )
        # self.srpassEnableCard = SwitchSettingCard1(
        #     FIF.RINGER,
        #     self.tr('领取无名勋礼奖励'),
        #     "取消勾选不会影响领取无名勋礼经验，大月卡玩家不要开启此功能",
        #     "srpass_enable"
        # )
        # self.dailyForgottenhallEnableCard = SwitchSettingCard1(
        #     FIF.TILES,
        #     self.tr('启用完成1次「忘却之庭」'),
        #     "请解锁混沌回忆并配置了队伍1后再打开该选项",
        #     "daily_forgottenhall_enable"
        # )
        self.dailyHimekoTryEnableCard = SwitchSettingCard1(
            FIF.TILES,
            self.tr('通过 “姬子试用” 完成任务'),
            "",
            "daily_himeko_try_enable"
        )
        self.dailyMemoryOneEnableCard = SwitchSettingCard1(
            FIF.TILES,
            self.tr('通过 “回忆一” 完成任务'),
            "请解锁混沌回忆并配置了队伍后再打开该选项",
            "daily_memory_one_enable"
        )
        self.dailyMemoryOneTeamCard = PushSettingCardEval(
            self.tr('修改'),
            FIF.FLAG,
            self.tr("用于 “回忆一” 的队伍"),
            "daily_memory_one_team"
        )
        self.dailyTasksCard = PushSettingCardDictBool(
            self.tr('修改'),
            FIF.PALETTE,
            self.tr("今日实训（False代表已完成）"),
            "daily_tasks"
        )
        self.lastRunTimeCard = PushSettingCardDate(
            self.tr('修改'),
            FIF.DATE_TIME,
            self.tr("上次检测日常的时间"),
            "last_run_timestamp"
        )

        self.FightGroup = SettingCardGroup(self.tr("锄大地 (Fhoe-Rail)"), self.scrollWidget)
        self.fightEnableCard = SwitchSettingCard1(
            FIF.BUS,
            self.tr('启用锄大地'),
            "",
            # self.tr('仅限完整运行生效'),
            "fight_enable"
        )
        self.fightOperationModeCard = ComboBoxSettingCard2(
            "fight_operation_mode",
            FIF.COMMAND_PROMPT,
            self.tr('运行模式'),
            self.tr('集成模式适合开箱即用。源码模式适合自定义，依赖 Python 环境。'),
            texts={'集成': 'exe', '源码': 'source'}
        )
        # self.fightPathCard = PushSettingCardStr(
        #     self.tr('修改'),
        #     FIF.COMMAND_PROMPT,
        #     self.tr("锄大地路径"),
        #     "fight_path"
        # )
        # self.fightTimeoutCard = PushSettingCardEval(
        #     self.tr('修改'),
        #     FIF.HISTORY,
        #     self.tr("锄大地超时（单位小时）"),
        #     "fight_timeout"
        # )
        self.fightTimeoutCard = RangeSettingCard1(
            "fight_timeout",
            [1, 10],
            FIF.HISTORY,
            self.tr("锄大地超时"),
            self.tr("超过设定时间强制停止（单位小时）"),
        )
        self.fightTeamEnableCard = SwitchSettingCard1(
            FIF.EDIT,
            self.tr('自动切换队伍'),
            None,
            "fight_team_enable"
        )
        self.fightTeamNumberCard = ComboBoxSettingCard1(
            "fight_team_number",
            FIF.FLAG,
            self.tr('队伍编号'),
            None,
            texts=['1', '2', '3', '4', '5', '6']
        )
        self.FightRunTimeCard = PushSettingCardDate(
            self.tr('修改'),
            FIF.DATE_TIME,
            self.tr("上次运行锄大地的时间"),
            "fight_timestamp"
        )
        self.guiFightCard = PrimaryPushSettingCard(
            self.tr('启动'),
            FIF.SETTING,
            self.tr('原版运行'),
            self.tr('启动调试模式，可以选择指定地图继续锄大地'),
        )
        self.updateFightCard = PrimaryPushSettingCard(
            self.tr('更新'),
            FIF.UPDATE,
            self.tr('更新锄大地 (Fhoe-Rail)'),
            None
        )

        self.UniverseGroup = SettingCardGroup(self.tr("模拟宇宙 (Auto_Simulated_Universe)"), self.scrollWidget)
        self.universeEnableCard = SwitchSettingCard1(
            FIF.VPN,
            self.tr('启用模拟宇宙'),
            "",
            # self.tr('仅限完整运行生效'),
            "universe_enable"
        )
        self.universeOperationModeCard = ComboBoxSettingCard2(
            "universe_operation_mode",
            FIF.COMMAND_PROMPT,
            self.tr('运行模式'),
            self.tr('集成模式适合开箱即用。源码模式适合自定义，依赖 Python 环境。'),
            texts={'集成': 'exe', '源码': 'source'}
        )
        # self.universePathCard = PushSettingCardStr(
        #     self.tr('修改'),
        #     FIF.COMMAND_PROMPT,
        #     self.tr("模拟宇宙路径"),
        #     "universe_path"
        # )
        # self.universeTimeoutCard = PushSettingCardEval(
        #     self.tr('修改'),
        #     FIF.HISTORY,
        #     self.tr("模拟宇宙超时（单位小时）"),
        #     "universe_timeout"
        # )
        self.universeTimeoutCard = RangeSettingCard1(
            "universe_timeout",
            [1, 24],
            FIF.HISTORY,
            self.tr("模拟宇宙超时"),
            self.tr("超过设定时间强制停止（单位小时）"),
        )
        self.universeRunTimeCard = PushSettingCardDate(
            self.tr('修改'),
            FIF.DATE_TIME,
            self.tr("上次运行模拟宇宙的时间"),
            "universe_timestamp"
        )
        self.universeBonusEnableCard = SwitchSettingCard1(
            FIF.IOT,
            self.tr('领取沉浸奖励'),
            None,
            "universe_bonus_enable"
        )
        self.universeFrequencyCard = ComboBoxSettingCard2(
            "universe_frequency",
            FIF.MINIMIZE,
            self.tr('运行频率'),
            '',
            texts={'每周': 'weekly', '每天': 'daily'}
        )
        self.universeCountCard = RangeSettingCard1(
            "universe_count",
            [0, 34],
            FIF.HISTORY,
            self.tr("运行次数"),
            self.tr("注意中途停止不会计数，0 代表不指定，使用模拟宇宙原版逻辑"),
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
            self.tr('更新模拟宇宙 (Auto_Simulated_Universe)'),
            None
        )

        self.ForgottenhallGroup = SettingCardGroup(self.tr("忘却之庭"), self.scrollWidget)
        self.forgottenhallEnableCard = SwitchSettingCard1(
            FIF.TILES,
            self.tr('启用混沌回忆'),
            "",
            # self.tr('仅限完整运行生效'),
            "forgottenhall_enable"
        )
        self.forgottenhallLevelCard = PushSettingCardEval(
            self.tr('修改'),
            FIF.MINIMIZE,
            self.tr("关卡范围"),
            "forgottenhall_level"
        )
        # self.forgottenhallRetriesCard = PushSettingCardEval(
        #     self.tr('修改'),
        #     FIF.REMOVE_FROM,
        #     self.tr("混沌回忆挑战失败后的重试次数"),
        #     "forgottenhall_retries"
        # )
        self.forgottenhallRetriesCard = RangeSettingCard1(
            "forgottenhall_retries",
            [0, 10],
            FIF.REMOVE_FROM,
            self.tr("重试次数"),
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
            self.tr("上次运行混沌回忆的时间"),
            "forgottenhall_timestamp"
        )

        self.NotifyGroup = SettingCardGroup(self.tr("消息推送"), self.scrollWidget)
        self.testNotifyCard = PrimaryPushSettingCard(
            self.tr('发送消息'),
            FIF.TILES,
            self.tr("测试消息推送"),
            ""
        )
        self.winotifyEnableCard = SwitchSettingCard1(
            FIF.BACK_TO_WINDOW,
            self.tr('启用 Windows 原生通知'),
            None,
            "notify_winotify_enable"
        )

        self.KeybindingGroup = SettingCardGroup(self.tr("按键"), self.scrollWidget)
        self.keybindingTechniqueCard = PushSettingCardKey(
            self.tr('按住以修改'),
            FIF.TILES,
            self.tr("秘技"),
            "hotkey_technique"
        )

        self.AboutGroup = SettingCardGroup(self.tr('关于'), self.scrollWidget)
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
        self.ProgramGroup.addSettingCard(self.logLevelCard)
        self.ProgramGroup.addSettingCard(self.importConfigCard)
        self.ProgramGroup.addSettingCard(self.gameScreenshotCard)
        self.ProgramGroup.addSettingCard(self.checkUpdateCard)
        self.ProgramGroup.addSettingCard(self.afterFinishCard)
        self.ProgramGroup.addSettingCard(self.playAudioCard)
        self.ProgramGroup.addSettingCard(self.powerLimitCard)
        # self.ProgramGroup.addSettingCard(self.useWindowsTerminalCard)
        self.ProgramGroup.addSettingCard(self.gamePathCard)

        # self.GameGroup.addSettingCard(self.gamePathCard)

        self.PowerGroup.addSettingCard(self.instanceTypeCard)
        self.PowerGroup.addSettingCard(self.instanceNameCard)
        self.PowerGroup.addSettingCard(self.instanceTeamEnableCard)
        self.PowerGroup.addSettingCard(self.instanceTeamNumberCard)
        self.PowerGroup.addSettingCard(self.useReservedTrailblazePowerEnableCard)
        self.PowerGroup.addSettingCard(self.useFuelEnableCard)
        self.PowerGroup.addSettingCard(self.echoofwarEnableCard)
        self.PowerGroup.addSettingCard(self.echoofwarRunTimeCard)

        self.BorrowGroup.addSettingCard(self.borrowCharacterEnableCard)
        self.BorrowGroup.addSettingCard(self.borrowCharacterFromCard)
        self.BorrowGroup.addSettingCard(self.borrowCharacterCard)

        self.DailyGroup.addSettingCard(self.dispatchEnableCard)
        self.DailyGroup.addSettingCard(self.mailEnableCard)
        self.DailyGroup.addSettingCard(self.assistEnableCard)
        # self.DailyGroup.addSettingCard(self.srpassEnableCard)
        # self.DailyGroup.addSettingCard(self.dailyForgottenhallEnableCard)
        self.DailyGroup.addSettingCard(self.dailyHimekoTryEnableCard)
        self.DailyGroup.addSettingCard(self.dailyMemoryOneEnableCard)
        self.DailyGroup.addSettingCard(self.dailyMemoryOneTeamCard)
        self.DailyGroup.addSettingCard(self.dailyTasksCard)
        self.DailyGroup.addSettingCard(self.lastRunTimeCard)

        self.FightGroup.addSettingCard(self.fightEnableCard)
        self.FightGroup.addSettingCard(self.fightOperationModeCard)
        # self.FightGroup.addSettingCard(self.fightPathCard)
        self.FightGroup.addSettingCard(self.fightTimeoutCard)
        self.FightGroup.addSettingCard(self.fightTeamEnableCard)
        self.FightGroup.addSettingCard(self.fightTeamNumberCard)
        self.FightGroup.addSettingCard(self.FightRunTimeCard)
        self.FightGroup.addSettingCard(self.guiFightCard)
        self.FightGroup.addSettingCard(self.updateFightCard)

        self.UniverseGroup.addSettingCard(self.universeEnableCard)
        self.UniverseGroup.addSettingCard(self.universeOperationModeCard)
        # self.UniverseGroup.addSettingCard(self.universePathCard)
        self.UniverseGroup.addSettingCard(self.universeTimeoutCard)
        self.UniverseGroup.addSettingCard(self.universeBonusEnableCard)
        self.UniverseGroup.addSettingCard(self.universeFrequencyCard)
        self.UniverseGroup.addSettingCard(self.universeCountCard)
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

        self.NotifyGroup.addSettingCard(self.testNotifyCard)
        self.NotifyGroup.addSettingCard(self.winotifyEnableCard)

        self.KeybindingGroup.addSettingCard(self.keybindingTechniqueCard)

        self.AboutGroup.addSettingCard(self.githubCard)
        self.AboutGroup.addSettingCard(self.qqGroupCard)
        self.AboutGroup.addSettingCard(self.feedbackCard)
        self.AboutGroup.addSettingCard(self.aboutCard)

        self.ProgramGroup.titleLabel.setHidden(True)
        # self.GameGroup.titleLabel.setHidden(True)
        self.PowerGroup.titleLabel.setHidden(True)
        self.BorrowGroup.titleLabel.setHidden(True)
        self.DailyGroup.titleLabel.setHidden(True)
        self.FightGroup.titleLabel.setHidden(True)
        self.UniverseGroup.titleLabel.setHidden(True)
        self.ForgottenhallGroup.titleLabel.setHidden(True)
        self.NotifyGroup.titleLabel.setHidden(True)
        self.KeybindingGroup.titleLabel.setHidden(True)
        self.AboutGroup.titleLabel.setHidden(True)

        # add items to pivot
        self.addSubInterface(self.ProgramGroup, 'programInterface', self.tr('程序'))
        # self.addSubInterface(self.GameGroup, 'GameInterface', self.tr('游戏'))
        self.addSubInterface(self.PowerGroup, 'PowerInterface', self.tr('体力'))
        self.addSubInterface(self.BorrowGroup, 'BorrowInterface', self.tr('支援'))
        self.addSubInterface(self.DailyGroup, 'DailyInterface', self.tr('日常'))
        self.addSubInterface(self.FightGroup, 'FightInterface', self.tr('锄大地'))
        self.addSubInterface(self.UniverseGroup, 'UniverseInterface', self.tr('模拟宇宙'))
        self.addSubInterface(self.ForgottenhallGroup, 'ForgottenhallInterface', self.tr('忘却之庭'))
        self.addSubInterface(self.NotifyGroup, 'NotifyInterface', self.tr('推送'))
        self.addSubInterface(self.KeybindingGroup, 'KeybindingInterface', self.tr('按键'))
        self.addSubInterface(self.AboutGroup, 'AboutInterface', self.tr('关于'))

        self.vBoxLayout.addWidget(self.pivot, 0, Qt.AlignLeft)
        self.vBoxLayout.addWidget(self.stackedWidget)

        # StyleSheet.NAVIGATION_VIEW_INTERFACE.apply(self)

        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.stackedWidget.setCurrentWidget(self.ProgramGroup)
        self.pivot.setCurrentItem(self.ProgramGroup.objectName())

        qrouter.setDefaultRouteKey(self.stackedWidget, self.ProgramGroup.objectName())

        # add setting card group to layout
        # self.vBoxLayout.setSpacing(28)
        self.vBoxLayout.setContentsMargins(36, 10, 36, 0)
        # self.vBoxLayout.addWidget(self.programGroup)
        # self.vBoxLayout.addWidget(self.GameGroup)
        # self.vBoxLayout.addWidget(self.PowerGroup)
        # self.vBoxLayout.addWidget(self.DailyGroup)
        # self.vBoxLayout.addWidget(self.FightGroup)
        # self.vBoxLayout.addWidget(self.UniverseGroup)
        # self.vBoxLayout.addWidget(self.ForgottenhallGroup)
        # self.vBoxLayout.addWidget(self.NotifyGroup)
        # self.vBoxLayout.addWidget(self.KeybindingGroup)
        # self.vBoxLayout.addWidget(self.AboutGroup)

    def addSubInterface(self, widget: QLabel, objectName, text):
        widget.setObjectName(objectName)
        self.stackedWidget.addWidget(widget)
        self.pivot.addItem(
            routeKey=objectName,
            text=text,
            onClick=lambda: self.stackedWidget.setCurrentWidget(widget)
        )

    def onCurrentIndexChanged(self, index):
        widget = self.stackedWidget.widget(index)
        self.pivot.setCurrentItem(widget.objectName())
        qrouter.push(self.stackedWidget, widget.objectName())

    def __onImportConfigCardClicked(self):
        configdir, _ = QFileDialog.getOpenFileName(self, "选取配置文件", "./", "Config Files (*.yaml)")
        if (configdir != ""):
            config._load_config(configdir)
            config.save_config()
            # self.importConfigCard.button.setText("导入完成，请重启小助手")
            self.__showRestartTooltip()

    def __onGameScreenshotCardClicked(self):
        from tasks.base.windowswitcher import WindowSwitcher
        from module.automation.screenshot import Screenshot
        if WindowSwitcher.check_and_switch(config.game_title_name):
            result = Screenshot.take_screenshot(config.game_title_name)
            if result:
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

    def __showRestartTooltip(self):
        """ show restart tooltip """
        InfoBar.success(
            self.tr('更新成功'),
            self.tr('配置在重启软件后生效'),
            duration=1500,
            parent=self
        )

    def __connectSignalToSlot(self):
        """ connect signal to slot """

        self.importConfigCard.clicked.connect(self.__onImportConfigCardClicked)
        self.gameScreenshotCard.clicked.connect(self.__onGameScreenshotCardClicked)
        self.gamePathCard.clicked.connect(self.__onGamePathCardClicked)

        self.forgottenhallTeamInfoCard.clicked.connect(lambda: subprocess.check_call("start /WAIT explorer .\\assets\\images\\character", shell=True))

        self.guiUniverseCard.clicked.connect(lambda: start_task("universe_gui"))
        self.guiFightCard.clicked.connect(lambda: start_task("fight_gui"))
        self.updateUniverseCard.clicked.connect(lambda: start_task("universe_update"))
        self.updateFightCard.clicked.connect(lambda: start_task("fight_update"))

        self.testNotifyCard.clicked.connect(lambda: start_task("notify"))

        self.githubCard.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/moesnow/March7thAssistant")))
        self.qqGroupCard.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://qm.qq.com/q/9gFqUrUGVq")))
        self.feedbackCard.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/moesnow/March7thAssistant/issues")))

        self.aboutCard.clicked.connect(lambda: checkUpdate(self.parent))
