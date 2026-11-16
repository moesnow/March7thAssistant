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
    initial_button_reads = 0

    def sleep(seconds):
        nonlocal now
        now += seconds

    def find(target, kind, *_args, **kwargs):
        nonlocal initial_button_reads
        clicks = auto.click_element_with_pos.call_count
        if clicks and isinstance(error, RunStopRequested):
            raise error
        if kwargs.get("crop") == instance.DIALOG:
            sleep(0.3)
        entered = clicks_to_enter is not None and clicks >= clicks_to_enter and now >= ready_at
        if target == "开始挑战":
            assert kwargs.get("take_screenshot", True)
            if not clicks:
                initial_button_reads += 1
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
    monkeypatch.setattr(instance.Instance, "select_waves", Mock(return_value=1))
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
    assert initial_button_reads == 1


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


def test_exit_after_victory_reuses_the_confirmed_main_screen(monkeypatch):
    auto = Mock()
    screen = Mock()
    screen.change_to.side_effect = RuntimeError("重复截图失败")
    monkeypatch.setattr(instance, "auto", auto)
    monkeypatch.setattr(instance, "screen", screen)
    monkeypatch.setattr(instance, "time", Mock())

    instance.Instance.complete_run(GOLDEN_CALYX)

    screen.check_screen.assert_called_once_with("main")
    screen.change_to.assert_not_called()
    auto.press_key.assert_not_called()


@pytest.mark.parametrize("instance_type", [ORNAMENT, ECHO])
def test_defeat_retries_stop_without_recording_completion(monkeypatch, instance_type):
    name = "测试副本"
    battle = Mock()
    battle.read_echo_rewards.return_value = 3
    battle.select_waves.return_value = 1
    battle.wait_fight.return_value = False
    balance = Mock(return_value=200)
    stock = Mock(return_value=1)
    monkeypatch.setattr(power, "Instance", battle)
    monkeypatch.setattr(power.Power, "get", balance)
    monkeypatch.setattr(power.Power, "get_immersifier_count", stock)
    monkeypatch.setattr(power, "get_raw_instance_names", lambda: {instance_type: {name: name}})
    monkeypatch.setattr(power, "cfg", SimpleNamespace(
        instance_names_challenge_count={}, tp_before_instance=False, use_reserved_trailblaze_power=True,
    ))

    run = power.Power._run_instance(instance_type, name, 1)
    with pytest.raises(BattleDefeat):
        next(run)
    assert battle.start_instance.call_count == battle.exit_defeat.call_count == 3
    balance.assert_called_once_with(use_supplement=True)
    assert stock.call_count == (1 if instance_type == ORNAMENT else 0)


def test_pc_power_plan_reuses_budget_for_defeat_retry_same_batch_and_smaller_batch(monkeypatch):
    name = "回忆之蕾"
    later_plan = [CAVERN, "密伶之径", 1]
    cfg = SimpleNamespace(
        power_plan=[[GOLDEN_CALYX, name, 10], later_plan], power_plan_keep=False, power_plan_continue=False,
        instance_names_challenge_count={GOLDEN_CALYX: 4}, tp_before_instance=False, set_value=Mock(),
    )
    forbidden_read = Mock(side_effect=PowerError("重复读数失败"))
    select = Mock(side_effect=lambda _kind, requested: requested)
    balance = Mock(side_effect=[95, PowerError("重复读余额")])
    monkeypatch.setattr(instance, "read_number", forbidden_read)
    monkeypatch.setattr(power, "cfg", cfg)
    monkeypatch.setattr(power.Power, "get", balance)
    monkeypatch.setattr(instance.Instance, "prepare_instance", Mock(return_value=True))
    monkeypatch.setattr(instance.Instance, "select_waves", select)
    monkeypatch.setattr(instance.Instance, "start_instance", Mock(return_value=False))
    monkeypatch.setattr(instance.Instance, "start_instance_again", Mock())
    monkeypatch.setattr(instance.Instance, "wait_fight", Mock(side_effect=[False, True, True, True]))
    monkeypatch.setattr(instance.Instance, "exit_defeat", Mock())
    monkeypatch.setattr(instance.Instance, "complete_run", Mock())

    assert power.Power.run(skip_weekly_cleanup=True, support=SupportDemand())
    assert cfg.set_value.call_args_list == [
        call("power_plan", [[GOLDEN_CALYX, name, remaining], later_plan]) for remaining in (6, 2, 1)
    ]
    assert select.call_args_list == [call(GOLDEN_CALYX, waves) for waves in (4, 4, 1)]
    instance.Instance.start_instance_again.assert_called_once_with()
    instance.Instance.exit_defeat.assert_called_once_with()
    assert instance.Instance.complete_run.call_count == 2
    balance.assert_called_once_with(use_supplement=True)
    forbidden_read.assert_not_called()


@pytest.mark.parametrize("quota", [1, 0], ids=["rewarded-echo", "practice"])
def test_pc_echo_finishes_without_reading_the_result_meter(monkeypatch, quota):
    battle = Mock()
    battle.read_echo_rewards.side_effect = [quota, 0]
    battle.select_waves.return_value = 1
    map_balance = Mock(return_value=90) if quota else Mock(side_effect=PowerError("地图余额读数失败"))
    config = SimpleNamespace(instance_names_challenge_count={}, tp_before_instance=False, save_timestamp=Mock())
    monkeypatch.setattr(power, "Instance", battle)
    monkeypatch.setattr(power.Power, "get", map_balance)
    monkeypatch.setattr(power, "cfg", config)
    monkeypatch.setattr(power, "screen", Mock())

    assert power.Power.process(ECHO, "毁灭的开端", planned_attempts=1) == 1
    assert battle.read_echo_rewards.call_count == (2 if quota else 1)
    assert map_balance.call_count == (1 if quota else 0)
    battle.complete_run.assert_called_once_with(ECHO)
    config.save_timestamp.assert_called_once_with("echo_of_war_timestamp")


def test_pc_immersifier_only_uses_stock_without_reading_power(monkeypatch):
    name = "浴火钢心"
    config = SimpleNamespace(instance_names_challenge_count={ORNAMENT: 1}, tp_before_instance=False)
    monkeypatch.setattr(power, "cfg", config)
    monkeypatch.setattr(power.Power, "get", Mock(side_effect=PowerError("地图余额读数失败")))
    stock = Mock(return_value=1)
    monkeypatch.setattr(power.Power, "get_immersifier_count", stock)
    monkeypatch.setattr(instance.Instance, "prepare_instance", Mock(return_value=True))
    monkeypatch.setattr(instance.Instance, "complete_run", Mock())
    monkeypatch.setattr(instance.Instance, "select_waves", Mock(return_value=1))
    monkeypatch.setattr(instance.Instance, "start_instance", Mock(return_value=False))
    monkeypatch.setattr(instance.Instance, "start_instance_again", Mock())
    monkeypatch.setattr(instance.Instance, "wait_fight", Mock(return_value=True))
    monkeypatch.setattr(power, "screen", Mock())

    assert power.Power.process(ORNAMENT, name, immersifier_only=True) == 1
    instance.Instance.start_instance.assert_called_once()
    instance.Instance.start_instance_again.assert_not_called()
    power.Power.get.assert_not_called()
    stock.assert_called_once_with()


def test_pc_ornament_mixed_repeat_and_defeat_reuse_the_initial_budget(monkeypatch):
    name = "浴火钢心"
    later_plan = [CAVERN, "密伶之径", 1]
    config = SimpleNamespace(
        power_plan=[[ORNAMENT, name, 15], later_plan], power_plan_keep=False, power_plan_continue=False,
        instance_names_challenge_count={ORNAMENT: 6}, tp_before_instance=False, set_value=Mock(),
    )
    balance = Mock(side_effect=[174, PowerError("重复读余额")])
    stock = Mock(side_effect=[10, PowerError("重复读库存")])
    battle = Mock()
    battle.select_waves.side_effect = lambda _kind, waves: waves
    battle.wait_fight.side_effect = [True, False, True, True]
    plan_batch = Mock(wraps=power.plan_paid_batch)
    monkeypatch.setattr(power, "cfg", config)
    monkeypatch.setattr(power, "Instance", battle)
    monkeypatch.setattr(power, "plan_paid_batch", plan_batch)
    monkeypatch.setattr(power.Power, "get", balance)
    monkeypatch.setattr(power.Power, "get_immersifier_count", stock)

    assert power.Power.run(skip_weekly_cleanup=True, support=SupportDemand())
    assert plan_batch.call_args_list == [
        call(6, 174, 40, immersifiers=10),
        call(6, 174, 40, immersifiers=4),
        call(6, 174, 40, immersifiers=4),
        call(3, 94, 40, immersifiers=0),
        call(1, 14, 40, immersifiers=0),
    ]
    assert battle.select_waves.call_args_list == [call(ORNAMENT, waves) for waves in (6, 6, 2)]
    battle.start_instance_again.assert_called_once_with()
    battle.exit_defeat.assert_called_once_with()
    assert config.set_value.call_args_list == [
        call("power_plan", [[ORNAMENT, name, remaining], later_plan]) for remaining in (9, 3, 1)
    ]
    stock.assert_called_once_with()
    balance.assert_called_once_with(use_supplement=True)


@pytest.mark.parametrize("entry", ["divergent", "universe"])
def test_universe_bonus_delegates_to_immersifier_only_power_task(monkeypatch, entry):
    from tasks.weekly import divergent_universe as divergent
    from tasks.weekly import universe

    module = divergent if entry == "divergent" else universe
    config = SimpleNamespace(
        weekly_divergent_timestamp=1, refresh_hour=4, weekly_divergent_bonus_enable=True,
        universe_bonus_enable=True, instance_names={ORNAMENT: "浴火钢心"}, build_target_enable=False,
        notify_template={"SimulatedUniverseRewardClaimed": "已领取积分奖励", "SimulatedUniverseCompleted": "已完成"},
    )
    monkeypatch.setattr(power, "cfg", config)
    monkeypatch.setattr(module, "cfg", config)
    monkeypatch.setattr(module.Base, "send_notification_with_screenshot", Mock())
    monkeypatch.setattr(module, "screen", Mock())
    auto = Mock()
    auto.find_element.return_value = False
    auto.click_element.return_value = True
    auto.get_single_line_text.return_value = ""
    monkeypatch.setattr(module, "auto", auto)
    monkeypatch.setattr(power.Power, "process", Mock(return_value=1))

    if entry == "divergent":
        task = divergent.DivergentUniverse()
        monkeypatch.setattr(task, "run", Mock(return_value=True))
        monkeypatch.setattr(task, "get_reward", Mock(return_value=True))
        monkeypatch.setattr(divergent.Date, "is_next_mon_x_am", Mock(return_value=False))
        assert task.start()
    else:
        monkeypatch.setattr(universe, "wait_for_weekly_reward", Mock(return_value=True))
        monkeypatch.setattr(universe, "time", SimpleNamespace(sleep=Mock()))
        universe.Universe.get_reward("divergent")

    power.Power.process.assert_called_once_with(ORNAMENT, "浴火钢心", immersifier_only=True)
    auto.get_single_line_text.assert_not_called()
