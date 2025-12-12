from module.automation import auto
from .rewardtemplate import RewardTemplate
import time
from tasks.base.base import Base
from module.notification.notification import NotificationLevel


class Mail(RewardTemplate):
    def run(self):
        if auto.click_element("./assets/images/zh_CN/reward/mail/receive_all.png", "image", 0.8):
            time.sleep(2)
            Base.send_notification_with_screenshot("邮件奖励已领取", level=NotificationLevel.ALL)
            auto.click_element("./assets/images/zh_CN/base/click_close.png", "image", 0.8, max_retries=10)
