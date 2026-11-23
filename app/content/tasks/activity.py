from qfluentwidgets import FluentIcon as FIF
from app.common.icon import UiIcon
from app.card.switchsettingcard1 import SwitchSettingCard1, SwitchSettingCardGardenofplenty
from module.localization import tr


def build(host):
    host.activityDailyCheckInEnableCard = SwitchSettingCard1(
        FIF.COMPLETED,
        tr('每日签到'),
        tr("自动领取「星轨专票」或「星琼」，包含巡星之礼、巡光之礼和庆典祝礼活动"),
        "activity_dailycheckin_enable",
        parent=host.card_parent,
    )
    host.activityGardenOfPlentyEnableCard = SwitchSettingCardGardenofplenty(
        UiIcon.LEAF,
        tr('花藏繁生'),
        tr("存在双倍次数时体力优先「拟造花萼」"),
        "activity_gardenofplenty_enable",
        parent=host.card_parent,
    )
    host.activityRealmOfTheStrangeEnableCard = SwitchSettingCard1(
        UiIcon.DIAMOND,
        tr('异器盈界'),
        tr("存在双倍次数时体力优先「侵蚀隧洞」"),
        "activity_realmofthestrange_enable",
        parent=host.card_parent,
    )
    host.activityPlanarFissureEnableCard = SwitchSettingCard1(
        UiIcon.CUBE,
        tr('位面分裂'),
        tr("存在双倍次数时体力优先「饰品提取」"),
        "activity_planarfissure_enable",
        parent=host.card_parent,
    )
    host.activityJourneyHighlightsNotificationEnableCard = SwitchSettingCard1(
        FIF.CALENDAR,
        tr('活动热点通知'),
        tr("每次运行时发送带有活动热点截图的通知"),
        "activity_journey_highlights_notification_enable",
        parent=host.card_parent,
    )
    return host.finish("activity")
