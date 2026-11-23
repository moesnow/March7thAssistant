from qfluentwidgets import FluentIcon as FIF
from app.card.switchsettingcard1 import SwitchSettingCard1
from app.card.pushsettingcard1 import PushSettingCardTeam
from module.localization import tr


def build(host):
    host.dailyMaterialEnableCard = SwitchSettingCard1(
        FIF.CHECKBOX,
        tr('通过 “合成材料” 完成任务'),
        tr("请确保背包中有足够的 “熄灭原核” 用于合成 “微光原核” "),
        "daily_material_enable",
        parent=host.card_parent,
    )
    host.dailyMemoryOneEnableCard = SwitchSettingCard1(
        FIF.CHECKBOX,
        tr('通过 “回忆一” 完成任务'),
        tr("请解锁混沌回忆并配置了队伍后再打开该选项"),
        "daily_memory_one_enable",
        parent=host.card_parent,
    )
    host.dailyMemoryOneTeamCard = PushSettingCardTeam(
        tr('修改'),
        FIF.FLAG,
        tr("回忆一队伍"),
        "daily_memory_one_team",
        parent=host.card_parent,
    )
    return host.finish("daily")
