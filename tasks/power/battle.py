import cv2
import numpy as np

from utils.image_utils import ImageUtils


SPEED_BUTTON = (0.805, 0.018, 0.092, 0.062)


def ensure_double_speed(auto):
    """双箭头已出现时保持现状，确认单箭头后才点击。"""
    template = ImageUtils.read_image("./assets/images/purefiction/battle_speed.png")
    if template is None:
        return False
    frame, _, _ = auto.take_screenshot(crop=SPEED_BUTTON)
    pixels = cv2.cvtColor(np.asarray(frame), cv2.COLOR_RGB2BGR)
    scales = (0.58, 1.05)
    score, _ = ImageUtils.scale_and_match_template(pixels, template, scale_range=scales)
    if score >= 0.83:
        return True
    # 1 倍速图标只有右侧箭头。排除双箭头匹配后才核对其形状。
    single = template[:, template.shape[1] // 2:]
    score, (left, top) = ImageUtils.scale_and_match_template(pixels, single, scale_range=scales)
    if score >= 0.90:
        x, y, width, height = SPEED_BUTTON
        cx = x + (left + single.shape[1] / 2) * width / frame.width
        cy = y + (top + single.shape[0] / 2) * height / frame.height
        auto.click_element((cx, cy, 0, 0), "crop")
    return False
