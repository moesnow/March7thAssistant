"""首次配置里可调整的完整运行开关、副本和耗时估算。"""
from dataclasses import dataclass

from module.instance_limits import GOLDEN_CALYX, CRIMSON_CALYX, STAGNANT_SHADOW, CAVERN, ORNAMENT
from module.localization import get_instance_names, get_raw_instance_names, tr
from module.task_catalog import BY_ID

TASK_IDS = ("power", "daily", "reward", "activity", "echo", "currencywars", "universe", "challenge", "fight")
WEEKLY = frozenset(("echo", "currencywars", "universe", "challenge"))
PRESETS = {"recommended": TASK_IDS[:7], "daily": TASK_IDS[:4], "all": TASK_IDS}
# 常见配置的下限、上限，单位为分钟。每次完整运行只计一次启动和收尾。
MINUTES = {
    "startup": (3, 5), "power": (8, 20), "daily": (2, 6), "reward": (1, 3),
    "activity": (1, 2), "fight": (60, 120), "echo": (6, 12), "currencywars": (30, 90),
    "universe": (30, 60), "challenge": (20, 60),
}
INSTANCE_TYPES = (GOLDEN_CALYX, CRIMSON_CALYX, STAGNANT_SHADOW, CAVERN, ORNAMENT)


@dataclass(frozen=True)
class SetupTask:
    id: str
    name: str
    description: str
    icon: str
    weekly: bool


@dataclass(frozen=True)
class InstanceItem:
    value: str
    text: str
    info: str


@dataclass(frozen=True)
class InstanceType:
    value: str
    text: str
    items: tuple[InstanceItem, ...]


def tasks(available):
    descriptions = {
        "power": tr("把开拓力用在你选择的副本上"), "daily": tr("完成实训，领取 500 活跃度奖励"),
        "reward": tr("委托、邮件、无名勋礼、兑换码等"), "activity": tr("每日签到和双倍掉落"),
        "echo": tr("每周 3 次，优先消耗开拓力"), "currencywars": tr("每周自动完成积分奖励"),
        "universe": tr("每周自动完成积分奖励"), "challenge": tr("混沌回忆等三项，需要先配好队伍"),
        "fight": tr("需要前台全屏，通常超过 1 小时"),
    }
    names = {"currencywars": tr("货币战争积分"), "universe": tr("差分宇宙积分")}
    return tuple(SetupTask(key, names.get(key) or tr(BY_ID[key].name), descriptions[key], BY_ID[key].icon,
                           key in WEEKLY) for key in TASK_IDS if available(key))


def enabled_tasks(config, available):
    return frozenset(key for key in available if any(config.get_value(switch) for switch in BY_ID[key].switches))


def preset_tasks(preset, available):
    return frozenset(available).intersection(PRESETS.get(preset, ()))


def instances():
    raw = get_raw_instance_names()
    local = get_instance_names() or {}
    return tuple(InstanceType(kind, tr(kind), tuple(
        InstanceItem(name, tr(name), local.get(tr(kind), {}).get(tr(name), ""))
        for name in raw.get(kind, {}))) for kind in INSTANCE_TYPES)


def instance(config):
    kind = config.get_value("instance_type")
    return kind, (config.get_value("instance_names") or {}).get(kind, "")


def instance_note(config):
    if config.get_value("power_plan"):
        return tr("已启用体力计划，清体力时会按计划选择副本。")
    if config.get_value("build_target_enable"):
        return tr("已启用培养目标，清体力时会按培养目标选择副本。")
    return ""


def task_changes(config, available, enabled, selected, before_enabled, before_instance):
    enabled = set(enabled)
    values = {}
    for key in enabled.symmetric_difference(before_enabled).intersection(available):
        switches = BY_ID[key].switches
        on = key in enabled
        if any(bool(config.get_value(switch)) != on for switch in switches):
            values.update(dict.fromkeys(switches, on))
    if selected and selected != before_instance and "power" in available and not instance_note(config):
        kind, name = selected
        if kind not in INSTANCE_TYPES or name not in get_raw_instance_names().get(kind, {}):
            raise ValueError(tr("请选择列表中的副本。"))
        names = config.get_value("instance_names") or {}
        if names.get(kind) != name:
            values["instance_names"] = {**names, kind: name}
        if config.get_value("instance_type") != kind:
            values["instance_type"] = kind
    return values


def _duration(low, high):
    low, high = (5 * ((n + 2) // 5) for n in (low, high))
    if low < 60 and high > 90:
        return tr("{minutes} 分钟–{hours} 小时").format(minutes=low, hours=f"{high / 60:.1f}".removesuffix(".0"))
    if high <= 90:
        return tr("{minutes} 分钟").format(minutes=str(low) if low == high else f"{low}–{high}")
    low, high = (f"{n / 60:.1f}".removesuffix(".0") for n in (low, high))
    return tr("{hours} 小时").format(hours=low if low == high else f"{low}–{high}")


def estimate(enabled):
    selected = set(enabled).intersection(TASK_IDS)
    if not selected:
        return tr("还没有选择任何任务，完整运行不会做任何事。")

    def duration(keys):
        return _duration(*(sum(MINUTES[key][i] for key in keys) for i in (0, 1)))

    daily = duration((selected - WEEKLY) | {"startup"})
    if weekly := selected & WEEKLY:
        return tr("按当前选择，每天大约 {daily}，周常每周另外 {weekly}（按常见配置估算）。").format(
            daily=daily, weekly=duration(weekly))
    return tr("按当前选择，每天大约 {daily}（按常见配置估算）。").format(daily=daily)
