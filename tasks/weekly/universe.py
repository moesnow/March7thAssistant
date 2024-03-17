from module.screen import screen
from module.config import cfg
from module.logger import log
from module.automation import auto
from tasks.base.base import Base
from tasks.power.relicset import Relicset
from tasks.base.pythonchecker import PythonChecker
from tasks.game.starrailcontroller import StarRailController
from utils.command import subprocess_with_timeout
import subprocess
import time
import sys
import os


class Universe:
    @staticmethod
    def update():
        from module.update.update_handler import UpdateHandler
        from tasks.base.fastest_mirror import FastestMirror
        if cfg.universe_operation_mode == "exe":
            import requests
            import json
            response = requests.get(FastestMirror.get_github_api_mirror("moesnow", "Auto_Simulated_Universe"), timeout=10, headers=cfg.useragent)
            if response.status_code == 200:
                data = json.loads(response.text)
                url = None
                for asset in data["assets"]:
                    url = FastestMirror.get_github_mirror(asset["browser_download_url"])
                    break
                if url is None:
                    log.error("没有找到可用更新，请稍后再试")
                    input("按回车键关闭窗口. . .")
                    sys.exit(0)
                update_handler = UpdateHandler(url, cfg.universe_path, "Auto_Simulated_Universe")
                update_handler.run()
        elif cfg.universe_operation_mode == "source":
            cfg.set_value("universe_requirements", False)
            url = FastestMirror.get_github_mirror("https://github.com/CHNZYX/Auto_Simulated_Universe/archive/main.zip")
            update_handler = UpdateHandler(url, cfg.universe_path, "Auto_Simulated_Universe-main")
            update_handler.run()

    @staticmethod
    def check_path():
        status = False
        if cfg.universe_operation_mode == "exe":
            if not os.path.exists(os.path.join(cfg.universe_path, "states.exe")):
                status = True
        elif cfg.universe_operation_mode == "source":
            if not os.path.exists(os.path.join(cfg.universe_path, "states.py")):
                status = True
        if status:
            log.warning(f"模拟宇宙路径不存在: {cfg.universe_path}")
            Universe.update()

    @staticmethod
    def check_requirements():
        if not cfg.universe_requirements:
            log.info("开始安装依赖")
            from tasks.base.fastest_mirror import FastestMirror
            subprocess.run([cfg.python_exe_path, "-m", "pip", "install", "-i", FastestMirror.get_pypi_mirror(), "pip", "--upgrade"])
            while not subprocess.run([cfg.python_exe_path, "-m", "pip", "install", "-i", FastestMirror.get_pypi_mirror(), "-r", "requirements.txt"], check=True, cwd=cfg.universe_path):
                log.error("依赖安装失败")
                input("按回车键重试. . .")
            log.info("依赖安装成功")
            cfg.set_value("universe_requirements", True)

    @staticmethod
    def before_start():
        Universe.check_path()
        if cfg.universe_operation_mode == "source":
            PythonChecker.run()
            Universe.check_requirements()
        return True

    @staticmethod
    def start(nums=cfg.universe_count, save=True):
        log.hr("准备模拟宇宙", 0)
        game = StarRailController(cfg.game_path, cfg.game_process_name, cfg.game_title_name, 'UnityWndClass', log)
        game.check_resolution(1920, 1080)
        if Universe.before_start():

            screen.change_to('universe_main')
            # 等待可能的周一弹窗
            time.sleep(2)
            # 进入黑塔办公室
            screen.change_to('main')

            if cfg.universe_operation_mode == "exe":
                log.info("开始校准")
                if subprocess_with_timeout([os.path.join(cfg.universe_path, "align_angle.exe")], cfg.universe_timeout * 3600, cfg.universe_path):

                    screen.change_to('universe_main')

                    log.info("开始模拟宇宙")
                    command = [os.path.join(cfg.universe_path, "states.exe")]
                    if cfg.universe_bonus_enable:
                        command.append("--bonus=1")
                    if nums:
                        command.append(f"--nums={nums}")
                    if subprocess_with_timeout(command, cfg.universe_timeout * 3600, cfg.universe_path):

                        if save:
                            cfg.save_timestamp("universe_timestamp")

                        Universe.get_reward()

                        if cfg.universe_bonus_enable and cfg.break_down_level_four_relicset:
                            Relicset.run()

                        return True

                    else:
                        log.error("模拟宇宙失败")
                else:
                    log.error("校准失败")
            elif cfg.universe_operation_mode == "source":
                log.info("开始校准")
                if subprocess_with_timeout([cfg.python_exe_path, "align_angle.py"], 60, cfg.universe_path, cfg.env):

                    screen.change_to('universe_main')

                    log.info("开始模拟宇宙")
                    command = [cfg.python_exe_path, "states.py"]
                    if cfg.universe_bonus_enable:
                        command.append("--bonus=1")
                    if nums:
                        command.append(f"--nums={nums}")
                    if subprocess_with_timeout(command, cfg.universe_timeout * 3600, cfg.universe_path, cfg.env):

                        if save:
                            cfg.save_timestamp("universe_timestamp")

                        Universe.get_reward()

                        if cfg.universe_bonus_enable and cfg.break_down_level_four_relicset:
                            Relicset.run()

                        return True

                    else:
                        log.error("模拟宇宙失败")
                else:
                    log.error("校准失败")
        Base.send_notification_with_screenshot(cfg.notify_template['SimulatedUniverseNotCompleted'])
        return False

    @staticmethod
    def get_reward():
        log.info("开始领取奖励")
        screen.change_to('universe_main')
        time.sleep(1)
        if auto.click_element("./assets/images/share/base/RedExclamationMark.png", "image", 0.9, crop=(0 / 1920, 877.0 / 1080, 422.0 / 1920, 202.0 / 1080)):
            if auto.click_element("./assets/images/zh_CN/universe/one_key_receive.png", "image", 0.9, max_retries=10):
                if auto.find_element("./assets/images/zh_CN/base/click_close.png", "image", 0.8, max_retries=10):
                    Base.send_notification_with_screenshot(cfg.notify_template['SimulatedUniverseRewardClaimed'])
                    auto.click_element("./assets/images/zh_CN/base/click_close.png", "image", 0.8, max_retries=10)
                    return
        Base.send_notification_with_screenshot(cfg.notify_template['SimulatedUniverseCompleted'])

    @staticmethod
    def gui():
        if Universe.before_start():
            if subprocess.run(["start", "gui.exe"], shell=True, check=True, cwd=cfg.universe_path, env=cfg.env):
                return True
        return False

    @staticmethod
    def run_daily():
        return False
        # if config.daily_universe_enable:
        # return Universe.start(nums=1, save=False)
