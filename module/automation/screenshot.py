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

    @staticmethod
    def get_main_screen_location():
        if cfg.cloud_game_enable:
            return None, None
        from desktopmagic.screengrab_win32 import getDisplayRects  # 延迟导入，避免非 Windows 平台报错
        rects = getDisplayRects()
        min_x = min([rect[0] for rect in rects])
        min_y = min([rect[1] for rect in rects])
        return -min_x, -min_y

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

            all_screens = cfg.all_screens
            if all_screens:
                offset_x, offset_y = Screenshot.get_main_screen_location()
            else:
                offset_x, offset_y = 0, 0
            import pyautogui
            screenshot = pyautogui.screenshot(region=(
                int(left + width * crop[0] + offset_x),
                int(top + height * crop[1] + offset_y),
                int(width * crop[2]),
                int(height * crop[3])
            ), allScreens=all_screens)

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
