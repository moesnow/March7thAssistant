
"""将 Automation 的鼠标接口映射到 Android 单指触摸。"""
import math

from module.automation.input_base import InputBase
from module.config.platform import TouchProfileInputError
from module.game.adb_transport import AdbError
from module.localization import tr


class AdbInput(InputBase):
    def __init__(self, controller):
        self._controller = controller

    def mouse_click(self, x, y):
        return self._controller.send_input("tap", x=float(x), y=float(y))

    def mouse_down(self, x, y):
        return self._controller.send_input("touch", action="down", x=float(x), y=float(y))

    def mouse_move(self, x, y):
        return self._controller.send_input("touch", action="move", x=float(x), y=float(y))

    def mouse_up(self):
        return self._controller.send_input("touch", action="up")

    def mouse_drag(self, start_x, start_y, end_x, end_y, duration=0.5, end_pause=0.0, repeats=1):
        if not math.isfinite(duration) or not 0 <= duration <= 60:
            raise ValueError("滑动时长必须在 0 到 60 秒之间")
        if not math.isfinite(end_pause) or not 0 <= end_pause <= 1:
            raise ValueError("拖动末尾停留时长必须在 0 到 1 秒之间")
        if type(repeats) is not int or not 1 <= repeats <= 10:
            raise ValueError("连续拖动次数必须是 1 到 10 之间的整数")
        points = [[float(start_x), float(start_y)], [float(end_x), float(end_y)]]
        for index in range(repeats):
            hold = end_pause if index == repeats - 1 else 0.0
            if not self._controller.send_input("swipe", points=points, duration_ms=round(duration * 1000),
                                               hold_end_ms=round(hold * 1000), timeout=4 + duration + hold):
                return False
        return True

    def release_all(self):
        self.mouse_up()

    def secretly_write(self, text, interval=0.1):
        raise AdbError("text_unsupported", tr("ADB 设备端服务不支持文本输入，请在设备上手动输入"))

    # Automation 的 touch_720 守卫会先拦截这些操作。
    def mouse_scroll(self, count, direction=-1, pause=True):
        raise TouchProfileInputError("mouse_scroll")

    def press_key(self, key, wait_time=0.2):
        raise TouchProfileInputError("press_key")

    def press_key_down(self, key):
        raise TouchProfileInputError("press_key_down")

    def press_key_up(self, key):
        raise TouchProfileInputError("press_key_up")

    def secretly_press_key(self, key, wait_time=0.2):
        raise TouchProfileInputError("secretly_press_key")

    def press_mouse(self, wait_time=0.2):
        raise TouchProfileInputError("press_mouse")
