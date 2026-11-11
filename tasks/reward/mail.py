from module.automation import auto
from module.logger import log
from .receipt import RewardError, close_item_reward, confirm_item_reward
from .rewardtemplate import RewardTemplate


class Mail(RewardTemplate):
    def run(self):
        if auto.click_element("./assets/images/zh_CN/reward/mail/receive_all.png", "image", 0.86, max_retries=4, retry_delay=0.3):
            confirm_item_reward("邮件奖励", notify=True)
            close_item_reward()
            return True
        if auto.find_element(("全部领取", "暂无邮件", "没有邮件"), "text", include=True, max_retries=3, retry_delay=0.3):
            log.info("邮箱暂无可领取附件")
            return False
        raise RewardError("未确认邮箱可领附件状态")
