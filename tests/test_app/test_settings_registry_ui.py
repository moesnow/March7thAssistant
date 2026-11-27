import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QWidget
from qfluentwidgets import ExpandSettingCard, SettingCard
from ruamel.yaml import YAML

from app.content import PageHost, build_page
from app.content.base import card_for, setting_for
from app.content.settings_state import config_events, defaults_for, is_modified, reset_reason, restore_default
from app.content.visibility import page_visible, section_visible, setting_visible
from module.config import cfg
from module.content_pages import PAGES
from module.settings_registry import SETTINGS, Scope, find_setting
from utils.runs import AFTER_FINISH_CHOICES


@pytest.fixture
def pages(qtbot, tmp_path, monkeypatch):
    config = YAML(typ="safe").load(Path(cfg.example_path))
    config.update(control_backend="local", ui_profile="pc_1080", auto_detect_game_hotkeys_enable=False)
    monkeypatch.setattr(cfg, "config", config)
    monkeypatch.setattr(cfg, "config_path", str(tmp_path / "config.yaml"))
    # Constructing OS controls must never touch the user's scheduled tasks or enumerate a device.
    from app.card import autostart_setting_card as startup
    from utils import uac_free
    monkeypatch.setattr(startup.AutostartSettingCard, "refreshState", lambda *args: None)
    monkeypatch.setattr(uac_free, "is_enabled", lambda: False)
    from app.tools import adb_service
    monkeypatch.setattr(adb_service, "list_devices", lambda *_: [])
    window = QWidget()
    qtbot.addWidget(window)
    window.refreshBackendTasks = Mock()
    hosts = {}
    for page in PAGES:
        if page.kind != "page":
            host = PageHost(window, QWidget(window))
            build_page(page.id, host)
            hosts[page.id] = host
    return window, hosts


def test_every_registered_widget_and_every_built_card(pages):
    _, hosts = pages
    for page, host in hosts.items():
        expected = {s.id for s in SETTINGS if s.page == page and s.widget and
                    (sys.platform == "win32" or s.id not in ("autostart_open_gui", "debug_mode_enable", "uacFreeCard"))}
        actual = set()
        for card in host.card_parent.findChildren(QWidget):
            is_card = isinstance(card, (SettingCard, ExpandSettingCard))
            if getattr(card.parentWidget(), "card", None) is card or (not is_card and not card.property("settingId")):
                continue
            item = setting_for(card)
            assert item and item.page == page, (page, card)
            assert card_for(item, host) is card
            assert item.id not in actual
            actual.add(item.id)
        assert actual == expected
    assert len(hosts["reward"].sections[1].checks) == 8
    assert not hosts["reward"].sections[1].cards
    assert not card_for("power_enable", hosts["power"])
    instances = next(s for s in hosts["power"].sections if s.id == "instances")
    assert hosts["power"].powerPlanCard in instances.cards
    host = hosts["universe"]
    host.universeEnableCard.setExpand(True)
    state = host.capture_card_state()
    host.universeEnableCard.setExpand(False)
    host.restore_card_state(state)
    assert host.universeEnableCard.isExpand


def test_backend_visibility_and_running_guard(pages, monkeypatch):
    from app.content import backend
    window, hosts = pages
    monkeypatch.setattr(backend, "read_active_run", lambda: None)
    monkeypatch.setattr(backend.InfoBar, "warning", Mock())
    changes = []
    hosts["run_mode"].visibilityChanged.connect(lambda: changes.append(True))
    for mode in ("cloud", "adb", "local"):
        if sys.platform != "win32" and mode == "local":
            continue
        assert backend.switch_backend(window, mode)
        assert backend.current().control_backend == mode
        assert section_visible("run_mode", mode)
        for name in ("local", "cloud", "adb"):
            assert section_visible("run_mode", name) == (name == mode)
        assert hosts["run_mode"].adbAdvancedCard.isHidden() == (mode != "adb")
        assert page_visible("fight") == (mode != "adb")
        assert hosts["daily"].dailyMemoryOneTeamCard.isHidden() == (mode == "adb")
        assert setting_visible(find_setting("reward_achievement_enable")) == (mode != "adb")
    assert changes and window.refreshBackendTasks.called
    monkeypatch.setattr(backend, "read_active_run", lambda: object())
    before = backend.current().control_backend
    assert not backend.switch_backend(window, "cloud" if before != "cloud" else "adb")
    assert backend.current().control_backend == before


def test_restore_real_controls_and_change_keys(pages, monkeypatch):
    from app.content.settings import notify
    _, hosts = pages
    changes = []
    config_events().changed.connect(changes.append)
    init = Mock()
    monkeypatch.setattr(notify, "init_notifiers", init)
    try:
        sample = {
            "overview_show_mascot": False, "notification_enable": not cfg.notification_enable,
            "use_fuel": not cfg.use_fuel, "borrow_scroll_times": 7, "currencywars_time_limit": 111,
            "local_control_mode": "background", "fight_map_version": "reward", "instance_names": {},
            "game_launch_method": "epic", "banner_path": "example.png",
            "power_plan": [{"name": "sample"}], "power_plan_keep": True,
            "fight_team_number": "9", "weekly_relic_cleanup_day_of_week": 6,
        }
        cfg.set_values(sample)
        for key in sample:
            item = find_setting(key)
            assert restore_default(item, hosts[item.page]), key
            assert not is_modified(item)
        assert hosts["currencywars"].currencywarsTimeLimitCard.spinBox.value() == cfg.currencywars_time_limit
        assert hosts["power"].borrowScrollTimesCard.valueLabel.text() == str(cfg.borrow_scroll_times)
        assert hosts["fight"].fightMapVersionCard.comboBox.currentData() == cfg.fight_map_version
        assert hosts["fight"].fightTeamEnableCard.comboBox.currentData() == cfg.fight_team_number
        assert hosts["power"].powerPlanCard.configvalue == cfg.power_plan
        assert hosts["run_mode"].gamePathCard.comboBox.currentData() == cfg.game_launch_method
        assert init.called
        assert any("notification_enable" in keys for keys in changes)
        for item in SETTINGS:
            if item.page in hosts and reset_reason(item):
                assert not restore_default(item, hosts[item.page])
        for item in SETTINGS:
            assert all(item.key_scope(k) != Scope.STATE for k in defaults_for(item))
        cfg.set_values({"fight_timestamp": 127})
        assert not is_modified(find_setting("fight_enable"))
    finally:
        config_events().changed.disconnect(changes.append)


def test_external_reload_emits_actual_keys(pages):
    _, hosts = pages
    cfg.save_config()
    path = Path(cfg.config_path)
    data = YAML(typ="safe").load(path)
    data["play_audio"] = not data["play_audio"]
    with path.open("w", encoding="utf-8") as stream:
        YAML().dump(data, stream)
    from PySide6.QtTest import QSignalSpy
    spy = QSignalSpy(config_events().changed)
    cfg._load_config(save=False)
    assert any("play_audio" in spy.at(i)[0] for i in range(spy.count()))
    assert hosts["after_run"].playAudioCard.switchButton.isChecked() == data["play_audio"]


def test_desktop_twin_after_finish_uses_shared_setting(qtbot, page_config, monkeypatch):
    monkeypatch.delenv("MARCH7TH_AFTER_FINISH", raising=False)
    config = page_config("after_finish: Exit\n")
    monkeypatch.setenv("MARCH7TH_DESKTOP_TWIN", "1")
    window = QWidget()
    qtbot.addWidget(window)
    host = PageHost(window, window)
    build_page("after_run", host)
    combo = host.afterFinishCard.comboBox
    assert [combo.itemData(i) for i in range(combo.count())] == ["None", "Exit"]
    assert card_for("script_path", host) is None
    assert not setting_visible(find_setting("script_path"))
    assert combo.currentData() == "Exit"

    path = Path(config.config_path)
    for action in AFTER_FINISH_CHOICES:
        path.write_text(f"after_finish: {action}\n", encoding="utf-8")
        config._load_config(save=False)
        expected = "Exit" if action == "Exit" else "None"
        assert combo.currentData() == config.after_finish == expected
        # 分身中保存其他设置也要保留共享配置里的原操作。
        config.set_value("play_audio", not config.play_audio)
        assert YAML(typ="safe").load(path)["after_finish"] == action

    for action in ("Exit", "None"):
        combo.setCurrentIndex(combo.findData(action))
        assert YAML(typ="safe").load(path)["after_finish"] == action
        assert config.after_finish == action
    monkeypatch.delenv("MARCH7TH_DESKTOP_TWIN")
    main_host = PageHost(window, window)
    build_page("after_run", main_host)
    main_combo = main_host.afterFinishCard.comboBox
    assert {main_combo.itemData(i) for i in range(main_combo.count())} == set(AFTER_FINISH_CHOICES)
    assert main_combo.currentData() == "None"


def test_resets_cover_composite_and_editor_cards(pages, monkeypatch):
    from app.common.signal_bus import signalBus
    from PySide6.QtTest import QSignalSpy
    _, hosts = pages
    spy = QSignalSpy(signalBus.hotkeyChangedSignal)
    examples = dict(activity_gardenofplenty_instance_type="拟造花萼（赤）", hotkey_stop_task="x",
                    daily_memory_one_team=[], borrow_friends=[], divergent_station_priority_enable=True,
                    instance_teams=[{}], forgottenhall_level=[1], notify_template={}, browser_launch_argument=["--test"],
                    update_download_proxy="http://test.invalid", telemetry_enable=not cfg.telemetry_enable,
                    asset_self_molding_resin_timestamp=123, asset_self_molding_resin_enable=not cfg.asset_self_molding_resin_enable,
                    adb_device_type="emulator", adb_tap_ms=321)
    cfg.set_values(examples)
    for key in examples:
        item = find_setting(key)
        assert restore_default(item, hosts[item.page]), key
        assert not is_modified(item)
    assert spy.count() > 0
    assert cfg.asset_self_molding_resin_timestamp == 123
    assert hosts["run_mode"].adbAdvancedCard.tapSpinBox.value() == cfg.adb_tap_ms
    assert hosts["notify"].notifyTemplateCard.configvalue == cfg.notify_template
    assert hosts["power"].borrowFriendsCard.configvalue == cfg.borrow_friends
    assert hosts["game"].autoLowerGraphicsCard.isEnabled() == (cfg.game_optimization_enable and sys.platform == "win32")


def test_task_model_operations(pages, monkeypatch):
    from types import SimpleNamespace
    from PySide6.QtCore import QObject, Signal
    from app.content.task_model import TaskModel
    from app.content.tasks import universe
    from app.content import task_model
    class Overview(QObject):
        changed = Signal(object)
    window, hosts = pages
    overview = Overview()
    overview.config = cfg
    overview.snapshot = SimpleNamespace(plan=())
    overview.request_refresh = Mock()
    overview.launch_shortcut = Mock(return_value=True)
    window._onStartTask = Mock()
    model = TaskModel(window, overview)
    monkeypatch.setattr(task_model.InfoBar, "success", Mock())
    monkeypatch.setattr(universe, "confirm_external_enable", lambda *_: False)
    cfg.set_value("universe_enable", False)
    assert not model.set_external_universe(True) and not cfg.universe_enable
    monkeypatch.setattr(universe, "confirm_external_enable", lambda *_: True)
    assert model.set_external_universe(True) and cfg.universe_enable
    assert model.set_enabled("challenge", False) and not model.enabled("challenge")
    assert model.set_reward("reward_mail_enable", False) and not cfg.reward_mail_enable
    assert not model.set_reward("after_finish", False)
    assert model.run("activity")
    assert window._onStartTask.call_args.args[0]["page_task"] == "activity"
    assert model.run("currencywars", "currencywarstemp")
    overview.launch_shortcut.assert_called_with("currencywarstemp")
    assert not model.run("daily", "_reset_fight_config")
    cfg.set_value("currencywars_strategy", "retired")
    assert model.notice("currencywars") and hosts["currencywars"].currencywarsStrategySelectCard.isHidden()
    assert model.apply_preset("currencywars", "promotion")
    assert hosts["currencywars"].currencywarsStrategySelectCard.comboBox.currentData() == cfg.currencywars_strategy
    assert not model.notice("currencywars")
    if sys.platform == "win32":
        assert model.apply_preset("fight", "acheron")
        assert hosts["fight"].fightMapVersionCard.comboBox.currentData() == "HuangQuan"
    from app.card import pushsettingcard1
    monkeypatch.setattr(pushsettingcard1, "choose_timestamp", lambda *_: (1234, None))
    assert model.edit_progress("echo_of_war_timestamp") and cfg.echo_of_war_timestamp == 1234
    cfg.set_value("fight_timestamp", 100)
    assert model.reset_progress("fight_timestamp") and cfg.fight_timestamp == 0
    assert overview.request_refresh.called


def test_notify_workers_use_drafts_and_one_recipient(pages, qtbot, monkeypatch):
    from app.content import notify_model
    from module.notification import channels, results
    from module.notification.qqbot import QqBotOpenIdBinder
    window, _ = pages
    model = notify_model.NotifyModel(window)
    sent = []
    def send(config, channel_id, draft):
        sent.append((channel_id, dict(draft)))
        return results.Delivery("sample", True)
    monkeypatch.setattr(channels, "send_test", send)
    with qtbot.waitSignal(model.testFinished) as event:
        assert model.test("telegram", {"notify_telegram_token": "unsaved"})
        assert not model.test("telegram", {})
    assert event.args == ["telegram", True, "发送成功"]
    assert len(sent) == 1 and sent[0][0] == "telegram"
    assert sent[0][1]["notify_telegram_token"] == "unsaved" and not cfg.notify_telegram_token
    monkeypatch.setattr(notify_model.MessageBox, "exec", lambda _: True)
    monkeypatch.setattr(QqBotOpenIdBinder, "capture", lambda *args: "sample-id")
    with qtbot.waitSignal(model.bound) as event:
        assert model.bind_qq("user", {"notify_qqbot_appid": "sample", "notify_qqbot_client_secret": "draft"})
    assert event.args == [True, "notify_qqbot_openid", "sample-id"] and not cfg.notify_qqbot_openid
    assert not model.binding_pending


def test_default_contract_for_each_concrete_card_class(pages):
    from collections import defaultdict
    _, hosts = pages
    classes = defaultdict(list)
    for item in SETTINGS:
        if item.page in hosts and (card := card_for(item, hosts[item.page])) is not None:
            classes[type(card)].append((item, card, hosts[item.page]))
    assert len(classes) >= 25
    for card_type, entries in classes.items():
        editable = [(item, card, host) for item, card, host in entries if not reset_reason(item)]
        if not editable:
            assert all(not restore_default(item, host) for item, _, host in entries), card_type
            continue
        item, card, host = editable[0]
        values = defaults_for(item)
        key, default = next(iter(values.items()))
        if hasattr(card, "switchButton") and isinstance(default, bool):
            alternate = not default
        elif hasattr(card, "comboBox") and card.comboBox.count() > 1:
            alternate = next(card.comboBox.itemData(i) for i in range(card.comboBox.count())
                             if card.comboBox.itemData(i) != default)
        elif isinstance(default, int):
            alternate = default - 1 if default > 1 else default + 1
        elif isinstance(default, dict):
            alternate = {**default, "test": 1}
        elif isinstance(default, list):
            alternate = default + ([default[-1]] if default else [])
        elif default in (None, ""):
            alternate = "sample"
        else:
            alternate = "test"
        if alternate != default:
            cfg.set_value(key, alternate)
            assert is_modified(item), card_type
        assert restore_default(item, host) and not is_modified(item), (item.id, card_type)
        assert all(cfg.get_value(k) == v for k, v in values.items())


def test_catalog_icon_names_exist():
    from qfluentwidgets import FluentIcon
    from app.common.icon import BrandIcon, UiIcon
    from app.content.backend import options
    from module.channel_catalog import CHANNELS
    from module.navigation import TOP_PAGES
    from module.tool_catalog import TOOLS

    icons = {entry.icon for entry in (*PAGES, *CHANNELS, *TOOLS, *options())}
    icons.update(icon for _, _, icon in TOP_PAGES.values())
    enums = {"FIF": FluentIcon, "UiIcon": UiIcon, "BrandIcon": BrandIcon}
    for icon in icons:
        family, member = icon.split(".")
        assert member in enums[family].__members__, icon
