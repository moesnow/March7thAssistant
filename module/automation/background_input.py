"""星铁窗口消息输入。保持任务层的屏幕坐标、分开按下/释放及滚轮接口。"""
import math
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar

from .input_base import InputBase
from .windows_input import (WINDOW_EMPTY, WINDOW_EXITED, WINDOW_HIDDEN, WINDOW_MINIMIZED, WINDOW_MISSING,
                            CursorUnavailable, WindowGoneError)
from utils.pause import pause_ctl


class InputInterrupted(RuntimeError):
    """后台输入无法继续且需要用户处理（例如窗口持续最小化、无法读写光标）；不会触发重启游戏。"""


class GameWindowLost(RuntimeError):
    """游戏进程已退出或长时间找不到游戏窗口：与前台模式找不到窗口一样按普通错误处理（启动阶段会重启游戏）。"""


class _PauseRequested(Exception):
    pass


class _WindowLost(Exception):
    """输入过程中窗口不可用、移动或坐标越界：清理后按未完成返回，由下一次截图等待窗口恢复。"""


class _MouseConflict(Exception):
    """可恢复的鼠标干扰，不能作为普通错误结束整个任务。"""


class _ForegroundChanged(Exception):
    """正常的窗口切换：结束本次输入，交回任务重新识别界面。"""


# 可恢复的中断：清理后按「未完成」返回，交回任务重新确认界面。TimeoutError 来自游戏处理鼠标消息超时
# （例如加载画面），WindowGoneError 来自窗口在发送途中关闭。
_RECOVERABLE = (_PauseRequested, _ForegroundChanged, _WindowLost, WindowGoneError, TimeoutError)


_KEYS = {'esc': 27, 'escape': 27, 'enter': 13, 'return': 13, 'space': 32, 'tab': 9,
         'backspace': 8, 'delete': 46, 'insert': 45, 'home': 36, 'end': 35,
         'pageup': 33, 'pagedown': 34, 'up': 38, 'down': 40, 'left': 37, 'right': 39,
         'shift': 16, 'ctrl': 17, 'control': 17, 'alt': 18,
         'shiftleft': 160, 'shiftright': 161, 'ctrlleft': 162, 'ctrlright': 163,
         'altleft': 164, 'altright': 165, 'capslock': 20, 'numlock': 144,
         **{f'f{i}': 111 + i for i in range(1, 25)}}


def _vk(key):
    key = str(key).lower()
    if key in _KEYS:
        return _KEYS[key]
    if len(key) == 1 and key.isascii() and key.isalnum():
        return ord(key.upper())
    raise ValueError(f'后台输入不支持此按键：{key}')


def _duration(value):
    value = float(value)
    if not math.isfinite(value) or not 0 <= value <= 60:
        raise ValueError('输入时长必须在 0 到 60 秒之间')
    return value


def _position(point):
    return (int(point[0]) & 0xffff) | ((int(point[1]) & 0xffff) << 16)


# 光标读回与写入位置的容差（像素）。实测游戏不回写光标，日志中的 1~4 像素偏差来自鼠标轻微抖动，
# 不影响点击落点，不应视为冲突；超过容差才说明光标被移走。
_CURSOR_TOLERANCE = 3


def _near(actual, expected):
    return (actual is not None and expected is not None
            and abs(actual[0] - expected[0]) <= _CURSOR_TOLERANCE and abs(actual[1] - expected[1]) <= _CURSOR_TOLERANCE)


_WINDOW_TEXT = {
    WINDOW_EXITED: '游戏进程已退出',
    WINDOW_MISSING: '未找到游戏窗口',
    WINDOW_MINIMIZED: '游戏窗口已最小化',
    WINDOW_HIDDEN: '游戏窗口不可见',
    WINDOW_EMPTY: '游戏窗口尺寸为 0',
}

# 窗口暂时不可用（最小化、隐藏、重建）时，截图和输入最多等待多久（秒），与前台截图找不到窗口时的重试时限一致。
WINDOW_WAIT_SECONDS = 60

# 本线程内后台输入的阻塞等待上限（秒），包括等待鼠标空闲和等待窗口恢复；
# None 表示任务进程的默认行为：鼠标一直等到空闲、窗口最多等 WINDOW_WAIT_SECONDS（可随时暂停或停止）。
_input_wait_limit = ContextVar('background_input_wait_limit', default=None)


@contextmanager
def input_wait_limit(seconds):
    """临时限制后台输入的阻塞等待：图形界面线程里的调用不能长时间阻塞，超时按未完成返回或报告原因。"""
    token = _input_wait_limit.set(max(0.0, float(seconds)))
    try:
        yield
    finally:
        _input_wait_limit.reset(token)


class BackgroundInput(InputBase):
    handles_pause = True
    is_background = True

    def __init__(self, logger, title, process_name, *, protect_mouse=False, api=None, banner=None, controller=None):
        self.logger, self.title, self.process_name = logger, title, process_name
        self._api = api
        self._banner = banner
        self._pause = controller if controller is not None else pause_ctl
        self._lock = threading.RLock()
        self._closed = False
        self._session = None
        self._keys = []
        self._mouse_down = False
        self._point = None
        self._last_click = None
        self._written_cursor = None
        self._target_identity = None
        self._foreground_identity = None
        self.protect_mouse = bool(protect_mouse)
        self._protection = None
        self._pointer_active = False
        self._committed = False
        self._settle_until = 0
        self._mouse_notice = False
        self._mouse_failures = 0
        self._mouse_interrupted = False
        self._window_notice = None
        self._window_wait_expired = False
        self._pause.register_input(self)

    @property
    def api(self):
        if self._api is None:
            from .windows_input import WindowsInputApi
            self._api = WindowsInputApi()
        return self._api

    @property
    def banner(self):
        if self._banner is None:
            from .scroll_banner import ScrollBanner
            self._banner = ScrollBanner()
        return self._banner

    def _target(self):
        target, problem = self.api.inspect(self.title, self.process_name)
        if problem:
            raise _WindowLost(_WINDOW_TEXT[problem])
        return target

    def window_problem(self):
        """游戏窗口不能后台操作的原因（WINDOW_* 之一），可以操作时返回 None。"""
        return self.api.inspect(self.title, self.process_name)[1]

    def is_available(self):
        if self.window_problem() is None:
            return True
        self._release_quietly()
        return False

    def _release_quietly(self):
        try:
            self.release_all()
        except Exception as error:
            if self.logger:
                self.logger.warning(f'后台输入清理失败：{error}')

    def wait_for_window(self, timeout):
        """等待游戏窗口恢复为可后台操作，期间不发送任何输入，仍响应暂停与停止。

        窗口暂时不可用（最小化、隐藏、重建）时最多等待 timeout 秒；游戏进程已退出时不再等待。
        超时或进程退出时抛出写明原因的异常，不把它们混同为「请恢复窗口」。
        同一段不可用期间只等待一次：任务代码常吞掉异常后重试，等满时限后再调用会立即报告，不会反复累积等待。
        """
        problem = self.window_problem()
        if problem is None:
            self._window_wait_expired = False
            return
        self._release_quietly()
        if self._window_wait_expired and problem != WINDOW_EXITED:
            raise self._window_timeout(problem, timeout)
        if problem != WINDOW_EXITED and timeout > 0 and self.logger:
            hint = '，请将游戏窗口还原（可以留在其他窗口之后，无需切到前台）' if problem == WINDOW_MINIMIZED else ''
            self.logger.warning(f'{_WINDOW_TEXT[problem]}，后台模式暂时无法截图和操作，'
                                f'最多等待 {timeout:.0f} 秒{hint}')
        deadline = time.monotonic() + timeout
        while problem is not None:
            if problem == WINDOW_EXITED:
                raise GameWindowLost('游戏进程已退出，游戏窗口已关闭')
            if time.monotonic() >= deadline:
                self._window_wait_expired = timeout > 0
                raise self._window_timeout(problem, timeout)
            paused_at = time.monotonic()
            self._pause.checkpoint()
            # 暂停期间不计入等待时长。
            deadline += max(0.0, time.monotonic() - paused_at - .05)
            time.sleep(max(0.0, min(.5, deadline - time.monotonic())))
            problem = self.window_problem()
        self._window_wait_expired = False
        if timeout > 0 and self.logger:
            self.logger.info('游戏窗口已恢复，继续执行')

    @staticmethod
    def _window_timeout(problem, timeout):
        waited = f'（已等待 {timeout:.0f} 秒）' if timeout > 0 else ''
        if problem == WINDOW_MISSING:
            return GameWindowLost(f'未找到游戏窗口{waited}')
        if problem == WINDOW_MINIMIZED:
            return InputInterrupted(f'游戏窗口已最小化{waited}。后台模式不会自动还原或激活游戏，'
                                    '请将游戏窗口还原（可以留在其他窗口之后，无需切到前台）后重新运行')
        return InputInterrupted(f'{_WINDOW_TEXT[problem]}{waited}，后台模式无法截图和操作，请检查游戏窗口后重新运行')

    def _check(self):
        self._pause.check_stop()
        if self._closed:
            raise InputInterrupted('后台输入已取消')
        if self._pause.is_paused():
            raise _PauseRequested()
        if self._session:
            target, foreground, _cursor, _activated, geometry = self._session
            if not self.api.usable(target) or self._geometry(target) != geometry:
                raise _WindowLost('游戏窗口已关闭、最小化或改变位置')
            if self.api.foreground() != foreground:
                raise _ForegroundChanged()
            if self._pointer_active:
                if self._protection is not None and not self._protection.active:
                    raise _MouseConflict('鼠标保护已到期')
                if self._written_cursor is not None:
                    actual = self.api.cursor()
                    if not _near(actual, self._written_cursor):
                        raise _MouseConflict(f'光标位置不同步（预期 {self._written_cursor}，实际 {actual}）')

    def _geometry(self, target):
        return self.api.client_to_screen(target, (0, 0)), self.api.size(target)

    def _wait(self, duration, check=None):
        end = time.monotonic() + duration
        check = check or self._check
        while True:
            check()
            remaining = end - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(.02, remaining))

    def _begin(self, target=None):
        self._check()
        if self._session:
            return
        target = target or self._target()
        if not self.api.usable(target):
            raise _WindowLost('游戏窗口已关闭、最小化或改变位置')
        self._adopt_target(target)
        foreground, cursor = self.api.foreground(), self.api.cursor()
        self._foreground_identity = self.api.identity(foreground)
        activated = foreground != target.hwnd
        self._session = (target, foreground, cursor, activated, self._geometry(target))
        if activated:
            self.api.post(target, 0x0006, 1)  # WM_ACTIVATE / WA_ACTIVE
            self._wait(.08)
            # 大世界激活可能由游戏自己居中光标，只有该位置仍归本次操作时才恢复。
            width, height = self.api.size(target)
            center = self.api.client_to_screen(target, ((width - 1)//2, (height - 1)//2))
            if _near(self.api.cursor(), center) and not _near(cursor, center):
                self._written_cursor = center

    def _adopt_target(self, target):
        if self._target_identity is not None and self._target_identity != target:
            self._point = self._last_click = None
        self._target_identity = target

    def _end(self):
        if self._session is None:
            self._release_protection()
            return
        target, foreground, cursor, activated, _geometry = self._session
        errors = []
        if self._mouse_down:
            self._mouse_interrupted = True
        alive = self.api.identity(target.hwnd) == target
        if alive:
            for vk in self._keys[:][::-1]:
                try:
                    self._key(vk, False, cleanup=True)
                    self._keys.remove(vk)
                except WindowGoneError:
                    alive = False  # 窗口刚好关闭：没有可释放的对象
                    break
                except Exception as e:
                    errors.append(e)
        if alive and self._mouse_down:
            try:
                self.api.post(target, 0x0202, 0, _position(self._point or (0, 0)))
                self._mouse_down = False
            except WindowGoneError:
                alive = False
            except Exception as e:
                errors.append(e)
        if alive and activated and self.api.foreground() != target.hwnd:
            try:
                self.api.post(target, 0x0006, 0)
                time.sleep(.05)  # 与实测一致：给异步失活消息一次处理机会再恢复光标。
            except WindowGoneError:
                alive = False
            except Exception as e:
                errors.append(e)
        if not alive:
            errors.clear()
            self._keys.clear()
            self._mouse_down = False
        # 用户后来移动了鼠标或切了窗口，就不再把光标拉回旧位置。恢复光标只是善后，
        # 失败（例如锁屏）不能让已释放的输入被当作清理失败。
        try:
            if (self._written_cursor is not None and self.api.foreground() == foreground
                    and self._foreground_identity is not None
                    and self.api.identity(foreground) == self._foreground_identity
                    and _near(self.api.cursor(), self._written_cursor)):
                self.api.move(cursor)
        except Exception as error:
            if self.logger:
                self.logger.warning(f'恢复光标位置失败：{error}')
        self._written_cursor = None
        self._pointer_active = False
        self._settle_until = 0
        if not errors:
            self._session = None
        try:
            self._release_protection()
        finally:
            if errors:
                raise RuntimeError('后台输入释放失败') from errors[0]

    def _finish(self):
        try:
            # PostMessage 成功不代表游戏已处理释放事件；过早失活会吞掉 ESC。
            remaining = self._settle_until - time.monotonic()
            if remaining > 0:
                self._wait(remaining)
        finally:
            self._end()

    def _release_protection(self):
        protection, self._protection = self._protection, None
        if protection is not None:
            protection.close()

    def _protection_expired(self, protection):
        # 分开调用 mouse_down/mouse_up 时也不能留下无限期按住的鼠标。
        with self._lock:
            if self._protection is protection:
                try:
                    if self._mouse_down:
                        self._mouse_interrupted = True
                        if self.logger:
                            self.logger.warning('鼠标保护已结束，已释放本次按住状态，请检查界面后继续')
                    self._end()
                except Exception as error:
                    if self.logger:
                        self.logger.warning(f'鼠标保护到期后的输入清理失败：{error}')

    def _mouse_context(self):
        target = self._session[0] if self._session else self._target()
        foreground = self._session[1] if self._session else self.api.foreground()
        identity = self._foreground_identity if self._session else self.api.identity(foreground)
        return target, foreground, identity, self._geometry(target)

    def _check_mouse_context(self, context):
        self._pause.check_stop()
        if self._closed:
            raise InputInterrupted('后台输入已取消')
        if self._pause.is_paused():
            raise _PauseRequested()
        target, foreground, identity, geometry = context
        if not self.api.usable(target) or self._geometry(target) != geometry:
            raise _WindowLost('游戏窗口已关闭、最小化或改变位置')
        if self.api.foreground() != foreground or self.api.identity(foreground) != identity:
            raise _ForegroundChanged()

    def _foreground_changed(self):
        # 调用点都已清理本次输入，并离开输入锁；不重放可能已经生效的按键/点击。
        self._pause.checkpoint()
        if self.logger:
            self.logger.debug('前台窗口已切换，已清理本次输入，继续检查游戏界面')
        return False

    def _interrupted(self, error, done=False, outcome=None):
        """可恢复的中断：调用点已清理输入并离开输入锁。

        已完整发出的操作仍返回原结果，避免任务把 False 当作未执行而重放已生效的点击/按键；
        尚未完成时返回 False，由任务重新确认界面，这里不重放。
        """
        if isinstance(error, _PauseRequested):
            self._pause.checkpoint()
        elif isinstance(error, _ForegroundChanged):
            self._foreground_changed()
        elif isinstance(error, TimeoutError):
            if self.logger:
                self.logger.warning('游戏未及时处理鼠标输入（可能正在加载），已释放本次输入，等待界面确认后重试')
        elif not done and self.window_problem() is not None:
            # 窗口不可用时不立即返回：有的任务循环只按键不截图，立即返回会空转。等窗口恢复后再按未完成返回，
            # 不重放之前决定的输入；游戏退出或等待超时由 wait_for_window 抛出写明原因的异常。
            limit = _input_wait_limit.get()
            self.wait_for_window(WINDOW_WAIT_SECONDS if limit is None else limit)
        elif self.logger:
            message = f'{error or "游戏窗口状态已变化"}，本次后台输入未完成，已释放输入，等待窗口恢复后重新确认界面'
            if message != self._window_notice:
                self._window_notice = message
                self.logger.warning(message)
            else:
                self.logger.debug(message)
        return outcome if done else False

    @staticmethod
    def _cursor_unavailable(error):
        return InputInterrupted('无法读写系统光标（可能处于锁屏或 UAC 等安全桌面），'
                                f'后台模式运行期间需要保持系统解锁：{error}')

    def _wait_mouse_idle(self, context, timeout=None):
        position = self.api.cursor()
        quiet_since = started = time.monotonic()
        while True:
            self._check_mouse_context(context)
            now, current = time.monotonic(), self.api.cursor()
            # 与静止起点比较，抖动不算使用，缓慢拖动累计超出容差仍算。
            if not _near(current, position) or self.api.mouse_buttons_down():
                position, quiet_since = current, now
            if now - quiet_since >= .25:
                return True
            if timeout is not None and now - started >= timeout:
                return False
            time.sleep(.02)

    def _show_mouse_notice(self, target, protection=False):
        from module.localization import tr
        message = (tr('正在短暂保护鼠标，键盘和暂停热键仍可用') if protection
                   else tr('等待鼠标空闲，任务将自动继续'))
        if self._mouse_notice == message:
            return
        if self.logger:
            self.logger.warning(message)
        try:
            self.banner.show(target, message=message)
            self._mouse_notice = message
        except Exception as error:
            if self.logger:
                self.logger.warning(f'无法显示后台输入提示：{error}')

    def _prepare_mouse(self, context, failures):
        self._check_mouse_context(context)
        if self._mouse_down or self._protection is not None:
            self._check()
            return
        limit = _input_wait_limit.get()
        if failures < 3:
            if not self._wait_mouse_idle(context, timeout=.5 if limit is None else min(.5, limit)):
                raise _MouseConflict('鼠标尚未空闲')
            return
        if self.protect_mouse and not self.api.mouse_buttons_down():
            self._show_mouse_notice(context[0], protection=True)
            try:
                self._protection = self.api.protect_mouse(timeout=2, on_expire=self._protection_expired)
                return
            except Exception as error:
                if self.logger:
                    self.logger.warning(f'无法启用鼠标保护，改为等待鼠标空闲：{error}')
        self._show_mouse_notice(context[0])
        if not self._wait_mouse_idle(context, timeout=limit):
            raise _MouseConflict('鼠标持续使用中')

    def release_all(self):
        with self._lock:
            try:
                self._end()
            finally:
                if self._banner is not None:
                    self._banner.hide(immediate=True)

    def close(self):
        self._closed = True
        try:
            self.release_all()
        finally:
            if self._banner is not None:
                self._banner.close()

    def _perform(self, operation, *, pointer=False):
        # 不持锁等待恢复，否则暂停线程无法完成清理回执。
        self._pause.checkpoint()
        done, outcome = False, None
        try:
            with self._lock:
                context = self._mouse_context() if pointer else None
                held_keys = self._keys[:]
                failures = self._mouse_failures if pointer else 0
                try:
                    while True:
                        self._committed = self._mouse_down
                        try:
                            if pointer:
                                self._prepare_mouse(context, failures)
                                self._check_mouse_context(context)
                            self._begin(context[0] if context else None)
                            # 重试前已释放所有输入，恢复显式按住的键（例如 Alt + 点击）。
                            for vk in held_keys:
                                if vk not in self._keys:
                                    self._key(vk, True)
                            outcome = operation()
                            done = True
                            if pointer:
                                self._mouse_failures = 0
                            self._window_notice = None
                            if not self._keys and not self._mouse_down:
                                self._finish()
                            elif not self._mouse_down and self._protection is not None:
                                self._wait(max(0, self._settle_until - time.monotonic()))
                                self._release_protection()
                            return outcome
                        except _MouseConflict as error:
                            committed = self._committed
                            self._end()
                            if done:
                                return outcome  # 操作已完整发出，收尾时的光标变化不重放
                            failures += 1
                            self._mouse_failures = failures
                            if committed:
                                self._mouse_interrupted = True
                                if self.logger:
                                    self.logger.warning(f'后台鼠标手势已中断：{error}；已释放输入，等待界面确认后重试')
                                return False
                            # 限定了等待时长（图形界面线程）时不在本次调用里反复重试，交给下一轮。
                            limited = _input_wait_limit.get() is not None
                            if failures > 3 or limited:
                                if self.logger:
                                    log = self.logger.debug if limited else self.logger.warning
                                    log(f'后台指针无法稳定定位：{error}；本次操作未发出，等待界面确认后重试')
                                return False
                            if self.logger:
                                self.logger.debug(f'后台鼠标输入尚未就绪：{error}；准备重试（{min(failures, 3)}/3）')
                        except BaseException:
                            self._end()
                            raise
                finally:
                    if self._mouse_notice:
                        self.banner.hide(immediate=True)
                        self._mouse_notice = False
        except _RECOVERABLE as error:
            return self._interrupted(error, done, outcome)
        except CursorUnavailable as error:
            raise self._cursor_unavailable(error) from error

    def _move_client(self, point):
        self._check()
        target = self._session[0]
        width, height = self.api.size(target)
        if not 0 <= point[0] < width or not 0 <= point[1] < height:
            raise _WindowLost('输入位置超出游戏客户区')
        self._point = (round(point[0]), round(point[1]))
        self._written_cursor = self.api.client_to_screen(target, self._point)
        self._pointer_active = True
        self.api.move(self._written_cursor)
        self.api.send_mouse(target, 0x0200, 1 if self._mouse_down else 0, _position(self._point))

    def _move_screen(self, x, y):
        self._move_client(self.api.screen_to_client(self._session[0], (round(x), round(y))))

    def mouse_move(self, x, y):
        def move():
            if not self._mouse_down:
                return self._move_screen(x, y)
            target = self._session[0]
            end = self.api.screen_to_client(target, (round(x), round(y)))
            width, height = self.api.size(target)
            if not (0 <= end[0] < width and 0 <= end[1] < height):
                raise _WindowLost('输入位置超出游戏客户区')
            start = self._point
            # move 的 .1 秒最多约六帧；长跳转不能排出数百个同步消息。
            steps = max(1, min(6, math.ceil(math.dist(start, end) / 16)))
            started = time.monotonic()
            # 分开调用 down/move/up 的扫动同样需要持续时间。前台 moveTo 默认停顿 .1 秒。
            for step in range(1, steps + 1):
                self._move_client(tuple(round(a+(b-a)*step/steps) for a,b in zip(start,end)))
                self._wait(max(0, started + .1*step/steps - time.monotonic()))
        return self._perform(move, pointer=True)

    def _down(self):
        self._check()
        # 先登记，再投递；投递过程出错也会尝试释放。
        self._committed = True
        self._mouse_interrupted = False
        self._mouse_down = True
        self.api.send_mouse(self._session[0], 0x0201, 1, _position(self._point))
        self._last_click = (self._session[0], self._point, self._session[4])

    def mouse_down(self, x, y):
        def down():
            self._move_screen(x, y)
            self._wait(.02)
            self._down()
        return self._perform(down, pointer=True)

    def _up_mouse(self):
        self.api.send_mouse(self._session[0], 0x0202, 0, _position(self._point))
        self._mouse_down = False
        self._pointer_active = False
        self._settle_until = time.monotonic() + .12

    def mouse_up(self):
        done = False
        try:
            with self._lock:
                if not self._mouse_down:
                    if self._mouse_interrupted:
                        self._mouse_interrupted = False
                        return False
                    return
                if self.api.identity(self._session[0].hwnd) != self._session[0]:
                    self._end()
                    return False
                try:
                    self._up_mouse()
                    done = True
                    if not self._keys:
                        self._finish()
                    elif self._protection is not None:
                        self._wait(max(0, self._settle_until - time.monotonic()))
                        self._release_protection()
                except BaseException:
                    self._end()
                    raise
        except _RECOVERABLE as error:
            return self._interrupted(error, done)
        except CursorUnavailable as error:
            raise self._cursor_unavailable(error) from error

    def mouse_click(self, x, y):
        def click():
            self._move_screen(x, y)
            self._wait(.02)
            self._down()
            self._wait(.08)
            self._up_mouse()
            return True
        return self._perform(click, pointer=True)

    def press_mouse(self, wait_time=.2):
        duration = _duration(wait_time)
        def click():
            target = self._session[0]
            captured = self.api.cursor_locked(target)
            if captured:
                # 不带坐标的普攻不应复用上一张 UI 的点击位置，也不能与视角锁定争夺光标。
                self._point = self.api.screen_to_client(target, self.api.cursor())
                self._pointer_active = False
            else:
                point = self._point or tuple(value//2 for value in self.api.size(target))
                self._move_client(point)
            self._down()
            if captured:
                self._last_click = None  # 普攻不是可供文字输入重新定位的 UI 输入框。
            self._wait(duration)
            self._up_mouse()
            return True
        return self._perform(click, pointer=True)

    def mouse_drag(self, start_x, start_y, end_x, end_y, duration=.5):
        duration = _duration(duration)
        def drag():
            self._move_screen(start_x, start_y)
            start = self._point
            end = self.api.screen_to_client(self._session[0], (round(end_x), round(end_y)))
            self._down()
            steps = max(1, round(duration * 60))
            for step in range(1, steps + 1):
                self._move_client(tuple(round(a+(b-a)*step/steps) for a,b in zip(start,end)))
                self._wait(duration/steps)
            self._up_mouse()
            return True
        return self._perform(drag, pointer=True)

    def _key(self, vk, down, cleanup=False):
        if not cleanup:
            self._check()
        if down and vk not in self._keys:
            # 通过切窗/暂停检查后才登记；发送过程失败仍会尝试释放。
            self._keys.append(vk)
        flags = (self.api.scan_code(vk) << 16) | 1
        if vk in (33,34,35,36,37,38,39,40,45,46,163,165):
            flags |= 1 << 24
        alt = vk in (18,164,165) or any(key in self._keys for key in (18,164,165))
        if alt:
            flags |= 1 << 29
        if not down:
            flags |= (1 << 30) | (1 << 31)
        self.api.post(self._session[0], (0x0104 if down else 0x0105) if alt else (0x0100 if down else 0x0101), vk, flags)
        if not down and not cleanup:
            self._settle_until = time.monotonic() + .12

    def press_key_down(self, key):
        vk = _vk(key)
        def down():
            self._key(vk, True)
        return self._perform(down)

    def press_key_up(self, key):
        vk = _vk(key)
        done = False
        try:
            with self._lock:
                if vk not in self._keys:
                    return
                if self.api.identity(self._session[0].hwnd) != self._session[0]:
                    self._end()
                    return
                try:
                    self._key(vk, False, cleanup=True)
                    self._keys.remove(vk)
                    done = True
                    self._settle_until = time.monotonic() + .12
                    if not self._keys and not self._mouse_down:
                        self._finish()
                except BaseException:
                    self._end()
                    raise
        except _RECOVERABLE as error:
            return self._interrupted(error, done)
        except CursorUnavailable as error:
            raise self._cursor_unavailable(error) from error

    def press_key(self, key, wait_time=.2):
        keys = [_vk(part) for part in str(key).split('+')]
        duration = _duration(wait_time)
        def press():
            added = [vk for vk in keys if vk not in self._keys]
            for vk in added:
                self._key(vk, True)
            self._wait(duration)
            for vk in reversed(added):
                self._key(vk, False)
                self._keys.remove(vk)
            return True
        return self._perform(press)

    def secretly_press_key(self, key, wait_time=.2):
        return self.press_key(key, wait_time)

    def secretly_write(self, text, interval=.1):
        interval = _duration(interval)
        def write():
            # 实测输入框需要在同一激活会话内重新点击。限定为最近点击的同一个窗口/几何。
            if self._last_click:
                target, point, geometry = self._last_click
                if target != self._session[0] or geometry != self._session[4]:
                    raise _WindowLost('输入框所属窗口已改变，请重新定位输入框')
                self._move_client(point)
                self._down()
                self._wait(.08)
                self._up_mouse()
                self._wait(.2)
                self._release_protection()
            encoded = str(text).encode('utf-16-le')
            for index in range(0, len(encoded), 2):
                self._check()
                self.api.post(self._session[0], 0x0102, int.from_bytes(encoded[index:index+2], 'little'), 1)
                self._committed = True
                self._settle_until = time.monotonic() + .12
                self._wait(interval)
            return True
        return self._perform(write, pointer=bool(self._last_click))

    def mouse_scroll(self, count, direction=-1, pause=True):
        if not isinstance(count, int) or count < 0 or not isinstance(direction, int):
            raise ValueError('滚轮次数必须为非负整数，方向必须为整数')
        if not count or not direction:
            return
        self._pause.checkpoint()
        try:
            with self._lock:
                self._end()
                self._check()
                context = self._mouse_context()
                remaining, failures = [count], self._mouse_failures
                try:
                    while remaining[0]:
                        try:
                            self._prepare_mouse(context, failures)
                            result = self._scroll_foreground(remaining, direction, pause, context)
                            self._mouse_failures = 0
                            return result
                        except _MouseConflict:
                            self._release_protection()
                            failures += 1
                            self._mouse_failures = failures
                            if _input_wait_limit.get() is not None and failures > 3:
                                return False
                    self._mouse_failures = 0
                    return True
                finally:
                    self._release_protection()
                    if self._mouse_notice:
                        self.banner.hide(immediate=True)
                        self._mouse_notice = False
        except _RECOVERABLE as error:
            return self._interrupted(error)
        except CursorUnavailable as error:
            raise self._cursor_unavailable(error) from error

    def _scroll_foreground(self, remaining, direction, pause, context):
        self._check_mouse_context(context)
        target, foreground, original, _geometry = context
        self._adopt_target(target)
        cursor = self.api.cursor()
        temporary = foreground != target.hwnd
        watch = None
        owned_cursor = None
        acquired = False
        succeeded = False

        def check():
            self._pause.check_stop()
            if self._closed:
                raise InputInterrupted('后台输入已取消')
            if self._pause.is_paused():
                raise _PauseRequested()
            if not self.api.usable(target):
                raise _WindowLost('游戏窗口已关闭或最小化，滚轮操作已取消')
            if (watch and watch.lost) or self.api.foreground() != target.hwnd:
                raise _ForegroundChanged()
            if owned_cursor is not None and not _near(self.api.cursor(), owned_cursor):
                raise _MouseConflict('滚轮位置发生变化')
            if self._protection is not None and not self._protection.active:
                raise _MouseConflict('鼠标保护已到期')

        try:
            if temporary:
                # 必须先显示提示且成功建立焦点观察，才允许切换游戏到前台。
                self.banner.show(target)
            watch = self.api.watch_foreground(target)
            expected = original.hwnd if original else 0
            if temporary:
                if not self.api.focus(target, expected, watch):
                    if watch.lost or self.api.foreground() != expected:
                        raise _ForegroundChanged()
                    raise InputInterrupted('无法安全切换游戏到前台，滚轮操作已取消')
            acquired = True
            watch.arm()
            watch.sync()
            check()
            if temporary:
                # 之前的后台悬停发送过 WA_INACTIVE。仅系统前台句柄变化不足以
                # 恢复游戏内部输入状态，需在确认前台归属后补齐激活并等待处理。
                self.api.post(target, 0x0006, 1)
                self._wait(.08, check)
            point = self._point or tuple(value//2 for value in self.api.size(target))
            width, height = self.api.size(target)
            if not (0 <= point[0] < width and 0 <= point[1] < height):
                raise _WindowLost('滚轮位置超出游戏客户区，请重新定位')
            owned_cursor = self.api.client_to_screen(target, point)
            self.api.move(owned_cursor)
            self._wait(.05, check)
            while remaining[0]:
                check()
                remaining[0] -= 1  # 已发出的滚轮不能因鼠标冲突重放。
                self.api.scroll(direction, pause)
                check()
            # 系统注入的滚轮异步分发，pause=False 时不能发完立刻挪开光标/失活。
            self._wait(.2, check)
            succeeded = True
            return True
        finally:
            try:
                if watch:
                    watch.sync()
                requested = watch is not None and watch.focus_requested == target.hwnd
                still_owned = (acquired or requested) and watch and not watch.lost and self.api.foreground() == target.hwnd
                if still_owned and owned_cursor is not None and _near(self.api.cursor(), owned_cursor):
                    self.api.move(cursor)
                if (temporary and still_owned and original and self.api.usable(original)
                        and not watch.lost and self.api.foreground() == target.hwnd):
                    if not self.api.focus(original, target.hwnd, watch) and self.logger:
                        if watch.lost or self.api.foreground() != target.hwnd:
                            self.logger.debug('滚轮结束时前台窗口已变化，保留当前窗口')
                        else:
                            self.logger.warning('滚轮操作结束，但系统未允许恢复原窗口')
            finally:
                if watch:
                    watch.close()
                if temporary and self._banner is not None:
                    self._banner.hide(immediate=not succeeded)
