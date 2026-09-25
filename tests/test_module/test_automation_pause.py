# coding:utf-8
"""module/automation 卡点插桩测试：暂停期间停止发出输入、读取入口停在卡点。"""
import threading
import time
from types import SimpleNamespace

import pytest

from module.automation.automation import Automation
from utils import pause as pause_mod
from utils.pause import PauseController


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
