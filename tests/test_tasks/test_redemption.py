from types import SimpleNamespace
from unittest.mock import Mock

from tasks.base.task_steps import run_steps
from tasks.daily import redemption


def test_redemption_get_returns_true_when_no_unused_codes_exist(monkeypatch):
    monkeypatch.setattr(redemption, "cfg", SimpleNamespace(cloud_game_enable=True, already_used_codes=["USED1"]))
    monkeypatch.setattr(redemption, "valid_codes_for_server", Mock(return_value=["USED1"]))
    start = Mock()
    monkeypatch.setattr(redemption.Redemption, "start", start)

    assert redemption.Redemption.get() is True
    start.assert_not_called()
    assert run_steps([("兑换码", redemption.Redemption.get)]) is True


def test_redemption_get_succeeds_when_fetched_code_was_already_redeemed_in_game(monkeypatch):
    monkeypatch.setattr(redemption, "valid_codes_for_server", Mock(return_value=["CODE1"]))
    monkeypatch.setattr(redemption, "screen", SimpleNamespace(change_to=Mock(), wait_for_screen_change=Mock()))
    monkeypatch.setattr(redemption, "get_game_controller", Mock(return_value=SimpleNamespace(copy=Mock())))
    monkeypatch.setattr(redemption, "time", SimpleNamespace(sleep=Mock()))

    used = []
    cfg = SimpleNamespace(
        cloud_game_enable=True,
        already_used_codes=used,
        set_value=Mock(side_effect=lambda k, v: used[:] if k != "already_used_codes" else None),
    )
    monkeypatch.setattr(redemption, "cfg", cfg)

    fake_auto = Mock()
    fake_auto.click_element.return_value = True
    fake_auto.find_element.return_value = ((0, 0), (1, 1))
    fake_auto.matched_text = "兑换码已被使用"
    monkeypatch.setattr(redemption, "auto", fake_auto)

    assert redemption.Redemption.get() is True
    assert "CODE1" in used
    assert redemption.Redemption.start(codes=["CODE1"]) is False


def test_redemption_get_returns_false_on_ui_error(monkeypatch):
    monkeypatch.setattr(redemption, "valid_codes_for_server", Mock(return_value=["CODE2"]))
    monkeypatch.setattr(redemption, "screen", SimpleNamespace(change_to=Mock(), wait_for_screen_change=Mock()))
    monkeypatch.setattr(redemption, "get_game_controller", Mock(return_value=SimpleNamespace(copy=Mock())))
    monkeypatch.setattr(redemption, "cfg", SimpleNamespace(cloud_game_enable=True, already_used_codes=[]))

    fake_auto = Mock()
    fake_auto.click_element.return_value = False
    monkeypatch.setattr(redemption, "auto", fake_auto)

    assert redemption.Redemption.get() is False
