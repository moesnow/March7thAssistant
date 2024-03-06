from managers.logger import logger
from managers.config import config
from managers.screen import screen
from utils.date import Date
from tasks.daily.photo import Photo
from tasks.daily.fight import Fight
from tasks.weekly.universe import Universe
import tasks.reward as reward
from tasks.daily.synthesis import Synthesis
import tasks.challenge as challenge
from tasks.power.power import Power
from tasks.daily.tasks import Tasks
from tasks.daily.himekotry import HimekoTry
from tasks.weekly.echoofwar import Echoofwar
from utils.color import red, green, yellow


class Daily:
    @staticmethod
    def start():
        if config.daily_enable:
            Daily.run()

        # 优先历战余响
        if Date.is_next_mon_x_am(config.echo_of_war_timestamp, config.refresh_hour):
            if config.echo_of_war_enable:
                Echoofwar.start()
            else:
                logger.info("历战余响未开启")
        else:
            logger.info("历战余响尚未刷新")

        Power.run()

        if Date.is_next_x_am(config.fight_timestamp, config.refresh_hour):
            if config.fight_enable:
                Fight.start()
            else:
                logger.info("锄大地未开启")
        else:
            logger.info("锄大地尚未刷新")

        if config.universe_frequency == "weekly":
            if Date.is_next_mon_x_am(config.universe_timestamp, config.refresh_hour):
                if config.universe_enable:
                    Power.run()
                    reward.start()
                    Universe.start(get_reward=True)
                    Power.run()
                else:
                    logger.info("模拟宇宙未开启")
            else:
                logger.info("模拟宇宙尚未刷新")
        elif config.universe_frequency == "daily":
            if Date.is_next_x_am(config.universe_timestamp, config.refresh_hour):
                if config.universe_enable:
                    Universe.start(get_reward=True)
                else:
                    logger.info("模拟宇宙未开启")
            else:
                logger.info("模拟宇宙尚未刷新")

        if Date.is_next_mon_x_am(config.forgottenhall_timestamp, config.refresh_hour):
            if config.forgottenhall_enable:
                challenge.start("memoryofchaos")
            else:
                logger.info("忘却之庭未开启")
        else:
            logger.info("忘却之庭尚未刷新")

        if Date.is_next_mon_x_am(config.purefiction_timestamp, config.refresh_hour):
            if config.purefiction_enable:
                challenge.start("purefiction")
            else:
                logger.info("虚构叙事未开启")
        else:
            logger.info("虚构叙事尚未刷新")

        Power.run()

    @staticmethod
    def run():
        logger.hr("开始日常任务", 0)

        if Date.is_next_x_am(config.last_run_timestamp, config.refresh_hour):
            screen.change_to("guide2")

            tasks = Tasks("./assets/config/task_mappings.json")
            tasks.start()

            config.set_value("daily_tasks", tasks.daily_tasks)
            config.save_timestamp("last_run_timestamp")
        else:
            logger.info("日常任务尚未刷新")

        if len(config.daily_tasks) > 0:
            task_functions = {
                "登录游戏": lambda: True,
                "拍照1次": lambda: Photo.photograph(),
                "使用1次「万能合成机」": lambda: Synthesis.material(),
                "合成1次消耗品": lambda: Synthesis.consumables(),
                "合成1次材料": lambda: Synthesis.material(),
                "使用1件消耗品": lambda: Synthesis.use_consumables(),
                "完成1次「拟造花萼（金）」": lambda: Power.customize_run("拟造花萼（金）", config.instance_names["拟造花萼（金）"], 10, 1),
                "完成1次「拟造花萼（赤）」": lambda: Power.customize_run("拟造花萼（赤）", config.instance_names["拟造花萼（赤）"], 10, 1),
                "完成1次「凝滞虚影」": lambda: Power.customize_run("凝滞虚影", config.instance_names["凝滞虚影"], 30, 1),
                "完成1次「侵蚀隧洞」": lambda: Power.customize_run("侵蚀隧洞", config.instance_names["侵蚀隧洞"], 40, 1),
                "完成1次「历战余响」": lambda: Power.customize_run("历战余响", config.instance_names["历战余响"], 30, 1),
                "累计施放2次秘技": lambda: HimekoTry.technique(),
                "累计击碎3个可破坏物": lambda: HimekoTry.item(),
                "完成1次「忘却之庭」": lambda: challenge.start_memory_one(1),
                "单场战斗中，触发3种不同属性的弱点击破": lambda: challenge.start_memory_one(1),
                "累计触发弱点击破效果5次": lambda: challenge.start_memory_one(1),
                "累计消灭20个敌人": lambda: challenge.start_memory_one(2),
                "利用弱点进入战斗并获胜3次": lambda: challenge.start_memory_one(3),
                "施放终结技造成制胜一击1次": lambda: challenge.start_memory_one(1),
                "通关「模拟宇宙」（任意世界）的1个区域": lambda: Universe.run_daily(),
                "完成1次「模拟宇宙」": lambda: Universe.run_daily(),
            }

            logger.hr(f"今日实训", 2)
            count = 0
            for key, value in config.daily_tasks.items():
                state = red("待完成") if value else green("已完成")
                logger.info(f"{key}: {state}")
                count = count + 1 if not value else count
            logger.info(f"已完成：{yellow(f'{count}/{len(config.daily_tasks)}')}")

            for task_name, task_function in task_functions.items():
                if task_name in config.daily_tasks and config.daily_tasks[task_name]:
                    if task_function():
                        config.daily_tasks[task_name] = False
                        config.save_config()

        logger.hr("完成", 2)
