from module.automation import auto
from module.logger import log
from module.notification.notification import NotificationLevel
from tasks.base.base import Base


class RewardError(RuntimeError):
    """未能确认领取或奖励页面状态。"""


ITEM_POPUP = (0.38, 0.055, 0.24, 0.14)


def confirm_item_reward(message, *, notify=False):
    if not auto.find_element("获得物品", "text", crop=ITEM_POPUP, max_retries=10, retry_delay=0.3):
        raise RewardError(f"{message}领取结果未确认（未出现获得物品）")
    log.info(f"已领取{message}")
    if notify:
        Base.send_notification_with_screenshot(f"{message}已领取", NotificationLevel.ALL)


def close_item_reward():
    if not auto.click_element("./assets/images/zh_CN/base/click_close.png", "image", 0.8, max_retries=4, retry_delay=0.3):
        log.warning("已确认到账，获得物品弹窗仍未关闭")
        return False
    return True
