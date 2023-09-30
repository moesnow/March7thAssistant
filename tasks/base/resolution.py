from managers.logger_manager import logger
from managers.translate_manager import _
import win32gui
import sys


class Resolution:
    @staticmethod
    def check(title, width, height):
        hwnd = win32gui.FindWindow("UnityWndClass", title)
        x, y, w, h = win32gui.GetClientRect(hwnd)
        if w != width or h != height:
            logger.error(_("游戏分辨率 {w}*{h} 请在游戏设置内切换为 {width}*{height} 窗口或全屏运行").format(w=w, h=h, width=width, height=height))
            input(_("按任意键关闭窗口. . ."))
            sys.exit(1)
        else:
            logger.debug(_("游戏分辨率 {w}*{h}").format(w=w, h=h))
