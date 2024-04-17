import os
import winreg
import itertools

reg_path = "Software\\miHoYo\\崩坏：星穹铁道"
full_reg_path = f"HKEY_CURRENT_USER\\{reg_path}"
uid_key = "App_LastUserID_h2841727341"


def gamereg_uid() -> int | None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
        try:
            for i in itertools.count():
                name, value, type1 = winreg.EnumValue(key, i)
                if name == uid_key:
                    return value
        except OSError:
            # OSError: [WinError 259] 没有可用的数据了。
            pass


def gamereg_export(path: str) -> None:
   subcommand = f"reg export {full_reg_path} {path} /y"
   result = os.system(subcommand)


def gamereg_import(path: str) -> None:
    subcommand = f"reg import {path}"
    result = os.system(subcommand)

