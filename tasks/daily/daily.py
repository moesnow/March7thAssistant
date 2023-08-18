from managers.logger_manager import logger
from managers.config_manager import config
from managers.translate_manager import _
from tasks.base.date import Date
from tasks.daily.mail import Mail
from tasks.daily.assist import Assist
from tasks.daily.photo import Photo
from tasks.daily.fight import Fight
from tasks.daily.universe import Universe
from tasks.daily.dispatch import Dispatch
from tasks.daily.quest import Quest
from tasks.daily.srpass import SRPass
from tasks.daily.synthesis import Synthesis
from tasks.daily.forgottenhall import ForgottenHall


class Daily:
    @staticmethod
    def start():
        logger.hr(_("开始日常任务"), 0)
        if Date.is_next_4_am(config.last_run_timestamp):
            Mail.get_reward()
            Assist.get_reward()
            Photo.photograph()
            Synthesis.start()
            config.save_timestamp("last_run_timestamp")

        if Date.is_next_4_am(config.fight_timestamp):
            Fight.start()
            config.save_timestamp("fight_timestamp")

        if Date.is_next_mon_4_am(config.universe_timestamp):
            Universe.start()
            config.save_timestamp("universe_timestamp")

        if Date.is_next_mon_4_am(config.forgottenhall_timestamp):
            ForgottenHall.start()
            config.save_timestamp("forgottenhall_timestamp")

        Dispatch.get_reward()
        Quest.get_reward()
        SRPass.get_reward()

        logger.hr(_("完成"), 2)
