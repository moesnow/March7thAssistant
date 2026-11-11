from module.automation import auto
from module.logger import log
from .receipt import RewardError, close_item_reward, confirm_item_reward
from .rewardtemplate import RewardTemplate


class Dispatch(RewardTemplate):
    def run(self):
        if auto.click_element("领取奖励", "text", max_retries=5, retry_delay=0.3,
                              crop=(1194 / 1920, 866 / 1080, 610 / 1920, 156 / 1080)):
            confirm_item_reward("委托奖励")
            close_item_reward()
            return True
        if auto.find_element(("委托正在进行中", "委托派遣中", "每小时可持续获得奖励", "未派遣"), "text",
                             include=True, crop=(1180 / 1920, 355 / 1080, 671 / 1920, 670 / 1080)):
            log.info("委托暂无可领取奖励")
            return False
        raise RewardError("未确认委托奖励状态")
