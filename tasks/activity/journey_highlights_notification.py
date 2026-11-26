import time
import cv2
import numpy as np
from PIL import Image
from module.logger import log
from module.screen import screen
from tasks.base.base import Base
from module.automation import auto
from tasks.base.list_drag import drag_list
from module.notification.notification import NotificationLevel


HEADER_CROP = (375 / 1920, 142 / 1080, 1460 / 1920, 193 / 1080)
LIST_CROP = (375 / 1920, 335 / 1080, 1460 / 1920, 655 / 1080)
MAX_SCROLLS = 8


def take_journey_highlights_screenshot():
    anchor_template = None

    screen.change_to("reward_guide")
    time.sleep(1.0)

    # 奖励总览固定在顶部，只拼接一次；下方列表单独滚动。
    header, _, _ = auto.take_screenshot(HEADER_CROP)
    frames = [np.array(header)]

    for page in range(MAX_SCROLLS + 1):
        img, _, _ = auto.take_screenshot(LIST_CROP)
        frame = np.array(img)

        if anchor_template is not None:
            # 到底前可能只移动很短一段，锚点也可能仍在画面下方。
            result = cv2.matchTemplate(frame, anchor_template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val < 0.85:
                log.warning("活动日历截图拼接失败，跳过本次提醒")
                return None

            new_content_top = max_loc[1] + anchor_template.shape[0]
            if new_content_top >= frame.shape[0]:
                break
            frames.append(frame[new_content_top:, :])
        else:
            frames.append(frame)

        anchor_template = frame[frame.shape[0] - 80 :, :]

        if page == MAX_SCROLLS:
            log.warning("活动日历滚动次数已达上限，未能获取完整截图，跳过本次提醒")
            return None

        if not drag_list(auto, (1370 / 1920, 850 / 1080), (1370 / 1920, 490 / 1080),
                         crop=LIST_CROP, duration=1.2):
            return None
        time.sleep(1.0)

    stitched = np.vstack(frames)
    return Image.fromarray(stitched)


def send_journey_highlights_notification():
    try:
        if screenshot := take_journey_highlights_screenshot():
            Base.send_notification_with_screenshot("活动日历提醒", NotificationLevel.ALL, screenshot=screenshot)
        else:
            log.warning("未能成功获取活动热点截图")
    except Exception as e:
        log.warning(f"获取奖励指南截图 过程中发生错误: {e}")
