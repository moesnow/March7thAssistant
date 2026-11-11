import time

import cv2
import numpy as np

from module.automation import auto
from module.logger import log
from module.notification.notification import NotificationLevel
from module.screen import screen
from tasks.base.base import Base
from tasks.base.list_drag import drag_list
from utils.image_utils import ImageUtils
from .receipt import ITEM_POPUP, RewardError, close_item_reward
from .rewardtemplate import RewardTemplate


class Message(RewardTemplate):
    _LIST = (300 / 1920, 252 / 1080, 435 / 1920, 635 / 1080)
    _NOTIFY_LIST_CROP = (323 / 1920, 257 / 1080, 100 / 1920, 632 / 1080)
    _UNREAD_MARK = "./assets/images/share/base/RedExclamationMark.png"
    _PENDING_THREAD = "./assets/images/share/reward/message/unread_incoming_message_icon.png"
    _REPLY_CROP = (0.38, 0.60, 0.54, 0.29)
    _REPLY_ASSETS = "./assets/touch_720/images/reward"

    @staticmethod
    def _reply():
        frame, _, _ = auto.take_screenshot(crop=Message._REPLY_CROP)
        pixels = cv2.cvtColor(np.asarray(frame.convert("RGB")), cv2.COLOR_RGB2BGR)
        for name, offset in (("message_reply", (0, 0)), ("message_sticker", (83, 93))):
            template = ImageUtils.read_image(f"{Message._REPLY_ASSETS}/{name}.png")
            if template is None:
                continue
            for scale in (1.0, 1.2, 1.5):
                matches = ImageUtils.scale_and_match_template_with_multiple_targets(pixels, template, 0.92, scale)
                if matches:
                    # 文字从上到下，表情从左到右，只点识别到的第一个。
                    pos = min(matches, key=lambda box: (box[0][1], box[0][0]) if name == "message_reply" else box[0][0])
                    (x, y), (right, bottom) = pos
                    box = ((x, y), (right, y), (right, bottom), (x, bottom))
                    return auto.click_element_with_pos(auto.calculate_text_position(box, False), offset=offset)
        return False

    def _finish(self, pending_crop):
        deadline = time.monotonic() + 65
        settled_frames = 0
        while time.monotonic() < deadline:
            if auto.find_element("获得物品", "text", crop=ITEM_POPUP):
                log.info("已领取短信奖励")
                close_item_reward()
                return True
            if auto.find_element(self._PENDING_THREAD, "image", 0.8, crop=pending_crop):
                settled_frames = 0
                if self._reply():
                    time.sleep(0.7)
            else:
                settled_frames += 1
                if settled_frames >= 3:
                    log.info("短信会话已结束，未出现奖励弹窗")
                    return False
            time.sleep(0.7)
        return None

    def run(self):
        drags = completed = received = 0
        timed_out_rows = set()
        try:
            for _ in range(30):
                pending = auto.find_element(self._PENDING_THREAD, "image", 0.8, crop=self._NOTIFY_LIST_CROP)
                if pending and pending[0][1] not in timed_out_rows:
                    pos = pending
                elif timed_out_rows:
                    unread = auto.find_element(self._UNREAD_MARK, "image_with_multiple_targets", 0.82,
                                               crop=self._NOTIFY_LIST_CROP) or []
                    pos = next((box for box in unread if all(abs(box[0][1] - y) > 24 for y in timed_out_rows)), None)
                else:
                    pos = auto.find_element(self._UNREAD_MARK, "image", 0.82, crop=self._NOTIFY_LIST_CROP)

                if not pos:
                    if drags >= 4:
                        break
                    if not drag_list(auto, (700 / 1920, 820 / 1080), (700 / 1920, 430 / 1080), crop=self._LIST, duration=0.8):
                        raise RewardError("短信列表拖动后未稳定")
                    drags += 1
                    continue
                if not auto.click_element_with_pos(pos):
                    raise RewardError("未读会话无法打开")
                (left, top), (right, bottom) = pos
                width, height = right - left, bottom - top
                pending_crop = auto.calculate_crop_with_pos((left - width, top - height), (width * 4, height * 4))
                result = self._finish(pending_crop)
                if result is None:
                    log.warning("短信会话超时，尝试返回列表继续其他会话")
                    timed_out_rows.add(top)
                    screen.change_to("menu", max_recursion=0)
                    screen.change_to("incoming_message", max_recursion=0)
                else:
                    completed += 1
                    received += result
                drags = 0
        finally:
            if received:
                Base.send_notification_with_screenshot(f"处理了 {completed} 个短信会话，领取 {received} 次奖励", NotificationLevel.ALL)
        log.info(f"本次已处理 {completed} 个短信会话" if completed else "本次未发现已完成会话")
        if timed_out_rows:
            raise RewardError(f"有 {len(timed_out_rows)} 个短信会话超时")
