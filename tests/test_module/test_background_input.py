"""纯替身测试：禁止接触真实窗口、鼠标或游戏进程。"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from module.automation import background_input as module
from module.automation.background_input import BackgroundInput, GameWindowLost, InputInterrupted
from module.automation.windows_input import CursorUnavailable, WindowGoneError, WindowIdentity
from utils.pause import RunStopRequested


class Controller:
    def __init__(self):
        self.handlers = []
        self.paused = self.cancelled = False
        self.on_checkpoint = None

    def register_input(self, handler):
        self.handlers.append(handler)

    def check_stop(self):
        if self.cancelled:
            raise RunStopRequested()

    def is_paused(self):
        return self.paused

    def checkpoint(self):
        self.check_stop()
        if self.paused:
            for handler in self.handlers:
                handler.release_all()
            if self.on_checkpoint:
                self.on_checkpoint()
            self.paused = False  # 模拟用户随后恢复，不保留假的阻塞线程。


class Api:
    def __init__(self):
        self.game = WindowIdentity(10, 100, 1)
        self.original = WindowIdentity(20, 200, 2)
        self.other = WindowIdentity(30, 300, 3)
        self.windows = {w.hwnd:w for w in (self.game,self.original,self.other)}
        self.fg, self.point = 20, (7,9)
        self.origin, self.dimensions = (100,200), (1920,1080)
        self.minimized = False
        self.events = []
        self.watchers = []
        self.on_post = self.on_scroll = self.on_move = self.on_focus = self.on_sync = None
        self.focus_denied = set()
        self.buttons_down = False
        self.protections = []
        self.captured = False
        self.problem = None  # 直接指定 inspect 结果：'exited' / 'missing' / 'hidden' ...

    def resolve(self, title, process_name):
        return self.game

    def identity(self, hwnd):
        return self.windows.get(hwnd)

    def usable(self, window):
        return self.identity(window.hwnd)==window and (window!=self.game or not self.minimized)

    def inspect(self, title, process_name):
        if self.problem:
            return (None if self.problem in ('exited', 'missing') else self.game), self.problem
        game = self.resolve(title, process_name)
        if self.identity(game.hwnd) != game:
            return None, 'exited'
        return game, ('minimized' if self.minimized else None)

    def size(self, window):
        return self.dimensions

    def foreground(self):
        return self.fg

    def change_focus(self, hwnd):
        self.fg = hwnd
        for watch in self.watchers:
            if hwnd != self.game.hwnd:
                watch.lost = True

    def focus(self, window, expected, watch=None):
        self.events.append(('focus',window.hwnd,expected))
        if self.fg!=expected or window.hwnd in self.focus_denied or (watch and watch.lost):
            return False
        if watch is not None:
            watch.focus_requested = window.hwnd
        self.change_focus(window.hwnd)
        if self.on_focus:
            self.on_focus(window)
        return True

    def watch_foreground(self, window):
        api = self
        class Watch:
            lost = False
            focus_requested = None
            def arm(self):
                api.events.append(('watch-arm',))
            def sync(self):
                if api.on_sync:
                    api.on_sync(self)
            def close(self):
                api.events.append(('watch-close',))
                api.watchers.remove(self)
        watch=Watch()
        self.watchers.append(watch)
        return watch

    def cursor(self):
        return self.point

    def cursor_locked(self, window):
        return self.captured

    def move(self, point):
        self.point=tuple(point)
        self.events.append(('move',self.point))
        if self.on_move:
            self.on_move(point)

    def screen_to_client(self, window, point):
        return tuple(a-b for a,b in zip(point,self.origin))

    def client_to_screen(self, window, point):
        return tuple(a+b for a,b in zip(point,self.origin))

    def post(self, window, msg, wp=0, lp=0):
        self.events.append(('post',window.hwnd,msg,wp,lp))
        if self.on_post:
            self.on_post(msg,wp,lp)

    def scan_code(self, vk):
        return vk+1

    def send_mouse(self, window, msg, wp=0, lp=0):
        self.post(window, msg, wp, lp)

    def scroll(self, direction, pause):
        self.events.append(('scroll',direction,pause,self.fg,self.point))
        if self.on_scroll:
            self.on_scroll()

    def mouse_buttons_down(self):
        return self.buttons_down

    def protect_mouse(self, timeout, on_expire):
        protection = SimpleNamespace(active=True)
        def close():
            protection.active = False
            self.events.append(('unprotect',))
        def expire():
            protection.active = False
            on_expire(protection)
        protection.close, protection.expire = close, expire
        self.protections.append(protection)
        self.events.append(('protect', timeout))
        return protection


@pytest.fixture
def backend(monkeypatch):
    clock=SimpleNamespace(now=0.0)
    def sleep(duration):
        clock.now += duration
    monkeypatch.setattr(module,'time',SimpleNamespace(monotonic=lambda:clock.now,sleep=sleep))
    api,controller,banner = Api(),Controller(),Mock()
    handler=BackgroundInput(Mock(),'game','StarRail',api=api,banner=banner,controller=controller)
    yield SimpleNamespace(input=handler,api=api,ctl=controller,banner=banner,clock=clock)
    handler.close()


def posts(api, message):
    return [event for event in api.events if event[0]=='post' and event[2]==message]


def test_click_maps_client_coordinates_and_restores_cursor(backend):
    b=backend
    assert b.input.mouse_click(350,450) is True
    assert posts(b.api,0x201)[0][4] == 250|(250<<16)
    assert posts(b.api,0x202)
    assert [event[3] for event in posts(b.api,0x6)] == [1,0]
    assert b.api.cursor()==(7,9) and b.api.foreground()==20
    assert not [event for event in b.api.events if event[0]=='focus']


def test_hold_modifier_across_click_and_release(backend):
    b=backend
    b.input.press_key_down('alt')
    b.input.mouse_click(350,450)
    assert b.input._session is not None
    assert [event[3] for event in posts(b.api,0x6)] == [1]
    b.input.press_key_up('alt')
    assert posts(b.api,0x104) and posts(b.api,0x105)
    assert [event[3] for event in posts(b.api,0x6)] == [1,0]
    assert b.input._session is None


def test_drag_preserves_button_mask_and_restores(backend):
    b=backend
    assert b.input.mouse_drag(300,400,500,600,.1)
    assert any(event[3]==1 for event in posts(b.api,0x200))
    assert len(posts(b.api,0x201))==len(posts(b.api,0x202))==1
    assert b.api.cursor()==(7,9)


def test_chord_releases_in_reverse_order(backend):
    b=backend
    b.input.press_key('ctrl+a',0)
    assert [event[3] for event in posts(b.api,0x100)]==[17,65]
    assert [event[3] for event in posts(b.api,0x101)]==[65,17]
    assert all(event[4] & (1<<31) for event in posts(b.api,0x101))


def test_unicode_text_refocuses_last_click_in_same_session(backend):
    b=backend
    b.input.mouse_click(350,450)
    b.api.events.clear()
    b.input.secretly_write('中A🙂',0)
    down = b.api.events.index(posts(b.api,0x201)[0])
    char = b.api.events.index(posts(b.api,0x102)[0])
    inactive = b.api.events.index(posts(b.api,0x6)[-1])
    assert down<char<inactive
    assert [event[3] for event in posts(b.api,0x102)]==[ord('中'),65,0xD83D,0xDE42]


def test_minimized_game_sends_no_messages_and_waits_for_restore(backend, monkeypatch):
    """最小化时不发任何消息；等窗口还原后按未完成返回，不重放之前决定的输入，也不让只按键的循环空转。"""
    b = backend
    b.api.minimized = True
    sleep_hook(b, monkeypatch, lambda now: setattr(b.api, 'minimized', now < 3))
    assert b.input.mouse_click(300,400) is False
    assert 3 <= b.clock.now < 4
    assert b.api.events == []
    warnings = [call.args[0] for call in b.input.logger.warning.call_args_list]
    assert len(warnings) == 1 and '最小化' in warnings[0]
    assert b.input.press_key('esc') is True  # 还原后的新输入照常发送


def test_input_on_window_minimized_for_too_long_reports_reason_once(backend):
    b = backend
    b.api.minimized = True
    with pytest.raises(InputInterrupted, match='最小化.*已等待 60 秒'):
        b.input.press_key('esc')
    assert 60 <= b.clock.now < 62
    started = b.clock.now
    with pytest.raises(InputInterrupted, match='最小化'):
        b.input.mouse_click(300, 400)  # 同一段不可用期间不再重复等待
    assert b.clock.now - started < .1
    assert b.api.events == []


def test_destroyed_or_reused_window_never_receives_release(backend):
    b=backend
    b.input.press_key_down('w')
    b.api.events.clear()
    b.api.windows[10]=WindowIdentity(10,999,9)
    b.input.press_key_up('w')
    assert not posts(b.api,0x101)
    assert not b.input._keys


def test_user_mouse_motion_retries_before_click_and_restores_latest_position(backend):
    b=backend
    def moved(_point):
        b.api.on_move=None
        b.api.point=(800,900)
    b.api.on_move=moved
    assert b.input.mouse_click(300,400)
    assert len(posts(b.api,0x201))==1
    assert b.api.cursor()==(800,900)
    assert not b.api.protections


def test_exception_after_mouse_down_releases_it(backend):
    b=backend
    def fail(msg,*_):
        if msg==0x201:
            raise OSError('injected send failure')
    b.api.on_post=fail
    with pytest.raises(OSError):
        b.input.mouse_click(300,400)
    assert posts(b.api,0x202)
    assert b.api.cursor()==(7,9)
    assert b.input._session is None


def test_pause_mid_hold_cleans_before_checkpoint(backend):
    b=backend
    def paused(msg,*_):
        if msg==0x100:
            b.ctl.paused=True
    b.api.on_post=paused
    b.ctl.on_checkpoint=lambda: (not b.input._keys and b.input._session is None) or pytest.fail('input still held')
    assert b.input.press_key('w',1) is False
    assert posts(b.api,0x101)


def test_cancel_mid_drag_releases_mouse(backend):
    b=backend
    def cancel(msg,*_):
        if msg==0x201:
            b.ctl.cancelled=True
    b.api.on_post=cancel
    with pytest.raises(RunStopRequested):
        b.input.mouse_drag(300,400,500,600,.5)
    assert posts(b.api,0x202)
    assert b.api.cursor()==(7,9)


def test_scroll_shows_banner_before_focus_uses_normal_wheel_and_restores(backend):
    b=backend
    b.input.mouse_move(400,500)
    b.api.events.clear()
    b.banner.show.side_effect=lambda _window:b.api.events.append(('banner',))
    assert b.input.mouse_scroll(3,-1,False)
    assert b.api.events[0]==('banner',)
    scrolls=[e for e in b.api.events if e[0]=='scroll']
    assert scrolls==[('scroll',-1,False,10,(400,500))]*3
    assert [e for e in b.api.events if e[0]=='focus']==[('focus',10,20),('focus',20,10)]
    assert b.api.foreground()==20 and b.api.cursor()==(7,9)
    b.banner.hide.assert_called_once_with(immediate=False)


def test_foreground_scroll_needs_no_banner_or_switch(backend):
    b=backend
    b.api.fg=10
    b.input.mouse_scroll(2)
    b.banner.show.assert_not_called()
    assert not [e for e in b.api.events if e[0]=='focus']


@pytest.mark.parametrize('failure',['raise','pause','cancel','focus','roundtrip'])
def test_scroll_failure_cleanup_respects_user_focus(backend,failure):
    b=backend
    def interrupt():
        if failure=='raise': raise OSError('wheel failed')
        if failure=='pause': b.ctl.paused=True
        if failure=='cancel': b.ctl.cancelled=True
        if failure=='focus': b.api.change_focus(30)
        if failure=='roundtrip':
            b.api.change_focus(30)
            b.api.change_focus(10)
        if failure=='cursor': b.api.point=(900,800)
    b.api.on_scroll=interrupt
    if failure in ('pause','focus','roundtrip'):
        assert b.input.mouse_scroll(3) is False
    else:
        expected=RunStopRequested if failure=='cancel' else (OSError if failure=='raise' else InputInterrupted)
        with pytest.raises(expected): b.input.mouse_scroll(3)
    assert len([e for e in b.api.events if e[0]=='scroll'])==1
    if failure in ('focus','roundtrip'):
        assert ('focus',20,10) not in b.api.events
    else:
        assert b.api.foreground()==20
    if failure=='cursor': assert b.api.cursor()==(900,800)
    assert b.banner.hide.called
    assert all(call.kwargs=={'immediate':True} for call in b.banner.hide.call_args_list)
    assert not b.api.watchers


def test_failed_focus_acquisition_does_not_scroll_or_restore(backend):
    b=backend
    b.api.focus_denied.add(10)
    with pytest.raises(InputInterrupted): b.input.mouse_scroll(1)
    assert not [e for e in b.api.events if e[0]=='scroll']
    assert b.api.foreground()==20
    assert ('focus',20,10) not in b.api.events


def test_exception_after_acquiring_foreground_still_restores(backend):
    b=backend
    def fail(window):
        if window.hwnd==10: raise OSError('focus acknowledgement failed')
    b.api.on_focus=fail
    with pytest.raises(OSError): b.input.mouse_scroll(1)
    assert b.api.foreground()==20


def test_closed_original_window_is_not_activated(backend):
    b=backend
    b.api.on_scroll=lambda:b.api.windows.pop(20,None)
    b.input.mouse_scroll(1)
    assert ('focus',20,10) not in b.api.events


def test_banner_failure_does_not_take_foreground(backend):
    b=backend
    b.banner.show.side_effect=RuntimeError('banner unavailable')
    with pytest.raises(RuntimeError): b.input.mouse_scroll(1)
    assert not [e for e in b.api.events if e[0] in ('focus','scroll')]
    b.banner.hide.assert_called_once_with(immediate=True)


def test_scroll_after_user_switch_during_cursor_cleanup_does_not_reclaim(backend):
    b=backend
    def switch(point):
        if point==(7,9): b.api.change_focus(30)
    b.api.on_move=switch
    b.input.mouse_scroll(1)
    assert b.api.foreground()==30
    assert ('focus',20,10) not in b.api.events


def test_scroll_sync_observes_deferred_user_focus_change(backend):
    b=backend
    syncs=[]
    def queued(watch):
        syncs.append(1)
        if len(syncs)==2: watch.lost=True
    b.api.on_sync=queued
    b.input.mouse_scroll(1)
    assert ('focus',20,10) not in b.api.events


def test_adjacent_scroll_calls_defer_banner_hide(backend):
    b=backend
    b.input.mouse_scroll(2)
    b.input.mouse_scroll(2)
    assert b.banner.hide.call_count==2
    assert all(call.kwargs=={'immediate':False} for call in b.banner.hide.call_args_list)


def test_close_releases_held_key_and_rejects_new_input(backend):
    b=backend
    b.input.press_key_down('w')
    b.input.close()
    assert posts(b.api,0x101)
    with pytest.raises(InputInterrupted): b.input.press_key('w')
    b.banner.close.assert_called_once()


def test_capture_while_minimized_releases_held_key_and_reports_after_bounded_wait(backend,monkeypatch):
    from module.automation.automation import Automation, Screenshot
    b=backend
    b.input.press_key_down('w')
    b.api.minimized=True
    automation=object.__new__(Automation)
    automation.input_handler=b.input
    automation.logger=Mock()
    screenshot=Mock(side_effect=AssertionError('must not capture minimized window'))
    monkeypatch.setattr(Screenshot,'take_screenshot',screenshot)
    with pytest.raises(InputInterrupted, match='最小化.*已等待 60 秒'):
        automation.take_screenshot()
    assert posts(b.api,0x101)
    assert not b.input._keys
    screenshot.assert_not_called()
    assert 60 <= b.clock.now < 62


def test_recreated_target_drops_previous_mouse_position(backend):
    b=backend
    b.input.mouse_move(400,500)
    b.api.game=WindowIdentity(10,999,9)
    b.api.windows[10]=b.api.game
    b.input.mouse_scroll(1)
    assert [event for event in b.api.events if event[0]=='scroll'][-1][-1] == (1060,740)


def test_cancel_and_user_focus_change_never_restores_old_window(backend):
    b=backend
    def stop():
        b.api.change_focus(30)
        b.ctl.cancelled=True
    b.api.on_scroll=stop
    with pytest.raises(RunStopRequested):b.input.mouse_scroll(3)
    assert b.api.foreground()==30
    assert ('focus',20,10) not in b.api.events


@pytest.mark.parametrize('split_release', [False, True])
def test_esc_release_gets_processing_time_before_deactivation(backend, split_release):
    b = backend
    times = {}
    def record(message, wp, _lp):
        if message == 0x101:
            times['up'] = b.clock.now
        if message == 0x6 and wp == 0:
            times['inactive'] = b.clock.now
    b.api.on_post = record
    if split_release:
        b.input.press_key_down('esc')
        b.input.press_key_up('esc')
    else:
        b.input.press_key('esc')
    assert times['inactive'] - times['up'] >= .12 - 1e-6


def test_cancelling_during_key_settle_cleans_without_replaying_esc(backend):
    b = backend
    def cancel(message, *_):
        if message == 0x101:
            b.ctl.cancelled = True
    b.api.on_post = cancel
    with pytest.raises(RunStopRequested):
        b.input.press_key('esc')
    assert len(posts(b.api, 0x100)) == len(posts(b.api, 0x101)) == 1
    assert not b.input._keys and b.input._session is None


def test_pure_key_ignores_mouse_motion_and_does_not_restore_user_cursor(backend):
    b = backend
    center = b.api.client_to_screen(b.api.game, (959, 539))
    def move(message, wp, _lp):
        if message == 0x6 and wp == 1:
            b.api.point = center
        if message == 0x100:
            b.api.point = (800, 900)
    b.api.on_post = move
    assert b.input.press_key('esc')
    assert b.api.cursor() == (800, 900)
    assert not b.api.protections


def test_mouse_retry_restores_held_alt_before_click(backend):
    b = backend
    b.input.press_key_down('alt')
    def move(_point):
        b.api.on_move = None
        b.api.point = (800, 900)
    b.api.on_move = move
    assert b.input.mouse_click(300, 400)
    assert len(posts(b.api, 0x104)) == 2
    assert len(posts(b.api, 0x105)) == 1
    assert b.input._keys == [18]
    b.input.press_key_up('alt')
    assert len(posts(b.api, 0x105)) == 2


@pytest.mark.parametrize('gesture', ['click', 'drag', 'text'])
def test_mouse_conflict_after_down_releases_without_replaying(backend, gesture):
    b = backend
    if gesture == 'text':
        b.input.mouse_click(300, 400)
        b.api.events.clear()
    def move(message, *_):
        if message == 0x201:
            b.api.point = (800, 900)
    b.api.on_post = move
    if gesture == 'click':
        result = b.input.mouse_click(300, 400)
    elif gesture == 'drag':
        result = b.input.mouse_drag(300, 400, 500, 600)
    else:
        result = b.input.secretly_write('不可重复输入')
    assert result is False
    assert len(posts(b.api, 0x201)) == len(posts(b.api, 0x202)) == 1
    assert not posts(b.api, 0x102)
    assert b.api.cursor() == (800, 900)
    assert not b.input._mouse_down and b.input._session is None


def test_three_conflicts_wait_without_protection_and_remain_cancellable(backend, monkeypatch):
    b = backend
    calls = []
    def idle(_context, timeout=None):
        calls.append(timeout)
        assert not b.input._mouse_down and not b.input._keys
        if timeout is None:
            b.ctl.cancelled = True
            b.ctl.check_stop()
        return False
    monkeypatch.setattr(b.input, '_wait_mouse_idle', idle)
    with pytest.raises(RunStopRequested):
        b.input.mouse_click(300, 400)
    assert calls == [.5, .5, .5, None]
    assert not b.api.protections and not posts(b.api, 0x201)
    b.banner.show.assert_called_once()
    b.banner.hide.assert_called_with(immediate=True)


def test_three_conflicts_then_idle_automatically_continue(backend, monkeypatch):
    b = backend
    idle = Mock(side_effect=[False, False, False, True])
    monkeypatch.setattr(b.input, '_wait_mouse_idle', idle)
    assert b.input.mouse_click(300, 400)
    assert idle.call_args_list[-1].kwargs == {'timeout': None}  # 任务进程里一直等到空闲
    assert len(posts(b.api, 0x201)) == 1
    assert not b.api.protections


def test_protection_is_opt_in_and_only_after_three_conflicts(backend, monkeypatch):
    b = backend
    b.input.protect_mouse = True
    monkeypatch.setattr(b.input, '_wait_mouse_idle', Mock(return_value=False))
    assert b.input.mouse_click(300, 400)
    assert len(b.api.protections) == 1
    assert not b.api.protections[0].active
    assert ('protect', 2) in b.api.events and ('unprotect',) in b.api.events
    assert len(posts(b.api, 0x201)) == 1 and not b.input._keys


def test_enabled_protection_does_not_lock_uncontended_mouse(backend):
    backend.input.protect_mouse = True
    assert backend.input.mouse_click(300, 400)
    assert not backend.api.protections


def test_failed_protection_falls_back_to_idle_wait(backend, monkeypatch):
    b = backend
    b.input.protect_mouse = True
    monkeypatch.setattr(b.input, '_wait_mouse_idle', Mock(side_effect=[False]*3+[True]))
    monkeypatch.setattr(b.api, 'protect_mouse', Mock(side_effect=OSError('hook unavailable')))
    assert b.input.mouse_click(300, 400)
    assert not b.api.protections


@pytest.mark.parametrize('failure', ['cancel', 'pause', 'send'])
def test_protected_input_always_unlocks_on_interruption(backend, monkeypatch, failure):
    b = backend
    b.input.protect_mouse = True
    monkeypatch.setattr(b.input, '_wait_mouse_idle', Mock(return_value=False))
    def interrupt(message, *_):
        if message == 0x201:
            if failure == 'cancel': b.ctl.cancelled = True
            if failure == 'pause': b.ctl.paused = True
            if failure == 'send': raise OSError('send failure')
    b.api.on_post = interrupt
    if failure == 'pause':
        assert b.input.mouse_click(300, 400) is False
    else:
        with pytest.raises(RunStopRequested if failure == 'cancel' else OSError):
            b.input.mouse_click(300, 400)
    assert not b.api.protections[0].active
    assert posts(b.api, 0x202) and not b.input._mouse_down


def test_expired_protection_releases_split_mouse_hold(backend, monkeypatch):
    b = backend
    b.input.protect_mouse = True
    monkeypatch.setattr(b.input, '_wait_mouse_idle', Mock(return_value=False))
    b.input.mouse_down(300, 400)
    assert b.input._mouse_down and b.api.protections[0].active
    b.api.protections[0].expire()
    assert not b.input._mouse_down and b.input._session is None
    assert posts(b.api, 0x202) and b.input._protection is None
    assert b.input.mouse_up() is False


def test_conflicts_after_click_accumulate_until_existing_ui_retry_gets_protection(backend):
    b = backend
    b.input.protect_mouse = True
    def move(message, *_):
        if message == 0x201 and not any(g.active for g in b.api.protections):
            b.api.point = (800, 900)
    b.api.on_post = move
    for _ in range(3):
        assert b.input.mouse_click(300, 400) is False
    assert not b.api.protections
    assert b.input.mouse_click(300, 400)
    assert len(b.api.protections) == 1
    assert b.input._mouse_failures == 0


def test_protection_covers_mouse_release_processing_and_cursor_restore(backend, monkeypatch):
    b = backend
    b.input.protect_mouse = True
    monkeypatch.setattr(b.input, '_wait_mouse_idle', Mock(return_value=False))
    released = []
    def record(message, *_):
        if message == 0x202: released.append(b.clock.now)
    b.api.on_post = record
    def restored(point):
        if point == (7, 9):
            assert b.api.protections[0].active
            assert b.clock.now - released[0] >= .12 - 1e-6
    b.api.on_move = restored
    assert b.input.mouse_click(300, 400)
    assert not b.api.protections[0].active


def test_idle_wait_handles_mouse_activity_without_moving_it(backend, monkeypatch):
    b = backend
    original_sleep = module.time.sleep
    def sleep(duration):
        original_sleep(duration)
        if b.clock.now < .4:
            b.api.point = (round(b.clock.now*1000), 900)
    monkeypatch.setattr(module.time, 'sleep', sleep)
    assert b.input.mouse_click(300, 400)
    assert b.clock.now >= .65
    assert b.api.cursor()[1] == 900


def test_wait_for_idle_is_pauseable_before_any_mouse_down(backend, monkeypatch):
    b = backend
    original_sleep = module.time.sleep
    def sleep(duration):
        original_sleep(duration)
        b.ctl.paused = True
    monkeypatch.setattr(module.time, 'sleep', sleep)
    assert b.input.mouse_click(300, 400) is False
    assert not posts(b.api, 0x201)


def test_user_focus_change_during_idle_wait_never_clicks(backend, monkeypatch):
    b = backend
    original_sleep = module.time.sleep
    def sleep(duration):
        original_sleep(duration)
        b.api.change_focus(30)
    monkeypatch.setattr(module.time, 'sleep', sleep)
    assert b.input.mouse_click(300, 400) is False
    assert not posts(b.api, 0x201) and b.api.foreground() == 30


def test_scroll_mouse_conflict_only_retries_unsent_ticks(backend):
    b = backend
    def move():
        b.api.on_scroll = None
        b.api.point = (800, 900)
    b.api.on_scroll = move
    assert b.input.mouse_scroll(3)
    assert len([e for e in b.api.events if e[0] == 'scroll']) == 3
    assert b.api.cursor() == (800, 900) and b.api.foreground() == 20


def test_cursor_restore_failure_still_unlocks(backend, monkeypatch):
    """恢复光标只是善后：失败时记录日志，已完成的点击和输入释放不受影响。"""
    b = backend
    b.input.protect_mouse = True
    monkeypatch.setattr(b.input, '_wait_mouse_idle', Mock(return_value=False))
    def fail_restore(point):
        if point == (7, 9): raise OSError('restore failed')
    b.api.on_move = fail_restore
    assert b.input.mouse_click(300, 400) is True
    assert not b.api.protections[0].active
    assert b.input._session is None and not b.input._mouse_down
    assert any('恢复光标' in call.args[0] for call in b.input.logger.warning.call_args_list)


@pytest.mark.parametrize('operation', ['click', 'scroll'])
def test_user_switch_during_protection_setup_never_adopts_new_foreground(backend, monkeypatch, operation):
    b = backend
    b.input.protect_mouse = True
    monkeypatch.setattr(b.input, '_wait_mouse_idle', Mock(return_value=False))
    protect = b.api.protect_mouse
    def switched(**kwargs):
        guard = protect(**kwargs)
        b.api.change_focus(30)
        return guard
    monkeypatch.setattr(b.api, 'protect_mouse', switched)
    if operation == 'click': assert b.input.mouse_click(300, 400) is False
    else: assert b.input.mouse_scroll(3) is False
    assert b.api.foreground() == 30
    assert not b.api.protections[0].active
    assert not [e for e in b.api.events if e[0] in ('scroll', 'focus')]
    assert not posts(b.api, 0x201)


def test_foreground_scroll_reactivates_game_before_ticks_and_waits_before_restoring(backend):
    b = backend
    b.input.mouse_move(300, 400)  # 模拟任务先后台悬停“等级”，该会话会发送 WA_INACTIVE。
    b.api.events.clear()
    times = {}
    def post(message, wp, _lp):
        if message == 0x6 and wp == 1:
            times['active'] = b.clock.now
    def tick():
        assert b.api.foreground() == 10
        assert b.clock.now - times['active'] >= .08 - 1e-6
        times['last_tick'] = b.clock.now
    def focus(window):
        if window == b.api.original:
            assert b.clock.now - times['last_tick'] >= .2 - 1e-6
    b.api.on_post, b.api.on_scroll, b.api.on_focus = post, tick, focus
    assert b.input.mouse_scroll(19, -1, False)
    assert len([e for e in b.api.events if e[0] == 'scroll']) == 19
    assert b.api.foreground() == 20 and b.api.cursor() == (7,9)


@pytest.mark.parametrize('interrupt', ['cancel', 'pause', 'switch'])
def test_wheel_processing_wait_remains_cancellable_and_does_not_replay(backend, monkeypatch, interrupt):
    b = backend
    sent = []
    b.api.on_scroll = lambda:sent.append(b.clock.now)
    original_sleep = module.time.sleep
    def sleep(duration):
        original_sleep(duration)
        if len(sent) == 3:
            if interrupt == 'cancel': b.ctl.cancelled = True
            if interrupt == 'pause': b.ctl.paused = True
            if interrupt == 'switch': b.api.change_focus(30)
    monkeypatch.setattr(module.time, 'sleep', sleep)
    if interrupt in ('pause','switch'):
        assert b.input.mouse_scroll(3) is False
    else:
        with pytest.raises(RunStopRequested if interrupt == 'cancel' else InputInterrupted):
            b.input.mouse_scroll(3)
    assert len(sent) == 3
    if interrupt == 'switch':
        assert b.api.foreground() == 30
        assert ('focus',20,10) not in b.api.events
    else:
        assert b.api.foreground() == 20


def test_split_held_moves_have_duration_interpolation_and_one_button_pair(backend):
    b = backend
    b.input.mouse_down(300, 400)
    started = b.clock.now
    b.api.events.clear()
    b.input.mouse_move(364, 400)
    assert b.clock.now - started >= .1 - 1e-6
    assert b.input._mouse_down
    moves = posts(b.api, 0x200)
    assert len(moves) == 4
    assert all(event[3] == 1 for event in moves)
    assert [event[4] & 0xffff for event in moves] == [216, 232, 248, 264]
    b.input.mouse_up()
    assert len(posts(b.api, 0x202)) == 1 and not b.input._mouse_down


def test_mouse_move_without_hold_does_not_add_drag_duration(backend):
    b = backend
    started = b.clock.now
    b.input.mouse_move(300, 400)
    # 空闲等待 .25 + 激活 .08 + 清理 .05；只有按住时才加扫动时间。
    assert b.clock.now - started < .5


def test_cancel_during_split_move_releases_without_replaying(backend):
    b = backend
    b.input.mouse_down(300, 400)
    def cancel(message, wp, _lp):
        if message == 0x200 and wp == 1:
            b.ctl.cancelled = True
    b.api.on_post = cancel
    with pytest.raises(RunStopRequested):
        b.input.mouse_move(364, 400)
    assert len(posts(b.api, 0x201)) == len(posts(b.api, 0x202)) == 1
    assert not b.input._mouse_down and b.input._session is None


def test_held_movement_uses_ordered_messages_instead_of_queued_mouse_positions(backend, monkeypatch):
    b = backend
    pending = []
    original_post, original_move = b.api.post, b.api.move
    def post(window, message, wp=0, lp=0):
        original_post(window, message, wp, lp)
        if message == 0x200:
            pending.append((lp & 0xffff, (lp >> 16) & 0xffff))
    def move(point):
        original_move(point)
        if pending:
            # 复现新坐标写入后，游戏晚处理前一个 WM_MOUSEMOVE 回写旧位置。
            b.api.point = b.api.client_to_screen(b.api.game, pending.pop(0))
    def send_mouse(window, message, wp=0, lp=0):
        assert not pending
        original_post(window, message, wp, lp)
    monkeypatch.setattr(b.api, 'post', post)
    monkeypatch.setattr(b.api, 'move', move)
    monkeypatch.setattr(b.api, 'send_mouse', send_mouse)
    b.input.mouse_down(300, 400)
    b.input.mouse_move(350, 450)
    b.input.mouse_move(400, 500)
    b.input.mouse_up()
    assert not pending and b.api.cursor() == (7,9)
    assert len(posts(b.api, 0x201)) == len(posts(b.api, 0x202)) == 1


def test_mouse_message_timeout_always_queues_release(backend, monkeypatch):
    b = backend
    original_send = b.api.send_mouse
    def send(window, message, wp=0, lp=0):
        if message == 0x201:
            raise TimeoutError('game did not respond')
        original_send(window, message, wp, lp)
    monkeypatch.setattr(b.api, 'send_mouse', send)
    # 加载画面等导致游戏未及时处理：释放输入并按未完成返回，不再作为错误结束整个任务。
    assert b.input.mouse_down(300, 400) is False
    assert posts(b.api, 0x202)
    assert not b.input._mouse_down and b.input._session is None
    assert any('未及时处理' in call.args[0] for call in b.input.logger.warning.call_args_list)


def test_cursor_mismatch_log_records_positions_without_claiming_user_moved(backend):
    b = backend
    def moved(message, *_):
        if message == 0x201:
            b.api.point = (800,900)
    b.api.on_post = moved
    assert b.input.mouse_click(300, 400) is False
    message = b.input.logger.warning.call_args.args[0]
    assert '预期' in message and '实际 (800, 900)' in message
    assert '用户' not in message and '受到干扰' not in message


def test_long_split_move_caps_messages_and_does_not_add_wait_after_delivery_time(backend, monkeypatch):
    b = backend
    b.input.mouse_down(110, 210)
    b.api.events.clear()
    original_send = b.api.send_mouse
    def send(window, message, wp=0, lp=0):
        original_send(window, message, wp, lp)
        if message == 0x200:
            b.clock.now += .02  # 模拟每次同步消息已经消耗一帧。
    monkeypatch.setattr(b.api, 'send_mouse', send)
    started = b.clock.now
    b.input.mouse_move(1800, 500)
    assert len(posts(b.api, 0x200)) == 6
    assert .12-1e-6 <= b.clock.now-started < .13
    assert b.input._mouse_down


def capture_view(backend):
    b = backend
    center = b.api.client_to_screen(b.api.game, (959,539))
    def activate(message, wp, _lp):
        if message == 0x6:
            b.api.captured = bool(wp)
            if wp: b.api.point = center
    b.api.on_post = activate
    return center


def test_attack_in_captured_view_does_not_reuse_old_ui_position(backend):
    b = backend
    center = capture_view(b)
    b.input._point = (860,802)  # 上一个 UI 点击，屏幕坐标 (960,1002)。
    b.input._last_click = ('old UI focus',)
    assert b.input.press_mouse()
    assert len(posts(b.api, 0x201)) == len(posts(b.api, 0x202)) == 1
    assert posts(b.api, 0x201)[0][4] == 959 | (539 << 16)
    assert not posts(b.api, 0x200)
    assert [event for event in b.api.events if event[0] == 'move'] == [('move',(7,9))]
    assert b.input._last_click is None
    assert b.api.cursor() == (7,9) and b.api.foreground() == 20
    b.banner.show.assert_not_called()


def test_uncaptured_press_still_uses_virtual_ui_position(backend):
    b = backend
    b.input._point = (250,250)
    assert b.input.press_mouse()
    assert posts(b.api, 0x201)[0][4] == 250 | (250 << 16)
    assert posts(b.api, 0x200)


@pytest.mark.parametrize('failure',['cancel','pause','focus'])
def test_captured_attack_interruption_releases_and_keeps_user_window(backend, failure):
    b = backend
    capture_view(b)
    activate = b.api.on_post
    def interrupt(message, wp, lp):
        activate(message, wp, lp)
        if message == 0x201:
            if failure == 'cancel': b.ctl.cancelled = True
            if failure == 'pause': b.ctl.paused = True
            if failure == 'focus': b.api.change_focus(30)
    b.api.on_post = interrupt
    if failure in ('pause','focus'):
        assert b.input.press_mouse() is False
    else:
        with pytest.raises(RunStopRequested if failure == 'cancel' else InputInterrupted):
            b.input.press_mouse()
    assert len(posts(b.api, 0x201)) == len(posts(b.api, 0x202)) == 1
    assert b.input._session is None and not b.input._mouse_down
    if failure == 'focus': assert b.api.foreground() == 30


def test_same_wait_banner_is_not_repeated_within_operation(backend):
    b = backend
    b.input._show_mouse_notice(b.api.game)
    b.input._show_mouse_notice(b.api.game)
    b.banner.show.assert_called_once()
    b.input.logger.warning.assert_called_once()


def test_persistent_unreachable_pointer_is_bounded_without_issuing_click(backend):
    b = backend
    b.api.on_move = lambda _point:setattr(b.api,'point',(800,900))
    assert b.input.mouse_click(300,400) is False
    assert not posts(b.api, 0x201)
    assert len([p for p in posts(b.api,0x6) if p[3] == 1]) == 4
    assert b.clock.now < 3
    b.banner.show.assert_called_once()
    assert b.input._session is None


@pytest.mark.parametrize('destination',[10,30])
def test_window_switch_during_key_hold_is_recoverable_and_does_not_replay(backend, destination):
    b = backend
    def switch(message, vk, _lp):
        if message == 0x100 and vk == ord('A'):
            b.api.change_focus(destination)
    b.api.on_post = switch
    assert b.input.press_key('a', 1) is False
    assert len(posts(b.api, 0x100)) == len(posts(b.api, 0x101)) == 1
    assert b.input._session is None and not b.input._keys
    assert b.api.foreground() == destination
    assert not [e for e in b.api.events if e[0] == 'focus']
    b.input.logger.error.assert_not_called()
    assert b.input.press_key('b', 0)
    assert len(posts(b.api, 0x100)) == len(posts(b.api, 0x101)) == 2


def test_foreground_switch_does_not_repeat_chord_or_partial_text(backend):
    b = backend
    def switch(message, *_args):
        if message in (0x100,0x102): b.api.change_focus(30)
    b.api.on_post = switch
    assert b.input.press_key('ctrl+a') is False
    assert [e[3] for e in posts(b.api,0x100)] == [17]
    assert [e[3] for e in posts(b.api,0x101)] == [17]
    b.api.change_focus(20)
    assert b.input.secretly_write('abc') is False
    assert [e[3] for e in posts(b.api,0x102)] == [ord('a')]
    b.input.logger.error.assert_not_called()


def test_switch_between_split_hold_and_move_releases_and_allows_next_click(backend):
    b = backend
    b.input.mouse_down(300,400)
    b.api.change_focus(30)
    b.api.point = (800,900)
    assert b.input.mouse_move(350,450) is False
    assert len(posts(b.api,0x201)) == len(posts(b.api,0x202)) == 1
    assert b.api.cursor() == (800,900) and b.api.foreground() == 30
    assert not b.input._mouse_down and b.input._session is None
    assert b.input.mouse_click(350,450)


@pytest.mark.parametrize('kind',['key','mouse'])
def test_switch_while_processing_release_is_recoverable(backend, kind):
    b = backend
    if kind == 'key': b.input.press_key_down('w')
    else: b.input.mouse_down(300,400)
    def switch(message, *_args):
        if message in (0x101,0x202): b.api.change_focus(30)
    b.api.on_post = switch
    # 释放已经发出：切窗只影响收尾等待，结果与正常释放一致，不让调用方误判为未完成。
    if kind == 'key': assert b.input.press_key_up('w') is None
    else: assert b.input.mouse_up() is None
    assert not b.input._keys and not b.input._mouse_down and b.input._session is None
    assert b.api.foreground() == 30
    b.input.logger.error.assert_not_called()


def test_switch_before_wheel_acquisition_is_recoverable_and_sends_no_wheel(backend):
    b = backend
    def switch(_target): b.api.change_focus(10)
    b.banner.show.side_effect = switch
    assert b.input.mouse_scroll(4) is False
    assert not [e for e in b.api.events if e[0] == 'scroll']
    assert b.api.foreground() == 10
    b.input.logger.error.assert_not_called()
    b.banner.show.side_effect = None
    assert b.input.mouse_scroll(2)
    assert len([e for e in b.api.events if e[0] == 'scroll']) == 2
    assert b.api.foreground() == 10


def test_stopping_during_focus_handoff_keeps_cancellation_priority(backend):
    b = backend
    def stop(message, *_args):
        if message == 0x100:
            b.api.change_focus(30)
            b.ctl.cancelled = True
    b.api.on_post = stop
    with pytest.raises(RunStopRequested): b.input.press_key('a')
    assert not b.input._keys and b.input._session is None


def test_focus_change_releases_active_mouse_protection(backend, monkeypatch):
    b = backend
    b.input.protect_mouse = True
    monkeypatch.setattr(b.input,'_wait_mouse_idle',Mock(return_value=False))
    def switch(message, *_args):
        if message == 0x201: b.api.change_focus(30)
    b.api.on_post = switch
    assert b.input.mouse_click(300,400) is False
    assert not b.api.protections[0].active
    assert posts(b.api,0x202) and not b.input._mouse_down
    assert b.api.foreground() == 30



# ---------- 窗口暂时不可用、游戏退出与可恢复中断（04:01 偶发“后台游戏窗口不可操作”问题的回归）----------

def sleep_hook(backend, monkeypatch, hook):
    """在替身时钟每次 sleep 后执行 hook(clock.now)，模拟等待期间发生的窗口变化。"""
    original = module.time.sleep
    def sleep(duration):
        original(duration)
        hook(backend.clock.now)
    monkeypatch.setattr(module.time, 'sleep', sleep)


def test_window_restored_during_wait_continues_without_error(backend, monkeypatch):
    b = backend
    b.api.minimized = True
    sleep_hook(b, monkeypatch, lambda now: setattr(b.api, 'minimized', now < 3))
    b.input.wait_for_window(60)
    assert 3 <= b.clock.now < 4
    warnings = [call.args[0] for call in b.input.logger.warning.call_args_list]
    assert len(warnings) == 1 and '最小化' in warnings[0] and '无需切到前台' in warnings[0]
    b.input.logger.info.assert_called_with('游戏窗口已恢复，继续执行')


def test_exited_game_is_reported_immediately_not_as_restore_window(backend):
    """游戏进程已退出时立即说明原因，不等待、不提示“请恢复窗口”，交给原有错误处理。"""
    b = backend
    b.input.press_key_down('w')
    b.api.problem = 'exited'
    with pytest.raises(GameWindowLost, match='游戏进程已退出'):
        b.input.wait_for_window(60)
    assert b.clock.now < .5
    assert not b.input._keys and b.input._session is None
    assert not isinstance(GameWindowLost('x'), InputInterrupted)  # 不阻止启动流程重启游戏


def test_window_missing_for_whole_timeout_is_reported_as_window_lost(backend):
    b = backend
    b.api.problem = 'missing'
    with pytest.raises(GameWindowLost, match='未找到游戏窗口（已等待 60 秒）'):
        b.input.wait_for_window(60)


def test_hidden_window_timeout_names_state(backend):
    b = backend
    b.api.problem = 'hidden'
    with pytest.raises(InputInterrupted, match='不可见'):
        b.input.wait_for_window(5)


def test_zero_timeout_reports_without_waiting_or_logging(backend):
    """图形界面（自动对话）只尝试一次：不等待，也不刷屏日志。"""
    b = backend
    b.api.minimized = True
    with pytest.raises(InputInterrupted, match='最小化'):
        b.input.wait_for_window(0)
    assert b.clock.now == 0
    b.input.logger.warning.assert_not_called()


def test_pause_during_window_wait_does_not_consume_timeout(backend, monkeypatch):
    b = backend
    b.api.minimized = True
    paused = {'done': False}
    def checkpoint():
        if b.clock.now >= 10 and not paused['done']:
            paused['done'] = True
            b.clock.now += 120  # 用户暂停两分钟后继续
    b.ctl.checkpoint = checkpoint
    sleep_hook(b, monkeypatch, lambda now: setattr(b.api, 'minimized', now < 140))
    b.input.wait_for_window(60)
    assert paused['done'] and b.clock.now >= 140


def test_stop_during_window_wait_ends_task(backend, monkeypatch):
    b = backend
    b.api.minimized = True
    sleep_hook(b, monkeypatch, lambda now: setattr(b.ctl, 'cancelled', now >= 2))
    with pytest.raises(RunStopRequested):
        b.input.wait_for_window(60)
    assert b.clock.now < 3


def test_capture_waits_for_restored_window_then_captures(backend, monkeypatch):
    from module.automation.automation import Automation, Screenshot
    b = backend
    b.api.minimized = True
    sleep_hook(b, monkeypatch, lambda now: setattr(b.api, 'minimized', now < 2))
    automation = object.__new__(Automation)
    automation.input_handler, automation.logger, automation.window_title = b.input, Mock(), 'game'
    automation._is_debug_enabled = lambda: False
    frame = (object(), (0, 0, 1920, 1080), 1)
    capture = Mock(return_value=frame)
    monkeypatch.setattr(Screenshot, 'take_screenshot', capture)
    assert automation.take_screenshot() == frame
    capture.assert_called_once()
    assert capture.call_args.kwargs['require_background'] is True


def test_capture_after_game_exit_reports_exit(backend, monkeypatch):
    from module.automation.automation import Automation, Screenshot
    b = backend
    b.api.problem = 'exited'
    automation = object.__new__(Automation)
    automation.input_handler, automation.logger = b.input, Mock()
    monkeypatch.setattr(Screenshot, 'take_screenshot', Mock(side_effect=AssertionError('no capture')))
    with pytest.raises(GameWindowLost, match='游戏进程已退出'):
        automation.take_screenshot()


@pytest.mark.parametrize('change', ['minimize', 'move'])
def test_window_change_during_key_hold_releases_and_returns_not_completed(backend, monkeypatch, change):
    """输入途中窗口被最小化或移动：释放按键、按未完成返回，不再作为错误结束任务。"""
    b = backend
    def act(message, vk, _lp):
        if message == 0x100 and vk == ord('W'):
            if change == 'minimize':
                b.api.minimized = True
                sleep_hook(b, monkeypatch, lambda now: setattr(b.api, 'minimized', False))
            else: b.api.origin = (300, 300)
    b.api.on_post = act
    assert b.input.press_key('w', 1) is False
    assert len(posts(b.api, 0x100)) == len(posts(b.api, 0x101)) == 1
    assert not b.input._keys and b.input._session is None
    b.input.logger.error.assert_not_called()


@pytest.mark.parametrize('after', ['exited', 'recreated'])
def test_window_closed_while_sending_clears_state_and_reports_outcome(backend, after):
    """发送途中窗口关闭：清理状态；游戏已退出时写明原因，窗口重建后按未完成返回。"""
    b = backend
    def gone(message, *_):
        if message == 0x201:
            b.api.windows.pop(10)
            if after == 'recreated':
                b.api.game = WindowIdentity(10, 999, 9)
                b.api.windows[10] = b.api.game
            raise WindowGoneError('游戏窗口已关闭或重建')
    b.api.on_post = gone
    if after == 'exited':
        with pytest.raises(GameWindowLost, match='游戏进程已退出'):
            b.input.mouse_click(300, 400)
    else:
        assert b.input.mouse_click(300, 400) is False
    assert not b.input._mouse_down and not b.input._keys and b.input._session is None


def test_release_into_closed_window_is_not_a_cleanup_failure(backend):
    b = backend
    b.input.press_key_down('w')
    def gone(message, *_):
        if message == 0x101:
            raise WindowGoneError('游戏窗口已关闭或重建')
    b.api.on_post = gone
    b.input.release_all()
    assert not b.input._keys and b.input._session is None


@pytest.mark.parametrize('interruption', ['focus', 'pause'])
def test_completed_key_is_not_reported_as_failed_when_interrupted_while_settling(backend, interruption):
    """ESC 已完整发出后才切窗/暂停：返回 True，避免调用方按失败重试而重复按 ESC。"""
    b = backend
    def act(message, vk, _lp):
        if message == 0x101 and vk == 27:
            if interruption == 'focus': b.api.change_focus(30)
            else: b.ctl.paused = True
    b.api.on_post = act
    assert b.input.press_key('esc') is True
    assert len(posts(b.api, 0x100)) == len(posts(b.api, 0x101)) == 1
    assert b.input._session is None


@pytest.mark.parametrize('offset', [(1, 0), (-3, 2)])
def test_small_cursor_jitter_is_not_a_conflict_and_cursor_is_restored(backend, offset):
    """实测游戏不回写光标；日志里 1~4 像素的偏差来自鼠标抖动，不应中止点击。"""
    b = backend
    def jitter(message, *_):
        if message == 0x201:
            b.api.point = (b.api.point[0] + offset[0], b.api.point[1] + offset[1])
    b.api.on_post = jitter
    assert b.input.mouse_click(300, 400) is True
    assert len(posts(b.api, 0x201)) == len(posts(b.api, 0x202)) == 1
    assert b.api.cursor() == (7, 9)


def test_cursor_moved_beyond_tolerance_is_still_a_conflict(backend):
    b = backend
    def moved(message, *_):
        if message == 0x201:
            b.api.point = (b.api.point[0] + 4, b.api.point[1])
    b.api.on_post = moved
    assert b.input.mouse_click(300, 400) is False


def test_gui_thread_idle_limit_gives_up_quickly_without_clicking(backend, monkeypatch):
    """图形界面线程（自动对话）里，鼠标被持续使用时短暂等待后放弃，不长时间阻塞界面。"""
    b = backend
    sleep_hook(b, monkeypatch, lambda now: setattr(b.api, 'point', (round(now * 1000) % 1000 + 10, 900)))
    with module.input_wait_limit(.3):
        assert b.input.mouse_click(300, 400) is False
    assert b.clock.now < 1
    assert not posts(b.api, 0x201) and not b.api.protections
    b.input.logger.warning.assert_not_called()


def test_locked_desktop_reports_clear_reason_and_releases_inputs(backend):
    b = backend
    b.input.press_key_down('alt')
    def locked():
        raise CursorUnavailable('无法读取系统光标：(5, GetCursorPos, 拒绝访问。)')
    b.api.cursor = locked
    with pytest.raises(InputInterrupted, match='锁屏'):
        b.input.mouse_click(300, 400)
    assert not b.input._keys and not b.input._mouse_down and b.input._session is None



def test_window_wait_is_not_repeated_within_same_unavailable_episode(backend):
    """任务代码常吞掉异常后重试：同一段不可用期间只等待一次，不会每次截图再等 60 秒；窗口恢复后重新计时。"""
    b = backend
    b.api.minimized = True
    with pytest.raises(InputInterrupted):
        b.input.wait_for_window(60)
    assert 60 <= b.clock.now < 62
    started = b.clock.now
    with pytest.raises(InputInterrupted, match='最小化'):
        b.input.wait_for_window(60)
    assert b.clock.now - started < .1
    b.api.minimized = False
    b.input.wait_for_window(60)
    b.api.minimized = True
    started = b.clock.now
    with pytest.raises(InputInterrupted):
        b.input.wait_for_window(5)
    assert b.clock.now - started >= 5



def test_gui_thread_limit_bounds_window_wait_for_input(backend):
    """图形界面线程里窗口不可用时只短暂等待，随即报告原因，不阻塞界面。"""
    b = backend
    b.api.minimized = True
    with module.input_wait_limit(.3):
        with pytest.raises(InputInterrupted, match='最小化'):
            b.input.press_key('esc')
    assert b.clock.now < 1
    assert b.api.events == []


def test_completed_release_does_not_wait_for_minimized_window(backend):
    """释放已经发出后窗口才被最小化：按成功返回，不等待窗口恢复。"""
    b = backend
    b.input.press_key_down('w')
    def minimize(message, *_):
        if message == 0x101:
            b.api.minimized = True
    b.api.on_post = minimize
    assert b.input.press_key_up('w') is None
    assert b.clock.now < 1
    assert not b.input._keys and b.input._session is None
