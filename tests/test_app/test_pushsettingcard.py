import sys
import pytest

from app.card import pushsettingcard1 as cards
from app.card.pushsettingcard1 import get_key_from_value, PushSettingCardKey


@pytest.mark.parametrize(("card_type", "key"), [
    (cards.PushSettingCardInstance, "instance_names"),
    (cards.PushSettingCardInstanceChallengeCount, "instance_names_challenge_count"),
    (cards.PushSettingCardNotifyTemplate, "notify_template"),
    (cards.PushSettingCardTeam, "daily_memory_one_team"),
    (cards.PushSettingCardFriends, "borrow_friends"),
    (cards.PushSettingCardPowerPlan, "power_plan"),
])
def test_settings_dialog_follows_window_resize(qtbot, monkeypatch, page_config, card_type, key):
    from PySide6.QtWidgets import QWidget
    from qfluentwidgets import FluentIcon, MessageBox

    page_config()
    window = QWidget()
    qtbot.addWidget(window)
    window.show()
    card = card_type("修改", FluentIcon.EDIT, key, key, window)
    monkeypatch.setattr(MessageBox, "exec", MessageBox.show)
    card.button.click()
    dialog = window.findChild(MessageBox)
    assert dialog.isVisible()

    window.resize(1024, 768)
    assert dialog.size() == window.size()
    assert dialog.contentLabel.text() == ""


def test_power_plan_preserves_yaml_integer_counts_and_uneditable_rows(qtbot):
    from PySide6.QtWidgets import QWidget
    from ruamel.yaml import YAML
    from app.card.messagebox_custom import MessageBoxPowerPlan

    parent = QWidget()
    qtbot.addWidget(parent)
    plans = YAML().load(
        "[[拟造花萼（金）, 回忆之蕾, 03], [旧副本, 遗留名称, 1], [拟造花萼（金）, 遗留名称, 1], [历战余响, 毁灭的开端, 0x2]]"
    )
    dialog = MessageBoxPowerPlan("体力计划", plans, parent)
    assert dialog.validate_inputs()
    assert dialog.get_plans() == [["拟造花萼（金）", "回忆之蕾", 3], plans[1], plans[2], ["历战余响", "毁灭的开端", 2]]

    dialog.plan_rows[1]["delete_button"].click()
    assert dialog.get_plans() == [["拟造花萼（金）", "回忆之蕾", 3], plans[2], ["历战余响", "毁灭的开端", 2]]


@pytest.mark.parametrize("stored", [{}, {"power_plan_continue": False}])
@pytest.mark.parametrize("accepted", [True, False])
def test_power_plan_dialog_saves_continue_option_only_on_confirmation(qtbot, monkeypatch, stored, accepted):
    from types import SimpleNamespace
    from unittest.mock import Mock

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QWidget
    from qfluentwidgets import FluentIcon

    from app.card import pushsettingcard1 as cards

    values = {"power_plan": [], "power_plan_keep": False, **stored}
    save = Mock()
    monkeypatch.setattr(cards, "cfg", SimpleNamespace(get_value=values.get, set_values=save))
    initial = values.get("power_plan_continue", True)

    class PlanDialog(cards.MessageBoxPowerPlan):
        def exec(self):
            assert self.continueAfterPlanCheckBox.isChecked() is initial
            self.continueAfterPlanCheckBox.setChecked(not initial)
            save.assert_not_called()
            button = self.yesButton if accepted else self.cancelButton
            QTimer.singleShot(0, button.click)
            return super().exec()

    monkeypatch.setattr(cards, "MessageBoxPowerPlan", PlanDialog)
    parent = QWidget()
    qtbot.addWidget(parent)
    card = cards.PushSettingCardPowerPlan("配置", FluentIcon.CALENDAR, "体力计划", "power_plan", parent)
    card.button.click()

    if accepted:
        save.assert_called_once_with({
            "power_plan": [], "power_plan_keep": False, "power_plan_continue": not initial,
        })
    else:
        save.assert_not_called()


class TestGetKeyValue:
    def test_found(self):
        m = {"a": 1, "b": 2, "c": 3}
        assert get_key_from_value(2, m) == "b"

    def test_not_found(self):
        m = {"a": 1, "b": 2}
        assert get_key_from_value(99, m) is None

    def test_empty_map(self):
        assert get_key_from_value(1, {}) is None

    def test_first_match(self):
        m = {"a": 1, "b": 1}
        result = get_key_from_value(1, m)
        assert result in ("a", "b")

    def test_none_value(self):
        m = {"a": None, "b": 2}
        assert get_key_from_value(None, m) == "a"


class TestFormatKeyDisplay:
    def test_f_key(self):
        assert PushSettingCardKey._format_key_display("f1") == "F1"
        assert PushSettingCardKey._format_key_display("f12") == "F12"

    def test_single_letter(self):
        assert PushSettingCardKey._format_key_display("a") == "A"
        assert PushSettingCardKey._format_key_display("z") == "Z"

    def test_empty_string(self):
        assert PushSettingCardKey._format_key_display("") == ""

    def test_none(self):
        assert PushSettingCardKey._format_key_display(None) is None

    def test_special_key(self):
        result = PushSettingCardKey._format_key_display("space")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_enter_key(self):
        result = PushSettingCardKey._format_key_display("enter")
        assert isinstance(result, str)

    def test_f_key_not_digit(self):
        # "fa" is not f+digit, should not be treated as function key
        result = PushSettingCardKey._format_key_display("fa")
        assert isinstance(result, str)
