"""可直接展示的账号方案差异，不构造设置卡。"""

from dataclasses import dataclass

from module.content_pages import PAGE_BY_ID
from module.localization import get_character_names, get_instance_names, tr
from module.search.setting_text import CHOICES, technique_labels
from module.settings_registry import find_setting, Scope
from .layers import SCOPES


@dataclass(frozen=True)
class Difference:
    key: str
    subkey: str | None
    title: str
    page: str
    page_title: str
    link: str
    account_text: str
    shared_text: str


def value_text(key, value, subkey=None):
    """把方案里持久化的原始选项、游戏名称或计数转换为当前语言。"""
    if value is None or value == "":
        return tr("未设置")
    if isinstance(value, (list, tuple, dict)):
        if not value:
            return tr("无")
        if key.endswith("_level") and isinstance(value, (tuple, list)):
            return tr("第 {level} 层").format(level="–".join(map(str, value)))
        if key.endswith(("_team1", "_team2", "_team3")) or key == "daily_memory_one_team":
            characters, techniques = get_character_names(), technique_labels()
            names = [
                f"{characters.get(v[0], v[0])}（{techniques.get(v[1], v[1])}）"
                for v in value
                if isinstance(v, (list, tuple))
                and len(v) == 2
                and isinstance(v[0], str)
                and isinstance(v[1], int)
            ]
            if names:
                return "、".join(names)
        if key == "instance_teams":
            names = [
                tr("{name} · 队伍 {number}").format(name=tr(str(v["instance_name"])), number=v["team_number"])
                for v in value
                if isinstance(v, dict) and "instance_name" in v and "team_number" in v
            ]
            if names:
                return "、".join(names[:3]) + ("…" if len(names) > 3 else "")
        if key == "power_plan" and isinstance(value, list):
            names = [
                tr("{name} × {count}").format(name=tr(str(v[1])), count=v[2])
                for v in value[:3]
                if isinstance(v, (list, tuple)) and len(v) == 3
            ]
            if names:
                return "、".join(names) + ("…" if len(value) > 3 else "")
        return tr("共 {count} 项").format(count=len(value))
    if key == "instance_names" and subkey and isinstance(value, str):
        name = tr(value)
        info = get_instance_names().get(tr(subkey), {}).get(name)
        if isinstance(info, str) and info and info != name:
            return f"{name} · {info}"
        return name
    label = CHOICES.get(key, {}).get(value)
    if label is not None:
        return tr(label)
    if isinstance(value, bool):
        return tr("开") if value else tr("关")
    if key == "weekly_divergent_level" and isinstance(value, int) and 1 <= value <= 6:
        return (
            tr("难度")
            + " "
            + ("Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅹ")[value - 1]
            + (tr("（星阶模式）") if value == 6 else "")
        )
    if key.endswith(("_team", "_team_number")) or key == "instance_teams":
        return tr("队伍 {number}").format(number=value)
    if key.endswith(("_count", "_times")):
        return tr("{count} 次").format(count=value)
    return tr(str(value))


# 隐藏的兼容设置没有独立设置卡，链接到管理它的任务页。
_HIDDEN = {
    "power": {"calyx_golden_preference": "拟造花萼（金）偏好地区", "fuel_ticket_batch_enable": "助燃券连续挑战"},
    "daily": {"daily_himeko_try_enable": "姬子试用", "daily_tasks": "每日实训"},
    "universe": {"divergent_team_type": "差分宇宙队伍类型"},
    "currencywars": {"currencywars_remembrance_trailblazer_name": "开拓者名称"},
}
_HIDDEN_SETTINGS = {key: (page, title) for page, settings in _HIDDEN.items() for key, title in settings.items()}


def differences(config, uid=None, *, store=None):
    rows = []
    for key, own in config.account_overrides(uid, store=store).items():
        if SCOPES.get(key) != Scope.PLAN:
            continue
        setting = find_setting(key)
        if setting:
            page, title, link = setting.page, setting.title, setting.link
        else:
            page, title = _HIDDEN_SETTINGS[key]
            link = "task:" + page
        base = config.shared_value(key)
        parts = own.items() if isinstance(own, dict) and isinstance(base, dict) else [(None, own)]
        for subkey, value in parts:
            shared = base.get(subkey) if subkey is not None else base
            if shared != value:
                label = tr(title) + (" · " + tr(str(subkey)) if subkey is not None else "")
                rows.append(
                    Difference(
                        key,
                        subkey,
                        label,
                        page,
                        tr(PAGE_BY_ID[page].name),
                        link,
                        value_text(key, value, subkey),
                        value_text(key, shared, subkey),
                    )
                )
    return tuple(rows)
