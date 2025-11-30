from module.ocr import ocr
import tkinter as tk
from tkinter import messagebox
from PIL import ImageTk, Image
import pyperclip
import pyautogui
import os
import atexit


class ScreenshotApp:
    def __init__(self, root, screenshot: Image.Image):
        """
        初始化应用界面和功能。
        参数:
        - root: tkinter的根窗口。
        - screenshot: PIL Image对象，表示要显示的截图。
        """
        self.setup_root(root, screenshot)
        atexit.register(ocr.exit_ocr)
        self.setup_canvas()
        self.bind_canvas_events()
        self.setup_buttons()
        self.setup_selection_tools()

    def setup_root(self, root, screenshot: Image.Image):
        """
        配置根窗口的基本属性。
        """
        self.root = root
        self.root.title("游戏截图")
        self.root.iconbitmap("./assets/logo/March7th.ico")
        self.root.geometry(f"{screenshot.width}x{screenshot.height + 60}")
        self.screenshot = screenshot

        self.screen_resolution = pyautogui.size()
        screen_width, screen_height = self.screen_resolution
        if screen_width <= 1920 and screen_height <= 1080:
            # 最大化窗口
            self.root.state('zoomed')
        # 设置窗口始终位于最前面
        self.root.attributes("-topmost", 1)

        # 通过延时恢复原始状态（不再保持在最前面）
        self.root.after(100, self.remove_topmost)
        # 当窗口被用户关闭时，优先执行 OCR 清理，再销毁窗口
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def remove_topmost(self):
        # 取消保持最前面状态
        self.root.attributes("-topmost", 0)

    def setup_canvas(self):
        """
        在根窗口中创建并配置画布用于显示截图。
        """
        self.canvas = tk.Canvas(self.root)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.photo = ImageTk.PhotoImage(master=self.root, image=self.screenshot)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)

    def bind_canvas_events(self):
        """
        绑定画布事件，用于处理鼠标点击和拖动。
        """
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)

    def setup_buttons(self):
        """
        在根窗口中创建操作按钮。
        """
        buttons = [
            ("显示坐标", self.show_coordinate_result),
            ("复制坐标到剪贴板", self.copy_coordinate_result_to_clipboard),
            ("保存完整截图", self.save_full_screenshot),
            ("保存选取截图", self.save_selection_screenshot),
            ("OCR识别选取区域", self.show_ocr_selection)
        ]
        for text, command in buttons:
            tk.Button(self.root, text=text, command=command).pack(side=tk.LEFT, padx=5, pady=5)

    def setup_selection_tools(self):
        """
        初始化用于选取截图区域的工具。
        """
        self.selection_rect = None
        self.start_x = None
        self.start_y = None

    def on_close(self):
        """
        在窗口关闭时调用：先尝试清理 OCR 相关资源，然后销毁窗口。
        使用 try/except 以防清理函数抛出异常导致界面无法关闭。
        """
        try:
            ocr.exit_ocr()
        except Exception:
            pass
        try:
            # 先尝试正常退出主循环
            self.root.destroy()
        except Exception:
            try:
                self.root.quit()
            except Exception:
                pass

    def on_button_press(self, event):
        """
        处理鼠标按下事件，记录开始选择的坐标。
        参数:
        - event: 鼠标事件，包含鼠标的位置。
        """
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)

    def on_mouse_drag(self, event):
        """
        处理鼠标拖动事件，用于绘制选择区域。
        参数:
        - event: 鼠标事件。
        """
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)

        if self.selection_rect:
            self.canvas.coords(self.selection_rect, self.start_x, self.start_y, cur_x, cur_y)
        else:
            self.selection_rect = self.canvas.create_rectangle(
                self.start_x, self.start_y, cur_x, cur_y,
                outline="#f18cb9", width=3
            )

    def get_selection_info(self):
        """
        获取当前选择区域的坐标和尺寸。
        返回:
        - 选择区域的起始x, y坐标，以及宽度和高度。
        """
        if not self.selection_rect:
            return None
        coords = self.canvas.coords(self.selection_rect)
        start_x, start_y, end_x, end_y = coords
        width = abs(end_x - start_x)
        height = abs(end_y - start_y)
        return start_x, start_y, width, height

    def show_coordinate_result(self):
        """
        显示当前选择区域的坐标和尺寸。
        """
        selection_info = self.get_selection_info()
        if selection_info:
            x, y, width, height = selection_info
            result = f"X: {x}, Y: {y}, Width: {width}, Height: {height}"
            messagebox.showinfo("结果", result)
        else:
            messagebox.showinfo("结果", "还没有选择区域呢")

    def copy_coordinate_result_to_clipboard(self):
        """
        将当前选择区域的坐标和尺寸复制到剪贴板。
        """
        selection_info = self.get_selection_info()
        if selection_info:
            x, y, width, height = selection_info
            text = f"crop=({x} / {self.screenshot.width}, {y} / {self.screenshot.height}, {width} / {self.screenshot.width}, {height} / {self.screenshot.height})"
            pyperclip.copy(text)
            messagebox.showinfo("结果", f"{text}\n复制到剪贴板成功")
        else:
            messagebox.showinfo("结果", "还没有选择区域呢")

    def save_full_screenshot(self):
        """
        保存截图到本地文件夹。
        """
        folder_path = "screenshots"
        os.makedirs(folder_path, exist_ok=True)
        screenshot_path = os.path.join(os.path.abspath(folder_path), "screenshot.png")
        self.screenshot.save(screenshot_path)
        os.startfile(os.path.dirname(screenshot_path))
        # messagebox.showinfo("保存截图", f"截图已保存至: {screenshot_path}")

    def save_selection_screenshot(self):
        """
        保存用户选择区域的截图到本地文件夹。
        """
        selection_info = self.get_selection_info()
        if selection_info:
            x, y, width, height = selection_info
            # 使用PIL的crop方法裁剪出选择区域
            cropped_image = self.screenshot.crop((x, y, x + width, y + height))
            folder_path = "screenshots"
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            screenshot_path = os.path.join(os.path.abspath(folder_path), "selection.png")
            cropped_image.save(screenshot_path)
            os.startfile(os.path.dirname(screenshot_path))
            # messagebox.showinfo("保存选区截图", f"选区截图已保存至: {screenshot_path}")
        else:
            messagebox.showinfo("保存选区截图", "还没有选择区域呢")

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
                messagebox.showinfo("OCR识别结果", f"{text}\n\n复制到剪贴板成功")
            else:
                messagebox.showinfo("OCR识别结果", "没有识别出任何内容")
        else:
            messagebox.showinfo("OCR识别结果", "还没有选择区域呢")
