from managers.logger_manager import logger
from managers.translate_manager import _
import pyautogui
import time


class Input:
    pyautogui.FAILSAFE = False

    @staticmethod
    def mouse_click(x, y):
        try:
            pyautogui.click(x, y)
            logger.debug(_("鼠标点击 ({x}, {y})").format(x=x, y=y))
        except Exception as e:
            logger.error(_("鼠标点击出错：{e}").format(e=e))

    @staticmethod
    def mouse_down(x, y):
        try:
            pyautogui.mouseDown(x, y)
            logger.debug(_("鼠标按下 ({x}, {y})").format(x=x, y=y))
        except Exception as e:
            logger.error(_("鼠标按下出错：{e}").format(e=e))

    @staticmethod
    def mouse_up():
        try:
            pyautogui.mouseUp()
            logger.debug(_("鼠标释放"))
        except Exception as e:
            logger.error(_("鼠标释放出错：{e}").format(e=e))

    @staticmethod
    def mouse_move(x, y):
        try:
            pyautogui.moveTo(x, y)
            logger.debug(_("鼠标移动 ({x}, {y})").format(x=x, y=y))
        except Exception as e:
            logger.error(_("鼠标移动出错：{e}").format(e=e))

    @staticmethod
    def mouse_scroll(count, direction=-1):
        for i in range(count):
            pyautogui.scroll(direction)
        logger.debug(_("滚轮滚动 {x} 次").format(x=count * direction))

    @staticmethod
    def press_key(key, wait_time=0.2):
        try:
            pyautogui.keyDown(key)
            time.sleep(wait_time)
            pyautogui.keyUp(key)
            logger.debug(_("键盘按下 {key}").format(key=key))
        except Exception as e:
            logger.debug(_("键盘按下 {key} 出错：{e}").format(key=key, e=e))

    @staticmethod
    def press_mouse(wait_time=0.2):
        try:
            pyautogui.mouseDown()
            time.sleep(wait_time)
            pyautogui.mouseUp()
            logger.debug(_("按下鼠标左键"))
        except Exception as e:
            logger.debug(_("按下鼠标左键出错：{e}").format(e=e))
