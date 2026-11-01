"""横幅/焦点观察的原生边界均为替身，不创建 Windows 窗口或挂钩。"""
import ctypes
import sys
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from module.automation.scroll_banner import ScrollBanner
from module.automation.windows_input import ForegroundWatch, WindowsInputApi, WindowIdentity

pytestmark=pytest.mark.skipif(sys.platform!='win32',reason='Windows 原生边界')


def test_banner_reuses_nonactivating_clickthrough_window(monkeypatch):
    import win32con as c
    events=[]
    gui=SimpleNamespace(
        CreateWindowEx=Mock(return_value=77), SetLayeredWindowAttributes=Mock(),
        SendMessage=Mock(), SetWindowText=Mock(), GetStockObject=Mock(return_value=1),
        SetWindowPos=Mock(side_effect=lambda *args:events.append(('show',args))),
        UpdateWindow=Mock(), ShowWindow=Mock(side_effect=lambda *args:events.append(('hide',args))),
        PumpWaitingMessages=Mock(), DestroyWindow=Mock())
    api=SimpleNamespace(GetModuleHandle=lambda _:1, MonitorFromWindow=lambda *_:1,
                        GetMonitorInfo=lambda _:{'Work':(-1920,0,0,1080)})
    monkeypatch.setitem(sys.modules,'win32gui',gui)
    monkeypatch.setitem(sys.modules,'win32api',api)
    banner=ScrollBanner()
    try:
        banner.show(WindowIdentity(10,1,1))
        banner.hide()
        banner.show(WindowIdentity(10,1,1))
        banner.show(WindowIdentity(10,1,1), message='waiting')
        gui.SetWindowText.assert_called_with(77,'waiting')
        banner.show(WindowIdentity(10,1,1))
        from module.localization import tr
        gui.SetWindowText.assert_called_with(77,tr('滚轮操作需临时切换游戏到前台'))
        assert gui.CreateWindowEx.call_count==1
        assert not gui.ShowWindow.called
        style=gui.CreateWindowEx.call_args.args[0]
        assert style & c.WS_EX_NOACTIVATE and style & c.WS_EX_TRANSPARENT
        assert all(args[1][-1] & c.SWP_NOACTIVATE for args in events if args[0]=='show')
        assert all(args[1][2]<0 for args in events if args[0]=='show')
        banner.hide(immediate=True)
        deadline=time.monotonic()+1
        while not gui.ShowWindow.called and time.monotonic()<deadline:
            time.sleep(.01)
        gui.ShowWindow.assert_called_with(77,c.SW_HIDE)
    finally:
        banner.close()
    gui.DestroyWindow.assert_called_once_with(77)


@pytest.mark.skipif(sys.platform!='win32',reason='ctypes 回调类型仅在 Windows 存在')
def test_foreground_watch_remembers_user_switch_away_and_back(monkeypatch):
    pending=[]
    callbacks=[]
    def hook(*args):
        callbacks.append(args[3])
        return 77
    native=SimpleNamespace(SetWinEventHook=Mock(side_effect=hook),UnhookWinEvent=Mock())
    monkeypatch.setattr(ctypes,'WinDLL',lambda *_args,**_kwargs:native)
    def pump():
        while pending:
            callbacks[0](77,3,pending.pop(0),0,0,0,0)
    api=SimpleNamespace(gui=SimpleNamespace(PumpWaitingMessages=pump),foreground=lambda:10)
    watch=ForegroundWatch(api,10)
    try:
        pending.extend([30,10])
        watch.arm()
        watch.sync()
        assert watch.lost
    finally:
        watch.close()
    native.UnhookWinEvent.assert_called_once_with(77)


def test_foreground_watch_allows_own_restore_and_zero_but_remembers_third_window(monkeypatch):
    pending, callbacks = [], []
    native = SimpleNamespace(SetWinEventHook=Mock(side_effect=lambda *args:callbacks.append(args[3]) or 77),
                             UnhookWinEvent=Mock())
    monkeypatch.setattr(ctypes,'WinDLL',lambda *_args,**_kwargs:native)
    def pump():
        while pending:
            callbacks[0](77,3,pending.pop(0),0,0,0,0)
    api = SimpleNamespace(gui=SimpleNamespace(PumpWaitingMessages=pump), foreground=lambda:20)
    watch = ForegroundWatch(api,10)
    try:
        watch.expect_foreground(20)
        watch.arm()
        pending.extend([0,20])
        watch.sync()
        assert not watch.lost
        pending.extend([30,20])
        watch.sync()
        assert watch.lost
    finally:
        watch.close()


def test_native_focus_refuses_changed_owner_without_calling_windows():
    api=object.__new__(WindowsInputApi)
    window=WindowIdentity(10,1,1)
    api.foreground=lambda:30
    api.identity=lambda _:window
    api.gui=SimpleNamespace(SetForegroundWindow=Mock())
    assert api.focus(window,20) is False
    api.gui.SetForegroundWindow.assert_not_called()


def test_native_focus_detaches_threads_when_switching_raises():
    api=object.__new__(WindowsInputApi)
    window=WindowIdentity(10,1,1)
    api.foreground=lambda:20
    api.identity=lambda _:window
    api.gui=SimpleNamespace(SetForegroundWindow=Mock(side_effect=OSError('denied')),
                            PumpWaitingMessages=Mock(), BringWindowToTop=Mock())
    api.api=SimpleNamespace(GetCurrentThreadId=lambda:1)
    api.process=SimpleNamespace(GetWindowThreadProcessId=lambda _:(2,200))
    api.user32=SimpleNamespace(AttachThreadInput=Mock(return_value=True))
    assert not api.focus(window,20)
    assert api.user32.AttachThreadInput.call_args_list[-1].args==(1,2,False)


def test_native_focus_never_attaches_after_user_focus_change():
    api=object.__new__(WindowsInputApi)
    window=WindowIdentity(10,1,1)
    foreground=[20]
    api.foreground=lambda:foreground[0]
    api.identity=lambda _:window
    def switch(_hwnd):
        foreground[0]=30
        raise OSError('user switched')
    api.gui=SimpleNamespace(SetForegroundWindow=Mock(side_effect=switch),PumpWaitingMessages=Mock())
    api.user32=SimpleNamespace(AttachThreadInput=Mock())
    assert not api.focus(window,20)
    api.user32.AttachThreadInput.assert_not_called()
