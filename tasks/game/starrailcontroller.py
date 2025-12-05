import time
import pyautogui
from typing import Literal, Optional
from module.config.config import Config
from module.game.local import LocalGameController
from utils.registry.star_rail_setting import get_game_resolution, set_game_resolution, get_auto_battle_open_setting, get_is_save_battle_speed_setting, set_auto_battle_open_setting, set_is_save_battle_speed_setting
from utils.registry.game_auto_hdr import get_game_auto_hdr, set_game_auto_hdr
from utils.logger.logger import Logger


class StarRailController(LocalGameController):
    def __init__(self, cfg: Config, logger: Optional[Logger] = None) -> None:
        super().__init__(cfg=cfg, logger=logger)
        self.game_resolution = None
        self.game_auto_hdr = None
        self.screen_resolution = pyautogui.size()

    def change_resolution(self, width: int, height: int):
        """通过注册表修改游戏分辨率"""
        try:
            self.game_resolution = get_game_resolution()
            if self.game_resolution:
                screen_width, screen_height = self.screen_resolution
                is_fullscreen = False if screen_width > width or screen_height > height else True
                if self.game_resolution[0] == width and self.game_resolution[1] == height and self.game_resolution[2] == is_fullscreen:
                    self.game_resolution = None
                    return
                set_game_resolution(width, height, is_fullscreen)
                self.log_debug(f"修改游戏分辨率: {self.game_resolution[0]}x{self.game_resolution[1]} ({'全屏' if self.game_resolution[2] else '窗口'}) --> {width}x{height} ({'全屏' if is_fullscreen else '窗口'})")
        except FileNotFoundError:
            self.log_debug("指定的注册表项未找到")
        except Exception as e:
            self.log_error(f"读取注册表值时发生错误: {e}")

    def restore_resolution(self):
        """通过注册表恢复游戏分辨率"""
        try:
            if self.game_resolution:
                set_game_resolution(self.game_resolution[0], self.game_resolution[1], self.game_resolution[2])
                self.log_debug(f"恢复游戏分辨率: {self.game_resolution[0]}x{self.game_resolution[1]} ({'全屏' if self.game_resolution[2] else '窗口'})")
        except Exception as e:
            self.log_error(f"写入注册表值时发生错误: {e}")

    def change_auto_hdr(self, status: Literal["enable", "disable", "unset"] = "unset"):
        """通过注册表修改游戏自动 HDR 设置"""
        status_map = {"enable": "启用", "disable": "禁用", "unset": "未设置"}
        try:
            self.game_auto_hdr = get_game_auto_hdr(self.game_path)
            if self.game_auto_hdr == status:
                self.game_auto_hdr = None
                return
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
                self.log_error(f"游戏分辨率: {window_width}x{window_height} ≠ {target_width}x{target_height} 可能出现未预期的错误")
                time.sleep(2)
            else:
                self.log_debug(f"游戏分辨率: {window_width}x{window_height}")
            self.log_debug(f"桌面分辨率: {screen_width}x{screen_height}")

    def change_auto_battle(self, status: bool) -> None:
        auto_battle_status = get_auto_battle_open_setting()
        if auto_battle_status is not None and auto_battle_status != status:
            set_auto_battle_open_setting(status)
            self.log_debug(f"修改自动战斗状态: {'开启' if auto_battle_status else '关闭'} --> {'开启' if status else '关闭'}")
        save_battle_status = get_is_save_battle_speed_setting()
        if save_battle_status is not None and save_battle_status != status:
            set_is_save_battle_speed_setting(status)
            self.log_debug(f"修改沿用自动战斗设置: {'启用' if save_battle_status else '禁用'} --> {'启用' if status else '禁用'}")
