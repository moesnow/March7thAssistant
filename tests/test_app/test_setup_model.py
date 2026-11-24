from dataclasses import replace
import sys
import threading
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QWidget

from app.common.signal_bus import signalBus
from app.content import setup_model as setup
from module.config import cfg
from tests.test_app.test_language_switch import window


@pytest.fixture
def editable(isolated_layout, window, monkeypatch):
    for method in ("set_value", "set_values"):
        monkeypatch.setattr(cfg, method, getattr(type(cfg), method).__get__(cfg))
    monkeypatch.setattr(setup.autostart, "is_enabled", lambda: False)
    monkeypatch.setattr(setup, "read_active_run", lambda: None)
    return window


def test_tasks_settings_run_page_and_overview_update(editable, qtbot, tmp_path, monkeypatch):
    window = editable
    model = window.setupModel
    model.begin(False)
    assert not model.first_time() and not model.account_note()
    assert model.notify_model() is window.notifyModel
    before = model.initial_tasks()
    assert before == model.enabled_tasks()
    selected = before.symmetric_difference({"reward"})
    header = window.taskInterface.pages["reward"].header.joinSwitch
    with qtbot.waitSignal(model.changed):
        assert model.save_tasks(selected, model.instance()).ok
    qtbot.waitUntil(lambda: header.isChecked() == ("reward" in selected))
    assert model.initial_tasks() == selected
    game = tmp_path / "StarRail.exe"
    game.touch()
    info = tmp_path / "StarRail_Data" / "app.info"
    info.parent.mkdir()
    info.write_text("Cognosphere\nStar Rail", encoding="utf-8")
    assert model.check_game("") and model.check_game(tmp_path / "absent") and model.check_game(info)
    assert not model.check_game(game)
    assert model.set_game(game, True).ok
    host = window.settingInterface.pages["run_mode"].host
    assert host.gamePathCard.card.contentLabel.text() == str(game)
    assert host.gamePathCard.comboBox.currentData() == "epic"
    assert model.game().path == str(game)
    if sys.platform == "win32":
        assert model.run_info().show_refresh
    # 老配置中的空行由运行页忽略，向导编辑有效行时也要保留它。
    cfg.set_value("scheduled_tasks", [None])
    scheduled = replace(model.run_plan(), mode="daily", time="07:17", after="Sleep")
    assert model.save_run_plan(scheduled).ok
    assert cfg.scheduled_tasks[0] is None
    qtbot.waitUntil(lambda: any(i.time == "07:17" for i in window.scheduleModel.items()))
    qtbot.waitUntil(lambda: window.homeInterface.model.snapshot.schedule is not None
                   and window.homeInterface.model.snapshot.schedule.at.strftime("%H:%M") == "07:17")
    assert "睡眠" in model.summary()[3].text
    assert tuple(r.step for r in model.summary()) == model.STEPS
    with qtbot.waitSignal(model.changed):
        cfg.set_value("browser_type", "edge")
    assert model.cloud().browser == "edge"
    assert model.set_cloud("chrome", True).ok and host.browserTypeCard.comboBox.currentData() == "chrome"
    assert host.browserHeadlessCard.switchButton.isChecked()
    monkeypatch.setattr(window.runController, "isTaskRunning", lambda: True)
    assert not model.set_backend("cloud").ok


def test_first_preset_account_plan_and_notify(editable, qtbot, tmp_path, monkeypatch):
    from module.accounts.files import write_yaml
    from module.accounts.store import AccountStore
    model = editable.setupModel
    monkeypatch.setattr(setup.state, "untouched", lambda _: True)
    model.begin(True)
    assert model.first_time() and model.initial_tasks() == model.preset_tasks("recommended")
    assert model.match_preset(model.initial_tasks()) == "recommended"
    model.begin(False)
    cfg.set_values({"notify_winotify_enable": True, "notify_bark_enable": False})
    if sys.platform == "win32":
        assert model.notify_text() == "只有 Windows 通知"
    cfg.set_values({"notify_winotify_enable": False, "notify_bark_enable": True})
    assert "Bark" in model.notify_text()
    cfg.set_value("notify_bark_enable", False)
    assert model.notify_text() == "没有通知"
    with qtbot.waitSignal(model.changed):
        signalBus.adbDevicesChanged.emit((SimpleNamespace(model="测试设备", serial="abc", ready=True),))
    assert model.device_text() == "测试设备"
    if sys.platform != "win32":
        return
    store = AccountStore(tmp_path / "accounts", role="ui")
    write_yaml(store.index_path, {"enabled": True, "current": "100000123", "accounts": [
        {"uid": "100000123", "name": "小号", "plan": "independent"}]})
    base = cfg.config["reward_enable"]
    try:
        cfg.bind_account("100000123", store=store)
        assert cfg.bound_account == "100000123"
        assert "小号" in model.account_note()
        enabled = model.initial_tasks().symmetric_difference({"reward"})
        assert model.save_tasks(enabled, model.instance()).ok
        assert cfg.config["reward_enable"] == base
        assert store.read("100000123", "plan.yaml")["reward_enable"] != base
    finally:
        cfg.bind_account(None)


def test_unchanged_steps_and_failed_writes(editable, qtbot, tmp_path, monkeypatch):
    import copy
    from pathlib import Path

    model = editable.setupModel
    path = tmp_path / "StarRail.exe"
    path.touch()
    cfg.set_values({"game_path": str(path), "game_launch_method": "direct", "setup_wizard_pending": True})
    model.begin(False)
    assert model.game().path == str(path)
    cloud = model.cloud()
    enabled, instance = model.initial_tasks(), model.instance()
    plan = model.run_plan()
    write = Mock(side_effect=PermissionError("file denied"))
    monkeypatch.setattr(cfg, "set_values", write)
    assert model.set_backend(model.backend()).ok
    assert model.set_game(path, False).ok
    assert model.set_cloud(cloud.browser, cloud.headless).ok
    assert model.save_tasks(enabled, instance).ok
    assert model.save_run_plan(plan).ok
    write.assert_not_called()

    # 配置文件在向导停留期间被编辑，再点下一步保留外部编辑。
    data = copy.deepcopy(cfg.config)
    data["browser_headless_enable"] = not cloud.headless
    with Path(cfg.config_path).open("w", encoding="utf-8") as stream:
        cfg.yaml.dump(data, stream)
    dialog = QDialog(editable)
    monkeypatch.setattr(editable, "_setup_dialog", dialog)
    settings_page = editable.settingInterface
    with qtbot.waitSignal(model.changed):
        editable.config_watcher._emit_change()
    assert editable.settingInterface is settings_page and editable._reload_after_setup
    assert model.set_cloud(cloud.browser, cloud.headless).ok
    assert cfg.browser_headless_enable != cloud.headless and not write.called
    assert not model.set_game(path, True).ok
    assert cfg.game_launch_method == "direct"
    monkeypatch.setattr(cfg, "set_value", write)
    assert not model.dismiss().ok and model.pending(cfg)
    assert "file denied" in model.close_result.text


def test_background_search_ignores_repeat_and_survives_owner_destruction(qtbot, tmp_path, monkeypatch):
    from PySide6.QtCore import QEvent, QCoreApplication, QThreadPool
    from app.content.settings_state import config_events
    path = tmp_path / "StarRail.exe"
    path.touch()
    release = threading.Event()
    ids = []
    def search(_):
        ids.append(threading.get_ident())
        release.wait(3)
        return [setup.game_search.Found(str(path), "hoyoplay")]
    monkeypatch.setattr(setup.game_search, "search_games", search)
    window = QWidget()
    window.runController = Mock()
    window.accountModel = SimpleNamespace(bindingChanged=config_events(cfg).reloaded)
    window.notifyModel = SimpleNamespace(changed=config_events(cfg).reloaded)
    model = setup.SetupModel(window)
    with qtbot.waitSignal(model.searchFinished):
        model.search_game()
        model.search_game()
        assert model.searching()
        release.set()
    assert ids == [ids[0]] and ids[0] != threading.get_ident()
    assert not model.searching() and model.candidates()[0].source_text == "官方启动器"
    release.clear()
    model.search_game()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    release.set()
    assert QThreadPool.globalInstance().waitForDone(3000)


def test_main_window_startup_actions_and_settings_search(editable, qtbot, monkeypatch):
    from app import main_window as main
    window = editable
    model = window.setupModel
    events = []
    monkeypatch.setattr(main, "checkUpdate", lambda owner, flag: events.append(("update", flag)))
    monkeypatch.setattr(main, "checkAnnouncement", lambda owner: events.append("announcement"))
    monkeypatch.setattr(window, "startFullTask", lambda: events.append("run"))
    monkeypatch.setattr(main.InfoBar, "info", Mock())
    monkeypatch.setattr(main.InfoBar, "warning", Mock())
    class Dialog(QWidget):
        closed = Signal(bool)
        runRequested = Signal()
        linkRequested = Signal(str)
        def __init__(self, model, parent):
            super().__init__(parent)
            self.model = model
        def open(self):
            self.show()
        def done_step(self, complete):
            self.model.finish() if complete else self.model.dismiss()
            self.close()
            self.closed.emit(complete)
    module = ModuleType("app.setup.dialog")
    module.SetupDialog = Dialog
    monkeypatch.setitem(sys.modules, module.__name__, module)
    cfg.set_value("setup_wizard_pending", True)
    window.start_minimized_to_tray = False
    monkeypatch.setattr(window.runController, "isTaskRunning", lambda: False)
    for task, tray, twin, readonly, paused in [
        ("main", False, False, False, False), (None, True, False, False, False),
        (None, False, True, False, False), (None, False, False, True, False), (None, False, False, False, True)]:
        with monkeypatch.context() as patch:
            patch.setattr(window, "startup_task", task)
            patch.setattr(window, "start_minimized_to_tray", tray)
            patch.setattr(setup, "in_desktop_twin", lambda: twin)
            patch.setattr(cfg, "_readonly", readonly)
            patch.setattr(cfg, "writes_suspended", paused)
            assert not window._shouldOpenSetup() and model.pending(cfg)
            if twin or readonly or paused:
                assert not window.openSetup()
    with monkeypatch.context() as patch:
        patch.setattr(window.runController, "isTaskRunning", lambda: True)
        assert not window._shouldOpenSetup() and model.pending(cfg)
    assert window._shouldOpenSetup(), (window.startup_task, window.start_minimized_to_tray,
                                       model.pending(cfg), model.blocked_reason())
    window._finishStartup()
    assert window._setup_dialog is None and not events
    qtbot.waitUntil(lambda: window._setup_dialog is not None)
    dialog = window._setup_dialog
    assert not dialog.isWindow() and model.first_time()
    assert window.openSetup() and window._setup_dialog is dialog and not events
    monkeypatch.setattr(window.runController, "isTaskRunning", lambda: True)
    dialog.done_step(False)
    qtbot.waitUntil(lambda: events == [("update", True), "announcement"])
    assert not model.pending(cfg) and "设置 › 高级" in main.InfoBar.info.call_args.args[1]
    assert main.InfoBar.info.call_args.kwargs["duration"] == 6000
    assert window.navigate("setting:setup_wizard")
    page = window.settingInterface.pages["advanced"]
    assert page.host.sections[0].cards[0] is page.host.setupWizardCard
    for word in ("向导", "新手", "引导", "初始化", "首次设置", "重新配置"):
        assert window.searchIndex.query(word, settings_only=True)[0].link == "setting:setup_wizard"
    page.host.setupWizardCard.button.click()
    dialog = window._setup_dialog
    assert not model.first_time()
    dialog.runRequested.emit()
    assert "run" not in events
    dialog.done_step(True)
    qtbot.waitUntil(lambda: "run" in events)
    assert window.openSetup()
    dialog = window._setup_dialog
    navigate = Mock()
    monkeypatch.setattr(window, "navigate", navigate)
    dialog.done_step(True)
    dialog.linkRequested.emit("setting:game_path")
    qtbot.waitUntil(lambda: navigate.called)
    navigate.assert_called_once_with("setting:game_path")


def test_constructor_and_search_failures_reach_existing_logger(editable, qtbot, monkeypatch):
    from app import main_window as main
    from module.logger import log
    error = Mock()
    monkeypatch.setattr(log, "error", error)
    info = Mock()
    monkeypatch.setattr(main.InfoBar, "error", info)
    monkeypatch.setattr("app.setup.dialog.SetupDialog", Mock(side_effect=ValueError("bad panel")))
    assert not editable.openSetup() and editable._setup_dialog is None
    assert "ValueError" in error.call_args.args[0] and "bad panel" in info.call_args.args[1]
    monkeypatch.setattr(setup.game_search, "search_games", Mock(side_effect=OSError("missing source")))
    model = editable.setupModel
    with qtbot.waitSignal(model.searchFinished, timeout=3000):
        model.search_game()
    assert not model.searching() and not model.candidates()
    assert "OSError" in error.call_args.args[0]


def test_reopening_uses_new_configured_game_even_if_old_search_is_still_running(editable, qtbot, monkeypatch):
    model = editable.setupModel
    old_entered, release_old = threading.Event(), threading.Event()
    monkeypatch.setitem(cfg.config, "game_path", "first/StarRail.exe")
    def search(path):
        if path.startswith("first"):
            old_entered.set()
            release_old.wait(5)
        return [setup.game_search.Found(path, "configured")]
    monkeypatch.setattr(setup.game_search, "search_games", search)
    model.search_game()
    try:
        qtbot.waitUntil(old_entered.is_set)
        monkeypatch.setitem(cfg.config, "game_path", "second/StarRail.exe")
        model.begin(False)
        with qtbot.waitSignal(model.searchFinished):
            model.search_game()
    finally:
        release_old.set()
    from PySide6.QtCore import QThreadPool
    assert QThreadPool.globalInstance().waitForDone(3000)
    qtbot.wait(20)
    assert [item.path for item in model.candidates()] == ["second/StarRail.exe"]
    model.begin(False)
    assert not model.candidates()


def test_summary_uses_saved_action_for_each_mode(editable, monkeypatch):
    model = editable.setupModel
    cfg.set_values({"scheduled_tasks": [], "after_finish": "None", "autostart_gui_task": ""})
    assert model.summary()[3].text == "我自己点开始"
    assert model.after_value("daily") == "None"
    monkeypatch.setattr(setup.autostart, "is_supported", lambda: True)
    monkeypatch.setattr(setup.autostart, "is_enabled", lambda: True)
    cfg.set_values({"autostart_gui_task": "main", "autostart_open_gui": True, "after_finish": "Sleep"})
    model.begin(False)
    assert model.summary()[3].text == "登录 Windows 后自动运行，完成后睡眠"
    cfg.set_value("scheduled_tasks", [{"program": "self", "args": "main", "time": "22:00", "post_action": "None"}])
    assert model.summary()[3].text == "每天 22:00 自动运行"
