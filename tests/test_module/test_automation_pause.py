# coding:utf-8
"""module/automation 卡点插桩测试：暂停期间停止发出输入、读取入口停在卡点。"""
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from module.automation.automation import Automation
from utils import pause as pause_mod
from utils.pause import PauseController, RunStopRequested


class _Boom(Exception):
    """哨兵异常：证明调用停在卡点（尚未执行方法体）。"""


class _BlockingController:
    """可手动控制暂停/恢复的卡点桩。"""

    def __init__(self):
        self.resume = threading.Event()
        self.resume.set()
        self.checkpoint_calls = 0

    def checkpoint(self):
        self.checkpoint_calls += 1
        self.resume.wait()


@pytest.fixture
def blocking_controller(monkeypatch):
    ctl = _BlockingController()
    monkeypatch.setattr(pause_mod, "pause_ctl", ctl)
    return ctl


@pytest.fixture
def automation(monkeypatch, blocking_controller):
    events = []

    def record(name):
        def _call(*args, **kwargs):
            events.append((name,) + args)
        return _call

    handler = SimpleNamespace(**{
        name: record(name)
        for name in (
            "mouse_click", "mouse_down", "mouse_up", "mouse_move", "mouse_drag",
            "mouse_scroll", "press_key", "press_key_down", "press_key_up",
            "secretly_press_key", "press_mouse", "secretly_write",
        )
    })
    monkeypatch.setattr(
        "module.automation.automation.get_game_controller",
        lambda: SimpleNamespace(get_input_handler=lambda: handler),
    )
    auto = object.__new__(Automation)
    auto._init_input()
    return auto, events


def test_input_blocked_while_paused_and_resumes(automation, blocking_controller):
    auto, events = automation
    blocking_controller.resume.clear()

    done = []

    def worker():
        auto.press_key("x")
        done.append(1)

    t = threading.Thread(target=worker)
    t.start()
    time.sleep(0.3)
    assert done == []
    assert events == []  # 输入尚未发出

    blocking_controller.resume.set()
    t.join(timeout=5)
    assert done == [1]
    assert events == [("press_key", "x")]


@pytest.mark.parametrize(("backend", "profile"), [("invalid", "pc_1080"), ("local", "invalid")])
def test_invalid_connection_allows_initialization_but_not_input(automation, monkeypatch, backend, profile):
    from module.config.platform import InvalidGameConnection

    _, events = automation
    config = SimpleNamespace(control_backend=backend, ui_profile=profile)
    monkeypatch.setattr("module.automation.automation.cfg", config)
    auto = object.__new__(Automation)
    auto.__init__("test")
    assert auto.input_handler is None
    with pytest.raises(InvalidGameConnection):
        auto.mouse_click(1, 2)
    assert not events

    config.control_backend, config.ui_profile = "local", "pc_1080"
    auto.mouse_click(1, 2)
    assert events == [("mouse_click", 1, 2)]


def test_all_input_aliases_go_through_checkpoint(automation, blocking_controller):
    auto, events = automation
    blocking_controller.resume.clear()

    def worker():
        auto.mouse_click(1, 2)
        auto.mouse_drag(0, 0, 5, 5, 0.1)

    t = threading.Thread(target=worker)
    t.start()
    time.sleep(0.3)
    assert events == []
    blocking_controller.resume.set()
    t.join(timeout=5)
    assert events == [("mouse_click", 1, 2), ("mouse_drag", 0, 0, 5, 5, 0.1)]
    assert blocking_controller.checkpoint_calls >= 2


@pytest.mark.skipif(sys.platform != "win32", reason="本地输入后端仅在 Windows 使用")
def test_local_secret_typing_releases_the_current_key_and_stops_before_the_next(monkeypatch):
    from module.automation import local_input

    controller = PauseController()
    controller._enabled = True
    controller._resume_event.set()
    monkeypatch.setattr(local_input, "pause_ctl", controller)
    events = []

    def down(key):
        events.append(("down", key))
        controller.request_stop()

    def up(key):
        events.append(("up", key))

    platform = local_input.pyautogui.platformModule
    monkeypatch.setattr(platform, "_keyDown", down)
    monkeypatch.setattr(platform, "_keyUp", up)
    backend = local_input.LocalInput(Mock())

    with pytest.raises(RunStopRequested):
        backend.secretly_write("abcdef", interval=0)

    assert events == [("down", "a"), ("up", "a")]


@pytest.mark.skipif(sys.platform != "win32", reason="本地输入后端仅在 Windows 使用")
def test_local_key_press_reports_dispatch_failure(monkeypatch):
    from module.automation import local_input

    down, up = Mock(), Mock()
    monkeypatch.setattr(local_input.pyautogui, "keyDown", down)
    monkeypatch.setattr(local_input.pyautogui, "keyUp", up)
    backend = local_input.LocalInput(Mock())

    assert backend.press_key("esc", wait_time=0) is True
    up.assert_called_once_with("esc")
    down.side_effect = RuntimeError("输入不可用")
    assert backend.press_key("esc", wait_time=0) is False
    up.assert_called_once_with("esc")


def test_cdp_key_press_reports_dispatch_failure(monkeypatch):
    from module.automation.cdp_input import CdpInput

    backend = CdpInput(Mock(), Mock())
    dispatched = Mock(return_value=True)
    monkeypatch.setattr(backend, "_dispatch_key_event", dispatched)

    assert backend.press_key("esc", wait_time=0) is True
    assert [call.args for call in dispatched.call_args_list] == [("esc", "keyDown"), ("esc", "keyUp")]
    dispatched.reset_mock()
    dispatched.side_effect = RuntimeError("浏览器连接中断")
    assert backend.press_key("esc", wait_time=0) is False
    dispatched.assert_called_once_with("esc", "keyDown")


@pytest.mark.skipif(sys.platform != "win32", reason="本地输入后端仅在 Windows 使用")
def test_local_recovery_input_checks_deadline_at_dispatch(monkeypatch):
    from module.automation import local_input
    from module.automation.background_input import input_wait_limit

    pressed, clicked = Mock(), Mock()
    monkeypatch.setattr(local_input.pyautogui, "keyDown", pressed)
    monkeypatch.setattr(local_input.pyautogui, "mouseDown", clicked)
    monkeypatch.setattr(local_input, "time", SimpleNamespace(monotonic=lambda: 2.0))
    backend = local_input.LocalInput(Mock())

    with input_wait_limit(1, deadline=1.0):
        assert backend.press_key("esc") is False
        assert backend.mouse_down(770, 743) is False
    pressed.assert_not_called()
    clicked.assert_not_called()


def test_cdp_escape_checks_deadline_again_after_slow_focus(monkeypatch):
    from module.automation import cdp_input
    from module.automation.background_input import input_wait_limit

    now = [0.0]
    events = []

    def dispatch(_, payload):
        events.append(payload["type"])
        if payload["type"] == "mouseMoved":
            now[0] = 2.0

    monkeypatch.setattr(cdp_input, "time", SimpleNamespace(monotonic=lambda: now[0], sleep=lambda _: None))
    backend = cdp_input.CdpInput(SimpleNamespace(execute_cdp_cmd=dispatch), Mock())
    with input_wait_limit(1, deadline=1.0):
        assert backend.press_key("esc", wait_time=0) is False
        assert backend.mouse_down(770, 743) is False
    assert events == ["mouseMoved"]


GUARDED_METHODS = [
    "take_screenshot",
    "find_element",
    "find_image_element",
    "find_text_element",
    "find_hsv_element",
    "find_yolo_element",
    "find_image_with_multiple_targets",
    "find_yolo_with_multiple_targets",
    "find_min_distance_text_element",
    "get_single_line_text",
    "is_rgb_ratio_above_threshold",
]


@pytest.mark.parametrize("method_name", GUARDED_METHODS)
def test_read_entrypoints_hit_checkpoint_before_body(monkeypatch, method_name):
    """读取类入口先经过卡点：卡点阻塞时方法体（截图/OCR）不会执行。"""

    class _RaisingController:
        def checkpoint(self):
            raise _Boom()

    monkeypatch.setattr(pause_mod, "pause_ctl", _RaisingController())
    method = getattr(Automation, method_name)
    with pytest.raises(_Boom):
        method(SimpleNamespace())  # 传入假 self；卡点在方法体执行前触发


def test_pure_calculation_methods_are_not_guarded(monkeypatch):
    """纯计算方法不插桩，暂停功能对它们零影响。"""

    class _RaisingController:
        def checkpoint(self):
            raise _Boom()

    monkeypatch.setattr(pause_mod, "pause_ctl", _RaisingController())
    auto = object.__new__(Automation)
    # 纯计算：((left, top), (right, bottom)) -> 中心点
    assert auto.calculate_click_position(((10, 20), (30, 40))) == (20, 30)
