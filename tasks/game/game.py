from managers.logger_manager import logger
from managers.automation_manager import auto
from managers.translate_manager import _
from managers.config_manager import config
from managers.notify_manager import notify
from tasks.power.power import Power
from tasks.base.date import Date
from tasks.game.start import Start
from tasks.game.stop import Stop
import time
import sys


class Game:
    @staticmethod
    def start():
        logger.hr(_("开始运行"), 0)
        logger.info(_("开始启动游戏"))
        if not auto.retry_with_timeout(Start.start_game, 1200, 1):
            notify.notify(_("⚠️启动游戏超时，退出程序⚠️"))
            logger.error(_("⚠️启动游戏超时，退出程序⚠️"))
            sys.exit(1)
        logger.hr(_("完成"), 2)

    @staticmethod
    def stop():
        logger.hr(_("停止运行"), 0)
        current_power = Power.power()
 
        if current_power >= config.power_limit and config.never_stop:
            logger.info(_("🟣开拓力 >= {limit}").format(limit=config.power_limit))
            logger.info(_("即将再次运行"))
            logger.hr(_("完成"), 2)
        else:
            if config.auto_exit:
                logger.info(_("开始退出游戏"))
                Stop.stop_game()

            if current_power == -1:
                logger.info(_("📅将在{power_rec_min}分钟后继续运行").format(power_rec_min=config.power_rec_min))
                logger.hr(_("完成"), 2)
                time.sleep(config.power_rec_min * 60)
            else:
                if not config.never_stop:
                    logger.hr(_("完成"), 2)
                    sys.exit(0)
                if current_power < config.power_limit:
                    wait_time = Stop.get_wait_time(current_power)
                    future_time = Date.calculate_future_time(wait_time)
                    logger.info(_("📅将在{future_time}继续运行").format(future_time=future_time))
                    notify.notify(_("📅将在{future_time}继续运行").format(future_time=future_time))
                    logger.hr(_("完成"), 2)
                    time.sleep(wait_time)
