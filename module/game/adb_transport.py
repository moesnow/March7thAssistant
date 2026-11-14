
"""ADB 设备发现、S1 服务启动和经过鉴权的传输。"""
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import time

from module.config import cfg
from module.localization import tr
from module.logger import log


GAME_PACKAGE = "com.miHoYo.hkrpg"
RESOLUTION = (1280, 720)
PROTOCOL = 1
SERVICE_VERSION = "0.1.1"
DEFAULT_JAR = Path("assets/binary/m7a-device-service.jar")
_DEVELOPMENT_JAR = Path("Android/device-service/build/outputs/m7a-device-service.jar")
_MAIN_CLASS = "org.march7th.deviceservice.Main"
_REMOTE_DIR = "/data/local/tmp"
_IDLE_SECONDS = 8
_SHUTDOWN_TIMEOUT_SECONDS = 9
_START_TIMEOUT_SECONDS = 10
_BUSY_TIMEOUT_SECONDS = _IDLE_SECONDS + _SHUTDOWN_TIMEOUT_SECONDS
_BUSY_RETRY_SECONDS = 0.4
_NETWORK_SERIAL = re.compile(r"(?:\[[^\]]+\]|[^:\s]+):\d{1,5}")
_ADB_RESTART = re.compile(r"server version.*(?:doesn.t match|mismatch)|restart(?:ing|ed).*daemon", re.I)
_ADB_DISCONNECT = re.compile(r"device (?:offline|disconnected|unauthorized|not found)|device .* not found|"
                             r"no devices/emulators found|(?:transport|connection) (?:is )?closed", re.I)


class AdbError(RuntimeError):
    """ADB 操作失败。界面按 code 判断原因，str(error) 用于显示。"""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def disconnected():
    return AdbError("disconnected", tr("ADB 设备或设备端服务已断开，请重新连接后再运行"))


@dataclass(frozen=True)
class AdbDevice:
    serial: str
    state: str
    model: str | None


@dataclass(frozen=True)
class AdbTouchInjectionStatus:
    """allowed 为 None 时无法确认权限。MIUI 安全设置未知或不适用时，第二项为 None。"""

    allowed: bool | None
    usb_debugging_security_enabled: bool | None = None


@dataclass(frozen=True)
class AdbEnvironment:
    adb_path: Path | None
    device: AdbDevice
    sdk: int
    android_version: str
    device_type: str
    display_size: tuple[int, int]
    game_installed: bool
    virtual_auto_focus: bool = False

    def check_touch_injection(self) -> AdbTouchInjectionStatus:
        """读取当前设备的 shell 注入权限和 MIUI 安全设置。无法判断时 allowed 为 None。"""
        if self.adb_path is None:
            return AdbTouchInjectionStatus(None)
        try:
            output = Adb(self.adb_path, self.device.serial).shell(
                'echo "miui=$(getprop ro.miui.ui.version.name)"; '
                'echo "adbinput=$(getprop persist.security.adbinput)"; '
                'dumpsys package com.android.shell | grep "android.permission.INJECT_EVENTS: granted" || true',
                timeout=8,
            )
        except AdbError:
            return AdbTouchInjectionStatus(None)

        values = dict(line.split("=", 1) for line in output.splitlines() if line.startswith(("miui=", "adbinput=")))
        security_enabled = values.get("adbinput") == "1" if values.get("miui") else None
        if security_enabled is False:
            return AdbTouchInjectionStatus(False, False)
        grants = re.findall(r"INJECT_EVENTS: granted=(true|false)", output)
        allowed = "true" in grants if grants else security_enabled
        return AdbTouchInjectionStatus(allowed, security_enabled)


def managed_adb_directory() -> Path:
    base = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
    return Path(base) / "March7thAssistant" / "PlatformTools"


def find_managed_adb() -> Path | None:
    """查找校验后安装的 adb。临时下载目录不会被选中。"""
    for directory in sorted(managed_adb_directory().glob("platform-tools-*"), reverse=True):
        path = directory / "adb.exe"
        if path.is_file():
            return path.resolve()
    return None


def resolve_adb_path(adb_path=None) -> Path:
    configured = None
    if adb_path:
        configured = Path(adb_path).expanduser().resolve()
        if configured.is_file():
            return configured
    # Windows 上手动路径失效时，可以继续使用本机的其他 adb。
    if configured is not None and os.name != "nt":
        raise AdbError("adb_not_found", tr("配置的 adb_path 不存在：{path}").format(path=configured))
    if executable := shutil.which("adb"):
        return Path(executable).resolve()
    if os.name == "nt":
        candidates = (
            "Netease/MuMuPlayerGlobal-12.0/shell/adb.exe",
            "Netease/MuMuPlayer-12.0/shell/adb.exe",
            "Netease/MuMuPlayer-12.0/nx_main/adb.exe",
            "BlueStacks_nxt/HD-Adb.exe",
            "Nox/bin/adb.exe",
            "Microvirt/MEmu/adb.exe",
        )
        for directory in ("ProgramFiles", "ProgramFiles(x86)"):
            if root := os.environ.get(directory):
                for name in candidates:
                    path = Path(root) / name
                    if path.is_file():
                        return path.resolve()
        sdk_roots = [
            os.environ.get("ANDROID_HOME"),
            os.environ.get("ANDROID_SDK_ROOT"),
            managed_adb_directory().parent.parent / "Android" / "Sdk",
        ]
        for root in filter(None, sdk_roots):
            path = Path(root) / "platform-tools" / "adb.exe"
            if path.is_file():
                return path.resolve()
        if path := find_managed_adb():
            return path
    if configured is not None:
        raise AdbError("adb_not_found", tr("配置的 adb_path 不存在：{path}").format(path=configured))
    raise AdbError("adb_not_found", tr("未找到 adb"))


def resolve_adb_service_jar(configured_path: str | Path | None = None) -> Path:
    """优先使用配置中的路径，其次使用随包 JAR 和源码构建产物。"""
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    for jar in (DEFAULT_JAR, _DEVELOPMENT_JAR):
        if jar.is_file():
            return jar.resolve()
    # 两处都缺文件时，返回当前运行形态预期的路径，由服务启动报告错误。
    return (DEFAULT_JAR if getattr(sys, "frozen", False) else _DEVELOPMENT_JAR).resolve()


class Adb:
    def __init__(self, path: Path, serial: str | None = None):
        self.path = path
        self.serial = serial

    def run(self, *args: str, timeout: float = 5, binary: bool = False) -> str | bytes:
        command = [str(self.path)]
        if self.serial:
            command.extend(("-s", self.serial))
        try:
            result = subprocess.run(
                [*command, *args], capture_output=True, timeout=timeout,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired as error:
            if self.serial:
                raise disconnected() from error
            raise AdbError("adb_timeout", tr("ADB 命令超时：{command}").format(command=args[0])) from error
        except OSError as error:
            raise AdbError("adb_failed", tr("无法执行 adb：{path}").format(path=self.path)) from error

        stdout = result.stdout.decode("utf-8", errors="replace") if not binary or result.returncode else ""
        output = (result.stderr.decode("utf-8", errors="replace") + "\n" + stdout).strip()
        if _ADB_RESTART.search(output):
            raise AdbError("adb_server_restarted", tr(
                "ADB 服务端被其他版本重启。请关闭模拟器自带的 adb，并固定使用 {path}"
            ).format(path=self.path))
        if "* daemon not running" in output.lower():
            log.info(f"ADB 服务端由 {self.path} 启动")
        if result.returncode:
            if _ADB_DISCONNECT.search(output):
                raise disconnected()
            # 不输出命令参数。启动设备服务的命令行含令牌。
            raise AdbError("adb_failed", tr("ADB 命令失败：{command}（退出码 {code}）").format(
                command=args[0], code=result.returncode
            ))
        return result.stdout if binary else stdout.strip()

    def shell(self, command: str, *, timeout: float = 5) -> str:
        return self.run("shell", command, timeout=timeout)

    def focused_window(self, display_id: int) -> str | None:
        output = self.shell("dumpsys -t 2 window displays", timeout=3)
        on_display = False
        for line in output.splitlines():
            if display := re.match(r"\s*Display: mDisplayId=(\d+)\b", line):
                on_display = int(display[1]) == display_id
            elif on_display and line.lstrip().startswith("mCurrentFocus="):
                window = re.match(r"\s*mCurrentFocus=Window\{\S+\s+u\d+\s+([^\s}]+)\}", line)
                return window[1] if window else None
        return None

    def devices(self) -> list[AdbDevice]:
        devices = []
        for line in self.run("devices", "-l").splitlines():
            fields = line.split()
            if len(fields) < 2 or line.startswith(("List of devices", "*")):
                continue
            serial, state, *details = fields
            model = next((field[6:].replace("_", " ") for field in details if field.startswith("model:")), None)
            devices.append(AdbDevice(serial, state, model))
        return devices


def list_adb_devices(adb_path=None) -> list[AdbDevice]:
    """列出 adb 已知的设备，保留未授权和离线状态。"""
    return Adb(resolve_adb_path(adb_path)).devices()


def check_adb_environment(config=None) -> AdbEnvironment:
    """检查指定设备的连接、系统、显示尺寸及游戏安装。配置网络地址时连接 ADB。"""
    config = cfg if config is None else config
    return _probe_environment(Adb(resolve_adb_path(config.adb_path)), config)


def _probe_environment(adb: Adb, config) -> AdbEnvironment:
    serial = str(config.adb_serial or "").strip()
    devices = adb.devices()
    device = next((item for item in devices if item.serial == serial), None)
    if _NETWORK_SERIAL.fullmatch(serial) and (device is None or device.state == "offline"):
        adb.run("connect", serial)
        devices = adb.devices()
        device = next((item for item in devices if item.serial == serial), None)
    if not serial:
        if len(devices) > 1:
            raise AdbError("multiple_devices", tr("检测到多个 ADB 设备，请设置 adb_serial"))
        device = devices[0] if devices else None
    if device is None:
        raise AdbError("device_not_found", tr("未找到指定的 ADB 设备，请检查连接和 adb_serial"))
    if device.state != "device":
        raise AdbError("device_not_ready", tr(
            "ADB 设备 {serial} 的状态为 {state}，请检查连接并在设备上授权 USB 调试"
        ).format(serial=device.serial, state=device.state))

    adb.serial = device.serial
    props = ("ro.build.version.sdk", "ro.build.version.release", "ro.product.cpu.abilist",
             "ro.kernel.qemu", "ro.boot.qemu", "ro.product.model")
    output = adb.shell("; ".join(f'echo "{key}=$(getprop {key})"' for key in props))
    values = dict(line.split("=", 1) for line in output.splitlines() if "=" in line)
    sdk = values.get("ro.build.version.sdk", "")
    if not sdk.isdigit() or int(sdk) < 29:
        raise AdbError("android_version", tr("ADB 后端需要 Android 10 或更高版本"))
    device = AdbDevice(device.serial, device.state, values.get("ro.product.model") or device.model)

    device_type = config.adb_device_type or "auto"
    if device_type not in ("auto", "physical", "emulator"):
        raise AdbError("device_type", tr("adb_device_type 必须为 auto、physical 或 emulator"))
    emulator_serial = device.serial.startswith("emulator-")
    loopback = device.serial.startswith(("127.0.0.1:", "localhost:", "[::1]:"))
    x86 = bool({"x86", "x86_64"}.intersection(values.get("ro.product.cpu.abilist", "").split(",")))
    qemu = any(values.get(key) == "1" for key in ("ro.kernel.qemu", "ro.boot.qemu"))
    if device_type == "auto":
        device_type = "emulator" if emulator_serial or loopback or x86 or qemu else "physical"
    # 回环地址可能是转发过来的实体机。切焦点还需要 x86 架构或模拟器的系统标记。
    virtual_auto_focus = emulator_serial or qemu or (loopback and x86)

    sizes = re.findall(r"(?:Physical|Override) size: (\d+)x(\d+)", adb.shell("wm size"))
    if not sizes:
        raise AdbError("display_size", tr("无法读取 Android display 0 的分辨率"))
    width, height = map(int, sizes[-1])
    # pm path 未安装时返回 1。列出匹配的包则在两种情况下都能读到状态。
    packages = adb.shell(f"pm list packages {GAME_PACKAGE}").splitlines()
    return AdbEnvironment(adb.path, device, int(sdk), values.get("ro.build.version.release", ""),
                          device_type, (width, height), f"package:{GAME_PACKAGE}" in packages, virtual_auto_focus)


class ServiceClient:
    """一条串行的 S1 连接。事件走 events 命令，避免服务端推送堵塞。"""

    def __init__(self, port: int, token: str):
        self._id = 0
        try:
            self._socket = socket.create_connection(("127.0.0.1", port), timeout=2)
        except OSError as error:
            raise disconnected() from error
        try:
            self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.hello, _ = self.request("hello", protocol=PROTOCOL, token=token, events=False)
        except BaseException:
            self.close()
            raise

    @property
    def closed(self):
        return self._socket.fileno() < 0

    def close(self):
        self._socket.close()

    def _read(self, size: int, deadline: float) -> bytearray:
        data = bytearray(size)
        view = memoryview(data)
        while view:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            self._socket.settimeout(remaining)
            received = self._socket.recv_into(view)
            if not received:
                raise EOFError
            view = view[received:]
        return data

    def request(self, cmd: str, *, timeout: float = 4, **params) -> tuple[dict, bytearray]:
        self._id += 1
        message = json.dumps({"id": self._id, "cmd": cmd, **params}, allow_nan=False).encode("utf-8")
        deadline = time.monotonic() + timeout
        try:
            self._socket.settimeout(timeout)
            self._socket.sendall(struct.pack(">II", len(message), 0) + message)
            header_size, payload_size = struct.unpack(">II", self._read(8, deadline))
            if not 0 < header_size <= 1 << 20 or payload_size > 64 << 20:
                raise ValueError("invalid message size")
            header = json.loads(self._read(header_size, deadline))
            if not isinstance(header, dict) or header.get("id") != self._id or type(header.get("ok")) is not bool:
                raise ValueError("invalid response")
            if not header["ok"] and not isinstance(header.get("error"), dict):
                raise ValueError("invalid error response")
            payload = self._read(payload_size, deadline)
        except (OSError, EOFError) as error:
            self.close()
            raise disconnected() from error
        except ValueError as error:
            self.close()
            raise AdbError("invalid_response", tr("ADB 设备端服务返回了无效的响应")) from error

        if not header["ok"]:
            error = header.get("error") or {}
            code = error.get("code", "unknown")
            raise AdbError(code, tr("ADB 设备端服务错误 {code}：{message}").format(
                code=code, message=error.get("message", "")
            ))
        return header, payload


def check_service_hello(hello):
    if hello.get("protocol") != PROTOCOL:
        raise AdbError("protocol_mismatch", tr("ADB 设备端协议版本不匹配"))
    if hello.get("version") != SERVICE_VERSION or "frame_after_ns" not in hello.get("features", ()):
        raise AdbError("service_version", tr("ADB 设备端服务版本不匹配，请检查 JAR"))


class AdbService:
    """一份 JAR、一个设备和一个仅本次运行持有的端口转发。"""

    def __init__(self, adb: Adb):
        self.adb = adb
        self.port = None
        self.client = None
        self.log_path = None
        self.token = None
        self.pid = None

    def start(self, jar: Path):
        try:
            digest = sha256(jar.read_bytes()).hexdigest()
        except OSError as error:
            raise AdbError("jar_not_found", tr(
                "无法读取设备端 JAR：{path}。请先构建 Android/device-service 或配置 adb_service_jar"
            ).format(path=jar)) from error
        remote_jar = f"{_REMOTE_DIR}/m7a-device-service-{digest}.jar"
        for attempt in range(2):
            try:
                self._start(jar, remote_jar, digest, force_push=attempt > 0)
                return
            except BaseException as error:
                retry = isinstance(error, AdbError) and error.code in ("protocol_mismatch", "service_version")
                self.close()
                if not retry or attempt:
                    raise
                log.warning("ADB 设备端版本不匹配，重新推送 JAR")
                if error.code == "protocol_mismatch":
                    # 旧协议拒绝握手，由其空闲超时释放实例锁。
                    time.sleep(_IDLE_SECONDS + 0.5)

    def _start(self, jar: Path, remote_jar: str, digest: str, *, force_push: bool):
        name = f"m7a-a1-{secrets.token_hex(8)}"
        current = self.adb.shell(f"if [ -f {remote_jar} ]; then sha256sum {remote_jar}; fi")
        if force_push or current.partition(" ")[0] != digest:
            staging = f"{_REMOTE_DIR}/{name}.jar"
            self.adb.run("push", str(jar), staging, timeout=10)
            self.adb.shell(f"mv {staging} {remote_jar}")

        self.token = secrets.token_urlsafe(32)
        self.log_path = f"{_REMOTE_DIR}/{name}.log"
        command = (
            f": > {self.log_path}; CLASSPATH={remote_jar} setsid nohup app_process / {_MAIN_CLASS} "
            f"--token {self.token} --socket {name} --idle-timeout {_IDLE_SECONDS} --no-replace "
            f"> {self.log_path} 2>&1 < /dev/null &"
        )
        self.pid = self._launch_process(command, name)

        port = self.adb.run("forward", "tcp:0", f"localabstract:{name}")
        if not port.isdigit() or not 0 < int(port) <= 65535:
            raise AdbError("forward_failed", tr("ADB 端口转发未返回有效端口"))
        self.port = int(port)
        self.client = ServiceClient(self.port, self.token)
        check_service_hello(self.client.hello)
        if "keep_awake" not in self.client.hello.get("features", ()):
            log.warning("ADB 设备端 JAR 不支持运行保活，请更新或重新构建 JAR")
            return
        try:
            self.request("keep_awake", on=True)
        except AdbError as error:
            if self.client.closed:
                raise
            log.warning(f"未能请求 Android 保持唤醒：{error}")
        else:
            log.info("已请求 Android 在 ADB 会话期间保持唤醒")

    def _launch_process(self, command: str, name: str) -> int:
        started = time.monotonic()
        deadline = started + _START_TIMEOUT_SECONDS
        busy = False
        while (remaining := deadline - time.monotonic()) > 0:
            self.adb.shell(command, timeout=min(5, remaining))
            while (remaining := deadline - time.monotonic()) > 0:
                output = self.adb.shell(f"cat {self.log_path} 2>/dev/null || true", timeout=min(5, remaining))
                if ready := re.search(rf"^M7A_DEVICE_SERVICE_READY .* socket={name} pid=([1-9]\d*)$", output, re.M):
                    return int(ready[1])
                if "another instance or its cleanup" in output:
                    busy = True
                    deadline = started + _BUSY_TIMEOUT_SECONDS
                    time.sleep(min(_BUSY_RETRY_SECONDS, max(0, deadline - time.monotonic())))
                    break
                time.sleep(min(0.15, max(0, deadline - time.monotonic())))
        if busy:
            raise AdbError("service_busy", tr("设备端服务已被占用或仍在清理，请稍后重试"))
        raise AdbError("service_start", tr("ADB 设备端服务启动超时"))

    def request(self, cmd, **params):
        return self.client.request(cmd, **params)

    def is_game_running(self):
        return bool(self.adb.shell(f"pidof {GAME_PACKAGE} || true"))

    def _wait_for_exit(self, pid: int):
        deadline = time.monotonic() + _SHUTDOWN_TIMEOUT_SECONDS
        while (remaining := deadline - time.monotonic()) > 0:
            stat = self.adb.shell(f"cat /proc/{pid}/stat 2>/dev/null || true", timeout=min(2, remaining))
            state = stat.rpartition(") ")[2].partition(" ")[0]
            if not stat or state in {"Z", "X"}:
                return
            time.sleep(min(0.1, max(0, deadline - time.monotonic())))
        log.warning(f"ADB 设备端服务 {pid} 未在限时内退出")

    def close(self):
        """收到 shutdown 应答后等待实例锁随进程释放。断线时由 S1 空闲超时清理。"""
        try:
            if self.port is not None:
                try:
                    if self.client is None or self.client.closed:
                        self.client = ServiceClient(self.port, self.token)
                    self.request("shutdown", timeout=2)
                    if self.pid is not None:
                        self._wait_for_exit(self.pid)
                except AdbError:
                    pass
        finally:
            if self.client is not None:
                self.client.close()
                self.client = None
            if self.port is not None:
                try:
                    self.adb.run("forward", "--remove", f"tcp:{self.port}", timeout=2)
                except AdbError:
                    pass
                self.port = None
            if self.log_path is not None:
                try:
                    self.adb.shell(f"rm -f {self.log_path}", timeout=2)
                except AdbError:
                    pass
                self.log_path = None
            self.token = None
            self.pid = None
