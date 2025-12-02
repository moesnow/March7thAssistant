import math
import cv2
import numpy as np


class ImageUtils:
    @staticmethod
    def get_image_info(image_path):
        """
        获取图片的信息，如尺寸。
        :param image_path: 图片路径。
        :return: 图片的宽度和高度。
        """
        template = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        return template.shape[::-1]

    @staticmethod
    def scale_and_match_template(screenshot, template, threshold=None, scale_range=None, mask=None):
        """
        对模板进行缩放并匹配至截图，找出最佳匹配位置。
        :param screenshot: 截图。
        :param template: 模板图片。
        :param threshold: 匹配阈值，小于此值的匹配将被忽略。
        :param scale_range: 缩放范围，格式为(start_scale, end_scale)。
        :param mask: 模板的掩码，用于匹配透明区域。
        :return: 最大匹配值和最佳匹配位置。
        """
        if mask is not None:
            # 我不知道为什么这里要用低分匹配方法，这导致了部分文件识别设置阈值要设置的很大很大（如界域锚点要设置到3,000,000)
            # 另外，就是用mask的图片和不用mask的图片判断逻辑是完全相反的，一个阈值要设置的高一个阈值要设置的低 带mask的是越低越好
            # 但是这个代码耦合的内容太多了，我不知道还有什么地方会受到影响，姑且就先这么用着了
            result = cv2.matchTemplate(screenshot, template, cv2.TM_SQDIFF, mask=mask) 
            min_val, _, min_loc, _ = cv2.minMaxLoc(result)
            return min_val, min_loc
        else:
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if scale_range and (math.isinf(max_val) or threshold is None or max_val < threshold):
            for scale in np.arange(scale_range[0], scale_range[1] + 0.0001, 0.05):
                scaled_template = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
                result = cv2.matchTemplate(screenshot, scaled_template, cv2.TM_CCOEFF_NORMED)
                _, local_max_val, _, local_max_loc = cv2.minMaxLoc(result)

                if local_max_val > max_val:
                    max_val = local_max_val
                    max_loc = local_max_loc

        return max_val, max_loc

    @staticmethod
    def scale_and_match_template_with_multiple_targets(screenshot, template, threshold=None, scale=None):
        """
        对模板进行缩放并匹配至截图，找出最佳匹配位置。
        :param screenshot: 截图。
        :param template: 模板图片。
        :param threshold: 匹配阈值，小于此值的匹配将被忽略。
        :param scale: 缩放值。
        :return: 匹配位置。
        """
        if scale is not None:
            template = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)
        matches = ImageUtils.filter_overlapping_matches(locations, template.shape[::-1])
        return ImageUtils.convert_np_int64_to_int(matches)

    @staticmethod
    def read_template_with_mask(target):
        """
        读取模板图片，并根据需要生成掩码。
        :param target: 目标图片路径。
        :return: 掩码（如果有透明通道）。
        """
        template = cv2.imread(target, cv2.IMREAD_UNCHANGED)  # 保留图片的透明通道
        if template is None:
            raise ValueError(f"读取图片失败：{target}")

        mask = None
        if template.shape[-1] == 4:  # 检查通道数是否为4（含有透明通道）
            alpha_channel = template[:, :, 3]
            if np.any(alpha_channel < 255):  # 检查是否存在非完全透明的像素
                mask = alpha_channel

        return mask

    @staticmethod
    def intersected(top_left1, botton_right1, top_left2, botton_right2):
        """判断两个矩形是否相交。

        参数:
        - top_left1: 第一个矩形的左上角坐标 (x, y)。
        - botton_right1: 第一个矩形的右下角坐标 (x, y)。
        - top_left2: 第二个矩形的左上角坐标 (x, y)。
        - botton_right2: 第二个矩形的右下角坐标 (x, y)。

        返回:
        - bool: 如果矩形相交返回True，否则返回False。

        逻辑说明:
        - 如果一个矩形在另一个矩形的右侧或左侧，它们不相交。
        - 如果一个矩形在另一个矩形的上方或下方，它们也不相交。
        - 否则，矩形相交。
        """
        # 检查矩形1是否在矩形2的右侧或矩形2是否在矩形1的右侧
        if top_left1[0] > botton_right2[0] or top_left2[0] > botton_right1[0]:
            return False
        # 检查矩形1是否在矩形2的下方或矩形2是否在矩形1的下方
        if top_left1[1] > botton_right2[1] or top_left2[1] > botton_right1[1]:
            return False
        # 上述条件都不成立，则矩形相交
        return True

    @staticmethod
    def is_match_non_overlapping(top_left, matches, width, height):
        """检查给定的匹配位置是否与已有的匹配重叠。

        参数:
        - top_left: 当前匹配的左上角坐标。
        - matches: 已有的匹配位置列表。
        - width: 模板宽度。
        - height: 模板高度。

        返回:
        - bool: 是否不重叠。
        """
        botton_right = (top_left[0] + width, top_left[1] + height)
        for match_top_left in matches:
            match_botton_right = (match_top_left[0] + width, match_top_left[1] + height)
            if ImageUtils.intersected(top_left, botton_right, match_top_left, match_botton_right):
                return False
        return True

    @staticmethod
    def filter_overlapping_matches(locations, template_size):
        """过滤掉重叠的匹配。

        参数:
        - locations: 匹配的位置数组。
        - template_size: 模板图片的大小 (宽度, 高度)。

        返回:
        - matches: 不重叠的匹配位置列表。
        """
        matches = []
        width, height = template_size
        for top_left in zip(*locations[::-1]):
            if ImageUtils.is_match_non_overlapping(top_left, matches, width, height):
                matches.append(top_left)
        return matches

    @staticmethod
    def count_template_matches(target, template, threshold):
        """使用模板匹配计算目标图片中的匹配数。

        参数:
        - target: 目标图片数组。
        - template: 模板图片数组。
        - threshold: 匹配阈值，用于决定哪些结果被认为是匹配。

        返回:
        - match_count: 匹配的数量。
        """
        # 执行模板匹配
        result = cv2.matchTemplate(target, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)

        matches = ImageUtils.filter_overlapping_matches(locations, template.shape[::-1])

        # 返回匹配数量
        return len(matches)

    @staticmethod
    def convert_np_int64_to_int(matches):
        return [(int(a), int(b)) for a, b in matches]
