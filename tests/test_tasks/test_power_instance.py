from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from tasks.power import instance, power
from tasks.power.policy import ECHO, ORNAMENT, BattleDefeat, PowerError


@pytest.mark.parametrize(
    "button, victory_at, clicks",
    [
        ("尝试重连", 7, ["尝试重连"]),
        ("退出游戏", 7, ["尝试重连", instance.CONFIRM]),
        (None, 4, []),
        ("尝试重连", None, ["尝试重连"] * 3),
    ],
    ids=["reconnect", "confirm-fallback", "title-only", "persistent-disconnect"],
)
def test_wait_fight_limits_reconnects_to_confirmed_dialogs(monkeypatch, button, victory_at, clicks):
    now = 0.0
    auto = Mock()

    def sleep(seconds):
        nonlocal now
        now += seconds

    def find(target, kind, *_args, **kwargs):
        if target == instance.FIGHT_AGAIN:
            return victory_at is not None and now >= victory_at
        if target == instance.PAUSE:
            return True
        if kind != "text" or now < 2:
            return False
        if "连接中断" in target:
            auto.matched_text = "连接中断"
            return True
        assert target == ("尝试重连", "退出游戏")
        assert kwargs["take_screenshot"] is kwargs["need_ocr"] is False
        return button in target

    auto.find_element.side_effect = find
    auto.click_element.side_effect = lambda target, *_args, **_kwargs: target == button or target == instance.CONFIRM
    monkeypatch.setattr(instance, "auto", auto)
    monkeypatch.setattr(instance, "time", SimpleNamespace(monotonic=lambda: now, sleep=sleep))
    monkeypatch.setattr(instance, "game_option_enabled", lambda *_args: False)

    if victory_at is None:
        with pytest.raises(PowerError, match="游戏连接中断"):
            instance.Instance.wait_fight()
    else:
        assert instance.Instance.wait_fight()
    assert [entry.args[0] for entry in auto.click_element.call_args_list] == clicks


@pytest.mark.parametrize("instance_type", [ORNAMENT, ECHO])
def test_defeat_retries_stop_without_recording_completion(monkeypatch, instance_type):
    name = "测试副本"
    battle = Mock()
    battle.read_echo_rewards.return_value = 3
    battle.read_balance.return_value = 200
    battle.prepare_payment.return_value = (1, 40)
    battle.wait_fight.return_value = False
    balance = Mock(return_value=200)
    monkeypatch.setattr(power, "Instance", battle)
    monkeypatch.setattr(power.Power, "get", balance)
    monkeypatch.setattr(power, "get_raw_instance_names", lambda: {instance_type: {name: name}})
    monkeypatch.setattr(power, "cfg", SimpleNamespace(instance_names_challenge_count={}, tp_before_instance=False))

    run = power.Power._run_instance(instance_type, name, 1)
    with pytest.raises(BattleDefeat):
        next(run)
    assert battle.start_instance.call_count == battle.exit_defeat.call_count == 3
    battle.completed_waves.assert_not_called()
    assert balance.call_args_list == [call(use_supplement=True)] + [call(use_supplement=False)] * 3
