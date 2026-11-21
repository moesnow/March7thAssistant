from abc import ABC, abstractmethod
from contextlib import contextmanager
from contextvars import ContextVar
import sys
from module.config.platform import get_control_backend


input_deadline = ContextVar("input_dispatch_deadline", default=None)
_dispatch_observer = ContextVar("input_dispatch_observer", default=None)


def input_deadline_reached(now):
    deadline = input_deadline.get()
    return deadline is not None and now >= deadline


@contextmanager
def limit_input_deadline(deadline):
    previous = input_deadline.get()
    if previous is not None:
        deadline = previous if deadline is None else min(previous, deadline)
    token = input_deadline.set(deadline)
    try:
        yield
    finally:
        input_deadline.reset(token)


@contextmanager
def observe_input_dispatch(callback, *, deadline=None):
    """报告当前操作首次调用鼠标或键盘派发 API 的时间。"""
    token = _dispatch_observer.set(callback)
    try:
        with limit_input_deadline(deadline):
            yield
    finally:
        _dispatch_observer.reset(token)


def record_input_dispatch(now):
    if (observer := _dispatch_observer.get()) is not None:
        observer(now)
        _dispatch_observer.set(None)


def begin_input_dispatch(now):
    """检查时限，并在调用派发 API 前记录尝试。结果仍需另行核对。"""
    if input_deadline_reached(now):
        return False
    record_input_dispatch(now)
    return True


def background_enabled(config):
    return (sys.platform == 'win32'
            and config.get_value('local_control_mode', 'foreground') == 'background'
            and get_control_backend(config) == 'local')


class InputBase(ABC):
    handles_pause = False
    is_background = False
    # 支持普通按键、点击和拖动的投递记录。
    reports_dispatch = False

    def release_all(self):
        """释放后端持有的输入；无状态后端无需处理。"""

    def close(self):
        self.release_all()

    @abstractmethod
    def mouse_click(self, x, y):
        '''在屏幕上的（x，y）位置执行鼠标点击操作'''
        pass

    @abstractmethod
    def mouse_down(self, x, y):
        '''在屏幕上的（x，y）位置按下鼠标按钮'''
        pass

    @abstractmethod
    def mouse_up(self):
        '''释放鼠标按钮'''
        pass

    @abstractmethod
    def mouse_move(self, x, y):
        '''将鼠标光标移动到屏幕上的（x，y）位置'''
        pass

    def mouse_park(self, x, y):
        '''把光标停到屏幕上的（x，y）位置并留在那里，避免悬停改变游戏画面；光标本来就留在原处的后端与移动相同'''
        return self.mouse_move(x, y)

    @abstractmethod
    def mouse_drag(self, start_x, start_y, end_x, end_y, duration=0.5, end_pause=0.0, repeats=1):
        '''连续执行相同拖动，仅最后一次在松手前停留 end_pause 秒'''
        pass

    @abstractmethod
    def mouse_scroll(self, count, direction=-1, pause=True):
        '''滚动鼠标滚轮，方向和次数由参数指定'''
        pass

    @abstractmethod
    def press_key(self, key, wait_time=0.2):
        '''模拟键盘按键，可以指定按下的时间'''
        pass

    @abstractmethod
    def press_key_down(self, key):
        '''模拟键盘按下指定按键'''
        pass

    @abstractmethod
    def press_key_up(self, key):
        '''模拟键盘释放指定按键'''
        pass

    @abstractmethod
    def secretly_press_key(self, key, wait_time=0.2):
        '''(不输出具体键位)模拟键盘按键，可以指定按下的时间'''
        pass

    @abstractmethod
    def press_mouse(self, wait_time=0.2):
        '''模拟鼠标左键的点击操作，可以指定按下的时间'''
        pass

    @abstractmethod
    def secretly_write(self, text, interval=0.1):
        '''模拟键盘输入字符串，可以指定字符输入间隔'''
        pass
