from copy import deepcopy
from dataclasses import replace
from unittest.mock import Mock

import pytest

from module.setup.run_plan import RunPlanner


class Settings:
    def __init__(self):
        self.values = dict(scheduled_tasks=[], after_finish="Exit", autostart_open_gui=True,
                           autostart_gui_task="", autostart_headless_task="main", autostart_minimize=False, refresh_hour=4)
        self.writes = []

    def get_value(self, key, default=None):
        return deepcopy(self.values.get(key, default))

    def set_values(self, values):
        self.writes.append(deepcopy(values))
        self.values.update(values)


class Login:
    def __init__(self):
        self.enabled = self.legacy = False
        self.is_supported = Mock(return_value=True)
        self.is_enabled = Mock(side_effect=lambda: self.enabled)
        self.is_legacy_task_enabled = Mock(side_effect=lambda: self.legacy)
        self.enable = Mock(side_effect=lambda: self.change(True))
        self.disable = Mock(side_effect=lambda: self.change(False))
        self.remove_legacy_for_setup = Mock(side_effect=self.remove)

    def change(self, on):
        self.enabled = on
        return True

    def remove(self):
        self.legacy = False
        return lambda: setattr(self, "legacy", True)


def row(key="owned", **values):
    return dict({"id": key, "program": "self", "args": "main", "time": "05:22", "enabled": True,
                 "weekdays": [1, 4], "post_action": "RunScript", "timeout": 731, "account": "123"}, **values)


@pytest.fixture
def env():
    config, login = Settings(), Login()
    save_rows = Mock(side_effect=lambda rows, values: config.set_values({**values, "scheduled_tasks": rows}))
    return config, login, save_rows, RunPlanner(config, save_rows, login)


@pytest.mark.parametrize("enabled,gui,gui_task,headless,mode", [
    (False, True, "main", "main", "manual"), (True, True, "daily", "main", "manual"),
    (True, True, "main", "daily", "login"), (True, False, "daily", "main", "login"),
    (True, False, "main", "daily", "manual")])
def test_read_no_change_and_cached_queries(env, enabled, gui, gui_task, headless, mode):
    cfg, login, save_rows, planner = env
    cfg.values.update(autostart_open_gui=gui, autostart_gui_task=gui_task, autostart_headless_task=headless)
    login.enabled = enabled
    assert planner.info(False).other_schedules == 0
    login.is_enabled.assert_not_called()
    plan = planner.read()
    assert plan.mode == mode and plan.time == "04:10" and plan.after == "Exit"
    assert planner.read() == plan and planner.save(plan, False).ok
    login.is_enabled.assert_called_once()
    login.is_legacy_task_enabled.assert_not_called()
    assert not cfg.writes and not save_rows.called


def test_first_enabled_preserves_other_schedules_and_seconds(env):
    cfg, login, save_rows, planner = env
    original = [row("off", enabled=False), row("chain", trigger_mode="chain"),
                row(time="05:22:17"), row("other", args="power"), row("last")]
    cfg.values["scheduled_tasks"] = deepcopy(original)
    cfg.values["autostart_gui_task"] = "main"
    login.enabled = True
    plan = planner.read()
    assert (plan.mode, plan.time, plan.after) == ("daily", "05:22", "RunScript")
    assert planner.info(True).other_schedules == 3
    assert "RunScript" in dict(planner.after_options("daily"))
    assert planner.save(replace(plan, after="Hibernate"), False).ok
    assert cfg.values["scheduled_tasks"] == [*original[:2], {**original[2], "post_action": "Hibernate"}, *original[3:]]
    assert save_rows.call_count == 1 and cfg.values["after_finish"] == "Exit"


@pytest.mark.parametrize("start,end", [
    ("manual", "daily"), ("manual", "login"), ("daily", "manual"), ("daily", "login"),
    ("login", "manual"), ("login", "daily"),
])
def test_mode_transition(env, start, end):
    cfg, login, save_rows, planner = env
    if start == "daily":
        cfg.values["scheduled_tasks"] = [row()]
    elif start == "login":
        login.enabled = True
        cfg.values.update(autostart_open_gui=False)
    plan = planner.read()
    assert plan.mode == start
    result = planner.save(replace(plan, mode=end, after="None", time="08:32"), False)
    assert result.ok, result.text
    assert planner.read().mode == end
    rows = cfg.values["scheduled_tasks"]
    if start == "daily":
        assert len(rows) == 1 and rows[0] == {**row(), "enabled": False}
    if end == "daily":
        assert len(rows) == 1
        assert rows[0] == {"id": rows[0]["id"], "name": "完整运行", "enabled": True, "program": "self",
                           "args": "main", "weekdays": list(range(1, 8)), "trigger_mode": "time", "time": "08:32",
                           "timeout": 0, "notify": False, "post_action": "None"}
        assert cfg.values["after_finish"] == "Exit"
    if end == "login":
        assert login.enabled and cfg.values["autostart_minimize"] and cfg.values["autostart_gui_task"] == "main"
    if start == "login":
        assert not cfg.values["autostart_gui_task"]
        assert login.enabled == (end == "manual")


def test_repeat_daily_and_manual_reuses_id_and_only_changes_selected_keys(env):
    cfg, login, _, planner = env
    for time in ("04:12", "23:32", "06:01"):
        assert planner.save(replace(planner.read(), mode="daily", time=time, after="Sleep", open_at_login=True), False).ok
        stored = cfg.values["scheduled_tasks"][0]
        if time == "04:12":
            key = stored["id"]
        assert len(cfg.values["scheduled_tasks"]) == 1 and stored["id"] == key and stored["time"] == time
        assert login.enabled and cfg.values["autostart_gui_task"] == ""
        assert planner.save(replace(planner.read(), open_at_login=False), False).ok
        assert not login.enabled and not planner.read().open_at_login
        assert planner.save(replace(planner.read(), mode="manual", after="Exit"), False).ok
    assert not cfg.values["scheduled_tasks"][0]["enabled"]


@pytest.mark.parametrize("fail", ["conflict", "delete", "enable", "config", "undo"])
def test_conflict_and_failure_leave_configuration_whole(env, fail):
    cfg, login, save_rows, planner = env
    cfg.values["scheduled_tasks"] = [row("other", args="daily", time="07:00", weekdays=[5])]
    login.legacy = True
    if fail == "delete":
        login.remove_legacy_for_setup.side_effect = PermissionError("legacy denied")
    elif fail == "enable":
        login.enable.side_effect = lambda: False
    elif fail in ("config", "undo"):
        save_rows.side_effect = PermissionError("file denied")
        if fail == "undo":
            login.disable.side_effect = lambda: False
    before = deepcopy(cfg.values)
    plan = replace(planner.read(), mode="daily", time="07:00" if fail == "conflict" else "05:00",
                   after="Sleep", open_at_login=True)
    result = planner.save(plan, True)
    assert not result.ok and result.text
    assert cfg.values == before and login.legacy
    if fail == "undo":
        assert "file denied" in result.text and "恢复" in result.text
    else:
        assert not login.enabled
    if fail == "conflict":
        assert "周五" in result.text and "07:00" in result.text
        login.is_legacy_task_enabled.assert_not_called()


def test_malformed_schedule_list_is_preserved(env):
    cfg, login, save_rows, planner = env
    cfg.values["scheduled_tasks"] = {"old": "format"}
    assert planner.read().mode == "manual"
    result = planner.save(replace(planner.read(), mode="daily", after="None"), False)
    assert not result.ok and "定时计划" in result.text
    assert not save_rows.called and not cfg.writes and not login.enable.called


def test_second_full_run_is_reported_after_disabling_the_first(env):
    cfg, _, _, planner = env
    cfg.values["scheduled_tasks"] = [row(), row("second", time="10:45")]
    before = planner.read()
    assert planner.save(replace(before, mode="manual", after="Exit"), False).ok
    assert not cfg.values["scheduled_tasks"][0]["enabled"] and cfg.values["scheduled_tasks"][1]["enabled"]
    assert planner.read().time == "10:45" and planner.info(False).other_schedules == 0


def test_external_replacement_with_another_id_is_never_overwritten(env):
    cfg, _, _, planner = env
    cfg.values["scheduled_tasks"] = [row()]
    before = planner.read()
    cfg.values["scheduled_tasks"] = [row("replacement")]
    result = planner.save(replace(before, time="09:00"), False)
    assert not result.ok and not cfg.writes


def test_refresh_hour_only_when_visible_and_keep_external_changes(env):
    cfg, login, save_rows, planner = env
    old = planner.read()
    cfg.values["after_finish"] = "RunScript"
    assert planner.save(replace(old, refresh_hour=8), False).ok and not cfg.writes
    assert planner.save(replace(planner.read(), refresh_hour=23), True).ok
    assert cfg.writes == [{"refresh_hour": 23}]
    assert not planner.save(replace(planner.read(), refresh_hour=24), True).ok
    assert "RunScript" in dict(planner.after_options("manual"))
    login.is_supported.return_value = False
    assert not planner.save(replace(planner.read(), mode="login"), False).ok
    assert not planner.save(replace(planner.read(), mode="daily", open_at_login=True), False).ok
    save_rows.assert_not_called()


def test_refresh_hour_edits_global_and_preserves_account_override(env):
    cfg, _, _, planner = env
    cfg.bound_account = "100000123"
    cfg.shared_value = cfg.get_value
    read = cfg.get_value
    cfg.get_value = lambda key, default=None: 15 if key == "refresh_hour" else read(key, default)
    assert planner.read().refresh_hour == 4
    assert planner.save(replace(planner.read(), refresh_hour=15), True).ok
    assert cfg.writes == [{"refresh_hour": 15}]
    assert planner.read().refresh_hour == 15


def test_reopen_reuses_first_disabled_everyday_plan(env):
    cfg, login, save, planner = env
    limited = row("weekend", enabled=False, weekdays=[6, 7])
    target = row("chosen", enabled=False, weekdays=list(range(1, 8)), time="22:00", post_action="Sleep")
    last = {**target, "id": "last", "time": "13:00"}
    cfg.values["scheduled_tasks"] = [limited, target, last]
    for _ in range(2):
        planner = RunPlanner(cfg, save, login)
        plan = planner.read()
        assert (plan.mode, plan.time, planner.after_value("daily")) == ("manual", "22:00", "Sleep")
        assert planner.after_value("login") == "Exit"
        assert planner.save(replace(plan, mode="daily", after="Sleep"), False).ok
        assert cfg.values["scheduled_tasks"] == [limited, {**target, "enabled": True}, last]
        assert planner.save(replace(planner.read(), mode="manual", after="Exit"), False).ok
        assert planner.read().time == "22:00" and planner.after_value("daily") == "Sleep"
        assert cfg.values["scheduled_tasks"] == [limited, target, last]


def test_disabled_partial_week_plan_is_left_alone_on_reopen(env):
    cfg, _, _, planner = env
    original = row("weekend", weekdays=[7], enabled=False)
    cfg.values["scheduled_tasks"] = [original]
    plan = planner.read()
    assert (plan.time, planner.after_value("daily")) == ("04:10", "None")
    assert planner.save(replace(plan, mode="daily", after="None"), False).ok
    assert cfg.values["scheduled_tasks"][0] == original and len(cfg.values["scheduled_tasks"]) == 2
