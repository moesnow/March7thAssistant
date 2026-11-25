"""Metadata for the existing desktop settings. Importing this module only reads Python data."""
from dataclasses import KW_ONLY, dataclass
from enum import StrEnum
from functools import partial

from module.channel_catalog import CHANNELS
from module.content_pages import GROUP_BY_ID, PAGE_BY_ID


class Scope(StrEnum):
    GLOBAL = 'GLOBAL'
    PLAN = 'PLAN'
    STATE = 'STATE'
    SECRET = 'SECRET'


@dataclass(frozen=True)
class Setting:
    widget: str  # Attribute path on the page host, empty for controls supplied by the page.
    title: str
    page: str
    section: str
    keys: tuple[str, ...] = ()
    _: KW_ONLY
    link_id: str = ''  # Stable link for actions without a configuration key.
    scope: Scope
    state_keys: tuple[str, ...] = ()
    secret_keys: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()

    role: str = 'card'
    doc: str = ''

    @property
    def id(self):
        return self.keys[0] if self.keys else (self.link_id or self.widget)

    @property
    def destination(self):
        page = PAGE_BY_ID[self.page]
        group = GROUP_BY_ID[self.page, self.section]
        prefix = {'setting': '设置', 'task': '任务'}.get(page.kind)
        return ' › '.join(filter(None, (prefix, page.name, group.title)))

    @property
    def link(self):
        if self.page == 'run':
            return 'run:schedule'
        if PAGE_BY_ID[self.page].kind == 'task':
            return f'task:{self.page}#{self.id}'
        return f'setting:{self.id}'

    def key_scope(self, key: str) -> Scope:
        if key in self.state_keys:
            return Scope.STATE
        if key in self.secret_keys:
            return Scope.SECRET
        return self.scope


_plan = partial(Setting, scope=Scope.PLAN)
_global = partial(Setting, scope=Scope.GLOBAL)


def _channel(channel):
    title = f'启用 {channel.name} 通知'
    yield _global('', title, 'notify', 'channels', (channel.enable_key,), role='channel')
    for field in channel.fields:
        yield _global('', field.label, 'notify', 'channels', (field.key,), role='channel',
                      scope=Scope.SECRET if field.secret else Scope.GLOBAL)
    if channel.id == 'qqbot':
        yield _global('', '自动绑定收件标识', 'notify', 'channels', (), role='channel', link_id='qqbot_bind')


SETTINGS = (
    # 体力
    _plan('', '启用清体力', 'power', 'header', ('power_enable', 'overview_power'),
        state_keys=('overview_power',), role='header'),
    _plan('powerPlanCard', '体力计划', 'power', 'instances', ('power_plan', 'power_plan_keep', 'power_plan_continue'),
        doc='doc:Tutorial#副本类型--副本名称'),
    _plan('instanceTypeCard', '副本类型', 'power', 'instances', ('instance_type',), doc='doc:Tutorial#副本类型--副本名称'),
    _plan('instanceTeamEnableCard', '自动切换队伍', 'power', 'battle',
        ('instance_team_enable', 'instance_team_number', 'instance_teams')),
    _plan('tpBeforeInstanceEnableCard', '清体力前传送至任意锚点', 'power', 'battle', ('tp_before_instance',)),
    _plan('useReservedTrailblazePowerEnableCard', '使用后备开拓力', 'power', 'refill',
        ('use_reserved_trailblaze_power',), doc='doc:Tutorial#使用后备开拓力--使用燃料'),
    _plan('useFuelEnableCard', '使用燃料', 'power', 'refill', ('use_fuel',), doc='doc:Tutorial#使用后备开拓力--使用燃料'),
    _plan('preferFuelTicketsCard', '优先使用助燃券（实验）', 'power', 'refill', ('prefer_fuel_tickets',)),
    _plan('weeklyRelicCleanupEnableCard', '每周清理遗器', 'assets', 'relics',
        ('break_down_level_four_relicset', 'weekly_relic_cleanup_day_of_week')),
    _plan('smartRelicDiscardEnableCard', '启用智能弃置', 'assets', 'relics', ('weekly_relic_smart_discard_enable',)),
    _plan('relicBagCleanupCard', '满包时自动分解遗器', 'assets', 'relics', ('relic_bag_cleanup_enable',)),
    _plan('instanceNameChallengeCountCard', '副本最大连续挑战次数（通常不建议修改保持默认即可）', 'power', 'battle',
        ('instance_names_challenge_count',)),
    _plan('instanceNameCard', '副本名称', 'power', 'instances', ('instance_names',), doc='doc:Tutorial#副本类型--副本名称'),
    _plan('borrowEnableCard', '启用使用支援角色', 'power', 'battle', ('borrow_enable',), doc='doc:Tutorial#支援角色'),
    _plan('borrowCharacterEnableCard', '强制使用支援角色', 'power', 'battle', ('borrow_character_enable',)),
    _plan('borrowFriendsCard', '支援列表', 'power', 'battle', ('borrow_friends',)),
    _plan('borrowScrollTimesCard', '滚动查找次数', 'power', 'battle', ('borrow_scroll_times',)),
    _plan('buildTargetEnableCard', '启用培养目标', 'power', 'instances', ('build_target_enable',), doc='doc:Tutorial#培养目标'),
    _plan('buildTargetSchemeCard', '识别方案', 'power', 'instances', ('build_target_scheme',)),
    _plan('buildTargetPlanarOrnamentWeeklyCountCard', '每周饰品提取次数', 'power', 'instances',
        ('build_target_ornament_weekly_count',)),
    _plan('buildTargetUseUserInstanceWhenOnlyErosionAndOrnamentCard', '仅识别到侵蚀隧洞/饰品提取时使用自定义副本', 'power', 'instances',
        ('build_target_use_user_instance_when_only_erosion_and_ornament',)),
    _plan('', '启用历战余响', 'echo', 'header', ('echo_of_war_enable',), role='header', doc='doc:Tutorial#历战余响'),
    _plan('echoStartDayCard', '周几开始执行历战余响', 'echo', 'schedule', ('echo_of_war_start_day_of_week',)),
    _plan('', '上次完成历战余响的时间', 'echo', 'header', ('echo_of_war_timestamp',),
        scope=Scope.STATE, role='state'),

    # 日常
    _plan('', '启用每日实训', 'daily', 'header', ('daily_enable', 'last_run_timestamp', 'overview_daily_activity'),
        state_keys=('last_run_timestamp', 'overview_daily_activity'), role='header'),
    _plan('dailyMaterialEnableCard', '通过 “合成材料” 完成任务', 'daily', 'training', ('daily_material_enable',)),
    _plan('dailyMemoryOneEnableCard', '通过 “回忆一” 完成任务', 'daily', 'training', ('daily_memory_one_enable',)),
    _plan('dailyMemoryOneTeamCard', '回忆一队伍', 'daily', 'training', ('daily_memory_one_team',)),
    _plan('', '启用活动检测', 'activity', 'header', ('activity_enable',), role='header'),
    _plan('activityDailyCheckInEnableCard', '每日签到', 'activity', 'events', ('activity_dailycheckin_enable',)),
    _plan('activityGardenOfPlentyEnableCard', '花藏繁生', 'activity', 'events',
        ('activity_gardenofplenty_enable', 'activity_gardenofplenty_instance_type')),
    _plan('activityRealmOfTheStrangeEnableCard', '异器盈界', 'activity', 'events', ('activity_realmofthestrange_enable',)),
    _plan('activityPlanarFissureEnableCard', '位面分裂', 'activity', 'events', ('activity_planarfissure_enable',)),
    _plan('activityJourneyHighlightsNotificationEnableCard', '活动热点通知', 'activity', 'events',
        ('activity_journey_highlights_notification_enable',)),
    _plan('', '启用奖励领取', 'reward', 'header', ('reward_enable',), role='header'),
    _plan('', '委托', 'reward', 'items', ('reward_dispatch_enable',), role='check'),
    _plan('', '邮件', 'reward', 'items', ('reward_mail_enable',), role='check'),
    _plan('', '支援', 'reward', 'items', ('reward_assist_enable',), role='check'),
    _plan('', '每日实训', 'reward', 'items', ('reward_quest_enable',), role='check'),
    _plan('', '无名勋礼', 'reward', 'items', ('reward_srpass_enable',), role='check'),
    _plan('', '兑换码', 'reward', 'items', ('reward_redemption_code_enable',), role='check'),
    _plan('', '成就', 'reward', 'items', ('reward_achievement_enable',), role='check'),
    _plan('', '短信', 'reward', 'items', ('reward_message_enable',), role='check'),
    _plan('', '启用资产管理', 'assets', 'header', ('asset_manager_enable',), role='header'),
    _plan('selfMoldingResinEnableCard', '启用「每月自动合成自塑尘脂」', 'assets', 'monthly',
        ('asset_self_molding_resin_enable', 'asset_self_molding_resin_timestamp'),
        state_keys=('asset_self_molding_resin_timestamp',)),
    _plan('emberSpecialPassEnableCard', '启用「每月自动购买星轨专票」', 'assets', 'monthly',
        ('asset_ember_special_pass_enable', 'asset_ember_special_pass_timestamp'),
        state_keys=('asset_ember_special_pass_timestamp',)),
    _plan('emberRegularPassEnableCard', '启用「每月自动购买星轨通票」', 'assets', 'monthly',
        ('asset_ember_regular_pass_enable', 'asset_ember_regular_pass_timestamp'),
        state_keys=('asset_ember_regular_pass_timestamp',)),
    _plan('emberTracksOfDestinyEnableCard', '启用「每月自动购买命运的足迹」', 'assets', 'monthly',
        ('asset_ember_tracks_of_destiny_enable', 'asset_ember_tracks_of_destiny_timestamp'),
        state_keys=('asset_ember_tracks_of_destiny_timestamp',)),
    _plan('lc3StarSuperimposeEnableCard', '启用「3星光锥自动叠加」', 'assets', 'materials', ('asset_lc3_star_superimpose_enable',)),

    # 货币战争
    _plan('', '启用「货币战争」积分奖励', 'currencywars', 'header',
        ('currencywars_enable', 'currencywars_timestamp'), state_keys=('currencywars_timestamp',), role='header'),
    _plan('', '快捷配置', 'currencywars', 'header', role='header', link_id='currencywarsPresetCard'),
    _plan('currencywarsTypeCard', '类别', 'currencywars', 'strategy', ('currencywars_type',)),
    _plan('currencywarsBonusEnableCard', '自动执行位面饰品快速提取', 'currencywars', 'strategy', ('currencywars_bonus_enable',)),
    _plan('currencywarsRankDifficultyCard', '职级难度', 'currencywars', 'strategy', ('currencywars_rank_difficulty',)),
    _plan('', '请更新货币战争策略', 'currencywars', 'header', role='header', link_id='currencywarsStrategyCard'),
    _plan('currencywarsStrategySelectCard', '货币战争策略', 'currencywars', 'strategy', ('currencywars_strategy',)),
    _plan('currencywarsInvestmentPriorityCard', '投资选项优先级', 'currencywars', 'strategy',
        ('currencywars_investment_priority',)),
    _plan('currencywarsUnfinishedMatchCard', '未完成对局', 'currencywars', 'strategy', ('currencywars_unfinished_match',)),
    _plan('currencywarsFastModeCard', '启用速通模式', 'currencywars', 'advanced', ('currencywars_fast_mode',)),
    _plan('currencywarsTimeLimitCard', '总时限', 'currencywars', 'advanced', ('currencywars_time_limit',)),

    # 差分宇宙
    _plan('', '启用「差分宇宙」积分奖励', 'universe', 'header',
        ('weekly_divergent_enable', 'weekly_divergent_timestamp'), state_keys=('weekly_divergent_timestamp',), role='header'),
    _plan('weeklyDivergentTypeCard', '类别', 'universe', 'points', ('weekly_divergent_type',)),
    _plan('weeklyDivergentBonusEnableCard', '自动执行饰品提取', 'universe', 'points', ('weekly_divergent_bonus_enable',)),
    _plan('weeklyDivergentLevelCard', '难度等级', 'universe', 'points', ('weekly_divergent_level',)),
    _plan('stationPriorityCard', '站点优先级', 'universe', 'points',
        ('divergent_station_priority_enable', 'divergent_station_priority', 'divergent_station_disabled')),
    _plan('weeklyDivergentStableModeCard', '启用低性能兼容模式', 'universe', 'points', ('weekly_divergent_stable_mode',)),
    _plan('divergentAutoSaveCard', '自动记录差分宇宙存档', 'universe', 'points', ('divergent_auto_save_enable',)),
    _plan('universeEnableCard', '启用模拟宇宙/差分宇宙 (Auto_Simulated_Universe)', 'universe', 'external',
        ('universe_enable',)),
    _plan('universeCategoryCard', '类别', 'universe', 'external', ('universe_category',)),
    _plan('divergentTypeCard', '选择差分宇宙时类别', 'universe', 'external', ('divergent_type',)),
    _plan('universeBonusEnableCard', '自动领取模拟宇宙沉浸奖励', 'universe', 'external', ('universe_bonus_enable',)),
    _plan('universeFrequencyCard', '运行频率', 'universe', 'external', ('universe_frequency',)),
    _plan('universeCountCard', '运行次数', 'universe', 'external', ('universe_count',)),
    _plan('', '差分宇宙已完成次数', 'universe', 'external',
        ('divergent_universe_daily_completed_count',
         'divergent_universe_daily_completed_timestamp',
         'divergent_universe_weekly_completed_count',
         'divergent_universe_weekly_completed_timestamp',),
        scope=Scope.STATE, role='state'),
    _plan('universeFateCard', '命途（仅模拟宇宙生效）', 'universe', 'external', ('universe_fate',)),
    _plan('universeDifficultyCard', '难度 (0为不配置，仅模拟宇宙生效)', 'universe', 'external', ('universe_difficulty',)),
    _plan('universeOperationModeCard', '运行模式', 'universe', 'external', ('universe_operation_mode',)),
    _plan('universeEnableGpuCard', '启用模拟宇宙 GPU 加速', 'universe', 'external',
        ('universe_enable_gpu',)),
    _plan('universeTimeoutCard', '模拟宇宙/差分宇宙超时', 'universe', 'external', ('universe_timeout',)),
    _plan('', '上次运行模拟宇宙/差分宇宙的时间', 'universe', 'external', ('universe_timestamp',), scope=Scope.STATE, role='state'),

    # 锄大地
    _plan('', '启用锄大地 (Fhoe-Rail)', 'fight', 'header',
        ('fight_enable', 'fight_timestamp'), state_keys=('fight_timestamp',), role='header'),
    _plan('fightOperationModeCard', '运行模式', 'fight', 'advanced', ('fight_operation_mode',)),
    _plan('fightTimeoutCard', '锄大地超时', 'fight', 'advanced', ('fight_timeout',)),
    _plan('', '快捷配置', 'fight', 'header', role='header', link_id='fightPresetCard'),
    _plan('fightTeamEnableCard', '自动切换队伍', 'fight', 'maps', ('fight_team_enable', 'fight_team_number')),
    _plan('fightMapVersionCard', '地图版本', 'fight', 'maps', ('fight_map_version',)),
    _plan('fightMainMapCard', '优先星球', 'fight', 'maps', ('fight_main_map',)),
    _plan('fightRewardEnableCard', '启用「特殊物品领取」', 'fight', 'rewards', ('fight_reward_enable',)),
    _plan('fightAllowSnackBuyCard', '购买秘技零食并合成零食', 'fight', 'rewards', ('fight_allow_snack_buy',)),
    _plan('fightAllowMapBuyCard', '购买代币与过期邮包', 'fight', 'rewards', ('fight_allow_map_buy',)),
    _plan('fightAllowMemoryTokenCard', '获得翁法罗斯记忆代币', 'fight', 'rewards', ('fight_allow_memory_token',)),

    # 逐光捡金
    _plan('forgottenhallEnableCard', '启用混沌回忆', 'challenge', 'forgottenhall',
        ('forgottenhall_enable', 'forgottenhall_timestamp'), state_keys=('forgottenhall_timestamp',)),
    _plan('forgottenhallConfigCard', '混沌回忆配置', 'challenge', 'forgottenhall',
        ('forgottenhall_level', 'forgottenhall_stellar_enable', 'forgottenhall_team1',
         'forgottenhall_team2', 'forgottenhall_team3',)),
    _plan('purefictionEnableCard', '启用虚构叙事', 'challenge', 'purefiction',
        ('purefiction_enable', 'purefiction_timestamp'), state_keys=('purefiction_timestamp',)),
    _plan('purefictionConfigCard', '虚构叙事配置', 'challenge', 'purefiction',
        ('purefiction_level', 'purefiction_stellar_enable', 'purefiction_team1',
         'purefiction_team2', 'purefiction_team3',)),
    _plan('ApocalypticEnableCard', '启用末日幻影', 'challenge', 'apocalyptic',
        ('apocalyptic_enable', 'apocalyptic_timestamp'), state_keys=('apocalyptic_timestamp',)),
    _plan('ApocalypticConfigCard', '末日幻影配置', 'challenge', 'apocalyptic',
        ('apocalyptic_level', 'apocalyptic_stellar_enable', 'apocalyptic_team1',
         'apocalyptic_team2', 'apocalyptic_team3',)),

    # 程序
    _global('setupWizardCard', '首次配置向导', 'advanced', 'general', link_id='setup_wizard'),
    _global('logLevelCard', '日志等级', 'advanced', 'general', ('log_level',), doc='doc:Tutorial#日志等级'),
    _global('startGameTimeoutCard', '启动游戏超时时间（分）', 'game', 'launch', ('start_game_timeout',)),
    _global('pauseAfterSuccess', '成功后暂停程序', 'after_run', 'actions', ('pause_after_success',)),
    _global('exitAfterFailure', '失败后直接退出', 'after_run', 'actions', ('exit_after_failure',)),
    _global('afterFinishCard', '任务完成后', 'after_run', 'actions', ('after_finish',), doc='doc:Tutorial#任务完成后'),
    _global('refreshHourEnableCard', '游戏刷新时间', 'game', 'launch', ('refresh_hour',)),
    _global('ScriptPathCard', '脚本或程序路径(选择运行脚本时生效)', 'after_run', 'actions', ('script_path',)),
    _global('exitAppAfterSuccess', '任务全部成功后关闭助手', 'after_run', 'actions', ('exit_app_after_success',)),
    _global('playAudioCard', '声音提示', 'after_run', 'actions', ('play_audio',)),
    _global('', '定时计划', 'run', 'schedule', ('scheduled_tasks',), role='action', doc='doc:Tutorial#定时运行'),
    _global('overviewBackgroundCard', '问候区背景图', 'appearance', 'appearance', ('banner_path',)),
    _global('overviewMascotCard', '显示 Q 版小人', 'appearance', 'appearance', ('overview_show_mascot',)),
    _global('themeCard', '界面主题', 'appearance', 'appearance', ('ui_theme',)),
    _global('closeWindowActionCard', '关闭窗口时', 'appearance', 'window', ('close_window_action',)),
    _global('windowMemoryCard', '窗口记忆', 'appearance', 'window', ('window_memory',)),

    # 游戏连接
    _global('', '游戏运行位置', 'run_mode', 'header',
        ('control_backend', 'cloud_game_enable', 'ui_profile'), role='header'),
    _global('gamePathCard', '游戏路径', 'run_mode', 'local', ('game_path',)),
    _global('gamePathCard.launchMethodCard', '游戏启动方式', 'run_mode', 'local', ('game_launch_method',)),
    _global('autoSetGamePathEnableCard', '启用自动配置游戏路径', 'run_mode', 'local',
        ('auto_set_game_path_enable',)),
    _global('updateViaLauncherEnableCard', '通过启动器更新游戏', 'game', 'launch', ('update_via_launcher',)),
    _global('launcherPathCard', '启动器路径', 'game', 'launch', ('launcher_path',)),
    _global('launcherType', '启动器类型', 'game', 'launch', ('launcher_title_name',)),
    _global('updateGameTimeoutCard', '更新游戏超时时间（时）', 'game', 'launch', ('update_game_timeout',)),
    _global('autoSetResolutionEnableCard', '启用自动修改分辨率并关闭自动 HDR', 'game', 'optimization',
        ('auto_set_resolution_enable',)),
    _global('autoLowerGraphicsCard', '任务期间自动降低画质', 'game', 'optimization', ('auto_lower_graphics_enable',)),
    _global('useBackgroundScreenshotCard', '优先使用后台截图', 'run_mode', 'local', ('use_background_screenshot',), doc='doc:Background#windows-后台模式'),
    _global('localControlModeCard', '本地操作模式', 'run_mode', 'local', ('local_control_mode',),
        keywords=('后台', '挂机', '不占鼠标'), doc='doc:Background#windows-后台模式'),
    _global('backgroundMouseProtectionCard', '重试失败时短暂锁定鼠标', 'run_mode', 'local',
        ('background_mouse_protection',), doc='doc:Background#对鼠标和键盘的影响'),
    _global('browserTypeCard', '浏览器类型', 'run_mode', 'cloud', ('browser_type',)),
    _global('browserDownloadUseMirrorCard', '使用国内镜像下载浏览器和驱动', 'run_mode', 'cloud',
        ('browser_download_use_mirror',)),
    _global('browserPersistentCard', '保存浏览器数据（游戏的登录状态和本地数据）', 'run_mode', 'cloud',
        ('browser_persistent_enable',)),
    _global('browserScaleCard', '浏览器画面缩放（DPI）', 'run_mode', 'cloud', ('browser_scale_factor',)),
    _global('browserLaunchArgCard', '浏览器启动参数', 'run_mode', 'cloud', ('browser_launch_argument',)),
    _global('cloudGameFullScreenCard', '全屏运行', 'run_mode', 'cloud', ('cloud_game_fullscreen_enable',)),
    _global('cloudGameUsePaidTimeCard', '使用付费时长', 'run_mode', 'cloud', ('cloud_game_use_paid_time',)),
    _global('browserHeadlessCard', '启用无窗口模式（后台运行）', 'run_mode', 'cloud', ('browser_headless_enable',)),
    _global('browserHeadlessRestartCard', '未登录时自动切换为有窗口模式', 'run_mode', 'cloud',
        ('browser_headless_restart_on_not_logged_in',)),
    _global('cloudGameMaxQueueTimeCard', '最大排队等待时间（分钟）', 'run_mode', 'cloud',
        ('cloud_game_max_queue_time',)),
    _global('cloudGameLoginTimeoutCard', '登录超时时间（分钟）', 'run_mode', 'cloud', ('cloud_game_login_timeout',)),
    _global('adbDeviceCard', 'Android 设备', 'run_mode', 'adb'),
    _global('adbEnvironmentCard', '环境检查', 'run_mode', 'adb'),
    _global('adbStatusCard', '运行状态', 'run_mode', 'adb'),
    _global('adbAdvancedCard', '高级设置', 'run_mode', 'adb'),
    _global('adbAdvancedCard.pathCard', 'adb 路径', 'run_mode', 'adb', ('adb_path',)),
    _global('adbAdvancedCard.serialCard', '设备序列号', 'run_mode', 'adb', ('adb_serial',)),
    _global('adbAdvancedCard.typeCard', '设备类型', 'run_mode', 'adb', ('adb_device_type',)),
    _global('adbAdvancedCard.tapCard', '点按时长（毫秒）', 'run_mode', 'adb', ('adb_tap_ms',)),

    # 推送
    _global('notifyMasterEnableCard', '启用消息推送', 'notify', 'header', ('notification_enable',), doc='doc:Tutorial#消息推送'),
    _global('testNotifyCard', '测试消息推送', 'notify', 'header', ()),
    _global('notifyLevelCard', '通知级别', 'notify', 'content', ('notify_level',)),
    _global('notifyMergeCard', '通知合并', 'notify', 'content', ('notify_merge',)),
    _global('notifyImageEnableCard', '推送图片', 'notify', 'content', ('notify_send_images',)),
    _global('notifyTemplateCard', '消息推送格式', 'notify', 'content', ('notify_template',)),
    _global('', '已添加的渠道', 'notify', 'channels', ('notification_added_channels',), role='channel'),
    *(item for channel in CHANNELS for item in _channel(channel)),

    # 杂项
    _global('gameOptimizationCard', '启用游戏优化', 'game', 'optimization', ('game_optimization_enable',)),
    _global('autoBattleDetectEnableCard', '启用自动战斗和二倍速检测', 'game', 'optimization', ('auto_battle_detect_enable',)),
    _global('ocrGpuAccelerationCard', 'OCR 加速模式', 'advanced', 'general', ('ocr_gpu_acceleration',)),
    _global('autostartCard', '在用户登录时启动', 'advanced', 'permissions',
        ('autostart_open_gui', 'autostart_minimize', 'autostart_gui_task', 'autostart_headless_task')),
    _global('uacFreeCard', '免 UAC 运行', 'advanced', 'permissions'),
    _global('debugModeEnableCard', '启用调试模式', 'advanced', 'general', ('debug_mode_enable',)),

    _global('auto_detect_game_hotkeys_enableCard', '自动识别游戏按键', 'game', 'keys', ('auto_detect_game_hotkeys_enable',)),
    _global('hotkey_interactCard', '交互', 'game', 'keys', ('hotkey_interact',)),
    _global('hotkey_character_detailsCard', '战斗内角色详情', 'game', 'keys', ('hotkey_character_details',)),
    _global('hotkey_techniqueCard', '秘技（只对清体力和逐光捡金场景生效）', 'game', 'keys', ('hotkey_technique',)),
    _global('hotkey_mapCard', '地图', 'game', 'keys', ('hotkey_map',)),
    _global('hotkey_warpCard', '跃迁', 'game', 'keys', ('hotkey_warp',)),
    _global('hotkey_messageCard', '短信', 'game', 'keys', ('hotkey_message',)),
    _global('hotkey_auto_battleCard', '自动战斗', 'game', 'keys', ('hotkey_auto_battle',)),
    _global('hotkey_stop_taskCard', '停止任务（全局热键，支持后台）', 'hotkeys', 'keys', ('hotkey_stop_task',)),
    _global('hotkey_pause_taskCard', '暂停/继续任务（全局热键，支持后台）', 'hotkeys', 'keys', ('hotkey_pause_task',)),
    _global('hotkey_toggle_autoplotCard', '自动对话（全局热键，支持后台）', 'hotkeys', 'keys', ('hotkey_toggle_autoplot',)),

    # 数据
    _global('folderCard', '数据文件夹', 'data', 'folder', doc='doc:Tutorial#数据保存在哪里', link_id='DataGroup.folderCard'),
    _global('backupCard', '备份数据', 'data', 'backup', link_id='DataGroup.backupCard'),
    _global('restoreCard', '从备份恢复', 'data', 'backup', link_id='DataGroup.restoreCard'),
    _global('importCard', '从旧版文件夹导入', 'data', 'backup', link_id='DataGroup.importCard'),
    _global('diagnosticCard', '导出排查包', 'data', 'diagnostics', link_id='DataGroup.diagnosticCard'),

    # 关于
    _global('aboutCard', '关于', 'about', 'header'),
    _global('aboutCard.homeButton', '项目主页', 'about', 'header', link_id='githubCard'),
    _global('agentPromptCard', 'AI 助手', 'about', 'project'),
    _global('bilibiliCard', '哔哩哔哩', 'about', 'project'),
    _global('qqGroupCard', 'QQ群', 'about', 'project'),
    _global('updateSourceCard', '更新源', 'update', 'source', ('update_source', 'update_prerelease_enable'), doc='doc:Tutorial#更新'),
    _global('checkUpdateCard', '启动时检测更新', 'update', 'source', ('check_update',)),
    _global('updateFullEnableCard', '更新时下载完整包', 'update', 'source', ('update_full_enable',)),
    _global('updateDownloadProxyCard', '下载代理', 'update', 'source', ('update_download_proxy',)),
    _global('githubTokenCard', 'GitHub Token', 'update', 'source', ('github_token',),
        secret_keys=('github_token',)),
    _global('mirrorchyanCdkCard', 'Mirror 酱 CDK', 'update', 'source', ('mirrorchyan_cdk',),
        secret_keys=('mirrorchyan_cdk',)),
    _global('languageCard', '界面语言 / 界面語言 / 日本語 / 인터페이스 언어 / UI Language', 'appearance', 'appearance', ('ui_language',)),
    _global('telemetryCard', '匿名使用数据收集', 'advanced', 'privacy', ('telemetry_enable',)),
)

_BY_ID = {setting.id: setting for setting in SETTINGS}
_BY_KEY = {key: setting for setting in SETTINGS for key in setting.keys}


def find_setting(key: str) -> Setting | None:
    return _BY_ID.get(key) or _BY_KEY.get(key)
