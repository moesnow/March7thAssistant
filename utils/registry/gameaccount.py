import subprocess
import sys
if sys.platform == 'win32':
    import winreg
import itertools

reg_path_cn = "Software\\miHoYo\\崩坏：星穹铁道"
reg_path_oversea = "Software\\Cognosphere\\Star Rail"
uid_key = "App_LastUserID_h2841727341"


def get_reg_path() -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path_cn):
            return reg_path_cn
    except FileNotFoundError:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path_oversea):
                return reg_path_oversea
        except FileNotFoundError:
            return None




def gamereg_uid() -> int | None:
    if sys.platform != "win32":
        return None
    current_path = get_reg_path()
    if current_path is None:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, current_path) as key:
            for i in itertools.count():
                name, value, type1 = winreg.EnumValue(key, i)
                if name == uid_key:
                    return value
    except FileNotFoundError:
        return None
    except OSError:
        # OSError: [WinError 259] 没有可用的数据了。
        return None


def _full_reg_path() -> str:
    if sys.platform != "win32":
        raise OSError("游戏注册表仅支持 Windows")
    path = get_reg_path()
    if path is None:
        raise FileNotFoundError("未找到游戏注册表，无法操作账号")
    return f"HKEY_CURRENT_USER\\{path}"


def _run_reg(*args: str) -> None:
    result = subprocess.run(["reg", *args], capture_output=True, text=True)
    if result.returncode:
        raise OSError(f"注册表操作失败（错误码 {result.returncode}）：{result.stderr.strip()}")


def gamereg_export(path: str) -> None:
    _run_reg("export", _full_reg_path(), path, "/y")


def gamereg_import(path: str) -> None:
    _run_reg("import", path)


def gamereg_delete_all() -> None:
    """删除游戏注册表中的账户信息。"""
    _run_reg("delete", _full_reg_path(), "/f")
