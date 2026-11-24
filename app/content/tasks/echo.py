from qfluentwidgets import FluentIcon as FIF
from app.card.comboboxsettingcard2 import ComboBoxSettingCard2
from module.localization import tr
from module.search.setting_text import choice_texts


def build(host):
    host.echoStartDayCard = ComboBoxSettingCard2(
        "echo_of_war_start_day_of_week", FIF.DATE_TIME, tr("周几开始执行历战余响"),
        texts=choice_texts("echo_of_war_start_day_of_week"), parent=host.card_parent,
    )
    return host.finish("echo")
