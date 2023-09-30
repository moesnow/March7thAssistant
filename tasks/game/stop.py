from managers.logger_manager import logger
from managers.automation_manager import auto
from managers.translate_manager import _
from managers.config_manager import config
from managers.notify_manager import notify
from tasks.power.power import Power
from tasks.base.date import Date
from tasks.base.windowswitcher import WindowSwitcher
import psutil
import time
import sys
import os


class Stop:
    @staticmethod
    def terminate_process(name, timeout=10):
        # 根据进程名中止进程
        for proc in psutil.process_iter(attrs=['pid', 'name']):
            if name in proc.info['name']:
                try:
                    process = psutil.Process(proc.info['pid'])
                    process.terminate()
                    process.wait(timeout)
                    return True
                except (psutil.NoSuchProcess, psutil.TimeoutExpired, psutil.AccessDenied):
                    pass
        return False

    @staticmethod
    def stop_game():
        logger.info(_("开始退出游戏"))
        if WindowSwitcher.check_and_switch(config.game_title_name):
            if not auto.retry_with_timeout(lambda: Stop.terminate_process(config.game_process_name), 10, 1):
                logger.error(_("游戏退出失败"))
                return False
            logger.info(_("游戏退出成功"))
        else:
            logger.warning(_("游戏已经退出了"))
        return True

    @staticmethod
    def get_wait_time(current_power):
        # 距离体力到达配置文件指定的上限剩余秒数
        wait_time_power_limit = (config.power_limit - current_power) * 6 * 60
        # 距离第二天凌晨4点剩余秒数，+30避免显示3点59分不美观
        wait_time_next_day = Date.get_time_next_4am() + 30
        # 取最小值
        wait_time = min(wait_time_power_limit, wait_time_next_day)
        return wait_time

    @staticmethod
    def play_audio():
        if config.play_audio:
            logger.debug(_("开始播放音频"))
            os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
            import pygame.mixer

            pygame.init()
            pygame.mixer.music.load('./assets/audio/pa.mp3')
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            logger.debug(_("播放音频完成"))

    @staticmethod
    def shutdown():
        logger.warning(_("将在1分钟后自动关机"))
        time.sleep(60)
        os.system("shutdown /s /t 0")

    @staticmethod
    def hibernate():
        logger.warning(_("将在1分钟后自动休眠"))
        time.sleep(60)
        os.system("shutdown /h")

    @staticmethod
    def sleep():
        logger.warning(_("将在1分钟后自动睡眠"))
        time.sleep(60)
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")

    @staticmethod
    def after_finish_is_loop():
        current_power = Power.power()
        if current_power >= config.power_limit:
            logger.info(_("🟣开拓力 >= {limit}").format(limit=config.power_limit))
            logger.info(_("即将再次运行"))
            logger.hr(_("完成"), 2)
        else:
            Stop.stop_game()
            wait_time = Stop.get_wait_time(current_power)
            future_time = Date.calculate_future_time(wait_time)
            logger.info(_("📅将在{future_time}继续运行").format(future_time=future_time))
            notify.notify(_("📅将在{future_time}继续运行").format(future_time=future_time))
            logger.hr(_("完成"), 2)
            time.sleep(wait_time)

    @staticmethod
    def after_finish_not_loop():
        if config.after_finish in ["Exit", "Shutdown", "Hibernate", "Sleep"]:
            Stop.stop_game()
            if config.after_finish == "Shutdown":
                Stop.shutdown()
            elif config.after_finish == "Hibernate":
                Stop.hibernate()
            elif config.after_finish == "Sleep":
                Stop.sleep()
        logger.hr(_("完成"), 2)
        if config.after_finish not in ["Shutdown", "Hibernate", "Sleep"]:
            input(_("按任意键关闭窗口. . ."))
        sys.exit(0)
