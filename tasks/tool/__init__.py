from typing import Literal
from module.config import cfg
from .screenshot import ScreenshotApp
from .autoplot import AutoPlot
from module.game import get_game_controller
from module.automation.screenshot import Screenshot
from module.logger import log
from PySide6.QtCore import QObject, Signal
import threading
import time


class ScreenshotSignals(QObject):
    """用于线程间通信的信号"""
    show_window = Signal(object)  # 传递截图数据


class ToolManager:
    def __init__(self):
        self.screenshot_data = None
        self.screenshot_window = None
        self.signals = ScreenshotSignals()
        # 连接信号到槽函数
        self.signals.show_window.connect(self._show_screenshot_window_slot)
        # AutoPlot instance
        self.autoplot_instance = None

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
        try:
            log.info("开始捕获图像...")
            if not cfg.cloud_game_enable:
                game = get_game_controller()
                if not game.switch_to_game():
                    log.error("游戏尚未启动")
                    return False
                time.sleep(0.5)  # 等待窗口切换

            log.info("开始截图...")
            result = Screenshot.take_screenshot(cfg.game_title_name)
            if result:
                log.info(f"截图成功，图像尺寸: {result[0].size}")
                self.screenshot_data = result[0]
                return True
            else:
                log.error("截图失败")
                return False
        except Exception as e:
            log.error(f"run_screenshot 发生异常: {e}")
            import traceback
            log.error(traceback.format_exc())
            return False

    def _show_screenshot_window_slot(self, screenshot_image):
        """槽函数：显示截图窗口（自动在主线程中调用）"""
        try:
            log.info("正在创建 ScreenshotApp 窗口...")
            self.screenshot_window = ScreenshotApp(screenshot_image)

            # 检查屏幕分辨率决定是否最大化
            import pyautogui
            screen_resolution = pyautogui.size()
            screen_width, screen_height = screen_resolution
            if screen_width <= 1920 and screen_height <= 1080:
                log.info("最大化显示窗口")
                self.screenshot_window.showMaximized()
            else:
                log.info("正常显示窗口")
                self.screenshot_window.show()

            log.info("截图窗口已显示")
        except Exception as e:
            log.error(f"_show_screenshot_window_slot 发生异常: {e}")
            import traceback
            log.error(traceback.format_exc())

    def show_screenshot_window(self):
        """触发显示截图窗口的信号（可从任何线程调用）"""
        log.info("发送显示窗口信号...")
        self.signals.show_window.emit(self.screenshot_data)

    def get_autoplot_instance(self):
        """获取或创建AutoPlot实例"""
        if self.autoplot_instance is None:
            self.autoplot_instance = AutoPlot(cfg.game_title_name)
        return self.autoplot_instance

    def run_plot(self):
        """自动对话（后台运行，无窗口）"""
        instance = self.get_autoplot_instance()
        instance.start()

    def stop_plot(self):
        """停止自动对话"""
        if self.autoplot_instance is not None:
            self.autoplot_instance.stop()

    def update_plot_options(self, options: dict):
        """更新自动对话配置"""
        instance = self.get_autoplot_instance()
        instance.update_options(options)


# 全局工具管理器实例
_tool_manager = ToolManager()


def start(tool: Literal["screenshot", "plot"]):
    """
    启动工具管理器的方法。
    :param tool: 启动工具，可以是'screenshot'或'plot'。
    """
    if tool == "screenshot":
        # 在后台线程中执行截图
        def capture_and_show():
            if _tool_manager.run_screenshot():
                # 截图成功后，通过信号在主线程中显示窗口
                log.info("截图完成，准备在主线程显示窗口...")
                _tool_manager.show_screenshot_window()

        # 在后台线程执行截图，不阻塞主线程
        capture_thread = threading.Thread(target=capture_and_show, daemon=True)
        capture_thread.start()
    elif tool == "plot":
        # 直接主线程调用窗口
        _tool_manager.run_plot()


def stop_plot():
    """停止自动对话"""
    _tool_manager.stop_plot()


def update_plot_options(options: dict):
    """更新自动对话配置"""
    _tool_manager.update_plot_options(options)
