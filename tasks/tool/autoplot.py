from module.automation import auto
import pygetwindow as gw
import tkinter as tk


class AutoPlot:
    def __init__(self, root, game_title_name: str, start_img: list, select_img: str, skip_img: str):
        """初始化 AutoPlot 类的实例。

        参数:
        - root: tkinter 的根窗口实例。
        """
        self.game_title_name = game_title_name
        self.start_img = start_img
        self.select_img = select_img
        self.skip_img = skip_img
        self.setup_root(root)
        self.check_game_status()

    def setup_root(self, root):
        """配置根窗口的基本属性和界面元素。

        参数:
        - root: tkinter 的根窗口实例。
        """
        self.root = root
        self.root.title("自动对话")
        self.root.geometry("500x200")
        self.root.iconbitmap("./assets/logo/March7th.ico")

        self.is_clicking = False  # 控制自动点击的状态

        # 显示当前的运行状态
        self.init_status_labels()

    def init_status_labels(self):
        """初始化并显示状态标签。"""
        instruction_text = "\n进入剧情页面后自动开始运行\n支持大于等于 1920*1080 的 16:9 分辨率\n"
        self.instruction_label = tk.Label(self.root, text=instruction_text)
        self.instruction_label.pack()

        self.update_status_label(False)  # 初始状态为停止

    def update_status_label(self, is_clicking):
        """更新状态标签的文本和颜色。

        参数:
        - is_clicking: 表示是否正在自动点击的布尔值。
        """
        status_text = "自动点击状态：运行中" if is_clicking else "自动点击状态：已停止"
        status_color = "green" if is_clicking else "red"
        if hasattr(self, 'status_label'):
            self.status_label.config(text=status_text, fg=status_color)
            self.root.update()  # 强制刷新界面
        else:
            self.status_label = tk.Label(self.root, text=status_text, fg=status_color)
            self.status_label.pack()

    def start_clicking(self):
        """启动自动点击流程。"""
        if not self.is_clicking:
            self.is_clicking = True
            self.update_status_label(True)
            self.click()

    def stop_clicking(self):
        """停止自动点击流程。"""
        if self.is_clicking:
            self.is_clicking = False
            self.update_status_label(False)

    def check_game_status(self):
        """检查游戏状态，并根据状态控制自动点击的开始或停止。"""
        window = gw.getWindowsWithTitle(self.game_title_name)
        if window and window[0].isActive:
            auto.take_screenshot(crop=(122.0 / 1920, 31.0 / 1080, 98.0 / 1920, 58.0 / 1080))
            for img in self.start_img:
                if auto.find_element(img, "image", 0.9, take_screenshot=False):
                    self.start_clicking()
                    if auto.click_element(self.skip_img, "image", 0.8, crop=(1563.0 / 1920, 45.0 / 1080, 33.0 / 1920, 28.0 / 1080)):
                        auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10)
                    else:
                        auto.click_element(self.select_img, "image", 0.9, crop=(1290.0 / 1920, 442.0 / 1080, 74.0 / 1920, 400.0 / 1080))
                    self.root.after(500, self.check_game_status)
                    return

        self.stop_clicking()

        # 每隔一段时间重新检查游戏状态
        self.root.after(500, self.check_game_status)

    def click(self):
        """执行一次点击操作，并根据状态决定是否继续点击。"""
        if self.is_clicking:
            auto.press_mouse()
            # 短时间后再次执行点击操作
            self.root.after(10, self.click)
