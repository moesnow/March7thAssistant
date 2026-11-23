"""Metadata for the existing desktop settings. Importing this module only reads Python data."""
from dataclasses import KW_ONLY, dataclass
from enum import StrEnum
from functools import partial


class Scope(StrEnum):
    GLOBAL = 'GLOBAL'
    PLAN = 'PLAN'
    STATE = 'STATE'
    SECRET = 'SECRET'


@dataclass(frozen=True)
class Setting:
    widget: str  # Attribute path on SettingInterface. Channel cards are identified by config key.
    title: str
    destination: str
    keys: tuple[str, ...] = ()
    parents: tuple[str, ...] = ()  # Expandable cards, outermost first
    _: KW_ONLY
    tab: str
    group: str
    scope: Scope
    state_keys: tuple[str, ...] = ()
    secret_keys: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()

    def key_scope(self, key: str) -> Scope:
        if key in self.state_keys:
            return Scope.STATE
        if key in self.secret_keys:
            return Scope.SECRET
        return self.scope


_power = partial(Setting, tab='体力', group='体力设置', scope=Scope.PLAN)
_daily = partial(Setting, tab='日常', group='日常设置', scope=Scope.PLAN)
_currency = partial(Setting, tab='货币战争', group='货币', scope=Scope.PLAN)
_universe = partial(Setting, tab='差分宇宙', group='差分宇宙', scope=Scope.PLAN)
_fight = partial(Setting, tab='锄大地', group='锄地', scope=Scope.PLAN)
_challenge = partial(Setting, tab='逐光捡金', group='逐光捡金', scope=Scope.PLAN)
_program = partial(Setting, tab='程序', group='程序设置', scope=Scope.GLOBAL)
_connection = partial(Setting, tab='游戏连接', group='游戏连接', scope=Scope.GLOBAL)
_notify = partial(Setting, tab='推送', group='消息推送', scope=Scope.GLOBAL)
_misc = partial(Setting, tab='杂项', group='杂项', scope=Scope.GLOBAL)
_data = partial(Setting, tab='数据', group='数据与备份', scope=Scope.GLOBAL, destination='设置 › 数据与备份')
_about = partial(Setting, tab='关于', group='关于', scope=Scope.GLOBAL)


def _channel(name, display_name, fields=(), *, secrets=()):
    title = f'启用 {display_name} 通知'
    destination = '设置 › 消息推送 › 已添加的渠道'
    yield _notify('', title, destination, (f'notify_{name}_enable',))
    for suffix, label in fields:
        keys = (f'notify_{name}_{suffix}',) if suffix else ()
        scope = Scope.SECRET if suffix in secrets else Scope.GLOBAL
        yield _notify('', label, destination, keys, (title,), scope=scope)


_EXTERNAL_UNIVERSE = '任务 › 差分宇宙 ›「模拟宇宙（外部工具，停止维护）」折叠区'
_CHALLENGE_TASK = '任务 › 逐光捡金（混沌回忆 / 虚构叙事 / 末日幻影 分段）'
_SUPPORT = '任务 › 清体力 › 战斗与高级（支援角色也供每日实训引用）'
_REWARDS = '任务 › 领取奖励（子项改为复选列表）'
_BUILD_TARGET = '任务 › 清体力 › 刷什么 ›「按培养目标选择副本」展开项'

SETTINGS = (
    # 体力
    _power('powerEnableCard', '启用清体力', '任务 › 清体力 › 页头「加入完整运行」', ('power_enable', 'overview_power'),
        state_keys=('overview_power',)),
    _power('powerPlanCard', '体力计划', '任务 › 清体力 › 战斗与高级', ('power_plan', 'power_plan_keep', 'power_plan_continue')),
    _power('instanceTypeCard', '副本类型', '任务 › 清体力 › 刷什么', ('instance_type',)),
    _power('instanceTeamEnableCard', '自动切换队伍', '任务 › 清体力 › 战斗与高级',
        ('instance_team_enable', 'instance_team_number', 'instance_teams'), ('副本类型',)),
    _power('tpBeforeInstanceEnableCard', '清体力前传送至任意锚点', '任务 › 清体力 › 战斗与高级', ('tp_before_instance',), ('副本类型',)),
    _power('useReservedTrailblazePowerEnableCard', '使用后备开拓力', '任务 › 清体力 › 开拓力不够时',
        ('use_reserved_trailblaze_power',), ('副本类型',)),
    _power('useFuelEnableCard', '使用燃料', '任务 › 清体力 › 开拓力不够时', ('use_fuel',), ('副本类型',)),
    _power('preferFuelTicketsCard', '优先使用助燃券（实验）', '任务 › 清体力 › 开拓力不够时', ('prefer_fuel_tickets',), ('副本类型',)),
    _power('weeklyRelicCleanupEnableCard', '每周清理遗器', '任务 › 资产管理 › 遗器清理',
        ('break_down_level_four_relicset', 'weekly_relic_cleanup_day_of_week'), ('副本类型',)),
    _power('smartRelicDiscardEnableCard', '启用智能弃置', '任务 › 资产管理 › 遗器清理', ('weekly_relic_smart_discard_enable',),
        ('副本类型', '每周清理遗器')),
    _power('relicBagCleanupCard', '满包时自动分解遗器', '任务 › 资产管理 › 遗器清理', ('relic_bag_cleanup_enable',), ('副本类型',)),
    _power('instanceNameChallengeCountCard', '副本最大连续挑战次数（通常不建议修改保持默认即可）', '任务 › 清体力 › 战斗与高级',
        ('instance_names_challenge_count',), ('副本类型',)),
    _power('instanceNameCard', '副本名称', '任务 › 清体力 › 刷什么', ('instance_names',)),
    _power('borrowEnableCard', '启用使用支援角色', _SUPPORT, ('borrow_enable',)),
    _power('borrowCharacterEnableCard', '强制使用支援角色', _SUPPORT, ('borrow_character_enable',), ('启用使用支援角色',)),
    _power('borrowFriendsCard', '支援列表', _SUPPORT, ('borrow_friends',), ('启用使用支援角色',)),
    _power('borrowScrollTimesCard', '滚动查找次数', _SUPPORT, ('borrow_scroll_times',), ('启用使用支援角色',)),
    _power('buildTargetEnableCard', '启用培养目标', _BUILD_TARGET, ('build_target_enable',)),
    _power('buildTargetSchemeCard', '识别方案', _BUILD_TARGET, ('build_target_scheme',), ('启用培养目标',)),
    _power('buildTargetPlanarOrnamentWeeklyCountCard', '每周饰品提取次数', _BUILD_TARGET,
        ('build_target_ornament_weekly_count',), ('启用培养目标',)),
    _power('buildTargetUseUserInstanceWhenOnlyErosionAndOrnamentCard', '仅识别到侵蚀隧洞/饰品提取时使用自定义副本', _BUILD_TARGET,
        ('build_target_use_user_instance_when_only_erosion_and_ornament',), ('启用培养目标',)),
    _power('echoofwarEnableCard', '启用历战余响', '任务 › 历战余响', ('echo_of_war_enable', 'echo_of_war_start_day_of_week')),
    _power('echoofwarRunTimeCard', '上次完成历战余响的时间', '任务 › 历战余响（本周进度）', ('echo_of_war_timestamp',), ('启用历战余响',),
        scope=Scope.STATE),

    # 日常
    _daily('dailyEnableCard', '启用每日实训', '任务 › 每日实训', ('daily_enable', 'last_run_timestamp', 'overview_daily_activity'),
        state_keys=('last_run_timestamp', 'overview_daily_activity')),
    _daily('dailyMaterialEnableCard', '通过 “合成材料” 完成任务', '任务 › 每日实训', ('daily_material_enable',), ('启用每日实训',)),
    _daily('dailyMemoryOneEnableCard', '通过 “回忆一” 完成任务', '任务 › 每日实训', ('daily_memory_one_enable',), ('启用每日实训',)),
    _daily('dailyMemoryOneTeamCard', '回忆一队伍', '任务 › 每日实训', ('daily_memory_one_team',), ('启用每日实训',)),
    _daily('activityEnableCard', '启用活动检测', '任务 › 活动', ('activity_enable',)),
    _daily('activityDailyCheckInEnableCard', '每日签到', '任务 › 活动', ('activity_dailycheckin_enable',), ('启用活动检测',)),
    _daily('activityGardenOfPlentyEnableCard', '花藏繁生', '任务 › 活动',
        ('activity_gardenofplenty_enable', 'activity_gardenofplenty_instance_type'), ('启用活动检测',)),
    _daily('activityRealmOfTheStrangeEnableCard', '异器盈界', '任务 › 活动', ('activity_realmofthestrange_enable',),
        ('启用活动检测',)),
    _daily('activityPlanarFissureEnableCard', '位面分裂', '任务 › 活动', ('activity_planarfissure_enable',), ('启用活动检测',)),
    _daily('activityJourneyHighlightsNotificationEnableCard', '活动热点通知', '任务 › 活动',
        ('activity_journey_highlights_notification_enable',), ('启用活动检测',)),
    _daily('rewardEnableCard', '启用奖励领取', _REWARDS, ('reward_enable',)),
    _daily('dispatchEnableCard', '委托', _REWARDS, ('reward_dispatch_enable',), ('启用奖励领取',)),
    _daily('mailEnableCard', '邮件', _REWARDS, ('reward_mail_enable',), ('启用奖励领取',)),
    _daily('assistEnableCard', '支援', _REWARDS, ('reward_assist_enable',), ('启用奖励领取',)),
    _daily('questEnableCard', '每日实训', _REWARDS, ('reward_quest_enable',), ('启用奖励领取',)),
    _daily('srpassEnableCard', '无名勋礼', _REWARDS, ('reward_srpass_enable',), ('启用奖励领取',)),
    _daily('redemptionEnableCard', '兑换码', _REWARDS, ('reward_redemption_code_enable',), ('启用奖励领取',)),
    _daily('achievementEnableCard', '成就', _REWARDS, ('reward_achievement_enable',), ('启用奖励领取',)),
    _daily('messageEnableCard', '短信', _REWARDS, ('reward_message_enable',), ('启用奖励领取',)),
    _daily('assetEnableCard', '启用资产管理', '任务 › 资产管理', ('asset_manager_enable',)),
    _daily('selfMoldingResinEnableCard', '启用「每月自动合成自塑尘脂」', '任务 › 资产管理',
        ('asset_self_molding_resin_enable', 'asset_self_molding_resin_timestamp'), ('启用资产管理',),
        state_keys=('asset_self_molding_resin_timestamp',)),
    _daily('emberSpecialPassEnableCard', '启用「每月自动购买星轨专票」', '任务 › 资产管理',
        ('asset_ember_special_pass_enable', 'asset_ember_special_pass_timestamp'), ('启用资产管理',),
        state_keys=('asset_ember_special_pass_timestamp',)),
    _daily('emberRegularPassEnableCard', '启用「每月自动购买星轨通票」', '任务 › 资产管理',
        ('asset_ember_regular_pass_enable', 'asset_ember_regular_pass_timestamp'), ('启用资产管理',),
        state_keys=('asset_ember_regular_pass_timestamp',)),
    _daily('emberTracksOfDestinyEnableCard', '启用「每月自动购买命运的足迹」', '任务 › 资产管理',
        ('asset_ember_tracks_of_destiny_enable', 'asset_ember_tracks_of_destiny_timestamp'), ('启用资产管理',),
        state_keys=('asset_ember_tracks_of_destiny_timestamp',)),
    _daily('lc3StarSuperimposeEnableCard', '启用「3星光锥自动叠加」', '任务 › 资产管理', ('asset_lc3_star_superimpose_enable',),
        ('启用资产管理',)),

    # 货币战争
    _currency('currencywarsEnableCard', '启用「货币战争」积分奖励', '任务 › 货币战争 › 页头开关；完成时间进入账号状态',
        ('currencywars_enable', 'currencywars_timestamp'), state_keys=('currencywars_timestamp',)),
    _currency('currencywarsPresetCard', '快捷配置', '任务 › 货币战争 › 页头「快捷配置」'),
    _currency('currencywarsTypeCard', '类别', '任务 › 货币战争', ('currencywars_type',)),
    _currency('currencywarsBonusEnableCard', '自动执行位面饰品快速提取', '任务 › 货币战争', ('currencywars_bonus_enable',)),
    _currency('currencywarsRankDifficultyCard', '职级难度', '任务 › 货币战争', ('currencywars_rank_difficulty',)),
    _currency('currencywarsStrategyCard', '请更新货币战争策略', '任务 › 货币战争 › 页内提示条（有新策略时显示）'),
    _currency('currencywarsStrategySelectCard', '货币战争策略', '任务 › 货币战争', ('currencywars_strategy',)),
    _currency('currencywarsInvestmentPriorityCard', '投资选项优先级', '任务 › 货币战争',
        ('currencywars_investment_priority',), ('货币战争策略',)),
    _currency('currencywarsUnfinishedMatchCard', '未完成对局', '任务 › 货币战争', ('currencywars_unfinished_match',),
        ('货币战争策略',)),
    _currency('currencywarsFastModeCard', '启用速通模式', '任务 › 货币战争', ('currencywars_fast_mode',)),
    _currency('currencywarsTimeLimitCard', '总时限', '任务 › 货币战争', ('currencywars_time_limit',)),

    # 差分宇宙
    _universe('weeklyDivergentEnableCard', '启用「差分宇宙」积分奖励', '任务 › 差分宇宙 › 页头开关；完成时间进入账号状态',
        ('weekly_divergent_enable', 'weekly_divergent_timestamp'), state_keys=('weekly_divergent_timestamp',)),
    _universe('weeklyDivergentTypeCard', '类别', '任务 › 差分宇宙', ('weekly_divergent_type',)),
    _universe('weeklyDivergentBonusEnableCard', '自动执行饰品提取', '任务 › 差分宇宙', ('weekly_divergent_bonus_enable',)),
    _universe('weeklyDivergentLevelCard', '难度等级', '任务 › 差分宇宙', ('weekly_divergent_level',)),
    _universe('stationPriorityCard', '站点优先级', '任务 › 差分宇宙',
        ('divergent_station_priority_enable', 'divergent_station_priority', 'divergent_station_disabled')),
    _universe('weeklyDivergentStableModeCard', '启用低性能兼容模式', '任务 › 差分宇宙', ('weekly_divergent_stable_mode',)),
    _universe('divergentAutoSaveCard', '自动记录差分宇宙存档', '任务 › 差分宇宙', ('divergent_auto_save_enable',)),
    _universe('universeEnableCard', '启用模拟宇宙/差分宇宙 (Auto_Simulated_Universe)', _EXTERNAL_UNIVERSE,
        ('universe_enable',)),
    _universe('universeCategoryCard', '类别', _EXTERNAL_UNIVERSE, ('universe_category',),
        ('启用模拟宇宙/差分宇宙 (Auto_Simulated_Universe)',)),
    _universe('divergentTypeCard', '选择差分宇宙时类别', _EXTERNAL_UNIVERSE, ('divergent_type',),
        ('启用模拟宇宙/差分宇宙 (Auto_Simulated_Universe)',)),
    _universe('universeBonusEnableCard', '自动领取模拟宇宙沉浸奖励', _EXTERNAL_UNIVERSE, ('universe_bonus_enable',),
        ('启用模拟宇宙/差分宇宙 (Auto_Simulated_Universe)',)),
    _universe('universeFrequencyCard', '运行频率', _EXTERNAL_UNIVERSE, ('universe_frequency',),
        ('启用模拟宇宙/差分宇宙 (Auto_Simulated_Universe)',)),
    _universe('universeCountCard', '运行次数', _EXTERNAL_UNIVERSE, ('universe_count',),
        ('启用模拟宇宙/差分宇宙 (Auto_Simulated_Universe)',)),
    _universe('divergentUniverseRunCountCard', '差分宇宙已完成次数', '任务 › 差分宇宙 ›「模拟宇宙（外部工具）」折叠区',
        ('divergent_universe_daily_completed_count',
         'divergent_universe_daily_completed_timestamp',
         'divergent_universe_weekly_completed_count',
         'divergent_universe_weekly_completed_timestamp',), ('启用模拟宇宙/差分宇宙 (Auto_Simulated_Universe)',),
        scope=Scope.STATE),
    _universe('universeFateCard', '命途（仅模拟宇宙生效）', _EXTERNAL_UNIVERSE, ('universe_fate',),
        ('启用模拟宇宙/差分宇宙 (Auto_Simulated_Universe)',)),
    _universe('universeDifficultyCard', '难度 (0为不配置，仅模拟宇宙生效)', _EXTERNAL_UNIVERSE, ('universe_difficulty',),
        ('启用模拟宇宙/差分宇宙 (Auto_Simulated_Universe)',)),
    _universe('universeOperationModeCard', '运行模式', _EXTERNAL_UNIVERSE, ('universe_operation_mode',),
        ('启用模拟宇宙/差分宇宙 (Auto_Simulated_Universe)',)),
    _universe('universeEnableGpuCard', '启用模拟宇宙 GPU 加速', '任务 › 差分宇宙 ›「模拟宇宙（外部工具）」折叠区（原放在锄大地分组，归位）',
        ('universe_enable_gpu',), ('启用模拟宇宙/差分宇宙 (Auto_Simulated_Universe)',)),
    _universe('universeTimeoutCard', '模拟宇宙/差分宇宙超时', _EXTERNAL_UNIVERSE, ('universe_timeout',),
        ('启用模拟宇宙/差分宇宙 (Auto_Simulated_Universe)',)),
    _universe('universeRunTimeCard', '上次运行模拟宇宙/差分宇宙的时间', '任务 › 差分宇宙 ›「模拟宇宙（外部工具）」折叠区', ('universe_timestamp',),
        ('启用模拟宇宙/差分宇宙 (Auto_Simulated_Universe)',), scope=Scope.STATE),

    # 锄大地
    _fight('fightEnableCard', '启用锄大地 (Fhoe-Rail)', '任务 › 锄大地 › 页头开关；上次运行时间进入账号状态',
        ('fight_enable', 'fight_timestamp'), state_keys=('fight_timestamp',)),
    _fight('fightOperationModeCard', '运行模式', '任务 › 锄大地', ('fight_operation_mode',), ('启用锄大地 (Fhoe-Rail)',)),
    _fight('fightTimeoutCard', '锄大地超时', '任务 › 锄大地', ('fight_timeout',), ('启用锄大地 (Fhoe-Rail)',)),
    _fight('fightPresetCard', '快捷配置', '任务 › 锄大地 › 页头「快捷配置」'),
    _fight('fightTeamEnableCard', '自动切换队伍', '任务 › 锄大地', ('fight_team_enable', 'fight_team_number')),
    _fight('fightMapVersionCard', '地图版本', '任务 › 锄大地', ('fight_map_version',)),
    _fight('fightMainMapCard', '优先星球', '任务 › 锄大地', ('fight_main_map',)),
    _fight('fightRewardEnableCard', '启用「特殊物品领取」', '任务 › 锄大地', ('fight_reward_enable',)),
    _fight('fightAllowSnackBuyCard', '购买秘技零食并合成零食', '任务 › 锄大地', ('fight_allow_snack_buy',), ('启用「特殊物品领取」',)),
    _fight('fightAllowMapBuyCard', '购买代币与过期邮包', '任务 › 锄大地', ('fight_allow_map_buy',), ('启用「特殊物品领取」',)),
    _fight('fightAllowMemoryTokenCard', '获得翁法罗斯记忆代币', '任务 › 锄大地', ('fight_allow_memory_token',), ('启用「特殊物品领取」',)),

    # 逐光捡金
    _challenge('forgottenhallEnableCard', '启用混沌回忆', _CHALLENGE_TASK,
        ('forgottenhall_enable', 'forgottenhall_timestamp'), state_keys=('forgottenhall_timestamp',)),
    _challenge('forgottenhallConfigCard', '混沌回忆配置', _CHALLENGE_TASK,
        ('forgottenhall_level', 'forgottenhall_stellar_enable', 'forgottenhall_team1',
         'forgottenhall_team2', 'forgottenhall_team3',), ('启用混沌回忆',)),
    _challenge('purefictionEnableCard', '启用虚构叙事', _CHALLENGE_TASK,
        ('purefiction_enable', 'purefiction_timestamp'), state_keys=('purefiction_timestamp',)),
    _challenge('purefictionConfigCard', '虚构叙事配置', _CHALLENGE_TASK,
        ('purefiction_level', 'purefiction_stellar_enable', 'purefiction_team1',
         'purefiction_team2', 'purefiction_team3',), ('启用虚构叙事',)),
    _challenge('ApocalypticEnableCard', '启用末日幻影', _CHALLENGE_TASK,
        ('apocalyptic_enable', 'apocalyptic_timestamp'), state_keys=('apocalyptic_timestamp',)),
    _challenge('ApocalypticConfigCard', '末日幻影配置', _CHALLENGE_TASK,
        ('apocalyptic_level', 'apocalyptic_stellar_enable', 'apocalyptic_team1',
         'apocalyptic_team2', 'apocalyptic_team3',), ('启用末日幻影',)),

    # 程序
    _program('logLevelCard', '日志等级', '设置 › 高级', ('log_level',)),
    _program('startGameTimeoutCard', '启动游戏超时时间（分）', '设置 › 游戏与启动', ('start_game_timeout',)),
    _program('pauseAfterSuccess', '成功后暂停程序', '设置 › 任务结束后', ('pause_after_success',)),
    _program('exitAfterFailure', '失败后直接退出', '设置 › 任务结束后', ('exit_after_failure',)),
    _program('afterFinishCard', '任务完成后', '设置 › 任务结束后', ('after_finish',)),
    _program('scheduledCard', '定时任务时间', '运行 › 定时计划（旧单一定时已迁移，移除此卡）', ('scheduled_time',), ('任务完成后',)),
    _program('refreshHourEnableCard', '游戏刷新时间', '设置 › 游戏与启动「游戏每日刷新时间」', ('refresh_hour',), ('任务完成后',)),
    _program('ScriptPathCard', '脚本或程序路径(选择运行脚本时生效)', '设置 › 任务结束后', ('script_path',), ('任务完成后',)),
    _program('exitAppAfterSuccess', '任务全部成功后关闭助手', '设置 › 任务结束后', ('exit_app_after_success',)),
    _program('playAudioCard', '声音提示', '设置 › 任务结束后', ('play_audio',)),
    _program('scheduleManagerCard', '定时计划', '运行 › 定时计划', ('scheduled_tasks',)),
    _program('overviewBackgroundCard', '问候区背景图', '设置 › 外观与窗口', ('banner_path',)),
    _program('overviewMascotCard', '显示 Q 版小人', '设置 › 外观与窗口', ('overview_show_mascot',)),
    _program('themeCard', '界面主题', '设置 › 外观与窗口', ('ui_theme',)),
    _program('closeWindowActionCard', '关闭窗口时', '设置 › 外观与窗口', ('close_window_action',)),
    _program('windowMemoryCard', '窗口记忆', '设置 › 外观与窗口', ('window_memory',)),

    # 游戏连接
    _connection('adbBackendCard', '游戏运行位置', '设置 › 运行方式 › 顶部三选一卡片',
        ('control_backend', 'cloud_game_enable', 'ui_profile')),
    _connection('gamePathCard', '游戏路径', '设置 › 运行方式 › 本地客户端', ('game_path',)),
    _connection('gamePathCard.launchMethodCard', '游戏启动方式', '设置 › 运行方式 › 本地客户端', ('game_launch_method',),
        ('游戏路径',)),
    _connection('autoSetGamePathEnableCard', '启用自动配置游戏路径', '设置 › 运行方式 › 本地客户端（游戏路径旁的「自动识别」）',
        ('auto_set_game_path_enable',)),
    _connection('updateViaLauncherEnableCard', '通过启动器更新游戏', '设置 › 游戏与启动', ('update_via_launcher',)),
    _connection('launcherPathCard', '启动器路径', '设置 › 游戏与启动', ('launcher_path',), ('通过启动器更新游戏',)),
    _connection('launcherType', '启动器类型', '设置 › 游戏与启动', ('launcher_title_name',), ('通过启动器更新游戏',)),
    _connection('updateGameTimeoutCard', '更新游戏超时时间（时）', '设置 › 游戏与启动', ('update_game_timeout',), ('通过启动器更新游戏',)),
    _connection('autoSetResolutionEnableCard', '启用自动修改分辨率并关闭自动 HDR', '设置 › 游戏与启动 › 游戏优化',
        ('auto_set_resolution_enable',)),
    _connection('autoLowerGraphicsCard', '任务期间自动降低画质', '设置 › 游戏与启动 › 游戏优化', ('auto_lower_graphics_enable',)),
    _connection('useBackgroundScreenshotCard', '优先使用后台截图', '设置 › 运行方式 › 本地客户端', ('use_background_screenshot',)),
    _connection('localControlModeCard', '本地操作模式', '设置 › 运行方式 › 本地客户端', ('local_control_mode',),
        keywords=('后台', '挂机', '不占鼠标')),
    _connection('backgroundMouseProtectionCard', '重试失败时短暂锁定鼠标', '设置 › 运行方式 › 本地客户端',
        ('background_mouse_protection',), ('本地操作模式',)),
    _connection('browserTypeCard', '浏览器类型', '设置 › 运行方式 › 云·星穹铁道', ('browser_type',)),
    _connection('browserDownloadUseMirrorCard', '使用国内镜像下载浏览器和驱动', '设置 › 运行方式 › 云·星穹铁道',
        ('browser_download_use_mirror',), ('浏览器类型',)),
    _connection('browserPersistentCard', '保存浏览器数据（游戏的登录状态和本地数据）', '设置 › 运行方式 › 云·星穹铁道',
        ('browser_persistent_enable',), ('浏览器类型',)),
    _connection('browserScaleCard', '浏览器画面缩放（DPI）', '设置 › 运行方式 › 云·星穹铁道', ('browser_scale_factor',), ('浏览器类型',)),
    _connection('browserLaunchArgCard', '浏览器启动参数', '设置 › 运行方式 › 云·星穹铁道', ('browser_launch_argument',),
        ('浏览器类型',)),
    _connection('cloudGameFullScreenCard', '全屏运行', '设置 › 运行方式 › 云·星穹铁道', ('cloud_game_fullscreen_enable',)),
    _connection('cloudGameUsePaidTimeCard', '使用付费时长', '设置 › 运行方式 › 云·星穹铁道', ('cloud_game_use_paid_time',)),
    _connection('browserHeadlessCard', '启用无窗口模式（后台运行）', '设置 › 运行方式 › 云·星穹铁道', ('browser_headless_enable',)),
    _connection('browserHeadlessRestartCard', '未登录时自动切换为有窗口模式', '设置 › 运行方式 › 云·星穹铁道',
        ('browser_headless_restart_on_not_logged_in',), ('启用无窗口模式（后台运行）',)),
    _connection('cloudGameMaxQueueTimeCard', '最大排队等待时间（分钟）', '设置 › 运行方式 › 云·星穹铁道',
        ('cloud_game_max_queue_time',)),
    _connection('cloudGameLoginTimeoutCard', '登录超时时间（分钟）', '设置 › 运行方式 › 云·星穹铁道', ('cloud_game_login_timeout',)),
    _connection('adbDeviceCard', 'Android 设备', '设置 › 运行方式 › 安卓设备'),
    _connection('adbEnvironmentCard', '环境检查', '设置 › 运行方式 › 安卓设备'),
    _connection('adbStatusCard', '运行状态', '设置 › 运行方式 › 安卓设备'),
    _connection('adbAdvancedCard', '高级设置', '设置 › 运行方式 › 安卓设备'),
    _connection('adbAdvancedCard.pathCard', 'adb 路径', '设置 › 运行方式 › 安卓设备', ('adb_path',), ('高级设置',)),
    _connection('adbAdvancedCard.serialCard', '设备序列号', '设置 › 运行方式 › 安卓设备', ('adb_serial',), ('高级设置',)),
    _connection('adbAdvancedCard.typeCard', '设备类型', '设置 › 运行方式 › 安卓设备', ('adb_device_type',), ('高级设置',)),
    _connection('adbAdvancedCard.tapCard', '点按时长（毫秒）', '设置 › 运行方式 › 安卓设备', ('adb_tap_ms',), ('高级设置',)),

    # 推送
    _notify('notifyMasterEnableCard', '启用消息推送', '设置 › 消息推送 › 页头', ('notification_enable',)),
    _notify('testNotifyCard', '测试消息推送', '设置 › 消息推送 › 页头', (), ('启用消息推送',)),
    _notify('notifyLevelCard', '通知级别', '设置 › 消息推送 › 推送内容', ('notify_level',), ('启用消息推送',)),
    _notify('notifyMergeCard', '通知合并', '设置 › 消息推送 › 推送内容', ('notify_merge',), ('启用消息推送',)),
    _notify('notifyImageEnableCard', '推送图片', '设置 › 消息推送 › 推送内容', ('notify_send_images',), ('启用消息推送',)),
    _notify('notifyTemplateCard', '消息推送格式', '设置 › 消息推送 › 推送内容', ('notify_template',), ('启用消息推送',)),
    *_channel('winotify', 'Windows'),
    *_channel('wechatworkbot', '企业微信机器人', (
        ('key', '机器人 Key'),
        ('webhook_url', 'Webhook 地址'),
    ), secrets=('key', 'webhook_url')),
    *_channel('qqbot', 'QQ 官方机器人', (
        ('appid', '机器人 AppID'),
        ('client_secret', '机器人 AppSecret'),
        ('openid', '单聊用户 openid'),
        ('group_openid', '群聊 group_openid'),
        ('', '自动绑定收件标识'),
    ), secrets=('client_secret',)),
    *_channel('smtp', 'SMTP', (
        ('host', 'SMTP 服务器'),
        ('user', '用户名/邮箱'),
        ('password', '密码/授权码'),
        ('From', '发件人'),
        ('To', '收件人'),
        ('port', '端口'),
        ('ssl', '启用 SSL'),
        ('starttls', '启用 STARTTLS'),
        ('ssl_unverified', '跳过证书验证'),
        ('plain_text', '纯文本模式'),
    ), secrets=('password',)),
    *_channel('lark', '飞书', (
        ('webhook', 'Webhook 地址'),
        ('content', '消息内容'),
        ('keyword', '关键词'),
        ('sign', '签名'),
        ('imageenable', '启用图片'),
        ('appid', '应用 AppId'),
        ('secret', '应用 Secret'),
    ), secrets=('webhook', 'sign', 'secret')),
    *_channel('telegram', 'Telegram', (
        ('token', '机器人令牌'),
        ('userid', '用户/群组 ID'),
        ('api_url', '自定义 API 地址'),
        ('proxies', '代理配置'),
        ('thread_id', '话题 ID'),
    ), secrets=('token',)),
    *_channel('dingtalk', '钉钉', (
        ('token', '机器人令牌'),
        ('secret', '加签密钥'),
    ), secrets=('token', 'secret')),
    *_channel('serverchan3', 'Server酱³', (
        ('sendkey', 'SendKey'),
    ), secrets=('sendkey',)),
    *_channel('onebot', 'OneBot', (
        ('endpoint', '服务地址'),
        ('token', '访问令牌'),
        ('user_id', '私聊用户 ID'),
        ('group_id', '群组 ID'),
    ), secrets=('token',)),
    *_channel('serverchanturbo', 'Server酱·Turbo版', (
        ('sctkey', 'SendKey'),
        ('channel', '发送通道'),
        ('openid', '接收人 OpenID'),
    ), secrets=('sctkey',)),
    *_channel('bark', 'Bark', (
        ('key', '推送密钥'),
        ('group', '分组名'),
        ('icon', '图标地址'),
        ('isarchive', '归档'),
        ('sound', '提示音'),
        ('url', '跳转链接'),
        ('base_url', '服务地址'),
        ('copy', '复制内容'),
        ('autocopy', '自动复制'),
        ('cipherkey', '加密密钥'),
        ('ciphermethod', '加密算法'),
    ), secrets=('key', 'cipherkey')),
    *_channel('wechatworkapp', '企业微信应用', (
        ('corpid', '企业 ID'),
        ('corpsecret', '应用密钥'),
        ('agentid', '应用 AgentId'),
        ('touser', '接收用户'),
        ('base_url', '自定义 API 地址'),
    ), secrets=('corpsecret',)),
    *_channel('pushplus', 'Pushplus', (
        ('token', '推送令牌'),
        ('channel', '推送渠道'),
        ('webhook', 'Webhook 地址'),
        ('callbackUrl', '回调地址'),
    ), secrets=('token', 'webhook')),
    *_channel('discord', 'Discord', (
        ('webhook', 'Webhook 地址'),
        ('username', '显示用户名'),
        ('avatar_url', '头像地址'),
        ('color', '消息颜色'),
    ), secrets=('webhook',)),
    *_channel('meow', 'MeoW', (
        ('nickname', '昵称'),
    )),
    *_channel('gotify', 'Gotify', (
        ('url', '服务地址'),
        ('token', '访问令牌'),
        ('priority', '优先级'),
    ), secrets=('token',)),
    *_channel('kook', 'KOOK', (
        ('token', '机器人令牌'),
        ('target_id', '目标 ID'),
        ('chat_type', '聊天类型'),
    ), secrets=('token',)),
    *_channel('qmsg', 'Qmsg', (
        ('key', '推送密钥'),
        ('qq', 'QQ 号'),
        ('mode', '发送模式'),
    ), secrets=('key',)),
    *_channel('matrix', 'Matrix', (
        ('homeserver', '服务器地址'),
        ('device_id', '设备 ID'),
        ('user_id', '用户 ID'),
        ('access_token', '访问令牌'),
        ('room_id', '房间 ID'),
        ('proxy', '代理配置'),
        ('separately_text_media', '文字与图片分开发送'),
    ), secrets=('access_token',)),
    *_channel('pushdeer', 'Pushdeer', (
        ('token', '推送令牌'),
        ('url', '服务地址'),
    ), secrets=('token',)),
    *_channel('gocqhttp', 'Go-cqhttp', (
        ('endpoint', '服务地址'),
        ('message_type', '消息类型'),
        ('token', '访问令牌'),
        ('user_id', '私聊用户 ID'),
        ('group_id', '群组 ID'),
    ), secrets=('token',)),
    *_channel('webhook', 'Webhook', (
        ('url', '接收地址'),
        ('method', '请求方法'),
        ('headers', '请求头'),
        ('body', '请求体'),
    ), secrets=('url', 'headers')),
    *_channel('custom', '自定义通知', (
        ('url', '请求地址'),
        ('method', '请求方法'),
        ('datatype', '数据类型'),
        ('image', '图片模板'),
        ('data', '数据模板'),
    ), secrets=('url',)),

    # 杂项
    _misc('gameOptimizationCard', '启用游戏优化', '设置 › 游戏与启动 › 游戏优化', ('game_optimization_enable',)),
    _misc('autoBattleDetectEnableCard', '启用自动战斗和二倍速检测', '设置 › 游戏与启动 › 游戏优化', ('auto_battle_detect_enable',)),
    _misc('ocrGpuAccelerationCard', 'OCR 加速模式', '设置 › 高级', ('ocr_gpu_acceleration',)),
    _misc('localControlModeMovedCard', '后台操作模式已移至「游戏连接」', '移除（改由全局搜索和深链接定位）'),
    _misc('autostartCard', '在用户登录时启动', '设置 › 高级 › 启动与权限',
        ('autostart_open_gui', 'autostart_minimize', 'autostart_gui_task', 'autostart_headless_task')),
    _misc('uacFreeCard', '免 UAC 运行', '设置 › 高级 › 启动与权限'),
    _misc('debugModeEnableCard', '启用调试模式', '设置 › 高级', ('debug_mode_enable',)),
    _misc('hotkeyCard', '修改按键', '拆分：游戏内按键 → 设置 › 游戏与启动；全局热键 → 设置 › 快捷键',
        ('auto_detect_game_hotkeys_enable', 'hotkey_interact', 'hotkey_character_details',
         'hotkey_technique', 'hotkey_map', 'hotkey_warp', 'hotkey_message',
         'hotkey_auto_battle', 'hotkey_stop_task', 'hotkey_pause_task',
         'hotkey_toggle_autoplot',)),

    # 数据
    _data('DataGroup.folderCard', '数据文件夹'),
    _data('DataGroup.backupCard', '备份数据'),
    _data('DataGroup.restoreCard', '从备份恢复'),
    _data('DataGroup.importCard', '从旧版文件夹导入'),
    _data('DataGroup.diagnosticCard', '导出排查包'),

    # 关于
    _about('githubCard', '项目主页', '设置 › 关于'),
    _about('agentPromptCard', 'AI 助手', '设置 › 关于'),
    _about('bilibiliCard', '哔哩哔哩', '设置 › 关于'),
    _about('qqGroupCard', 'QQ群', '设置 › 关于'),
    _about('aboutCard', '关于', '设置 › 关于'),
    _about('updateSourceCard', '更新源', '设置 › 更新', ('update_source', 'update_prerelease_enable')),
    _about('checkUpdateCard', '启动时检测更新', '设置 › 更新', ('check_update',), ('更新源',)),
    _about('updateFullEnableCard', '更新时下载完整包', '设置 › 更新', ('update_full_enable',), ('更新源',)),
    _about('updateDownloadProxyCard', '下载代理', '设置 › 更新', ('update_download_proxy',), ('更新源',)),
    _about('githubTokenCard', 'GitHub Token', '设置 › 更新', ('github_token',), ('更新源',),
        secret_keys=('github_token',)),
    _about('mirrorchyanCdkCard', 'Mirror 酱 CDK', '设置 › 更新', ('mirrorchyan_cdk',),
        secret_keys=('mirrorchyan_cdk',)),
    _about('languageCard', '界面语言 / 界面語言 / 日本語 / 인터페이스 언어 / UI Language', '设置 › 外观与窗口', ('ui_language',)),
    _about('telemetryCard', '匿名使用数据收集', '设置 › 高级 › 隐私', ('telemetry_enable',)),
)

_BY_KEY = {key: setting for setting in SETTINGS for key in setting.keys}


def find_setting(key: str) -> Setting | None:
    return _BY_KEY.get(key)
