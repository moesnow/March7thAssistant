from typing import Literal
from managers.config import config
from .screenshot import ScreenshotApp
from .autoplot import AutoPlot
from utils.gamecontroller import GameController
from module.automation.screenshot import Screenshot
from managers.logger import logger
import tkinter as tk
import threading
import time


class ToolManager:
    def run(self, tool: Literal["screenshot", "plot"]):
        try:
            if tool == "screenshot":
                self.run_screenshot()
            elif tool == "plot":
                self.run_plot()
        except Exception as e:
            logger.error(e)

    def run_screenshot(self):
        """捕获图像"""
        game = GameController(config.game_path, config.game_process_name, config.game_title_name, 'UnityWndClass', logger)
        if not game.switch_to_game():
            logger.error("游戏尚未启动")
        time.sleep(0.5)  # 等待窗口切换

        result = Screenshot.take_screenshot(config.game_title_name)
        if result:
            root = tk.Tk()
            ScreenshotApp(root, result[0])
            root.mainloop()
        else:
            logger.error("截图失败")

    def run_plot(self):
        """自动对话"""
        root = tk.Tk()
        AutoPlot(root, config.game_title_name, "./assets/images/share/plot/start.png", "./assets/images/share/plot/select.png")
        root.mainloop()


def start(tool: Literal["screenshot", "plot"]):
    """
    启动工具管理器的方法。
    :param tool: 启动工具，可以是'screenshot'或'plot'。
    """
    tool_manager = ToolManager()
    gui_thread = threading.Thread(target=tool_manager.run, args=(tool,))
    gui_thread.start()
