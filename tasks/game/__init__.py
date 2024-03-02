import os
import sys
import time
import psutil
import random

from .starrailcontroller import StarRailController

from utils.date import Date
from tasks.power.power import Power
from managers.logger_manager import logger
from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.config_manager import config
from managers.notify_manager import notify
from managers.ocr_manager import ocr


class Game:
    @staticmethod
    def start():
        logger.hr("开始运行", 0)
        Game.start_game()
        logger.hr("完成", 2)

    @staticmethod
    def start_game():
        game = StarRailController(config.game_path, config.game_process_name, config.game_title_name, 'UnityWndClass', logger)
        MAX_RETRY = 3

        def wait_until(condition, timeout, period=1):
            """等待直到条件满足或超时"""
            end_time = time.time() + timeout
            while time.time() < end_time:
                if condition():
                    return True
                time.sleep(period)
            return False

        def check_and_click_enter():
            # 点击进入
            if auto.click_element("./assets/images/screen/click_enter.png", "image", 0.9):
                return True
            # 游戏热更新，需要确认重启
            auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, take_screenshot=False)
            # 网络异常等问题，需要重新启动
            auto.click_element("./assets/images/zh_CN/base/restart.png", "image", 0.9, take_screenshot=False)
            # 适配国际服，需要点击“开始游戏”
            auto.click_element("./assets/images/screen/start_game.png", "image", 0.9, take_screenshot=False)
            return False

        def get_process_path(name):
            # 通过进程名获取运行路径
            for proc in psutil.process_iter(attrs=['pid', 'name']):
                if name in proc.info['name']:
                    process = psutil.Process(proc.info['pid'])
                    return process.exe()
            return None

        for retry in range(MAX_RETRY):
            try:
                if not game.switch_to_game():
                    if config.auto_set_resolution_enable:
                        game.change_resolution(1920, 1080)
                        game.change_auto_hdr("disable")

                    if not game.start_game():
                        raise Exception("启动游戏失败")
                    time.sleep(10)

                    if not wait_until(lambda: game.switch_to_game(), 60):
                        game.restore_resolution()
                        game.restore_auto_hdr()
                        raise TimeoutError("切换到游戏超时")

                    time.sleep(10)
                    game.restore_resolution()
                    game.restore_auto_hdr()
                    game.check_resolution_ratio(1920, 1080)

                    if not wait_until(lambda: check_and_click_enter(), 600):
                        raise TimeoutError("查找并点击进入按钮超时")
                    time.sleep(10)
                else:
                    game.check_resolution_ratio(1920, 1080)
                    if config.auto_set_game_path_enable:
                        program_path = get_process_path(config.game_process_name)
                        if program_path is not None and program_path != config.game_path:
                            config.set_value("game_path", program_path)
                            logger.info("游戏路径更新成功：{program_path}")

                if not wait_until(lambda: screen.get_current_screen(), 180):
                    raise TimeoutError("获取当前界面超时")
                break  # 成功启动游戏，跳出重试循环
            except Exception as e:
                logger.error(f"尝试启动游戏时发生错误：{e}")
                game.stop_game()  # 确保在重试前停止游戏
                if retry == MAX_RETRY - 1:
                    raise  # 如果是最后一次尝试，则重新抛出异常

    @staticmethod
    def stop(detect_loop=False):
        logger.hr("停止运行", 0)
        game = StarRailController(config.game_path, config.game_process_name, config.game_title_name, 'UnityWndClass', logger)

        def play_audio():
            logger.info("开始播放音频")
            os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
            import pygame.mixer

            pygame.init()
            pygame.mixer.music.load("./assets/audio/pa.mp3")
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            logger.info("播放音频完成")

        if config.play_audio:
            play_audio()

        if detect_loop and config.after_finish == "Loop":
            Game.after_finish_is_loop(game)
        else:
            if config.after_finish in ["Exit", "Loop", "Shutdown", "Hibernate", "Sleep"]:
                game.shutdown(config.after_finish)
            logger.hr("完成", 2)
            if config.after_finish not in ["Shutdown", "Hibernate", "Sleep"]:
                input("按回车键关闭窗口. . .")
            sys.exit(0)

    @staticmethod
    def after_finish_is_loop(game):

        def get_wait_time(current_power):
            # 距离体力到达配置文件指定的上限剩余秒数
            wait_time_power_limit = (config.power_limit - current_power) * 6 * 60
            # 距离第二天凌晨4点剩余秒数，+30避免显示3点59分不美观，#7
            wait_time_next_day = Date.get_time_next_x_am(config.refresh_hour) + random.randint(30, 600)
            # 取最小值
            wait_time = min(wait_time_power_limit, wait_time_next_day)
            return wait_time

        current_power = Power.get()
        if current_power >= config.power_limit:
            logger.info(f"🟣开拓力 >= {config.power_limit}")
            logger.info("即将再次运行")
            logger.hr("完成", 2)
        else:
            game.stop_game()
            wait_time = get_wait_time(current_power)
            future_time = Date.calculate_future_time(wait_time)
            logger.info(f"📅将在{future_time}继续运行")
            notify.notify(f"📅将在{future_time}继续运行")
            logger.hr("完成", 2)
            # 等待状态退出OCR避免内存占用
            ocr.exit_ocr()
            time.sleep(wait_time)
