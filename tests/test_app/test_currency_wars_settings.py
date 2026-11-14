import sys
from unittest.mock import Mock

import pytest

from module.config.config import Config
from tasks.weekly.currency_wars_strategy import HIGH_ANAXA, HIGH_FIREFLY, HIGH_SERVAL, STRATEGY_ID


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
    assert widget.currencywarsStrategyCard.isHidden()


@pytest.mark.skipif(sys.platform != "win32", reason="原生设置界面仅在 Windows 验证")
@pytest.mark.parametrize(("configured", "displayed"), [
    ("default", STRATEGY_ID),
    (STRATEGY_ID, STRATEGY_ID),
    (HIGH_ANAXA, HIGH_ANAXA),
    (HIGH_FIREFLY, None),
    (HIGH_SERVAL, None),
])
def test_currency_wars_settings_lists_only_anaxa(qtbot, tmp_path, monkeypatch, configured, displayed):
    import app.setting_interface as settings

    path = tmp_path / "config.yaml"
    path.write_text(f"currencywars_strategy: {configured}\n", encoding="utf-8")
    config = Config.__new__(Config)
    Config.__init__(config, "assets/config/version.txt", "assets/config/config.example.yaml", str(path))
    monkeypatch.setattr("module.config.cfg", config)
    monkeypatch.setattr("app.card.comboboxsettingcard2.cfg", config)
    monkeypatch.setattr(settings, "cfg", config)
    widget = settings.SettingInterface()
    qtbot.addWidget(widget)

    assert widget.currencywarsStrategyCard is None
    combo = widget.currencywarsStrategySelectCard.comboBox
    assert [combo.itemData(index) for index in range(combo.count())] == [STRATEGY_ID, HIGH_ANAXA]
    assert combo.currentData() == displayed
    config._load_config()
    assert config.get_value("currencywars_strategy") == configured
    if displayed is None:
        assert combo.text() == settings.tr("实验性")
        combo.setCurrentIndex(0)
        config._load_config()
        assert config.get_value("currencywars_strategy") == STRATEGY_ID


@pytest.mark.skipif(sys.platform != "win32", reason="原生设置界面仅在 Windows 验证")
def test_currency_wars_quick_presets(qtbot, tmp_path, monkeypatch):
    import app.setting_interface as settings

    path = tmp_path / "config.yaml"
    path.write_text(
        "currencywars_strategy: aglaea\ncurrencywars_enable: false\ncurrencywars_timestamp: 123\n",
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
        (preset.leftButton, ("overclock", "lowest", STRATEGY_ID, True)),
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
