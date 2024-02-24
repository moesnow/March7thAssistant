from managers.logger_manager import logger
from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.translate_manager import _
from managers.config_manager import config
from managers.notify_manager import notify
from .start import Start
from .stop import Stop
import sys


class Game:
    @staticmethod
    def start():
        logger.hr(_("开始运行"), 0)
        logger.info(_("开始启动游戏"))
        if not auto.retry_with_timeout(lambda: Start.start_game(), 1200, 1):
            raise RuntimeError(_("⚠️启动游戏超时，退出程序⚠️"))
        logger.hr(_("完成"), 2)

    @staticmethod
    def stop(detect_loop=False):
        logger.hr(_("停止运行"), 0)
        Stop.play_audio()
        if detect_loop and config.after_finish == "Loop":
            Stop.after_finish_is_loop()
        else:
            Stop.after_finish_not_loop()
