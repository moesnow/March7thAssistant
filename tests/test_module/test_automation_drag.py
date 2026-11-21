from types import SimpleNamespace
import sys

import pytest

from module.automation.automation import Automation
from module.automation.cdp_input import CdpInput
from unittest.mock import Mock


def create_automation(events):
    automation = object.__new__(Automation)
    automation.screenshot = SimpleNamespace(width=960, height=540)
    automation.screenshot_pos = (100, 50, 960, 540)
    automation.screenshot_scale_factor = 0.5
    automation.take_screenshot = lambda: None
    automation.mouse_drag = lambda *args: events.append(("drag", *args)) or True
    return automation


def fake_clock():
    clock = SimpleNamespace(now=0.0)
    clock.monotonic = lambda: clock.now
    clock.sleep = lambda seconds: setattr(clock, "now", clock.now + seconds)
    return clock


def test_drag_mouse_converts_relative_coordinates():
    events = []
    automation = create_automation(events)

    result = automation.drag_mouse((0.1, 0.2), (0.9, 0.8), duration=0.1)

    assert result is True
    assert events == [("drag", 292, 266, 1828, 914, 0.1)]


def test_drag_mouse_forwards_optional_pause_before_release():
    events = []
    automation = create_automation(events)
    assert automation.drag_mouse((0.1, 0.2), (0.9, 0.8), 0.4, 0.25)
    assert events == [("drag", 292, 266, 1828, 914, 0.4, 0.25)]


def test_move_mouse_converts_relative_coordinates_without_pressing():
    events = []
    automation = create_automation(events)
    automation.mouse_move = lambda *args: events.append(("move", *args))
    automation.take_screenshot = Mock()

    assert automation.move_mouse((0.1, 0.2)) is True
    assert automation.move_mouse((1, 1)) is True
    assert events == [("move", 292, 266), ("move", 2019, 1129)]
    automation.take_screenshot.assert_not_called()
    with pytest.raises(ValueError):
        automation.move_mouse((1.2, 0.5))
    assert len(events) == 2


def test_park_mouse_converts_relative_coordinates_and_uses_the_park_input():
    """停放指针与移动一样按窗口换算坐标，交给后端的停放输入（后台模式据此决定是否归还用户光标）。"""
    events = []
    automation = create_automation(events)
    automation.mouse_park = lambda *args: events.append(("park", *args))
    automation.take_screenshot = Mock()

    assert automation.park_mouse((0.1, 0.2)) is True
    assert events == [("park", 292, 266)]
    automation.take_screenshot.assert_not_called()
    with pytest.raises(ValueError):
        automation.park_mouse((1.2, 0.5))
    assert len(events) == 1


def test_input_park_defaults_to_a_plain_move():
    """前台、云游戏和安卓后端的光标本来就留在移动后的位置，停放与移动相同。"""
    from module.automation.input_base import InputBase

    handler = Mock()
    assert InputBase.mouse_park(handler, 3, 4) is handler.mouse_move.return_value
    handler.mouse_move.assert_called_once_with(3, 4)


def test_drag_group_captures_geometry_once_and_propagates_interruption():
    automation = create_automation([])
    automation.take_screenshot = Mock()
    automation.mouse_drag = Mock(return_value=False)
    assert automation.drag_mouse((0.1, 0.2), (0.9, 0.8), 0.4, 0.25, repeats=3) is False
    automation.take_screenshot.assert_called_once()
    automation.mouse_drag.assert_called_once_with(292, 266, 1828, 914, 0.4, 0.25, 3)


@pytest.mark.parametrize("repeats", [0, -1, 11, 1.5, True, None])
def test_invalid_drag_count_is_rejected_before_capture(repeats):
    automation = create_automation([])
    automation.take_screenshot = Mock()
    with pytest.raises(ValueError):
        automation.drag_mouse((0, 0), (1, 1), repeats=repeats)
    automation.take_screenshot.assert_not_called()


@pytest.mark.skipif(sys.platform != "win32", reason="本地输入后端仅在 Windows 使用")
@pytest.mark.parametrize("interrupted", [False, True])
def test_local_drag_group_releases_each_stroke_and_holds_only_last(monkeypatch, interrupted):
    from module.automation import local_input as module

    events = []
    monkeypatch.setattr(module.pyautogui, "moveTo", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.pyautogui, "mouseUp", lambda: events.append("up"))

    def down():
        events.append("down")
        if interrupted and events.count("down") == 2:
            raise RuntimeError("interrupted")

    clock = fake_clock()
    monkeypatch.setattr(module.pyautogui, "mouseDown", down)
    monkeypatch.setattr(module, "time", clock)
    backend = module.LocalInput(SimpleNamespace(debug=lambda *_: None, error=lambda *_: None))
    if interrupted:
        with pytest.raises(RuntimeError):
            backend.mouse_drag(1, 2, 3, 4, 0.4, 0.25, 3)
        assert events == ["down", "up", "down", "up"]
    else:
        assert backend.mouse_drag(1, 2, 3, 4, 0.4, 0.25, 3)
        assert events == ["down", "up", "down", "up", "down", "up"]
        assert clock.now == pytest.approx(3 * 0.4 + 0.25)


@pytest.mark.parametrize("interrupted", [False, True])
def test_cdp_drag_group_releases_each_stroke_and_stops_after_failure(monkeypatch, interrupted):
    from module.automation import cdp_input as module

    events = []

    def dispatch(_, event):
        events.append(event)
        if interrupted and event["type"] == "mousePressed" and sum(e["type"] == "mousePressed" for e in events) == 2:
            raise RuntimeError("interrupted")

    def hold(seconds):
        assert seconds == 0.25
        assert sum(e["type"] == "mousePressed" for e in events) == 3
        assert sum(e["type"] == "mouseReleased" for e in events) == 2

    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: 0, sleep=hold))
    backend = module.CdpInput(SimpleNamespace(execute_cdp_cmd=dispatch), SimpleNamespace(error=lambda *_: None))
    if interrupted:
        with pytest.raises(RuntimeError):
            backend.mouse_drag(1, 2, 3, 4, 0, 0.25, 3)
    else:
        assert backend.mouse_drag(1, 2, 3, 4, 0, 0.25, 3)
    expected = 2 if interrupted else 3
    assert sum(e["type"] == "mousePressed" for e in events) == expected
    assert sum(e["type"] == "mouseReleased" for e in events) == expected


@pytest.mark.parametrize("end_pause", [float("nan"), float("inf"), -1, 1.01])
def test_drag_mouse_rejects_invalid_end_pause_before_input(end_pause):
    automation = create_automation([])
    automation.take_screenshot = Mock()
    with pytest.raises(ValueError):
        automation.drag_mouse((0, 0), (1, 1), 0.4, end_pause)
    automation.take_screenshot.assert_not_called()


@pytest.mark.skipif(sys.platform != "win32", reason="本地输入后端仅在 Windows 使用")
@pytest.mark.parametrize("interrupted", [False, True])
def test_local_drag_holds_endpoint_before_release_and_cleans_on_interruption(monkeypatch, interrupted):
    from module.automation import local_input as module

    events = []
    monkeypatch.setattr(module.pyautogui, "moveTo", lambda *args, **kwargs: events.append("move"))
    monkeypatch.setattr(module.pyautogui, "mouseDown", lambda: events.append("down"))
    monkeypatch.setattr(module.pyautogui, "mouseUp", lambda: events.append("up"))

    clock = fake_clock()
    advance = clock.sleep

    def hold(seconds):
        if clock.now < 0.4:
            advance(seconds)
            return
        if events[-1] != "hold":
            assert events[-1] == "move"
            events.append("hold")
        if interrupted:
            raise RuntimeError("interrupted")
        advance(seconds)

    clock.sleep = hold
    monkeypatch.setattr(module, "time", clock)
    backend = module.LocalInput(SimpleNamespace(debug=lambda *_: None, error=lambda *_: None))
    if interrupted:
        with pytest.raises(RuntimeError):
            backend.mouse_drag(1, 2, 3, 4, 0.4, 0.25)
    else:
        assert backend.mouse_drag(1, 2, 3, 4, 0.4, 0.25)
    assert events[:2] == ["move", "down"]
    assert events[-3:] == ["move", "hold", "up"]
    assert clock.now == pytest.approx(0.4 if interrupted else 0.65)


@pytest.mark.skipif(sys.platform != "win32", reason="本地输入后端仅在 Windows 使用")
@pytest.mark.parametrize("stop_at", ["down", "move", "hold"])
def test_local_drag_stops_at_the_current_position(monkeypatch, stop_at):
    from module.automation import local_input as module
    from utils.pause import PauseController, RunStopRequested

    control = PauseController()
    control._enabled = True
    clock = fake_clock()
    advance = clock.sleep
    events = []

    def move(x, y, **kwargs):
        events.append(("move", x, y, control.stop_requested))
        if stop_at == "move" and kwargs:
            control.request_stop()

    def down():
        events.append(("down",))
        if stop_at == "down":
            control.request_stop()

    def sleep(seconds):
        advance(seconds)
        if stop_at == "hold" and clock.now > 0.4:
            control.request_stop()

    clock.sleep = sleep
    monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(module, "pause_ctl", control)
    monkeypatch.setattr(module.pyautogui, "moveTo", move)
    monkeypatch.setattr(module.pyautogui, "mouseDown", down)
    monkeypatch.setattr(module.pyautogui, "mouseUp", lambda: events.append(("up", control.stop_requested)))
    backend = module.LocalInput(Mock())

    with pytest.raises(RunStopRequested):
        backend.mouse_drag(10, 20, 300, 400, 0.4, 0.25, repeats=1 if stop_at == "hold" else 3)

    assert events[:2] == [("move", 10, 20, False), ("down",)]
    assert events[-1] == ("up", True)
    assert all(not event[-1] for event in events if event[0] == "move")
    assert sum(event[0] == "move" for event in events) == {"down": 1, "move": 2, "hold": 25}[stop_at]


@pytest.mark.parametrize("interrupted", [False, True])
def test_cdp_drag_holds_with_button_down_and_releases_on_interruption(monkeypatch, interrupted):
    from module.automation import cdp_input as module

    events = []

    def hold(seconds):
        assert seconds == 0.25
        assert events[-1]["type"] == "mouseMoved" and events[-1]["buttons"] == 1
        if interrupted:
            raise RuntimeError("interrupted")

    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: 0, sleep=hold))
    backend = module.CdpInput(SimpleNamespace(execute_cdp_cmd=lambda _, event: events.append(event)),
                              SimpleNamespace(error=lambda *_: None))
    if interrupted:
        with pytest.raises(RuntimeError):
            backend.mouse_drag(1, 2, 3, 4, 0, 0.25)
    else:
        assert backend.mouse_drag(1, 2, 3, 4, 0, 0.25)
    assert events[-1]["type"] == "mouseReleased" and events[-1]["buttons"] == 0


@pytest.mark.parametrize('action', ['click', 'down', 'up', 'move'])
def test_interrupted_background_pointer_result_reaches_existing_callers(action):
    automation = object.__new__(Automation)
    automation.calculate_click_position = lambda *_:(100, 200)
    automation.mouse_click = Mock(return_value=False)
    automation.mouse_down = Mock(return_value=False)
    automation.mouse_up = Mock(return_value=False)
    automation.mouse_move = Mock(return_value=False)
    assert automation.click_element_with_pos(((1,2),(3,4)), action=action) is False
    if action == 'up':
        automation.mouse_up.assert_called_once()


def test_interrupted_mouse_down_does_not_sleep_or_claim_a_complete_long_press(monkeypatch):
    import module.automation.automation as module
    automation = object.__new__(Automation)
    automation.calculate_click_position = lambda *_:(100, 200)
    automation.mouse_down = Mock(return_value=False)
    automation.mouse_up = Mock()
    sleep = Mock()
    monkeypatch.setattr(module.time, 'sleep', sleep)
    assert automation.click_element_with_pos(((1,2),(3,4)), press_duration=1) is False
    sleep.assert_not_called()
    automation.mouse_up.assert_not_called()


@pytest.mark.parametrize("failure", (None, "mousePressed", "mouseReleased"))
def test_cdp_timed_click_reports_dispatch_result(failure):
    events = []

    def dispatch(_, payload):
        event = payload["type"]
        events.append(event)
        if event == failure:
            raise RuntimeError("浏览器连接中断")

    backend = CdpInput(SimpleNamespace(execute_cdp_cmd=dispatch), Mock())
    automation = object.__new__(Automation)
    automation.input_handler = backend
    automation.mouse_down = backend.mouse_down

    assert automation.click_element_with_pos(((1, 2), (3, 4)), press_duration=0.001) is (failure is None)
    assert events == ["mousePressed", "mouseReleased"]


def test_timed_click_releases_even_if_interrupted_before_the_pause_checkpoint(monkeypatch):
    import module.automation.automation as module

    automation = object.__new__(Automation)
    automation.calculate_click_position = lambda *_: (100, 200)
    automation.mouse_down = Mock(return_value=True)
    automation.mouse_up = Mock()
    automation.input_handler = SimpleNamespace(mouse_up=Mock(return_value=True))
    monkeypatch.setattr(module.time, "sleep", Mock(side_effect=KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        automation.click_element_with_pos(((1, 2), (3, 4)), press_duration=0.2)
    automation.input_handler.mouse_up.assert_called_once_with()
    automation.mouse_up.assert_not_called()


@pytest.mark.skipif(sys.platform != "win32", reason="本地输入后端仅在 Windows 使用")
@pytest.mark.parametrize("failure", ["press", "move"])
def test_local_drag_releases_button_when_input_fails(monkeypatch, failure):
    from module.automation.local_input import LocalInput

    events = []
    logger = SimpleNamespace(debug=lambda *_: None, error=lambda *_: None)
    local_input = LocalInput(logger)

    def move_to(x, y, **kwargs):
        events.append(("move", x, y))
        if kwargs and failure == "move":
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
