from utils.game_options import game_option_enabled
import os
import sys
import time
import psutil
from contextlib import nullcontext


from module.accounts.runtime import AccountError, load_acc_and_pwd, mark_expired, prepare_launch, verify_ready
from module.accounts.switching import renew as renew_login
from utils.registry.gameaccount import gamereg_uid
from .starrailcontroller import GameResolutionMismatch, StarRailController
from .adb_check import wait_for_game as wait_for_adb_game

from utils.date import Date
from utils.console import pause_on_success
from utils.desktop_twin import in_desktop_twin
from tasks.power.power import Power
from module.game import cloud_game, get_game_controller
from module.game.adb_transport import AdbError
from module.game.cloud import (
    CloudGameDisconnectedError, CloudGameLoginTimeoutError, CloudGamePageNotReadyError, CloudGameProbeUnready,
    CloudGameQueueTimeoutError, CloudGameZeroDurationError,
)
from module.logger import log
from module.screen import screen
from module.automation import auto
from module.automation.automation import screenshot_retry_timeout
from module.automation.background_input import WINDOW_WAIT_SECONDS, GameWindowLost, InputInterrupted
from module.automation.windows_input import WindowsInputApi
from module.config import cfg
from module.config.platform import ProfileAssetNotFoundError, TouchProfileInputError, get_control_backend, get_ui_profile
from module.notification import notif
from module.notification.notification import NotificationLevel
from tasks.base.base import Base
from tasks.base.task_steps import GameRecoveryError
from module.ocr import ocr
from module.localization import tr
from utils.console import is_gui_started
from utils.pause import RunStopRequested, pause_ctl
from utils.runs import describe_run, idle_without_run_lock
from utils.temporary_graphics import begin_temporary_graphics, restore_temporary_graphics
from utils.wait import wait_until
from utils.windows_power import task_power_request
from utils.windows_session import process_session_id


class GameClientOutdatedError(RuntimeError):
    """游戏客户端版本过低（供 except 类型判断，勿用文本匹配异常消息）。"""


class GameStartupUnavailable(InputInterrupted, GameRecoveryError):
    """启动时无法确认游戏可用，保留当前游戏现场。"""

    reason = "game_startup_unavailable"


def start(headless=None, *, optimize_graphics=True, screen_ready=None, preserve_cloud_session=False):
    task_power_request.acquire(log)
    log.hr("开始运行", 0)
    if isinstance(getattr(cfg, "bound_account", None), str):
        pause_ctl.checkpoint()
        prepare_launch(cfg)
    try:
        start_game(headless=headless, optimize_graphics=optimize_graphics, screen_ready=screen_ready,
                   preserve_cloud_session=preserve_cloud_session)
    except GameStartupUnavailable as error:
        layer = getattr(cfg, "_account_layer", None)
        if layer is not None and getattr(layer, "login_prompt_seen", False) is True:
            raise AccountError("account_login_expired", "登录过期，本次未能完成登录，请在客户端重新登录") from error
        raise
    verify_ready(cfg)
    log.hr("完成", 2)


def switch_to_game():
    log.hr("切换到游戏窗口", 0)
    if get_control_backend(cfg) == "adb":
        get_game_controller().switch_to_game()
    else:
        starrail = StarRailController(cfg=cfg, logger=log)
        starrail.switch_to_game(force=True)
    log.hr("完成", 2)


def _local_game_process_running(controller):
    try:
        if controller.is_game_running():
            return True
        return WindowsInputApi().process_running(controller.process_name, session_id=process_session_id())
    except Exception as error:
        log.debug(f"暂未确认本地游戏进程状态：{error}")
        return None


def _wait_for_local_foreground(controller, timeout):
    def activate():
        pause_ctl.checkpoint()
        if controller.switch_to_game():
            return True
        if _local_game_process_running(controller) is False:
            raise GameWindowLost("游戏进程已退出，无法激活游戏窗口")
        return False

    activated = wait_until(activate, min(WINDOW_WAIT_SECONDS, timeout))
    pause_ctl.checkpoint()
    if not activated:
        raise GameStartupUnavailable("无法将本地游戏窗口切到前台，已保留游戏现场")


def _wait_for_local_window(controller, timeout):
    if getattr(auto.input_handler, "is_background", False) is not True:
        _wait_for_local_foreground(controller, timeout)
        return
    try:
        auto.input_handler.wait_for_window(min(WINDOW_WAIT_SECONDS, timeout))
    except GameWindowLost as error:
        if _local_game_process_running(controller) is False:
            raise
        raise GameStartupUnavailable(f"游戏窗口持续不可用，已保留游戏现场：{error}") from error
    except InputInterrupted as error:
        raise GameStartupUnavailable(f"游戏窗口持续不可用，已保留游戏现场：{error}") from error
    pause_ctl.checkpoint()


def prepare_local_takeover():
    """让已有本地游戏进入可操作状态，保留游戏进程与对局。"""
    pause_ctl.checkpoint()
    try:
        _wait_for_local_window(StarRailController(cfg=cfg, logger=log), WINDOW_WAIT_SECONDS)
    except GameWindowLost as error:
        raise GameStartupUnavailable(f"无法接管本地游戏：{error}") from error


def connect_to_running_cloud_game():
    """有限重试连接已有云游戏会话。"""
    attempts = 3
    for attempt in range(1, attempts + 1):
        pause_ctl.checkpoint()
        connected = cloud_game.connect_to_running_game()
        pause_ctl.checkpoint()
        if connected:
            return True
        if attempt < attempts:
            log.warning(f"暂未连接到正在运行的云游戏，重新连接（{attempt}/{attempts}）")
            time.sleep(1)
    return False


def ensure_game_ready():
    """连接云游戏会话，或校验本地游戏窗口可操作（workflow 执行前置）。

    与流程编排启动语义一致：游戏未启动或切换失败时记录错误并返回 False，
    由调用方决定如何终止（本地与云游戏均经 controller 处理）。
    """
    backend = get_control_backend(cfg)
    controller = get_game_controller()
    if backend == "cloud":
        if not controller.connect_to_running_game():
            log.error("云游戏会话未就绪，workflow 未执行")
            return False
        return True
    if backend == "adb":
        start_game()
        return True
    if not controller.is_game_running():
        log.error("未检测到游戏窗口，workflow 未执行")
        return False
    if backend != "local":
        return True
    if getattr(auto.input_handler, 'is_background', False) is True:
        # 后台模式不切换前台：窗口暂时不可操作（例如被最小化）时等待还原，失败时写明原因
        try:
            auto.input_handler.wait_for_window(WINDOW_WAIT_SECONDS)
        except (InputInterrupted, GameWindowLost) as error:
            log.error(f"{error}，workflow 未执行")
            return False
        return True
    if not controller.switch_to_game():
        log.error("切换到游戏窗口失败，workflow 未执行")
        return False
    return True


def _start_local_touch_game():
    controller = get_game_controller("local")
    profile = get_ui_profile(cfg)

    def touch_game_ready():
        pause_ctl.checkpoint()
        if controller.get_resolution() != profile.resolution:
            return False
        if screen.get_current_screen(autotry=False):
            return True
        auto.click_element("./assets/touch_720/images/screen/click_enter.png", "image", 0.9,
                           crop=(840 / 1920, 930 / 1080, 240 / 1920, 130 / 1080))
        return False

    with controller.launch_touch_game(profile.resolution):
        if getattr(auto.input_handler, "is_background", False) is True:
            auto.input_handler.wait_for_window(WINDOW_WAIT_SECONDS)
        elif not controller.switch_to_game():
            raise RuntimeError(tr("切换到游戏窗口失败"))
        if controller.get_resolution() != profile.resolution:
            raise RuntimeError(tr("请退出当前游戏，再启动 1280×720 触屏模式"))
        if not wait_until(touch_game_ready, cfg.start_game_timeout * 60):
            raise TimeoutError(tr("未能进入触屏主界面，请检查游戏登录状态"))


def start_game(headless=None, *, optimize_graphics=True, screen_ready=None, preserve_cloud_session=False):
    """启动或接管游戏。可选的任务就绪回调补充只读画面识别。"""
    backend = get_control_backend(cfg)
    timeout = getattr(cfg, "start_game_timeout", 10) * 60
    if backend == "adb":
        controller = get_game_controller(backend)

        def recover():
            try:
                with screenshot_retry_timeout(0):
                    if auto.find_element(("消息获取失败", "网络连接失败"), "text", crop=(0.30, 0.40, 0.40, 0.18), include=True):
                        if auto.click_element("确认", "text", crop=(0.35, 0.59, 0.30, 0.17)):
                            log.info("已关闭 Android 启动时的网络提示，重新检查游戏画面")
                        return
                    if screen.get_current_screen(autotry=False, max_retries=1) and screen.can_change_from(screen.current_screen, "main"):
                        screen.change_to("main", max_recursion=0)
            except AdbError as error:
                if error.code not in {"frame_timeout", "frame_clock_unavailable"}:
                    raise
                log.debug(f"ADB 启动恢复：{error}")
            except TouchProfileInputError:
                raise
            except RuntimeError as error:
                log.debug(f"ADB 启动恢复：{error}")

        controller.start_game_process()
        wait_for_adb_game(controller, timeout, recover=recover)
        return
    if backend == "local" and get_ui_profile(cfg).name == "touch_720":
        _start_local_touch_game()
        return

    MAX_RETRY = 3
    login_attempts = 0
    credentials_started = False
    login_error = None

    def remaining_startup_time():
        return max(0, deadline - time.monotonic())

    def reset_login_attempts():
        nonlocal login_attempts, credentials_started, login_error
        login_attempts = 0
        credentials_started = False
        login_error = None

    def mark_credentials_started():
        nonlocal credentials_started
        pause_ctl.checkpoint()
        credentials_started = True

    def login_with_saved_credentials(login, *, before_credentials=None):
        if load_acc_and_pwd(gamereg_uid()) == (None, None):
            return False
        log.info("检测到登录过期，尝试自动登录")
        login(before_credentials=before_credentials)
        return True

    def try_local_login():
        nonlocal login_attempts, login_error
        if credentials_started or login_attempts >= MAX_RETRY:
            return False
        if auto.find_element("./assets/images/screen/account_and_password.png", "image", 0.9, take_screenshot=False):
            login = auto_login
        elif auto.find_element("./assets/images/screen/password_field.png", "image", 0.9, take_screenshot=False):
            if not auto.find_element("./assets/images/screen/account_field_os.png", "image", 0.9, take_screenshot=False):
                # 登陆界面仍在，等到能确认账号输入框后再输入。
                return True
            login = auto_login_os
        else:
            return False
        login_attempts += 1
        mark_expired(cfg)
        try:
            found_credentials = login_with_saved_credentials(login, before_credentials=mark_credentials_started)
        except (InputInterrupted, GameWindowLost, GameRecoveryError, ProfileAssetNotFoundError, TouchProfileInputError):
            raise
        except (OSError, RuntimeError) as error:
            pause_ctl.checkpoint()
            login_error = error
            if login_attempts >= MAX_RETRY:
                raise GameStartupUnavailable(f"未能完成本地游戏登录：{error}，已保留游戏现场") from error
            # 凭据输入前失败时复核原登录页，再决定是否重试。
            return True
        if not found_credentials:
            from utils.runs import publish_progress
            publish_progress(login_required="local")
            if isinstance(getattr(cfg, "bound_account", None), str):
                raise AccountError("account_login_expired", "账号登录过期，请重新登录或保存账号密码")
            raise GameStartupUnavailable("本地游戏账号登录过期，未找到保存的登录凭据，已保留游戏现场")
        login_error = None
        return True

    def check_local_client_version():
        if auto.find_element("前往启动器下载最新客户端", "text", take_screenshot=False, include=True):
            raise GameClientOutdatedError(tr("检测到游戏客户端版本过低，请前往启动器下载最新客户端"))

    def check_and_click_enter():
        # 点击进入
        if auto.click_element("./assets/images/screen/click_enter.png", "image", 0.9):
            return True
        check_local_client_version()
        if credentials_started or try_local_login():
            return False
        # 游戏热更新，需要确认重启
        auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, take_screenshot=False)
        # 网络异常等问题，需要重新启动
        auto.click_element("./assets/images/zh_CN/base/restart.png", "image", 0.9, take_screenshot=False)
        # 适配国际服，需要点击“开始游戏”
        auto.click_element("./assets/images/screen/start_game.png", "image", 0.9, take_screenshot=False)
        # 出现多账号登录页时，需要点击“登录其他账号”
        auto.click_element("./assets/images/screen/login_switch_account.png", "image", 0.9, take_screenshot=False)
        # 适配用户协议和隐私政策更新提示，需要点击“同意”
        auto.click_element("./assets/images/screen/agree_update.png", "image", 0.9, take_screenshot=False)
        # 适配B服，需要点击“登录”，强制使用前台截图方式（#901）
        if auto.find_element(("bilibili游戏隐私政策提示", "登录记录"), "text", use_background_screenshot=False):
            if auto.matched_text == "bilibili游戏隐私政策提示":
                auto.click_element("同意", "text", take_screenshot=False)
            elif auto.matched_text == "登录记录":
                auto.click_element("登录", "text", take_screenshot=False)
        else:
            auto.click_element("./assets/images/screen/bilibili_login.png", "image", 0.9, take_screenshot=False)
            auto.click_element("./assets/images/screen/bilibili_login_2.png", "image", 0.9, take_screenshot=False)
            auto.click_element("./assets/images/screen/bilibili_login_3.png", "image", 0.9, take_screenshot=False)
            auto.click_element("./assets/images/screen/bilibili_agree_update.png", "image", 0.9, take_screenshot=False)
            auto.click_element("./assets/images/screen/bilibili_agree_update_2.png", "image", 0.9, take_screenshot=False)

        return False

    def cloud_game_check_and_enter():
        def cloud_click_element(*args, **kwargs):
            kwargs.setdefault("prefer_frame_screenshot", False)
            return auto.click_element(*args, **kwargs)

        # 点击进入
        if cloud_click_element("./assets/images/screen/click_enter.png", "image", 0.9):
            return True
        # 同意浏览器授权
        if cloud_click_element("./assets/images/screen/cloud/agree_to_authorize.png", "image", 0.9, take_screenshot=False):
            time.sleep(0.5)
            cloud_click_element("每次访问时都充许", "text", 0.9)
        # 是否保存网页地址，点击 x 关闭
        cloud_click_element("./assets/images/screen/cloud/close.png", "image", 0.9, take_screenshot=False)
        # 是否将《云·星穹铁道》添加到桌面，需要点击“下次再说”
        cloud_click_element("./assets/images/screen/cloud/next_time.png", "image", 0.9, take_screenshot=False)
        # 免责声明，需要点击“接受”
        cloud_click_element("./assets/images/screen/cloud/accept.png", "image", 0.9, take_screenshot=False)
        # 适配用户协议和隐私政策更新提示，需要点击“同意”
        cloud_click_element("./assets/images/screen/agree_update.png", "image", 0.9, take_screenshot=False)
        # 云游戏设置的引导，需要多次点击 “下一步”
        if cloud_click_element("下一步", "text", 0.9, include=True, take_screenshot=False):
            time.sleep(0.5)
            cloud_click_element("下一步", "text", 0.9, include=True)
            time.sleep(0.5)
            cloud_click_element("我知道了", "text", 0.9, include=True)
        # 由于浏览器语言原因，云游戏启动时可能会是默认英文，需要改成中文
        if cloud_click_element("Settings", "text", 0.9, take_screenshot=False):
            time.sleep(0.5)
            cloud_click_element("English", "text", 0.9, crop=(1541.0 / 1920, 198.0 / 1080, 156.0 / 1920, 58.0 / 1080))
            time.sleep(0.5)
            cloud_click_element("简体中文", "text", 0.9)
            time.sleep(0.5)
            auto.press_key("esc")

    def get_process_path(name):
        # 通过进程名获取运行路径
        for proc in psutil.process_iter(attrs=['pid', 'name']):
            if name in proc.info['name']:
                process = psutil.Process(proc.info['pid'])
                return process.exe()
        return None

    def update_game_path(program_path):
        if program_path and program_path != cfg.game_path:
            cfg.set_value("game_path", program_path)
            log.info(f"游戏路径更新成功：{program_path}")

    def start_local_game(starrail):
        nonlocal started_local_process
        resolution = get_ui_profile(cfg).resolution

        def switch_to_window():
            pause_ctl.checkpoint()
            return starrail.switch_to_game()

        def check_local_resolution():
            try:
                starrail.check_resolution(*resolution)
            except (GameWindowLost, InputInterrupted):
                raise
            except (OSError, RuntimeError) as error:
                raise GameWindowLost(f"读取游戏窗口分辨率失败：{error}") from error

        background = getattr(auto.input_handler, 'is_background', False) is True
        switched = not background and switch_to_window()
        if not switched and _local_game_process_running(starrail) is not False:
            _wait_for_local_window(starrail, remaining_startup_time())
            switched = True
        if not switched:
            try:
                if game_option_enabled(cfg, "auto_set_resolution_enable"):
                    starrail.change_resolution(*resolution)
                    starrail.change_auto_hdr("disable")

                if game_option_enabled(cfg, "auto_battle_detect_enable"):
                    if in_desktop_twin():
                        # 分身与主桌面共用游戏设置，启动前不改写；战斗中检测到未开启会自动补开。
                        log.debug("桌面分身内跳过启动前改写自动战斗和二倍速")
                    else:
                        starrail.change_auto_battle(True)

                if optimize_graphics and game_option_enabled(cfg, "auto_lower_graphics_enable"):
                    begin_temporary_graphics(starrail.game_path, log)

                if not starrail.start_game_process():
                    raise RuntimeError("启动游戏失败")
                started_local_process = starrail.launched_new_process is True
                switched = starrail.launched_new_process is False
                if started_local_process:
                    reset_login_attempts()
                if not switched:
                    time.sleep(10)

                # 直启前刚发现的已有进程也走有界的接管等待，超时保留游戏现场。
                if switched or background:
                    _wait_for_local_window(starrail, remaining_startup_time())
                elif not wait_until(switch_to_window, remaining_startup_time()):
                    pause_ctl.checkpoint()
                    raise TimeoutError("切换到游戏超时")

                if not switched:
                    time.sleep(10)
            finally:
                # 游戏已读取临时值后尽早恢复持久配置，缩短强杀/断电的风险窗口。
                # 备份保留到任务结束，届时再次检查可能的游戏写回。
                restore_temporary_graphics()
                starrail.restore_resolution()
                starrail.restore_auto_hdr()
        check_local_resolution()

        if not switched:
            if not wait_until(check_and_click_enter, remaining_startup_time()):
                pause_ctl.checkpoint()
                if credentials_started:
                    if _local_game_process_running(starrail) is False:
                        raise GameWindowLost("游戏进程已退出，未能完成本地游戏登录")
                    message = "未能完成本地游戏登录"
                    if login_error is not None:
                        message += f"：{login_error}"
                    raise GameStartupUnavailable(f"{message}，已保留游戏现场") from login_error
                if login_error is not None:
                    raise TimeoutError(f"未能完成本地游戏登录：{login_error}") from login_error
                raise TimeoutError("查找并点击进入按钮超时")

            # 偶现加载慢时分辨率修改不成功，进入游戏前增加一次分辨率检查
            check_local_resolution()

            time.sleep(10)
            # 修复B服问题 https://github.com/moesnow/March7thAssistant/discussions/321#discussioncomment-10565807
            auto.press_mouse()
        else:
            if cfg.auto_set_game_path_enable:
                update_game_path(get_process_path(cfg.game_process_name))
            time.sleep(1)

    cloud_disconnected = False

    def cloud_startup_entry():
        nonlocal cloud_disconnected
        last_error = None
        for attempt in range(MAX_RETRY):
            pause_ctl.checkpoint()
            try:
                in_game = cloud_game.is_in_game()
                pause_ctl.checkpoint()
                if in_game:
                    return "running"
                if preserve_cloud_session:
                    entry = cloud_game.startup_entry(disconnected=cloud_disconnected)
                    if entry is not None:
                        pause_ctl.checkpoint()
                        return entry
                    if cloud_disconnected:
                        raise CloudGameProbeUnready("云游戏断开后暂未确认播放器或原排队状态，或可重新进入的大厅")
                    raise CloudGameProbeUnready("暂未确认云游戏播放器、大厅或排队状态")
                if last_error is None:
                    return "enter"
            except (CloudGameDisconnectedError, CloudGameProbeUnready, TimeoutError) as error:
                cloud_disconnected |= isinstance(error, CloudGameDisconnectedError)
                last_error = error
            pause_ctl.checkpoint()
            if attempt + 1 < MAX_RETRY:
                log.warning(f"暂未确认云游戏会话，等待复核：{last_error}")
                time.sleep(1)
        raise GameStartupUnavailable(f"云游戏连接持续不可用，已保留游戏现场：{last_error}") from last_error

    def start_cloud_game():
        if preserve_cloud_session:
            started = cloud_game.start_game_process(headless=headless, preserve_existing=True)
        else:
            started = cloud_game.start_game_process(headless=headless)
        pause_ctl.checkpoint()
        if not started:
            raise ConnectionError("启动或连接浏览器失败")
        entry = cloud_startup_entry()
        if entry != "running":
            if entry == "resume_queue":
                entered = cloud_game.enter_cloud_game(resume_queue=True)
            elif entry == "signed_in_lobby":
                entered = cloud_game.enter_cloud_game(signed_in_lobby_only=True)
            else:
                entered = cloud_game.enter_cloud_game()
            pause_ctl.checkpoint()
            if entered == "game_running":
                if not cloud_game.is_in_game():
                    raise CloudGameProbeUnready("暂未确认恢复的云游戏播放器")
                return
            if not entered:
                raise ConnectionError("进入云游戏失败")
            time.sleep(10)
            if not wait_until(cloud_game_check_and_enter, timeout):
                raise TimeoutError("查找并点击进入按钮超时")
            time.sleep(10)

    def task_screen_ready():
        nonlocal readiness_error, recovery_attempted
        pause_ctl.checkpoint()
        # 已有进程是否需要重启，由最后一次画面探测与恢复决定。
        recovery_attempted = False
        ready = False
        probe_error = None
        if screen_ready is not None:
            try:
                ready = screen_ready()
            except (InputInterrupted, GameWindowLost, ProfileAssetNotFoundError, TouchProfileInputError):
                raise
            except (RuntimeError, OSError) as error:
                if backend == "local" and _local_game_process_running(starrail) is False:
                    raise GameWindowLost("游戏进程已在首帧前退出") from error
                probe_error = error
                readiness_error = error
                log.debug(f"补充画面识别暂不可用：{error}")
        confirmed_screen = ready if isinstance(ready, str) else None
        if not ready:
            try:
                with screenshot_retry_timeout(0) if probe_error is not None else nullcontext():
                    ready = screen.get_current_screen(autotry=False, max_retries=1)
            except (InputInterrupted, GameWindowLost, GameRecoveryError, ProfileAssetNotFoundError, TouchProfileInputError):
                raise
            except (RuntimeError, OSError) as error:
                if backend == "local" and _local_game_process_running(starrail) is False:
                    raise GameWindowLost("游戏进程已在首帧前退出") from error
                if isinstance(probe_error, GameRecoveryError):
                    raise probe_error from error
                readiness_error = error
                log.debug(f"游戏首帧暂不可用：{error}")
                return False
            if ready:
                confirmed_screen = screen.current_screen
            elif isinstance(probe_error, GameRecoveryError):
                raise probe_error
        if backend == "local":
            if not ready or confirmed_screen in ("start_game", "click_enter"):
                check_local_client_version()
            if not ready and (credentials_started or try_local_login()):
                readiness_error = login_error or readiness_error
                return False
        if not ready:
            pause_ctl.checkpoint()
            if screen_ready is None:
                screen.recover_current_screen()
                recovery_attempted = True
            else:
                with screenshot_retry_timeout(0):
                    screen.dismiss_story_recap(take_screenshot=False)
        readiness_error = None if ready else login_error or readiness_error
        return ready

    if backend == "cloud":
        cloud_game.reset_queue_wait()
    for retry in range(MAX_RETRY):
        deadline = time.monotonic() + timeout
        starrail = None
        started_local_process = False
        try:
            pause_ctl.checkpoint()
            if backend == "cloud":
                start_cloud_game()
            else:
                starrail = StarRailController(cfg=cfg, logger=log)
                start_local_game(starrail)
            ready_timeout = timeout if backend == "cloud" else remaining_startup_time()
            readiness_error = None
            recovery_attempted = False
            ready = wait_until(task_screen_ready, ready_timeout)
            pause_ctl.checkpoint()
            if not ready:
                if retry + 1 < MAX_RETRY and not credentials_started and (started_local_process or recovery_attempted):
                    raise TimeoutError("获取当前界面超时") from readiness_error
                message = "未能确认游戏起始画面，已保留游戏现场"
                if readiness_error is not None:
                    message += f"：{readiness_error}"
                raise GameStartupUnavailable(message) from readiness_error
            break
        except CloudGamePageNotReadyError as error:
            cloud_game.preserve_running_browser()
            raise GameStartupUnavailable(f"{error}，已保留当前浏览器") from error
        except CloudGameZeroDurationError:
            # 重入时长为 0 时保留附着的浏览器，播放器可能在读取余额后恢复。
            if preserve_cloud_session and cloud_disconnected:
                cloud_game.preserve_running_browser()
            else:
                cloud_game.stop_game()
            raise
        except (AccountError, CloudGameLoginTimeoutError, TouchProfileInputError, ProfileAssetNotFoundError):
            raise
        except (InputInterrupted, RunStopRequested):
            # 窗口持续最小化等需要用户处理的情况不能触发原有的“关闭游戏后重启”恢复路径；
            # 游戏进程退出（GameWindowLost）仍按普通错误重启游戏。
            if backend == "cloud":
                cloud_game.preserve_running_browser()
            raise
        except Exception as e:
            if isinstance(e, GameRecoveryError) and not started_local_process:
                if backend == "cloud":
                    cloud_game.preserve_running_browser()
                raise
            pause_ctl.check_stop()
            log.error(f"尝试启动游戏时发生错误：{e}")
            if backend == "cloud" and preserve_cloud_session:
                cloud_game.preserve_running_browser()
                if isinstance(e, CloudGameQueueTimeoutError):
                    raise GameStartupUnavailable(f"{e}，已保留云游戏队列") from e
                if retry == MAX_RETRY - 1:
                    raise GameStartupUnavailable(f"云游戏启动持续不可用，已保留游戏现场：{e}") from e
                time.sleep(1)
                continue
            if backend == "local" and isinstance(e, GameWindowLost):
                if _local_game_process_running(starrail) is False:
                    if retry == MAX_RETRY - 1:
                        raise GameStartupUnavailable(f"游戏进程多次退出，无法完成启动：{e}") from e
                    reset_login_attempts()
                    continue
                if not started_local_process:
                    if retry == MAX_RETRY - 1:
                        raise GameStartupUnavailable(f"游戏窗口持续不可用，已保留游戏现场：{e}") from e
                    time.sleep(1)
                    continue
            if backend == "local" and starrail is not None and starrail.launch_method == "epic":
                from module.game.epic import EpicLaunchError
                if isinstance(e, EpicLaunchError):
                    # 渠道启动已给出具体阶段错误，不重放协议/点击，不关闭用户启动器。
                    raise
            if isinstance(e, GameResolutionMismatch):
                if retry == MAX_RETRY - 1 or not game_option_enabled(cfg, "auto_set_resolution_enable"):
                    raise GameStartupUnavailable(f"{e}，已保留游戏现场") from e
                if cfg.auto_set_game_path_enable:
                    try:
                        update_game_path(get_process_path(cfg.game_process_name))
                    except (psutil.Error, OSError) as path_error:
                        log.warning(f"暂未读取到当前游戏路径，沿用已配置的路径。{path_error}")
                    starrail.game_path = os.path.normpath(cfg.game_path)
                if not os.path.isfile(starrail.game_path):
                    raise GameStartupUnavailable(f"{e}，未找到可重新启动的游戏路径，已保留游戏现场") from e
            if isinstance(e, GameClientOutdatedError) and not cfg.update_via_launcher:
                raise GameStartupUnavailable(f"{e}，已保留游戏现场") from e
            # 确保在重试前停止游戏
            if backend == "cloud":
                cloud_game.stop_game()
            elif starrail is not None:
                pause_ctl.checkpoint()
                stopped = starrail.stop_game()
                if stopped is False:
                    raise GameStartupUnavailable(f"无法关闭游戏，已保留游戏现场：{e}") from e
                # 非云游戏模式下，若检测到是版本过低则尝试通过启动器更新
                if isinstance(e, GameClientOutdatedError) and cfg.update_via_launcher:
                    pause_ctl.checkpoint()
                    update_via_launcher()
            if retry == MAX_RETRY - 1:
                raise  # 如果是最后一次尝试，则重新抛出异常


def _finish_game_run():
    try:
        restore_temporary_graphics(final=True)
    finally:
        task_power_request.release(log)


def prepare_game_connection(backend, profile):
    if auto.connection != (backend, profile):
        auto.reload_connection()
        screen.reload_profile()


def play_finish_audio():
    log.info("开始播放音频")
    try:
        from playsound3 import playsound
        playsound("./assets/audio/pa.mp3")
        log.info("播放音频完成")
    except Exception as error:
        log.warning(f"播放音频时发生错误：{error}")


def stop(detect_loop=False, *, success=True):
    """执行完成后操作；success 控制非循环运行的退出码和成功等待提示。"""
    pause_ctl.check_stop()
    renew_login(cfg)
    log.hr("停止运行", 0)

    from utils.runs import effective_after_finish
    action = effective_after_finish(cfg.after_finish)
    child = bool(os.getenv("M7A_ROTATION_PARENT"))
    if detect_loop and action == "Loop":
        if cfg.play_audio and not child:
            play_finish_audio()
        after_finish_is_loop()
    else:
        if detect_loop:
            notify_after_finish_not_loop()
        if cfg.play_audio and not child:
            play_finish_audio()
        # 在关闭游戏前优先退出 OCR 避免内存占用
        ocr.exit_ocr()
        if action in ["Exit", "Shutdown", "Sleep", "Hibernate", "Restart", "Logoff", "TurnOffDisplay", "RunScript"]:
            if get_game_controller().shutdown(action, on_stopped=_finish_game_run) is False:
                raise RuntimeError(f"任务完成后的操作失败：{action}")
        else:
            # 无完成后操作时也要在 CLI 等待回车前结束 ADB 会话。
            if get_control_backend(cfg) == "adb":
                get_game_controller("adb").close()
            _finish_game_run()
        log.hr("完成", 2)
        if success and not child and action not in ["Shutdown", "Sleep", "Hibernate", "Restart", "Logoff", "TurnOffDisplay", "RunScript"]:
            pause_on_success()
        sys.exit(0 if success else 1)


def after_finish_is_loop(*, preserve_game=False):
    pause_ctl.check_stop()
    if preserve_game:
        log.info("已保留本地游戏现场，等待下一轮定时运行")
    else:
        get_game_controller().stop_game()
    _finish_game_run()
    scheduled_time = cfg.scheduled_time
    wait_time = Date.time_to_seconds(scheduled_time)
    future_time = Date.calculate_future_time(scheduled_time)

    # 图形界面不支持循环模式，提前检查并退出
    if is_gui_started():
        msg = "图形界面启动的任务不支持循环模式。请到「运行」页配置「定时任务」。"
        log.error(msg)
        notif.flush_batch(extra_content=msg, level=NotificationLevel.ERROR)
        log.hr("完成", 2)
        sys.exit(0)

    final_content = cfg.notify_template['ContinueTime'].format(time=future_time)
    log.info(final_content)
    notif.flush_batch(extra_content=final_content, level=NotificationLevel.ALL)
    log.hr("完成", 2)
    # 等待状态退出OCR避免内存占用
    ocr.exit_ocr()
    # 等待期间不操控游戏，让出运行锁，图形界面或其他命令行可以照常运行任务；
    # 到点后若其他任务仍在运行，等它结束再开始下一轮
    with idle_without_run_lock(
            on_wait=lambda holder: log.info(f"等待正在运行的{describe_run(holder)}结束后再开始下一轮"),
            on_unavailable=lambda error: log.warning(f"运行锁不可用（{error}），无法确认是否已有其他任务在运行，照常开始下一轮")):
        # 使用wall clock轮询等待，避免系统休眠后time.sleep剩余时间不准确的问题
        target_time = time.time() + wait_time
        poll_interval = 1 if pause_ctl.enabled else 60
        while True:
            pause_ctl.check_stop()
            remaining = target_time - time.time()
            if remaining <= 0:
                break
            time.sleep(min(poll_interval, remaining))

    # 启动前重新加载配置 #262
    cfg._load_config()


def wait_after_cloud_zero_duration(error):
    """云游戏时长为 0 时，循环模式下发送通知并等待到下次定时运行，返回 True；
    非循环模式返回 False，由调用方按错误退出。"""
    from utils.runs import effective_after_finish
    if effective_after_finish(cfg.after_finish) != "Loop":
        return False
    msg = cfg.notify_template['ErrorOccurred'].format(error=error)
    log.error(msg)
    notif.flush_batch(extra_content=msg, level=NotificationLevel.ERROR)
    after_finish_is_loop()
    return True


def _start_launcher_and_get_automation(game):
    """启动米哈游启动器并返回 (launcher, launcher_auto)。
    若无法找到路径，返回 (None, None)。若启动器未切换到窗口，返回 (launcher, None)。"""
    from module.game.launcher import LauncherController
    if game is None:
        game = "hkrpg_global" if cfg.launcher_title_name == "HoYoPlay" else "hkrpg_cn"
    if os.path.exists(cfg.launcher_path):
        path = cfg.launcher_path
    else:
        from utils.registry.star_rail_setting import get_launcher_path
        path = get_launcher_path()
        if path is None:
            log.error("未找到米哈游启动器路径")
            return None, None
    launcher = LauncherController(path=path, process_name=cfg.launcher_process_name, window_name=cfg.launcher_title_name, logger=log)
    launcher.start_game_process(f"--game={game}")
    time.sleep(10)
    if launcher.switch_to_game():
        time.sleep(5)
        from module.automation.launcher_automation import LauncherAutomation
        launcher_auto = LauncherAutomation(cfg.launcher_title_name, log)
        return launcher, launcher_auto
    return launcher, None


def _handle_launcher_self_update(launcher, launcher_auto):
    """处理启动器自身更新：优先点击“稍后”，否则点击“立即更新”并等待完成。"""
    # 查找启动器自身更新按钮并点击，如有稍后按钮优先点击
    if launcher_auto.click_element("稍后", "text"):
        log.info("已点击稍后更新启动器按钮")
        time.sleep(5)
        return True

    if launcher_auto.click_element("立即更新", "text"):
        log.info("已点击启动器更新按钮，等待更新完成...")
        Base.send_notification_with_screenshot("检测到启动器可更新已开始下载", NotificationLevel.ALL, launcher_auto.screenshot)
        time.sleep(10)
        # 等待启动器更新完成，最长等待60分钟
        if not wait_until(lambda: launcher_auto.find_element(("更新游戏", "开始游戏"), "text"), 60 * 60, period=30):
            launcher.stop_game()
            log.error("等待启动器更新超时")
            return False
        log.info("启动器更新完成")
    return True


def _click_update_game_and_wait(launcher, launcher_auto):
    """点击“更新游戏”并等待完成，失败或超时返回 False。"""
    if launcher_auto.click_element("更新游戏", "text"):
        log.info("已点击更新游戏按钮，等待更新完成...")
        Base.send_notification_with_screenshot("检测到游戏可更新已开始下载", NotificationLevel.ALL, launcher_auto.screenshot)

        def check_update_complete():
            """检查更新是否完成，同时处理重试按钮"""
            # 检查是否有重试按钮，如果有则点击
            if launcher_auto.click_element("重试", "text"):
                log.info("检测到重试按钮，正在点击...")
                return False
            # 检查是否已出现开始游戏按钮（表示更新完成）
            return launcher_auto.find_element("开始游戏", "text")

        # 等待更新完成，最长等待 cfg.update_game_timeout 小时
        if not wait_until(check_update_complete, cfg.update_game_timeout * 60 * 60, period=60):
            launcher.stop_game()
            log.error("等待游戏更新超时")
            return False
        log.info("游戏更新完成")
        return True
    log.info("未找到更新游戏按钮，可能已是最新版本")
    return False


def _click_pre_download(launcher, launcher_auto):
    """点击“预下载”并确认下载，成功返回 True。"""
    if launcher_auto.click_element("预下载", "text"):
        time.sleep(10)
        if launcher_auto.click_element("确认下载", "text"):
            log.info("已点击预下载按钮...")
            Base.send_notification_with_screenshot("检测到预下载已开始下载", NotificationLevel.ALL, launcher_auto.screenshot)
            # 暂不等待预下载完成（按钮：已完成）
            return True
    log.info("未找到预下载按钮，可能已是最新版本")
    return False


def update_via_launcher(game=None):
    """
    通过米哈游启动器尝试更新指定游戏到最新客户端
    'hkrpg_cn'（崩坏：星穹铁道国服）、'hk4e_cn'（原神国服）、'nap_cn'（绝区零国服）、'hkrpg_global'（崩坏：星穹铁道国际服）
    """
    # 未指定游戏时按启动器类型选择星铁；显式传入的游戏标识保持不变。
    launcher, launcher_auto = _start_launcher_and_get_automation(game)
    if launcher is None:
        return

    # 如果无法切换到启动器窗口，则直接关闭并返回
    if launcher_auto is None:
        launcher.stop_game()
        return

    # 处理启动器自身更新（点击稍后或立即更新并等待）
    if not _handle_launcher_self_update(launcher, launcher_auto):
        return

    # 查找更新按钮并点击，等待完成
    _click_update_game_and_wait(launcher, launcher_auto)

    # 关闭启动器
    launcher.stop_game()


def pre_download_via_launcher(game=None):
    """
    通过米哈游启动器尝试预下载指定游戏的最新客户端
    'hkrpg_cn'（崩坏：星穹铁道国服）、'hk4e_cn'（原神国服）、'nap_cn'（绝区零国服）、'hkrpg_global'（崩坏：星穹铁道国际服）
    """
    launcher, launcher_auto = _start_launcher_and_get_automation(game)
    if launcher is None:
        return

    # 如果无法切换到启动器窗口，则直接关闭并返回
    if launcher_auto is None:
        launcher.stop_game()
        return

    # 先处理启动器自身更新（若有）
    if not _handle_launcher_self_update(launcher, launcher_auto):
        return

    # 触发预下载（暂不处理等待下载过程，直接返回不关闭启动器）
    if _click_pre_download(launcher, launcher_auto):
        return

    # 关闭启动器
    launcher.stop_game()


def notify_after_finish_not_loop():
    if get_ui_profile(cfg).name == "touch_720":
        notif.flush_batch()
        return

    from module.overview.readings import seconds_until_full

    try:
        current_power = Power.get(use_supplement=False)
    except Exception as error:
        log.warning(f"未能确认开拓力恢复时间：{error}")
        notif.flush_batch()
        return

    wait_time = seconds_until_full(current_power)
    future_time = Date.calculate_future_time(wait_time)
    final_content = cfg.notify_template['FullTime'].format(power=current_power, time=future_time)
    log.info(final_content)
    notif.flush_batch(extra_content=final_content, level=NotificationLevel.ALL)


def ensure_IME_lang_en():
    """
    切换输入法语言/键盘语言至英文

    分两种情况，若系统有英语语言，则切换至英语语言，若没有，则切换输入法语言为英文
    """
    pause_ctl.checkpoint()
    from module.automation.input_base import background_enabled
    if background_enabled(cfg):
        return True  # 后台文本使用 Unicode 消息，不改变用户前台窗口的输入法。
    import win32api
    import win32gui
    from win32con import WM_INPUTLANGCHANGEREQUEST
    EN = 0x0409
    hwnd = win32gui.GetForegroundWindow()
    result = win32api.SendMessage(hwnd, WM_INPUTLANGCHANGEREQUEST, 0, EN)
    return result == 0


def auto_login(*, before_credentials=None):
    def auto_type(text):
        ensure_IME_lang_en()
        if before_credentials is not None:
            before_credentials()
        auto.secretly_write(text, interval=0.1)

    account, password = load_acc_and_pwd(gamereg_uid())
    if auto.click_element("./assets/images/screen/account_and_password.png", "image", 0.9, max_retries=10):
        if auto.click_element("./assets/images/screen/account_field.png", "image", 0.9, max_retries=10):
            auto_type(account)
            if auto.click_element("./assets/images/screen/password_field.png", "image", 0.9, take_screenshot=False):
                time.sleep(5)  # 等待切换到密码输入框
                auto_type(password)
                if auto.click_element("./assets/images/screen/agree_conditions.png", "image", 0.9, max_retries=10):
                    if auto.click_element("./assets/images/screen/enter_game.png", "image", 0.9, max_retries=10):
                        if auto.find_element("./assets/images/screen/welcome.png", "image", 0.9, max_retries=10):
                            return
    raise PermissionError("尝试自动登录失败")


def auto_login_os(*, before_credentials=None):
    def auto_type(text):
        ensure_IME_lang_en()
        time.sleep(1)
        if before_credentials is not None:
            before_credentials()
        auto.secretly_write(text, interval=0.1)

    account, password = load_acc_and_pwd(gamereg_uid())
    if auto.click_element("./assets/images/screen/account_field_os.png", "image", 0.9, max_retries=10):
        auto_type(account)
        if auto.click_element("./assets/images/screen/password_field.png", "image", 0.9, take_screenshot=False):
            time.sleep(5)  # 等待切换到密码输入框
            auto_type(password)
            if auto.click_element("./assets/images/screen/enter_game.png", "image", 0.9, max_retries=10):
                if auto.find_element("./assets/images/screen/welcome.png", "image", 0.9, max_retries=10):
                    return
    raise PermissionError("尝试自动登录失败")
