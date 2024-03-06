from managers.screen import screen
from managers.config import config
from managers.logger import logger
from managers.automation import auto
from tasks.base.base import Base
from tasks.power.relicset import Relicset
from tasks.base.pythonchecker import PythonChecker
from tasks.game.starrailcontroller import StarRailController
from utils.command import subprocess_with_timeout
import subprocess
import sys
import os


class Universe:
    @staticmethod
    def update():
        from module.update.update_handler import UpdateHandler
        from tasks.base.fastest_mirror import FastestMirror
        if config.universe_operation_mode == "exe":
            import requests
            import json
            response = requests.get(FastestMirror.get_github_api_mirror("moesnow", "Auto_Simulated_Universe"), timeout=10, headers=config.useragent)
            if response.status_code == 200:
                data = json.loads(response.text)
                url = None
                for asset in data["assets"]:
                    url = FastestMirror.get_github_mirror(asset["browser_download_url"])
                    break
                if url is None:
                    logger.error("没有找到可用更新，请稍后再试")
                    input("按回车键关闭窗口. . .")
                    sys.exit(0)
                update_handler = UpdateHandler(url, config.universe_path, "Auto_Simulated_Universe")
                update_handler.run()
        elif config.universe_operation_mode == "source":
            config.set_value("universe_requirements", False)
            url = FastestMirror.get_github_mirror("https://github.com/CHNZYX/Auto_Simulated_Universe/archive/main.zip")
            update_handler = UpdateHandler(url, config.universe_path, "Auto_Simulated_Universe-main")
            update_handler.run()

    @staticmethod
    def check_path():
        status = False
        if config.universe_operation_mode == "exe":
            if not os.path.exists(os.path.join(config.universe_path, "states.exe")):
                status = True
        elif config.universe_operation_mode == "source":
            if not os.path.exists(os.path.join(config.universe_path, "states.py")):
                status = True
        if status:
            logger.warning(f"模拟宇宙路径不存在: {config.universe_path}")
            Universe.update()

    @staticmethod
    def check_requirements():
        if not config.universe_requirements:
            logger.info("开始安装依赖")
            from tasks.base.fastest_mirror import FastestMirror
            subprocess.run([config.python_exe_path, "-m", "pip", "install", "-i", FastestMirror.get_pypi_mirror(), "pip", "--upgrade"])
            while not subprocess.run([config.python_exe_path, "-m", "pip", "install", "-i", FastestMirror.get_pypi_mirror(), "-r", "requirements.txt"], check=True, cwd=config.universe_path):
                logger.error("依赖安装失败")
                input("按回车键重试. . .")
            logger.info("依赖安装成功")
            config.set_value("universe_requirements", True)

    @staticmethod
    def before_start():
        Universe.check_path()
        if config.universe_operation_mode == "source":
            PythonChecker.run()
            Universe.check_requirements()
        return True

    @staticmethod
    def start(get_reward=False, nums=config.universe_count, save=True):
        logger.hr("准备模拟宇宙", 0)
        game = StarRailController(config.game_path, config.game_process_name, config.game_title_name, 'UnityWndClass', logger)
        game.check_resolution(1920, 1080)
        if Universe.before_start():

            screen.change_to('main')

            if config.universe_operation_mode == "exe":
                logger.info("开始校准")
                if subprocess_with_timeout([os.path.join(config.universe_path, "align_angle.exe")], config.universe_timeout * 3600, config.universe_path):

                    screen.change_to('universe_main')

                    logger.info("开始模拟宇宙")
                    command = [os.path.join(config.universe_path, "states.exe")]
                    if config.universe_bonus_enable:
                        command.append("--bonus=1")
                    if nums:
                        command.append(f"--nums={nums}")
                    if subprocess_with_timeout(command, config.universe_timeout * 3600, config.universe_path):

                        if save:
                            config.save_timestamp("universe_timestamp")
                        if get_reward:
                            Universe.get_reward()
                        else:
                            Base.send_notification_with_screenshot("🎉模拟宇宙已完成🎉")

                        if config.universe_bonus_enable and config.break_down_level_four_relicset:
                            Relicset.run()

                        return True

                    else:
                        logger.error("模拟宇宙失败")
                else:
                    logger.error("校准失败")
            elif config.universe_operation_mode == "source":
                logger.info("开始校准")
                if subprocess_with_timeout([config.python_exe_path, "align_angle.py"], 60, config.universe_path, config.env):

                    screen.change_to('universe_main')

                    logger.info("开始模拟宇宙")
                    command = [config.python_exe_path, "states.py"]
                    if config.universe_bonus_enable:
                        command.append("--bonus=1")
                    if nums:
                        command.append(f"--nums={nums}")
                    if subprocess_with_timeout(command, config.universe_timeout * 3600, config.universe_path, config.env):

                        if save:
                            config.save_timestamp("universe_timestamp")
                        if get_reward:
                            Universe.get_reward()
                        else:
                            Base.send_notification_with_screenshot("🎉模拟宇宙已完成🎉")
                        return True

                    else:
                        logger.error("模拟宇宙失败")
                else:
                    logger.error("校准失败")
        Base.send_notification_with_screenshot("⚠️模拟宇宙未完成⚠️")
        return False

    @staticmethod
    def get_reward():
        logger.info("开始领取奖励")
        screen.change_to('universe_main')
        if auto.click_element("./assets/images/share/base/RedExclamationMark.png", "image", 0.9, crop=(0 / 1920, 877.0 / 1080, 422.0 / 1920, 202.0 / 1080)):
            if auto.click_element("./assets/images/zh_CN/universe/one_key_receive.png", "image", 0.9, max_retries=10):
                if auto.find_element("./assets/images/zh_CN/base/click_close.png", "image", 0.8, max_retries=10):
                    Base.send_notification_with_screenshot("🎉模拟宇宙奖励已领取🎉")
                    auto.click_element("./assets/images/zh_CN/base/click_close.png", "image", 0.8, max_retries=10)

    @staticmethod
    def gui():
        if Universe.before_start():
            if subprocess.run(["start", "gui.exe"], shell=True, check=True, cwd=config.universe_path, env=config.env):
                return True
        return False

    @staticmethod
    def run_daily():
        return False
        # if config.daily_universe_enable:
        # return Universe.start(get_reward=False, nums=1, save=False)

    @staticmethod
    def reset_config():
        config_path = os.path.join(config.universe_path, "info.yml")

        try:
            os.remove(config_path)
            logger.info(f"重置配置文件完成：{config_path}")
        except Exception as e:
            logger.warning(f"重置配置文件失败：{e}")
