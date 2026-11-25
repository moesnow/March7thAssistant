from pathlib import Path

from module.localization import get_current_language, tr
from module.settings_registry import SETTINGS
from module.task_catalog import step_page
from utils.tasks import TASK_NAMES
from . import plan
from .history import game_day
from .schedule import following_tasks, next_schedule
from .types import Check, PlanItem, ScheduledRun, WeeklyItem

STATUS_TEXT = {
    "pending": "将执行", "running": "进行中", "done_day": "今日已完成", "done_week": "本周已完成",
    "done_month": "本月已完成", "disabled": "未开启", "not_due": "未到执行日",
    "unsupported": "当前环境不支持", "claim_only": "仅检查奖励", "zero_count": "计划次数为零",
}
SUMMARY_TEXT = {
    "redemption": "检查新兑换码", "build_target": "读取培养目标", "support": "检查支援角色需求",
    "activity": "检查已开启的活动", "resin": "每月合成", "ember": "每月购买所选物品",
    "fight": "按配置路线运行", "lc3": "叠加三星光锥", "reward": "领取已开启的奖励",
    "daily": "检查实训活跃度",
}


OPTIONS = {
    "activity": {"activity_dailycheckin_enable": "每日签到", "activity_gardenofplenty_enable": "花藏繁生",
                 "activity_realmofthestrange_enable": "异器盈界", "activity_planarfissure_enable": "位面分裂",
                 "activity_journey_highlights_notification_enable": "活动热点通知"},
    "reward": {"reward_dispatch_enable": "委托", "reward_mail_enable": "邮件", "reward_assist_enable": "支援礼盒",
               "reward_srpass_enable": "无名勋礼", "reward_message_enable": "短信", "reward_achievement_enable": "成就"},
    "daily": {"daily_material_enable": "合成材料", "daily_memory_one_enable": "回忆一", "daily_himeko_try_enable": "试用姬子"},
}


def summary(key, cfg, touch=False):
    if key in OPTIONS:
        selected = [tr(label) for switch, label in OPTIONS[key].items() if cfg.get_value(switch, False)]
        if selected:
            return " · ".join(selected[:2]) + ("…" if len(selected) > 2 else "")
    if key in SUMMARY_TEXT:
        return tr(SUMMARY_TEXT[key])
    if key == "power":
        if cfg.power_plan:
            return tr("体力计划 · {count} 项").format(count=len(cfg.power_plan))
        if cfg.build_target_enable and not touch:
            return tr("培养目标")
        name = cfg.instance_names.get(cfg.instance_type, "")
        return tr(name) if name else tr(cfg.instance_type)
    if key in ("echo", "relic_cleanup"):
        day = cfg.echo_of_war_start_day_of_week if key == "echo" else cfg.weekly_relic_cleanup_day_of_week
        return tr("周{day}起执行").format(day=day)
    if key == "currencywars":
        return tr("速通模式") if cfg.currencywars_fast_mode else tr("每周积分奖励")
    if key == "weekly_divergent":
        return tr("难度 {level} · 周积分").format(level=cfg.weekly_divergent_level)
    if key in ("divergent_count", "universe"):
        label = tr("每周 {count} 次") if cfg.universe_frequency == "weekly" else tr("每天 {count} 次")
        return label.format(count=cfg.universe_count)
    levels = getattr(cfg, key + "_level")
    return tr("挑战第 {level} 层").format(level="–".join(map(str, levels)) if isinstance(levels, (tuple, list)) else levels)


def preview(config, now, *, touch=False, backend="local", current_step=None):
    rows = []
    for key in plan.plan_order(config, touch):
        step = plan.STEPS[key]
        state = plan.entry_state(key, config, touch=touch, now=now)
        if state == "pending":
            state = plan.detail_state(key, config, now=now, backend=backend, headless=lambda: config.browser_headless_enable)
        if key == current_step:
            state = "running"
        detail = summary(key, config, touch)
        if get_current_language() in ("zh_CN", "zh_TW") and len(detail) > 16:
            detail = detail[:15] + "…"
        rows.append(PlanItem(key, tr(plan.STEP_NAMES[key]), step.icon, detail, state,
                             tr(STATUS_TEXT[state]), "task:" + step_page(key)))
    return tuple(rows)


def weekly_items(config, now, touch):
    items = []
    for key in plan.plan_order(config, touch):
        step = plan.STEPS[key]
        if key == "relic_cleanup":
            enabled = config.power_enable and config.get_value("break_down_level_four_relicset", False)
            stamp = config.get_value("weekly_relic_cleanup_timestamp", 0)
        elif plan.cycle_for(step, config) == "week":
            enabled = all(getattr(config, switch) for switch in step.switches)
            stamp = getattr(config, step.timestamp)
        else:
            continue
        items.append(WeeklyItem(key, tr(plan.STEP_NAMES[key]), not plan.due("week", stamp, config.refresh_hour, now), bool(enabled)))
    return tuple(items)


def scheduled_run(config, now):
    tasks = config.get_value("scheduled_tasks", []) or []
    _, at, task = next_schedule(tasks, now)
    if task is None:
        return None

    def name(row):
        if row.get("name"):
            return row["name"]
        if row.get("program", "self") == "self":
            key = row.get("args") or "main"
            return tr(TASK_NAMES.get(key, key))
        return row.get("workflow_name") or row.get("program") or tr("未命名")

    chain = (task, *following_tasks(task, [t for t in tasks if isinstance(t, dict)]))
    return ScheduledRun(at, tuple(name(row) for row in chain), chain[-1].get("post_action", "None"))


REMOTE_SWITCHES = tuple(k for card in SETTINGS for k in card.keys
                        if k.startswith("notify_") and k.endswith("_enable") and k != "notify_winotify_enable")


def setup_check(config, backend, connection_error, is_file):
    if connection_error:
        return Check("connection", "error", tr("游戏连接设置需要调整"), str(connection_error), "setting:control_backend")
    if backend == "local" and not (config.game_path and is_file(config.game_path)):
        return Check("game_path", "error", tr("找不到本地游戏"), tr("选择游戏的可执行文件后即可开始。"), "setting:game_path")
    return None


def checks(config, now, setup, backend, last, schedule, *, schedule_available=True):
    items = [setup] if setup else []
    if not config.notification_enable or not any(config.get_value(k, False) for k in REMOTE_SWITCHES):
        items.append(Check("push", "info", tr("尚未设置远程推送"), tr("要在其他设备收到任务通知，请开启推送并设置渠道。"),
                           "setting:notification_enable"))
    if schedule_available and schedule is None:
        items.append(Check("schedule", "info", tr("没有可运行的定时计划"), tr("可以设置自动启动任务的时间。"),
                           "setting:scheduled_tasks"))
    hour = config.refresh_hour if isinstance(getattr(config, "bound_account", None), str) else 4
    if (last and last.status in ("failed", "partial", "aborted") and backend == last.login_required
            and backend in ("cloud", "local") and game_day(last.ended_at or last.started_at, hour) == game_day(now, hour)):
        cloud = backend == "cloud"
        items.append(Check("login", "warning", tr("上次运行需要登录"),
                           tr("云游戏等待登录超时，请打开云游戏完成登录。") if cloud
                           else tr("上次启动时游戏要求重新登录，请打开本地客户端登录。"),
                           "setting:cloud_game_login_timeout" if cloud else "setting:control_backend"))
    return tuple(items)


def background_path(config):
    path = config.get_value("banner_path") or ""
    if path and Path(path).resolve() != Path("./assets/app/images/bg37.jpg").resolve():
        return path
    return ""
