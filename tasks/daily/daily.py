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
from tasks.weekly.echoofwar import Echoofwar
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
        else:
            logger.info(_("日常任务尚未刷新"))

        if len(config.daily_tasks) > 0:
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
            count = 0
            for key, value in config.daily_tasks.items():
                state = "\033[91m"+_("待完成")+"\033[0m" if value else "\033[92m"+_("已完成")+"\033[0m"
                logger.info(f"{key}: {state}")
                count = count + 1 if not value else count
            # logger.info(_("已完成：{count}/{total}").format(count=count, total=len(config.daily_tasks)))
            logger.info(_("已完成：{count_total}").format(count_total=f"\033[93m{count}/{len(config.daily_tasks)}\033[0m"))

            for task_name, task_function in task_functions.items():
                if task_name in config.daily_tasks and config.daily_tasks[task_name]:
                    if task_function():
                        config.daily_tasks[task_name] = False
                        config.save_config()

        logger.hr(_("完成"), 2)

        if Date.is_next_mon_4_am(config.echo_of_war_timestamp):
            if config.echo_of_war_enable:
                Echoofwar.start()
            else:
                logger.info(_("历战余响未开启"))
        else:
            logger.info(_("历战余响尚未刷新"))

        Power.start()

        if Date.is_next_4_am(config.fight_timestamp):
            if config.fight_enable:
                Fight.start()
            else:
                logger.info(_("锄大地未开启"))
        else:
            logger.info(_("锄大地尚未刷新"))

        if Date.is_next_mon_4_am(config.universe_timestamp):
            if config.universe_enable:
                Power.start()
                Daily.get_reward()
                Universe.start(get_reward=True)
                Power.start()
            else:
                logger.info(_("模拟宇宙未开启"))
        else:
            logger.info(_("模拟宇宙尚未刷新"))

        if Date.is_next_mon_4_am(config.forgottenhall_timestamp):
            if config.forgottenhall_enable:
                ForgottenHall.start()
            else:
                logger.info(_("忘却之庭未开启"))
        else:
            logger.info(_("忘却之庭尚未刷新"))

        Daily.get_reward()


    @staticmethod
    def get_reward():
        logger.hr(_("开始领奖励"), 0)
        Mail.get_reward()
        Assist.get_reward()
        Dispatch.get_reward()
        Quest.get_reward()
        SRPass.get_reward()
        logger.hr(_("完成"), 2)
