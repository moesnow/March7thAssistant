from managers.logger_manager import logger
from managers.config_manager import config
from managers.translate_manager import _
from tasks.base.date import Date
from tasks.reward.mail import Mail
from tasks.power.power import Power
from tasks.reward.assist import Assist
from tasks.daily.photo import Photo
from tasks.daily.fight import Fight
from tasks.weekly.universe import Universe
from tasks.reward.dispatch import Dispatch
from tasks.reward.quest import Quest
from tasks.reward.srpass import SRPass
from tasks.daily.synthesis import Synthesis
from tasks.weekly.forgottenhall import ForgottenHall


class Daily:
    @staticmethod
    def start():
        logger.hr(_("开始日常任务"), 0)
        if Date.is_next_4_am(config.last_run_timestamp):
            Photo.photograph()
            Synthesis.start()
            config.save_timestamp("last_run_timestamp")

        if Date.is_next_4_am(config.fight_timestamp):
            Fight.start()
            config.save_timestamp("fight_timestamp")

        if Date.is_next_mon_4_am(config.universe_timestamp):
            Power.start()
            Universe.start()
            config.save_timestamp("universe_timestamp")
            Power.start()

        if Date.is_next_mon_4_am(config.forgottenhall_timestamp):
            ForgottenHall.start()
            config.save_timestamp("forgottenhall_timestamp")

        Mail.get_reward()
        Assist.get_reward()
        Dispatch.get_reward()
        Quest.get_reward()
        SRPass.get_reward()

        logger.hr(_("完成"), 2)
