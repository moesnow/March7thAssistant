from module.automation import auto
from .rewardtemplate import RewardTemplate
import time


class Achievement(RewardTemplate):
    def run(self):
        auto.click_element(
            './assets/images/zh_CN/reward/achievement/one_key_receive.png', 'image', 0.8
        )
        time.sleep(3.0)
        auto.click_element(
            './assets/images/zh_CN/base/confirm.png', 'image', 0.9, max_retries=10
        )
        time.sleep(0.5)
        auto.click_element(
            './assets/images/zh_CN/base/click_close.png', 'image', 0.8, max_retries=10
        )
