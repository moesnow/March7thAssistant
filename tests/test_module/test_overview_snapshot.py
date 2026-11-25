from dataclasses import replace
from datetime import datetime, timedelta
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from ruamel.yaml import YAML

from module.navigation import parse_link
from module.task_catalog import step_page
from module.overview import cards, history, readings
from module.overview.samples import sample_snapshot, _Config
from module.overview.snapshot import build_snapshot, make_greeting, time_greeting
from module.overview.types import LiveRun, PowerReading
from module.settings_registry import Scope, find_setting
from utils import runs


@pytest.mark.parametrize("state,pose", [("ready", "full"), ("running", "typing"), ("completed", "wave"),
                                        ("failed", "lost"), ("setup", "ok"), ("stopped", "full")])
def test_every_sample_is_complete(state, pose):
    sample = sample_snapshot(state)
    assert sample.unavailable == ()
    assert sample.greeting.state == state and sample.greeting.mascot == "chibi_" + pose
    assert len(sample.shortcuts) == 4
    for row in sample.plan:
        assert len(row.summary) <= 16 and parse_link(row.link) == ("task", step_page(row.id), "")
    for check in sample.checks:
        assert find_setting(parse_link(check.link)[1])
    if state == "running":
        assert sample.greeting.phase == "execute" and len(sample.schedule.names[0]) > 16
    if state == "setup":
        assert sample.schedule is None and sample.power.value is None


@pytest.mark.parametrize("status,before,after", [("failed", "failed", "ready"), ("stopped", "stopped", "ready"),
                                                ("success", "ready", "ready")])
def test_refresh_priority_and_later_success(status, before, after):
    sample = sample_snapshot("ready")
    now = datetime(2026, 11, 24, 3, 59, 59)
    last = replace(sample.last_run, ended_at=now, status=status)
    hist = history.History(last)
    def state(at, live=None, setup=None, records=hist):
        return make_greeting(at, live, setup, records, sample.plan, sample.daily).state
    assert state(now) == before and state(now + timedelta(seconds=1)) == after
    setup = sample_snapshot("setup").checks[0]
    assert state(now, setup=setup) == "setup"
    assert state(now, LiveRun("power", "清体力"), setup) == "running"
    assert state(now, records=history.History(replace(last, status="success"))) == "ready"


@pytest.mark.parametrize("hour,prefix", [(4, "晚上"), (5, "早上"), (10, "早上"), (11, "中午"), (13, "中午"),
                                         (14, "下午"), (17, "下午"), (18, "晚上"), (23, "晚上")])
def test_greeting_hours(hour, prefix):
    assert time_greeting(hour).startswith(prefix)


def test_readings_are_observed_values_and_survive_save_failure(monkeypatch):
    now = datetime(2026, 11, 23, 8)
    cfg = _Config(**YAML(typ="safe").load(Path("assets/config/config.example.yaml")))
    cfg.set_value = lambda k, v: setattr(cfg, k, v)
    monkeypatch.setattr(readings.time, "time", lambda: now.timestamp())
    readings.save_reading(cfg, "overview_power", 186)
    assert readings.power_reading(cfg).value == 186
    assert readings.power_reading(cfg).full_at == now + timedelta(minutes=684)
    for full in (300, 302):
        readings.save_reading(cfg, "overview_power", full)
        assert readings.power_reading(cfg).full_at == now
    readings.save_reading(cfg, "overview_daily_activity", 340)
    assert readings.daily_training(cfg, now).activity == 340
    assert readings.daily_training(cfg, now + timedelta(days=1)).activity is None
    assert all(find_setting(k).key_scope(k) == Scope.STATE for k in ("overview_power", "overview_daily_activity"))
    cfg.set_value = Mock(side_effect=OSError("磁盘已满"))
    from tasks.power import power
    monkeypatch.setattr(power, "cfg", cfg)
    monkeypatch.setattr(power, "screen", Mock())
    monkeypatch.setattr(power, "read_number", Mock(return_value=92))
    assert power.Power.get() == 92


@pytest.mark.parametrize("value,minutes,expected,left", [
    (186, 0, 186, 360), (186, 5.5, 186, 30), (186, 6, 187, 360), (186, 17, 188, 60), (186, -10, 186, 360),
    (299, 5, 299, 60), (299, 6, 300, None), (0, 3 * 24 * 60, 300, None), (300, 1, 300, None), (302, 60, 302, None),
])
def test_power_recovers_every_six_minutes_up_to_the_cap(value, minutes, expected, left):
    read_at = datetime(2026, 11, 23, 8)
    reading = PowerReading(value, read_at, read_at + timedelta(seconds=readings.seconds_until_full(value)))
    now = read_at + timedelta(minutes=minutes)
    assert (readings.power_now(reading, now), readings.next_power_in(reading, now)) == (expected, left)


def test_power_summary_follows_the_order_of_use():
    cfg = _Config(**YAML(typ="safe").load(Path("assets/config/config.example.yaml")))
    cfg.instance_type, cfg.instance_names = "侵蚀隧洞", {"侵蚀隧洞": "睿治之径"}
    assert cards.summary("power", cfg) == "睿治之径"
    cfg.build_target_enable = True
    assert (cards.summary("power", cfg), cards.summary("power", cfg, touch=True)) == ("培养目标", "睿治之径")
    cfg.power_plan = [["侵蚀隧洞", "睿治之径", 1]]
    assert cards.summary("power", cfg) == "体力计划 · 1 项"


def test_corrupt_missing_and_old_history(tmp_path, monkeypatch):
    monkeypatch.setattr(runs, "runs_dir", lambda: str(tmp_path))
    now = datetime(2026, 11, 23, 13)
    assert history.read_history(now) == history.History()
    def put(run_id, obj):
        (tmp_path / (run_id + ".json")).write_text(json.dumps(obj), encoding="utf-8")
    old = "20261123-100000-abcd"
    run = dict(task="power", status="success", started_at="2026-11-23T10:00:00",
               ended_at="2026-11-23T10:02:00", invoker="gui")
    put(old, run)
    put("20261123-110000-abcd", {"started_at": "bad"})
    (tmp_path / "20261123-110010-abcd.json").write_text("{", encoding="utf-8")
    last = history.read_history(now).last
    assert (last.id, last.steps, last.seconds, last.trigger) == (old, (), 120, "gui")
    put(old, {**run, "trigger": "scheduled", "steps": [False, {"id":"power", "status":"failed", "seconds":4}]})
    assert history.read_history(now).last.trigger == "scheduled"
    assert history.read_history(now).last.steps[0].status == "failed"


def test_each_check_and_isolated_failure():
    cfg = _Config(**YAML(typ="safe").load(Path("assets/config/config.example.yaml")))
    now = datetime(2026, 11, 23, 13)
    def get(backend="local", error=None):
        return build_snapshot(cfg, now=now, is_file=lambda _: False, connection=(backend, False, error),
                              history_reader=lambda _: history.History())
    assert {i.id for i in get().checks} == {"game_path", "schedule", "push"}
    assert get(error="invalid").checks[0].id == "connection"
    cfg.notify_telegram_enable = True
    cfg.scheduled_tasks = [{"time": "14:30", "name": "A"}, {"trigger_mode": "chain", "name": "B", "post_action": "Sleep"}]
    assert get("cloud").checks == ()
    assert get("cloud").schedule.names == ("A", "B") and get("cloud").schedule.post_action == "Sleep"
    cfg.overview_power = {"value": "?"}
    snapshot = get("cloud")
    assert snapshot.unavailable == ("power",) and snapshot.power is None
    assert snapshot.daily and snapshot.weekly and snapshot.greeting


@pytest.mark.parametrize("backend,saved,shown,hidden", [
    ("local", None, 4, False), ("adb", None, 2, False), ("nonsense", None, 0, True),
    ("adb", [{"id": "currencywars"}], 0, True), ("local", [{"id": "currencywars"}], 1, False),
    ("nonsense", [], 0, False), ("nonsense", [{"id": "menu", "name": "空菜单", "menu": []}], 0, False),
])
def test_shortcuts_hidden_by_the_connection_are_not_reported_as_missing(backend, saved, shown, hidden):
    cfg = _Config(**YAML(typ="safe").load(Path("assets/config/config.example.yaml")))
    cfg.control_backend, cfg.overview_shortcuts = backend, saved
    snapshot = build_snapshot(cfg, now=datetime(2026, 11, 23, 13), is_file=lambda _: False,
                              connection=("local", False, None), history_reader=lambda _: history.History())
    assert (len(snapshot.shortcuts), snapshot.shortcuts_hidden, snapshot.unavailable) == (shown, hidden, ())


def test_recording_does_not_change_action_result(monkeypatch):
    session = runs.RunSession({"run_id": "20261123-100000-abcd"})
    monkeypatch.setattr(runs, "_current_session", session)
    monkeypatch.setattr(session, "_save", lambda: None)
    assert runs.observe_step("daily", lambda: False)() is False
    assert session.record["steps"][0]["status"] == "failed"
    with pytest.raises(ValueError):
        runs.observe_step("power", Mock(side_effect=ValueError("read")))()
    assert session.record["steps"][-1]["status"] == "failed"
    monkeypatch.setattr(session, "update_record", Mock(side_effect=OSError))
    assert runs.observe_step("daily", lambda: 123)() == 123


@pytest.mark.parametrize("backend", ["cloud", "local"])
def test_login_check_only_with_observed_evidence_for_this_backend_and_game_day(backend):
    sample = sample_snapshot("failed")
    cfg = _Config(**YAML(typ="safe").load(Path("assets/config/config.example.yaml")))
    def login_checks(last, backend):
        return [c for c in cards.checks(cfg, sample.now, None, backend, last, None) if c.id == "login"]
    last = replace(sample.last_run, login_required=backend)
    check, = login_checks(last, backend)
    assert find_setting(parse_link(check.link)[1])
    assert not login_checks(last, "adb")
    assert not login_checks(replace(last, login_required=None), backend)
    assert not login_checks(replace(last, status="success"), backend)
    assert not login_checks(replace(last, ended_at=sample.now - timedelta(days=1)), backend)


def test_history_orders_by_finish_and_marks_all_corrupt(tmp_path, monkeypatch):
    monkeypatch.setattr(runs, "runs_dir", lambda: str(tmp_path))
    now = datetime(2026, 11, 23, 12)
    def save(run_id, data):
        (tmp_path / (run_id + ".json")).write_text(json.dumps(data), encoding="utf-8")
    save("20261123-095900-abcd", {"status": "success"})
    assert history.read_history(now).unreadable
    save("20261123-100000-abcd", {"task":"main", "started_at":"2026-11-23T10:00:00",
                                  "ended_at":"2026-11-23T11:40:00", "status":"success"})
    save("20261123-110000-abcd", {"task":"power", "started_at":"2026-11-23T11:00:00",
                                  "ended_at":"2026-11-23T11:01:00", "status":"failed"})
    hist = history.read_history(now)
    assert not hist.unreadable and hist.last == hist.full and hist.last.task == "main"


def test_display_labels_and_single_task_retry():
    from module.overview.labels import trigger_label, result_label, post_action_label
    sample = sample_snapshot("failed")
    last = replace(sample.last_run, task="power", steps=(sample.last_run.steps[1],))
    g = make_greeting(sample.now, None, None, history.History(last), sample.plan, sample.daily)
    assert g.buttons[-1].id == "start_task" and g.buttons[-1].target == "power"
    assert result_label("partial") == "部分失败"
    assert trigger_label("scheduled") == "定时" and post_action_label("Shutdown") == "关机"


def test_weeklies_keep_completion_when_disabled_and_respect_refresh_hour():
    cfg = _Config(**YAML(typ="safe").load(Path("assets/config/config.example.yaml")))
    cfg.currencywars_enable = False
    cfg.refresh_hour = 9
    cfg.currencywars_timestamp = datetime(2026, 11, 22, 18).timestamp()
    def weekly(at):
        return {item.id: item for item in cards.weekly_items(cfg, at, False)}
    before = weekly(datetime(2026, 11, 23, 8, 59, 59))["currencywars"]
    after = weekly(datetime(2026, 11, 23, 9))["currencywars"]
    assert before.completed and not before.enabled and not after.completed
    assert [i.id for i in cards.weekly_items(cfg, datetime(2026, 11, 23, 9), True)] == ["echo"]
