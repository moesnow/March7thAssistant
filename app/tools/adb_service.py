"""ADB 界面用到的设备发现、环境检查和错误指引。

只调用 A1 提供的 Python 接口，不含 Qt 代码。所有函数都是同步调用，界面放在后台线程执行。
"""
from dataclasses import dataclass
import re
from types import SimpleNamespace

from module.config import cfg
from module.config.platform import get_control_backend
from module.game.adb import AdbGameController
from module.game.adb_transport import (
    RESOLUTION, Adb, AdbError, check_adb_environment, list_adb_devices, resolve_adb_path,
)
from module.localization import tr


DEFAULT_NETWORK_PORT = 5555
MUMU_ADDRESS = "127.0.0.1:16384"

# 环境检查项的固定顺序。resolution 只对模拟器报告。
CHECK_KEYS = ("adb", "server", "device", "android", "inject", "service", "display", "game", "resolution")

PASS, WARN, FAIL, SKIP = "pass", "warn", "fail", "skip"

_ADB_CONFIG_KEYS = ("adb_path", "adb_serial", "adb_device_type", "adb_service_jar", "adb_tap_ms")


@dataclass(frozen=True)
class DeviceInfo:
    serial: str
    state: str
    model: str | None = None
    android_version: str | None = None
    sdk: int | None = None
    device_type: str | None = None
    error_code: str | None = None
    error: str | None = None

    @property
    def ready(self):
        return self.state == "device" and self.error_code is None


@dataclass(frozen=True)
class CheckResult:
    key: str
    status: str
    detail: str
    guide: str = ""


def adb_config(config=None, **overrides):
    """取出 ADB 相关配置并固定触屏形态，环境检查不要求先切换设备后端。"""
    config = cfg if config is None else config
    if isinstance(config, SimpleNamespace):
        values = vars(config).copy()
    else:
        values = {key: config.get_value(key) for key in _ADB_CONFIG_KEYS}
    values.update(ui_profile="touch_720", control_backend="adb")
    values.update(overrides)
    return SimpleNamespace(**values)


# ---------- 设备后端 ----------

def current_backend(config=None):
    """当前生效的设备后端。配置值无效时按本地处理，交给用户重新选择。"""
    try:
        return get_control_backend(cfg if config is None else config)
    except ValueError:
        return "local"


def backend_changes(backend, config=None):
    """切换设备后端要写入的配置。

    本地和云游戏沿用旧开关 `cloud_game_enable`，`control_backend` 留空，
    没用过 ADB 的配置文件因此保持原样。ADB 需要显式后端和触屏形态。
    """
    config = cfg if config is None else config
    if backend == "adb":
        return {"control_backend": "adb", "ui_profile": "touch_720"}
    changes = {}
    cloud = backend == "cloud"
    if config.get_value("control_backend") is not None:
        # 显式后端生效期间读到的旧开关是推导值，清空后端时必须把旧开关一并写明。
        changes.update(control_backend=None, cloud_game_enable=cloud)
    elif bool(config.get_value("cloud_game_enable")) != cloud:
        changes["cloud_game_enable"] = cloud
    if current_backend(config) == "adb" and config.get_value("ui_profile") == "touch_720":
        changes["ui_profile"] = "pc_1080"
    return changes


# ---------- 设备发现 ----------

def normalize_address(text):
    """把用户输入整理成 `主机:端口`。只写主机时补上 adb 的默认端口。"""
    address = str(text or "").strip().replace("：", ":")
    if not address or re.search(r"\s", address):
        return None
    if re.fullmatch(r"\[[^\]]+\]", address) or ":" not in address:
        address = f"{address}:{DEFAULT_NETWORK_PORT}"
    host, _, port = address.rpartition(":")
    if not host or not port.isdigit() or not 0 < int(port) <= 65535:
        return None
    return address


def _device_info(device, config):
    if device.state != "device":
        return DeviceInfo(device.serial, device.state, device.model)
    try:
        environment = check_adb_environment(adb_config(config, adb_serial=device.serial, adb_device_type="auto"))
    except AdbError as error:
        return DeviceInfo(device.serial, device.state, device.model, error_code=error.code, error=str(error))
    return DeviceInfo(device.serial, device.state, environment.device.model, environment.android_version,
                      environment.sdk, environment.device_type)


def list_devices(config=None):
    """列出设备并补全型号、系统版本和设备类型。未授权、离线的设备也保留。"""
    config = adb_config(config)
    return [_device_info(device, config) for device in list_adb_devices(config.adb_path)]


def connect_device(address, config=None):
    """连接网络地址（模拟器或无线调试）并返回设备信息。失败时抛出 AdbError。"""
    environment = check_adb_environment(adb_config(config, adb_serial=address, adb_device_type="auto"))
    device = environment.device
    return DeviceInfo(device.serial, device.state, device.model, environment.android_version,
                      environment.sdk, environment.device_type)


# ---------- 错误指引 ----------

def error_guide(code, state=None):
    """错误码对应的下一步做法。未收录的错误码返回通用提示。"""
    if code == "device_not_ready" and state == "unauthorized":
        return tr("手机上会弹出“允许 USB 调试吗？”，勾选“一律允许”后点“确定”。没有弹窗时重新插拔数据线，"
                  "或在开发者选项里点“撤销 USB 调试授权”后再连接。")
    guides = {
        "adb_not_found": tr("安装 Android Platform-Tools 并把它加入 PATH，或在“高级设置”里指定 adb 的位置。"
                            "装有 MuMu 等模拟器时会自动使用模拟器自带的 adb。"),
        "adb_server_restarted": tr("电脑上还有另一个版本的 adb（常见于模拟器和手机助手）在抢占服务端。"
                                   "关闭这些程序，或在“高级设置”里把 adb 路径改成它们使用的那一个，然后重试。"),
        "adb_timeout": tr("adb 没有响应。重新插拔数据线或重启模拟器后重试。"),
        "adb_failed": tr("adb 命令执行失败。重新插拔数据线或重启模拟器后重试。"),
        "device_not_found": tr("用数据线连接手机，并在开发者选项里打开“USB 调试”。"
                               "模拟器请在“Android 设备”里输入地址连接，MuMu 默认是 127.0.0.1:16384。"),
        "multiple_devices": tr("检测到多台设备，请在“Android 设备”里选择要使用的那一台。"),
        "device_not_ready": tr("设备已连接但还不能使用。重新插拔数据线或重启模拟器，然后点“刷新”。"),
        "android_version": tr("ADB 模式需要 Android 10 或更高版本，请换一台设备，或改用模拟器。"),
        "display_size": tr("读不到设备的屏幕分辨率。解锁设备并保持亮屏后重试。"),
        "device_type": tr("请在“高级设置”里重新选择设备类型。"),
        "emulator_resolution": tr("在模拟器设置里把分辨率改成 1280×720（横屏、240 DPI），重启模拟器后重试。"),
        "emulator_input_unsupported": tr("这台模拟器的 Android 版本低于 14，不能直接使用模拟器画面。"
                                         "请在“高级设置”里把设备类型改回“自动判断”。"),
        "game_not_installed": tr("在设备上安装国服《崩坏：星穹铁道》，并先手动登录一次账号。"),
        "jar_not_found": tr("缺少设备端服务文件。请重新解压完整的程序包；"
                            "从源码运行时先在 Android 目录执行 gradlew :device-service:assemble。"),
        "service_busy": tr("设备正被另一个任务占用，或上一次运行还在收尾。"
                           "等十几秒后重试；有任务在运行时先等它结束。"),
        "service_start": tr("设备端服务没能启动。重新插拔数据线后重试，仍然失败时重启设备。"),
        "service_version": tr("设备端服务和本程序的版本不一致，请把程序更新到最新版本后重试。"),
        "protocol_mismatch": tr("设备端服务和本程序的版本不一致，请把程序更新到最新版本后重试。"),
        "inject_denied": tr("系统拒绝了触摸注入。小米、红米手机请在开发者选项里打开“USB 调试（安全设置）”，"
                            "其他品牌请打开名称相近的开关，然后重新插拔数据线。"),
        "manual_action_required": tr("在手机屏幕或模拟器窗口里完成登录，然后重新运行任务。"
                                     "登录界面这时留在手机屏幕上是正常现象。"),
        "disconnected": tr("设备连接断开了。检查数据线，或确认模拟器还在运行，重新连接后再运行任务。"),
        "game_exited": tr("游戏进程被关闭了，可能是系统清理了后台。请把游戏加入自启动和省电白名单，"
                          "不要在最近任务里一键清理，然后重新运行任务。"),
        "move_back_failed": tr("游戏没能回到虚拟屏。请在设备上结束游戏，然后重新运行任务。"),
        "game_start_timeout": tr("游戏没有在限定时间内进入主界面。请确认账号已登录、网络正常，"
                                 "必要时先在设备上手动进入一次游戏。"),
        "frame_timeout": tr("长时间取不到新的游戏画面。请确认设备没有锁屏，然后重新运行任务。"),
        "desktop_task_unsupported": tr("这个任务只能在本地或云游戏后端运行，请切换设备后端后再运行。"),
        "update_unsupported": tr("请在 Android 设备上通过游戏自带的更新流程更新游戏。"),
        "text_unsupported": tr("ADB 模式不能代替你输入文字，请在设备上手动输入。"),
        "ui_profile": tr("请在本页把设备后端重新选择为“Android 设备（ADB）”。"),
        "tap_duration": tr("请在“高级设置”里把点按时长改为 1 到 10000 毫秒之间的整数。"),
    }
    return guides.get(code) or tr("请按提示处理后重试。仍然失败时，把日志页的内容发给开发者。")


# ---------- 环境检查 ----------

def check_titles():
    return {
        "adb": tr("adb 工具"),
        "server": tr("adb 服务端"),
        "device": tr("设备连接与 USB 调试授权"),
        "android": tr("Android 版本"),
        "inject": tr("触摸注入权限"),
        "service": tr("设备端服务"),
        "display": tr("虚拟屏"),
        "game": tr("游戏安装"),
        "resolution": tr("模拟器分辨率"),
    }


def _touch_injection(adb_path, serial):
    """读取系统属性判断 shell 能否注入触摸。读不到时返回 None，交给运行时的错误提示兜底。"""
    output = Adb(adb_path, serial).shell(
        'echo "miui=$(getprop ro.miui.ui.version.name)"; '
        'echo "adbinput=$(getprop persist.security.adbinput)"; '
        'dumpsys package com.android.shell | grep "android.permission.INJECT_EVENTS: granted" || true',
        timeout=8,
    )
    values = dict(line.split("=", 1) for line in output.splitlines() if line.startswith(("miui=", "adbinput=")))
    grants = re.findall(r"INJECT_EVENTS: granted=(true|false)", output)
    miui = bool(values.get("miui"))
    if miui and values.get("adbinput") != "1":
        return False, miui
    if grants:
        return "true" in grants, miui
    return (True if miui else None), miui


def _check_injection(environment):
    try:
        allowed, miui = _touch_injection(environment.adb_path, environment.device.serial)
    except AdbError:
        allowed, miui = None, False
    if allowed is None:
        return CheckResult("inject", WARN, tr("没能读到系统的触摸注入权限"), tr(
            "可以先运行任务试试。如果提示“拒绝触摸注入”，请在开发者选项里打开“USB 调试（安全设置）”或名称相近的开关。"))
    if allowed:
        detail = tr("已开启“USB 调试（安全设置）”") if miui else tr("系统允许通过 USB 调试注入触摸")
        return CheckResult("inject", PASS, detail)
    if miui:
        return CheckResult("inject", FAIL, tr("没有开启“USB 调试（安全设置）”，小助手无法点击游戏"), tr(
            "打开“设置 → 更多设置 → 开发者选项”，开启“USB 调试（安全设置）”。"
            "系统会要求登录小米账号并插入 SIM 卡，开启后重新插拔数据线。"))
    return CheckResult("inject", FAIL, tr("系统没有允许通过 USB 调试注入触摸，小助手无法点击游戏"), tr(
        "在开发者选项里打开“USB 调试（安全设置）”“禁止权限监控”或名称相近的开关，然后重新插拔数据线。"))


def _check_resolution(environment, config):
    width, height = environment.display_size
    if sorted((width, height)) == sorted(RESOLUTION):
        return CheckResult("resolution", PASS, tr("模拟器分辨率为 1280×720"))
    detail = tr("模拟器当前分辨率为 {width}×{height}").format(width=width, height=height)
    if environment.sdk >= 34 or config.adb_device_type == "emulator":
        return CheckResult("resolution", FAIL, detail, error_guide("emulator_resolution"))
    return CheckResult("resolution", WARN, detail, tr(
        "这台模拟器会改用独立的虚拟屏运行，当前分辨率不影响使用。"
        "想直接使用模拟器画面时，再把分辨率改成 1280×720 横屏。"))


def _selected_device(devices, serial):
    serial = str(serial or "").strip()
    if serial:
        return next((device for device in devices if device.serial == serial), None)
    return devices[0] if len(devices) == 1 else None


def run_environment_checks(report, config=None, controller_factory=None):
    """依次检查 ADB 环境，每得出一项结果就调用 `report(CheckResult)`。

    会短暂启动设备端服务并建立虚拟屏，检查结束后立即释放。不会启动游戏。
    """
    config = adb_config(config)
    pending = [key for key in CHECK_KEYS if key != "resolution"]

    def done(key, status, detail, guide=""):
        if key in pending:
            pending.remove(key)
        report(CheckResult(key, status, detail, guide))

    def skip_rest():
        for key in list(pending):
            done(key, SKIP, tr("前面的检查没有通过，这一项还没检查"))

    try:
        path = resolve_adb_path(config.adb_path)
    except AdbError as error:
        done("adb", FAIL, str(error), error_guide(error.code))
        return skip_rest()
    done("adb", PASS, str(path))

    try:
        devices = list_adb_devices(config.adb_path)
    except AdbError as error:
        if error.code != "adb_server_restarted":
            done("server", FAIL, str(error), error_guide(error.code))
            return skip_rest()
        done("server", WARN, tr("adb 服务端刚被重启，电脑上还有其他版本的 adb 在运行"),
             error_guide(error.code))
        try:
            devices = list_adb_devices(config.adb_path)
        except AdbError as retry_error:
            done("device", FAIL, str(retry_error), error_guide(retry_error.code))
            return skip_rest()
    else:
        done("server", PASS, tr("没有其他版本的 adb 抢占服务端"))

    try:
        environment = check_adb_environment(config)
    except AdbError as error:
        if error.code == "android_version":
            device = _selected_device(devices, config.adb_serial)
            done("device", PASS, tr("{name} 已连接并授权").format(
                name=(device.model or device.serial) if device else tr("设备")))
            done("android", FAIL, str(error), error_guide(error.code))
        else:
            device = _selected_device(devices, config.adb_serial)
            done("device", FAIL, str(error), error_guide(error.code, device.state if device else None))
        return skip_rest()

    device = environment.device
    done("device", PASS, tr("{name}（{serial}）已连接并授权").format(
        name=device.model or device.serial, serial=device.serial))
    done("android", PASS, tr("Android {version}（API {sdk}）").format(
        version=environment.android_version, sdk=environment.sdk))
    injection = _check_injection(environment)
    done(injection.key, injection.status, injection.detail, injection.guide)
    if environment.game_installed:
        done("game", PASS, tr("已安装国服《崩坏：星穹铁道》"))
    else:
        done("game", FAIL, tr("设备上没有安装国服《崩坏：星穹铁道》"), error_guide("game_not_installed"))
    if environment.device_type == "emulator":
        report(_check_resolution(environment, config))

    controller = (controller_factory or AdbGameController)(config)
    try:
        try:
            controller.connect()
            version = controller.get_runtime_status().service_version
        except AdbError as error:
            done("service", FAIL, str(error), error_guide(error.code))
            return skip_rest()
        done("service", PASS, tr("设备端服务已启动，版本 {version}").format(version=version))
        try:
            display_id = controller.prepare_display()
        except AdbError as error:
            done("display", FAIL, str(error), error_guide(error.code))
        else:
            if display_id == 0:
                done("display", PASS, tr("直接使用模拟器画面（display 0），不需要虚拟屏"))
            else:
                done("display", PASS, tr("已建立 1280×720 虚拟屏（display {display}），检查结束后释放").format(
                    display=display_id))
    finally:
        try:
            controller.close()
        except Exception:
            pass
