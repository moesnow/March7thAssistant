"""共用的 Android 冷启动检查，复用触屏 720p 素材。"""
from pathlib import Path
import time

import cv2
import numpy as np

from module.game.adb_transport import AdbError
from module.localization import tr
from utils.image_utils import ImageUtils
from utils.pause import pause_ctl


_TEMPLATES = {
    "main": (10, 40, 65, 95),
    "menu": (1040, 45, 1220, 125),
    "click_enter": (540, 620, 740, 705),
}


def _load_template(name):
    path = Path("assets/touch_720/images/screen") / f"{name}.png"
    template = ImageUtils.read_image(path)
    if template is None:
        raise AdbError("template_missing", tr("无法读取 ADB 启动所需的触屏素材：{path}").format(path=path))
    return template


def _match(image, name, template):
    x, y, right, bottom = _TEMPLATES[name]
    crop = cv2.cvtColor(np.asarray(image.crop((x, y, right, bottom))), cv2.COLOR_RGB2BGR)
    score, (left, top) = ImageUtils.scale_and_match_template(crop, template)
    if score < 0.90:
        return None
    height, width = template.shape[:2]
    return x + left + width // 2, y + top + height // 2


def wait_for_game(controller, timeout):
    """等游戏可操作。只有输入后的新画面仍是标题页才重试点按。"""
    templates = {name: _load_template(name) for name in _TEMPLATES}
    inputs = controller.get_input_handler()
    deadline = time.monotonic() + timeout
    next_enter = 0.0
    while time.monotonic() < deadline:
        pause_ctl.checkpoint()
        if frame := controller.capture_frame():
            image = frame[0]
            for name in ("main", "menu"):
                if point := _match(image, name, templates[name]):
                    return name, point
            if time.monotonic() >= next_enter and (point := _match(image, "click_enter", templates["click_enter"])):
                if inputs.mouse_click(*point):
                    controller.log_info("ADB 已点按标题进入")
                    next_enter = time.monotonic() + 4
        time.sleep(0.35)
    raise AdbError("game_start_timeout", tr("ADB 启动超时，请检查 Android 游戏的登录和横屏状态"))
