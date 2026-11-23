from app.common.icon import UiIcon
from app.card.comboboxsettingcard2 import ComboBoxSettingCard2
from app.card.switchsettingcard1 import SwitchSettingCardTeam
from app.card.rangesettingcard1 import RangeSettingCard1
from app.card.expandable_switch_setting_card import ExpandableSwitchSettingCard
from module.localization import tr


def build(host):
    host.fightOperationModeCard = ComboBoxSettingCard2(
        "fight_operation_mode",
        UiIcon.OPTIONS,
        tr('运行模式'),
        '',
        texts={tr('集成'): 'exe', tr('源码'): 'source'},
        parent=host.card_parent,
    )
    host.fightTimeoutCard = RangeSettingCard1(
        "fight_timeout",
        [1, 24],
        UiIcon.CLOCK,
        tr("锄大地超时"),
        tr("超过设定时间强制停止（单位小时）"),
        parent=host.card_parent,
    )
    host.fightTeamEnableCard = SwitchSettingCardTeam(
        UiIcon.PEOPLE_SWAP,
        tr('自动切换队伍'),
        None,
        "fight_team_enable",
        "fight_team_number",
        parent=host.card_parent,
    )
    host.fightMapVersionCard = ComboBoxSettingCard2(
        "fight_map_version",
        UiIcon.MAP,
        tr('地图版本'),
        '',
        texts={tr("不配置"): "不配置", tr("默认（疾跑）"): "default", tr("黄泉专用"): "HuangQuan", tr("获得特殊物品"): "reward"},
        parent=host.card_parent,
    )
    host.fightMainMapCard = ComboBoxSettingCard2(
        "fight_main_map",
        UiIcon.PLANET,
        tr('优先星球'),
        '',
        texts={tr("不配置"): "0", tr("空间站"): "1", tr("雅利洛"): "2", tr("仙舟"): "3", tr("匹诺康尼"): "4", tr("翁法罗斯"): 5, tr("二相乐园"): 6},
        parent=host.card_parent,
    )
    host.fightRewardEnableCard = ExpandableSwitchSettingCard(
        "fight_reward_enable",
        UiIcon.GIFT,
        tr('启用「特殊物品领取」'),
        tr("按下面对三项的选择写入锄大地的配置；关闭时完全不干预锄大地自己那边的设置"),
        parent=host.card_parent,
    )
    host.fightAllowSnackBuyCard = ComboBoxSettingCard2(
        "fight_allow_snack_buy",
        UiIcon.FOOD,
        tr('购买秘技零食并合成零食'),
        tr("每日获得特殊物品：购买秘技零食材料并合成零食"),
        texts={tr("不配置"): "不配置", tr("启用"): True, tr("停用"): False},
        parent=host.card_parent,
    )
    host.fightAllowMapBuyCard = ComboBoxSettingCard2(
        "fight_allow_map_buy",
        UiIcon.COIN,
        tr('购买代币与过期邮包'),
        tr("每周获得特殊物品：购买仙舟过期邮包与匹诺康尼艾迪恩代币"),
        texts={tr("不配置"): "不配置", tr("启用"): True, tr("停用"): False},
        parent=host.card_parent,
    )
    host.fightAllowMemoryTokenCard = ComboBoxSettingCard2(
        "fight_allow_memory_token",
        UiIcon.COIN_STACK,
        tr('获得翁法罗斯记忆代币'),
        tr("每周获得特殊物品：收集翁法罗斯忆质残晶"),
        texts={tr("不配置"): "不配置", tr("启用"): True, tr("停用"): False},
        parent=host.card_parent,
    )
    return host.finish("fight", (
        ("fightRewardEnableCard", ('fightAllowSnackBuyCard', 'fightAllowMapBuyCard', 'fightAllowMemoryTokenCard')),
    ))
