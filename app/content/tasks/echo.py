from qfluentwidgets import FluentIcon as FIF
from app.card.comboboxsettingcard2 import ComboBoxSettingCard2
from module.localization import tr

WEEKDAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def build(host):
    host.echoStartDayCard = ComboBoxSettingCard2(
        "echo_of_war_start_day_of_week", FIF.DATE_TIME, tr("周几开始执行历战余响"),
        texts={tr(name): i for i, name in enumerate(WEEKDAYS, 1)}, parent=host.card_parent,
    )
    return host.finish("echo")
