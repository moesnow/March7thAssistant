"""定时循环回归：使用真实等待/完成函数，隔离游戏、时钟和运行锁。"""
import ast
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


class EndRun(BaseException):
    pass


@pytest.fixture
def loop(monkeypatch):
    import tasks.game as game
    from utils.date import Date

    cfg = MagicMock()
    cfg.after_finish = "Loop"
    cfg.play_audio = False
    cfg.notify_merge = False
    cfg.scheduled_time = "4:00"
    cfg.notify_template = {"ContinueTime": "下次运行 {time}", "ErrorOccurred": "错误 {error}"}
    clock = SimpleNamespace(now=0, sleeps=[])

    def sleep(seconds):
        clock.sleeps.append(seconds)
        clock.now += seconds

    events = []

    @contextmanager
    def idle(**kwargs):
        events.append("release")
        yield
        events.append("reacquire")

    cfg._load_config.side_effect = lambda: events.append("reload")
    monkeypatch.setattr(game, "cfg", cfg)
    monkeypatch.setattr(game, "time", SimpleNamespace(time=lambda: clock.now, sleep=sleep))
    monkeypatch.setattr(game, "idle_without_run_lock", idle)
    monkeypatch.setattr(game, "is_gui_started", lambda: False)
    monkeypatch.setattr(game, "get_game_controller", MagicMock())
    monkeypatch.setattr(game, "ocr", MagicMock())
    monkeypatch.setattr(game, "notif", MagicMock())
    monkeypatch.setattr(game, "log", MagicMock())
    monkeypatch.setattr(game, "Power", MagicMock())

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls):
            return cls(2026, 11, 5, 3, 58)

    monkeypatch.setattr("utils.date.datetime", FrozenDatetime)
    monkeypatch.setattr(game, "Date", Date)
    return SimpleNamespace(game=game, cfg=cfg, clock=clock, events=events)


def test_wait_releases_lock_reloads_and_never_reads_power(loop):
    loop.game.after_finish_is_loop()
    assert loop.clock.sleeps == [60, 60]
    assert loop.events == ["release", "reacquire", "reload"]
    loop.game.Power.get.assert_not_called()
    loop.game.get_game_controller().stop_game.assert_called_once_with()
    loop.game.ocr.exit_ocr.assert_called_once_with()
    loop.game.notif.flush_batch.assert_called_once()


def test_sleep_resume_uses_wall_clock(loop):
    def resume(seconds):
        loop.clock.sleeps.append(seconds)
        loop.clock.now += 86400
    loop.game.time.sleep = resume
    loop.game.after_finish_is_loop()
    assert loop.clock.sleeps == [60]
    assert loop.events[-1] == "reload"


@pytest.mark.parametrize("trigger", ["startup", "finished", "zero_duration"])
def test_main_loop_waits_then_starts_next_run(loop, trigger):
    game = loop.game
    real_stop = game.stop
    starts = []

    def start():
        starts.append(loop.clock.now)
        if trigger == "startup" or len(starts) == 2:
            raise EndRun
        if trigger == "zero_duration":
            raise game.CloudGameZeroDurationError("时长为 0")

    # 与现有启动等待测试一致，仅加载主循环，避免 CLI 入口初始化副作用。
    source = Path(__file__).resolve().parents[2] / "main.py"
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_main_actions")
    scope = dict(game=SimpleNamespace(start=start, stop=real_stop,
                                     after_finish_is_loop=game.after_finish_is_loop,
                                     wait_after_cloud_zero_duration=game.wait_after_cloud_zero_duration),
                 cfg=loop.cfg, version=MagicMock(), Daily=MagicMock(), reward=MagicMock(),
                 notif=game.notif, telemetry=MagicMock(), time=game.time,
                 CloudGameZeroDurationError=game.CloudGameZeroDurationError)
    exec(compile(ast.Module(body=[run], type_ignores=[]), str(source), "exec"), scope)
    with pytest.raises(EndRun):
        scope["run_main_actions"](no_run_immediately=trigger == "startup")
    assert starts == ([120] if trigger == "startup" else [0, 120])
    assert loop.events == ["release", "reacquire", "reload"]
    game.Power.get.assert_not_called()
    if trigger == "finished":
        scope["Daily"].start.assert_called_once_with()
        scope["reward"].start.assert_called_once_with()
