import time
import math
import cv2
import numpy as np

from .screenshot import Screenshot
from utils.logger.logger import Logger
from typing import Optional
from utils.singleton import SingletonMeta
from utils.image_utils import ImageUtils
from module.game import get_game_controller
from module.ocr import ocr


class Automation(metaclass=SingletonMeta):
    """
    自动化管理类，用于管理与游戏窗口相关的自动化操作。
    """

    def __init__(self, window_title, logger: Optional[Logger] = None):
        """
        :param window_title: 游戏窗口的标题。
        :param logger: 用于记录日志的Logger对象，可选参数。
        """
        self.window_title = window_title
        self.logger = logger
        self.screenshot = None
        self._init_input()
        self.img_cache = {}

    def _init_input(self):
        """
        初始化输入处理器，将输入操作如点击、移动等绑定至实例变量。
        """
        self.input_handler = get_game_controller().get_input_handler()
        self.mouse_click = self.input_handler.mouse_click
        self.mouse_down = self.input_handler.mouse_down
        self.mouse_up = self.input_handler.mouse_up
        self.mouse_move = self.input_handler.mouse_move
        self.mouse_scroll = self.input_handler.mouse_scroll
        self.press_key = self.input_handler.press_key
        self.secretly_press_key = self.input_handler.secretly_press_key
        self.press_mouse = self.input_handler.press_mouse
        self.secretly_write = self.input_handler.secretly_write

    def take_screenshot(self, crop=(0, 0, 1, 1)):
        """
        捕获游戏窗口的截图。
        :param crop: 截图的裁剪区域，格式为(x1, y1, x2, y2)，默认为全屏。
        :return: 成功时返回截图及其位置和缩放因子，失败时抛出异常。
        """
        start_time = time.monotonic()
        while True:
            try:
                result = Screenshot.take_screenshot(self.window_title, crop=crop)
                if result:
                    self.screenshot, self.screenshot_pos, self.screenshot_scale_factor = result
                    return result
                else:
                    self.logger.error("截图失败：没有找到游戏窗口")
            except Exception as e:
                self.logger.error(f"截图失败：{e}")
            time.sleep(1)
            if time.monotonic() - start_time > 60:
                raise RuntimeError("截图超时")

    def calculate_positions(self, template, max_loc, relative):
        """
        计算匹配位置。
        :param template: 模板图片。
        :param max_loc: 最佳匹配位置。
        :param relative: 是否返回相对位置。
        :return: 匹配位置的顶点坐标和相似度。
        """
        try:
            channels, width, height = template.shape[::-1]
        except:
            width, height = template.shape[::-1]

        scale_factor = self.screenshot_scale_factor if not relative else 1
        top_left = (int(max_loc[0] / scale_factor) + self.screenshot_pos[0] * (not relative),
                    int(max_loc[1] / scale_factor) + self.screenshot_pos[1] * (not relative))
        bottom_right = (top_left[0] + int(width / scale_factor), top_left[1] + int(height / scale_factor))
        return top_left, bottom_right

    def find_image_element(self, target, threshold, scale_range, relative=False, cacheable=True):
        """
        查找图像元素。
        :param target: 目标图像路径。
        :param threshold: 相似度阈值。
        :param scale_range: 缩放范围。
        :param relative: 是否返回相对位置。
        :return: 最佳匹配位置和相似度。
        """
        try:
            if cacheable and target in self.img_cache:
                mask = self.img_cache[target]['mask']
                template = self.img_cache[target]['template']
            else:
                mask = ImageUtils.read_template_with_mask(target)  # 读取模板图片掩码
                template = cv2.imread(target)  # 读取模板图片
                if cacheable:
                    self.img_cache[target] = {'mask': mask, 'template': template}
            screenshot = cv2.cvtColor(np.array(self.screenshot), cv2.COLOR_BGR2RGB)  # 将截图转换为RGB
            if mask is not None:
                matchVal, matchLoc = ImageUtils.scale_and_match_template(screenshot, template, threshold, scale_range, mask)  # 执行缩放并匹配模板
            else:
                matchVal, matchLoc = ImageUtils.scale_and_match_template(screenshot, template, threshold, scale_range)  # 执行缩放并匹配模板

            # 这里的相似度文本说明有问题，对于无mask匹配相似度越高越好。有mask匹配则是越低越好
            self.logger.debug(f"目标图片：{target.replace('./assets/images/', '')} 相似度：{matchVal:.2f} 匹配阈值：{threshold}")

            # # 获取模板图像的宽度和高度
            # template_width = template.shape[1]
            # template_height = template.shape[0]

            # # 在输入图像上绘制矩形框
            # top_left = matchLoc
            # bottom_right = (top_left[0] + template_width, top_left[1] + template_height)
            # cv2.rectangle(screenshot, top_left, bottom_right, (0, 255, 0), 2)

            # # 显示标记了匹配位置的图像
            # cv2.imshow('Matched Image', screenshot)
            # cv2.waitKey(0)
            # cv2.destroyAllWindows()

            if mask is not None:
                if not math.isinf(matchVal) and (threshold is None or matchVal <= threshold):
                    top_left, bottom_right = self.calculate_positions(template, matchLoc, relative)
                    return top_left, bottom_right, matchVal
            else:
                if not math.isinf(matchVal) and (threshold is None or matchVal >= threshold):
                    top_left, bottom_right = self.calculate_positions(template, matchLoc, relative)
                    return top_left, bottom_right, matchVal
        except Exception as e:
            self.logger.error(f"寻找图片出错：{e}")
        return None, None, None

    def generate_black_white_map(self, pixel_bgr):
        """生成黑白图，标记与目标像素相似的区域。

        参数:
        - pixel_bgr: 目标像素的BGR值。

        返回:
        - 黑白图数组。
        """
        screenshot = cv2.cvtColor(np.array(self.screenshot), cv2.COLOR_BGR2RGB)
        bw_map = np.zeros(screenshot.shape[:2], dtype=np.uint8)
        bw_map[np.sum((screenshot - pixel_bgr) ** 2, axis=-1) <= 800] = 255
        return bw_map

    def find_image_and_count(self, target, threshold, pixel_bgr):
        """在屏幕截图中查找与目标图片相似的图片，并计算匹配数量。

        参数:
        - target: 目标图片路径。
        - threshold: 匹配阈值。
        - pixel_bgr: 目标像素的BGR值，用于生成黑白图。

        返回:
        - 匹配的数量，或在出错时返回 None。
        """
        try:
            template = cv2.imread(target, cv2.IMREAD_GRAYSCALE)
            if template is None:
                raise ValueError("读取图片失败")
            bw_map = self.generate_black_white_map(pixel_bgr)
            return ImageUtils.count_template_matches(bw_map, template, threshold)
        except Exception as e:
            self.logger.error(f"寻找图片并计数出错：{e}")
            return None

    def find_image_with_multiple_targets(self, target, threshold, scale_range, relative=False):
        try:
            template = cv2.imread(target, cv2.IMREAD_GRAYSCALE)
            if template is None:
                raise ValueError("读取图片失败")
            screenshot = cv2.cvtColor(np.array(self.screenshot), cv2.COLOR_BGR2GRAY)
            matches = ImageUtils.scale_and_match_template_with_multiple_targets(screenshot, template, threshold, scale_range)
            if len(matches) == 0:
                return []
            new_matches = []
            for match in matches:
                top_left, bottom_right = self.calculate_positions(template, match, relative)
                new_matches.append((top_left, bottom_right))
            return new_matches
        except Exception as e:
            self.logger.error(f"寻找图片出错：{e}")
            return []

    def calculate_text_position(self, box, relative):
        """
        计算文本的位置坐标。
        :param box: 文本的边界框。
        :param relative: 是否返回相对位置。
        :return: 文本的顶点和底点坐标。
        """
        # 先计算相对坐标
        top_left_relative = (int(box[0][0] / self.screenshot_scale_factor), int(box[0][1] / self.screenshot_scale_factor))
        bottom_right_relative = (int(box[2][0] / self.screenshot_scale_factor), int(box[2][1] / self.screenshot_scale_factor))

        if not relative:
            # 如果需要返回绝对位置，就加上偏移量
            top_left = (top_left_relative[0] + self.screenshot_pos[0], top_left_relative[1] + self.screenshot_pos[1])
            bottom_right = (bottom_right_relative[0] + self.screenshot_pos[0], bottom_right_relative[1] + self.screenshot_pos[1])
        else:
            # 否则直接返回相对坐标
            top_left = top_left_relative
            bottom_right = bottom_right_relative

        return top_left, bottom_right

    def is_text_match(self, text, targets, include):
        """
        判断文本是否符合搜索条件，并返回匹配的文本。
        :param text: OCR识别出的文本。
        :param targets: 目标文本列表。
        :param include: 是否包含目标字符串。
        :return: (是否匹配, 匹配的目标文本)
        """
        if include:
            for target in targets:
                if target in text:
                    return True, target  # 直接返回匹配成功及匹配的目标文本
            return False, None  # 如果没有匹配，返回False和None
        else:
            return (text in targets, text if text in targets else None)

    def search_text_in_ocr_results(self, targets, include, relative):
        """
        在OCR结果中搜索目标文本。
        :param targets: 目标文本列表。
        :param include: 是否包含目标字符串。
        :param relative: 是否返回相对位置。
        :return: 如果找到，返回文本的位置坐标。
        """
        for box, (text, confidence) in self.ocr_result:
            match, matched_text = self.is_text_match(text, targets, include)
            if match:
                self.matched_text = matched_text  # 更新匹配的文本变量
                self.logger.debug(f"目标文字：{matched_text} 相似度：{confidence:.2f}")
                return self.calculate_text_position(box, relative)
        self.logger.debug(f"目标文字：{', '.join(targets)} 未找到匹配文字")
        return None, None

    def perform_ocr(self):
        """执行OCR识别，并更新OCR结果列表。如果未识别到文字，保留ocr_result为一个空列表。"""
        try:
            self.ocr_result = ocr.recognize_multi_lines(np.array(self.screenshot))
            if not self.ocr_result:
                self.logger.debug(f"未识别出任何文字")
                self.ocr_result = []
        except Exception as e:
            self.logger.error(f"OCR识别失败：{e}")
            self.ocr_result = []  # 确保在异常情况下，ocr_result为列表类型

    def find_text_element(self, target, include, need_ocr=True, relative=False):
        """
        查找文本元素。
        :param target: 目标文本或包含目标文本的元组。
        :param include: 如果为True，寻找包含目标字符串的文本；如果为False，寻找与目标字符串精确匹配的文本。
        :param need_ocr: 是否需要执行OCR识别来识别屏幕上的文本。
        :param relative: 如果为True，返回相对于截图的位置；如果为False，返回绝对位置。
        :return: 文本的位置坐标，如果找到的话。
        """
        target_texts = [target] if isinstance(target, str) else list(target)  # 确保目标文本是列表格式
        if need_ocr:
            self.perform_ocr()  # 执行OCR识别

        return self.search_text_in_ocr_results(target_texts, include, relative)

    def calculate_text_position2(self, pos):
        """计算文本的位置坐标。"""
        top_left = (int(pos[0][0] / self.screenshot_scale_factor) + self.screenshot_pos[0],
                    int(pos[0][1] / self.screenshot_scale_factor) + self.screenshot_pos[1])
        bottom_right = (int(pos[2][0] / self.screenshot_scale_factor) + self.screenshot_pos[0],
                        int(pos[2][1] / self.screenshot_scale_factor) + self.screenshot_pos[1])
        return top_left, bottom_right

    def is_position_matched(self, target_pos, source_pos, position):
        """根据方位判断目标位置是否符合条件。"""
        dx = target_pos[0][0] - source_pos[0]
        dy = target_pos[0][1] - source_pos[1]
        if position == 'bottom_right':
            return dx > 0 and dy > 0
        elif position == 'top_left':
            return dx < 0 and dy < 0
        elif position == 'bottom_left':
            return dx < 0 and dy > 0
        elif position == 'top_right':
            return dx > 0 and dy < 0
        return False

    def find_target_near_source(self, target, include, source_pos, position):
        """在指定方位查找距离源最近的目标文本。"""
        target_texts = [target] if isinstance(target, str) else list(target)  # 确保目标文本是列表格式
        min_distance = float('inf')
        target_pos = None
        for box in self.ocr_result:
            text, _ = box[1]
            match, matched_text = self.is_text_match(text, target_texts, include)
            if match:
                pos = box[0]
                if self.is_position_matched(pos, source_pos, position):
                    distance = math.sqrt((pos[0][0] - source_pos[0]) ** 2 + (pos[0][1] - source_pos[1]) ** 2)
                    self.logger.debug(f"目标文字：{matched_text} 距离：{distance}")
                    if distance < min_distance:
                        self.matched_text = matched_text  # 更新匹配的文本变量
                        min_distance = distance
                        target_pos = pos
        if target_pos is None:
            self.logger.debug(f"目标文字：{', '.join(target_texts)} 未找到匹配文字")
            return None, None
        return self.calculate_text_position2(target_pos)

    def find_source_position(self, source, source_type, include):
        """根据源类型查找源位置。"""
        if source_type == 'text':
            for box in self.ocr_result:
                text, confidence = box[1]
                match, matched_text = self.is_text_match(text, [source], include)
                if match:
                    self.logger.debug(f"目标文字：{source} 相似度：{confidence:.2f}")
                    return box[0][0]  # 返回文本的起始位置
        elif source_type == 'image':
            top_left, _, _ = self.find_image_element(source, 0.7, None, True)
            return top_left
        return None

    def find_min_distance_text_element(self, target, source, source_type, include, need_ocr=True, position='bottom_right'):
        """
        查找距离特定源最近的文本元素。
        :param target: 目标文本或包含目标文本的元组。
        :param source: 源文本或图片路径。
        :param source_type: 源类型，'text'或'image'。
        :param include: 是否包含目标字符串。
        :param need_ocr: 是否需要执行OCR识别。
        :param position: 查找方位，'top_left', 'top_right', 'bottom_left', 或 'bottom_right'。
        :return: 最近的文本位置。
        """
        if need_ocr:
            self.perform_ocr()  # 执行OCR识别

        source_pos = self.find_source_position(source, source_type, include)

        if source_pos is None:
            self.logger.debug(f"目标内容：{source.replace('./assets/images/', '')} 未找到")
            return None, None

        return self.find_target_near_source(target, include, source_pos, position)

    def calculate_click_position(self, coordinates, offset=(0, 0)):
        """
        计算实际点击位置的坐标。

        参数:
        - coordinates: 元组，表示元素的坐标，格式为((left, top), (right, bottom))。
        - offset: 元组，表示相对于元素中心的偏移量，格式为(x_offset, y_offset)。

        返回:
        - (x, y): 元组，表示计算后的点击位置坐标。
        """
        (left, top), (right, bottom) = coordinates
        x = (left + right) // 2 + offset[0]
        y = (top + bottom) // 2 + offset[1]
        return x, y

    def find_element(self, target, find_type, threshold=None, max_retries=1, crop=(0, 0, 1, 1), take_screenshot=True, relative=False, scale_range=None, include=None, need_ocr=True, source=None, source_type=None, pixel_bgr=None, position="bottom_right", retry_delay: float = 1.0):
        """
        查找元素，并根据指定的查找类型执行不同的查找策略。
        :param target: 查找目标，可以是图像路径或文字。
        :param find_type: 查找类型，例如'image', 'text'等。
        :param threshold: 查找阈值，用于图像查找时的相似度匹配。
        :param max_retries: 最大重试次数。
        :param crop: 截图的裁剪区域，格式为（x坐标百分比，y坐标百分比，长百分比，宽百分比）。
        :param take_screenshot: 是否需要先截图。
        :param relative: 返回相对位置还是绝对位置。
        :param scale_range: 图像查找时的缩放范围。
        :param include: 文字查找时是否包含目标字符串。
        :param need_ocr: 是否需要执行OCR识别。
        :param source: 查找参照物，用于距离最小化查找。
        :param source_type: 查找参照物的类型。
        :param pixel_bgr: 颜色查找时的BGR值。
        :param position: 查找方位，'top_left', 'top_right', 'bottom_left', 或 'bottom_right'。
        :param retry_delay: 每次重试之间的等待时间（秒），默认1.0秒。
        :return: 查找到的元素位置，或者在图像计数查找时返回计数。
        """
        take_screenshot = take_screenshot and need_ocr
        max_retries = 1 if not take_screenshot else max_retries
        for i in range(max_retries):
            if take_screenshot:
                screenshot_result = self.take_screenshot(crop)
                if not screenshot_result:
                    continue  # 如果截图失败，则跳过本次循环
            if find_type in ['image', 'image_threshold', 'text', "min_distance_text", 'crop']:
                if find_type in ['image', 'image_threshold']:
                    top_left, bottom_right, image_threshold = self.find_image_element(target, threshold, scale_range, relative)
                elif find_type == 'text':
                    top_left, bottom_right = self.find_text_element(target, include, need_ocr, relative)
                elif find_type == 'min_distance_text':
                    top_left, bottom_right = self.find_min_distance_text_element(target, source, source_type, include, need_ocr, position)
                elif find_type == 'crop':
                    top_left = (int(target[0] * self.screenshot.width) + self.screenshot_pos[0], int(target[1] * self.screenshot.height) + self.screenshot_pos[1])
                    bottom_right = (int((target[0] + target[2]) * self.screenshot.width) + self.screenshot_pos[0], int((target[1] + target[3]) * self.screenshot.height) + self.screenshot_pos[1])
                if top_left and bottom_right:
                    if find_type == 'image_threshold':
                        return image_threshold
                    return top_left, bottom_right
            elif find_type in ['image_count']:
                return self.find_image_and_count(target, threshold, pixel_bgr)
            elif find_type in ['image_with_multiple_targets']:
                return self.find_image_with_multiple_targets(target, threshold, scale_range, relative)
            else:
                raise ValueError("错误的类型")

            if i < max_retries - 1:
                time.sleep(retry_delay)  # 在重试前等待一定时间
        return None

    def click_element_with_pos(self, coordinates, offset=(0, 0), action="click", cnt=1):
        """
        在指定坐标上执行点击操作。

        参数:
        - coordinates: 元素的坐标。
        - offset: 坐标的偏移量。
        - action: 执行的动作，包括'click', 'down', 'move'。

        返回:
        - 如果操作成功，则返回True；否则返回False。
        """
        x, y = self.calculate_click_position(coordinates, offset)
        # 动作到方法的映射
        action_map = {
            "click": self.mouse_click,
            "down": self.mouse_down,
            "move": self.mouse_move,
        }

        if action in action_map:
            for _ in range(cnt):
                action_map[action](x, y)
        else:
            raise ValueError(f"未知的动作类型: {action}")

        return True

    def click_element(self, target, find_type, threshold=None, max_retries=1, crop=(0, 0, 1, 1), take_screenshot=True, relative=False, scale_range=None, include=None, need_ocr=True, source=None, source_type=None, pixel_bgr=None, position="bottom_right", offset=(0, 0), action="click", retry_delay: float = 1.0):
        """
        查找并点击屏幕上的元素。

        参数:
        同 find_element 方法的参数，以及：
        offset: 点击坐标的偏移量。
        action: 执行的动作。
        retry_delay: 每次重试之间的等待时间（秒），默认1.0秒。

        返回:
        如果找到元素并点击成功，则返回True；否则返回False。
        """
        coordinates = self.find_element(target, find_type, threshold, max_retries, crop, take_screenshot, relative, scale_range, include, need_ocr, source, source_type, pixel_bgr, position, retry_delay)
        if coordinates:
            return self.click_element_with_pos(coordinates, offset, action)
        return False

    def get_single_line_text(self, crop=(0, 0, 1, 1), blacklist=None, max_retries=3, retry_delay=0.0):
        """
        尝试多次获取屏幕截图中的单行文本。

        参数:
        crop: 裁剪区域，格式为(x1, y1, x2, y2)。
        blacklist: 需要过滤掉的字符列表。
        max_retries: 尝试识别的最大次数。
        retry_delay: 每次重试之间的等待时间（秒），默认0.0秒。

        返回:
        识别到的文本，如果多次尝试后仍未识别到，则返回None。
        """
        for i in range(max_retries):
            self.take_screenshot(crop)
            ocr_result = ocr.recognize_single_line(np.array(self.screenshot), blacklist)
            if ocr_result:
                self.logger.debug(f"OCR识别结果：{ocr_result[0]}")
                return ocr_result[0]
            if retry_delay > 0 and i < max_retries - 1:
                time.sleep(retry_delay)
        self.logger.debug("OCR未识别到任何文字")
        return None
