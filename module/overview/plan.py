"""完整运行的编排顺序与准入条件。每组仍在原先构造步骤列表的时刻求值。"""
from dataclasses import dataclass
from datetime import date
import sys

from utils.date import Date


@dataclass(frozen=True)
class Step:
    icon: str
    setting: str
    switches: tuple[str, ...] = ()
    timestamp: str = ""
    cycle: str = ""


STEP_NAMES = {
    "prepare": "日常准备",
    "redemption": "兑换码",
    "relic_cleanup": "每周遗器清理",
    "build_target": "培养目标",
    "support": "查询支援实训",
    "activity": "活动",
    "echo": "历战余响",
    "power": "清体力",
    "resin": "合成自塑尘脂",
    "ember": "余烬兑换",
    "currencywars": "货币战争",
    "weekly_divergent": "差分宇宙积分奖励",
    "fight": "锄大地",
    "divergent_count": "差分宇宙固定次数",
    "universe": "模拟宇宙",
    "forgottenhall": "混沌回忆",
    "purefiction": "虚构叙事",
    "apocalyptic": "末日幻影",
    "lc3": "三星光锥叠加",
    "reward": "日常领奖",
    "daily": "每日实训",
}

STEPS = {
    "prepare": Step("UiIcon.CLIPBOARD_TASK", "daily_enable"),
    "redemption": Step("UiIcon.TICKET", "reward_redemption_code_enable", ("reward_enable", "reward_redemption_code_enable")),
    "relic_cleanup": Step("UiIcon.BOX", "break_down_level_four_relicset", ("power_enable",)),
    "build_target": Step("UiIcon.TARGET", "build_target_enable", ("build_target_enable",)),
    "support": Step("UiIcon.PEOPLE", "borrow_enable"),
    "activity": Step("UiIcon.SPARKLE", "activity_enable"),
    "echo": Step("UiIcon.CROWN", "echo_of_war_enable", ("power_enable", "echo_of_war_enable"), "echo_of_war_timestamp", "week"),
    "power": Step("UiIcon.BATTERY_CHARGE", "power_enable", ("power_enable",)),
    "resin": Step("UiIcon.BOX", "asset_self_molding_resin_enable", ("asset_manager_enable", "asset_self_molding_resin_enable"), "asset_self_molding_resin_timestamp", "month"),
    "ember": Step("UiIcon.COIN", "asset_manager_enable", ("asset_manager_enable",)),
    "currencywars": Step("UiIcon.COIN_STACK", "currencywars_enable", ("currencywars_enable",), "currencywars_timestamp", "week"),
    "weekly_divergent": Step("UiIcon.PLANET", "weekly_divergent_enable", ("weekly_divergent_enable",), "weekly_divergent_timestamp", "week"),
    "fight": Step("UiIcon.MAP", "fight_enable", ("fight_enable",), "fight_timestamp", "day"),
    "divergent_count": Step("UiIcon.PLANET", "universe_enable", ("universe_enable",), "universe_timestamp", "frequency"),
    "universe": Step("UiIcon.PLANET", "universe_enable", ("universe_enable",), "universe_timestamp", "frequency"),
    "forgottenhall": Step("UiIcon.TROPHY", "forgottenhall_enable", ("forgottenhall_enable",), "forgottenhall_timestamp", "week"),
    "purefiction": Step("UiIcon.TROPHY", "purefiction_enable", ("purefiction_enable",), "purefiction_timestamp", "week"),
    "apocalyptic": Step("UiIcon.TROPHY", "apocalyptic_enable", ("apocalyptic_enable",), "apocalyptic_timestamp", "week"),
    "lc3": Step("UiIcon.STACK", "asset_lc3_star_superimpose_enable", ("asset_manager_enable", "asset_lc3_star_superimpose_enable")),
    "reward": Step("UiIcon.GIFT", "reward_enable"),
    "daily": Step("UiIcon.CLIPBOARD_TASK", "daily_enable"),
}
PREPARATION = ("redemption", "relic_cleanup", "build_target", "support", "activity", "echo", "power")
TOUCH = ("support", "echo", "power", "reward", "daily")
EMBER_ITEMS = (
    ("星轨专票", "asset_ember_special_pass", 5),
    ("星轨通票", "asset_ember_regular_pass", 5),
    ("命运的足迹", "asset_ember_tracks_of_destiny", 2),
)


def main_order(cfg):
    universe = "divergent_count" if getattr(cfg, "universe_category", None) == "divergent" else "universe"
    return ("prepare", "resin", "ember", "currencywars", "weekly_divergent", "fight", universe,
            "forgottenhall", "purefiction", "apocalyptic", "lc3", "reward", "daily")


def plan_order(cfg, touch=False):
    return TOUCH if touch else PREPARATION + main_order(cfg)[1:]


def planned_steps(cfg, task, *, touch, backend):
    if task == "routine":
        order = TOUCH if touch else (*PREPARATION, "reward", "daily")
        return [key for key in order if key in ("reward", "daily") or
                entry_state(key, cfg, touch=touch, full_run=False) == "pending"]
    return [key for key in plan_order(cfg, touch) if entry_state(key, cfg, touch=touch) == "pending"
            and detail_state(key, cfg, backend=backend, headless=lambda: cfg.browser_headless_enable)
            in ("pending", "claim_only")]


def due(cycle, timestamp, hour, now=None):
    check = {"day": Date.is_next_x_am, "week": Date.is_next_mon_x_am, "month": Date.is_next_month_x_am}[cycle]
    return check(timestamp, hour) if now is None else check(timestamp, hour, now=now)


def cycle_for(step, cfg):
    if step.cycle == "frequency":
        return "week" if cfg.universe_frequency == "weekly" else "day"
    return step.cycle


def entry_state(key, cfg, *, touch=False, full_run=True, now=None):
    """是否将该函数加入 run_steps。内层自行跳过的操作仍进入原有日志和恢复流程。"""
    step = STEPS[key]
    if not all(getattr(cfg, switch) for switch in step.switches):
        return "disabled"
    if key == "support" and not cfg.power_enable:
        if touch or not (cfg.activity_enable and (cfg.activity_gardenofplenty_enable
                         or cfg.activity_realmofthestrange_enable or cfg.activity_planarfissure_enable)):
            return "disabled"
    if key == "reward" and touch and not cfg.reward_enable:
        return "disabled"
    if key == "ember" and not any(cfg.get_value(base + "_enable", False) for _, base, _ in EMBER_ITEMS):
        return "disabled"
    if step.timestamp and (key != "echo" or full_run):
        cycle = cycle_for(step, cfg)
        if not due(cycle, getattr(cfg, step.timestamp), cfg.refresh_hour, now):
            return "done_" + cycle
    return "pending"


def activity_enabled(cfg):
    return cfg.activity_enable


def rewards_enabled(cfg):
    return cfg.reward_enable


def training_due(cfg, *, full_run=False, now=None):
    return cfg.daily_enable and (not full_run or due("day", cfg.last_run_timestamp, cfg.refresh_hour, now))


def support_query_enabled(cfg, *, full_run=False, now=None):
    return training_due(cfg, full_run=full_run, now=now) and cfg.borrow_enable and not cfg.borrow_character_enable


def count_keys(cycle):
    base = "divergent_universe_weekly" if cycle == "weekly" else "divergent_universe_daily"
    return base + "_completed_count", base + "_completed_timestamp"


def current_count(cfg, cycle, now=None):
    count_key, stamp_key = count_keys(cycle)
    count = max(int(cfg.get_value(count_key, 0) or 0), 0)
    stamp = float(cfg.get_value(stamp_key, 0) or 0)
    expired = not stamp or due("week" if cycle == "weekly" else "day", stamp, cfg.refresh_hour, now)
    return (0 if expired else count), bool(expired and (count or stamp))


def remaining_runs(target, completed):
    return max(0, target - completed)


def training_collect(cfg):
    return cfg.reward_enable and cfg.reward_quest_enable


def echo_day_due(cfg, today=None):
    return (today or date.today()).isoweekday() >= cfg.echo_of_war_start_day_of_week


def relic_due(cfg, now=None):
    if not cfg.get_value("break_down_level_four_relicset", False):
        return False
    args = (cfg.get_value("weekly_relic_cleanup_timestamp", 0),
            cfg.get_value("weekly_relic_cleanup_day_of_week", 1), cfg.refresh_hour)
    return Date.is_weekly_day_due(*args) if now is None else Date.is_weekly_day_due(*args, now=now)


def ember_due(cfg, timestamp_key, now=None):
    return due("month", float(cfg.get_value(timestamp_key, 0) or 0), cfg.refresh_hour, now)


def desktop_extra_supported(backend, is_headless):
    return sys.platform == "win32" and (backend() != "cloud" or not is_headless())


def detail_state(key, cfg, *, now=None, backend="local", headless=lambda: False):
    """已进入步骤后，游戏操作前已有的跳过条件。实时画面才能决定的内容留待运行确认。"""
    if key == "support" and not support_query_enabled(cfg, full_run=True, now=now):
        return "done_day" if cfg.daily_enable and not training_due(cfg, full_run=True, now=now) else "disabled"
    if key == "divergent_count":
        cycle = "weekly" if cfg.universe_frequency == "weekly" else "daily"
        target = int(cfg.universe_count)
        if target <= 0:
            return "zero_count"
        if not remaining_runs(target, current_count(cfg, cycle, now)[0]):
            return "done_week" if cycle == "weekly" else "done_day"
    if key == "echo" and not echo_day_due(cfg, now.date() if now else None):
        return "not_due"
    if key == "relic_cleanup" and not relic_due(cfg, now):
        if not cfg.get_value("break_down_level_four_relicset", False):
            return "disabled"
        stamp = cfg.get_value("weekly_relic_cleanup_timestamp", 0)
        return "not_due" if due("week", stamp, cfg.refresh_hour, now) else "done_week"
    if key == "ember" and not any(ember_due(cfg, base + "_timestamp", now) for _, base, _ in EMBER_ITEMS
                                  if cfg.get_value(base + "_enable", False)):
        return "done_month"
    if key == "daily" and not training_due(cfg, full_run=True, now=now):
        if training_collect(cfg):
            return "claim_only"
        return "done_day" if cfg.daily_enable else "disabled"
    if (key == "activity" and not activity_enabled(cfg)) or (key == "reward" and not rewards_enabled(cfg)):
        return "disabled"
    if key in ("fight", "universe") and not desktop_extra_supported(lambda: backend, headless):
        return "unsupported"
    return "pending"


def select_steps(order, cfg, actions, *, full_run=True, touch=False, only=None):
    from utils.runs import observe_step

    steps = []
    # 单项重试仅附带该项本来需要的准备工作，不启动同组的其他任务。
    prerequisites = set()
    if only in ("echo", "power", "activity") and only in order:
        if entry_state(only, cfg, full_run=full_run, touch=touch) != "pending":
            return []
        prerequisites.add("support")
        if not touch:
            prerequisites.add("build_target")
    for key in order:
        if only and key != only and key not in prerequisites and not (key == "prepare" and only in PREPARATION):
            continue
        if entry_state(key, cfg, full_run=full_run, touch=touch) == "pending":
            action = actions[key]
            if key != "prepare":
                def skipped(key=key):
                    if not full_run:
                        return False
                    from module.config.platform import get_control_backend
                    state = detail_state(key, cfg, backend=get_control_backend(cfg),
                                         headless=lambda: cfg.browser_headless_enable)
                    return state not in ("pending", "claim_only")

                action = observe_step(key, action, skipped)
            steps.append((STEP_NAMES[key], action))
    return steps
