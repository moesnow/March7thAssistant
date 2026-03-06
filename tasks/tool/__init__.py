from typing import Literal
from module.config import cfg
from .screenshot import ScreenshotApp
from .autoplot import AutoPlot
from module.game import get_game_controller
from module.automation.screenshot import Screenshot
from module.logger import log
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import QApplication
from qfluentwidgets import InfoBar, InfoBarPosition
from module.localization import tr
import threading
import time
import os
from PIL import Image


class ScreenshotSignals(QObject):
    """用于线程间通信的信号"""
    show_window = Signal(object)  # 传递截图数据
    show_error = Signal(str)  # 传递错误信息


class ToolManager:
    def __init__(self):
        self.screenshot_data = None
        self.screenshot_error_message = ""
        self.screenshot_window = None
        self.signals = ScreenshotSignals()
        # 连接信号到槽函数
        self.signals.show_window.connect(self._show_screenshot_window_slot)
        self.signals.show_error.connect(self._show_error_dialog_slot)
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
            self.screenshot_error_message = ""
            log.info("开始捕获图像...")
            # if not cfg.cloud_game_enable:
            #     game = get_game_controller()
            #     if not game.switch_to_game():
            #         log.error("游戏尚未启动")
            #         return False
            #     time.sleep(0.5)  # 等待窗口切换

            log.debug("开始截图...")
            result = Screenshot.take_screenshot(cfg.game_title_name)
            if result:
                log.debug(f"截图成功，图像尺寸: {result[0].size}")
                self.screenshot_data = result[0]
                return True
            else:
                log.error("截图失败")
                self.screenshot_error_message = tr("无法获取游戏窗口截图，请确认游戏窗口已打开")
                return False
        except Exception as e:
            log.error(f"run_screenshot 发生异常: {e}")
            import traceback
            log.error(traceback.format_exc())
            self.screenshot_error_message = f"截图时发生异常：{e}"
            return False

    def run_screenshot_from_file(self, file_path: str):
        """从本地文件加载图像"""
        try:
            self.screenshot_error_message = ""

            if not file_path or not os.path.exists(file_path):
                self.screenshot_error_message = tr("图片文件不存在，请重新选择")
                return False

            with Image.open(file_path) as image:
                # 统一转为 RGB，避免后续 QImage 转换时因模式不一致报错
                self.screenshot_data = image.convert("RGB").copy()

            log.debug(f"加载本地图片成功，图像尺寸: {self.screenshot_data.size}")
            return True
        except Exception as e:
            log.error(f"run_screenshot_from_file 发生异常: {e}")
            import traceback
            log.error(traceback.format_exc())
            self.screenshot_error_message = f"读取图片时发生异常：{e}"
            return False

    def _show_screenshot_window_slot(self, screenshot_image):
        """槽函数：显示截图窗口（自动在主线程中调用）"""
        try:
            self.screenshot_window = ScreenshotApp(screenshot_image)

            # 检查屏幕分辨率决定是否最大化
            import pyautogui
            screen_resolution = pyautogui.size()
            screen_width, screen_height = screen_resolution
            if screen_width <= 1920 and screen_height <= 1080:
                log.debug("最大化显示窗口")
                self.screenshot_window.showMaximized()
            else:
                log.debug("正常显示窗口")
                self.screenshot_window.show()

            log.debug("截图窗口已显示")
        except Exception as e:
            log.error(f"_show_screenshot_window_slot 发生异常: {e}")
            import traceback
            log.error(traceback.format_exc())

    def show_screenshot_window(self):
        """触发显示截图窗口的信号（可从任何线程调用）"""
        self.signals.show_window.emit(self.screenshot_data)

    def _show_error_dialog_slot(self, message: str):
        """槽函数：显示错误提示（自动在主线程中调用）"""
        try:
            InfoBar.error(
                title=tr('截图失败(╥╯﹏╰╥)'),
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=QApplication.activeWindow()
            )
        except Exception as e:
            log.error(f"_show_error_dialog_slot 发生异常: {e}")

    def show_error_dialog(self, message: str):
        """触发显示错误弹窗的信号（可从任何线程调用）"""
        self.signals.show_error.emit(message)

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
                _tool_manager.show_screenshot_window()
            else:
                # 截图失败后，通过信号在主线程中显示错误弹窗
                _tool_manager.show_error_dialog(
                    _tool_manager.screenshot_error_message or "截图失败，请稍后重试。"
                )

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


def start_screenshot_from_file(file_path: str):
    """从本地图片启动截图工具"""

    def load_and_show():
        if _tool_manager.run_screenshot_from_file(file_path):
            _tool_manager.show_screenshot_window()
        else:
            _tool_manager.show_error_dialog(
                _tool_manager.screenshot_error_message or "读取图片失败，请稍后重试。"
            )

    load_thread = threading.Thread(target=load_and_show, daemon=True)
    load_thread.start()
