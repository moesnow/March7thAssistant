from managers.logger_manager import logger
from managers.translate_manager import _
import win32gui
import pyautogui
import sys


class Resolution:
    @staticmethod
    def check(title, width, height):
        screen_width, screen_height = pyautogui.size()
        hwnd = win32gui.FindWindow("UnityWndClass", title)
        x, y, w, h = win32gui.GetClientRect(hwnd)
        if w != width or h != height:
            logger.error(_("游戏分辨率 {w}*{h} 请在游戏设置内切换为 {width}*{height} 窗口或全屏运行").format(w=w, h=h, width=width, height=height))
            if screen_width < 1920 or screen_height < 1080:
                logger.error(_("桌面分辨率 {w}*{h} 你可能需要更大的显示器或使用 HDMI/VGA 显卡欺骗器").format(w=w, h=h))
            input(_("按回车键关闭窗口. . ."))
            sys.exit(1)
        else:
            logger.debug(_("游戏分辨率 {w}*{h}").format(w=w, h=h))
