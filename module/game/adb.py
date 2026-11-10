
"""桌面 ADB 控制器。输入、取帧和看门狗共享同一次设备会话。"""
from collections import deque
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from threading import RLock
import time

from PIL import Image

from module.config.platform import get_ui_profile
from module.game.adb_transport import (
    DEFAULT_JAR, GAME_PACKAGE, RESOLUTION, Adb, AdbEnvironment, AdbError, AdbService,
    _probe_environment, resolve_adb_path,
)
from module.game.base import FrameCapture, GameControllerBase
from module.localization import tr


_GAME_ACTIVITY = "com.mihoyo.combosdk.ComboSDKActivity"
_TEMPORARY_INPUT_ERRORS = {"game_not_on_display", "sdk_window_active"}


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
        self._display_id = None
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

    def connect(self, *, adb_path=None) -> AdbEnvironment:
        """启动并鉴权服务。当前运行断线后先 close，再显式发起下一次连接。"""
        with self._lock:
            if self._failure:
                raise self._failure
            if self._service is not None:
                return self._environment
            if get_ui_profile(self.cfg).name != "touch_720":
                raise AdbError("ui_profile", tr("ADB 后端需要设置 ui_profile: touch_720"))
            tap_ms = self.cfg.adb_tap_ms
            if tap_ms is not None and (type(tap_ms) is not int or not 1 <= tap_ms <= 10000):
                raise AdbError("tap_duration", tr("adb_tap_ms 必须是 1 到 10000 毫秒之间的整数"))
            adb = Adb(adb_path if adb_path is not None else resolve_adb_path(self.cfg.adb_path))
            environment = _probe_environment(adb, self.cfg)
            service = AdbService(adb)
            jar = Path(self.cfg.adb_service_jar or DEFAULT_JAR).expanduser().resolve()
            service.start(jar)
            self._service = service
            self._environment = environment
            self._tap_ms = tap_ms if tap_ms is not None else service.client.hello.get("default_tap_ms", 50)
            return environment

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
        self.log_info(f"ADB 看门狗 {name}：{event}")
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
        elif name == "game_exited":
            self._failure = AdbError(name, tr("Android 游戏进程已退出，请检查游戏与设备的后台设置后重试"))

    def _poll_events(self, *, force=False):
        if not self._watching or (not force and time.monotonic() - self._last_event_poll < 0.35):
            return
        response, _ = self._call("events", after=self._event_seq)
        self._last_event_poll = time.monotonic()
        for event in response["events"]:
            self._record_event(event)
        self._event_seq = response["event_seq"]
        if self._failure:
            raise self._failure

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
            if environment.device_type == "emulator":
                if sorted(environment.display_size) != sorted(RESOLUTION):
                    raise AdbError("emulator_resolution", tr(
                        "模拟器 display 0 当前为 {width}×{height}。请在模拟器设置中选择 1280×720 横屏后重试"
                    ).format(width=environment.display_size[0], height=environment.display_size[1]))
                self._display_id = 0
            else:
                response, _ = self._call("create_display", width=RESOLUTION[0], height=RESOLUTION[1], dpi=240)
                self._display_id = response["display_id"]
            return self._display_id

    def start_game_process(self) -> bool:
        with self._lock:
            display_id = self.prepare_display()
            if not self._environment.game_installed:
                raise AdbError("game_not_installed", tr("Android 设备未安装国服《崩坏：星穹铁道》"))
            if self._watching:
                self._poll_events(force=True)
                return True

            # MuMu 的独立应用窗口可能把显式指定到 display 0 的启动重定向到外接屏。
            self._call("watchdog", package=GAME_PACKAGE, main_activity=_GAME_ACTIVITY, display_id=display_id,
                       subscribe=False)
            self._call("launch", timeout=17, timeout_ms=15000, display_id=display_id,
                       component=f"{GAME_PACKAGE}/{_GAME_ACTIVITY}")
            self._watching = True
            self._poll_events(force=True)
            return True

    def is_game_running(self) -> bool:
        with self._lock:
            if self._failure:
                raise self._failure
            if self._service is None:
                return False
            try:
                return bool(self._service.adb.shell(f"pidof {GAME_PACKAGE} || true"))
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

    def send_input(self, command, *, timeout=4, **params):
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
                if not self._display_available() or (self._display_id == 0 and not self._landscape):
                    return False
            if command == "tap":
                params["duration_ms"] = self._tap_ms
                timeout += self._tap_ms / 1000
            try:
                if action == "up":
                    # SDK 迁移或手动登录期间也要允许结束已经按下的触点。
                    response, _ = self._service.request(command, display_id=self._display_id, **params)
                else:
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
        if (type(seq) is not int or seq < min_seq or header.get("stale")
                or header.get("display_id") != self._display_id
                or header.get("crop") != list(pixels) or header.get("encoding") != "rgb"
                or len(payload) != pixels[2] * pixels[3] * 3):
            raise AdbError("invalid_response", tr("ADB 设备端服务返回了无效的帧"))
        if self._input_ns is not None and (
            header.get("timestamp_comparable") is not True
            or header.get("image_ns", 0) <= self._input_ns
        ):
            raise AdbError("invalid_response", tr("ADB 设备端服务返回了输入前的帧"))
        return seq, Image.frombytes("RGB", pixels[2:], bytes(payload))

    def _capture_emulator(self, pixels):
        # S1 的 ImageReader 只接虚拟屏。screencap 在输入应答之后才启动，
        # 本地序号只统计成功的采样。是否切换界面仍由调用方检查画面。
        try:
            data = self._service.adb.run("exec-out", "screencap", "-p", binary=True)
        except AdbError as error:
            self._failure = error
            raise
        try:
            with Image.open(BytesIO(data)) as image:
                self._landscape = image.size == RESOLUTION
                if not self._landscape:
                    return False
                x, y, w, h = pixels
                return self._frame_seq + 1, image.crop((x, y, x + w, y + h)).convert("RGB")
        except OSError as error:
            raise AdbError("invalid_response", tr("无法解码模拟器 display 0 的截图")) from error
