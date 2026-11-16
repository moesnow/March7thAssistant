import sys
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt

from module.config.config import Config
from tasks.weekly.currency_wars_strategy import (
    DEFAULT_STRATEGY, HIGH_ANAXA, HIGH_FIREFLY, HIGH_SERVAL, PROMOTION_CAP_DIFFICULTY, STRATEGY_ID,
)


@pytest.mark.skipif(sys.platform != "win32", reason="原生设置界面仅在 Windows 验证")
@pytest.mark.parametrize(("saved_limit", "expected"), [(None, 240), ("bad", 240), (120, 120)])
def test_currency_wars_time_limit_is_at_the_bottom_and_saves_minutes(qtbot, tmp_path, monkeypatch, saved_limit, expected):
    import app.setting_interface as settings

    path = tmp_path / "config.yaml"
    contents = "currencywars_strategy: s2_anaxa\n"
    if saved_limit is not None:
        contents += f"currencywars_time_limit: {saved_limit}\n"
    path.write_text(contents, encoding="utf-8")
    config = Config.__new__(Config)
    Config.__init__(config, "assets/config/version.txt", "assets/config/config.example.yaml", str(path))
    monkeypatch.setattr("module.config.cfg", config)
    monkeypatch.setattr("app.card.comboboxsettingcard2.cfg", config)
    monkeypatch.setattr("app.card.spinboxsettingcard1.cfg", config)
    monkeypatch.setattr(settings, "cfg", config)
    widget = settings.SettingInterface()
    qtbot.addWidget(widget)

    group = widget.CurrencywarsGroup
    widget.stackedWidget.setCurrentWidget(group)
    widget.show()
    card = widget.currencywarsTimeLimitCard
    assert card.parent() is group
    assert card.y() > widget.currencywarsFastModeCard.geometry().bottom()
    assert card.spinBox.value() == expected
    assert (card.spinBox.minimum(), card.spinBox.maximum()) == (0, 1440)
    card.spinBox.setValue(360)
    assert config.yaml.load(path.read_text(encoding="utf-8"))["currencywars_time_limit"] == 360
    card.spinBox.setValue(0)
    assert config.yaml.load(path.read_text(encoding="utf-8"))["currencywars_time_limit"] == 0


@pytest.mark.skipif(sys.platform != "win32", reason="原生设置界面仅在 Windows 验证")
@pytest.mark.parametrize("legacy", ("aglaea", "seele"))
def test_currency_wars_old_config_requires_explicit_migration(qtbot, tmp_path, monkeypatch, legacy):
    import app.setting_interface as settings

    path = tmp_path / "config.yaml"
    path.write_text(f"currencywars_strategy: {legacy}\n", encoding="utf-8")
    config = Config.__new__(Config)
    Config.__init__(config, "assets/config/version.txt", "assets/config/config.example.yaml", str(path))
    monkeypatch.setattr("module.config.cfg", config)
    monkeypatch.setattr(settings, "cfg", config)
    widget = settings.SettingInterface()
    qtbot.addWidget(widget)
    assert config.get_value("currencywars_strategy") == legacy
    assert widget.currencywarsStrategyCard is not None
    widget.currencywarsStrategyCard.button.click()
    config._load_config()
    assert config.get_value("currencywars_strategy") == STRATEGY_ID
    assert widget.currencywarsStrategySelectCard.comboBox.currentData() == STRATEGY_ID
    assert widget.currencywarsStrategyCard.isHidden()


@pytest.mark.skipif(sys.platform != "win32", reason="原生设置界面仅在 Windows 验证")
@pytest.mark.parametrize(("configured", "displayed"), [
    (None, DEFAULT_STRATEGY),
    (DEFAULT_STRATEGY, DEFAULT_STRATEGY),
    (STRATEGY_ID, STRATEGY_ID),
    (HIGH_ANAXA, HIGH_ANAXA),
    (HIGH_FIREFLY, None),
    (HIGH_SERVAL, None),
])
def test_currency_wars_settings_lists_default_and_both_anaxa_strategies(qtbot, tmp_path, monkeypatch, configured, displayed):
    import app.setting_interface as settings

    path = tmp_path / "config.yaml"
    path.write_text(f"currencywars_strategy: {configured}\n" if configured else "{}\n", encoding="utf-8")
    config = Config.__new__(Config)
    Config.__init__(config, "assets/config/version.txt", "assets/config/config.example.yaml", str(path))
    monkeypatch.setattr("module.config.cfg", config)
    monkeypatch.setattr("app.card.comboboxsettingcard2.cfg", config)
    monkeypatch.setattr(settings, "cfg", config)
    widget = settings.SettingInterface()
    qtbot.addWidget(widget)

    assert widget.currencywarsStrategyCard is None
    combo = widget.currencywarsStrategySelectCard.comboBox
    assert [combo.itemData(index) for index in range(combo.count())] == [DEFAULT_STRATEGY, STRATEGY_ID, HIGH_ANAXA]
    assert combo.currentData() == displayed
    config._load_config()
    assert config.get_value("currencywars_strategy") == (configured or DEFAULT_STRATEGY)
    if displayed is None:
        assert combo.text() == settings.tr("实验性")
        combo.setCurrentIndex(0)
        config._load_config()
        assert config.get_value("currencywars_strategy") == DEFAULT_STRATEGY


@pytest.mark.skipif(sys.platform != "win32", reason="原生设置界面仅在 Windows 验证")
def test_currency_wars_unfinished_match_defaults_to_restart_and_saves_resume(qtbot, tmp_path, monkeypatch):
    import app.setting_interface as settings

    path = tmp_path / "config.yaml"
    path.write_text("currencywars_strategy: s2_anaxa\n", encoding="utf-8")
    config = Config.__new__(Config)
    Config.__init__(config, "assets/config/version.txt", "assets/config/config.example.yaml", str(path))
    monkeypatch.setattr("module.config.cfg", config)
    monkeypatch.setattr("app.card.comboboxsettingcard2.cfg", config)
    monkeypatch.setattr(settings, "cfg", config)
    widget = settings.SettingInterface()
    qtbot.addWidget(widget)

    card = widget.currencywarsUnfinishedMatchCard
    assert card.parent() is widget.currencywarsStrategySelectCard.view
    combo = card.comboBox
    assert combo.currentData() == "restart"
    combo.setCurrentIndex(combo.findData("resume"))
    config._load_config(save=False)
    assert config.get_value("currencywars_unfinished_match") == "resume"


@pytest.mark.skipif(sys.platform != "win32", reason="原生设置界面仅在 Windows 验证")
def test_currency_wars_investment_priority_defaults_to_strategy_and_saves_catalog(qtbot, tmp_path, monkeypatch):
    import app.setting_interface as settings

    path = tmp_path / "config.yaml"
    path.write_text("currencywars_strategy: default\n", encoding="utf-8")
    config = Config.__new__(Config)
    Config.__init__(config, "assets/config/version.txt", "assets/config/config.example.yaml", str(path))
    monkeypatch.setattr("module.config.cfg", config)
    monkeypatch.setattr("app.card.comboboxsettingcard2.cfg", config)
    monkeypatch.setattr(settings, "cfg", config)
    widget = settings.SettingInterface()
    qtbot.addWidget(widget)

    card = widget.currencywarsInvestmentPriorityCard
    strategy = widget.currencywarsStrategySelectCard
    widget.resize(1050, 800)
    widget.show()
    widget.stackedWidget.setCurrentWidget(widget.CurrencywarsGroup)
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


@pytest.mark.skipif(sys.platform != "win32", reason="原生设置界面仅在 Windows 验证")
def test_currency_wars_quick_presets(qtbot, tmp_path, monkeypatch):
    import app.setting_interface as settings

    path = tmp_path / "config.yaml"
    path.write_text(
        "currencywars_strategy: aglaea\ncurrencywars_enable: false\ncurrencywars_timestamp: 123\n"
        "currencywars_investment_priority: catalog\ncurrencywars_unfinished_match: resume\n",
        encoding="utf-8",
    )
    config = Config.__new__(Config)
    Config.__init__(config, "assets/config/version.txt", "assets/config/config.example.yaml", str(path))
    monkeypatch.setattr("module.config.cfg", config)
    monkeypatch.setattr("app.card.comboboxsettingcard2.cfg", config)
    monkeypatch.setattr("app.card.switchsettingcard1.cfg", config)
    monkeypatch.setattr(settings, "cfg", config)
    monkeypatch.setattr(settings.InfoBar, "success", Mock())
    widget = settings.SettingInterface()
    qtbot.addWidget(widget)
    preset = widget.currencywarsPresetCard

    assert preset.parent() is widget.CurrencywarsGroup
    assert widget.currencywarsStrategySelectCard.isHidden()
    for button, expected in (
        (preset.leftButton, ("overclock", "lowest", DEFAULT_STRATEGY, True)),
        (preset.middleButton, ("overclock", PROMOTION_CAP_DIFFICULTY, STRATEGY_ID, False)),
        (preset.rightButton, ("normal", "highest", HIGH_ANAXA, False)),
    ):
        button.click()
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
        assert widget.currencywarsStrategyCard.isHidden()
        assert not widget.currencywarsStrategySelectCard.isHidden()
        assert config.get_value("currencywars_enable") is False
        assert config.get_value("currencywars_timestamp") == 123
        assert config.get_value("currencywars_investment_priority") == "catalog"
        assert config.get_value("currencywars_unfinished_match") == "resume"
