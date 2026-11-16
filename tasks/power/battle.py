import cv2
import numpy as np

from utils.image_utils import ImageUtils


SPEED_BUTTON = (0.805, 0.018, 0.092, 0.062)
SPEED_TEMPLATE = "./assets/images/purefiction/battle_speed.png"
SPEED_SCALES = (0.58, 1.05)


def _capture_speed_button(auto):
    frame, _, _ = auto.take_screenshot(crop=SPEED_BUTTON)
    return frame, cv2.cvtColor(np.asarray(frame), cv2.COLOR_RGB2BGR)


def _double_speed_score(pixels, template):
    score, _ = ImageUtils.scale_and_match_template(pixels, template, scale_range=SPEED_SCALES)
    return score


def battle_speed_visible(auto):
    """用战斗 HUD 上的双箭头确认已经进入战斗。"""
    template = ImageUtils.read_image(SPEED_TEMPLATE)
    if template is None:
        return False
    _, pixels = _capture_speed_button(auto)
    return _double_speed_score(pixels, template) >= 0.90


def ensure_double_speed(auto):
    """双箭头已出现时保持现状，确认单箭头后才点击。"""
    template = ImageUtils.read_image(SPEED_TEMPLATE)
    if template is None:
        return False
    frame, pixels = _capture_speed_button(auto)
    if _double_speed_score(pixels, template) >= 0.83:
        return True
    # 1 倍速图标只有右侧箭头。排除双箭头匹配后才核对其形状。
    single = template[:, template.shape[1] // 2:]
    score, (left, top) = ImageUtils.scale_and_match_template(pixels, single, scale_range=SPEED_SCALES)
    if score >= 0.90:
        x, y, width, height = SPEED_BUTTON
        cx = x + (left + single.shape[1] / 2) * width / frame.width
        cy = y + (top + single.shape[0] / 2) * height / frame.height
        auto.click_element((cx, cy, 0, 0), "crop")
    return False
