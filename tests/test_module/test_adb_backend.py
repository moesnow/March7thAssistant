
"""ADB 后端协议测试。只使用本地 TCP 和假的 adb，不启动 Android。"""
from io import BytesIO
import json
from pathlib import Path
import re
import socketserver
import struct
from subprocess import CompletedProcess
from threading import Thread
from types import SimpleNamespace

from PIL import Image
import pytest

from module.game import adb as backend
from module.game import adb_transport as transport


class FakeS1(socketserver.ThreadingTCPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), Handler)
        self.token = "test-token-for-device-service"
        self.protocol = 1
        self.version = "0.1.1"
        self.display_id = 42
        self.task_visible = True
        self.target_mismatch = False
        self.top_activity = f"{transport.GAME_PACKAGE}/com.mihoyo.combosdk.ComboSDKActivity"
        self.launch_display_id = None
        self.sequence = 8
        self.image_ns = 400
        self.events = []
        self.requests = []
        self.drop_command = None
        self.ignore_boundary = False
        self.hello_versions = []

    def event(self, name, **details):
        self.events.append(dict(event=name, event_seq=len(self.events) + 1, **details))

    def reply(self, header):
        cmd = header["cmd"]
        if cmd == "hello":
            if header["token"] != self.token:
                return None
            if header["protocol"] != self.protocol:
                return {"error": {"code": "protocol_mismatch"}}, b""
            version = self.hello_versions.pop(0) if self.hello_versions else self.version
            return dict(protocol=self.protocol, version=version, features=["frame_after_ns"], default_tap_ms=50), b""
        if cmd == "create_display":
            return dict(display_id=self.display_id), b""
        if cmd == "watchdog":
            self.display_id = header["display_id"]
            return {}, b""
        if cmd == "launch":
            target = self.display_id if self.launch_display_id is None else self.launch_display_id
            self.event("task_display_changed", to=target)
            return {}, b""
        if cmd == "events":
            return dict(events=self.events[header["after"]:], event_seq=len(self.events)), b""
        if cmd == "status":
            return dict(watchdog=dict(pid=12, task={
                "display_id": self.display_id, "visible": self.task_visible, "top_activity": self.top_activity,
            })), b""
        if cmd in ("tap", "swipe", "touch"):
            if self.target_mismatch:
                return {"error": {"code": "inject_failed", "message": "target UID mismatch"}}, b""
            return dict(delivered=True, seq=self.sequence + 1, input_ns=500), b""
        if cmd == "frame":
            x, y, width, height = header["crop"]
            if not self.ignore_boundary and (
                self.sequence < header["min_seq"] or self.image_ns <= header.get("after_ns", 0)
            ):
                return {"error": {"code": "timeout"}}, b""
            return dict(seq=self.sequence, display_id=self.display_id, crop=[x, y, width, height],
                        encoding="rgb", timestamp_comparable=True, image_ns=self.image_ns), b"\x12\x34\x56" * (width * height)
        assert cmd in ("shutdown", "stop_app")
        return {}, b""


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        with self.request.makefile("rb") as reader:
            while prefix := reader.read(8):
                header_len, payload_len = struct.unpack(">II", prefix)
                assert payload_len == 0
                request = json.loads(reader.read(header_len))
                self.server.requests.append(request)
                if request["cmd"] == self.server.drop_command:
                    return
                result = self.server.reply(request)
                if result is None:
                    return
                fields, payload = result
                header = json.dumps(dict(id=request["id"], ok="error" not in fields, **fields)).encode()
                # 将长度与头、负载分开写，和真实 TCP 的分段一样。
                self.request.sendall(struct.pack(">II", len(header), len(payload)))
                self.request.sendall(header + payload)


class FakeAdb(transport.Adb):
    def __init__(self, service):
        super().__init__(Path("adb"))
        self.service = service
        self.name = None
        self.pushes = 0
        self.forwarding = False
        self.devices_found = [transport.AdbDevice("usb-serial", "device", "Redmi Note 7")]
        self.display_size = "1080x2340"
        self.sdk = 29
        self.abis = "arm64-v8a"
        self.calls = []
        self.image = None
        self.focus_output = (
            f"  Display: mDisplayId=0 rootTasks=1\n"
            f"  mCurrentFocus=Window{{123abc u0 {service.top_activity}}}"
        )
        self.exit_probes = 0
        self.exit_checks_remaining = 0
        self.start_busy = False
        self.busy_launches_remaining = 0
        self.launch_attempts = 0

    def devices(self):
        return self.devices_found

    def run(self, *args, **kwargs):
        self.calls.append(args)
        if args[0] == "push":
            self.pushes += 1
            return ""
        if args[0] == "connect":
            self.devices_found = [transport.AdbDevice(args[1], "device", "M2007J17C")]
            return "connected"
        if args[:2] == ("forward", "tcp:0"):
            self.forwarding = True
            return str(self.service.server_address[1])
        if args[:2] == ("forward", "--remove"):
            self.forwarding = False
            return ""
        if args[:2] == ("exec-out", "screencap"):
            output = BytesIO()
            self.image.save(output, format="PNG")
            return output.getvalue()
        raise AssertionError(args)

    def shell(self, command, **kwargs):
        if command.startswith("echo "):
            return "\n".join((f"ro.build.version.sdk={self.sdk}", f"ro.build.version.release={self.sdk - 19}",
                              f"ro.product.cpu.abilist={self.abis}", "ro.kernel.qemu=", "ro.boot.qemu="))
        if command == "wm size":
            return f"Physical size: {self.display_size}"
        if command.startswith("pm list packages"):
            return f"package:{transport.GAME_PACKAGE}"
        if command.startswith(("if [ -f ", "mv ", "rm -f ", "pidof ")):
            return ""
        if command == "dumpsys -t 2 window displays":
            return self.focus_output
        if command.startswith("cat /proc/"):
            assert command == "cat /proc/128/stat 2>/dev/null || true"
            self.exit_probes += 1
            if self.exit_checks_remaining > 0:
                self.exit_checks_remaining -= 1
                return "128 (m7a-device-service) S 1 128 128"
            return ""
        if command.startswith(": > ") and "CLASSPATH=" in command:
            self.launch_attempts += 1
            self.start_busy = self.busy_launches_remaining > 0 or (
                self.name is not None and self.exit_checks_remaining > 0
            )
            if self.busy_launches_remaining > 0:
                self.busy_launches_remaining -= 1
            self.service.token = re.search(r"--token ([\w-]+)", command)[1]
            self.name = re.search(r"--socket ([\w-]+)", command)[1]
            assert "--no-replace" in command
            return ""
        if command.startswith("cat "):
            if self.start_busy:
                return "another instance or its cleanup is still running"
            return f"M7A_DEVICE_SERVICE_READY protocol=1 version={self.service.version} socket={self.name} pid=128"
        raise AssertionError(command)


@pytest.fixture
def s1():
    with FakeS1() as server:
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join()


@pytest.fixture
def adb(s1, monkeypatch, tmp_path):
    jar = tmp_path / "service.jar"
    jar.write_bytes(b"dummy dex")
    config = SimpleNamespace(ui_profile="touch_720", adb_path=None, adb_serial=None,
                             adb_device_type="auto", adb_service_jar=jar, adb_tap_ms=None)
    fake_adb = FakeAdb(s1)
    monkeypatch.setattr(backend, "resolve_adb_path", lambda path: fake_adb.path)
    monkeypatch.setattr(backend, "Adb", lambda path: fake_adb)
    controller = backend.AdbGameController(config)
    try:
        yield controller, fake_adb
    finally:
        controller.close()


def test_authentication_and_protocol(s1):
    port = s1.server_address[1]
    with pytest.raises(transport.AdbError) as error:
        transport.ServiceClient(port, "incorrect")
    assert error.value.code == "disconnected"
    s1.protocol += 1
    with pytest.raises(transport.AdbError) as error:
        transport.ServiceClient(port, s1.token)
    assert error.value.code == "protocol_mismatch"
    s1.protocol -= 1
    client = transport.ServiceClient(port, s1.token)
    try:
        assert client.hello["version"] == s1.version
        assert s1.requests[-1]["cmd"] == "hello"
    finally:
        client.close()


@pytest.mark.parametrize("miui, switch, granted, expected", [
    ("V125", "1", "true", (True, True)),
    ("V125", "0", "true", (False, False)),
    ("V125", "1", "false", (False, True)),
    ("V125", "1", None, (True, True)),
    ("", "", "true", (True, None)),
    ("", "", "false", (False, None)),
    ("", "", None, (None, None)),
])
def test_environment_checks_touch_injection(monkeypatch, miui, switch, granted, expected):
    adb_path = Path("adb")
    device = transport.AdbDevice("selected-serial", "device", None)
    environment = transport.AdbEnvironment(adb_path, device, 32, "12", "physical", (720, 1280), True)

    def shell(adb, command, *, timeout):
        assert (adb.path, adb.serial) == (adb_path, device.serial)
        assert "getprop persist.security.adbinput" in command
        assert "dumpsys package com.android.shell" in command
        assert timeout == 8
        grant = f"\n      android.permission.INJECT_EVENTS: granted={granted}" if granted else ""
        return f"miui={miui}\nadbinput={switch}{grant}"

    monkeypatch.setattr(transport.Adb, "shell", shell)
    assert environment.check_touch_injection() == transport.AdbTouchInjectionStatus(*expected)


@pytest.mark.parametrize("adb_path", [None, Path("adb")])
def test_environment_reports_unknown_if_permission_cannot_be_read(monkeypatch, adb_path):
    def disconnected(*args, **kwargs):
        raise transport.AdbError("disconnected", "设备已断开")

    device = transport.AdbDevice("selected-serial", "device", None)
    environment = transport.AdbEnvironment(adb_path, device, 32, "12", "physical", (720, 1280), True)
    monkeypatch.setattr(transport.Adb, "shell", disconnected)
    assert environment.check_touch_injection() == transport.AdbTouchInjectionStatus(None)


@pytest.mark.parametrize("bundled, override, expected", [
    (True, True, "service.jar"),
    (True, False, "assets/binary/m7a-device-service.jar"),
    (False, False, "Android/device-service/build/outputs/m7a-device-service.jar"),
])
def test_connect_selects_service_jar(adb, tmp_path, monkeypatch, bundled, override, expected):
    controller, fake = adb
    monkeypatch.chdir(tmp_path)
    development = tmp_path / "Android/device-service/build/outputs/m7a-device-service.jar"
    development.parent.mkdir(parents=True)
    development.write_bytes(b"development")
    if bundled:
        installed = tmp_path / "assets/binary/m7a-device-service.jar"
        installed.parent.mkdir(parents=True)
        installed.write_bytes(b"bundled")
    if not override:
        controller.cfg.adb_service_jar = None

    controller.connect()
    assert [Path(args[1]) for args in fake.calls if args[0] == "push"] == [(tmp_path / expected).resolve()]


def test_missing_configured_service_jar_does_not_fall_back(adb, tmp_path, monkeypatch):
    controller, fake = adb
    monkeypatch.chdir(tmp_path)
    bundled = tmp_path / "assets/binary/m7a-device-service.jar"
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(b"bundled")
    controller.cfg.adb_service_jar = "missing.jar"

    with pytest.raises(transport.AdbError) as raised:
        controller.connect()
    assert raised.value.code == "jar_not_found"
    assert str((tmp_path / "missing.jar").resolve()) in str(raised.value)
    assert fake.pushes == 0


def test_version_mismatch_repushes_and_reconnects(adb, s1):
    controller, fake = adb
    s1.hello_versions = ["0.1.0", "0.1.1"]
    controller.connect()
    assert fake.pushes == 2
    tokens = [request["token"] for request in s1.requests if request["cmd"] == "hello"]
    assert len(set(tokens)) == 2
    controller.close()
    assert not fake.forwarding
    assert [request["cmd"] for request in s1.requests].count("shutdown") == 2


def test_crop_and_strict_sequence_after_input(adb, s1):
    controller, _ = adb
    controller.start_game_process()
    crop = (0.25, 0.25, 0.5, 0.5)
    image, position, scale = controller.capture_frame(crop)
    assert image.mode == "RGB"
    assert image.size == (640, 360)
    assert image.getpixel((0, 0)) == (0x12, 0x34, 0x56)
    assert position == (320, 180, 640, 360)
    assert scale == 1
    assert controller.get_input_handler().mouse_click(38, 59)

    assert controller.capture_frame(crop) is False
    assert s1.requests[-1]["min_seq"] == 9
    assert s1.requests[-1]["after_ns"] == 500
    s1.sequence, s1.image_ns = 9, 499
    assert controller.capture_frame(crop) is False
    s1.image_ns = 501
    assert controller.capture_frame(crop)
    assert controller.capture_frame(crop, fresh=True) is False
    assert s1.requests[-1]["min_seq"] == 10

    s1.ignore_boundary = True
    s1.image_ns = 490
    with pytest.raises(transport.AdbError, match="输入前"):
        controller.capture_frame(crop)


def test_touch_mapping_and_release(adb, s1):
    controller, _ = adb
    controller.cfg.adb_tap_ms = 65
    controller.start_game_process()
    inputs = controller.get_input_handler()
    assert inputs.mouse_click(38, 59)
    assert inputs.mouse_down(10, 20)
    assert inputs.mouse_move(30, 40)
    inputs.release_all()
    inputs.release_all()
    assert inputs.mouse_drag(15, 25, 200, 400, duration=0.6, end_pause=0.2, repeats=2)
    with pytest.raises(transport.AdbError) as error:
        inputs.secretly_write("ignored")
    assert error.value.code == "text_unsupported"

    commands = [r for r in s1.requests if r["cmd"] in ("tap", "touch", "swipe")]
    assert [r["cmd"] for r in commands] == ["tap", "touch", "touch", "touch", "swipe", "swipe"]
    assert all(r["display_id"] == 42 for r in commands)
    assert (commands[0]["x"], commands[0]["y"], commands[0]["duration_ms"]) == (38, 59, 65)
    assert [r["action"] for r in commands[1:4]] == ["down", "move", "up"]
    assert commands[-1]["points"] == [[15, 25], [200, 400]]
    assert commands[-1]["duration_ms"] == 600
    assert [r["hold_end_ms"] for r in commands[-2:]] == [0, 200]


def test_disconnect_aborts_without_replaying_input_and_next_run_reconnects(adb, s1):
    controller, fake = adb
    controller.start_game_process()
    s1.drop_command = "tap"
    with pytest.raises(transport.AdbError) as error:
        controller.get_input_handler().mouse_click(38, 59)
    assert error.value.code == "disconnected"
    with pytest.raises(transport.AdbError):
        controller.capture_frame()
    assert not controller.get_runtime_status().connected

    controller.close()
    assert not fake.forwarding
    s1.drop_command = None
    controller.start_game_process()
    assert controller.capture_frame()
    assert sum(request["cmd"] == "tap" for request in s1.requests) == 1


def test_watchdog_blocks_input_until_recovered_and_stops_on_manual_login(adb, s1):
    controller, _ = adb
    controller.start_game_process()
    s1.event("task_display_changed", to=0)
    s1.event("sdk_window_shown", display_id=0)
    assert controller.get_runtime_status().sdk_window
    assert controller.capture_frame() is False
    assert controller.get_input_handler().mouse_click(38, 59) is False
    assert all(request["cmd"] != "tap" for request in s1.requests)

    s1.event("sdk_window_gone")
    s1.event("task_display_changed", to=42)
    s1.event("move_back_succeeded", first_frame_seq=10)
    controller.get_runtime_status()
    assert controller.capture_frame() is False
    assert s1.requests[-1]["min_seq"] == 10

    s1.event("manual_action_required", display_id=0)
    assert controller.get_runtime_status().error_code == "manual_action_required"
    with pytest.raises(transport.AdbError, match="手动登录"):
        controller.capture_frame()


def test_emulator_network_address_uses_display_zero_and_checks_actual_orientation(adb, s1):
    controller, fake = adb
    controller.cfg.adb_serial = "127.0.0.1:16384"
    fake.sdk = 34
    fake.display_size = "720x1280"
    environment = controller.connect()
    assert environment.device_type == "emulator"
    assert ("connect", controller.cfg.adb_serial) in fake.calls
    s1.launch_display_id = 8
    controller.start_game_process()
    assert controller.capture_frame() is False
    watchdog = next(request for request in s1.requests if request["cmd"] == "watchdog")
    assert watchdog["display_id"] == 0
    assert watchdog.get("auto_move_back", True) is True
    s1.event("task_display_changed", to=0)
    s1.event("move_back_succeeded", first_frame_seq=-1)
    controller.get_runtime_status()
    fake.image = Image.new("RGB", (720, 1280))
    assert controller.capture_frame() is False
    assert not controller.get_input_handler().mouse_click(38, 59)
    fake.image = Image.new("RGB", (1280, 720), (12, 34, 56))
    assert controller.capture_frame()[0].getpixel((0, 0)) == (12, 34, 56)
    assert controller.get_input_handler().mouse_click(38, 59)
    assert s1.requests[-1]["display_id"] == 0
    assert not {"create_display", "frame"}.intersection(r["cmd"] for r in s1.requests)


def test_emulator_rejects_wrong_size_before_launch(adb, s1):
    controller, fake = adb
    controller.cfg.adb_device_type = "emulator"
    fake.sdk = 34
    with pytest.raises(transport.AdbError) as error:
        controller.start_game_process()
    assert error.value.code == "emulator_resolution"
    assert "launch" not in [request["cmd"] for request in s1.requests]


def test_adb_uses_selected_executable_and_reports_server_restart(monkeypatch, tmp_path):
    executable = tmp_path / "custom-adb"
    executable.touch()
    monkeypatch.setattr(transport.shutil, "which", lambda *_: pytest.fail("PATH lookup"))
    assert transport.resolve_adb_path(executable) == executable
    commands = []

    def run(command, **options):
        commands.append(command)
        return CompletedProcess(command, 0, b"List of devices attached\n",
                                b"adb server version (41) doesn't match this client (40); killing...\n")

    monkeypatch.setattr(transport.subprocess, "run", run)
    with pytest.raises(transport.AdbError) as error:
        transport.list_adb_devices(executable)
    assert error.value.code == "adb_server_restarted"
    assert commands == [[str(executable), "devices", "-l"]]



@pytest.mark.parametrize("condition", ["hidden", "sdk_activity", "other_app", "other_display", "unknown_focus"])
def test_review_emulator_refuses_touch_without_game_foreground(adb, s1, condition):
    controller, fake = adb
    controller.cfg.adb_device_type = "emulator"
    fake.sdk = 34
    fake.display_size = "720x1280"
    fake.image = Image.new("RGB", (1280, 720))
    controller.start_game_process()
    assert controller.capture_frame()
    inputs = controller.get_input_handler()

    if condition == "hidden":
        s1.task_visible = False
    elif condition == "sdk_activity":
        s1.top_activity = f"{transport.GAME_PACKAGE}/com.miHoYo.sdk.platform.SdkActivity"
    elif condition == "other_app":
        fake.focus_output = ("Display: mDisplayId=0 rootTasks=3\n"
                             "mCurrentFocus=Window{abcdef u0 com.mumu.launcher/.Launcher}")
    elif condition == "other_display":
        fake.focus_output = (f"Display: mDisplayId=8 rootTasks=1\n"
                             f"mCurrentFocus=Window{{abcdef u0 {s1.top_activity}}}\n"
                             "Display: mDisplayId=0 rootTasks=3\nmCurrentFocus=null")
    else:
        fake.focus_output = ""

    assert inputs.mouse_click(38, 59) is False
    assert inputs.mouse_down(38, 59) is False
    assert inputs.mouse_drag(38, 59, 80, 110) is False
    assert not {"tap", "touch", "swipe"}.intersection(request["cmd"] for request in s1.requests)


def test_review_emulator_releases_held_touch_after_backgrounding(adb, s1):
    controller, fake = adb
    controller.cfg.adb_device_type = "emulator"
    fake.sdk = 34
    fake.display_size = "720x1280"
    fake.image = Image.new("RGB", (1280, 720))
    controller.start_game_process()
    assert controller.capture_frame()
    inputs = controller.get_input_handler()
    assert inputs.mouse_down(38, 59)
    s1.task_visible = False
    assert inputs.mouse_move(100, 120) is False
    assert inputs.mouse_up()
    assert [request["action"] for request in s1.requests if request["cmd"] == "touch"] == ["down", "up"]


def test_review_adb_close_waits_for_owned_instance_before_reopening(adb):
    controller, fake = adb
    controller.connect()
    fake.exit_checks_remaining = 2

    controller.close()
    assert not fake.forwarding
    controller.connect()
    assert fake.exit_probes == 3
    assert fake.forwarding



@pytest.mark.parametrize("acknowledged", [True, False])
def test_review_adb_close_clears_forward_when_exit_cannot_be_confirmed(adb, s1, monkeypatch, acknowledged):
    from unittest.mock import Mock

    controller, fake = adb
    controller.connect()
    fake.exit_checks_remaining = 10
    if not acknowledged:
        s1.drop_command = "shutdown"
    monkeypatch.setattr(transport, "_SHUTDOWN_TIMEOUT_SECONDS", 0.05)
    warning = Mock()
    monkeypatch.setattr(transport.log, "warning", warning)

    controller.close()

    assert not fake.forwarding
    assert bool(fake.exit_probes) is acknowledged
    assert warning.called is acknowledged



@pytest.mark.parametrize(("sdk", "abis", "auto_focus"), [
    (32, "x86_64,arm64-v8a", True),
    (33, "x86_64", True),
    (32, "arm64-v8a", False),
])
def test_auto_uses_virtual_display_on_older_android(adb, s1, sdk, abis, auto_focus):
    controller, fake = adb
    controller.cfg.adb_serial = "127.0.0.1:16384"
    fake.sdk = sdk
    fake.abis = abis
    fake.display_size = "720x1280"

    assert controller.connect().device_type == "emulator"
    controller.start_game_process()

    assert controller.cfg.adb_device_type == "auto"
    assert controller.display_id == 42
    watchdog = next(r for r in s1.requests if r["cmd"] == "watchdog")
    assert watchdog["display_id"] == 42
    assert watchdog["auto_focus"] is auto_focus
    assert controller.capture_frame()
    assert controller.get_input_handler().mouse_click(38, 59)
    assert s1.requests[-1]["display_id"] == 42


@pytest.mark.parametrize("sdk", [32, 33])
def test_emulator_display_zero_requires_strict_android_dispatch(adb, s1, sdk):
    controller, fake = adb
    controller.cfg.adb_device_type = "emulator"
    fake.display_size = "720x1280"
    fake.sdk = sdk

    with pytest.raises(transport.AdbError) as raised:
        controller.start_game_process()

    assert raised.value.code == "emulator_input_unsupported"
    assert "adb_device_type: physical" in str(raised.value)
    assert not {"watchdog", "launch", "tap"}.intersection(r["cmd"] for r in s1.requests)


def test_older_s1_version_is_rejected_before_launch(adb, s1):
    controller, fake = adb
    controller.cfg.adb_device_type = "emulator"
    fake.sdk = 34
    fake.display_size = "720x1280"
    s1.version = "0.1.0"

    with pytest.raises(transport.AdbError) as raised:
        controller.start_game_process()

    assert raised.value.code == "service_version"
    assert fake.pushes == 2
    assert not fake.forwarding
    assert "launch" not in [r["cmd"] for r in s1.requests]


def test_target_mismatch_after_focus_check_does_not_replay_tap(adb, s1, monkeypatch):
    controller, fake = adb
    controller.cfg.adb_device_type = "emulator"
    fake.sdk = 34
    fake.display_size = "720x1280"
    fake.image = Image.new("RGB", (1280, 720))
    controller.start_game_process()
    assert controller.capture_frame()

    focused_window = fake.focused_window

    def switch_after_read(display_id):
        window = focused_window(display_id)
        s1.target_mismatch = True
        return window

    monkeypatch.setattr(fake, "focused_window", switch_after_read)
    with pytest.raises(transport.AdbError) as raised:
        controller.get_input_handler().mouse_click(38, 59)

    assert raised.value.code == "inject_failed"
    assert sum(r["cmd"] == "tap" for r in s1.requests) == 1


def test_fast_reconnect_retries_until_old_service_releases_lock(adb, s1, monkeypatch):
    controller, fake = adb
    controller.start_game_process()
    s1.drop_command = "frame"
    with pytest.raises(transport.AdbError) as raised:
        controller.capture_frame()
    assert raised.value.code == "disconnected"
    s1.drop_command = "shutdown"
    controller.close()
    assert not fake.forwarding

    s1.drop_command = None
    fake.busy_launches_remaining = 2
    monkeypatch.setattr(transport, "_BUSY_RETRY_SECONDS", 0.01)
    controller.start_game_process()

    assert fake.launch_attempts == 4
    assert fake.forwarding
    assert controller.capture_frame()


def test_busy_retry_is_bounded_and_never_takes_over_active_service(adb, s1, monkeypatch):
    controller, fake = adb
    fake.busy_launches_remaining = 100
    clock = SimpleNamespace(now=0.0)

    def sleep(seconds):
        clock.now += seconds

    monkeypatch.setattr(transport, "time", SimpleNamespace(monotonic=lambda: clock.now, sleep=sleep))

    with pytest.raises(transport.AdbError) as raised:
        controller.connect()

    assert raised.value.code == "service_busy"
    assert clock.now == pytest.approx(transport._BUSY_TIMEOUT_SECONDS)
    assert 1 < fake.launch_attempts < 100
    assert fake.pushes == 1
    assert not fake.forwarding
    assert s1.requests == []



@pytest.mark.parametrize(("abis", "auto_focus"), [("x86_64,arm64-v8a", True), ("arm64-v8a", False)])
def test_virtual_display_focus_distinguishes_mumu_from_forwarded_phone(adb, s1, abis, auto_focus):
    controller, fake = adb
    controller.cfg.adb_serial = "127.0.0.1:16384"
    controller.cfg.adb_device_type = "physical"
    fake.sdk = 32
    fake.abis = abis

    controller.start_game_process()

    watchdog = next(r for r in s1.requests if r["cmd"] == "watchdog")
    assert watchdog["display_id"] == 42
    assert watchdog["auto_focus"] is auto_focus
