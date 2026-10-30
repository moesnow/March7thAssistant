"""真实 Windows 适配器的前台切换时序，所有系统调用都使用替身。"""
from types import SimpleNamespace
from unittest.mock import Mock
import ctypes
import sys

import pytest

import module.automation.windows_input as module
from module.automation.windows_input import WindowsInputApi, WindowIdentity


@pytest.fixture
def native(monkeypatch):
    api = object.__new__(WindowsInputApi)
    game, previous, other = (WindowIdentity(10, 1, 1), WindowIdentity(20, 2, 2), WindowIdentity(30, 3, 3))
    windows = {w.hwnd:w for w in (game, previous, other)}
    state = SimpleNamespace(foreground=20, now=0, scheduled=[])
    def sleep(seconds):
        state.now += seconds
        for deadline, callback in state.scheduled[:]:
            if deadline <= state.now:
                state.scheduled.remove((deadline, callback))
                callback()
    monkeypatch.setattr(module, 'time', SimpleNamespace(monotonic=lambda:state.now, sleep=sleep))
    api.foreground = lambda:state.foreground
    api.identity = windows.get
    api.gui = SimpleNamespace(SetForegroundWindow=Mock(), BringWindowToTop=Mock(), PumpWaitingMessages=Mock())
    api.api = SimpleNamespace(GetCurrentThreadId=lambda:1)
    api.process = SimpleNamespace(GetWindowThreadProcessId=lambda _:(2, 200))
    api.user32 = SimpleNamespace(AttachThreadInput=Mock(return_value=True))
    watch = SimpleNamespace(lost=False, expect_foreground=Mock(), focus_requested=None)
    return SimpleNamespace(api=api, state=state, game=game, previous=previous, other=other,
                           windows=windows, watch=watch)


def test_direct_activation_waits_for_transient_zero(native):
    n = native
    def activate(_hwnd):
        n.state.foreground = 0
        n.state.scheduled.append((.03, lambda:setattr(n.state, 'foreground', 10)))
    n.api.gui.SetForegroundWindow.side_effect = activate
    assert n.api.focus(n.game, 20, n.watch)
    assert n.state.now >= .03
    n.api.user32.AttachThreadInput.assert_not_called()
    n.watch.expect_foreground.assert_called_once_with(10)


def test_activation_fallback_creates_queue_brings_window_up_and_always_detaches(native):
    n = native
    n.api.gui.SetForegroundWindow.side_effect = OSError('direct activation denied')
    def bring(_hwnd):
        n.state.foreground = 0
        n.state.scheduled.append((n.state.now+.02, lambda:setattr(n.state, 'foreground', 10)))
    n.api.gui.BringWindowToTop.side_effect = bring
    assert n.api.focus(n.game, 20, n.watch)
    n.api.gui.PumpWaitingMessages.assert_called_once()
    n.api.gui.BringWindowToTop.assert_called_once_with(10)
    n.api.gui.SetForegroundWindow.assert_called_once_with(10)
    assert [c.args for c in n.api.user32.AttachThreadInput.call_args_list] == [(1,2,True),(1,2,False)]


def test_original_window_restore_waits_for_actual_activation(native):
    n = native
    n.state.foreground = 10
    def restore(_hwnd):
        n.state.foreground = 0
        n.state.scheduled.append((.02, lambda:setattr(n.state, 'foreground', 20)))
    n.api.gui.SetForegroundWindow.side_effect = restore
    assert n.api.focus(n.previous, 10, n.watch)
    assert n.state.foreground == 20
    n.watch.expect_foreground.assert_called_once_with(20)


def test_user_window_during_pending_activation_stops_without_attaching(native):
    n = native
    def activate(_hwnd):
        n.state.foreground = 0
        n.state.scheduled.append((.01, lambda:setattr(n.state, 'foreground', 30)))
    n.api.gui.SetForegroundWindow.side_effect = activate
    assert not n.api.focus(n.game, 20, n.watch)
    assert n.state.foreground == 30 and n.state.now < .3
    n.api.user32.AttachThreadInput.assert_not_called()
    n.api.gui.BringWindowToTop.assert_not_called()


def test_user_switch_during_bring_does_not_issue_another_focus_request(native):
    n = native
    n.api.gui.SetForegroundWindow.side_effect = OSError('denied')
    n.api.gui.BringWindowToTop.side_effect = lambda _hwnd:setattr(n.state, 'foreground', 30)
    assert not n.api.focus(n.game, 20, n.watch)
    n.api.gui.SetForegroundWindow.assert_called_once_with(10)
    assert n.state.foreground == 30
    assert n.api.user32.AttachThreadInput.call_args_list[-1].args == (1,2,False)


def test_focus_timeout_is_bounded(native):
    n = native
    assert not n.api.focus(n.game, 20, n.watch)
    assert .6 <= n.state.now < .65
    assert n.api.gui.SetForegroundWindow.call_count == 2


def test_reused_target_is_not_activated_again(native):
    n = native
    def activate(_hwnd):
        n.state.scheduled.append((.01, lambda:n.windows.__setitem__(10, WindowIdentity(10, 9, 9))))
    n.api.gui.SetForegroundWindow.side_effect = activate
    assert not n.api.focus(n.game, 20, n.watch)
    n.api.user32.AttachThreadInput.assert_not_called()


def test_lost_focus_watch_stops_even_if_user_returns_to_target(native):
    n = native
    def activate(_hwnd):
        n.state.foreground, n.watch.lost = 10, True
    n.api.gui.SetForegroundWindow.side_effect = activate
    assert not n.api.focus(n.game, 20, n.watch)
    n.api.user32.AttachThreadInput.assert_not_called()


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows last-error API')
def test_mouse_messages_wait_for_target_processing_with_finite_timeout(native):
    n = native
    n.api.user32.SendMessageTimeoutW = Mock(return_value=1)
    n.api.send_mouse(n.game, 0x200, 1, 0x01234567)
    args = n.api.user32.SendMessageTimeoutW.call_args.args
    assert args[:6] == (10, 0x200, 1, 0x01234567, 0x23, 100)
    assert ctypes.sizeof(args[6]._obj) == ctypes.sizeof(ctypes.c_void_p)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows last-error API')
def test_mouse_message_failure_is_reported_instead_of_silently_advancing(native):
    native.api.user32.SendMessageTimeoutW = Mock(return_value=0)
    with pytest.raises(TimeoutError, match='未及时处理'):
        native.api.send_mouse(native.game, 0x201, 1, 0)


@pytest.mark.parametrize('origin',[(0,0),(-1920,0),(100,200)])
def test_game_center_point_clip_is_recognized_without_global_visibility_flag(native, origin):
    n = native
    n.api.size = lambda _window:(1920,1080)
    n.api.client_to_screen = lambda _window,point:(origin[0]+point[0],origin[1]+point[1])
    n.api.cursor = lambda:(origin[0]+959,origin[1]+539)
    def clip(pointer):
        rect = pointer._obj
        rect.left = rect.right = origin[0]+960
        rect.top = rect.bottom = origin[1]+540
        return True
    n.api.user32.GetClipCursor = Mock(side_effect=clip)
    assert n.api.cursor_locked(n.game)


def test_normal_window_clip_does_not_turn_ui_click_into_captured_attack(native):
    n = native
    n.api.size = lambda _window:(1920,1080)
    n.api.client_to_screen = lambda _window,point:point
    n.api.cursor = lambda:(959,539)
    def clip(pointer):
        rect = pointer._obj
        rect.left,rect.top,rect.right,rect.bottom = 0,0,1920,1080
        return True
    n.api.user32.GetClipCursor = Mock(side_effect=clip)
    assert not n.api.cursor_locked(n.game)


def test_user_brings_game_foreground_before_native_request_does_not_claim_ownership(native):
    n = native
    n.api.gui.PumpWaitingMessages.side_effect = lambda:setattr(n.state,'foreground',10)
    assert not n.api.focus(n.game,20,n.watch)
    assert n.watch.focus_requested is None
    n.api.gui.SetForegroundWindow.assert_not_called()
    n.api.user32.AttachThreadInput.assert_not_called()


def test_closed_previous_window_during_activation_does_not_raise(native):
    n = native
    n.api.gui.SetForegroundWindow.side_effect = OSError('denied')
    n.api.process.GetWindowThreadProcessId = Mock(side_effect=OSError('window closed'))
    assert not n.api.focus(n.game,20,n.watch)
    n.api.user32.AttachThreadInput.assert_not_called()
