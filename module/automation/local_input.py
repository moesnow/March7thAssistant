import pyautogui
import time
from math import ceil

from module.automation.input_base import InputBase, begin_input_dispatch, input_deadline_reached
from utils.pause import pause_ctl


class LocalInput(InputBase):
    reports_dispatch = True
    # 禁用pyautogui的失败安全特性，防止意外中断
    pyautogui.FAILSAFE = False

    def __init__(self, logger):
        self.logger = logger  # 初始化日志记录器

    def mouse_click(self, x, y):
        '''在屏幕上的（x，y）位置执行鼠标点击操作'''
        pause_ctl.check_stop()
        if not begin_input_dispatch(time.monotonic()):
            return False
        try:
            pyautogui.click(x, y)
            self.logger.debug(f"鼠标点击 ({x}, {y})")
        except Exception as e:
            self.logger.error(f"鼠标点击出错：{e}")

    def mouse_down(self, x, y):
        '''在屏幕上的（x，y）位置按下鼠标按钮'''
        pause_ctl.check_stop()
        if not begin_input_dispatch(time.monotonic()):
            return False
        try:
            pyautogui.mouseDown(x, y)
            self.logger.debug(f"鼠标按下 ({x}, {y})")
        except Exception as e:
            self.logger.error(f"鼠标按下出错：{e}")
            return False

    def mouse_up(self):
        '''释放鼠标按钮'''
        try:
            pyautogui.mouseUp()
            self.logger.debug("鼠标释放")
        except Exception as e:
            self.logger.error(f"鼠标释放出错：{e}")
            return False

    def mouse_move(self, x, y):
        '''将鼠标光标移动到屏幕上的（x，y）位置'''
        try:
            pyautogui.moveTo(x, y)
            self.logger.debug(f"鼠标移动 ({x}, {y})")
        except Exception as e:
            self.logger.error(f"鼠标移动出错：{e}")

    def mouse_drag(self, start_x, start_y, end_x, end_y, duration=0.5, end_pause=0.0, repeats=1):
        '''按住鼠标左键从起点拖动到终点'''
        duration = max(0.0, float(duration or 0.0))
        steps = max(1, ceil(duration * 60))
        try:
            for index in range(repeats):
                pause_ctl.check_stop()
                if input_deadline_reached(time.monotonic()):
                    return False
                pyautogui.moveTo(start_x, start_y)
                pause_ctl.check_stop()
                if not begin_input_dispatch(time.monotonic()):
                    return False
                try:
                    pyautogui.mouseDown()
                    started = time.monotonic()
                    for step in range(1, steps + 1):
                        pause_ctl.check_stop()
                        progress = step / steps
                        remaining = started + duration * progress - time.monotonic()
                        if remaining > 0:
                            time.sleep(remaining)
                        pause_ctl.check_stop()
                        x = round(start_x + (end_x - start_x) * progress)
                        y = round(start_y + (end_y - start_y) * progress)
                        pyautogui.moveTo(x, y, _pause=False)
                    if end_pause and index == repeats - 1:
                        release_at = time.monotonic() + end_pause
                        while (remaining := release_at - time.monotonic()) > 0:
                            pause_ctl.check_stop()
                            time.sleep(min(1 / 60, remaining))
                finally:
                    try:
                        pyautogui.mouseUp()
                    except Exception as error:
                        self.logger.error(f"鼠标拖动结束时释放失败：{error}")
                        pause_ctl.check_stop()
                        raise
                pause_ctl.check_stop()
            self.logger.debug(f"鼠标拖动 ({start_x}, {start_y}) -> ({end_x}, {end_y})")
            return True
        except Exception as e:
            self.logger.error(f"鼠标拖动出错：{e}")
            raise

    def mouse_scroll(self, count, direction=-1, pause=True):
        '''滚动鼠标滚轮，方向和次数由参数指定'''
        for _ in range(count):
            pyautogui.scroll(direction, _pause=pause)
        self.logger.debug(f"滚轮滚动 {count * direction} 次")

    def press_key(self, key, wait_time=0.2):
        '''模拟键盘按键，可以指定按下的时间'''
        pause_ctl.check_stop()
        if not begin_input_dispatch(time.monotonic()):
            return False
        try:
            pyautogui.keyDown(key)
            time.sleep(wait_time)  # 等待指定的时间
            pyautogui.keyUp(key)
            self.logger.debug(f"键盘按下 {key}")
            return True
        except Exception as e:
            self.logger.error(f"键盘按下 {key} 出错：{e}")
            return False

    def press_key_down(self, key):
        '''模拟键盘按下指定按键'''
        try:
            pyautogui.keyDown(key)
            self.logger.debug(f"键盘按下 {key}")
        except Exception as e:
            self.logger.error(f"键盘按下 {key} 出错：{e}")

    def press_key_up(self, key):
        '''模拟键盘释放指定按键'''
        try:
            pyautogui.keyUp(key)
            self.logger.debug(f"键盘释放 {key}")
        except Exception as e:
            self.logger.error(f"键盘释放 {key} 出错：{e}")

    def secretly_press_key(self, key, wait_time=0.2):
        '''(不输出具体键位)模拟键盘按键，可以指定按下的时间'''
        try:
            pyautogui.write
            pyautogui.keyDown(key)
            time.sleep(wait_time)  # 等待指定的时间
            pyautogui.keyUp(key)
            self.logger.debug("键盘按下 *")
        except Exception as e:
            self.logger.error(f"键盘按下 * 出错：{e}")

    def press_mouse(self, wait_time=0.2):
        '''模拟鼠标左键的点击操作，可以指定按下的时间'''
        try:
            pyautogui.mouseDown()
            time.sleep(wait_time)  # 等待指定的时间
            pyautogui.mouseUp()
            self.logger.debug("按下鼠标左键")
        except Exception as e:
            self.logger.error(f"按下鼠标左键出错：{e}")

    def secretly_write(self, text, interval=0.1):
        '''模拟键盘输入字符串，可以指定字符输入间隔'''
        try:
            for character in text:
                pause_ctl.check_stop()
                pyautogui.write(character, interval=interval, _pause=False)
            pause_ctl.check_stop()
            self.logger.debug("键盘输入 ***")
        except Exception as e:
            self.logger.error(f"键盘输入 *** 出错：{e}")
