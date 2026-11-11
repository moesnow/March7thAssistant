import sys
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from tasks.power import power as desktop
from tasks.power.policy import CAVERN, GOLDEN_CALYX, PowerError, SupportDemand
from tasks.touch import power as touch


MATERIALS = [GOLDEN_CALYX, "回忆之蕾", 2]
RELICS = [CAVERN, "睿治之径", 1]


def config(**overrides):
    values = dict(power_plan=[MATERIALS], power_plan_keep=False, power_plan_continue=True,
                  instance_type=CAVERN, instance_names={CAVERN: RELICS[1]}, build_target_enable=False,
                  get_value=Mock(side_effect=lambda key, default=None: default), set_value=Mock(),
                  save_timestamp=Mock(), refresh_hour=4)
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize("backend", [desktop, touch], ids=["pc", "touch"])
@pytest.mark.parametrize("keep", [False, True])
@pytest.mark.parametrize("continue_default", [False, True])
def test_material_plan_before_default_relics(monkeypatch, backend, keep, continue_default):
    cfg = config(power_plan_keep=keep, power_plan_continue=continue_default)
    monkeypatch.setattr(backend, "cfg", cfg)
    runs = []

    def run_instance(kind, name, planned, **kwargs):
        runs.append((kind, name, planned))
        if planned is not None:
            yield 1
            yield 1

    if backend is desktop:
        monkeypatch.setattr(desktop.Power, "_run_instance", run_instance)
        assert desktop.Power.run(skip_weekly_cleanup=True, support=SupportDemand())
    else:
        monkeypatch.setattr(touch, "_run_instance", run_instance)
        assert touch.run()

    assert runs == [tuple(MATERIALS)] + ([(CAVERN, RELICS[1], None)] if continue_default else [])
    assert cfg.set_value.call_args_list == ([] if keep else [
        call("power_plan", [[GOLDEN_CALYX, MATERIALS[1], 1]]), call("power_plan", []),
    ])


@pytest.mark.parametrize("platform", ["win32", "android"])
@pytest.mark.parametrize("continue_default", [False, True])
def test_touch_plan_continuation_is_the_same_on_every_platform(monkeypatch, platform, continue_default):
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(touch, "cfg", config(power_plan_continue=continue_default))
    runs = []

    def run_instance(kind, name, planned, **kwargs):
        runs.append((kind, name, planned))
        if planned is not None:
            yield planned

    monkeypatch.setattr(touch, "_run_instance", run_instance)
    assert touch.run()
    assert runs == [tuple(MATERIALS)] + ([(CAVERN, RELICS[1], None)] if continue_default else [])


@pytest.mark.parametrize("backend", [desktop, touch], ids=["pc", "touch"])
def test_insufficient_power_preserves_current_and_later_plan(monkeypatch, backend):
    cfg = config(power_plan=[MATERIALS, RELICS])
    monkeypatch.setattr(backend, "cfg", cfg)
    runs = Mock(side_effect=lambda *args, **kwargs: iter([1]))
    if backend is desktop:
        monkeypatch.setattr(desktop.Power, "_run_instance", runs)
        assert desktop.Power.run(skip_weekly_cleanup=True, support=SupportDemand())
    else:
        monkeypatch.setattr(touch, "_run_instance", runs)
        assert touch.run()
    assert runs.call_count == 1
    assert runs.call_args.args == tuple(MATERIALS)
    cfg.set_value.assert_called_once_with("power_plan", [[GOLDEN_CALYX, MATERIALS[1], 1], RELICS])


@pytest.mark.parametrize("failure", ["余额识别失败", "退出副本失败"])
def test_pc_writes_confirmed_progress_before_later_failure(monkeypatch, failure):
    cfg = config(power_plan=[["invalid"], MATERIALS, RELICS])
    monkeypatch.setattr(desktop, "cfg", cfg)

    def settled(*args, **kwargs):
        yield 1
        raise PowerError(failure)

    monkeypatch.setattr(desktop.Power, "_run_instance", settled)
    with pytest.raises(PowerError, match=failure):
        desktop.Power.execute_power_plan()
    cfg.set_value.assert_called_once_with("power_plan", [["invalid"], [GOLDEN_CALYX, MATERIALS[1], 1], RELICS])


@pytest.mark.parametrize("due,cleanup_succeeds", [(False, True), (True, False), (True, True)])
def test_weekly_cleanup_records_only_confirmed_completion(monkeypatch, due, cleanup_succeeds):
    cfg = config(get_value=Mock(side_effect=lambda key, default: {
        "break_down_level_four_relicset": True, "weekly_relic_cleanup_day_of_week": 5,
    }.get(key, default)))
    monkeypatch.setattr(desktop, "cfg", cfg)
    is_due = Mock(return_value=due)
    clean = Mock(return_value=cleanup_succeeds)
    monkeypatch.setattr(desktop.Date, "is_weekly_day_due", is_due)
    monkeypatch.setattr(desktop.WeeklyRelicCleanup, "run", clean)
    if due and not cleanup_succeeds:
        with pytest.raises(RuntimeError, match="每周遗器清理未完成"):
            desktop.Power.run_weekly_relic_cleanup()
    else:
        desktop.Power.run_weekly_relic_cleanup()
    is_due.assert_called_once_with(0, 5, 4)
    assert clean.call_count == due
    assert cfg.save_timestamp.call_args_list == ([call("weekly_relic_cleanup_timestamp")] if due and cleanup_succeeds else [])
