from tasks.base.windowswitcher import WindowSwitcher
from module.automation.screenshot import Screenshot
from managers.config_manager import config
from managers.logger_manager import logger
from .screenshot import ScreenshotApp
import tkinter as tk
import threading


def run_gui():
    try:
        if WindowSwitcher.check_and_switch(config.game_title_name):
            result = Screenshot.take_screenshot(config.game_title_name)
            if result:
                root = tk.Tk()
                ScreenshotApp(root, result[0])
                root.mainloop()
            else:
                logger.error("截图失败")
        else:
            logger.error("游戏尚未启动")
    except Exception as e:
        logger.error(e)


def game_screenshot():
    gui_thread = threading.Thread(target=run_gui)
    gui_thread.start()
