from managers.logger_manager import logger
from managers.automation_manager import auto
from managers.translate_manager import _
from managers.config_manager import config
from tasks.base.base import Base
from tasks.base.date import Date
import psutil
import time
import sys
import os


class Stop:
    @staticmethod
    def terminate_process(name):
        for proc in psutil.process_iter(attrs=['pid', 'name']):
            if name in proc.info['name']:
                try:
                    process = psutil.Process(proc.info['pid'])
                    process.terminate()
                    process.wait(timeout=10)
                    return True
                except (psutil.NoSuchProcess, psutil.TimeoutExpired, psutil.AccessDenied):
                    pass
        return False

    @staticmethod
    def stop_game():
        logger.info(_("开始退出游戏"))
        if Base.check_and_switch(config.game_title_name):
            if not auto.retry_with_timeout(Stop.terminate_process, 10, 1, config.game_process_name):
                logger.error(_("游戏退出失败"))
                return False
            logger.info(_("游戏退出成功"))
        else:
            logger.warning(_("游戏已经退出了"))
        return True

    @staticmethod
    def get_wait_time(current_power):
        # 距离体力到达配置文件指定的上限剩余秒数
        wait_time_power_limit = (config.power_limit - current_power) * config.power_rec_min * 60
        # 距离第二天凌晨4点剩余秒数，+30避免显示3点59分不美观:）
        wait_time_next_day = Date.get_time_next_4am() + 30
        # 取最小值
        wait_time = min(wait_time_power_limit, wait_time_next_day)
        return wait_time

    @staticmethod
    def shutdown():
        logger.warning(_("将在1分钟后自动关机"))
        time.sleep(60)
        os.system("shutdown /s /t 0")
        sys.exit(0)

    @staticmethod
    def play_audio():
        if config.play_audio:
            os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
            import pygame.mixer

            pygame.init()
            pygame.mixer.music.load('./assets/audio/pa.mp3')
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
