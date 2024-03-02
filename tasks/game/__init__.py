from managers.logger_manager import logger
from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.config_manager import config
from managers.notify_manager import notify
from managers.ocr_manager import ocr
from tasks.power.power import Power
from utils.date import Date
from utils.gamecontroller import GameController
from utils.registry.star_rail_resolution import get_game_resolution, set_game_resolution
from utils.registry.game_auto_hdr import get_game_auto_hdr, set_game_auto_hdr
from typing import Literal, Optional
import time
import logging
import pyautogui
import psutil
import random
import sys
import os


class StarRailController(GameController):
    def __init__(self, game_path: str, process_name: str, window_name: str, window_class: Optional[str], logger: Optional[logging.Logger] = None) -> None:
        super().__init__(game_path, process_name, window_name, window_class, logger)
        self.game_resolution = None
        self.game_auto_hdr = None
        self.screen_resolution = pyautogui.size()

    def change_resolution(self, width: int, height: int):
        """通过注册表修改游戏分辨率"""
        try:
            self.game_resolution = get_game_resolution()
            if self.game_resolution:
                screen_width, screen_height = self.screen_resolution
                is_fullscreen = False if screen_width > width and screen_height > height else True
                set_game_resolution(width, height, is_fullscreen)
                self.log_debug(f"修改游戏分辨率: {self.game_resolution[0]}x{self.game_resolution[1]} ({'全屏' if self.game_resolution[2] else '窗口'}) --> {width}x{height} ({'全屏' if is_fullscreen else '窗口'})")
        except FileNotFoundError:
            self.log_debug("指定的注册表项未找到")
        except Exception as e:
            self.log_error("读取注册表值时发生错误:", e)

    def restore_resolution(self):
        """通过注册表恢复游戏分辨率"""
        try:
            if self.game_resolution:
                set_game_resolution(self.game_resolution[0], self.game_resolution[1], self.game_resolution[2])
                self.log_debug(f"恢复游戏分辨率: {self.game_resolution[0]}x{self.game_resolution[1]} ({'全屏' if self.game_resolution[2] else '窗口'})")
        except Exception as e:
            self.log_error("写入注册表值时发生错误:", e)

    def change_auto_hdr(self, status: Literal["enable", "disable", "unset"] = "unset"):
        """通过注册表修改游戏自动 HDR 设置"""
        status_map = {"enable": "启用", "disable": "禁用", "unset": "未设置"}
        try:
            self.game_auto_hdr = get_game_auto_hdr(self.game_path)
            set_game_auto_hdr(self.game_path, status)
            self.log_debug(f"修改游戏自动 HDR: {status_map.get(self.game_auto_hdr)} --> {status_map.get(status)}")
        except Exception as e:
            self.log_debug(f"修改游戏自动 HDR 设置时发生错误：{e}")

    def restore_auto_hdr(self):
        """通过注册表恢复游戏自动 HDR 设置"""
        status_map = {"enable": "启用", "disable": "禁用", "unset": "未设置"}
        try:
            if self.game_auto_hdr:
                set_game_auto_hdr(self.game_path, self.game_auto_hdr)
            self.log_debug(f"恢复游戏自动 HDR: {status_map.get(self.game_auto_hdr)}")
        except Exception as e:
            self.log_debug(f"恢复游戏自动 HDR 设置时发生错误：{e}")

    def check_resolution(self, target_width: int, target_height: int) -> None:
        """
        检查游戏窗口的分辨率是否匹配目标分辨率。

        如果游戏窗口的分辨率与目标分辨率不匹配，则记录错误并抛出异常。
        如果桌面分辨率小于目标分辨率，也会记录错误建议。

        参数:
            target_width (int): 目标分辨率的宽度。
            target_height (int): 目标分辨率的高度。
        """
        resolution = self.get_resolution()
        if not resolution:
            raise Exception("游戏分辨率获取失败")
        window_width, window_height = resolution

        screen_width, screen_height = self.screen_resolution
        if window_width != target_width or window_height != target_height:
            self.log_error(f"游戏分辨率: {window_width}x{window_height}，请在游戏设置内切换为 {target_width}x{target_height} 窗口或全屏运行")
            if screen_width < target_width or screen_height < target_height:
                self.log_error(f"桌面分辨率: {screen_width}x{screen_height}，你可能需要更大的显示器或使用 HDMI/VGA 显卡欺骗器")
            raise Exception("游戏分辨率过低")
        else:
            self.log_debug(f"游戏分辨率: {window_width}x{window_height}")

    def check_resolution_ratio(self, target_width: int, target_height: int) -> None:
        """
        检查游戏窗口的分辨率和比例是否符合目标设置。

        如果游戏窗口的分辨率小于目标分辨率或比例不正确，则记录错误并抛出异常。
        如果桌面分辨率不符合最小推荐值，也会记录错误建议。

        参数:
            target_width (int): 目标分辨率的宽度。
            target_height (int): 目标分辨率的高度。
        """
        resolution = self.get_resolution()
        if not resolution:
            raise Exception("游戏分辨率获取失败")
        window_width, window_height = resolution

        screen_width, screen_height = self.screen_resolution

        if window_width < target_width or window_height < target_height:
            self.log_error(f"游戏分辨率: {window_width}x{window_height} 请在游戏设置内切换为 {target_width}x{target_height} 窗口或全屏运行")
            if screen_width < 1920 or screen_height < 1080:
                self.log_error(f"桌面分辨率: {screen_width}x{screen_height} 你可能需要更大的显示器或使用 HDMI/VGA 显卡欺骗器")
            raise Exception("游戏分辨率过低")
        elif abs(window_width / window_height - (target_width / target_height)) > 0.01:
            self.log_error(f"游戏分辨率: {window_width}x{window_height} 请在游戏设置内切换为 {target_width}:{target_height} 比例")
            raise Exception("游戏分辨率比例不正确")
        else:
            if window_width != target_width or window_height != target_height:
                self.log_warning(f"游戏分辨率: {window_width}x{window_height} ≠ {target_width}x{target_height} 可能出现未预期的错误")
                time.sleep(2)
            else:
                self.log_debug(f"游戏分辨率: {window_width}x{window_height}")


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
