from managers.translate_manager import _
from managers.logger_manager import logger
import pygetwindow as gw
import pyautogui
import win32gui
import time


class WindowSwitcher:
    @staticmethod
    def check_and_switch(title, max_retries=4):
        for i in range(max_retries):
            windows = gw.getWindowsWithTitle(title)
            for window in windows:
                if window.title == title:
                    WindowSwitcher._activate_window(window)
                    if WindowSwitcher._is_window_active(window, title):
                        return True
                    else:
                        logger.info(_("切换窗口失败，尝试 ALT+TAB"))
                        pyautogui.hotkey('alt', 'tab')
                        time.sleep(2)
                    break
        return False

    @staticmethod
    def _activate_window(window):
        try:
            window.restore()
            window.activate()
            time.sleep(2)
        except Exception as e:
            logger.warning(f"切换窗口失败: {e}")

    @staticmethod
    def _is_window_active(window, title):
        try:
            hwnd = win32gui.FindWindow("UnityWndClass", title)
            win32gui.GetWindowRect(hwnd)
            return window.isActive
        except Exception as e:
            logger.warning(f"检测窗口状态失败: {e}")
            return False
