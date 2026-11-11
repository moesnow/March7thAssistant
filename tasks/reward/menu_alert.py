import cv2
import numpy as np

from utils.image_utils import ImageUtils


def red_dot_present(pixels):
    """只把有红色圆底与白色中心的标记作为红点。"""
    red, green, blue = np.moveaxis(pixels.astype(np.int16), -1, 0)
    mask = (red >= 155) & (red - green >= 75) & (red - blue >= 60)
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if 9 <= width <= 38 and 9 <= height <= 38 and 0.75 <= width / height <= 1.33:
            area = cv2.contourArea(contour) / (width * height)
            center = pixels[y + height // 4:y + height * 3 // 4, x + width // 3:x + width * 2 // 3]
            if 0.53 <= area <= 0.89 and (center.min(axis=-1) >= 190).any():
                return True
    return False


def menu_alert(auto, crop, icon, *, scales=(0.8, 1.12)):
    """定位图标不被角标遮挡的部分，再检查其右上角。"""
    frame, _, _ = auto.take_screenshot(crop=crop)
    rgb = np.asarray(frame.convert("RGB"))
    pixels = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    template = ImageUtils.read_image(icon, cv2.IMREAD_GRAYSCALE)
    if template is None:
        return None
    height, width = template.shape
    lower = template[height // 2:, :]
    best = None
    for scale in np.arange(scales[0], scales[1] + 0.001, 0.02):
        glyph = cv2.resize(lower, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if glyph.shape[0] > pixels.shape[0] or glyph.shape[1] > pixels.shape[1]:
            continue
        _, score, _, (x, y) = cv2.minMaxLoc(cv2.matchTemplate(pixels, glyph, cv2.TM_CCOEFF_NORMED))
        if score >= 0.87 and (best is None or score > best[0]):
            best = score, x, y, scale
    if best is None:
        return None
    _, x, y, scale = best
    edge = x + round(width * scale)
    top = y - round(height * scale / 2)
    if top < 14 or edge + 15 > pixels.shape[1]:
        return None
    corner = rgb[top - 14:y + 8, max(0, edge - 26):edge + 15]
    if red_dot_present(corner):
        return True
    # 图标定位成功但邻域有其他红色内容时，留给页内判断。
    red, green, blue = np.moveaxis(corner.astype(np.int16), -1, 0)
    if ((red >= 155) & (green <= 95) & (red - green >= 65) & (red - blue >= 55)).any():
        return None
    return False
