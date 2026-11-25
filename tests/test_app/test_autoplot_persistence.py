"""自动对话总开关在界面重建后应保持与运行状态一致。"""

import sys
from unittest.mock import Mock

import pytest


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="自动对话界面仅在 Windows 上启用")


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_options_follow_the_card_and_save_each_change_once(qtbot, monkeypatch):
    from PySide6.QtWidgets import QVBoxLayout, QWidget
    from qfluentwidgets import FluentIcon, Theme, qconfig, setTheme
    from app.toolbox import autoplot

    config = Mock()
    config.get_value.side_effect = lambda key, default=None: default
    monkeypatch.setattr(autoplot, "cfg", config)
    host = QWidget()
    qtbot.addWidget(host)
    card = autoplot.AutoPlotCard(FluentIcon.CHAT, host)
    QVBoxLayout(host).addWidget(card)
    host.resize(350, 180)
    host.show()
    initial = card.geometry()
    old_theme = qconfig.theme
    try:
        for enabled in (True, False, True):
            card.button.click()
            popup = card._flyout
            assert popup.isVisible() and card.options.isVisibleTo(popup)
            before = popup.height()
            config.reset_mock()
            with qtbot.waitSignal(autoplot.signalBus.hotkeyChangedSignal):
                card.hotkeyToggleCheckBox.setChecked(enabled)
            qtbot.waitUntil(lambda: popup.height() != before)
            assert (popup.height() > before) == enabled
            assert card.hotkeyHintLabel.isVisible() == enabled
            config.set_value.assert_called_once_with("hotkey_toggle_autoplot_enable", enabled)
            config.set_values.assert_not_called()
            with qtbot.waitSignal(card.optionsChanged):
                card.autoSkipCheckBox.click()
            config.set_values.assert_called_once()
            assert config.set_values.call_args.args[0]["autoplot_skip_enable"] == card.autoSkipCheckBox.isChecked()
            setTheme(Theme.DARK if enabled else Theme.LIGHT, save=False)
            with monkeypatch.context() as translation:
                translation.setattr(autoplot, "tr", lambda source: "new " + source)
                card.retranslateUi()
                assert card.autoSkipCheckBox.text().startswith("new ")
            card.retranslateUi()
            assert card._flyout is popup and card.geometry() == initial
            popup.close()
            assert not popup.isVisible()
        card.button.click()
        host.showMinimized()
        qtbot.waitUntil(lambda: not popup.isVisible())
        host.showNormal()
        card.button.click()
        host.close()
        assert not popup.isVisible()
    finally:
        setTheme(old_theme, save=False)


def test_autoplot_switch_persists_and_restores_running_state(qapp, monkeypatch):
    from app.toolbox import autoplot as card_module
    import app.tools_interface as tools_module

    values = {}

    class FakeConfig:
        def get_value(self, key, default=None):
            return values.get(key, default)

        def set_value(self, key, value):
            values[key] = value

        def set_values(self, updates):
            values.update(updates)

    fake_config = FakeConfig()
    monkeypatch.setattr(card_module, "cfg", fake_config)
    monkeypatch.setattr(tools_module, "cfg", fake_config)
    start = Mock()
    stop = Mock()
    update_options = Mock()
    monkeypatch.setattr(tools_module.tool, "start", start)
    monkeypatch.setattr(tools_module.tool, "stop_plot", stop)
    monkeypatch.setattr(tools_module.tool, "update_plot_options", update_options)
    monkeypatch.setattr(tools_module.InfoBar, "success", Mock())
    monkeypatch.setattr(tools_module.InfoBar, "info", Mock())

    first = tools_module.ToolsInterface()
    assert not first.automaticPlotCard.getSwitchState()
    start.assert_not_called()

    first.automaticPlotCard.switchButton.setChecked(True)
    assert values["autoplot_enable"] is False
    start.assert_called_once_with("plot")

    # 默认不恢复，即使配置中有旧的开启状态。
    values["autoplot_enable"] = True
    fresh = tools_module.ToolsInterface()
    assert not fresh.automaticPlotCard.getSwitchState()
    assert start.call_count == 1

    # 已开启自动对话时再启用记忆，也要保存当前状态。
    first.automaticPlotCard.rememberStateCheckBox.setChecked(True)
    assert values["autoplot_remember_enable"] is True
    assert values["autoplot_enable"] is True
    start.assert_called_once_with("plot")

    restored = tools_module.ToolsInterface()
    assert restored.automaticPlotCard.getSwitchState()
    assert start.call_count == 2
    assert update_options.call_count == 2

    restored.setDesktopTwinHosting(True)
    stop.assert_called_once_with()
    restored.toggleAutoPlot()
    assert restored.automaticPlotCard.getSwitchState() and start.call_count == 2
    restored.setDesktopTwinHosting(False)
    restored.setDesktopTwinHosting(False)
    assert start.call_count == 3
    restored.toggleAutoPlot()
    assert values["autoplot_enable"] is False
    assert stop.call_count == 2

    disabled = tools_module.ToolsInterface()
    assert not disabled.automaticPlotCard.getSwitchState()
    assert start.call_count == 3

    disabled.toggleAutoPlot()
    assert values["autoplot_enable"] is True
    disabled.automaticPlotCard.rememberStateCheckBox.setChecked(False)
    assert values["autoplot_enable"] is False
    assert disabled.automaticPlotCard.getSwitchState()
    assert not tools_module.ToolsInterface().automaticPlotCard.getSwitchState()
