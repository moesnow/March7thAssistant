"""一次游戏任务持有的 Windows 系统电源请求。"""
import ctypes
from ctypes import wintypes
from functools import cache
import sys


_CONTEXT_VERSION = 0
_SIMPLE_STRING = 1
_SYSTEM_REQUIRED = 1
_INVALID_HANDLE = ctypes.c_void_p(-1).value


class _DetailedReason(ctypes.Structure):
    _fields_ = [
        ("module", wintypes.HMODULE),
        ("id", wintypes.ULONG),
        ("count", wintypes.ULONG),
        ("strings", ctypes.POINTER(wintypes.LPWSTR)),
    ]


class _Reason(ctypes.Union):
    _fields_ = [("simple", wintypes.LPWSTR), ("detailed", _DetailedReason)]


class _ReasonContext(ctypes.Structure):
    _fields_ = [("version", wintypes.ULONG), ("flags", wintypes.DWORD), ("reason", _Reason)]


@cache
def _kernel32():
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.PowerCreateRequest.argtypes = (ctypes.POINTER(_ReasonContext),)
    api.PowerCreateRequest.restype = wintypes.HANDLE
    api.PowerSetRequest.argtypes = api.PowerClearRequest.argtypes = (wintypes.HANDLE, ctypes.c_int)
    api.PowerSetRequest.restype = api.PowerClearRequest.restype = wintypes.BOOL
    api.CloseHandle.argtypes = (wintypes.HANDLE,)
    api.CloseHandle.restype = wintypes.BOOL
    return api


class WindowsSystemPowerRequest:
    def __init__(self):
        self._request = None

    def acquire(self, log):
        if sys.platform != "win32" or self._request is not None:
            return
        try:
            api = _kernel32()
            context = _ReasonContext(_CONTEXT_VERSION, _SIMPLE_STRING, _Reason(simple="三月七助手正在执行游戏任务"))
            handle = api.PowerCreateRequest(ctypes.byref(context))
            if handle in (None, _INVALID_HANDLE):
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                if not api.PowerSetRequest(handle, _SYSTEM_REQUIRED):
                    raise ctypes.WinError(ctypes.get_last_error())
                self._request = api, handle
            except BaseException:
                api.CloseHandle(handle)
                raise
        except (AttributeError, OSError) as error:
            log.warning(f"未能申请 Windows 防自动睡眠：{error}")
        else:
            log.info("已申请 Windows 防自动睡眠")

    def release(self, log):
        request, self._request = self._request, None
        if request is None:
            return
        api, handle = request
        try:
            if not api.PowerClearRequest(handle, _SYSTEM_REQUIRED):
                log.warning(f"未能清除 Windows 电源请求：{ctypes.WinError(ctypes.get_last_error())}")
        finally:
            if api.CloseHandle(handle):
                log.info("已释放 Windows 电源请求")
            else:
                log.warning(f"未能关闭 Windows 电源请求句柄：{ctypes.WinError(ctypes.get_last_error())}")


# GUI 启动的任务也在独立的 CLI 进程执行，每轮最多持有一份请求。
task_power_request = WindowsSystemPowerRequest()
