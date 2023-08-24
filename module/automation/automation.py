import cv2
import time
import pyautogui
import numpy as np
from managers.ocr_manager import ocr
from managers.logger_manager import logger
from managers.translate_manager import _


class Automation:
    _instance = None

    def __new__(cls, window_title):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.window_title = window_title
            cls._instance.screenshot = None
        return cls._instance

    def mouse_click(self, x, y):
        try:
            pyautogui.click(x, y)
            logger.debug(_("点击 ({x}, {y})").format(x=x, y=y))
            # logger.debug(_("mouse clicked at ({x}, {y})").format(x=x, y=y))
        except Exception as e:
            logger.error(_("点击出错：{e}").format(e=e))
            # logger.error(_("Error clicking mouse: {e}").format(e=e))

    def mouse_scroll(self, count, direction=-1):
        for i in range(count):
            pyautogui.scroll(direction)
        logger.debug(_("滚动 {x} 次").format(x=count * direction))
        # logger.debug(_("mouse scrolled {x} times").format(x=count*direction))
        # time.sleep(1)

    def press_key(self, key, wait_time=0.2):
        try:
            pyautogui.keyDown(key)
            time.sleep(wait_time)
            pyautogui.keyUp(key)
            logger.debug(_("按下 {key}").format(key=key))
            # logger.debug(_("key pressed: {key}").format(key=key))
        except Exception as e:
            logger.debug(_("按下 {key} 出错：{e}").format(key=key, e=e))
            # logger.error(_("An error occurred: {e}").format(e=e))

    def press_mouse(self, wait_time=0.2):
        try:
            pyautogui.mouseDown()
            time.sleep(wait_time)
            pyautogui.mouseUp()
            logger.debug(_("按下鼠标左键"))
        except Exception as e:
            logger.debug(_("按下鼠标左键出错：{e}").format(e=e))
            # logger.error(_("An error occurred: {e}").format(e=e))

    @staticmethod
    def is_application_fullscreen(window):
        screen_width, screen_height = pyautogui.size()
        return (window.width, window.height) == (screen_width, screen_height)

    @staticmethod
    def get_window_region(window):
        up_border = 58
        other_border = 13
        if Automation.is_application_fullscreen(window):
            return (window.left, window.top, window.width, window.height)
        else:
            return (window.left + other_border, window.top + up_border, window.width -
                    other_border - other_border, window.height - up_border - other_border)

    def take_screenshot(self, crop=(0, 0, 0, 0)):
        try:
            windows = pyautogui.getWindowsWithTitle(self.window_title)
            if windows:
                window = windows[0]

                if crop == (0, 0, 0, 0):
                    self.screenshot_pos = Automation.get_window_region(window)
                else:
                    left, top, width, height = Automation.get_window_region(window)
                    self.screenshot_pos = left + width * crop[0], top + height * crop[1], width * crop[2], height * crop[3]
                self.screenshot = pyautogui.screenshot(region=self.screenshot_pos)

                return True
            return False
        except Exception as e:
            logger.error(_("截图出错：{e}").format(e=e))
            # logger.error(_("An error occurred while taking a screenshot: {e}").format(e=e))
            return False

    def get_image_info(self, image_path):
        template = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        return template.shape[::-1]

    def scale_and_match_template(self, screenshot, template, threshold=None, scale_range=None):
        max_val = -np.inf
        max_loc = None

        # 匹配原始尺寸（不缩放）
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, local_max_val, _, local_max_loc = cv2.minMaxLoc(result)

        if threshold is None or local_max_val >= threshold:
            max_val = local_max_val
            max_loc = local_max_loc

        # 如果匹配度低于阈值，再进行缩放匹配
        if (threshold is None or max_val < threshold) and scale_range is not None:
            for scale in np.arange(scale_range[0], scale_range[1], 0.1):
                scaled_template = cv2.resize(template, None, fx=scale, fy=scale)
                result = cv2.matchTemplate(screenshot, scaled_template, cv2.TM_CCOEFF_NORMED)
                _, local_max_val, _, local_max_loc = cv2.minMaxLoc(result)

                if local_max_val > max_val:
                    max_val = local_max_val
                    max_loc = local_max_loc

        return max_val, max_loc

    def find_element(self, target, find_type, threshold=None, max_retries=1, take_screenshot=True, scale_range=None, crop=(0, 0, 0, 0), include=None):
        max_retries = 1 if not take_screenshot else max_retries

        for i in range(max_retries):
            if take_screenshot and not self.take_screenshot(crop):
                continue

            if find_type in ['image', 'text']:
                if find_type == 'image':
                    top_left, bottom_right = self.find_image_element(target, threshold, scale_range)
                else:  # find_type == 'text'
                    top_left, bottom_right = self.find_text_element(target, include)

                if top_left and bottom_right:
                    return top_left, bottom_right
            else:
                raise ValueError(_("错误的类型"))

            time.sleep(1)
        return None

    def find_image_element(self, target, threshold, scale_range):
        try:
            template = cv2.imread(target, cv2.IMREAD_GRAYSCALE)
            if template is None:
                raise ValueError(_("读取图片失败"))
            screenshot = cv2.cvtColor(np.array(self.screenshot), cv2.COLOR_RGB2GRAY)
            max_val, max_loc = self.scale_and_match_template(screenshot, template, threshold, scale_range)
            logger.debug(_("目标图片：{target} 相似度：{max_val}").format(target=target, max_val=max_val))
            if threshold is None or max_val >= threshold:
                width, height = template.shape[::-1]
                top_left = (max_loc[0] + self.screenshot_pos[0], max_loc[1] + self.screenshot_pos[1])
                bottom_right = (top_left[0] + width, top_left[1] + height)
                return top_left, bottom_right
        except Exception as e:
            logger.error(_("寻找图片出错：{e}").format(e=e))
        return None, None

    def find_text_element(self, target, include):
        try:
            ocr_result = ocr.recognize_multi_lines(np.array(self.screenshot))
            if not ocr_result:
                logger.debug(_("目标文字：{target} 未找到，没有识别出任何文字").format(target=target))
                return None, None
            for box in ocr_result:
                text = box[1][0]
                if (include is None and target == text) or (include and target in text) or (not include and target == text):
                    logger.debug(_("目标文字：{target} 相似度：{max_val}").format(target=target, max_val=box[1][1]))
                    top_left = (box[0][0][0] + self.screenshot_pos[0], box[0][0][1] + self.screenshot_pos[1])
                    bottom_right = (box[0][2][0] + self.screenshot_pos[0], box[0][2][1] + self.screenshot_pos[1])
                    return top_left, bottom_right
            logger.debug(_("目标文字：{target} 未找到，没有识别出匹配文字").format(target=target))
            return None, None
        except Exception as e:
            logger.error(_("寻找文本出错：{e}").format(e=e))
            return None, None

    def click_element(self, target, find_type, similarity_threshold=None, max_retries=1, offset=(0, 0), scale_range=None, crop=(0, 0, 0, 0), include=None):
        coordinates = self.find_element(target, find_type, similarity_threshold, max_retries, scale_range=scale_range, crop=crop, include=include)
        if coordinates:
            (left, top), (right, bottom) = coordinates
            x = (left + right) // 2 + offset[0]
            y = (top + bottom) // 2 + offset[1]
            time.sleep(0.5)
            self.mouse_click(x, y)
            return True
        return False

    def get_single_line_text_from_matched_screenshot_region(
            self, target_image_path, offset=[(0, 0), (0, 0)], similarity_threshold=None, blacklist=None):
        result = self.find_element(target_image_path, 'image', similarity_threshold)
        if result:
            width = result[1][0] - result[0][0]
            height = result[1][1] - result[0][1]
            # print(left,top,right,bottom)
            left = result[0][0] + width * offset[0][0]
            top = result[0][1] + height * offset[0][1]
            right = result[1][0] + width * offset[1][0]
            bottom = result[1][1] + height * offset[1][1]
            captured_image = self.screenshot.crop(
                (left - self.screenshot_pos[0],
                 top - self.screenshot_pos[1],
                 right - self.screenshot_pos[0],
                 bottom - self.screenshot_pos[1]))
            # captured_image.save("test.png")
            ocr_result = ocr.recognize_single_line(np.array(captured_image), blacklist)
            logger.debug(_("ocr_result: {ocr_result}").format(ocr_result=ocr_result))
            if ocr_result:
                return ocr_result[0]
        return None

    def click_text_from_matched_screenshot_region(self, text, offset=[(0, 0), (0, 0)], max_retries=1, blacklist=None, target_text=None):
        result = self.find_element(text, "text", max_retries)
        if result:
            width = result[1][0] - result[0][0]
            height = result[1][1] - result[0][1]
            # print(left,top,right,bottom)
            left = result[0][0] + width * offset[0][0]
            top = result[0][1] + height * offset[0][1]
            right = result[1][0] + width * offset[1][0]
            bottom = result[1][1] + height * offset[1][1]

            captured_image = self.screenshot.crop(
                (left - self.screenshot_pos[0],
                 top - self.screenshot_pos[1],
                 right - self.screenshot_pos[0],
                 bottom - self.screenshot_pos[1]))
            # captured_image.save("test.png")
            ocr_result = ocr.recognize_single_line(np.array(captured_image), blacklist)
            logger.debug(_("ocr_result: {ocr_result}").format(ocr_result=ocr_result))
            if ocr_result:
                if ocr_result[0] == target_text:
                    x = (left + right) // 2
                    y = (top + bottom) // 2
                    self.mouse_click(x, y)
                    return True
        return False

    def retry_with_timeout(self, func, timeout=120, interval=1, *args, **kwargs):
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                result = func(*args, **kwargs)
                if result:
                    return result
            except Exception as e:
                logger.error(e)
            time.sleep(interval)

        return False  # 超时时返回 False

    # def perform_automation(self, action, *args, **kwargs):
    #     if hasattr(self, action):
    #         method = getattr(self, action)
    #         method(*args, **kwargs)
