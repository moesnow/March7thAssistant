"""设置页的 ADB 卡片：选择后端 → 选择设备 → 环境检查 → 运行状态，全部使用模拟数据。"""
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="原生设置界面仅在 Windows 验证")

from module.game.adb_transport import AdbError, AdbTouchInjectionStatus  # noqa: E402

from .adb_fakes import EMULATOR, PHONE, UNAUTHORIZED, FakeAdb, FakeConfig, status  # noqa: E402


@pytest.fixture
def config(monkeypatch):
    from app.card import adb_setting_cards as cards
    from app.tools import adb_service as service
    config = FakeConfig()
    monkeypatch.setattr(cards, "cfg", config)
    monkeypatch.setattr(service, "cfg", config)
    return config


@pytest.fixture
def adb(monkeypatch):
    from app.tools import adb_service as service
    return FakeAdb(devices=[PHONE, EMULATOR, UNAUTHORIZED]).install(monkeypatch, service)


def wait_idle(qtbot, card):
    qtbot.waitUntil(lambda: not card.isBusy(), timeout=5000)
    qtbot.wait(20)


# ---------- 设备后端 ----------

def test_backend_card_shows_derived_backend_without_writing(qtbot, config):
    from app.card.adb_setting_cards import AdbBackendSettingCard
    config.values["cloud_game_enable"] = True
    card = AdbBackendSettingCard()
    qtbot.addWidget(card)
    assert card.comboBox.currentData() == "cloud"
    assert [card.comboBox.itemData(index) for index in range(card.comboBox.count())] == ["local", "cloud", "adb"]
    assert config.writes == []


def test_selecting_adb_writes_backend_and_touch_profile(qtbot, config):
    from app.card.adb_setting_cards import AdbBackendSettingCard
    card = AdbBackendSettingCard()
    qtbot.addWidget(card)
    changed = []
    card.backendChanged.connect(changed.append)
    card.comboBox.setCurrentIndex(card.comboBox.findData("adb"))
    assert config.writes == [{"control_backend": "adb", "ui_profile": "touch_720"}]
    assert changed == ["adb"]
    card.comboBox.setCurrentIndex(card.comboBox.findData("local"))
    assert config.writes[-1] == {"control_backend": None, "cloud_game_enable": False, "ui_profile": "pc_1080"}
    assert changed == ["adb", "local"]


def test_blocked_backend_change_restores_selection(qtbot, config):
    from app.card.adb_setting_cards import AdbBackendSettingCard
    asked = []
    card = AdbBackendSettingCard(blocker=lambda backend: asked.append(backend) or True)
    qtbot.addWidget(card)
    card.comboBox.setCurrentIndex(card.comboBox.findData("adb"))
    assert asked == ["adb"]
    assert card.comboBox.currentData() == "local" and card.backend() == "local"
    assert config.writes == []


def test_set_backend_only_updates_display(qtbot, config):
    from app.card.adb_setting_cards import AdbBackendSettingCard
    card = AdbBackendSettingCard()
    qtbot.addWidget(card)
    changed = []
    card.backendChanged.connect(changed.append)
    card.setBackend("cloud")
    assert card.comboBox.currentData() == "cloud"
    assert config.writes == [] and changed == []


def test_backend_card_is_read_only_in_desktop_twin(qtbot, config, monkeypatch):
    from app.card import adb_setting_cards as cards
    monkeypatch.setattr(cards, "in_desktop_twin", lambda: True)
    card = cards.AdbBackendSettingCard()
    qtbot.addWidget(card)
    assert not card.comboBox.isEnabled()


# ---------- 设备面板 ----------

def test_device_card_lists_devices_with_details(qtbot, config, adb):
    from app.card.adb_setting_cards import AdbDeviceCard
    card = AdbDeviceCard()
    qtbot.addWidget(card)
    assert card.isExpand
    assert [row.radio.property("serial") for row in card.deviceRows()] == [None]
    card.refresh()
    wait_idle(qtbot, card)
    rows = card.deviceRows()
    assert [row.radio.property("serial") for row in rows] == [None, PHONE.serial, EMULATOR.serial, UNAUTHORIZED.serial]
    assert rows[1].radio.text() == "Redmi Note 7"
    assert rows[1].summary.text() == "序列号 4e6780d5 · Android 10 · 实体机"
    assert rows[2].summary.text() == "序列号 127.0.0.1:16384 · Android 12 · 模拟器"
    assert "未授权 USB 调试" in rows[3].summary.text()
    assert "允许 USB 调试" in rows[3].guide.text()
    assert rows[0].radio.isChecked()
    assert card.refreshButton.isEnabled()


def test_selecting_device_writes_serial(qtbot, config, adb):
    from app.card.adb_setting_cards import AdbDeviceCard
    card = AdbDeviceCard()
    qtbot.addWidget(card)
    card.refresh()
    wait_idle(qtbot, card)
    selected = []
    card.serialChanged.connect(selected.append)
    card.deviceRows()[1].radio.click()
    assert config.values["adb_serial"] == PHONE.serial
    assert selected == [PHONE.serial]
    assert card.card.contentLabel.text() == "Redmi Note 7（4e6780d5）"
    card.deviceRows()[0].radio.click()
    assert config.values["adb_serial"] is None and selected == [PHONE.serial, None]


def test_configured_device_that_is_not_connected_stays_selected(qtbot, config, adb):
    from app.card.adb_setting_cards import AdbDeviceCard
    config.values["adb_serial"] = "192.168.1.9:5555"
    card = AdbDeviceCard()
    qtbot.addWidget(card)
    card.refresh()
    wait_idle(qtbot, card)
    row = card.deviceRows()[-1]
    assert row.radio.property("serial") == "192.168.1.9:5555" and row.radio.isChecked()
    assert row.summary.text() == "当前没有连接这台设备"
    assert config.writes == []


def test_manual_connect_selects_new_device(qtbot, config, adb):
    from app.card.adb_setting_cards import AdbDeviceCard
    adb.devices = [PHONE]
    card = AdbDeviceCard()
    qtbot.addWidget(card)
    card.addressEdit.setText(" 127.0.0.1：16384 ")
    card.connectButton.click()
    wait_idle(qtbot, card)
    assert adb.connected == [EMULATOR.serial]
    assert config.values["adb_serial"] == EMULATOR.serial
    assert card.addressEdit.text() == ""
    assert [row.radio.isChecked() for row in card.deviceRows()] == [False, False, True]


def test_invalid_address_is_explained_without_calling_adb(qtbot, config, adb):
    from app.card.adb_setting_cards import AdbDeviceCard
    card = AdbDeviceCard()
    qtbot.addWidget(card)
    card.addressEdit.setText("not an address")
    card.connectButton.click()
    assert not card.isBusy()
    assert card.messageRow.message.text() == "地址格式不对"
    assert adb.connected == []


def test_list_failure_shows_message_and_guide(qtbot, config, adb):
    from app.card.adb_setting_cards import AdbDeviceCard
    from app.tools import adb_service as service
    adb.errors["list"] = AdbError("adb_not_found", "未找到 adb")
    card = AdbDeviceCard()
    qtbot.addWidget(card)
    card.refresh()
    wait_idle(qtbot, card)
    assert card.messageRow.message.text() == "未找到 adb"
    assert card.messageRow.guide.text() == service.error_guide("adb_not_found")


def test_empty_list_tells_user_how_to_connect(qtbot, config, adb):
    from app.card.adb_setting_cards import AdbDeviceCard
    adb.devices = []
    card = AdbDeviceCard()
    qtbot.addWidget(card)
    card.refresh()
    wait_idle(qtbot, card)
    assert card.messageRow.message.text() == "没有发现设备"
    assert "127.0.0.1:16384" in card.messageRow.guide.text()


def test_device_card_grows_with_its_rows(qtbot, config, adb):
    from app.card.adb_setting_cards import AdbDeviceCard
    card = AdbDeviceCard()
    qtbot.addWidget(card)
    card.resize(900, card.height())
    card.show()
    qtbot.wait(50)
    before = card.height()
    card.refresh()
    wait_idle(qtbot, card)
    assert card.height() > before
    assert card.height() == card.card.height() + card.body.height()
    assert all(row.isVisible() for row in card.deviceRows())


# ---------- 环境检查 ----------

def test_environment_card_shows_each_result(qtbot, config, adb):
    from app.card.adb_setting_cards import AdbEnvironmentCard
    config.values["adb_serial"] = PHONE.serial
    card = AdbEnvironmentCard()
    qtbot.addWidget(card)
    assert not card.isExpand
    finished = []
    card.checkFinished.connect(finished.append)
    card.start()
    assert card.isExpand and not card.checkButton.isEnabled()
    wait_idle(qtbot, card)
    assert finished == [True]
    assert card.card.contentLabel.text() == "全部通过，可以运行任务"
    assert card.rows["android"].detail.text() == "Android 10（API 29）"
    assert card.rows["resolution"].isHidden()
    assert card.checkButton.isEnabled() and card.checkButton.text() == "重新检查"
    assert adb.controllers[0].closed


def test_environment_card_explains_failures(qtbot, config, adb):
    from app.card.adb_setting_cards import AdbEnvironmentCard
    config.values["adb_serial"] = PHONE.serial
    adb.injection = AdbTouchInjectionStatus(False, False)
    adb.errors["connect"] = AdbError("service_busy", "设备端服务已被占用或仍在清理，请稍后重试")
    card = AdbEnvironmentCard()
    qtbot.addWidget(card)
    card.show()
    finished = []
    card.checkFinished.connect(finished.append)
    card.start()
    wait_idle(qtbot, card)
    assert finished == [False]
    assert card.card.contentLabel.text() == "有 3 项没有通过，请按提示处理后重新检查"
    assert card.rows["inject"].guide.isVisible() and "USB 调试（安全设置）" in card.rows["inject"].guide.text()
    assert card.rows["service"].detail.text() == "设备端服务已被占用或仍在清理，请稍后重试"
    assert card.rows["display"].detail.text() == "前面的检查没有通过，这一项还没检查"
    assert not card.rows["adb"].guide.isVisible()


def test_environment_card_shows_resolution_for_emulator(qtbot, config, adb):
    from app.card.adb_setting_cards import AdbEnvironmentCard
    config.values["adb_serial"] = EMULATOR.serial
    card = AdbEnvironmentCard()
    qtbot.addWidget(card)
    card.start()
    wait_idle(qtbot, card)
    assert not card.rows["resolution"].isHidden()
    assert card.rows["resolution"].detail.text() == "模拟器分辨率为 1280×720"


def test_environment_check_is_blocked_while_task_runs(qtbot, config, adb):
    from app.card.adb_setting_cards import AdbEnvironmentCard
    card = AdbEnvironmentCard(blocker=lambda: True)
    qtbot.addWidget(card)
    card.checkButton.click()
    assert not card.isBusy() and not adb.controllers
    assert card.rows["adb"].detail.text() == "还没有检查"


def test_environment_card_survives_unexpected_error(qtbot, config):
    from app.card.adb_setting_cards import AdbEnvironmentCard

    def broken(report):
        raise RuntimeError("意外错误")

    card = AdbEnvironmentCard(run_checks=broken)
    qtbot.addWidget(card)
    finished = []
    card.checkFinished.connect(finished.append)
    card.start()
    wait_idle(qtbot, card)
    assert finished == [False]
    assert card.card.contentLabel.text() == "检查中断：意外错误"
    assert card.checkButton.isEnabled()


# ---------- 运行状态 ----------

def rows_of(data, backend="adb"):
    from app.card.adb_setting_cards import describe_status
    summary, rows = describe_status(data, backend)
    return summary, {key: value[1] for key, value in rows.items()}, rows


def test_status_without_run():
    summary, texts, _ = rows_of(None)
    assert summary == "运行任务后，这里会显示设备的状态"
    assert texts["device"] == "未连接" and texts["error"] == "没有错误"
    assert rows_of(None, "local")[0] == "没有使用 Android 设备后端"


def test_status_while_connecting():
    summary, texts, _ = rows_of(status(phase="starting", connected=False, serial=None, service_version=None,
                                       display_id=None, game_display_id=None, game_running=False, capture_fps=0.0))
    assert summary == "任务正在启动"
    assert (texts["device"], texts["service"], texts["display"]) == ("正在连接…", "正在启动…", "未建立")


def test_status_running_on_virtual_display():
    summary, texts, _ = rows_of(status())
    assert summary == "任务正在运行"
    assert texts == {
        "device": "已连接 4e6780d5", "service": "运行中，版本 0.1.1", "display": "1280×720，display 44",
        "game": "虚拟屏，手机屏幕可以照常使用", "fps": "8.3 帧/秒", "error": "没有错误",
    }


def test_status_explains_sdk_bringing_game_to_physical_screen():
    for data in (status(game_display_id=0), status(sdk_window=True)):
        _, texts, rows = rows_of(data)
        assert texts["game"] == "被登录界面带回了实体屏"
        assert "正常现象" in rows["game"][2]


def test_status_on_emulator_display_zero():
    _, texts, _ = rows_of(status(display_id=0, game_display_id=0))
    assert (texts["display"], texts["game"]) == ("不使用虚拟屏，直接用模拟器画面", "模拟器画面")
    assert rows_of(status(display_id=0, game_display_id=21))[1]["game"] == "在模拟器的其他窗口，正在移回"


def test_status_error_comes_with_next_step():
    from app.tools import adb_service as service
    data = status(phase="failed", connected=False, game_running=False, capture_fps=0.0,
                  error_code="disconnected", error_message="ADB 设备或设备端服务已断开，请重新连接后再运行")
    summary, texts, rows = rows_of(data)
    assert summary == "上次运行出错，请看“最近一次错误”"
    assert texts["error"] == "ADB 设备或设备端服务已断开，请重新连接后再运行"
    assert rows["error"][2] == service.error_guide("disconnected")
    assert texts["device"] == "未连接"


def test_status_manual_login_does_not_promise_automatic_recovery():
    _, texts, rows = rows_of(status(sdk_window=True, game_display_id=0, error_code="manual_action_required",
                                    error_message="游戏需要手动登录"))
    assert texts["game"] == "停在登录界面，等待手动登录"
    assert rows["game"][2] == ""


@pytest.mark.parametrize("phase, summary", [
    ("finished", "上次运行正常结束"), ("stopped", "上次运行已被停止"), ("aborted", "上次运行的进程已退出"),
])
def test_status_summary_after_run(phase, summary):
    data = status(phase=phase, connected=False, game_running=False, capture_fps=0.0)
    assert rows_of(data)[0] == summary


def test_status_card_follows_reader(qtbot, config):
    from app.card.adb_setting_cards import AdbStatusCard
    current = {"data": None}
    card = AdbStatusCard(reader=lambda: current["data"], backend=lambda: "adb")
    qtbot.addWidget(card)
    card.resize(900, card.height())
    card.show()
    qtbot.wait(50)
    assert card.isExpand and card._timer.isActive()
    assert card.rows["device"].value.text() == "未连接"
    idle_height = card.height()
    current["data"] = status(sdk_window=True, game_display_id=0)
    card.refresh()
    qtbot.wait(20)
    assert card.rows["game"].value.text() == "被登录界面带回了实体屏"
    assert card.rows["game"].hint.isVisible()
    assert card.height() > idle_height
    assert card.height() == card.card.height() + card.body.height()
    card.hide()
    assert not card._timer.isActive()


def test_status_card_ignores_reader_errors(qtbot, config):
    from app.card.adb_setting_cards import AdbStatusCard

    def reader():
        raise OSError("locked")

    card = AdbStatusCard(reader=reader, backend=lambda: "adb")
    qtbot.addWidget(card)
    assert card.rows["device"].value.text() == "未连接"


# ---------- 高级设置 ----------

def test_advanced_card_is_collapsed_and_writes_values(qtbot, config):
    from app.card.adb_setting_cards import AdbAdvancedCard
    config.values.update(adb_tap_ms=80, adb_device_type="physical", adb_serial=PHONE.serial)
    card = AdbAdvancedCard()
    qtbot.addWidget(card)
    assert not card.isExpand
    assert card.tapSpinBox.value() == 80
    assert card.typeComboBox.currentData() == "physical"
    assert card.serialCard.contentLabel.text() == PHONE.serial
    assert config.writes == []
    card.tapSpinBox.setValue(120)
    card.typeComboBox.setCurrentIndex(card.typeComboBox.findData("auto"))
    card._setPath("C:/tools/adb.exe")
    assert config.values["adb_tap_ms"] == 120 and type(config.values["adb_tap_ms"]) is int
    assert config.values["adb_device_type"] == "auto"
    assert card.pathCard.contentLabel.text() == "C:/tools/adb.exe"
    card.pathResetButton.click()
    assert config.values["adb_path"] is None
    assert card.pathCard.contentLabel.text().startswith("自动查找")


def test_advanced_card_tolerates_invalid_tap_duration(qtbot, config):
    from app.card.adb_setting_cards import AdbAdvancedCard
    config.values["adb_tap_ms"] = "fast"
    card = AdbAdvancedCard()
    qtbot.addWidget(card)
    assert card.tapSpinBox.value() == 50
    assert config.writes == []


# ---------- 设置页 ----------

@pytest.fixture
def settings_page(qtbot, tmp_path, monkeypatch, adb):
    import app.setting_interface as settings
    from app.card import adb_setting_cards as cards
    from app.tools import adb_service as service
    from module.config.config import Config

    path = tmp_path / "config.yaml"
    path.write_text("cloud_game_enable: false\n", encoding="utf-8")
    monkeypatch.delenv("MARCH7TH_CLOUD_GAME_ENABLE", raising=False)
    config = Config.__new__(Config)
    Config.__init__(config, "assets/config/version.txt", "assets/config/config.example.yaml", str(path))
    import app.card.switchsettingcard1 as switch_card
    # 旧的云游戏开关自己写配置，不替换就会写到运行目录下的真实配置。
    for module in (settings, cards, service, switch_card):
        monkeypatch.setattr(module, "cfg", config)
    monkeypatch.setattr("module.config.cfg", config)
    monkeypatch.setattr(cards, "read_adb_run_status", lambda: None)
    interface = settings.SettingInterface()
    qtbot.addWidget(interface)
    interface.resize(1050, 800)
    interface.show()
    interface.stackedWidget.setCurrentWidget(interface.AdbGroup)
    qtbot.wait(100)
    return interface, config, path


def saved(path):
    from ruamel.yaml import YAML
    return YAML().load(path.read_text(encoding="utf-8"))


def test_settings_page_has_android_tab(settings_page):
    interface, config, path = settings_page
    assert interface.pivot.items["adbInterface"].text() == "安卓设备"
    for card in (interface.adbBackendCard, interface.adbDeviceCard, interface.adbEnvironmentCard,
                 interface.adbStatusCard, interface.adbAdvancedCard):
        assert card.parentWidget() is interface.AdbGroup
    assert interface.adbBackendCard.comboBox.currentData() == "local"
    assert not interface.adbAdvancedCard.isExpand
    assert interface.stackedWidget.height() >= interface.AdbGroup.sizeHint().height()
    # 打开页面不改动没用过 ADB 的配置。
    assert saved(path)["control_backend"] is None and saved(path)["ui_profile"] == "pc_1080"
    # 没有使用 ADB 后端时不主动调用 adb。
    assert [row.radio.property("serial") for row in interface.adbDeviceCard.deviceRows()] == [None]


def test_settings_page_walks_through_adb_setup(settings_page, qtbot, adb):
    """选择后端 → 选择设备 → 环境检查 → 显示状态。"""
    interface, config, path = settings_page
    backend = interface.adbBackendCard
    backend.comboBox.setCurrentIndex(backend.comboBox.findData("adb"))
    assert (saved(path)["control_backend"], saved(path)["ui_profile"]) == ("adb", "touch_720")
    assert not interface.cloudGameEnableCard.switchButton.isChecked()

    devices = interface.adbDeviceCard
    wait_idle(qtbot, devices)  # 切到 ADB 后自动查找设备
    assert len(devices.deviceRows()) == 4
    devices.deviceRows()[1].radio.click()
    assert saved(path)["adb_serial"] == PHONE.serial
    assert interface.adbAdvancedCard.serialCard.contentLabel.text() == PHONE.serial

    checks = interface.adbEnvironmentCard
    checks.start()
    wait_idle(qtbot, checks)
    assert checks.card.contentLabel.text() == "全部通过，可以运行任务"
    assert interface.stackedWidget.height() >= interface.AdbGroup.sizeHint().height()

    interface.adbStatusCard._reader = lambda: status(sdk_window=True, game_display_id=0)
    interface.adbStatusCard.refresh()
    assert interface.adbStatusCard.rows["game"].value.text() == "被登录界面带回了实体屏"


def test_cloud_switch_and_backend_card_stay_in_sync(settings_page):
    interface, config, path = settings_page
    backend = interface.adbBackendCard
    switch = interface.cloudGameEnableCard.switchButton

    # 旧开关照常工作：只写 cloud_game_enable。
    switch.setChecked(True)
    assert saved(path)["cloud_game_enable"] is True and saved(path)["control_backend"] is None
    assert backend.comboBox.currentData() == "cloud"

    backend.comboBox.setCurrentIndex(backend.comboBox.findData("adb"))
    assert not switch.isChecked()
    assert saved(path)["cloud_game_enable"] is True  # YAML 里的旧值保留

    # ADB 生效期间打开旧开关：清掉显式后端，旧开关重新生效。
    switch.setChecked(True)
    data = saved(path)
    assert (data["control_backend"], data["cloud_game_enable"], data["ui_profile"]) == (None, True, "pc_1080")
    assert backend.comboBox.currentData() == "cloud"

    backend.comboBox.setCurrentIndex(backend.comboBox.findData("local"))
    assert saved(path)["cloud_game_enable"] is False
    assert not switch.isChecked()


def test_backend_change_is_blocked_while_task_runs(settings_page):
    from types import SimpleNamespace
    interface, config, path = settings_page
    interface.parent = SimpleNamespace(logInterface=SimpleNamespace(isTaskRunning=lambda: True))
    backend = interface.adbBackendCard
    backend.comboBox.setCurrentIndex(backend.comboBox.findData("adb"))
    assert backend.comboBox.currentData() == "local"
    assert saved(path)["control_backend"] is None
    interface.adbEnvironmentCard.checkButton.click()
    assert not interface.adbEnvironmentCard.isBusy()
