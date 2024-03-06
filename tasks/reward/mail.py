from managers.automation import auto
from .rewardtemplate import RewardTemplate


class Mail(RewardTemplate):
    def run(self):
        if auto.click_element("./assets/images/zh_CN/reward/mail/receive_all.png", "image", 0.8):
            auto.click_element("./assets/images/zh_CN/base/click_close.png", "image", 0.8, max_retries=10)
