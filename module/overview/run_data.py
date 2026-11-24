"""运行记录转为界面所需数据，无 Qt 依赖。"""

from dataclasses import dataclass
from datetime import datetime

from module.accounts.reasons import reason_text
from module.localization import tr
from module.overview.history import read_record
from module.overview.labels import trigger_label
from module.overview.plan import STEP_NAMES
from utils.tasks import TASK_NAMES


@dataclass(frozen=True)
class Step:
    id: str
    name: str
    status: str
    note: str = ""
    seconds: float = None


@dataclass(frozen=True)
class Ref:
    uid: str
    name: str
    color: int


@dataclass(frozen=True)
class Progress:
    uid: str
    name: str
    color: int
    status: str
    reason: str = ""
    run_id: str = ""


@dataclass(frozen=True)
class Run:
    id: str
    title: str
    status: str
    started_at: datetime
    seconds: float
    trigger_text: str = ""
    account: object = None
    accounts: tuple = ()
    steps: tuple = ()
    reason: str = ""
    screenshot: str = ""
    parent_id: str = ""


@dataclass(frozen=True)
class RunView:
    state: str = "idle"
    title: str = ""
    account: object = None
    accounts: tuple = ()
    account_index: int = 0
    seconds: float = None
    steps: tuple = ()
    can_pause: bool = False
    can_stop: bool = False
    can_skip: bool = False
    finish_text: str = ""
    finish_skipped: bool = False
    can_skip_finish: bool = False
    countdown: object = None
    last: object = None
    can_start: bool = True
    can_start_all: bool = False


@dataclass(frozen=True)
class Outcome:
    ok: bool
    text: str = ""


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    enabled: bool
    chained: bool
    time: str
    detail: str
    account_text: str = ""
    account_problem: str = ""
    next: bool = False
    next_at: object = None


@dataclass(frozen=True)
class Slot:
    id: str
    time: str
    name: str
    next: bool = False
    past: bool = False

def account_ref(row, colors):
    if isinstance(row, dict) and row.get("uid"):
        uid = str(row["uid"])
        return Ref(uid, row.get("name") or uid, colors.get(uid, 0))
    return None


def account_progress(record, colors):
    result = []
    for row in (record.get("rotation") or {}).get("accounts", ()):
        ref = account_ref(row, colors)
        if ref:
            result.append(Progress(ref.uid, ref.name, ref.color, row.get("status", "waiting"),
                                   reason_text(row.get("reason"), row.get("error")), row.get("run_id") or ""))
    return tuple(result)


def detail_text(detail):
    if not isinstance(detail, dict) or not isinstance(detail.get("msgid"), str):
        return ""
    args = dict(detail.get("args") or {})
    if isinstance(args.get("name"), str):
        args["name"] = tr(args["name"])
    try:
        return tr(detail["msgid"]).format(**args)
    except (KeyError, ValueError, IndexError):
        return ""


def run_steps(record, task, status, preview=()):
    from module.overview.labels import format_duration

    if task == "workflow" or task not in TASK_NAMES:
        return ()
    items = {s["id"]: s for s in record.get("steps") or () if isinstance(s, dict) and isinstance(s.get("id"), str)}
    current = record.get("current_step")
    keys = list(dict.fromkeys([*(record.get("plan") or preview), *items]))
    if current and current not in keys:
        keys.append(current)
    if not keys:
        if task in ("main", "routine") and not (record.get("retry_step") or record.get("page_task")):
            return ()
        keys = [record.get("retry_step") or task]
    single = record.get("page_task") or record.get("retry_step") or (task if task not in ("main", "routine") else None)
    if single:
        keys = [single]
    result = []
    for key in keys:
        item = items.get(key, {})
        state = item.get("status", "running" if current == key else "pending")
        if not item and (single or len(keys) == 1 and not current):
            state = status
        if state == "running" and status != "running":
            state = "interrupted"
        seconds = item.get("seconds")
        if not isinstance(seconds, (float, int)) or seconds < 0:
            seconds = None
        note = ""
        if state == "running":
            note = detail_text(record.get("detail"))
        elif state == "success":
            note = format_duration(seconds)
        elif state in ("failed", "skipped", "interrupted"):
            note = reason_text(item.get("reason"), item.get("error"))
        name = task_name(task, page=record.get("page_task"), step=key) if single else STEP_NAMES.get(key, key)
        result.append(Step(key, tr(name), state, note, seconds))
    return tuple(result)


def task_name(task, *, page=None, step=None):
    from module.task_catalog import BY_ID
    if page in BY_ID:
        return BY_ID[page].name
    return STEP_NAMES.get(step) or TASK_NAMES.get(task, task or "")


def history_entry(run_id, record, colors):
    info = read_record(run_id, record)
    accounts = account_progress(record, colors)
    status = info.status
    if accounts and status == "failed" and any(row.status in ("success", "partial") for row in accounts):
        status = "partial"
    trigger = {"gui": "manual", "non_interactive": "cli", "ai_assistant": "ai", "agent": "ai"}.get(info.trigger, info.trigger)
    reason = info.error or reason_text(record.get("reason"))
    if accounts and not reason:
        reason = "、".join(tr("{name}（{reason}）").format(name=row.name, reason=row.reason or tr("未完成"))
                          for row in accounts if row.status in ("failed", "partial", "timeout", "skipped"))
    if status == "aborted" and not reason:
        reason = tr("运行进程已退出")
    name = (record.get("display_name") or record.get("workflow") or
            tr(task_name(info.task, page=record.get("page_task"), step=record.get("retry_step"))))
    return Run(run_id, name, status, info.started_at, info.seconds, trigger_label(trigger),
               account_ref(record.get("account"), colors), accounts,
               () if accounts else run_steps(record, info.task, status), reason,
               record.get("screenshot") or "", record.get("parent_run_id") or "")


def preview_steps(task, config):
    from module.config.platform import get_control_backend, get_ui_profile
    from module.overview.plan import planned_steps
    if task not in ("main", "routine"):
        return ()
    try:
        return tuple(planned_steps(config, task, touch=get_ui_profile(config).name == "touch_720",
                                   backend=get_control_backend(config)))
    except (AttributeError, ValueError, TypeError, KeyError, OSError) as exc:
        import logging
        logging.getLogger("March7thAssistant").warning("无法预览步骤，将按运行记录更新：%s", exc)
        return ()
