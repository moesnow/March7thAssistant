"""定时循环回归：使用真实等待/完成函数，隔离游戏、时钟和运行锁。"""
import ast
from contextlib import contextmanager, nullcontext
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tasks.base.task_steps import GameRecoveryError


class EndRun(BaseException):
    pass


@pytest.fixture
def loop(monkeypatch):
    import tasks.game as game
    from utils.date import Date

    cfg = MagicMock()
    cfg.control_backend = None
    cfg.ui_profile = None
    cfg.cloud_game_enable = False
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
    monkeypatch.setattr(game, "task_power_request", SimpleNamespace(release=lambda log: events.append("release_power")))

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
    assert loop.events == ["release_power", "release", "reacquire", "reload"]
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


def test_preserved_local_game_wait_releases_resources_and_honors_stop(loop, monkeypatch):
    from utils.pause import RunStopRequested

    def check_stop():
        if loop.clock.now:
            raise RunStopRequested

    monkeypatch.setattr(loop.game, "pause_ctl", SimpleNamespace(enabled=True, check_stop=check_stop))

    with pytest.raises(RunStopRequested):
        loop.game.after_finish_is_loop(preserve_game=True)

    assert loop.clock.sleeps == [1]
    assert loop.events == ["release_power", "release"]
    loop.game.get_game_controller.assert_not_called()
    loop.game.ocr.exit_ocr.assert_called_once_with()


@pytest.mark.parametrize("trigger", ["startup", "finished", "failed", "zero_duration"])
def test_main_loop_waits_then_starts_next_run(loop, trigger):
    game = loop.game
    from module.config.platform import get_control_backend
    real_stop = game.stop
    starts = []
    if trigger == "failed":
        loop.cfg.cloud_game_enable = True

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
                 CloudGameZeroDurationError=game.CloudGameZeroDurationError,
                 GameRecoveryError=GameRecoveryError,
                 get_ui_profile=lambda cfg: SimpleNamespace(name="pc_1080"), get_control_backend=get_control_backend,
                 is_gui_started=game.is_gui_started, _game_connection=lambda _: nullcontext())
    scope["Daily"].start.return_value = trigger != "failed"
    exec(compile(ast.Module(body=[run], type_ignores=[]), str(source), "exec"), scope)
    with pytest.raises(EndRun):
        scope["run_main_actions"](no_run_immediately=trigger == "startup")
    assert starts == ([120] if trigger == "startup" else [0, 120])
    assert loop.events == ["release_power", "release", "reacquire", "reload"]
    game.Power.get.assert_not_called()
    if trigger == "finished":
        scope["Daily"].start.assert_called_once_with()
        scope["reward"].start.assert_not_called()
    if trigger == "failed":
        scope["telemetry"].track_task_complete.assert_called_once_with("main", False, 0)
        game.get_game_controller.return_value.stop_game.assert_called_once_with()


@pytest.mark.parametrize(("initial", "new", "zero_duration"), [
    ("local", "adb", False), ("adb", "cloud", False), ("cloud", "local", True),
])
def test_loop_rebinds_game_connection_for_the_next_round(loop, monkeypatch, initial, new, zero_duration):
    from module.config.platform import pin_game_connection
    from tasks.touch import rewards
    from utils.tasks import task_is_supported

    game = loop.game
    loop.cfg.control_backend = initial
    loop.cfg._load_config.side_effect = lambda: setattr(loop.cfg, "control_backend", new)
    controller = game.get_game_controller.return_value
    automation, navigation = MagicMock(), MagicMock()
    automation.connection = initial, game.get_ui_profile(loop.cfg).name
    monkeypatch.setattr(game, "auto", automation)
    monkeypatch.setattr(game, "screen", navigation)
    monkeypatch.setattr(rewards, "routine", MagicMock(return_value=True))
    started = []
    status_endpoints = []
    session = SimpleNamespace(record={}, update_record=MagicMock())
    stopped = []
    controller.stop_game.side_effect = lambda: stopped.append(game.get_control_backend(loop.cfg))

    @contextmanager
    def publish(current, run):
        assert current is controller and run is session
        status_endpoints.append(loop.cfg.control_backend)
        session.record["adb_status_endpoint"] = True
        yield

    def start():
        started.append((game.get_control_backend(loop.cfg), "adb_status_endpoint" in session.record))
        if len(started) == 2:
            raise EndRun
        # 其他进程修改配置，当前轮保存进度时合并了游戏连接字段。
        loop.cfg.control_backend = new
        assert game.get_control_backend(loop.cfg) == initial
        if zero_duration:
            raise game.CloudGameZeroDurationError("时长为 0")

    source = Path(__file__).resolve().parents[2] / "main.py"
    nodes = [n for n in ast.parse(source.read_text(encoding="utf-8-sig")).body
             if isinstance(n, ast.FunctionDef) and n.name in {"run_main_actions", "_game_connection"}]
    scope = dict(cfg=loop.cfg, contextmanager=contextmanager, pin_game_connection=pin_game_connection,
                 HOST_TASKS=set(), publish_status=publish,
                 task_is_supported=task_is_supported,
                 recover_temporary_graphics=MagicMock(), restore_temporary_graphics=MagicMock(), log=game.log,
                 run_session=session, get_control_backend=game.get_control_backend, get_ui_profile=game.get_ui_profile,
                 game=SimpleNamespace(start=start, stop=game.stop, get_game_controller=game.get_game_controller,
                                      wait_after_cloud_zero_duration=game.wait_after_cloud_zero_duration,
                                      prepare_game_connection=game.prepare_game_connection),
                 version=MagicMock(), Daily=MagicMock(), notif=game.notif, telemetry=MagicMock(), time=game.time,
                 CloudGameZeroDurationError=game.CloudGameZeroDurationError,
                 GameRecoveryError=GameRecoveryError)
    scope["Daily"].start.return_value = True
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), scope)
    with pytest.raises(EndRun):
        scope["run_main_actions"]()
    assert started == [(initial, initial == "adb"), (new, new == "adb")]
    assert status_endpoints == [backend for backend in (initial, new) if backend == "adb"]
    assert stopped == [initial]
    automation.reload_connection.assert_called_once_with()
    navigation.reload_profile.assert_called_once_with()
