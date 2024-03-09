from utils.gamecontroller import GameController
from module.automation.screenshot import Screenshot
from managers.config import config
from managers.logger import logger
from .screenshot import ScreenshotApp
import tkinter as tk
import threading
import time


def run_gui():
    game = GameController(config.game_path, config.game_process_name, config.game_title_name, 'UnityWndClass', logger)
    try:
        if game.switch_to_game():
            time.sleep(0.5)
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
        logger.error(f"截图失败: {e}")


def game_screenshot():
    gui_thread = threading.Thread(target=run_gui)
    gui_thread.start()
