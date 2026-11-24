from PySide6.QtCore import QSignalBlocker
from app.common.icon import UiIcon
from app.card.comboboxsettingcard2 import ComboBoxSettingCard2
from app.card.switchsettingcard1 import SwitchSettingCard1
from app.card.spinboxsettingcard1 import SpinBoxSettingCard1
from app.card.expandable_switch_setting_card import ExpandableComboBoxSettingCard
from module.config import cfg
from module.localization import tr
from module.search.setting_text import choice_texts
from tasks.weekly.currency_wars_strategy import (
    DEFAULT_STRATEGY as CURRENCY_WARS_DEFAULT,
    HIGH_ANAXA,
    STRATEGY_NAMES,
)


def build(host):
    host.currencywarsTypeCard = ComboBoxSettingCard2(
        "currencywars_type",
        UiIcon.OPTIONS,
        tr('类别'),
        '',
        texts=choice_texts("currencywars_type"),
        parent=host.card_parent,
    )
    host.currencywarsBonusEnableCard = SwitchSettingCard1(
        UiIcon.DIAMOND,
        tr('自动执行位面饰品快速提取'),
        tr("在领取积分奖励后自动执行位面饰品快速提取消耗深度沉浸器"),
        "currencywars_bonus_enable",
        parent=host.card_parent,
    )
    host.currencywarsRankDifficultyCard = ComboBoxSettingCard2(
        "currencywars_rank_difficulty",
        UiIcon.GAUGE,
        tr('职级难度'),
        '',
        texts=choice_texts("currencywars_rank_difficulty"),
        parent=host.card_parent,
    )
    visible_strategies = (CURRENCY_WARS_DEFAULT, HIGH_ANAXA)
    host.currencywarsStrategySelectCard = ExpandableComboBoxSettingCard(
        "currencywars_strategy",
        UiIcon.LIST,
        tr("货币战争策略"),
        "",
        texts={tr(STRATEGY_NAMES[value]): value for value in visible_strategies},
        parent=host.card_parent,
    )
    if cfg.get_value("currencywars_strategy") not in visible_strategies:
        with QSignalBlocker(host.currencywarsStrategySelectCard.comboBox):
            host.currencywarsStrategySelectCard.comboBox.setCurrentIndex(-1)
        host.currencywarsStrategySelectCard.comboBox.setPlaceholderText(tr("实验性"))
    host.currencywarsInvestmentPriorityCard = ComboBoxSettingCard2(
        "currencywars_investment_priority",
        UiIcon.OPTIONS,
        tr("投资选项优先级"),
        "",
        texts=choice_texts("currencywars_investment_priority"),
        parent=host.card_parent,
    )
    host.currencywarsUnfinishedMatchCard = ComboBoxSettingCard2(
        "currencywars_unfinished_match",
        UiIcon.OPTIONS,
        tr("未完成对局"),
        "",
        texts=choice_texts("currencywars_unfinished_match"),
        parent=host.card_parent,
    )
    host.currencywarsFastModeCard = SwitchSettingCard1(
        UiIcon.ROCKET,
        tr('启用速通模式'),
        tr("仅在首领节点处理装备"),
        "currencywars_fast_mode",
        parent=host.card_parent,
    )
    host.currencywarsTimeLimitCard = SpinBoxSettingCard1(
        "currencywars_time_limit",
        UiIcon.TIMER,
        tr("总时限"),
        tr("单次运行的分钟数，0 表示不限时"),
        default=240,
        parent=host.card_parent,
    )
    return host.finish("currencywars", (
        ("currencywarsStrategySelectCard", ('currencywarsInvestmentPriorityCard', 'currencywarsUnfinishedMatchCard')),
    ))
