"""自动对话总开关在界面重建后应保持与运行状态一致。"""

import sys
from unittest.mock import Mock

import pytest


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="自动对话界面仅在 Windows 上启用")


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("width", [600, 900])
def test_autoplot_expand_collapse_leaves_no_blank_strip(qapp, qtbot, monkeypatch, width):
    from PySide6.QtWidgets import QVBoxLayout, QWidget
    from qfluentwidgets import FluentIcon

    import app.card.autoplot_setting_card as card_module

    fake_config = Mock()
    fake_config.get_value.side_effect = lambda key, default=None: default
    monkeypatch.setattr(card_module, "cfg", fake_config)

    host = QWidget()
    qtbot.addWidget(host)
    layout = QVBoxLayout(host)
    card = card_module.AutoPlotSettingCard(FluentIcon.CHAT, "自动对话", "说明")
    layout.addWidget(card)
    layout.addStretch()
    host.resize(width, 800)
    host.show()
    qapp.processEvents()
    initial_height = card.height()
    assert initial_height == card.card.height()

    # 同时覆盖快捷键提示显隐后的高度更新，以及多次展开/收起。
    for show_hint in (False, True, False):
        with qtbot.waitSignal(card.expandAni.finished):
            card.setExpand(True)
        card.hotkeyToggleCheckBox.setChecked(show_hint)
        qapp.processEvents()
        assert card.view.height() == card.viewLayout.sizeHint().height()
        assert card.height() == card.card.height() + card.view.height()
        with qtbot.waitSignal(card.expandAni.finished):
            card.setExpand(False)
        qapp.processEvents()
        assert card.height() == initial_height


def test_autoplot_switch_persists_and_restores_running_state(qapp, monkeypatch):
    import app.card.autoplot_setting_card as card_module
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

    restored.toggleAutoPlot()
    assert values["autoplot_enable"] is False
    stop.assert_called_once_with()

    disabled = tools_module.ToolsInterface()
    assert not disabled.automaticPlotCard.getSwitchState()
    assert start.call_count == 2

    disabled.toggleAutoPlot()
    assert values["autoplot_enable"] is True
    disabled.automaticPlotCard.rememberStateCheckBox.setChecked(False)
    assert values["autoplot_enable"] is False
    assert disabled.automaticPlotCard.getSwitchState()
    assert not tools_module.ToolsInterface().automaticPlotCard.getSwitchState()
