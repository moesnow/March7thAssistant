from types import SimpleNamespace

import pytest

from module.automation.automation import Automation
from module.automation.cdp_input import CdpInput
from module.automation.local_input import LocalInput


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


def test_local_drag_releases_button_when_movement_fails(monkeypatch):
    events = []
    logger = SimpleNamespace(debug=lambda *_: None, error=lambda *_: None)
    local_input = LocalInput(logger)

    def move_to(x, y, duration=None):
        events.append(("move", x, y, duration))
        if duration is not None:
            raise RuntimeError("movement failed")

    monkeypatch.setattr("module.automation.local_input.pyautogui.moveTo", move_to)
    monkeypatch.setattr("module.automation.local_input.pyautogui.mouseDown", lambda: events.append(("down",)))
    monkeypatch.setattr("module.automation.local_input.pyautogui.mouseUp", lambda: events.append(("up",)))

    with pytest.raises(RuntimeError, match="movement failed"):
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
        "pointerType": "mouse",
    }]
    assert events[-1][1]["type"] == "mouseReleased"
