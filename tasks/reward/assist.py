from module.automation import auto
from .rewardtemplate import RewardTemplate
import time

class Assist(RewardTemplate):
    def run(self):
        if auto.click_element("./assets/images/share/reward/assist/gift.png", "image", 0.9):
            time.sleep(1)
            auto.press_key("esc")
