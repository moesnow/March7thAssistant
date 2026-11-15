"""直接启动任务时的云游戏模式选择与失败状态回归。"""
import ast
import sys
from collections import deque
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from PIL import Image
import pytest

from module.config.platform import ProfileAssetNotFoundError, TouchProfileInputError, get_control_backend, get_ui_profile
from module.game.adb_transport import AdbError
from module.localization import tr
from tasks.base import task_steps
from tasks.daily import daily
from tasks.weekly import currency_wars
from tasks.weekly.currency_wars_strategy import Slot
from tasks.weekly.currency_wars_ui import Frame, Label, Page
from utils.pause import RunStopRequested
from utils.runs import EXIT_FAILED, EXIT_OK, EXIT_STOPPED, STATUS_STOPPED, RunSession, exit_code_of
from utils.tasks import AVAILABLE_TASKS, CLI_ONLY_TASKS, HOST_TASKS, PAUSABLE_TASKS, UNSUPPORTED_TASK, task_is_supported


@pytest.fixture
def runner():
    source = Path(__file__).resolve().parents[2] / "main.py"
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {"run_main_actions", "run_sub_task", "run_sub_task_gui", "run_sub_task_update",
                                   "run_notify_action", "run_workflow_action", "main", "_run_action"}]
    entrypoint = next(node for node in tree.body if isinstance(node, ast.If)
                      and isinstance(node.test, ast.Compare)
                      and isinstance(node.test.left, ast.Name)
                      and node.test.left.id == "__name__")
    names = ("game", "cfg", "cloud_game", "telemetry", "time", "Daily", "reward",
             "Power", "CurrencyWars", "DivergentUniverse", "Fight", "Universe",
             "screen_test", "character_export", "challenge", "Redemption", "adb_check",
             "first_run", "pause_ctl", "ensure_exclusive_run", "version",
             "recover_temporary_graphics", "restore_temporary_graphics", "log", "publish_status", "run_session", "notif",
             "task_power_request", "app_update_task", "Genshin_StarRail_fps_unlocker",
             "NotificationLevel", "pause_always")
    scope = {name: MagicMock() for name in names}
    scope["cfg"].control_backend = None
    scope["cfg"].ui_profile = None
    scope["cfg"].cloud_game_enable = False
    scope["cfg"].after_finish = "None"
    scope["cfg"].browser_headless_enable = True
    scope["cfg"].notify_merge = False
    scope["CloudGameZeroDurationError"] = type("CloudGameZeroDurationError", (Exception,), {})
    scope.update(get_control_backend=get_control_backend, get_ui_profile=get_ui_profile,
                 AVAILABLE_TASKS=AVAILABLE_TASKS, CLI_ONLY_TASKS=CLI_ONLY_TASKS, HOST_TASKS=HOST_TASKS,
                 UNSUPPORTED_TASK=UNSUPPORTED_TASK, task_is_supported=task_is_supported, tr=tr, AdbError=AdbError,
                 ProfileAssetNotFoundError=ProfileAssetNotFoundError,
                 TouchProfileInputError=TouchProfileInputError,
                 CurrencyWarsTerminalError=currency_wars.CurrencyWarsTerminalError)
    scope.update(sys=sys, time=SimpleNamespace(time=lambda: 0))
    scope["EXCLUSIVE_ACTIONS"] = PAUSABLE_TASKS | {"game", "game_update", "game_pre_download", "app_update", "adb_check"}
    # 仅加载入口函数，避免导入 CLI 时触发权限检查或游戏操作。
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"), scope)
    return SimpleNamespace(
        **scope,
        entrypoint=compile(ast.Module(body=[entrypoint], type_ignores=[]), str(source), "exec"),
    )


# PC 内置任务的入口及其处理函数。
PC_TASK_HANDLERS = {
    "main": "Daily.start",
    "routine": "Daily.routine",
    "daily": "Daily.run_standalone",
    "power": "Power.run",
    "game_update": "game.update_via_launcher",
    "game_pre_download": "game.pre_download_via_launcher",
    "app_update": "app_update_task.start",
    "currencywars": "CurrencyWars.return_value.start",
    "divergent": "DivergentUniverse.return_value.start",
    "fight": "Fight.start",
    "universe": "Universe.start",
    "forgottenhall": "challenge.start",
    "purefiction": "challenge.start",
    "apocalyptic": "challenge.start",
    "currencywarsloop": "CurrencyWars.return_value.start",
    "currencywarstemp": "CurrencyWars.return_value.start",
    "divergentloop": "DivergentUniverse.return_value.start",
    "divergenttemp": "DivergentUniverse.return_value.loop",
    "universe_gui": "Universe.gui",
    "fight_gui": "Fight.gui",
    "universe_update": "Universe.update",
    "fight_update": "Fight.update",
    "mobileui_update": "Genshin_StarRail_fps_unlocker.update",
    "game": "game.start",
    "notify": "notif.notify",
    "redemption": "Redemption.start",
    "screen_test": "screen_test.run",
    "character_export": "character_export.run",
}


@pytest.mark.parametrize("action", AVAILABLE_TASKS)
def test_pc_command_dispatches_to_expected_handler(runner, action):
    handler = runner
    for attribute in PC_TASK_HANDLERS[action].split("."):
        handler = getattr(handler, attribute)
    handler.return_value = True

    if action in ("currencywarsloop", "divergentloop"):
        handler.side_effect = RunStopRequested
        with pytest.raises(RunStopRequested):
            runner.main(action=action)
    elif action in ("main", "universe_gui", "fight_gui", "universe_update", "fight_update", "mobileui_update", "notify"):
        runner.game.stop.side_effect = SystemExit(EXIT_OK)
        with pytest.raises(SystemExit) as completed:
            runner.main(action=action)
        assert completed.value.code == EXIT_OK
    else:
        assert runner.main(action=action) is not False

    handler.assert_called_once()
    if action in ("forgottenhall", "purefiction", "apocalyptic"):
        handler.assert_called_once_with("memoryofchaos" if action == "forgottenhall" else action)
    if action == "universe":
        handler.assert_called_once_with(category="universe")
    if action == "currencywarstemp":
        handler.assert_called_once_with(resume=True)
    runner.publish_status.assert_not_called()


@pytest.mark.parametrize("configured_headless", [False, True])
@pytest.mark.parametrize("action, headless", [
    ("fight", False), ("universe", False), ("power", None),
    ("divergent", None), ("currencywars", None),
])
def test_direct_task_selects_browser_mode(runner, action, headless, configured_headless):
    runner.cfg.cloud_game_enable = True
    runner.cfg.browser_headless_enable = configured_headless

    runner.run_sub_task(action)

    if action == "currencywars":
        runner.game.start.assert_called_once_with(headless=headless, screen_ready=runner.CurrencyWars.game_screen_ready)
    else:
        runner.game.start.assert_called_once_with(headless=headless)
    assert runner.cfg.browser_headless_enable is configured_headless
    runner.cfg.set_value.assert_not_called()


@pytest.mark.parametrize(("explicit_backend", "legacy_cloud", "runtime"), [
    (None, False, "local_game"),
    (None, True, "cloud_game"),
    ("adb", True, "adb_game"),
])
def test_startup_telemetry_uses_selected_backend(runner, monkeypatch, explicit_backend, legacy_cloud, runtime):
    from module.telemetry import telemetry

    telemetry_module = import_module("module.telemetry.telemetry")
    monkeypatch.setattr(telemetry_module, "_collect_startup_configuration_snapshot", dict)
    monkeypatch.setattr(telemetry_module, "_resolve_effective_ocr_mode", lambda: "cpu")
    monkeypatch.setattr(telemetry_module, "_resolve_effective_language", lambda: "zh_CN")
    monkeypatch.setattr(telemetry, "_enabled", True)
    monkeypatch.setattr(telemetry, "_queue", deque())
    runner.telemetry.track_startup.side_effect = telemetry.track_startup
    runner.cfg.control_backend = explicit_backend
    runner.cfg.cloud_game_enable = legacy_cloud

    runner.main(action="game")

    event, = telemetry._queue
    assert event["event"] == "app_startup"
    assert event["properties"]["game_runtime"] == runtime


@pytest.mark.parametrize("stop_error", (RunStopRequested, RuntimeError))
def test_currency_wars_loop_continues_after_settled_matches_until_stopped(runner, stop_error):
    war = runner.CurrencyWars.return_value
    war.start.side_effect = [True, False, True, True, stop_error()]

    with pytest.raises(stop_error):
        runner.run_sub_task("currencywarsloop")

    assert war.start.call_count == 5
    assert [call.args for call in runner.telemetry.track_task_complete.call_args_list[:4]] == [
        ("currencywarsloop", won, 0) for won in (True, False, True, True)
    ]
    runner.game.stop.assert_not_called()


@pytest.fixture
def currency_wars_game(runner, monkeypatch):
    image = Image.new("RGB", (1920, 1080))

    def frame(page, *labels, **properties):
        current = Frame(image, tuple(Label(text, point) for text, point in labels))
        current.__dict__.update(page=page, **properties)
        return current

    frames = {
        "home": frame(Page.HOME, ("开始货币战争", (1600, 972)), ("积分", (381, 961))),
        "mode": frame(Page.MODES, ("进入标准博弈", (1640, 961)), unfinished_match=False),
        "rank": frame(Page.RANK, ("开始对局", (1680, 965)), rank_mode="normal", enemy_rank=1),
        "board": frame(Page.BOARD, ("出战", (1818, 750)), stage="1-1", capacity=(1, 1),
                       slots=lambda: (Slot("front", 0, (745, 405), True),), inventory_items=lambda: ()),
        "delayed": frame(Page.UNKNOWN),
        "battle": frame(Page.BATTLE, auto_off=False),
        "result": frame(Page.MATCH_RESULT, ("挑战成功", (960, 233)), ("返回货币战争", (960, 899))),
    }
    state = SimpleNamespace(page="home", now=0.0, completed=0, clicks=[], delayed_reads=0, battle_reads=0,
                            fault=None, stop=False, delayed_until=None, later_steps=[], capture_failures=0)
    clock = SimpleNamespace(monotonic=lambda: state.now,
                            sleep=lambda seconds: setattr(state, "now", state.now + seconds))
    auto = MagicMock()

    def capture():
        if state.page == "delayed":
            state.delayed_reads += 1
            if state.fault == "unavailable":
                state.capture_failures += 1
                raise OSError("窗口持续不可用")
            if state.fault is None and state.now >= state.delayed_until:
                state.page = "battle"
        if state.page == "battle":
            state.battle_reads += 1
            if state.battle_reads == 3:
                state.page = "result"
        if state.page == "weekly":
            score = 18000 if state.completed else 0
            return frame(Page.WEEKLY, (f"{score}/18000", (245, 748)), claim_available=lambda: False)
        return frames[state.page]

    def click(point, *, press_duration):
        state.clicks.append((state.page, point))
        if state.page == "board":
            assert point == (1818, 750)
            state.battle_reads = 0
            state.delayed_until = state.now + 28
            state.page = "battle" if state.completed else "delayed"
        else:
            if state.page == "result":
                state.completed += 1
            state.page = {
                ("home", (1600, 972)): "mode", ("home", (381, 961)): "weekly",
                ("mode", (1640, 961)): "rank", ("rank", (1680, 965)): "board",
                ("result", (960, 899)): "home",
            }[state.page, point]

    def press(key):
        assert key == "esc" and state.page == "weekly"
        state.page = "home"

    def checkpoint():
        if state.stop or (state.page == "delayed" and state.fault == "stopped"):
            raise RunStopRequested

    auto.find_element.side_effect = lambda pos, *args, **kwargs: (round(pos[0] * 1920), round(pos[1] * 1080))
    auto.click_element_with_pos.side_effect = click
    auto.press_key.side_effect = press
    cfg = SimpleNamespace(
        currencywars_strategy="default", currencywars_type="normal", currencywars_rank_difficulty="current",
        currencywars_bonus_enable=False, currencywars_enable=True, currencywars_timestamp=1, refresh_hour=4,
        asset_manager_enable=False, weekly_divergent_enable=False, fight_enable=False, universe_enable=False,
        forgottenhall_enable=False, purefiction_enable=False, apocalyptic_enable=False,
        forgottenhall_timestamp=1, purefiction_timestamp=1, apocalyptic_timestamp=1,
        save_timestamp=MagicMock(),
    )
    cfg.get_value = lambda key, default=None: getattr(cfg, key, default)
    monkeypatch.setattr(currency_wars, "cfg", cfg)
    monkeypatch.setattr(currency_wars, "auto", auto)
    monkeypatch.setattr(currency_wars, "time", clock)
    monkeypatch.setattr(currency_wars, "pause_ctl", SimpleNamespace(checkpoint=checkpoint))
    monkeypatch.setattr(currency_wars, "get_ui_profile", lambda _: SimpleNamespace(name="pc_1080"))
    monkeypatch.setattr(currency_wars, "Base", MagicMock())
    monkeypatch.setattr(currency_wars, "save_error_screenshot", MagicMock(return_value="currencywars.png"))
    monkeypatch.setattr(currency_wars, "TASK_SECONDS", 90)
    monkeypatch.setattr(currency_wars.CurrencyWars, "_capture", staticmethod(capture))
    def create_task():
        war = currency_wars.CurrencyWars()
        war._recover_transit = MagicMock(wraps=war._recover_transit)
        state.recover_transit = war._recover_transit
        return war

    factory = MagicMock(side_effect=create_task)
    factory.game_screen_ready = currency_wars.CurrencyWars.game_screen_ready
    runner.main.__globals__["CurrencyWars"] = factory
    runner.game.stop.side_effect = lambda detect_loop: sys.exit(EXIT_OK) if detect_loop else None
    monkeypatch.setattr(daily, "cfg", cfg)
    monkeypatch.setattr(daily, "CurrencyWars", factory)
    monkeypatch.setattr(daily.Date, "is_next_mon_x_am", lambda *_: True)
    monkeypatch.setattr(daily.Daily, "prepare_daily", lambda: True)
    monkeypatch.setattr(daily.reward, "start", lambda: state.later_steps.append("日常领奖"))
    monkeypatch.setattr(daily.Daily, "run", lambda **_: state.later_steps.append("每日实训"))
    monkeypatch.setattr(task_steps, "screen", MagicMock())
    runner.Daily.start.side_effect = daily.Daily.start
    state.factory = factory
    return state


def run_currency_wars_cli(runner, action):
    session = RunSession({"run_id": "20261115-120000-abcd"})
    session._save = MagicMock()
    session.release_lock = MagicMock()
    runner.cfg.get_value.return_value = False
    runner.cfg.notify_template = {"ErrorOccurred": "发生错误：{error}"}
    scope = runner.main.__globals__
    scope.update(
        __name__="__main__", sys=sys, atexit=MagicMock(), exit_handler=MagicMock(),
        args=SimpleNamespace(task=action, workflow_name=None, no_run_immediately=False),
        run_session=session, RunStopRequested=RunStopRequested, STATUS_STOPPED=STATUS_STOPPED,
        EXIT_FAILED=EXIT_FAILED, EXIT_OK=EXIT_OK, EXIT_STOPPED=EXIT_STOPPED, exit_code_of=exit_code_of,
        release_input=MagicMock(), pause_on_error=MagicMock(), save_error_screenshot=MagicMock(),
        NotificationLevel=currency_wars.NotificationLevel,
    )
    try:
        exec(runner.entrypoint, scope)
    except SystemExit as error:
        assert error.code == session.record["exit_code"]
    session.release_lock.assert_called_once()
    return session.record


@pytest.mark.parametrize("action", ("currencywars", "currencywarsloop", "currencywarstemp", "main"))
def test_currency_wars_entry_continues_after_the_fight_receipt_times_out(runner, currency_wars_game, action):
    state = currency_wars_game
    if action == "currencywarstemp":
        state.page = "board"
    if action == "currencywarsloop":
        def stop_after_two(task_id, success, duration):
            assert task_id == "currencywarsloop" and success
            if state.completed == 2:
                state.stop = True

        runner.telemetry.track_task_complete.side_effect = stop_after_two

    record = run_currency_wars_cli(runner, action)
    expected = 2 if action == "currencywarsloop" else 1
    assert state.completed == expected
    state.recover_transit.assert_called_once()
    assert isinstance(state.recover_transit.call_args.args[1], currency_wars.CurrencyWarsReceiptTimeout)
    assert state.clicks.count(("board", (1818, 750))) == expected
    assert state.clicks.count(("rank", (1680, 965))) == (0 if action == "currencywarstemp" else expected)
    state.factory.assert_called_once_with()
    assert record["status"] == ("stopped" if action == "currencywarsloop" else "success")
    if action == "main":
        assert state.later_steps == ["日常领奖", "每日实训"]
    task_steps.screen.change_to.assert_not_called()


@pytest.mark.parametrize("action", ("currencywars", "currencywarsloop", "currencywarstemp", "main"))
@pytest.mark.parametrize(("fault", "status", "reason", "exit_code"), (
    ("unavailable", "failed", "currencywars_unavailable", EXIT_FAILED),
    ("timeout", "failed", "currencywars_timeout", EXIT_FAILED),
    ("stopped", "stopped", None, EXIT_STOPPED),
))
def test_currency_wars_entry_records_clear_terminal_states(
        runner, currency_wars_game, monkeypatch, action, fault, status, reason, exit_code):
    state = currency_wars_game
    state.fault = fault
    if action == "currencywarstemp":
        state.page = "board"
    if fault == "timeout":
        monkeypatch.setattr(currency_wars, "TASK_SECONDS", 34)
    record = run_currency_wars_cli(runner, action)

    assert (record["status"], record["reason"], record["exit_code"]) == (status, reason, exit_code)
    assert state.completed == 0 and state.later_steps == []
    assert state.clicks.count(("board", (1818, 750))) == 1
    state.factory.assert_called_once_with()
    task_steps.screen.change_to.assert_not_called()
    scope = runner.main.__globals__
    scope["save_error_screenshot"].assert_not_called()
    scope["pause_on_error"].assert_not_called()
    if fault == "stopped":
        scope["release_input"].assert_called_once_with(close=True)
        assert record["error"] is None and record["screenshot"] is None
        currency_wars.save_error_screenshot.assert_not_called()
        runner.notif.notify.assert_not_called()
    else:
        scope["release_input"].assert_called_once_with()
        assert record["error"] and record["screenshot"] == "currencywars.png"
        currency_wars.save_error_screenshot.assert_called_once()
    if fault == "unavailable":
        assert state.capture_failures == currency_wars.MAX_CAPTURE_ATTEMPTS


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
def test_pc_daily_uses_desktop_daily_entry(runner, backend):
    runner.cfg.control_backend = backend

    assert runner.main(action="daily") is True

    runner.Daily.run_standalone.assert_called_once_with()


@pytest.mark.parametrize("backend", ["local", "adb"])
@pytest.mark.parametrize(("action", "target"), [
    ("daily", "tasks.touch.rewards.run_daily_training"),
    ("routine", "tasks.touch.rewards.routine"),
    ("power", "tasks.touch.power.run_standalone"),
])
def test_touch_subtasks_run_without_pc_tasks(runner, monkeypatch, backend, action, target):
    runner.cfg.ui_profile = "touch_720"
    runner.cfg.control_backend = backend
    task = MagicMock(return_value=True)
    monkeypatch.setattr(target, task)

    assert runner.main(action=action) is True

    runner.game.start.assert_called_once_with(headless=None)
    task.assert_called_once_with()
    runner.Daily.run.assert_not_called()
    runner.Daily.run_standalone.assert_not_called()
    runner.Daily.routine.assert_not_called()
    runner.Power.run.assert_not_called()
    runner.reward.start.assert_not_called()
    if backend == "adb":
        runner.game.get_game_controller.assert_called_once_with("adb")
        runner.publish_status.assert_called_once_with(runner.game.get_game_controller.return_value, runner.run_session)
        runner.game.get_game_controller.return_value.close.assert_called_once_with()


@pytest.mark.parametrize("action, workflow, backend", [
    *[(action, None, "local") for action in sorted(
        AVAILABLE_TASKS.keys() - {"main", "daily", "routine", "power", "screen_test", "game", "mobileui_update", "app_update", "notify"}
    )],
    (None, "测试流程", "local"),
    ("daily", None, "cloud"),
    ("routine", None, "cloud"),
    ("power", None, "cloud"),
    ("game", None, "cloud"),
])
def test_touch_skips_unsupported_tasks_before_starting_game(runner, action, workflow, backend):
    runner.cfg.ui_profile = "touch_720"
    runner.cfg.control_backend = backend

    assert runner.main(action=action, workflow_name=workflow) is False

    assert UNSUPPORTED_TASK in runner.log.warning.call_args.args[0]
    assert runner.run_session.note.call_args.kwargs["reason"] == "unsupported_backend"
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
    runner.task_power_request.acquire.assert_called_once_with(runner.log)
    runner.task_power_request.release.assert_called_once_with(runner.log)
    scope["run_session"].finish.assert_called_once_with(EXIT_FAILED)
    runner.game.start.assert_not_called()
    runner.version.start.assert_not_called()
    runner.game.after_finish_is_loop.assert_not_called()
    scope["save_error_screenshot"].assert_not_called()
    scope["pause_on_error"].assert_not_called()



@pytest.mark.parametrize("action", ["fight", "fight_gui", "universe", "universe_gui"])
def test_review_adb_cli_rejects_desktop_tasks_before_game_start(runner, action):
    runner.cfg.control_backend = "adb"

    assert runner.main(action=action) is False
    assert runner.run_session.note.call_args.kwargs["status"] == "blocked"
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


@pytest.mark.parametrize("result", [True, False])
def test_adb_full_run_uses_touch_routine(runner, monkeypatch, result):
    from tasks.touch import rewards

    runner.cfg.control_backend = "adb"
    routine = MagicMock(return_value=result)
    monkeypatch.setattr(rewards, "routine", routine)
    if result:
        runner.game.stop.side_effect = SystemExit(EXIT_OK)
        with pytest.raises(SystemExit) as raised:
            runner.main(action="main")
        assert raised.value.code == EXIT_OK
    else:
        assert runner.main(action="main") is False
        runner.game.stop.assert_not_called()
    routine.assert_called_once_with(full_run=True)
    runner.Daily.start.assert_not_called()
    runner.telemetry.track_task_complete.assert_called_once_with("main", result, 0)


def test_adb_workflow_reports_not_executed(runner):
    runner.cfg.control_backend = "adb"
    assert runner.main(workflow_name="测试流程") is False
    assert runner.run_session.note.call_args.kwargs["reason"] == "unsupported_backend"
    runner.game.get_game_controller.assert_not_called()
