import pyautogui
import time


class Input:
    # 禁用pyautogui的失败安全特性，防止意外中断
    pyautogui.FAILSAFE = False

    def __init__(self, logger):
        self.logger = logger  # 初始化日志记录器

    def mouse_click(self, x, y):
        '''在屏幕上的（x，y）位置执行鼠标点击操作'''
        try:
            pyautogui.click(x, y)
            self.logger.debug(f"鼠标点击 ({x}, {y})")
        except Exception as e:
            self.logger.error(f"鼠标点击出错：{e}")

    def mouse_down(self, x, y):
        '''在屏幕上的（x，y）位置按下鼠标按钮'''
        try:
            pyautogui.mouseDown(x, y)
            self.logger.debug(f"鼠标按下 ({x}, {y})")
        except Exception as e:
            self.logger.error(f"鼠标按下出错：{e}")

    def mouse_up(self):
        '''释放鼠标按钮'''
        try:
            pyautogui.mouseUp()
            self.logger.debug("鼠标释放")
        except Exception as e:
            self.logger.error(f"鼠标释放出错：{e}")

    def mouse_move(self, x, y):
        '''将鼠标光标移动到屏幕上的（x，y）位置'''
        try:
            pyautogui.moveTo(x, y)
            self.logger.debug(f"鼠标移动 ({x}, {y})")
        except Exception as e:
            self.logger.error(f"鼠标移动出错：{e}")

    def mouse_scroll(self, count, direction=-1):
        '''滚动鼠标滚轮，方向和次数由参数指定'''
        for _ in range(count):
            pyautogui.scroll(direction)
        self.logger.debug(f"滚轮滚动 {count * direction} 次")

    def press_key(self, key, wait_time=0.2):
        '''模拟键盘按键，可以指定按下的时间'''
        try:
            pyautogui.keyDown(key)
            time.sleep(wait_time)  # 等待指定的时间
            pyautogui.keyUp(key)
            self.logger.debug(f"键盘按下 {key}")
        except Exception as e:
            self.logger.error(f"键盘按下 {key} 出错：{e}")

    def press_mouse(self, wait_time=0.2):
        '''模拟鼠标左键的点击操作，可以指定按下的时间'''
        try:
            pyautogui.mouseDown()
            time.sleep(wait_time)  # 等待指定的时间
            pyautogui.mouseUp()
            self.logger.debug("按下鼠标左键")
        except Exception as e:
            self.logger.error(f"按下鼠标左键出错：{e}")
