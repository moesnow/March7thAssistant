import time
import math
import cv2
import numpy as np
from PIL import Image

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
        self.press_key_down = self.input_handler.press_key_down
        self.press_key_up = self.input_handler.press_key_up
        self.secretly_press_key = self.input_handler.secretly_press_key
        self.press_mouse = self.input_handler.press_mouse
        self.secretly_write = self.input_handler.secretly_write

    def calculate_crop_with_pos(self, left_top, size):
        """
        通过大小和左上角位置计算出 take_screenshot 所需的 crop 参数。
        :param left_top: 左上角坐标，格式为(x, y)。
        :param size: 截图的大小，格式为(width, height)。
        温馨提示: 下加上减，左减右加
        """
        left, top, width, height = Screenshot.get_window_region(
            Screenshot.get_window(self.window_title)
        )
        return (
            (left_top[0] - left) / width,
            (left_top[1] - top) / height,
            (size[0]) / width,
            (size[1]) / height,
        )

    def take_screenshot(self, crop=(0, 0, 1, 1), use_background_screenshot=None):
        """
        捕获游戏窗口的截图。
        :param crop: 截图的裁剪区域，格式为(x1, y1, x2, y2)，默认为全屏。
        :return: 成功时返回截图及其位置和缩放因子，失败时抛出异常。
        """
        start_time = time.monotonic()
        while True:
            try:
                result = Screenshot.take_screenshot(
                    self.window_title,
                    crop=crop,
                    use_background_screenshot=use_background_screenshot,
                )
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
            cnt = ImageUtils.count_template_matches(bw_map, template, threshold)
            self.logger.debug(f"目标图片：{target.replace('./assets/images/', '')} 匹配数量：{cnt} 匹配阈值：{threshold} 目标像素BGR：{pixel_bgr}")
            return cnt
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
        elif position == 'right':
            return dx > 0 and abs(dy) < 10  # 允许一定的垂直偏差
        elif position == 'left':
            return dx < 0 and abs(dy) < 10  # 允许一定的垂直偏差
        elif position == 'top':
            return dy < 0 and abs(dx) < 10  # 允许一定的水平偏差
        elif position == 'bottom':
            return dy > 0 and abs(dx) < 10  # 允许一定的水平偏差
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

    def find_hsv_element(self, target, relative=False):
        """
        通过HSV颜色范围查找最大连通区域的外接矩形。
        :param target: 元组 (lower, upper)，分别为HSV下界和上界的numpy数组。
        :param relative: 是否返回相对位置。
        :return: (top_left, bottom_right) 或 (None, None)。
        """
        lower, upper = target
        img = np.array(self.screenshot)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, lower, upper)

        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)
        if num_labels <= 1:
            return None, None

        max_area = 0
        best_box = None
        for i in range(1, num_labels):
            x, y, bw, bh, area = stats[i]
            if area > max_area:
                max_area = area
                best_box = (x, y, bw, bh)

        x, y, bw, bh = best_box

        scale_factor = self.screenshot_scale_factor if not relative else 1
        top_left = (int(x / scale_factor) + self.screenshot_pos[0] * (not relative),
                    int(y / scale_factor) + self.screenshot_pos[1] * (not relative))
        bottom_right = (int((x + bw) / scale_factor) + self.screenshot_pos[0] * (not relative),
                        int((y + bh) / scale_factor) + self.screenshot_pos[1] * (not relative))
        return top_left, bottom_right

    def _get_yolo_session(self, model_path):
        """获取或创建YOLO ONNX推理会话（带缓存）。"""
        if not hasattr(self, '_yolo_sessions'):
            self._yolo_sessions = {}
        if model_path not in self._yolo_sessions:
            import onnxruntime as ort
            # providers = ort.get_available_providers()
            preferred = []
            # if "DmlExecutionProvider" in providers:
            #     preferred.append("DmlExecutionProvider")
            preferred.append("CPUExecutionProvider")
            self._yolo_sessions[model_path] = ort.InferenceSession(model_path, providers=preferred)
        return self._yolo_sessions[model_path]

    def _yolo_preprocess(self, img, input_size=640):
        """YOLO letterbox预处理。返回 (input_tensor, scale)。"""
        orig_h, orig_w = img.shape[:2]
        scale = min(input_size / orig_w, input_size / orig_h)
        new_w, new_h = int(orig_w * scale), int(orig_h * scale)
        resized = cv2.resize(img, (new_w, new_h))
        canvas = np.full((input_size, input_size, 3), 114, dtype=np.uint8)
        canvas[:new_h, :new_w] = resized
        input_img = canvas[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
        return np.expand_dims(input_img, axis=0), scale

    def _yolo_postprocess(self, preds, scale, names, target_classes, threshold):
        """YOLO后处理，返回按置信度降序排列的检测结果列表 [(cls_name, score, x1, y1, x2, y2), ...]。"""
        results = []
        for det in preds:
            x1, y1, x2, y2, score, cls_id = det
            if score < threshold:
                continue
            cls_id = int(cls_id)
            if cls_id >= len(names):
                continue
            cls_name = names[cls_id]
            if target_classes is not None and cls_name not in target_classes:
                continue
            results.append((cls_name, float(score), x1 / scale, y1 / scale, x2 / scale, y2 / scale))
        results.sort(key=lambda r: r[1], reverse=True)
        return results

    def _yolo_box_to_pos(self, x1, y1, x2, y2, relative):
        """将YOLO检测框坐标转换为与其他find方法一致的 (top_left, bottom_right) 格式。"""
        scale_factor = self.screenshot_scale_factor if not relative else 1
        offset_x = self.screenshot_pos[0] * (not relative)
        offset_y = self.screenshot_pos[1] * (not relative)
        top_left = (int(x1 / scale_factor) + offset_x, int(y1 / scale_factor) + offset_y)
        bottom_right = (int(x2 / scale_factor) + offset_x, int(y2 / scale_factor) + offset_y)
        return top_left, bottom_right

    def find_yolo_element(self, target, threshold=0.25, relative=False):
        """
        使用YOLO模型查找置信度最高的目标对象。
        :param target: dict，包含 model_path（模型路径）, names（类别名列表）, target_class（目标类名，str或list，可选）。
        :param threshold: 置信度阈值。
        :param relative: 是否返回相对位置。
        :return: (top_left, bottom_right) 或 (None, None)。
        """
        try:
            model_path = target["model_path"]
            names = target["names"]
            target_class = target.get("target_class")
            if isinstance(target_class, str):
                target_class = [target_class]

            session = self._get_yolo_session(model_path)
            img = cv2.cvtColor(np.array(self.screenshot), cv2.COLOR_RGB2BGR)
            input_tensor, scale = self._yolo_preprocess(img)

            input_name = session.get_inputs()[0].name
            outputs = session.run(None, {input_name: input_tensor})
            preds = outputs[0][0]

            results = self._yolo_postprocess(preds, scale, names, target_class, threshold)
            if not results:
                target_desc = ', '.join(target_class) if target_class else 'any'
                self.logger.debug(f"YOLO未检测到目标：{target_desc} 阈值：{threshold}")
                return None, None

            cls_name, score, x1, y1, x2, y2 = results[0]
            self.logger.debug(f"YOLO检测：{cls_name} 置信度：{score:.5f}")
            return self._yolo_box_to_pos(x1, y1, x2, y2, relative)
        except Exception as e:
            self.logger.error(f"YOLO查找出错：{e}")
            return None, None

    def find_yolo_with_multiple_targets(self, target, threshold=0.25, relative=False):
        """
        使用YOLO模型查找所有匹配的目标对象。
        :param target: dict，包含 model_path（模型路径）, names（类别名列表）, target_class（目标类名，str或list，可选）。
        :param threshold: 置信度阈值。
        :param relative: 是否返回相对位置。
        :return: [(top_left, bottom_right), ...] 列表。
        """
        try:
            model_path = target["model_path"]
            names = target["names"]
            target_class = target.get("target_class")
            if isinstance(target_class, str):
                target_class = [target_class]

            session = self._get_yolo_session(model_path)
            img = cv2.cvtColor(np.array(self.screenshot), cv2.COLOR_RGB2BGR)
            input_tensor, scale = self._yolo_preprocess(img)

            input_name = session.get_inputs()[0].name
            outputs = session.run(None, {input_name: input_tensor})
            preds = outputs[0][0]

            results = self._yolo_postprocess(preds, scale, names, target_class, threshold)
            if not results:
                target_desc = ', '.join(target_class) if target_class else 'any'
                self.logger.debug(f"YOLO未检测到目标：{target_desc} 阈值：{threshold}")
                return []

            matches = []
            for cls_name, score, x1, y1, x2, y2 in results:
                self.logger.debug(f"YOLO检测：{cls_name} 置信度：{score:.5f}")
                matches.append(self._yolo_box_to_pos(x1, y1, x2, y2, relative))
            return matches
        except Exception as e:
            self.logger.error(f"YOLO查找出错：{e}")
            return []

    def find_element(self, target, find_type, threshold=None, max_retries=1, crop=(0, 0, 1, 1), take_screenshot=True, relative=False, scale_range=None, include=None, need_ocr=True, source=None, source_type=None, pixel_bgr=None, position="bottom_right", retry_delay: float = 1.0, use_background_screenshot=None):
        """
        查找元素，并根据指定的查找类型执行不同的查找策略。
        :param target: 查找目标，可以是图像路径或文字。
        :param find_type: 查找类型，例如'image', 'text', 'hsv'等。
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
        :param use_background_screenshot: 是否使用后台截图。为None时沿用配置文件设置。
        :return: 查找到的元素位置，或者在图像计数查找时返回计数。
        """
        take_screenshot = take_screenshot and need_ocr
        max_retries = 1 if not take_screenshot else max_retries
        for i in range(max_retries):
            if take_screenshot:
                screenshot_result = self.take_screenshot(crop, use_background_screenshot)
                if not screenshot_result:
                    continue  # 如果截图失败，则跳过本次循环
            if find_type in ['image', 'image_threshold', 'text', "min_distance_text", 'crop', 'hsv', 'yolo']:
                if find_type in ['image', 'image_threshold']:
                    top_left, bottom_right, image_threshold = self.find_image_element(target, threshold, scale_range, relative)
                elif find_type == 'text':
                    top_left, bottom_right = self.find_text_element(target, include, need_ocr, relative)
                elif find_type == 'min_distance_text':
                    top_left, bottom_right = self.find_min_distance_text_element(target, source, source_type, include, need_ocr, position)
                elif find_type == 'crop':
                    top_left = (int(target[0] * self.screenshot.width) + self.screenshot_pos[0], int(target[1] * self.screenshot.height) + self.screenshot_pos[1])
                    bottom_right = (int((target[0] + target[2]) * self.screenshot.width) + self.screenshot_pos[0], int((target[1] + target[3]) * self.screenshot.height) + self.screenshot_pos[1])
                elif find_type == 'hsv':
                    top_left, bottom_right = self.find_hsv_element(target, relative)
                elif find_type == 'yolo':
                    top_left, bottom_right = self.find_yolo_element(target, threshold or 0.25, relative)
                if top_left and bottom_right:
                    if find_type == 'image_threshold':
                        return image_threshold
                    return top_left, bottom_right
            elif find_type in ['image_count']:
                return self.find_image_and_count(target, threshold, pixel_bgr)
            elif find_type in ['image_with_multiple_targets']:
                return self.find_image_with_multiple_targets(target, threshold, scale_range, relative)
            elif find_type == 'yolo_with_multiple_targets':
                return self.find_yolo_with_multiple_targets(target, threshold or 0.25, relative)
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

    def click_element(self, target, find_type, threshold=None, max_retries=1, crop=(0, 0, 1, 1), take_screenshot=True, relative=False, scale_range=None, include=None, need_ocr=True, source=None, source_type=None, pixel_bgr=None, position="bottom_right", offset=(0, 0), action="click", retry_delay: float = 1.0, use_background_screenshot=None):
        """
        查找并点击屏幕上的元素。

        参数:
        同 find_element 方法的参数，以及：
        offset: 点击坐标的偏移量。
        action: 执行的动作。
        retry_delay: 每次重试之间的等待时间（秒），默认1.0秒。
        use_background_screenshot: 是否使用后台截图。为None时沿用配置文件设置。

        返回:
        如果找到元素并点击成功，则返回True；否则返回False。
        """
        coordinates = self.find_element(target, find_type, threshold, max_retries, crop, take_screenshot, relative, scale_range, include,
                                        need_ocr, source, source_type, pixel_bgr, position, retry_delay, use_background_screenshot)
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
                return ocr_result[0]
            if retry_delay > 0 and i < max_retries - 1:
                time.sleep(retry_delay)
        self.logger.debug("OCR未识别到任何文字")
        return None

    def is_rgb_ratio_above_threshold(self, crop, rgb, threshold, tolerance=0.0):
        """判断指定 crop 区域内目标 RGB 像素占比是否超过阈值。

        参数:
        - crop: 裁剪区域，格式为 (x, y, w, h)，使用相对比例(0~1)。
        - rgb: 目标颜色，格式为 (R, G, B)。
        - threshold: 占比阈值，支持 0~1 的比例值或 0~100 的百分比值。
        - tolerance: RGB 通道允许偏差，支持 0~1 的比例值或 0~100 的百分比值。
          例如 0.05 或 5 表示每个通道允许约 13 的偏差。

        返回:
        - 若目标 RGB 像素占比超过阈值则返回 True，否则返回 False。
        """
        if not isinstance(rgb, (list, tuple)) or len(rgb) != 3 or not all(isinstance(v, (int, float)) for v in rgb):
            raise ValueError("rgb 参数必须是 (R, G, B)")

        if not isinstance(threshold, (int, float)):
            raise ValueError("threshold 参数必须是数字")
        if not isinstance(tolerance, (int, float)):
            raise ValueError("tolerance 参数必须是数字")

        ratio_threshold = float(threshold)
        if ratio_threshold > 1:
            if ratio_threshold <= 100:
                ratio_threshold /= 100
            else:
                raise ValueError("threshold 参数必须在 0~1 或 0~100 范围内")
        if ratio_threshold < 0:
            raise ValueError("threshold 参数不能小于 0")

        ratio_tolerance = float(tolerance)
        if ratio_tolerance > 1:
            if ratio_tolerance <= 100:
                ratio_tolerance /= 100
            else:
                raise ValueError("tolerance 参数必须在 0~1 或 0~100 范围内")
        if ratio_tolerance < 0:
            raise ValueError("tolerance 参数不能小于 0")

        self.take_screenshot(crop)

        img_np = np.array(self.screenshot)
        if img_np.size == 0:
            self.logger.warning("截图为空，无法计算 RGB 占比")
            return False
        if img_np.ndim == 2:
            self.logger.warning("当前截图为灰度图，无法按 RGB 计算占比")
            return False

        rgb_tuple = tuple(int(v) for v in rgb)
        channel_tolerance = 255 * ratio_tolerance
        target_rgb = np.array(rgb_tuple, dtype=np.int16)
        rgb_img = img_np[:, :, :3].astype(np.int16)
        matched_pixels = np.count_nonzero(
            np.all(np.abs(rgb_img - target_rgb) <= channel_tolerance, axis=-1)
        )
        total_pixels = rgb_img.shape[0] * rgb_img.shape[1]
        ratio = matched_pixels / total_pixels if total_pixels else 0

        self.logger.debug(
            f"RGB占比判断：rgb={rgb_tuple} 容差={ratio_tolerance:.4f} 占比={ratio:.4f} 阈值={ratio_threshold:.4f}"
        )
        return ratio > ratio_threshold

    def fill_crop_with_color(self, crop, color, use_background_screenshot=None):
        """截图后将指定 crop 区域填充为给定颜色。

        参数:
        - crop: 裁剪区域。可传单个(x, y, w, h)或多个[(x, y, w, h), ...]，
          均使用相对比例(0~1)。
        - color: 颜色值。灰度图传 int；彩色图传 (R, G, B) 或 (R, G, B, A)。
        - use_background_screenshot: 是否使用后台截图。为None时沿用配置文件设置。

        返回:
        - 处理后的截图对象（PIL Image）。
        """
        self.take_screenshot((0, 0, 1, 1), use_background_screenshot)

        img_np = np.array(self.screenshot).copy()
        h, w = img_np.shape[:2]

        is_single_crop = (
            isinstance(crop, (list, tuple))
            and len(crop) == 4
            and all(isinstance(v, (int, float)) for v in crop)
        )
        if is_single_crop:
            crop_list = [crop]
        elif isinstance(crop, (list, tuple)):
            crop_list = list(crop)
        else:
            raise ValueError("crop 参数必须是 (x, y, w, h) 或其列表")

        if not crop_list:
            raise ValueError("crop 列表不能为空")

        if img_np.ndim == 2:
            fill_value = int(color)
        else:
            channel_count = img_np.shape[2]
            if isinstance(color, int):
                fill_value = [color] * channel_count
            else:
                fill_value = list(color)[:channel_count]
                if len(fill_value) < channel_count:
                    fill_value.extend([fill_value[-1]] * (channel_count - len(fill_value)))

        has_valid_crop = False
        for index, item in enumerate(crop_list):
            if not isinstance(item, (list, tuple)) or len(item) != 4 or not all(isinstance(v, (int, float)) for v in item):
                self.logger.warning(f"无效的 crop 格式，已跳过: index={index}, crop={item}")
                continue

            x1 = max(0, min(w, int(item[0] * w)))
            y1 = max(0, min(h, int(item[1] * h)))
            x2 = max(0, min(w, int((item[0] + item[2]) * w)))
            y2 = max(0, min(h, int((item[1] + item[3]) * h)))

            if x2 <= x1 or y2 <= y1:
                self.logger.warning(f"无效的 crop 区域，已跳过: index={index}, crop={item}")
                continue

            img_np[y1:y2, x1:x2] = fill_value
            has_valid_crop = True

        if not has_valid_crop:
            self.logger.warning("未找到有效的 crop 区域，截图未修改")

        self.screenshot = Image.fromarray(img_np)
        return self.screenshot
