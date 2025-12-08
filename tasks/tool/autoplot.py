
from enum import Enum
import cv2
import numpy as np
import pygetwindow as gw
from module.automation import auto
from module.logger import log
from PyQt5.QtCore import QObject, QTimer


class ClickMode(Enum):
    Period = "period"
    Adaptive = "adaptive"


class AutoPlot(QObject):
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

    def __init__(self, game_title_name: str):
        super().__init__()
        self.game_title_name = game_title_name
        self.is_clicking = False
        self.adaptive_last_text_pixels = 0
        self.is_running = False
        
        # Default configuration
        self.mode = ClickMode.Period
        self.auto_skip = True
        self.auto_click = True
        self.adaptive_delay = 10
        self.period_interval = 50

        self._monitor_timer = QTimer(self)
        self._monitor_timer.timeout.connect(self._monitor_loop)

    def start(self):
        """Start auto plot"""
        if not self.is_running:
            self.is_running = True
            log.info("自动对话已启动")
            self._monitor_timer.start(500)
    
    def stop(self):
        """Stop auto plot"""
        if self.is_running:
            self.is_running = False
            self.is_clicking = False
            log.info("自动对话已停止")
            self._monitor_timer.stop()
    
    def update_options(self, options: dict):
        """Update configuration options"""
        mode_str = options.get('mode', 'period')
        self.mode = ClickMode.Adaptive if mode_str == 'adaptive' else ClickMode.Period
        self.auto_skip = options.get('auto_skip', True)
        self.auto_click = options.get('auto_click', True)
        self.adaptive_delay = options.get('adaptive_delay', 10)
        self.period_interval = options.get('period_interval', 50)
        log.debug(f"自动对话配置已更新: {options}")

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
        if not self.is_running:
            return
            
        if self._is_game_window_active() and self._is_dialog_scene():
            if not self.is_clicking:
                QTimer.singleShot(500, self._dialog_loop)
            self.is_clicking = True
        else:
            self.is_clicking = False

    def _dialog_loop(self):
        if not self.is_clicking or not self.is_running:
            return

        if not self.auto_click:
            auto.take_screenshot(crop=(1290.0 / 1920, 442.0 / 1080, 74.0 / 1920, 400.0 / 1080))
            for func_img in self._DIALOG_OPTIONS_IMGS:
                if auto.find_element(func_img, "image", 0.8, take_screenshot=False):
                    log.debug("根据设置，暂停点击以等待用户选择对话选项")
                    QTimer.singleShot(500, self._dialog_loop)
                    return

        if self.auto_skip and auto.click_element("./assets/images/share/plot/skip.png", "image", 0.8, crop=(1563.0 / 1920, 45.0 / 1080, 33.0 / 1920, 28.0 / 1080)):
            auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10, retry_delay=0.1)
        else:
            auto.click_element("./assets/images/share/plot/select.png", "image", 0.9, crop=(1290.0 / 1920, 442.0 / 1080, 74.0 / 1920, 400.0 / 1080))

        if self.mode == ClickMode.Period:
            self._period_click()
        else:
            self._adaptive_click()

    def _period_click(self):
        auto.press_mouse()
        QTimer.singleShot(self.period_interval, self._dialog_loop)

    def _adaptive_click(self):
        text_pixels = self._adaptive_count_text_pixels()
        pixel_diff = abs(text_pixels - self.adaptive_last_text_pixels)
        threshold = max(50, text_pixels * 0.01)
        is_finished = pixel_diff < threshold

        log.debug(f"对话状态:{'完成' if is_finished else '加载'} 差异:{pixel_diff}/{threshold}")

        self.adaptive_last_text_pixels = text_pixels

        if is_finished:
            delay = self.adaptive_delay
            QTimer.singleShot(delay, self._adaptive_click_continue)
            log.debug(f"文本显示完成，延迟 {delay} 毫秒后点击")
        else:
            QTimer.singleShot(50, self._adaptive_click)

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
        log.debug("执行计划的点击，切换到下一个对话文本")
        for _ in range(5):
            if not auto.find_element("./assets/images/share/plot/continue.png", "image", 0.8, crop=(946.0 / 1920, 996.0 / 1080, 28.0 / 1920, 21.0 / 1080)):
                break
            auto.press_mouse()
        self.adaptive_last_text_pixels = 0
        QTimer.singleShot(500, self._dialog_loop)
