"""自动对话总开关在界面重建后应保持与运行状态一致。"""

import sys
from unittest.mock import Mock

import pytest


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="自动对话界面仅在 Windows 上启用")


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_autoplot_switch_persists_and_restores_running_state(qapp, monkeypatch):
    import app.card.autoplot_setting_card as card_module
    import app.tools_interface as tools_module

    values = {}

    class FakeConfig:
        def get_value(self, key, default=None):
            return values.get(key, default)

        def set_value(self, key, value):
            values[key] = value

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
    assert values["autoplot_enable"] is True
    start.assert_called_once_with("plot")

    restored = tools_module.ToolsInterface()
    assert restored.automaticPlotCard.getSwitchState()
    assert start.call_count == 2
    assert update_options.call_count == 2

    restored.toggleAutoPlot()
    assert values["autoplot_enable"] is False
    stop.assert_called_once_with()

    disabled = tools_module.ToolsInterface()
    assert not disabled.automaticPlotCard.getSwitchState()
    assert start.call_count == 2
