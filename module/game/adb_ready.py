"""共用的 Android 冷启动检查，复用触屏 720p 素材。"""
from pathlib import Path
import time

import cv2
import numpy as np

from module.automation.input_base import limit_input_deadline, observe_input_dispatch
from module.game.adb_startup_frames import StartupFrameHealth
from module.game.adb_transport import AdbError
from module.localization import tr
from module.logger import log
from utils.image_utils import ImageUtils
from utils.pause import pause_ctl


_TEMPLATES = {
    "main": (10, 40, 65, 95),
    "menu": (1040, 45, 1220, 125),
    "click_enter": (540, 620, 740, 705),
    "monthly_card": (556, 38, 725, 91),
    "monthly_card_claim": (671, 307, 794, 508),
    "monthly_card_reward": (587, 298, 693, 417),
    "monthly_card_prompt": (548, 663, 733, 710),
}
_MONTHLY_CARD_RETRY_DELAY = 4.0
_MONTHLY_CARD_MAX_TAPS = 2


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
    log.debug(f"ADB 启动模板 {name} 区域={_TEMPLATES[name]} 相似度={score:.3f} 阈值=0.90")
    if score < 0.90:
        return None
    height, width = template.shape[:2]
    return x + left + width // 2, y + top + height // 2


class _MonthlyCard:
    def __init__(self):
        self.seen = False
        self.stage = "monthly_card_claim"
        self.taps = 0
        self.retry_at = 0.0

    def _input_sent(self, sent_at):
        self.taps += 1
        self.retry_at = sent_at + _MONTHLY_CARD_RETRY_DELAY

    def handle(self, image, templates, controller, inputs, deadline):
        if not _match(image, "monthly_card", templates["monthly_card"]):
            return False
        self.seen = True

        # 领奖动画和结果页共用底部提示，看到星琼卡片后才关闭。
        if self.stage == "monthly_card_claim" and _match(image, "monthly_card_reward", templates["monthly_card_reward"]):
            self.stage = "monthly_card_reward"
            self.taps = 0
            self.retry_at = 0.0
        elif not _match(image, self.stage, templates[self.stage]):
            return True

        if self.taps < _MONTHLY_CARD_MAX_TAPS and time.monotonic() >= self.retry_at:
            point = _match(image, "monthly_card_prompt", templates["monthly_card_prompt"])
            pause_ctl.check_stop()
            if point and time.monotonic() < deadline:
                with observe_input_dispatch(self._input_sent, deadline=deadline):
                    if inputs.mouse_click(*point):
                        action = "领取" if self.stage == "monthly_card_claim" else "关闭"
                        controller.log_info(f"ADB 已点按{action}列车补给")
        return True


def wait_for_game(controller, timeout, *, recover=None, recover_without_frame=None):
    """点按标题进入，处理列车补给弹窗，等待游戏可操作。"""
    deadline = time.monotonic() + timeout
    templates = {name: _load_template(name) for name in _TEMPLATES}
    inputs = controller.get_input_handler()
    monthly_card = _MonthlyCard()
    frame_health = StartupFrameHealth() if controller.display_id else None
    next_enter = 0.0
    next_recovery = 0.0
    while time.monotonic() < deadline:
        pause_ctl.checkpoint()
        frame = controller.capture_frame(fresh=monthly_card.seen)
        pause_ctl.check_stop()
        if time.monotonic() >= deadline:
            break
        if frame_health is not None and not monthly_card.seen:
            frame_health.check(controller, frame, time.monotonic(), deadline)
            pause_ctl.check_stop()
            if time.monotonic() >= deadline:
                break
        if frame:
            image = frame[0]
            if monthly_card.handle(image, templates, controller, inputs, deadline):
                time.sleep(0.35)
                continue
            for name in ("main", "menu"):
                if point := _match(image, name, templates[name]):
                    return name, point
            if time.monotonic() >= next_enter and (point := _match(image, "click_enter", templates["click_enter"])):
                with limit_input_deadline(deadline):
                    if time.monotonic() < deadline and inputs.mouse_click(*point):
                        controller.log_info("ADB 已点按标题进入")
                        next_enter = time.monotonic() + 4
            elif recover is not None and max(next_enter, next_recovery) <= time.monotonic() < deadline:
                with limit_input_deadline(deadline):
                    recover()
                next_recovery = time.monotonic() + 4
        elif recover_without_frame is not None:
            recover_without_frame(deadline)
        time.sleep(0.35)
    if monthly_card.seen:
        raise AdbError("game_start_timeout", tr("等待列车补给弹窗关闭并返回主界面超时，请在游戏中检查领取状态"))
    raise AdbError("game_start_timeout", tr("ADB 启动超时，请在安卓设备上检查是否需要登录或更新游戏"))
