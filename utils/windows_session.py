"""Windows 会话身份查询。Session ID 可以复用，不能单独作为注销凭据。"""

import ctypes
import os
from ctypes import wintypes
from functools import cache
from typing import NamedTuple


class SessionIdentity(NamedTuple):
    session_id: int
    logon_time: int


class _WtsInfo(ctypes.Structure):
    # WTSINFOW，见 Windows SDK 的 wtsapi32.h。
    _fields_ = [
        ("state", ctypes.c_int),
        ("session_id", wintypes.DWORD),
        ("traffic_counters", wintypes.DWORD * 6),
        ("station", ctypes.c_wchar * 32),
        ("domain", ctypes.c_wchar * 17),
        ("user", ctypes.c_wchar * 21),
        ("connect_time", ctypes.c_int64),
        ("disconnect_time", ctypes.c_int64),
        ("last_input_time", ctypes.c_int64),
        ("logon_time", ctypes.c_int64),
        ("current_time", ctypes.c_int64),
    ]

    @property
    def identity(self):
        return SessionIdentity(self.session_id, self.logon_time)

    @property
    def active(self):
        return self.state == 0  # WTSActive


@cache
def _wts():
    api = ctypes.WinDLL("wtsapi32", use_last_error=True)
    api.WTSQuerySessionInformationW.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, ctypes.c_int,
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.DWORD),
    )
    api.WTSFreeMemory.argtypes = (ctypes.c_void_p,)
    api.WTSFreeMemory.restype = None
    return api


def process_session_id(pid=None):
    import win32ts

    return win32ts.ProcessIdToSessionId(os.getpid() if pid is None else pid)


def session_info(session_id):
    api = _wts()
    buffer = ctypes.c_void_p()
    size = wintypes.DWORD()
    # 24 = WTSSessionInfo
    if not api.WTSQuerySessionInformationW(None, session_id, 24, ctypes.byref(buffer), ctypes.byref(size)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if size.value < ctypes.sizeof(_WtsInfo):
            raise RuntimeError("Windows 返回的会话信息不完整")
        return _WtsInfo.from_buffer_copy(ctypes.string_at(buffer, ctypes.sizeof(_WtsInfo)))
    finally:
        api.WTSFreeMemory(buffer)


def child_session_id():
    session_id = wintypes.DWORD(0xFFFFFFFF)
    if not _wts().WTSGetChildSessionId(ctypes.byref(session_id)):
        error = ctypes.get_last_error()
        if error != 1168:  # ERROR_NOT_FOUND，在没有子会话时可返回 FALSE
            raise ctypes.WinError(error)
    return None if session_id.value == 0xFFFFFFFF else session_id.value


def child_sessions_enabled():
    enabled = wintypes.BOOL()
    if not _wts().WTSIsChildSessionsEnabled(ctypes.byref(enabled)):
        raise ctypes.WinError(ctypes.get_last_error())
    return bool(enabled.value)


def enable_child_sessions():
    if not _wts().WTSEnableChildSessions(True):
        raise ctypes.WinError(ctypes.get_last_error())
