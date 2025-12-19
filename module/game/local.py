import os
import psutil
import getpass
import subprocess
import win32gui
import pyperclip
from typing import Optional
from module.config.config import Config
from module.game.base import GameControllerBase
from utils.logger.logger import Logger

class LocalGameController(GameControllerBase):
    def __init__(self, cfg: Config, logger: Optional[Logger] = None) -> None:
        super().__init__(script_path=cfg.script_path, logger=logger)
        self.game_path = os.path.normpath(cfg.game_path)
        self.process_name = cfg.game_process_name
        self.window_name = cfg.game_title_name
        self.window_class = 'UnityWndClass'

    def start_game_process(self) -> bool:
        """启动游戏"""
        if not os.path.exists(self.game_path):
            self.log_error(f"游戏路径不存在：{self.game_path}")
            return False

        game_folder = self.game_path.rpartition('\\')[0]
        if not os.system(f'cmd /C start "" /D "{game_folder}" "{self.game_path}"'):
            self.log_info(f"游戏启动：{self.game_path}")
            return True
        else:
            self.log_error("启动游戏时发生错误")
            try:
                # 为什么有的用户环境变量内没有cmd呢？
                subprocess.Popen(self.game_path)
                self.log_info(f"游戏启动：{self.game_path}")
                return True
            except Exception as e:
                self.log_error(f"启动游戏时发生错误：{e}")
            return False

    @staticmethod
    def terminate_named_process(target_process_name, termination_timeout=10):
        """
        根据进程名终止属于当前用户的进程。

        参数:
        - target_process_name (str): 要终止的进程名。
        - termination_timeout (int, optional): 终止进程前等待的超时时间（秒）。

        返回值:
        - bool: 如果成功终止进程则返回True，否则返回False。
        """
        current_user = getpass.getuser()
        success = False

        for proc in psutil.process_iter(attrs=["pid", "name", "username"]):
            try:
                name = proc.info["name"]
                user = (proc.info["username"] or "").split("\\")[-1]  # 兼容 DOMAIN\\User
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

            # 精准匹配进程名并属于当前用户
            if target_process_name.lower() in name.lower() and user == current_user:
                try:
                    p = psutil.Process(proc.info["pid"])
                    p.terminate()
                    try:
                        p.wait(timeout=termination_timeout)
                    except psutil.TimeoutExpired:
                        # 超时直接kill
                        p.kill()
                        p.wait(timeout=3)

                    success = True

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.Error):
                    continue

        return success

    def get_input_handler(self):
        from module.automation.local_input import LocalInput
        return LocalInput(self.logger)

    def stop_game(self) -> bool:
        """终止游戏"""
        try:
            # os.system(f'taskkill /f /im {self.process_name}')
            self.terminate_named_process(self.process_name)
            self.log_info(f"游戏终止：{self.process_name}")
            return True
        except Exception as e:
            self.log_error(f"终止游戏时发生错误：{e}")
            return False

    def get_window_handle(self):
        return win32gui.FindWindow(self.window_class, self.window_name)
    
    def copy(self, text):
        pyperclip.copy(text)
