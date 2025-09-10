from module.logger import log
from module.screen import screen
from module.config import cfg
from module.automation import auto
from .mail import Mail
from .assist import Assist
from .dispatch import Dispatch
from .quest import Quest
from .srpass import SRPass


class RewardManager:
    def __init__(self):
        self.assist = Assist("支援", cfg.reward_assist_enable, "visa")
        self.mail = Mail("邮件", cfg.reward_mail_enable, "mail")
        self.dispatch = Dispatch("委托", cfg.reward_dispatch_enable, "dispatch")
        self.quest = Quest("每日实训", cfg.reward_quest_enable, "guide2")
        self.srpass = SRPass("无名勋礼", cfg.reward_srpass_enable, "pass2")
        self.crop = (1263.0 / 1920, 52.0 / 1080, 642.0 / 1920, 982.0 / 1080)

        self.reward_instances = {
            "mail": self.mail,
            "assist": self.assist,
            "dispatch": self.dispatch,
            "quest": self.quest,
            "srpass": self.srpass,
        }

        self.reward_mapping = {
            "mail": ("./assets/images/share/menu/mail_reward.png", 3000000, (1823.0 / 1920, 224.0 / 1080, 91.0 / 1920, 92.0 / 1080)),
            "assist": ("./assets/images/share/menu/assist_reward.png", 2000000, self.crop),
            "dispatch": ("./assets/images/share/menu/dispatch_reward.png", 2000000, self.crop),
            "quest": ("./assets/images/share/menu/quest_reward.png", 2000000, self.crop),
            "srpass": ("./assets/images/share/menu/pass_reward.png", 2000000, self.crop),
        }

    def check_and_collect_rewards(self):
        log.hr("开始领取奖励", 0)

        for reward_type, (image_path, confidence, crop) in self.reward_mapping.items():
            if self._find_reward(image_path, confidence, crop):
                self.reward_instances[reward_type].start()
            else:
                reward_name = self._get_reward_name(reward_type)
                log.info(f"未检测到{reward_name}奖励")

        log.hr("完成", 2)

    def check_and_collect_specific_reward(self, reward_type):
        reward_name = self._get_reward_name(reward_type)
        log.hr(f"开始领取{reward_name}奖励", 0)

        if reward_type in self.reward_mapping:
            image_path, confidence, crop = self.reward_mapping[reward_type]
            if self._find_reward(image_path, confidence, crop):
                self.reward_instances[reward_type].start()
            else:
                log.info(f"未检测到{reward_name}奖励")
        else:
            log.error(f"未知的奖励类型: {reward_type}")

        log.hr("完成", 2)

    def _get_reward_name(self, reward_type):
        instance = self.reward_instances.get(reward_type)
        return instance.name if instance else "未知"

    def _find_reward(self, image_path, confidence, crop):
        screen.change_to('menu')
        return auto.find_element(image_path, "image", confidence, crop=crop)


def start():
    if not cfg.reward_enable:
        log.info("领取奖励未开启")
        return

    reward_manager = RewardManager()
    reward_manager.check_and_collect_rewards()


def start_specific(reward_type):
    if not cfg.reward_enable:
        log.info("领取奖励未开启")
        return

    reward_manager = RewardManager()
    reward_manager.check_and_collect_specific_reward(reward_type)
