import configparser
import os
import sys
import time
import psutil
import getpass
import subprocess
from contextlib import contextmanager
from pathlib import Path
from utils import clipboard
from utils.desktop_twin import in_desktop_twin
from typing import Optional
from module.config.config import Config
from module.game.base import GameControllerBase
from module.localization import tr
from utils.logger.logger import Logger
from utils.pause import pause_ctl
from utils.temporary_graphics import recover_temporary_graphics, restore_temporary_graphics


class LocalGameController(GameControllerBase):
    def __init__(self, cfg: Config, logger: Optional[Logger] = None) -> None:
        super().__init__(script_path=None, logger=logger)
        self.game_path = ""
        self.process_name = ""
        self.window_name = ""
        self.window_class = 'UnityWndClass'
        self.reload_config(cfg)

    def reload_config(self, cfg: Config) -> None:
        """从最新配置同步本地游戏控制器参数。"""
        self.script_path = os.path.normpath(cfg.script_path) if cfg.script_path else None
        self.game_path = os.path.normpath(cfg.game_path)
        self.process_name = cfg.game_process_name
        self.window_name = cfg.game_title_name
        self.launch_method = cfg.get_value("game_launch_method", "direct")
        self._config = cfg

    @contextmanager
    def launch_touch_game(self, resolution: tuple[int, int]):
        """为本地触屏开发启动游戏，进入游戏后恢复持久分辨率。"""
        if self._config.get_value("genshin_starRail_fps_unlocker_allow") is not True:
            raise PermissionError(tr("请先在工具箱的触屏模式中完成第三方解锁器的风险确认"))
        if self.is_game_running():
            yield
            return

        from utils.registry.star_rail_setting import (
            get_game_resolution, read_registry_value, registry_key_path,
            resolution_value_name, set_game_resolution, write_registry_value,
        )
        import winreg

        game_path = Path(self.game_path).resolve()
        if not game_path.is_file():
            raise FileNotFoundError(tr("请在“设置”→“程序”中配置正确的游戏路径"))
        directory = Path(self._config.genshin_starRail_fps_unlocker_path).resolve()
        unlocker = directory / "unlocker.exe"
        if not unlocker.is_file():
            raise FileNotFoundError(tr("未找到触屏解锁器，请先运行 mobileui_update"))

        original = read_registry_value(winreg.HKEY_CURRENT_USER, registry_key_path, resolution_value_name)
        if original is None or get_game_resolution() is None:
            raise RuntimeError(tr("未找到原始游戏分辨率，请先在游戏内保存分辨率设置"))

        config_path = directory / "hoyofps_config.ini"
        config = configparser.ConfigParser()
        config.read(config_path, encoding="utf-16")
        if not config.has_section("Setting"):
            config.add_section("Setting")
        setting = config["Setting"]
        if setting.get("HKSRPath") != str(game_path) or setting.get("FPS") != "60":
            setting.update({"HKSRPath": str(game_path), "FPS": "60"})
            with config_path.open("w", encoding="utf-16") as stream:
                config.write(stream)

        pause_ctl.checkpoint()
        try:
            set_game_resolution(*resolution, False)
            launcher = subprocess.Popen(
                [str(unlocker), "-HKSR", "-EnableMobileUI"],
                cwd=directory,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            self.log_info("正在启动触屏模式")
            deadline = time.monotonic() + 90
            while self.get_resolution() != resolution:
                pause_ctl.checkpoint()
                if time.monotonic() >= deadline:
                    raise TimeoutError(tr("等待 1280×720 触屏游戏窗口超时"))
                exit_code = launcher.poll()
                if exit_code:
                    raise RuntimeError(tr("触屏解锁器启动失败，退出码为 {code}").format(code=exit_code))
                time.sleep(0.25)
            # 首次出现 720p 窗口时游戏仍可能在读注册表，须等登录画面加载并进入场景。
            yield
        finally:
            write_registry_value(winreg.HKEY_CURRENT_USER, registry_key_path, resolution_value_name,
                                 original, winreg.REG_BINARY)

    def start_game_process(self) -> bool:
        """启动游戏"""
        # 包括图形界面的“启动游戏”：先恢复已退出任务的备份，不给手动启动降画质。
        if self.logger is not None:
            recover_temporary_graphics(self.logger)
        if self.is_game_running():
            self.log_info("游戏已运行，复用现有游戏窗口")
            return True

        if in_desktop_twin():
            from utils.desktop_twin import check_game_config
            from utils.windows_session import process_session_id
            check_game_config(self._config, process_session_id())

        if not os.path.exists(self.game_path):
            self.log_error(f"游戏路径不存在：{self.game_path}")
            return False

        if self.launch_method == "epic":
            from module.game.epic import EpicGameLauncher
            return EpicGameLauncher(self).start()
        if self.launch_method != "direct":
            self.log_error(f"未知的游戏启动方式：{self.launch_method}")
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
    def terminate_named_process(target_process_name, termination_timeout=10, *, executable=None):
        """
        根据进程名终止属于当前用户和当前桌面会话的进程。

        参数:
        - target_process_name (str): 要终止的进程名。
        - termination_timeout (int, optional): 终止进程前等待的超时时间（秒）。
        - executable (str, optional): 要求实际可执行文件路径相符。

        返回值:
        - bool: 如果成功终止进程则返回True，否则返回False。
        """
        current_user = getpass.getuser()
        session_id = None
        if sys.platform == "win32":
            from utils.windows_session import process_session_id
            session_id = process_session_id()
        expected_path = os.path.normcase(os.path.abspath(executable)) if executable else None
        success = False

        for proc in psutil.process_iter(attrs=["pid", "name", "username"]):
            try:
                name = proc.info["name"]
                user = (proc.info["username"] or "").split("\\")[-1]  # 兼容 DOMAIN\\User
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

            # 精准匹配进程名并属于当前用户
            if name and target_process_name.lower() in name.lower() and user == current_user:
                try:
                    if session_id is not None and process_session_id(proc.pid) != session_id:
                        continue
                    if expected_path and os.path.normcase(proc.exe()) != expected_path:
                        continue
                    # psutil 会在 terminate / kill 前复核进程创建时间，避免 PID 复用。
                    proc.terminate()
                    try:
                        proc.wait(timeout=termination_timeout)
                    except psutil.TimeoutExpired:
                        # 超时直接kill
                        proc.kill()
                        proc.wait(timeout=3)

                    success = True

                except Exception:
                    continue

        return success

    def get_input_handler(self):
        from module.automation.input_base import background_enabled
        if background_enabled(self._config):
            from module.automation.background_input import BackgroundInput
            return BackgroundInput(self.logger, self.window_name, self.process_name,
                                   protect_mouse=self._config.get_value('background_mouse_protection', False))
        from module.automation.local_input import LocalInput
        return LocalInput(self.logger)

    def switch_to_game(self, force=False) -> bool:
        from module.automation.input_base import background_enabled
        if not force and background_enabled(self._config):
            # 后台模式不激活、不还原游戏窗口，只报告窗口当前能否后台操作；不阻塞也不抛出，图形界面也会调用。
            # 窗口存在但暂时不可用（例如被最小化）时由启动流程等待，不能当作游戏未运行而重新启动。
            from module.automation.windows_input import WindowsInputApi
            return WindowsInputApi().inspect(self.window_name, self.process_name)[1] is None
        return super().switch_to_game()

    def stop_game(self) -> bool:
        """终止游戏"""
        try:
            if in_desktop_twin():
                self.terminate_named_process(self.process_name, executable=self.game_path)
            else:
                self.terminate_named_process(self.process_name)
            # 终止后、关机/睡眠等系统操作之前恢复，避免退出时写回临时设置。
            restore_temporary_graphics(final=True)
            self.log_info(f"游戏终止：{self.process_name}")
            return True
        except Exception as e:
            self.log_error(f"终止游戏时发生错误：{e}")
            return False

    def get_window_handle(self):
        import win32gui  # 延迟导入，避免非 Windows 平台报错
        return win32gui.FindWindow(self.window_class, self.window_name)

    def copy(self, text):
        clipboard.copy(text)
