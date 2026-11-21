import sys

from .platform import InvalidGameConnection, get_control_backend, get_ui_profile
from utils.game_key_templates import PROMPT_KEY_DEFAULTS, key_prompt_path


AUTO_DETECT_GAME_HOTKEYS = "auto_detect_game_hotkeys_enable"


def manual_game_hotkey(config, name, default=None):
    key = config.get_value(name, default)
    if name not in PROMPT_KEY_DEFAULTS:
        return key
    key = key.lower() if isinstance(key, str) else None
    return key if key_prompt_path(key) else PROMPT_KEY_DEFAULTS[name]


def detect_game_hotkeys(config, names: tuple[str, ...] | None = None) -> dict[str, str]:
    """读取 Windows 本地键鼠客户端的键位，供弹窗预览和任务使用。"""
    if sys.platform != "win32":
        return {}
    try:
        if get_control_backend(config) != "local" or get_ui_profile(config).name != "pc_1080":
            return {}
    except InvalidGameConnection:
        return {}
    game_path = config.get_value("game_path", "")
    if not isinstance(game_path, str) or not game_path:
        return {}

    from utils.registry.star_rail_setting import read_game_hotkeys

    return read_game_hotkeys(game_path, names)
