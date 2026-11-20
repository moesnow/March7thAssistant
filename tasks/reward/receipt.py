from module.automation import auto
from module.automation.automation import screenshot_retry_timeout
from module.logger import log
from module.notification import notif
from module.notification.notification import NotificationLevel
from tasks.base.base import Base
from tasks.base.task_steps import optional_reward


class RewardError(RuntimeError):
    """未能确认领取或奖励页面状态。"""


# 标题位于物品图标下方，委托到账画面中占到高度的约 22%。
ITEM_POPUP = (0.38, 0.055, 0.24, 0.205)


def confirm_item_reward(message, *, notify=False):
    if not auto.find_element("获得物品", "text", crop=ITEM_POPUP, max_retries=10, retry_delay=0.3):
        raise RewardError(f"{message}领取结果未确认（未出现获得物品）")
    log.info(f"已领取{message}")
    if notify:
        notify_reward(auto, f"{message}已领取")


def notify_reward(automation, message, *, crop=(0, 0, 1, 1)):
    """到账已确认，通知图片只做一次尽力截取。"""
    screenshot = None
    with optional_reward("已确认奖励到账，通知截图"):
        with screenshot_retry_timeout(0):
            screenshot, _, _ = automation.take_screenshot(crop=crop)
    with optional_reward("已确认到账的奖励通知"):
        if screenshot is not None:
            Base.send_notification_with_screenshot(message, NotificationLevel.ALL, screenshot=screenshot)
        else:
            log.info(message)
            notif.notify(content=message, level=NotificationLevel.ALL)


def close_item_reward():
    with optional_reward("奖励到账后的弹窗收尾"):
        if auto.click_element("./assets/images/zh_CN/base/click_close.png", "image", 0.8, max_retries=4, retry_delay=0.3):
            return True
        log.warning("已确认到账，获得物品弹窗仍未关闭")
    return False
