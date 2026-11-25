"""首次配置向导的真实控件、模型契约和主窗口接入。外部设备、游戏和系统任务均用假对象。"""
from copy import deepcopy
from dataclasses import replace
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock
import sys

import pytest
import shiboken6
from PySide6.QtCore import QDateTime, QObject, QPoint, QSize, Qt, QThread, QTimer
from PySide6.QtWidgets import QApplication, QPushButton, QSystemTrayIcon, QWidget
from qfluentwidgets import Theme, qconfig, setTheme, setThemeColor
from ruamel.yaml import YAML

from app.common.design_tokens import EVERNIGHT_RED, MARCH7TH_PINK
from app.content import setup_model as setup
from app.content.backend import options
from app.content.notify_model import NotifyModel
from app.setup.dialog import SetupDialog
from module import localization
from module.config import cfg
from module.localization import tr
from module.overview.run_data import Outcome
from module.setup import tasks
from module.setup.run_plan import RunPlan, RunInfo
from tests.test_app.test_language_switch import window

LEFT = Qt.MouseButton.LeftButton


class FakeSetupModel(setup.SetupModel):
    """固定设备、游戏和定时数据，任务名及选项仍取当前语言的实际目录。"""

    def __init__(self, window, mode="local", first=True, windows=True):
        QObject.__init__(self, window)
        self.window = window
        self.config = cfg
        self.mode, self._first, self.windows = mode, first, windows
        self.enabled = tasks.preset_tasks("recommended", self._available())
        self.selected = ("侵蚀隧洞", "睿治之径")
        self._game = self._cloud_before = None
        self._candidates = (setup.GameCandidate("D:/Example/StarRail.exe", "hoyoplay", tr("官方启动器"),
                                                "cn", tr("国服"), False),)
        self.busy = self.block = False
        self.plan = RunPlan("manual", "04:10", "None", False, 4)
        self.calls = []

    def backends(self):
        return tuple(replace(o, available=self.windows) if o.value == "local" else o for o in options())

    def backend(self):
        return self.mode

    def set_backend(self, value):
        if self.block:
            return Outcome(False, tr("请先停止任务，再切换游戏运行位置"))
        self.calls.append(("backend", value))
        self.mode = value
        return Outcome(True)

    def game(self):
        return self._game

    def search_game(self):
        pass

    def searching(self):
        return self.busy

    def set_game(self, path, epic):
        self.calls.append(("game", path, epic))
        self._game = next(item for item in self.candidates() if item.path == path)
        return Outcome(True)

    def set_cloud(self, browser, headless):
        self.calls.append(("cloud", browser, headless))
        return Outcome(True)

    def _available(self):
        return ("power", "daily", "reward", "echo") if self.mode == "adb" else tasks.TASK_IDS

    def tasks(self):
        return tasks.tasks(self._available().__contains__)

    def initial_tasks(self):
        return self.enabled

    enabled_tasks = initial_tasks

    def save_tasks(self, enabled, instance):
        self.calls.append(("tasks", enabled, instance))
        self.enabled, self.selected = enabled, instance
        return Outcome(True)

    def instance(self):
        return self.selected

    def instance_names(self):
        return {**super().instance_names(), "拟造花萼（金）": "回忆之蕾"}

    def account_note(self):
        return ""

    def run_info(self):
        return RunInfo(self.windows, False, 0)

    def run_plan(self):
        return self.plan

    def after_options(self, mode):
        return (("None", tr("无操作")), ("Sleep", tr("睡眠")))

    def after_value(self, mode):
        return self.plan.after if self.plan.mode == mode else "None"

    def save_run_plan(self, plan):
        self.plan = plan
        self.calls.append(("plan", plan))
        return Outcome(True)

    def step_text(self, step):
        return step, "neutral"

    def summary(self):
        return tuple(setup.SummaryRow(key, key, key, "neutral") for key in self.STEPS)

    def finish(self):
        self.calls.append("finish")

    def dismiss(self):
        self.calls.append("dismiss")


@pytest.fixture
def panel(qtbot, isolated_layout, monkeypatch, tmp_path):
    window = QWidget()
    window.resize(1280, 640)
    window.titleBar = QPushButton("title", window)
    window.titleBar.setGeometry(0, 0, 240, 48)
    window.runController = SimpleNamespace(isTaskRunning=lambda: False)
    window.notifyModel = NotifyModel(window)
    qtbot.addWidget(window)
    window.show()
    monkeypatch.setattr("app.setup.dialog.animations_enabled", lambda: False)
    monkeypatch.setattr("app.tools.adb_service.list_devices", lambda *_: [])
    monkeypatch.setattr(cfg, "config", deepcopy(cfg._account_defaults))
    monkeypatch.setattr(cfg, "config_path", str(tmp_path / "config.yaml"))

    def make(mode="local", first=True, windows=True):
        model = FakeSetupModel(window, mode, first, windows)
        dialog = SetupDialog(model, window)
        dialog.open()
        QApplication.processEvents()
        return model, dialog
    return make


def click(qtbot, widget):
    qtbot.mouseClick(widget, LEFT)


def test_keyboard_tasks_drafts_schedule_and_done(panel, qtbot):
    model, dialog = panel()
    window = dialog.parentWidget()
    assert dialog.y() == window.titleBar.height()
    assert window.childAt(QPoint(40, 20)) is window.titleBar
    with qtbot.waitSignal(window.titleBar.clicked):
        click(qtbot, window.childAt(QPoint(40, 20)))
    QApplication.setActiveWindow(window)
    dialog.setFocus()
    for key in [Qt.Key.Key_Tab] * 28 + [Qt.Key.Key_Backtab] * 12:
        qtbot.keyClick(QApplication.focusWidget() or dialog, key)
        assert dialog.isAncestorOf(QApplication.focusWidget())
    dialog.setFocus()
    qtbot.keyClick(dialog, Qt.Key.Key_Return)
    assert dialog.currentIndex() == 1 and model.calls[-1] == ("backend", "local")
    click(qtbot, dialog.nextButton)
    assert model.calls[-1][0] == "game"
    step = dialog.currentStep()
    tile = step.tiles["fight"]
    qtbot.mouseClick(tile, LEFT, pos=QPoint(60, 20))
    assert tile.isChecked() and not any(chip.isChecked() for chip in step.chips.values())
    click(qtbot, getattr(tile.switch, "indicator", tile.switch))
    assert not tile.isChecked()
    for _ in range(2):
        click(qtbot, step.chips["daily"])
        assert step.chips["daily"].isChecked() and step._draft == model.preset_tasks("daily")
    power = step.tiles["power"]
    power.typeCombo.setCurrentIndex(0)
    assert power.instance() == ("拟造花萼（金）", "回忆之蕾")
    power.nameCombo.setCurrentIndex(power.nameCombo.findData("藏珍之蕾"))
    power.typeCombo.setCurrentIndex(3)
    power.typeCombo.setCurrentIndex(0)
    expected = ("拟造花萼（金）", "藏珍之蕾")
    assert power.instance() == expected
    click(qtbot, dialog.backButton)
    click(qtbot, dialog.nextButton)
    assert step._instance == expected
    click(qtbot, dialog.nextButton)
    assert model.calls[-1] == ("tasks", model.preset_tasks("daily"), expected)
    plan = dialog.currentStep()
    assert plan.timeRow.isHidden() and plan.loginRow.isHidden() and plan.afterRow.isVisible()
    click(qtbot, plan.cards["daily"])
    assert plan.timeRow.isVisible() and plan.loginRow.isVisible()
    click(qtbot, plan.timeChips["22:00"])
    plan.loginSwitch.setChecked(True)
    plan.afterCombo.setCurrentIndex(plan.afterCombo.findData("Sleep"))
    for mode in ("manual", "login"):
        click(qtbot, plan.cards[mode])
        assert plan._draft.after == "None" and plan.timeRow.isHidden()
        click(qtbot, plan.cards["daily"])
        assert (plan._draft.time, plan._draft.after, plan._draft.open_at_login) == ("22:00", "Sleep", True)
    click(qtbot, dialog.nextButton)
    assert model.calls[-1] == ("plan", model.plan) and dialog.nextButton.text() == tr("完成设置")
    click(qtbot, dialog.nextButton)
    assert dialog.currentStep() is dialog.donePage and not dialog.nextButton.isVisible()
    click(qtbot, dialog.donePage.lines[2].editButton)
    assert [row.state() for row in dialog.rail.rows] == ["done", "done", "current", "done", "done"]
    click(qtbot, dialog.rail.rows[4])
    assert dialog.currentIndex() == 4
    window.resize(1500, 860)
    qtbot.waitUntil(lambda: dialog.size() == QSize(1500, 812))
    assert dialog.panel.width() == 1040
    click(qtbot, dialog.nextButton)
    events = []
    dialog.closed.connect(lambda done: events.append(done))
    dialog.runRequested.connect(lambda: events.append("run"))
    click(qtbot, dialog.runButton)
    assert events == [True, "run"] and model.calls[-1] == "finish"
    qtbot.waitUntil(lambda: not shiboken6.isValid(dialog))


def test_search_skip_epic_error_and_reopen(panel, qtbot):
    model, dialog = panel()
    model.block = True
    click(qtbot, dialog.nextButton)
    assert dialog.currentIndex() == 0 and dialog.currentStep().errorStrip.isVisible()
    model.block = False
    cn = model.candidates()[0]
    model._candidates, model.busy = (), True
    click(qtbot, dialog.nextButton)
    assert not dialog.nextButton.isEnabled()
    model.busy = False
    model.searchFinished.emit()
    assert dialog.nextButton.text() == tr("先跳过")
    click(qtbot, dialog.nextButton)
    assert dialog.currentIndex() == 2 and len(model.calls) == 1
    click(qtbot, dialog.backButton)
    model._candidates = (cn, replace(cn, path="E:/Example/StarRail.exe"),
                         replace(cn, path="F:/Example/StarRail.exe", epic=True))
    model.searchFinished.emit()
    game = dialog.currentStep().page()
    assert game.path() == cn.path and len(game.rows) == 3
    click(qtbot, game.rows[2])
    assert game.epicGroup.isVisible() and game.epicSwitch.isChecked()
    click(qtbot, dialog.nextButton)
    assert model.calls[-1] == ("game", model.candidates()[2].path, True)
    with qtbot.waitSignal(dialog.closed) as closed:
        click(qtbot, dialog.closeButton)
    assert closed.args == [False] and model.calls[-1] == "dismiss"
    model, dialog = panel("cloud", first=False, windows=False)
    assert dialog.rail.titleLabel.text() == tr("首次配置向导")
    assert all(row.state() == "done" for row in dialog.rail.rows[1:])
    assert not dialog.currentStep().cards["local"].option.available
    click(qtbot, dialog.nextButton)
    cloud = dialog.currentStep().page()
    cloud.browserCombo.setCurrentIndex(cloud.browserCombo.findData("edge"))
    cloud.headlessSwitch.setChecked(True)
    click(qtbot, dialog.nextButton)
    assert model.calls[-1] == ("cloud", "edge", True)
    click(qtbot, dialog.rail.rows[3])
    assert "login" not in dialog.currentStep().cards
    click(qtbot, dialog.currentStep().cards["daily"])
    assert dialog.currentStep().loginRow.isHidden()
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert model.calls[-1] == "dismiss"


def test_close_during_real_device_worker(panel, qtbot, monkeypatch):
    entered, release = Event(), Event()
    def list_devices(*_):
        entered.set()
        release.wait(5)
        return []
    monkeypatch.setattr("app.tools.adb_service.list_devices", list_devices)
    model, dialog = panel("adb")
    click(qtbot, dialog.nextButton)
    qtbot.waitUntil(entered.is_set)
    worker = dialog.currentStep().page().deviceCard._worker
    try:
        assert isinstance(worker, QThread) and worker.isRunning()
        click(qtbot, dialog.nextButton)
        assert tuple(dialog.currentStep().tiles) == ("power", "daily", "reward", "echo")
        with qtbot.waitSignal(dialog.closed):
            click(qtbot, dialog.closeButton)
        qtbot.wait(260)
        assert shiboken6.isValid(dialog) and dialog.isHidden() and worker.isRunning()
    finally:
        release.set()
    qtbot.waitUntil(lambda: not shiboken6.isValid(dialog), timeout=3000)


@pytest.mark.parametrize("lang", ["zh_CN", "zh_TW", "en_US", "ja_JP", "ko_KR"])
def test_languages_themes_and_sizes(panel, qtbot, compiled_locales, lang, monkeypatch):
    original = localization.get_current_language()
    old_theme, old_color = qconfig.get(qconfig.themeMode), qconfig.get(qconfig.themeColor)
    monkeypatch.setattr(localization, "_locale_dir", str(compiled_locales))
    try:
        localization.load_language(lang)
        _, dialog = panel(first=False)
        if lang == "en_US":
            assert dialog.nextButton.text().isascii()
        for theme, color, size in ((Theme.LIGHT, MARCH7TH_PINK, (1280, 640)), (Theme.DARK, MARCH7TH_PINK, (1680, 960)),
                                   (Theme.DARK, EVERNIGHT_RED, (1280, 640))):
            setTheme(theme)
            setThemeColor(color)
            dialog.parentWidget().resize(*size)
            QApplication.processEvents()
            for i in range(6):
                dialog.goTo(i)
                QApplication.processEvents()
                if lang == "en_US":
                    title = dialog.currentStep().titleLabel
                    assert title.height() >= title.heightForWidth(title.width()), title.text()
                    for button in (dialog.nextButton, dialog.backButton, dialog.runButton, dialog.doneButton):
                        if button.isVisible():
                            assert button.width() >= button.sizeHint().width(), button.text()
        dialog.dismiss()
    finally:
        setTheme(old_theme)
        setThemeColor(old_color)
        localization.load_language(original)


@pytest.mark.skipif(sys.platform != "win32", reason="首次本地客户端配置")
def test_full_window_from_disclaimer_to_saved_setup(qtbot, isolated_layout, tmp_path, monkeypatch):
    from app import main_window as main
    from app.tools.disclaimer import MessageBoxDisclaimer
    from app.tools import adb_service
    from utils import game_search
    from utils.registry import star_rail_setting

    path = tmp_path / "config.yaml"
    game = tmp_path / "Example" / "StarRail.exe"
    game.parent.mkdir()
    game.touch()
    (game.parent / "StarRail_Data").mkdir()
    (game.parent / "StarRail_Data/app.info").write_text("Cognosphere\nStar Rail", encoding="utf-8")
    def saved():
        return YAML(typ="safe").load(path.read_text(encoding="utf-8"))

    monkeypatch.setenv("ProgramData", str(tmp_path))
    monkeypatch.setattr(cfg, "config", deepcopy(cfg._account_defaults))
    monkeypatch.setattr(cfg, "config_path", str(path))
    monkeypatch.setattr(cfg, "_account_layer", None)
    monkeypatch.setattr(cfg, "writes_suspended", False)
    cfg.save_config()
    assert not saved()["setup_wizard_pending"]
    checks, runs, confirmations = [], [], []
    original_exec = MessageBoxDisclaimer.exec
    def accept_in_test(box):
        def acknowledge():
            if box._confirm_waited_long_enough():
                confirmations.append(box.cancelButton.text())
                click(qtbot, box.cancelButton)
            else:
                QTimer.singleShot(100, box, acknowledge)
        QTimer.singleShot(100, box, acknowledge)
        return original_exec(box)
    monkeypatch.setattr(MessageBoxDisclaimer, "exec", accept_in_test)
    monkeypatch.setattr(main, "checkThemeChange", lambda _: Mock())
    monkeypatch.setattr(main, "checkUpdate", lambda *a, **kw: checks.append("update"))
    monkeypatch.setattr(main, "checkAnnouncement", lambda *_: checks.append("announcement"))
    monkeypatch.setattr(main.QSystemTrayIcon, "show", lambda _: None)
    monkeypatch.setattr(main.MainWindow, "closeEvent", lambda _, event: event.accept())
    for name in ("_RunController__initShortcut", "_startScheduleTimer", "_initOverlayMonitor"):
        monkeypatch.setattr(main.RunController, name, lambda _: None)
    monkeypatch.setattr(setup.autostart, "is_enabled", lambda: False)
    monkeypatch.setattr(setup.autostart, "is_legacy_task_enabled", lambda: False)
    monkeypatch.setattr("utils.uac_free.is_enabled", lambda: False)
    monkeypatch.setattr(adb_service, "list_devices", lambda *_: [])
    monkeypatch.setattr(star_rail_setting, "read_game_hotkeys", lambda *_: {})
    monkeypatch.setattr(game_search, "search_games", lambda _: [game_search.Found(str(game), "hoyoplay")])
    monkeypatch.setattr("tasks.base.tasks.start_task", runs.append)
    monkeypatch.setattr(setup, "read_active_run", lambda: None)
    monkeypatch.setattr("app.content.notify_model.init_notifiers", lambda: None)
    window = main.MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.stackedWidget.setAnimationEnabled(False)
    qtbot.waitUntil(lambda: isinstance(window._setup_dialog, SetupDialog))
    dialog = window._setup_dialog

    def press_search_shortcut(target):
        # 经过托盘还原及子控件删除后，离屏平台需要显式指定接收键盘的窗口。
        QApplication.setActiveWindow(window)
        target.setFocus(Qt.FocusReason.OtherFocusReason)
        QApplication.processEvents()
        qtbot.waitUntil(window.isActiveWindow)
        with qtbot.waitSignal(window._searchShortcut.activated):
            qtbot.keyClick(target, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)

    try:
        assert confirmations == [tr("我已知晓")] and saved()["setup_wizard_pending"] and not checks
        press_search_shortcut(dialog)
        assert window._search_popup is None
        if QApplication.platformName() == "offscreen":
            # 离屏 Qt 没有 Windows 句柄，原生窗口组另用真实窗口状态运行此用例。
            monkeypatch.setattr("qframelesswindow.windows.win_utils.isMaximized", lambda _: False)
        window.showMinimized()
        window.showNormal()
        window.onTrayIconActivated(QSystemTrayIcon.ActivationReason.Trigger)
        assert not window.isVisible()
        window.onTrayIconActivated(QSystemTrayIcon.ActivationReason.Trigger)
        assert window._setup_dialog is dialog and dialog.isVisible()
        click(qtbot, dialog.nextButton)
        assert dialog.currentIndex() == 1 and not saved()["cloud_game_enable"]
        qtbot.waitUntil(lambda: not dialog.model.searching())
        click(qtbot, dialog.nextButton)
        assert saved()["game_path"] == str(game)
        step = dialog.currentStep()
        assert step.chips["recommended"].isChecked()
        power = step.tiles["power"]
        power.typeCombo.setCurrentIndex(power.typeCombo.findData("侵蚀隧洞"))
        power.nameCombo.setCurrentIndex(power.nameCombo.findData("睿治之径"))
        click(qtbot, dialog.nextButton)
        data = saved()
        assert data["instance_names"]["侵蚀隧洞"] == "睿治之径" and data["instance_type"] == "侵蚀隧洞"
        assert data["weekly_divergent_enable"] and not data["fight_enable"]
        plan = dialog.currentStep()
        click(qtbot, plan.cards["daily"])
        click(qtbot, plan.timeChips["22:00"])
        plan.afterCombo.setCurrentIndex(plan.afterCombo.findData("Sleep"))
        plan.refreshCombo.setCurrentIndex(plan.refreshCombo.findData(6))
        click(qtbot, dialog.nextButton)
        data = saved()
        assert data["refresh_hour"] == 6 and [(r["time"], r["post_action"]) for r in data["scheduled_tasks"]] == [("22:00", "Sleep")]
        row = dialog.currentStep().panel.rows["winotify"]
        click(qtbot, getattr(row.switch, "indicator", row.switch))
        assert not saved()["notify_winotify_enable"]
        click(qtbot, dialog.nextButton)
        assert dialog.donePage.lines[3].textLabel.fullText() == "每天 22:00 自动运行，完成后睡眠"
        click(qtbot, dialog.donePage.lines[3].editButton)
        assert dialog.currentIndex() == 3
        click(qtbot, dialog.nextButton)
        click(qtbot, dialog.nextButton)
        click(qtbot, dialog.runButton)
        qtbot.waitUntil(lambda: checks == ["update", "announcement"] and runs == ["main"])
        assert not saved()["setup_wizard_pending"] and window._setup_dialog is None

        press_search_shortcut(window)
        qtbot.waitUntil(lambda: window._search_popup is not None and window._search_popup.isVisible())
        popup = window._search_popup
        popup.input.setText("向导")
        qtbot.keyClick(popup.input, Qt.Key.Key_Return)
        qtbot.waitUntil(lambda: window.settingInterface.currentCategory() == "advanced" and popup.isHidden())
        card = window.settingInterface.pages["advanced"].host.setupWizardCard
        page_targets = (window.taskInterface, window.helpInterface, window.helpInterface)
        navigate = Mock(wraps=window.navigate)
        monkeypatch.setattr(window, "navigate", navigate)
        for i, (link, page) in enumerate(zip(("task:power", "doc:Background", "doc:Tutorial"), page_targets)):
            click(qtbot, card.button)
            reopened = window._setup_dialog
            assert reopened.rail.titleLabel.text() == tr("首次配置向导")
            click(qtbot, reopened.rail.rows[4])
            click(qtbot, reopened.nextButton)
            click(qtbot, reopened.donePage.links[i])
            qtbot.waitUntil(lambda: navigate.called)
            navigate.assert_called_once_with(link)
            assert window.stackedWidget.currentWidget() is page
            navigate.reset_mock()
            assert window.navigate("setting:setup_wizard")
            navigate.reset_mock()

        click(qtbot, card.button)
        reopened = window._setup_dialog
        pending = saved()
        pending["browser_type"] = "edge"
        with path.open("w", encoding="utf-8") as stream:
            YAML().dump(pending, stream)
        with qtbot.waitSignal(reopened.model.changed):
            window.config_watcher._emit_change()
        assert reopened.model.cloud().browser == "edge"
        launch = Mock()
        monkeypatch.setattr(window.runController, "runScheduledTask", launch)
        window.runController._checkScheduledTime(QDateTime.fromString("2026-11-24 22:00:00", "yyyy-MM-dd HH:mm:ss"))
        assert launch.called and window._setup_dialog is reopened
        click(qtbot, reopened.closeButton)
        assert window._setup_dialog is None and not saved()["setup_wizard_pending"]
        monkeypatch.setattr(window.runController, "isTaskRunning", lambda: True)
        assert window.openSetup()
        running = window._setup_dialog
        click(qtbot, running.nextButton)
        assert running.currentIndex() == 0 and running.currentStep().errorStrip.isVisible()
        click(qtbot, running.closeButton)
        monkeypatch.setattr(window.runController, "setDesktopTwinHosting", Mock())
        monkeypatch.setattr(window.toolsInterface, "setDesktopTwinHosting", Mock())
        try:
            window.setDesktopTwinHosting(True)
            assert not card.isEnabled() and not window.openSetup()
        finally:
            window.setDesktopTwinHosting(False)
        monkeypatch.setattr(setup, "in_desktop_twin", lambda: True)
        assert not window.openSetup()
    finally:
        if window._setup_dialog:
            window._setup_dialog.dismiss()
        window._config_reload_timer.stop()
        window._language_change_timer.stop()
        window.runController.cleanup()
        window.hide()


def test_real_window_releases_overlay_only_after_device_query(window, qtbot, monkeypatch):
    entered, release = Event(), Event()
    def list_devices(*_):
        entered.set()
        release.wait(6)
        return []
    monkeypatch.setattr("app.tools.adb_service.list_devices", list_devices)
    monkeypatch.setattr(setup.autostart, "is_enabled", lambda: False)
    monkeypatch.setattr(setup, "read_active_run", lambda: None)
    monkeypatch.setattr(window.runController, "isTaskRunning", lambda: False)
    monkeypatch.setitem(cfg.config, "control_backend", "adb")
    monkeypatch.setitem(cfg.config, "ui_profile", "touch_720")
    assert window.openSetup()
    dialog = window._setup_dialog
    click(qtbot, dialog.nextButton)
    try:
        qtbot.waitUntil(entered.is_set)
        worker = dialog.currentStep().page().deviceCard._worker
        click(qtbot, dialog.closeButton)
        assert window._setup_dialog is None
        qtbot.wait(230)
        assert shiboken6.isValid(dialog) and worker.isRunning()
    finally:
        release.set()
    qtbot.waitUntil(lambda: not shiboken6.isValid(dialog), timeout=3000)
