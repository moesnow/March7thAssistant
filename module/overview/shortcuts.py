"""快捷启动的存储、迁移和编辑。配置只保存操作 ID、中文原文和用户输入。"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, replace
import os
from pathlib import Path

from module.localization import tr
from utils.tasks import AVAILABLE_TASKS
from .legacy_cards import DEFAULT_CARDS, HOME_EXTRA_TASKS, display_label, migrate_home_cards
from .types import Shortcut, ShortcutAction

KEY = "overview_shortcuts"
TOOLS = {"autoplot": "自动对话", "screenshot": "游戏截图"}
ACTIONS = AVAILABLE_TASKS | HOME_EXTRA_TASKS | TOOLS
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
PORTRAITS = ("March7th", "JingYuan", "Yanqing", "Herta", "SilverWolf", "Bronya")


def icon_for(action):
    if action in ACTION_ICONS:
        return ACTION_ICONS[action]
    for family in ("currencywars", "divergent", "universe", "fight"):
        if action.startswith(family) or action in HOME_EXTRA_TASKS and family in action:
            return ACTION_ICONS[family]
    return "UiIcon.TOOLBOX"


def defaults():
    return tuple(Shortcut(key, ACTIONS[key], icon_for(key)) for key in
                 ("currencywarsloop", "divergentloop", "autoplot", "screenshot"))


def _builtin_image(path):
    # 文件选择器可能写入绝对路径。仅识别安装目录中这 13 个文件。
    root = Path("assets/app/images")
    allowed = [root / f"{name}.jpg" for name in PORTRAITS]
    allowed.extend(root / "dark" / f"{name}.png" for name in (*PORTRAITS, "Evernight"))
    candidate = os.path.normcase(os.path.abspath(path.replace("\\", "/")))
    return any(candidate == os.path.normcase(os.path.abspath(p)) for p in allowed)


def _name(value, fallback):
    return value if isinstance(value, str) and value.strip() else fallback


def _decode(row, legacy=False):
    if not isinstance(row, dict):
        return None
    action = row.get("task_id" if legacy else "id", "main" if legacy else None)
    menu = ()
    if (row.get("action_type") == "menu" if legacy else action == "menu"):
        entries = row.get("menu_items" if legacy else "menu")
        children = []
        for entry in entries if isinstance(entries, (list, tuple)) else ():
            if not isinstance(entry, dict):
                continue
            child = entry.get("task_id" if legacy else "id")
            if isinstance(child, str) and child in ACTIONS:
                children.append(ShortcutAction(child, _name(entry.get("label" if legacy else "name"), ACTIONS[child])))
        action, menu = "menu", tuple(children)
    elif not isinstance(action, str) or action not in ACTIONS:
        return None
    name = _name(row.get("title" if legacy else "name"), ACTIONS.get(action, "任务菜单"))
    fallback = icon_for(menu[0].id if menu else action)
    image = row.get("icon" if legacy else "image")
    image = image if isinstance(image, str) and image.strip() else None
    if legacy and image and _builtin_image(image):
        image = None
    icon = row.get("icon")
    return Shortcut(action, name, icon if not legacy and icon in ICONS else fallback, image, menu)


def _matches_defaults(cards):
    if cards == DEFAULT_CARDS:
        return True
    if not isinstance(cards, list) or len(cards) != len(DEFAULT_CARDS):
        return False
    from module.localization import translations_of

    def matches_label(value, expected):
        return value == expected or isinstance(value, str) and value in translations_of(expected).values()

    for card, default in zip(cards, DEFAULT_CARDS):
        if not isinstance(card, dict) or card.keys() != default.keys():
            return False
        if any(card[key] != default[key] for key in ("icon", "task_id", "action_type")):
            return False
        if not matches_label(card["title"], default["title"]):
            return False
        menu, expected = card["menu_items"], default["menu_items"]
        if not isinstance(menu, list) or len(menu) != len(expected):
            return False
        for item, old in zip(menu, expected):
            if (not isinstance(item, dict) or item.keys() != old.keys() or item["task_id"] != old["task_id"]
                    or not matches_label(item["label"], old["label"])):
                return False
    return True


def migrate(cards):
    if cards is None or _matches_defaults(cards):
        return defaults()
    if not isinstance(cards, list):
        return defaults()
    copied = deepcopy(cards)
    migrate_home_cards(copied)
    return _decode_list(copied, legacy=True)


def _decode_list(raw, *, legacy=False):
    if not isinstance(raw, list):
        return defaults()
    items = tuple(item for row in raw if (item := _decode(row, legacy)) is not None)
    return items if items or not raw else defaults()


def _encode(cards):
    return [{"id": card.id, "name": card.name, "icon": card.icon, "image": card.image,
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


def load_shortcuts(config):
    raw = config.get_value(KEY)
    if raw is not None:
        return _decode_list(raw)
    legacy = config.get_value("home_cards")
    # Each config may reload (or edit) its legacy list in place. Keep an independent
    # copy for comparison and reuse the immutable conversion between refreshes.
    cache = getattr(config, "__dict__", None)
    previous = cache.get("_overview_legacy_shortcuts") if cache is not None else None
    if previous is not None and previous[0] == legacy:
        return previous[1]
    items = migrate(legacy)
    if cache is not None:
        cache["_overview_legacy_shortcuts"] = deepcopy(legacy), items
    return items


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
    if name == "任务菜单":
        return tr("任务菜单")
    return display_label(name, TOOLS.values())


def display_shortcuts(config):
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
                    or item.image is not None and not isinstance(item.image, str)
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
            self._config.set_value(KEY, _encode(items))
        self._original = items
