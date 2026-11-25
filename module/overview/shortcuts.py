"""总览快捷启动的读取、显示和编辑。"""
from contextlib import contextmanager
from dataclasses import asdict, replace
from pathlib import Path

from module.localization import tr
from module.task_catalog import TASKS
from utils.tasks import AVAILABLE_TASKS
from .types import Shortcut, ShortcutAction

KEY = "overview_shortcuts"
HOME_EXTRA_TASKS = {
    "_reset_universe_config": "重置模拟宇宙配置文件",
    "_open_universe_dir": "打开模拟宇宙目录",
    "_open_universe_homepage": "打开模拟宇宙项目主页",
    "_reset_fight_config": "重置锄大地配置文件",
    "_open_fight_dir": "打开锄大地程序目录",
    "_open_fight_homepage": "打开锄大地项目主页",
}
TOOLS = {"autoplot": "自动对话", "screenshot": "游戏截图"}
ACTIONS = AVAILABLE_TASKS | HOME_EXTRA_TASKS | TOOLS
# 两个默认菜单：按钮写玩法名，菜单项写运行方式，和任务页的叫法一致。
MENUS = {
    "currencywars": {"currencywars": "运行一次", "currencywarsloop": "循环运行", "currencywarstemp": "中途接管"},
    "divergent": {"divergent": "运行一次", "divergentloop": "循环运行", "divergenttemp": "中途接管"},
}
MENU_NAMES = {key: name for menu in MENUS.values() for key, name in menu.items()}
BUILTIN_LABELS = (
    frozenset(ACTIONS.values()) | frozenset(MENU_NAMES.values()) | {"任务菜单"}
    | {task.name for task in TASKS if task.menu}
    | {label for task in TASKS for _, label in task.menu}
)
ACTION_ICONS = {
    "main": "FIF.PLAY", "routine": "UiIcon.CLIPBOARD_TASK", "daily": "UiIcon.CLIPBOARD_TASK",
    "power": "UiIcon.BATTERY_CHARGE", "currencywars": "UiIcon.COIN_STACK", "divergent": "UiIcon.PLANET",
    "universe": "UiIcon.PLANET", "fight": "UiIcon.MAP", "forgottenhall": "UiIcon.TROPHY",
    "purefiction": "UiIcon.TROPHY", "apocalyptic": "UiIcon.TROPHY", "redemption": "UiIcon.TICKET",
    "character_export": "UiIcon.EXPORT", "game": "FIF.PLAY", "screen_test": "UiIcon.COMPASS",
    "autoplot": "UiIcon.PEOPLE_CHAT", "screenshot": "FIF.CAMERA", "notify": "UiIcon.SEND",
    "app_update": "UiIcon.REFRESH", "game_update": "UiIcon.REFRESH", "game_pre_download": "UiIcon.CLOUD_DOWNLOAD",
    "mobileui_update": "UiIcon.REFRESH",
}
ICONS = tuple(sorted(set(ACTION_ICONS.values()) | {"UiIcon.TOOLBOX", "UiIcon.GIFT", "UiIcon.LIST", "UiIcon.STAR"}))


def icon_for(action):
    if action in ACTION_ICONS:
        return ACTION_ICONS[action]
    for family in ("currencywars", "divergent", "universe", "fight"):
        if action.startswith(family) or action in HOME_EXTRA_TASKS and family in action:
            return ACTION_ICONS[family]
    return "UiIcon.TOOLBOX"


def defaults():
    shortcuts = [Shortcut(key, ACTIONS[key], icon_for(key)) for key in ("routine", "power")]
    for task, names in MENUS.items():
        menu = tuple(ShortcutAction(key, name) for key, name in names.items())
        shortcuts.append(Shortcut("menu", ACTIONS[task], icon_for(task), menu))
    return tuple(shortcuts)


def _name(value, fallback):
    return value if isinstance(value, str) and value.strip() else fallback


def _decode(row):
    if not isinstance(row, dict):
        return None
    action = row.get("id")
    menu = ()
    if action == "menu":
        entries = row.get("menu")
        children = []
        for entry in entries if isinstance(entries, (list, tuple)) else ():
            if not isinstance(entry, dict):
                continue
            child = entry.get("id")
            if isinstance(child, str) and child in ACTIONS:
                children.append(ShortcutAction(child, _name(entry.get("name"), ACTIONS[child])))
        menu = tuple(children)
    elif not isinstance(action, str) or action not in ACTIONS:
        return None
    name = _name(row.get("name"), ACTIONS.get(action, "任务菜单"))
    fallback = icon_for(menu[0].id if menu else action)
    icon = row.get("icon")
    return Shortcut(action, name, icon if icon in ICONS else fallback, menu)


def load_shortcuts(config):
    raw = config.get_value(KEY)
    if not isinstance(raw, list):
        return defaults()
    items = tuple(item for row in raw if (item := _decode(row)) is not None)
    return items if items or not raw else defaults()


def _encode(cards):
    return [{"id": card.id, "name": card.name, "icon": card.icon,
             "menu": [asdict(child) for child in card.menu]} for card in cards]


@contextmanager
def _edit_lock(config):
    if hasattr(config, "config_path") and hasattr(config, "_load_config"):
        from utils.data_files import data_lock
        with data_lock(Path(config.config_path).absolute().parent, name=".overview-shortcuts.lock", timeout=0.5):
            config._load_config(save=False)
            yield
    else:
        yield


def available_actions(config):
    from module.config.platform import InvalidGameConnection, get_control_backend
    from utils.tasks import supported_tasks
    try:
        tasks = supported_tasks(config)
        if "fight" in tasks:
            tasks.update(HOME_EXTRA_TASKS)
        if get_control_backend(config) != "adb":
            tasks["autoplot"] = TOOLS["autoplot"]
    except InvalidGameConnection:
        tasks = {}
    tasks["screenshot"] = TOOLS["screenshot"]
    return {key: tr(name) for key, name in tasks.items()}


def display_name(name):
    return tr(name) if name in BUILTIN_LABELS else name


def stored_label(text: str, msgid: str | None) -> str:
    """编辑器保留未改名项的原文键，其他名称按用户输入保存。"""
    return msgid if msgid is not None and text == display_name(msgid) else text


def display_shortcuts(config, *, choices=None):
    if choices is None:
        choices = available_actions(config)
    result = []
    for item in load_shortcuts(config):
        if item.id == "menu":
            menu = tuple(replace(child, name=display_name(child.name)) for child in item.menu if child.id in choices)
            if menu:
                result.append(replace(item, name=display_name(item.name), menu=menu))
        elif item.id in choices:
            result.append(replace(item, name=display_name(item.name)))
    return tuple(result)


class ShortcutEditor:
    """操作草稿；save 前可随时丢弃。索引来自未过滤的 items，可编辑同名或重复操作。"""
    def __init__(self, config):
        self._config = config
        self._original = load_shortcuts(config)
        self.items = list(self._original)

    def add(self, item: Shortcut):
        self.items.append(item)

    def replace(self, index: int, item: Shortcut):
        self.items[index] = item

    def move(self, index: int, destination: int):
        if not 0 <= index < len(self.items) or not 0 <= destination < len(self.items):
            raise IndexError("快捷启动的位置无效")
        self.items.insert(destination, self.items.pop(index))

    def remove(self, index: int):
        del self.items[index]

    def reset(self):
        self.items = list(defaults())

    def save(self):
        items = tuple(self.items)
        for item in items:
            if (not isinstance(item, Shortcut) or not isinstance(item.name, str) or not item.name.strip()
                    or item.icon not in ICONS or item.id not in (*ACTIONS, "menu")
                    or item.id != "menu" and item.menu):
                raise ValueError(tr("快捷启动的名称、图标或操作无效。"))
            for child in item.menu:
                if not isinstance(child, ShortcutAction) or child.id not in ACTIONS or not isinstance(child.name, str) or not child.name.strip():
                    raise ValueError(tr("任务菜单中的菜单项名称不能为空"))
        if getattr(self._config, "writes_suspended", False) or getattr(self._config, "_readonly", False):
            raise ValueError(tr("配置写入已暂停，请恢复后再保存。"))
        with _edit_lock(self._config):
            if load_shortcuts(self._config) != self._original:
                raise ValueError(tr("快捷启动已在其他窗口修改，请重新打开编辑。"))
            # 和默认项相同时存空值，以后调整默认项也会跟着变。
            self._config.set_value(KEY, None if items == defaults() else _encode(items))
        self._original = items
