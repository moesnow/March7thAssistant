from managers.screen_manager import screen
from managers.config_manager import config
from managers.logger_manager import logger
from managers.translate_manager import _
from tasks.base.base import Base
from tasks.base.pythonchecker import PythonChecker
from tasks.base.runsubprocess import RunSubprocess
import os


class Fight:
    @staticmethod
    def start():
        logger.hr(_("准备锄大地"), 2)

        if PythonChecker.run(config.python_path):
            python_path = os.path.abspath(config.python_path)
            if not os.path.exists(config.fight_path):
                logger.error(_("锄大地路径不存在: {path}").format(path=config.fight_path))
                logger.info(_("请先安装锄大地功能后再使用！"))
                logger.info(_("你可以从 QQ 群文件(855392201)获取锄大地补丁包"))
            else:
                if config.fight_team_enable:
                    Base.change_team(config.fight_team_number)

                screen.change_to('main')

                logger.info(_("开始安装依赖"))
                if RunSubprocess.run(f"set PATH={python_path};{python_path}\\Scripts;%PATH% && cd {config.fight_path} && pip install -i {config.pip_mirror} -r requirements.txt", 3600):
                    logger.info(_("开始锄大地"))
                    if RunSubprocess.run(f"set PATH={python_path};{python_path}\\Scripts;%PATH% && cd {config.fight_path} && python Fast_Star_Rail.py", config.fight_timeout * 3600):
                        config.save_timestamp("fight_timestamp")
                        Base.send_notification_with_screenshot(_("🎉锄大地已完成🎉"))
                        return
                    else:
                        logger.info(_("锄大地失败"))
                else:
                    logger.info(_("依赖安装失败"))
        Base.send_notification_with_screenshot(_("⚠️锄大地未完成⚠️"))
