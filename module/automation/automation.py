from managers.ocr_manager import ocr
from managers.logger_manager import logger
from managers.translate_manager import _

import numpy as np
import time
import math
import cv2

from .input import Input
from .screenshot import Screenshot


class Automation:
    _instance = None

    def __new__(cls, window_title):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.window_title = window_title
            cls._instance.screenshot = None
            cls._instance.init_automation()

        return cls._instance

    # 兼容旧代码
    def init_automation(self):
        self.mouse_click = Input.mouse_click
        self.mouse_down = Input.mouse_down
        self.mouse_up = Input.mouse_up
        self.mouse_move = Input.mouse_move
        self.mouse_scroll = Input.mouse_scroll
        self.press_key = Input.press_key
        self.press_mouse = Input.press_mouse

    def take_screenshot(self, crop=(0, 0, 0, 0)):
        result = Screenshot.take_screenshot(self.window_title, crop=crop)
        if result:
            self.screenshot, self.screenshot_pos = result
        return result

    def get_image_info(self, image_path):
        template = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        return template.shape[::-1]

    def scale_and_match_template(self, screenshot, template, threshold=None, scale_range=None):
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if (threshold is None or max_val < threshold) and scale_range is not None:
            for scale in np.arange(scale_range[0], scale_range[1] + 0.0001, 0.05):
                scaled_template = cv2.resize(template, None, fx=scale, fy=scale)
                result = cv2.matchTemplate(screenshot, scaled_template, cv2.TM_CCOEFF_NORMED)
                _, local_max_val, _, local_max_loc = cv2.minMaxLoc(result)

                if local_max_val > max_val:
                    max_val = local_max_val
                    max_loc = local_max_loc

        return max_val, max_loc

    def find_element(self, target, find_type, threshold=None, max_retries=1, crop=(0, 0, 0, 0), take_screenshot=True, relative=False, scale_range=None, include=None, need_ocr=True, source=None, pixel_bgr=None):
        # 参数有些太多了，以后改
        take_screenshot = False if not need_ocr else take_screenshot
        max_retries = 1 if not take_screenshot else max_retries
        for i in range(max_retries):
            if take_screenshot and not self.take_screenshot(crop):
                continue
            if find_type in ['image', 'text', "min_distance_text"]:
                if find_type == 'image':
                    top_left, bottom_right = self.find_image_element(target, threshold, scale_range)
                elif find_type == 'text':
                    top_left, bottom_right = self.find_text_element(target, include, need_ocr, relative)
                elif find_type == 'min_distance_text':
                    top_left, bottom_right = self.find_min_distance_text_element(target, source, include, need_ocr)
                if top_left and bottom_right:
                    return top_left, bottom_right
            elif find_type in ['image_count']:
                return self.find_image_and_count(target, threshold, pixel_bgr)
            else:
                raise ValueError(_("错误的类型"))

            if i < max_retries - 1:
                time.sleep(1)
        return None

    def find_image_element(self, target, threshold, scale_range):
        try:
            # template = cv2.imread(target, cv2.IMREAD_GRAYSCALE)
            template = cv2.imread(target)
            if template is None:
                raise ValueError(_("读取图片失败"))
            # screenshot = cv2.cvtColor(np.array(self.screenshot), cv2.COLOR_BGR2GRAY)
            screenshot = cv2.cvtColor(np.array(self.screenshot), cv2.COLOR_BGR2RGB)
            max_val, max_loc = self.scale_and_match_template(screenshot, template, threshold, scale_range)
            logger.debug(_("目标图片：{target} 相似度：{max_val}").format(target=target, max_val=max_val))
            if threshold is None or max_val >= threshold:
                channels, width, height = template.shape[::-1]
                top_left = (max_loc[0] + self.screenshot_pos[0], max_loc[1] + self.screenshot_pos[1])
                bottom_right = (top_left[0] + width, top_left[1] + height)
                return top_left, bottom_right
        except Exception as e:
            logger.error(_("寻找图片出错：{e}").format(e=e))
        return None, None

    @staticmethod
    def intersected(top_left1, botton_right1, top_left2, botton_right2):
        if top_left1[0] > botton_right2[0] or top_left2[0] > botton_right1[0]:
            return False
        if top_left1[1] > botton_right2[1] or top_left2[1] > botton_right1[1]:
            return False
        return True

    @staticmethod
    def count_template_matches(target, template, threshold):
        result = cv2.matchTemplate(target, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)
        match_count = 0
        matches = []
        width, height = template.shape[::-1]
        for top_left in zip(*locations[::-1]):
            flag = True
            for match_top_left in matches:
                botton_right = (top_left[0] + width, top_left[1] + height)
                match_botton_right = (match_top_left[0] + width, match_top_left[1] + height)
                is_intersected = Automation.intersected(top_left, botton_right, match_top_left, match_botton_right)
                if is_intersected:
                    flag = False
                    break
            if flag == True:
                matches.append(top_left)
                match_count += 1
        return match_count

    def find_image_and_count(self, target, threshold, pixel_bgr):
        try:
            template = cv2.imread(target, cv2.IMREAD_GRAYSCALE)
            screenshot = cv2.cvtColor(np.array(self.screenshot), cv2.COLOR_BGR2RGB)
            bw_map = np.zeros(screenshot.shape[:2], dtype=np.uint8)
            # 遍历每个像素并判断与目标像素的相似性
            bw_map[np.sum((screenshot - pixel_bgr) ** 2, axis=-1) <= 800] = 255
            return Automation.count_template_matches(bw_map, template, threshold)
        except Exception as e:
            logger.error(_("寻找图片并计数出错：{e}").format(e=e))
            return None

    def find_text_element(self, target, include, need_ocr=True, relative=False):
        # 兼容旧代码
        if isinstance(target, str):
            target = (target,)
        try:
            if need_ocr:
                self.ocr_result = ocr.recognize_multi_lines(np.array(self.screenshot))
            if not self.ocr_result:
                logger.debug(_("目标文字：{target} 未找到，没有识别出任何文字").format(target=", ".join(target)))
                return None, None
            for box in self.ocr_result:
                text = box[1][0]
                # if (include is None and target == text) or (include and target in text) or (not include and target == text):
                if ((include is None or not include) and text in target) or (include and any(t in text for t in target)):
                    self.matched_text = next((t for t in target if t in text), None)
                    logger.debug(_("目标文字：{target} 相似度：{max_val}").format(target=self.matched_text, max_val=box[1][1]))
                    if relative == False:
                        top_left = (box[0][0][0] + self.screenshot_pos[0], box[0][0][1] + self.screenshot_pos[1])
                        bottom_right = (box[0][2][0] + self.screenshot_pos[0], box[0][2][1] + self.screenshot_pos[1])
                    else:
                        top_left = (box[0][0][0], box[0][0][1])
                        bottom_right = (box[0][2][0], box[0][2][1])
                    return top_left, bottom_right
            logger.debug(_("目标文字：{target} 未找到，没有识别出匹配文字").format(target=", ".join(target)))
            return None, None
        except Exception as e:
            logger.error(_("寻找文字：{target} 出错：{e}").format(target=", ".join(target), e=e))
            return None, None

    def find_min_distance_text_element(self, target, source, include, need_ocr=True):
        if need_ocr:
            self.ocr_result = ocr.recognize_multi_lines(np.array(self.screenshot))
        if not self.ocr_result:
            logger.debug(_("目标文字：{target} 未找到，没有识别出任何文字").format(target=f"{target}, {source}"))
            return None, None
        # logger.debug(self.ocr_result)
        source_pos = None
        for box in self.ocr_result:
            text = box[1][0]
            if ((include is None or not include) and source == text) or (include and source in text):
                logger.debug(_("目标文字：{target} 相似度：{max_val}").format(target=source, max_val=box[1][1]))
                source_pos = box[0]
                break
        if source_pos is None:
            logger.debug(_("目标文字：{target} 未找到，没有识别出匹配文字").format(target=source))
            return None, None

        target_pos = None
        min_distance = float('inf')
        for box in self.ocr_result:
            text = box[1][0]
            if ((include is None or not include) and target == text) or (include and target in text):
                pos = box[0]
                # 如果target不在source右下角
                if not ((pos[0][0] - source_pos[0][0]) > 0 and (pos[0][1] - source_pos[0][1]) > 0):
                    continue
                distance = math.sqrt((pos[0][0] - source_pos[0][0]) ** 2 + (pos[0][1] - source_pos[0][1]) ** 2)
                logger.debug(_("目标文字：{target} 相似度：{max_val} 距离：{min_distance}").format(target=target, max_val=box[1][1], min_distance=distance))
                if distance < min_distance:
                    min_distance = distance
                    target_pos = pos
        if target_pos is None:
            logger.debug(_("目标文字：{target} 未找到，没有识别出匹配文字").format(target=target))
            return None, None
        logger.debug(_("目标文字：{target} 最短距离：{min_distance}").format(target=target, min_distance=min_distance))
        top_left = (target_pos[0][0] + self.screenshot_pos[0], target_pos[0][1] + self.screenshot_pos[1])
        bottom_right = (target_pos[2][0] + self.screenshot_pos[0], target_pos[2][1] + self.screenshot_pos[1])
        return top_left, bottom_right

    def click_element_with_pos(self, coordinates, offset=(0, 0), action="click"):
        (left, top), (right, bottom) = coordinates
        x = (left + right) // 2 + offset[0]
        y = (top + bottom) // 2 + offset[1]
        if action == "click":
            self.mouse_click(x, y)
        elif action == "down":
            self.mouse_down(x, y)
        elif action == "move":
            self.mouse_move(x, y)
        return True

    def click_element(self, target, find_type, threshold=None, max_retries=1, crop=(0, 0, 0, 0), take_screenshot=True, relative=False, scale_range=None, include=None, need_ocr=True, source=None, offset=(0, 0)):
        coordinates = self.find_element(target, find_type, threshold, max_retries, crop, take_screenshot,
                                        relative, scale_range, include, need_ocr, source)
        if coordinates:
            return self.click_element_with_pos(coordinates, offset)
        return False

    def get_single_line_text(self, crop=(0, 0, 0, 0), blacklist=None, max_retries=3):
        for i in range(max_retries):
            self.take_screenshot(crop)
            ocr_result = ocr.recognize_single_line(np.array(self.screenshot), blacklist)
            logger.debug(_("ocr识别结果: {ocr_result}").format(ocr_result=ocr_result))
            if ocr_result:
                return ocr_result[0]
        return None

    def retry_with_timeout(self, lambda_func, timeout=120, interval=1):
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                result = lambda_func()
                if result:
                    return result
            except Exception as e:
                logger.error(e)

            time.sleep(interval)

        return False
