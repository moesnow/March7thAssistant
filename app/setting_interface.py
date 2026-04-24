from PySide6.QtCore import Qt, QUrl, QObject, QEvent, QPoint
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget, QLabel, QFileDialog, QVBoxLayout, QStackedWidget, QSpacerItem, QScroller, QScrollerProperties, QScrollArea, QFrame, QApplication
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import SettingCardGroup, PushSettingCard, ScrollArea, InfoBar, InfoBarPosition, PrimaryPushSettingCard
from app.sub_interfaces.accounts_interface import accounts_interface
from .common.style_sheet import StyleSheet
from .components.pivot import SettingPivot
from .card.comboboxsettingcard1 import ComboBoxSettingCard1
from .card.comboboxsettingcard2 import ComboBoxSettingCard2, ComboBoxSettingCardUpdateSource, ComboBoxSettingCardLog, ComboBoxSettingCardLanguage
from .card.switchsettingcard1 import SwitchSettingCard1, StartMarch7thAssistantSwitchSettingCard, SwitchSettingCardTeam, SwitchSettingCardImmersifier, SwitchSettingCardGardenofplenty, SwitchSettingCardEchoofwar, SwitchSettingCardHotkey, SwitchSettingCardCloudGameStatus
from .card.rangesettingcard1 import RangeSettingCard1
from .card.pushsettingcard1 import CustomPushSettingCard, DualPushSettingCard, PushSettingCardInstance, PushSettingCardInstanceChallengeCount, PushSettingCardNotifyTemplate, PushSettingCardMirrorchyan, PushSettingCardStr, PushSettingCardEval, PushSettingCardDate, PushSettingCardKey, PushSettingCardTeam, PushSettingCardFriends, PushSettingCardTeamWithSwap, PushSettingCardPowerPlan, InstanceTeamSettingCard
from .card.timepickersettingcard1 import TimePickerSettingCard1
from .card.expandable_switch_setting_card import ExpandableSwitchSettingCard, ExpandableComboBoxSettingCardUpdateSource, ExpandableComboBoxSettingCard, ExpandableComboBoxSettingCardInstanceType, ExpandableSwitchSettingCardEchoofwar
from .card.messagebox_custom import MessageBoxEdit
from .card.stationprioritysettingcard import StationPrioritySettingCard
from module.config import cfg
from module.notification import init_notifiers
from module.localization import tr
from tasks.base.tasks import start_task
from .tools.check_update import checkUpdate
import os
import sys


class _PivotScrollFilter(QObject):
    """为 pivot 及其所有子控件（tab 按钮）提供横向拖拽滚动支持。

    安装方式（在所有 addItem 完成后）：
        self.pivot.installEventFilter(filter)
        for child in self.pivot.findChildren(QWidget):
            child.installEventFilter(filter)

    拖拽后防止误切 tab 的机制：
        进入拖拽模式后立即对 pivot 调用 grabMouse()，把后续所有鼠标事件
        路由到 pivot 而非 tab 子控件。松开时 releaseMouse() 还原路由，
        并对 pivot 发送 Leave 事件重置 hover 状态，完全杜绝误切 tab。
    """
    _DRAG_THRESHOLD = 5  # px；低于此值视为点击，不进入拖拽模式

    def __init__(self, scroll_area: QScrollArea, pivot):
        super().__init__(scroll_area)
        self._sa = scroll_area
        self._pivot = pivot
        self._press_global: QPoint | None = None
        self._drag_origin: int = 0
        self._is_dragging: bool = False

    def eventFilter(self, obj, event: QEvent) -> bool:
        t = event.type()

        # ── 滚轮 → 横向滚动（消费，不冒泡给外层纵向 ScrollArea）───────
        if t == QEvent.Type.Wheel:
            delta = event.angleDelta()
            scroll = delta.x() if delta.x() != 0 else delta.y()
            sb = self._sa.horizontalScrollBar()
            sb.setValue(sb.value() - scroll // 3)
            return True

        # ── 按下 → 记录全局起点，放行（tab 正常 press/hover）────────────
        if t == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._drag_origin = self._sa.horizontalScrollBar().value()
            self._is_dragging = False
            return False

        # ── 移动 → 超阈值进入拖拽，grabMouse 接管后续事件 ───────────────
        if t == QEvent.Type.MouseMove and (event.buttons() & Qt.MouseButton.LeftButton):
            if self._press_global is not None:
                dx = event.globalPosition().toPoint().x() - self._press_global.x()
                if not self._is_dragging and abs(dx) > self._DRAG_THRESHOLD:
                    self._is_dragging = True
                    # grabMouse：把所有后续鼠标事件路由到 pivot，
                    # 子控件（tab 按钮）不再收到 Release/Click，彻底防止误切 tab
                    self._pivot.grabMouse(Qt.CursorShape.ClosedHandCursor)
                if self._is_dragging:
                    self._sa.horizontalScrollBar().setValue(self._drag_origin - dx)
                    return True
            return False

        # ── 释放 → 拖拽：releaseMouse + 发送 Leave，清理状态 ────────────
        if t == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            if self._press_global is not None:
                was_dragging = self._is_dragging
                self._press_global = None
                self._is_dragging = False
                if was_dragging:
                    self._pivot.releaseMouse()
                    # 发送 Leave 事件让 pivot 及子控件重置 hover 样式
                    leave = QEvent(QEvent.Type.Leave)
                    QApplication.sendEvent(self._pivot, leave)
                    return True  # 消费 Release，不触发 tab 切换
            return False

        return False


class SettingInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.scrollWidget = QWidget()
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)

        # self.title_area = QScrollArea(self)
        self.pivot = SettingPivot(self)
        self.stackedWidget = QStackedWidget(self)

        self.settingLabel = QLabel(tr("设置"), self)

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

        # ── 选项卡滚动容器 ──────────────────────────────────────────────
        # 当标签文字较长（如英语）时允许横向滚动。滚动条隐藏，仅保留拖拽交互。
        # 注意：不在此处安装 _PivotScrollFilter，因为 pivot 的 tab 子控件
        # 尚未创建（addItem 在 __initLayout 中调用）。filter 在 __initLayout
        # 最后通过 pivot.findChildren(QWidget) 递归安装，覆盖所有 tab 子控件。
        self.pivotScrollArea = QScrollArea(self)
        self.pivotScrollArea.setWidget(self.pivot)
        self.pivotScrollArea.setWidgetResizable(False)
        self.pivotScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.pivotScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.pivotScrollArea.setFrameShape(QFrame.Shape.NoFrame)

        QScroller.grabGesture(self.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)
        scroller = QScroller.scroller(self.viewport())
        scroller_props = scroller.scrollerProperties()
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootDragDistanceFactor, 0.05)
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootScrollDistanceFactor, 0.05)
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.DecelerationFactor, 0.5)
        scroller.setScrollerProperties(scroller_props)

    def __initCard(self):
        self.PowerGroup = SettingCardGroup(tr("体力设置"), self.scrollWidget)
        self.powerPlanCard = PushSettingCardPowerPlan(
            tr('配置'),
            FIF.CALENDAR,
            tr("体力计划"),
            "power_plan"
        )
        self.instanceTypeCard = ExpandableComboBoxSettingCardInstanceType(
            "instance_type",
            FIF.ALIGNMENT,
            tr("副本类型"),
            None,
            texts=[tr('拟造花萼（金）'), tr('拟造花萼（赤）'), tr('凝滞虚影'), tr('侵蚀隧洞'), tr('饰品提取')]
        )
        # self.calyxGoldenPreferenceCard = ComboBoxSettingCard2(
        #     "calyx_golden_preference",
        #     FIF.PIE_SINGLE,
        #     '拟造花萼（金）偏好地区',
        #     '',
        #     texts={'雅利洛-VI': 'Jarilo-VI', '仙舟「罗浮」': 'XianzhouLuofu', '匹诺康尼': 'Penacony'}
        # )
        self.instanceNameCard = PushSettingCardInstance(
            tr('修改'),
            FIF.PALETTE,
            tr("副本名称"),
            "instance_names"
        )
        # self.maxCalyxPerRoundNumOfAttempts = RangeSettingCard1(
        #     "max_calyx_per_round_num_of_attempts",
        #     [1, 6],
        #     FIF.HISTORY,
        #     "每轮拟造花萼挑战次数",
        #     '',
        # )
        self.instanceTeamEnableCard = InstanceTeamSettingCard(
            FIF.EDIT,
            tr("自动切换队伍"),
            None
        )
        self.tpBeforeInstanceEnableCard = SwitchSettingCard1(
            FIF.LEAF,
            tr("清体力前传送至任意锚点"),
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
            tr("使用后备开拓力"),
            tr("单次上限300点，全部使用需要将“任务完成后”选项修改为“循环”，然后点击“完整运行”"),
            "use_reserved_trailblaze_power"
        )
        self.useFuelEnableCard = SwitchSettingCard1(
            FIF.CAFE,
            tr("使用燃料"),
            tr("单次上限5个，全部使用需要将“任务完成后”选项修改为“循环”，然后点击“完整运行”"),
            "use_fuel"
        )
        self.breakDownLevelFourRelicsetEnableCard = SwitchSettingCard1(
            FIF.FILTER,
            tr("自动分解四星遗器（建议在游戏内配置结算遗器时自动分解）"),
            tr("侵蚀隧洞、饰品提取、历战余响和模拟宇宙完成后自动分解四星及以下遗器"),
            "break_down_level_four_relicset"
        )
        self.mergeImmersifierEnableCard = SwitchSettingCardImmersifier(
            FIF.BASKETBALL,
            tr("体力优先合成沉浸器（建议直接通过饰品提取获取位面饰品）"),
            tr("达到指定上限后停止"),
            "merge_immersifier"
        )
        self.instanceNameChallengeCountCard = PushSettingCardInstanceChallengeCount(
            tr('修改'),
            FIF.HISTORY,
            tr("副本最大连续挑战次数（通常不建议修改保持默认即可）"),
            "instance_names_challenge_count"
        )
        self.borrowEnableCard = ExpandableSwitchSettingCard(
            "borrow_enable",
            FIF.PIN,
            tr("启用使用支援角色"),
            ''
        )
        self.borrowCharacterEnableCard = SwitchSettingCard1(
            FIF.UNPIN,
            tr("强制使用支援角色"),
            tr("无论何时都要使用支援角色，即使日常实训中的要求已经完成"),
            "borrow_character_enable"
        )
        self.borrowFriendsCard = PushSettingCardFriends(
            tr('修改'),
            FIF.FLAG,
            tr("支援列表"),
            "borrow_friends"
        )
        self.borrowScrollTimesCard = RangeSettingCard1(
            "borrow_scroll_times",
            [1, 10],
            FIF.HISTORY,
            tr("滚动查找次数"),
            '',
        )
        self.buildTargetEnableCard = ExpandableSwitchSettingCard(
            "build_target_enable",
            FIF.LEAF,
            tr("启用培养目标"),
            tr("根据培养目标刷取行迹与遗器副本，如果无法获取培养目标则回退到默认的副本设置")
        )
        self.buildTargetSchemeCard = ComboBoxSettingCard2(
            "build_target_scheme",
            FIF.SEARCH,
            tr("识别方案"),
            tr("副本名称识别会进入挑战页读取副本信息；掉落物识别根据列表中的掉落物匹配副本，异常时可尝试切换方案"),
            texts={
                tr("副本名称识别"): "instance",
                tr("掉落物识别"): "drop"
            }
        )
        self.buildTargetPlanarOrnamentWeeklyCountCard = RangeSettingCard1(
            "build_target_ornament_weekly_count",
            [0, 7],
            FIF.CALENDAR,
            tr("每周饰品提取次数"),
            tr("目标有足够资源后，执行饰品提取的次数，其余时间执行侵蚀隧洞"),
        )
        self.buildTargetUseUserInstanceWhenOnlyErosionAndOrnamentCard = SwitchSettingCard1(
            FIF.SYNC,
            tr("仅识别到侵蚀隧洞/饰品提取时使用自定义副本"),
            tr("开启后，当培养目标仅包含侵蚀隧洞和饰品提取时，清体力将改用你在体力设置中配置的副本"),
            "build_target_use_user_instance_when_only_erosion_and_ornament"
        )
        self.echoofwarEnableCard = ExpandableSwitchSettingCardEchoofwar(
            "echo_of_war_enable",
            FIF.MEGAPHONE,
            tr("启用历战余响"),
            tr("每周体力优先完成三次「历战余响」，支持配置从周几后开始执行，仅限完整运行生效"),
        )
        self.echoofwarRunTimeCard = PushSettingCardDate(
            tr('修改'),
            FIF.DATE_TIME,
            tr("上次完成历战余响的时间"),
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

        self.DailyGroup = SettingCardGroup(tr("日常设置"), self.scrollWidget)
        self.dailyEnableCard = ExpandableSwitchSettingCard(
            "daily_enable",
            FIF.CALENDAR,
            tr("启用每日实训"),
            ""
        )
        self.dailyMaterialEnableCard = SwitchSettingCard1(
            FIF.CHECKBOX,
            tr('通过 “合成材料” 完成任务'),
            tr("请确保背包中有足够的 “熄灭原核” 用于合成 “微光原核” "),
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
            tr('通过 “回忆一” 完成任务'),
            tr("请解锁混沌回忆并配置了队伍后再打开该选项"),
            "daily_memory_one_enable"
        )
        self.dailyMemoryOneTeamCard = PushSettingCardTeam(
            tr('修改'),
            FIF.FLAG,
            tr("回忆一队伍"),
            "daily_memory_one_team"
        )
        self.lastRunTimeCard = PushSettingCardDate(
            tr('修改'),
            FIF.DATE_TIME,
            tr("上次检测到完成日常的时间"),
            "last_run_timestamp"
        )
        self.activityEnableCard = ExpandableSwitchSettingCard(
            "activity_enable",
            FIF.CERTIFICATE,
            tr('启用活动检测'),
            None
        )
        self.activityDailyCheckInEnableCard = SwitchSettingCard1(
            FIF.COMPLETED,
            tr('每日签到'),
            tr("自动领取「星轨专票」或「星琼」，包含巡星之礼、巡光之礼和庆典祝礼活动"),
            "activity_dailycheckin_enable"
        )
        self.activityGardenOfPlentyEnableCard = SwitchSettingCardGardenofplenty(
            FIF.CALORIES,
            tr('花藏繁生'),
            tr("存在双倍次数时体力优先「拟造花萼」"),
            "activity_gardenofplenty_enable"
        )
        self.activityRealmOfTheStrangeEnableCard = SwitchSettingCard1(
            FIF.CALORIES,
            tr('异器盈界'),
            tr("存在双倍次数时体力优先「侵蚀隧洞」"),
            "activity_realmofthestrange_enable"
        )
        self.activityPlanarFissureEnableCard = SwitchSettingCard1(
            FIF.CALORIES,
            tr('位面分裂'),
            tr("存在双倍次数时体力优先「饰品提取」"),
            "activity_planarfissure_enable"
        )
        self.activityJourneyHighlightsNotificationEnableCard = SwitchSettingCard1(
            FIF.CALENDAR,
            tr('活动热点通知'),
            tr("每次运行时发送带有活动热点截图的通知"),
            "activity_journey_highlights_notification_enable"
        )
        self.rewardEnableCard = ExpandableSwitchSettingCard(
            "reward_enable",
            FIF.TRANSPARENT,
            tr('启用奖励领取'),
            ""
        )
        self.dispatchEnableCard = SwitchSettingCard1(
            FIF.STOP_WATCH,
            tr('委托'),
            None,
            "reward_dispatch_enable"
        )
        self.mailEnableCard = SwitchSettingCard1(
            FIF.MAIL,
            tr('邮件'),
            None,
            "reward_mail_enable"
        )
        self.assistEnableCard = SwitchSettingCard1(
            FIF.BRUSH,
            tr('支援'),
            None,
            "reward_assist_enable"
        )
        self.questEnableCard = SwitchSettingCard1(
            FIF.STOP_WATCH,
            tr('每日实训'),
            None,
            "reward_quest_enable"
        )
        self.srpassEnableCard = SwitchSettingCard1(
            FIF.QUIET_HOURS,
            tr('无名勋礼'),
            None,
            "reward_srpass_enable"
        )
        self.achievementEnableCard = SwitchSettingCard1(
            FIF.CERTIFICATE,
            tr('成就'),
            None,
            "reward_achievement_enable"
        )

        # 兑换码奖励开关
        self.redemptionEnableCard = SwitchSettingCard1(
            FIF.BOOK_SHELF,
            tr('兑换码'),
            None,
            "reward_redemption_code_enable"
        )

        # 短信奖励开关
        self.messageEnableCard = SwitchSettingCard1(
            FIF.CHAT,
            tr('短信'),
            None,
            "reward_message_enable"
        )

        self.assetEnableCard = ExpandableSwitchSettingCard(
            "asset_manager_enable",
            FIF.LIBRARY,
            tr("启用资产管理"),
            ""
        )

        self.lc3StarSuperimposeEnableCard = SwitchSettingCard1(
            FIF.ZIP_FOLDER,
            tr("启用「3星光锥自动叠加」"),
            tr("自动将3星光锥进行叠加以节省背包空间"),
            "asset_lc3_star_superimpose_enable",
        )

        self.CurrencywarsGroup = SettingCardGroup(tr("货币"), self.scrollWidget)
        self.currencywarsEnableCard = ExpandableSwitchSettingCard(
            "currencywars_enable",
            FIF.DICTIONARY,
            tr('启用「货币战争」积分奖励'),
            ""
        )
        self.currencywarsPresetCard = DualPushSettingCard(
            tr('提升晋升等级'),
            tr('提升职级等级'),
            FIF.SYNC,
            tr('快捷配置')
        )
        self.currencywarsRunTimeCard = PushSettingCardDate(
            tr('修改'),
            FIF.DATE_TIME,
            tr("上次检测到完成货币战争积分奖励的时间"),
            "currencywars_timestamp"
        )
        self.currencywarsTypeCard = ComboBoxSettingCard2(
            "currencywars_type",
            FIF.COMMAND_PROMPT,
            tr('类别'),
            '',
            texts={tr('标准博弈'): 'normal', tr('超频博弈'): 'overclock'}
        )
        self.currencywarsBonusEnableCard = SwitchSettingCard1(
            FIF.IOT,
            tr('自动执行位面饰品快速提取'),
            tr("在领取积分奖励后自动执行位面饰品快速提取消耗深度沉浸器"),
            "currencywars_bonus_enable"
        )
        self.currencywarsRankDifficultyCard = ComboBoxSettingCard2(
            "currencywars_rank_difficulty",
            FIF.HISTORY,
            tr('职级难度'),
            '',
            texts={tr('最高职级'): 'highest', tr('当前职级'): 'current', tr('最低职级'): 'lowest'}
        )
        self.currencywarsStrategyCard = ExpandableComboBoxSettingCard(
            "currencywars_strategy",
            FIF.BOOK_SHELF,
            tr('货币战争策略'),
            tr('提升晋升等级，推荐在最低职级选择默认策略。提升职级等级，推荐在最高职级选择阿格莱雅策略。'),
            {tr('默认'): 'default', tr('阿格莱雅'): 'aglaea'}
        )
        self.currencywarsRemembranceTrailblazerNameCard = PushSettingCardStr(
            tr('修改'),
            FIF.EDIT,
            tr('「开拓者•记忆」名称'),
            "currencywars_remembrance_trailblazer_name",
            empty_content=tr('未配置，阿格莱雅策略下将跳过该角色，需要填入自己游戏名称')
        )
        self.currencywarsStrategyRestartOnSpecialTagsCard = SwitchSettingCard1(
            FIF.SYNC,
            tr('遇到特定词条时接受重开'),
            tr('根据所选策略，在遇到特定词条或词条组合时允许重开'),
            "currencywars_strategy_restart_on_special_tags"
        )
        self.currencywarsFastModeCard = SwitchSettingCard1(
            FIF.SPEED_HIGH,
            tr('启用速通模式'),
            tr("开启后，仅在首领节点尝试装备武器，只推荐在最低职级时开启"),
            "currencywars_fast_mode"
        )

        self.UniverseGroup = SettingCardGroup(tr("差分宇宙"), self.scrollWidget)
        self.weeklyDivergentEnableCard = ExpandableSwitchSettingCard(
            "weekly_divergent_enable",
            FIF.DICTIONARY,
            tr('启用「差分宇宙」积分奖励'),
            ""
        )
        self.weeklyDivergentRunTimeCard = PushSettingCardDate(
            tr('修改'),
            FIF.DATE_TIME,
            tr("上次检测到完成差分宇宙积分奖励的时间"),
            "weekly_divergent_timestamp"
        )
        self.weeklyDivergentTypeCard = ComboBoxSettingCard2(
            "weekly_divergent_type",
            FIF.COMMAND_PROMPT,
            tr('类别'),
            '',
            texts={tr('常规演算'): 'normal', tr('周期演算'): 'cycle'}
        )
        self.weeklyDivergentLevelCard = RangeSettingCard1(
            "weekly_divergent_level",
            [1, 6],
            FIF.HISTORY,
            tr("难度等级（难度6对应常规演算星阶模式）"),
            "",
        )
        self.weeklyDivergentBonusEnableCard = SwitchSettingCard1(
            FIF.IOT,
            tr('自动执行饰品提取'),
            tr("在领取积分奖励后自动执行饰品提取消耗沉浸器"),
            "weekly_divergent_bonus_enable"
        )
        self.weeklyDivergentStableModeCard = SwitchSettingCard1(
            FIF.SPEED_OFF,
            tr('启用稳定模式'),
            tr("运行若出现问题可尝试开启，适配低性能环境，云游戏默认使用此模式"),
            "weekly_divergent_stable_mode"
        )

        self.stationPriorityCard = StationPrioritySettingCard(
            FIF.MENU,
            tr('站点优先级'),
            tr("自定义差分宇宙「选择下一站」的站点优先级"),
        )

        self.universeEnableCard = ExpandableSwitchSettingCard(
            "universe_enable",
            FIF.VPN,
            tr('启用模拟宇宙/差分宇宙 (Auto_Simulated_Universe)'),
            tr("通常用于反复刷取遗器经验和灵之珠泪（代替敌方掉落素材）直到每周上限")
        )
        self.universeOperationModeCard = ComboBoxSettingCard2(
            "universe_operation_mode",
            FIF.COMMAND_PROMPT,
            tr('运行模式'),
            '',
            texts={tr('集成'): 'exe', tr('源码'): 'source'}
        )
        self.universeCategoryCard = ComboBoxSettingCard2(
            "universe_category",
            FIF.COMMAND_PROMPT,
            tr('类别'),
            '',
            texts={tr('差分宇宙'): 'divergent', tr('模拟宇宙'): 'universe'}
        )
        self.divergentTypeCard = ComboBoxSettingCard2(
            "divergent_type",
            FIF.COMMAND_PROMPT,
            tr('选择差分宇宙时类别'),
            '',
            texts={tr('常规演算'): 'normal', tr('周期演算'): 'cycle'}
        )
        self.universeTimeoutCard = RangeSettingCard1(
            "universe_timeout",
            [1, 24],
            FIF.HISTORY,
            tr("模拟宇宙/差分宇宙超时"),
            tr("超过设定时间强制停止（单位小时）"),
        )
        self.universeRunTimeCard = PushSettingCardDate(
            tr('修改'),
            FIF.DATE_TIME,
            tr("上次运行模拟宇宙/差分宇宙的时间"),
            "universe_timestamp"
        )
        self.universeBonusEnableCard = SwitchSettingCard1(
            FIF.IOT,
            tr('自动领取模拟宇宙沉浸奖励'),
            tr("类别为“模拟宇宙”时，自动领取沉浸奖励"),
            "universe_bonus_enable"
        )
        self.universeFrequencyCard = ComboBoxSettingCard2(
            "universe_frequency",
            FIF.MINIMIZE,
            tr('运行频率'),
            '',
            texts={tr('每周'): 'weekly', tr('每天'): 'daily'}
        )
        self.universeCountCard = RangeSettingCard1(
            "universe_count",
            [0, 34],
            FIF.HISTORY,
            tr("运行次数"),
            tr("注意中途停止不会计数，0 代表不指定，使用模拟宇宙原版逻辑"),
        )
        # self.divergentTeamTypeCard = ComboBoxSettingCard2(
        #     "divergent_team_type",
        #     FIF.FLAG,
        #     tr('差分宇宙队伍类型'),
        #     '',
        #     texts={tr('追击'): '追击', tr('持续伤害 (DoT)'): 'dot', tr('终结技'): '终结技', tr('击破'): '击破', tr('盾反'): '盾反'}
        # )
        fates = {}
        fates = {}
        for a in [tr("不配置"), tr("存护"), tr("记忆"), tr("虚无"), tr("丰饶"), tr("巡猎"), tr("毁灭"), tr("欢愉"), tr("繁育"), tr("智识")]:
            fates[a] = a
        self.universeFateCard = ComboBoxSettingCard2(
            "universe_fate",
            FIF.PIE_SINGLE,
            tr('命途（仅模拟宇宙生效）'),
            '',
            texts=fates
        )
        self.universeDifficultyCard = RangeSettingCard1(
            "universe_difficulty",
            [0, 5],
            FIF.HISTORY,
            tr("难度 (0为不配置，仅模拟宇宙生效)"),
            "",
        )

        self.FightGroup = SettingCardGroup(tr("锄地"), self.scrollWidget)
        self.fightEnableCard = ExpandableSwitchSettingCard(
            "fight_enable",
            FIF.BUS,
            tr('启用锄大地 (Fhoe-Rail)'),
            ""
        )
        self.fightOperationModeCard = ComboBoxSettingCard2(
            "fight_operation_mode",
            FIF.COMMAND_PROMPT,
            tr('运行模式'),
            '',
            texts={tr('集成'): 'exe', tr('源码'): 'source'}
        )
        self.universeEnableGpuCard = SwitchSettingCard1(
            FIF.COMMAND_PROMPT,
            tr('启用模拟宇宙 GPU 加速'),
            tr('开启后可能提升运行速度，若出现错误、异常或不稳定，请关闭此选项'),
            "universe_enable_gpu"
        )

        self.fightTimeoutCard = RangeSettingCard1(
            "fight_timeout",
            [1, 24],
            FIF.HISTORY,
            tr("锄大地超时"),
            tr("超过设定时间强制停止（单位小时）"),
        )
        self.fightTeamEnableCard = SwitchSettingCardTeam(
            FIF.EDIT,
            tr('自动切换队伍'),
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
            tr('修改'),
            FIF.DATE_TIME,
            tr("上次运行锄大地的时间"),
            "fight_timestamp"
        )
        self.fightMapVersionCard = ComboBoxSettingCard2(
            "fight_map_version",
            FIF.GLOBE,
            tr('地图版本'),
            '',
            texts={tr("不配置"): "不配置", tr("默认（疾跑）"): "default", tr("黄泉专用"): "HuangQuan"}
        )
        self.fightMainMapCard = ComboBoxSettingCard2(
            "fight_main_map",
            FIF.GLOBE,
            tr('优先星球'),
            '',
            texts={tr("不配置"): "0", tr("空间站"): "1", tr("雅利洛"): "2", tr("仙舟"): "3", tr("匹诺康尼"): "4", tr("翁法罗斯"): 5, tr("二相乐园"): 6}
        )
        self.fightAllowSnackBuyCard = ComboBoxSettingCard2(
            "fight_allow_snack_buy",
            FIF.GLOBE,
            tr('购买秘技零食并合成零食'),
            '',
            texts={tr("不配置"): "不配置", tr("启用"): True, tr("停用"): False}
        )
        self.fightAllowMapBuyCard = ComboBoxSettingCard2(
            "fight_allow_map_buy",
            FIF.GLOBE,
            tr('购买代币与过期邮包'),
            '',
            texts={tr("不配置"): "不配置", tr("启用"): True, tr("停用"): False}
        )

        self.ImmortalGameGroup = SettingCardGroup(tr("逐光捡金"), self.scrollWidget)
        self.forgottenhallEnableCard = ExpandableSwitchSettingCard(
            "forgottenhall_enable",
            FIF.SPEED_HIGH,
            tr('启用混沌回忆'),
            ""
        )
        self.forgottenhallLevelCard = PushSettingCardEval(
            tr('修改'),
            FIF.MINIMIZE,
            tr("关卡范围"),
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
            tr("混沌回忆队伍配置"),
            "forgottenhall_team1",
            "forgottenhall_team2"
        )
        self.forgottenhallRunTimeCard = PushSettingCardDate(
            tr('修改'),
            FIF.DATE_TIME,
            tr("上次运行混沌回忆的时间"),
            "forgottenhall_timestamp"
        )

        self.purefictionEnableCard = ExpandableSwitchSettingCard(
            "purefiction_enable",
            FIF.SPEED_HIGH,
            tr('启用虚构叙事'),
            ""
        )
        self.purefictionLevelCard = PushSettingCardEval(
            tr('修改'),
            FIF.MINIMIZE,
            tr("关卡范围"),
            "purefiction_level"
        )
        self.purefictionTeamsCard = PushSettingCardTeamWithSwap(
            FIF.FLAG,
            tr("虚构叙事队伍配置"),
            "purefiction_team1",
            "purefiction_team2"
        )
        self.purefictionRunTimeCard = PushSettingCardDate(
            tr('修改'),
            FIF.DATE_TIME,
            tr("上次运行虚构叙事的时间"),
            "purefiction_timestamp"
        )

        self.ApocalypticEnableCard = ExpandableSwitchSettingCard(
            "apocalyptic_enable",
            FIF.SPEED_HIGH,
            tr('启用末日幻影'),
            ""
        )
        self.ApocalypticLevelCard = PushSettingCardEval(
            tr('修改'),
            FIF.MINIMIZE,
            tr("关卡范围"),
            "apocalyptic_level"
        )
        self.ApocalypticTeamsCard = PushSettingCardTeamWithSwap(
            FIF.FLAG,
            tr("末日幻影队伍配置"),
            "apocalyptic_team1",
            "apocalyptic_team2"
        )
        self.ApocalypticRunTimeCard = PushSettingCardDate(
            tr('修改'),
            FIF.DATE_TIME,
            tr("上次运行末日幻影的时间"),
            "apocalyptic_timestamp"
        )

        self.CloudGameGroup = SettingCardGroup(
            tr("云崩铁设置"),
            self.scrollWidget
        )
        self.cloudGameEnableCard = SwitchSettingCard1(
            FIF.SPEED_HIGH,
            tr("使用“云·星穹铁道”"),
            tr("开启后，将改用云·星穹铁道来执行清体力等自动化任务。无需固定窗口，可在后台运行。（模拟宇宙和锄大地仍需保持窗口全屏）"),
            "cloud_game_enable"
        )
        self.cloudGameFullScreenCard = SwitchSettingCard1(
            FIF.FULL_SCREEN,
            tr("全屏运行"),
            None,
            "cloud_game_fullscreen_enable"
        )
        self.cloudGameMaxQueueTimeCard = RangeSettingCard1(
            "cloud_game_max_queue_time",
            [1, 120],
            FIF.SPEED_MEDIUM,
            tr("最大排队等待时间（分钟）"),
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
            tr("浏览器类型"),
            tr("建议保持默认的“集成（Chrome For Testing）”效果最好"),
            {tr("集成（Chrome For Testing）"): "integrated", tr("Chrome"): "chrome", tr("Edge"): "edge"}
        )
        self.browserDownloadUseMirrorCard = SwitchSettingCard1(
            FIF.CLOUD_DOWNLOAD,
            tr("使用国内镜像下载浏览器和驱动"),
            None,
            "browser_download_use_mirror"
        )
        self.browserPersistentCard = SwitchSettingCard1(
            FIF.DOWNLOAD,
            tr("保存浏览器数据（游戏的登录状态和本地数据）"),
            None,
            "browser_persistent_enable"
        )
        self.browserScaleCard = ComboBoxSettingCard2(
            "browser_scale_factor",
            FIF.ZOOM,
            tr("浏览器画面缩放（DPI）"),
            tr("非 1920x1080 屏幕下，云游戏画面无法铺满屏幕，可以调整这个值改变画面缩放"),
            texts={'50%': 0.5, '67%': 0.67, '75%': 0.75, '80%': 0.80, '90%': 0.90, tr('无缩放（100%）'): 1.0,
                   '110%': 1.10, '125%': 1.25, '150%': 1.5, '175%': 1.75, '200%': 2.0}
        )
        self.browserLaunchArgCard = PushSettingCardEval(
            "修改",
            FIF.CODE,
            tr("浏览器启动参数"),
            "browser_launch_argument"
        )
        self.browserHeadlessCard = ExpandableSwitchSettingCard(
            "browser_headless_enable",
            FIF.VIEW,
            tr("启用无窗口模式（后台运行）"),
            tr("不支持模拟宇宙和锄大地")
        )
        self.browserHeadlessRestartCard = SwitchSettingCard1(
            FIF.SYNC,
            tr("未登录时自动切换为有窗口模式"),
            tr("开启后：在无窗口模式检测到未登录时，将自动以有窗口模式重启浏览器以便登录；关闭后：将在无窗口模式下尝试二维码登录。"),
            "browser_headless_restart_on_not_logged_in"
        )
        # self.browserCookiesCard = SwitchSettingCard1(
        #     FIF.PALETTE,    # 这个画盘长得很像 Cookie
        #     "保存 Cookies（登录状态）",
        #     None,
        #     "browser_dump_cookies_enable"
        # )

        self.ProgramGroup = SettingCardGroup(tr('程序设置'), self.scrollWidget)
        self.logLevelCard = ComboBoxSettingCardLog(
            "log_level",
            FIF.TAG,
            tr('日志等级'),
            "",
            texts={tr('简洁'): 'INFO', tr('详细'): 'DEBUG'}
        )
        self.gamePathCard = PushSettingCard(
            tr('修改'),
            FIF.GAME,
            tr("游戏路径"),
            cfg.game_path
        )
        self.updateViaLauncherEnableCard = ExpandableSwitchSettingCard(
            "update_via_launcher",
            FIF.UPDATE,
            tr('通过启动器更新游戏'),
            ""
        )
        self.launcherPathCard = PushSettingCard(
            tr('修改'),
            FIF.GAME,
            tr("米哈游启动器路径"),
            cfg.launcher_path
        )
        self.startGameTimeoutCard = RangeSettingCard1(
            "start_game_timeout",
            [10, 60],
            FIF.DATE_TIME,
            tr("启动游戏超时时间（分）"),
            "",
        )
        self.updateGameTimeoutCard = RangeSettingCard1(
            "update_game_timeout",
            [1, 24],
            FIF.DATE_TIME,
            tr("更新游戏超时时间（时）"),
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
            tr('成功后暂停程序'),
            tr("如果勾选，除非循环模式，执行成功后暂停程序。"),
            "pause_after_success"
        )
        self.exitAfterFailure = SwitchSettingCard1(
            FIF.SYNC,
            tr('失败后直接退出'),
            tr("如果勾选，那么失败后直接退出，否则失败后暂停程序。"),
            "exit_after_failure"
        )
        self.afterFinishCard = ExpandableComboBoxSettingCard(
            "after_finish",
            FIF.POWER_BUTTON,
            tr('任务完成后'),
            tr('“退出”指退出游戏，不再建议使用循环模式，请改用日志界面的定时运行功能'),
            texts={tr('无'): 'None', tr('退出'): 'Exit', tr('关机'): 'Shutdown', tr('睡眠'): 'Sleep', tr('休眠'): 'Hibernate', tr('重启')
                      : 'Restart', tr('注销'): 'Logoff', tr('关闭显示器'): 'TurnOffDisplay', tr('运行脚本'): 'RunScript', tr('循环'): 'Loop'}
        )
        self.loopModeCard = ComboBoxSettingCard2(
            "loop_mode",
            FIF.COMMAND_PROMPT,
            tr('循环模式（请改用日志界面的定时运行功能）'),
            '',
            texts={tr('定时任务'): 'scheduled', tr('根据开拓力'): 'power'}
        )
        self.scheduledCard = TimePickerSettingCard1(
            "scheduled_time",
            FIF.DATE_TIME,
            tr("定时任务时间"),
        )
        self.powerLimitCard = RangeSettingCard1(
            "power_limit",
            [10, 300],
            FIF.HEART,
            tr("循环运行再次启动所需开拓力"),
            tr("游戏刷新后优先级更高"),
        )
        self.refreshHourEnableCard = RangeSettingCard1(
            "refresh_hour",
            [0, 23],
            FIF.DATE_TIME,
            tr("游戏刷新时间"),
            tr("用于循环运行及判断任务状态，默认凌晨四点"),
        )
        self.ScriptPathCard = PushSettingCard(
            tr('修改'),
            FIF.CODE,
            tr("脚本或程序路径(选择运行脚本时生效)"),
            cfg.script_path
        )
        self.playAudioCard = SwitchSettingCard1(
            FIF.ALBUM,
            tr('声音提示'),
            tr('任务完成后列车长唱歌提示帕！'),
            "play_audio"
        )
        self.closeWindowActionCard = ComboBoxSettingCard2(
            "close_window_action",
            FIF.CLOSE,
            tr('关闭窗口时'),
            tr('选择关闭窗口时的默认行为，也可以在关闭时由对话框询问'),
            texts={tr('询问'): 'ask', tr('最小化到托盘'): 'minimize', tr('关闭程序'): 'close'}
        )
        self.windowMemoryCard = ComboBoxSettingCard2(
            "window_memory",
            FIF.LAYOUT,
            tr('窗口记忆'),
            tr('选择启动时恢复的窗口状态'),
            texts={tr('记忆窗口大小'): 'size', tr('记忆窗口位置'): 'position', tr('记忆窗口大小和位置'): 'size_and_position', tr('都不记忆'): 'none'}
        )

        self.NotifyGroup = SettingCardGroup(tr("消息推送"), self.scrollWidget)
        self.notifyMasterEnableCard = ExpandableSwitchSettingCard(
            "notification_enable",
            FIF.RINGER,
            tr("启用消息推送"),
            tr("消息推送总开关")
        )
        self.testNotifyCard = PrimaryPushSettingCard(
            tr("发送消息"),
            FIF.SEND,
            tr("测试消息推送"),
            ""
        )
        self.notifyLevelCard = ComboBoxSettingCard2(
            "notify_level",
            FIF.COMMAND_PROMPT,
            tr('通知级别'),
            '',
            texts={tr('推送所有通知'): 'all', tr('仅推送错误通知'): 'error'}
        )
        self.notifyMergeCard = SwitchSettingCard1(
            FIF.PASTE,
            tr('通知合并'),
            tr('开启后，完整运行结束时将所有通知合并为一条发送'),
            "notify_merge"
        )
        self.notifyImageEnableCard = SwitchSettingCard1(
            FIF.CAMERA,
            tr('推送图片'),
            tr('关闭后推送消息时不再发送截图'),
            "notify_send_images"
        )
        self.notifyTemplateCard = PushSettingCardNotifyTemplate(
            tr('修改'),
            FIF.FONT_SIZE,
            tr("消息推送格式"),
            "notify_template"
        )

        self.notifyEnableGroup = []
        self.notifyProviderMeta = {
            "winotify": {
                "icon": FIF.BACK_TO_WINDOW,
                "display_name": "Windows",
                "description": tr("Windows 原生通知"),
            },
            "telegram": {
                "icon": FIF.AIRPLANE,
                "display_name": "Telegram",
                "description": tr("通常需要可访问 Telegram 网络"),
                "support_image": True,
                "params": {
                    "token": {"title": tr("机器人令牌"), "description": tr("获取方式：创建 Bot → @BotFather → /newbot → 获取 Token")},
                    "userid": {"title": tr("用户/群组 ID"), "description": tr("接收通知的用户 ID 或群组 ID（以 - 开头）")},
                    "api_url": {"title": tr("自定义 API 地址"), "description": tr("可选参数，自定义 Telegram API 地址，例如 api.telegram.org")},
                    "proxies": {"title": tr("代理配置"), "description": tr("可选参数，例如 127.0.0.1:10808 或 socks5://127.0.0.1:1080，不填则使用系统 PAC 代理")},
                }
            },
            "matrix": {
                "icon": FIF.GLOBE,
                "display_name": "Matrix",
                "description": tr("适用于 Matrix 协议"),
                "support_image": True,
                "params": {
                    "homeserver": {"title": tr("服务器地址"), "description": tr("服务器地址，例如 https://matrix.org")},
                    "device_id": {"title": tr("设备 ID"), "description": tr("设备 ID，通常是 10 位大写字母或数字")},
                    "user_id": {"title": tr("用户 ID"), "description": tr("用户 ID，例如 @user:matrix.org")},
                    "access_token": {"title": tr("访问令牌"), "description": tr("登录后分配的 Access Token")},
                    "room_id": {"title": tr("房间 ID"), "description": tr("目标房间 ID，例如 !xxx:matrix.org")},
                    "proxy": {"title": tr("代理配置"), "description": tr("可选参数，例如 127.0.0.1:10808 或 socks5://127.0.0.1:1080，不填则使用系统 PAC 代理")},
                    "separately_text_media": {"title": tr("文字与图片分开发送"), "description": tr("是否分开发送文字和图片，避免部分客户端不显示文字"), "type": "bool"},
                }
            },
            "serverchanturbo": {
                "icon": FIF.ROBOT,
                "display_name": tr("Server酱·Turbo版"),
                "description": tr("微信推送，适合轻量通知"),
                "params": {
                    "sctkey": {"title": tr("SendKey"), "description": tr("在 https://sct.ftqq.com/ 获取的 SendKey")},
                    "channel": {"title": tr("发送通道"), "description": tr("可选参数")},
                    "openid": {"title": tr("接收人 OpenID"), "description": tr("可选参数")},
                }
            },
            "serverchan3": {
                "icon": FIF.ROBOT,
                "display_name": tr("Server酱³"),
                "description": tr("Server酱³ APP 推送"),
                "params": {
                    "sendkey": {"title": tr("SendKey",), "description": tr("在 https://sc3.ft07.com/ 获取的 SendKey")},
                }
            },
            "bark": {
                "icon": FIF.MAIL,
                "display_name": "Bark",
                "description": tr("适合 iOS 设备推送"),
                "params": {
                    "key": {"title": tr("推送密钥"), "description": tr("在 Bark APP 中获取的唯一标识符")},
                    "group": {"title": tr("分组名"), "description": tr("可选参数，Bark 通知的分组名")},
                    "icon": {"title": tr("图标地址"), "description": tr("可选参数，通知图标的 URL")},
                    "isarchive": {"title": tr("归档"), "description": tr("可选参数：1 归档，0 不归档")},
                    "sound": {"title": tr("提示音"), "description": tr("可选参数，自定义提示音名称")},
                    "url": {"title": tr("服务地址"), "description": tr("可选参数，自定义 Bark 服务的 URL")},
                    "copy": {"title": tr("复制内容"), "description": tr("可选参数，通知点击后复制内容")},
                    "autocopy": {"title": tr("自动复制"), "description": tr("可选参数，是否自动复制")},
                    "cipherkey": {"title": tr("加密密钥"), "description": tr("可选参数，推送加密密钥，需在 Bark APP 中配置相同的密钥")},
                    "ciphermethod": {"title": tr("加密算法"), "description": tr("可选参数，支持 cbc 或 ecb，需与 Bark APP 中配置的算法一致")},
                }
            },
            "smtp": {
                "icon": FIF.MAIL,
                "display_name": "SMTP",
                "description": tr("常用于邮箱提醒"),
                "support_image": True,
                "params": {
                    "host": {"title": tr("SMTP 服务器")},
                    "user": {"title": tr("用户名/邮箱")},
                    "password": {"title": tr("密码/授权码"), "description": tr("部分邮箱需要填写授权码（如 QQ 邮箱）")},
                    "From": {"title": tr("发件人"), "description": tr("可选参数，发件人邮箱，默认使用 user")},
                    "To": {"title": tr("收件人"), "description": tr("可选参数，收件人邮箱，默认使用 user")},
                    "port": {"title": tr("端口"), "description": tr("可选参数，端口，默认 465")},
                    "ssl": {"title": tr("启用 SSL"), "description": tr("可选参数，是否启用 SSL"), "type": "bool"},
                    "starttls": {"title": tr("启用 STARTTLS"), "description": tr("可选参数，是否启用 STARTTLS"), "type": "bool"},
                    "ssl_unverified": {"title": tr("跳过证书验证"), "description": tr("可选参数，是否跳过 SSL 证书验证"), "type": "bool"},
                }
            },
            "onebot": {
                "icon": FIF.ROBOT,
                "display_name": "OneBot",
                "description": tr("适用于 OneBot 协议"),
                "support_image": True,
                "params": {
                    "endpoint": {"title": tr("服务地址"), "description": tr("OneBot 服务端点地址，例如 http://127.0.0.1:3000")},
                    "token": {"title": tr("访问令牌"), "description": tr("可选参数，Access Token")},
                    "user_id": {"title": tr("私聊用户 ID"), "description": tr("可选参数，私聊接收用户 ID")},
                    "group_id": {"title": tr("群组 ID"), "description": tr("可选参数，群聊接收群组 ID")},
                }
            },
            "gocqhttp": {
                "icon": FIF.ROBOT,
                "display_name": "Go-cqhttp",
                "description": tr("Go-cqhttp 项目已停止维护"),
                "support_image": True,
                "params": {
                    "endpoint": {"title": tr("服务地址")},
                    "message_type": {"title": tr("消息类型"), "description": tr("消息类型：private 或 group")},
                    "token": {"title": tr("访问令牌"), "description": tr("可选参数，Access Token")},
                    "user_id": {"title": tr("私聊用户 ID"), "description": tr("可选参数，私聊接收用户 ID")},
                    "group_id": {"title": tr("群组 ID"), "description": tr("可选参数，群聊接收群组 ID")},
                }
            },
            "dingtalk": {
                "icon": FIF.MAIL,
                "display_name": tr("钉钉"),
                "description": tr("钉钉机器人推送"),
                "params": {
                    "token": {"title": tr("机器人令牌")},
                    "secret": {"title": tr("加签密钥"), "description": tr("可选参数，安全加签密钥")},
                }
            },
            "pushplus": {
                "icon": FIF.MAIL,
                "display_name": "Pushplus",
                "description": tr("Pushplus 通知服务"),
                "params": {
                    "token": {"title": tr("推送令牌")},
                    "channel": {"title": tr("推送渠道"), "description": tr("可选参数")},
                    "webhook": {"title": tr("Webhook 地址"), "description": tr("可选参数，Webhook URL")},
                    "callbackUrl": {"title": tr("回调地址"), "description": tr("可选参数，回调 URL")},
                }
            },
            "wechatworkbot": {
                "icon": FIF.MAIL,
                "display_name": tr("企业微信机器人"),
                "description": tr("企业微信机器人消息推送"),
                "support_image": True,
                "params": {
                    "key": {"title": tr("机器人 Key")},
                    "webhook_url": {"title": tr("Webhook 地址"), "description": tr("可选参数，企业微信机器人 Webhook URL")},
                }
            },
            "wechatworkapp": {
                "icon": FIF.MAIL,
                "display_name": tr("企业微信应用"),
                "description": tr("企业微信应用消息推送"),
                "support_image": True,
                "params": {
                    "corpid": {"title": tr("企业 ID")},
                    "corpsecret": {"title": tr("应用密钥")},
                    "agentid": {"title": tr("应用 AgentId")},
                    "touser": {"title": tr("接收用户"), "description": tr("可选参数，接收用户，@all 表示全员")},
                }
            },
            "gotify": {
                "icon": FIF.MAIL,
                "display_name": "Gotify",
                "description": tr("Gotify 私有通知服务"),
                "params": {
                    "url": {"title": tr("服务地址"), "description": tr("Gotify 服务器 URL，例如 https://gotify.example.com")},
                    "token": {"title": tr("访问令牌"), "description": tr("Gotify 应用的 Access Token")},
                    "priority": {"title": tr("优先级"), "description": tr("可选参数，通知优先级，范围 1-10，越高优先级越高。1-3:仅图标，4-7:图标 + 声音，8-10:图标 + 声音 + 震动")},
                }
            },
            "discord": {
                "icon": FIF.MAIL,
                "display_name": "Discord",
                "description": tr("Discord Webhook 推送"),
                "params": {
                    "webhook": {"title": tr("Webhook 地址")},
                    "username": {"title": tr("显示用户名"), "description": tr("可选参数，显示用户名")},
                    "avatar_url": {"title": tr("头像地址"), "description": tr("可选参数，头像 URL")},
                    "color": {"title": tr("消息颜色"), "description": tr("可选参数，嵌入消息颜色，十六进制颜色值（如：0x3498db）")},
                }
            },
            "pushdeer": {
                "icon": FIF.MAIL,
                "display_name": "Pushdeer",
                "description": tr("Pushdeer 通知服务"),
                "params": {
                    "token": {"title": tr("推送令牌"), "description": tr("Pushdeer Token")},
                    "url": {"title": tr("服务地址"), "description": tr("可选参数，自定义 Pushdeer 服务地址")},
                }
            },
            "lark": {
                "icon": FIF.MAIL,
                "display_name": tr("飞书"),
                "description": tr("飞书机器人推送"),
                "support_image": True,
                "params": {
                    "webhook": {"title": tr("Webhook 地址")},
                    "content": {"title": tr("消息内容")},
                    "keyword": {"title": tr("关键词"), "description": tr("可选参数，关键词安全校验内容")},
                    "sign": {"title": tr("签名"), "description": tr("可选参数，签名安全校验参数")},
                    "imageenable": {"title": tr("启用图片"), "description": tr("是否发送图片"), "type": "bool"},
                    "appid": {"title": tr("应用 AppId"), "description": tr("发送图片时必填：飞书应用 AppId")},
                    "secret": {"title": tr("应用 Secret"), "description": tr("发送图片时必填：飞书应用 Secret")},
                }
            },
            "meow": {
                "icon": FIF.ROBOT,
                "display_name": "MeoW",
                "description": tr("适合 鸿蒙NEXT 设备推送"),
                "params": {
                    "nickname": {"title": tr("昵称")},
                }
            },
            "kook": {
                "icon": FIF.ROBOT,
                "display_name": "KOOK",
                "description": tr("KOOK 机器人推送"),
                "support_image": True,
                "params": {
                    "token": {"title": tr("机器人令牌"), "description": tr("KOOK 机器人的 Token")},
                    "target_id": {"title": tr("目标 ID"), "description": tr("接收消息的用户 ID 或频道 ID")},
                    "chat_type": {"title": tr("聊天类型"), "description": tr("可选参数，1 为私聊，9 为频道")},
                }
            },
            "webhook": {
                "icon": FIF.CODE,
                "display_name": "Webhook",
                "description": tr("可自定义请求方法、请求头和请求体"),
                "support_image": True,
                "params": {
                    "url": {"title": tr("接收地址")},
                    "method": {"title": tr("请求方法"), "description": tr("可选参数，HTTP 方法，默认 POST")},
                    "headers": {"title": tr("请求头"), "description": tr('可选参数，请求头 JSON 格式字符串，如：{"Authorization": "Bearer token"}')},
                    "body": {"title": tr("请求体"), "description": tr("可选参数，请求体模板 JSON 格式字符串，支持 {title}/{content}/{image} 占位符")},
                }
            },
            "custom": {
                "icon": FIF.CODE,
                "display_name": tr("自定义通知"),
                "description": tr("自定义 HTTP 请求推送"),
                "support_image": True,
                "params": {
                    "url": {"title": tr("请求地址"), "description": tr("请求地址，OneBot 可填写 send_msg 接口 URL")},
                    "method": {"title": tr("请求方法"), "description": tr("请求方法，通常 get 或 post")},
                    "datatype": {"title": tr("数据类型"), "description": tr("数据类型，通常为 data 或 json")},
                    "image": {"title": tr("图片模板"), "description": tr("可选参数，图片消息模板，{image} 会替换为 Base64")},
                    "data": {"title": tr("数据模板"), "description": tr("请求体模板，{message} 会替换为标题和内容")},
                }
            },
        }

        self.notifyEnableGroup = []
        provider_names = self.__getNotifyProviderNames()
        for notifier_name in provider_names:
            enable_key = f"notify_{notifier_name}_enable"
            provider_meta = self.notifyProviderMeta.get(notifier_name, {})
            display_name = provider_meta.get("display_name", notifier_name.capitalize())
            support_image = tr("（支持图片）") if provider_meta.get("support_image", False) else ""
            provider_description = provider_meta.get("description", "")
            has_params = bool(provider_meta.get("params"))
            if support_image:
                provider_description = f"{provider_description} {support_image}".strip()

            if has_params:
                notifyEnableCard = ExpandableSwitchSettingCard(
                    enable_key,
                    provider_meta.get("icon", FIF.MAIL),
                    tr('启用 {} 通知').format(display_name),
                    provider_description
                )
                notifyEnableCard.switchChanged.connect(self.__refreshNotifiers)

                notifyParamCards = self.__createNotifyParamCards(notifier_name)
                if notifyParamCards:
                    notifyEnableCard.addSettingCards(notifyParamCards)
            else:
                notifyEnableCard = SwitchSettingCard1(
                    provider_meta.get("icon", FIF.MAIL),
                    tr('启用 {} 通知').format(display_name),
                    provider_description,
                    enable_key,
                    self
                )
                notifyEnableCard.switchButton.checkedChanged.connect(self.__refreshNotifiers)

            self.notifyEnableGroup.append(notifyEnableCard)

        self.MiscGroup = SettingCardGroup(tr("杂项"), self.scrollWidget)
        self.autoBattleDetectEnableCard = SwitchSettingCard1(
            FIF.ROBOT,
            tr('启用自动战斗和二倍速检测'),
            tr("游戏启动前通过修改注册表或本地存储开启自动战斗和二倍速，并在清体力、货币战争和逐光捡金场景中检测并保持自动战斗状态"),
            "auto_battle_detect_enable"
        )
        self.ocrGpuAccelerationCard = ComboBoxSettingCard2(
            "ocr_gpu_acceleration",
            FIF.SPEED_HIGH,
            tr('OCR 加速模式'),
            tr("设置 OCR 引擎与加速后端。自动模式会优先尝试 DirectML，若不可用则回退到 CPU 引擎。"),
            texts={
                tr('自动'): 'auto',
                tr('GPU'): 'gpu',
                tr('ONNXRuntime（DirectML）'): 'onnx_dml',
                tr('CPU'): 'cpu',
                tr('OpenVINO（CPU）'): 'openvino_cpu',
                tr('ONNXRuntime（CPU）'): 'onnx_cpu',
            }
        )
        self.autoSetResolutionEnableCard = SwitchSettingCard1(
            FIF.FULL_SCREEN,
            tr('启用自动修改分辨率并关闭自动 HDR'),
            tr("通过软件启动游戏会自动修改 1920x1080 分辨率并关闭自动 HDR，不影响手动启动游戏（支持国服和国际服）"),
            "auto_set_resolution_enable"
        )
        self.autoSetGamePathEnableCard = SwitchSettingCard1(
            FIF.GAME,
            tr('启用自动配置游戏路径'),
            tr("通过快捷方式、官方启动器、运行中的游戏进程等方式尝试自动配置游戏路径（支持国服和国际服）"),
            "auto_set_game_path_enable"
        )
        self.useBackgroundScreenshotCard = SwitchSettingCard1(
            FIF.CAMERA,
            tr('优先使用后台截图'),
            tr("默认开启，可以避免悬浮窗等干扰"),
            "use_background_screenshot"
        )
        if sys.platform == 'win32':
            self.StartMarch7thAssistantCard = StartMarch7thAssistantSwitchSettingCard(
                FIF.GAME,
                tr('在用户登录时启动'),
                tr("通过任务计划程序在开机后自动执行完整运行模式（可能还需要自行配置电脑无需输入密码自动登录）")
            )
        self.hotkeyCard = SwitchSettingCardHotkey(
            FIF.SETTING,
            tr('修改按键'),
            tr("配置秘技、地图、跃迁、停止任务等按键设置")
        )

        self.AboutGroup = SettingCardGroup(tr('关于'), self.scrollWidget)
        self.githubCard = PrimaryPushSettingCard(
            tr('项目主页'),
            FIF.GITHUB,
            tr('项目主页'),
            "https://github.com/moesnow/March7thAssistant"
        )
        self.bilibiliCard = PrimaryPushSettingCard(
            tr('立即前往'),
            FIF.MOVIE,
            tr('哔哩哔哩'),
            tr('欢迎关注我们的B站账号，获取最新动态和教程')
        )
        self.qqGroupCard = PrimaryPushSettingCard(
            tr('加入群聊'),
            FIF.EXPRESSIVE_INPUT_ENTRY,
            tr('QQ群'),
            ""
        )
        # self.feedbackCard = PrimaryPushSettingCard(
        #     tr('提供反馈'),
        #     FIF.FEEDBACK,
        #     tr('提供反馈'),
        #     tr('帮助我们改进 March7thAssistant')
        # )
        self.aboutCard = PrimaryPushSettingCard(
            tr('检查更新'),
            FIF.INFO,
            tr('关于'),
            tr('当前版本：') + " " + cfg.version
        )
        self.updateSourceCard = ExpandableComboBoxSettingCardUpdateSource(
            "update_source",
            FIF.SPEED_HIGH,
            tr('更新源'),
            self.parent,
            "",
            texts={tr('海外源'): 'GitHub', tr('Mirror 酱'): 'MirrorChyan'}
        )
        self.checkUpdateCard = SwitchSettingCard1(
            FIF.SYNC,
            tr('启动时检测更新'),
            "",
            "check_update"
        )
        self.updatePrereleaseEnableCard = SwitchSettingCard1(
            FIF.TRAIN,
            tr('加入预览版更新渠道'),
            "",
            "update_prerelease_enable"
        )
        self.updateFullEnableCard = SwitchSettingCard1(
            FIF.GLOBE,
            tr('更新时下载完整包'),
            tr("更新将包含依赖组件，建议保持开启。若关闭此选项，需自行手动更新依赖组件，可能会导致出现不可预期的错误。"),
            "update_full_enable"
        )
        self.updateDownloadProxyCard = PushSettingCardStr(
            tr('修改'),
            FIF.GLOBE,
            tr("下载代理"),
            "update_download_proxy",
            empty_content=tr("留空则使用系统代理；支持 http:// 和 socks5://")
        )
        self.mirrorchyanCdkCard = PushSettingCardMirrorchyan(
            tr('修改'),
            FIF.BOOK_SHELF,
            tr("Mirror 酱 CDK"),
            self.parent,
            "mirrorchyan_cdk"
        )
        self.languageCard = ComboBoxSettingCardLanguage(
            "ui_language",
            FIF.LANGUAGE,
            '界面语言 / 界面語言 / 日本語 / 인터페이스 언어 / UI Language',
            '切换后即时生效 / 切換後即時生效 / 切り替え後すぐ適用 / 변경 즉시 적용 / Takes effect immediately',
            texts={'自动': 'auto', '简体中文': 'zh_CN', '繁體中文': 'zh_TW', '日本語': 'ja_JP', '한국어': 'ko_KR', 'English': 'en_US'}
        )

    def __initLayout(self):
        self.settingLabel.move(36, 30)
        # pivot 位于 pivotScrollArea 内；x=40 与标题对齐，y=80 与原位置一致
        # height=54：pivot ~46px + 8px 供 AsNeeded 滚动条偶尔占用，底边 y=134
        # setViewportMargins(0, 140, ...) 保留 6px 间距，不影响内容区域
        self.pivotScrollArea.move(40, 80)
        self.pivotScrollArea.setFixedHeight(46)  # pivot 本身高度，无需为滚动条留空
        # ── 关键修复：构造时必须给 scroll area 设置初始宽度 ──────────────
        # self.width() 在 __init__ 期间为 0（QWidget 尚未布局），
        # 但 self.parent 是已显示的 MainWindow，其宽度有效（≥960）。
        # 若无法取到父宽度则回退到最小窗口宽度 960。
        # resizeEvent 会在窗口缩放时持续更新该值。
        try:
            initial_w = self.parent.width() if self.parent and self.parent.width() > 0 else 960
        except Exception:
            initial_w = 960
        self.pivotScrollArea.setFixedWidth(max(initial_w - 40, 400))
        # self.title_area.move(36, 80)
        # self.vBoxLayout.addWidget(self.pivot, 0, Qt.AlignTop)
        self.vBoxLayout.addWidget(self.stackedWidget, 0, Qt.AlignmentFlag.AlignTop)
        self.vBoxLayout.setContentsMargins(36, 0, 36, 0)

        self.PowerGroup.addSettingCard(self.powerPlanCard)
        self.PowerGroup.addSettingCard(self.instanceTypeCard)
        # self.PowerGroup.addSettingCard(self.calyxGoldenPreferenceCard)
        self.PowerGroup.addSettingCard(self.instanceTypeCard)
        self.instanceTypeCard.addSettingCards([
            self.instanceTeamEnableCard,
            self.tpBeforeInstanceEnableCard,
            self.useReservedTrailblazePowerEnableCard,
            self.useFuelEnableCard,
            self.breakDownLevelFourRelicsetEnableCard,
            self.mergeImmersifierEnableCard,
            self.instanceNameChallengeCountCard
        ])
        self.PowerGroup.addSettingCard(self.instanceNameCard)
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
            self.buildTargetSchemeCard,
            self.buildTargetPlanarOrnamentWeeklyCountCard,
            self.buildTargetUseUserInstanceWhenOnlyErosionAndOrnamentCard
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
            self.activityPlanarFissureEnableCard,
            self.activityJourneyHighlightsNotificationEnableCard
        ])
        self.DailyGroup.addSettingCard(self.rewardEnableCard)
        self.rewardEnableCard.addSettingCards([
            self.dispatchEnableCard,
            self.mailEnableCard,
            self.assistEnableCard,
            self.questEnableCard,
            self.srpassEnableCard,
            self.redemptionEnableCard,
            self.achievementEnableCard,
            self.messageEnableCard
        ])
        self.DailyGroup.addSettingCard(self.assetEnableCard)
        self.assetEnableCard.addSettingCards(
            [
                self.lc3StarSuperimposeEnableCard,
            ]
        )

        self.CurrencywarsGroup.addSettingCard(self.currencywarsEnableCard)
        self.currencywarsEnableCard.addSettingCards([
            self.currencywarsRunTimeCard
        ])
        self.CurrencywarsGroup.addSettingCard(self.currencywarsPresetCard)
        self.CurrencywarsGroup.addSettingCard(self.currencywarsTypeCard)
        self.CurrencywarsGroup.addSettingCard(self.currencywarsBonusEnableCard)
        self.CurrencywarsGroup.addSettingCard(self.currencywarsRankDifficultyCard)
        self.CurrencywarsGroup.addSettingCard(self.currencywarsStrategyCard)
        self.currencywarsStrategyCard.addSettingCards([
            self.currencywarsRemembranceTrailblazerNameCard,
            self.currencywarsStrategyRestartOnSpecialTagsCard,
            self.currencywarsFastModeCard
        ])

        self.UniverseGroup.addSettingCard(self.weeklyDivergentEnableCard)
        self.weeklyDivergentEnableCard.addSettingCards([
            self.weeklyDivergentRunTimeCard
        ])
        self.UniverseGroup.addSettingCard(self.weeklyDivergentTypeCard)
        self.UniverseGroup.addSettingCard(self.weeklyDivergentBonusEnableCard)
        self.UniverseGroup.addSettingCard(self.weeklyDivergentLevelCard)
        self.UniverseGroup.addSettingCard(self.stationPriorityCard)
        self.UniverseGroup.addSettingCard(self.weeklyDivergentStableModeCard)

        self.UniverseGroup.addSettingCard(self.universeEnableCard)
        self.universeEnableCard.addSettingCards([
            self.universeCategoryCard,
            self.divergentTypeCard,
            self.universeBonusEnableCard,
            self.universeFrequencyCard,
            self.universeCountCard,
            self.universeFateCard,
            self.universeDifficultyCard,
            self.universeOperationModeCard,
            self.universeEnableGpuCard,
            self.universeTimeoutCard,
            self.universeRunTimeCard,
        ])
        # self.UniverseGroup.addSettingCard(self.divergentTeamTypeCard)

        self.FightGroup.addSettingCard(self.fightEnableCard)
        self.fightEnableCard.addSettingCards([
            self.fightOperationModeCard,
            self.fightTimeoutCard,
            self.FightRunTimeCard,
        ])
        self.FightGroup.addSettingCard(self.fightTeamEnableCard)
        # self.FightGroup.addSettingCard(self.fightTeamNumberCard)
        self.FightGroup.addSettingCard(self.fightMapVersionCard)
        self.FightGroup.addSettingCard(self.fightMainMapCard)
        self.FightGroup.addSettingCard(self.fightAllowSnackBuyCard)
        self.FightGroup.addSettingCard(self.fightAllowMapBuyCard)

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
        self.ProgramGroup.addSettingCard(self.windowMemoryCard)

        self.NotifyGroup.addSettingCard(self.notifyMasterEnableCard)
        self.notifyMasterEnableCard.addSettingCards([
            self.testNotifyCard,
            self.notifyLevelCard,
            self.notifyMergeCard,
            self.notifyImageEnableCard,
            self.notifyTemplateCard
        ])
        for value in self.notifyEnableGroup:
            self.NotifyGroup.addSettingCard(value)

        self.MiscGroup.addSettingCard(self.autoBattleDetectEnableCard)
        self.MiscGroup.addSettingCard(self.ocrGpuAccelerationCard)
        self.MiscGroup.addSettingCard(self.autoSetResolutionEnableCard)
        self.MiscGroup.addSettingCard(self.autoSetGamePathEnableCard)
        self.MiscGroup.addSettingCard(self.useBackgroundScreenshotCard)
        if sys.platform == 'win32':
            self.MiscGroup.addSettingCard(self.StartMarch7thAssistantCard)
        self.MiscGroup.addSettingCard(self.hotkeyCard)

        self.AboutGroup.addSettingCard(self.githubCard)
        self.AboutGroup.addSettingCard(self.bilibiliCard)
        self.AboutGroup.addSettingCard(self.qqGroupCard)
        # self.AboutGroup.addSettingCard(self.feedbackCard)
        self.AboutGroup.addSettingCard(self.aboutCard)
        self.AboutGroup.addSettingCard(self.updateSourceCard)
        self.updateSourceCard.addSettingCards([
            self.checkUpdateCard,
            self.updatePrereleaseEnableCard,
            self.updateFullEnableCard,
            self.updateDownloadProxyCard
        ])
        self.AboutGroup.addSettingCard(self.mirrorchyanCdkCard)
        self.AboutGroup.addSettingCard(self.languageCard)

        if sys.platform != 'win32':
            self.gamePathCard.setHidden(True)
            self.updateViaLauncherEnableCard.setHidden(True)
            self.autoSetResolutionEnableCard.setHidden(True)
            self.autoSetGamePathEnableCard.setHidden(True)
            self.useBackgroundScreenshotCard.setHidden(True)
            self.cloudGameEnableCard.setDisabled(True)  # 在配置文件中强制启用，禁止用户修改

        self.addSubInterface(self.PowerGroup, 'PowerInterface', tr('体力'))
        # self.addSubInterface(self.BorrowGroup, 'BorrowInterface', '支援')
        self.addSubInterface(self.DailyGroup, 'DailyInterface', tr('日常'))
        self.addSubInterface(self.CurrencywarsGroup, 'CurrencywarsInterface', tr('货币战争'))
        if sys.platform == 'win32':
            self.addSubInterface(self.UniverseGroup, 'UniverseInterface', tr('差分宇宙'))
            self.addSubInterface(self.FightGroup, 'FightInterface', tr('锄大地'))
        else:
            self.UniverseGroup.setHidden(True)
            self.FightGroup.setHidden(True)
        self.addSubInterface(self.ImmortalGameGroup, 'ImmortalGameInterface', tr('逐光捡金'))

        self.pivot.addItem(
            routeKey='verticalBar',
            text="|",
            onClick=lambda: self.pivot.setCurrentItem(self.stackedWidget.currentWidget().objectName()),
        )

        self.addSubInterface(self.ProgramGroup, 'programInterface', tr('程序'))
        self.addSubInterface(self.CloudGameGroup, "cloudGameInterface", tr('云游戏'))
        self.addSubInterface(self.NotifyGroup, 'NotifyInterface', tr('推送'))
        self.addSubInterface(self.MiscGroup, 'KeybindingInterface', tr('杂项'))
        if sys.platform == 'win32':
            self.addSubInterface(
                accounts_interface(self.tr, self.scrollWidget),
                'AccountsInterface',
                tr('账号')
            )
        self.addSubInterface(self.AboutGroup, 'AboutInterface', tr('关于'))

        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.pivot.setCurrentItem(self.stackedWidget.currentWidget().objectName())
        self.stackedWidget.setFixedHeight(self.stackedWidget.currentWidget().sizeHint().height())

        # ── pivot 尺寸与滚动过滤器 ────────────────────────────────────
        # 所有 addItem 调用完成后 pivot 才能计算正确宽度
        self.pivot.adjustSize()
        # 将滚动/拖拽过滤器安装到 pivot 本身及其所有子控件（tab 按钮）
        # 只在 viewport 上安装不够：tab 子控件直接收到鼠标事件，不经过 viewport
        self._pivot_scroll_filter = _PivotScrollFilter(self.pivotScrollArea, self.pivot)
        self.pivot.installEventFilter(self._pivot_scroll_filter)
        for child in self.pivot.findChildren(QWidget):
            child.installEventFilter(self._pivot_scroll_filter)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 随窗口宽度同步 pivot 滚动容器宽度（right margin = 40px 与布局对齐）
        if self.width() > 0:
            self.pivotScrollArea.setFixedWidth(max(self.width() - 40, 400))

    def __connectSignalToSlot(self):
        # self.importConfigCard.clicked.connect(self.__onImportConfigCardClicked)
        self.gamePathCard.clicked.connect(self.__onGamePathCardClicked)
        self.launcherPathCard.clicked.connect(self.__onLauncherPathCardClicked)
        self.ScriptPathCard.clicked.connect(self.__onScriptPathCardClicked)
        self.currencywarsPresetCard.leftClicked.connect(self.__applyCurrencywarsPromotionPreset)
        self.currencywarsPresetCard.rightClicked.connect(self.__applyCurrencywarsRankPreset)
        # self.borrowCharacterInfoCard.clicked.connect(self.__openCharacterFolder())

        self.testNotifyCard.clicked.connect(lambda: start_task("notify"))
        self.notifyMasterEnableCard.switchChanged.connect(self.__refreshNotifiers)

        self.afterFinishCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)

        self.githubCard.clicked.connect(self.__openUrl("https://github.com/moesnow/March7thAssistant"))
        self.qqGroupCard.clicked.connect(self.__openUrl("https://qm.qq.com/q/C3IryUWCQw"))
        # self.feedbackCard.clicked.connect(self.__openUrl("https://github.com/moesnow/March7thAssistant/issues"))
        self.bilibiliCard.clicked.connect(self.__openUrl("https://space.bilibili.com/3706960664857075"))

        self.aboutCard.clicked.connect(lambda: checkUpdate(self.parent))

        # 连接可展开卡片的展开状态改变信号，在动画前调整 stackedWidget 高度
        self.borrowEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.buildTargetEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.dailyEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.activityEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.rewardEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.assetEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.currencywarsEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.currencywarsStrategyCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.fightEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.weeklyDivergentEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.universeEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.forgottenhallEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.purefictionEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.ApocalypticEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.updateViaLauncherEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.updateSourceCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.notifyMasterEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        for notify_card in self.notifyEnableGroup:
            if hasattr(notify_card, "expandStateChanged"):
                notify_card.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.instanceTypeCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.echoofwarEnableCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.browserTypeCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)
        self.browserHeadlessCard.expandStateChanged.connect(self.__onExpandableCardStateChanged)

    def __getNotifyProviderNames(self):
        provider_names = []
        for key in cfg.config.keys():
            if key.startswith("notify_") and key.endswith("_enable"):
                notifier_name = key[len("notify_"):-len("_enable")]
                if sys.platform != 'win32' and notifier_name == 'winotify':
                    continue
                provider_names.append(notifier_name)

        order_map = {name: index for index, name in enumerate(self.notifyProviderMeta.keys())}
        return sorted(provider_names, key=lambda name: (order_map.get(name, 999), name))

    def __createNotifyParamCards(self, notifier_name):
        param_cards = []
        prefix = f"notify_{notifier_name}_"
        enable_key = f"notify_{notifier_name}_enable"

        for key in cfg.config.keys():
            if not key.startswith(prefix) or key == enable_key:
                continue

            param_name = key[len(prefix):]
            param_meta = self.notifyProviderMeta.get(notifier_name, {}).get("params", {}).get(param_name, {})
            if "description" in param_meta:
                param_description = param_meta.get("description", "")
            elif param_meta:
                param_description = ""
            else:
                param_description = tr("该参数用于配置该通知方式的请求字段")
            param_title = param_meta.get("title", param_name)
            param_type = param_meta.get("type", "text")

            if param_type == "bool":
                # self.__normalizeNotifyBoolConfigValue(key)
                notify_param_card = SwitchSettingCard1(
                    FIF.CHECKBOX,
                    param_title,
                    param_description,
                    key,
                    self
                )
                notify_param_card.switchButton.checkedChanged.connect(self.__refreshNotifiers)
            else:
                notify_param_card = CustomPushSettingCard(
                    tr('修改'),
                    FIF.EDIT,
                    param_title,
                    key,
                    param_description,
                    self
                )
                notify_param_card.button.clicked.connect(
                    lambda _, card=notify_param_card: self.__onNotifyParamCardClicked(card)
                )
            param_cards.append(notify_param_card)

        return param_cards

    def __onNotifyParamCardClicked(self, card):
        current_value = cfg.get_value(card.configname)
        message_box = MessageBoxEdit(card.title, str(current_value), self.window())
        if message_box.exec():
            cfg.set_value(card.configname, self.__parseNotifyValue(message_box.getText()))
            self.__refreshNotifiers()

    def __parseNotifyValue(self, input_text):
        try:
            return eval(input_text)
        except (SyntaxError, NameError, ValueError):
            return input_text

    def __normalizeNotifyBoolConfigValue(self, configname):
        value = cfg.get_value(configname)
        if isinstance(value, bool):
            return

        normalized = False
        if isinstance(value, str):
            text = value.strip().lower()
            if text in {"1", "true", "yes", "on"}:
                normalized = True
            elif text in {"0", "false", "no", "off", "", "none", "null"}:
                normalized = False
            else:
                normalized = bool(text)
        else:
            normalized = bool(value)

        cfg.set_value(configname, normalized)

    def __refreshNotifiers(self, *_):
        try:
            init_notifiers()
        except Exception:
            pass

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
        game_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("选择游戏路径"),
            "",
            tr("脚本或可执行文件 (*.exe *.bat *.cmd *.ps1)")
        )
        if not game_path or cfg.game_path == game_path:
            return
        cfg.set_value("game_path", game_path)
        self.gamePathCard.setContent(game_path)

    def __onLauncherPathCardClicked(self):
        launcher_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("选择米哈游启动器路径"),
            "",
            tr("脚本或可执行文件 (*.exe *.bat *.cmd *.ps1)")
        )
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
        script_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("脚本或程序路径"),
            "",
            tr("脚本或可执行文件 (*.exe *.bat *.cmd *.ps1)")
        )
        if not script_path or cfg.script_path == script_path:
            return
        cfg.set_value("script_path", script_path)
        self.ScriptPathCard.setContent(script_path)

    def __setComboBoxCardValue(self, card, value):
        for index in range(card.comboBox.count()):
            if card.comboBox.itemData(index) != value:
                continue

            if card.comboBox.currentIndex() != index:
                card.comboBox.setCurrentIndex(index)
            else:
                cfg.set_value(card.configname, value)
            return

        cfg.set_value(card.configname, value)

    def __setSwitchCardValue(self, card, value):
        if card.switchButton.isChecked() != value:
            card.switchButton.setChecked(value)
            return

        card.setValue(value)
        cfg.set_value(card.configname, value)

    def __applyCurrencywarsPromotionPreset(self):
        self.__setComboBoxCardValue(self.currencywarsTypeCard, 'overclock')
        self.__setComboBoxCardValue(self.currencywarsRankDifficultyCard, 'lowest')
        self.__setComboBoxCardValue(self.currencywarsStrategyCard, 'default')
        self.__setSwitchCardValue(self.currencywarsFastModeCard, True)
        InfoBar.success(
            title=tr('已应用快捷配置'),
            content=tr('当前为“提升晋升等级”模式'),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def __applyCurrencywarsRankPreset(self):
        self.__setComboBoxCardValue(self.currencywarsTypeCard, 'normal')
        self.__setComboBoxCardValue(self.currencywarsRankDifficultyCard, 'highest')
        self.__setComboBoxCardValue(self.currencywarsStrategyCard, 'aglaea')
        self.__setSwitchCardValue(self.currencywarsFastModeCard, False)
        InfoBar.success(
            title=tr('已应用快捷配置'),
            content=tr('当前为“提升职级等级”模式'),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

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
