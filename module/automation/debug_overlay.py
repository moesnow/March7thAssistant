"""
调试叠加层模块 - 在屏幕上实时绘制检测范围框的透明悬浮窗。
仅在 Windows 上可用，使用 pywin32 + GDI，兼容 CLI 和 GUI 模式。
"""
import sys
import threading


if sys.platform != 'win32':
    class DebugOverlay:
        COLOR_GREEN = (0, 255, 0, 200)
        COLOR_RED = (255, 0, 0, 200)
        COLOR_BLUE = (0, 120, 255, 200)
        COLOR_YELLOW = (255, 220, 0, 200)
        COLOR_ORANGE = (255, 140, 0, 200)
        COLOR_CYAN = (0, 255, 255, 200)
        COLOR_MAGENTA = (255, 0, 255, 200)
        COLOR_WHITE = (255, 255, 255, 200)

        def add_rect(self, *a, **kw):
            pass

        def clear_rects(self):
            pass

        def show_overlay(self):
            pass

        def hide_overlay(self):
            pass

    _debug_overlay_instance = DebugOverlay()

    def get_debug_overlay():
        return _debug_overlay_instance
else:
    import ctypes
    import win32api
    import win32con
    import win32gui

    # GDI 函数引用（用于创建字体）
    _gdi32 = ctypes.windll.gdi32

    def _rgba_to_gdi(r, g, b, _a):
        """RGBA → GDI COLORREF (BGR 顺序)。"""
        return (b << 16) | (g << 8) | r

    def _create_scaled_font(scale):
        """创建按屏幕分辨率缩放的 GDI 字体。
        使用 NONANTIALIASED_QUALITY 关闭 ClearType 抗锯齿，
        避免颜色键透明窗口上出现文字边缘杂色。
        """
        font_height = int(round(-14 * scale))  # 负值 = 字符高度
        return _gdi32.CreateFontW(
            font_height, 0, 0, 0,
            win32con.FW_BOLD,
            0, 0, 0,
            win32con.DEFAULT_CHARSET,
            win32con.OUT_DEFAULT_PRECIS,
            win32con.CLIP_DEFAULT_PRECIS,
            win32con.NONANTIALIASED_QUALITY,
            win32con.DEFAULT_PITCH | win32con.FF_DONTCARE,
            "Microsoft YaHei",
        )

    # 透明颜色键 — 品红色像素变为全透明
    TRANSPARENCY_KEY = win32api.RGB(255, 0, 255)

    CLASS_NAME = "M7ADebugOverlayW"
    _window_map = {}
    _window_map_lock = threading.Lock()

    def _register_class():
        """注册窗口类（仅执行一次）。"""
        try:
            wc = win32gui.WNDCLASS()
            wc.lpfnWndProc = _global_wnd_proc
            wc.hInstance = win32api.GetModuleHandle(None)
            wc.lpszClassName = CLASS_NAME
            wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
            win32gui.RegisterClass(wc)
        except Exception:
            pass  # 已注册则忽略

    def _global_wnd_proc(hwnd, msg, wparam, lparam):
        with _window_map_lock:
            overlay = _window_map.get(hwnd)
        if overlay is not None:
            return overlay._wnd_proc(hwnd, msg, wparam, lparam)
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    class DebugOverlay:
        """透明悬浮窗，使用 Win32 GDI 在屏幕上绘制调试矩形框。
        兼容 CLI 和 GUI 两种运行模式，不依赖 Qt。
        """

        COLOR_GREEN = (0, 255, 0, 200)
        COLOR_RED = (255, 0, 0, 200)
        COLOR_BLUE = (0, 120, 255, 200)
        COLOR_YELLOW = (255, 220, 0, 200)
        COLOR_ORANGE = (255, 140, 0, 200)
        COLOR_CYAN = (0, 255, 255, 200)
        COLOR_MAGENTA = (255, 0, 255, 200)
        COLOR_WHITE = (255, 255, 255, 200)

        _class_registered = False

        def __init__(self):
            self._rects = []
            self._hwnd = None
            self._lock = threading.Lock()
            self._msg_thread = None
            self._screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            self._screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            # 以 1920 为基准计算缩放比例，用于线条粗细和字体大小
            self._scale = max(0.75, self._screen_w / 1920.0)
            self._pen_width = max(1, int(round(2 * self._scale)))
            self._font = _create_scaled_font(self._scale)
            self._label_offset = int(round(20 * self._scale))

            self._init_window()

        def _init_window(self):
            if not DebugOverlay._class_registered:
                _register_class()
                DebugOverlay._class_registered = True

            ready_event = threading.Event()

            def _thread_proc():
                # 必须在此线程中创建窗口和运行消息循环
                self._hwnd = win32gui.CreateWindowEx(
                    win32con.WS_EX_LAYERED
                    | win32con.WS_EX_TRANSPARENT
                    | win32con.WS_EX_TOOLWINDOW
                    | win32con.WS_EX_NOACTIVATE
                    | win32con.WS_EX_TOPMOST,
                    CLASS_NAME,
                    "",
                    win32con.WS_POPUP,
                    0, 0, self._screen_w, self._screen_h,
                    0, 0,
                    win32api.GetModuleHandle(None),
                    None,
                )
                if not self._hwnd:
                    ready_event.set()
                    return

                with _window_map_lock:
                    _window_map[self._hwnd] = self

                # 设置透明颜色键
                win32gui.SetLayeredWindowAttributes(
                    self._hwnd, TRANSPARENCY_KEY, 0,
                    win32con.LWA_COLORKEY,
                )

                # 置顶
                win32gui.SetWindowPos(
                    self._hwnd, win32con.HWND_TOPMOST,
                    0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
                    | win32con.SWP_NOACTIVATE,
                )

                ready_event.set()

                # win32gui 消息循环（不支持 GetMessage 的简单循环）
                win32gui.PumpMessages()

            self._msg_thread = threading.Thread(target=_thread_proc, daemon=True)
            self._msg_thread.start()
            ready_event.wait(5.0)

        def _wnd_proc(self, hwnd, msg, wparam, lparam):
            if msg == win32con.WM_PAINT:
                self._on_paint(hwnd)
                return 0
            elif msg == win32con.WM_ERASEBKGND:
                return 1
            elif msg == win32con.WM_NCHITTEST:
                return win32con.HTTRANSPARENT
            elif msg == win32con.WM_DESTROY:
                win32gui.PostQuitMessage(0)
                return 0
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

        def _on_paint(self, hwnd):
            """WM_PAINT：用 GDI 双缓冲绘制所有矩形。"""
            hdc, ps = win32gui.BeginPaint(hwnd)

            # 双缓冲
            mem_dc = win32gui.CreateCompatibleDC(hdc)
            bmp = win32gui.CreateCompatibleBitmap(hdc, self._screen_w, self._screen_h)
            old_bmp = win32gui.SelectObject(mem_dc, bmp)

            # 透明背景
            brush = win32gui.CreateSolidBrush(TRANSPARENCY_KEY)
            win32gui.FillRect(mem_dc, (0, 0, self._screen_w, self._screen_h), brush)
            win32gui.DeleteObject(brush)

            # 选择缩放后的字体
            old_font = win32gui.SelectObject(mem_dc, self._font) if self._font else None

            # 绘制矩形
            with self._lock:
                rects = list(self._rects)

            null_brush = win32gui.GetStockObject(win32con.NULL_BRUSH)

            for x1, y1, x2, y2, color, label in rects:
                r, g, b, a = color
                gdi_color = _rgba_to_gdi(r, g, b, a)

                pen = win32gui.CreatePen(win32con.PS_SOLID, self._pen_width, gdi_color)
                old_pen = win32gui.SelectObject(mem_dc, pen)
                old_br = win32gui.SelectObject(mem_dc, null_brush)

                win32gui.Rectangle(mem_dc, x1, y1, x2, y2)

                win32gui.SelectObject(mem_dc, old_br)
                win32gui.SelectObject(mem_dc, old_pen)
                win32gui.DeleteObject(pen)

                if label:
                    win32gui.SetTextColor(mem_dc, gdi_color)
                    win32gui.SetBkMode(mem_dc, win32con.TRANSPARENT)
                    win32gui.DrawText(mem_dc, str(label), -1,
                                      (x1, y1 - self._label_offset, x2, y1),
                                      win32con.DT_SINGLELINE | win32con.DT_NOCLIP)

            # 还原字体
            if old_font is not None:
                win32gui.SelectObject(mem_dc, old_font)

            # 输出到屏幕
            win32gui.BitBlt(hdc, 0, 0, self._screen_w, self._screen_h,
                            mem_dc, 0, 0, win32con.SRCCOPY)

            win32gui.SelectObject(mem_dc, old_bmp)
            win32gui.DeleteObject(bmp)
            win32gui.DeleteDC(mem_dc)
            win32gui.EndPaint(hwnd, ps)

        def _invalidate(self):
            if self._hwnd:
                win32gui.InvalidateRect(self._hwnd, None, True)

        def add_rect(self, x1, y1, x2, y2, color=None, label=None):
            """添加一个矩形框。

            :param x1: 左上角 X（屏幕绝对像素）
            :param y1: 左上角 Y
            :param x2: 右下角 X
            :param y2: 右下角 Y
            :param color: RGBA 元组 (R,G,B,A)，默认绿色
            :param label: 可选标签文字
            """
            if color is None:
                color = self.COLOR_GREEN
            with self._lock:
                self._rects.append((x1, y1, x2, y2, color, label))
            self._invalidate()

        def clear_rects(self):
            """清除所有矩形框。"""
            with self._lock:
                if self._rects:
                    self._rects.clear()
                    self._invalidate()

        def show_overlay(self):
            """显示叠加层。"""
            if self._hwnd:
                win32gui.ShowWindow(self._hwnd, win32con.SW_SHOW)
                win32gui.SetWindowPos(
                    self._hwnd, win32con.HWND_TOPMOST,
                    0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
                    | win32con.SWP_NOACTIVATE,
                )

        def hide_overlay(self):
            """隐藏叠加层。"""
            if self._hwnd:
                win32gui.ShowWindow(self._hwnd, win32con.SW_HIDE)
            self.clear_rects()

        def __del__(self):
            self.hide_overlay()
            if self._hwnd:
                with _window_map_lock:
                    _window_map.pop(self._hwnd, None)
                win32gui.DestroyWindow(self._hwnd)
                self._hwnd = None
            if self._font:
                win32gui.DeleteObject(self._font)
                self._font = None

    # ══════════════════════════════════════════════════════════════
    # 全局单例
    # ══════════════════════════════════════════════════════════════

    _debug_overlay_instance = None

    def get_debug_overlay() -> DebugOverlay:
        """获取全局 DebugOverlay 单例。"""
        global _debug_overlay_instance
        if _debug_overlay_instance is None:
            _debug_overlay_instance = DebugOverlay()
        return _debug_overlay_instance
