from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QFont
from PyQt5.QtWidgets import QWidget, QLabel, QFileDialog, QVBoxLayout, QStackedWidget, QSpacerItem, QScrollArea, QSizePolicy
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import SettingCardGroup, PushSettingCard, ScrollArea, InfoBar, PrimaryPushSettingCard
from app.sub_interfaces.accounts_interface import accounts_interface
from .common.style_sheet import StyleSheet
from .components.pivot import SettingPivot
from .card.comboboxsettingcard1 import ComboBoxSettingCard1
from .card.comboboxsettingcard2 import ComboBoxSettingCard2, ComboBoxSettingCardLog
from .card.switchsettingcard1 import SwitchSettingCard1, SwitchSettingCardNotify, StartMarch7thAssistantSwitchSettingCard, SwitchSettingCardTeam, SwitchSettingCardImmersifier, SwitchSettingCardGardenofplenty, SwitchSettingCardEchoofwar
from .card.rangesettingcard1 import RangeSettingCard1
from .card.pushsettingcard1 import PushSettingCardInstance, PushSettingCardNotifyTemplate, PushSettingCardMirrorchyan, PushSettingCardEval, PushSettingCardDate, PushSettingCardKey, PushSettingCardTeam, PushSettingCardFriends
from .card.timepickersettingcard1 import TimePickerSettingCard1
from module.config import cfg
from module.notification import notif
from tasks.base.tasks import start_task
from .tools.check_update import checkUpdate
import os


class SettingInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.scrollWidget = QWidget()
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)

        # self.title_area = QScrollArea(self)
        self.pivot = SettingPivot(self)
        self.stackedWidget = QStackedWidget(self)

        self.settingLabel = QLabel(self.tr("设置"), self)

        self.__initWidget()
        self.__initCard()
        self.__initLayout()
        self.__connectSignalToSlot()

    def __initWidget(self):
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setViewportMargins(0, 140, 0, 5)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # self.title_area.setWidget(self.pivot)
        # self.title_area.setWidgetResizable(True)
        # self.title_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        # self.title_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.title_area.setMinimumSize(800, 50)
        # self.title_area.setStyleSheet("""
        #     QScrollBar:horizontal {
        #         height: 4px;
        #         background: #f0f0f0;
        #         border-radius: 10px;
        #     }

        #     QScrollBar::handle:horizontal {
        #         background: #888;
        #         border-radius: 10px;
        #     }

        #     QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        #         background: none;
        #     }

        #     QScrollBar::handle:horizontal:hover {
        #         background: #555;
        #     }
        # """)
        self.setObjectName('settingInterface')
        self.scrollWidget.setObjectName('scrollWidget')
        self.settingLabel.setObjectName('settingLabel')
        StyleSheet.SETTING_INTERFACE.apply(self)

    def __initCard(self):
        self.PowerGroup = SettingCardGroup(self.tr("体力设置"), self.scrollWidget)
        self.instanceTypeCard = ComboBoxSettingCard1(
            "instance_type",
            FIF.ALIGNMENT,
            self.tr('副本类型'),
            None,
            texts=['拟造花萼（金）', '拟造花萼（赤）', '凝滞虚影', '侵蚀隧洞', '饰品提取']
        )
        # self.calyxGoldenPreferenceCard = ComboBoxSettingCard2(
        #     "calyx_golden_preference",
        #     FIF.PIE_SINGLE,
        #     self.tr('拟造花萼（金）偏好地区'),
        #     '',
        #     texts={'雅利洛-VI': 'Jarilo-VI', '仙舟「罗浮」': 'XianzhouLuofu', '匹诺康尼': 'Penacony'}
        # )
        self.instanceNameCard = PushSettingCardInstance(
            self.tr('修改'),
            FIF.PALETTE,
            self.tr("副本名称"),
            "instance_names",
            "./assets/config/instance_names.json"
        )
        self.breakDownLevelFourRelicsetEnableCard = SwitchSettingCard1(
            FIF.FILTER,
            self.tr('自动分解四星遗器'),
            self.tr('侵蚀隧洞、饰品提取、历战余响和模拟宇宙完成后自动分解四星及以下遗器'),
            "break_down_level_four_relicset"
        )
        self.instanceTeamEnableCard = SwitchSettingCardTeam(
            FIF.EDIT,
            self.tr('自动切换队伍'),
            None,
            "instance_team_enable",
            "instance_team_number"
        )
        # self.instanceTeamNumberCard = ComboBoxSettingCard1(
        #     "instance_team_number",
        #     FIF.FLAG,
        #     self.tr('队伍编号'),
        #     None,
        #     texts=['3', '4', '5', '6', '7']
        # )
        self.mergeImmersifierEnableCard = SwitchSettingCardImmersifier(
            FIF.BASKETBALL,
            self.tr('优先合成沉浸器'),
            "达到指定上限后停止，可搭配每天一定次数的模拟宇宙实现循环",
            "merge_immersifier"
        )
        self.useReservedTrailblazePowerEnableCard = SwitchSettingCard1(
            FIF.HEART,
            self.tr('使用后备开拓力'),
            "单次上限300点，全部使用需要将“任务完成后”选项修改为“循环”，然后点击“完整运行”",
            "use_reserved_trailblaze_power"
        )
        self.useFuelEnableCard = SwitchSettingCard1(
            FIF.CAFE,
            self.tr('使用燃料'),
            "单次上限5个，全部使用需要将“任务完成后”选项修改为“循环”，然后点击“完整运行”",
            "use_fuel"
        )
        self.echoofwarEnableCard = SwitchSettingCardEchoofwar(
            FIF.MEGAPHONE,
            self.tr('启用历战余响'),
            "每周体力优先完成三次「历战余响」，支持配置从周几后开始执行，仅限完整运行生效",
            "echo_of_war_enable"
        )
        self.echoofwarRunTimeCard = PushSettingCardDate(
            self.tr('修改'),
            FIF.DATE_TIME,
            self.tr("上次完成历战余响的时间"),
            "echo_of_war_timestamp"
        )
        # self.echoofwarStartDayOfWeekCard = RangeSettingCard1(
        #     "echo_of_war_start_day_of_week",
        #     [1, 7],
        #     FIF.HISTORY,
        #     self.tr("周几开始执行【历战余响】"),
        #     self.tr("假设值为4，那么周1、2、3不执行「历战余响」，周4、5、6、7则执行"),
        # )

        self.BorrowGroup = SettingCardGroup(self.tr("支援设置"), self.scrollWidget)
        self.borrowEnableCard = SwitchSettingCard1(
            FIF.PIN,
            self.tr('启用使用支援角色'),
            '',
            "borrow_enable"
        )
        self.borrowCharacterEnableCard = SwitchSettingCard1(
            FIF.UNPIN,
            self.tr('强制使用支援角色'),
            self.tr('无论何时都要使用支援角色，即使日常实训中没有要求'),
            "borrow_character_enable"
        )
        self.borrowFriendsCard = PushSettingCardFriends(
            self.tr('修改'),
            FIF.FLAG,
            self.tr("支援列表"),
            "borrow_friends"
        )
        self.borrowScrollTimesCard = RangeSettingCard1(
            "borrow_scroll_times",
            [1, 10],
            FIF.HISTORY,
            self.tr("滚动查找次数"),
            '',
        )
        # self.borrowCharacterFromCard = PushSettingCardEval(
        #     self.tr('修改'),
        #     FIF.PEOPLE,
        #     self.tr("指定好友的支援角色（填写用户名，模糊匹配模式）"),
        #     "borrow_character_from"
        # )
        # self.borrowCharacterInfoCard = PrimaryPushSettingCard(
        #     self.tr('打开角色文件夹'),
        #     FIF.INFO,
        #     self.tr("↓↓支援角色↓↓"),
        #     self.tr("角色对应的英文名字可以在 \"March7thAssistant\\assets\\images\\share\\character\" 中查看")
        # )
        # self.borrowCharacterCard = PushSettingCardEval(
        #     self.tr('修改'),
        #     FIF.ARROW_DOWN,
        #     self.tr("支援角色优先级（从高到低）"),
        #     "borrow_character"
        # )

        self.DailyGroup = SettingCardGroup(self.tr("日常设置"), self.scrollWidget)
        self.dispatchEnableCard = SwitchSettingCard1(
            FIF.STOP_WATCH,
            self.tr('领取委托奖励'),
            None,
            "reward_dispatch_enable"
        )
        self.mailEnableCard = SwitchSettingCard1(
            FIF.MAIL,
            self.tr('领取邮件奖励'),
            None,
            "reward_mail_enable"
        )
        self.assistEnableCard = SwitchSettingCard1(
            FIF.BRUSH,
            self.tr('领取支援奖励'),
            None,
            "reward_assist_enable"
        )
        self.dailyEnableCard = SwitchSettingCard1(
            FIF.CALENDAR,
            self.tr('启用每日实训'),
            "关闭后可通过手动配置每天一次模拟宇宙来完成500活跃度（推荐每天四次）",
            "daily_enable"
        )
        self.dailyHimekoTryEnableCard = SwitchSettingCard1(
            FIF.CHECKBOX,
            self.tr('通过 “姬子试用” 完成任务'),
            "",
            "daily_himeko_try_enable"
        )
        self.dailyMemoryOneEnableCard = SwitchSettingCard1(
            FIF.CHECKBOX,
            self.tr('通过 “回忆一” 完成任务'),
            "请解锁混沌回忆并配置了队伍后再打开该选项，部分任务需要反复运行至多三次",
            "daily_memory_one_enable"
        )
        self.dailyMemoryOneTeamCard = PushSettingCardTeam(
            self.tr('修改'),
            FIF.FLAG,
            self.tr("回忆一队伍"),
            "daily_memory_one_team"
        )
        self.lastRunTimeCard = PushSettingCardDate(
            self.tr('修改'),
            FIF.DATE_TIME,
            self.tr("上次检测日常的时间"),
            "last_run_timestamp"
        )

        self.ActivityGroup = SettingCardGroup(self.tr("活动设置"), self.scrollWidget)
        self.activityEnableCard = SwitchSettingCard1(
            FIF.CERTIFICATE,
            self.tr('启用活动检测'),
            None,
            "activity_enable"
        )
        self.activityDailyCheckInEnableCard = SwitchSettingCard1(
            FIF.COMPLETED,
            self.tr('启用每日签到'),
            "自动领取「星轨专票」或「星琼」，包含巡星之礼、巡光之礼和庆典祝礼活动",
            "activity_dailycheckin_enable"
        )
        self.activityGardenOfPlentyEnableCard = SwitchSettingCardGardenofplenty(
            FIF.CALORIES,
            self.tr('启用花藏繁生'),
            "存在双倍次数时体力优先「拟造花萼」",
            "activity_gardenofplenty_enable"
        )
        self.activityRealmOfTheStrangeEnableCard = SwitchSettingCard1(
            FIF.CALORIES,
            self.tr('启用异器盈界'),
            "存在双倍次数时体力优先「侵蚀隧洞」",
            "activity_realmofthestrange_enable"
        )
        self.activityPlanarFissureEnableCard = SwitchSettingCard1(
            FIF.CALORIES,
            self.tr('启用位面分裂'),
            "存在双倍次数时体力优先「饰品提取」",
            "activity_planarfissure_enable"
        )

        self.FightGroup = SettingCardGroup(self.tr("锄大地"), self.scrollWidget)
        self.fightEnableCard = SwitchSettingCard1(
            FIF.BUS,
            self.tr('启用锄大地 (Fhoe-Rail)'),
            "",
            "fight_enable"
        )
        self.fightOperationModeCard = ComboBoxSettingCard2(
            "fight_operation_mode",
            FIF.COMMAND_PROMPT,
            self.tr('运行模式'),
            '',
            texts={'集成': 'exe', '源码': 'source'}
        )
        self.fightTimeoutCard = RangeSettingCard1(
            "fight_timeout",
            [1, 10],
            FIF.HISTORY,
            self.tr("锄大地超时"),
            self.tr("超过设定时间强制停止（单位小时）"),
        )
        self.fightTeamEnableCard = SwitchSettingCardTeam(
            FIF.EDIT,
            self.tr('自动切换队伍'),
            None,
            "fight_team_enable",
            "fight_team_number"
        )
        # self.fightTeamNumberCard = ComboBoxSettingCard1(
        #     "fight_team_number",
        #     FIF.FLAG,
        #     self.tr('队伍编号'),
        #     None,
        #     texts=['3', '4', '5', '6', '7']
        # )
        self.FightRunTimeCard = PushSettingCardDate(
            self.tr('修改'),
            FIF.DATE_TIME,
            self.tr("上次运行锄大地的时间"),
            "fight_timestamp"
        )
        self.fightAllowMapBuyCard = ComboBoxSettingCard2(
            "fight_allow_map_buy",
            FIF.GLOBE,
            self.tr('购买代币与过期邮包'),
            '',
            texts={"不配置": "不配置", "启用": True, "停用": False}
        )
        self.fightAllowSnackBuyCard = ComboBoxSettingCard2(
            "fight_allow_snack_buy",
            FIF.GLOBE,
            self.tr('购买秘技零食并合成零食'),
            '',
            texts={"不配置": "不配置", "启用": True, "停用": False}
        )
        self.fightMainMapCard = ComboBoxSettingCard2(
            "fight_main_map",
            FIF.GLOBE,
            self.tr('优先星球'),
            '',
            texts={"不配置": "0", "空间站": "1", "雅利洛": "2", "仙舟": "3", "匹诺康尼": "4", "翁法罗斯": 5}
        )

        self.UniverseGroup = SettingCardGroup(self.tr("模拟宇宙"), self.scrollWidget)
        self.universeEnableCard = SwitchSettingCard1(
            FIF.VPN,
            self.tr('启用模拟宇宙 (Auto_Simulated_Universe)'),
            "",
            "universe_enable"
        )
        self.universeOperationModeCard = ComboBoxSettingCard2(
            "universe_operation_mode",
            FIF.COMMAND_PROMPT,
            self.tr('运行模式'),
            '',
            texts={'集成': 'exe', '源码': 'source'}
        )
        self.universeCategoryCard = ComboBoxSettingCard2(
            "universe_category",
            FIF.COMMAND_PROMPT,
            self.tr('类别'),
            '',
            texts={'差分宇宙': 'divergent', '模拟宇宙': 'universe'}
        )
        self.universeDisableGpuCard = SwitchSettingCard1(
            FIF.COMMAND_PROMPT,
            self.tr('禁用GPU加速'),
            self.tr('差分宇宙无法正常运行时，可尝试打开此选项'),
            "universe_disable_gpu"
        )
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
        self.weeklyDivergentEnableCard = SwitchSettingCard1(
            FIF.VPN,
            self.tr('每周优先运行一次差分宇宙'),
            "如需执行周期演算，请自行打开 “主页→模拟宇宙→原版运行”，然后勾选“周期演算”",
            "weekly_divergent_enable"
        )
        self.weeklyDivergentRunTimeCard = PushSettingCardDate(
            self.tr('修改'),
            FIF.DATE_TIME,
            self.tr("上次运行每周一次差分宇宙的时间"),
            "weekly_divergent_timestamp"
        )
        self.universeBonusEnableCard = SwitchSettingCard1(
            FIF.IOT,
            self.tr('领取沉浸奖励/执行饰品提取'),
            "类别为“模拟宇宙”时，自动领取沉浸奖励。类别为“差分宇宙”时，在领取积分奖励后自动执行饰品提取消耗沉浸器。",
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
        fates = {}
        for a in ["不配置", "存护", "记忆", "虚无", "丰饶", "巡猎", "毁灭", "欢愉", "繁育", "智识"]:
            fates[a] = a
        self.universeFateCard = ComboBoxSettingCard2(
            "universe_fate",
            FIF.PIE_SINGLE,
            self.tr('命途（仅模拟宇宙生效）'),
            '',
            texts=fates
        )
        self.universeDifficultyCard = RangeSettingCard1(
            "universe_difficulty",
            [0, 5],
            FIF.HISTORY,
            self.tr("难度 (0为不配置，仅模拟宇宙生效)"),
            self.tr(""),
        )

        self.ForgottenhallGroup = SettingCardGroup(self.tr("混沌回忆"), self.scrollWidget)
        self.forgottenhallEnableCard = SwitchSettingCard1(
            FIF.SPEED_HIGH,
            self.tr('启用混沌回忆'),
            "",
            "forgottenhall_enable"
        )
        self.forgottenhallLevelCard = PushSettingCardEval(
            self.tr('修改'),
            FIF.MINIMIZE,
            self.tr("关卡范围"),
            "forgottenhall_level"
        )
        # self.forgottenhallRetriesCard = RangeSettingCard1(
        #     "forgottenhall_retries",
        #     [0, 10],
        #     FIF.REMOVE_FROM,
        #     self.tr("重试次数"),
        # )
        self.forgottenhallTeam1Card = PushSettingCardTeam(
            self.tr('修改'),
            FIF.FLAG,
            self.tr("混沌回忆队伍1"),
            "forgottenhall_team1"
        )
        self.forgottenhallTeam2Card = PushSettingCardTeam(
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

        self.PureFictionGroup = SettingCardGroup(self.tr("虚构叙事"), self.scrollWidget)
        self.purefictionEnableCard = SwitchSettingCard1(
            FIF.SPEED_HIGH,
            self.tr('启用虚构叙事'),
            "",
            "purefiction_enable"
        )
        self.purefictionLevelCard = PushSettingCardEval(
            self.tr('修改'),
            FIF.MINIMIZE,
            self.tr("关卡范围"),
            "purefiction_level"
        )
        self.purefictionTeam1Card = PushSettingCardTeam(
            self.tr('修改'),
            FIF.FLAG,
            self.tr("虚构叙事队伍1"),
            "purefiction_team1"
        )
        self.purefictionTeam2Card = PushSettingCardTeam(
            self.tr('修改'),
            FIF.FLAG,
            self.tr("虚构叙事队伍2"),
            "purefiction_team2"
        )
        self.purefictionRunTimeCard = PushSettingCardDate(
            self.tr('修改'),
            FIF.DATE_TIME,
            self.tr("上次运行虚构叙事的时间"),
            "purefiction_timestamp"
        )

        self.ApocalypticGroup = SettingCardGroup(self.tr("末日"), self.scrollWidget)
        self.ApocalypticEnableCard = SwitchSettingCard1(
            FIF.SPEED_HIGH,
            self.tr('启用末日幻影'),
            "",
            "apocalyptic_enable"
        )
        self.ApocalypticLevelCard = PushSettingCardEval(
            self.tr('修改'),
            FIF.MINIMIZE,
            self.tr("关卡范围"),
            "apocalyptic_level"
        )
        self.ApocalypticTeam1Card = PushSettingCardTeam(
            self.tr('修改'),
            FIF.FLAG,
            self.tr("末日幻影队伍1"),
            "apocalyptic_team1"
        )
        self.ApocalypticTeam2Card = PushSettingCardTeam(
            self.tr('修改'),
            FIF.FLAG,
            self.tr("末日幻影队伍2"),
            "apocalyptic_team2"
        )
        self.ApocalypticRunTimeCard = PushSettingCardDate(
            self.tr('修改'),
            FIF.DATE_TIME,
            self.tr("上次运行末日幻影的时间"),
            "apocalyptic_timestamp"
        )

        self.ProgramGroup = SettingCardGroup(self.tr('程序设置'), self.scrollWidget)
        self.logLevelCard = ComboBoxSettingCardLog(
            "log_level",
            FIF.TAG,
            self.tr('日志等级'),
            "",
            texts={'简洁': 'INFO', '详细': 'DEBUG'}
        )
        self.gamePathCard = PushSettingCard(
            self.tr('修改'),
            FIF.GAME,
            self.tr("游戏路径"),
            cfg.game_path
        )
        # self.importConfigCard = PushSettingCard(
        #     self.tr('导入'),
        #     FIF.ADD_TO,
        #     self.tr('导入配置'),
        #     self.tr('选择需要导入的 config.yaml 文件（重启后生效）')
        # )
        self.checkUpdateCard = SwitchSettingCard1(
            FIF.SYNC,
            self.tr('启动时检测更新'),
            "新版本将更加稳定并拥有更多功能（建议启用）",
            "check_update"
        )
        self.afterFinishCard = ComboBoxSettingCard2(
            "after_finish",
            FIF.POWER_BUTTON,
            self.tr('任务完成后'),
            self.tr('其中“退出”指退出游戏，“循环”指7×24小时无人值守循环运行程序（仅限完整运行生效）'),
            texts={'无': 'None', '退出': 'Exit', '循环': 'Loop',
                   '关机': 'Shutdown', '睡眠': 'Sleep', '休眠': 'Hibernate', '重启': 'Restart', '注销': 'Logoff', '运行脚本': 'RunScript'}
        )
        self.ScriptPathCard = PushSettingCard(
            self.tr('修改'),
            FIF.CODE,
            self.tr("脚本或程序路径(选择运行脚本时生效)"),
            cfg.script_path
        )
        self.loopModeCard = ComboBoxSettingCard2(
            "loop_mode",
            FIF.COMMAND_PROMPT,
            self.tr('循环模式'),
            '',
            texts={'根据开拓力': 'power', '定时任务': 'scheduled'}
        )
        self.scheduledCard = TimePickerSettingCard1(
            "scheduled_time",
            FIF.DATE_TIME,
            "定时任务时间",
        )
        self.playAudioCard = SwitchSettingCard1(
            FIF.ALBUM,
            self.tr('声音提示'),
            self.tr('任务完成后列车长唱歌提示帕！'),
            "play_audio"
        )
        self.powerLimitCard = RangeSettingCard1(
            "power_limit",
            [10, 300],
            FIF.HEART,
            # self.tr("循环运行再次启动所需开拓力（游戏刷新后优先级更高）"),
            self.tr("循环运行再次启动所需开拓力"),
            self.tr("游戏刷新后优先级更高"),
        )
        self.refreshHourEnableCard = RangeSettingCard1(
            "refresh_hour",
            [0, 23],
            FIF.DATE_TIME,
            self.tr("游戏刷新时间"),
            self.tr("用于循环运行及判断任务状态，默认凌晨四点"),
        )

        self.NotifyGroup = SettingCardGroup(self.tr("消息推送"), self.scrollWidget)
        self.testNotifyCard = PrimaryPushSettingCard(
            self.tr('发送消息'),
            FIF.RINGER,
            self.tr("测试消息推送"),
            ""
        )
        self.notifyTemplateCard = PushSettingCardNotifyTemplate(
            self.tr('修改'),
            FIF.FONT_SIZE,
            self.tr("消息推送格式"),
            "notify_template"
        )

        self.notifyEnableGroup = []
        self.notifyLogoDict = {
            "winotify": FIF.BACK_TO_WINDOW,
            "telegram": FIF.AIRPLANE,
            "serverchanturbo": FIF.ROBOT,
            "serverchan3": FIF.ROBOT,
            # "bark": FIF.MAIL,
            "smtp": FIF.MAIL,
            # "dingtalk": FIF.MAIL,
            # "pushplus": FIF.MAIL,
            # "wechatworkapp": FIF.MAIL,
            # "wechatworkbot": FIF.MAIL,
            # "onebot": FIF.MAIL,
            # "gocqhttp": FIF.MAIL,
            # "gotify": FIF.MAIL,
            # "discord": FIF.MAIL,
            # "pushdeer": FIF.MAIL,
            # "lark": FIF.MAIL,
            # "custom": FIF.MAIL
        }
        self.notifySupportImage = ["telegram", "matrix", "smtp", "wechatworkapp", "onebot", "gocqhttp", "lark", "custom"]

        for key, _ in cfg.config.items():
            if key.startswith("notify_") and key.endswith("_enable"):
                notifier_name = key[len("notify_"):-len("_enable")]

                notifyEnableCard = SwitchSettingCardNotify(
                    self.notifyLogoDict[notifier_name] if notifier_name in self.notifyLogoDict else FIF.MAIL,
                    self.tr(f'启用 {notifier_name.capitalize()} 通知 {"（支持图片）"if notifier_name in self.notifySupportImage else ""}'),
                    notifier_name,
                    key
                )
                self.notifyEnableGroup.append(notifyEnableCard)

        self.MiscGroup = SettingCardGroup(self.tr("杂项"), self.scrollWidget)
        self.autoBattleDetectEnableCard = SwitchSettingCard1(
            FIF.ROBOT,
            self.tr('启用自动战斗检测'),
            "只对清体力和逐光捡金场景生效，并在启动游戏前自动检测并修改注册表值",
            "auto_battle_detect_enable"
        )
        self.autoSetResolutionEnableCard = SwitchSettingCard1(
            FIF.FULL_SCREEN,
            self.tr('启用自动修改分辨率并关闭自动 HDR'),
            "通过软件启动游戏会自动修改 1920x1080 分辨率并关闭自动 HDR，不影响手动启动游戏（未测试国际服）",
            "auto_set_resolution_enable"
        )
        self.autoSetGamePathEnableCard = SwitchSettingCard1(
            FIF.GAME,
            self.tr('启用自动配置游戏路径'),
            "通过快捷方式、官方启动器、运行中的游戏进程等方式尝试自动配置游戏路径（未测试国际服）",
            "auto_set_game_path_enable"
        )
        self.allScreensCard = SwitchSettingCard1(
            FIF.ZOOM,
            self.tr('在多显示器上进行截屏'),
            "默认开启，如果正在使用多显示器且无法正常截屏请关闭此选项重试",
            "all_screens"
        )
        self.StartMarch7thAssistantCard = StartMarch7thAssistantSwitchSettingCard(
            FIF.GAME,
            self.tr('在用户登录时启动'),
            "用于开机后自动执行完整运行模式"
        )
        self.keybindingTechniqueCard = PushSettingCardKey(
            self.tr('按住以修改'),
            FIF.LEAF,
            self.tr("秘技（只对清体力和逐光捡金场景生效）"),
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
            self.tr('当前版本：') + " " + cfg.version
        )
        self.updateSourceCard = ComboBoxSettingCard2(
            "update_source",
            FIF.SPEED_HIGH,
            '更新源',
            self.parent,
            '',
            texts={'海外源': 'GitHub', 'Mirror 酱': 'MirrorChyan'}
        )
        self.mirrorchyanCdkCard = PushSettingCardMirrorchyan(
            self.tr('修改'),
            FIF.BOOK_SHELF,
            self.tr("Mirror 酱 CDK"),
            self.parent,
            "mirrorchyan_cdk"
        )
        self.updatePrereleaseEnableCard = SwitchSettingCard1(
            FIF.TRAIN,
            self.tr('加入预览版更新渠道（预览版暂不支持Mirror酱）'),
            "",
            "update_prerelease_enable"
        )
        self.updateFullEnableCard = SwitchSettingCard1(
            FIF.GLOBE,
            self.tr('更新时下载完整包（非完整包暂不支持Mirror酱）'),
            "包含模拟宇宙和锄大地等，但压缩包体积更大",
            "update_full_enable"
        )

    def __initLayout(self):
        self.settingLabel.move(36, 30)
        self.pivot.move(40, 80)
        # self.title_area.move(36, 80)
        # self.vBoxLayout.addWidget(self.pivot, 0, Qt.AlignTop)
        self.vBoxLayout.addWidget(self.stackedWidget, 0, Qt.AlignTop)
        self.vBoxLayout.setContentsMargins(36, 0, 36, 0)

        self.PowerGroup.addSettingCard(self.instanceTypeCard)
        # self.PowerGroup.addSettingCard(self.calyxGoldenPreferenceCard)
        self.PowerGroup.addSettingCard(self.instanceNameCard)
        self.PowerGroup.addSettingCard(self.breakDownLevelFourRelicsetEnableCard)
        self.PowerGroup.addSettingCard(self.instanceTeamEnableCard)
        # self.PowerGroup.addSettingCard(self.instanceTeamNumberCard)
        self.PowerGroup.addSettingCard(self.mergeImmersifierEnableCard)
        self.PowerGroup.addSettingCard(self.useReservedTrailblazePowerEnableCard)
        self.PowerGroup.addSettingCard(self.useFuelEnableCard)
        self.PowerGroup.addSettingCard(self.echoofwarEnableCard)
        self.PowerGroup.addSettingCard(self.echoofwarRunTimeCard)
        # self.PowerGroup.addSettingCard(self.echoofwarStartDayOfWeekCard)

        self.BorrowGroup.addSettingCard(self.borrowEnableCard)
        self.BorrowGroup.addSettingCard(self.borrowCharacterEnableCard)
        self.BorrowGroup.addSettingCard(self.borrowFriendsCard)
        self.BorrowGroup.addSettingCard(self.borrowScrollTimesCard)
        # self.BorrowGroup.addSettingCard(self.borrowCharacterFromCard)
        # self.BorrowGroup.addSettingCard(self.borrowCharacterInfoCard)
        # self.BorrowGroup.addSettingCard(self.borrowCharacterCard)

        self.DailyGroup.addSettingCard(self.dispatchEnableCard)
        self.DailyGroup.addSettingCard(self.mailEnableCard)
        self.DailyGroup.addSettingCard(self.assistEnableCard)
        self.DailyGroup.addSettingCard(self.dailyEnableCard)
        self.DailyGroup.addSettingCard(self.dailyHimekoTryEnableCard)
        self.DailyGroup.addSettingCard(self.dailyMemoryOneEnableCard)
        self.DailyGroup.addSettingCard(self.dailyMemoryOneTeamCard)
        self.DailyGroup.addSettingCard(self.lastRunTimeCard)

        self.ActivityGroup.addSettingCard(self.activityEnableCard)
        self.ActivityGroup.addSettingCard(self.activityDailyCheckInEnableCard)
        self.ActivityGroup.addSettingCard(self.activityGardenOfPlentyEnableCard)
        self.ActivityGroup.addSettingCard(self.activityRealmOfTheStrangeEnableCard)
        self.ActivityGroup.addSettingCard(self.activityPlanarFissureEnableCard)

        self.FightGroup.addSettingCard(self.fightEnableCard)
        self.FightGroup.addSettingCard(self.fightOperationModeCard)
        self.FightGroup.addSettingCard(self.fightTimeoutCard)
        self.FightGroup.addSettingCard(self.fightTeamEnableCard)
        # self.FightGroup.addSettingCard(self.fightTeamNumberCard)
        self.FightGroup.addSettingCard(self.FightRunTimeCard)
        self.FightGroup.addSettingCard(self.fightAllowMapBuyCard)
        self.FightGroup.addSettingCard(self.fightAllowSnackBuyCard)
        self.FightGroup.addSettingCard(self.fightMainMapCard)

        self.UniverseGroup.addSettingCard(self.universeEnableCard)
        self.UniverseGroup.addSettingCard(self.universeOperationModeCard)
        self.UniverseGroup.addSettingCard(self.universeCategoryCard)
        self.UniverseGroup.addSettingCard(self.universeDisableGpuCard)
        self.UniverseGroup.addSettingCard(self.universeTimeoutCard)
        self.UniverseGroup.addSettingCard(self.universeBonusEnableCard)
        self.UniverseGroup.addSettingCard(self.universeFrequencyCard)
        self.UniverseGroup.addSettingCard(self.universeCountCard)
        self.UniverseGroup.addSettingCard(self.universeRunTimeCard)
        self.UniverseGroup.addSettingCard(self.weeklyDivergentEnableCard)
        self.UniverseGroup.addSettingCard(self.weeklyDivergentRunTimeCard)
        self.UniverseGroup.addSettingCard(self.universeFateCard)
        self.UniverseGroup.addSettingCard(self.universeDifficultyCard)

        self.ForgottenhallGroup.addSettingCard(self.forgottenhallEnableCard)
        self.ForgottenhallGroup.addSettingCard(self.forgottenhallLevelCard)
        # self.ForgottenhallGroup.addSettingCard(self.forgottenhallRetriesCard)
        self.ForgottenhallGroup.addSettingCard(self.forgottenhallTeam1Card)
        self.ForgottenhallGroup.addSettingCard(self.forgottenhallTeam2Card)
        self.ForgottenhallGroup.addSettingCard(self.forgottenhallRunTimeCard)

        self.PureFictionGroup.addSettingCard(self.purefictionEnableCard)
        self.PureFictionGroup.addSettingCard(self.purefictionLevelCard)
        self.PureFictionGroup.addSettingCard(self.purefictionTeam1Card)
        self.PureFictionGroup.addSettingCard(self.purefictionTeam2Card)
        self.PureFictionGroup.addSettingCard(self.purefictionRunTimeCard)

        self.ApocalypticGroup.addSettingCard(self.ApocalypticEnableCard)
        self.ApocalypticGroup.addSettingCard(self.ApocalypticLevelCard)
        self.ApocalypticGroup.addSettingCard(self.ApocalypticTeam1Card)
        self.ApocalypticGroup.addSettingCard(self.ApocalypticTeam2Card)
        self.ApocalypticGroup.addSettingCard(self.ApocalypticRunTimeCard)

        self.ProgramGroup.addSettingCard(self.logLevelCard)
        self.ProgramGroup.addSettingCard(self.gamePathCard)
        # self.ProgramGroup.addSettingCard(self.importConfigCard)
        self.ProgramGroup.addSettingCard(self.checkUpdateCard)
        self.ProgramGroup.addSettingCard(self.afterFinishCard)
        self.ProgramGroup.addSettingCard(self.ScriptPathCard)
        self.ProgramGroup.addSettingCard(self.loopModeCard)
        self.ProgramGroup.addSettingCard(self.scheduledCard)
        self.ProgramGroup.addSettingCard(self.playAudioCard)
        self.ProgramGroup.addSettingCard(self.powerLimitCard)
        self.ProgramGroup.addSettingCard(self.refreshHourEnableCard)

        self.NotifyGroup.addSettingCard(self.testNotifyCard)
        self.NotifyGroup.addSettingCard(self.notifyTemplateCard)
        for value in self.notifyEnableGroup:
            self.NotifyGroup.addSettingCard(value)

        self.MiscGroup.addSettingCard(self.autoBattleDetectEnableCard)
        self.MiscGroup.addSettingCard(self.autoSetResolutionEnableCard)
        self.MiscGroup.addSettingCard(self.autoSetGamePathEnableCard)
        self.MiscGroup.addSettingCard(self.allScreensCard)
        self.MiscGroup.addSettingCard(self.StartMarch7thAssistantCard)
        self.MiscGroup.addSettingCard(self.keybindingTechniqueCard)

        self.AboutGroup.addSettingCard(self.githubCard)
        self.AboutGroup.addSettingCard(self.qqGroupCard)
        self.AboutGroup.addSettingCard(self.feedbackCard)
        self.AboutGroup.addSettingCard(self.aboutCard)
        self.AboutGroup.addSettingCard(self.updateSourceCard)
        self.AboutGroup.addSettingCard(self.mirrorchyanCdkCard)
        self.AboutGroup.addSettingCard(self.updatePrereleaseEnableCard)
        self.AboutGroup.addSettingCard(self.updateFullEnableCard)

        self.addSubInterface(self.PowerGroup, 'PowerInterface', self.tr('体力'))
        self.addSubInterface(self.BorrowGroup, 'BorrowInterface', self.tr('支援'))
        self.addSubInterface(self.DailyGroup, 'DailyInterface', self.tr('日常'))
        self.addSubInterface(self.ActivityGroup, 'ActivityInterface', self.tr('活动'))
        self.addSubInterface(self.FightGroup, 'FightInterface', self.tr('锄大地'))
        self.addSubInterface(self.UniverseGroup, 'UniverseInterface', self.tr('宇宙'))
        self.addSubInterface(self.ForgottenhallGroup, 'ForgottenhallInterface', self.tr('混沌'))
        self.addSubInterface(self.PureFictionGroup, 'PureFictionInterface', self.tr('虚构'))
        self.addSubInterface(self.ApocalypticGroup, 'ApocalypticInterface', self.tr('末日'))

        self.pivot.addItem(
            routeKey='verticalBar',
            text="|",
            onClick=lambda: self.pivot.setCurrentItem(self.stackedWidget.currentWidget().objectName()),
        )

        self.addSubInterface(self.ProgramGroup, 'programInterface', self.tr('程序'))
        self.addSubInterface(self.NotifyGroup, 'NotifyInterface', self.tr('推送'))
        self.addSubInterface(self.MiscGroup, 'KeybindingInterface', self.tr('杂项'))
        self.addSubInterface(
            accounts_interface(self.tr, self.scrollWidget),
            'AccountsInterface',
            self.tr('账号')
        )
        self.addSubInterface(self.AboutGroup, 'AboutInterface', self.tr('关于'))

        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.pivot.setCurrentItem(self.stackedWidget.currentWidget().objectName())
        self.stackedWidget.setFixedHeight(self.stackedWidget.currentWidget().sizeHint().height())

    def __connectSignalToSlot(self):
        # self.importConfigCard.clicked.connect(self.__onImportConfigCardClicked)
        self.gamePathCard.clicked.connect(self.__onGamePathCardClicked)
        self.ScriptPathCard.clicked.connect(self.__onScriptPathCardClicked)
        # self.borrowCharacterInfoCard.clicked.connect(self.__openCharacterFolder())

        self.testNotifyCard.clicked.connect(lambda: start_task("notify"))

        self.githubCard.clicked.connect(self.__openUrl("https://github.com/moesnow/March7thAssistant"))
        self.qqGroupCard.clicked.connect(self.__openUrl("https://qm.qq.com/q/9gFqUrUGVq"))
        self.feedbackCard.clicked.connect(self.__openUrl("https://github.com/moesnow/March7thAssistant/issues"))

        self.aboutCard.clicked.connect(lambda: checkUpdate(self.parent))

    def addSubInterface(self, widget: QLabel, objectName, text):
        def remove_spacing(layout):
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if isinstance(item, QSpacerItem):
                    layout.removeItem(item)
                    break

        remove_spacing(widget.vBoxLayout)
        widget.titleLabel.setHidden(True)

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

        self.verticalScrollBar().setValue(0)
        self.stackedWidget.setFixedHeight(self.stackedWidget.currentWidget().sizeHint().height())

    # def __onImportConfigCardClicked(self):
    #     configdir, _ = QFileDialog.getOpenFileName(self, "选取配置文件", "./", "Config Files (*.yaml)")
    #     if (configdir != ""):
    #         cfg._load_config(configdir)
    #         cfg.save_config()
    #         self.__showRestartTooltip()

    def __onGamePathCardClicked(self):
        game_path, _ = QFileDialog.getOpenFileName(self, "选择游戏路径", "", "All Files (*)")
        if not game_path or cfg.game_path == game_path:
            return
        cfg.set_value("game_path", game_path)
        self.gamePathCard.setContent(game_path)

    # def __openCharacterFolder(self):
    #     return lambda: os.startfile(os.path.abspath("./assets/images/share/character"))

    def __openUrl(self, url):
        return lambda: QDesktopServices.openUrl(QUrl(url))

    # def __showRestartTooltip(self):
    #     InfoBar.success(
    #         self.tr('更新成功'),
    #         self.tr('配置在重启软件后生效'),
    #         duration=1500,
    #         parent=self
    #     )
    def __onScriptPathCardClicked(self):
        script_path, _ = QFileDialog.getOpenFileName(self, "脚本或程序路径", "", "脚本或可执行文件 (*.ps1 *.bat *.exe)")
        if not script_path or cfg.script_path == script_path:
            return
        cfg.set_value("script_path", script_path)
        self.ScriptPathCard.setContent(script_path)
