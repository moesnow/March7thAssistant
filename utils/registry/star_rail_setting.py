from functools import lru_cache
from typing import Tuple, Optional
import winreg
import json
import os
from pathlib import Path
from utils.game_key_templates import PROMPT_KEY_DEFAULTS, key_prompt_path

# Registry key paths for different server regions
registry_key_path_cn = r"SOFTWARE\miHoYo\崩坏：星穹铁道"
registry_key_path_oversea = r"SOFTWARE\Cognosphere\Star Rail"

# Specify the value name (assumed to be the same for both CN and international servers)
# International server players should verify these key names are correct
resolution_value_name = "GraphicsSettings_PCResolution_h431323223"
graphics_value_name = "GraphicsSettings_Model_h2986158309"

_HOTKEY_VALUE_NAMES = {
    "hotkey_interact": "HotkeysSettings_Menu_MazeInteract_Keyboard_h2537131863",
    "hotkey_character_details": "HotkeysSettings_Menu_BattleAvatarDetail_Keyboard_h1744695036",
    "hotkey_technique": "HotkeysSettings_Menu_MazeSkill_Keyboard_h1042695892",
    "hotkey_map": "HotkeysSettings_Maze_Map_Keyboard_h1833719210",
    "hotkey_warp": "HotkeysSettings_Maze_Gacha_Keyboard_h3861591226",
    "hotkey_message": "HotkeysSettings_Menu_PhoneMessage_Keyboard_h3569468801",
    "hotkey_auto_battle": "HotkeysSettings_Menu_BattleAuto_Keyboard_h3719200595",
}

# 游戏在按键说明里改绑后写入的编码。
_KEY_NAMES_BY_CODE = {
    5: "shiftleft",
    8: "ctrlleft",
    9: "shiftright",
    10: "altright",
    12: "ctrlright",
    **{13 + n: f"f{n}" for n in range(1, 13)},
    **{26 + n: str(n) for n in range(10)},
    **{36 + n: letter for n, letter in enumerate("abcdefghijklmnopqrstuvwxyz")},
    62: "`",
    63: "-",
    64: "=",
    65: "backspace",
    67: "[",
    68: "]",
    69: "\\",
    70: ";",
    71: "'",
    72: "enter",
    73: ",",
    74: ".",
    75: "/",
    76: "space",
    83: "left",
    84: "right",
    85: "up",
    86: "down",
    **{87 + n: f"num{n}" for n in range(10)},
    98: "divide",
    99: "multiply",
    100: "subtract",
    101: "add",
    103: "decimal",
    110: "capslock",
}


class MissingFPSSettingError(ValueError):
    """游戏未使用自定义图像质量，没有可修改的帧率配置。"""


def registry_path_for_game(game_path: str) -> Optional[str]:
    """仅根据当前所选游戏的 Unity 元数据识别渠道，不猜测。"""
    if not game_path or Path(game_path).name.lower() != "starrail.exe":
        return None
    try:
        info = Path(game_path).parent / "StarRail_Data" / "app.info"
        names = tuple(line.strip() for line in info.read_text(encoding="utf-8-sig").strip().splitlines())
    except (OSError, UnicodeError):
        return None
    return {
        ("miHoYo", "崩坏：星穹铁道"): registry_key_path_cn,
        ("Cognosphere", "Star Rail"): registry_key_path_oversea,
    }.get(names)


def read_game_hotkeys(game_path: str, names: tuple[str, ...] | None = None) -> dict[str, str]:
    """只读所选客户端的键鼠改绑。缺失或无法解码的项目交给调用方回退。"""
    detected = {}
    try:
        path = registry_path_for_game(game_path)
        if path is None:
            return {}
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as registry:
            for name in _HOTKEY_VALUE_NAMES if names is None else names:
                value_name = _HOTKEY_VALUE_NAMES.get(name)
                if value_name is None:
                    continue
                try:
                    code, value_type = winreg.QueryValueEx(registry, value_name)
                except OSError:
                    continue
                if value_type != winreg.REG_DWORD:
                    continue
                key = _KEY_NAMES_BY_CODE.get(code)
                if name in PROMPT_KEY_DEFAULTS and key_prompt_path(key) is None:
                    _warn_missing_key_prompt(name, code, key)
                elif key is not None:
                    detected[name] = key
    except (OSError, ValueError):
        return {}
    return detected


@lru_cache(maxsize=64)
def _warn_missing_key_prompt(name: str, code: int, key: str | None):
    from module.logger import log

    label = "交互" if name == "hotkey_interact" else "角色详情"
    key_text = f"{key.upper()}（键码 {code}）" if key else f"键码 {code}"
    log.warning(f"游戏内{label}键 {key_text} 缺少识别模板，使用小助手设置。")


def get_registry_key_path() -> Optional[str]:
    """检测当前选中游戏的注册表路径，未知或尚不存在时返回 None。"""
    # 延迟导入避免配置模块初始化时的循环依赖，并始终读取最新配置。
    from module.config import cfg
    path = registry_path_for_game(cfg.game_path)
    if path is None:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path):
            return path
    except FileNotFoundError:
        return None


def get_server_by_registry() -> Optional[str]:
    path = get_registry_key_path()
    if path == registry_key_path_cn:
        return "cn"
    if path == registry_key_path_oversea:
        return "global"
    return None


def set_auto_battle_open_setting(value: bool) -> None:
    write_registry_value(winreg.HKEY_CURRENT_USER, get_registry_key_path(), "OtherSettings_AutoBattleOpen_h1164514826", value, winreg.REG_DWORD)


def set_is_save_battle_speed_setting(value: bool) -> None:
    write_registry_value(winreg.HKEY_CURRENT_USER, get_registry_key_path(), "OtherSettings_IsSaveBattleSpeed_h3606297293", value, winreg.REG_DWORD)


def set_user_speed_up_open_setting(uid: str, value: bool) -> None:
    write_registry_value(winreg.HKEY_CURRENT_USER, get_registry_key_path(), f"User_{uid}_SpeedUpOpen_h3552997784", value, winreg.REG_DWORD)


def get_auto_battle_open_setting() -> Optional[bytes]:
    return read_registry_value(winreg.HKEY_CURRENT_USER, get_registry_key_path(), "OtherSettings_AutoBattleOpen_h1164514826")


def get_is_save_battle_speed_setting() -> Optional[bytes]:
    return read_registry_value(winreg.HKEY_CURRENT_USER, get_registry_key_path(), "OtherSettings_IsSaveBattleSpeed_h3606297293")


def get_user_speed_up_open_setting(uid: str) -> Optional[bytes]:
    return read_registry_value(winreg.HKEY_CURRENT_USER, get_registry_key_path(), f"User_{uid}_SpeedUpOpen_h3552997784")


def get_graphics_setting() -> Optional[bytes]:
    return read_registry_value(winreg.HKEY_CURRENT_USER, get_registry_key_path(), graphics_value_name)


def game_paths(*, skip_errors=False):
    """按原有优先级读取国服和国际服，向导可以继续查找下一条记录。"""
    for registry_path in (r"Software\miHoYo\HYP\1_1\hkrpg_cn", r"Software\Cognosphere\HYP\1_0\hkrpg_global"):
        try:
            install_path = read_registry_value(winreg.HKEY_CURRENT_USER, registry_path, "GameInstallPath")
        except OSError:
            if skip_errors:
                continue
            raise
        if install_path:
            executable = os.path.join(install_path, "StarRail.exe")
            if os.path.exists(executable):
                yield executable


def get_game_path() -> Optional[str]:
    return next(game_paths(), None)


def get_launcher_path() -> Optional[str]:
    """
    获取启动器路径函数，尝试从注册表中读取指定键值并验证启动器可执行文件是否存在。
    支持国服和国际服。

    Returns:
        Optional[str]: 如果找到有效的启动器路径，则返回完整路径，否则返回 None。
    """
    # 注册表键路径和键值名称（国服和国际服）
    registry_paths = [
        r"Software\miHoYo\HYP\1_1",     # 国服路径
        r"Software\Cognosphere\HYP\1_0"  # 国际服路径
    ]
    registry_value_name = "InstallPath"  # 启动器安装路径的键值名称

    # 尝试从不同的注册表路径中读取
    for registry_path in registry_paths:
        install_path = read_registry_value(
            winreg.HKEY_CURRENT_USER,  # 从当前用户的注册表路径中读取
            registry_path,             # 注册表的具体路径
            registry_value_name        # 需要读取的键值名称
        )

        # 如果成功读取到路径，检查对应的启动器可执行文件是否存在
        if install_path:
            launcher_executable = os.path.join(install_path, "launcher.exe")  # 构造完整的启动器可执行文件路径
            if os.path.exists(launcher_executable):  # 验证文件路径是否存在
                return launcher_executable  # 返回有效的启动器路径
    # 如果路径无效或文件不存在，返回 None
    return None


def parse_game_resolution(value: bytes | None) -> Optional[Tuple[int, int, bool]]:
    """解析已读取的游戏分辨率注册表数据。"""
    if value:
        data_dict = json.loads(value.decode('utf-8').strip('\x00'))
        # Convert keys to lower case to ensure case-insensitivity
        data_dict = {k.lower(): v for k, v in data_dict.items()}

        # Validate data format with case-insensitive keys
        if 'width' in data_dict and 'height' in data_dict and 'isfullscreen' in data_dict:
            if isinstance(data_dict['width'], int) and isinstance(data_dict['height'], int) and isinstance(data_dict['isfullscreen'], bool):
                return data_dict['width'], data_dict['height'], data_dict['isfullscreen']
            else:
                raise ValueError("Registry data is invalid: width, height, and isFullScreen must be of type int, int, and bool respectively.")
        else:
            raise ValueError("Registry data is missing required fields: width, height, or isFullScreen.")

    return None


def get_game_resolution() -> Optional[Tuple[int, int, bool]]:
    """读取当前选中游戏的分辨率和全屏设置。"""
    value = read_registry_value(winreg.HKEY_CURRENT_USER, get_registry_key_path(), resolution_value_name)
    return parse_game_resolution(value)


def set_game_resolution(width: int, height: int, is_fullscreen: bool, *, registry_path: str | None = None) -> None:
    """
    Set the resolution of the game and whether it should run in fullscreen mode.

    Parameters:
    - width: The width of the game window.
    - height: The height of the game window.
    - is_fullscreen: Whether the game should run in fullscreen mode.
    - registry_path: An already resolved game key. Defaults to the currently selected game.
    """
    data_dict = {
        'width': width,
        'height': height,
        'isFullScreen': is_fullscreen
    }
    data = (json.dumps(data_dict) + '\x00').encode('utf-8')
    if registry_path is None:
        registry_path = get_registry_key_path()
    write_registry_value(winreg.HKEY_CURRENT_USER, registry_path, resolution_value_name, data, winreg.REG_BINARY)


def get_game_fps() -> Optional[int]:
    """
    Return the game FPS settings from the registry value.

    This function does not take any parameters.
    """
    value = read_registry_value(winreg.HKEY_CURRENT_USER, get_registry_key_path(), graphics_value_name)
    if value:
        data_dict = json.loads(value.decode('utf-8').strip('\x00'))

        # Validate data format
        if 'FPS' in data_dict:
            if isinstance(data_dict['FPS'], int):
                return data_dict['FPS']
            else:
                raise ValueError("Registry data is invalid: FPS must be of type int.")
        else:
            return 60

    return None


def set_game_fps(fps: int) -> None:
    """
    Set the FPS of the game.

    Parameters:
    - fps
    """
    value = read_registry_value(winreg.HKEY_CURRENT_USER, get_registry_key_path(), graphics_value_name)
    if not value:
        raise MissingFPSSettingError("请将游戏图像质量修改为自定义后重试")
    data_dict = json.loads(value.decode('utf-8').strip('\x00'))
    if 'FPS' not in data_dict:
        raise MissingFPSSettingError("请将游戏图像质量修改为自定义后重试")
    data_dict['FPS'] = fps
    data = (json.dumps(data_dict) + '\x00').encode('utf-8')
    write_registry_value(winreg.HKEY_CURRENT_USER, get_registry_key_path(), graphics_value_name, data, winreg.REG_BINARY)


def read_registry_value(key, sub_key, value_name):
    """
    Read the content of the specified registry value.

    Parameters:
    - key: The handle of an open registry key.
    - sub_key: The name of the key, relative to key, to open.
    - value_name: The name of the value to query.

    Returns:
        The content of the specified value in the registry.
    """
    if sub_key is None:
        raise OSError("Registry key path not found. Please ensure the game is installed.")
    try:
        # Open the specified registry key
        registry_key = winreg.OpenKey(key, sub_key)
        try:
            value, _ = winreg.QueryValueEx(registry_key, value_name)
            return value
        finally:
            winreg.CloseKey(registry_key)
    except FileNotFoundError:
        # raise FileNotFoundError(f"Specified registry key or value not found: {sub_key}\\{value_name}")
        return None
    except Exception as e:
        raise OSError(f"Error reading registry value: {e}")


def write_registry_value(key, sub_key, value_name, data, mode) -> None:
    """
    Write a registry value to the specified registry key.

    Parameters:
    - key: The registry key.
    - sub_key: The subkey under the specified registry key.
    - value_name: The name of the registry value.
    - data: The data to be written to the registry.
    - mode: The type of data.
    """
    if sub_key is None:
        raise OSError("Registry key path not found. Please ensure the game is installed.")
    try:
        # Open or create the specified registry key
        registry_key = winreg.CreateKey(key, sub_key)
        try:
            winreg.SetValueEx(registry_key, value_name, 0, mode, data)
        finally:
            winreg.CloseKey(registry_key)
    except Exception as e:
        raise OSError(f"Error writing registry value: {e}")
