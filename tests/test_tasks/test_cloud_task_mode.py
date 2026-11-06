"""直接启动任务时的云游戏模式选择与失败状态回归。"""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def runner():
    source = Path(__file__).resolve().parents[2] / "main.py"
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {"run_sub_task", "main"}]
    names = ("game", "cfg", "cloud_game", "telemetry", "time", "Daily", "reward",
             "Power", "CurrencyWars", "DivergentUniverse", "Fight", "Universe",
             "screen_test", "character_export", "challenge", "Redemption",
             "first_run", "pause_ctl", "ensure_exclusive_run")
    scope = {name: MagicMock() for name in names}
    scope["time"] = SimpleNamespace(time=lambda: 0)
    scope["EXCLUSIVE_ACTIONS"] = {"fight", "universe", "power", "divergent"}
    # 仅加载入口函数，避免导入 CLI 时触发权限检查或游戏操作。
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"), scope)
    return SimpleNamespace(**scope)


@pytest.mark.parametrize("action, headless", [
    ("fight", False), ("universe", False), ("power", None),
    ("divergent", None), ("currencywars", None),
])
def test_direct_task_selects_browser_mode(runner, action, headless):
    runner.run_sub_task(action)
    runner.game.start.assert_called_once_with(headless=headless)


@pytest.mark.parametrize("action", ["fight", "universe"])
def test_failed_task_reaches_main_without_success_shutdown(runner, action):
    runner.Fight.start.return_value = False
    runner.Universe.start.return_value = False

    assert runner.main(action=action) is False

    runner.telemetry.track_task_complete.assert_called_once_with(action, False, 0)
    runner.game.stop.assert_not_called()
    runner.game.get_game_controller().stop_game.assert_called_once_with()


def test_legacy_task_without_return_value_still_succeeds(runner):
    runner.Power.run.return_value = None
    assert runner.run_sub_task("power") is True
    runner.game.stop.assert_called_once_with(False)


def test_browser_start_failure_never_runs_task(runner):
    runner.game.start.side_effect = ConnectionError("browser unavailable")
    with pytest.raises(ConnectionError):
        runner.main(action="fight")
    runner.Fight.start.assert_not_called()
    runner.game.stop.assert_not_called()
