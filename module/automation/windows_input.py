"""Windows 接口边界。构造时才导入 Windows 依赖，测试使用替身，不访问游戏。"""
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
import threading
import time


class _MouseEvent(ctypes.Structure):
    _fields_ = [('point', wintypes.POINT), ('data', wintypes.DWORD),
                ('flags', wintypes.DWORD), ('time', wintypes.DWORD), ('extra', ctypes.c_size_t)]


class MouseProtection:
    """只保护鼠标的短时租约；消息线程负责挂钩和解钩，不影响键盘。"""

    def __init__(self, api, timeout=2, on_expire=None):
        self.api, self.on_expire = api, on_expire
        self.timeout = min(2.0, max(.05, float(timeout)))
        self._stop, self._ready, self._done = threading.Event(), threading.Event(), threading.Event()
        self._active = threading.Event()
        self._error = None
        self._expected = None
        self._thread = threading.Thread(target=self._run, name='M7AMouseProtection', daemon=True)
        self._thread.start()
        if not self._ready.wait(2) or self._error or not self.active:
            self.close()
            raise RuntimeError('无法建立鼠标保护') from self._error

    @property
    def active(self):
        return self._active.is_set() and not self._stop.is_set()

    def allow_move(self, point):
        self._expected = tuple(point)

    def close(self):
        self._stop.set()
        # 到期回调可能正在等待输入后端的锁；只等原生钩子移除，不在这里 join 回调。
        if self._thread is not threading.current_thread():
            if not self._done.wait(1):
                raise RuntimeError('鼠标保护尚未释放')
        if getattr(self.api, '_mouse_protection', None) is self:
            self.api._mouse_protection = None

    def _run(self):
        user32 = self.api.user32
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user32.SetWindowsHookExW.argtypes = (ctypes.c_int, callback_type, wintypes.HINSTANCE, wintypes.DWORD)
        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        user32.CallNextHookEx.argtypes = (wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user32.CallNextHookEx.restype = ctypes.c_ssize_t
        user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        blocked = set()
        release = {0x201:0x202, 0x204:0x205, 0x207:0x208, 0x20b:0x20c}
        hook = None
        deadline = float('inf')
        expired = False

        @callback_type
        def changed(code, message, data):
            if code >= 0 and self.active and time.monotonic() < deadline:
                event = ctypes.cast(data, ctypes.POINTER(_MouseEvent)).contents
                injected = bool(event.flags & 1)  # LLMHF_INJECTED
                own_move = message == 0x200 and (event.point.x, event.point.y) == self._expected
                if not injected and not own_move:
                    button = event.data >> 16 if message in (0x20b,0x20c) else 0
                    if message in release:
                        blocked.add((release[message], button))
                        return 1
                    if message in release.values():
                        if (message, button) in blocked:
                            blocked.remove((message, button))
                            return 1
                        # 挂钩建立前已按下的物理鼠标必须能释放，避免前台留下按住状态。
                    elif message in (0x200,0x20a,0x20e):
                        return 1
            return user32.CallNextHookEx(None, code, message, data)

        try:
            self.api.gui.PumpWaitingMessages()
            hook = user32.SetWindowsHookExW(14, changed, self.api.api.GetModuleHandle(None), 0)
            if not hook:
                raise ctypes.WinError(ctypes.get_last_error())
            deadline = time.monotonic() + self.timeout
            self._active.set()
            self._ready.set()
            while not self._stop.wait(.005):
                self.api.gui.PumpWaitingMessages()
                if time.monotonic() >= deadline:
                    expired = True
                    break
        except BaseException as error:
            self._error = error
        finally:
            self._active.clear()
            try:
                if hook and not user32.UnhookWindowsHookEx(hook):
                    self._error = ctypes.WinError(ctypes.get_last_error())
            except BaseException as error:
                self._error = error
            finally:
                self._ready.set()
                self._done.set()
        if (expired or self._error is not None) and self.on_expire:
            self.on_expire(self)


@dataclass(frozen=True)
class WindowIdentity:
    hwnd: int
    pid: int
    started: float


class ForegroundWatch:
    """记录滚轮回退期间的焦点让渡，切走后再切回也不恢复旧窗口。"""

    def __init__(self, api, hwnd):
        self.api, self.hwnd = api, hwnd
        self._lost = threading.Event()
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._error = None
        self._armed = False
        self._expected_foreground = hwnd
        self.focus_requested = None
        self._flush = threading.Event()
        self._flushed = threading.Event()
        self._thread = threading.Thread(target=self._run, name='M7AForegroundWatch', daemon=True)
        self._thread.start()
        if not self._ready.wait(2) or self._error:
            self.close()
            raise RuntimeError('无法监测前台窗口变化，滚轮操作已取消') from self._error

    def _run(self):
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
                                          wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)
        user32.SetWinEventHook.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE,
                                           callback_type, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD)
        user32.SetWinEventHook.restype = wintypes.HANDLE
        user32.UnhookWinEvent.argtypes = (wintypes.HANDLE,)
        hook = None

        @callback_type
        def changed(_hook, _event, window, *_args):
            if window and window not in (self.hwnd, self._expected_foreground):
                self._lost.set()

        try:
            # EVENT_SYSTEM_FOREGROUND, WINEVENT_OUTOFCONTEXT：无进程注入。
            hook = user32.SetWinEventHook(3, 3, None, changed, 0, 0, 0)
            if not hook:
                raise ctypes.WinError(ctypes.get_last_error())
            self._ready.set()
            while not self._stop.wait(.005):
                self.api.gui.PumpWaitingMessages()
                current = self.api.foreground()
                if self._armed and current and current not in (self.hwnd, self._expected_foreground):
                    self._lost.set()
                if self._flush.is_set():
                    self._flush.clear()
                    self._flushed.set()
            self.api.gui.PumpWaitingMessages()
        except BaseException as error:
            self._error = error
            self._lost.set()
        finally:
            if hook:
                user32.UnhookWinEvent(hook)
            self._ready.set()

    def arm(self):
        self._armed = True

    def expect_foreground(self, hwnd):
        # 仅放行本次主动发起的切换；已经观察到的用户切换始终保留。
        self._expected_foreground = hwnd

    def sync(self):
        self._flushed.clear()
        self._flush.set()
        if not self._flushed.wait(.2):
            self._lost.set()

    @property
    def lost(self):
        return self._lost.is_set()

    def close(self):
        self._stop.set()
        self._thread.join(timeout=2)


class WindowsInputApi:
    def __init__(self):
        import win32api
        import win32gui
        import win32process
        import psutil
        self.api, self.gui, self.process, self.psutil = win32api, win32gui, win32process, psutil
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self.user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        self.user32.PostMessageW.restype = wintypes.BOOL
        self.user32.SendMessageTimeoutW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
            wintypes.LPARAM, wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t))
        self.user32.SendMessageTimeoutW.restype = wintypes.LPARAM
        self.user32.GetClipCursor.argtypes = (ctypes.POINTER(wintypes.RECT),)
        self.user32.GetClipCursor.restype = wintypes.BOOL

    def identity(self, hwnd):
        if not hwnd or not self.gui.IsWindow(hwnd):
            return None
        try:
            pid = self.process.GetWindowThreadProcessId(hwnd)[1]
            return WindowIdentity(hwnd, pid, self.psutil.Process(pid).create_time())
        except Exception:
            return None

    def resolve(self, title, process_name):
        hwnd = self.gui.FindWindow('UnityWndClass', title)
        identity = self.identity(hwnd)
        if identity and Path(self.psutil.Process(identity.pid).name()).stem.casefold() == Path(process_name).stem.casefold():
            return identity
        raise RuntimeError('未找到匹配的游戏窗口')

    def usable(self, window):
        return (window is not None and self.identity(window.hwnd) == window
                and self.gui.IsWindowVisible(window.hwnd) and not self.gui.IsIconic(window.hwnd)
                and all(value > 0 for value in self.size(window)))

    def size(self, window):
        _, _, width, height = self.gui.GetClientRect(window.hwnd)
        return width, height

    def foreground(self):
        return self.gui.GetForegroundWindow()

    def focus(self, window, expected, watch=None):
        def allowed():
            return (self.foreground() == expected and self.identity(window.hwnd) == window
                    and (watch is None or not watch.lost))
        if not allowed():
            return False
        if watch is not None:
            watch.expect_foreground(window.hwnd)
        # AttachThreadInput 要求调用线程已有消息队列。CLI 输入线程不一定有。
        self.gui.PumpWaitingMessages()
        if not allowed():
            return False
        requested = False
        try:
            if watch is not None:
                watch.focus_requested = window.hwnd
            self.gui.SetForegroundWindow(window.hwnd)
            requested = True
        except Exception:
            pass
        if self._wait_foreground(window, expected, watch, timeout=.3 if requested else 0):
            return True
        # 复用项目现有切前台策略中的线程挂接，但不发送全局 Alt，也不反复抢焦点。
        if not expected or not allowed():
            return False
        attached = False
        thread = self.api.GetCurrentThreadId()
        try:
            foreground_thread = self.process.GetWindowThreadProcessId(expected)[0]
        except Exception:
            return False  # 用户关闭原前台窗口时，句柄可能在检查后失效。
        try:
            attached = bool(self.user32.AttachThreadInput(thread, foreground_thread, True))
            if attached and allowed():
                # 与现有前台模式一致。仅 SetForegroundWindow 在部分窗口下会被拒绝。
                self.gui.BringWindowToTop(window.hwnd)
                if allowed():
                    self.gui.SetForegroundWindow(window.hwnd)
        except Exception:
            pass
        finally:
            if attached:
                self.user32.AttachThreadInput(thread, foreground_thread, False)
        return self._wait_foreground(window, expected, watch)

    def _wait_foreground(self, window, previous, watch=None, timeout=.3):
        deadline = time.monotonic() + timeout
        while True:
            if (self.identity(window.hwnd) != window or (watch is not None and watch.lost)):
                return False
            current = self.foreground()
            if current == window.hwnd:
                return True
            # 0 是激活期间可能出现的短暂状态；真正的第三个窗口不能被重新抢走。
            if current not in (0, previous) or time.monotonic() >= deadline:
                return False
            time.sleep(.01)

    def watch_foreground(self, window):
        return ForegroundWatch(self, window.hwnd)

    def cursor(self):
        return self.api.GetCursorPos()

    def cursor_locked(self, window):
        """识别游戏的视角捕获：光标被限制在本窗口中心的一个点。"""
        rect = wintypes.RECT()
        if not self.user32.GetClipCursor(ctypes.byref(rect)):
            raise ctypes.WinError(ctypes.get_last_error())
        width, height = self.size(window)
        center = self.client_to_screen(window, (width//2, height//2))
        cursor = self.cursor()
        # GetCursorInfo 是全局可见状态，前台应用可能仍显示光标，不能单独用它判断。
        return (0 <= rect.right-rect.left <= 1 and 0 <= rect.bottom-rect.top <= 1
                and abs(rect.left-center[0]) <= 1 and abs(rect.top-center[1]) <= 1
                and abs(cursor[0]-center[0]) <= 1 and abs(cursor[1]-center[1]) <= 1)

    def move(self, point):
        protection = getattr(self, '_mouse_protection', None)
        if protection is not None:
            protection.allow_move(point)
        self.api.SetCursorPos(point)

    def mouse_buttons_down(self):
        return any(self.api.GetAsyncKeyState(key) & 0x8000 for key in (1,2,4,5,6))

    def protect_mouse(self, timeout=2, on_expire=None):
        if self.mouse_buttons_down():
            raise RuntimeError('用户正在按住鼠标，等待释放后再操作')
        protection = MouseProtection(self, timeout, on_expire)
        self._mouse_protection = protection
        return protection

    def screen_to_client(self, window, point):
        return self.gui.ScreenToClient(window.hwnd, point)

    def client_to_screen(self, window, point):
        return self.gui.ClientToScreen(window.hwnd, point)

    def post(self, window, message, wparam=0, lparam=0):
        ctypes.set_last_error(0)
        if not self.user32.PostMessageW(window.hwnd, message, wparam, lparam):
            raise ctypes.WinError(ctypes.get_last_error())

    def send_mouse(self, window, message, wparam=0, lparam=0):
        """鼠标消息有序处理，避免旧 WM_MOUSEMOVE 在下一次定位后回写旧光标。"""
        result = ctypes.c_size_t()
        ctypes.set_last_error(0)
        # SMTO_BLOCK | SMTO_ABORTIFHUNG | SMTO_ERRORONEXIT；不允许无限等待游戏线程。
        if not self.user32.SendMessageTimeoutW(window.hwnd, message, wparam, lparam,
                                               0x23, 100, ctypes.byref(result)):
            error = ctypes.get_last_error()
            if error in (0, 1460):
                raise TimeoutError('游戏未及时处理鼠标输入')
            raise ctypes.WinError(error)

    def scan_code(self, vk):
        return self.api.MapVirtualKey(vk, 0)

    def scroll(self, direction, pause):
        import pyautogui
        pyautogui.scroll(direction, _pause=pause)
