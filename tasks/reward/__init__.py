from managers.logger_manager import logger
from managers.screen_manager import screen
from managers.config_manager import config
from managers.automation_manager import auto
from managers.translate_manager import _
from tasks.reward.mail import Mail
from tasks.reward.assist import Assist
from tasks.reward.dispatch import Dispatch
from tasks.reward.quest import Quest
from tasks.reward.srpass import SRPass


class RewardManager:
    def __init__(self):
        self.assist = Assist("支援", config.reward_assist_enable, "visa")
        self.mail = Mail("邮件", config.reward_mail_enable, "mail")
        self.dispatch = Dispatch("委托", config.reward_dispatch_enable, "dispatch")
        self.quest = Quest("每日实训", config.reward_quest_enable, "guide2")
        self.srpass = SRPass("无名勋礼", config.reward_srpass_enable, "pass2")

    def check_and_collect_rewards(self):
        logger.hr(_("开始领奖励"), 0)

        reward_mapping = {
            "mail": (self.mail, "./assets/images/menu/mail_reward.png", 0.9),
            "assist": (self.assist, "./assets/images/menu/assist_reward.png", 0.9),
            "dispatch": (self.dispatch, "./assets/images/menu/dispatch_reward.png", 0.95),
            "quest": (self.quest, "./assets/images/menu/quest_reward.png", 0.95),
            "srpass": (self.srpass, "./assets/images/menu/pass_reward.png", 0.95)
        }

        flag = False
        for reward, (instance, image_path, confidence) in reward_mapping.items():
            if self._find_reward(image_path, confidence):
                flag = True
                instance.start()

        if not flag:
            logger.info(_("未检测到任何奖励"))

        logger.hr(_("完成"), 2)

    def _find_reward(self, image_path, confidence):
        screen.change_to('menu')
        return auto.find_element(image_path, "image", confidence)


def start():
    if not config.reward_enable:
        logger.info(_("领奖励未开启"))
        return

    reward_manager = RewardManager()
    reward_manager.check_and_collect_rewards()
