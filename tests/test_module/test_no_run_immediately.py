import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from module.config.config import Config


@pytest.mark.parametrize("env_value, cli, expected", [
    (None, False, False), ("false", False, False), ("0", False, False),
    ("true", False, True), ("1", False, True), (None, True, True), ("false", True, True),
])
def test_startup_wait_uses_cli_or_environment(monkeypatch, env_value, cli, expected):
    if env_value is None:
        monkeypatch.delenv("MARCH7TH_NO_RUN_IMMEDIATELY", raising=False)
    else:
        monkeypatch.setenv("MARCH7TH_NO_RUN_IMMEDIATELY", env_value)

    source = Path(__file__).resolve().parents[2] / "main.py"
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    startup = next(n for n in tree.body if isinstance(n, ast.If) and ast.unparse(n.test) == "__name__ == '__main__'")
    assignment = next(n for n in ast.walk(startup) if isinstance(n, ast.Assign)
                      and ast.unparse(n.targets[0]) == "args.no_run_immediately")
    run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_main_actions")
    cfg = Config.__new__(Config)
    cfg.config = {"notify_merge": False}
    args = SimpleNamespace(no_run_immediately=cli)
    scope = {"args": args, "cfg": cfg}
    exec(compile(ast.Module(body=[assignment], type_ignores=[]), str(source), "exec"), scope)
    assert args.no_run_immediately is expected

    game = MagicMock()
    game.after_finish_is_loop.side_effect = InterruptedError
    game.start.side_effect = InterruptedError
    scope.update(game=game, version=MagicMock(), notif=MagicMock(), telemetry=MagicMock(), time=MagicMock(), CloudGameZeroDurationError=type("CloudGameZeroDurationError", (Exception,), {}))
    exec(compile(ast.Module(body=[run], type_ignores=[]), str(source), "exec"), scope)
    with pytest.raises(InterruptedError):
        scope["run_main_actions"](args.no_run_immediately)
    if expected:
        game.after_finish_is_loop.assert_called_once_with()
        game.start.assert_not_called()
    else:
        game.after_finish_is_loop.assert_not_called()
        game.start.assert_called_once_with()
