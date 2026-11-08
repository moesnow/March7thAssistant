"""Exercise the real Qt task lifecycle without launching the game or system actions."""
from copy import deepcopy
from functools import partial
import subprocess
import sys
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QWidget


def _auxiliary_page(object_name, parent=None):
    """退出规则不访问这些页面的内容，仍保留真实 QWidget 和导航结构。"""
    page = QWidget(parent)
    page.setObjectName(object_name)
    return page


@pytest.fixture
def exit_window(qtbot, monkeypatch, tmp_path, request):
    from app import main_window as module
    from app import log_interface
    from module import localization
    from module.config import cfg

    original_language = localization.get_current_language()
    monkeypatch.setattr(cfg, "config", deepcopy(cfg.config))
    cfg.config.update(exit_app_after_success=True, after_finish="Exit", scheduled_tasks=[],
                      scheduled_run_enable=False, log_overlay_enable=False)
    monkeypatch.setattr(cfg, "config_path", str(tmp_path / "config.yaml"))
    monkeypatch.setattr(cfg, "save_config", Mock())
    monkeypatch.setattr(module, "checkThemeChange", lambda _: Mock())
    monkeypatch.setattr(module, "checkUpdate", lambda *a, **k: None)
    monkeypatch.setattr(module, "checkAnnouncement", lambda *a, **k: None)
    monkeypatch.setattr(module, "disclaimer", lambda _: None)
    monkeypatch.setattr(module.MainWindow, "initSystemTray",
                        lambda self: setattr(self, "_tray_actions", [Mock() for _ in range(4)]))
    monkeypatch.setattr(module.MainWindow, "closeEvent", lambda self, event: event.accept())
    monkeypatch.setattr(module.LogInterface, "_LogInterface__initShortcut", lambda _: None)
    monkeypatch.setattr(module.LogInterface, "_migrate_legacy_schedule", lambda _: None)
    monkeypatch.setattr(module.LogInterface, "_startScheduleTimer", lambda _: None)
    monkeypatch.setattr(module.LogInterface, "_initOverlayMonitor", lambda _: None)
    monkeypatch.setattr(log_interface.notif, "notify", Mock())
    localization.load_language("zh_CN")
    if getattr(request, "param", "focused") != "full":
        # 每个用例仍新建真实 MainWindow、LogInterface、QProcess 和 QTimer，
        # 走原有初始化与信号连接；只省去与退出规则无关的六个完整页面。
        # 设置开关和成功退出另用 full 参数覆盖完整窗口，避免状态共享。
        for name, object_name in (
            ("HomeInterface", "homeInterface"),
            ("HelpInterface", "helpInterface"),
            ("WarpInterface", "warpInterface"),
            ("ToolsInterface", "toolsInterface"),
            ("WorkflowInterface", "workflowInterface"),
            ("SettingInterface", "settingInterface"),
        ):
            monkeypatch.setattr(module, name, partial(_auxiliary_page, object_name))
    page = module.MainWindow(start_minimized_to_tray=True)
    qtbot.addWidget(page)
    if getattr(request, "param", "focused") == "full":
        page.show()
        qtbot.wait(1)
    page.quitApp = Mock()
    page.logInterface._perform_post_action = Mock()
    page.completed_sequences = []
    page.logInterface.taskSequenceFinished.connect(page.completed_sequences.append)
    yield page
    page._cancelTaskExit()
    page._language_change_timer.stop()
    page._config_reload_timer.stop()
    if page.logInterface.process:
        page.logInterface.process.kill()
        page.logInterface.process.waitForFinished(3000)
    page.logInterface.cleanup()
    if page.logInterface._log_overlay:
        page.logInterface._log_overlay.deleteLater()
    localization.load_language(original_language)
    page.hide()


@pytest.fixture
def harmless_task(tmp_path):
    def make(name="one", code=0, delay=0.02, **overrides):
        script = tmp_path / (name + ".py")
        script.write_text(
            "import sys, time\n"
            f"time.sleep({delay!r})\n"
            f"sys.exit({code!r})\n", encoding="utf-8")
        task = {"id": name, "name": name, "program": sys.executable,
                "args": subprocess.list2cmdline([str(script)]), "timeout": 0,
                "enabled": False, "post_action": "None", "notify": False}
        task.update(overrides)
        return task
    return make


def wait_finished(window, qtbot, count=1):
    qtbot.waitUntil(lambda: len(window.completed_sequences) >= count, timeout=10000)
    assert not window.logInterface._hasActiveStartedProcess()


def test_old_config_defaults_off_and_new_setting_persists_independently(tmp_path):
    from module.config.config import Config

    path = tmp_path / "config.yaml"
    path.write_text("after_finish: Exit\n", encoding="utf-8")
    config = Config.__new__(Config)
    Config.__init__(config, "assets/config/version.txt", "assets/config/config.example.yaml", str(path))
    assert config.exit_app_after_success is False
    config.set_value("exit_app_after_success", True)
    loaded = Config.__new__(Config)
    Config.__init__(loaded, "assets/config/version.txt", "assets/config/config.example.yaml", str(path))
    assert loaded.exit_app_after_success is True
    assert loaded.after_finish == "Exit"


@pytest.mark.parametrize("exit_window", ["full"], indirect=True)
def test_setting_switch_does_not_replace_exit_game(exit_window):
    from module.config import cfg

    card = exit_window.settingInterface.exitAppAfterSuccess
    assert card.configname == "exit_app_after_success"
    assert card.switchButton.isChecked()
    card.switchButton.setChecked(False)
    assert cfg.get_value("exit_app_after_success") is False
    card.switchButton.setChecked(True)
    assert cfg.get_value("exit_app_after_success") is True
    assert cfg.after_finish == "Exit"
    assert "启用按时任务" in card.contentLabel.text()


@pytest.mark.parametrize("exit_window", ["focused", "full"], indirect=True)
def test_single_success_uses_real_timer_and_existing_quit_path(exit_window, harmless_task, qtbot):
    from module.config import cfg

    assert exit_window.TASK_EXIT_DELAY_MS == 5000
    exit_window.TASK_EXIT_DELAY_MS = 20
    exit_window.logInterface.startTask(harmless_task())
    qtbot.waitUntil(lambda: exit_window.quitApp.called, timeout=10000)
    exit_window.quitApp.assert_called_once_with()
    assert exit_window.completed_sequences == [0]
    assert cfg.after_finish == "Exit"


@pytest.mark.parametrize("enabled", [False, True])
def test_single_failure_never_auto_closes(exit_window, harmless_task, qtbot, enabled):
    from module.config import cfg

    cfg.config["exit_app_after_success"] = enabled
    exit_window.logInterface.startTask(harmless_task(code=1))
    wait_finished(exit_window, qtbot)
    assert exit_window.completed_sequences == [1]
    assert not exit_window._task_exit_timer.isActive()
    exit_window.quitApp.assert_not_called()


def test_disabled_setting_preserves_existing_behavior(exit_window, harmless_task, qtbot):
    from module.config import cfg

    cfg.config["exit_app_after_success"] = False
    exit_window.logInterface.startTask(harmless_task())
    wait_finished(exit_window, qtbot)
    assert not exit_window._task_exit_timer.isActive()
    exit_window.quitApp.assert_not_called()


@pytest.mark.parametrize("first_code", [0, 1])
@pytest.mark.parametrize("cli_exit", [False, True])
def test_entire_chain_must_succeed(exit_window, harmless_task, qtbot, first_code, cli_exit):
    from module.config import cfg

    cfg.config["scheduled_chain_continue_on_failure"] = True
    cfg.config["exit_app_after_success"] = not cli_exit
    exit_window.startup_task = "main" if cli_exit else None
    exit_window.exit_on_complete = cli_exit
    root = harmless_task("root", code=first_code)
    child = harmless_task("child", trigger_mode="chain", enabled=True)
    last = harmless_task("last", trigger_mode="chain", enabled=True)
    per_task = []
    exit_window.logInterface.taskFinished.connect(per_task.append)
    exit_window.logInterface.runScheduledTask(root, tasks=[root, child, last], manual=True)
    wait_finished(exit_window, qtbot)
    assert per_task == [first_code, 0, 0]
    assert exit_window.completed_sequences == [0 if first_code == 0 else 1]
    assert exit_window._task_exit_timer.isActive() == (first_code == 0)
    exit_window.quitApp.assert_not_called()


@pytest.mark.parametrize("failed_index", [0, 1])
def test_failed_start_is_not_lost_or_completed_twice(exit_window, harmless_task, qtbot, tmp_path, failed_index):
    from module.config import cfg

    cfg.config["scheduled_chain_continue_on_failure"] = True
    root = harmless_task("root")
    child = harmless_task("child", trigger_mode="chain", enabled=True)
    tasks = [root, child]
    tasks[failed_index]["program"] = str(tmp_path / "missing.exe")
    exit_window.logInterface.runScheduledTask(root, tasks=tasks, manual=True)
    wait_finished(exit_window, qtbot)
    assert exit_window.completed_sequences == [1]
    assert not exit_window._task_exit_timer.isActive()


def test_new_run_does_not_inherit_failed_chain(exit_window, harmless_task, qtbot):
    root = harmless_task("failed", code=1)
    child = harmless_task("child", trigger_mode="chain", enabled=True)
    exit_window.logInterface.runScheduledTask(root, tasks=[root, child], manual=True)
    wait_finished(exit_window, qtbot)
    exit_window.logInterface.startTask(harmless_task("fresh"))
    wait_finished(exit_window, qtbot, count=2)
    assert exit_window.completed_sequences == [1, 0]
    assert exit_window._task_exit_timer.isActive()


def test_new_task_cancels_countdown_and_queued_callback(exit_window, harmless_task, qtbot):
    page = exit_window.logInterface
    page.startTask(harmless_task("first"))
    wait_finished(exit_window, qtbot)
    assert exit_window._task_exit_timer.isActive()
    page.startTask(harmless_task("second", code=1, delay=0.2))
    assert not exit_window._task_exit_timer.isActive()
    exit_window._task_exit_timer.timeout.emit()
    exit_window.quitApp.assert_not_called()
    wait_finished(exit_window, qtbot, count=2)
    assert not exit_window._task_exit_pending


@pytest.mark.parametrize("change", ["disabled", "schedule", "post_action"])
def test_countdown_rechecks_new_config_or_pending_work(exit_window, harmless_task, qtbot, change):
    from module.config import cfg

    page = exit_window.logInterface
    page.startTask(harmless_task())
    wait_finished(exit_window, qtbot)
    if change == "disabled":
        cfg.config["exit_app_after_success"] = False
    elif change == "schedule":
        cfg.config["scheduled_tasks"] = [{"enabled": True, "trigger_mode": "time", "time": "04:00"}]
    else:
        page._schedulePostAction("Shutdown")
    exit_window._task_exit_timer.timeout.emit()
    exit_window.quitApp.assert_not_called()
    assert not exit_window._task_exit_pending
    if change == "post_action":
        assert page._pending_post_action_timer.isActive()
        page._perform_post_action.assert_not_called()


@pytest.mark.parametrize("cli_exit", [False, True])
def test_enabled_time_schedule_is_preserved_unless_cli_explicitly_exits(
        exit_window, harmless_task, qtbot, cli_exit):
    from module.config import cfg

    cfg.config["scheduled_tasks"] = [{"enabled": True, "time": "04:00"}]
    cfg.config["exit_app_after_success"] = not cli_exit
    exit_window.startup_task = "main" if cli_exit else None
    exit_window.exit_on_complete = cli_exit
    exit_window.logInterface.startTask(harmless_task())
    wait_finished(exit_window, qtbot)
    assert exit_window._task_exit_timer.isActive() == cli_exit
    if cli_exit:
        exit_window._task_exit_timer.timeout.emit()
        exit_window.quitApp.assert_called_once_with()
    else:
        assert "仍有已启用的按时任务" in (exit_window.logInterface.logTextEdit.toPlainText() + exit_window.logInterface._buffered_logs)


@pytest.mark.parametrize("cli_exit", [False, True])
def test_scheduled_post_action_is_never_canceled_by_auto_exit(exit_window, harmless_task, qtbot, cli_exit):
    exit_window.startup_task = "main" if cli_exit else None
    exit_window.exit_on_complete = cli_exit
    task = harmless_task(post_action="Shutdown")
    exit_window.logInterface.runScheduledTask(task, tasks=[task], manual=True)
    wait_finished(exit_window, qtbot)
    assert exit_window.logInterface._pending_post_action_timer.isActive()
    assert not exit_window._task_exit_timer.isActive()
    exit_window.logInterface._perform_post_action.assert_not_called()


@pytest.mark.parametrize("stopped", [False, True])
def test_external_task_completion_obeys_same_rule(exit_window, stopped):
    page = exit_window.logInterface
    page.startExternalTask("safe in-process task")
    page.finishExternalTask(0, user_stopped=stopped)
    assert exit_window.completed_sequences == [1 if stopped else 0]
    assert exit_window._task_exit_timer.isActive() == (not stopped)


@pytest.mark.parametrize("reason", ["crash", "user_stop", "timeout"])
def test_zero_exit_code_does_not_hide_abnormal_completion(exit_window, reason):
    from app.log_interface import _TaskSequence

    page = exit_window.logInterface
    page.process = QProcess(page)
    page._task_sequence = _TaskSequence()
    page._user_initiated_stop = reason == "user_stop"
    page._stopped_abnormally = reason == "timeout"
    status = QProcess.CrashExit if reason == "crash" else QProcess.NormalExit
    page._onProcessFinished(0, status, page.process)
    assert exit_window.completed_sequences == [1]
    assert not exit_window._task_exit_pending


def test_conflict_replacement_starts_fresh_sequence(exit_window, harmless_task, qtbot):
    page = exit_window.logInterface
    old = harmless_task("old", code=1, delay=0.2)
    new = harmless_task("replacement")
    page.startTask(old)
    page._pending_start_task_after_stop = (new, new, [])
    page._suppress_chain_continuation_once = True
    wait_finished(exit_window, qtbot)
    assert exit_window.completed_sequences == [0]
    assert exit_window._task_exit_timer.isActive()
    assert "延迟启动任务" in (page.logTextEdit.toPlainText() + page._buffered_logs)


def test_starting_process_and_queued_work_block_exit(exit_window):
    from types import SimpleNamespace

    page = exit_window.logInterface
    page.process = SimpleNamespace(state=lambda: QProcess.Starting)
    assert page.autoCloseBlockReason() == "仍有运行中或排队的任务"
    page.process = None
    page._pending_start_task_after_stop = ({}, {}, [])
    assert page.autoCloseBlockReason() == "仍有运行中或排队的任务"
    page._pending_start_task_after_stop = None


def test_user_stop_of_real_process_does_not_close_assistant(exit_window, harmless_task, qtbot):
    page = exit_window.logInterface
    page.startTask(harmless_task(delay=30))
    qtbot.waitUntil(lambda: page.process.state() == QProcess.Running, timeout=5000)
    page.stopTask(user_initiated=True)
    wait_finished(exit_window, qtbot)
    assert exit_window.completed_sequences == [1]
    assert not exit_window._task_exit_pending
    exit_window.quitApp.assert_not_called()
