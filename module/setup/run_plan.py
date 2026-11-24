"""首次配置的运行时间。一个向导会话只编辑同一个完整运行计划。"""
from dataclasses import dataclass
import uuid

from module.localization import tr
from module.overview.labels import post_action_label
from module.overview.run_data import Outcome
from module.overview.schedule import (
    find_scheduled_task, format_task_weekdays, schedule_conflict, schedule_time, task_trigger_mode, task_weekdays,
)


@dataclass(frozen=True)
class RunPlan:
    mode: str
    time: str
    after: str
    open_at_login: bool
    refresh_hour: int


@dataclass(frozen=True)
class RunInfo:
    login_supported: bool
    show_refresh: bool
    other_schedules: int


DEFAULT_TIME = "04:10"
DAILY_ACTIONS = ("None", "Shutdown", "Sleep", "Hibernate", "TurnOffDisplay")
MANUAL_ACTIONS = ("None", "Exit", *DAILY_ACTIONS[1:])


def _full_run(row):
    return (isinstance(row, dict) and task_trigger_mode(row) == "time" and row.get("program", "self") == "self"
            and row.get("args") == "main")


class RunPlanner:
    def __init__(self, config, save_schedules, autostart):
        self.config = config
        self.save_schedules = save_schedules
        self.autostart = autostart
        self._enabled = None
        self._managed = None
        self._before = None
        self.system_changed = False

    def invalidate_autostart(self):
        self._enabled = None

    def _autostart_enabled(self):
        if self._enabled is None:
            self._enabled = self.autostart.is_supported() and self.autostart.is_enabled()
        return self._enabled

    def _rows(self):
        rows = self.config.get_value("scheduled_tasks")
        return rows if isinstance(rows, list) else []

    def _remembered(self, rows):
        if self._managed is None:
            return None
        candidates = [row for row in rows if _full_run(row)]
        if key := self._managed.get("id"):
            return next((row for row in candidates if row.get("id") == key), None)
        index = find_scheduled_task(self._managed, candidates)
        return candidates[index] if index >= 0 else None

    def _row(self, rows):
        full = [row for row in rows if _full_run(row)]
        enabled = next((row for row in full if row.get("enabled", True)), None)
        if enabled is not None:
            return enabled
        # 本次会话刚停用的计划保留原身份；重新打开只接管每天都执行的停用计划。
        return self._remembered(rows) or next((row for row in full if len(task_weekdays(row)) == 7), None)

    def days_text(self):
        return format_task_weekdays(self._row(self._rows()) or {})

    def info(self, show_refresh):
        rows = self._rows()
        managed = self._row(rows)
        count = sum(isinstance(row, dict) and row is not managed and row.get("enabled", True)
                    for row in rows)
        return RunInfo(self.autostart.is_supported(), show_refresh, count)

    def _refresh_hour(self):
        # 账号自己的刷新时间在账号页维护；向导与这里的全局写入读取同一层。
        if getattr(self.config, "bound_account", None):
            return self.config.shared_value("refresh_hour")
        return self.config.get_value("refresh_hour", 4)

    def current(self):
        get = self.config.get_value
        row = self._row(self._rows())
        auto = self._autostart_enabled()
        gui = get("autostart_open_gui", True)
        login_task = get("autostart_gui_task") if gui else get("autostart_headless_task", "main")
        mode = "login" if auto and login_task == "main" else "manual"
        after, time = self.after_value("manual"), DEFAULT_TIME
        if row is not None:
            clock = schedule_time(row.get("time"))
            time = clock.strftime("%H:%M") if clock else DEFAULT_TIME
            if row.get("enabled", True):
                mode, after = "daily", row.get("post_action") or "None"
        return RunPlan(mode, time, after, bool(auto and gui and not login_task and get("autostart_minimize")),
                       self._refresh_hour())

    def read(self):
        current = self.current()
        if self._before is None:
            self._before = current
            self._managed = self._row(self._rows())
        return current

    def after_value(self, mode):
        if mode == "daily":
            row = self._row(self._rows())
            return (row or {}).get("post_action") or "None"
        return self.config.get_value("after_finish") or "None"

    def after_options(self, mode):
        current = self.after_value(mode)
        actions = DAILY_ACTIONS if mode == "daily" else MANUAL_ACTIONS
        return tuple((key, post_action_label(key)) for key in dict.fromkeys((*actions, current)))

    def _settings(self, plan, before, show_refresh):
        get = self.config.get_value
        values = {}
        target = None  # None 表示保留系统开关。
        if show_refresh and plan.refresh_hour != before.refresh_hour:
            if type(plan.refresh_hour) is not int or not 0 <= plan.refresh_hour < 24:
                raise ValueError(tr("游戏刷新时间应在 0 至 23 点之间。"))
            values["refresh_hour"] = plan.refresh_hour
        switched = plan.mode != before.mode
        if plan.mode != "daily" and (switched or plan.after != before.after):
            values["after_finish"] = plan.after
        if switched and before.mode == "login":
            values.update(autostart_gui_task="", autostart_open_gui=True)
        if plan.mode == "login" and switched:
            target = True
            values.update(autostart_gui_task="main", autostart_open_gui=True, autostart_minimize=True)
        if plan.mode == "daily" and (plan.open_at_login != before.open_at_login or
                                     switched and (plan.open_at_login or before.mode == "login")):
            target = plan.open_at_login
            if target:
                values.update(autostart_gui_task="", autostart_open_gui=True, autostart_minimize=True)
        changes = {key: value for key, value in values.items()
                   if (self._refresh_hour() if key == "refresh_hour" else get(key)) != value}
        return changes, target

    def _schedule(self, plan, before):
        rows = self._rows()
        row = self._remembered(rows) if self._managed is not None else self._row(rows)
        switched = plan.mode != before.mode
        if plan.mode == "daily" or switched and before.mode == "daily":
            saved_rows = self.config.get_value("scheduled_tasks")
            if saved_rows is not None and not isinstance(saved_rows, list):
                raise ValueError(tr("现有定时计划无法读取，请到「运行」检查后再设置。"))
        if self._managed is not None and row is None and (switched or plan.mode == "daily"):
            raise ValueError(tr("这个定时计划已被移除，请重新打开向导后再设置。"))
        if plan.mode == "daily" and (switched or plan.time != before.time or plan.after != before.after):
            clock = schedule_time(plan.time)
            if clock is None or clock.strftime("%H:%M") != plan.time:
                raise ValueError(tr("请选择有效的运行时间。"))
            # 旧计划可能带秒或其它字段，只写用户确实编辑过的部分。
            candidate = dict(row) if row is not None else dict(
                id=str(uuid.uuid4()), name=tr("完整运行"), trigger_mode="time", weekdays=list(range(1, 8)),
                program="self", args="main", timeout=0, notify=False)
            if switched or plan.time != before.time:
                candidate["time"] = plan.time
            if switched or plan.after != before.after:
                candidate["post_action"] = plan.after
            if switched or row is None:
                candidate["enabled"] = True
            conflict = schedule_conflict(rows, schedule_time(candidate.get("time")) or clock,
                                         task_weekdays(candidate), row)
            if conflict:
                raise ValueError(conflict)
        elif switched and before.mode == "daily" and row is not None:
            candidate = {**row, "enabled": False}
        else:
            return None, row
        if row is None:
            return [*rows, candidate], candidate
        return [candidate if item is row else item for item in rows], candidate

    def save(self, plan, show_refresh):
        undos = []
        self.system_changed = False
        try:
            before = self._before or self.read()
            if plan == before:
                return Outcome(True)
            needs_login = plan.mode == "login" or (plan.mode == "daily" and plan.open_at_login)
            if plan.mode not in ("manual", "daily", "login") or (needs_login and not self.autostart.is_supported()):
                return Outcome(False, tr("当前系统不支持这种运行方式。"))
            if (plan.after != before.after or plan.mode != before.mode) and plan.after not in dict(self.after_options(plan.mode)):
                return Outcome(False, tr("请选择可用的完成后操作。"))
            rows, managed = self._schedule(plan, before)
            values, target = self._settings(plan, before, show_refresh)
            if target is not None and self.autostart.is_supported():
                if target and self.autostart.is_legacy_task_enabled():
                    undos.append(self.autostart.remove_legacy_for_setup())
                if target != self._autostart_enabled():
                    change, undo = ((self.autostart.enable, self.autostart.disable) if target else
                                    (self.autostart.disable, self.autostart.enable))
                    if not change():
                        raise OSError(tr("开机启动设置失败，请检查 Windows 计划任务权限后重试。"))
                    undos.append(undo)
            if rows is not None:
                self.save_schedules(rows, values)
            elif values:
                self.config.set_values(values)
            self._managed = managed
            self.system_changed = bool(undos)
        except Exception as error:
            self.invalidate_autostart()
            rollback_errors = []
            for undo in reversed(undos):
                try:
                    if undo() is False:
                        raise OSError(tr("开机启动设置失败"))
                except Exception as rollback_error:
                    rollback_errors.append(str(rollback_error))
            if rollback_errors:
                return Outcome(False, tr("{error}；恢复原开机启动设置失败：{reason}").format(
                    error=error, reason="、".join(rollback_errors)))
            return Outcome(False, str(error))
        if rows is not None or values or target is not None:
            self.invalidate_autostart()
        self._before = self.current()
        if self._before.mode == "daily":
            self._managed = self._row(self._rows())
        return Outcome(True)
