from managers.logger import logger
from managers.screen import screen
from managers.config import config
from managers.automation import auto
from .mail import Mail
from .assist import Assist
from .dispatch import Dispatch
from .quest import Quest
from .srpass import SRPass


class RewardManager:
    def __init__(self):
        self.assist = Assist("支援", config.reward_assist_enable, "visa")
        self.mail = Mail("邮件", config.reward_mail_enable, "mail")
        self.dispatch = Dispatch("委托", config.reward_dispatch_enable, "dispatch")
        self.quest = Quest("每日实训", config.reward_quest_enable, "guide2")
        self.srpass = SRPass("无名勋礼", config.reward_srpass_enable, "pass2")
        self.crop = (1263.0 / 1920, 52.0 / 1080, 642.0 / 1920, 982.0 / 1080)

    def check_and_collect_rewards(self):
        logger.hr("开始领奖励", 0)

        reward_mapping = {
            self.mail: ("./assets/images/share/menu/mail_reward.png", 0.9),
            self.assist: ("./assets/images/share/menu/assist_reward.png", 0.9),
            self.dispatch: ("./assets/images/share/menu/dispatch_reward.png", 0.95),
            self.quest: ("./assets/images/share/menu/quest_reward.png", 0.95),
            self.srpass: ("./assets/images/share/menu/pass_reward.png", 0.95)
        }

        flag = False
        for instance, (image_path, confidence) in reward_mapping.items():
            if self._find_reward(image_path, confidence):
                flag = True
                instance.start()

        if not flag:
            logger.info("未检测到任何奖励")

        logger.hr("完成", 2)

    def _find_reward(self, image_path, confidence):
        screen.change_to('menu')
        return auto.find_element(image_path, "image", confidence, crop=self.crop)


def start():
    if not config.reward_enable:
        logger.info("领奖励未开启")
        return

    reward_manager = RewardManager()
    reward_manager.check_and_collect_rewards()
