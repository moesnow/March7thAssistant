from managers.logger_manager import logger
from managers.translate_manager import _
import win32gui
import sys


class Resolution:
    @staticmethod
    def check(title):
        hwnd = win32gui.FindWindow("UnityWndClass", title)
        x, y, w, h = win32gui.GetClientRect(hwnd)
        if w != 1920 or h != 1080:
            logger.error(_("游戏分辨率 {w}*{h} 请在游戏设置内切换为 1920*1080 窗口或全屏运行").format(w=w, h=h))
            input(_("按任意键关闭窗口. . ."))
            sys.exit(1)
        else:
            logger.debug(_("游戏分辨率 {w}*{h}").format(w=w, h=h))
