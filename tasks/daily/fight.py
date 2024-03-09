from module.screen import screen
from module.config import cfg
from module.logger import log
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
        if cfg.fight_operation_mode == "exe":
            import requests
            import json
            response = requests.get(FastestMirror.get_github_api_mirror("linruowuyin", "Fhoe-Rail"), timeout=10, headers=cfg.useragent)
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
                update_handler = UpdateHandler(url, cfg.fight_path, "Fhoe-Rail", os.path.join(cfg.fight_path, "map"))
                update_handler.run()
        elif cfg.fight_operation_mode == "source":
            cfg.set_value("fight_requirements", False)
            url = FastestMirror.get_github_mirror(
                "https://github.com/linruowuyin/Fhoe-Rail/archive/master.zip")
            update_handler = UpdateHandler(url, cfg.fight_path, "Fhoe-Rail-master")
            update_handler.run()

    @staticmethod
    def check_path():
        status = False
        if cfg.fight_operation_mode == "exe":
            if not os.path.exists(os.path.join(cfg.fight_path, "Fhoe-Rail.exe")):
                status = True
        elif cfg.fight_operation_mode == "source":
            if not os.path.exists(os.path.join(cfg.fight_path, "Honkai_Star_Rail.py")):
                status = True
            if not os.path.exists(os.path.join(cfg.fight_path, "点这里啦.exe")):
                status = True
        if status:
            log.warning(f"锄大地路径不存在: {cfg.fight_path}")
            Fight.update()

    @staticmethod
    def check_requirements():
        if not cfg.fight_requirements:
            log.info("开始安装依赖")
            from tasks.base.fastest_mirror import FastestMirror
            subprocess.run([cfg.python_exe_path, "-m", "pip", "install", "-i",
                           FastestMirror.get_pypi_mirror(), "pip", "--upgrade"])
            while not subprocess.run([cfg.python_exe_path, "-m", "pip", "install", "-i", FastestMirror.get_pypi_mirror(), "-r", "requirements.txt"], check=True, cwd=cfg.fight_path):
                log.error("依赖安装失败")
                input("按回车键重试. . .")
            log.info("依赖安装成功")
            cfg.set_value("fight_requirements", True)

    @staticmethod
    def before_start():
        Fight.check_path()
        if cfg.fight_operation_mode == "source":
            PythonChecker.run()
            Fight.check_requirements()
        return True

    @staticmethod
    def start():
        log.hr("准备锄大地", 0)
        game = StarRailController(cfg.game_path, cfg.game_process_name, cfg.game_title_name, 'UnityWndClass', log)
        game.check_resolution(1920, 1080)
        if Fight.before_start():
            # 切换队伍
            if cfg.fight_team_enable:
                Team.change_to(cfg.fight_team_number)

            log.info("开始锄大地")
            screen.change_to('main')

            status = False
            if cfg.fight_operation_mode == "exe":
                if subprocess_with_timeout([os.path.join(cfg.fight_path, "Fhoe-Rail.exe")], cfg.fight_timeout * 3600, cfg.fight_path):
                    status = True
            elif cfg.fight_operation_mode == "source":
                if subprocess_with_timeout([cfg.python_exe_path, "Honkai_Star_Rail.py"], cfg.fight_timeout * 3600, cfg.fight_path, cfg.env):
                    status = True
            if status:
                cfg.save_timestamp("fight_timestamp")
                Base.send_notification_with_screenshot("🎉锄大地已完成🎉")
                return True

        log.error("锄大地失败")
        Base.send_notification_with_screenshot("⚠️锄大地未完成⚠️")
        return False

    @staticmethod
    def gui():
        if Fight.before_start():
            if cfg.fight_operation_mode == "exe":
                if subprocess.run(["start", "Fhoe-Rail.exe", "--debug"], shell=True, check=True, cwd=cfg.fight_path):
                    return True
            elif cfg.fight_operation_mode == "source":
                if subprocess.run(["start", "点这里啦.exe"], shell=True, check=True, cwd=cfg.fight_path, env=cfg.env):
                    return True
        return False

    @staticmethod
    def reset_config():
        config_path = os.path.join(cfg.fight_path, "config.json")

        try:
            os.remove(config_path)
            log.info(f"重置配置文件完成：{config_path}")
        except Exception as e:
            log.warning(f"重置配置文件失败：{e}")
