from module.automation import auto
from module.logger import log
from .receipt import RewardError, close_item_reward, confirm_item_reward
from .rewardtemplate import RewardTemplate


class Assist(RewardTemplate):
    def run(self):
        header = (0.50, 0.13, 0.47, 0.12)
        if not auto.find_element("支援角色", "text", crop=header):
            if auto.click_element("角色展示", "text", crop=(0.38, 0.03, 0.25, 0.10), max_retries=3, retry_delay=0.3):
                if not auto.find_element("支援角色", "text", crop=header, max_retries=4, retry_delay=0.3):
                    raise RewardError("未确认支援角色展示页")
            else:
                raise RewardError("未找到支援角色展示页")
        if not auto.click_element("./assets/images/share/reward/assist/gift.png", "image", 0.9, crop=header):
            log.info("暂无支援礼盒")
            return False
        confirm_item_reward("支援礼盒")
        close_item_reward()
        return True
