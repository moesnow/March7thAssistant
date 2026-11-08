"""CLI/GUI 共用的非激活横幅；相邻滚动复用窗口，短暂延迟隐藏。"""
import threading
import time


class ScrollBanner:
    def __init__(self):
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        self._request = None
        self._hide_at = 0
        self._error = None

    def show(self, window, message=None):
        from module.localization import tr
        with self._lock:
            self._ready.clear()
            self._request = (window.hwnd, message or tr('滚轮操作需临时切换游戏到前台'))
            self._hide_at = float('inf')
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name='M7AScrollBanner', daemon=True)
                self._thread.start()
        self._wake.set()
        if not self._ready.wait(2) or self._error:
            raise RuntimeError('无法显示滚轮前台回退提示，操作已取消') from self._error

    def hide(self, immediate=False):
        with self._lock:
            self._hide_at = time.monotonic() + (0 if immediate else .6)
        self._wake.set()

    def close(self):
        self._stop.set()
        self._wake.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)

    def _run(self):
        import win32api
        import win32con as c
        import win32gui as g
        from module.localization import tr
        hwnd = None
        try:
            hwnd = g.CreateWindowEx(
                c.WS_EX_TOPMOST | c.WS_EX_NOACTIVATE | c.WS_EX_TOOLWINDOW | c.WS_EX_LAYERED | c.WS_EX_TRANSPARENT,
                'STATIC', tr('滚轮操作需临时切换游戏到前台'),
                c.WS_POPUP | c.WS_BORDER | c.SS_CENTER | c.SS_CENTERIMAGE,
                0, 0, 640, 48, 0, 0, win32api.GetModuleHandle(None), None)
            g.SetLayeredWindowAttributes(hwnd, 0, 240, c.LWA_ALPHA)
            g.SendMessage(hwnd, c.WM_SETFONT, g.GetStockObject(17), True)  # DEFAULT_GUI_FONT
            shown = False
            while not self._stop.is_set():
                self._wake.wait(.02)
                self._wake.clear()
                with self._lock:
                    request, until = self._request, self._hide_at
                    self._request = None
                if request:
                    target, message = request
                    g.SetWindowText(hwnd, message)
                    monitor = win32api.MonitorFromWindow(target, c.MONITOR_DEFAULTTONEAREST)
                    left, top, right, bottom = win32api.GetMonitorInfo(monitor)['Work']
                    width = min(640, right - left)
                    g.SetWindowPos(hwnd, c.HWND_TOPMOST, left + (right-left-width)//2, top+24,
                                   width, min(48, bottom-top), c.SWP_NOACTIVATE | c.SWP_SHOWWINDOW)
                    g.UpdateWindow(hwnd)
                    shown = True
                    self._ready.set()
                if shown and time.monotonic() >= until:
                    g.ShowWindow(hwnd, c.SW_HIDE)
                    shown = False
                g.PumpWaitingMessages()
        except BaseException as error:
            self._error = error
        finally:
            if hwnd:
                g.DestroyWindow(hwnd)
            self._ready.set()
