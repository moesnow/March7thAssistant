"""静音本进程的音频会话。仅由 Windows 的桌面分身窗口加载。

分身里的声音由本进程中的 RDP 控件在本机播放，隐藏分身窗口时静音这些会话，
再次显示时恢复。直接调用 Windows Core Audio，不需要额外的依赖。
"""

import ctypes
import os
from ctypes import wintypes
from functools import cache
from uuid import UUID

import pythoncom  # noqa: F401  导入时为当前线程初始化 COM

_CLSID_MM_DEVICE_ENUMERATOR = UUID("BCDE0395-E52F-467C-8E3D-C4579291692E").bytes_le
_IID_MM_DEVICE_ENUMERATOR = UUID("A95664D2-9614-4F35-A746-DE8DB63617E6").bytes_le
_IID_AUDIO_SESSION_MANAGER2 = UUID("77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F").bytes_le
_IID_AUDIO_SESSION_CONTROL2 = UUID("BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D").bytes_le
_IID_SIMPLE_AUDIO_VOLUME = UUID("87CE5498-68D6-44E5-9215-6DA47EF883D8").bytes_le
_CLSCTX_ALL = 0x17
_E_RENDER = 0
_DEVICE_STATE_ACTIVE = 1


@cache
def _ole32():
    ole32 = ctypes.WinDLL("ole32")
    ole32.CoCreateInstance.argtypes = (ctypes.c_char_p, ctypes.c_void_p, wintypes.DWORD, ctypes.c_char_p,
                                       ctypes.POINTER(ctypes.c_void_p))
    ole32.CoCreateInstance.restype = ctypes.c_long
    ole32.CoTaskMemFree.argtypes = (ctypes.c_void_p,)
    ole32.CoTaskMemFree.restype = None
    return ole32


def _method(pointer, index, *arg_types):
    vtable = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    return ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *arg_types)(vtable[index])


def _check(hr):
    if hr < 0:
        raise ctypes.WinError(hr)
    return hr


def _release(pointer):
    if pointer:
        vtable = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[2])(pointer)


def _query(pointer, iid):
    result = ctypes.c_void_p()
    hr = _method(pointer, 0, ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p))(pointer, iid, ctypes.byref(result))
    return result if hr >= 0 and result else None


class _SimpleVolume:
    """ISimpleAudioVolume：3 SetMasterVolume, 4 GetMasterVolume, 5 SetMute, 6 GetMute。"""

    def __init__(self, pointer):
        self._pointer = pointer

    def muted(self):
        value = wintypes.BOOL()
        _check(_method(self._pointer, 6, ctypes.POINTER(wintypes.BOOL))(self._pointer, ctypes.byref(value)))
        return bool(value.value)

    def set_muted(self, muted):
        _check(_method(self._pointer, 5, wintypes.BOOL, ctypes.c_void_p)(self._pointer, bool(muted), None))


def _visit_session(control, pid, visit):
    control2 = _query(control, _IID_AUDIO_SESSION_CONTROL2)
    if control2 is None:
        return
    try:
        # IAudioSessionControl2：13 GetSessionInstanceIdentifier, 14 GetProcessId。
        # 跨进程会话返回成功码 AUDCLNT_S_NO_SINGLE_PROCESS，进程号不会等于本进程。
        process = wintypes.DWORD()
        if _method(control2, 14, ctypes.POINTER(wintypes.DWORD))(control2, ctypes.byref(process)) < 0:
            return
        if process.value != pid:
            return
        text = ctypes.c_void_p()
        _check(_method(control2, 13, ctypes.POINTER(ctypes.c_void_p))(control2, ctypes.byref(text)))
        try:
            instance = ctypes.wstring_at(text.value)
        finally:
            _ole32().CoTaskMemFree(text)
        volume = _query(control, _IID_SIMPLE_AUDIO_VOLUME)
        if volume is None:
            return
        try:
            visit(instance, _SimpleVolume(volume))
        finally:
            _release(volume)
    finally:
        _release(control2)


def _visit_device(device, pid, visit):
    manager = ctypes.c_void_p()
    # IMMDevice::Activate
    activate = _method(device, 3, ctypes.c_char_p, wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
    if activate(device, _IID_AUDIO_SESSION_MANAGER2, _CLSCTX_ALL, None, ctypes.byref(manager)) < 0:
        return
    try:
        sessions = ctypes.c_void_p()
        # IAudioSessionManager2::GetSessionEnumerator
        if _method(manager, 5, ctypes.POINTER(ctypes.c_void_p))(manager, ctypes.byref(sessions)) < 0:
            return
        try:
            count = ctypes.c_int()
            _check(_method(sessions, 3, ctypes.POINTER(ctypes.c_int))(sessions, ctypes.byref(count)))
            get_session = _method(sessions, 4, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))
            for index in range(count.value):
                control = ctypes.c_void_p()
                if get_session(sessions, index, ctypes.byref(control)) < 0:
                    continue
                try:
                    _visit_session(control, pid, visit)
                finally:
                    _release(control)
        finally:
            _release(sessions)
    finally:
        _release(manager)


def visit_process_sessions(pid, visit):
    """对 pid 在所有可用播放设备上的音频会话调用 visit(会话实例 ID, 音量)。"""
    enumerator = ctypes.c_void_p()
    _check(_ole32().CoCreateInstance(_CLSID_MM_DEVICE_ENUMERATOR, None, _CLSCTX_ALL, _IID_MM_DEVICE_ENUMERATOR,
                                     ctypes.byref(enumerator)))
    try:
        devices = ctypes.c_void_p()
        # IMMDeviceEnumerator::EnumAudioEndpoints
        enum_endpoints = _method(enumerator, 3, ctypes.c_int, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p))
        _check(enum_endpoints(enumerator, _E_RENDER, _DEVICE_STATE_ACTIVE, ctypes.byref(devices)))
        try:
            count = wintypes.UINT()
            _check(_method(devices, 3, ctypes.POINTER(wintypes.UINT))(devices, ctypes.byref(count)))
            item = _method(devices, 4, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p))
            for index in range(count.value):
                device = ctypes.c_void_p()
                if item(devices, index, ctypes.byref(device)) < 0:
                    continue
                try:
                    _visit_device(device, pid, visit)
                finally:
                    _release(device)
        finally:
            _release(devices)
    finally:
        _release(enumerator)


class ProcessAudioMuter:
    """静音一个进程的音频会话，并记住每个会话原来的状态。

    重复调用 mute() 只处理新出现的会话，用户在音量合成器里手动取消的静音不会被改回；
    restore() 只恢复由这里静音过的会话。

    Windows 会按程序记住会话的静音状态并带到下次启动。静音期间进程被结束时来不及恢复，
    所以静音时写入 marker 文件、恢复后删除；启动时文件还在就标记为 stale，
    由 clear_stale() 解除遗留的静音。
    """

    def __init__(self, pid=None, visit_sessions=visit_process_sessions, marker=None):
        self._pid = os.getpid() if pid is None else pid
        self._visit = visit_sessions
        self._marker = marker
        self._saved = {}
        self.muting = False
        self.stale = bool(marker and os.path.exists(marker))

    def mute(self):
        if not self.muting:
            self._write_marker()
        self.muting = True

        def apply(instance, volume):
            if instance not in self._saved:
                # 遗留的静音不是用户的选择，恢复时按未静音处理
                self._saved[instance] = False if self.stale else volume.muted()
                volume.set_muted(True)

        self._visit(self._pid, apply)

    def restore(self):
        self.muting = False
        saved, self._saved = self._saved, {}
        if saved:
            def apply(instance, volume):
                if instance in saved:
                    volume.set_muted(saved.pop(instance))

            try:
                self._visit(self._pid, apply)
            except Exception:
                self._saved = saved
                raise
            self.stale = False
        if not self.stale:
            self._remove_marker()

    def clear_stale(self):
        """解除上次异常退出遗留的静音。会话要等程序开始播放声音才出现，找到会话才算完成。"""
        if not self.stale or self.muting:
            return
        found = []

        def apply(instance, volume):
            found.append(instance)
            if volume.muted():
                volume.set_muted(False)

        self._visit(self._pid, apply)
        if found:
            self.stale = False
            self._remove_marker()

    def _write_marker(self):
        if self._marker:
            os.makedirs(os.path.dirname(self._marker) or ".", exist_ok=True)
            with open(self._marker, "w", encoding="utf-8") as stream:
                stream.write(str(self._pid))

    def _remove_marker(self):
        if self._marker:
            try:
                os.remove(self._marker)
            except FileNotFoundError:
                pass
