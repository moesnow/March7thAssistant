"""运行记录和定时计划的界面模型。记录转换、日志解析、定时计算可独立使用。"""
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
import uuid

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices

from app.common.schedule import format_task_weekdays, task_launch_block_reason, task_timeout_seconds
from module.config import cfg
from module.localization import get_current_language, tr
from module.overview.labels import post_action_label
from module.overview.schedule import next_occurrence, next_schedule, schedule_time, task_trigger_mode, task_weekdays
from utils import runs
from utils.tasks import TASK_NAMES
from module.overview.run_data import Item, Outcome, Ref, Slot, history_entry
from module.overview.run_log import read_log


class RunHistory(QObject):
    changed = Signal()

    def __init__(self, window=None):
        super().__init__(window)
        self._root = Path(runs.runs_dir())
        self._files = {}
        self._entries = {}
        self._records = {}
        self._colors = {}
        self._watcher = QFileSystemWatcher(self)
        self._timer = QTimer(self, singleShot=True, interval=350)
        self._timer.timeout.connect(self.refresh)
        self._watcher.directoryChanged.connect(self.request_refresh)
        self._watcher.fileChanged.connect(self.request_refresh)
        self._active_timer = QTimer(self, interval=750)
        self._active_timer.timeout.connect(self.refresh)
        self.refresh()

    def request_refresh(self, *_):
        if not self._timer.isActive():
            self._timer.start()

    def refresh(self):
        window = self.parent()
        model = getattr(window, "accountModel", None)
        colors = {a.uid: a.color for a in model.accounts()} if model else {}
        language = get_current_language()
        entries, files, records = {}, {}, {}
        target = self._root
        while not target.is_dir() and target != target.parent:
            target = target.parent
        watched = {str(target)}
        for rid in runs.list_run_ids():
            path = self._root / (rid + ".json")
            try:
                stat = path.stat()
                stamp = (stat.st_mtime_ns, stat.st_size)
                old = self._files.get(rid)
                record = self._records.get(rid) if old and old[:2] == stamp else runs.load_run(rid)
                if not record or record.get("run_id", rid) != rid:
                    continue
                if "run_id" not in record:
                    record = dict(record, run_id=rid)
                signature = (*stamp, language, runs.effective_status(record))
                entries[rid] = (self._entries[rid] if old == signature and self._colors == colors else
                                history_entry(rid, record, colors))
                files[rid], records[rid] = signature, record
                if entries[rid].status == "running":
                    watched.add(str(path))
            except (OSError, AttributeError, KeyError, ValueError, OverflowError, TypeError):
                continue
        previous = set(self._watcher.files() + self._watcher.directories())
        if previous - watched:
            self._watcher.removePaths(list(previous - watched))
        if watched - previous:
            self._watcher.addPaths(list(watched - previous))
        changed = self._entries != entries
        self._files, self._entries, self._records, self._colors = files, entries, records, colors
        active = self.active()
        if active and not self._active_timer.isActive():
            self._active_timer.start()
        elif not active:
            self._active_timer.stop()
        controller = getattr(window, "runController", None)
        if controller and getattr(window, "runHistory", None) is self:
            controller.sync_records()
        if changed:
            self.changed.emit()

    def active(self, preferred=None, *, local=False):
        live = [rid for rid, e in self._entries.items() if e.status == "running" and not e.parent_id]
        if preferred:
            return self.raw(preferred) if preferred in live else None
        if live:
            if local:
                # 未提权 GUI 的转交入口自行分配编号，按该次启动的控制文件关联。
                path = self.parent().runController._pauseControlPath()
                return next((self.raw(rid) for rid in reversed(live) if self.raw(rid).get("control_file") == path), None)
            return self.raw(live[-1])
        return None

    def records(self):
        return self._records.items()

    def raw(self, rid):
        return self._records.get(rid)

    def entry(self, rid):
        return self._entries.get(rid)

    def last(self):
        return max((e for e in self._entries.values() if e.status != "running" and not e.parent_id),
                   key=lambda e: e.started_at + timedelta(seconds=e.seconds or 0), default=None)

    def days(self, account=None, problems=False):
        groups = defaultdict(list)
        for entry in sorted(self._entries.values(), key=lambda e: e.started_at, reverse=True):
            if account:
                uid = (entry.account.uid if entry.account else
                       getattr(cfg, "account_inherited", None) if "account" not in self.raw(entry.id) else None)
                if uid != account or entry.accounts:
                    continue
            elif entry.parent_id:
                continue
            if problems and entry.status in ("success", "running"):
                continue
            groups[entry.started_at.date()].append(entry)
        return list(groups.items())

    def any(self):
        return bool(self._entries)

    def today(self):
        return datetime.now().date()

    def accounts(self):
        model = getattr(self.parent(), "accountModel", None)
        refs = {a.uid: Ref(a.uid, a.name, a.color) for a in model.accounts()} if model else {}
        for entry in self._entries.values():
            for a in ((entry.account,) if entry.account else entry.accounts):
                refs.setdefault(a.uid, Ref(a.uid, a.name, a.color))
        return tuple(refs.values())

    def log(self, entry):
        return read_log(runs.run_file(entry.id, ".log")) if entry and self.entry(entry.id) else []

    def _retry_command(self, entry):
        record = self.raw(entry.id)
        controller = self.parent().runController
        if not record or controller.isTaskRunning() or getattr(controller, "_desktop_twin_hosting", False) or entry.status == "running":
            return None
        account = "all" if entry.accounts else entry.account.uid if entry.account else None
        model = getattr(self.parent(), "accountModel", None)
        if account and (not model or not model.active() or
                        account != "all" and not any(a.uid == account for a in model.accounts())):
            return None
        task = record.get("task")
        if record.get("workflow"):
            from module.workflow import get_workflow_by_name, build_workflow_task
            name = record["workflow"]
            if not get_workflow_by_name(name):
                return None
            command = build_workflow_task(name, record.get("workflow_step_path"))
        elif task in TASK_NAMES:
            if task_launch_block_reason(task, cfg):
                return None
            from module.config.platform import get_ui_profile
            from module.task_catalog import BY_ID
            from module.overview.plan import STEPS, TOUCH
            touch = get_ui_profile(cfg).name == "touch_720"
            page = record.get("page_task")
            if page and (page not in BY_ID or touch and not BY_ID[page].touch):
                return None
            step = next((s.id for s in entry.steps if s.status == "failed" and s.id in STEPS and s.id != "prepare"), None)
            command = {"program": "self", "args": task}
            if step and (not touch or step in TOUCH):
                command.update(args="routine", retry_step=step)
            elif record.get("retry_step"):
                if touch and record["retry_step"] not in TOUCH:
                    return None
                command.update(args="routine", retry_step=record["retry_step"])
            elif page:
                command["page_task"] = page
            else:
                args = record.get("args") or []
                if "--page-task" in args and args.index("--page-task")+1 < len(args):
                    command["page_task"] = args[args.index("--page-task")+1]
        elif task == "external" and record.get("schedule_id"):
            schedule = next((t for t in ScheduleModel._tasks() if t.get("id") == record["schedule_id"]), None)
            if not schedule or schedule.get("program") in ("self", "workflow") or not Path(schedule["program"]).is_file():
                return None
            from app.common.schedule import scheduled_task_payload
            command = scheduled_task_payload(schedule)
        else:
            return None
        command["account"] = account
        return None if task_launch_block_reason(command, cfg) else command

    def retry_text(self, entry):
        command = self._retry_command(entry)
        return (tr("重试这一项") if command.get("retry_step") else tr("重新运行")) if command else ""

    def retry(self, entry):
        command = self._retry_command(entry)
        if command:
            self.parent()._onStartTask(command)
        return bool(command)

    def open_log(self, entry):
        return self._open(runs.run_file(entry.id, ".log")) if entry and self.entry(entry.id) else False

    def open_screenshot(self, entry):
        if not entry or Path(entry.screenshot).suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
            return False
        return self._open(entry.screenshot)

    @staticmethod
    def _open(path):
        path = Path(path)
        return path.is_file() and QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.absolute())))

class ScheduleModel(QObject):
    changed = Signal()

    def __init__(self, window=None):
        super().__init__(window)
        self.controller = window.runController
        self.controller.scheduleChanged.connect(self.changed)
        self._unsubscribe = cfg.subscribe(self._config_changed)
        self.destroyed.connect(lambda: self._unsubscribe())

    def _config_changed(self, keys, external):
        if external or set(keys).intersection(("scheduled_tasks", "scheduled_on_conflict", "scheduled_chain_continue_on_failure")):
            self.changed.emit()

    @staticmethod
    def now():
        return datetime.now()

    @staticmethod
    def _tasks():
        return [task for task in cfg.get_value("scheduled_tasks", []) or [] if isinstance(task, dict)]

    def enabled_count(self):
        return sum(bool(task.get("enabled", True)) for task in self._tasks())

    def _name(self, task):
        return task.get("name") or tr(TASK_NAMES.get(task.get("args"), "未命名"))

    def items(self):
        from module.accounts.runtime import ROTATABLE
        model = getattr(self.parent(), "accountModel", None)
        tasks, now = self._tasks(), self.now()
        _, nearest, selected = next_schedule(tasks, now)
        items = []
        for task in tasks:
            chained = task_trigger_mode(task) == "chain"
            enabled = task.get("enabled", True)
            builtin = task.get("program", "self") == "self"
            task_id = task.get("args") or "main"
            uid = task.get("account") or "all"
            account_text = problem = ""
            if builtin:
                if uid != "all":
                    info = next((a for a in model.accounts() if a.uid == uid), None) if model else None
                    account_text = info.name if info and model.active() else ""
                    if not info or not model.active():
                        problem = tr("指定的账号不可用，计划将跳过")
                elif model and model.active() and task_id in ROTATABLE:
                    account_text = tr("全部账号轮流")
            action = task.get("post_action") or "None"
            parts = [tr("上一项完成后") if chained else format_task_weekdays(task)]
            if builtin:
                parts.append(tr(TASK_NAMES.get(task_id, task_id)))
            elif task.get("program") == "workflow":
                parts.append(task.get("workflow_name") or task_id)
            else:
                parts.append(tr("外部程序 {name}").format(name=Path(task.get("program", "")).name))
            if action != "None":
                parts.append(tr("完成后{action}").format(action=post_action_label(action)))
            if task.get("notify"):
                parts.append(tr("推送通知"))
            if timeout := task_timeout_seconds(task):
                parts.append(tr("超时 {minutes} 分钟").format(minutes=f"{timeout/60:g}"))
            at = next_occurrence(task, now) if enabled and not chained else None
            items.append(Item(task.get("id", ""), self._name(task), enabled, chained, "" if chained else task.get("time", ""),
                              " · ".join(parts), account_text, problem, task is selected, at))
        return tuple(items)

    def week(self):
        now = self.now()
        tasks = self._tasks()
        _, nearest, selected = next_schedule(tasks, now)
        result = []
        for offset in range(7):
            day = now.date() + timedelta(days=offset)
            slots = []
            for task in tasks:
                clock = schedule_time(task.get("time", ""))
                if (not task.get("enabled", True) or not clock or task_trigger_mode(task) == "chain"
                        or day.isoweekday() not in task_weekdays(task)):
                    continue
                at = datetime.combine(day, clock)
                slots.append(Slot(task.get("id", ""), clock.strftime("%H:%M"), self._name(task),
                                  task is selected and at == nearest, at < now))
            result.append((day, offset == 0, sorted(slots, key=lambda s: s.time)))
        return result

    def next_text(self):
        from app.overview.style import format_when
        now = self.now()
        _, at, task = next_schedule(self._tasks(), now)
        return tr("下次定时：{time} {name}").format(time=format_when(at, now), name=self._name(task)) if task else ""

    def summary(self):
        count, _, _ = next_schedule(self._tasks(), self.now())
        return (" · ".join(filter(None, (tr("已启用 {count} 个按时计划").format(count=count), self.next_text())))
                if count else tr("还没有启用的计划"))

    def conflict(self):
        return cfg.get_value("scheduled_on_conflict", "skip")

    def set_conflict(self, value):
        if value in ("skip", "stop"):
            cfg.set_value("scheduled_on_conflict", value)

    def chain_continue(self):
        return self.controller._continue_chain_on_failure()

    def set_chain_continue(self, on):
        cfg.set_value("scheduled_chain_continue_on_failure", bool(on))

    def _index(self, tasks, item_id):
        return next((i for i, t in enumerate(tasks) if t.get("id") == item_id), -1)

    def set_enabled(self, item_id, on):
        tasks = self._tasks()
        i = self._index(tasks, item_id)
        if i >= 0:
            tasks[i]["enabled"] = bool(on)
            self.controller._saveScheduledTasks(tasks)

    def can_move(self, item_id, delta):
        tasks = self._tasks()
        i = self._index(tasks, item_id)
        return i >= 0 and delta in (-1, 1) and 0 <= i + delta < len(tasks)

    def move(self, item_id, delta):
        tasks = self._tasks()
        i = self._index(tasks, item_id)
        if i >= 0 and delta in (-1, 1) and 0 <= i + delta < len(tasks):
            tasks.insert(i + delta, tasks.pop(i))
            self.controller._saveScheduledTasks(tasks)

    @staticmethod
    def _copy_index(tasks, i, copy):
        """副本放在原计划和它的链式任务之后，不截断原来的链。链式任务的链式副本紧跟在它后面。"""
        if i < 0:
            return len(tasks)
        end = i + 1
        if not (task_trigger_mode(tasks[i]) == task_trigger_mode(copy) == "chain"):
            while end < len(tasks) and task_trigger_mode(tasks[end]) == "chain":
                end += 1
        return end

    def duplicate(self, item_id, window):
        """打开填好同样内容的编辑窗口，确认后才新增。"""
        from app.schedule_dialog import AddEditScheduleDialog
        tasks = self._tasks()
        i = self._index(tasks, item_id)
        if i < 0:
            return
        copy = deepcopy(tasks[i])
        copy.update(id=str(uuid.uuid4()), name=tr("{name}（副本）").format(name=self._name(copy)))
        dialog = AddEditScheduleDialog(window, copy, scheduled_tasks=tasks, title=tr("复制定时计划"))
        if dialog.exec():
            copy, tasks = dialog.get_task(), self._tasks()
            tasks.insert(self._copy_index(tasks, self._index(tasks, item_id), copy), copy)
            self.controller._saveScheduledTasks(tasks)

    def remove(self, item_id):
        self.controller._saveScheduledTasks([t for t in self._tasks() if t.get("id") != item_id])

    def edit(self, item_id, window):
        from app.schedule_dialog import AddEditScheduleDialog
        tasks = self._tasks()
        i = self._index(tasks, item_id)
        if item_id and i < 0:
            return
        dialog = AddEditScheduleDialog(window, tasks[i] if i >= 0 else None, scheduled_tasks=tasks)
        if dialog.exec():
            tasks = self._tasks()
            if item_id is None:
                tasks.append(dialog.get_task())
            elif (i := self._index(tasks, item_id)) >= 0:
                tasks[i] = dialog.get_task()
            self.controller._saveScheduledTasks(tasks)

    def run_now(self, item_id):
        tasks = self._tasks()
        i = self._index(tasks, item_id)
        if i < 0:
            return Outcome(False, tr("定时计划已删除"))
        if self.controller.isTaskRunning():
            return Outcome(False, tr("任务正在运行"))
        if not self.controller.runScheduledTask(tasks[i], tasks, manual=True):
            return Outcome(False, tr("计划未能启动，请查看运行日志"))
        return Outcome(True)
