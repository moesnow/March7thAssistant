"""自动对话长期待机、前台窗口识别及临时异常恢复。"""

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="自动对话仅在 Windows 上启用")


@pytest.fixture
def plot(qapp, monkeypatch):
    import tasks.tool.autoplot._engine as module

    foreground = Mock(return_value=SimpleNamespace(title="test-game"))
    monkeypatch.setattr(module, "gw", SimpleNamespace(getActiveWindow=foreground))
    detector = Mock()
    detector.is_dialog_scene.return_value = True
    detector.detect_skip_button.return_value = False
    monkeypatch.setattr(module, "SceneDetector", detector)
    automation = Mock()
    automation.click_element.return_value = False
    monkeypatch.setattr(module, "auto", automation)
    monkeypatch.setattr(module, "log", Mock())
    pending = []
    single_shot = module.QTimer.singleShot
    monkeypatch.setattr(module.QTimer, "singleShot", lambda delay, callback: pending.append(callback))
    engine = module.AutoPlot("test-game")
    engine.start()
    yield SimpleNamespace(
        module=module, engine=engine, foreground=foreground,
        detector=detector, automation=automation, pending=pending, single_shot=single_shot,
    )
    engine.stop()


@pytest.mark.parametrize("title", [None, "test-game - 浏览器", "其他窗口", "test-game"])
def test_checks_exact_foreground_title(plot, title):
    plot.foreground.return_value = None if title is None else SimpleNamespace(title=title)
    assert plot.engine._is_game_window_active() is (title == "test-game")


def test_idle_polling_resumes_when_game_appears(plot, monkeypatch):
    # 模拟三天的轮询次数，无需实际等待，也不保存 Mock 调用历史。
    monkeypatch.setattr(plot.engine, "_is_game_window_active", lambda: False)
    for _ in range(3 * 24 * 60 * 60 * 2):
        plot.engine._monitor_loop()
    plot.detector.is_dialog_scene.assert_not_called()
    assert not plot.pending
    monkeypatch.setattr(plot.engine, "_is_game_window_active", lambda: True)
    plot.engine._monitor_loop()
    plot.pending.pop(0)()
    assert len(plot.pending) == 1
    assert plot.engine.is_running


def test_dialog_exception_recovers_without_toggling_switch(plot):
    plot.detector.detect_skip_button.side_effect = [RuntimeError("临时截图失败"), False]
    plot.engine._monitor_loop()
    old_session = plot.engine._dialog_session
    plot.pending.pop(0)()
    assert plot.engine.is_running
    assert plot.engine._monitor_timer.isActive()
    assert plot.engine._state == plot.module.EngineState.MONITORING
    assert not plot.engine._is_session_valid(old_session)

    plot.engine._monitor_loop()
    plot.pending.pop(0)()
    assert plot.detector.detect_skip_button.call_count == 2
    assert len(plot.pending) == 1


def test_qt_timer_recovers_after_dialog_exception(plot, qtbot, monkeypatch):
    # 使用真实 Qt 事件循环，确认异常不会逸出回调或留下假运行状态。
    monkeypatch.setattr(plot.module.QTimer, "singleShot", plot.single_shot)
    monkeypatch.setattr(plot.module.Threshold, "DIALOG_LOOP_INITIAL_DELAY", 0)
    plot.engine._monitor_timer.setInterval(10)
    plot.detector.detect_skip_button.side_effect = [RuntimeError("临时截图失败"), False]
    qtbot.waitUntil(lambda: plot.detector.detect_skip_button.call_count == 2)
    assert plot.engine.is_running
    assert plot.engine._monitor_timer.isActive()
    plot.automation.click_element.assert_called_once()


@pytest.mark.parametrize("stage", ["window", "scene", "helper"])
def test_monitor_exception_recovers_on_next_tick(plot, stage):
    error = RuntimeError("窗口或画面暂时不可用")
    if stage == "window":
        failing = plot.foreground
        result = SimpleNamespace(title="test-game")
    elif stage == "scene":
        failing = plot.detector.is_dialog_scene
        result = True
    else:
        plot.detector.is_dialog_scene.return_value = False
        failing = plot.detector.is_auto_battle_off
        result = False
    failing.side_effect = [error, result]
    plot.engine._monitor_loop()
    assert plot.engine._state == plot.module.EngineState.MONITORING
    plot.engine._monitor_loop()
    assert failing.call_count == 2
    assert plot.engine.is_running


def test_pending_dialog_is_cancelled_when_game_loses_focus(plot):
    plot.engine._monitor_loop()
    stale_callback = plot.pending.pop(0)
    plot.foreground.return_value = None
    stale_callback()
    plot.detector.detect_skip_button.assert_not_called()
    assert plot.engine._state == plot.module.EngineState.MONITORING

    # 游戏重新出现时旧会话仍不能执行，新会话正常启动。
    plot.foreground.return_value = SimpleNamespace(title="test-game")
    plot.engine._monitor_loop()
    stale_callback()
    plot.detector.detect_skip_button.assert_not_called()
    plot.pending.pop(0)()
    plot.detector.detect_skip_button.assert_called_once()


def test_pending_dialog_is_cancelled_after_stop(plot):
    plot.engine._monitor_loop()
    callback = plot.pending.pop(0)
    plot.engine.stop()
    callback()
    plot.detector.detect_skip_button.assert_not_called()
    assert not plot.pending


def test_persistent_failures_do_not_flood_log(plot, monkeypatch):
    clock = SimpleNamespace(monotonic=lambda: 100.0)
    monkeypatch.setattr(plot.module, "time", clock)
    plot.foreground.side_effect = RuntimeError("窗口不可用")
    for _ in range(20):
        plot.engine._monitor_loop()
    assert plot.module.log.warning.call_count == 1
    clock.monotonic = lambda: 131.0
    plot.engine._monitor_loop()
    assert plot.module.log.warning.call_count == 2


@pytest.mark.parametrize("stage", ["monitor", "dialog"])
def test_screenshot_failure_in_timer_never_sleeps(plot, monkeypatch, stage):
    import module.automation.automation as automation_module

    automation = object.__new__(automation_module.Automation)
    automation.window_title = "test-game"
    automation.logger = Mock()
    capture = Mock(return_value=False)
    sleep = Mock(side_effect=AssertionError("GUI 回调中不得等待截图重试"))
    monkeypatch.setattr(automation_module.Screenshot, "take_screenshot", capture)
    monkeypatch.setattr(automation_module, "time", SimpleNamespace(monotonic=lambda: 0, sleep=sleep))
    if stage == "monitor":
        plot.detector.is_dialog_scene.side_effect = lambda: automation.take_screenshot()
        plot.engine._monitor_loop()
    else:
        plot.engine._monitor_loop()
        plot.detector.detect_skip_button.side_effect = lambda: automation.take_screenshot()
        plot.pending.pop(0)()
    capture.assert_called_once()
    sleep.assert_not_called()
    assert plot.engine._state == plot.module.EngineState.MONITORING
