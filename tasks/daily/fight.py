from managers.screen import screen
from managers.config import config
from managers.logger import logger
from tasks.base.base import Base
from tasks.base.team import Team
from tasks.base.pythonchecker import PythonChecker
from tasks.game.starrailcontroller import StarRailController
from utils.command import subprocess_with_timeout
import subprocess
import sys
import os


class Fight:

    @staticmethod
    def update():
        from module.update.update_handler import UpdateHandler
        from tasks.base.fastest_mirror import FastestMirror
        if config.fight_operation_mode == "exe":
            import requests
            import json
            response = requests.get(FastestMirror.get_github_api_mirror("linruowuyin", "Fhoe-Rail"), timeout=10, headers=config.useragent)
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
                update_handler = UpdateHandler(url, config.fight_path, "Fhoe-Rail", os.path.join(config.fight_path, "map"))
                update_handler.run()
        elif config.fight_operation_mode == "source":
            config.set_value("fight_requirements", False)
            url = FastestMirror.get_github_mirror(
                "https://github.com/linruowuyin/Fhoe-Rail/archive/master.zip")
            update_handler = UpdateHandler(url, config.fight_path, "Fhoe-Rail-master")
            update_handler.run()

    @staticmethod
    def check_path():
        status = False
        if config.fight_operation_mode == "exe":
            if not os.path.exists(os.path.join(config.fight_path, "Fhoe-Rail.exe")):
                status = True
        elif config.fight_operation_mode == "source":
            if not os.path.exists(os.path.join(config.fight_path, "Honkai_Star_Rail.py")):
                status = True
            if not os.path.exists(os.path.join(config.fight_path, "点这里啦.exe")):
                status = True
        if status:
            logger.warning(f"锄大地路径不存在: {config.fight_path}")
            Fight.update()

    @staticmethod
    def check_requirements():
        if not config.fight_requirements:
            logger.info("开始安装依赖")
            from tasks.base.fastest_mirror import FastestMirror
            subprocess.run([config.python_exe_path, "-m", "pip", "install", "-i",
                           FastestMirror.get_pypi_mirror(), "pip", "--upgrade"])
            while not subprocess.run([config.python_exe_path, "-m", "pip", "install", "-i", FastestMirror.get_pypi_mirror(), "-r", "requirements.txt"], check=True, cwd=config.fight_path):
                logger.error("依赖安装失败")
                input("按回车键重试. . .")
            logger.info("依赖安装成功")
            config.set_value("fight_requirements", True)

    @staticmethod
    def before_start():
        Fight.check_path()
        if config.fight_operation_mode == "source":
            PythonChecker.run()
            Fight.check_requirements()
        return True

    @staticmethod
    def start():
        logger.hr("准备锄大地", 0)
        game = StarRailController(config.game_path, config.game_process_name, config.game_title_name, 'UnityWndClass', logger)
        game.check_resolution(1920, 1080)
        if Fight.before_start():
            # 切换队伍
            if config.fight_team_enable:
                Team.change_to(config.fight_team_number)

            logger.info("开始锄大地")
            screen.change_to('main')

            status = False
            if config.fight_operation_mode == "exe":
                if subprocess_with_timeout([os.path.join(config.fight_path, "Fhoe-Rail.exe")], config.fight_timeout * 3600, config.fight_path):
                    status = True
            elif config.fight_operation_mode == "source":
                if subprocess_with_timeout([config.python_exe_path, "Honkai_Star_Rail.py"], config.fight_timeout * 3600, config.fight_path, config.env):
                    status = True
            if status:
                config.save_timestamp("fight_timestamp")
                Base.send_notification_with_screenshot("🎉锄大地已完成🎉")
                return True

        logger.error("锄大地失败")
        Base.send_notification_with_screenshot("⚠️锄大地未完成⚠️")
        return False

    @staticmethod
    def gui():
        if Fight.before_start():
            if config.fight_operation_mode == "exe":
                if subprocess.run(["start", "Fhoe-Rail.exe", "--debug"], shell=True, check=True, cwd=config.fight_path):
                    return True
            elif config.fight_operation_mode == "source":
                if subprocess.run(["start", "点这里啦.exe"], shell=True, check=True, cwd=config.fight_path, env=config.env):
                    return True
        return False

    @staticmethod
    def reset_config():
        config_path = os.path.join(config.fight_path, "config.json")

        try:
            os.remove(config_path)
            logger.info(f"重置配置文件完成：{config_path}")
        except Exception as e:
            logger.warning(f"重置配置文件失败：{e}")
