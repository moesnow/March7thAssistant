"""相对镜头移动的纯替身测试，不向真实桌面发送输入。"""
import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def camera_input(monkeypatch):
    pointer = SimpleNamespace(FAILSAFE=True, moveTo=Mock(), mouseDown=Mock(), mouseUp=Mock())
    native = SimpleNamespace(mouse_event=Mock())
    pause = SimpleNamespace(checkpoint=Mock())
    base = ModuleType("module.automation.input_base")
    base.InputBase = object
    for name, value in {
        "pyautogui": pointer,
        "win32api": native,
        "win32con": SimpleNamespace(MOUSEEVENTF_MOVE=1),
        "win32gui": SimpleNamespace(GetCursorInfo=lambda: (0, None, (0, 0))),
        "module.automation.input_base": base,
        "utils.pause": SimpleNamespace(pause_ctl=pause),
    }.items():
        monkeypatch.setitem(__import__("sys").modules, name, value)
    path = Path(__file__).parents[2] / "module/automation/local_input.py"
    spec = importlib.util.spec_from_file_location("camera_input_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.time, "sleep", Mock())
    return module, module.LocalInput(Mock()), pointer, native, pause


def test_hidden_cursor_moves_camera_without_firing(camera_input):
    module, handler, pointer, native, pause = camera_input
    assert handler.mouse_drag(100, 100, 93, 111, duration=.1, repeats=2)
    movements = [call.args for call in native.mouse_event.call_args_list]
    assert sum(move[1] for move in movements) == -14
    assert sum(move[2] for move in movements) == 22
    assert pause.checkpoint.call_count == len(movements)
    pointer.mouseDown.assert_not_called()
    pointer.moveTo.assert_not_called()


def test_visible_cursor_keeps_menu_drag_and_release(camera_input):
    module, handler, pointer, native, pause = camera_input
    module.win32gui.GetCursorInfo = lambda: (1, None, (0, 0))
    pointer.moveTo.side_effect = [None, RuntimeError("drag failed")]
    with pytest.raises(RuntimeError, match="drag failed"):
        handler.mouse_drag(100, 100, 200, 200)
    pointer.mouseDown.assert_called_once()
    pointer.mouseUp.assert_called_once()
    native.mouse_event.assert_not_called()


def test_camera_movement_stops_before_next_input(camera_input):
    module, handler, pointer, native, pause = camera_input
    pause.checkpoint.side_effect = [None, RuntimeError("stopped")]
    with pytest.raises(RuntimeError, match="stopped"):
        handler.mouse_drag(100, 100, 200, 200, duration=.1)
    assert native.mouse_event.call_count == 1
