from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget, QLabel, QFileDialog, QVBoxLayout, QStackedWidget, QSpacerItem, QScroller, QScrollerProperties
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import SettingCardGroup, PushSettingCard, ScrollArea, InfoBar, PrimaryPushSettingCard
from app.sub_interfaces.accounts_interface import accounts_interface
from .common.style_sheet import StyleSheet
from .components.pivot import SettingPivot
from .card.comboboxsettingcard1 import ComboBoxSettingCard1
from .card.comboboxsettingcard2 import ComboBoxSettingCard2, ComboBoxSettingCardUpdateSource, ComboBoxSettingCardLog
from .card.switchsettingcard1 import SwitchSettingCard1, SwitchSettingCardNotify, StartMarch7thAssistantSwitchSettingCard, SwitchSettingCardTeam, SwitchSettingCardImmersifier, SwitchSettingCardGardenofplenty, SwitchSettingCardEchoofwar, SwitchSettingCardHotkey, SwitchSettingCardCloudGameStatus
from .card.rangesettingcard1 import RangeSettingCard1
from .card.pushsettingcard1 import PushSettingCardInstance, PushSettingCardInstanceChallengeCount, PushSettingCardNotifyTemplate, PushSettingCardMirrorchyan, PushSettingCardEval, PushSettingCardDate, PushSettingCardKey, PushSettingCardTeam, PushSettingCardFriends, PushSettingCardTeamWithSwap, PushSettingCardPowerPlan
from .card.timepickersettingcard1 import TimePickerSettingCard1
from .card.expandable_switch_setting_card import ExpandableSwitchSettingCard, ExpandableComboBoxSettingCardUpdateSource, ExpandablePushSettingCard, ExpandableComboBoxSettingCard, ExpandableComboBoxSettingCard1, ExpandableSwitchSettingCardEchoofwar
from module.config import cfg
from module.notification import notif
from tasks.base.tasks import start_task
from .tools.check_update import checkUpdate
import os
import sys


class SettingInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.scrollWidget = QWidget()
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)

        # self.title_area = QScrollArea(self)
        self.pivot = SettingPivot(self)
        self.stackedWidget = QStackedWidget(self)

        self.settingLabel = QLabel("设置", self)

        self.__initWidget()
        self.__initCard()
        self.__initLayout()
        self.__connectSignalToSlot()

    def __initWidget(self):
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setViewportMargins(0, 140, 0, 5)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

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

        QScroller.grabGesture(self.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)
        scroller = QScroller.scroller(self.viewport())
        scroller_props = scroller.scrollerProperties()
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootDragDistanceFactor, 0.05)
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootScrollDistanceFactor, 0.05)
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.DecelerationFactor, 0.5)
        scroller.setScrollerProperties(scroller_props)

    def __initCard(self):
        self.PowerGroup = SettingCardGroup("体力设置", self.scrollWidget)
        self.powerPlanCard = PushSettingCardPowerPlan(
            '配置',
            FIF.CALENDAR,
            "体力计划",
            "power_plan",
            "./assets/config/instance_names.json"
        )
        self.instanceTypeCard = ExpandableComboBoxSettingCard1(
            "instance_type",
            FIF.ALIGNMENT,
            '副本类型',
            None,
            texts=['拟造花萼（金）', '拟造花萼（赤）', '凝滞虚影', '侵蚀隧洞', '饰品提取']
        )
        # self.calyxGoldenPreferenceCard = ComboBoxSettingCard2(
        #     "calyx_golden_preference",
        #     FIF.PIE_SINGLE,
        #     '拟造花萼（金）偏好地区',
        #     '',
        #     texts={'雅利洛-VI': 'Jarilo-VI', '仙舟「罗浮」': 'XianzhouLuofu', '匹诺康尼': 'Penacony'}
        # )
        self.instanceNameCard = PushSettingCardInstance(
            '修改',
            FIF.PALETTE,
            "副本名称",
            "instance_names",
            "./assets/config/instance_names.json"
        )
        # self.maxCalyxPerRoundNumOfAttempts = RangeSettingCard1(
        #     "max_calyx_per_round_num_of_attempts",
        #     [1, 6],
        #     FIF.HISTORY,
        #     "每轮拟造花萼挑战次数",
        #     '',
        # )
        self.instanceTeamEnableCard = SwitchSettingCardTeam(
            FIF.EDIT,
            '自动切换队伍',
            None,
            "instance_team_enable",
            "instance_team_number"
        )
        self.tpBeforeInstanceEnableCard = SwitchSettingCard1(
            FIF.LEAF,
            '清体力前传送至任意锚点',
            "",
            "tp_before_instance"
        )
        # self.instanceTeamNumberCard = ComboBoxSettingCard1(
        #     "instance_team_number",
        #     FIF.FLAG,
        #     '队伍编号',
        #     None,
        #     texts=['3', '4', '5', '6', '7']
        # )
        self.useReservedTrailblazePowerEnableCard = SwitchSettingCard1(
            FIF.HEART,
            '使用后备开拓力',
            "单次上限300点，全部使用需要将“任务完成后”选项修改为“循环”，然后点击“完整运行”",
            "use_reserved_trailblaze_power"
        )
        self.useFuelEnableCard = SwitchSettingCard1(
            FIF.CAFE,
            '使用燃料',
            "单次上限5个，全部使用需要将“任务完成后”选项修改为“循环”，然后点击“完整运行”",
            "use_fuel"
        )
        self.breakDownLevelFourRelicsetEnableCard = SwitchSettingCard1(
            FIF.FILTER,
            '自动分解四星遗器（建议在游戏内配置结算遗器时自动分解）',
            '侵蚀隧洞、饰品提取、历战余响和模拟宇宙完成后自动分解四星及以下遗器',
            "break_down_level_four_relicset"
        )
        self.mergeImmersifierEnableCard = SwitchSettingCardImmersifier(
            FIF.BASKETBALL,
            '体力优先合成沉浸器（建议直接通过饰品提取获取位面饰品）',
            "达到指定上限后停止",
            "merge_immersifier"
        )
        self.instanceNameChallengeCountCard = PushSettingCardInstanceChallengeCount(
            '修改',
            FIF.HISTORY,
            "副本最大连续挑战次数（通常不建议修改保持默认即可）",
            "instance_names_challenge_count"
        )
        self.borrowEnableCard = ExpandableSwitchSettingCard(
            "borrow_enable",
            FIF.PIN,
            '启用使用支援角色',
            ''
        )
        self.borrowCharacterEnableCard = SwitchSettingCard1(
            FIF.UNPIN,
            '强制使用支援角色',
            '无论何时都要使用支援角色，即使日常实训中的要求已经完成',
            "borrow_character_enable"
        )
        self.borrowFriendsCard = PushSettingCardFriends(
            '修改',
            FIF.FLAG,
            "支援列表",
            "borrow_friends"
        )
        self.borrowScrollTimesCard = RangeSettingCard1(
            "borrow_scroll_times",
            [1, 10],
            FIF.HISTORY,
            "滚动查找次数",
            '',
        )
        self.buildTargetEnableCard = ExpandableSwitchSettingCard(
            "build_target_enable",
            FIF.LEAF,
            '启用培养目标',
            "根据培养目标刷取行迹与遗器副本，如果无法获取培养目标则回退到默认的副本设置"
        )
        self.buildTargetPlanarOrnamentWeeklyCountCard = RangeSettingCard1(
            "build_target_ornament_weekly_count",
            [0, 7],
            FIF.CALENDAR,
            '每周饰品提取次数',
            '目标有足够资源后，执行饰品提取的次数，其余时间执行侵蚀隧洞',
        )
        self.echoofwarEnableCard = ExpandableSwitchSettingCardEchoofwar(
            "echo_of_war_enable",
            FIF.MEGAPHONE,
            '启用历战余响',
            "每周体力优先完成三次「历战余响」，支持配置从周几后开始执行，仅限完整运行生效",
        )
        self.echoofwarRunTimeCard = PushSettingCardDate(
            '修改',
            FIF.DATE_TIME,
            "上次完成历战余响的时间",
            "echo_of_war_timestamp"
        )
        # self.echoofwarStartDayOfWeekCard = RangeSettingCard1(
        #     "echo_of_war_start_day_of_week",
        #     [1, 7],
        #     FIF.HISTORY,
        #     "周几开始执行【历战余响】",
        #     "假设值为4，那么周1、2、3不执行「历战余响」，周4、5、6、7则执行",
        # )
        # self.borrowCharacterFromCard = PushSettingCardEval(
        #     '修改',
        #     FIF.PEOPLE,
        #     "指定好友的支援角色（填写用户名，模糊匹配模式）",
        #     "borrow_character_from"
        # )
        # self.borrowCharacterInfoCard = PrimaryPushSettingCard(
        #     '打开角色文件夹',
        #     FIF.INFO,
        #     "↓↓支援角色↓↓",
        #     "角色对应的英文名字可以在 \"March7thAssistant\\assets\\images\\share\\character\" 中查看"
        # )
        # self.borrowCharacterCard = PushSettingCardEval(
        #     '修改',
        #     FIF.ARROW_DOWN,
        #     "支援角色优先级（从高到低）",
        #     "borrow_character"
        # )

        self.DailyGroup = SettingCardGroup("日常设置", self.scrollWidget)
        self.dailyEnableCard = ExpandableSwitchSettingCard(
            "daily_enable",
            FIF.CALENDAR,
            '启用每日实训',
            ""
        )
        self.dailyMaterialEnableCard = SwitchSettingCard1(
            FIF.CHECKBOX,
            '通过 “合成材料” 完成任务',
            "请确保背包中有足够的 “熄灭原核” 用于合成 “微光原核” ",
            "daily_material_enable"
        )
        # self.dailyHimekoTryEnableCard = SwitchSettingCard1(
        #     FIF.CHECKBOX,
        #     '通过 “姬子试用” 完成任务',
        #     "",
        #     "daily_himeko_try_enable"
        # )
        self.dailyMemoryOneEnableCard = SwitchSettingCard1(
            FIF.CHECKBOX,
            '通过 “回忆一” 完成任务',
            "请解锁混沌回忆并配置了队伍后再打开该选项",
            "daily_memory_one_enable"
        )
        self.dailyMemoryOneTeamCard = PushSettingCardTeam(
            '修改',
            FIF.FLAG,
            "回忆一队伍",
            "daily_memory_one_team"
        )
        self.lastRunTimeCard = PushSettingCardDate(
            '修改',
            FIF.DATE_TIME,
            "上次检测到完成日常的时间",
            "last_run_timestamp"
        )
        self.activityEnableCard = ExpandableSwitchSettingCard(
            "activity_enable",
            FIF.CERTIFICATE,
            '启用活动检测',
            None
        )
        self.activityDailyCheckInEnableCard = SwitchSettingCard1(
            FIF.COMPLETED,
            '每日签到',
            "自动领取「星轨专票」或「星琼」，包含巡星之礼、巡光之礼和庆典祝礼活动",
            "activity_dailycheckin_enable"
        )
        self.activityGardenOfPlentyEnableCard = SwitchSettingCardGardenofplenty(
            FIF.CALORIES,
            '花藏繁生',
            "存在双倍次数时体力优先「拟造花萼」",
            "activity_gardenofplenty_enable"
        )
        self.activityRealmOfTheStrangeEnableCard = SwitchSettingCard1(
            FIF.CALORIES,
            '异器盈界',
            "存在双倍次数时体力优先「侵蚀隧洞」",
            "activity_realmofthestrange_enable"
        )
        self.activityPlanarFissureEnableCard = SwitchSettingCard1(
            FIF.CALORIES,
            '位面分裂',
            "存在双倍次数时体力优先「饰品提取」",
            "activity_planarfissure_enable"
        )
        self.rewardEnableCard = ExpandableSwitchSettingCard(
            "reward_enable",
            FIF.TRANSPARENT,
            '启用奖励领取',
            ""
        )
        self.dispatchEnableCard = SwitchSettingCard1(
            FIF.STOP_WATCH,
            '委托',
            None,
            "reward_dispatch_enable"
        )
        self.mailEnableCard = SwitchSettingCard1(
            FIF.MAIL,
            '邮件',
            None,
            "reward_mail_enable"
        )
        self.assistEnableCard = SwitchSettingCard1(
            FIF.BRUSH,
            '支援',
            None,
            "reward_assist_enable"
        )
        self.questEnableCard = SwitchSettingCard1(
            FIF.STOP_WATCH,
            '每日实训',
            None,
            "reward_quest_enable"
        )
        self.srpassEnableCard = SwitchSettingCard1(
            FIF.QUIET_HOURS,
            '无名勋礼',
            None,
            "reward_srpass_enable"
        )
        self.achievementEnableCard = SwitchSettingCard1(
            FIF.CERTIFICATE,
            '成就',
            None,
            "reward_achievement_enable"
        )

        # 兑换码奖励开关
        self.redemptionEnableCard = SwitchSettingCard1(
            FIF.BOOK_SHELF,
            '兑换码',
            None,
            "reward_redemption_code_enable"
        )

        self.CurrencywarsGroup = SettingCardGroup("货币", self.scrollWidget)
        self.currencywarsEnableCard = SwitchSettingCard1(
            FIF.DICTIONARY,
            '启用「货币战争」积分奖励',
            "",
            "currencywars_enable"
        )
        self.currencywarsTypeCard = ComboBoxSettingCard2(
            "currencywars_type",
            FIF.COMMAND_PROMPT,
            '类别',
            '',
            texts={'标准博弈': 'normal', '超频博弈': 'overclock'}
        )
        self.currencywarsRunTimeCard = PushSettingCardDate(
            '修改',
            FIF.DATE_TIME,
            "上次检测到完成货币战争积分奖励的时间",
            "currencywars_timestamp"
        )

        self.UniverseGroup = SettingCardGroup("模拟宇宙", self.scrollWidget)
        self.weeklyDivergentEnableCard = ExpandableSwitchSettingCard(
            "weekly_divergent_enable",
            FIF.VPN,
            '启用「差分宇宙」积分奖励',
            ""
        )
        self.weeklyDivergentTypeCard = ComboBoxSettingCard2(
            "weekly_divergent_type",
            FIF.COMMAND_PROMPT,
            '类别',
            '',
            texts={'常规演算': 'normal', '周期演算': 'cycle'}
        )
        self.weeklyDivergentRunTimeCard = PushSettingCardDate(
            '修改',
            FIF.DATE_TIME,
            "上次检测到完成差分宇宙积分奖励的时间",
            "weekly_divergent_timestamp"
        )
        self.universeEnableCard = ExpandableSwitchSettingCard(
            "universe_enable",
            FIF.VPN,
            '启用模拟宇宙/差分宇宙 (Auto_Simulated_Universe)',
            "通常用于反复刷取遗器经验和灵之珠泪（代替敌方掉落素材）直到每周上限"
        )
        self.universeOperationModeCard = ComboBoxSettingCard2(
            "universe_operation_mode",
            FIF.COMMAND_PROMPT,
            '运行模式',
            '',
            texts={'集成': 'exe', '源码': 'source'}
        )
        self.universeCategoryCard = ComboBoxSettingCard2(
            "universe_category",
            FIF.COMMAND_PROMPT,
            '类别',
            '',
            texts={'差分宇宙': 'divergent', '模拟宇宙': 'universe'}
        )
        self.divergentTypeCard = ComboBoxSettingCard2(
            "divergent_type",
            FIF.COMMAND_PROMPT,
            '选择差分宇宙时类别',
            '',
            texts={'常规演算': 'normal', '周期演算': 'cycle'}
        )
        self.universeDisableGpuCard = SwitchSettingCard1(
            FIF.COMMAND_PROMPT,
            '禁用GPU加速',
            '差分宇宙无法正常运行时，可尝试打开此选项',
            "universe_disable_gpu"
        )
        self.universeTimeoutCard = RangeSettingCard1(
            "universe_timeout",
            [1, 24],
            FIF.HISTORY,
            "模拟宇宙/差分宇宙超时",
            "超过设定时间强制停止（单位小时）",
        )
        self.universeRunTimeCard = PushSettingCardDate(
            '修改',
            FIF.DATE_TIME,
            "上次运行模拟宇宙/差分宇宙的时间",
            "universe_timestamp"
        )
        self.universeBonusEnableCard = SwitchSettingCard1(
            FIF.IOT,
            '自动执行饰品提取/领取沉浸奖励',
            "类别为“差分宇宙”时，在领取积分奖励后自动执行饰品提取消耗沉浸器。类别为“模拟宇宙”时，自动领取沉浸奖励。",
            "universe_bonus_enable"
        )
        self.universeFrequencyCard = ComboBoxSettingCard2(
            "universe_frequency",
            FIF.MINIMIZE,
            '运行频率',
            '',
            texts={'每周': 'weekly', '每天': 'daily'}
        )
        self.universeCountCard = RangeSettingCard1(
            "universe_count",
            [0, 34],
            FIF.HISTORY,
            "运行次数",
            "注意中途停止不会计数，0 代表不指定，使用模拟宇宙原版逻辑",
        )
        self.divergentTeamTypeCard = ComboBoxSettingCard2(
            "divergent_team_type",
            FIF.FLAG,
            '差分宇宙队伍类型',
            '',
            texts={'追击': '追击', 'dot': 'dot', '终结技': '终结技', '击破': '击破', '盾反': '盾反'}
        )
        fates = {}
        for a in ["不配置", "存护", "记忆", "虚无", "丰饶", "巡猎", "毁灭", "欢愉", "繁育", "智识"]:
            fates[a] = a
        self.universeFateCard = ComboBoxSettingCard2(
            "universe_fate",
            FIF.PIE_SINGLE,
            '命途（仅模拟宇宙生效）',
            '',
            texts=fates
        )
        self.universeDifficultyCard = RangeSettingCard1(
            "universe_difficulty",
            [0, 5],
            FIF.HISTORY,
            "难度 (0为不配置，仅模拟宇宙生效)",
            "",
        )

        self.FightGroup = SettingCardGroup("锄地", self.scrollWidget)
        self.fightEnableCard = ExpandableSwitchSettingCard(
            "fight_enable",
            FIF.BUS,
            '启用锄大地 (Fhoe-Rail)',
            ""
        )
        self.fightOperationModeCard = ComboBoxSettingCard2(
            "fight_operation_mode",
            FIF.COMMAND_PROMPT,
            '运行模式',
            '',
            texts={'集成': 'exe', '源码': 'source'}
        )
        self.fightTimeoutCard = RangeSettingCard1(
            "fight_timeout",
            [1, 24],
            FIF.HISTORY,
            "锄大地超时",
            "超过设定时间强制停止（单位小时）",
        )
        self.fightTeamEnableCard = SwitchSettingCardTeam(
            FIF.EDIT,
            '自动切换队伍',
            None,
            "fight_team_enable",
            "fight_team_number"
        )
        # self.fightTeamNumberCard = ComboBoxSettingCard1(
        #     "fight_team_number",
        #     FIF.FLAG,
        #     '队伍编号',
        #     None,
        #     texts=['3', '4', '5', '6', '7']
        # )
        self.FightRunTimeCard = PushSettingCardDate(
            '修改',
            FIF.DATE_TIME,
            "上次运行锄大地的时间",
            "fight_timestamp"
        )
        self.fightAllowMapBuyCard = ComboBoxSettingCard2(
            "fight_allow_map_buy",
            FIF.GLOBE,
            '购买代币与过期邮包',
            '',
            texts={"不配置": "不配置", "启用": True, "停用": False}
        )
        self.fightAllowSnackBuyCard = ComboBoxSettingCard2(
            "fight_allow_snack_buy",
            FIF.GLOBE,
            '购买秘技零食并合成零食',
            '',
            texts={"不配置": "不配置", "启用": True, "停用": False}
        )
        self.fightMainMapCard = ComboBoxSettingCard2(
            "fight_main_map",
            FIF.GLOBE,
            '优先星球',
            '',
            texts={"不配置": "0", "空间站": "1", "雅利洛": "2", "仙舟": "3", "匹诺康尼": "4", "翁法罗斯": 5}
        )

        self.ImmortalGameGroup = SettingCardGroup("逐光捡金", self.scrollWidget)
        self.forgottenhallEnableCard = ExpandableSwitchSettingCard(
            "forgottenhall_enable",
            FIF.SPEED_HIGH,
            '启用混沌回忆',
            ""
        )
        self.forgottenhallLevelCard = PushSettingCardEval(
            '修改',
            FIF.MINIMIZE,
            "关卡范围",
            "forgottenhall_level"
        )
        # self.forgottenhallRetriesCard = RangeSettingCard1(
        #     "forgottenhall_retries",
        #     [0, 10],
        #     FIF.REMOVE_FROM,
        #     "重试次数",
        # )
        self.forgottenhallTeamsCard = PushSettingCardTeamWithSwap(
            FIF.FLAG,
            "混沌回忆队伍配置",
            "forgottenhall_team1",
            "forgottenhall_team2"
        )
        self.forgottenhallRunTimeCard = PushSettingCardDate(
            '修改',
            FIF.DATE_TIME,
            "上次运行混沌回忆的时间",
            "forgottenhall_timestamp"
        )

        self.purefictionEnableCard = ExpandableSwitchSettingCard(
            "purefiction_enable",
            FIF.SPEED_HIGH,
            '启用虚构叙事',
            ""
        )
        self.purefictionLevelCard = PushSettingCardEval(
            '修改',
            FIF.MINIMIZE,
            "关卡范围",
            "purefiction_level"
        )
        self.purefictionTeamsCard = PushSettingCardTeamWithSwap(
            FIF.FLAG,
            "虚构叙事队伍配置",
            "purefiction_team1",
            "purefiction_team2"
        )
        self.purefictionRunTimeCard = PushSettingCardDate(
            '修改',
            FIF.DATE_TIME,
            "上次运行虚构叙事的时间",
            "purefiction_timestamp"
        )

        self.ApocalypticEnableCard = ExpandableSwitchSettingCard(
            "apocalyptic_enable",
            FIF.SPEED_HIGH,
            '启用末日幻影',
            ""
        )
        self.ApocalypticLevelCard = PushSettingCardEval(
            '修改',
            FIF.MINIMIZE,
            "关卡范围",
            "apocalyptic_level"
        )
        self.ApocalypticTeamsCard = PushSettingCardTeamWithSwap(
            FIF.FLAG,
            "末日幻影队伍配置",
            "apocalyptic_team1",
            "apocalyptic_team2"
        )
        self.ApocalypticRunTimeCard = PushSettingCardDate(
            '修改',
            FIF.DATE_TIME,
            "上次运行末日幻影的时间",
            "apocalyptic_timestamp"
        )

        self.CloudGameGroup = SettingCardGroup(
            "云崩铁设置",
            self.scrollWidget
        )
        self.cloudGameEnableCard = SwitchSettingCard1(
            FIF.SPEED_HIGH,
            "使用“云·星穹铁道”",
            "开启后，将改用云·星穹铁道来执行清体力等自动化任务。无需固定窗口，可在后台运行。（模拟宇宙和锄大地仍需保持窗口全屏）",
            "cloud_game_enable"
        )
        self.cloudGameFullScreenCard = SwitchSettingCard1(
            FIF.FULL_SCREEN,
            "全屏运行",
            None,
            "cloud_game_fullscreen_enable"
        )
        self.cloudGameMaxQueueTimeCard = RangeSettingCard1(
            "cloud_game_max_queue_time",
            [1, 120],
            FIF.SPEED_MEDIUM,
            "最大排队等待时间（分钟）",
            ''
        )
        # self.cloudGameVideoQualityCard = ComboBoxSettingCard2(
        #     "cloud_game_video_quality",
        #     FIF.VIDEO,
        #     "云游戏画质",
        #     None,
        #     texts={"超高清": "0", "高清": "1", "标清": "2", "低清": "3"}
        # )
        # self.cloudGameSmoothFirstCard = SwitchSettingCard1(
        #     FIF.SPEED_HIGH,
        #     "画面流畅优先",
        #     "启用这个选项后，当网速过慢时，会自动调低画质",
        #     "cloud_game_smooth_first_enable"
        # )
        # self.cloudGameShowStatusCard = SwitchSettingCardCloudGameStatus(
        #     FIF.INFO,
        #     "云游戏内显示网络状态",
        #     None,
        #     "cloud_game_status_bar_enable",
        #     "cloud_game_status_bar_type"
        # )
        self.browserTypeCard = ExpandableComboBoxSettingCard(
            "browser_type",
            FIF.GLOBE,
            "浏览器类型",
            "建议保持默认的“集成（Chrome For Testing）”效果最好",
            {"集成（Chrome For Testing）": "integrated", "Chrome": "chrome", "Edge": "edge"}
        )
        self.browserDownloadUseMirrorCard = SwitchSettingCard1(
            FIF.CLOUD_DOWNLOAD,
            "使用国内镜像下载浏览器和驱动",
            None,
            "browser_download_use_mirror"
        )
        self.browserPersistentCard = SwitchSettingCard1(
            FIF.DOWNLOAD,
            "保存浏览器数据（游戏的登录状态和本地数据）",
            None,
            "browser_persistent_enable"
        )
        self.browserScaleCard = ComboBoxSettingCard2(
            "browser_scale_factor",
            FIF.ZOOM,
            "浏览器画面缩放（DPI）",
            "非 1920x1080 屏幕下，云游戏画面无法铺满屏幕，可以调整这个值改变画面缩放",
            texts={'50%': 0.5, '67%': 0.67, '75%': 0.75, '80%': 0.80, '90%': 0.90, '无缩放（100%）': 1.0,
                   '110%': 1.10, '125%': 1.25, '150%': 1.5, '175%': 1.75, '200%': 2.0}
        )
        self.browserLaunchArgCard = PushSettingCardEval(
            "修改",
            FIF.CODE,
            "浏览器启动参数",
            "browser_launch_argument"
        )
        self.browserHeadlessCard = ExpandableSwitchSettingCard(
            "browser_headless_enable",
            FIF.VIEW,
            "启用无窗口模式（后台运行）",
            "不支持模拟宇宙和锄大地"
        )
        self.browserHeadlessRestartCard = SwitchSettingCard1(
            FIF.SYNC,
            "未登录时自动切换为有窗口模式",
            "开启后：在无窗口模式检测到未登录时，将自动以有窗口模式重启浏览器以便登录；关闭后：将在无窗口模式下尝试二维码登录。",
            "browser_headless_restart_on_not_logged_in"
        )
        # self.browserCookiesCard = SwitchSettingCard1(
        #     FIF.PALETTE,    # 这个画盘长得很像 Cookie
        #     "保存 Cookies（登录状态）",
        #     None,
        #     "browser_dump_cookies_enable"
        # )

        self.ProgramGroup = SettingCardGroup('程序设置', self.scrollWidget)
        self.logLevelCard = ComboBoxSettingCardLog(
            "log_level",
            FIF.TAG,
            '日志等级',
            "",
            texts={'简洁': 'INFO', '详细': 'DEBUG'}
        )
        self.gamePathCard = PushSettingCard(
            '修改',
            FIF.GAME,
            "游戏路径",
            cfg.game_path
        )
        self.updateViaLauncherEnableCard = ExpandableSwitchSettingCard(
            "update_via_launcher",
            FIF.UPDATE,
            '通过启动器更新游戏【测试版】',
            ""
        )
        self.launcherPathCard = PushSettingCard(
            '修改',
            FIF.GAME,
            "米哈游启动器路径",
            cfg.launcher_path
        )
        self.startGameTimeoutCard = RangeSettingCard1(
            "start_game_timeout",
            [10, 60],
            FIF.DATE_TIME,
            "启动游戏超时时间（分）",
            "",
        )
        self.updateGameTimeoutCard = RangeSettingCard1(
            "update_game_timeout",
            [1, 24],
            FIF.DATE_TIME,
            "更新游戏超时时间（时）",
            "",
        )
        # self.importConfigCard = PushSettingCard(
        #     '导入',
        #     FIF.ADD_TO,
        #     '导入配置',
        #     '选择需要导入的 config.yaml 文件（重启后生效）'
        # )
        self.pauseAfterSuccess = SwitchSettingCard1(
            FIF.SYNC,
            '成功后暂停程序',
            "如果勾选，除非循环模式，执行成功后暂停程序。",
            "pause_after_success"
        )
        self.exitAfterFailure = SwitchSettingCard1(
            FIF.SYNC,
            '失败后直接退出',
            "如果勾选，那么失败后直接退出，否则失败后暂停程序。",
            "exit_after_failure"
        )
        self.afterFinishCard = ExpandableComboBoxSettingCard(
            "after_finish",
            FIF.POWER_BUTTON,
            '任务完成后',
            '“退出”指退出游戏，不再建议使用循环模式，请改用日志界面的定时运行功能',
            texts={'无': 'None', '退出': 'Exit', '关机': 'Shutdown', '睡眠': 'Sleep', '休眠': 'Hibernate', '重启': 'Restart', '注销': 'Logoff', '关闭显示器': 'TurnOffDisplay', '运行脚本': 'RunScript', '循环': 'Loop'}
        )
        self.loopModeCard = ComboBoxSettingCard2(
            "loop_mode",
            FIF.COMMAND_PROMPT,
            '循环模式（请改用日志界面的定时运行功能）',
            '',
            texts={'定时任务': 'scheduled', '根据开拓力': 'power'}
        )
        self.scheduledCard = TimePickerSettingCard1(
            "scheduled_time",
            FIF.DATE_TIME,
            "定时任务时间",
        )
        self.powerLimitCard = RangeSettingCard1(
            "power_limit",
            [10, 300],
            FIF.HEART,
            "循环运行再次启动所需开拓力",
            "游戏刷新后优先级更高",
        )
        self.refreshHourEnableCard = RangeSettingCard1(
            "refresh_hour",
            [0, 23],
            FIF.DATE_TIME,
            "游戏刷新时间",
            "用于循环运行及判断任务状态，默认凌晨四点",
        )
        self.ScriptPathCard = PushSettingCard(
            '修改',
            FIF.CODE,
            "脚本或程序路径(选择运行脚本时生效)",
            cfg.script_path
        )
        self.playAudioCard = SwitchSettingCard1(
            FIF.ALBUM,
            '声音提示',
            '任务完成后列车长唱歌提示帕！',
            "play_audio"
        )
        self.closeWindowActionCard = ComboBoxSettingCard2(
            "close_window_action",
            FIF.CLOSE,
            '关闭窗口时',
            '选择关闭窗口时的默认行为，也可以在关闭时由对话框询问',
            texts={'询问': 'ask', '最小化到托盘': 'minimize', '关闭程序': 'close'}
        )

        self.NotifyGroup = SettingCardGroup("消息推送", self.scrollWidget)
        self.testNotifyCard = ExpandablePushSettingCard(
            "测试消息推送",
            FIF.RINGER,
            "",
            "发送消息"
        )
        self.notifyLevelCard = ComboBoxSettingCard2(
            "notify_level",
            FIF.COMMAND_PROMPT,
            '通知级别',
            '',
            texts={'推送所有通知': 'all', '仅推送错误通知': 'error'}
        )
        self.notifyTemplateCard = PushSettingCardNotifyTemplate(
            '修改',
            FIF.FONT_SIZE,
            "消息推送格式",
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
        self.notifySupportImage = ["telegram", "matrix", "smtp", "wechatworkapp", "wechatworkbot", "onebot", "gocqhttp", "lark", "custom"]

        for key, _ in cfg.config.items():
            if key.startswith("notify_") and key.endswith("_enable"):
                notifier_name = key[len("notify_"):-len("_enable")]
                if sys.platform != 'win32' and notifier_name == 'winotify':
                    continue
                notifyEnableCard = SwitchSettingCardNotify(
                    self.notifyLogoDict[notifier_name] if notifier_name in self.notifyLogoDict else FIF.MAIL,
                    self.tr(f'启用 {notifier_name.capitalize()} 通知 {"（支持图片）"if notifier_name in self.notifySupportImage else ""}'),
                    notifier_name,
                    key
                )
                self.notifyEnableGroup.append(notifyEnableCard)

        self.MiscGroup = SettingCardGroup("杂项", self.scrollWidget)
        self.autoBattleDetectEnableCard = SwitchSettingCard1(
            FIF.ROBOT,
            '启用自动战斗和二倍速检测',
            "游戏启动前通过修改注册表或本地存储开启自动战斗和二倍速，并在清体力、货币战争和逐光捡金场景中检测并保持自动战斗状态",
            "auto_battle_detect_enable"
        )
        self.ocrGpuAccelerationCard = SwitchSettingCard1(
            FIF.SPEED_HIGH,
            '启用 OCR GPU 加速',
            "使用 DirectML 加速 OCR 识别，若 GPU 负载高导致 OCR 过慢会自动关闭（仅 Windows 10 Build 18362 及以上支持）",
            "ocr_gpu_acceleration"
        )
        self.autoSetResolutionEnableCard = SwitchSettingCard1(
            FIF.FULL_SCREEN,
            '启用自动修改分辨率并关闭自动 HDR',
            "通过软件启动游戏会自动修改 1920x1080 分辨率并关闭自动 HDR，不影响手动启动游戏（支持国服和国际服）",
            "auto_set_resolution_enable"
        )
        self.autoSetGamePathEnableCard = SwitchSettingCard1(
            FIF.GAME,
            '启用自动配置游戏路径',
            "通过快捷方式、官方启动器、运行中的游戏进程等方式尝试自动配置游戏路径（支持国服和国际服）",
            "auto_set_game_path_enable"
        )
        self.allScreensCard = SwitchSettingCard1(
            FIF.ZOOM,
            '在多显示器上进行截屏',
            "默认开启，如果正在使用多显示器且无法正常截屏请关闭此选项重试",
            "all_screens"
        )
        if sys.platform == 'win32':
            self.StartMarch7thAssistantCard = StartMarch7thAssistantSwitchSettingCard(
                FIF.GAME,
                '在用户登录时启动',
                "通过任务计划程序在开机后自动执行完整运行模式（可能还需要自行配置电脑无需输入密码自动登录）"
            )
        self.hotkeyCard = SwitchSettingCardHotkey(
            FIF.SETTING,
            '修改按键',
            "配置秘技、地图、跃迁、停止任务等按键设置"
        )

        self.AboutGroup = SettingCardGroup('关于', self.scrollWidget)
        self.githubCard = PrimaryPushSettingCard(
            '项目主页',
            FIF.GITHUB,
            '项目主页',
            "https://github.com/moesnow/March7thAssistant"
        )
        self.qqGroupCard = PrimaryPushSettingCard(
            '加入群聊',
            FIF.EXPRESSIVE_INPUT_ENTRY,
            'QQ群',
            ""
        )
        self.feedbackCard = PrimaryPushSettingCard(
            '提供反馈',
            FIF.FEEDBACK,
            '提供反馈',
            '帮助我们改进 March7thAssistant'
        )
        self.aboutCard = PrimaryPushSettingCard(
            '检查更新',
            FIF.INFO,
            '关于',
            '当前版本：' + " " + cfg.version
        )
        self.updateSourceCard = ExpandableComboBoxSettingCardUpdateSource(
            "update_source",
            FIF.SPEED_HIGH,
            '更新源',
            self.parent,
            "",
            texts={'海外源': 'GitHub', 'Mirror 酱': 'MirrorChyan'}
        )
        self.checkUpdateCard = SwitchSettingCard1(
            FIF.SYNC,
            '启动时检测更新',
            "",
            "check_update"
        )
        self.updatePrereleaseEnableCard = SwitchSettingCard1(
            FIF.TRAIN,
            '加入预览版更新渠道',
            "",
            "update_prerelease_enable"
        )
        self.updateFullEnableCard = SwitchSettingCard1(
            FIF.GLOBE,
            '更新时下载完整包',
            "更新将包含依赖组件，建议保持开启。若关闭此选项，需自行手动更新依赖组件，可能会导致出现不可预期的错误。",
            "update_full_enable"
        )
        self.mirrorchyanCdkCard = PushSettingCardMirrorchyan(
            '修改',
            FIF.BOOK_SHELF,
            "Mirror 酱 CDK",
            self.parent,
            "mirrorchyan_cdk"
        )

    def __initLayout(self):
        self.settingLabel.move(36, 30)
        self.pivot.move(40, 80)
        # self.title_area.move(36, 80)
        # self.vBoxLayout.addWidget(self.pivot, 0, Qt.AlignTop)
        self.vBoxLayout.addWidget(self.stackedWidget, 0, Qt.AlignmentFlag.AlignTop)
        self.vBoxLayout.setContentsMargins(36, 0, 36, 0)

        self.PowerGroup.addSettingCard(self.powerPlanCard)
        self.PowerGroup.addSettingCard(self.instanceTypeCard)
        # self.PowerGroup.addSettingCard(self.calyxGoldenPreferenceCard)
        self.PowerGroup.addSettingCard(self.instanceTypeCard)
        self.instanceTypeCard.addSettingCards([
            self.instanceNameCard,
            self.instanceTeamEnableCard,
            self.tpBeforeInstanceEnableCard,
            self.useReservedTrailblazePowerEnableCard,
            self.useFuelEnableCard,
            self.breakDownLevelFourRelicsetEnableCard,
            self.mergeImmersifierEnableCard,
            self.instanceNameChallengeCountCard
        ])
        self.PowerGroup.addSettingCard(self.borrowEnableCard)
        # 将子卡片添加到 borrowEnableCard 的可展开区域
        self.borrowEnableCard.addSettingCards([
            self.borrowCharacterEnableCard,
            self.borrowFriendsCard,
            self.borrowScrollTimesCard
        ])
        # self.PowerGroup.addSettingCard(self.maxCalyxPerRoundNumOfAttempts)
        self.PowerGroup.addSettingCard(self.buildTargetEnableCard)
        self.buildTargetEnableCard.addSettingCards([
            self.buildTargetPlanarOrnamentWeeklyCountCard
        ])
        self.PowerGroup.addSettingCard(self.echoofwarEnableCard)
        self.echoofwarEnableCard.addSettingCards([
            self.echoofwarRunTimeCard
        ])
        # self.PowerGroup.addSettingCard(self.echoofwarStartDayOfWeekCard)
        # self.BorrowGroup.addSettingCard(self.borrowCharacterFromCard)
        # self.BorrowGroup.addSettingCard(self.borrowCharacterInfoCard)
        # self.BorrowGroup.addSettingCard(self.borrowCharacterCard)

        self.DailyGroup.addSettingCard(self.dailyEnableCard)
        self.dailyEnableCard.addSettingCards([
            self.dailyMaterialEnableCard,
            # self.dailyHimekoTryEnableCard,
            self.dailyMemoryOneEnableCard,
            self.dailyMemoryOneTeamCard,
            self.lastRunTimeCard
        ])
        self.DailyGroup.addSettingCard(self.activityEnableCard)
        self.activityEnableCard.addSettingCards([
            self.activityDailyCheckInEnableCard,
            self.activityGardenOfPlentyEnableCard,
            self.activityRealmOfTheStrangeEnableCard,
            self.activityPlanarFissureEnableCard
        ])
        self.DailyGroup.addSettingCard(self.rewardEnableCard)
        self.rewardEnableCard.addSettingCards([
            self.dispatchEnableCard,
            self.mailEnableCard,
            self.assistEnableCard,
            self.questEnableCard,
            self.srpassEnableCard,
            self.redemptionEnableCard,
            self.achievementEnableCard
        ])

        self.CurrencywarsGroup.addSettingCard(self.currencywarsEnableCard)
        self.CurrencywarsGroup.addSettingCard(self.currencywarsTypeCard)
        self.CurrencywarsGroup.addSettingCard(self.currencywarsRunTimeCard)

        self.UniverseGroup.addSettingCard(self.weeklyDivergentEnableCard)
        self.weeklyDivergentEnableCard.addSettingCards([
            self.weeklyDivergentTypeCard,
            self.weeklyDivergentRunTimeCard
        ])
        self.UniverseGroup.addSettingCard(self.universeEnableCard)
        self.universeEnableCard.addSettingCards([
            self.universeCategoryCard,
            self.divergentTypeCard,
            self.universeFrequencyCard,
            self.universeCountCard,
            self.universeFateCard,
            self.universeDifficultyCard,
            self.universeOperationModeCard,
            self.universeTimeoutCard,
            self.universeRunTimeCard,
        ])
        self.UniverseGroup.addSettingCard(self.divergentTeamTypeCard)
        self.UniverseGroup.addSettingCard(self.universeBonusEnableCard)
        self.UniverseGroup.addSettingCard(self.universeDisableGpuCard)

        self.FightGroup.addSettingCard(self.fightEnableCard)
        self.fightEnableCard.addSettingCards([
            self.fightOperationModeCard,
            self.fightTimeoutCard,
            self.FightRunTimeCard,
        ])
        self.FightGroup.addSettingCard(self.fightTeamEnableCard)
        # self.FightGroup.addSettingCard(self.fightTeamNumberCard)
        self.FightGroup.addSettingCard(self.fightAllowMapBuyCard)
        self.FightGroup.addSettingCard(self.fightAllowSnackBuyCard)
        self.FightGroup.addSettingCard(self.fightMainMapCard)

        self.ImmortalGameGroup.addSettingCard(self.forgottenhallEnableCard)
        self.forgottenhallEnableCard.addSettingCards([
            self.forgottenhallLevelCard,
            self.forgottenhallTeamsCard,
            self.forgottenhallRunTimeCard
        ])

        self.ImmortalGameGroup.addSettingCard(self.purefictionEnableCard)
        self.purefictionEnableCard.addSettingCards([
            self.purefictionLevelCard,
            self.purefictionTeamsCard,
            self.purefictionRunTimeCard
        ])

        self.ImmortalGameGroup.addSettingCard(self.ApocalypticEnableCard)
        self.ApocalypticEnableCard.addSettingCards([
            self.ApocalypticLevelCard,
            self.ApocalypticTeamsCard,
            self.ApocalypticRunTimeCard
        ])

        self.CloudGameGroup.addSettingCard(self.cloudGameEnableCard)
        self.CloudGameGroup.addSettingCard(self.browserTypeCard)
        self.browserTypeCard.addSettingCards([
            self.browserDownloadUseMirrorCard,
            self.browserPersistentCard,
            self.browserScaleCard,
            self.browserLaunchArgCard
        ])
        self.CloudGameGroup.addSettingCard(self.cloudGameFullScreenCard)
        self.CloudGameGroup.addSettingCard(self.browserHeadlessCard)
        self.browserHeadlessCard.addSettingCards([self.browserHeadlessRestartCard])
        self.CloudGameGroup.addSettingCard(self.cloudGameMaxQueueTimeCard)
        # self.CloudGameGroup.addSettingCard(self.cloudGameVideoQualityCard)
        # self.CloudGameGroup.addSettingCard(self.cloudGameSmoothFirstCard)
        # self.CloudGameGroup.addSettingCard(self.cloudGameShowStatusCard)
        # self.CloudGameGroup.addSettingCard(self.browserCookiesCard)
        # self.CloudGameGroup.addSettingCard(self.browserPersistentCard)
        # self.CloudGameGroup.addSettingCard(self.browserScaleCard)
        # self.CloudGameGroup.addSettingCard(self.browserLaunchArgCard)

        self.ProgramGroup.addSettingCard(self.logLevelCard)
        self.ProgramGroup.addSettingCard(self.gamePathCard)
        self.ProgramGroup.addSettingCard(self.updateViaLauncherEnableCard)
        self.updateViaLauncherEnableCard.addSettingCards([
            self.launcherPathCard,
            self.updateGameTimeoutCard
        ])
        self.ProgramGroup.addSettingCard(self.startGameTimeoutCard)
        # self.ProgramGroup.addSettingCard(self.importConfigCard)
        self.ProgramGroup.addSettingCard(self.pauseAfterSuccess)
        self.ProgramGroup.addSettingCard(self.exitAfterFailure)
        self.ProgramGroup.addSettingCard(self.afterFinishCard)
        self.afterFinishCard.addSettingCards([
            self.loopModeCard,
            self.scheduledCard,
            self.powerLimitCard,
            self.refreshHourEnableCard,
            self.ScriptPathCard
        ])
        self.ProgramGroup.addSettingCard(self.playAudioCard)
        self.ProgramGroup.addSettingCard(self.closeWindowActionCard)

        self.NotifyGroup.addSettingCard(self.testNotifyCard)
        self.testNotifyCard.addSettingCards([
            self.notifyLevelCard,
            self.notifyTemplateCard
        ])
        for value in self.notifyEnableGroup:
            self.NotifyGroup.addSettingCard(value)

        self.MiscGroup.addSettingCard(self.autoBattleDetectEnableCard)
        self.MiscGroup.addSettingCard(self.ocrGpuAccelerationCard)
        self.MiscGroup.addSettingCard(self.autoSetResolutionEnableCard)
        self.MiscGroup.addSettingCard(self.autoSetGamePathEnableCard)
        self.MiscGroup.addSettingCard(self.allScreensCard)
        if sys.platform == 'win32':
            self.MiscGroup.addSettingCard(self.StartMarch7thAssistantCard)
        self.MiscGroup.addSettingCard(self.hotkeyCard)

        self.AboutGroup.addSettingCard(self.githubCard)
        self.AboutGroup.addSettingCard(self.qqGroupCard)
        self.AboutGroup.addSettingCard(self.feedbackCard)
        self.AboutGroup.addSettingCard(self.aboutCard)
        self.AboutGroup.addSettingCard(self.updateSourceCard)
        self.updateSourceCard.addSettingCards([
            self.checkUpdateCard,
            self.updatePrereleaseEnableCard,
            self.updateFullEnableCard
        ])
        self.AboutGroup.addSettingCard(self.mirrorchyanCdkCard)

        if sys.platform != 'win32':
            self.gamePathCard.setHidden(True)
            self.updateViaLauncherEnableCard.setHidden(True)
            self.autoSetResolutionEnableCard.setHidden(True)
            self.autoSetGamePathEnableCard.setHidden(True)
            self.allScreensCard.setHidden(True)
            self.cloudGameEnableCard.setDisabled(True)  # 在配置文件中强制启用，禁止用户修改

        self.addSubInterface(self.PowerGroup, 'PowerInterface', '体力')
        # self.addSubInterface(self.BorrowGroup, 'BorrowInterface', '支援')
        self.addSubInterface(self.DailyGroup, 'DailyInterface', '日常')
        self.addSubInterface(self.CurrencywarsGroup, 'CurrencywarsInterface', '货币战争')
        if sys.platform == 'win32':
            self.addSubInterface(self.UniverseGroup, 'UniverseInterface', '差分宇宙')
            self.addSubInterface(self.FightGroup, 'FightInterface', '锄大地')
        else:
            self.UniverseGroup.setHidden(True)
            self.FightGroup.setHidden(True)
        self.addSubInterface(self.ImmortalGameGroup, 'ImmortalGameInterface', '逐光捡金')

        self.pivot.addItem(
            routeKey='verticalBar',
            text="|",
            onClick=lambda: self.pivot.setCurrentItem(self.stackedWidget.currentWidget().objectName()),
        )

        self.addSubInterface(self.ProgramGroup, 'programInterface', '程序')
        self.addSubInterface(self.CloudGameGroup, "cloudGameInterface", '云游戏')
        self.addSubInterface(self.NotifyGroup, 'NotifyInterface', '推送')
        self.addSubInterface(self.MiscGroup, 'KeybindingInterface', '杂项')
        if sys.platform == 'win32':
            self.addSubInterface(
                accounts_interface(self.tr, self.scrollWidget),
                'AccountsInterface',
                '账号'
            )
        self.addSubInterface(self.AboutGroup, 'AboutInterface', '关于')

        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.pivot.setCurrentItem(self.stackedWidget.currentWidget().objectName())
        self.stackedWidget.setFixedHeight(self.stackedWidget.currentWidget().sizeHint().height())

    def __connectSignalToSlot(self):
        # self.importConfigCard.clicked.connect(self.__onImportConfigCardClicked)
        self.gamePathCard.clicked.connect(self.__onGamePathCardClicked)
        self.launcherPathCard.clicked.connect(self.__onLauncherPathCardClicked)
        self.ScriptPathCard.clicked.connect(self.__onScriptPathCardClicked)
        # self.borrowCharacterInfoCard.clicked.connect(self.__openCharacterFolder())

        self.testNotifyCard.clicked.connect(lambda: start_task("notify"))

        self.afterFinishCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)

        self.githubCard.clicked.connect(self.__openUrl("https://github.com/moesnow/March7thAssistant"))
        self.qqGroupCard.clicked.connect(self.__openUrl("https://qm.qq.com/q/C3IryUWCQw"))
        self.feedbackCard.clicked.connect(self.__openUrl("https://github.com/moesnow/March7thAssistant/issues"))

        self.aboutCard.clicked.connect(lambda: checkUpdate(self.parent))

        # 连接可展开卡片的展开状态改变信号，在动画前调整 stackedWidget 高度
        self.borrowEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.buildTargetEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.dailyEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.activityEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.rewardEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.fightEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.weeklyDivergentEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.universeEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.forgottenhallEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.purefictionEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.ApocalypticEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.updateViaLauncherEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.updateSourceCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.testNotifyCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.instanceTypeCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.echoofwarEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.browserTypeCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.browserHeadlessCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)

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

    def __onLauncherPathCardClicked(self):
        launcher_path, _ = QFileDialog.getOpenFileName(self, "选择米哈游启动器路径", "", "All Files (*)")
        if not launcher_path or cfg.launcher_path == launcher_path:
            return
        cfg.set_value("launcher_path", launcher_path)
        self.launcherPathCard.setContent(launcher_path)

    # def __openCharacterFolder(self):
    #     return lambda: os.startfile(os.path.abspath("./assets/images/share/character"))

    def __openUrl(self, url):
        return lambda: QDesktopServices.openUrl(QUrl(url))

    # def __showRestartTooltip(self):
    #     InfoBar.success(
    #         '更新成功',
    #         '配置在重启软件后生效',
    #         duration=1500,
    #         parent=self
    #     )
    def __onScriptPathCardClicked(self):
        script_path, _ = QFileDialog.getOpenFileName(self, "脚本或程序路径", "", "脚本或可执行文件 (*.ps1 *.bat *.exe)")
        if not script_path or cfg.script_path == script_path:
            return
        cfg.set_value("script_path", script_path)
        self.ScriptPathCard.setContent(script_path)

    def __onExpandableCardStateChanged(self, is_expanding: bool):
        """可展开卡片状态改变时，调整 stackedWidget 高度以包含子卡片"""
        # 获取发送信号的卡片对象
        sender_card = self.sender()

        # 根据展开的卡片获取其 viewLayout 的高度
        if sender_card:
            card_weight = sender_card.viewLayout.sizeHint().height()
        else:
            # 如果无法获取发送者，使用默认高度（向后兼容）
            card_weight = 0

        # 在动画执行前调整 stackedWidget 高度
        if is_expanding:
            self.stackedWidget.setFixedHeight(self.stackedWidget.currentWidget().sizeHint().height() + card_weight)
        else:
            self.stackedWidget.setFixedHeight(self.stackedWidget.currentWidget().sizeHint().height())
