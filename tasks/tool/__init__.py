from typing import Literal
from module.config import cfg
from .screenshot import ScreenshotApp
from .autoplot import AutoPlot
from utils.gamecontroller import GameController
from module.automation.screenshot import Screenshot
from module.logger import log
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
            log.error(e)

    def run_screenshot(self):
        """捕获图像"""
        game = GameController(cfg.game_path, cfg.game_process_name, cfg.game_title_name, 'UnityWndClass', log)
        if not game.switch_to_game():
            log.error("游戏尚未启动")
        time.sleep(0.5)  # 等待窗口切换

        result = Screenshot.take_screenshot(cfg.game_title_name)
        if result:
            root = tk.Tk()
            ScreenshotApp(root, result[0])
            root.mainloop()
        else:
            log.error("截图失败")

    def run_plot(self):
        """自动对话"""
        root = tk.Tk()
        AutoPlot(root, cfg.game_title_name,
                 [
                     "./assets/images/share/plot/start.png",
                     "./assets/images/share/plot/start_ps5.png",
                     "./assets/images/share/plot/start_xbox.png"
                 ],
                 "./assets/images/share/plot/select.png",
                 "./assets/images/share/plot/skip.png",)
        root.mainloop()


def start(tool: Literal["screenshot", "plot"]):
    """
    启动工具管理器的方法。
    :param tool: 启动工具，可以是'screenshot'或'plot'。
    """
    tool_manager = ToolManager()
    gui_thread = threading.Thread(target=tool_manager.run, args=(tool,))
    gui_thread.start()
