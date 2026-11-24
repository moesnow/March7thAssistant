from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from PySide6.QtCore import QObject, Signal
from ruamel.yaml import YAML

from app.common.signal_bus import signalBus
from app.overview_model import OverviewModel
from app.navigation import navigate
from module.navigation import parse_link
from module.overview.samples import _Config
from utils import runs


class Page(QObject):
    taskStarted = Signal()
    taskFinished = Signal(int)
    pauseStateChanged = Signal()


def test_signals_actions_and_late_created_runs(qtbot, monkeypatch, tmp_path):
    import json
    from PySide6.QtTest import QSignalSpy
    cfg = _Config(**YAML(typ="safe").load(Path("assets/config/config.example.yaml")))
    cfg.config_path = str(tmp_path / "config.yaml")
    Path(cfg.config_path).write_text("enabled", encoding="utf-8")
    cfg._load_config = Mock()
    window = QObject()
    page = window.runController = Page(window)
    page.isTaskRunning, page.stop, page.toggle_pause = Mock(return_value=False), Mock(), Mock()
    page._pause_supported, page._pause_state, page._task_name_is_msgid = True, "running", True
    page._task_display_name, page.current_task, page.process = "完整运行", "main", None
    window._onStartTask, window.startFullTask = Mock(), Mock()
    directory = tmp_path / "logs/runs"
    monkeypatch.setattr(runs, "runs_dir", lambda: str(directory))
    now = datetime(2026, 11, 23, 13)
    model = OverviewModel(window, config=cfg, clock=lambda: now)
    spy = QSignalSpy(model.changed)
    with qtbot.waitSignal(model.changed):
        model._minute.timeout.emit()
    with qtbot.waitSignal(model.changed):
        page.isTaskRunning.return_value = True
        page.taskStarted.emit()
    assert model.snapshot.greeting.state == "running"
    with qtbot.waitSignal(model.changed):
        page._pause_state = "paused"
        page.pauseStateChanged.emit()
    assert model.snapshot.greeting.buttons[1].text == "继续任务"
    assert model.stop() and model.toggle_pause()
    page.stop.assert_called_once()
    page.toggle_pause.assert_called_once()
    with qtbot.waitSignal(model.changed):
        page.isTaskRunning.return_value = False
        page.taskFinished.emit(0)
    with qtbot.waitSignal(model.changed, timeout=3000):
        Path(cfg.config_path).write_text("changed and saved", encoding="utf-8")
    cfg._load_config.assert_called()
    with qtbot.waitSignal(model.changed, timeout=3000):
        directory.mkdir(parents=True)
        data = {"task":"daily", "started_at": now.isoformat(), "status":"success", "invoker":"gui"}
        (directory / "20261123-130000-abcd.json").write_text(json.dumps(data), encoding="utf-8")
    assert model.snapshot.last_run.task == "daily" and spy.count() >= 6
    with qtbot.waitSignal(signalBus.startTaskSignal) as signal:
        assert model.start_task("power")
    assert signal.args == ["power"] and not model.start_task("unknown")
    model.start_full()
    window.startFullTask.assert_called_once()
    window.toolsInterface = Mock()
    assert model.launch_shortcut("autoplot") and model.launch_shortcut("screenshot")
    window.toolsInterface.toggleAutoPlot.assert_called_once()
    window.toolsInterface.gameScreenshotCard.clicked.emit.assert_called_once()
    assert not model.launch_shortcut("unregistered")
    assert model.retry_step("echo") and not model.retry_step("prepare")
    assert window._onStartTask.call_args.args[0]["retry_step"] == "echo"


def test_run_navigation(monkeypatch, tmp_path):
    from PySide6.QtGui import QDesktopServices
    monkeypatch.setattr(runs, "runs_dir", lambda: str(tmp_path))
    window = Mock()
    monkeypatch.setattr("app.navigation.highlight", Mock())
    assert navigate(window, "run:current")
    window.switchTo.assert_called_once_with(window.logInterface)
    assert navigate(window, "run:schedule")
    window.logInterface.showSchedule.assert_called_once()
    for link in ("run:../test", "run:current#file", "run:fake.json"):
        assert parse_link(link) is None
    run_id = "20261123-130000-abcd"
    warning = Mock()
    monkeypatch.setattr("qfluentwidgets.InfoBar.warning", warning)
    window.logInterface.showRun.return_value = False
    assert not navigate(window, "run:" + run_id)
    warning.assert_called_once()
    window.logInterface.showRun.return_value = True
    assert navigate(window, "run:" + run_id)
    window.logInterface.showRun.assert_called_with(run_id)


def test_appearance_controls_offscreen(qtbot, monkeypatch, tmp_path):
    from app.setting_interface import SettingInterface
    from app.content.settings.appearance import cfg, QFileDialog
    from module.overview.cards import background_path
    example = YAML(typ="safe").load(Path("assets/config/config.example.yaml"))
    monkeypatch.setattr(cfg, "config", example)
    monkeypatch.setattr(cfg, "config_path", str(tmp_path / "config.yaml"))
    cfg.set_values({"banner_path": "./assets/app/images/bg37.jpg", "overview_show_mascot": True})
    page = SettingInterface()
    qtbot.addWidget(page)
    assert background_path(cfg) == ""
    chosen = str(tmp_path / "背景.png")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_: (chosen, "Images"))
    page.pages["appearance"].host.overviewBackgroundCard.leftClicked.emit()
    assert cfg.banner_path == background_path(cfg) == chosen
    page.pages["appearance"].host.overviewBackgroundCard.rightClicked.emit()
    assert cfg.banner_path == ""
    page.pages["appearance"].host.overviewMascotCard.switchButton.setChecked(False)
    assert cfg.overview_show_mascot is False


def test_task_icons_resolve_and_extra_actions_use_original_targets(qapp, monkeypatch, tmp_path):
    from qfluentwidgets import FluentIcon
    from PySide6.QtGui import QDesktopServices
    from app.common.icon import UiIcon
    from app.common.home_actions import run_home_extra
    from module.overview.plan import STEPS
    from module.overview.shortcuts import ICONS
    from utils import external_config
    enums = {"UiIcon": UiIcon, "FIF": FluentIcon}
    for name in set(ICONS) | {step.icon for step in STEPS.values()}:
        family, member = name.split(".")
        assert member in enums[family].__members__
    cfg = _Config(fight_path=str(tmp_path))
    reset, open_url = Mock(return_value=[]), Mock(return_value=True)
    monkeypatch.setattr(external_config, "reset", reset)
    monkeypatch.setattr(QDesktopServices, "openUrl", open_url)
    assert run_home_extra(None, cfg, "_reset_fight_config")
    reset.assert_called_once_with("fight", str(tmp_path))
    assert run_home_extra(None, cfg, "_open_fight_dir")
    assert Path(open_url.call_args.args[0].toLocalFile()) == tmp_path
    assert run_home_extra(None, cfg, "_open_fight_homepage")
    assert open_url.call_args.args[0].host() == "github.com"
