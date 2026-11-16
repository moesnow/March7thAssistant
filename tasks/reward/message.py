import time

from module.automation import auto
from module.logger import log
from module.screen import screen
from tasks.base.list_drag import drag_list
from .receipt import ITEM_POPUP, RewardError, close_item_reward, notify_reward
from .rewardtemplate import RewardTemplate
from .sms import close_sms_receipt, find_thread_title, first_unblocked_thread


class Message(RewardTemplate):
    _LIST = (300 / 1920, 252 / 1080, 435 / 1920, 635 / 1080)
    _NOTIFY_LIST_CROP = (323 / 1920, 257 / 1080, 100 / 1920, 632 / 1080)
    _UNREAD_MARK = "./assets/images/share/base/RedExclamationMark.png"
    _PENDING_THREAD = "./assets/images/share/reward/message/unread_incoming_message_icon.png"
    _REPLY_CROP = (0.38, 0.60, 0.54, 0.29)
    _REPLY_ASSETS = "./assets/touch_720/images/reward"

    @staticmethod
    def _reply():
        auto.take_screenshot(crop=Message._REPLY_CROP)
        for name, offset, axis in (("message_reply", (0, 0), 1), ("message_sticker", (83, 93), 0)):
            for scale in (1.0, 1.2, 1.5):
                matches = auto.find_element(
                    f"{Message._REPLY_ASSETS}/{name}.png", "image_with_multiple_targets", 0.92,
                    take_screenshot=False, scale_range=scale,
                )
                if matches:
                    # 文字从上到下，表情从左到右，只点识别到的第一个。
                    first = min(matches, key=lambda box: (box[0][axis], box[0][1 - axis]))
                    return auto.click_element_with_pos(first, offset=offset)
        return False

    def _finish(self, pending_crop):
        deadline = time.monotonic() + 65
        settled_frames = 0
        while time.monotonic() < deadline:
            if auto.find_element("获得物品", "text", crop=ITEM_POPUP):
                log.info("已领取短信奖励")
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

    @staticmethod
    def _receipt_visible():
        auto.take_screenshot(crop=ITEM_POPUP)
        auto.perform_ocr(raise_on_error=True)
        return auto.find_element("获得物品", "text", take_screenshot=False, need_ocr=False)

    def run(self):
        drags = completed = received = timed_out = 0
        timed_out_titles = set()
        try:
            for _ in range(30):
                if timed_out_titles:
                    pos = first_unblocked_thread(
                        auto, self._LIST, self._NOTIFY_LIST_CROP,
                        ((self._PENDING_THREAD, 0.8), (self._UNREAD_MARK, 0.82)), timed_out_titles,
                    )
                else:
                    pos = (auto.find_element(self._PENDING_THREAD, "image", 0.8, crop=self._NOTIFY_LIST_CROP)
                           or auto.find_element(self._UNREAD_MARK, "image", 0.82, crop=self._NOTIFY_LIST_CROP))

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
                    timed_out += 1
                    title = find_thread_title(auto, self._LIST, pending_crop, self._PENDING_THREAD, 0.8)
                    log.warning("短信会话超时，尝试返回列表继续其他会话")
                    screen.change_to("menu", max_recursion=0)
                    screen.change_to("incoming_message", max_recursion=0)
                    if not title:
                        log.warning("未识别超时会话标题，停止本次短信处理")
                        break
                    timed_out_titles.add(title)
                else:
                    completed += 1
                    received += result
                    if result and not close_sms_receipt(close_item_reward, self._receipt_visible):
                        log.warning("已确认短信奖励到账，弹窗仍未关闭，停止本次短信处理")
                        break
                drags = 0
        finally:
            if received:
                notify_reward(auto, f"处理了 {completed} 个短信会话，领取 {received} 次奖励")
        log.info(f"本次已处理 {completed} 个短信会话" if completed else "本次未发现已完成会话")
        if timed_out:
            raise RewardError(f"有 {timed_out} 个短信会话超时")
