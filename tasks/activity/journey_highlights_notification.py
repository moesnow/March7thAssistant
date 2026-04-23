import time
import cv2
import numpy as np
from PIL import Image
from module.logger import log
from module.screen import screen
from tasks.base.base import Base
from module.automation import auto
from module.notification.notification import NotificationLevel


def take_journey_highlights_screenshot():
    frames = []
    anchor_template = None

    screen.change_to("reward_guide")
    time.sleep(1.0)

    for _ in range(3):
        img, _, _ = auto.take_screenshot((375 / 1920, 300 / 1080, 1260 / 1920, 650 / 1080))
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        if anchor_template is not None:
            search_region = frame[: int(frame.shape[0] * 0.8), :]
            result = cv2.matchTemplate(search_region, anchor_template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val < 0.85:
                log.debug("锚点匹配失败，已到底部或丢失，停止滚动")
                break

            new_content_top = max_loc[1] + anchor_template.shape[0]
            frames.append(frame[new_content_top:, :])
        else:
            frames.append(frame)

        anchor_template = frame[frame.shape[0] - 80 :, :]

        auto.click_element((0, 0, 1, 1), "crop")
        auto.mouse_scroll(12)
        time.sleep(1.0)

    if not frames:
        return None

    stitched = np.vstack(frames)
    return Image.fromarray(cv2.cvtColor(stitched, cv2.COLOR_BGR2RGB))


def send_journey_highlights_notification():
    try:
        if screenshot := take_journey_highlights_screenshot():
            Base.send_notification_with_screenshot("活动日历提醒", NotificationLevel.ALL, screenshot=screenshot)
        else:
            log.warning("未能成功获取活动热点截图")
    except Exception as e:
        log.warning(f"获取奖励指南截图 过程中发生错误: {e}")
