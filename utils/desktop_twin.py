"""桌面分身的会话归属检查和定向 GUI 启动。"""

import ctypes
import hashlib
import os
import sys
from ctypes import wintypes
from pathlib import Path
from subprocess import list2cmdline
from typing import NamedTuple
from uuid import uuid4

import psutil

from utils.runs import process_create_time
from utils.windows_session import SessionIdentity, child_session_id, process_session_id, session_info

SESSION_ARG = "--desktop-twin-session"
SESSION_ENV = "MARCH7TH_DESKTOP_TWIN"
_CONNECTION_MUTEX = r"Global\March7thAssistant_DesktopTwin"


class DesktopTwinError(RuntimeError):
    pass


def _mutex_name(session_id):
    return _CONNECTION_MUTEX if session_id is None else f"{_CONNECTION_MUTEX}_{session_id}"


def reserve_connection(session_id=None):
    """进程退出时由系统释放，防止两个小助手同时尝试认领子会话。"""
    import win32api
    import win32event

    handle = win32event.CreateMutex(None, False, _mutex_name(session_id))
    if win32api.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        handle.Close()
        raise DesktopTwinError("另一个小助手正在使用桌面分身")
    return handle


def connection_reserved(session_id=None):
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenMutexW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
    api.OpenMutexW.restype = wintypes.HANDLE
    api.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = api.OpenMutexW(0x00100000, False, _mutex_name(session_id))  # SYNCHRONIZE
    if handle:
        api.CloseHandle(handle)
        return True
    error = ctypes.get_last_error()
    if error == 2:  # ERROR_FILE_NOT_FOUND
        return False
    if error == 5:  # ERROR_ACCESS_DENIED：另一个账户已创建
        return True
    raise ctypes.WinError(error)


def in_desktop_twin():
    return bool(os.environ.get(SESSION_ENV))


def launcher_path():
    return os.path.abspath(sys.executable if getattr(sys, "frozen", False) else "app.py")


def launcher_server_key(session_id=None):
    """主 GUI 沿用安装路径的键，分身 GUI 追加 Windows 会话 ID。"""
    path_hash = hashlib.sha1(launcher_path().encode("utf-8")).hexdigest()
    key = f"March7thAssistant_{path_hash}"
    return key if session_id is None else f"{key}_{session_id}"


def _session_account(session_id):
    import win32ts

    user = win32ts.WTSQuerySessionInformation(None, session_id, win32ts.WTSUserName)
    domain = win32ts.WTSQuerySessionInformation(None, session_id, win32ts.WTSDomainName)
    if not user or not domain:
        raise DesktopTwinError("无法确认桌面会话的 Windows 账户")
    return f"{domain}\\{user}"


def check_parent_session():
    import win32security

    from utils.uac_free import current_user_sid

    parent_id = process_session_id()
    sid, _, _ = win32security.LookupAccountName(None, _session_account(parent_id))
    if win32security.ConvertSidToStringSid(sid) != current_user_sid():
        raise DesktopTwinError("请用当前桌面的登录账户启动小助手")


def check_child_available():
    existing = child_session_id()
    if existing is not None:
        raise DesktopTwinError(f"会话 {existing} 已占用桌面分身。请先注销该会话后重试")


def claim_child_session(started_at):
    """在 RDP 登录完成后，只认领此次连接后登录的同账户子会话。"""
    session_id = child_session_id()
    parent_id = process_session_id()
    if not session_id or session_id == parent_id:
        raise DesktopTwinError("无法确认独立的子会话")
    info = session_info(session_id)
    if not info.active or info.logon_time < started_at or not info.logon_time:
        raise DesktopTwinError("无法确认子会话由本次连接创建")
    if _session_account(session_id).casefold() != _session_account(parent_id).casefold():
        raise DesktopTwinError("分身与主桌面的登录账户不同")
    return info.identity


def owned_session_info(identity):
    """返回本次子会话的信息。消失或 ID 已复用时返回 None。"""
    if not identity.session_id or identity.session_id == process_session_id():
        return None
    if child_session_id() != identity.session_id:
        return None
    info = session_info(identity.session_id)
    return info if info.identity == identity else None


def logoff_owned_session(identity):
    import win32ts

    if owned_session_info(identity) is None:
        return False
    win32ts.WTSLogoffSession(None, identity.session_id, False)
    return True


def session_exists(identity):
    try:
        return session_info(identity.session_id).identity == identity
    except OSError as error:
        if getattr(error, "winerror", None) not in (2, 5, 1168, 7022):
            raise
        # 注销过程中详情可能暂时拒绝访问，确认会话已从列表移除后再收尾。
        import win32ts

        return any(entry["SessionId"] == identity.session_id
                   for entry in win32ts.WTSEnumerateSessions(None, 1, 0))


def check_game_config(config, session_id):
    if config.get_value("game_launch_method", "direct") != "direct":
        raise DesktopTwinError("桌面分身需要直接启动本地游戏")
    path = Path(config.get_value("game_path") or "")
    if not path.is_absolute() or path.suffix.lower() != ".exe" or not path.is_file():
        raise DesktopTwinError("请先在设置中填写本地游戏路径")
    for proc in psutil.process_iter(["name"]):
        if (proc.info["name"] or "").casefold() == path.name.casefold():
            try:
                if proc.is_running() and process_session_id(proc.pid) != session_id:
                    raise DesktopTwinError("请先关闭其他桌面会话中的游戏")
            except psutil.NoSuchProcess:
                continue


class SessionContext(NamedTuple):
    session: SessionIdentity
    host_pid: int
    host_create_time: float

    @classmethod
    def from_args(cls, args):
        session_id, logon_time, pid, create_time = args
        return cls(SessionIdentity(int(session_id), int(logon_time)), int(pid), float(create_time))

    @classmethod
    def from_environment(cls):
        value = os.environ.get(SESSION_ENV)
        return cls.from_args(value.split()) if value else None

    def as_args(self):
        return [str(self.session.session_id), str(self.session.logon_time),
                str(self.host_pid), str(self.host_create_time)]

    def check(self, *, require_active=True):
        if (not self.host_create_time or process_create_time(self.host_pid) != self.host_create_time
                or process_session_id(self.host_pid) == self.session.session_id):
            raise DesktopTwinError("桌面分身的控制窗口已退出或会话不符")
        if process_session_id() != self.session.session_id:
            raise DesktopTwinError("小助手未在指定的桌面分身内启动")
        info = session_info(self.session.session_id)
        if info.identity != self.session or (require_active and not info.active):
            raise DesktopTwinError("桌面分身已断开或会话身份已变化")
        return info


class ScheduledLauncher:
    """独占一个无触发器的任务和 RunEx 返回的运行实例。"""

    def __init__(self):
        self._task_name = f"M7A-DesktopTwin-{uuid4().hex}"
        self._root = None
        self._running = None

    def start(self, identity):
        import win32com.client

        from utils.schedule import apply_task_settings
        from utils.uac_free import current_user_sid

        info = owned_session_info(identity)
        if info is None or not info.active:
            raise DesktopTwinError("桌面分身已断开或会话身份已变化")
        service = win32com.client.Dispatch("Schedule.Service")
        service.Connect()
        root = service.GetFolder("\\")
        definition = service.NewTask(0)
        apply_task_settings(definition)
        sid = current_user_sid()
        definition.Principal.UserId = sid
        definition.Principal.LogonType = 3  # TASK_LOGON_INTERACTIVE_TOKEN
        definition.Principal.RunLevel = 1  # TASK_RUNLEVEL_HIGHEST
        definition.Settings.AllowDemandStart = True
        entry = launcher_path()
        if not Path(entry).is_file():
            raise DesktopTwinError("找不到小助手图形界面入口")
        pid = os.getpid()
        host_time = process_create_time(pid)
        if not host_time:
            raise DesktopTwinError("无法确认桌面分身的控制进程")
        context = SessionContext(identity, pid, host_time)
        program = sys.executable
        args = [] if getattr(sys, "frozen", False) else [entry]
        args += [SESSION_ARG, *context.as_args()]
        action = definition.Actions.Create(0)  # TASK_ACTION_EXEC
        action.Path = program
        action.Arguments = list2cmdline(args)
        action.WorkingDirectory = os.getcwd()
        # TASK_CREATE：只创建本次任务，不覆盖任何同名任务。
        task = root.RegisterTaskDefinition(self._task_name, definition, 2, sid, None, 3, None)
        self._root = root
        info = owned_session_info(identity)
        if info is None or not info.active:
            raise DesktopTwinError("桌面分身已断开或会话身份已变化")
        self._running = task.RunEx(None, 4, identity.session_id, "")  # TASK_RUN_USE_SESSION_ID

    def remove_registration(self):
        if self._root is not None:
            self._root.DeleteTask(self._task_name, 0)
            self._root = None

    def cancel_launch(self):
        if self._running is None:
            return
        import pywintypes

        try:
            self._running.Stop()
        except pywintypes.com_error as error:
            if (error.hresult & 0xFFFFFFFF) != 0x8004130B:  # SCHED_E_TASK_NOT_RUNNING
                raise
