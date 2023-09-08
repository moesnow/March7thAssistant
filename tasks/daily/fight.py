from managers.screen_manager import screen
from managers.config_manager import config
from managers.logger_manager import logger
from managers.translate_manager import _
from tasks.base.base import Base
from tasks.base.subprocess import Subprocess


class Fight:
    @staticmethod
    def start():
        if config.fight_team_enable:
            Base.change_team(config.fight_team_number)

        logger.hr(_("准备锄大地"), 2)

        screen.change_to('main')

        if Subprocess.run(config.fight_command, config.fight_timeout * 3600):
            Base.send_notification_with_screenshot(_("🎉锄大地已完成🎉"))
            logger.info(_("锄大地完成"))
            config.save_timestamp("fight_timestamp")
        else:
            Base.send_notification_with_screenshot(_("⚠️锄大地未完成⚠️"))
            logger.info(_("锄大地失败"))
