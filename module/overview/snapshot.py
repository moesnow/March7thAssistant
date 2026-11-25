from datetime import datetime
import logging
from pathlib import Path

from module.localization import tr
from . import cards, plan
from .history import game_day, read_history
from .shortcuts import display_shortcuts, load_shortcuts
from .readings import daily_training, power_reading
from .types import Button, Greeting, OverviewSnapshot

PHASE_NAMES = {"prepare": "准备", "launch": "启动游戏", "execute": "执行任务", "finish": "收尾"}


def time_greeting(hour):
    if 5 <= hour < 11:
        return tr("早上好，开拓者")
    if 11 <= hour < 14:
        return tr("中午好，开拓者")
    if 14 <= hour < 18:
        return tr("下午好，开拓者")
    return tr("晚上好，开拓者")


def make_greeting(now, live, setup, history, rows, daily, refresh_hour=4):
    if live:
        name = tr(plan.STEP_NAMES[live.step]) if live.step in plan.STEP_NAMES else live.name
        phase = live.phase if live.phase in PHASE_NAMES else "execute"
        buttons = []
        if live.can_stop:
            buttons.append(Button("stop", tr("停止")))
        if live.can_pause:
            buttons.append(Button("toggle_pause", tr("继续任务") if live.paused else tr("暂停")))
        buttons.append(Button("view_run", tr("查看运行"), "run:current"))
        description = tr(PHASE_NAMES[phase])
        if live.started_at is not None:
            minutes = max(0, int((now - live.started_at).total_seconds() // 60))
            description = tr("{phase} · 已运行 {minutes} 分钟").format(phase=description, minutes=minutes)
        if live.account_number is not None:
            name = tr("{name} · 第 {index} / {total} 个账号").format(
                name=live.account_name, index=live.account_number, total=live.account_total) + " · " + name
        elif live.account_name:
            name = f"{live.account_name} · {name}"
        return Greeting("running", tr("运行中"), tr("正在运行：{name}").format(name=name),
                        tr("任务已暂停") if live.paused else description, "chibi_typing", tuple(buttons), name, phase)
    if setup:
        return Greeting("setup", tr("待设置"), tr("还差一步就能开始"), setup.description, "chibi_ok",
                        (Button("configure", tr("继续设置"), setup.link),))
    last = history.last if history else None
    if last and game_day(last.ended_at or last.started_at, refresh_hour) == game_day(now, refresh_hour):
        if last.status in ("failed", "partial", "aborted", "blocked"):
            failed = next((s for s in last.steps if s.status in ("failed", "interrupted")), None)
            key = failed.id if failed else last.retry_step
            name = tr(plan.STEP_NAMES[key]) if key in plan.STEP_NAMES else last.name
            buttons = [Button("view_reason", tr("查看原因"), last.link)]
            if key in plan.STEPS and (last.task == "main" or last.task == "routine"):
                buttons.append(Button("retry_step", tr("重试这一项"), target=key))
            else:
                from utils.tasks import AVAILABLE_TASKS
                if last.task in AVAILABLE_TASKS:
                    buttons.append(Button("start_task", tr("重新运行"), target=last.task))
            return Greeting("failed", tr("需要处理"), tr("{name}没有完成").format(name=name),
                            last.error or tr("查看运行日志了解原因。"), "chibi_lost", tuple(buttons))
        if last.status in ("stopped", "interrupted"):
            return Greeting("stopped", tr("已停止"), tr("任务已停止"), tr("继续运行时会重新检查已完成的项目。"),
                            "chibi_full", (Button("continue", tr("继续运行")),))
    full = history.full if history else None
    if rows is not None and daily is not None and full and game_day(full.ended_at or full.started_at, refresh_hour) == game_day(now, refresh_hour):
        covered = {item.id for item in full.steps if item.status == "success"}
        # 去重/刷新型项目仍按时间戳。无时间戳的常规检查由当天成功的完整运行佐证。
        def settled(row):
            if row.status == "claim_only":
                return daily.completed or row.id in covered
            if row.status != "pending":
                return True
            if plan.STEPS[row.id].timestamp or row.id in ("daily", "relic_cleanup", "ember"):
                return False
            return not full.steps or row.id in covered

        if all(settled(row) for row in rows):
            return Greeting("completed", tr("已完成"), tr("今天的任务都做完了"), tr("本次完整运行的结果已保存。"),
                            "chibi_wave", (Button("view_result", tr("查看本次结果"), full.link),))
    if rows is None:
        description = tr("暂时无法读取运行计划。")
    else:
        count = sum(row.status in ("pending", "claim_only") for row in rows)
        description = tr("本次完整运行有 {count} 项待执行。").format(count=count)
    return Greeting("ready", tr("就绪"), time_greeting(now.hour), description,
                    "chibi_full", (Button("start_full", tr("开始完整运行")), Button("choose_task", tr("运行单项"))))


def build_snapshot(config, *, now=None, live=None, history_reader=read_history, shortcuts_reader=display_shortcuts,
                   connection=None, is_file=Path.is_file):
    """now 为本机墙上时间。传入 connection=(backend, touch, error) 可离线构造。"""
    now = now or datetime.now()
    unavailable = []

    def block(key, get, fallback=None):
        try:
            return get()
        except Exception:
            logging.getLogger("March7thAssistant").warning("总览无法读取 %s", key, exc_info=True)
            unavailable.append(key)
            return fallback

    def get_connection():
        from module.config.platform import InvalidGameConnection, get_control_backend, get_ui_profile
        try:
            backend = get_control_backend(config)
            touch = get_ui_profile(config).name == "touch_720"
            error = tr("当前后端不支持，未执行") if backend == "cloud" and touch else None
            return backend, touch, error
        except InvalidGameConnection as exc:
            return None, False, str(exc)

    backend, touch, error = connection or block("connection", get_connection, (None, False, tr("配置加载失败")))
    history = block("last_run", lambda: read_history(now, config) if history_reader is read_history else history_reader(now))
    if history and history.unreadable:
        unavailable.append("last_run")
    # GUI 的暂停、停止状态来自运行页。相同进程的细分步骤由工作进程补充。
    recorded = history.live if history else None
    if live and recorded and (live.run_id == recorded.run_id or (not live.run_id and live.task == recorded.task)):
        from dataclasses import replace
        live = replace(live, phase=recorded.phase, step=recorded.step, run_id=recorded.run_id, started_at=recorded.started_at,
                       account_number=recorded.account_number, account_total=recorded.account_total, account_name=recorded.account_name)
    live = live or recorded
    setup = block("setup", lambda: cards.setup_check(config, backend, error, lambda p: is_file(Path(p))))
    rows = block("plan", lambda: cards.preview(config, now, touch=touch, backend=backend,
                                               current_step=(live.step or live.task) if live and live.phase == "execute" else None))
    daily = block("daily", lambda: daily_training(config, now))
    hour = config.refresh_hour if isinstance(getattr(config, "bound_account", None), str) else 4
    greeting = block("greeting", lambda: make_greeting(now, live, setup, history, rows, daily, hour))
    power = block("power", lambda: power_reading(config))
    weekly = block("weekly", lambda: cards.weekly_items(config, now, touch))
    schedule = block("schedule", lambda: cards.scheduled_run(config, now))
    checks = block("checks", lambda: cards.checks(config, now, setup, backend, history.last if history else None,
                                                schedule, schedule_available="schedule" not in unavailable))
    shortcuts = block("shortcuts", lambda: shortcuts_reader(config))
    hidden = shortcuts == () and block(
        "shortcuts", lambda: any(item.menu or item.id != "menu" for item in load_shortcuts(config)), False)
    background = block("background", lambda: cards.background_path(config), "")
    mascot = block("show_mascot", lambda: bool(config.get_value("overview_show_mascot", True)), True)
    return OverviewSnapshot(now, greeting, power, daily, weekly, schedule, rows, history.last if history else None,
                            checks, shortcuts, background, mascot, tuple(unavailable), hidden)
