from managers.screen_manager import screen
from managers.config_manager import config
from managers.logger_manager import logger
from managers.translate_manager import _
from tasks.base.base import Base
from tasks.base.pythonchecker import PythonChecker
from tasks.base.command import subprocess_with_timeout
import subprocess
import os


class Fight:

    @staticmethod
    def update():
        config.set_value("fight_requirements", False)
        from module.update.update_handler import UpdateHandler
        from tasks.base.fastest_mirror import FastestMirror
        url = FastestMirror.get_github_mirror("https://github.com/linruowuyin/Fhoe-Rail/archive/master.zip")
        update_handler = UpdateHandler(url, config.fight_path, "Fhoe-Rail-master")
        update_handler.run()

    @staticmethod
    def check_path():
        if not os.path.exists(config.fight_path):
            logger.warning(_("锄大地路径不存在: {path}").format(path=config.fight_path))
            Fight.update()

    @staticmethod
    def check_requirements():
        if not config.fight_requirements:
            logger.info(_("开始安装依赖"))
            from tasks.base.fastest_mirror import FastestMirror
            subprocess.run([config.python_exe_path, "-m", "pip", "install", "-i", FastestMirror.get_pypi_mirror(), "pip", "--upgrade"])
            while not subprocess.run([config.python_exe_path, "-m", "pip", "install", "-i", FastestMirror.get_pypi_mirror(), "-r", "requirements.txt"], check=True, cwd=config.fight_path):
                logger.error(_("依赖安装失败"))
                input(_("按任意键重试. . ."))
            logger.info(_("依赖安装成功"))
            config.set_value("fight_requirements", True)

    @staticmethod
    def before_start():
        PythonChecker.run()
        Fight.check_path()
        Fight.check_requirements()
        return True

    @staticmethod
    def start():
        logger.hr(_("准备锄大地"), 2)

        if Fight.before_start():
            # 切换队伍
            if config.fight_team_enable:
                Base.change_team(config.fight_team_number)

            screen.change_to('main')

            logger.info(_("开始锄大地"))
            if subprocess_with_timeout([config.python_exe_path, "Fast_Star_Rail.py"], config.fight_timeout * 3600, config.fight_path, config.env):
                config.save_timestamp("fight_timestamp")
                Base.send_notification_with_screenshot(_("🎉锄大地已完成🎉"))
                return
            else:
                logger.error(_("锄大地失败"))
        Base.send_notification_with_screenshot(_("⚠️锄大地未完成⚠️"))

    @staticmethod
    def gui():
        if Fight.before_start():
            if subprocess.run(["start", "点我点我.exe"], shell=True, check=True, cwd=config.fight_path, env=config.env):
                return True
        return False
