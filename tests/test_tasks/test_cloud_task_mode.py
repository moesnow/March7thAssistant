"""直接启动任务时的云游戏模式选择与失败状态回归。"""
import ast
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from utils.pause import RunStopRequested
from utils.runs import EXIT_FAILED, EXIT_OK, exit_code_of


@pytest.fixture
def runner():
    source = Path(__file__).resolve().parents[2] / "main.py"
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {"run_main_actions", "run_sub_task", "main", "_run_action"}]
    entrypoint = next(node for node in tree.body if isinstance(node, ast.If)
                      and isinstance(node.test, ast.Compare)
                      and isinstance(node.test.left, ast.Name)
                      and node.test.left.id == "__name__")
    names = ("game", "cfg", "cloud_game", "telemetry", "time", "Daily", "reward",
             "Power", "CurrencyWars", "DivergentUniverse", "Fight", "Universe",
             "screen_test", "character_export", "challenge", "Redemption",
             "first_run", "pause_ctl", "ensure_exclusive_run", "version",
             "recover_temporary_graphics", "restore_temporary_graphics", "log")
    scope = {name: MagicMock() for name in names}
    scope["cfg"].cloud_game_enable = False
    scope["cfg"].after_finish = "None"
    scope["cfg"].browser_headless_enable = True
    scope["cfg"].notify_merge = False
    scope["CloudGameZeroDurationError"] = type("CloudGameZeroDurationError", (Exception,), {})
    scope["time"] = SimpleNamespace(time=lambda: 0)
    scope["EXCLUSIVE_ACTIONS"] = {"fight", "universe", "power", "divergent"}
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


@pytest.mark.parametrize("accounts", [[], [{"enabled": False}]])
@pytest.mark.parametrize("after_finish", ["Shutdown", "RunScript"])
def test_multi_account_empty_queue_fails_before_start_and_success_cleanup(runner, monkeypatch, accounts, after_finish):
    from tasks.game import multi_account

    runner.cfg.after_finish = after_finish
    values = {"multi_account_enable": True, "multi_accounts": accounts}
    runner.cfg.get_value.side_effect = lambda key, default=None: values.get(key, default)
    monkeypatch.setattr(multi_account, "cfg", runner.cfg)

    with pytest.raises(ValueError, match="添加并启用至少一个账号"):
        runner.run_main_actions()

    runner.version.start.assert_not_called()
    runner.game.start.assert_not_called()
    runner.Daily.start.assert_not_called()
    runner.reward.start.assert_not_called()
    runner.game.stop.assert_not_called()
    runner.telemetry.track_task_complete.assert_called_once_with("main", False, 0)


@pytest.mark.parametrize("accounts", [[], [{"enabled": False}]])
def test_routine_rejects_empty_account_queue_before_start(runner, monkeypatch, accounts):
    from tasks.game import multi_account

    values = {"multi_account_enable": True, "multi_accounts": accounts}
    runner.cfg.get_value.side_effect = lambda key, default=None: values.get(key, default)
    monkeypatch.setattr(multi_account, "cfg", runner.cfg)

    with pytest.raises(ValueError, match="添加并启用至少一个账号"):
        runner.run_sub_task("routine")

    runner.game.start.assert_not_called()
    runner.Daily.routine.assert_not_called()
    runner.game.stop.assert_not_called()


@pytest.mark.parametrize("enabled, cloud", [(False, False), (True, True)])
def test_routine_without_local_multi_account_runs_once(runner, monkeypatch, enabled, cloud):
    from tasks.game import multi_account

    runner.cfg.get_value.return_value = enabled
    runner.cfg.cloud_game_enable = cloud
    run_accounts = MagicMock()
    monkeypatch.setattr(multi_account, "run_accounts", run_accounts)

    assert runner.run_sub_task("routine") is True

    runner.Daily.routine.assert_called_once_with()
    run_accounts.assert_not_called()
    runner.game.stop.assert_called_once_with(False)


def test_routine_account_failure_skips_success_cleanup(runner, monkeypatch):
    from tasks.game import multi_account

    runner.cfg.get_value.return_value = True
    monkeypatch.setattr(multi_account, "get_enabled_accounts", lambda: [{"enabled": True}])
    monkeypatch.setattr(multi_account, "run_accounts", MagicMock(side_effect=RuntimeError("task failed")))

    with pytest.raises(RuntimeError, match="task failed"):
        runner.run_sub_task("routine")

    runner.game.stop.assert_not_called()
    runner.telemetry.track_task_complete.assert_called_once_with("routine", False, 0)


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
