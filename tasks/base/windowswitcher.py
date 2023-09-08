from managers.translate_manager import _
from managers.logger_manager import logger
import pygetwindow as gw
import pyautogui
import win32gui
import time


class WindowSwitcher:
    @staticmethod
    def check_and_switch(title):
        return WindowSwitcher.switch_window(title, max_retries=4)

    def switch_window(title, max_retries):
        for i in range(max_retries):
            window = gw.getWindowsWithTitle(title)
            if not window:
                continue
            for w in window:
                if w.title == title:
                    try:
                        hwnd = win32gui.FindWindow("UnityWndClass", title)
                        win32gui.GetWindowRect(hwnd)
                    except Exception as e:
                        continue
                    try:
                        w.restore()
                        w.activate()
                    except Exception as e:
                        logger.error(e)
                    time.sleep(2)
                    if w.isActive:
                        try:
                            hwnd = win32gui.FindWindow("UnityWndClass", title)
                            win32gui.GetWindowRect(hwnd)
                            return True
                        except Exception as e:
                            logger.error(e)
                    logger.info(_("切换窗口失败，尝试ALT+TAB"))
                    pyautogui.hotkey('alt', 'tab')
                    time.sleep(2)
                    continue
        return False
