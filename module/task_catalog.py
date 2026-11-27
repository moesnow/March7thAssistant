"""Task-page metadata and calculations. All labels stored here are source msgids."""
from dataclasses import dataclass
from datetime import datetime

from module.content_pages import PAGE_BY_ID
from module.localization import get_raw_instance_names, tr
from module.overview import plan
from module.overview.readings import POWER_CAP, power_now, power_reading
from module.settings_registry import SETTINGS, Scope, find_setting


@dataclass(frozen=True)
class Task:
    id: str
    description: str
    switches: tuple[str, ...]
    action: str
    steps: tuple[str, ...]
    menu: tuple[tuple[str, str], ...] = ()
    presets: tuple[tuple[str, str], ...] = ()
    touch: bool = False

    @property
    def page(self):
        return PAGE_BY_ID[self.id]

    @property
    def name(self):
        return self.page.name

    @property
    def group(self):
        return self.page.task_group

    @property
    def icon(self):
        return self.page.icon


TASK_MENUS = {
    "fight": {
        "fight": "快速启动 ⭐",
        "fight_gui": "原版运行",
        "fight_update": "更新锄大地",
        "_reset_fight_config": "重置配置文件",
        "_open_fight_dir": "打开程序目录",
        "_open_fight_homepage": "打开项目主页",
    },
    "currencywars": {
        "currencywars": "运行一次",
        "currencywarsloop": "循环运行",
        "currencywarstemp": "中途接管",
    },
    "universe": {
        "divergent": "差分宇宙运行一次 ⭐",
        "divergentloop": "差分宇宙循环运行 ⭐",
        "divergenttemp": "差分宇宙中途接管",
        "universe": "模拟宇宙快速启动（停止维护）",
        "universe_gui": "模拟宇宙原版运行（停止维护）",
        "universe_update": "更新模拟宇宙（停止维护）",
        "_reset_universe_config": "重置模拟宇宙配置文件（停止维护）",
        "_open_universe_dir": "打开模拟宇宙目录（停止维护）",
        "_open_universe_homepage": "打开模拟宇宙项目主页（停止维护）",
    },
    "challenge": {
        "forgottenhall": "混沌回忆",
        "purefiction": "虚构叙事",
        "apocalyptic": "末日幻影",
    },
}


TASKS = (
    Task("power", "按体力计划、培养目标、默认副本的顺序消耗开拓力。", ("power_enable",), "power", ("power",), touch=True),
    Task("daily", "完成当天的每日实训。", ("daily_enable",), "daily", ("daily",), touch=True),
    Task("activity", "检查签到、双倍掉落和活动热点。", ("activity_enable",), "activity", ("activity",)),
    Task("reward", "检查并领取已选的日常奖励。", ("reward_enable",), "reward", ("reward", "redemption"), touch=True),
    Task("fight", "按地图路线清理大世界敌人。", ("fight_enable",), "fight", ("fight",), tuple(TASK_MENUS["fight"].items()),
         (("ranged", "远程一号位锄地"), ("acheron", "黄泉一号位锄地"), ("reward_only", "仅获取特殊物品"))),
    Task("echo", "按所选星期挑战历战余响。", ("echo_of_war_enable",), "echo", ("echo",), touch=True),
    Task("currencywars", "参加货币战争并获取每周积分。", ("currencywars_enable",), "currencywars", ("currencywars",),
         tuple(TASK_MENUS["currencywars"].items()), (("weekly", "刷周积分"), ("promotion", "刷晋升点"), ("rank", "冲职级"))),
    Task("universe", "获取差分宇宙积分，或按配置运行模拟宇宙。", ("weekly_divergent_enable",), "divergent",
         ("weekly_divergent", "divergent_count", "universe"), tuple(TASK_MENUS["universe"].items())),
    Task("challenge", "分别配置混沌回忆、虚构叙事和末日幻影。",
         ("forgottenhall_enable", "purefiction_enable", "apocalyptic_enable"), "forgottenhall",
         ("forgottenhall", "purefiction", "apocalyptic"), tuple(TASK_MENUS["challenge"].items())),
    Task("assets", "处理每月兑换、光锥叠加和遗器清理。", ("asset_manager_enable",), "assets",
         ("resin", "ember", "lc3", "relic_cleanup")),
)
BY_ID = {task.id: task for task in TASKS}
# Only operations without an existing one-shot CLI action use a scoped routine.
PAGE_ACTIONS = ("activity", "echo", "reward", "assets")


def step_page(step_id):
    return find_setting(plan.STEPS[step_id].setting).page


@dataclass(frozen=True)
class TaskStatus:
    kind: str
    text: str
    steps: tuple = ()
    progress: tuple = ()  # (STATE key, saved value)


def status(task, rows, config, *, supported=True):
    from module.overview.cards import STATUS_TEXT
    steps = tuple(row for row in (rows or ()) if row.id in task.steps)
    if not supported:
        kind = "unsupported"
    else:
        states = {row.status for row in steps}
        kind = next((s for s in ("running", "pending", "claim_only", "not_due", "zero_count",
                                 "done_day", "done_week", "done_month", "unsupported", "disabled")
                     if s in states), "unknown")
    progress = tuple((key, config.get_value(key)) for item in SETTINGS if item.page == task.id
                     for key in item.keys if item.key_scope(key) == Scope.STATE)
    return TaskStatus(kind, tr(STATUS_TEXT[kind]) if kind in STATUS_TEXT else tr("暂时无法读取"), steps, progress)


@dataclass(frozen=True)
class OrderState:
    id: str
    title: str
    kind: str  # first：先刷；then：前面刷完或用不上时；skip：不会用到；warning：没有可刷的副本
    text: str
    detail: str


def power_order(config):
    """清体力依次考虑的三个来源，以及按现在的设置会不会用到。顺序和 Power.run 一致。"""
    from module.connection_values import build_target_supported
    from tasks.power.policy import remaining_plan
    plan, remaining = config.power_plan, remaining_plan(config)
    stop = bool(remaining) and not config.power_plan_continue
    target = bool(config.build_target_enable) and build_target_supported(config)
    name = (config.instance_names or {}).get(config.instance_type)
    chosen = bool(name) and name != "无"
    after = ("skip", tr("计划刷完就停，不会刷")) if stop else ("then", tr("计划刷完再刷"))
    if remaining:
        first = ("first", tr("先刷 {count} 项").format(count=len(remaining)))
    else:
        first = ("skip", tr("计划已刷完，跳过") if plan else tr("暂无计划，跳过"))
    if not target:
        second = ("skip", tr("未启用，跳过"))
    else:
        second = after if remaining else ("first", tr("先刷这里"))
    if stop:
        third = after
    elif not chosen:
        third = ("skip" if remaining or target else "warning", tr("没选副本，不会刷"))
    elif target:
        third = ("then", tr("培养目标用不上时才刷"))
    else:
        third = after if remaining else ("first", tr("直接刷这里"))
    place = f"{tr(config.instance_type)} · {tr(name)}" if chosen else tr(config.instance_type)
    return (OrderState("plan", tr("先刷体力计划"), *first, tr("按列表里的副本和次数")),
            OrderState("target", tr("再刷培养目标"), *second, tr("按游戏里的培养目标自动选副本")),
            OrderState("default", tr("最后刷默认副本"), *third, place))


@dataclass(frozen=True)
class Estimate:
    text: str
    ratio: float


def estimate(task_id, config, now=None):
    if task_id != "power" or config.power_plan or config.build_target_enable:
        return None
    from module.instance_limits import INSTANCE_LIMITS
    try:
        reading = power_reading(config)
        category = config.instance_type
        name = config.instance_names.get(category)
        cost, maximum = INSTANCE_LIMITS[category]
        waves = config.instance_names_challenge_count.get(category, maximum)
        if (reading.value is None or not name or name == "无" or name not in get_raw_instance_names().get(category, {})
                or type(waves) is not int or not 1 <= waves <= maximum):
            return None
        power = power_now(reading, now or datetime.now())
        count, remainder = divmod(power // cost, waves)
        if not count:
            text = tr("现在约有 {power} 开拓力，{name}可挑战 {count} 轮").format(power=power, name=tr(name), count=remainder)
        else:
            text = tr("现在约有 {power} 开拓力，{name}可挑战 {count} 次（每次 {waves} 轮）").format(
                power=power, name=tr(name), count=count, waves=waves)
            if remainder:
                text += tr("，另可挑战 {count} 轮").format(count=remainder)
        return Estimate(text, min(power / POWER_CAP, 1.0))
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError, OSError):
        return None
