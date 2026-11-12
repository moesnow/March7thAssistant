from types import SimpleNamespace
from unittest.mock import Mock

import pytest

win32gui = pytest.importorskip("win32gui")

import win32con

from tasks.game import starrailcontroller as module


@pytest.fixture
def controller():
    controller = object.__new__(module.StarRailController)
    controller.logger = Mock()
    return controller


@pytest.mark.parametrize("optimization_enabled", [True, False])
def test_running_game_uses_resolution_option(monkeypatch, optimization_enabled):
    import tasks.game as game

    controller = Mock()
    controller.switch_to_game.return_value = True
    monkeypatch.setattr(game, "StarRailController", Mock(return_value=controller))
    monkeypatch.setattr(game, "cfg", SimpleNamespace(
        cloud_game_enable=False,
        auto_set_resolution_enable=True,
        game_optimization_enable=optimization_enabled,
        auto_set_game_path_enable=False,
    ))
    monkeypatch.setattr(game, "auto", SimpleNamespace(input_handler=SimpleNamespace(is_background=False)))
    monkeypatch.setattr(game, "wait_until", Mock(return_value=True))
    monkeypatch.setattr(game.time, "sleep", Mock())

    game.start_game()

    controller.check_resolution.assert_called_once_with(1920, 1080, auto_resize=optimization_enabled)
    controller.start_game_process.assert_not_called()
    controller.change_resolution.assert_not_called()
    controller.change_auto_hdr.assert_not_called()


@pytest.mark.parametrize("work_area, expected_position", [
    ((-2560, 0, 0, 1368), (-1936, 249)),
    ((-1920, 0, 0, 1040), None),
])
def test_resize_respects_current_monitor(monkeypatch, controller, work_area, expected_position):
    controller.get_window_handle = Mock(return_value=123)
    monitor_from_window = Mock(return_value=456)
    monkeypatch.setattr(module, "win32api", SimpleNamespace(
        MonitorFromWindow=monitor_from_window,
        GetMonitorInfo=Mock(return_value={"Work": work_area}),
    ))
    set_window_pos = Mock()
    monkeypatch.setattr(module, "win32gui", SimpleNamespace(
        GetWindowLong=Mock(return_value=win32con.WS_OVERLAPPEDWINDOW),
        GetWindowRect=Mock(return_value=(-1460, 350, -11, 1181)),
        GetClientRect=Mock(return_value=(0, 0, 1433, 792)),
        SetWindowPos=set_window_pos,
    ))

    assert controller.resize_game_window(1920, 1080) is (expected_position is not None)

    monitor_from_window.assert_called_once_with(123, win32con.MONITOR_DEFAULTTONEAREST)
    if expected_position is None:
        set_window_pos.assert_not_called()
    else:
        flags = win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER | win32con.SWP_ASYNCWINDOWPOS
        set_window_pos.assert_called_once_with(123, 0, *expected_position, 1936, 1119, flags)


@pytest.mark.parametrize("style", [
    win32con.WS_POPUP,
    win32con.WS_OVERLAPPEDWINDOW | win32con.WS_MINIMIZE,
    win32con.WS_OVERLAPPEDWINDOW | win32con.WS_MAXIMIZE,
])
def test_resize_leaves_non_normal_windows_alone(monkeypatch, controller, style):
    controller.get_window_handle = Mock(return_value=123)
    gui = Mock()
    gui.GetWindowLong.return_value = style
    monkeypatch.setattr(module, "win32gui", gui)

    assert controller.resize_game_window(1920, 1080) is False
    gui.SetWindowPos.assert_not_called()


@pytest.mark.parametrize("accepts_resize", [True, False])
def test_resolution_rechecks_actual_size_after_request(monkeypatch, controller, accepts_resize):
    controller.get_resolution = Mock(side_effect=[(1433, 792), (1920, 1080)] if accepts_resize else None,
                                     return_value=(1433, 792))
    controller.resize_game_window = Mock(return_value=True)
    monkeypatch.setattr(module.time, "sleep", Mock())

    if accepts_resize:
        controller.check_resolution(1920, 1080, auto_resize=True)
        assert controller.get_resolution.call_count == 2
    else:
        with pytest.raises(ValueError, match="游戏分辨率不正确"):
            controller.check_resolution(1920, 1080, auto_resize=True)

    controller.resize_game_window.assert_called_once_with(1920, 1080)


def test_resize_sets_native_windows_client_size(controller):
    hwnd = win32gui.CreateWindow("STATIC", "March7th resolution test", win32con.WS_OVERLAPPEDWINDOW,
                                0, 0, 200, 160, 0, 0, 0, None)
    controller.get_window_handle = Mock(return_value=hwnd)
    try:
        assert controller.resize_game_window(320, 180)
        assert win32gui.GetClientRect(hwnd) == (0, 0, 320, 180)
    finally:
        win32gui.DestroyWindow(hwnd)
