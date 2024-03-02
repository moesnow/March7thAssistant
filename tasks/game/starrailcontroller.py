import time
import logging
import pyautogui
from typing import Literal, Optional
from utils.gamecontroller import GameController
from utils.registry.star_rail_resolution import get_game_resolution, set_game_resolution
from utils.registry.game_auto_hdr import get_game_auto_hdr, set_game_auto_hdr


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
