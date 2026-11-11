from module.automation import auto
from module.config import cfg
from module.logger import log
from module.screen import screen
from tasks.base.task_steps import run_steps
from .achievement import Achievement
from .assist import Assist
from .dispatch import Dispatch
from .mail import Mail
from .menu_alert import menu_alert
from .message import Message
from .quest import Quest
from .srpass import SRPass


class RewardManager:
    def __init__(self):
        self.reward_instances = {
            "dispatch": Dispatch("委托", cfg.reward_dispatch_enable, "dispatch"),
            "mail": Mail("邮件", cfg.reward_mail_enable, "mail"),
            "assist": Assist("支援礼盒", cfg.reward_assist_enable, "visa"),
            "srpass": SRPass("无名勋礼", cfg.reward_srpass_enable, "pass2"),
            "message": Message("短信", cfg.reward_message_enable, "incoming_message"),
            "achievement": Achievement("成就", cfg.reward_achievement_enable, "achievement"),
            "quest": Quest("每日实训", cfg.reward_quest_enable, "guide2"),
        }

    def check_and_collect_rewards(self):
        log.hr("开始领取奖励", 0)

        def collect(key):
            # 领取结果的 False 表示页内确认暂无奖励；无法确认时由任务抛出异常。
            self.check_and_collect_specific_reward(key)

        return run_steps(
            (self.reward_instances[key].name, lambda key=key: collect(key))
            for key in ("dispatch", "mail", "assist", "srpass", "message", "achievement")
            if self.reward_instances[key].enabled
        )

    def check_and_collect_specific_reward(self, reward_type):
        instance = self.reward_instances.get(reward_type)
        if not instance or not instance.enabled:
            return False
        if reward_type == "mail":
            screen.change_to("menu")
            if menu_alert(auto, (0.925, 0.185, 0.075, 0.15), "./assets/images/share/menu/mail.png") is False:
                log.info("已确认邮件图标无红点")
                return False
        elif reward_type == "assist":
            screen.change_to("menu")
            if menu_alert(auto, (0.87, 0.055, 0.13, 0.15), "./assets/images/share/menu/more.png") is False:
                log.info("已确认更多菜单无红点")
                return False
        elif reward_type == "achievement":
            screen.change_to("menu")
            if not auto.find_element("./assets/images/share/menu/achievement_reward.png", "image", 2000000,
                                     crop=(1263 / 1920, 52 / 1080, 642 / 1920, 982 / 1080)):
                return False
        return instance.start()


def start():
    if not cfg.reward_enable:
        log.info("领取奖励未开启")
        return True
    return RewardManager().check_and_collect_rewards()


def start_specific(reward_type):
    if not cfg.reward_enable:
        return False
    return RewardManager().check_and_collect_specific_reward(reward_type)
