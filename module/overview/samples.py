"""使用发行模板和内存数据的离屏示例，不连接游戏或读取用户目录。"""
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from ruamel.yaml import YAML

from module.localization import tr
from .history import History
from .cards import preview
from .plan import STEP_NAMES, STEPS
from .snapshot import build_snapshot
from .shortcuts import ACTIONS, display_shortcuts
from .types import LiveRun, RunInfo, StepResult


class _Config(SimpleNamespace):
    def set_value(self, key, value):
        setattr(self, key, value)

    def get_value(self, key, default=None):
        return getattr(self, key, default)


def sample_snapshot(state: str, *, now=None):
    if state not in ("ready", "running", "completed", "failed", "setup", "stopped"):
        raise ValueError(f"未知问候状态：{state}")
    now = now or datetime(2026, 11, 23, 13, 20)
    # 即使在 04:00 整取样，也使用当前游戏日内的记录。
    start_day = (now - timedelta(hours=4)).replace(hour=4, minute=0, second=0, microsecond=0)
    end = min(start_day + timedelta(minutes=41), now)
    start = max(end - timedelta(minutes=41), start_day)
    config = _Config(**YAML(typ="safe").load(Path("assets/config/config.example.yaml")))
    config.control_backend = "local"
    config.overview_power = {"value": 186, "timestamp": (now - timedelta(minutes=17)).timestamp()}
    config.scheduled_tasks = [{"name": tr("完整运行"), "time": "04:10", "post_action": "Shutdown"}]
    config.currencywars_enable = config.weekly_divergent_enable = config.echo_of_war_enable = True
    config.daily_enable = config.power_enable = True
    if state in ("setup", "stopped"):
        config.scheduled_tasks = []
    if state == "setup":
        config.overview_power = None
    config.last_run_timestamp = end.timestamp() if state in ("completed", "ready") else 0
    run_id = start.strftime("%Y%m%d-%H%M%S") + "-ac0e"
    result = "partial" if state == "failed" else "stopped" if state == "stopped" else "success"
    keys = ("activity", "power", "reward", "daily")
    if state == "completed":
        for key in vars(config):
            if key.endswith("_timestamp"):
                setattr(config, key, end.timestamp())
        keys = [row.id for row in preview(config, now) if row.status not in ("disabled", "unsupported", "not_due")
                and all(getattr(config, key) for key in STEPS[row.id].switches)]
    if state == "stopped":
        keys = ("activity", "power")
    items = []
    for key in keys:
        status = "success"
        if key == "power" and state in ("stopped", "failed"):
            status = "interrupted" if state == "stopped" else "failed"
        items.append(StepResult(key, tr(STEP_NAMES[key]), status, 713 if key == "power" else 67))
    last = RunInfo(run_id, "main", tr("完整运行"), start, end, (end - start).total_seconds(), "scheduled", result,
                   tuple(items), tr("连续几次未能识别副本结算画面，已保存日志供检查。") if state == "failed" else None, f"run:{run_id}")
    live = LiveRun("main", tr("完整运行"), "execute", "power", True, True, started_at=now - timedelta(minutes=22)) if state == "running" else None
    if state == "running":
        config.scheduled_tasks[0]["name"] = tr("完整运行后检查每周积分奖励与日常领取情况")
    return build_snapshot(config, now=now, live=live, connection=("local", False, None),
                          history_reader=lambda _: History(None if state == "setup" else last, last if state == "completed" else None),
                          is_file=lambda _: state != "setup",
                          shortcuts_reader=lambda cfg: display_shortcuts(cfg, choices=ACTIONS))
