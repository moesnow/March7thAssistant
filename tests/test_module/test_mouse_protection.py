"""仅执行替身回调，不安装原生钩子、不访问物理鼠标或游戏。"""
import ctypes
from queue import Queue, Empty
import sys
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from module.automation.windows_input import MouseProtection, WindowsInputApi, _MouseEvent

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Windows 回调类型')


@pytest.fixture
def native():
    queue, callbacks, protections = Queue(), [], []
    def hook(_kind, callback, _module, _thread):
        callbacks.append(callback)
        return 77
    def pump():
        while True:
            try:
                code, message, event, answer = queue.get_nowait()
            except Empty:
                break
            try:
                answer.result = callbacks[0](code, message, ctypes.addressof(event))
            finally:
                answer.done.set()
    api = object.__new__(WindowsInputApi)
    api.user32 = SimpleNamespace(SetWindowsHookExW=Mock(side_effect=hook),
                                 CallNextHookEx=Mock(return_value=99),
                                 UnhookWindowsHookEx=Mock(return_value=True))
    api.gui = SimpleNamespace(PumpWaitingMessages=pump)
    api.api = SimpleNamespace(GetModuleHandle=lambda _:42, GetAsyncKeyState=Mock(return_value=0),
                              SetCursorPos=Mock())
    def start(timeout=2, on_expire=None):
        protection = api.protect_mouse(timeout=timeout, on_expire=on_expire)
        protections.append(protection)
        return protection
    def emit(message, *, code=0, flags=0, point=(10, 20), data=0):
        event = _MouseEvent()
        event.point.x, event.point.y = point
        event.flags, event.data = flags, data
        answer = SimpleNamespace(done=threading.Event())
        queue.put((code, message, event, answer))
        assert answer.done.wait(1), '替身消息循环未处理回调'
        return answer.result
    yield SimpleNamespace(api=api, start=start, emit=emit)
    for protection in protections:
        protection.close()


def test_mouse_hook_blocks_physical_move_and_wheel_but_passes_injected_input(native):
    n = native
    guard = n.start()
    assert n.emit(0x200) == 1
    assert n.emit(0x20a) == 1
    assert n.emit(0x20e) == 1
    assert n.emit(0x200, flags=1) == 99
    assert n.emit(0x200, code=-1) == 99
    assert n.api.user32.SetWindowsHookExW.call_args.args[0] == 14  # 只有鼠标钩子。
    guard.close()
    assert not guard.active
    n.api.user32.UnhookWindowsHookEx.assert_called_once_with(77)


def test_own_cursor_move_is_allowed_while_physical_moves_remain_blocked(native):
    n = native
    guard = n.start()
    n.api.move((40, 50))
    n.api.api.SetCursorPos.assert_called_once_with((40, 50))
    assert n.emit(0x200, point=(40, 50)) == 99
    assert n.emit(0x200, point=(41, 50)) == 1
    guard.close()
    assert n.api._mouse_protection is None


@pytest.mark.parametrize('down,up,data', [(0x201,0x202,0), (0x204,0x205,0),
                                        (0x207,0x208,0), (0x20b,0x20c,2<<16)])
def test_mouse_releases_from_before_hook_are_not_swallowed(native, down, up, data):
    native.start()
    assert native.emit(up, data=data) == 99
    assert native.emit(down, data=data) == 1
    assert native.emit(up, data=data) == 1
    assert native.emit(up, data=data) == 99


def test_expiry_unhooks_before_notifying_backend_and_can_close_in_callback(native):
    n = native
    expired = threading.Event()
    def on_expire(guard):
        assert not guard.active
        n.api.user32.UnhookWindowsHookEx.assert_called_once_with(77)
        guard.close()
        expired.set()
    n.start(timeout=.05, on_expire=on_expire)
    assert expired.wait(1)


def test_explicit_close_does_not_invoke_expiry_callback(native):
    callback = Mock()
    native.start(on_expire=callback).close()
    callback.assert_not_called()


def test_hook_failure_returns_no_active_protection(native):
    n = native
    n.api.user32.SetWindowsHookExW.side_effect = None
    n.api.user32.SetWindowsHookExW.return_value = 0
    with pytest.raises(RuntimeError, match='无法建立'):
        n.start()
    n.api.user32.UnhookWindowsHookEx.assert_not_called()


def test_does_not_start_protection_while_user_holds_mouse_button(native):
    n = native
    n.api.api.GetAsyncKeyState.return_value = 0x8000
    with pytest.raises(RuntimeError, match='按住鼠标'):
        n.start()
    n.api.user32.SetWindowsHookExW.assert_not_called()


def test_message_thread_failure_unhooks_and_notifies_input_cleanup(native):
    n = native
    stopped = threading.Event()
    guard = n.start(on_expire=lambda _guard:stopped.set())
    n.api.gui.PumpWaitingMessages = Mock(side_effect=OSError('message pump failed'))
    assert stopped.wait(1)
    assert not guard.active
    n.api.user32.UnhookWindowsHookEx.assert_called_once_with(77)


def test_unhook_exception_still_finishes_cleanup_without_blocking_mouse(native):
    n = native
    guard = n.start()
    n.api.user32.UnhookWindowsHookEx.side_effect = OSError('unhook failed')
    guard.close()
    assert not guard.active and guard._done.is_set()
