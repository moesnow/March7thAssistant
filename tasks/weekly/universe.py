from managers.screen_manager import screen
from managers.config_manager import config
from managers.logger_manager import logger
from managers.automation_manager import auto
from managers.translate_manager import _
from tasks.base.base import Base
from tasks.base.pythonchecker import PythonChecker
from tasks.base.runsubprocess import RunSubprocess
import subprocess
import os


class Universe:

    @staticmethod
    def update():
        config.set_value("universe_requirements", False)
        from module.update.update_handler import UpdateHandler
        from tasks.base.fastest_mirror import FastestMirror
        url = FastestMirror.get_github_mirror("https://github.com/CHNZYX/Auto_Simulated_Universe/archive/main.zip")
        update_handler = UpdateHandler(url, config.universe_path, "Auto_Simulated_Universe-main")
        update_handler.run()

    @staticmethod
    def check_path():
        if not os.path.exists(config.universe_path):
            logger.warning(_("模拟宇宙路径不存在: {path}").format(path=config.universe_path))
            Universe.update()

    @staticmethod
    def check_requirements():
        if not config.universe_requirements:
            python_path = os.path.abspath(config.python_path)
            logger.info(_("开始安装依赖"))
            from tasks.base.fastest_mirror import FastestMirror
            while not RunSubprocess.run(f"set PATH={python_path};{python_path}\\Scripts;%PATH% && cd {config.universe_path} && pip install -i {FastestMirror.get_pypi_mirror()} -r requirements.txt", 3600):
                logger.error(_("依赖安装失败"))
                input(_("按任意键重试. . ."))
            logger.info(_("依赖安装成功"))
            config.set_value("universe_requirements", True)

    @staticmethod
    def before_start():
        if not PythonChecker.run(config.python_path):
            return False
        Universe.check_path()
        Universe.check_requirements()
        return True

    @staticmethod
    def start(get_reward=False):
        logger.hr(_("准备模拟宇宙"), 2)

        if Universe.before_start():
            python_path = os.path.abspath(config.python_path)

            screen.change_to('universe_main')
            screen.change_to('main')

            logger.info(_("开始校准"))
            if RunSubprocess.run(f"set PATH={python_path};{python_path}\\Scripts;%PATH% && cd {config.universe_path} && python align_angle.py", 60):
                logger.info(_("开始模拟宇宙"))
                if RunSubprocess.run(f"set PATH={python_path};{python_path}\\Scripts;%PATH% && cd {config.universe_path} && python states.py" + (" --bonus=1" if config.universe_bonus_enable else ""), config.universe_timeout * 3600):
                    config.save_timestamp("universe_timestamp")
                    if get_reward:
                        Universe.get_reward()
                    else:
                        Base.send_notification_with_screenshot(_("🎉模拟宇宙已完成🎉"))
                    return
                else:
                    logger.info(_("模拟宇宙失败"))
            else:
                logger.info(_("校准失败"))
        Base.send_notification_with_screenshot(_("⚠️模拟宇宙未完成⚠️"))

    @staticmethod
    def get_reward():
        logger.info(_("开始领取奖励"))
        screen.change_to('universe_main')
        if auto.click_element("./assets/images/universe/universe_reward.png", "image", 0.9):
            if auto.click_element("./assets/images/universe/one_key_receive.png", "image", 0.9, max_retries=10):
                if auto.find_element("./assets/images/base/click_close.png", "image", 0.9, max_retries=10):
                    Base.send_notification_with_screenshot(_("🎉模拟宇宙奖励已领取🎉"))
                    auto.click_element("./assets/images/base/click_close.png", "image", 0.9, max_retries=10)

    @staticmethod
    def gui():
        if Universe.before_start():
            python_path = os.path.abspath(config.python_path)
            if subprocess.run(f"set PATH={python_path};{python_path}\\Scripts;%PATH% && cd {config.universe_path} && start gui.exe", shell=True, check=True):
                return True
        return False
