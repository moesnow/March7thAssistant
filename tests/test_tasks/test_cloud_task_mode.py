"""直接启动任务时的云游戏模式选择与失败状态回归。"""
import ast
import sys
from collections import deque
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from PIL import Image, ImageDraw
import pytest
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, WebDriverException

from module.config.platform import ProfileAssetNotFoundError, TouchProfileInputError, get_control_backend, get_ui_profile
from module.game import cloud
from module.game.adb_transport import AdbError
from module.game.cloud import CloudGameController, CloudGamePaidTimeExhaustedError
from module.localization import tr
from module.notification import notif
from module.ocr import ocr
from tasks.base import task_steps
from tasks.daily import daily
from tasks.game import GameStartupUnavailable
from tasks.weekly import currency_wars
from tasks.weekly.currency_wars_strategy import Slot
from tasks.weekly.currency_wars_ui import BENCH_POINTS, FRONT_Y, Frame, Label, Page
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
    scope["Daily"].currency_wars_due.return_value = False
    scope["CloudGameZeroDurationError"] = type("CloudGameZeroDurationError", (Exception,), {})
    scope.update(get_control_backend=get_control_backend, get_ui_profile=get_ui_profile,
                 AVAILABLE_TASKS=AVAILABLE_TASKS, CLI_ONLY_TASKS=CLI_ONLY_TASKS, HOST_TASKS=HOST_TASKS,
                 UNSUPPORTED_TASK=UNSUPPORTED_TASK, task_is_supported=task_is_supported, tr=tr, AdbError=AdbError,
                 ProfileAssetNotFoundError=ProfileAssetNotFoundError,
                 TouchProfileInputError=TouchProfileInputError,
                 CurrencyWarsTerminalError=currency_wars.CurrencyWarsTerminalError,
                 CurrencyWarsUnavailable=currency_wars.CurrencyWarsUnavailable,
                 GameStartupUnavailable=GameStartupUnavailable,
                 CloudGamePaidTimeExhaustedError=CloudGamePaidTimeExhaustedError)
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

    reconnect_image = image.copy()
    ImageDraw.Draw(reconnect_image).rectangle((1090, 649, 1278, 693), fill="white")
    reconnect = Frame(reconnect_image, (
        Label("提示", (959, 412)),
        Label("失去网络连接，战斗结果同步失败，是否尝试重新连接？", (956, 526)),
        Label("确认", (1188, 672)),
    ))
    disconnected = Frame(image, (Label("连接中断", (960, 480)), Label("退出游戏", (960, 600))))
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
                            fault=None, stop=False, delayed_until=None, later_steps=[], capture_failures=0,
                            reward_read_failures=0, reconnect_count=0, disconnect_reads=0,
                            capture_board=lambda: frames["board"])
    clock = SimpleNamespace(monotonic=lambda: state.now,
                            sleep=lambda seconds: setattr(state, "now", state.now + seconds))
    auto = MagicMock()

    def capture():
        if state.page == "delayed":
            state.delayed_reads += 1
            if state.fault == "unavailable":
                state.capture_failures += 1
                raise OSError("窗口持续不可用")
            if state.fault == "disconnected" or (state.fault == "brief_disconnect" and state.delayed_reads == 1):
                state.disconnect_reads += 1
                return disconnected
            resumed = state.fault == "brief_disconnect" and state.delayed_reads >= 3
            if resumed or (state.fault not in ("timeout", "stopped", "unidentified")
                           and state.now >= state.delayed_until):
                state.page = "battle"
        if state.page == "reconnect":
            return reconnect
        if state.page == "board":
            return state.capture_board()
        if state.page == "battle":
            state.battle_reads += 1
            if state.battle_reads == 3:
                state.page = "result"
        if state.page == "weekly":
            score = 18000 if state.completed else 0

            def claim_available():
                if state.fault == "weekly_read" and state.completed and not state.reward_read_failures:
                    state.reward_read_failures += 1
                    raise OSError("暂时无法读取领奖区")
                return False

            return frame(Page.WEEKLY, (f"{score}/18000", (245, 748)), claim_available=claim_available)
        return frames[state.page]

    def click(point, *, press_duration):
        state.clicks.append((state.page, point))
        if state.page == "board":
            assert point == (1818, 750)
            state.battle_reads = 0
            state.delayed_until = state.now + 28
            state.page = "battle" if state.completed else "delayed"
        elif state.page == "reconnect":
            assert point == (1188, 672)
            state.reconnect_count += 1
            state.page = "home"
        elif (state.page == "home" and point == (381, 961) and state.fault == "weekly_reconnect"
              and state.completed and not state.reconnect_count):
            state.page = "reconnect"
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
        currencywars_fast_mode=False, currencywars_bonus_enable=False, currencywars_enable=True, currencywars_timestamp=1, refresh_hour=4,
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
    monkeypatch.setattr(daily, "Date", MagicMock(wraps=daily.Date, is_next_mon_x_am=lambda *_: True))
    monkeypatch.setattr(daily.Daily, "prepare_daily", lambda: True)
    monkeypatch.setattr(daily.reward, "start", lambda: state.later_steps.append("日常领奖"))
    monkeypatch.setattr(daily.Daily, "run", lambda **_: state.later_steps.append("每日实训"))
    monkeypatch.setattr(task_steps, "screen", MagicMock())
    runner.Daily.start.side_effect = daily.Daily.start
    runner.Daily.currency_wars_due.side_effect = daily.Daily.currency_wars_due
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
def test_currency_wars_entry_continues_after_the_fight_receipt_times_out(
        runner, currency_wars_game, monkeypatch, action):
    logger = MagicMock()
    monkeypatch.setattr(currency_wars, "log", logger)
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
    round_messages = [call.args[0] for call in logger.info.call_args_list
                      if str(call.args[0]).startswith("货币战争第 ")]
    numbered_matches = 0 if action == "currencywarstemp" else expected
    assert round_messages == [f"货币战争第 {number} 局" for number in range(1, numbered_matches + 1)]
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
def test_currency_wars_entry_recovers_svarog_modification_before_preparation(
        runner, currency_wars_game, monkeypatch, action):
    state = currency_wars_game
    monkeypatch.setattr(currency_wars, "screen", MagicMock())
    preparation = state.capture_board
    episode = Frame(preparation().image, (
        Label("机心巧匠", (1046, 79)), Label("请选择1个强化效果", (1046, 141)),
        Label("反击模组", (516, 376)), Label("导弹模组", (918, 376)), Label("响指模组", (1308, 376)),
        *(Label("0", (x, 375)) for x in (815, 1212, 1609)),
        *(Label("详情", (x, 426)) for x in (650, 1046, 1444)),
        Label("确认选择", (1492, 585)),
    ))
    wrong_prices = Frame(episode.image, tuple(
        Label("1", label.point) if label.text == "0" else label for label in episode.labels
    ))
    task_auto = currency_wars.auto
    click_preparation = task_auto.click_element_with_pos.side_effect
    card_clicks = []
    confirmed = []
    opened_at = {}

    def capture_board():
        if state.completed in confirmed:
            return preparation()
        shown = opened_at.setdefault(state.completed, state.now)
        # 报价在首轮操作窗口过后才恢复，仍需在当前运行里完成改装。
        return wrong_prices if state.now - shown < 9 else episode

    def click(point, *, press_duration):
        if state.page != "board" or state.completed in confirmed:
            return click_preparation(point, press_duration=press_duration)
        assert state.now - opened_at[state.completed] >= 9
        if point == (1492, 585):
            assert state.completed in card_clicks
            confirmed.append(state.completed)
        else:
            assert any(abs(point[0] - x) < 188 for x in (650, 1046, 1444)) and 177 < point[1] < 397
            card_clicks.append(state.completed)
        return True

    state.capture_board = capture_board
    task_auto.click_element_with_pos.side_effect = click
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
    assert card_clicks == confirmed == list(range(expected))
    assert state.clicks.count(("board", (1818, 750))) == expected
    assert state.clicks.count(("rank", (1680, 965))) == (0 if action == "currencywarstemp" else expected)
    assert record["status"] == ("stopped" if action == "currencywarsloop" else "success")
    currency_wars.screen.change_to.assert_not_called()
    if action == "main":
        assert state.later_steps == ["日常领奖", "每日实训"]


@pytest.mark.parametrize("action", ("currencywars", "currencywarsloop", "currencywarstemp", "main"))
def test_currency_wars_entry_selects_two_of_four_supply_cards_after_lost_input(
        runner, currency_wars_game, action):
    state = currency_wars_game
    preparation = state.capture_board
    task_auto = currency_wars.auto
    click_preparation = task_auto.click_element_with_pos.side_effect
    centers = (428, 783, 1137, 1492)
    confirm = (1692, 984)
    image = Image.new("RGB", (1920, 1080), (153, 111, 56))
    draw = ImageDraw.Draw(image)
    for x in centers:
        draw.rectangle((x - 164, 345, x + 164, 781), fill=(39, 39, 42))
        draw.rectangle((x - 133, 293, x + 133, 595), fill=(18, 17, 19))
        draw.rectangle((x - 126, 301, x + 126, 587), fill=(86, 93, 130))
    selected = {}
    lost_inputs = set()
    confirmed = set()
    supply_clicks = []
    views = {}

    def capture_board():
        if state.completed in confirmed:
            return preparation()
        cards = frozenset(selected.setdefault(state.completed, set()))
        if cards not in views:
            view = image.copy()
            border = ImageDraw.Draw(view)
            for x in cards:
                border.line((x - 129, 778, x + 129, 778), fill="white", width=3)
            views[cards] = Frame(view, (
                Label("补给阶段", (960, 155)), Label("1-1", (470, 76)),
                Label(f"已选择{len(cards)}/2", (1692, 924)), Label("确认", confirm),
            ))
        return views[cards]

    def click(point, *, press_duration):
        match = state.completed
        if state.page != "board" or match in confirmed:
            return click_preparation(point, press_duration=press_duration)
        supply_clicks.append((match, point))
        cards = selected[match]
        if point == confirm:
            if len(cards) == 2:
                confirmed.add(match)
            return True
        x = next((x for x in centers if abs(x - point[0]) < 125 and 320 <= point[1] <= 780), None)
        if x is None:
            return False
        if len(cards) == 1 and match not in lost_inputs:
            lost_inputs.add(match)
            return False
        cards.symmetric_difference_update((x,))
        return True

    state.capture_board = capture_board
    task_auto.click_element_with_pos.side_effect = click
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
    assert state.completed == expected, record
    state.factory.assert_called_once_with()
    assert confirmed == lost_inputs == set(range(expected))
    for match in range(expected):
        first, second, retry, submitted = [point for n, point in supply_clicks if n == match]
        assert first != second and retry == second and submitted == confirm
        assert selected[match] == {first[0], second[0]}
    assert state.clicks.count(("board", (1818, 750))) == expected
    assert record["status"] == ("stopped" if action == "currencywarsloop" else "success")
    if action == "main":
        assert state.later_steps == ["日常领奖", "每日实训"]


@pytest.mark.parametrize("action", ("currencywars", "currencywarsloop", "currencywarstemp", "main"))
@pytest.mark.parametrize("restores_picture", (True, False))
def test_currency_wars_entry_rechecks_unattempted_deployment_after_picture_recovers(
        runner, currency_wars_game, monkeypatch, action, restores_picture):
    state = currency_wars_game
    task_auto = currency_wars.auto
    game_click = task_auto.click_element_with_pos.side_effect
    bench = BENCH_POINTS[0]
    front = (745, FRONT_Y)
    labels = (
        Label("备战阶段", (470, 46)), Label("1-1", (470, 79)), Label("商店", (1624, 983)),
        Label("出战", (1818, 750)), Label("前台区域", (973, 316)), Label("后台区域", (976, 575)),
        Label("0", (1640, 923)),
    )
    monkeypatch.setattr(currency_wars.cfg, "currencywars_strategy", "s2_anaxa")
    monkeypatch.setattr(Frame, "read_local", lambda *args, **kwargs: None)

    def preparation(*, deployed=False, flashing=False):
        image = Image.new("RGB", (1920, 1080), (35, 30, 74))
        draw = ImageDraw.Draw(image)
        for i in range(6):
            x = round(960 + (i - 2.5) * 142)
            draw.rectangle((x - 59, 598, x + 59, 731), outline=(78, 74, 113), width=2)
        x, y = front if deployed else bench
        draw.rectangle((x - 24, y - 23, x, y + 17), fill=(222, 180, 155))
        draw.rectangle((x + 1, y - 23, x + 24, y + 17), fill=(98, 58, 21))
        role_x = x + (44 if deployed else 36)
        draw.rectangle((role_x - 3, y - 54, role_x + 3, y - 48), fill="white")
        if flashing:
            x, y = front
            # 只在目标空格中心注入闪动。人数、来源肖像和卡框持续可辨认。
            draw.rectangle((x - 19, y - 9, x + 19, y + 9), fill=(70, 65, 109))
        return Frame(image, (*labels, Label("1/3" if deployed else "0/3", (960, 259))))

    before = preparation()
    flashing = preparation(flashing=True)
    after = preparation(deployed=True)
    detail = Frame(before.image, (*labels, Label("那刻夏", (1641, 228)), Label("前台", (1578, 278)),
                                  Label("输出", (1825, 274)), Label("能量", (1490, 364))))
    assert before.page == flashing.page == after.page == Page.BOARD and detail.page == Page.DETAIL
    assert before.slot_occupied(bench) and not before.slot_occupied(front) and not flashing.slot_occupied(front)
    assert not flashing.same_control(front, before, front)
    assert after.slot_occupied(front) and not after.slot_occupied(bench)
    capture_count = 0
    detail_open = False
    recovered = set()
    unattempted = set()
    deployed = []
    recover_default_board = currency_wars.CurrencyWars._recover_default_board

    def recover_board(war, stage, operation, error):
        if operation == "上阵" and isinstance(error, currency_wars.CurrencyWarsActionUnready):
            assert "已尝试 0 次" in str(error)
            unattempted.add(state.completed)
            if restores_picture:
                recovered.add(state.completed)
        return recover_default_board(war, stage, operation, error)

    def capture_board():
        nonlocal capture_count
        capture_count += 1
        if detail_open:
            return detail
        if state.completed in deployed:
            return after
        return before if state.completed in recovered or capture_count % 2 else flashing

    def click(point, *, press_duration):
        nonlocal detail_open
        if state.page == "board" and point in (bench, front, (12, 12)):
            assert detail_open == (point == (12, 12))
            detail_open = not detail_open
            return True
        if state.page == "board":
            assert point == (1818, 750) and state.completed in deployed
        return game_click(point, press_duration=press_duration)

    def drag(start, end, **kwargs):
        start_x, start_y = start
        end_x, end_y = end
        assert (round(start_x * 1920), round(start_y * 1080)) == bench
        assert (round(end_x * 1920), round(end_y * 1080)) == front
        assert state.completed in recovered and state.completed not in deployed
        deployed.append(state.completed)
        return True

    monkeypatch.setattr(currency_wars.CurrencyWars, "_recover_default_board", recover_board)
    monkeypatch.setattr(currency_wars, "TASK_SECONDS", 150)
    state.capture_board = capture_board
    task_auto.click_element_with_pos.side_effect = click
    task_auto.drag_mouse.side_effect = drag
    if action == "currencywarstemp":
        state.page = "board"
    if action == "currencywarsloop" and restores_picture:
        def stop_after_two(task_id, success, duration):
            assert task_id == "currencywarsloop" and success
            if state.completed == 2:
                state.stop = True

        runner.telemetry.track_task_complete.side_effect = stop_after_two

    record = run_currency_wars_cli(runner, action)

    state.factory.assert_called_once_with()
    if restores_picture:
        expected = 2 if action == "currencywarsloop" else 1
        assert state.completed == expected
        assert deployed == list(range(expected)) and recovered == unattempted == set(deployed)
        assert task_auto.drag_mouse.call_count == expected
        assert state.clicks.count(("board", (1818, 750))) == expected
        assert (record["status"], record["reason"], record["exit_code"]) == (
            ("stopped", None, EXIT_STOPPED) if action == "currencywarsloop" else ("success", None, EXIT_OK))
        if action == "main":
            assert state.later_steps == ["日常领奖", "每日实训"]
    else:
        assert unattempted == {0} and not deployed and not recovered
        task_auto.drag_mouse.assert_not_called()
        assert state.completed == 0 and state.later_steps == []
        assert ("board", (1818, 750)) not in state.clicks
        assert (record["status"], record["reason"], record["exit_code"]) == (
            "failed", "currencywars_unavailable", EXIT_FAILED)
        assert "备战" in record["error"] and state.now < currency_wars.TASK_SECONDS


@pytest.mark.parametrize("action", ("currencywars", "currencywarsloop", "currencywarstemp", "main"))
@pytest.mark.parametrize("outcome", ("recovered", "unavailable", "timeout", "stopped"))
def test_currency_wars_entry_switches_from_shaking_tea_to_chat(
        runner, currency_wars_game, monkeypatch, action, outcome):
    state = currency_wars_game
    board = state.capture_board
    image = board().image
    shake = (1534, 838)
    chat = (386, 837)
    open_reward = (960, 981)
    tea = Frame(image, (
        Label("1-8", (905, 63)), Label("返回备战界面", (1790, 65)), Label("幕后茶歇", (960, 162)),
        Label("聊一聊", chat), Label("享用茶歇", (1534, 647)),
        Label("回复20小队生命值", (1534, 782)), Label("摇一摇", shake),
    ))
    reward = Frame(image, (Label("领取茶歇奖励", (960, 195)), Label("开启", open_reward)))
    task_auto = currency_wars.auto
    game_click = task_auto.click_element_with_pos.side_effect
    tea_clicks = []
    chats_finished = set()
    rewards_opened = set()

    def capture_board():
        if state.completed in rewards_opened:
            return board()
        return reward if state.completed in chats_finished else tea

    def click(point, *, press_duration):
        if state.page != "board" or state.completed in rewards_opened:
            return game_click(point, press_duration=press_duration)
        tea_clicks.append((state.completed, point))
        if point == shake:
            if outcome == "timeout":
                state.now += currency_wars.TASK_SECONDS
            elif outcome == "stopped":
                state.stop = True
        elif point == chat and outcome == "recovered":
            chats_finished.add(state.completed)
        elif point == open_reward:
            assert state.completed in chats_finished
            rewards_opened.add(state.completed)
        else:
            assert point == chat
        return True

    assert tea.page == reward.page == Page.TEA
    state.capture_board = capture_board
    task_auto.click_element_with_pos.side_effect = click
    monkeypatch.setattr(currency_wars, "TASK_SECONDS", 150)
    if action == "currencywarstemp":
        state.page = "board"
    if action == "currencywarsloop" and outcome == "recovered":
        def stop_after_two(task_id, success, duration):
            assert task_id == "currencywarsloop" and success
            if state.completed == 2:
                state.stop = True

        runner.telemetry.track_task_complete.side_effect = stop_after_two

    record = run_currency_wars_cli(runner, action)

    state.factory.assert_called_once_with()
    if outcome == "recovered":
        expected = 2 if action == "currencywarsloop" else 1
        assert state.completed == expected
        assert rewards_opened == chats_finished == set(range(expected))
        for number in range(expected):
            clicks = [point for match, point in tea_clicks if match == number]
            assert clicks[-2:] == [chat, open_reward]
            assert len(clicks) >= 4 and set(clicks[:-2]) == {shake}
        assert state.clicks.count(("board", (1818, 750))) == expected
        assert (record["status"], record["reason"], record["exit_code"]) == (
            ("stopped", None, EXIT_STOPPED) if action == "currencywarsloop" else ("success", None, EXIT_OK))
        if action == "main":
            assert state.later_steps == ["日常领奖", "每日实训"]
        return

    assert state.completed == 0 and state.later_steps == []
    assert ("board", (1818, 750)) not in state.clicks
    if outcome == "unavailable":
        assert (0, shake) in tea_clicks and (0, chat) in tea_clicks
        assert (record["status"], record["reason"], record["exit_code"]) == (
            "failed", "currencywars_unavailable", EXIT_FAILED)
        assert "茶歇" in record["error"] and state.now < currency_wars.TASK_SECONDS
    else:
        assert tea_clicks == [(0, shake)]
        assert (record["status"], record["reason"], record["exit_code"]) == (
            ("stopped", None, EXIT_STOPPED) if outcome == "stopped" else ("failed", "currencywars_timeout", EXIT_FAILED))


def test_currency_wars_local_takeover_does_not_enter_an_unavailable_window(runner):
    runner.game.prepare_currency_wars_takeover.side_effect = GameStartupUnavailable(
        "无法切换到货币战争游戏窗口，已保留游戏现场"
    )

    record = run_currency_wars_cli(runner, "currencywarstemp")

    assert (record["status"], record["reason"], record["exit_code"]) == (
        "failed", "game_startup_unavailable", EXIT_FAILED)
    runner.game.prepare_currency_wars_takeover.assert_called_once_with()
    runner.game.switch_to_game.assert_not_called()
    runner.game.start.assert_not_called()
    runner.CurrencyWars.assert_not_called()


def test_currency_wars_loop_stops_after_repeated_unconfirmed_attempts(runner):
    war = runner.CurrencyWars.return_value
    war.result = None
    war.start.side_effect = [False, False, False, RunStopRequested]
    runner.main.__globals__["CurrencyWarsUnavailable"] = currency_wars.CurrencyWarsUnavailable

    record = run_currency_wars_cli(runner, "currencywarsloop")

    assert (record["status"], record["reason"], record["exit_code"]) == (
        "failed", "currencywars_unavailable", EXIT_FAILED)
    assert war.start.call_count == 3
    assert runner.telemetry.track_task_complete.call_count == 3


@pytest.mark.parametrize("action", ("currencywars", "currencywarsloop", "currencywarstemp", "main"))
def test_currency_wars_entry_stops_when_clear_frames_remain_unidentified(
        runner, currency_wars_game, monkeypatch, action):
    state = currency_wars_game
    unknown = Frame(Image.new("RGB", (1920, 1080)), ())
    capture = MagicMock(return_value=unknown)
    monkeypatch.setattr(currency_wars.CurrencyWars, "_capture", staticmethod(capture))
    navigation = MagicMock()
    navigation.get_current_screen.return_value = False
    monkeypatch.setattr(currency_wars, "screen", navigation)
    # 旧循环需要在一次实际运行内触发显式终止，回归时用有限时钟防止测试自身无限等待。
    normal_checkpoint = currency_wars.pause_ctl.checkpoint

    def checkpoint():
        if capture.call_count >= 32:
            raise RunStopRequested
        normal_checkpoint()

    monkeypatch.setattr(currency_wars.pause_ctl, "checkpoint", checkpoint)
    record = run_currency_wars_cli(runner, action)

    assert (record["status"], record["reason"], record["exit_code"]) == (
        "failed", "currencywars_unavailable", EXIT_FAILED)
    assert state.clicks == [] and state.completed == 0 and state.later_steps == []
    assert capture.call_count < 32
    task_steps.screen.change_to.assert_not_called()


@pytest.mark.parametrize("action", ("currencywars", "currencywarsloop", "currencywarstemp", "main"))
@pytest.mark.parametrize(("fault", "status", "reason", "exit_code"), (
    ("unavailable", "failed", "currencywars_unavailable", EXIT_FAILED),
    ("disconnected", "failed", "currencywars_unavailable", EXIT_FAILED),
    ("unidentified", "failed", "currencywars_unavailable", EXIT_FAILED),
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
    if fault == "unidentified":
        monkeypatch.setattr(currency_wars, "MATCH_UNIDENTIFIED_SECONDS", 8)
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
    if fault == "disconnected":
        assert state.disconnect_reads == currency_wars.MAX_CAPTURE_ATTEMPTS
        assert "云游戏连接" in record["error"]
    if fault == "unidentified":
        assert "对局画面持续无法识别" in record["error"]
        assert state.now < currency_wars.TASK_SECONDS


@pytest.mark.parametrize("action", ("currencywars", "currencywarsloop", "currencywarstemp", "main"))
@pytest.mark.parametrize("fault", ("brief_disconnect", "local_capacity", "node_read", "weekly_read", "weekly_reconnect"))
def test_currency_wars_entry_recovers_the_same_run(runner, currency_wars_game, monkeypatch, action, fault):
    state = currency_wars_game
    state.fault = fault
    local_reads = MagicMock(side_effect=OSError("暂时无法识别部署人数裁片"))
    if fault == "local_capacity":
        image = Image.new("RGB", (1920, 1080), (35, 30, 74))
        draw = ImageDraw.Draw(image)
        for i in range(6):
            x = round(960 + (i - 2.5) * 142)
            draw.rectangle((x - 59, 598, x + 59, 731), outline=(78, 74, 113), width=2)
        draw.rectangle((715, 382, 745, 423), fill=(220, 184, 147))
        draw.rectangle((746, 382, 770, 423), fill=(93, 60, 11))
        labels = (
            Label("备战阶段", (470, 46)), Label("1-1", (470, 79)), Label("商店", (1624, 983)),
            Label("出战", (1818, 750)), Label("前台区域", (973, 316)), Label("1/3", (960, 259)),
        )
        state.capture_board = lambda: Frame(image, labels)
        monkeypatch.setattr(ocr, "recognize_multi_lines", local_reads)
        monkeypatch.setattr(ocr, "recognize_single_line", lambda *_: None)
    if fault == "node_read":
        read_node = MagicMock(side_effect=OSError("暂时无法读取节点"))

        class UnreadableNode(Frame):
            @property
            def stage(self):
                return read_node()

        normal_board = state.capture_board()
        broken_board = UnreadableNode(normal_board.image, normal_board.labels)
        broken_board.page = Page.BOARD
        first_frame = iter((broken_board,))
        state.capture_board = lambda: next(first_frame, normal_board)
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
    assert state.clicks.count(("board", (1818, 750))) == expected
    assert state.clicks.count(("rank", (1680, 965))) == (0 if action == "currencywarstemp" else expected)
    assert state.clicks.count(("home", (381, 961))) == expected + (action == "main") + (fault == "weekly_reconnect")
    assert not any(point == (1640, 728) for _, point in state.clicks)
    assert record["status"] == ("stopped" if action == "currencywarsloop" else "success")
    assert record["error"] is None and record["reason"] is None
    assert state.disconnect_reads == (fault == "brief_disconnect")
    assert state.reward_read_failures == (fault == "weekly_read")
    assert state.reconnect_count == (fault == "weekly_reconnect")
    if fault == "local_capacity":
        assert local_reads.call_count >= 2
    if fault == "node_read":
        read_node.assert_called_once()
    if action == "main":
        assert state.later_steps == ["日常领奖", "每日实训"]
    state.factory.assert_called_once_with()
    task_steps.screen.change_to.assert_not_called()


@pytest.mark.parametrize("action", ("currencywars", "currencywarsloop", "currencywarstemp", "main"))
def test_currency_wars_records_cloud_paid_time_exhaustion(runner, currency_wars_game, monkeypatch, action):
    state = currency_wars_game
    if action == "currencywarstemp":
        state.page = "board"
    controller = object.__new__(CloudGameController)
    controller.driver = MagicMock()
    controller.driver.find_elements.return_value = [SimpleNamespace(text="星云币时长不足")]
    controller.cfg = SimpleNamespace(cloud_game_use_paid_time=True)
    controller._last_interruption_check_time = 0
    controller.logger = None
    controller.stop_game = MagicMock()
    monkeypatch.setattr(notif, "notify", MagicMock())
    normal_capture = currency_wars.CurrencyWars._capture

    def capture():
        if state.page == "delayed":
            return controller.take_screenshot()
        return normal_capture()

    monkeypatch.setattr(currency_wars.CurrencyWars, "_capture", staticmethod(capture))
    record = run_currency_wars_cli(runner, action)

    assert (record["status"], record["reason"], record["exit_code"]) == (
        "failed", "cloud_game_paid_time_exhausted", EXIT_FAILED)
    assert "云游戏付费时长已耗尽" in record["error"]
    assert state.completed == 0 and state.later_steps == []
    assert state.clicks.count(("board", (1818, 750))) == 1
    controller.stop_game.assert_called_once_with()
    notif.notify.assert_called_once()
    runner.notif.flush_batch.assert_called()
    assert not runner.main.__globals__["pause_on_error"].called


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


def test_currency_wars_respects_explicit_exit_after_a_settled_loss(runner):
    runner.cfg.control_backend = "cloud"
    runner.cfg.after_finish = "Exit"
    runner.CurrencyWars.return_value.result = False
    runner.CurrencyWars.return_value.start.return_value = False

    record = run_currency_wars_cli(runner, "currencywars")

    assert (record["status"], record["exit_code"]) == ("failed", EXIT_FAILED)
    runner.game.get_game_controller.return_value.stop_game.assert_called_once_with()
    runner.cloud_game.preserve_running_browser.assert_not_called()


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


@pytest.mark.parametrize(("fault", "expected_attempts", "exit_code", "reason"), (
    ("transient", 2, EXIT_OK, None),
    ("persistent", 3, EXIT_FAILED, "currencywars_unavailable"),
    ("stopped", 1, EXIT_STOPPED, None),
))
def test_currency_wars_takeover_retries_cloud_attach_without_restarting_browser(
        runner, fault, expected_attempts, exit_code, reason):
    from module.game.cloud import CloudGameController

    controller = object.__new__(CloudGameController)
    controller.driver = None
    controller.logger = MagicMock()
    controller._confirm_viewport_resolution = MagicMock()
    driver = MagicMock()
    driver.command_executor._client_config.timeout = 120
    driver.find_elements.side_effect = lambda by, selector: [MagicMock()] if selector == ".game-player" else []
    stopped = False

    def connect_browser(*, connect_only):
        nonlocal stopped
        assert connect_only
        if fault == "stopped":
            stopped = True
        if fault == "transient" and controller._connect_or_create_browser.call_count == 2:
            controller.driver = driver
            return
        raise OSError("CDP 暂时无法连接")

    def checkpoint():
        if stopped:
            raise RunStopRequested

    controller._connect_or_create_browser = MagicMock(side_effect=connect_browser)
    runner.cloud_game.connect_to_running_game.side_effect = controller.connect_to_running_game
    runner.cfg.control_backend = "cloud"
    runner.pause_ctl.checkpoint.side_effect = checkpoint
    runner.time.sleep = MagicMock()
    runner.main.__globals__["CurrencyWarsUnavailable"] = currency_wars.CurrencyWarsUnavailable
    runner.CurrencyWars.return_value.start.return_value = True

    record = run_currency_wars_cli(runner, "currencywarstemp")

    assert (record["exit_code"], record["reason"]) == (exit_code, reason)
    assert controller._connect_or_create_browser.call_count == expected_attempts
    assert runner.time.sleep.call_count == expected_attempts - 1
    runner.cloud_game.start_game_process.assert_not_called()
    runner.game.start.assert_not_called()
    runner.game.switch_to_game.assert_not_called()
    if fault == "transient":
        controller._confirm_viewport_resolution.assert_called_once_with()
        runner.CurrencyWars.return_value.start.assert_called_once_with(resume=True)
    else:
        runner.CurrencyWars.assert_not_called()
        if fault == "persistent":
            assert "连续无法连接正在运行的云游戏" in record["error"]
        else:
            assert record["status"] == STATUS_STOPPED


@pytest.mark.parametrize("action", ("currencywars", "currencywarsloop", "main"))
@pytest.mark.parametrize("fault", (
    "transient_disconnect", "stale_dom", "probe_timeout", "probe_timeout_no_player", "persistent_disconnect", "unavailable_frames",
    "existing_board", "different_window_mode", "transient_attach", "persistent_attach", "attach_stopped", "cold_start",
    "runtime_unavailable", "runtime_timeout", "runtime_stopped",
))
def test_currency_wars_startup_keeps_the_cloud_session(runner, currency_wars_game, monkeypatch, action, fault):
    from module import screen as screen_module
    from tasks import game
    from utils import wait

    state = currency_wars_game
    clock = SimpleNamespace(monotonic=lambda: state.now, sleep=lambda seconds: setattr(state, "now", state.now + seconds))
    monkeypatch.setattr(game, "time", clock)
    monkeypatch.setattr(wait, "time", clock)
    monkeypatch.setattr(game, "cfg", SimpleNamespace(control_backend="cloud", start_game_timeout=0.05))
    monkeypatch.setattr(game, "task_power_request", MagicMock())
    stop_control = SimpleNamespace(checkpoint=currency_wars.pause_ctl.checkpoint, check_stop=currency_wars.pause_ctl.checkpoint)
    monkeypatch.setattr(game, "pause_ctl", stop_control)
    monkeypatch.setattr(cloud, "pause_ctl", stop_control)
    screen = MagicMock()
    screen.get_current_screen.return_value = False
    monkeypatch.setattr(game, "screen", screen)
    monkeypatch.setattr(screen_module, "screen", screen)
    runner.game.start.side_effect = game.start
    runner.cfg.control_backend = "cloud"

    controller = object.__new__(CloudGameController)
    controller.driver = None
    controller.logger = MagicMock()
    controller.cfg = SimpleNamespace(
        browser_headless_enable=True, browser_type="chrome", browser_debug_port=9222,
        cloud_game_fullscreen_enable=False, browser_persistent_enable=True, browser_dump_cookies_enable=False,
        game_optimization_enable=False,
    )
    controller.user_profile_path = str(Path.cwd())
    controller._prepare_browser_and_driver = MagicMock(return_value=("chrome.exe", "chromedriver.exe"))
    controller._configure_pointer_lock = MagicMock()
    controller._confirm_viewport_resolution = MagicMock()
    controller._get_port_bind_error = MagicMock(return_value=None)
    controller._get_browser_arguments = MagicMock(return_value=[])
    controller._refresh_page = MagicMock()
    controller.enter_cloud_game = MagicMock()
    controller.stop_game = MagicMock()
    controller.close_all_m7a_browser = MagicMock()
    browser = MagicMock()
    browser_args = ["chrome.exe", "--remote-debugging-port=9225"]
    if fault != "different_window_mode":
        browser_args.append("--headless=new")
    browser.cmdline.return_value = browser_args
    controller.get_m7a_browsers = MagicMock(return_value=[] if fault == "cold_start" else [browser])
    driver = MagicMock()
    driver.command_executor._client_config.timeout = 120
    driver.service.process.poll.return_value = 0
    visible = SimpleNamespace(is_displayed=lambda: True)
    probes = []

    attach = MagicMock(return_value=driver)
    if fault == "transient_attach":
        attach.side_effect = (WebDriverException("DevTools 暂时无法连接"), driver)
    elif fault == "persistent_attach":
        attach.side_effect = WebDriverException("DevTools 持续无法连接")
    elif fault == "attach_stopped":
        def stop_after_attaching(**_):
            state.stop = True
            return driver

        attach.side_effect = stop_after_attaching
    monkeypatch.setattr(cloud.webdriver, "Chrome", attach)

    def elements(_by, selector):
        if "连接中断" in selector:
            if fault in ("transient_disconnect", "stale_dom", "probe_timeout"):
                probes.append(("disconnected", "loading", "player")[len(probes)])
            elif fault == "probe_timeout_no_player":
                probes.append("loading")
            else:
                probes.append("disconnected" if fault == "persistent_disconnect" else "player")
        disconnected = "连接中断" in selector or "退出游戏" in selector
        if fault == "stale_dom" and len(probes) == 1:
            stale_element = MagicMock()
            stale_element.is_displayed.side_effect = StaleElementReferenceException("旧节点已销毁")
            return [stale_element]
        if fault in ("probe_timeout", "probe_timeout_no_player") and len(probes) == 1:
            raise TimeoutException("播放器读取暂时超时")
        if disconnected and probes[-1] == "disconnected" or selector == ".game-player" and probes[-1] == "player":
            return [visible]
        return []

    driver.find_elements.side_effect = elements
    monkeypatch.setattr(game, "cloud_game", controller)
    runner.main.__globals__["cloud_game"] = controller
    existing_board_faults = ("existing_board", "different_window_mode", "transient_attach")
    if fault in existing_board_faults:
        state.page = "board"
        frame = Frame(Image.new("RGB", (1920, 1080)), tuple(Label(text, (x, y)) for text, x, y in (
            ("备战阶段", 472, 46), ("1-1", 472, 78), ("1/1", 960, 259), ("商店", 1624, 982), ("出战", 1818, 750),
            ("前台区域", 975, 315), ("后台区域", 963, 577),
        )))
        assert frame.page == Page.BOARD
        frame.__dict__.update(slots=lambda: (Slot("front", 0, (745, 405), True),), inventory_items=lambda: ())
        state.capture_board = lambda: frame

        def prepare_daily():
            assert state.completed == 1

        monkeypatch.setattr(daily.Daily, "prepare_daily", prepare_daily)
    if fault.startswith("runtime_"):
        state.fault = fault.removeprefix("runtime_")
        if state.fault == "timeout":
            monkeypatch.setattr(currency_wars, "TASK_SECONDS", 34)
    if fault == "unavailable_frames":
        capture = MagicMock(side_effect=OSError("截图持续不可用"))
        monkeypatch.setattr(currency_wars.CurrencyWars, "_capture", staticmethod(capture))
        screen.get_current_screen.side_effect = OSError("截图持续不可用")
    recovered = (*existing_board_faults, "transient_disconnect", "stale_dom", "probe_timeout", "cold_start")
    if action == "currencywarsloop" and fault in recovered:
        runner.telemetry.track_task_complete.side_effect = lambda *_: setattr(state, "stop", True)

    record = run_currency_wars_cli(runner, action)

    assert attach.call_count == {"transient_attach": 2, "persistent_attach": 3}.get(fault, 1)
    if fault == "cold_start":
        assert not attach.call_args.kwargs["options"].debugger_address
        assert "--remote-debugging-port=9222" in attach.call_args.kwargs["options"].arguments
        controller._refresh_page.assert_called_once_with()
    else:
        assert all(call.kwargs["options"].debugger_address == "127.0.0.1:9225" for call in attach.call_args_list)
        controller._refresh_page.assert_not_called()
    assert controller.is_headless() == (fault != "different_window_mode")
    controller.enter_cloud_game.assert_not_called()
    controller.stop_game.assert_not_called()
    controller.close_all_m7a_browser.assert_not_called()
    assert controller.driver is (None if fault == "persistent_attach" else driver)
    if fault in recovered:
        assert probes == (["player"] if fault in (*existing_board_faults, "cold_start") else ["disconnected", "loading", "player"])
        if fault in existing_board_faults:
            assert ("rank", (1680, 965)) not in state.clicks
        assert state.completed == 1
        assert record["status"] == (STATUS_STOPPED if action == "currencywarsloop" else "success")
    else:
        expected = {
            "persistent_disconnect": ("failed", "game_startup_unavailable", EXIT_FAILED),
            "probe_timeout_no_player": ("failed", "game_startup_unavailable", EXIT_FAILED),
            "persistent_attach": ("failed", "game_startup_unavailable", EXIT_FAILED),
            "attach_stopped": (STATUS_STOPPED, None, EXIT_STOPPED),
            "unavailable_frames": ("failed", "currencywars_unavailable", EXIT_FAILED),
            "runtime_unavailable": ("failed", "currencywars_unavailable", EXIT_FAILED),
            "runtime_timeout": ("failed", "currencywars_timeout", EXIT_FAILED),
            "runtime_stopped": (STATUS_STOPPED, None, EXIT_STOPPED),
        }
        assert (record["status"], record["reason"], record["exit_code"]) == expected[fault]
        if fault in ("persistent_disconnect", "probe_timeout_no_player", "unavailable_frames", "persistent_attach", "attach_stopped"):
            assert state.clicks == []
            state.factory.assert_not_called()
        else:
            assert state.clicks.count(("board", (1818, 750))) == 1
        if fault == "persistent_disconnect":
            assert probes == ["disconnected"] * 3
        elif fault == "probe_timeout_no_player":
            assert probes == ["loading"] * 3
        elif fault == "unavailable_frames":
            assert capture.call_count == currency_wars.MAX_CAPTURE_ATTEMPTS
        elif fault == "attach_stopped":
            assert probes == []
            controller._configure_pointer_lock.assert_not_called()
            controller._confirm_viewport_resolution.assert_not_called()
        controller._clean_at_exit()
        controller.close_all_m7a_browser.assert_not_called()
        assert controller.driver is None
    if fault == "unavailable_frames" and action == "main":
        screen.get_current_screen.assert_called_once_with(autotry=False, max_retries=1)
    else:
        screen.get_current_screen.assert_not_called()


@pytest.mark.parametrize("scenario, started, entries, attachments, queue_choice", (
    ("already_queued", True, 0, 1, None),
    ("already_selecting_free", True, 0, 1, 1),
    ("already_selecting_paid", True, 0, 1, 0),
    ("already_selecting_unknown_balance", True, 0, 1, 1),
    ("disconnect_into_queue", True, 0, 1, None),
    ("disconnect_then_lobby", False, 0, 1, None),
    ("disconnect_then_queue_selection", False, 0, 1, None),
    ("disconnect_queue_returns_to_lobby", False, 0, 2, None),
    ("disconnect_queue_returns_to_selection", False, 0, 2, None),
    ("lobby", True, 1, 1, None),
    ("probe_failed_after_enter", True, 1, 2, None),
    ("queued_while_locating_enter", True, 0, 1, None),
    ("player_loading", True, 0, 1, None),
    ("player_unidentified", False, 0, 1, None),
    ("queue_timeout", False, 0, 1, None),
    ("queue_timeout_after_probe_failure", False, 0, 2, None),
))
def test_cloud_startup_keeps_existing_queue_and_checks_page_before_input(
        monkeypatch, scenario, started, entries, attachments, queue_choice):
    from selenium.webdriver.support import wait as selenium_wait
    from tasks import game
    from utils import wait

    initial = {
        "already_queued": "in_queue",
        "already_selecting_free": "select_queue",
        "already_selecting_paid": "select_queue",
        "already_selecting_unknown_balance": "select_queue",
        "disconnect_into_queue": "in_queue",
        "disconnect_then_queue_selection": "select_queue",
        "disconnect_queue_returns_to_lobby": "in_queue",
        "disconnect_queue_returns_to_selection": "in_queue",
        "player_loading": None,
        "player_unidentified": None,
        "queue_timeout": "in_queue",
        "queue_timeout_after_probe_failure": "in_queue",
    }
    state = SimpleNamespace(time=0, entry=initial.get(scenario, "lobby"), entries=0, failed=False, choice=None)
    clock = SimpleNamespace(monotonic=lambda: state.time, sleep=lambda seconds: setattr(state, "time", state.time + seconds))
    for module in (game, cloud, wait, selenium_wait):
        monkeypatch.setattr(module, "time", clock)

    def current_state():
        if scenario.startswith("queue_timeout"):
            return state.entry
        if (scenario == "player_loading" and state.time >= 1
                or state.entry == "in_queue" and state.time >= 45):
            return "game_running"
        return state.entry

    driver = MagicMock()
    driver.command_executor._client_config.timeout = 120
    visible = SimpleNamespace(is_displayed=lambda: True)

    def find_elements(_by, selector):
        current = current_state()
        if (scenario.startswith("disconnect") and state.time == 0
                and ("连接中断" in selector or "退出游戏" in selector)):
            return [visible]
        if selector == ".game-player" and current == "game_running":
            return [visible]
        if "div.user-aid.wel-card__aid" in selector and current == "lobby":
            return [visible]
        return []

    def find_enter_button(_by, selector):
        assert selector == "div.wel-card__content--start" and current_state() == "lobby"
        if scenario == "queued_while_locating_enter":
            state.entry = "in_queue"
        return visible

    def execute(script, *args):
        current = current_state()
        if 'return "select_queue"' in script:
            injected_fault = (scenario == "probe_failed_after_enter" and state.entry == "in_queue"
                              or scenario == "queue_timeout_after_probe_failure" and state.time >= 55)
            if injected_fault and not state.failed:
                state.failed = True
                raise WebDriverException("排队状态读取暂时失败")
            if current == "in_queue" and scenario.startswith("disconnect_queue_returns_to"):
                state.entry = "lobby" if scenario.endswith("lobby") else "select_queue"
            return current
        if script == "arguments[0].click();":
            assert current == "lobby"
            state.entries += 1
            state.entry = "in_queue"
        elif "coin-prior-choose-item-include-info" in script:
            assert current == "select_queue"
            state.choice, = args
            state.entry = "in_queue"
        elif "game-player__video" in script:
            return current == "game_running"

    driver.find_elements.side_effect = find_elements
    driver.find_element.side_effect = find_enter_button
    driver.execute_script.side_effect = execute
    driver.service.process.poll.return_value = 0

    controller = object.__new__(CloudGameController)
    controller.driver = None
    controller.logger = MagicMock()
    controller.cfg = SimpleNamespace(
        browser_headless_enable=True, browser_headless_restart_on_not_logged_in=True, browser_dump_cookies_enable=False,
        cloud_game_max_queue_time=1,
        cloud_game_use_paid_time=scenario in ("already_selecting_paid", "already_selecting_unknown_balance"),
    )
    controller._get_remaining_playtime = MagicMock(
        return_value=(None, None) if scenario == "already_selecting_unknown_balance" else (10, 50)
    )
    controller._confirm_viewport_resolution = MagicMock()
    controller._restart_browser = MagicMock()
    controller.stop_game = MagicMock()
    controller.try_dump_page = MagicMock()

    def connect_browser(**_):
        controller.driver = driver
        return True

    controller._connect_or_create_browser = MagicMock(side_effect=connect_browser)
    monkeypatch.setattr(game, "cloud_game", controller)
    monkeypatch.setattr(game, "cfg", SimpleNamespace(control_backend="cloud", start_game_timeout=1))
    click = MagicMock(return_value=True)
    monkeypatch.setattr(game, "auto", SimpleNamespace(click_element=click))
    ready = MagicMock(return_value=True)

    if started:
        game.start_game(screen_ready=ready)
        ready.assert_called_once_with()
    else:
        if scenario.startswith("queue_timeout"):
            message = "排队已达到等待时限"
        elif scenario.startswith("disconnect"):
            message = "云游戏断开后暂未确认播放器或原排队状态"
        else:
            message = "暂未确认云游戏播放器"
        with pytest.raises(GameStartupUnavailable, match=message):
            game.start_game(screen_ready=ready)
        ready.assert_not_called()
        if scenario.startswith("queue_timeout"):
            assert state.time == 60

    assert controller._connect_or_create_browser.call_count == attachments
    assert all(call.kwargs == {"headless": True, "preserve_existing": True}
               for call in controller._connect_or_create_browser.call_args_list)
    assert state.entries == entries
    assert state.choice == queue_choice
    assert click.call_count == (1 if started and scenario != "player_loading" else 0)
    controller.stop_game.assert_not_called()
    controller._restart_browser.assert_not_called()


@pytest.mark.parametrize("action", ("currencywars", "currencywarsloop"))
@pytest.mark.parametrize("title_page", ("start_game", "click_enter"))
def test_currency_wars_enters_from_an_existing_game_title(
        runner, currency_wars_game, monkeypatch, action, title_page):
    from tasks import game
    from utils import wait

    state = currency_wars_game
    state.page = title_page
    clock = currency_wars.time
    screen_module = import_module("module.screen.screen")
    auto = currency_wars.auto
    navigator = object.__new__(screen_module.Screen)
    screen_module.Screen.__init__(navigator, Path("assets/config/screens.json"), MagicMock())
    navigator.current_screen = title_page
    navigator._handle_autotry = MagicMock()
    capture = currency_wars.CurrencyWars._capture
    unknown = Frame(Image.new("RGB", (1920, 1080)), ())

    def capture_title():
        if state.page in (title_page, "click_enter", "main", "menu", "guide5"):
            return unknown
        return capture()

    def find_image(path, *_args, **_kwargs):
        screen_id = "currency_wars_homepage" if state.page == "home" else state.page
        asset = navigator.screen_map.get(screen_id, {}).get("image_path")
        return 1.0 if path == asset else None

    title_inputs = []
    transitions = {
        ("start_game", "./assets/images/screen/start_game.png"): "click_enter",
        ("click_enter", "./assets/images/screen/click_enter.png"): "main",
        ("main", "esc"): "menu",
        ("menu", "./assets/images/share/menu/guide.png"): "menu",
        ("menu", "./assets/images/screen/guide/enter_guide5.png"): "guide5",
        ("guide5", "货币战争"): "guide5",
        ("guide5", "前往参与"): "home",
    }

    def navigate(target, *_args, **_kwargs):
        title_inputs.append((state.page, target))
        state.page = transitions[state.page, target]
        return True

    press = auto.press_key.side_effect
    auto.press_key.side_effect = lambda key: navigate(key) if state.page == "main" else press(key)
    auto.click_element.side_effect = navigate
    monkeypatch.setattr(navigator, "_find_image", find_image)
    monkeypatch.setattr(currency_wars.CurrencyWars, "_capture", staticmethod(capture_title))
    monkeypatch.setattr(currency_wars, "screen", navigator)
    monkeypatch.setattr(game, "screen", navigator)
    monkeypatch.setattr(screen_module, "auto", auto)
    for module in (game, screen_module, wait):
        monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(game, "cfg", SimpleNamespace(control_backend="local", start_game_timeout=1,
                                                      auto_set_game_path_enable=False))
    monkeypatch.setattr(game, "task_power_request", MagicMock())
    monkeypatch.setattr(game, "auto", auto)
    controller = MagicMock(launch_method="direct")
    controller.switch_to_game.return_value = True
    controller.get_resolution.return_value = (1920, 1080)
    monkeypatch.setattr(game, "StarRailController", MagicMock(return_value=controller))
    runner.game.start.side_effect = game.start
    if action == "currencywarsloop":
        runner.telemetry.track_task_complete.side_effect = lambda *_: setattr(state, "stop", True)

    record = run_currency_wars_cli(runner, action)

    assert record["status"] == (STATUS_STOPPED if action == "currencywarsloop" else "success")
    assert state.completed == 1
    assert [page for page, _ in title_inputs] == (
        ["start_game"] * (title_page == "start_game") + ["click_enter", "main", "menu", "menu", "guide5", "guide5"]
    )
    assert title_inputs[0][1].endswith(f"/{title_page}.png")
    navigator._handle_autotry.assert_not_called()
    controller.start_game_process.assert_not_called()
    controller.stop_game.assert_not_called()


@pytest.mark.parametrize("action", ("currencywars", "currencywarsloop", "currencywarstemp", "main"))
@pytest.mark.parametrize("outcome", ("recovers", "unavailable", "stopped"))
def test_currency_wars_background_waits_for_the_existing_game_window(
        runner, currency_wars_game, monkeypatch, action, outcome):
    from module.automation import background_input
    from tasks import game
    from utils import wait

    state = currency_wars_game
    state.page = "board"
    clock = currency_wars.time
    for module in (game, background_input, wait):
        monkeypatch.setattr(module, "time", clock)
    controller = MagicMock(launch_method="direct", process_name="StarRail.exe")
    controller.get_resolution.return_value = (1920, 1080)
    windows = MagicMock()
    windows.return_value.process_running.return_value = True

    def window_ready():
        return outcome == "recovers" and state.now >= 2

    controller.is_game_running.side_effect = window_ready
    controller.switch_to_game.side_effect = window_ready
    monkeypatch.setattr(game, "StarRailController", MagicMock(return_value=controller))
    monkeypatch.setattr(game, "WindowsInputApi", windows)
    monkeypatch.setattr(game, "process_session_id", lambda: 4)
    monkeypatch.setattr(game, "cfg", SimpleNamespace(control_backend="local", start_game_timeout=.1,
                                                      auto_set_game_path_enable=False))
    monkeypatch.setattr(game, "task_power_request", MagicMock())

    def checkpoint():
        if outcome == "stopped" and state.now >= .5:
            state.stop = True
        currency_wars.pause_ctl.checkpoint()

    control = SimpleNamespace(checkpoint=checkpoint, check_stop=checkpoint)
    monkeypatch.setattr(game, "pause_ctl", control)
    handler = object.__new__(background_input.BackgroundInput)
    handler.logger = MagicMock()
    handler._window_wait_expired = False
    handler._release_quietly = MagicMock()
    handler._pause = control
    handler.window_problem = lambda: None if window_ready() else background_input.WINDOW_MISSING
    handler.wait_for_window = MagicMock(wraps=handler.wait_for_window)
    auto = currency_wars.auto
    auto.input_handler = handler
    monkeypatch.setattr(game, "auto", auto)
    runner.game.start.side_effect = game.start
    runner.game.prepare_currency_wars_takeover.side_effect = game.prepare_currency_wars_takeover
    if action == "currencywarsloop" and outcome == "recovers":
        runner.telemetry.track_task_complete.side_effect = lambda *_: setattr(state, "stop", True)
    if action == "main":
        monkeypatch.setattr(daily.Daily, "prepare_daily", lambda: state.completed == 1)

    record = run_currency_wars_cli(runner, action)

    handler.wait_for_window.assert_called_once_with(
        game.WINDOW_WAIT_SECONDS if action == "currencywarstemp" else 6
    )
    if outcome == "recovers":
        assert record["status"] == (STATUS_STOPPED if action == "currencywarsloop" else "success"), record
        assert state.completed == 1
        assert ("rank", (1680, 965)) not in state.clicks
    else:
        assert (record["status"], record["reason"]) == (
            (STATUS_STOPPED, None) if outcome == "stopped" else ("failed", "game_startup_unavailable")
        )
        assert state.clicks == []
        state.factory.assert_not_called()
    if action != "currencywarstemp":
        windows.return_value.process_running.assert_called_with("StarRail.exe", session_id=4)
    controller.start_game_process.assert_not_called()
    controller.stop_game.assert_not_called()
    auto.click_element.assert_not_called()
    auto.press_mouse.assert_not_called()


def bind_currency_wars_local_startup(runner, state, monkeypatch, action):
    from tasks import game
    from utils import wait

    clock = currency_wars.time
    monkeypatch.setattr(game, "time", clock)
    monkeypatch.setattr(wait, "time", clock)
    monkeypatch.setattr(game, "cfg", SimpleNamespace(control_backend="local", start_game_timeout=.2,
                                                      auto_set_game_path_enable=False))
    monkeypatch.setattr(game, "task_power_request", MagicMock())
    checkpoint = currency_wars.pause_ctl.checkpoint
    monkeypatch.setattr(game, "pause_ctl", SimpleNamespace(checkpoint=checkpoint, check_stop=checkpoint))
    monkeypatch.setattr(game, "auto", currency_wars.auto)
    controller = MagicMock(launch_method="direct")
    controller.is_game_running.return_value = True
    controller.switch_to_game.return_value = True
    controller.get_resolution.return_value = (1920, 1080)
    monkeypatch.setattr(game, "StarRailController", MagicMock(return_value=controller))
    runner.game.start.side_effect = game.start
    if action == "currencywarsloop":
        runner.telemetry.track_task_complete.side_effect = lambda *_: setattr(state, "stop", True)
    if action == "main":
        monkeypatch.setattr(daily.Daily, "prepare_daily", lambda: state.completed == 1)
    return game, controller


@pytest.mark.parametrize("action", ("currencywars", "currencywarsloop", "main"))
@pytest.mark.parametrize("outcome", ("missing_once", "read_error_once", "bad_size", "unavailable", "stopped"))
def test_currency_wars_startup_rechecks_resolution_without_closing_the_window(
        runner, currency_wars_game, monkeypatch, action, outcome):
    from module.game.base import GameControllerBase

    state = currency_wars_game
    state.page = "board"
    _, controller = bind_currency_wars_local_startup(runner, state, monkeypatch, action)
    controller.get_window_handle.return_value = 12
    if outcome == "missing_once":
        controller.get_window_handle.side_effect = [0, 12]
    get_rect = MagicMock(return_value=(0, 0, 1920, 1080))
    if outcome == "read_error_once":
        get_rect.side_effect = [OSError("窗口尺寸读取失败"), (0, 0, 1920, 1080)]
    elif outcome == "bad_size":
        get_rect.return_value = (0, 0, 1600, 900)
    elif outcome == "unavailable":
        get_rect.side_effect = OSError("窗口尺寸读取失败")
    elif outcome == "stopped":
        def stop_during_read(_):
            state.stop = True
            return 0, 0, 0, 0

        get_rect.side_effect = stop_during_read
    monkeypatch.setitem(sys.modules, "win32gui", SimpleNamespace(GetClientRect=get_rect))
    controller.get_resolution.side_effect = lambda: GameControllerBase.get_resolution(controller)

    record = run_currency_wars_cli(runner, action)

    controller.start_game_process.assert_not_called()
    controller.stop_game.assert_not_called()
    if outcome in ("missing_once", "read_error_once"):
        assert record["status"] == (STATUS_STOPPED if action == "currencywarsloop" else "success"), record
        assert state.completed == 1
        assert state.clicks[0] == ("board", (1818, 750))
        assert controller.get_resolution.call_count == 2
    else:
        assert state.clicks == []
        state.factory.assert_not_called()
        if outcome == "stopped":
            assert (record["status"], record["exit_code"]) == (STATUS_STOPPED, EXIT_STOPPED)
            assert controller.get_resolution.call_count == 1
        else:
            assert record["reason"] == "game_startup_unavailable"
            assert "已保留游戏现场" in record["error"]
            assert ("1600x900" if outcome == "bad_size" else "持续无法读取游戏窗口分辨率") in record["error"]
            assert controller.get_resolution.call_count > 1


@pytest.mark.parametrize("action", ("currencywars", "currencywarsloop", "main"))
@pytest.mark.parametrize("prompt", (
    "account_and_password", "os", "missing_credentials", "password_only", "cold_login_pending",
    "opening_capture_error", "os_opening_capture_error", "opening_capture_unavailable",
    "after_account_capture_error", "stopped_before_credentials",
))
def test_currency_wars_startup_uses_saved_credentials_only_on_a_confirmed_login_prompt(
        runner, currency_wars_game, monkeypatch, action, prompt):
    state = currency_wars_game
    state.page = "native_login"
    game, controller = bind_currency_wars_local_startup(runner, state, monkeypatch, action)
    game.cfg.start_game_timeout = .5
    auto = currency_wars.auto
    clock = currency_wars.time
    screen_module = import_module("module.screen.screen")
    monkeypatch.setattr(screen_module, "auto", auto)
    monkeypatch.setattr(screen_module, "time", clock)
    navigator = object.__new__(screen_module.Screen)
    screen_module.Screen.__init__(navigator, Path("assets/config/screens.json"), MagicMock())
    monkeypatch.setattr(game, "screen", navigator)
    original_capture = currency_wars.CurrencyWars._capture
    unrecognized_page = Frame(Image.new("RGB", (1920, 1080)), ())
    monkeypatch.setattr(currency_wars.CurrencyWars, "_capture", staticmethod(
        lambda: unrecognized_page if state.page == "native_login" else original_capture()
    ))
    templates = {
        "account_and_password": {"account_and_password"},
        "os": {"account_field_os", "password_field"},
        "missing_credentials": {"account_and_password"},
        "password_only": {"password_field"},
        "cold_login_pending": {"account_and_password"},
        "opening_capture_error": {"account_and_password"},
        "os_opening_capture_error": {"account_field_os", "password_field"},
        "opening_capture_unavailable": {"account_and_password"},
        "after_account_capture_error": {"account_and_password"},
        "stopped_before_credentials": {"account_and_password"},
    }[prompt]
    find_point = auto.find_element.side_effect
    opening_attempts = []
    verified_prompts = []
    verified_frames = []

    def find(target, *args, **kwargs):
        if not isinstance(target, str):
            return find_point(target, *args, **kwargs)
        asset = Path(target).stem
        if asset == "welcome":
            return state.page == "home"
        matched = state.page == "native_login" and asset in templates
        if matched and asset in ("account_and_password", "account_field_os"):
            verified_prompts.append(asset)
            verified_frames.append(auto.take_screenshot.call_count)
        return matched

    def click_login(target, *args, **kwargs):
        assert state.page == "native_login"
        asset = Path(target).stem
        if asset in ("account_and_password", "account_field_os"):
            opening_attempts.append(asset)
            if prompt == "stopped_before_credentials":
                state.stop = True
                raise RuntimeError("登录截图超时")
            if (prompt == "opening_capture_unavailable" or
                    prompt in ("opening_capture_error", "os_opening_capture_error") and len(opening_attempts) == 1):
                raise RuntimeError("登录截图超时")
        if prompt == "after_account_capture_error" and asset == "password_field":
            raise RuntimeError("登录截图超时")
        if asset == "enter_game" and prompt != "cold_login_pending":
            state.page = "home"
        return asset in ("account_and_password", "account_field", "account_field_os", "password_field",
                         "agree_conditions", "enter_game")

    auto.find_element.side_effect = find
    auto.click_element.side_effect = click_login
    credentials = (None, None) if prompt == "missing_credentials" else ("local_test", "mock_password")
    monkeypatch.setattr(game, "load_acc_and_pwd", MagicMock(return_value=credentials))
    monkeypatch.setattr(game, "gamereg_uid", lambda: 1)
    monkeypatch.setattr(game, "ensure_IME_lang_en", MagicMock())
    monkeypatch.setattr(navigator, "_handle_autotry", MagicMock())
    if prompt == "cold_login_pending":
        game.cfg.start_game_timeout = 1.5
        controller.is_game_running.side_effect = lambda: controller.start_game_process.called
        controller.switch_to_game.side_effect = [False, True, True]
        windows = MagicMock()
        windows.return_value.process_running.return_value = False
        monkeypatch.setattr(game, "WindowsInputApi", windows)
        monkeypatch.setattr(game, "process_session_id", lambda: 4)
        monkeypatch.setattr(game, "game_option_enabled", lambda *_: False)
        monkeypatch.setattr(game, "restore_temporary_graphics", MagicMock())

    record = run_currency_wars_cli(runner, action)

    assert all(previous < current for previous, current in zip(verified_frames, verified_frames[1:]))
    navigator._handle_autotry.assert_not_called()
    controller.stop_game.assert_not_called()
    assert controller.start_game_process.call_count == (1 if prompt == "cold_login_pending" else 0)
    if prompt in ("account_and_password", "os", "opening_capture_error", "os_opening_capture_error"):
        assert record["status"] == (STATUS_STOPPED if action == "currencywarsloop" else "success"), record
        assert state.completed == 1
        assert [call.args[0] for call in auto.secretly_write.call_args_list] == list(credentials)
        assert verified_prompts == opening_attempts
        assert len(opening_attempts) == (2 if prompt.endswith("capture_error") else 1)
    elif prompt == "cold_login_pending":
        assert record["reason"] == "game_startup_unavailable"
        assert "尝试自动登录失败" in record["error"]
        assert [call.args[0] for call in auto.secretly_write.call_args_list] == list(credentials)
        assert opening_attempts == ["account_and_password"]
    elif prompt in ("opening_capture_unavailable", "after_account_capture_error", "stopped_before_credentials"):
        assert verified_prompts == opening_attempts
        assert len(opening_attempts) == (3 if prompt == "opening_capture_unavailable" else 1)
        assert state.clicks == []
        if prompt == "stopped_before_credentials":
            assert (record["status"], record["exit_code"]) == (STATUS_STOPPED, EXIT_STOPPED)
        else:
            assert record["reason"] == "game_startup_unavailable"
            assert "登录截图超时" in record["error"]
        if prompt == "after_account_capture_error":
            auto.secretly_write.assert_called_once_with(credentials[0], interval=0.1)
        else:
            auto.secretly_write.assert_not_called()
    else:
        assert record["reason"] == "game_startup_unavailable"
        assert state.clicks == []
        auto.click_element.assert_not_called()
        auto.secretly_write.assert_not_called()
        if prompt == "password_only":
            game.load_acc_and_pwd.assert_not_called()
        else:
            game.load_acc_and_pwd.assert_called_once_with(1)
            assert "未找到保存的登录凭据" in record["error"]


@pytest.mark.parametrize(("recognized", "current_screen", "can_continue"), (
    (True, "main", True),
    (True, "menu", True),
    (True, "currency_wars_homepage", False),
    (False, "main", False),
))
def test_full_run_uses_a_known_game_screen_when_currency_wars_prefilter_cannot_read(
        runner, currency_wars_game, monkeypatch, recognized, current_screen, can_continue):
    from module import screen as screen_module
    from tasks import game
    from utils import wait

    state = currency_wars_game
    clock = SimpleNamespace(monotonic=lambda: state.now, sleep=lambda n: setattr(state, "now", state.now + n))
    monkeypatch.setattr(game, "time", clock)
    monkeypatch.setattr(wait, "time", clock)
    monkeypatch.setattr(game, "task_power_request", MagicMock())
    monkeypatch.setattr(game, "cfg", SimpleNamespace(control_backend="cloud", start_game_timeout=0.08))
    screen = MagicMock()
    screen.get_current_screen.return_value = recognized
    screen.current_screen = current_screen
    monkeypatch.setattr(game, "screen", screen)
    monkeypatch.setattr(screen_module, "screen", screen)
    runner.cfg.control_backend = "cloud"
    runner.game.start.side_effect = game.start
    runner.cloud_game.start_game_process.return_value = True
    runner.cloud_game.is_in_game.return_value = True
    monkeypatch.setattr(game, "cloud_game", runner.cloud_game)
    state.factory.game_screen_ready = MagicMock(side_effect=currency_wars.CurrencyWarsUnavailable("专用画面 OCR 暂不可用"))
    runner.Daily.start.side_effect = None
    runner.Daily.start.return_value = True

    record = run_currency_wars_cli(runner, "main")

    if can_continue:
        assert record["status"] == "success"
        screen.get_current_screen.assert_called_once_with(autotry=False, max_retries=1)
        runner.Daily.start.assert_called_once_with()
    else:
        assert record["reason"] == "currencywars_unavailable"
        runner.Daily.start.assert_not_called()
    runner.cloud_game.stop_game.assert_not_called()


@pytest.mark.parametrize("dialog", ("reward_limit", "weekly_receipt", "generic_receipt"))
def test_full_run_checks_the_context_of_existing_reward_dialog(runner, currency_wars_game, monkeypatch, dialog):
    from tasks import game
    from utils import wait

    state = currency_wars_game
    clock = SimpleNamespace(monotonic=lambda: state.now, sleep=lambda n: setattr(state, "now", state.now + n))
    monkeypatch.setattr(game, "time", clock)
    monkeypatch.setattr(wait, "time", clock)
    monkeypatch.setattr(game, "task_power_request", MagicMock())
    monkeypatch.setattr(game, "cfg", SimpleNamespace(control_backend="cloud", start_game_timeout=0.08))
    screen = MagicMock()
    screen.get_current_screen.return_value = False
    monkeypatch.setattr(game, "screen", screen)
    runner.cfg.control_backend = "cloud"
    runner.game.start.side_effect = game.start
    runner.cloud_game.start_game_process.return_value = True
    runner.cloud_game.is_in_game.return_value = True
    monkeypatch.setattr(game, "cloud_game", runner.cloud_game)

    image = Image.new("RGB", (1920, 1080))
    if dialog == "reward_limit":
        ImageDraw.Draw(image).rectangle((823, 694, 1097, 754), fill="white")
        point = (960, 724)
        frame = Frame(image, (Label("背包内助燃券持有数量已达上限", (960, 486)), Label("确认", point)))
        assert frame.page == Page.REWARD_LIMIT
    else:
        point = (964, 851)
        labels = [Label("获得奖励", (960, 281)), Label("点击空白处关闭", point)]
        if dialog == "weekly_receipt":
            labels.append(Label("积分奖励", (151, 338)))
        frame = Frame(image, tuple(labels))
        assert frame.page == Page.REWARD_RECEIPT
    capture = currency_wars.CurrencyWars._capture
    click = currency_wars.auto.click_element_with_pos.side_effect
    pressed = []

    def click_or_close(target, *, press_duration):
        if pressed:
            return click(target, press_duration=press_duration)
        assert target == point
        pressed.append(target)

    monkeypatch.setattr(currency_wars.CurrencyWars, "_capture", staticmethod(lambda: capture() if pressed else frame))
    currency_wars.auto.click_element_with_pos.side_effect = click_or_close
    record = run_currency_wars_cli(runner, "main")

    runner.cloud_game.enter_cloud_game.assert_not_called()
    runner.cloud_game.stop_game.assert_not_called()
    if dialog == "generic_receipt":
        assert record["reason"] == "game_startup_unavailable"
        assert pressed == []
        state.factory.assert_not_called()
        assert all(call.kwargs == {"autotry": False, "max_retries": 1} for call in screen.get_current_screen.call_args_list)
    else:
        assert record["status"] == "success"
        assert pressed == [point]
        assert state.completed == 1
        screen.get_current_screen.assert_not_called()


@pytest.mark.parametrize("action", ("currencywars", "currencywarsloop", "currencywarstemp", "main"))
def test_currency_wars_stop_during_cdp_drag_releases_at_the_current_position(
        runner, currency_wars_game, monkeypatch, action):
    from module.automation import cdp_input
    from module.automation.automation import Automation
    from utils import pause

    state = currency_wars_game
    runner.cfg.control_backend = "cloud"
    stop_control = pause.PauseController()
    stop_control._enabled = True
    stop_control._resume_event.set()
    monkeypatch.setattr(currency_wars, "pause_ctl", stop_control)
    monkeypatch.setattr(cdp_input, "pause_ctl", stop_control)
    if action == "currencywarstemp":
        state.page = "board"
        runner.cloud_game.connect_to_running_game.return_value = True

    dispatched = []

    def send(_command, event):
        dispatched.append((event["type"], event["x"], event["y"], stop_control.stop_requested))
        if event["type"] == "mousePressed":
            stop_control.request_stop()

    backend = cdp_input.CdpInput(SimpleNamespace(execute_cdp_cmd=send), MagicMock())
    automation = object.__new__(Automation)
    automation.screenshot = Image.new("RGB", (1920, 1080))
    automation.screenshot_pos = (0, 0, 1920, 1080)
    automation.screenshot_scale_factor = 1
    automation.take_screenshot = MagicMock(return_value=True)
    automation.mouse_drag = backend.mouse_drag
    currency_wars.auto.drag_mouse.side_effect = automation.drag_mouse
    monkeypatch.setattr(currency_wars.CurrencyWars, "_prepare", lambda self, frame: self._drag(frame, (750, 400), (900, 400)))

    record = run_currency_wars_cli(runner, action)

    assert (record["status"], record["reason"], record["exit_code"]) == (STATUS_STOPPED, None, EXIT_STOPPED)
    assert dispatched == [("mouseMoved", 750, 400, False), ("mousePressed", 750, 400, False),
                          ("mouseReleased", 750, 400, True)]
    assert state.completed == 0 and state.later_steps == []
