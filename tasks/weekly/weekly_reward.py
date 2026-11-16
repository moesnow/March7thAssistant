"""周期奖励领取时处理助燃券满额提示。"""

import time

from module.automation import auto
from module.logger import log
from utils.screenshot_util import save_error_screenshot


REWARD_CLOSE = "./assets/images/zh_CN/base/click_close.png"
ONE_KEY_RECEIVE = "./assets/images/zh_CN/universe/one_key_receive.png"
# Issue #1260 截图中的提示正文与左下角按钮，使用窗口相对坐标。
LIMIT_MESSAGE_CROP = (0.20, 0.30, 0.60, 0.30)
CLEANUP_BUTTON_CROP = (0.28, 0.61, 0.22, 0.09)


def _fuel_ticket_limit_visible():
    auto.take_screenshot(LIMIT_MESSAGE_CROP)
    auto.perform_ocr()
    # 物品名称可能单独成框，提示也可能换行；只拼接本弹窗的正文。
    text = "".join("".join(value.split()) for _, (value, _) in auto.ocr_result)
    return "背包内助燃券持有数量已达上限" in text


def wait_for_weekly_reward():
    """各阶段最多检测十次，最多清理一次、重新领取一次。"""
    cleaned = False
    retried = False
    reason = "等待周期奖励展示超时"
    remaining_checks = 10
    while remaining_checks > 0:
        remaining_checks -= 1
        if auto.find_element(REWARD_CLOSE, "image", 0.8):
            return True

        if _fuel_ticket_limit_visible():
            if not cleaned:
                log.info("助燃券持有数量已达上限，尝试清理后继续领取周期奖励")
                if not auto.click_element("清理", "text", crop=CLEANUP_BUTTON_CROP, include=False):
                    reason = "助燃券满额提示中未找到或无法点击清理按钮"
                    break
                cleaned = True
                # 清理发起新的界面转换，不复用弹窗出现前消耗的等待次数。
                remaining_checks = 10
            reason = "清理助燃券后满额提示仍未消失"
        elif cleaned:
            reason = "清理助燃券后未出现周期奖励展示"
            # 清理可能自动完成领取；只有返回领取页才重试，避免盲点确认。
            if not retried and auto.click_element(ONE_KEY_RECEIVE, "image", 0.9):
                retried = True
                remaining_checks = 10

        time.sleep(1)

    log.warning(reason)
    save_error_screenshot(log)
    return False
