"""ADB 界面测试共用的模拟数据：假配置、假设备和假控制器，不连接真实设备。"""
from pathlib import Path

from module.game.adb import AdbRuntimeStatus
from module.game.adb_transport import AdbDevice, AdbEnvironment, AdbError

ADB_PATH = Path("C:/platform-tools/adb.exe")
PHONE = AdbDevice("4e6780d5", "device", "Redmi Note 7")
EMULATOR = AdbDevice("127.0.0.1:16384", "device", "M2007J17C")
UNAUTHORIZED = AdbDevice("R58M123ABCD", "unauthorized", None)


class FakeConfig:
    """只保留界面用到的取值规则：显式后端生效时，旧开关读到的是推导值。"""

    def __init__(self, **values):
        self.values = dict(control_backend=None, cloud_game_enable=False, ui_profile="pc_1080", adb_path=None,
                           adb_serial=None, adb_device_type="auto", adb_service_jar=None, adb_tap_ms=50)
        self.values.update(values)
        self.writes = []

    def get_value(self, key, default=None):
        if key == "cloud_game_enable" and self.values.get("control_backend") is not None:
            return self.values["control_backend"] == "cloud"
        return self.values.get(key, default)

    def __getattr__(self, name):
        if name in ("values", "writes"):
            raise AttributeError(name)
        if name in self.values:
            return self.get_value(name)
        raise AttributeError(name)

    def set_value(self, key, value):
        self.set_values({key: value})

    def set_values(self, values):
        self.writes.append(dict(values))
        self.values.update(values)


def environment(device=PHONE, *, sdk=29, version="10", device_type="physical", size=(1080, 2340), installed=True):
    return AdbEnvironment(ADB_PATH, device, sdk, version, device_type, size, installed, device_type == "emulator")


class FakeAdb:
    """替换 adb_service 里的 A1 接口。按序列号返回环境，或抛出预设的 AdbError。"""

    def __init__(self, devices=(PHONE,), environments=None, errors=None):
        self.devices = list(devices)
        self.environments = environments or {PHONE.serial: environment(),
                                             EMULATOR.serial: environment(EMULATOR, sdk=32, version="12",
                                                                          device_type="emulator", size=(720, 1280))}
        self.errors = dict(errors or {})
        self.injection = (True, True)
        self.controllers = []
        self.connected = []

    def install(self, monkeypatch, service):
        monkeypatch.setattr(service, "resolve_adb_path", self.resolve_adb_path)
        monkeypatch.setattr(service, "list_adb_devices", self.list_adb_devices)
        monkeypatch.setattr(service, "check_adb_environment", self.check_adb_environment)
        monkeypatch.setattr(service, "_touch_injection", lambda path, serial: self.injection)
        monkeypatch.setattr(service, "AdbGameController", self.controller)
        return self

    def _raise(self, key):
        error = self.errors.get(key)
        if isinstance(error, list):
            error = error.pop(0) if error else None
        if error is not None:
            raise error

    def resolve_adb_path(self, adb_path=None):
        self._raise("resolve")
        return ADB_PATH

    def list_adb_devices(self, adb_path=None):
        self._raise("list")
        return list(self.devices)

    def check_adb_environment(self, config):
        self._raise("environment")
        serial = config.adb_serial
        if not serial:
            if len(self.devices) > 1:
                raise AdbError("multiple_devices", "检测到多个 ADB 设备，请设置 adb_serial")
            if not self.devices:
                raise AdbError("device_not_found", "未找到指定的 ADB 设备，请检查连接和 adb_serial")
            serial = self.devices[0].serial
        device = next((item for item in self.devices if item.serial == serial), None)
        if device is None and serial in self.environments and ":" in serial:
            self.connected.append(serial)
            device = self.environments[serial].device
            self.devices.append(device)
        if device is None:
            raise AdbError("device_not_found", "未找到指定的 ADB 设备，请检查连接和 adb_serial")
        if device.state != "device":
            raise AdbError("device_not_ready", f"ADB 设备 {serial} 的状态为 {device.state}")
        self._raise(serial)
        return self.environments[serial]

    def controller(self, config):
        controller = FakeController(self, config)
        self.controllers.append(controller)
        return controller


class FakeController:
    def __init__(self, adb, config):
        self.adb = adb
        self.config = config
        self.closed = False
        self.display_id = 44

    def connect(self):
        self.adb._raise("connect")
        return self.adb.check_adb_environment(self.config)

    def get_runtime_status(self):
        return AdbRuntimeStatus(True, self.config.adb_serial, "0.1.1", None, None, False, False, 0.0, None, None)

    def prepare_display(self):
        self.adb._raise("display")
        return self.display_id

    def close(self):
        self.closed = True


def status(**values):
    """一份任务进程写出的状态快照。"""
    data = dict(schema=1, pid=1, running=True, phase="running", connected=True, serial=PHONE.serial,
                service_version="0.1.1", display_id=44, game_display_id=44, game_running=True, sdk_window=False,
                capture_fps=8.3, error_code=None, error_message=None, updated=0.0)
    data.update(values)
    return data
