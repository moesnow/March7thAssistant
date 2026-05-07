from __future__ import annotations

import argparse
import ctypes
import os
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass

from module.logger import log
from module.localization import load_language, tr
from module.update.downloader import format_size
from module.update.update_engine import UpdateBlockedError, UpdateCancelledError, UpdateEngine, UpdateProgress, UpdateStage
from module.update.version_check import check_for_update


if os.name != "nt":
    raise RuntimeError("Updater helper only supports Windows")


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
comctl32 = ctypes.windll.comctl32

LRESULT = getattr(wintypes, "LRESULT", ctypes.c_ssize_t)
HICON = getattr(wintypes, "HICON", wintypes.HANDLE)
HCURSOR = getattr(wintypes, "HCURSOR", wintypes.HANDLE)
HBRUSH = getattr(wintypes, "HBRUSH", wintypes.HANDLE)
ATOM = getattr(wintypes, "ATOM", wintypes.WORD)
UINT_PTR = getattr(wintypes, "UINT_PTR", ctypes.c_size_t)
LPVOID = getattr(wintypes, "LPVOID", ctypes.c_void_p)

WM_CREATE = 0x0001
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_TIMER = 0x0113

SW_HIDE = 0
SW_SHOW = 5

SC_CLOSE = 0xF060
MF_BYCOMMAND = 0x00000000
MF_ENABLED = 0x00000000
MF_GRAYED = 0x00000001

WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_CLIPCHILDREN = 0x02000000

PBS_SMOOTH = 0x01
PBS_MARQUEE = 0x08

MB_OK = 0x00000000
MB_ICONINFORMATION = 0x00000040
MB_ICONWARNING = 0x00000030
MB_ICONERROR = 0x00000010
MB_RETRYCANCEL = 0x00000005

IDOK = 1
IDCANCEL = 2
IDRETRY = 4

PBM_SETPOS = 0x0402
PBM_SETRANGE32 = 0x0406
PBM_SETMARQUEE = 0x040A

ICC_PROGRESS_CLASS = 0x00000020
COLOR_WINDOW = 5
TIMER_ID = 1
CLEANUP_BACKUP_WAIT_TIMEOUT = 120.0
CLEANUP_BACKUP_DELETE_TIMEOUT = 30.0


class INITCOMMONCONTROLSEX(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("dwICC", wintypes.DWORD)]


WNDPROCTYPE = ctypes.WINFUNCTYPE(
    LRESULT,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROCTYPE),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", HICON),
        ("hCursor", HCURSOR),
        ("hbrBackground", HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
        ("lPrivate", wintypes.DWORD),
    ]


user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = ATOM
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.UpdateWindow.argtypes = [wintypes.HWND]
user32.UpdateWindow.restype = wintypes.BOOL
user32.SetTimer.argtypes = [wintypes.HWND, UINT_PTR, wintypes.UINT, LPVOID]
user32.SetTimer.restype = UINT_PTR
user32.KillTimer.argtypes = [wintypes.HWND, UINT_PTR]
user32.KillTimer.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.TranslateMessage.restype = wintypes.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
user32.LoadCursorW.restype = HCURSOR
user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
user32.LoadIconW.restype = HICON
user32.GetSysColorBrush.argtypes = [ctypes.c_int]
user32.GetSysColorBrush.restype = HBRUSH
user32.SetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
user32.SetWindowTextW.restype = wintypes.BOOL
user32.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]
user32.MessageBoxW.restype = ctypes.c_int
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = LRESULT
user32.GetSystemMenu.argtypes = [wintypes.HWND, wintypes.BOOL]
user32.GetSystemMenu.restype = wintypes.HMENU
user32.EnableMenuItem.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.UINT]
user32.EnableMenuItem.restype = wintypes.BOOL
user32.DrawMenuBar.argtypes = [wintypes.HWND]
user32.DrawMenuBar.restype = wintypes.BOOL


_WINDOW_INSTANCES: dict[int, "NativeUpdaterWindow"] = {}
_CREATING_INSTANCE: "NativeUpdaterWindow | None" = None


def _make_int_resource(resource_id: int):
    return ctypes.cast(ctypes.c_void_p(resource_id), wintypes.LPCWSTR)


def _format_size(size: int | None) -> str:
    return format_size(size)


@dataclass(slots=True)
class HelperOptions:
    mode: str
    download_url: str | None
    file_name: str | None
    sha256: str | None
    extract_folder_path: str | None
    wait_pid: int | None
    auto_mode: bool = False
    cleanup_backup_path: str | None = None


@dataclass(slots=True)
class ResultState:
    kind: str
    message: str
    details: list[str]


@dataclass(slots=True)
class RetryContext:
    stage: UpdateStage
    file_name: str
    extract_folder_path: str | None
    self_backup_path: str | None = None


def _global_wnd_proc(hwnd, msg, w_param, l_param):
    global _CREATING_INSTANCE

    instance = _WINDOW_INSTANCES.get(int(hwnd))
    if instance is None and msg == WM_CREATE and _CREATING_INSTANCE is not None:
        instance = _CREATING_INSTANCE
        _WINDOW_INSTANCES[int(hwnd)] = instance
        instance.hwnd = hwnd

    if instance is not None:
        return instance.wnd_proc(hwnd, msg, w_param, l_param)

    return user32.DefWindowProcW(hwnd, msg, w_param, l_param)


GLOBAL_WND_PROC = WNDPROCTYPE(_global_wnd_proc)


class NativeUpdaterWindow:
    CLASS_NAME = "March7thAssistantUpdaterWindow"

    def __init__(self, options: HelperOptions):
        self.options = options
        self.hwnd = None
        self.title_hwnd = None
        self.status_hwnd = None
        self.detail_hwnd = None
        self.progress_hwnd = None
        self._thread: threading.Thread | None = None
        self._engine: UpdateEngine | None = None
        self._lock = threading.Lock()
        self._running = False
        self._title_text = tr("正在准备更新")
        self._status_text = tr("即将开始下载和安装新版本")
        self._detail_text = ""
        self._progress_value = 0
        self._indeterminate = True
        self._current_result: ResultState | None = None
        self._success_deadline = None
        self._no_update_deadline = None
        self._marquee_enabled = False
        self._close_button_disabled = False
        self._cancel_requested = False
        self._current_stage = UpdateStage.PREPARE
        self._retry_context: RetryContext | None = None

        if self.options.mode == "finalize":
            self._title_text = tr("正在更新 March7th Assistant")
            self._status_text = tr("正在等待主程序退出...")

    def run(self) -> int:
        self._init_common_controls()
        self._create_window()
        self._start_worker()
        user32.ShowWindow(self.hwnd, SW_SHOW)
        user32.UpdateWindow(self.hwnd)

        msg = MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        return 0

    def _init_common_controls(self):
        icc = INITCOMMONCONTROLSEX()
        icc.dwSize = ctypes.sizeof(INITCOMMONCONTROLSEX)
        icc.dwICC = ICC_PROGRESS_CLASS
        comctl32.InitCommonControlsEx(ctypes.byref(icc))

    def _create_window(self):
        global _CREATING_INSTANCE

        h_instance = kernel32.GetModuleHandleW(None)
        wnd_class = WNDCLASSW()
        wnd_class.lpfnWndProc = GLOBAL_WND_PROC
        wnd_class.hInstance = h_instance
        wnd_class.lpszClassName = self.CLASS_NAME
        wnd_class.hbrBackground = user32.GetSysColorBrush(COLOR_WINDOW)
        wnd_class.hCursor = user32.LoadCursorW(None, _make_int_resource(32512))
        wnd_class.hIcon = user32.LoadIconW(None, _make_int_resource(32512))
        user32.RegisterClassW(ctypes.byref(wnd_class))

        _CREATING_INSTANCE = self
        self.hwnd = user32.CreateWindowExW(
            0,
            self.CLASS_NAME,
            "March7th Updater",
            WS_VISIBLE | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_CLIPCHILDREN,
            0x80000000,
            0x80000000,
            560,
            220,
            None,
            None,
            h_instance,
            None,
        )
        _CREATING_INSTANCE = None
        _WINDOW_INSTANCES[int(self.hwnd)] = self

        child_style = WS_CHILD | WS_VISIBLE
        progress_style = child_style | PBS_SMOOTH | PBS_MARQUEE

        self.title_hwnd = user32.CreateWindowExW(0, "STATIC", self._title_text, child_style, 20, 20, 500, 28, self.hwnd, None, h_instance, None)
        self.status_hwnd = user32.CreateWindowExW(0, "STATIC", self._status_text, child_style, 20, 58, 500, 40, self.hwnd, None, h_instance, None)
        self.detail_hwnd = user32.CreateWindowExW(0, "STATIC", self._detail_text, child_style, 20, 104, 500, 18, self.hwnd, None, h_instance, None)
        self.progress_hwnd = user32.CreateWindowExW(0, "msctls_progress32", "", progress_style, 20, 132, 500, 24, self.hwnd, None, h_instance, None)

        user32.SendMessageW(self.progress_hwnd, PBM_SETRANGE32, 0, 1000)
        user32.SendMessageW(self.progress_hwnd, PBM_SETMARQUEE, 1, 40)
        self._marquee_enabled = True
        user32.SetTimer(self.hwnd, TIMER_ID, 100, None)

    def wnd_proc(self, hwnd, msg, w_param, l_param):
        if msg == WM_CLOSE:
            with self._lock:
                running = self._running
                stage = self._current_stage
            if running:
                if stage == UpdateStage.COVER:
                    # 覆盖阶段不允许中断，直接忽略关闭请求。
                    return 0
                else:
                    self._request_cancel_from_ui()
                return 0
            user32.DestroyWindow(hwnd)
            return 0

        if msg == WM_TIMER:
            self._refresh_controls()
            self._process_result_state()
            return 0

        if msg == WM_DESTROY:
            user32.KillTimer(hwnd, TIMER_ID)
            _WINDOW_INSTANCES.pop(int(hwnd), None)
            user32.PostQuitMessage(0)
            return 0

        return user32.DefWindowProcW(hwnd, msg, w_param, l_param)

    def _start_worker(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._current_result = None
            self._success_deadline = None

        self._thread = threading.Thread(target=self._worker_main, daemon=True)
        self._thread.start()

    def _worker_main(self):
        try:
            self._log("info", f"更新程序启动，模式={self.options.mode}")
            engine = UpdateEngine(progress_callback=self._on_progress, log_callback=self._on_engine_log)
            self._engine = engine
            retry_context = self._retry_context

            if retry_context is not None:
                engine.set_local_package(
                    retry_context.file_name,
                    retry_context.extract_folder_path,
                )
                engine.self_backup_path = retry_context.self_backup_path
                self._log("info", f"从 {retry_context.stage.value} 阶段继续重试")

            elif self.options.mode == "finalize" and self.options.file_name:
                engine.set_local_package(self.options.file_name, self.options.extract_folder_path)
                self._log("debug", f"finalize 模式使用本地更新包：{self.options.file_name}")
            elif self.options.download_url and self.options.file_name:
                self._log("debug", f"已预设URL和文件名：{self.options.file_name}")
                engine.set_package(
                    self.options.download_url,
                    self.options.file_name,
                    self.options.sha256,
                )

            if self._cancel_requested:
                self._log("debug", "检测到取消请求，传递给引擎")
                engine.request_cancel()

            if retry_context is not None:
                self._run_retry_from_stage(engine, retry_context.stage)
            elif self.options.mode == "finalize":
                self._log("info", f"执行最终化模式，等待PID={self.options.wait_pid}")
                engine.finalize_update(wait_pid=self.options.wait_pid)
            else:
                # 未预设 URL 时，通过统一的版本检测获取更新信息
                if not engine.download_url:
                    self._log("debug", "未预设URL，执行版本检测")
                    try:
                        from module.config import cfg
                        source = getattr(cfg, "update_source", "GitHub")
                        cdk = getattr(cfg, "mirrorchyan_cdk", "")
                        prerelease = bool(getattr(cfg, "update_prerelease_enable", False))
                        full = bool(getattr(cfg, "update_full_enable", True))
                    except Exception:
                        source, cdk, prerelease, full = "GitHub", "", False, True

                    try:
                        info = check_for_update(source, cdk, prerelease, full)
                    except Exception as e:
                        self._log("warning", f"版本检测失败: {e}")
                        info = None

                    if info is None:
                        self._log("info", "当前已是最新版本")
                        self._set_result("no-update", tr("当前已是最新版本"))
                        return

                    engine.set_update_info(info)
                    self._log("info", f"发现新版本: {info.version} ({info.source})")

                if not engine.run_full_update(wait_pid=self.options.wait_pid):
                    self._set_result("no-update", tr("当前已是最新版本"))
                    return

            with self._lock:
                self._running = False
                self._title_text = tr("更新完成")
                self._status_text = tr("新版本已启动，此窗口将自动关闭")
                self._detail_text = ""
                self._progress_value = 1000
                self._indeterminate = False
                self._current_result = ResultState("success", tr("更新完成"), [])
                self._success_deadline = time.monotonic() + 1.5
                self._retry_context = None
                self._log("info", "更新成功完成")
        except UpdateCancelledError:
            self._log("info", "用户取消了更新")
            with self._lock:
                self._retry_context = None
            self._set_result("cancelled", tr("更新已取消"))
        except UpdateBlockedError as e:
            retry_context = self._build_retry_context(engine, self._current_stage)
            with self._lock:
                self._retry_context = retry_context
            self._log("error", f"更新被文件占用阻止：{str(e)}")
            self._set_result("blocked", str(e), e.locked_files)
        except Exception as e:
            self._log("error", f"更新过程出错：{str(e) or tr('更新失败')}")
            with self._lock:
                self._retry_context = None
            self._set_result("failed", str(e) or tr("更新失败"))
        finally:
            self._engine = None

    def _run_retry_from_stage(self, engine: UpdateEngine, stage: UpdateStage):
        if stage == UpdateStage.COVER:
            engine.cover_folder()
            engine.cleanup()
            engine.launch_application()
            return

        if stage == UpdateStage.CLEANUP:
            engine.cleanup()
            engine.launch_application()
            return

        engine.finalize_update(wait_pid=self.options.wait_pid)

    def _build_retry_context(
        self,
        engine: UpdateEngine,
        stage: UpdateStage,
    ) -> RetryContext | None:
        if stage not in {UpdateStage.COVER, UpdateStage.CLEANUP}:
            return None

        file_name = engine.file_name or self.options.file_name
        if not file_name:
            return None

        return RetryContext(
            stage=stage,
            file_name=file_name,
            extract_folder_path=engine.extract_folder_path or self.options.extract_folder_path,
            self_backup_path=engine.self_backup_path,
        )

    def _on_progress(self, progress: UpdateProgress):
        detail = ""
        progress_value = 0
        indeterminate = progress.indeterminate or not progress.total

        if progress.total and not indeterminate:
            current = max(0, progress.current or 0)
            total = max(1, progress.total)
            progress_value = min(1000, int(current * 1000 / total))
            percent = min(100, int(current * 100 / total))
            if progress.stage == UpdateStage.COVER:
                detail = f"{percent}%"
            else:
                detail = f"{_format_size(current)} / {_format_size(total)}"

        with self._lock:
            self._current_stage = progress.stage
            self._title_text = tr("正在更新 March7th Assistant")
            self._status_text = progress.message
            self._detail_text = detail
            self._progress_value = progress_value
            self._indeterminate = indeterminate

        # 调试日志：输出阶段变化
        if progress_value % 100 == 0 or indeterminate:  # 每10%进度或不确定时输出
            self._log("debug", f"进度更新：stage={progress.stage.value}, 进度={progress_value}/1000, 详情={detail}")

    def _request_cancel_from_ui(self):
        with self._lock:
            if self._cancel_requested:
                return
            self._cancel_requested = True
            self._title_text = tr("正在更新 March7th Assistant")
            self._status_text = tr("已请求取消更新，正在等待当前步骤结束")
            self._detail_text = ""
            self._indeterminate = True

        engine = self._engine
        if engine is not None:
            engine.request_cancel()

    def _set_close_button_enabled(self, enabled: bool):
        if self.hwnd is None:
            return

        if enabled == (not self._close_button_disabled):
            return

        system_menu = user32.GetSystemMenu(self.hwnd, False)
        if not system_menu:
            return

        flags = MF_BYCOMMAND | (MF_ENABLED if enabled else MF_GRAYED)
        user32.EnableMenuItem(system_menu, SC_CLOSE, flags)
        user32.DrawMenuBar(self.hwnd)
        self._close_button_disabled = not enabled

    def _update_log_detail(self, level: str, message: str):
        if level.lower() in {"warning", "error"}:
            with self._lock:
                self._detail_text = message

    def _on_engine_log(self, level: str, message: str):
        self._update_log_detail(level, message)

    def _log(self, level: str, message: str):
        log_method = getattr(log, level.lower(), None)
        if callable(log_method):
            log_method(message)
        self._update_log_detail(level, message)

    def _set_result(self, kind: str, message: str, details: list[str] | None = None):
        with self._lock:
            self._running = False
            if kind == "failed":
                self._title_text = tr("更新失败")
            elif kind == "no-update":
                self._title_text = tr("无需更新")
            self._status_text = message
            self._detail_text = ""
            self._progress_value = 0 if kind in {"failed", "blocked"} else self._progress_value
            self._indeterminate = False
            self._current_result = ResultState(kind, message, details or [])
            self._success_deadline = None
            self._no_update_deadline = time.monotonic() + 10 if kind == "no-update" else None

    def _refresh_controls(self):
        with self._lock:
            title_text = self._title_text
            status_text = self._status_text
            detail_text = self._detail_text
            progress_value = self._progress_value
            indeterminate = self._indeterminate
            running = self._running
            stage = self._current_stage

        user32.SetWindowTextW(self.title_hwnd, title_text)
        user32.SetWindowTextW(self.status_hwnd, status_text)
        user32.SetWindowTextW(self.detail_hwnd, detail_text)

        self._set_close_button_enabled(not (running and stage == UpdateStage.COVER))

        if indeterminate != self._marquee_enabled:
            user32.SendMessageW(self.progress_hwnd, PBM_SETMARQUEE, 1 if indeterminate else 0, 40)
            self._marquee_enabled = indeterminate

        if not indeterminate:
            user32.SendMessageW(self.progress_hwnd, PBM_SETRANGE32, 0, 1000)
            user32.SendMessageW(self.progress_hwnd, PBM_SETPOS, progress_value, 0)

    def _process_result_state(self):
        with self._lock:
            result = self._current_result
            success_deadline = self._success_deadline
            no_update_deadline = self._no_update_deadline

        if result is None:
            return

        if result.kind == "success":
            if success_deadline is not None and time.monotonic() >= success_deadline:
                user32.DestroyWindow(self.hwnd)
            return

        if result.kind == "cancelled":
            user32.DestroyWindow(self.hwnd)
            return

        if result.kind == "no-update":
            if no_update_deadline is not None:
                remaining = no_update_deadline - time.monotonic()
                if remaining <= 0:
                    user32.DestroyWindow(self.hwnd)
                else:
                    countdown_text = tr("{seconds} 秒后自动退出").format(seconds=int(remaining) + 1)
                    with self._lock:
                        self._detail_text = countdown_text
            return

        with self._lock:
            self._current_result = None

        if result.kind == "blocked":
            response = user32.MessageBoxW(
                self.hwnd,
                self._compose_result_message(result),
                tr("更新被阻塞"),
                MB_RETRYCANCEL | MB_ICONWARNING,
            )
        else:
            response = user32.MessageBoxW(
                self.hwnd,
                self._compose_result_message(result),
                tr("更新失败"),
                MB_RETRYCANCEL | MB_ICONERROR,
            )

        if response == IDRETRY:
            self._start_worker()
        else:
            user32.DestroyWindow(self.hwnd)

    def _compose_result_message(self, result: ResultState) -> str:
        lines = [result.message]
        for path in result.details[:5]:
            lines.append(path)
        return "\n".join(lines)


def parse_args(argv=None) -> HelperOptions:
    normalized_argv = list(argv or [])
    normalized_argv = ["--auto" if arg == "/auto" else arg for arg in normalized_argv]

    parser = argparse.ArgumentParser(
        prog="March7th Updater",
        description="March7th Assistant 轻量更新器",
    )
    parser.add_argument("download_url", nargs="?")
    parser.add_argument("file_name", nargs="?")
    parser.add_argument("--mode", choices=("full", "finalize", "cleanup-backup"), default="full")
    parser.add_argument("--wait-pid", type=int, default=None)
    parser.add_argument("--file-name", dest="file_name_option", default=None)
    parser.add_argument("--sha256", default=None)
    parser.add_argument("--extract-folder-path", default=None)
    parser.add_argument("--cleanup-backup-path", default=None)
    parser.add_argument("--auto", "-a", action="store_true", dest="auto_mode")

    args = parser.parse_args(normalized_argv)
    effective_download_url = args.download_url
    effective_file_name = args.file_name_option or args.file_name

    if args.mode == "finalize" and not effective_file_name and args.download_url and not args.file_name:
        effective_download_url = None
        effective_file_name = args.download_url

    if args.mode == "finalize" and not effective_file_name:
        parser.error("finalize mode requires file_name")

    if args.mode == "cleanup-backup" and not args.cleanup_backup_path:
        parser.error("cleanup-backup mode requires --cleanup-backup-path")

    return HelperOptions(
        mode=args.mode,
        download_url=effective_download_url,
        file_name=effective_file_name,
        sha256=args.sha256,
        extract_folder_path=args.extract_folder_path,
        wait_pid=args.wait_pid,
        auto_mode=args.auto_mode,
        cleanup_backup_path=args.cleanup_backup_path,
    )


def run_cleanup_backup(options: HelperOptions) -> int:
    backup = options.cleanup_backup_path
    if not backup:
        return 0

    engine = UpdateEngine(logger=log)
    if options.wait_pid:
        if not engine.wait_for_process_exit(options.wait_pid, timeout=CLEANUP_BACKUP_WAIT_TIMEOUT):
            log.warning(f"等待旧版更新器退出超时，跳过旧版更新器备份清理: PID={options.wait_pid}")
            return 1

    deadline = time.monotonic() + CLEANUP_BACKUP_DELETE_TIMEOUT
    while True:
        try:
            os.remove(backup)
            log.info(f"已清理旧版更新器备份: {backup}")
            return 0
        except FileNotFoundError:
            return 0
        except OSError as e:
            if not os.path.exists(backup):
                return 0
            if time.monotonic() >= deadline:
                log.warning(f"无法删除旧版更新器备份: {e}")
                return 1
            time.sleep(0.2)


def main(argv=None) -> int:
    load_language()
    options = parse_args(argv)
    if options.mode == "cleanup-backup":
        return run_cleanup_backup(options)
    window = NativeUpdaterWindow(options)
    return window.run()
