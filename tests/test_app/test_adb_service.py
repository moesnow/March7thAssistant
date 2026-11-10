"""ADB 界面的服务层：后端切换写入的配置、设备发现和环境检查。全部使用模拟数据。"""
import pytest

from app.tools import adb_service as service
from module.game.adb_transport import AdbError, AdbTouchInjectionStatus

from .adb_fakes import EMULATOR, PHONE, UNAUTHORIZED, FakeAdb, FakeConfig, environment


def run_checks(config):
    results = {}
    service.run_environment_checks(lambda result: results.__setitem__(result.key, result), config)
    return results


@pytest.fixture
def adb(monkeypatch):
    return FakeAdb().install(monkeypatch, service)


# ---------- 设备后端 ----------

@pytest.mark.parametrize("values, backend", [
    ({}, "local"),
    ({"cloud_game_enable": True}, "cloud"),
    ({"control_backend": "adb", "cloud_game_enable": True}, "adb"),
    ({"control_backend": "bogus"}, "local"),
])
def test_current_backend_follows_legacy_switch_until_explicit(values, backend):
    assert service.current_backend(FakeConfig(**values)) == backend


def test_untouched_config_needs_no_write():
    """没用过 ADB 的配置重新选中当前后端时一个键都不写。"""
    assert service.backend_changes("local", FakeConfig()) == {}
    assert service.backend_changes("cloud", FakeConfig(cloud_game_enable=True)) == {}


def test_local_and_cloud_only_touch_legacy_switch():
    assert service.backend_changes("cloud", FakeConfig()) == {"cloud_game_enable": True}
    assert service.backend_changes("local", FakeConfig(cloud_game_enable=True)) == {"cloud_game_enable": False}


def test_adb_sets_explicit_backend_and_touch_profile():
    config = FakeConfig(cloud_game_enable=True)
    assert service.backend_changes("adb", config) == {"control_backend": "adb", "ui_profile": "touch_720"}


@pytest.mark.parametrize("backend, legacy", [("local", True), ("cloud", False)])
def test_leaving_adb_restores_legacy_switch_and_pc_profile(backend, legacy):
    """旧开关在 YAML 里的值可能与目标相反，离开 ADB 时必须写明。"""
    config = FakeConfig(control_backend="adb", ui_profile="touch_720", cloud_game_enable=legacy)
    changes = service.backend_changes(backend, config)
    assert changes == {"control_backend": None, "cloud_game_enable": backend == "cloud", "ui_profile": "pc_1080"}
    config.set_values(changes)
    assert service.current_backend(config) == backend


def test_touch_profile_of_local_developer_setup_is_kept():
    """本地触屏开发环境（touch_720 + local）切到云游戏不改 UI 形态。"""
    config = FakeConfig(ui_profile="touch_720")
    assert service.backend_changes("cloud", config) == {"cloud_game_enable": True}


# ---------- 设备发现 ----------

@pytest.mark.parametrize("text, address", [
    ("127.0.0.1:16384", "127.0.0.1:16384"),
    (" 127.0.0.1：16384 ", "127.0.0.1:16384"),
    ("192.168.1.8", "192.168.1.8:5555"),
    ("[::1]:5555", "[::1]:5555"),
    ("", None),
    ("127.0.0.1:abc", None),
    ("127.0.0.1:70000", None),
    ("emu lator", None),
])
def test_normalize_address(text, address):
    assert service.normalize_address(text) == address


def test_list_devices_keeps_unauthorized_and_fills_details(adb):
    adb.devices = [PHONE, EMULATOR, UNAUTHORIZED]
    devices = service.list_devices(FakeConfig(adb_serial="does-not-matter", adb_device_type="emulator"))
    assert [(device.serial, device.android_version, device.device_type, device.ready) for device in devices] == [
        (PHONE.serial, "10", "physical", True),
        (EMULATOR.serial, "12", "emulator", True),
        (UNAUTHORIZED.serial, None, None, False),
    ]
    assert devices[2].state == "unauthorized"


def test_list_devices_reports_per_device_error(adb):
    adb.errors[PHONE.serial] = AdbError("android_version", "ADB 后端需要 Android 10 或更高版本")
    device = service.list_devices(FakeConfig())[0]
    assert (device.error_code, device.ready) == ("android_version", False)


def test_connect_device_uses_network_address(adb):
    adb.devices = []
    device = service.connect_device(EMULATOR.serial, FakeConfig())
    assert adb.connected == [EMULATOR.serial]
    assert (device.serial, device.device_type, device.android_version) == (EMULATOR.serial, "emulator", "12")


# ---------- 环境检查 ----------

def test_checks_pass_on_phone_and_release_session(adb):
    results = run_checks(FakeConfig(adb_serial=PHONE.serial))
    assert list(results) == ["adb", "server", "device", "android", "inject", "game", "service", "display"]
    assert {result.status for result in results.values()} == {service.PASS}
    assert "44" in results["display"].detail
    controller, = adb.controllers
    assert controller.closed
    # 环境检查不要求先切换后端：传给控制器的配置固定为触屏形态。
    assert (controller.config.ui_profile, controller.config.adb_serial) == ("touch_720", PHONE.serial)


def test_missing_adb_skips_everything_else(adb):
    adb.errors["resolve"] = AdbError("adb_not_found", "未找到 adb")
    results = run_checks(FakeConfig())
    assert results["adb"].status == service.FAIL and results["adb"].guide
    assert {results[key].status for key in results if key != "adb"} == {service.SKIP}
    assert not adb.controllers


def test_server_restart_is_reported_then_checks_continue(adb):
    adb.errors["list"] = [AdbError("adb_server_restarted", "ADB 服务端被其他版本重启")]
    results = run_checks(FakeConfig())
    assert results["server"].status == service.WARN and results["server"].guide
    assert results["display"].status == service.PASS


def test_unauthorized_device_gets_authorization_guide(adb):
    adb.devices = [UNAUTHORIZED]
    results = run_checks(FakeConfig())
    assert results["device"].status == service.FAIL
    assert results["device"].guide == service.error_guide("device_not_ready", "unauthorized")
    assert results["service"].status == service.SKIP


def test_multiple_devices_ask_user_to_choose(adb):
    adb.devices = [PHONE, EMULATOR]
    results = run_checks(FakeConfig())
    assert results["device"].guide == service.error_guide("multiple_devices")


def test_old_android_fails_version_but_device_is_connected(adb):
    adb.errors[PHONE.serial] = AdbError("android_version", "ADB 后端需要 Android 10 或更高版本")
    results = run_checks(FakeConfig())
    assert (results["device"].status, results["android"].status) == (service.PASS, service.FAIL)
    assert results["inject"].status == service.SKIP


def test_miui_without_security_setting_fails_injection(adb):
    adb.injection = AdbTouchInjectionStatus(False, False)
    result = run_checks(FakeConfig())["inject"]
    assert result.status == service.FAIL and "USB 调试（安全设置）" in result.guide


def test_security_setting_enabled_but_injection_denied(adb):
    adb.injection = AdbTouchInjectionStatus(False, True)
    result = run_checks(FakeConfig())["inject"]
    assert result.status == service.FAIL and "系统没有允许" in result.detail


def test_unknown_injection_state_is_a_warning(adb):
    adb.injection = AdbTouchInjectionStatus(None)
    assert run_checks(FakeConfig())["inject"].status == service.WARN


def test_missing_game_fails_but_service_is_still_checked(adb):
    adb.environments[PHONE.serial] = environment(installed=False)
    results = run_checks(FakeConfig())
    assert results["game"].status == service.FAIL
    assert results["service"].status == service.PASS


def test_busy_service_is_reported_and_session_released(adb):
    adb.errors["connect"] = AdbError("service_busy", "设备端服务已被占用或仍在清理，请稍后重试")
    results = run_checks(FakeConfig())
    assert results["service"].status == service.FAIL
    assert results["service"].guide == service.error_guide("service_busy")
    assert results["display"].status == service.SKIP
    assert adb.controllers[0].closed


def test_display_failure_keeps_error_text(adb):
    adb.errors["display"] = AdbError("emulator_input_unsupported", "display 0 的触摸目标校验需要 Android 14")
    results = run_checks(FakeConfig())
    assert results["display"].status == service.FAIL
    assert results["display"].guide == service.error_guide("emulator_input_unsupported")
    assert adb.controllers[0].closed


def test_emulator_reports_resolution_only_for_emulators(adb):
    adb.devices = [EMULATOR]
    assert run_checks(FakeConfig())["resolution"].status == service.PASS
    adb.devices = [PHONE]
    assert "resolution" not in run_checks(FakeConfig())


def test_emulator_resolution_mismatch_depends_on_display_path(adb):
    adb.devices = [EMULATOR]
    adb.environments[EMULATOR.serial] = environment(EMULATOR, sdk=32, version="12", device_type="emulator",
                                                    size=(1600, 900))
    # Android 14 以下的模拟器走虚拟屏，分辨率不影响运行。
    assert run_checks(FakeConfig())["resolution"].status == service.WARN
    assert run_checks(FakeConfig(adb_device_type="emulator"))["resolution"].status == service.FAIL
    adb.environments[EMULATOR.serial] = environment(EMULATOR, sdk=34, version="14", device_type="emulator",
                                                    size=(1600, 900))
    assert run_checks(FakeConfig())["resolution"].status == service.FAIL


@pytest.mark.parametrize("code", [
    "adb_not_found", "adb_server_restarted", "device_not_found", "multiple_devices", "device_not_ready",
    "android_version", "emulator_resolution", "game_not_installed", "jar_not_found", "service_busy",
    "service_version", "protocol_mismatch", "emulator_input_unsupported", "desktop_task_unsupported",
    "inject_denied", "manual_action_required", "disconnected",
])
def test_every_documented_error_code_has_its_own_guide(code):
    assert service.error_guide(code) != service.error_guide("not-a-known-code")
