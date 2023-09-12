import pyautogui


class Screenshot:
    @staticmethod
    def is_application_fullscreen(window):
        screen_width, screen_height = pyautogui.size()
        return (window.width, window.height) == (screen_width, screen_height)

    @staticmethod
    def get_window_region(window):
        # 去除边框
        other_border = (window.width - 1920) // 2
        up_border = window.height - 1080 - other_border

        if Screenshot.is_application_fullscreen(window):
            return (window.left, window.top, window.width, window.height)
        else:
            return (window.left + other_border, window.top + up_border, window.width -
                    other_border - other_border, window.height - up_border - other_border)

    @staticmethod
    def get_window(title):
        windows = pyautogui.getWindowsWithTitle(title)
        if windows:
            window = windows[0]
            return window
        return False

    @staticmethod
    def take_screenshot(title, crop=(0, 0, 0, 0)):
        window = Screenshot.get_window(title)
        if window:
            if crop == (0, 0, 0, 0):
                screenshot_pos = Screenshot.get_window_region(window)
            else:
                left, top, width, height = Screenshot.get_window_region(window)
                screenshot_pos = left + width * crop[0], top + height * crop[1], width * crop[2], height * crop[3]

            screenshot = pyautogui.screenshot(region=screenshot_pos)
            return screenshot, screenshot_pos

        return False
