"""直接启动任务时的云游戏模式选择与失败状态回归。"""
import ast
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from module.config.platform import ProfileAssetNotFoundError, TouchProfileInputError, get_control_backend, get_ui_profile
from module.game import require_desktop_task
from module.game.adb_transport import AdbError
from module.localization import tr
from utils.pause import RunStopRequested
from utils.runs import EXIT_FAILED, EXIT_OK, exit_code_of
from utils.tasks import AVAILABLE_TASKS, PAUSABLE_TASKS


@pytest.fixture
def runner():
    source = Path(__file__).resolve().parents[2] / "main.py"
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {"run_main_actions", "run_sub_task", "run_workflow_action", "main", "_run_action"}]
    entrypoint = next(node for node in tree.body if isinstance(node, ast.If)
                      and isinstance(node.test, ast.Compare)
                      and isinstance(node.test.left, ast.Name)
                      and node.test.left.id == "__name__")
    names = ("game", "cfg", "cloud_game", "telemetry", "time", "Daily", "reward",
             "Power", "CurrencyWars", "DivergentUniverse", "Fight", "Universe",
             "screen_test", "character_export", "challenge", "Redemption", "adb_check",
             "first_run", "pause_ctl", "ensure_exclusive_run", "version",
             "recover_temporary_graphics", "restore_temporary_graphics", "log")
    scope = {name: MagicMock() for name in names}
    scope["cfg"].control_backend = None
    scope["cfg"].ui_profile = None
    scope["cfg"].cloud_game_enable = False
    scope["cfg"].after_finish = "None"
    scope["cfg"].browser_headless_enable = True
    scope["cfg"].notify_merge = False
    scope["CloudGameZeroDurationError"] = type("CloudGameZeroDurationError", (Exception,), {})
    scope.update(get_control_backend=get_control_backend, get_ui_profile=get_ui_profile,
                 require_desktop_task=require_desktop_task, AVAILABLE_TASKS=AVAILABLE_TASKS, tr=tr, AdbError=AdbError,
                 ProfileAssetNotFoundError=ProfileAssetNotFoundError,
                 TouchProfileInputError=TouchProfileInputError)
    scope["time"] = SimpleNamespace(time=lambda: 0)
    scope["EXCLUSIVE_ACTIONS"] = PAUSABLE_TASKS | {"game", "game_update", "game_pre_download", "app_update", "adb_check"}
    # 仅加载入口函数，避免导入 CLI 时触发权限检查或游戏操作。
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"), scope)
    return SimpleNamespace(
        **scope,
        entrypoint=compile(ast.Module(body=[entrypoint], type_ignores=[]), str(source), "exec"),
    )


@pytest.mark.parametrize("configured_headless", [False, True])
@pytest.mark.parametrize("action, headless", [
    ("fight", False), ("universe", False), ("power", None),
    ("divergent", None), ("currencywars", None),
])
def test_direct_task_selects_browser_mode(runner, action, headless, configured_headless):
    runner.cfg.cloud_game_enable = True
    runner.cfg.browser_headless_enable = configured_headless

    runner.run_sub_task(action)

    runner.game.start.assert_called_once_with(headless=headless)
    assert runner.cfg.browser_headless_enable is configured_headless
    runner.cfg.set_value.assert_not_called()


@pytest.mark.parametrize("cloud_game_enable", [False, True], ids=["local", "visible-cloud"])
@pytest.mark.parametrize("after_finish", [
    "None", "Exit", "Loop", "Shutdown", "Sleep", "Hibernate", "Restart", "Logoff",
    "TurnOffDisplay", "RunScript",
])
@pytest.mark.parametrize("action", ["fight", "universe"])
def test_failed_task_respects_cleanup_setting(runner, action, after_finish, cloud_game_enable):
    runner.cfg.cloud_game_enable = cloud_game_enable
    runner.cfg.after_finish = after_finish
    runner.Fight.start.return_value = False
    runner.Universe.start.return_value = False

    assert runner.main(action=action) is False
    runner.restore_temporary_graphics.assert_called_once_with(final=True)

    runner.game.start.assert_called_once_with(headless=False)
    runner.telemetry.track_task_complete.assert_called_once_with(action, False, 0)
    runner.game.stop.assert_not_called()
    runner.game.after_finish_is_loop.assert_not_called()
    controller = runner.game.get_game_controller.return_value
    controller.shutdown.assert_not_called()
    controller.run_script.assert_not_called()
    if after_finish == "Exit":
        controller.stop_game.assert_called_once_with()
    else:
        runner.game.get_game_controller.assert_not_called()
        controller.stop_game.assert_not_called()


@pytest.mark.parametrize("action", ["fight", "universe"])
def test_failed_task_exits_with_failure_code(runner, action):
    runner.Fight.start.return_value = False
    runner.Universe.start.return_value = False
    runner.cfg.get_value.return_value = False
    scope = runner.main.__globals__
    scope.update(
        __name__="__main__", sys=sys, atexit=MagicMock(), exit_handler=MagicMock(),
        args=SimpleNamespace(task=action, workflow_name=None, no_run_immediately=False),
        run_session=MagicMock(), RunStopRequested=RunStopRequested,
        EXIT_FAILED=EXIT_FAILED, EXIT_OK=EXIT_OK, exit_code_of=exit_code_of,
    )

    with pytest.raises(SystemExit) as raised:
        exec(runner.entrypoint, scope)

    assert raised.value.code == EXIT_FAILED
    scope["run_session"].finish.assert_called_once_with(EXIT_FAILED)
    scope["atexit"].register.assert_called_once_with(scope["exit_handler"])
    runner.telemetry.track_task_complete.assert_called_once_with(action, False, 0)
    runner.game.stop.assert_not_called()
    runner.game.get_game_controller.assert_not_called()


@pytest.mark.parametrize("action", ["fight", "universe"])
def test_successful_task_keeps_success_cleanup(runner, action):
    runner.Fight.start.return_value = True
    runner.Universe.start.return_value = True

    assert runner.main(action=action) is True

    runner.telemetry.track_task_complete.assert_called_once_with(action, True, 0)
    runner.game.stop.assert_called_once_with(False)
    runner.game.get_game_controller.assert_not_called()


def test_legacy_task_without_return_value_still_succeeds(runner):
    runner.Power.run.return_value = None
    assert runner.run_sub_task("power") is True
    runner.telemetry.track_task_complete.assert_called_once_with("power", True, 0)
    runner.game.stop.assert_called_once_with(False)


@pytest.mark.parametrize("backend", ["local", "cloud"])
def test_pc_daily_still_runs_daily_and_rewards(runner, backend):
    runner.cfg.control_backend = backend

    assert runner.main(action="daily") is True

    runner.Daily.run.assert_called_once_with()
    runner.reward.start.assert_called_once_with()


@pytest.mark.parametrize("backend", ["local", "adb"])
def test_touch_daily_runs_without_pc_rewards(runner, monkeypatch, backend):
    runner.cfg.ui_profile = "touch_720"
    runner.cfg.control_backend = backend
    task = MagicMock(return_value=True)
    monkeypatch.setattr("tasks.touch.daily.run", task)

    assert runner.main(action="daily") is True

    runner.game.start.assert_called_once_with(headless=None)
    task.assert_called_once_with()
    runner.Daily.run.assert_not_called()
    runner.reward.start.assert_not_called()
    if backend == "adb":
        runner.game.get_game_controller.assert_called_once_with("adb")
        runner.game.get_game_controller.return_value.close.assert_called_once_with()


@pytest.mark.parametrize("action, workflow, backend", [
    *[(action, None, "local") for action in sorted(
        AVAILABLE_TASKS.keys() - {"daily", "game", "mobileui_update", "app_update", "notify"}
    )],
    (None, None, "local"),
    (None, "测试流程", "local"),
    ("daily", None, "cloud"),
    ("game", None, "cloud"),
])
def test_touch_skips_unsupported_tasks_before_starting_game(runner, action, workflow, backend):
    runner.cfg.ui_profile = "touch_720"
    runner.cfg.control_backend = backend

    assert runner.main(action=action, workflow_name=workflow) is None

    assert "触屏模式暂不支持" in runner.log.warning.call_args.args[0]
    runner.ensure_exclusive_run.assert_not_called()
    runner.game.start.assert_not_called()
    runner.game.get_game_controller.assert_not_called()
    runner.Daily.start.assert_not_called()
    runner.reward.start.assert_not_called()


@pytest.mark.parametrize("action", [None, "main"])
def test_full_run_keeps_default_browser_mode(runner, action):
    runner.cfg.cloud_game_enable = True
    runner.game.stop.side_effect = SystemExit(0)

    with pytest.raises(SystemExit) as raised:
        runner.main(action=action)

    assert raised.value.code == 0
    runner.game.start.assert_called_once_with()
    runner.game.stop.assert_called_once_with(True)
    runner.cfg.set_value.assert_not_called()


@pytest.mark.parametrize("action", ["screen_test", "character_export"])
@pytest.mark.parametrize("result", [False, True])
def test_cleanup_exceptions_remain_exempt(runner, action, result):
    runner.cfg.after_finish = "Exit"
    getattr(runner, action).run.return_value = result

    assert runner.main(action=action) is result

    runner.telemetry.track_task_complete.assert_called_once_with(action, result, 0)
    runner.game.stop.assert_not_called()
    runner.game.get_game_controller.assert_not_called()


def test_browser_start_failure_never_runs_task(runner):
    runner.game.start.side_effect = ConnectionError("browser unavailable")
    with pytest.raises(ConnectionError):
        runner.main(action="fight")
    runner.Fight.start.assert_not_called()
    runner.game.stop.assert_not_called()


def test_adb_cli_returns_failure_without_screenshot_or_pause(runner):
    runner.cfg.control_backend = "adb"
    runner.cfg.ui_profile = "touch_720"
    runner.adb_check.run.side_effect = AdbError("disconnected", "ADB 设备断开")
    scope = runner.main.__globals__
    scope.update(
        __name__="__main__", sys=sys, atexit=MagicMock(), exit_handler=MagicMock(),
        args=SimpleNamespace(task="adb_check", workflow_name=None, no_run_immediately=False),
        run_session=MagicMock(), RunStopRequested=RunStopRequested,
        EXIT_FAILED=EXIT_FAILED, EXIT_OK=EXIT_OK, exit_code_of=exit_code_of,
        release_input=MagicMock(), save_error_screenshot=MagicMock(), pause_on_error=MagicMock(),
    )

    with pytest.raises(SystemExit) as raised:
        exec(runner.entrypoint, scope)

    assert raised.value.code == EXIT_FAILED
    scope["run_session"].note.assert_called_once_with(error=str(runner.adb_check.run.side_effect))
    runner.game.get_game_controller.return_value.close.assert_called_once_with()
    scope["run_session"].finish.assert_called_once_with(EXIT_FAILED)
    runner.game.start.assert_not_called()
    runner.version.start.assert_not_called()
    runner.game.after_finish_is_loop.assert_not_called()
    scope["save_error_screenshot"].assert_not_called()
    scope["pause_on_error"].assert_not_called()



@pytest.mark.parametrize("action", ["fight", "fight_gui", "universe", "universe_gui"])
def test_review_adb_cli_rejects_desktop_tasks_before_game_start(runner, action):
    runner.cfg.control_backend = "adb"

    with pytest.raises(AdbError) as raised:
        runner.main(action=action)

    assert raised.value.code == "desktop_task_unsupported"
    runner.game.start.assert_not_called()
    runner.Fight.start.assert_not_called()
    runner.Universe.start.assert_not_called()


@pytest.mark.parametrize(("module_name", "class_name"), [
    ("tasks.daily.fight", "Fight"),
    ("tasks.weekly.universe", "Universe"),
])
@pytest.mark.parametrize("method", ["start", "gui"])
def test_review_adb_blocks_desktop_task_preparation(monkeypatch, module_name, class_name, method):
    from importlib import import_module
    from unittest.mock import Mock

    task_module = import_module(module_name)
    task = getattr(task_module, class_name)
    monkeypatch.setattr(task_module, "cfg", SimpleNamespace(control_backend="adb", cloud_game_enable=False))
    monkeypatch.setattr(task_module, "sys", SimpleNamespace(platform="win32"))
    check_path = Mock(side_effect=AssertionError("unexpected host task preparation"))
    monkeypatch.setattr(task, "check_path", check_path)

    with pytest.raises(AdbError) as raised:
        getattr(task, method)()

    assert raised.value.code == "desktop_task_unsupported"
    check_path.assert_not_called()


def test_review_adb_blocks_fight_scheduled_by_daily(monkeypatch):
    from unittest.mock import Mock

    from tasks.daily import daily, fight

    config = SimpleNamespace(control_backend="adb", cloud_game_enable=False, asset_manager_enable=False,
                             currencywars_enable=False, weekly_divergent_enable=False, fight_enable=True,
                             fight_timestamp=None, refresh_hour=4)
    monkeypatch.setattr(daily, "cfg", config)
    monkeypatch.setattr(fight, "cfg", config)
    monkeypatch.setattr(fight, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(daily.Daily, "prepare_daily", Mock())
    monkeypatch.setattr(daily, "DivergentUniverse", Mock())
    monkeypatch.setattr(daily, "Date", SimpleNamespace(is_next_x_am=Mock(return_value=True)))
    check_path = Mock(side_effect=AssertionError("unexpected host task preparation"))
    monkeypatch.setattr(fight.Fight, "check_path", check_path)

    with pytest.raises(AdbError) as raised:
        daily.Daily.start()

    assert raised.value.code == "desktop_task_unsupported"
    check_path.assert_not_called()



@pytest.mark.parametrize("error_code", ["disconnected", "manual_action_required"])
def test_review_adb_workflow_cli_records_failure(runner, monkeypatch, error_code):
    from unittest.mock import Mock

    from module.workflow import WorkflowRunner

    runner.cfg.control_backend = "adb"
    runner.game.ensure_game_ready.return_value = True
    error = AdbError(error_code, "ADB 任务中断")
    click = Mock(side_effect=error)
    monkeypatch.setattr("module.workflow.auto.click_element", click)
    sleep = Mock()
    workflow = {"name": "ADB 工作流", "steps": [
        {"type": "click_crop", "crop": "0, 0, 1, 1"},
        {"type": "wait", "seconds": 1},
    ]}
    scope = runner.main.__globals__
    scope.update(
        __name__="__main__", sys=sys, atexit=MagicMock(), exit_handler=MagicMock(),
        args=SimpleNamespace(task=None, workflow_name="ADB 工作流", workflow_step_path=None, no_run_immediately=False),
        run_session=MagicMock(), RunStopRequested=RunStopRequested, release_input=MagicMock(),
        EXIT_FAILED=EXIT_FAILED, EXIT_OK=EXIT_OK, exit_code_of=exit_code_of,
        load_workflow_execution_payload=Mock(return_value=workflow),
        WorkflowRunner=lambda **kwargs: WorkflowRunner(sleep_func=sleep, **kwargs),
    )

    with pytest.raises(SystemExit) as raised:
        exec(runner.entrypoint, scope)

    assert raised.value.code == EXIT_FAILED
    click.assert_called_once()
    sleep.assert_not_called()
    scope["run_session"].note.assert_called_once_with(error=str(error))
    scope["run_session"].finish.assert_called_once_with(EXIT_FAILED)
    runner.game.get_game_controller.return_value.close.assert_called_once_with()
