"""兼容只有整次结果的旧运行记录。时间统一转换为本地时间。"""
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from math import isfinite

from module.localization import tr
from utils import runs
from utils.tasks import TASK_NAMES, PAUSABLE_TASKS
from .plan import STEP_NAMES
from .types import LiveRun, RunInfo, StepResult


def game_day(value):
    return (value - timedelta(hours=4)).date()


def _local(value):
    dt = datetime.fromisoformat(value)
    return dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt


def _step_result(item, terminal):
    if not isinstance(item, dict) or not isinstance(item.get("id"), str):
        return None
    key = item["id"]
    name = STEP_NAMES.get(key) or TASK_NAMES.get(key)
    if name is None:
        return None
    status = item.get("status")
    if status not in ("success", "failed", "skipped", "interrupted", "running"):
        return None
    if terminal and status == "running":
        status = "interrupted"
    seconds = item.get("seconds")
    if not isinstance(seconds, (float, int)) or not isfinite(seconds) or seconds < 0:
        seconds = None
    return StepResult(key, tr(name), status, seconds)


def read_record(run_id, record):
    started = _local(record["started_at"])
    end = record.get("ended_at")
    ended = _local(end) if end else None
    task = record.get("task") or "workflow"
    if not isinstance(task, str):
        raise ValueError("运行记录任务编号无效")
    workflow = record.get("workflow")
    name = workflow if isinstance(workflow, str) and workflow else tr(TASK_NAMES.get(task, task))
    status = runs.effective_status(record)
    if status not in ("running", "success", "failed", "blocked", "stopped", "interrupted", "aborted"):
        raise ValueError("运行记录状态无效")
    items = record.get("steps")
    steps = tuple(step for item in items if (step := _step_result(item, status != "running"))) if isinstance(items, list) else ()
    if status == "failed" and any(step.status == "success" for step in steps) and any(step.status == "failed" for step in steps):
        status = "partial"
    trigger = record.get("trigger") or record.get("invoker") or "unknown"
    if not isinstance(trigger, str):
        trigger = "unknown"
    retry = record.get("retry_step")
    error = record.get("error")
    return RunInfo(run_id, task, name, started, ended,
                   max(0, (ended - started).total_seconds()) if ended else None,
                   trigger, status, steps, error if isinstance(error, str) else None, f"run:{run_id}",
                   retry if isinstance(retry, str) and retry in STEP_NAMES else None,
                   record.get("login_required") if record.get("login_required") in ("local", "cloud") else None)


@dataclass(frozen=True)
class History:
    last: RunInfo | None = None
    full: RunInfo | None = None
    live: LiveRun | None = None
    unreadable: bool = False


def read_history(now):
    last = full = live = None
    unreadable = False
    holder = runs.read_active_run() or {}
    active_id = holder.get("run_id")
    ids = list(reversed(runs.list_run_ids()))
    if active_id in ids:
        ids.remove(active_id)
        ids.insert(0, active_id)
    for run_id in ids:
        try:
            record = runs.load_run(run_id)
            if not record:
                raise ValueError("记录缺失或损坏")
            info = read_record(run_id, record)
            if info.status == "running":
                if live is None:
                    from utils.pause import read_state
                    control = record.get("control_file")
                    supported = bool(control and (info.task in PAUSABLE_TASKS or info.task == "workflow"))
                    state = read_state(control) if supported else None
                    phase = record.get("phase")
                    step = record.get("current_step")
                    live = LiveRun(info.task, info.name, phase if isinstance(phase, str) else "execute",
                                   step if isinstance(step, str) else None,
                                   supported, supported, state == "paused", run_id, info.started_at)
                continue
            # 运行锁允许部分任务并存；较早启动的长任务可能最后才结束。
            finished = info.ended_at or info.started_at
            if last is None or finished > (last.ended_at or last.started_at):
                last = info
            if (info.task == "main" and info.status == "success" and game_day(finished) == game_day(now)
                    and (full is None or finished > (full.ended_at or full.started_at))):
                full = info
        except (TypeError, ValueError, KeyError, OverflowError, OSError) as exc:
            unreadable = True
            logging.getLogger("March7thAssistant").warning("跳过无效的运行记录 %s：%s", run_id, exc)
    return History(last, full, live, unreadable and last is None)
