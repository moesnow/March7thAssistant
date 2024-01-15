from managers.automation_manager import auto
from managers.translate_manager import _
from .rewardtemplate import RewardTemplate


class Assist(RewardTemplate):
    def run(self):
        if auto.click_element("./assets/images/share/reward/assist/gift.png", "image", 0.9):
            auto.click_element("./assets/images/zh_CN/base/click_close.png", "image", 0.9, max_retries=10)
