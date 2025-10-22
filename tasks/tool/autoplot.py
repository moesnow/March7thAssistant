from enum import Enum
import tkinter as tk
from tkinter import ttk
from textwrap import dedent
import cv2
import numpy as np
import pygetwindow as gw
from module.automation import auto
from module.logger import log


class ClickMode(Enum):
    Period = "固定间隔"
    Adaptive = "自适应"


class AutoPlot:
    _START_IMGS = [
        "./assets/images/share/plot/start.png",
        "./assets/images/share/plot/start_ps5.png",
        "./assets/images/share/plot/start_xbox.png",
    ]
    _DIALOG_OPTIONS_IMGS = [
        "./assets/images/share/plot/select.png",
        "./assets/images/share/plot/message.png",
        "./assets/images/share/plot/exit.png",
        "./assets/images/share/plot/prev-page.png",
    ]
    _DILATE_KERNEL = cv2.getStructuringElement(cv2.MORPH_RECT, (8, 8))

    def __init__(self, root: tk.Tk, game_title_name: str):
        """初始化 AutoPlot 类的实例。

        参数:
        - root: tkinter 的根窗口实例。
        """
        self.root = root
        self.game_title_name = game_title_name
        self.is_clicking = False
        self.monitor_task_id = None
        self.click_task_id = None
        self.adaptive_last_text_pixels = 0

        self._setup_root()
        self._init_controls()
        self._monitor_loop()

    def _setup_root(self):
        """配置根窗口的基本属性和界面元素。

        参数:
        - root: tkinter 的根窗口实例。
        """
        self.root.title("自动对话")
        self.root.geometry("560x500")
        self.root.iconbitmap("./assets/logo/March7th.ico")

    def _init_controls(self):
        """初始化视图控件。"""
        self.var_auto_skip = tk.BooleanVar(value=True)
        self.var_auto_click_dialog_options = tk.BooleanVar(value=True)
        self.var_dialogue_mode = tk.StringVar(value=ClickMode.Period.value)
        self.var_reading_speed = tk.DoubleVar(value=1.0)
        self.var_adaptive_delay = tk.IntVar(value=10)
        self.var_period_interval = tk.IntVar(value=50)

        # 介绍文本
        intro = dedent(
            """\
                进入剧情页面后自动开始运行
                支持大于等于 1920*1080 的 16:9 分辨率

                • 固定间隔：按固定时间间隔持续点击
                • 自适应：文本显示完成后自动点击"""
        )
        self.intro_label = ttk.Label(self.root, text=intro)
        self.intro_label.pack(pady=(10, 10))

        # 设置选项容器
        settings_frame = ttk.LabelFrame(self.root, text="设置", padding=16)
        settings_frame.pack(pady=10, padx=20, fill="x")
        settings_frame.columnconfigure(1, weight=1)

        # 对话模式
        self.mode_label = ttk.Label(settings_frame, text="对话模式:")
        self.mode_combobox = ttk.Combobox(
            settings_frame,
            textvariable=self.var_dialogue_mode,
            values=[m.value for m in ClickMode],
            state="readonly",
        )
        self.mode_combobox.bind("<<ComboboxSelected>>", self._handle_click_change)

        # 自动跳过剧情
        self.auto_skip_label = ttk.Label(settings_frame, text="自动跳过:")
        self.auto_skip_checkbutton = ttk.Checkbutton(
            settings_frame,
            text="(当出现跳过按钮时自动点击)",
            variable=self.var_auto_skip,
        )

        # 自动选择选项
        self.auto_click_label = ttk.Label(settings_frame, text="自动选择:")
        self.auto_click_checkbutton = ttk.Checkbutton(
            settings_frame,
            text="(自动选择任意对话选项)",
            variable=self.var_auto_click_dialog_options,
        )

        # 自适应模式：阅读延迟
        self.adaptive_delay_label = ttk.Label(settings_frame, text="阅读延迟:")
        self.adaptive_delay_frame = ttk.Frame(settings_frame)
        self.adaptive_delay_spinbox = ttk.Spinbox(
            self.adaptive_delay_frame,
            from_=100,
            to=5000,
            increment=100,
            textvariable=self.var_adaptive_delay,
        )
        adaptive_delay_unit_label = ttk.Label(self.adaptive_delay_frame, text="毫秒")
        self.adaptive_delay_spinbox.pack(side="left")
        adaptive_delay_unit_label.pack(side="left", padx=(8, 0))

        # 固定间隔模式：点击间隔
        self.period_interval_label = ttk.Label(settings_frame, text="点击间隔:")
        self.period_interval_frame = ttk.Frame(settings_frame)
        self.period_interval_spinbox = ttk.Spinbox(
            self.period_interval_frame,
            from_=10,
            to=5000,
            increment=10,
            textvariable=self.var_period_interval,
        )
        period_interval_unit_label = ttk.Label(self.period_interval_frame, text="毫秒")
        self.period_interval_spinbox.pack(side="left")
        period_interval_unit_label.pack(side="left", padx=(8, 0))

        # Grid 布局
        grid_pad = 12
        self.mode_label.grid(row=0, column=0, sticky="w", pady=(0, grid_pad))
        self.mode_combobox.grid(row=0, column=1, columnspan=2, sticky="w", padx=(grid_pad, 0), pady=(0, grid_pad))
        self.auto_skip_label.grid(row=1, column=0, sticky="w", pady=(0, grid_pad))
        self.auto_skip_checkbutton.grid(row=1, column=1, columnspan=2, sticky="w", padx=(grid_pad, 0), pady=(0, grid_pad))
        self.auto_click_label.grid(row=2, column=0, sticky="w", pady=(0, grid_pad))
        self.auto_click_checkbutton.grid(row=2, column=1, columnspan=2, sticky="w", padx=(grid_pad, 0), pady=(0, grid_pad))
        self.adaptive_delay_label.grid(row=3, column=0, sticky="w")
        self.adaptive_delay_frame.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(grid_pad, 0))
        self.period_interval_label.grid(row=4, column=0, sticky="w")
        self.period_interval_frame.grid(row=4, column=1, columnspan=2, sticky="ew", padx=(grid_pad, 0))

        self.status_label = ttk.Label(self.root)
        self.status_label.pack(pady=(0, 10))

        self._update_status_label()
        self._handle_click_change()

    def _handle_click_change(self, event=None):
        """处理对话方式切换事件。"""
        if self.click_task_id:
            self.root.after_cancel(self.click_task_id)
            self.click_task_id = None

        mode = self.var_dialogue_mode.get()

        if mode == ClickMode.Adaptive.value:
            self.adaptive_delay_label.grid()
            self.adaptive_delay_frame.grid()
            self.period_interval_label.grid_remove()
            self.period_interval_frame.grid_remove()
        else:
            self.adaptive_delay_label.grid_remove()
            self.adaptive_delay_frame.grid_remove()
            self.period_interval_label.grid()
            self.period_interval_frame.grid()

    def _update_status_label(self, status: str = "未知", color: str = "red"):
        """更新状态标签的文本和颜色。"""
        self.status_label.config(text=f"自动点击状态：{status}", foreground=color)
        self.root.update()

    def _is_game_window_active(self) -> bool:
        window = gw.getWindowsWithTitle(self.game_title_name)
        return window and window[0].isActive

    def _is_dialog_scene(self) -> bool:
        """检查当前是否处于对话场景。"""
        auto.take_screenshot(crop=(122.0 / 1920, 31.0 / 1080, 98.0 / 1920, 58.0 / 1080))

        for img in self._START_IMGS:
            if auto.find_element(img, "image", 0.9, take_screenshot=False):
                return True

        if auto.find_element("./assets/images/share/plot/hide.png", "image", 0.8, crop=(1801.0 / 1920, 47.0 / 1080, 36.0 / 1920, 25.0 / 1080)):
            return True

        if auto.find_element("./assets/images/share/plot/continue.png", "image", 0.9, crop=(946.0 / 1920, 996.0 / 1080, 28.0 / 1920, 21.0 / 1080)):
            return True

        return False

    def _monitor_loop(self):
        """监控对话场景，并根据场景状态控制对话自动化。"""
        if self._is_game_window_active() and self._is_dialog_scene():
            if not self.is_clicking:
                self.click_task_id = self.root.after(500, self._dialog_loop)
            self.is_clicking = True
        else:
            self.is_clicking = False
            self._update_status_label("未检测到对话场景", "red")
            if self.click_task_id:
                self.root.after_cancel(self.click_task_id)
                self.click_task_id = None
        self.monitor_task_id = self.root.after(500, self._monitor_loop)

    def _dialog_loop(self):
        if not self.is_clicking:
            return

        if not self.var_auto_click_dialog_options.get():
            auto.take_screenshot(crop=(1290.0 / 1920, 442.0 / 1080, 74.0 / 1920, 400.0 / 1080))
            for func_img in self._DIALOG_OPTIONS_IMGS:
                if auto.find_element(func_img, "image", 0.8, take_screenshot=False):
                    log.debug("根据设置，暂停点击以等待用户选择对话选项")
                    self._update_status_label("等待用户选择对话选项", "orange")
                    self.click_task_id = self.root.after(500, self._dialog_loop)
                    return

        self._update_status_label("正在运行中...", "green")

        if self.var_auto_skip.get() and auto.click_element("./assets/images/share/plot/skip.png", "image", 0.8, crop=(1563.0 / 1920, 45.0 / 1080, 33.0 / 1920, 28.0 / 1080)):
            auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10, retry_delay=0.1)
        else:
            auto.click_element("./assets/images/share/plot/select.png", "image", 0.9, crop=(1290.0 / 1920, 442.0 / 1080, 74.0 / 1920, 400.0 / 1080))

        mode = self.var_dialogue_mode.get()
        if mode == ClickMode.Period.value:
            self._period_click()
        else:
            self._adaptive_click()

    def _period_click(self):
        """启动固定间隔点击模式。"""
        auto.press_mouse()
        self.click_task_id = self.root.after(self.var_period_interval.get(), self._dialog_loop)

    def _adaptive_click(self):
        """自适应点击模式。"""
        text_pixels = self._adaptive_count_text_pixels()
        pixel_diff = abs(text_pixels - self.adaptive_last_text_pixels)
        threshold = max(50, text_pixels * 0.01)
        is_finished = pixel_diff < threshold

        log.debug(f"对话状态:{'完成' if is_finished else '加载'} 差异:{pixel_diff}/{threshold}")

        self.adaptive_last_text_pixels = text_pixels

        if is_finished:
            delay = self.var_adaptive_delay.get()
            self.click_task_id = self.root.after(delay, self._adaptive_click_continue)
            log.debug(f"文本显示完成，延迟 {delay} 毫秒后点击")
        else:
            self.click_task_id = self.root.after(50, self._adaptive_click)

    def _adaptive_count_text_pixels(self) -> int:
        """统计文本区域的文本像素数量。

        返回:
        - 文本像素数量
        """
        try:
            screenshot, _, _ = auto.take_screenshot(crop=(240.0 / 1920, 856.0 / 1080, 1440.0 / 1920, 140.0 / 1080))

            if not screenshot:
                return 0

            img_orig = cv2.resize(np.array(screenshot), (360, 35), interpolation=cv2.INTER_LANCZOS4)
            img_gray = cv2.cvtColor(img_orig, cv2.COLOR_BGR2GRAY)
            _, img_binary = cv2.threshold(img_gray, 180, 255, cv2.THRESH_BINARY)
            img_dilated = cv2.dilate(img_binary, self._DILATE_KERNEL, iterations=1)
            white_pixel_count = cv2.countNonZero(img_dilated)

            return white_pixel_count

        except Exception as e:
            log.error(f"统计文本像素失败: {e}")
            return 0

    def _adaptive_click_continue(self):
        """执行点击继续按钮的操作。"""
        log.debug("执行计划的点击，切换到下一个对话文本")

        for _ in range(5):
            if not auto.find_element("./assets/images/share/plot/continue.png", "image", 0.8, crop=(946.0 / 1920, 996.0 / 1080, 28.0 / 1920, 21.0 / 1080)):
                break
            auto.press_mouse()

        self.adaptive_last_text_pixels = 0
        self.click_task_id = self.root.after(500, self._dialog_loop)
