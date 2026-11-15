from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from tasks.power import instance, power
from tasks.power.policy import CAVERN, ECHO, GOLDEN_CALYX, ORNAMENT, BattleDefeat, PowerError, RelicBagFull, SupportDemand
from utils.pause import RunStopRequested


@pytest.mark.parametrize(
    "clicks_to_enter, ready_at, error, expected_clicks",
    [
        (1, 0, None, 1),
        (3, 0, None, 3),
        (5, 0, None, 5),
        (1, 0.75, None, 1),
        (1, 8, None, 5),
        (None, 0, PowerError("等待进入战斗超时"), 5),
        (1, 0, PowerError("等待进入战斗超时"), 1),
        (None, 0, RunStopRequested(), 1),
        (None, 0, RelicBagFull("遗器背包已满"), 1),
    ],
    ids=["first-click", "retry", "last-click", "transition-during-popup-read", "slow-transition",
         "stuck", "entry-timeout", "user-stop", "bag-full"],
)
def test_pc_power_retries_start_challenge_until_button_disappears(
    monkeypatch, clicks_to_enter, ready_at, error, expected_clicks,
):
    name = "密伶之径"
    auto = Mock()
    now = 0.0

    def sleep(seconds):
        nonlocal now
        now += seconds

    def find(target, kind, *_args, **kwargs):
        clicks = auto.click_element_with_pos.call_count
        if clicks and isinstance(error, RunStopRequested):
            raise error
        if kwargs.get("crop") == instance.DIALOG:
            sleep(0.3)
        entered = clicks_to_enter is not None and clicks >= clicks_to_enter and now >= ready_at
        if target == "开始挑战":
            assert kwargs.get("take_screenshot", True)
            if entered:
                return None
            return ((1720 + clicks, 985), (1800 + clicks, 1005))
        if target == instance.FIGHT_AGAIN:
            return error is None and entered
        if isinstance(error, RelicBagFull) and "背包内遗器持有数量已达上限" in target:
            auto.matched_text = "背包内遗器持有数量已达上限"
            return True
        return None

    auto.find_element.side_effect = find
    auto.click_element.return_value = True
    auto.click_element_with_pos.return_value = True
    cfg = SimpleNamespace(instance_names_challenge_count={}, tp_before_instance=False,
                          instance_team_enable=False, borrow_enable=False)
    monkeypatch.setattr(instance, "auto", auto)
    monkeypatch.setattr(instance, "cfg", cfg)
    monkeypatch.setattr(instance, "time", SimpleNamespace(monotonic=lambda: now, sleep=sleep))
    monkeypatch.setattr(power, "cfg", cfg)
    monkeypatch.setattr(power.Power, "get", Mock(return_value=65))
    monkeypatch.setattr(instance.Instance, "prepare_instance", Mock(return_value=True))
    monkeypatch.setattr(instance.Instance, "prepare_payment", Mock(return_value=(1, 40)))
    monkeypatch.setattr(instance.Instance, "read_balance", Mock(side_effect=[65, 25]))
    monkeypatch.setattr(instance.Instance, "clean_full_bag", Mock(return_value=False))
    finish = Mock()
    monkeypatch.setattr(instance.Instance, "complete_run", finish)

    if error is None:
        assert power.Power.process(CAVERN, name, planned_attempts=1) == 1
        finish.assert_called_once_with(CAVERN)
    else:
        with pytest.raises(type(error), match=str(error) or None):
            power.Power.process(CAVERN, name, planned_attempts=1)
        finish.assert_not_called()
    assert auto.click_element_with_pos.call_args_list == [
        call(((1720 + index, 985), (1800 + index, 1005))) for index in range(expected_clicks)
    ]


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
    assert balance.call_args_list == [call(use_supplement=True)] + [call(use_supplement=False)] * 3


@pytest.mark.parametrize("after", [46, PowerError("余额读数失败")], ids=["balance-readable", "balance-ocr-failure"])
def test_pc_power_plan_records_the_selected_batch_on_victory(monkeypatch, after):
    name = "回忆之蕾"
    cfg = SimpleNamespace(
        power_plan=[[GOLDEN_CALYX, name, 4]], power_plan_keep=False, power_plan_continue=False,
        instance_names_challenge_count={}, tp_before_instance=False, set_value=Mock(),
    )
    unreadable_result = Mock(side_effect=PowerError("未能确认已结算的挑战次数"))
    monkeypatch.setattr(instance, "read_number", unreadable_result)
    monkeypatch.setattr(power, "cfg", cfg)
    monkeypatch.setattr(power.Power, "get", Mock(return_value=86))
    monkeypatch.setattr(instance.Instance, "prepare_instance", Mock(return_value=True))
    monkeypatch.setattr(instance.Instance, "prepare_payment", Mock(return_value=(4, 40)))
    monkeypatch.setattr(instance.Instance, "read_balance", Mock(side_effect=[86, after]))
    monkeypatch.setattr(instance.Instance, "start_instance", Mock(return_value=False))
    monkeypatch.setattr(instance.Instance, "wait_fight", Mock(return_value=True))
    monkeypatch.setattr(instance.Instance, "complete_run", Mock())

    if isinstance(after, PowerError):
        with pytest.raises(PowerError, match="余额读数失败"):
            power.Power.run(skip_weekly_cleanup=True, support=SupportDemand())
    else:
        assert power.Power.run(skip_weekly_cleanup=True, support=SupportDemand())

    cfg.set_value.assert_called_once_with("power_plan", [])
    instance.Instance.start_instance.assert_called_once()
    unreadable_result.assert_not_called()
