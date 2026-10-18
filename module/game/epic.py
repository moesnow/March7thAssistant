"""通过 Epic 协议启动 HoYoPlay 并进入游戏。"""
import json
import ntpath
import os
import time
from pathlib import Path
from urllib.parse import quote

import psutil
import win32gui
import win32process

from module.game.launcher import LauncherController
from utils.pause import pause_ctl


class EpicLaunchError(RuntimeError):
    """Epic 渠道启动失败。"""


def build_epic_launch_url(game_path):
    """将 StarRail.exe 所在目录编码为 Epic 启动链接。"""
    path = ntpath.normpath(game_path)
    if not ntpath.isabs(path) or ntpath.basename(path).lower() != "starrail.exe":
        raise ValueError("Epic 游戏路径必须是 StarRail.exe 的绝对路径")
    folder = ntpath.dirname(path).replace("\\", "/")
    return f"com.epicgames.launcher://apps/{quote(folder, safe='')}?action=launch&silent=true"


def _inside(path, root):
    try:
        path, root = ntpath.normcase(ntpath.normpath(path)), ntpath.normcase(ntpath.normpath(root))
        return ntpath.commonpath([path, root]) == root
    except ValueError:
        return False


def find_epic_install_root(game_path):
    """从 Epic 本地安装清单查找包含游戏路径的安装目录。"""
    manifest_dir = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Epic/EpicGamesLauncher/Data/Manifests"
    roots = set()
    for manifest in manifest_dir.glob("*.item"):
        try:
            with manifest.open(encoding="utf-8-sig") as stream:
                root = json.load(stream).get("InstallLocation")
            if isinstance(root, str) and ntpath.isabs(root) and _inside(game_path, root):
                roots.add(ntpath.normcase(ntpath.normpath(root)))
        except (OSError, ValueError, AttributeError):
            continue
    if len(roots) > 1:
        raise EpicLaunchError("Epic 启动[窗口归属]：多个安装目录包含游戏路径，无法确认渠道实例")
    return next(iter(roots), None)


class EpicLauncherController(LauncherController):
    """通过窗口标题和进程路径定位对应 Epic 安装目录下的 HoYoPlay。"""

    def __init__(self, install_root, logger):
        super().__init__(install_root or "", "HYP", "HoYoPlay", logger)
        self.install_root = install_root

    def get_window_handle(self):
        candidates = self.get_window_handles()
        if not candidates:
            return None
        if not self.install_root:
            raise EpicLaunchError("Epic 启动[窗口归属]：未找到包含游戏路径的 Epic 安装记录，不能确认 HoYoPlay 归属")
        matches = []
        for hwnd in candidates:
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                executable = psutil.Process(pid).exe()
            except (psutil.Error, OSError):
                raise EpicLaunchError("Epic 启动[窗口归属]：无法读取 HoYoPlay 进程路径，不能安全点击") from None
            if (ntpath.basename(executable).lower() in ("hyp.exe", "launcher.exe")
                    and _inside(executable, self.install_root)):
                matches.append(hwnd)
        if len(matches) > 1:
            raise EpicLaunchError("Epic 启动[窗口归属]：存在多个匹配的 HoYoPlay 窗口，停止操作")
        return matches[0] if matches else None


class EpicGameLauncher:
    LAUNCHER_TIMEOUT = 120
    BUTTON_TIMEOUT = 120
    GAME_TIMEOUT = 360
    # 按客户区比例定义按钮区域：(left, top, width, height)。
    BUTTON_REGION = (0.60, 0.70, 0.40, 0.30)
    START_TEXTS = ("开始游戏", "開始遊戲", "ゲーム開始", "게임 실행", "Start Game", "START GAME", "Launch Game", "Launch", "Play", "PLAY")

    def __init__(self, game):
        self.game = game
        self.stage = "打开协议"

    def _wait(self, condition, timeout):
        deadline = time.monotonic() + timeout
        while True:
            before_pause = time.monotonic()
            pause_ctl.checkpoint()
            deadline += time.monotonic() - before_pause
            if time.monotonic() >= deadline:
                return False
            if condition():
                return True
            time.sleep(0.5)

    def _game_ready(self):
        return bool(self.game.get_window_handle())

    def _find_launcher(self):
        if self._game_ready():
            return True
        self.hwnd = self.launcher.get_window_handle()
        return bool(self.hwnd)

    def _click_start(self):
        if self._game_ready():
            return True
        if self.launcher.get_window_handle() != self.hwnd:
            raise EpicLaunchError("Epic 启动[识别按钮]：HoYoPlay 窗口已变化，停止操作")
        self.launcher.set_foreground_window_with_retry(self.hwnd)
        from module.automation.launcher_automation import LauncherAutomation
        from module.automation.screenshot import Screenshot
        if self.automation is None:
            self.automation = LauncherAutomation("HoYoPlay", self.game.logger)
        left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
        origin = win32gui.ClientToScreen(self.hwnd, (left, top))
        region = (*origin, right - left, bottom - top)
        if region[2] <= 0 or region[3] <= 0:
            return False
        if win32gui.GetForegroundWindow() != self.hwnd:
            return False
        crop_region = (
            origin[0] + int(region[2] * self.BUTTON_REGION[0]),
            origin[1] + int(region[3] * self.BUTTON_REGION[1]),
            int(region[2] * self.BUTTON_REGION[2]),
            int(region[3] * self.BUTTON_REGION[3]),
        )
        # 截取窗口右下客户区，供 OCR 识别开始游戏按钮。
        image = Screenshot.capture_screen_with_mss(crop_region)
        if image is None:
            return False
        self.automation.screenshot = image
        self.automation.screenshot_pos = crop_region[:2]
        self.automation.screenshot_scale_factor = 1
        position = self.automation.find_element(
            self.START_TEXTS, "text", take_screenshot=False, include=False)
        if not position:
            return False
        # 暂停后重新截图识别；点击前确认窗口位置和前台状态。
        if pause_ctl.is_paused():
            return False
        if self._game_ready():
            return True
        if (self.launcher.get_window_handle() != self.hwnd
                or win32gui.GetForegroundWindow() != self.hwnd
                or win32gui.GetClientRect(self.hwnd) != (left, top, right, bottom)
                or win32gui.ClientToScreen(self.hwnd, (left, top)) != origin):
            return False
        self.automation.click_element_with_pos(position)
        self.game.log_info("Epic 启动[识别按钮]：已点击 HoYoPlay 开始游戏，停止按钮操作")
        return True

    def start(self):
        try:
            pause_ctl.checkpoint()
            if self._game_ready():
                return True
            url = build_epic_launch_url(self.game.game_path)
            self.game.log_info("Epic 启动[打开协议]：通过系统协议请求渠道启动")
            os.startfile(url)
            self.stage = "等待启动器"
            # Epic 直接打开游戏时跳过启动器识别。
            if not self._game_ready():
                root = find_epic_install_root(self.game.game_path)
                self.launcher = EpicLauncherController(root, self.game.logger)
                self.hwnd = None
                if not self._wait(self._find_launcher, self.LAUNCHER_TIMEOUT):
                    raise EpicLaunchError("Epic 启动[等待启动器]超时：游戏和匹配的 HoYoPlay 均未出现，请确认 Epic 已登录及游戏路径正确")
                if not self._game_ready():
                    self.game.log_info(f"Epic 启动[等待启动器]：已确认渠道 HoYoPlay 窗口 hwnd={self.hwnd}")
                    self.stage = "识别按钮"
                    self.automation = None
                    if not self._wait(self._click_start, self.BUTTON_TIMEOUT):
                        raise EpicLaunchError("Epic 启动[识别按钮]超时：未识别到右下角开始游戏，请确认登录完成、星铁页面已打开且无需更新")
            self.stage = "等待游戏"
            self.game.log_info("Epic 启动[等待游戏]：等待星铁窗口")
            if not self._wait(self._game_ready, self.GAME_TIMEOUT):
                raise EpicLaunchError("Epic 启动[等待游戏]超时：星铁窗口未出现，请检查 HoYoPlay 提示")
            self.game.log_info("Epic 启动[完成]：星铁窗口已出现，初始化及登录由现有进入游戏流程确认")
            return True
        except EpicLaunchError as error:
            self.game.log_error(str(error))
            raise
        except Exception as error:
            message = f"Epic 启动[{self.stage}]失败：{error}"
            if self.stage == "打开协议":
                message += "；请确认 Epic 已安装并注册启动协议，且已提前登录"
            self.game.log_error(message)
            raise EpicLaunchError(message) from error
