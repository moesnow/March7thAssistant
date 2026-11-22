import ast
from contextlib import contextmanager, nullcontext
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import ANY, Mock, call

from PIL import Image
import pytest


@pytest.fixture
def startup(monkeypatch):
    import tasks.game as game
    cfg = SimpleNamespace(cloud_game_enable=False, auto_set_resolution_enable=True,
                          auto_battle_detect_enable=True, auto_lower_graphics_enable=True,
                          game_optimization_enable=True, start_game_timeout=1,
                          auto_set_game_path_enable=False, update_via_launcher=False)
    controller = Mock(launch_method="direct", game_path="test/StarRail.exe", process_name="StarRail.exe",
                      launched_new_process=True)
    controller.switch_to_game.return_value = False
    controller.start_game_process.return_value = True
    controller.is_game_running.return_value = False
    controller.get_resolution.return_value = (1920, 1080)
    monkeypatch.setattr(game, "cfg", cfg)
    monkeypatch.setattr(game, "StarRailController", Mock(return_value=controller))
    windows = Mock()
    windows.return_value.process_running.return_value = False
    monkeypatch.setattr(game, "WindowsInputApi", windows)
    monkeypatch.setattr(game, "process_session_id", lambda: 1)
    monkeypatch.setattr(game, "auto", SimpleNamespace(input_handler=SimpleNamespace(is_background=False),
                                                      press_mouse=Mock(), find_element=Mock(return_value=None)))
    monkeypatch.setattr(game, "wait_until", Mock(return_value=True))
    monkeypatch.setattr(game.time, "sleep", Mock())
    monkeypatch.setattr(game, "begin_temporary_graphics", Mock())
    monkeypatch.setattr(game, "restore_temporary_graphics", Mock())
    return game, controller, cfg


def test_launch_loads_low_quality_then_restores_persisted_settings(startup):
    game, controller, cfg = startup
    events = Mock()
    events.attach_mock(game.begin_temporary_graphics, "begin")
    events.attach_mock(controller.start_game_process, "launch")
    events.attach_mock(game.restore_temporary_graphics, "restore")
    game.start_game()
    assert [call[0] for call in events.mock_calls] == ["begin", "launch", "restore"]
    game.begin_temporary_graphics.assert_called_once_with(controller.game_path, game.log)


@pytest.mark.parametrize("already_running", [False, True])
def test_pc_local_start_uses_profile_resolution(startup, already_running):
    game, controller, cfg = startup
    resolution = (1920, 1080)
    controller.switch_to_game.return_value = already_running

    game.start_game()

    if already_running:
        controller.change_resolution.assert_not_called()
        controller.check_resolution.assert_called_once_with(*resolution)
    else:
        controller.change_resolution.assert_called_once_with(*resolution)
        assert controller.check_resolution.call_args_list == [call(*resolution), call(*resolution)]


def test_start_recognizes_task_screen_before_generic_navigation(startup, monkeypatch):
    game, controller, _ = startup
    controller.switch_to_game.return_value = True
    monkeypatch.setattr(game, "screen", Mock())
    game.wait_until.side_effect = lambda condition, timeout: condition()
    ready = Mock(return_value=True)

    game.start_game(screen_ready=ready)

    ready.assert_called_once_with()
    game.screen.get_current_screen.assert_not_called()
    controller.stop_game.assert_not_called()


def test_task_readiness_fallback_uses_read_only_recognition_and_preserves_window(startup, monkeypatch):
    game, controller, _ = startup
    controller.switch_to_game.return_value = True
    monkeypatch.setattr(game, "screen", Mock())
    game.screen.get_current_screen.return_value = False
    game.wait_until.side_effect = lambda condition, timeout: condition()

    with pytest.raises(game.InputInterrupted, match="已保留游戏现场"):
        game.start_game(screen_ready=lambda: False)

    game.screen.get_current_screen.assert_called_once_with(autotry=False, max_retries=1)
    controller.stop_game.assert_not_called()


@pytest.mark.parametrize("outcome", ("task_recovers", "template_ready", "unavailable"))
def test_task_readiness_falls_back_after_an_unavailable_frame(startup, monkeypatch, outcome):
    game, controller, _ = startup
    controller.switch_to_game.return_value = True
    controller.is_game_running.return_value = True
    monkeypatch.setattr(game, "screen", Mock())
    game.screen.get_current_screen.return_value = outcome == "template_ready"
    game.wait_until.side_effect = lambda condition, timeout: condition() or condition()
    ready = Mock(side_effect=(RuntimeError("截图超时"), outcome == "task_recovers"))

    if outcome == "unavailable":
        with pytest.raises(game.GameStartupUnavailable, match="截图超时"):
            game.start_game(screen_ready=ready)
    else:
        game.start_game(screen_ready=ready)

    assert ready.call_count == (1 if outcome == "template_ready" else 2)
    assert game.screen.get_current_screen.call_args_list == [
        call(autotry=False, max_retries=1)
    ] * (2 if outcome == "unavailable" else 1)
    game.screen.recover_current_screen.assert_not_called()
    controller.stop_game.assert_not_called()


@pytest.mark.parametrize("template_ready", (False, True))
def test_task_recognition_error_allows_a_confirmed_generic_page(startup, monkeypatch, template_ready):
    from tasks.weekly.currency_wars import CurrencyWarsUnavailable

    game, controller, _ = startup
    controller.switch_to_game.return_value = True
    controller.is_game_running.return_value = True
    screen = Mock()
    screen.get_current_screen.return_value = template_ready
    screen.current_screen = "main"
    monkeypatch.setattr(game, "screen", screen)
    game.wait_until.side_effect = lambda condition, timeout: condition()
    ready = Mock(side_effect=CurrencyWarsUnavailable("补充画面识别失败"))

    if template_ready:
        game.start_game(screen_ready=ready)
    else:
        with pytest.raises(CurrencyWarsUnavailable, match="补充画面识别失败"):
            game.start_game(screen_ready=ready)

    screen.get_current_screen.assert_called_once_with(autotry=False, max_retries=1)
    screen.recover_current_screen.assert_not_called()
    controller.stop_game.assert_not_called()


@pytest.mark.parametrize("outcome", ("recovers", "repeated_exit", "window_missing"))
def test_currency_wars_startup_checks_the_process_after_its_first_frame_fails(startup, monkeypatch, outcome):
    from module.automation import automation, screenshot as screenshot_module
    from module.automation.screenshot import Screenshot
    from tasks.weekly import currency_wars
    from utils import wait

    game, controller, cfg = startup
    state = SimpleNamespace(running=True, window=True, now=0)
    clock = SimpleNamespace(monotonic=lambda: state.now,
                            sleep=lambda seconds: setattr(state, "now", state.now + seconds))
    for module in (game, wait, automation, currency_wars):
        monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(game, "wait_until", wait.wait_until)
    monkeypatch.setattr(game, "WindowsInputApi", Mock())
    game.WindowsInputApi.return_value.process_running.side_effect = lambda *_args, **_kwargs: state.running
    monkeypatch.setattr(game, "process_session_id", lambda: 4)
    monkeypatch.setattr(automation, "cfg", cfg)
    monkeypatch.setattr(screenshot_module, "cfg", cfg)
    monkeypatch.setattr(game, "screen", Mock())
    game.screen.get_current_screen.return_value = False

    def start_process():
        state.running = state.window = True
        return True

    controller.switch_to_game.side_effect = lambda: state.window
    controller.is_game_running.side_effect = lambda: state.window
    controller.start_game_process.side_effect = start_process

    def window_disappears(_title):
        state.window = False
        state.running = outcome == "window_missing"
        return None

    actual_screenshot = Screenshot.take_screenshot
    image = Image.new("RGB", (1920, 1080))

    def screenshot(*args, **kwargs):
        if outcome == "recovers" and controller.start_game_process.called:
            return image, (0, 0, 1920, 1080), 1
        return actual_screenshot(*args, **kwargs)

    monkeypatch.setattr(Screenshot, "get_window", window_disappears)
    monkeypatch.setattr(Screenshot, "take_screenshot", Mock(side_effect=screenshot))
    board = (("备战阶段", 472, 46), ("1-1", 472, 78), ("1/1", 960, 259), ("商店", 1624, 982),
             ("出战", 1818, 750), ("前台区域", 975, 315), ("后台区域", 963, 577))
    auto = Mock(input_handler=game.auto.input_handler, window_title="星穹铁道",
                ocr_result=[([(x, y)], (text, 1)) for text, x, y in board])
    auto.take_screenshot = MethodType(automation.Automation.take_screenshot, auto)
    auto._is_debug_enabled.return_value = False
    monkeypatch.setattr(game, "auto", auto)
    monkeypatch.setattr(currency_wars, "auto", auto)

    if outcome == "recovers":
        game.start_game(screen_ready=currency_wars.CurrencyWars.game_screen_ready)
        controller.start_game_process.assert_called_once_with()
        auto.perform_ocr.assert_called_once_with(raise_on_error=True)
    elif outcome == "repeated_exit":
        with pytest.raises(game.GameStartupUnavailable, match="游戏进程多次退出") as error:
            game.start_game(screen_ready=currency_wars.CurrencyWars.game_screen_ready)
        assert error.value.reason == "game_startup_unavailable"
        assert controller.start_game_process.call_count == 2
        auto.perform_ocr.assert_not_called()
    else:
        with pytest.raises(currency_wars.CurrencyWarsUnavailable, match="截图超时"):
            game.start_game(screen_ready=currency_wars.CurrencyWars.game_screen_ready)
        controller.start_game_process.assert_not_called()
        auto.perform_ocr.assert_not_called()
        game.screen.get_current_screen.assert_called_once_with(autotry=False, max_retries=1)
    game.WindowsInputApi.return_value.process_running.assert_called_with(controller.process_name, session_id=4)
    controller.stop_game.assert_not_called()
    if outcome != "window_missing":
        game.screen.get_current_screen.assert_not_called()
    game.screen.recover_current_screen.assert_not_called()


@pytest.mark.parametrize("entry", ("default", "task", "takeover"))
@pytest.mark.parametrize("outcome", ("recovers", "unavailable", "stopped"))
def test_local_front_window_activation_preserves_the_existing_process(startup, monkeypatch, entry, outcome):
    from module.game.base import GameControllerBase
    from utils import wait
    from utils.pause import RunStopRequested

    game, controller, cfg = startup
    cfg.start_game_timeout = .05
    state = SimpleNamespace(now=0)
    clock = SimpleNamespace(monotonic=lambda: state.now,
                            sleep=lambda seconds: setattr(state, "now", state.now + seconds))
    monkeypatch.setattr(game, "time", clock)
    monkeypatch.setattr(wait, "time", clock)
    monkeypatch.setattr(game, "wait_until", wait.wait_until)
    controller.is_game_running.return_value = True
    controller.get_window_handle.return_value = 12
    controller.switch_to_game = MethodType(GameControllerBase.switch_to_game, controller)
    activation_denied = RuntimeError("Failed to set window foreground after multiple attempts")
    if outcome == "recovers":
        controller.set_foreground_window_with_retry.side_effect = [activation_denied, None]
    else:
        controller.set_foreground_window_with_retry.side_effect = activation_denied

    def checkpoint():
        if outcome == "stopped" and controller.set_foreground_window_with_retry.called:
            raise RunStopRequested

    monkeypatch.setattr(game, "pause_ctl", SimpleNamespace(checkpoint=checkpoint, check_stop=checkpoint))
    monkeypatch.setattr(game, "screen", Mock(get_current_screen=Mock(return_value=True), current_screen="main"))
    ready = Mock(return_value=True)

    def start():
        if entry == "takeover":
            game.prepare_local_takeover()
        else:
            game.start_game(screen_ready=ready if entry == "task" else None)

    if outcome == "recovers":
        start()
        assert controller.set_foreground_window_with_retry.call_count == 2
        assert ready.call_count == (1 if entry == "task" else 0)
    elif outcome == "stopped":
        with pytest.raises(RunStopRequested):
            start()
        controller.set_foreground_window_with_retry.assert_called_once()
        ready.assert_not_called()
    else:
        with pytest.raises(game.GameStartupUnavailable, match="无法将本地游戏窗口切到前台"):
            start()
        assert state.now == (game.WINDOW_WAIT_SECONDS if entry == "takeover" else 3)
        ready.assert_not_called()
    controller.start_game_process.assert_not_called()
    controller.stop_game.assert_not_called()


def test_generic_readiness_keeps_startup_retries_when_the_frame_is_readable(startup, monkeypatch):
    game, controller, _ = startup
    controller.switch_to_game.return_value = True
    screen = Mock()
    screen.get_current_screen.return_value = False
    monkeypatch.setattr(game, "screen", screen)
    game.wait_until.side_effect = lambda condition, timeout: condition()

    with pytest.raises(game.GameStartupUnavailable, match="已保留游戏现场"):
        game.start_game()

    assert screen.get_current_screen.call_count == 3
    assert controller.stop_game.call_count == 2


@pytest.mark.parametrize("has_probe", [False, True])
@pytest.mark.parametrize(("error_type", "outcome"), [
    (RuntimeError, "recovers"),
    (OSError, "recovers"),
    (OSError, "unavailable"),
    (OSError, "process_exits"),
])
def test_startup_rechecks_an_existing_game_after_a_first_frame_error(startup, monkeypatch, has_probe, error_type, outcome):
    from utils import wait

    game, controller, cfg = startup
    cfg.start_game_timeout = .7 if outcome == "process_exits" else .1
    state = SimpleNamespace(now=0, running=True, reads=0)
    clock = SimpleNamespace(monotonic=lambda: state.now,
                            sleep=lambda seconds: setattr(state, "now", state.now + seconds))
    monkeypatch.setattr(game, "time", clock)
    monkeypatch.setattr(wait, "time", clock)
    game.wait_until.side_effect = wait.wait_until
    monkeypatch.setattr(game, "process_session_id", lambda: 4)
    controller.switch_to_game.side_effect = lambda: state.running
    controller.is_game_running.side_effect = lambda: state.running

    def start_process():
        state.running = True
        return True

    def probe_frame(**_):
        state.reads += 1
        if outcome == "unavailable":
            if state.reads == 1:
                return False
            raise error_type("截图持续失败")
        if state.reads == 1:
            if outcome == "process_exits":
                state.running = False
            raise error_type("首帧截图失败")
        return True

    controller.start_game_process.side_effect = start_process
    game.auto.click_element = Mock(return_value=True)
    screen = Mock(get_current_screen=Mock(side_effect=probe_frame), current_screen="main")
    monkeypatch.setattr(game, "screen", screen)
    options = {"screen_ready": lambda: False} if has_probe else {}

    if outcome == "unavailable":
        with pytest.raises(game.GameStartupUnavailable, match="已保留游戏现场：截图持续失败"):
            game.start_game(**options)
        assert state.now == 6
    else:
        game.start_game(**options)
        assert state.reads == 2
    controller.stop_game.assert_not_called()
    assert controller.start_game_process.call_count == (1 if outcome == "process_exits" else 0)
    assert screen.recover_current_screen.call_count == (1 if outcome == "unavailable" and not has_probe else 0)


@pytest.mark.parametrize("fault", ("generic_screenshot", "title", "task_screenshot", "task_unrecognized", "login"))
def test_local_startup_retries_after_a_failure_of_the_first_process(startup, monkeypatch, fault):
    from utils import wait

    game, controller, _ = startup
    ordinary = fault == "generic_screenshot"
    state = SimpleNamespace(now=0, process=0, running=False, logged_in=False, entered=False)
    clock = SimpleNamespace(monotonic=lambda: state.now,
                            sleep=lambda seconds: setattr(state, "now", state.now + seconds))
    monkeypatch.setattr(game, "time", clock)
    monkeypatch.setattr(wait, "time", clock)
    game.wait_until.side_effect = wait.wait_until
    monkeypatch.setattr(game, "WindowsInputApi", Mock())
    game.WindowsInputApi.return_value.process_running.return_value = False
    monkeypatch.setattr(game, "process_session_id", lambda: 4)
    controller.switch_to_game.side_effect = lambda: state.running
    controller.is_game_running.side_effect = lambda: state.running

    def start_process():
        state.process += 1
        state.running = True
        return True

    def stop_process():
        state.running = False
        return True

    controller.start_game_process.side_effect = start_process
    controller.stop_game.side_effect = stop_process

    def click(path, *_args, **_kwargs):
        if not path.endswith("/click_enter.png"):
            return False
        state.entered = state.logged_in if fault == "login" else fault != "title" or state.process > 1
        return state.entered

    def login(*, before_credentials):
        before_credentials()
        if state.process == 1:
            state.running = False
            raise game.GameWindowLost("输凭据时进程退出")
        state.logged_in = True

    game.auto.click_element = Mock(side_effect=click)
    game.auto.find_element.side_effect = lambda path, *_args, **_kwargs: (
        fault == "login" and path == "./assets/images/screen/account_and_password.png"
    )
    monkeypatch.setattr(game, "load_acc_and_pwd", Mock(return_value=("account", "password")))
    monkeypatch.setattr(game, "gamereg_uid", lambda: None)
    monkeypatch.setattr(game, "auto_login", Mock(side_effect=login))

    def generic_probe(**_kwargs):
        if ordinary and state.process == 1:
            raise OSError("截图持续失败，重启后恢复")
        return ordinary

    def task_probe():
        if fault == "task_screenshot" and state.process == 1:
            raise game.GameRecoveryError("币战启动连续无法获取截图")
        return state.entered and (fault != "task_unrecognized" or state.process > 1)

    monkeypatch.setattr(game, "screen", Mock(get_current_screen=Mock(side_effect=generic_probe)))
    game.start_game(screen_ready=None if ordinary else task_probe)

    assert controller.start_game_process.call_count == 2
    assert controller.stop_game.call_count == (0 if fault == "login" else 1)
    assert game.auto_login.call_count == (2 if fault == "login" else 0)


def test_local_startup_preserves_a_window_that_appears_at_launch(startup, monkeypatch):
    from module.game.local import LocalGameController

    game, controller, _ = startup
    controller.logger = None
    controller.switch_to_game.side_effect = (False, True)
    controller.is_game_running.side_effect = (False, True, True)
    controller.start_game_process = MethodType(LocalGameController.start_game_process, controller)
    game.auto.click_element = Mock()
    game.wait_until.side_effect = lambda condition, _timeout: condition()
    monkeypatch.setattr(game, "screen", Mock(get_current_screen=Mock(return_value=False)))
    monkeypatch.setattr(game, "WindowsInputApi", Mock())
    game.WindowsInputApi.return_value.process_running.return_value = False
    monkeypatch.setattr(game, "process_session_id", lambda: 4)
    ready = Mock(side_effect=game.GameRecoveryError("已有游戏暂时无法识别"))

    with pytest.raises(game.GameRecoveryError, match="已有游戏暂时无法识别"):
        game.start_game(screen_ready=ready)

    assert controller.launched_new_process is False
    ready.assert_called_once_with()
    game.auto.click_element.assert_not_called()
    controller.stop_game.assert_not_called()


@pytest.mark.parametrize(("outcome", "startup_seconds", "elapsed"), [
    ("late_window", 90, 3),
    ("window_missing", 90, 60),
    ("window_missing", 3, 3),
    ("stopped", 90, 1),
])
def test_direct_start_waits_for_the_reused_process_window(startup, monkeypatch, tmp_path, outcome,
                                                         startup_seconds, elapsed):
    from module.automation import windows_input
    from module.game import local
    from utils import wait, windows_session
    from utils.pause import RunStopRequested

    game, controller, cfg = startup
    cfg.start_game_timeout = startup_seconds / 60
    game_path = tmp_path / "StarRail.exe"
    game_path.touch()
    controller.game_path = str(game_path)
    controller.logger = None
    controller.start_game_process = Mock(wraps=MethodType(local.LocalGameController.start_game_process, controller))
    controller.stop_game.side_effect = AssertionError("复用的游戏进程被关闭")
    launch = Mock(side_effect=AssertionError("已有游戏进程时重复直启"))
    monkeypatch.setattr(local, "os", SimpleNamespace(path=local.os.path, system=launch))
    monkeypatch.setattr(local, "in_desktop_twin", lambda: False)
    api = game.WindowsInputApi.return_value
    # 首次探测时进程尚不存在，直到直启前的复核才看到进程。
    api.process_running.side_effect = lambda *_args, **_kwargs: api.process_running.call_count > 1
    monkeypatch.setattr(windows_input, "WindowsInputApi", game.WindowsInputApi)
    monkeypatch.setattr(windows_session, "process_session_id", game.process_session_id)

    state = SimpleNamespace(now=0)
    clock = SimpleNamespace(monotonic=lambda: state.now,
                            sleep=lambda seconds: setattr(state, "now", state.now + seconds))
    monkeypatch.setattr(game, "time", clock)
    monkeypatch.setattr(wait, "time", clock)
    monkeypatch.setattr(game, "wait_until", wait.wait_until)
    controller.switch_to_game.side_effect = lambda: outcome == "late_window" and state.now >= 2

    def checkpoint():
        if outcome == "stopped" and state.now >= 1:
            raise RunStopRequested

    monkeypatch.setattr(game, "pause_ctl", SimpleNamespace(checkpoint=checkpoint, check_stop=checkpoint))
    monkeypatch.setattr(game, "log", Mock())
    monkeypatch.setattr(game, "screen", Mock(get_current_screen=Mock(return_value=True), current_screen="main"))
    game.auto.click_element = Mock()

    if outcome == "late_window":
        game.start_game()
        game.screen.get_current_screen.assert_called_once_with(autotry=False, max_retries=1)
    elif outcome == "stopped":
        with pytest.raises(RunStopRequested):
            game.start_game()
        game.screen.get_current_screen.assert_not_called()
    else:
        with pytest.raises(game.GameStartupUnavailable, match="无法将本地游戏窗口切到前台，已保留游戏现场"):
            game.start_game()
        game.screen.get_current_screen.assert_not_called()

    assert state.now == elapsed
    assert controller.launched_new_process is False
    controller.start_game_process.assert_called_once_with()
    api.process_running.assert_called_with(controller.process_name, session_id=1)
    launch.assert_not_called()
    controller.stop_game.assert_not_called()
    game.auto.click_element.assert_not_called()
    game.auto.press_mouse.assert_not_called()


@pytest.mark.parametrize("background", [False, True])
def test_touch_local_start_uses_clicks_and_native_resolution(startup, monkeypatch, background):
    game, controller, cfg = startup
    cfg.ui_profile = "touch_720"
    controller.launch_touch_game.return_value = nullcontext()
    controller.get_resolution.return_value = (1280, 720)
    controller.switch_to_game.return_value = True
    monkeypatch.setattr(game, "get_game_controller", Mock(return_value=controller))
    monkeypatch.setattr(game, "screen", Mock())
    game.screen.get_current_screen.side_effect = [False, True]
    game.wait_until.side_effect = lambda condition, timeout: condition() or condition()
    game.auto.input_handler = Mock(is_background=background)
    game.auto.click_element = Mock()

    game.start_game()

    game.get_game_controller.assert_called_once_with("local")
    controller.launch_touch_game.assert_called_once_with((1280, 720))
    if background:
        controller.switch_to_game.assert_not_called()
        game.auto.input_handler.wait_for_window.assert_called_once_with(game.WINDOW_WAIT_SECONDS)
    else:
        controller.switch_to_game.assert_called_once_with()
        game.auto.input_handler.wait_for_window.assert_not_called()
    assert game.screen.get_current_screen.call_args_list == [call(autotry=False), call(autotry=False)]
    assert game.auto.click_element.call_args.args[:3] == ("./assets/touch_720/images/screen/click_enter.png", "image", 0.9)
    game.auto.press_mouse.assert_not_called()
    game.StarRailController.assert_not_called()


def test_explicit_cloud_start_skips_local_resolution(startup, monkeypatch):
    game, controller, cfg = startup
    cfg.control_backend = "cloud"
    cfg.ui_profile = "touch_720"
    cloud = Mock()
    monkeypatch.setattr(game, "cloud_game", cloud)

    game.start_game()

    cloud.start_game_process.assert_called_once_with(headless=None)
    game.StarRailController.assert_not_called()
    controller.change_resolution.assert_not_called()
    controller.check_resolution.assert_not_called()


def test_adb_start_uses_adb_bootstrap(startup, monkeypatch):
    game, _, cfg = startup
    cfg.control_backend = "adb"
    cloud = Mock()
    adb = Mock()
    wait_for_game = Mock()
    monkeypatch.setattr(game, "cloud_game", cloud)
    monkeypatch.setattr(game, "get_game_controller", Mock(return_value=adb))
    monkeypatch.setattr(game, "wait_for_adb_game", wait_for_game)

    game.start_game()

    adb.start_game_process.assert_called_once_with()
    wait_for_game.assert_called_once_with(adb, 60, recover=ANY)
    game.StarRailController.assert_not_called()
    cloud.start_game_process.assert_not_called()
    game.wait_until.assert_not_called()


@pytest.mark.parametrize("code", ["frame_timeout", "frame_clock_unavailable", "disconnected"])
def test_adb_start_keeps_waiting_after_a_transient_recovery_probe(startup, monkeypatch, code):
    from module.game import adb_ready

    game, _, cfg = startup
    cfg.control_backend = "adb"
    adb = Mock(capture_frame=Mock(side_effect=[("loading",), ("main",)]))
    monkeypatch.setattr(game, "get_game_controller", Mock(return_value=adb))
    monkeypatch.setattr(adb_ready, "_load_template", lambda name: None)
    monkeypatch.setattr(adb_ready, "_match", lambda frame, name, template: (1, 1) if frame == name else None)
    game.auto.find_element.side_effect = game.AdbError(code, "测试截图失败")

    if code == "disconnected":
        with pytest.raises(game.AdbError) as error:
            game.start_game()
        assert error.value.code == code
        assert adb.capture_frame.call_count == 1
    else:
        game.start_game()
        assert adb.capture_frame.call_count == 2


@pytest.mark.parametrize("mode", ["master-off", "child-off", "already-running", "manual", "cloud"])
def test_no_quality_change_for_excluded_launches(startup, monkeypatch, mode):
    game, controller, cfg = startup
    if mode == "master-off":
        cfg.game_optimization_enable = False
    elif mode == "child-off":
        cfg.auto_lower_graphics_enable = False
    elif mode == "already-running":
        controller.switch_to_game.return_value = True
    elif mode == "cloud":
        cfg.cloud_game_enable = True
        monkeypatch.setattr(game, "cloud_game", Mock())
    game.start_game(optimize_graphics=mode != "manual")
    game.begin_temporary_graphics.assert_not_called()
    if mode == "master-off":
        controller.change_resolution.assert_not_called()
        controller.change_auto_hdr.assert_not_called()
        controller.change_auto_battle.assert_not_called()


def test_desktop_twin_skips_battle_setting_write(startup, monkeypatch):
    game, controller, cfg = startup
    monkeypatch.setattr(game, "in_desktop_twin", lambda: True)

    game.start_game()

    # 分身与主桌面共用游戏设置，启动前不改写；战斗中检测到未开启会按 V 补开。
    controller.change_auto_battle.assert_not_called()
    controller.start_game_process.assert_called_once_with()


def test_failed_launch_restores_each_attempt(startup):
    game, controller, cfg = startup
    controller.start_game_process.return_value = False
    with pytest.raises(RuntimeError, match="启动游戏失败"):
        game.start_game()
    assert game.begin_temporary_graphics.call_count == 3
    assert game.restore_temporary_graphics.call_count == 3


@pytest.mark.parametrize("failure", [RuntimeError("fail"), KeyboardInterrupt(), SystemExit(0)])
def test_main_finally_restores_before_outer_error_handling(failure):
    from module.config.platform import pin_game_connection

    tree = ast.parse(Path("main.py").read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {"main", "_game_connection"}]
    action = Mock(side_effect=failure)
    events = Mock()
    restore, recover = events.restore, Mock()
    namespace = {"_run_action": action, "restore_temporary_graphics": restore,
                 "recover_temporary_graphics": recover, "log": Mock(), "task_power_request": events.power}
    namespace.update(cfg=SimpleNamespace(control_backend="local"), game=Mock(), HOST_TASKS=set(),
                     get_control_backend=lambda cfg: "local", task_is_supported=lambda action, cfg: True,
                     contextmanager=contextmanager, pin_game_connection=pin_game_connection,
                     run_session=SimpleNamespace(record={}))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "main.py", "exec"), namespace)
    with pytest.raises(type(failure)):
        namespace["main"](action="daily")
    restore.assert_called_once_with(final=True)
    recover.assert_called_once()
    assert [call[0] for call in events.mock_calls] == ["restore", "power.release"]


def test_main_normal_return_restores():
    from module.config.platform import pin_game_connection

    tree = ast.parse(Path("main.py").read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {"main", "_game_connection"}]
    restore = Mock()
    namespace = {"_run_action": Mock(return_value=True), "restore_temporary_graphics": restore,
                 "recover_temporary_graphics": Mock(), "log": Mock(), "task_power_request": Mock()}
    namespace.update(cfg=SimpleNamespace(control_backend="local"), game=Mock(), HOST_TASKS=set(),
                     get_control_backend=lambda cfg: "local", task_is_supported=lambda action, cfg: True,
                     contextmanager=contextmanager, pin_game_connection=pin_game_connection,
                     run_session=SimpleNamespace(record={}))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "main.py", "exec"), namespace)
    assert namespace["main"](action="daily") is True
    restore.assert_called_once_with(final=True)


def test_force_stop_restores_before_os_exit():
    tree = ast.parse(Path("main.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_force_stop")
    calls = Mock()
    exit_mock = Mock(side_effect=SystemExit(6))
    calls.attach_mock(exit_mock, "exit")
    namespace = {"restore_temporary_graphics": calls.restore, "run_session": calls.session,
                 "os": SimpleNamespace(_exit=exit_mock), "log": Mock(),
                 "STOP_GRACE_SECONDS": 5, "STATUS_STOPPED": "stopped", "EXIT_STOPPED": 6}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "main.py", "exec"), namespace)
    with pytest.raises(SystemExit):
        namespace["_force_stop"]()
    names = [call[0] for call in calls.mock_calls]
    assert names.index("restore") < names.index("session.finish") < names.index("exit")


@pytest.mark.parametrize("backend", ["local", "adb"])
def test_stop_releases_game_resources_before_success_pause(monkeypatch, backend):
    import tasks.game as game
    events = Mock()
    monkeypatch.setattr(game, "cfg", SimpleNamespace(after_finish="None", play_audio=False, control_backend=backend))
    monkeypatch.setattr(game, "get_game_controller", Mock(return_value=events.controller))
    monkeypatch.setattr(game, "ocr", Mock())
    monkeypatch.setattr(game, "restore_temporary_graphics", events.restore)
    monkeypatch.setattr(game, "pause_on_success", events.pause)
    monkeypatch.setattr(game, "task_power_request", events.power)
    with pytest.raises(SystemExit):
        game.stop()
    device_cleanup = ["controller.close"] if backend == "adb" else []
    assert [call[0] for call in events.mock_calls] == [*device_cleanup, "restore", "power.release", "pause"]
    events.restore.assert_called_once_with(final=True)


def test_stop_releases_power_before_after_finish_sleep(monkeypatch):
    import module.game.base as base
    import tasks.game as game

    events = Mock()
    controller = base.GameControllerBase()
    controller.stop_game = events.stop_game
    monkeypatch.setattr(game, "cfg", SimpleNamespace(after_finish="Sleep", play_audio=False, control_backend="local"))
    monkeypatch.setattr(game, "get_game_controller", Mock(return_value=controller))
    monkeypatch.setattr(game, "ocr", Mock())
    monkeypatch.setattr(game, "restore_temporary_graphics", events.restore)
    monkeypatch.setattr(game, "task_power_request", events.power)
    monkeypatch.setattr(base, "time", SimpleNamespace(sleep=events.delay))
    monkeypatch.setattr(base, "os", SimpleNamespace(system=events.system))

    with pytest.raises(SystemExit):
        game.stop()
    assert [call[0] for call in events.mock_calls][:5] == [
        "stop_game", "restore", "power.release", "delay", "system",
    ]


def test_start_requests_power_before_preparing_any_backend(monkeypatch):
    import tasks.game as game

    events = Mock()
    monkeypatch.setattr(game, "task_power_request", events.power)
    monkeypatch.setattr(game, "start_game", events.start_game)

    game.start()

    assert [call[0] for call in events.mock_calls] == ["power.acquire", "start_game"]


def test_stop_game_restores_after_process_termination(monkeypatch):
    import module.game.local as local
    events = Mock()
    controller = object.__new__(local.LocalGameController)
    controller.process_name = "StarRail"
    controller.logger = Mock()
    controller.terminate_named_process = events.terminate
    monkeypatch.setattr(local, "restore_temporary_graphics", events.restore)
    assert controller.stop_game()
    assert [call[0] for call in events.mock_calls] == ["terminate", "restore"]


def test_all_runtime_battle_reads_use_master_gate():
    # 防止之后增加分支时绕过总开关；自动对话的独立配置不属于这里的三项优化。
    paths = ["app/main_window.py", "module/game/cloud.py", "tasks/challenge/__init__.py",
             "tasks/power/instance.py", "tasks/weekly/currency_wars.py",
             "tasks/weekly/divergent_universe.py", "tasks/game/__init__.py"]
    for path in paths:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id == "game_option_enabled" for node in ast.walk(tree)), path
        assert not any(isinstance(node, ast.Attribute) and node.attr == "auto_battle_detect_enable"
                       for node in ast.walk(tree)), path


def test_epic_failure_restores_graphics_without_replaying(startup):
    pytest.importorskip("win32gui")
    from module.game.epic import EpicLaunchError
    game, controller, cfg = startup
    controller.launch_method = "epic"
    controller.start_game_process.side_effect = EpicLaunchError("Epic launch failed")
    with pytest.raises(EpicLaunchError):
        game.start_game()
    game.begin_temporary_graphics.assert_called_once()
    game.restore_temporary_graphics.assert_called_once()
    controller.start_game_process.assert_called_once()
    controller.stop_game.assert_not_called()
