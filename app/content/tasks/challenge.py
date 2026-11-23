from app.common.icon import UiIcon
from app.card.expandable_switch_setting_card import ExpandableTimestampSwitchSettingCard
from app.challenge_config_dialog import ChallengeConfigCard
from module.localization import tr


def build(host):
    host.forgottenhallEnableCard = ExpandableTimestampSwitchSettingCard(
        "forgottenhall_enable",
        "forgottenhall_timestamp",
        UiIcon.TARGET_ARROW,
        tr('启用混沌回忆'),
        tr("上次运行混沌回忆的时间"),
        "",
        parent=host.card_parent,
    )
    host.forgottenhallConfigCard = ChallengeConfigCard(
        UiIcon.PEOPLE_TEAM,
        tr("混沌回忆配置"), "forgottenhall", 12,
        parent=host.card_parent,
    )
    host.purefictionEnableCard = ExpandableTimestampSwitchSettingCard(
        "purefiction_enable",
        "purefiction_timestamp",
        UiIcon.TARGET_ARROW,
        tr('启用虚构叙事'),
        tr("上次运行虚构叙事的时间"),
        "",
        parent=host.card_parent,
    )
    host.purefictionConfigCard = ChallengeConfigCard(
        UiIcon.PEOPLE_TEAM,
        tr("虚构叙事配置"), "purefiction", 4,
        parent=host.card_parent,
    )
    host.ApocalypticEnableCard = ExpandableTimestampSwitchSettingCard(
        "apocalyptic_enable",
        "apocalyptic_timestamp",
        UiIcon.TARGET_ARROW,
        tr('启用末日幻影'),
        tr("上次运行末日幻影的时间"),
        "",
        parent=host.card_parent,
    )
    host.ApocalypticConfigCard = ChallengeConfigCard(
        UiIcon.PEOPLE_TEAM,
        tr("末日幻影配置"), "apocalyptic", 4,
        parent=host.card_parent,
    )
    return host.finish("challenge", (
        ("forgottenhallEnableCard", ('forgottenhallConfigCard',)),
        ("purefictionEnableCard", ('purefictionConfigCard',)),
        ("ApocalypticEnableCard", ('ApocalypticConfigCard',)),
    ))
