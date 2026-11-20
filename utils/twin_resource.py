"""桌面分身的资源调节：进程优先级与空闲时最小化游戏窗口。

分身里的游戏和任务进程与主桌面共享同一台机器。把它们的 CPU 优先级降到
低于正常，可以让主桌面在前台更流畅；代价是分身内的自动化会略慢。
"""
import sys


def _psutil():
    import psutil
    return psutil


def lower_process_priority(pid=None):
    """把指定进程（默认当前进程）降到低于正常优先级；失败返回 False。"""
    try:
        process = _psutil().Process(pid)
        process.nice(_psutil().BELOW_NORMAL_PRIORITY_CLASS)
        return True
    except Exception:
        return False


def lower_current_process_priority():
    """把当前进程降到低于正常优先级。"""
    return lower_process_priority()


def lower_game_process_priority(process_name, session_id=None):
    """把当前 Windows 会话内所有同名游戏进程降到低于正常优先级。

    返回实际调整的进程数；找不到进程或系统不支持时返回 0。
    """
    if not process_name or sys.platform != "win32":
        return 0
    try:
        from utils.windows_session import process_session_id
        if session_id is None:
            session_id = process_session_id()
        psutil = _psutil()
        lowered = 0
        for process in psutil.process_iter(["pid", "name"]):
            try:
                name = process.info.get("name") or ""
                if process_name.lower() not in name.lower():
                    continue
                if process_session_id(process.info["pid"]) != session_id:
                    continue
                process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                lowered += 1
            except Exception:
                continue
        return lowered
    except Exception:
        return 0


def _find_window(title):
    """按标题精确匹配一个可见窗口；找不到返回 None。"""
    import win32gui

    matches = []

    def callback(hwnd, _):
        try:
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd) == title:
                matches.append(hwnd)
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(callback, None)
    except Exception:
        return None
    return matches[0] if matches else None


def minimize_game_window(title):
    """最小化标题匹配的游戏窗口；成功返回 True。"""
    if not title or sys.platform != "win32":
        return False
    hwnd = _find_window(title)
    if hwnd is None:
        return False
    try:
        import win32con
        import win32gui
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        return True
    except Exception:
        return False


def restore_game_window(title):
    """还原标题匹配的游戏窗口并尝试置前；成功返回 True。"""
    if not title or sys.platform != "win32":
        return False
    hwnd = _find_window(title)
    if hwnd is None:
        return False
    try:
        import win32con
        import win32gui
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        return True
    except Exception:
        return False
