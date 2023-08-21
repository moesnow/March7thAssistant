from managers.screen_manager import screen
from managers.config_manager import config
from managers.logger_manager import logger
from managers.translate_manager import _
import subprocess
from threading import Thread
from tasks.base.base import Base


class Fight:
    @staticmethod
    def run_subprocess_with_timeout(command, timeout):
        process = None
        try:
            process = subprocess.Popen(command, shell=True)
            process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if process is not None:
                process.terminate()
                process.wait()

    @staticmethod
    def start():
        if not config.fight_enable:
            logger.debug(_("锄大地未开启"))
            return False
        screen.change_to('main')

        logger.hr(_("准备锄大地"), 2)

        subprocess_thread = Thread(target=Fight.run_subprocess_with_timeout, args=(config.fight_command, config.fight_timeout * 3600))
        subprocess_thread.start()
        subprocess_thread.join()

        Base.send_notification_with_screenshot(_("🎉锄大地已完成🎉"))
        screen.change_to('main')
        logger.info(_("锄大地完成"))
        config.save_timestamp("fight_timestamp")
