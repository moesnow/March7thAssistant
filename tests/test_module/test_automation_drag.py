from types import SimpleNamespace
import sys

import pytest

from module.automation.automation import Automation
from module.automation.cdp_input import CdpInput


def create_automation(events):
    automation = object.__new__(Automation)
    automation.screenshot = SimpleNamespace(width=960, height=540)
    automation.screenshot_pos = (100, 50, 960, 540)
    automation.screenshot_scale_factor = 0.5
    automation.take_screenshot = lambda: None
    automation.mouse_drag = lambda *args: events.append(("drag", *args)) or True
    return automation


def test_drag_mouse_converts_relative_coordinates():
    events = []
    automation = create_automation(events)

    result = automation.drag_mouse((0.1, 0.2), (0.9, 0.8), duration=0.1)

    assert result is True
    assert events == [("drag", 292, 266, 1828, 914, 0.1)]


@pytest.mark.skipif(sys.platform != "win32", reason="本地输入后端仅在 Windows 使用")
@pytest.mark.parametrize("failure", ["press", "move"])
def test_local_drag_releases_button_when_input_fails(monkeypatch, failure):
    from module.automation.local_input import LocalInput

    events = []
    logger = SimpleNamespace(debug=lambda *_: None, error=lambda *_: None)
    local_input = LocalInput(logger)

    def move_to(x, y, duration=None):
        events.append(("move", x, y, duration))
        if duration is not None and failure == "move":
            raise RuntimeError("movement failed")

    def mouse_down():
        events.append(("down",))
        if failure == "press":
            raise RuntimeError("press failed")

    monkeypatch.setattr("module.automation.local_input.pyautogui.moveTo", move_to)
    monkeypatch.setattr("module.automation.local_input.pyautogui.mouseDown", mouse_down)
    monkeypatch.setattr("module.automation.local_input.pyautogui.mouseUp", lambda: events.append(("up",)))

    with pytest.raises(RuntimeError, match="failed"):
        local_input.mouse_drag(10, 20, 30, 40, duration=0.1)

    assert events[-1] == ("up",)


def test_cdp_drag_marks_move_event_as_left_button_held():
    events = []
    cloud_game = SimpleNamespace(
        execute_cdp_cmd=lambda command, payload: events.append((command, payload)),
    )
    logger = SimpleNamespace(debug=lambda *_: None, error=lambda *_: None)
    cdp_input = CdpInput(cloud_game, logger)

    result = cdp_input.mouse_drag(10, 20, 30, 40, duration=0)

    assert result is True
    drag_moves = [payload for _, payload in events if payload["type"] == "mouseMoved" and payload.get("buttons") == 1]
    assert drag_moves == [{
        "type": "mouseMoved",
        "button": "left",
        "buttons": 1,
        "x": 30,
        "y": 40,
        "modifiers": 0,
        "clickCount": 0,
        "pointerType": "mouse",
    }]
    assert events[-1][1]["type"] == "mouseReleased"
    assert events[-1][1]["buttons"] == 0


def test_drag_mouse_uses_window_dimensions_and_keeps_endpoints_inside():
    events = []
    automation = create_automation(events)
    # 截图可能被强制缩放为 16:9，窗口区域仍保存实际宽高比例。
    automation.screenshot_pos = (-1920, 50, 960, 600)
    automation.drag_mouse((0, 0), (1, 1), 0)
    assert events == [("drag", -1920, 50, -1, 1249, 0)]


@pytest.mark.parametrize("duration", [float("nan"), float("inf"), -1, 61])
def test_drag_mouse_rejects_invalid_duration_before_input(duration):
    events = []
    automation = create_automation(events)
    with pytest.raises(ValueError):
        automation.drag_mouse((0, 0), (1, 1), duration)
    assert events == []


@pytest.mark.parametrize("failure", ["mousePressed", "dragMove", "mouseReleased"])
def test_cdp_drag_propagates_failures_and_attempts_release(failure):
    events = []

    def dispatch(command, payload):
        events.append(payload)
        stage = "dragMove" if payload["type"] == "mouseMoved" and payload["buttons"] else payload["type"]
        if stage == failure:
            raise RuntimeError("dispatch failed")

    cdp = CdpInput(SimpleNamespace(execute_cdp_cmd=dispatch), SimpleNamespace(error=lambda *_: None))
    with pytest.raises(RuntimeError, match="dispatch failed"):
        cdp.mouse_drag(10, 20, 30, 40, 0)
    assert events[-1]["type"] == "mouseReleased"
    assert events[-1]["buttons"] == 0


def test_cdp_drag_duration_accounts_for_transport_latency(monkeypatch):
    clock = [0.0]
    events = []

    def advance(seconds):
        clock[0] += seconds

    def dispatch(command, payload):
        events.append(payload)
        advance(0.05)

    monkeypatch.setattr("module.automation.cdp_input.time.monotonic", lambda: clock[0])
    monkeypatch.setattr("module.automation.cdp_input.time.sleep", advance)
    cdp = CdpInput(SimpleNamespace(execute_cdp_cmd=dispatch), SimpleNamespace(error=lambda *_: None))
    cdp.active_modifiers = 8
    assert cdp.mouse_drag(0, 0, 100, 200, 1) is True
    assert 1.1 <= clock[0] <= 1.25
    assert events[-2]["x"] == 100 and events[-2]["y"] == 200
    assert all(event["modifiers"] == 8 for event in events)
