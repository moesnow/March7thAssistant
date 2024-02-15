from tasks.base.windowswitcher import WindowSwitcher
from module.automation.screenshot import Screenshot
from managers.config_manager import config
from managers.logger_manager import logger
from .screenshot import ScreenshotApp
import tkinter as tk


def game_screenshot():
    try:
        if WindowSwitcher.check_and_switch(config.game_title_name):
            result = Screenshot.take_screenshot(config.game_title_name)
            if result:
                root = tk.Tk()
                app = ScreenshotApp(root, result[0])
                root.mainloop()
            else:
                logger.error("截图失败")
        else:
            logger.error("游戏尚未启动")
    except Exception:
        pass
