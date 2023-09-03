from managers.logger_manager import logger
from managers.config_manager import config
from managers.screen_manager import screen
from managers.translate_manager import _
from tasks.base.date import Date
from tasks.reward.mail import Mail
from tasks.reward.assist import Assist
from tasks.daily.photo import Photo
from tasks.daily.fight import Fight
from tasks.weekly.universe import Universe
from tasks.reward.dispatch import Dispatch
from tasks.reward.quest import Quest
from tasks.reward.srpass import SRPass
from tasks.daily.synthesis import Synthesis
from tasks.weekly.forgottenhall import ForgottenHall
from tasks.power.power import Power
from tasks.daily.tasks import Tasks


class Daily:
    @staticmethod
    def start():
        logger.hr(_("开始日常任务"), 0)
        if Date.is_next_4_am(config.last_run_timestamp):
            screen.change_to("guide2")
            tasks = Tasks("./assets/config/task_mappings.json")
            tasks.start()

            config.set_value("daily_tasks", tasks.daily_tasks)
            config.save_timestamp("last_run_timestamp")

        task_functions = {
            "拍照1次": lambda: Photo.photograph(),
            "合成1次消耗品": lambda: Synthesis.consumables(),
            "合成1次材料": lambda: Synthesis.material(),
            "使用1件消耗品": lambda: Synthesis.use_consumables(),
            "完成1次「拟造花萼（金）」": lambda: Power.instance("拟造花萼（金）", config.instance_names["拟造花萼（金）"], 10, 1),
            "完成1次「拟造花萼（赤）」": lambda: Power.instance("拟造花萼（赤）", config.instance_names["拟造花萼（赤）"], 10, 1),
            "完成1次「凝滞虚影」": lambda: Power.instance("凝滞虚影", config.instance_names["凝滞虚影"], 30, 1),
            "完成1次「侵蚀隧洞」": lambda: Power.instance("侵蚀隧洞", config.instance_names["侵蚀隧洞"], 40, 1),
            "完成1次「历战余响」": lambda: Power.instance("历战余响", config.instance_names["历战余响"], 30, 1),
            "完成1次「忘却之庭」": lambda: ForgottenHall.start_daily(),
        }
        logger.hr(_("今日实训"), 2)
        for key, value in config.daily_tasks.items():
            if value:
                logger.info(f"{key}: {value}")

        for task_name, task_function in task_functions.items():
            if config.daily_tasks[task_name]:
                if task_function():
                    config.daily_tasks[task_name] = False
                    config.save_config()

        Power.start()

        if Date.is_next_4_am(config.fight_timestamp):
            if config.fight_enable:
                Fight.start()
            else:
                logger.debug(_("锄大地未开启"))

        if Date.is_next_mon_4_am(config.universe_timestamp):
            if config.universe_enable:
                Power.start()
                Daily.get_reward()
                Universe.start()
                Power.start()
            else:
                logger.debug(_("模拟宇宙未开启"))

        if Date.is_next_mon_4_am(config.forgottenhall_timestamp):
            if config.forgottenhall_enable:
                ForgottenHall.start()
            else:
                logger.debug(_("忘却之庭未开启"))

        Daily.get_reward()

        logger.hr(_("完成"), 2)

    @staticmethod
    def get_reward():
        Mail.get_reward()
        Assist.get_reward()
        Dispatch.get_reward()
        Quest.get_reward()
        SRPass.get_reward()
