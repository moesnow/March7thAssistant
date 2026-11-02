"""GUI 接入配置应保留参数边界，并在首次启用时引导配置。"""

import sys
from unittest.mock import MagicMock

import pytest

@pytest.fixture
def settings(qapp, monkeypatch):
    import app.card.agent_decision_setting_card as module

    values = {
        "divergent_decision_enable": False,
        "divergent_decision_command": [],
        "divergent_decision_timeout": 120,
        "divergent_decision_context": "优先生存",
    }
    config = MagicMock()
    config.get_value.side_effect = lambda key, default=None: values.get(key, default)
    config.set_value.side_effect = lambda key, value: values.update({key: value})
    config.set_values.side_effect = values.update
    monkeypatch.setattr(module, "cfg", config)
    return module, values, config


@pytest.fixture
def host(qtbot):
    from PySide6.QtWidgets import QWidget
    window = QWidget()
    window.resize(1100, 760)
    qtbot.addWidget(window)
    return window


def test_toggle_saves_and_restores_without_running_program(settings, qtbot):
    module, values, config = settings
    values["divergent_decision_command"] = [sys.executable, "some adapter.py"]
    card = module.AgentDecisionSettingCard()
    qtbot.addWidget(card)
    card.switchButton.setChecked(True)
    assert values["divergent_decision_enable"] is True
    recreated = module.AgentDecisionSettingCard()
    qtbot.addWidget(recreated)
    assert recreated.switchButton.isChecked()
    recreated.switchButton.setChecked(False)
    assert values["divergent_decision_enable"] is False
    assert config.set_value.call_count == 2


def test_first_enable_cancel_keeps_disabled(settings, qtbot, monkeypatch):
    module, values, config = settings
    card = module.AgentDecisionSettingCard()
    qtbot.addWidget(card)
    configure = MagicMock(return_value=False)
    monkeypatch.setattr(card, "_configure", configure)
    card.switchButton.setChecked(True)
    configure.assert_called_once()
    assert not card.switchButton.isChecked()
    config.set_value.assert_not_called()


def test_first_enable_configures_then_enables(settings, qtbot, monkeypatch):
    module, values, config = settings
    card = module.AgentDecisionSettingCard()
    qtbot.addWidget(card)

    def configure():
        values["divergent_decision_command"] = [sys.executable]
        return True

    monkeypatch.setattr(card, "_configure", configure)
    card.switchButton.setChecked(True)
    assert card.switchButton.isChecked()
    assert values["divergent_decision_enable"] is True


def test_dialog_round_trip_preserves_argument_boundaries(settings, qtbot, host):
    module, values, _ = settings
    command = [sys.executable, "D:/中文 路径/adapter.py", "--context", "包含 空格 '与引号'"]
    values["divergent_decision_command"] = command
    dialog = module.AgentDecisionDialog(host)
    qtbot.addWidget(dialog)
    assert dialog.values() == {key: value for key, value in values.items() if key != "divergent_decision_enable"}
    dialog.timeoutSpinBox.setValue(300)
    assert dialog.values()["divergent_decision_timeout"] == 300


@pytest.mark.parametrize("program, arguments", [
    ("", ""), ("missing-agent-123456.exe", ""),
    (sys.executable, "a\n\nb"), (sys.executable, "a\n" * 32),
])
def test_invalid_input_cannot_be_saved(settings, qtbot, host, program, arguments):
    module, _, config = settings
    dialog = module.AgentDecisionDialog(host)
    qtbot.addWidget(dialog)
    dialog.programEdit.setText(program)
    dialog.argumentsEdit.setPlainText(arguments)
    dialog.accept()
    assert dialog.result() == 0
    assert not dialog.errorLabel.isHidden()
    assert dialog.isEnabled()
    config.set_values.assert_not_called()


def test_configure_saves_atomically_and_cancel_does_not_save(settings, qtbot, monkeypatch):
    module, values, config = settings
    card = module.AgentDecisionSettingCard()
    qtbot.addWidget(card)
    dialog = MagicMock()
    dialog.exec.return_value = 1
    new = {"divergent_decision_command": [sys.executable], "divergent_decision_timeout": 45,
           "divergent_decision_context": "队伍由用户提供"}
    dialog.values.return_value = new
    monkeypatch.setattr(module, "AgentDecisionDialog", lambda parent: dialog)
    assert card._configure()
    config.set_values.assert_called_once_with(new)
    assert values["divergent_decision_enable"] is False
    config.reset_mock()
    dialog.exec.return_value = 0
    assert not card._configure()
    config.set_values.assert_not_called()
