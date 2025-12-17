import os
import psutil
import getpass
import subprocess
import win32gui
from typing import Optional
from module.game.base import GameControllerBase
from module.config.config import Config
from utils.logger.logger import Logger


class LauncherController(GameControllerBase):
    def __init__(self, path, process_name, window_name, logger: Optional[Logger] = None,) -> None:
        super().__init__(script_path=None, logger=logger)
        self.game_path = os.path.normpath(path)
        self.process_name = process_name
        self.window_name = window_name

    def start_game_process(self, args: Optional[str] = None) -> bool:
        """启动启动器

        参数:
        - args (Optional[str]): 可选的命令行参数，例如 "--game=hkrpg_cn"，会附加到启动命令末尾。
        """
        if not os.path.exists(self.game_path):
            self.log_error(f"启动器路径不存在：{self.game_path}")
            return False

        game_folder = self.game_path.rpartition('\\')[0]
        args_str = f' {args.strip()}' if args else ''

        # 使用 cmd start 启动（带工作目录），并附加参数
        cmd = f'cmd /C start "" /D "{game_folder}" "{self.game_path}"{args_str}'
        if not os.system(cmd):
            self.log_info(f"启动器启动：{self.game_path}{args_str}")
            return True
        else:
            self.log_error("启动启动器时发生错误")
            try:
                # 为什么有的用户环境变量内没有cmd呢？
                if args:
                    import shlex
                    args_list = shlex.split(args)
                    subprocess.Popen([self.game_path] + args_list)
                else:
                    subprocess.Popen(self.game_path)
                self.log_info(f"启动器启动：{self.game_path}{args_str}")
                return True
            except Exception as e:
                self.log_error(f"启动启动器时发生错误：{e}")
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

    def stop_game(self) -> bool:
        """终止启动器"""
        try:
            # os.system(f'taskkill /f /im {self.process_name}')
            self.terminate_named_process(self.process_name)
            self.log_info(f"启动器终止：{self.process_name}")
            return True
        except Exception as e:
            self.log_error(f"终止启动器时发生错误：{e}")
            return False

    def get_window_handle(self):
        """
        只查找窗口标题匹配的窗口，返回其句柄。
        """
        def callback(hwnd, result):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title == self.window_name:
                    result.append(hwnd)
        result = []
        win32gui.EnumWindows(callback, result)
        return result[0] if result else None
