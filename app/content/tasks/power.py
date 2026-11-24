from qfluentwidgets import FluentIcon as FIF
from app.common.icon import UiIcon
from app.card.comboboxsettingcard2 import ComboBoxSettingCard2
from app.card.switchsettingcard1 import SwitchSettingCard1
from app.card.rangesettingcard1 import RangeSettingCard1
from app.card.pushsettingcard1 import (
    PushSettingCardInstance,
    PushSettingCardInstanceChallengeCount,
    PushSettingCardFriends,
    PushSettingCardPowerPlan,
    InstanceTeamSettingCard,
)
from app.card.expandable_switch_setting_card import ExpandableSwitchSettingCard
from module.localization import tr
from module.search.setting_text import choice_texts


def build(host):
    host.powerPlanCard = PushSettingCardPowerPlan(
        tr('配置'),
        FIF.CALENDAR,
        tr("体力计划"),
        "power_plan",
        parent=host.card_parent,
    )
    host.instanceTypeCard = ComboBoxSettingCard2(
        "instance_type", UiIcon.LIST, tr("副本类型"),
        texts=choice_texts("instance_type"),
        parent=host.card_parent,
    )
    host.instanceTeamEnableCard = InstanceTeamSettingCard(
        UiIcon.PEOPLE_SWAP,
        tr("自动切换队伍"),
        None,
        parent=host.card_parent,
    )
    host.tpBeforeInstanceEnableCard = SwitchSettingCard1(
        UiIcon.PIN,
        tr("清体力前传送至任意锚点"),
        "",
        "tp_before_instance",
        parent=host.card_parent,
    )
    host.useReservedTrailblazePowerEnableCard = SwitchSettingCard1(
        UiIcon.BATTERY_CHARGE,
        tr("使用后备开拓力"),
        tr("每个副本项最多补充一次，数量以游戏弹窗为准"),
        "use_reserved_trailblaze_power",
        parent=host.card_parent,
    )
    host.useFuelEnableCard = SwitchSettingCard1(
        UiIcon.DROP,
        tr("使用燃料"),
        tr("同时启用后备开拓力时，后备库存用完才使用燃料"),
        "use_fuel",
        parent=host.card_parent,
    )
    host.preferFuelTicketsCard = SwitchSettingCard1(
        UiIcon.DROP,
        tr("优先使用助燃券（实验）"),
        tr("PC 花萼、凝滞虚影优先快速刷取，保留支援实训，券不足时普通挑战"),
        "prefer_fuel_tickets",
        parent=host.card_parent,
    )
    host.instanceNameChallengeCountCard = PushSettingCardInstanceChallengeCount(
        tr('修改'),
        UiIcon.REPEAT,
        tr("副本最大连续挑战次数（通常不建议修改保持默认即可）"),
        "instance_names_challenge_count",
        parent=host.card_parent,
    )
    host.instanceNameCard = PushSettingCardInstance(
        tr('修改'),
        UiIcon.BOOKMARK,
        tr("副本名称"),
        "instance_names",
        parent=host.card_parent,
    )
    host.borrowEnableCard = ExpandableSwitchSettingCard(
        "borrow_enable",
        UiIcon.PEOPLE,
        tr("启用使用支援角色"),
        '',
        parent=host.card_parent,
    )
    host.borrowCharacterEnableCard = SwitchSettingCard1(
        UiIcon.PEOPLE_CHECKMARK,
        tr("强制使用支援角色"),
        tr("无论何时都要使用支援角色，即使日常实训中的要求已经完成"),
        "borrow_character_enable",
        parent=host.card_parent,
    )
    host.borrowFriendsCard = PushSettingCardFriends(
        tr('修改'),
        UiIcon.PEOPLE_LIST,
        tr("支援列表"),
        "borrow_friends",
        parent=host.card_parent,
    )
    host.borrowScrollTimesCard = RangeSettingCard1(
        "borrow_scroll_times",
        [1, 10],
        UiIcon.REPEAT,
        tr("滚动查找次数"),
        '',
        parent=host.card_parent,
    )
    host.buildTargetEnableCard = ExpandableSwitchSettingCard(
        "build_target_enable",
        UiIcon.TARGET,
        tr("启用培养目标"),
        tr("根据培养目标刷取行迹与遗器副本，如果无法获取培养目标则回退到默认的副本设置"),
        parent=host.card_parent,
    )
    host.buildTargetSchemeCard = ComboBoxSettingCard2(
        "build_target_scheme",
        FIF.SEARCH,
        tr("识别方案"),
        tr("副本名称识别会进入挑战页读取副本信息；掉落物识别根据列表中的掉落物匹配副本，异常时可尝试切换方案"),
        texts=choice_texts("build_target_scheme"),
        parent=host.card_parent,
    )
    host.buildTargetPlanarOrnamentWeeklyCountCard = RangeSettingCard1(
        "build_target_ornament_weekly_count",
        [0, 7],
        UiIcon.DIAMOND,
        tr("每周饰品提取次数"),
        tr("目标有足够资源后，执行饰品提取的次数，其余时间执行侵蚀隧洞"),
        parent=host.card_parent,
    )
    host.buildTargetUseUserInstanceWhenOnlyErosionAndOrnamentCard = SwitchSettingCard1(
        FIF.SYNC,
        tr("仅识别到侵蚀隧洞/饰品提取时使用自定义副本"),
        tr("开启后，当培养目标仅包含侵蚀隧洞和饰品提取时，清体力将改用你在体力设置中配置的副本"),
        "build_target_use_user_instance_when_only_erosion_and_ornament",
        parent=host.card_parent,
    )
    return host.finish("power", (
        ("borrowEnableCard", ('borrowCharacterEnableCard', 'borrowFriendsCard', 'borrowScrollTimesCard')),
        ("buildTargetEnableCard", ('buildTargetSchemeCard', 'buildTargetPlanarOrnamentWeeklyCountCard', 'buildTargetUseUserInstanceWhenOnlyErosionAndOrnamentCard')),
    ))
