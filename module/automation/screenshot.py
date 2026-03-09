from io import BytesIO
from PIL import Image
from module.config import cfg


class Screenshot:
    @staticmethod
    def is_application_fullscreen(window):
        if cfg.cloud_game_enable:
            return True
        import pyautogui
        screen_width, screen_height = pyautogui.size()
        return (window.width, window.height) == (screen_width, screen_height)

    @staticmethod
    def get_window_real_resolution(window):
        if cfg.cloud_game_enable:
            return 1920, 1080
        import win32gui  # 延迟导入，避免非 Windows 平台报错
        left, top, right, bottom = win32gui.GetClientRect(window._hWnd)
        return right - left, bottom - top

    @staticmethod
    def get_window_region(window):
        if cfg.cloud_game_enable:
            return (0, 0, 1920, 1080)
        if Screenshot.is_application_fullscreen(window):
            return (window.left, window.top, window.width, window.height)
        else:
            real_width, real_height = Screenshot.get_window_real_resolution(window)
            other_border = (window.width - real_width) // 2
            up_border = window.height - real_height - other_border
            return (window.left + other_border, window.top + up_border, window.width - other_border - other_border, window.height - up_border - other_border)

    @staticmethod
    def get_window(title):
        if cfg.cloud_game_enable:
            return False  # TODO
        import pyautogui
        windows = pyautogui.getWindowsWithTitle(title)
        if windows:
            for window in windows:
                if window.title == title:
                    return window
        return False

    # @staticmethod
    # def get_virtual_screen_offset():
    #     if cfg.cloud_game_enable:
    #         return None, None
    #     from desktopmagic.screengrab_win32 import getDisplayRects  # 延迟导入，避免非 Windows 平台报错
    #     rects = getDisplayRects()
    #     min_x = min([rect[0] for rect in rects])
    #     min_y = min([rect[1] for rect in rects])
    #     return -min_x, -min_y

    @staticmethod
    def capture_screen_with_mss(region):
        import mss

        with mss.mss() as sct:
            screenshot = sct.grab(region)
            return Image.frombytes('RGB', screenshot.size, screenshot.rgb)

    @staticmethod
    def capture_window_background(hwnd, region, crop_params, offset=(0, 0)):
        """
        后台截取指定窗口，不会包含覆盖在其上的其他窗口（如浮窗）
        crop_params: (left_ratio, top_ratio, width_ratio, height_ratio)
        offset: (offset_x, offset_y)
        """
        import win32gui
        import win32ui
        import win32con
        from PIL import Image

        # 获取窗口坐标
        # left, top, right, bot = win32gui.GetWindowRect(hwnd)
        left, top, width, height = region

        # 创建设备上下文
        hwndDC = win32gui.GetWindowDC(hwnd)
        mfcDC = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()

        # 创建位图对象
        saveBitMap = win32ui.CreateBitmap()
        saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
        saveDC.SelectObject(saveBitMap)

        # 使用 PrintWindow 截取后台内容
        win32gui.SendMessage(hwnd, win32con.WM_PAINT, 0, 0)  # 触发重绘
        import ctypes
        # 0	默认模式，抓取整个窗口（含边框）
        # 1	只抓取客户区，不含标题栏
        # 2	强制完整渲染（部分游戏需要这个标志）
        # 3	强制渲染 + 只抓客户区
        result = ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)

        # 转换为 PIL 图像
        bmpinfo = saveBitMap.GetInfo()
        bmpstr = saveBitMap.GetBitmapBits(True)
        img = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRX', 0, 1)

        # 清理内存
        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwndDC)

        if result != 1:
            return None  # 截图失败

        # 执行原来的 crop 逻辑
        crop_left = int(width * crop_params[0] + offset[0])
        crop_top = int(height * crop_params[1] + offset[1])
        crop_width = int(width * crop_params[2])
        crop_height = int(height * crop_params[3])

        return img.crop((crop_left, crop_top, crop_left + crop_width, crop_top + crop_height))

    @staticmethod
    def take_screenshot(title, crop=(0, 0, 1, 1)):
        if cfg.cloud_game_enable:
            from module.game import cloud_game
            screenshot = Image.open(BytesIO(cloud_game.take_screenshot()))
            width, height = screenshot.size

            left = int(width * crop[0])
            top = int(height * crop[1])
            crop_width = int(width * crop[2])
            crop_height = int(height * crop[3])

            screenshot = screenshot.crop((left, top, left + crop_width, top + crop_height))

            # Selenium 截图分辨率一般就是浏览器窗口实际像素，所以 scale_factor 默认为 1
            screenshot_scale_factor = 1

            screenshot_pos = (left, top, crop_width, crop_height)

            return screenshot, screenshot_pos, screenshot_scale_factor

        window = Screenshot.get_window(title)
        if window:
            left, top, width, height = Screenshot.get_window_region(window)

            screenshot = None

            if cfg.use_background_screenshot:
                try:
                    screenshot = Screenshot.capture_window_background(window._hWnd, (left, top, width, height), crop)
                except Exception:
                    screenshot = None

            if screenshot is None:
                # import pyautogui

                # all_screens = cfg.all_screens
                # if all_screens:
                #     offset_x, offset_y = Screenshot.get_virtual_screen_offset()
                # else:
                #     offset_x, offset_y = 0, 0

                # screenshot = pyautogui.screenshot(region=(
                #     int(left + width * crop[0] + offset_x),
                #     int(top + height * crop[1] + offset_y),
                #     int(width * crop[2]),
                #     int(height * crop[3])
                # ), allScreens=all_screens)

                capture_left = int(left + width * crop[0])
                capture_top = int(top + height * crop[1])
                capture_width = int(width * crop[2])
                capture_height = int(height * crop[3])

                monitor = {
                    "left": capture_left,
                    "top": capture_top,
                    "width": capture_width,
                    "height": capture_height
                }
                try:
                    screenshot = Screenshot.capture_screen_with_mss(monitor)
                except Exception:
                    return False

            real_width, _ = Screenshot.get_window_real_resolution(window)
            if real_width > 1920:
                screenshot_scale_factor = 1920 / real_width
                screenshot = screenshot.resize((int(1920 * crop[2]), int(1080 * crop[3])))
            else:
                screenshot_scale_factor = 1

            screenshot_pos = (
                int(left + width * crop[0]),
                int(top + height * crop[1]),
                int(width * crop[2] * screenshot_scale_factor),
                int(height * crop[3] * screenshot_scale_factor)
            )

            return screenshot, screenshot_pos, screenshot_scale_factor

        return False
