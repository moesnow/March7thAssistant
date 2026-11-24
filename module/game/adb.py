
"""Android 控制器。输入、取帧和看门狗共享同一次设备会话。"""
from collections import deque
from dataclasses import dataclass
from io import BytesIO
from threading import RLock
import time

from PIL import Image

from module.config.platform import get_ui_profile
from module.game.adb_transport import (
    GAME_PACKAGE, RESOLUTION, Adb, AdbEnvironment, AdbError, AdbService,
    _probe_environment, resolve_adb_path, resolve_adb_service_jar,
)
from module.game.base import FrameCapture, GameControllerBase
from module.localization import tr
from utils.pause import pause_ctl


_GAME_ACTIVITY = "com.mihoyo.combosdk.ComboSDKActivity"
_GAME_COMPONENT = f"{GAME_PACKAGE}/{_GAME_ACTIVITY}"
_TEMPORARY_INPUT_ERRORS = {"game_not_on_display", "sdk_window_active"}
_STARTUP_TASK_MISSING_MS = 1000
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_MULTI_DISPLAY_WARNING = b"[Warning] Multiple displays were found"


@dataclass
class _GameStartup:
    saw_task: bool = False
    missing_since_ms: int | None = None
    relaunched: bool = False


@dataclass(frozen=True)
class AdbRuntimeStatus:
    connected: bool
    serial: str | None
    service_version: str | None
    display_id: int | None
    game_display_id: int | None
    game_running: bool
    sdk_window: bool
    capture_fps: float
    error_code: str | None
    error_message: str | None


def _pixel_crop(crop):
    x, y, w, h = crop
    if not (0 <= x < 1 and 0 <= y < 1 and 0 < w <= 1 and 0 < h <= 1):
        raise ValueError("无效的截图裁剪区域")
    width, height = RESOLUTION
    left, top = int(x * width), int(y * height)
    right, bottom = min(width, int((x + w) * width)), min(height, int((y + h) * height))
    if right <= left or bottom <= top:
        raise ValueError("截图裁剪区域不足一个像素")
    return left, top, right - left, bottom - top


class AdbGameController(GameControllerBase):
    def __init__(self, cfg, logger=None):
        super().__init__(logger=logger)
        self.cfg = cfg
        self._lock = RLock()
        self._service = None
        self._environment = None
        self._input = None
        self._reset_display()

    def _reset_display(self):
        self._on_event = None
        self._startup = None
        self._display_id = None
        self._emulator_physical_display_id = None
        self._game_display_id = None
        self._watching = False
        self._sdk_window = False
        self._moving = False
        self._landscape = False
        self._failure = None
        self._pointer_down = False
        self._tap_ms = 50
        self._event_seq = 0
        self._events = deque(maxlen=256)
        self._last_event_poll = 0.0
        self._frame_seq = 0
        self._min_seq = 0
        self._input_ns = None
        self._frame_times = deque(maxlen=20)

    @property
    def display_id(self):
        return self._display_id

    @property
    def frame_sequence(self):
        return self._frame_seq

    @property
    def events(self):
        with self._lock:
            return tuple(self._events)

    def _validated_tap_ms(self):
        if get_ui_profile(self.cfg).name != "touch_720":
            raise AdbError("ui_profile", tr("ADB 后端需要设置 ui_profile: touch_720"))
        tap_ms = self.cfg.adb_tap_ms
        if tap_ms is not None and (type(tap_ms) is not int or not 1 <= tap_ms <= 10000):
            raise AdbError("tap_duration", tr("adb_tap_ms 必须是 1 到 10000 毫秒之间的整数"))
        return tap_ms

    def _attach(self, environment, service, tap_ms):
        self._service = service
        self._environment = environment
        self._tap_ms = tap_ms if tap_ms is not None else service.client.hello.get("default_tap_ms", 50)
        return environment

    def attach_virtual_session(self, environment: AdbEnvironment, service, *, on_event=None):
        """接管 APK 进程已鉴权的虚拟屏传输，不运行 adb 命令。"""
        with self._lock:
            if self._service is not None or self._failure or environment.device_type != "physical":
                raise RuntimeError("无法接管 Android 虚拟屏会话")
            attached = self._attach(environment, service, self._validated_tap_ms())
            self._on_event = on_event
            return attached

    def connect(self, *, adb_path=None) -> AdbEnvironment:
        """启动并鉴权服务。当前运行断线后先 close，再显式发起下一次连接。"""
        with self._lock:
            if self._failure:
                raise self._failure
            if self._service is not None:
                return self._environment
            tap_ms = self._validated_tap_ms()
            adb = Adb(adb_path if adb_path is not None else resolve_adb_path(self.cfg.adb_path))
            environment = _probe_environment(adb, self.cfg)
            service = AdbService(adb)
            service.start(resolve_adb_service_jar(self.cfg.adb_service_jar))
            return self._attach(environment, service, tap_ms)

    def _call(self, cmd, **params):
        if self._failure:
            raise self._failure
        if self._service is None:
            raise AdbError("not_connected", tr("ADB 会话尚未启动，请先启动游戏"))
        try:
            return self._service.request(cmd, **params)
        except AdbError as error:
            if error.code in {"disconnected", "invalid_response"}:
                self._failure = error
            raise

    def _record_event(self, event):
        name = event["event"]
        self._events.append(event)
        if self._on_event is None:
            self.log_info(f"ADB 看门狗 {name}：{event}")
        else:
            self._on_event(event)
        if name == "watchdog_started":
            self._game_display_id = (event.get("task") or {}).get("display_id")
            self._sdk_window = bool(event.get("sdk_window"))
        elif name == "task_display_changed":
            self._game_display_id = event.get("to")
            if self._game_display_id != self._display_id:
                self._moving = False
        elif name in ("sdk_window_shown", "sdk_window_gone"):
            self._sdk_window = name == "sdk_window_shown"
        elif name == "move_back_started":
            self._moving = True
        elif name in ("move_back_succeeded", "move_back_frame_timeout", "move_back_failed"):
            self._moving = False
            if name == "move_back_succeeded":
                self._min_seq = max(self._min_seq, event.get("first_frame_seq", 0))
            elif name == "move_back_frame_timeout":
                self._min_seq = max(self._min_seq, event.get("frame_seq", 0) + 1)
            elif event.get("final"):
                self._failure = AdbError("move_back_failed", tr("游戏未能回到目标 Android 屏幕，请结束游戏后重试"))
        elif name == "manual_action_required":
            self._failure = AdbError(name, tr("游戏需要手动登录，请在 Android 实体屏或模拟器中完成登录后重试"))
        elif name == "game_exited" and (self._startup is None or not self._startup.saw_task):
            self._failure = AdbError(name, tr("Android 游戏进程已退出，请检查游戏与设备的后台设置后重试"))
        if (self._startup is not None and name in {"watchdog_started", "task_display_changed"}
                and self._game_display_id is not None):
            self._startup.saw_task = True
            self._startup.missing_since_ms = None

    def _poll_events(self, *, force=False, startup=False):
        if not self._watching or (not force and time.monotonic() - self._last_event_poll < 0.35):
            return
        response, _ = self._call("events", after=self._event_seq, **({"startup": True} if startup else {}))
        self._last_event_poll = time.monotonic()
        for event in response["events"]:
            self._record_event(event)
        self._event_seq = response["event_seq"]
        if self._failure:
            raise self._failure
        return response

    def startup_frame_snapshot(self):
        """只在虚拟屏启动检查取样，旧服务沿用原来的事件与超时处理。"""
        with self._lock:
            if not self._display_id or "startup_snapshot" not in self._service.client.hello.get("features", ()):
                return None
            try:
                response = self._poll_events(force=True, startup=True)
            except AdbError as error:
                if self._failure is not None:
                    raise
                self.log_debug(f"ADB 启动状态取样不可用：{error}")
                return None
            if not response or not self._display_available():
                return None
            snapshot = response.get("startup")
            if not isinstance(snapshot, dict) or snapshot.get("display_id") != self._display_id:
                return None
            # 两次取样之间也可能曾短暂锁屏、移走任务或弹出 SDK。
            snapshot["last_transition"] = next((event["event_seq"] for event in reversed(self._events)
                if event["event"] in {"device_state", "task_display_changed", "sdk_window_shown", "sdk_window_gone",
                                      "game_exited", "game_started", "move_back_started"}), 0)
            return snapshot

    def log_startup_evidence(self, deadline):
        """已判定故障后再读系统窗口和 SurfaceFlinger；取证失败仍返回原故障。"""
        remaining = deadline - time.monotonic()
        if remaining < 8:
            return
        try:
            with self._lock:
                result, _ = self._call("startup_evidence", timeout=8)
            for layer, fields in result.get("game_layers", {}).items():
                self.log_debug(f"ADB SurfaceFlinger {layer} {fields}")
            for key, value in result.items():
                if key not in {"id", "ok", "game_layers"}:
                    self.log_debug(f"ADB 虚拟屏系统诊断 {key}={value}")
            if not result.get("game_layers"):
                self.log_debug("ADB SurfaceFlinger 未取得游戏图层的 buffer 信息")
        except Exception as error:
            self.log_debug(f"ADB 虚拟屏系统诊断不可用：{error}")

    def get_runtime_status(self) -> AdbRuntimeStatus:
        """查询本进程的会话。未连接时不启动服务，连接故障通过 error_code 返回。"""
        with self._lock:
            watchdog = {}
            if self._service is not None and self._failure is None:
                try:
                    self._poll_events(force=True)
                    status, _ = self._call("status")
                    watchdog = status["watchdog"]
                except AdbError as error:
                    self._failure = error
            task = watchdog.get("task") or {}
            healthy = self._service is not None and not (
                self._failure and self._failure.code in {"disconnected", "invalid_response", "adb_server_restarted"}
            )
            times = self._frame_times
            fps = 0.0
            if len(times) > 1 and time.monotonic() - times[-1] < 3:
                fps = (len(times) - 1) / max(0.001, times[-1] - times[0])
            return AdbRuntimeStatus(
                healthy, self._environment.device.serial if self._environment else None,
                self._service.client.hello["version"] if healthy else None, self._display_id,
                task.get("display_id", self._game_display_id), watchdog.get("pid", -1) > 0,
                bool(watchdog.get("sdk_window")) or self._sdk_window, fps,
                self._failure.code if self._failure else None, str(self._failure) if self._failure else None,
            )

    def prepare_display(self) -> int:
        with self._lock:
            environment = self.connect()
            if self._display_id is not None:
                return self._display_id
            use_display_zero = environment.device_type == "emulator"
            if use_display_zero and environment.sdk < 34:
                if self.cfg.adb_device_type == "emulator":
                    raise AdbError("emulator_input_unsupported", tr(
                        "display 0 的触摸目标校验需要 Android 14 或更高版本，请设置 adb_device_type: physical 使用虚拟屏"
                    ))
                use_display_zero = False

            if use_display_zero:
                if sorted(environment.display_size) != sorted(RESOLUTION):
                    raise AdbError("emulator_resolution", tr(
                        "模拟器 display 0 当前为 {width}×{height}。请在模拟器设置中选择 1280×720 横屏后重试"
                    ).format(width=environment.display_size[0], height=environment.display_size[1]))
                self._display_id = 0
            else:
                response, _ = self._call("create_display", width=RESOLUTION[0], height=RESOLUTION[1], dpi=240)
                self._display_id = response["display_id"]
                self.log_debug(f"ADB 虚拟屏 display={self._display_id} size={RESOLUTION} dpi=240 "
                               f"device={self._service.client.hello.get('device')} diagnostic={response.get('diagnostic')}")
            return self._display_id

    def start_game_process(self, *, recover_startup=False) -> bool:
        with self._lock:
            display_id = self.prepare_display()
            if not self._environment.game_installed:
                raise AdbError("game_not_installed", tr("Android 设备未安装国服《崩坏：星穹铁道》"))
            if self._watching:
                self._poll_events(force=True)
                return True
            if recover_startup:
                self._startup = _GameStartup()

            # MuMu 的独立应用窗口可能把显式指定到 display 0 的启动重定向到外接屏。
            self._call("watchdog", package=GAME_PACKAGE, main_activity=_GAME_ACTIVITY, display_id=display_id,
                       auto_focus=display_id != 0 and self._environment.virtual_auto_focus, subscribe=False)
            self._call("launch", timeout=17, timeout_ms=15000, display_id=display_id,
                       component=_GAME_COMPONENT)
            self._watching = True
            self._poll_events(force=True)
            return True

    def recover_game_start(self, deadline):
        """启动期确认窗口持续消失后，在原虚拟屏补一次启动。"""
        with self._lock:
            startup = self._startup
            if startup is None or not startup.saw_task or self._game_display_id is not None:
                return
            remaining = deadline - time.monotonic()
            if remaining < 1:
                return
            response, _ = self._call("status", timeout=min(4, remaining))
            watchdog = response["watchdog"]
            if watchdog.get("task") is not None or not watchdog.get("interactive") or watchdog.get("keyguard_locked"):
                startup.missing_since_ms = None
                return
            checked = watchdog.get("task_checked_ms")
            if type(checked) is not int or checked <= 0:
                return
            if startup.missing_since_ms is None:
                startup.missing_since_ms = checked
            if checked - startup.missing_since_ms < _STARTUP_TASK_MISSING_MS:
                return
            if startup.relaunched:
                raise AdbError("game_exited", tr("重新启动后，Android 游戏窗口再次消失"))
            remaining = deadline - time.monotonic()
            if remaining < 1:
                return
            result, _ = self._call(
                "launch_if_missing", timeout=min(4, remaining), timeout_ms=min(3000, int(remaining * 1000)),
                display_id=self._display_id, component=_GAME_COMPONENT, wait=False,
            )
            startup.missing_since_ms = None
            if result["launched"]:
                startup.relaunched = True
                startup.saw_task = False
                self._min_seq = max(self._min_seq, result["seq"] + 1)
                self.log_warning("Android 游戏窗口已消失，已在原虚拟屏重新启动星铁")

    def finish_game_startup(self):
        with self._lock:
            self._startup = None

    def is_game_running(self) -> bool:
        with self._lock:
            if self._failure:
                raise self._failure
            if self._service is None:
                return False
            try:
                return self._service.is_game_running()
            except AdbError as error:
                self._failure = error
                raise

    def switch_to_game(self) -> bool:
        # 实体机上切换桌面焦点会干扰用户。虚拟屏的任务归属由看门狗保证。
        return self.is_game_running()

    def stop_game(self) -> bool:
        with self._lock:
            try:
                if self._service is not None:
                    self._service.request("stop_app", package=GAME_PACKAGE, timeout=3)
                return True
            finally:
                self.close()

    def run_script(self) -> bool:
        self.script_path = self.cfg.script_path
        return super().run_script()

    def close(self):
        with self._lock:
            try:
                if self._service is not None:
                    self._service.close()
            finally:
                self._service = None
                self._environment = None
                self._reset_display()

    def get_resolution(self):
        return RESOLUTION

    def get_window_handle(self) -> int:
        return 0

    def get_input_handler(self):
        from module.automation.adb_input import AdbInput
        with self._lock:
            if self._input is None:
                self._input = AdbInput(self)
            return self._input

    def copy(self, text: str):
        self.get_input_handler().secretly_write(text)

    def _display_available(self):
        return not (self._sdk_window or self._moving or (
            self._watching and self._game_display_id != self._display_id
        ))

    def _emulator_game_has_focus(self) -> bool:
        status, _ = self._call("status")
        task = status["watchdog"].get("task") or {}
        if (task.get("display_id") != 0 or task.get("visible") is not True
                or task.get("top_activity") != _GAME_COMPONENT):
            return False
        # 可见的游戏任务仍可能被其他窗口抢走焦点，触摸前检查 display 0 的实际窗口。
        try:
            return self._service.adb.focused_window(0) == _GAME_COMPONENT
        except AdbError as error:
            self._failure = error
            raise

    def send_input(self, command, *, timeout=4, **params):
        from module.automation.input_base import begin_input_dispatch

        with self._lock:
            action = params.get("action")
            if action in ("up", "move") and not self._pointer_down:
                return False
            if action != "up":
                if self._failure:
                    raise self._failure
                if self._display_id is None:
                    raise AdbError("no_display", tr("ADB 尚未准备游戏画面，请先启动游戏"))
                self._poll_events()
                if not self._display_available():
                    return False
                if self._display_id == 0 and not (self._landscape and self._emulator_game_has_focus()):
                    return False
            if command == "tap":
                params["duration_ms"] = self._tap_ms
                timeout += self._tap_ms / 1000
            try:
                if action == "up":
                    # SDK 迁移或手动登录期间也要允许结束已经按下的触点。
                    response, _ = self._service.request(command, display_id=self._display_id, **params)
                else:
                    pause_ctl.check_stop()
                    if not begin_input_dispatch(time.monotonic()):
                        return False
                    response, _ = self._call(command, timeout=timeout, display_id=self._display_id, **params)
            except AdbError as error:
                if error.code in _TEMPORARY_INPUT_ERRORS:
                    return False
                if error.code == "inject_denied":
                    raise AdbError(error.code, tr("Android 拒绝触摸注入，请检查 USB 调试（安全设置）是否开启")) from error
                raise
            finally:
                if action == "up":
                    self._pointer_down = False
            if not response.get("delivered"):
                return False
            if action == "down":
                self._pointer_down = True
            if self._display_id != 0:
                self._input_ns = response["input_ns"]
                self._min_seq = max(self._min_seq, self._frame_seq + 1)
            return True

    def capture_frame(self, crop=(0, 0, 1, 1), *, prefer_frame=True, fresh=False) -> FrameCapture:
        """截图等待暂时无帧时返回 False，断线和登录中断立即抛出 AdbError。"""
        with self._lock:
            if self._failure:
                raise self._failure
            if self._display_id is None:
                raise AdbError("no_display", tr("ADB 尚未准备游戏画面，请先启动游戏"))
            self._poll_events()
            if not self._display_available():
                return False
            pixels = _pixel_crop(crop)
            if self._display_id == 0:
                result = self._capture_emulator(pixels)
            else:
                result = self._capture_virtual(pixels, fresh)
            self._poll_events()
            if not result or not self._display_available():
                return False
            seq, image = result
            if seq < self._min_seq:
                return False
            if seq > self._frame_seq:
                self._frame_seq = seq
                self._frame_times.append(time.monotonic())
            return image, pixels, 1

    def _capture_virtual(self, pixels, fresh):
        min_seq = max(self._min_seq, self._frame_seq + 1 if fresh else self._frame_seq)
        params = {} if self._input_ns is None else {"after_ns": self._input_ns}
        try:
            header, payload = self._call("frame", min_seq=min_seq, timeout_ms=1000,
                                         crop=list(pixels), encoding="rgb", **params)
        except AdbError as error:
            if error.code == "timeout":
                return False
            raise
        seq = header.get("seq")
        stale = header.get("stale", False)
        if (type(seq) is not int or type(stale) is not bool or header.get("display_id") != self._display_id
                or header.get("crop") != list(pixels) or header.get("encoding") != "rgb"
                or len(payload) != pixels[2] * pixels[3] * 3):
            raise AdbError("invalid_response", tr("ADB 设备端服务返回了无效的帧"))
        if seq < min_seq or stale:
            raise AdbError("invalid_response", tr("ADB 设备端服务返回了无效的帧"), frame_only=True)
        if self._input_ns is not None:
            comparable = header.get("timestamp_comparable")
            image_ns = header.get("image_ns")
            if type(comparable) is not bool or type(image_ns) is not int:
                raise AdbError("invalid_response", tr("ADB 设备端服务返回了无效的帧"))
            if not comparable or image_ns <= self._input_ns:
                raise AdbError("invalid_response", tr("ADB 设备端服务返回了输入前的帧"), frame_only=True)
        return seq, Image.frombytes("RGB", pixels[2:], bytes(payload))

    def _capture_emulator(self, pixels):
        # S1 的 ImageReader 只接虚拟屏。screencap 在输入应答之后才启动，
        # 本地序号只统计成功的采样。是否切换界面仍由调用方检查画面。
        for attempt in range(2):
            pause_ctl.check_stop()
            try:
                data = self._read_emulator_png(refresh_display=attempt > 0)
                pause_ctl.check_stop()
                image = self._decode_emulator_png(data, pixels)
            except AdbError as error:
                self._landscape = False
                pause_ctl.check_stop()
                if attempt or error.code not in {"adb_failed", "invalid_response"}:
                    if error.code != "invalid_response":
                        self._failure = error
                    raise
            else:
                self._landscape = image is not None
                return (self._frame_seq + 1, image) if image is not None else False

            self._poll_events(force=True)
            if not self._display_available():
                return False

    def _read_emulator_png(self, *, refresh_display):
        adb = self._service.adb
        command = ("exec-out", "screencap", "-p")
        display_id = self._emulator_physical_display_id
        if display_id is None:
            data = adb.run(*command, binary=True)
            # exec-out 会把设备端警告混进 PNG。多屏时默认捕获的画面也可能来自其他屏。
            if data.startswith(_PNG_SIGNATURE) or _MULTI_DISPLAY_WARNING not in data[:512]:
                return data

        if display_id is None or refresh_display:
            pause_ctl.check_stop()
            display_id = adb.primary_physical_display_id()
            if display_id is None:
                raise AdbError("invalid_response", tr("检测到多个显示器，无法确定模拟器 display 0 对应的 SurfaceFlinger ID"))
            self._emulator_physical_display_id = display_id

        pause_ctl.check_stop()
        return adb.run(*command, "-d", display_id, binary=True)

    @staticmethod
    def _decode_emulator_png(data, pixels):
        if not data:
            raise AdbError("invalid_response", tr("模拟器 display 0 的截图输出为空"), frame_only=True)
        if not data.startswith(_PNG_SIGNATURE):
            raise AdbError("invalid_response", tr("模拟器 display 0 的截图输出不符合 PNG 格式（{size} 字节）").format(
                size=len(data),
            ), frame_only=True)
        try:
            with Image.open(BytesIO(data)) as image:
                if image.size != RESOLUTION:
                    return None
                x, y, w, h = pixels
                return image.crop((x, y, x + w, y + h)).convert("RGB")
        except (OSError, SyntaxError, Image.DecompressionBombError) as error:
            raise AdbError("invalid_response", tr("无法解码模拟器 display 0 的截图"), frame_only=True) from error
