import os
import sys
from subprocess import list2cmdline


# ShowWindow 常量（ShellExecuteEx 的 nShow）
SW_SHOWNORMAL = 1
SW_SHOWMINNOACTIVE = 7

# 用户在 UAC 弹窗中选择「否」时 ShellExecuteEx 返回的错误码（ERROR_CANCELLED）
ERROR_CANCELLED = 1223


def is_user_admin() -> bool:
    """
    检查当前进程是否以管理员权限（或 root）运行。

    :return: 权限已提升时返回 True。
    """
    if sys.platform != 'win32':
        return os.getuid() == 0
    import ctypes
    return ctypes.windll.shell32.IsUserAnAdmin() != 0


def current_command_line() -> list:
    """当前进程的完整命令行：[程序, 参数...]。

    源码运行时为 [python.exe, main.py, 参数...]；打包后 sys.argv[0] 就是 exe 本身，
    不能再拼在 sys.executable 后面，否则提权后的进程会把 exe 路径当成第一个参数。
    """
    if getattr(sys, 'frozen', False):
        return [sys.executable] + sys.argv[1:]
    return [sys.executable] + sys.argv


class ElevatedProcess:
    """ShellExecuteEx 启动的提权进程句柄（只能等待与读取退出码，无法读取其输出）。"""

    def __init__(self, handle):
        import ctypes
        from ctypes import wintypes
        self._handle = handle or None
        self._exit_code = None
        self.pid = None
        if self._handle is not None:
            self.pid = ctypes.windll.kernel32.GetProcessId(wintypes.HANDLE(self._handle)) or None

    def poll(self, timeout: float = 0):
        """等待最多 timeout 秒；进程已退出时返回退出码，否则返回 None。"""
        if self._exit_code is not None:
            return self._exit_code
        if self._handle is None:
            # 系统未返回进程句柄（极少见），无法跟踪，视为已结束
            return 0
        import ctypes
        from ctypes import wintypes
        wait_object_0 = 0
        kernel32 = ctypes.windll.kernel32
        result = kernel32.WaitForSingleObject(wintypes.HANDLE(self._handle), max(0, int(timeout * 1000)))
        if result != wait_object_0:
            return None
        exit_code = wintypes.DWORD()
        kernel32.GetExitCodeProcess(wintypes.HANDLE(self._handle), ctypes.byref(exit_code))
        self._exit_code = exit_code.value
        self.close()
        return self._exit_code

    def wait(self):
        """阻塞直到进程退出，返回退出码。"""
        while True:
            code = self.poll(3600)
            if code is not None:
                return code

    def close(self):
        if self._handle is not None:
            import ctypes
            from ctypes import wintypes
            ctypes.windll.kernel32.CloseHandle(wintypes.HANDLE(self._handle))
            self._handle = None


def start_as_admin(cmd_line=None, show_cmd: int = SW_SHOWNORMAL, cwd: str = None) -> ElevatedProcess:
    """
    以管理员权限启动程序（触发 UAC 提权），立即返回进程句柄。

    :param cmd_line: 可选，自定义命令行，格式为 [命令, 参数1, 参数2...]，默认使用当前进程的命令行。
    :param show_cmd: 新窗口的显示方式（ShowWindow 常量），默认正常显示。
    :param cwd: 新进程的工作目录，默认继承当前目录。
    :return: ElevatedProcess。
    :raises ValueError: cmd_line 不是列表或元组时抛出。
    :raises RuntimeError: 在非 Windows 平台调用时抛出。
    :raises OSError: 启动失败；用户在 UAC 弹窗中取消时 winerror 为 ERROR_CANCELLED。
    """
    if not cmd_line:
        cmd_line = current_command_line()
    elif not isinstance(cmd_line, (list, tuple)):
        raise ValueError("cmd_line 必须是序列")

    if sys.platform != 'win32':
        raise RuntimeError("run_as_admin 仅支持 Windows 平台")

    import ctypes
    from ctypes import wintypes

    see_mask_nocloseprocess = 0x00000040

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
    execute_info.lpDirectory = cwd
    execute_info.nShow = show_cmd

    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(execute_info)):
        raise ctypes.WinError()

    return ElevatedProcess(execute_info.hProcess)


def run_as_admin(cmd_line=None, wait: bool = True):
    """
    以管理员权限重新启动程序（触发 UAC 提权）。

    默认使用与当前进程相同的命令行（见 current_command_line）。

    :param cmd_line: 可选，自定义命令行，格式为 [命令, 参数1, 参数2...]，首元素通常是解释器路径。
    :param wait: 是否等待提权进程结束，默认为 True。
    :return: wait 为 True 时返回提权进程的退出码，否则返回 None。
    :raises ValueError: cmd_line 不是列表或元组时抛出。
    :raises RuntimeError: 在非 Windows 平台调用时抛出。
    """
    process = start_as_admin(cmd_line)
    if not wait:
        process.close()
        return None
    return process.wait()
