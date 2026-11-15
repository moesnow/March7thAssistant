import ast
from contextlib import nullcontext
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
    controller = Mock(launch_method="direct", game_path="test/StarRail.exe")
    controller.switch_to_game.return_value = False
    controller.start_game_process.return_value = True
    controller.is_game_running.return_value = False
    controller.get_resolution.return_value = (1920, 1080)
    monkeypatch.setattr(game, "cfg", cfg)
    monkeypatch.setattr(game, "StarRailController", Mock(return_value=controller))
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


def test_task_readiness_waits_through_an_unavailable_frame(startup, monkeypatch):
    game, controller, _ = startup
    controller.switch_to_game.return_value = True
    controller.is_game_running.return_value = True
    monkeypatch.setattr(game, "screen", Mock())
    game.wait_until.side_effect = lambda condition, timeout: condition() or condition()
    ready = Mock(side_effect=(RuntimeError("截图超时"), True))

    game.start_game(screen_ready=ready)

    assert ready.call_count == 2
    game.screen.get_current_screen.assert_not_called()
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
    game.WindowsInputApi.return_value.process_running.assert_called_with(controller.process_name, session_id=4)
    controller.stop_game.assert_not_called()
    game.screen.get_current_screen.assert_not_called()


@pytest.mark.parametrize("takeover", (False, True))
@pytest.mark.parametrize("outcome", ("recovers", "unavailable", "stopped"))
def test_currency_wars_front_window_activation_preserves_the_existing_process(
        startup, monkeypatch, takeover, outcome):
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
    ready = Mock(return_value=True)

    def start():
        if takeover:
            game.prepare_currency_wars_takeover()
        else:
            game.start_game(screen_ready=ready)

    if outcome == "recovers":
        start()
        assert controller.set_foreground_window_with_retry.call_count == 2
        assert ready.call_count == (0 if takeover else 1)
    elif outcome == "stopped":
        with pytest.raises(RunStopRequested):
            start()
        controller.set_foreground_window_with_retry.assert_called_once()
        ready.assert_not_called()
    else:
        with pytest.raises(game.GameStartupUnavailable, match="无法将本地游戏窗口切到前台"):
            start()
        assert state.now == (game.WINDOW_WAIT_SECONDS if takeover else 3)
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
    tree = ast.parse(Path("main.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    action = Mock(side_effect=failure)
    events = Mock()
    restore, recover = events.restore, Mock()
    namespace = {"_run_action": action, "restore_temporary_graphics": restore,
                 "recover_temporary_graphics": recover, "log": Mock(), "task_power_request": events.power}
    namespace.update(cfg=None, get_control_backend=lambda cfg: "local", task_is_supported=lambda action, cfg: True)
    exec(compile(ast.Module(body=[node], type_ignores=[]), "main.py", "exec"), namespace)
    with pytest.raises(type(failure)):
        namespace["main"](action="daily")
    restore.assert_called_once_with(final=True)
    recover.assert_called_once()
    assert [call[0] for call in events.mock_calls] == ["restore", "power.release"]


def test_main_normal_return_restores():
    tree = ast.parse(Path("main.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    restore = Mock()
    namespace = {"_run_action": Mock(return_value=True), "restore_temporary_graphics": restore,
                 "recover_temporary_graphics": Mock(), "log": Mock(), "task_power_request": Mock()}
    namespace.update(cfg=None, get_control_backend=lambda cfg: "local", task_is_supported=lambda action, cfg: True)
    exec(compile(ast.Module(body=[node], type_ignores=[]), "main.py", "exec"), namespace)
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
