import sys
from pathlib import Path

from module.localization import tr

import pytest
from PySide6.QtCore import Qt

from tasks.weekly.currency_wars_strategy import (
    DEFAULT_STRATEGY, HIGH_ANAXA, HIGH_FIREFLY, HIGH_SERVAL, PROMOTION_CAP_DIFFICULTY,
)


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="原生设置界面仅在 Windows 验证")


@pytest.fixture
def open_currency(qtbot, page_config, content_window):
    from app.task_interface import TaskInterface

    def open_page(yaml):
        config = page_config(yaml)
        interface = TaskInterface(content_window)
        qtbot.addWidget(interface)
        content_window.resize(1050, 800)
        interface.resize(content_window.size())
        content_window.show()
        interface.show()
        assert interface.showTask("currencywars")
        return config, interface.pages["currencywars"]

    return open_page


@pytest.mark.parametrize(("saved_limit", "expected"), [(None, 240), ("bad", 240), (120, 120)])
def test_currency_wars_time_limit_is_at_the_bottom_and_saves_minutes(open_currency, saved_limit, expected):
    contents = "currencywars_strategy: s2_anaxa_high\n"
    if saved_limit is not None:
        contents += f"currencywars_time_limit: {saved_limit}\n"
    config, page = open_currency(contents)
    widget = page.host

    card = widget.currencywarsTimeLimitCard
    section = page.views["advanced"]
    assert section.isAncestorOf(card)
    assert section.bodyLayout.itemAt(section.bodyLayout.count() - 1).widget() is card
    assert card.spinBox.value() == expected
    assert (card.spinBox.minimum(), card.spinBox.maximum()) == (0, 1440)
    card.spinBox.setValue(360)
    assert config.yaml.load(Path(config.config_path).read_text(encoding="utf-8"))["currencywars_time_limit"] == 360
    card.spinBox.setValue(0)
    assert config.yaml.load(Path(config.config_path).read_text(encoding="utf-8"))["currencywars_time_limit"] == 0


@pytest.mark.parametrize("legacy", ("aglaea", "seele", "s2_anaxa"))
def test_currency_wars_old_config_requires_explicit_migration(open_currency, legacy):
    config, page = open_currency(f"currencywars_strategy: {legacy}\n")
    widget = page.host
    assert config.get_value("currencywars_strategy") == legacy
    assert not page.notice.isHidden()
    page.notice.actionButton.click()
    config._load_config()
    assert config.get_value("currencywars_strategy") == HIGH_ANAXA
    assert widget.currencywarsStrategySelectCard.comboBox.currentData() == HIGH_ANAXA
    assert page.notice.isHidden()


@pytest.mark.parametrize(("configured", "displayed"), [
    (None, DEFAULT_STRATEGY),
    (DEFAULT_STRATEGY, DEFAULT_STRATEGY),
    (HIGH_ANAXA, HIGH_ANAXA),
    (HIGH_FIREFLY, None),
    (HIGH_SERVAL, None),
])
def test_currency_wars_settings_lists_default_and_anaxa_strategies(open_currency, configured, displayed):
    config, page = open_currency(f"currencywars_strategy: {configured}\n" if configured else "{}\n")
    widget = page.host

    assert page.notice.isHidden()
    combo = widget.currencywarsStrategySelectCard.comboBox
    assert [combo.itemData(index) for index in range(combo.count())] == [DEFAULT_STRATEGY, HIGH_ANAXA]
    assert combo.currentData() == displayed
    config._load_config()
    assert config.get_value("currencywars_strategy") == (configured or DEFAULT_STRATEGY)
    if displayed is None:
        assert combo.text() == tr("实验性")
        combo.setCurrentIndex(0)
        config._load_config()
        assert config.get_value("currencywars_strategy") == DEFAULT_STRATEGY


def test_currency_wars_unfinished_match_defaults_to_restart_and_saves_resume(open_currency):
    config, page = open_currency("currencywars_strategy: s2_anaxa_high\n")
    widget = page.host

    card = widget.currencywarsUnfinishedMatchCard
    assert card.parent() is widget.currencywarsStrategySelectCard.view
    combo = card.comboBox
    assert combo.currentData() == "restart"
    combo.setCurrentIndex(combo.findData("resume"))
    config._load_config(save=False)
    assert config.get_value("currencywars_unfinished_match") == "resume"


def test_currency_wars_investment_priority_defaults_to_strategy_and_saves_catalog(open_currency, qtbot):
    config, page = open_currency("currencywars_strategy: default\n")
    widget = page.host

    card = widget.currencywarsInvestmentPriorityCard
    strategy = widget.currencywarsStrategySelectCard
    assert card.parent() is strategy.view
    assert not strategy.isExpand
    collapsed_height = strategy.height()
    with qtbot.waitSignal(strategy.expandAni.finished):
        qtbot.mouseClick(strategy.card.expandButton, Qt.MouseButton.LeftButton)
    assert strategy.isExpand and strategy.height() > collapsed_height
    for child in (card, widget.currencywarsUnfinishedMatchCard):
        assert not child.visibleRegion().isEmpty()
    combo = card.comboBox
    assert combo.currentData() == "strategy"
    combo.setCurrentIndex(combo.findData("catalog"))
    config._load_config(save=False)
    assert config.get_value("currencywars_investment_priority") == "catalog"


def test_currency_wars_quick_presets(open_currency):
    config, page = open_currency(
        "currencywars_strategy: aglaea\ncurrencywars_enable: false\ncurrencywars_timestamp: 123\n"
        "currencywars_investment_priority: catalog\ncurrencywars_unfinished_match: resume\n",
    )
    widget = page.host
    preset = page.header.presetButton
    assert page.header.isAncestorOf(preset)
    assert widget.currencywarsStrategySelectCard.isHidden()
    actions = preset.menu().actions()
    expected_values = (("overclock", "lowest", DEFAULT_STRATEGY, True),
                       ("overclock", PROMOTION_CAP_DIFFICULTY, HIGH_ANAXA, False),
                       ("normal", "highest", HIGH_ANAXA, False))
    assert len(actions) == len(expected_values)
    for action, expected in zip(actions, expected_values):
        action.trigger()
        config._load_config(save=False)
        assert (
            config.get_value("currencywars_type"),
            config.get_value("currencywars_rank_difficulty"),
            config.get_value("currencywars_strategy"),
            config.get_value("currencywars_fast_mode"),
        ) == expected
        assert (
            widget.currencywarsTypeCard.comboBox.currentData(),
            widget.currencywarsRankDifficultyCard.comboBox.currentData(),
            widget.currencywarsStrategySelectCard.comboBox.currentData(),
            widget.currencywarsFastModeCard.switchButton.isChecked(),
        ) == expected
        assert page.notice.isHidden()
        assert not widget.currencywarsStrategySelectCard.isHidden()
        assert config.get_value("currencywars_enable") is False
        assert config.get_value("currencywars_timestamp") == 123
        assert config.get_value("currencywars_investment_priority") == "catalog"
        assert config.get_value("currencywars_unfinished_match") == "resume"
