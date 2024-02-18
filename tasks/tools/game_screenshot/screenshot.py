from managers.ocr_manager import ocr
import tkinter as tk
from tkinter import messagebox
from PIL import ImageTk
import os


class ScreenshotApp:
    def __init__(self, root, screenshot):
        self.root = root
        self.root.title("游戏截图")
        self.root.iconbitmap("./assets/logo/March7th.ico")

        self.canvas = tk.Canvas(root)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.screenshot = screenshot
        self.photo = ImageTk.PhotoImage(self.screenshot)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)

        self.selection_rect = None
        self.start_x = None
        self.start_y = None

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)

        # 设置窗口大小
        self.root.geometry(f"{self.screenshot.width}x{self.screenshot.height}")

        self.show_result_button = tk.Button(root, text="显示坐标", command=self.show_coordinate_result)
        self.show_result_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.copy_to_clipboard_button = tk.Button(root, text="复制坐标到剪贴板", command=self.copy_coordinate_result_to_clipboard)
        self.copy_to_clipboard_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.save_screenshot_button = tk.Button(root, text="保存完整截图", command=self.save_full_screenshot)
        self.save_screenshot_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.save_selection_button = tk.Button(root, text="保存选取截图", command=self.save_selection_screenshot)
        self.save_selection_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.ocr_selection_button = tk.Button(root, text="OCR识别选取区域", command=self.show_ocr_selection)
        self.ocr_selection_button.pack(side=tk.LEFT, padx=5, pady=5)

    def on_button_press(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)

    def on_mouse_drag(self, event):
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
        start_x, start_y, end_x, end_y = self.canvas.coords(self.selection_rect)
        width = abs(end_x - start_x)
        height = abs(end_y - start_y)
        return start_x, start_y, width, height

    def copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

    def show_coordinate_result(self):
        if self.selection_rect:
            x, y, width, height = self.get_selection_info()
            result = f"X: {x}, Y: {y}, Width: {width}, Height: {height}"
            messagebox.showinfo("结果", result)
        else:
            messagebox.showinfo("结果", "还没有选择区域呢")

    def copy_coordinate_result_to_clipboard(self):
        if self.selection_rect:
            x, y, width, height = self.get_selection_info()
            text = f"crop=({x} / {self.screenshot.width}, {y} / {self.screenshot.height}, {width} / {self.screenshot.width}, {height} / {self.screenshot.height})"
            self.copy_to_clipboard(text)
            result = f"{text}\n复制到剪贴板成功"
            messagebox.showinfo("结果", result)
        else:
            messagebox.showinfo("结果", "还没有选择区域呢")

    def save_full_screenshot(self):
        if not os.path.exists("screenshots"):
            os.makedirs("screenshots")
        screenshot_path = os.path.abspath(r"screenshots\screenshot.png")
        self.screenshot.save(screenshot_path)
        os.startfile(os.path.dirname(screenshot_path))

    def save_selection_screenshot(self):
        if self.selection_rect:
            x, y, width, height = self.get_selection_info()
            if not os.path.exists("screenshots"):
                os.makedirs("screenshots")
            screenshot_path = os.path.abspath(r"screenshots\selection.png")
            self.screenshot.crop((x, y, x + width, y + height)).save(screenshot_path)
            os.startfile(os.path.dirname(screenshot_path))
        else:
            messagebox.showinfo("结果", "还没有选择区域呢")

    def show_ocr_selection(self):
        if self.selection_rect:
            x, y, width, height = self.get_selection_info()
            result = ocr.recognize_multi_lines(self.screenshot.crop((x, y, x + width, y + height)))
            if result:
                text = ""
                Flag = True
                for box in result:
                    if Flag:
                        text = text + box[1][0]
                        Flag = False
                    else:
                        text = text + "\n" + box[1][0]
                self.copy_to_clipboard(text)
                messagebox.showinfo("结果", text + "\n\n复制到剪贴板成功")
            else:
                messagebox.showinfo("结果", "没有识别出任何内容")
        else:
            messagebox.showinfo("结果", "还没有选择区域呢")
