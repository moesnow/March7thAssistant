import ast
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, Mock, call

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
    monkeypatch.setattr(game, "cfg", cfg)
    monkeypatch.setattr(game, "StarRailController", Mock(return_value=controller))
    monkeypatch.setattr(game, "auto", SimpleNamespace(input_handler=SimpleNamespace(is_background=False), press_mouse=Mock()))
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
