from module.ocr import ocr
from PySide6.QtWidgets import QMainWindow, QLabel, QPushButton, QHBoxLayout, QWidget, QMessageBox, QScrollArea, QApplication, QStyle
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QPainter, QPen, QImage, QColor
from PIL import Image
import pyperclip
import os
import sys
import atexit


class ScreenshotApp(QMainWindow):
    def __init__(self, screenshot: Image.Image):
        """
        初始化应用界面和功能。
        参数:
        - screenshot: PIL Image对象，表示要显示的截图。
        """
        try:
            from module.logger import log
            log.info("ScreenshotApp.__init__ 开始")
            super().__init__()
            log.debug("QMainWindow 初始化完成")
            self.screenshot = screenshot
            log.debug(f"截图尺寸: {screenshot.size}")
            atexit.register(ocr.exit_ocr)

            # 初始化选择区域工具
            self.selection_rect = None
            self.start_x = None
            self.start_y = None
            self.current_x = None
            self.current_y = None
            self.is_drawing = False
            self.need_maximize = False  # 是否需要最大化窗口

            log.debug("开始设置 UI...")
            self.setup_ui()
            log.info("ScreenshotApp.__init__ 完成")
        except Exception as e:
            from module.logger import log
            log.error(f"ScreenshotApp.__init__ 发生异常: {e}")
            import traceback
            log.error(traceback.format_exc())
            raise

    def setup_ui(self):
        """
        配置窗口和UI元素。
        """
        try:
            from module.logger import log
            log.info("setup_ui 开始")
            self.setWindowTitle("游戏截图")
            log.debug("设置窗口标题完成")
            self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon))
            log.debug("设置窗口图标完成")

            # 获取屏幕的 DPI 缩放因子
            screen = QApplication.primaryScreen()
            self.dpi_scale = screen.devicePixelRatio() if screen else 1.0
            log.debug(f"DPI 缩放因子: {self.dpi_scale}")

            # 转换PIL Image到QPixmap
            log.debug("开始转换 PIL Image 到 QPixmap...")
            img_data = self.screenshot.tobytes("raw", "RGB")
            log.debug(f"图像数据长度: {len(img_data)}")
            qimage = QImage(img_data, self.screenshot.width, self.screenshot.height,
                            self.screenshot.width * 3, QImage.Format.Format_RGB888)
            log.debug(f"QImage 创建成功，尺寸: {qimage.width()}x{qimage.height()}")

            # 计算逻辑尺寸（缩小后在高DPI下显示为原始大小）
            self.logical_width = int(self.screenshot.width / self.dpi_scale)
            self.logical_height = int(self.screenshot.height / self.dpi_scale)
            log.debug(f"逻辑尺寸: {self.logical_width}x{self.logical_height}")

            # 将图像缩放到逻辑尺寸
            original_pixmap = QPixmap.fromImage(qimage)
            self.pixmap = original_pixmap.scaled(
                self.logical_width, self.logical_height,
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            log.debug(f"QPixmap 缩放后尺寸: {self.pixmap.width()}x{self.pixmap.height()}")
        except Exception as e:
            from module.logger import log
            log.error(f"setup_ui 转换图像时发生异常: {e}")
            import traceback
            log.error(traceback.format_exc())
            raise

        # 创建中心部件和布局
        try:
            log.debug("创建中心部件和布局...")
            central_widget = QWidget()
            self.setCentralWidget(central_widget)

            # 创建垂直布局
            from PySide6.QtWidgets import QVBoxLayout
            main_layout = QVBoxLayout(central_widget)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(0)
            log.debug("布局创建完成")

            # 创建滚动区域
            log.debug("创建滚动区域...")
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(False)  # 不自动调整大小
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

            # 创建画布标签
            log.debug("创建画布标签...")
            self.canvas_label = QLabel()
            self.canvas_label.setPixmap(self.pixmap)
            self.canvas_label.setScaledContents(False)  # 不缩放内容
            self.canvas_label.setMouseTracking(True)
            self.canvas_label.mousePressEvent = self.on_mouse_press
            self.canvas_label.mouseMoveEvent = self.on_mouse_move
            self.canvas_label.mouseReleaseEvent = self.on_mouse_release

            # 将标签放入滚动区域
            scroll_area.setWidget(self.canvas_label)
            main_layout.addWidget(scroll_area)
            log.debug("画布标签创建完成")

            # 创建按钮布局
            log.debug("创建按钮...")
            button_layout = QHBoxLayout()
            button_layout.setContentsMargins(5, 5, 5, 5)
            button_layout.setSpacing(5)

            # 创建按钮
            buttons_config = [
                ("显示坐标", self.show_coordinate_result),
                ("复制坐标到剪贴板", self.copy_coordinate_result_to_clipboard),
                ("保存完整截图", self.save_full_screenshot),
                ("保存选取截图", self.save_selection_screenshot),
                ("OCR识别选取区域", self.show_ocr_selection)
            ]

            for text, slot in buttons_config:
                btn = QPushButton(text)
                btn.clicked.connect(slot)
                button_layout.addWidget(btn)

            button_layout.addStretch()
            main_layout.addLayout(button_layout)
            log.debug("按钮创建完成")

            # 按钮区域高度
            button_area_height = 40

            # 设置窗口大小
            log.debug("设置窗口大小和位置...")

            # 获取可用屏幕区域（排除任务栏等）
            screen = QApplication.primaryScreen()
            available_geometry = screen.availableGeometry()
            available_width = available_geometry.width()
            available_height = available_geometry.height()
            log.debug(f"可用屏幕区域: {available_width}x{available_height}")
            log.debug(f"截图逻辑尺寸: {self.logical_width}x{self.logical_height}")

            # 计算窗口所需的尺寸（包括边框等额外空间）
            window_frame_width = 20  # 窗口边框宽度估计
            window_frame_height = 40  # 窗口标题栏高度估计
            needed_width = self.logical_width + window_frame_width
            needed_height = self.logical_height + button_area_height + window_frame_height

            # 判断截图是否能在屏幕内完整显示
            if needed_width <= available_width and needed_height <= available_height:
                # 截图不大，可以完整显示，调整窗口大小使截图刚好显示全
                log.debug("截图可以完整显示，调整窗口大小")
                # 额外增加一些像素避免滚动条出现
                extra_padding = 4
                window_width = self.logical_width + extra_padding
                window_height = self.logical_height + button_area_height + extra_padding
                # 计算居中位置
                pos_x = (available_width - window_width) // 2
                pos_y = (available_height - window_height) // 2
                self.setGeometry(pos_x, pos_y, window_width, window_height)
            else:
                # 截图太大，使用最大化或设置为可用区域大小
                log.info("截图太大，将窗口设置为最大化")
                self.setGeometry(100, 100, self.logical_width, self.logical_height + button_area_height)
                self.need_maximize = True  # 标记需要最大化，在外部调用

            # 设置窗口置顶标志（不在这里显示窗口）
            log.debug("设置窗口置顶标志...")
            # 修复关闭窗口按钮无法点击的问题
            self.setWindowFlags(
                Qt.WindowType.Window |
                Qt.WindowType.WindowCloseButtonHint |
                Qt.WindowType.WindowMinimizeButtonHint |
                Qt.WindowType.WindowMaximizeButtonHint |
                Qt.WindowType.WindowStaysOnTopHint
            )
            # 使用定时器来移除置顶
            QTimer.singleShot(100, self.remove_topmost)
            log.info("setup_ui 完成")
        except Exception as e:
            log.error(f"setup_ui 创建UI时发生异常: {e}")
            import traceback
            log.error(traceback.format_exc())
            raise

    def remove_topmost(self):
        """取消保持最前面状态"""
        # 修复关闭窗口按钮无法点击的问题
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint
        )
        self.show()

    def closeEvent(self, event):
        """
        在窗口关闭时调用：先尝试清理 OCR 相关资源。
        """
        try:
            ocr.exit_ocr()
        except Exception:
            pass
        event.accept()

    def on_mouse_press(self, event):
        """
        处理鼠标按下事件，记录开始选择的坐标。
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_x = event.x()
            self.start_y = event.y()
            self.current_x = event.x()
            self.current_y = event.y()
            self.is_drawing = True

    def on_mouse_move(self, event):
        """
        处理鼠标移动事件，用于绘制选择区域。
        """
        if self.is_drawing:
            self.current_x = event.x()
            self.current_y = event.y()
            self.update_canvas()

    def on_mouse_release(self, event):
        """
        处理鼠标释放事件。
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing = False
            self.current_x = event.x()
            self.current_y = event.y()
            self.update_canvas()

    def update_canvas(self):
        """
        更新画布，重绘截图和选择框。
        """
        if self.start_x is not None and self.current_x is not None:
            # 创建新的QPixmap并绘制
            new_pixmap = self.pixmap.copy()
            painter = QPainter(new_pixmap)

            # 设置画笔 - 使用 QColor 创建自定义颜色
            pen = QPen(QColor(0xf1, 0x8c, 0xb9))  # RGB格式
            pen.setWidth(3)
            painter.setPen(pen)

            # 绘制矩形
            x = min(self.start_x, self.current_x)
            y = min(self.start_y, self.current_y)
            width = abs(self.current_x - self.start_x)
            height = abs(self.current_y - self.start_y)
            painter.drawRect(x, y, width, height)

            painter.end()
            self.canvas_label.setPixmap(new_pixmap)

    def get_selection_info(self):
        """
        获取当前选择区域的坐标和尺寸（转换为原始截图的像素坐标）。
        返回:
        - 选择区域的起始x, y坐标，以及宽度和高度（原始像素坐标）。
        """
        if self.start_x is None or self.current_x is None:
            return None

        # 逻辑坐标（缩放后的坐标）
        logical_x = min(self.start_x, self.current_x)
        logical_y = min(self.start_y, self.current_y)
        logical_width = abs(self.current_x - self.start_x)
        logical_height = abs(self.current_y - self.start_y)

        if logical_width == 0 or logical_height == 0:
            return None

        # 转换为原始截图的像素坐标
        x = int(logical_x * self.dpi_scale)
        y = int(logical_y * self.dpi_scale)
        width = int(logical_width * self.dpi_scale)
        height = int(logical_height * self.dpi_scale)

        return x, y, width, height

    def show_coordinate_result(self):
        """
        显示当前选择区域的坐标和尺寸。
        """
        selection_info = self.get_selection_info()
        if selection_info:
            x, y, width, height = selection_info
            result = f"X: {x}, Y: {y}, Width: {width}, Height: {height}"
            QMessageBox.information(self, "结果", result)
        else:
            QMessageBox.information(self, "结果", "还没有选择区域呢")

    def copy_coordinate_result_to_clipboard(self):
        """
        将当前选择区域的坐标和尺寸复制到剪贴板。
        """
        selection_info = self.get_selection_info()
        if selection_info:
            x, y, width, height = selection_info
            text = f"({x} / {self.screenshot.width}, {y} / {self.screenshot.height}, {width} / {self.screenshot.width}, {height} / {self.screenshot.height})"
            pyperclip.copy(text)
            QMessageBox.information(self, "结果", f"{text}\n复制到剪贴板成功")
        else:
            QMessageBox.information(self, "结果", "还没有选择区域呢")

    def save_full_screenshot(self):
        """
        保存截图到本地文件夹，文件名带时间戳。
        """
        import datetime
        folder_path = "screenshots"
        os.makedirs(folder_path, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = os.path.join(os.path.abspath(folder_path), f"screenshot_{timestamp}.png")
        self.screenshot.save(screenshot_path)
        self._start_file(os.path.dirname(screenshot_path))

    def save_selection_screenshot(self):
        """
        保存用户选择区域的截图到本地文件夹，文件名带时间戳。
        """
        import datetime
        selection_info = self.get_selection_info()
        if selection_info:
            x, y, width, height = selection_info
            # 使用PIL的crop方法裁剪出选择区域
            cropped_image = self.screenshot.crop((x, y, x + width, y + height))
            folder_path = "screenshots"
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join(os.path.abspath(folder_path), f"selection_{timestamp}.png")
            cropped_image.save(screenshot_path)
            self._start_file(os.path.dirname(screenshot_path))
        else:
            QMessageBox.information(self, "保存选区截图", "还没有选择区域呢")

    def format_ocr_result(self, result):
        """
        格式化OCR识别的结果。

        Args:
            result: OCR识别的原始结果列表，每个元素包含识别的文本和位置信息。

        Returns:
            格式化后的文本字符串，每行文本之间用换行符分隔。
        """
        # 使用列表推导式和join方法将识别结果转换成字符串，每行之间用换行符分隔
        text_lines = [box[1][0] for box in result]
        formatted_text = "\n".join(text_lines)
        return formatted_text

    def show_ocr_selection(self):
        """
        对用户选择的截图区域进行OCR识别，并显示识别结果。
        """
        selection_info = self.get_selection_info()
        if selection_info:
            x, y, width, height = selection_info
            cropped_image = self.screenshot.crop((x, y, x + width, y + height))  # 裁剪选中区域
            result = ocr.recognize_multi_lines(cropped_image)  # 进行OCR识别
            if result:
                # 如果识别出结果，处理并显示结果
                text = self.format_ocr_result(result)  # 格式化OCR识别的结果
                pyperclip.copy(text)  # 将结果复制到剪贴板
                QMessageBox.information(self, "OCR识别结果", f"{text}\n\n复制到剪贴板成功")
            else:
                QMessageBox.information(self, "OCR识别结果", "没有识别出任何内容")
        else:
            QMessageBox.information(self, "OCR识别结果", "还没有选择区域呢")

    def _start_file(self, path):
        if sys.platform == 'win32':
            os.startfile(path)
        elif sys.platform == 'darwin':
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
