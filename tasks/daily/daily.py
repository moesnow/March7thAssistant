from module.logger import log
from module.config import cfg
from module.screen import screen
from utils.date import Date
from tasks.daily.photo import Photo
from tasks.daily.fight import Fight
from tasks.weekly.universe import Universe
import tasks.reward as reward
import tasks.activity as activity
from tasks.daily.synthesis import Synthesis
import tasks.challenge as challenge
from tasks.power.power import Power
from tasks.daily.tasks import Tasks
from tasks.daily.himekotry import HimekoTry
from tasks.weekly.echoofwar import Echoofwar
from utils.color import red, green, yellow
import datetime

class Daily:
    @staticmethod
    def start():
        activity.start()
        if cfg.daily_enable:
            Daily.run()

        # 优先历战余响
        if Date.is_next_mon_x_am(cfg.echo_of_war_timestamp, cfg.refresh_hour):
            if cfg.echo_of_war_enable:
                # 注意，这里并没有解决每天开始时间。也就是4点开始。按照真实时间进行执行
                isoweekday = datetime.date.today().isoweekday()
                if isoweekday >= cfg.echo_of_war_start_day_of_week:
                    Echoofwar.start()
                else:
                    log.info(f"历战余响设置周{cfg.echo_of_war_start_day_of_week}后开始执行，当前为周{isoweekday}, 跳过执行")
            else:
                log.info("历战余响未开启")
        else:
            log.info("历战余响尚未刷新")

        Power.run()

        if Date.is_next_x_am(cfg.fight_timestamp, cfg.refresh_hour):
            if cfg.fight_enable:
                Fight.start()
            else:
                log.info("锄大地未开启")
        else:
            log.info("锄大地尚未刷新")

        if cfg.weekly_divergent_enable:
            if Date.is_next_mon_x_am(cfg.weekly_divergent_timestamp, cfg.refresh_hour):
                if Universe.start(1, False, "divergent"):
                    cfg.save_timestamp("weekly_divergent_timestamp")
            else:
                log.info("每周一次差分宇宙尚未刷新")

        if cfg.universe_frequency == "weekly":
            if Date.is_next_mon_x_am(cfg.universe_timestamp, cfg.refresh_hour):
                if cfg.universe_enable:
                    Power.run()
                    reward.start()
                    Universe.start()
                    Power.run()
                else:
                    log.info("模拟宇宙未开启")
            else:
                log.info("模拟宇宙尚未刷新")
        elif cfg.universe_frequency == "daily":
            if Date.is_next_x_am(cfg.universe_timestamp, cfg.refresh_hour):
                if cfg.universe_enable:
                    Universe.start()
                else:
                    log.info("模拟宇宙未开启")
            else:
                log.info("模拟宇宙尚未刷新")

        if Date.is_next_mon_x_am(cfg.forgottenhall_timestamp, cfg.refresh_hour):
            if cfg.forgottenhall_enable:
                challenge.start("memoryofchaos")
            else:
                log.info("忘却之庭未开启")
        else:
            log.info("忘却之庭尚未刷新")

        if Date.is_next_mon_x_am(cfg.purefiction_timestamp, cfg.refresh_hour):
            if cfg.purefiction_enable:
                challenge.start("purefiction")
            else:
                log.info("虚构叙事未开启")
        else:
            log.info("虚构叙事尚未刷新")

        if Date.is_next_mon_x_am(cfg.apocalyptic_timestamp, cfg.refresh_hour):
            if cfg.apocalyptic_enable:
                challenge.start("apocalyptic")
            else:
                log.info("末日幻影未开启")
        else:
            log.info("末日幻影尚未刷新")

        activity.start()

        # 优先历战余响
        if Date.is_next_mon_x_am(cfg.echo_of_war_timestamp, cfg.refresh_hour):
            if cfg.echo_of_war_enable:
                # 注意，这里并没有解决每天开始时间。也就是4点开始。按照真实时间进行执行
                isoweekday = datetime.date.today().isoweekday()
                if isoweekday >= cfg.echo_of_war_start_day_of_week:
                    Echoofwar.start()
                else:
                    log.info(f"历战余响设置周{cfg.echo_of_war_start_day_of_week}后开始执行，当前为周{isoweekday}, 跳过执行")
            else:
                log.info("历战余响未开启")
        else:
            log.info("历战余响尚未刷新")
        Power.run()

    @staticmethod
    def run():
        log.hr("开始日常任务", 0)

        if Date.is_next_x_am(cfg.last_run_timestamp, cfg.refresh_hour):
            screen.change_to("guide2")

            tasks = Tasks("./assets/config/task_mappings.json")
            tasks.start()

            cfg.set_value("daily_tasks", tasks.daily_tasks)
            cfg.save_timestamp("last_run_timestamp")
        else:
            log.info("日常任务尚未刷新")

        if len(cfg.daily_tasks) > 0:
            task_functions = {
                "登录游戏": lambda: True,
                "拍照1次": lambda: Photo.photograph(),
                "使用1次「万能合成机」": lambda: Synthesis.material(),
                "合成1次消耗品": lambda: Synthesis.consumables(),
                "合成1次材料": lambda: Synthesis.material(),
                "使用1件消耗品": lambda: Synthesis.use_consumables(),
                # "完成1次「拟造花萼（金）」": lambda: Power.customize_run("拟造花萼（金）", cfg.instance_names["拟造花萼（金）"], 10, 1),
                # "完成1次「拟造花萼（赤）」": lambda: Power.customize_run("拟造花萼（赤）", cfg.instance_names["拟造花萼（赤）"], 10, 1),
                # "完成1次「凝滞虚影」": lambda: Power.customize_run("凝滞虚影", cfg.instance_names["凝滞虚影"], 30, 1),
                # "完成1次「侵蚀隧洞」": lambda: Power.customize_run("侵蚀隧洞", cfg.instance_names["侵蚀隧洞"], 40, 1),
                # "完成1次「历战余响」": lambda: Power.customize_run("历战余响", cfg.instance_names["历战余响"], 30, 1),
                "累计施放2次秘技": lambda: HimekoTry.technique(),
                "累计击碎3个可破坏物": lambda: HimekoTry.item(),
                "完成1次「忘却之庭」": lambda: challenge.start_memory_one(1),
                "单场战斗中，触发3种不同属性的弱点击破": lambda: challenge.start_memory_one(1),
                "累计触发弱点击破效果5次": lambda: challenge.start_memory_one(1),
                "累计消灭20个敌人": lambda: challenge.start_memory_one(2),
                "利用弱点进入战斗并获胜3次": lambda: challenge.start_memory_one(3),
                "施放终结技造成制胜一击1次": lambda: challenge.start_memory_one(1),
                "通关「模拟宇宙」（任意世界）的1个区域": lambda: Universe.run_daily(),
                "完成1次「差分宇宙」或「模拟宇宙」": lambda: Universe.run_daily(),
            }

            log.hr(f"今日实训", 2)
            count = 0
            for key, value in cfg.daily_tasks.items():
                state = red("待完成") if value else green("已完成")
                log.info(f"{key}: {state}")
                count = count + 1 if not value else count
            log.info(f"已完成：{yellow(f'{count}/{len(cfg.daily_tasks)}')}")

            for task_name, task_function in task_functions.items():
                if task_name in cfg.daily_tasks and cfg.daily_tasks[task_name]:
                    if task_function():
                        cfg.daily_tasks[task_name] = False
                        cfg.save_config()

        log.hr("完成", 2)
