"""Task-page metadata and calculations. All labels stored here are source msgids."""
from dataclasses import dataclass

from module.content_pages import PAGE_BY_ID
from module.localization import get_raw_instance_names, tr
from module.overview import plan
from module.overview.legacy_cards import DEFAULT_CARDS
from module.overview.readings import POWER_CAP, power_reading
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


def _menu(name):
    card = next(card for card in DEFAULT_CARDS if card["title"] == name)
    return tuple((item["task_id"], item["label"]) for item in card["menu_items"])


TASKS = (
    Task("power", "按体力计划或所选副本消耗开拓力。", ("power_enable",), "power", ("power",), touch=True),
    Task("daily", "完成当天的每日实训。", ("daily_enable",), "daily", ("daily",), touch=True),
    Task("activity", "检查签到、双倍掉落和活动热点。", ("activity_enable",), "activity", ("activity",)),
    Task("reward", "检查并领取已选的日常奖励。", ("reward_enable",), "reward", ("reward", "redemption"), touch=True),
    Task("fight", "按地图路线清理大世界敌人。", ("fight_enable",), "fight", ("fight",), _menu("锄大地"),
         (("ranged", "远程一号位锄地"), ("acheron", "黄泉一号位锄地"), ("reward_only", "仅获取特殊物品"))),
    Task("echo", "按所选星期挑战历战余响。", ("echo_of_war_enable",), "echo", ("echo",), touch=True),
    Task("currencywars", "参加货币战争并获取每周积分。", ("currencywars_enable",), "currencywars", ("currencywars",),
         _menu("货币战争"), (("weekly", "刷周积分"), ("promotion", "刷晋升点"), ("rank", "冲职级"))),
    Task("universe", "获取差分宇宙积分，或按配置运行模拟宇宙。", ("weekly_divergent_enable",), "divergent",
         ("weekly_divergent", "divergent_count", "universe"), _menu("差分宇宙")),
    Task("challenge", "分别配置混沌回忆、虚构叙事和末日幻影。",
         ("forgottenhall_enable", "purefiction_enable", "apocalyptic_enable"), "forgottenhall",
         ("forgottenhall", "purefiction", "apocalyptic"), _menu("逐光捡金")),
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
class Estimate:
    text: str
    ratio: float


def estimate(task_id, config):
    if task_id != "power" or config.power_plan or config.build_target_enable:
        return None
    from module.instance_limits import INSTANCE_LIMITS
    try:
        reading = power_reading(config).value
        category = config.instance_type
        name = config.instance_names.get(category)
        cost, maximum = INSTANCE_LIMITS[category]
        waves = config.instance_names_challenge_count.get(category, maximum)
        if (reading is None or not name or name == "无" or name not in get_raw_instance_names().get(category, {})
                or type(waves) is not int or not 1 <= waves <= maximum):
            return None
        count, remainder = divmod(reading // cost, waves)
        text = tr("按上次读取的 {power} 开拓力，{name}可挑战 {count} 次（每次 {waves} 轮）").format(
            power=reading, name=tr(name), count=count, waves=waves)
        if remainder:
            text += tr("，另可挑战 {count} 轮").format(count=remainder)
        return Estimate(text, min(reading / POWER_CAP, 1.0))
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError, OSError):
        return None
