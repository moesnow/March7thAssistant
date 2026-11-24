"""已选本地客户端的账号注册表。所有系统操作由上层显式发起。"""
import subprocess
import sys

if sys.platform == "win32":
    import winreg

reg_path_cn = r"Software\miHoYo\崩坏：星穹铁道"
reg_path_oversea = r"Software\Cognosphere\Star Rail"
uid_key = "App_LastUserID_h2841727341"


def get_reg_path(game_path=None):
    if sys.platform != "win32":
        return None
    from utils.registry.star_rail_setting import get_registry_key_path, registry_path_for_game
    return get_registry_key_path() if game_path is None else registry_path_for_game(game_path)


def server_for_path(game_path):
    path = get_reg_path(game_path)
    if path:
        return {reg_path_cn.casefold(): "cn", reg_path_oversea.casefold(): "global"}.get(path.casefold())
    return None


def gamereg_uid(game_path=None):
    path = get_reg_path(game_path)
    if not path:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            value, _ = winreg.QueryValueEx(key, uid_key)
            return int(value) if str(value).isascii() and str(value).isdigit() else None
    except FileNotFoundError:
        return None


def _full_reg_path(game_path=None):
    path = get_reg_path(game_path)
    if path is None:
        raise FileNotFoundError("未找到游戏注册表，无法操作账号")
    return "HKEY_CURRENT_USER\\" + path


def _run_reg(*args):
    result = subprocess.run(["reg", *args], capture_output=True, text=True, errors="replace", timeout=15)
    if result.returncode:
        raise OSError(f"注册表操作失败（错误码 {result.returncode}）：{result.stderr.strip()}")


def gamereg_export(path, game_path=None):
    _run_reg("export", _full_reg_path(game_path), path, "/y")


def gamereg_import(path):
    _run_reg("import", path)


def gamereg_delete_all(game_path=None):
    _run_reg("delete", _full_reg_path(game_path), "/f")


def local_settings(game_path):
    from utils.registry.star_rail_setting import graphics_value_name, resolution_value_name, _HOTKEY_VALUE_NAMES
    from utils.temporary_graphics import QUALITY, VERSION
    values = {}
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, get_reg_path(game_path)) as key:
        for name in (graphics_value_name, resolution_value_name, QUALITY, VERSION, *_HOTKEY_VALUE_NAMES.values()):
            try:
                values[name] = winreg.QueryValueEx(key, name)
            except FileNotFoundError:
                continue
    return values


def restore_settings(game_path, values):
    if not values:
        return
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, get_reg_path(game_path), 0, winreg.KEY_SET_VALUE) as key:
        for name, (value, kind) in values.items():
            winreg.SetValueEx(key, name, 0, kind, value)
