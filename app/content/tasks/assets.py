from qfluentwidgets import FluentIcon as FIF
from app.common.icon import UiIcon
from app.card.switchsettingcard1 import SwitchSettingCard1, TimestampSwitchSettingCard
from app.card.expandable_switch_setting_card import ExpandableWeeklyRelicSettingCard
from module.localization import tr


def build(host):
    host.weeklyRelicCleanupEnableCard = ExpandableWeeklyRelicSettingCard(
        "break_down_level_four_relicset",
        "weekly_relic_cleanup_day_of_week",
        FIF.FILTER,
        tr("每周清理遗器"),
        parent=host.card_parent,
    )
    host.smartRelicDiscardEnableCard = SwitchSettingCard1(
        FIF.DELETE,
        tr("启用智能弃置"),
        tr("按不匹配推荐角色和副属性 0 次筛选，分解已弃置及四星以下遗器"),
        "weekly_relic_smart_discard_enable",
        parent=host.card_parent,
    )
    host.relicBagCleanupCard = SwitchSettingCard1(
        FIF.FILTER, tr("满包时自动分解遗器"), tr("遇到遗器满包时分解四星及以下遗器"),
        "relic_bag_cleanup_enable",
        parent=host.card_parent,
    )
    host.selfMoldingResinEnableCard = TimestampSwitchSettingCard(
        FIF.CALENDAR,
        tr("启用「每月自动合成自塑尘脂」"),
        tr("每月自动尝试合成 2 个自塑尘脂，成功后记录时间，并在每月 1 号刷新"),
        "asset_self_molding_resin_enable",
        "asset_self_molding_resin_timestamp",
        tr("上次完成自塑尘脂合成的时间"),
        parent=host.card_parent,
    )
    host.emberSpecialPassEnableCard = TimestampSwitchSettingCard(
        FIF.CALENDAR,
        tr("启用「每月自动购买{item}」").format(item=tr("星轨专票")),
        tr("每月自动尝试在余烬兑换中购买「{item}」，点击最大值并确认后记录时间，并在每月 1 号刷新").format(item=tr("星轨专票")),
        "asset_ember_special_pass_enable",
        "asset_ember_special_pass_timestamp",
        tr("上次完成{item}购买的时间").format(item=tr("星轨专票")),
        parent=host.card_parent,
    )
    host.emberRegularPassEnableCard = TimestampSwitchSettingCard(
        FIF.CALENDAR,
        tr("启用「每月自动购买{item}」").format(item=tr("星轨通票")),
        tr("每月自动尝试在余烬兑换中购买「{item}」，点击最大值并确认后记录时间，并在每月 1 号刷新").format(item=tr("星轨通票")),
        "asset_ember_regular_pass_enable",
        "asset_ember_regular_pass_timestamp",
        tr("上次完成{item}购买的时间").format(item=tr("星轨通票")),
        parent=host.card_parent,
    )
    host.emberTracksOfDestinyEnableCard = TimestampSwitchSettingCard(
        FIF.CALENDAR,
        tr("启用「每月自动购买{item}」").format(item=tr("命运的足迹")),
        tr("每月自动尝试在余烬兑换中购买「{item}」，点击最大值并确认后记录时间，并在每月 1 号刷新").format(item=tr("命运的足迹")),
        "asset_ember_tracks_of_destiny_enable",
        "asset_ember_tracks_of_destiny_timestamp",
        tr("上次完成{item}购买的时间").format(item=tr("命运的足迹")),
        parent=host.card_parent,
    )
    host.lc3StarSuperimposeEnableCard = SwitchSettingCard1(
        UiIcon.STACK,
        tr("启用「3星光锥自动叠加」"),
        tr("缺乏维护，已禁用"),
        "asset_lc3_star_superimpose_enable",
        parent=host.card_parent,
    )
    host.lc3StarSuperimposeEnableCard.setEnabled(False)
    return host.finish("assets", (
        ("weeklyRelicCleanupEnableCard", ('smartRelicDiscardEnableCard',)),
    ))
