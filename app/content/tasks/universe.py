from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import MessageBox
from app.common.icon import UiIcon
from app.card.comboboxsettingcard2 import ComboBoxSettingCard2
from app.card.switchsettingcard1 import SwitchSettingCard1
from app.card.rangesettingcard1 import RangeSettingCard1
from app.card.expandable_switch_setting_card import ExpandableSwitchSettingCard
from app.card.stationprioritysettingcard import StationPrioritySettingCard
from app.common.mascot import Mascot
from app.components.mascot_dialog import add_mascot
from module.localization import tr, translations_of
from module.search.setting_text import choice_texts
from module.config import cfg
from PySide6.QtCore import QSignalBlocker


def confirm_external_enable(window):
    confirm = MessageBox(
        tr("启用前请确认用途"),
        tr("此选项及其子选项用于配置反复刷取遗器经验和灵之珠泪，直到达到每周上限。\n默认运行次数为每周 34 次。\n请确认你已经清楚了解这个功能的作用，并确保知道自己在做什么后再开启。"),
        window
    )
    confirm.yesButton.setText(tr("我已了解，继续开启"))
    confirm.cancelButton.setText(tr("取消"))
    add_mascot(confirm, Mascot.SERIOUS)

    return bool(confirm.exec())


def build(host):
    def confirm_external(checked):
        if checked and not confirm_external_enable(host.window):
            host.universeEnableCard.switchButton.setChecked(False)

    host.weeklyDivergentTypeCard = ComboBoxSettingCard2(
        "weekly_divergent_type",
        UiIcon.OPTIONS,
        tr('类别'),
        '',
        texts=choice_texts("weekly_divergent_type"),
        parent=host.card_parent,
    )
    host.weeklyDivergentBonusEnableCard = SwitchSettingCard1(
        UiIcon.DIAMOND,
        tr('自动执行饰品提取'),
        tr("在领取积分奖励后自动执行饰品提取消耗沉浸器"),
        "weekly_divergent_bonus_enable",
        parent=host.card_parent,
    )
    host.weeklyDivergentLevelCard = ComboBoxSettingCard2(
        "weekly_divergent_level",
        UiIcon.GAUGE,
        tr("难度等级"),
        "",
        texts={f"{tr('难度')} Ⅰ": 1, f"{tr('难度')} Ⅱ": 2, f"{tr('难度')} Ⅲ": 3, f"{tr('难度')} Ⅳ": 4, f"{tr('难度')} Ⅴ": 5, f"{tr('难度')} Ⅹ{tr('（星阶模式）')}": 6},
        parent=host.card_parent,
    )
    host.stationPriorityCard = StationPrioritySettingCard(
        UiIcon.LIST,
        tr('站点优先级'),
        tr("自定义差分宇宙「选择下一站」的站点优先级"),
        parent=host.card_parent,
    )
    host.weeklyDivergentStableModeCard = SwitchSettingCard1(
        FIF.SPEED_OFF,
        tr('启用低性能兼容模式'),
        tr("建议仅在低性能设备开启，可以提高事件和随意门交互的成功率（云游戏强制使用此模式）"),
        "weekly_divergent_stable_mode",
        parent=host.card_parent,
    )
    host.divergentAutoSaveCard = SwitchSettingCard1(
        FIF.SAVE_AS,
        tr("自动记录差分宇宙存档"),
        tr("探索成功后保存到第一个空存档位；存档已满时跳过"),
        "divergent_auto_save_enable",
        parent=host.card_parent,
    )
    host.universeEnableCard = ExpandableSwitchSettingCard(
        "universe_enable",
        UiIcon.PLANET,
        tr('启用模拟宇宙/差分宇宙 (Auto_Simulated_Universe)'),
        tr("通常用于反复刷取遗器经验和灵之珠泪（代替敌方掉落素材）直到每周上限"),
        parent=host.card_parent,
    )
    host.universeCategoryCard = ComboBoxSettingCard2(
        "universe_category",
        UiIcon.OPTIONS,
        tr('类别'),
        '',
        texts=choice_texts("universe_category"),
        parent=host.card_parent,
    )
    host.divergentTypeCard = ComboBoxSettingCard2(
        "divergent_type",
        UiIcon.OPTIONS,
        tr('选择差分宇宙时类别'),
        '',
        texts=choice_texts("divergent_type"),
        parent=host.card_parent,
    )
    host.universeBonusEnableCard = SwitchSettingCard1(
        UiIcon.GIFT,
        tr('自动领取模拟宇宙沉浸奖励'),
        tr("类别为“模拟宇宙”时，自动领取沉浸奖励"),
        "universe_bonus_enable",
        parent=host.card_parent,
    )
    host.universeFrequencyCard = ComboBoxSettingCard2(
        "universe_frequency",
        UiIcon.TIMER,
        tr('运行频率'),
        '',
        texts=choice_texts("universe_frequency"),
        parent=host.card_parent,
    )
    host.universeCountCard = RangeSettingCard1(
        "universe_count",
        [0, 34],
        UiIcon.REPEAT,
        tr("运行次数"),
        tr("注意中途停止不会计数，0 代表不指定，使用模拟宇宙原版逻辑"),
        parent=host.card_parent,
    )
    fates = {tr(name): name for name in ("不配置", "存护", "记忆", "虚无", "丰饶", "巡猎", "毁灭", "欢愉", "繁育", "智识")}
    host.universeFateCard = ComboBoxSettingCard2(
        "universe_fate",
        UiIcon.COMPASS,
        tr('命途（仅模拟宇宙生效）'),
        '',
        texts=fates,
        parent=host.card_parent,
    )
    # Previously saved by the old dialog in the display language. Show the matching
    # path without rewriting a user's external-tool configuration during construction.
    saved = cfg.get_value("universe_fate")
    combo = host.universeFateCard.comboBox
    if combo.findData(saved) < 0:
        for name in fates.values():
            if saved in translations_of(name).values():
                with QSignalBlocker(combo):
                    combo.setCurrentIndex(combo.findData(name))
                break
    host.universeDifficultyCard = RangeSettingCard1(
        "universe_difficulty",
        [0, 5],
        UiIcon.GAUGE,
        tr("难度 (0为不配置，仅模拟宇宙生效)"),
        "",
        parent=host.card_parent,
    )
    host.universeOperationModeCard = ComboBoxSettingCard2(
        "universe_operation_mode",
        UiIcon.OPTIONS,
        tr('运行模式'),
        '',
        texts=choice_texts("universe_operation_mode"),
        parent=host.card_parent,
    )
    host.universeEnableGpuCard = SwitchSettingCard1(
        FIF.COMMAND_PROMPT,
        tr('启用模拟宇宙 GPU 加速'),
        tr('开启后可能提升运行速度，若出现错误、异常或不稳定，请关闭此选项'),
        "universe_enable_gpu",
        parent=host.card_parent,
    )
    host.universeTimeoutCard = RangeSettingCard1(
        "universe_timeout",
        [1, 24],
        UiIcon.CLOCK,
        tr("模拟宇宙/差分宇宙超时"),
        tr("超过设定时间强制停止（单位小时）"),
        parent=host.card_parent,
    )
    host.universeEnableCard.switchChanged.connect(confirm_external)
    return host.finish("universe", (
        ("universeEnableCard", ('universeCategoryCard', 'divergentTypeCard', 'universeBonusEnableCard', 'universeFrequencyCard', 'universeCountCard', 'universeFateCard', 'universeDifficultyCard', 'universeOperationModeCard', 'universeEnableGpuCard', 'universeTimeoutCard')),
    ))
