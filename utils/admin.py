import os
import sys
from subprocess import list2cmdline


def is_user_admin() -> bool:
    """
    检查当前进程是否以管理员权限（或 root）运行。

    :return: 权限已提升时返回 True。
    """
    if sys.platform != 'win32':
        return os.getuid() == 0
    import ctypes
    return ctypes.windll.shell32.IsUserAnAdmin() != 0


def run_as_admin(cmd_line=None, wait: bool = True):
    """
    以管理员权限重新启动程序（触发 UAC 提权）。

    默认使用与当前进程相同的命令行：[sys.executable] + sys.argv。

    :param cmd_line: 可选，自定义命令行，格式为 [命令, 参数1, 参数2...]，首元素通常是解释器路径。
    :param wait: 是否等待提权进程结束，默认为 True。
    :return: wait 为 True 时返回提权进程的退出码，否则返回 None。
    :raises ValueError: cmd_line 不是列表或元组时抛出。
    :raises RuntimeError: 在非 Windows 平台调用时抛出。
    """
    if not cmd_line:
        cmd_line = [sys.executable] + sys.argv
    elif not isinstance(cmd_line, (list, tuple)):
        raise ValueError("cmd_line 必须是序列")

    if sys.platform != 'win32':
        raise RuntimeError("run_as_admin 仅支持 Windows 平台")

    import ctypes
    from ctypes import wintypes

    see_mask_nocloseprocess = 0x00000040
    sw_shownormal = 1
    infinite = 0xFFFFFFFF

    class ShellExecuteInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", ctypes.c_ulong),
            ("hwnd", wintypes.HWND),
            ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR),
            ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR),
            ("nShow", ctypes.c_int),
            ("hInstApp", wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", wintypes.LPCWSTR),
            ("hKeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD),
            ("hIcon", wintypes.HANDLE),
            ("hProcess", wintypes.HANDLE),
        ]

    execute_info = ShellExecuteInfo()
    execute_info.cbSize = ctypes.sizeof(ShellExecuteInfo)
    execute_info.fMask = see_mask_nocloseprocess
    execute_info.lpVerb = "runas"  # 触发 UAC 提权提示
    execute_info.lpFile = cmd_line[0]
    execute_info.lpParameters = list2cmdline(list(cmd_line[1:]))
    execute_info.nShow = sw_shownormal

    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(execute_info)):
        raise ctypes.WinError()

    if not wait:
        return None

    handle = execute_info.hProcess
    try:
        ctypes.windll.kernel32.WaitForSingleObject(handle, infinite)
        exit_code = wintypes.DWORD()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        return exit_code.value
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)
