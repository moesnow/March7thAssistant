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


if sys.platform == 'win32':
    reg_path = get_reg_path()
    if reg_path is not None:
        full_reg_path = "HKEY_CURRENT_USER\\{0}".format(reg_path.replace('\\\\', '\\'))
    else:
        full_reg_path = None
else:
    reg_path = None
    full_reg_path = None


def gamereg_uid() -> int | None:
    if reg_path is None:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
            for i in itertools.count():
                name, value, type1 = winreg.EnumValue(key, i)
                if name == uid_key:
                    return value
    except FileNotFoundError:
        return None
    except OSError:
        # OSError: [WinError 259] 没有可用的数据了。
        return None


def gamereg_export(path: str) -> None:
    if full_reg_path is not None:
        result = subprocess.run(['reg', 'export', full_reg_path, path, '/y'], check=False)


def gamereg_import(path: str) -> None:
    result = subprocess.run(['reg', 'import', path], check=False)


def gamereg_delete_all() -> None:
    """
    删除注册表中的所有账户信息
    """
    if full_reg_path is None:
        return
    result = subprocess.run(['reg', 'delete', full_reg_path, '/f'], check=False)
    if result.returncode != 0:
        raise Exception(f"Failed to delete registry key: {full_reg_path}. Error code: {result.returncode}")
