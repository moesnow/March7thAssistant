from abc import abstractmethod
import os
import time
import subprocess
import win32gui
import ctypes
from typing import Literal, Tuple, Optional
from utils.logger.logger import Logger


class GameControllerBase:
    def __init__(self, script_path: Optional[str] = None, logger: Optional[Logger] = None) -> None:
        self.script_path = os.path.normpath(script_path) if script_path and isinstance(script_path, (str, bytes, os.PathLike)) else None
        self.logger = logger

    def log_debug(self, message: str) -> None:
        """记录调试日志，如果logger不为None"""
        if self.logger is not None:
            self.logger.debug(message)

    def log_info(self, message: str) -> None:
        """记录信息日志，如果logger不为None"""
        if self.logger is not None:
            self.logger.info(message)

    def log_error(self, message: str) -> None:
        """记录错误日志，如果logger不为None"""
        if self.logger is not None:
            self.logger.error(message)

    def log_warning(self, message: str) -> None:
        """记录警告日志，如果logger不为None"""
        if self.logger is not None:
            self.logger.warning(message)

    @abstractmethod
    def start_game_process(self) -> bool:
        """启动游戏进程"""
        ...

    @abstractmethod
    def stop_game(self) -> bool:
        """终止游戏"""
        ...

    @abstractmethod
    def get_window_handle(self) -> int:
        """获取 window handle"""
        ...

    @abstractmethod
    def get_input_handler(self):  # -> InputBase
        """获取用于模拟鼠标和键盘操作的类"""
        ...

    def switch_to_game(self) -> bool:
        """将游戏窗口切换到前台"""
        try:
            hwnd = self.get_window_handle()
            if hwnd == 0:
                self.log_debug("游戏窗口未找到")
                return False
            self.set_foreground_window_with_retry(hwnd)
            self.log_info("游戏窗口已切换到前台")
            return True
        except Exception as e:
            self.log_error(f"激活游戏窗口时发生错误：{e}")
            return False

    def get_resolution(self) -> Optional[Tuple[int, int]]:
        """检查游戏窗口的分辨率"""
        try:
            hwnd = self.get_window_handle()
            if hwnd == 0:
                self.log_debug("游戏窗口未找到")
                return None
            _, _, window_width, window_height = win32gui.GetClientRect(hwnd)
            return window_width, window_height
        except IndexError:
            self.log_debug("游戏窗口未找到")
            return None

    def shutdown(self, action: Literal['Exit', 'Loop', 'Shutdown', 'Sleep', 'Hibernate', 'Restart', 'Logoff', 'TurnOffDisplay', 'RunScript'], delay: int = 60) -> bool:
        """
        终止游戏并在指定的延迟后执行系统操作：关机、睡眠、休眠、重启、注销。

        参数:
            action: 要执行的系统操作。
            delay: 延迟时间，单位为秒，默认为60秒。

        返回:
            操作成功执行返回True，否则返回False。
        """
        self.stop_game()
        if action not in ["Shutdown", "Sleep", "Hibernate", "Restart", "Logoff", "TurnOffDisplay", "RunScript"]:
            return True

        self.log_warning(f"将在{delay}秒后开始执行系统操作：{action}")
        time.sleep(delay)  # 暂停指定的秒数

        try:
            if action == 'Shutdown':
                os.system("shutdown /s /t 0")
            elif action == 'Sleep':
                # 必须先关闭休眠，否则下面的指令不会进入睡眠，而是优先休眠
                os.system("powercfg -h off")
                os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
                os.system("powercfg -h on")
            elif action == 'Hibernate':
                os.system("shutdown /h")
            elif action == 'Restart':
                os.system("shutdown /r")
            elif action == 'Logoff':
                os.system("shutdown /l")
            elif action == 'TurnOffDisplay':
                HWND_BROADCAST = 0xFFFF
                WM_SYSCOMMAND = 0x0112
                SC_MONITORPOWER = 0xF170
                ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, 2)
            elif action == 'RunScript':
                self.run_script()
            self.log_info(f"执行系统操作：{action}")
            return True
        except Exception as e:
            self.log_error(f"执行系统操作时发生错误：{action}, 错误：{e}")
            return False

    def run_script(self) -> bool:
        """运行指定的程序或脚本（支持.exe、.ps1和.bat）"""
        if not self.script_path or not isinstance(self.script_path, str) or not os.path.exists(
                self.script_path):
            self.log_warning(f"指定的路径无效或不存在：{self.script_path}")
            return False

        try:
            # 获取脚本所在目录
            script_dir = os.path.dirname(os.path.abspath(self.script_path))
            # 保存当前工作目录
            original_cwd = os.getcwd()

            try:
                # 切换到脚本所在目录
                os.chdir(script_dir)

                file_ext = os.path.splitext(self.script_path)[1].lower()
                if file_ext == '.ps1':
                    # PowerShell脚本
                    subprocess.Popen(["powershell", "-ExecutionPolicy", "Bypass", "-File", self.script_path],
                                     creationflags=subprocess.CREATE_NEW_CONSOLE)
                    self.log_info(f"已启动PowerShell脚本：{self.script_path}")
                elif file_ext == '.bat':
                    # Batch脚本
                    subprocess.Popen([self.script_path], shell=True,
                                     creationflags=subprocess.CREATE_NEW_CONSOLE)
                    self.log_info(f"已启动Batch脚本：{self.script_path}")
                elif file_ext == '.exe':
                    # 可执行文件
                    subprocess.Popen([self.script_path],
                                     creationflags=subprocess.CREATE_NEW_CONSOLE)
                    self.log_info(f"已启动可执行文件：{self.script_path}")
                else:
                    self.log_warning(f"不支持的文件类型：{file_ext}")
                    return False
                return True
            finally:
                # 恢复原始工作目录
                os.chdir(original_cwd)
        except Exception as e:
            self.log_error(f"启动脚本时发生错误：{str(e)}")
            return False

    @staticmethod
    def set_foreground_window_with_retry(hwnd) -> None:
        """尝试将窗口设置为前台，失败时先最小化再恢复。"""

        def toggle_window_state(hwnd, minimize=False):
            """最小化或恢复窗口。"""
            SW_MINIMIZE = 6
            SW_RESTORE = 9
            state = SW_MINIMIZE if minimize else SW_RESTORE
            ctypes.windll.user32.ShowWindow(hwnd, state)

        toggle_window_state(hwnd, minimize=False)
        if ctypes.windll.user32.SetForegroundWindow(hwnd) == 0:
            toggle_window_state(hwnd, minimize=True)
            toggle_window_state(hwnd, minimize=False)
            if ctypes.windll.user32.SetForegroundWindow(hwnd) == 0:
                raise Exception("Failed to set window foreground")
