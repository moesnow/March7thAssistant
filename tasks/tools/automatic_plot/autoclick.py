from managers.automation_manager import auto
from managers.config_manager import config
from managers.logger_manager import logger
import pygetwindow as gw
import tkinter as tk


class AutoClick:
    def __init__(self, root):
        self.root = root
        self.root.title("自动对话")
        self.root.iconbitmap("./assets/logo/March7th.ico")

        self.start_img = "./assets/images/share/plot/start.png"
        self.select_img = "./assets/images/share/plot/select.png"

        # 设置窗口大小
        self.root.geometry("500x200")

        self.is_clicking = False

        self.status_label = tk.Label(root, text="\n进入剧情页面后自动开始运行\n支持大于等于 1920*1080 的 16:9 分辨率\n")
        self.status_label.pack()

        self.status_label = tk.Label(root, text="自动点击状态：已停止", fg="red")
        self.status_label.pack()

        self.check_game_status()

    def start_clicking(self):
        if not self.is_clicking:
            self.is_clicking = True
            logger.info("自动点击状态：运行中")
            self.status_label.config(text="自动点击状态：运行中", fg="green")
            self.click()

    def stop_clicking(self):
        if self.is_clicking:
            self.is_clicking = False
            logger.info("自动点击状态：已停止")
            self.status_label.config(text="自动点击状态：已停止", fg="red")

    def check_game_status(self):
        window = gw.getWindowsWithTitle(config.game_title_name)
        # 游戏前台
        if window and window[0].isActive:
            # 剧情界面
            if auto.find_element(self.start_img, "image", 0.9):
                self.start_clicking()
                # 存在选项
                auto.click_element(self.select_img, "image", 0.9, take_screenshot=False)
            else:
                self.stop_clicking()
        else:
            self.stop_clicking()
        # 定时检查游戏状态
        self.root.after(500, self.check_game_status)

    def click(self):
        if self.is_clicking:
            auto.press_mouse()
            self.root.after(10, self.click)
