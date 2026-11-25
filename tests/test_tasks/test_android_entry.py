"""Android 入口脚本里不需要设备的部分：入口对照、设置校验、步骤和进度回报。"""
import ast
import importlib
import importlib.util
import inspect
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image
from ruamel.yaml import YAML

import module.game
import module.game.adb_ready
import module.game.adb_transport
import module.localization
import module.ocr
from module.config import cfg
from module.game.adb import AdbGameController
from module.game.adb_ready import wait_for_game as wait_for_game_frames
from module.logger import log
from tasks.touch import power, rewards


ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "Android" / "app" / "src" / "main" / "python" / "android_task.py"

# 与 test_cloud_task_mode.py 断言的 Windows 触屏入口相同。
WINDOWS_TARGETS = {
    "daily": "tasks.touch.rewards.run_daily_training",
    "routine": "tasks.touch.rewards.routine",
    "power": "tasks.touch.power.run_standalone",
}
APP_TASKS = {"ROUTINE": "routine", "DAILY": "daily", "POWER": "power"}
# 界面契约里设置对照表的 30 个键。
SETTING_KEYS = {
    "power_enable", "power_plan", "power_plan_keep", "power_plan_continue", "instance_type", "instance_names",
    "use_reserved_trailblaze_power", "use_fuel", "instance_team_enable", "instance_team_number", "instance_teams",
    "borrow_enable", "borrow_character_enable", "borrow_friends", "borrow_scroll_times", "echo_of_war_enable",
    "echo_of_war_start_day_of_week", "tp_before_instance", "relic_bag_cleanup_enable",
    "instance_names_challenge_count", "auto_battle_detect_enable", "reward_enable", "reward_dispatch_enable",
    "reward_mail_enable", "reward_assist_enable", "reward_quest_enable", "reward_srpass_enable",
    "reward_message_enable", "daily_enable", "daily_material_enable",
}


@pytest.fixture(scope="module")
def entry():
    # 入口脚本的模块级只导入标准库，按路径加载即可。
    spec = importlib.util.spec_from_file_location("android_task_under_test", ENTRY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main_touch_actions():
    """读出 main.py 里 touch_actions 的写法，例如 {"daily": "rewards.run_daily_training"}。"""
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(target, "id", None) == "touch_actions" for target in node.targets):
            return {key.value: f"{value.value.id}.{value.attr}" for key, value in zip(node.value.keys, node.value.values)}
    raise AssertionError("main.py 里没有 touch_actions")


def payload(**changes):
    values = dict.fromkeys(SETTING_KEYS, False)
    values.update(changes)
    return json.dumps(values, ensure_ascii=False)


def test_targets_are_the_windows_touch_entries(entry):
    targets = {APP_TASKS[task]: ".".join(target) for task, target in entry.TASK_TARGETS.items()}
    assert targets == WINDOWS_TARGETS
    assert {task: path.removeprefix("tasks.touch.") for task, path in targets.items()} == main_touch_actions()
    for module_name, name in entry.TASK_TARGETS.values():
        assert "on_summary" in inspect.signature(getattr(importlib.import_module(module_name), name)).parameters
    assert "on_step" in inspect.signature(rewards.routine).parameters


def test_single_steps_use_the_routine_step_names(entry):
    assert entry.SINGLE_STEPS.keys() == entry.TASK_TARGETS.keys() - {"ROUTINE"}
    source = inspect.getsource(rewards.routine)
    for name in entry.SINGLE_STEPS.values():
        assert f'("{name}"' in source


def test_setting_keys_match_the_contract_and_exist_in_the_template(entry):
    assert entry.SETTING_KEYS == SETTING_KEYS
    assert len(SETTING_KEYS) == 30
    template = YAML(typ="safe").load((ROOT / "assets" / "config" / "config.example.yaml").read_text(encoding="utf-8"))
    assert SETTING_KEYS <= template.keys()
    assert entry.FIXED_SETTINGS.keys() <= template.keys()
    assert not SETTING_KEYS & entry.FIXED_SETTINGS.keys()


def test_build_settings_adds_the_fixed_values(entry):
    plan = [["拟造花萼（金）", "回忆之蕾", 1]]
    settings = entry.build_settings(payload(power_plan=plan, instance_team_number="6"))

    assert settings.keys() == SETTING_KEYS | entry.FIXED_SETTINGS.keys()
    assert settings["power_plan"] == plan
    assert settings["instance_team_number"] == "6"
    assert {key: settings[key] for key in entry.FIXED_SETTINGS} == entry.FIXED_SETTINGS


@pytest.mark.parametrize(("change", "key"), [("drop", "use_fuel"), ("add", "control_backend"), ("add", "power_waves")])
def test_build_settings_rejects_missing_or_extra_keys(entry, change, key):
    values = dict.fromkeys(SETTING_KEYS, False)
    if change == "drop":
        del values[key]
    else:
        values[key] = "local"
    with pytest.raises(ValueError, match=key):
        entry.build_settings(json.dumps(values))
    with pytest.raises(ValueError):
        entry.build_settings("[]")


class Bridge:
    """记下 Python 调到 Kotlin 的方法。"""

    def __init__(self, cancelled=False):
        self.cancelled = cancelled
        self.calls = []
        self.steps = []
        self.summary = None
        self.progress = None

    def isCancelled(self):
        return self.cancelled

    def log(self, time_ms, level, category, message, heading):
        self.calls.append(("log", level, message))

    def reportStep(self, name, state, detail):
        self.steps.append((name, state, detail))

    def reportSummary(self, text):
        self.summary = text

    def reportProgress(self, text):
        self.calls.append(("progress",))
        self.progress = json.loads(text)

    def openDevice(self):
        return 23333

    def cleaning(self):
        self.calls.append(("cleaning",))

    def __getattr__(self, name):
        # displayReady、gameEvent、gameReady、panelChanged 只记调用。
        return lambda *args: self.calls.append((name, *args))


def record(level, message, **extra):
    item = logging.LogRecord("test", level, __file__, 0, message, None, None)
    item.__dict__.update(extra)
    return item


def test_task_log_keeps_the_reason_instead_of_the_generic_step_line(entry):
    bridge = Bridge()
    handler = entry._TaskLog(bridge)

    handler.begin_step("日常领奖")
    handler.emit(record(logging.ERROR, "邮件失败：未确认邮箱附件状态"))
    handler.emit(record(logging.ERROR, "日常领奖未完成"))
    assert handler.last_error == "邮件失败：未确认邮箱附件状态"
    handler.begin_step("每日实训")
    assert handler.last_error is None
    handler.emit(record(logging.INFO, "=== 开始 ===", section_title="开始触屏每日实训"))
    assert handler.last_error is None
    assert bridge.calls[-1] == ("log", "INFO", "开始触屏每日实训")


@pytest.fixture
def device(monkeypatch, entry):
    """替换设备、OCR 和配置文件，只跑入口脚本自己的流程。"""
    values = {"start_game_timeout": 3, "power_plan": [], "last_run_timestamp": 0, "echo_of_war_timestamp": 0}
    monkeypatch.setattr(cfg, "config", values)
    monkeypatch.setattr(cfg, "set_values", values.update)
    # 替换过的配置绝不能落盘，否则会覆盖开发者自己的 config.yaml。
    monkeypatch.setattr(cfg, "save_config", Mock(side_effect=AssertionError("测试不应写入配置文件")))
    monkeypatch.setattr(module.localization, "load_language", Mock())
    monkeypatch.setattr(module.ocr, "ocr", Mock())
    monkeypatch.setattr(entry, "_ocr_parameters", Mock(return_value={}))
    controller = Mock()
    controller.prepare_display.return_value = 65
    monkeypatch.setattr(module.game, "get_game_controller", Mock(return_value=controller))
    monkeypatch.setattr(module.game.adb_ready, "wait_for_game", Mock())
    client = Mock(closed=True)
    client.hello = {"features": ["keep_awake"]}
    client.request.return_value = ({"original_mode": "allowed"}, None)
    monkeypatch.setattr(module.game.adb_transport, "ServiceClient", Mock(return_value=client))
    monkeypatch.setattr(module.game.adb_transport, "check_service_hello", Mock())
    monkeypatch.setenv("MARCH7TH_NON_INTERACTIVE", "1")
    monkeypatch.chdir(ROOT)
    return values


def start(entry, task, bridge, **settings):
    return entry.run(str(ROOT), "token", 29, "10", "Redmi", False, task, payload(**settings),
                     False, True, "zh_CN", bridge)


@pytest.mark.parametrize("support", ["supported", "missing", "failed"])
def test_keep_awake_is_requested_before_launch_only_if_supported(entry, device, monkeypatch, support):
    client = module.game.adb_transport.ServiceClient.return_value
    controller = module.game.get_game_controller.return_value
    client.hello = {"features": []} if support == "missing" else {"features": ["keep_awake"]}
    request = Mock()

    def respond(command, **params):
        request(command, **params)
        if command == "keep_awake":
            controller.prepare_display.assert_called_once_with()
            if support == "failed":
                raise module.game.adb_transport.AdbError("unsupported", "无法保持唤醒")
        return {"original_mode": "allowed"}, None

    client.request.side_effect = respond

    def check_before_launch(*, recover_startup):
        assert recover_startup
        calls = [call for call in request.call_args_list if call.args == ("keep_awake",)]
        assert [call.kwargs for call in calls] == ([] if support == "missing" else [{"on": True}])

    controller.start_game_process.side_effect = check_before_launch
    monkeypatch.setattr(rewards, "run_daily_training", Mock(return_value=True))
    bridge = Bridge()

    assert start(entry, "DAILY", bridge) == "success"
    controller.start_game_process.assert_called_once_with(recover_startup=True)
    warnings = [call[2] for call in bridge.calls if call[:2] == ("log", "WARNING")]
    assert warnings == {
        "supported": [],
        "missing": ["设备端服务不支持保持系统唤醒"],
        "failed": ["未能保持系统唤醒：无法保持唤醒"],
    }[support]


@pytest.mark.parametrize("disconnect", [False, True])
def test_mute_warning_allows_start_and_cleans_up_when_the_socket_survives(entry, device, monkeypatch, disconnect):
    client = module.game.adb_transport.ServiceClient.return_value
    controller = module.game.get_game_controller.return_value
    bridge = Bridge()
    client.closed = False
    client.close.side_effect = lambda: setattr(client, "closed", True)
    controller.close.side_effect = lambda: controller.attach_virtual_session.call_args.args[1].close()

    def respond(command, **params):
        if command == "mute" and params["on"]:
            raise module.game.adb_transport.AdbError("unsupported", "device rejected mute")
        return {"original_mode": "allow"}, None

    client.request.side_effect = respond

    def launch(*, recover_startup):
        assert recover_startup
        if disconnect:
            client.closed = True
            raise module.game.adb_transport.disconnected("watchdog/receive, EOFError")

    controller.start_game_process.side_effect = launch
    run_task = Mock(return_value=True)
    monkeypatch.setattr(rewards, "run_daily_training", run_task)

    assert start(entry, "DAILY", bridge) == ("disconnected" if disconnect else "success")
    assert ("log", "WARNING", "未能设置游戏静音：device rejected mute") in bridge.calls
    assert run_task.call_count == (0 if disconnect else 1)
    recovery_states = [args[1] for args in bridge.calls if args[0] == "audioRecoveryPending"]
    assert recovery_states == ([True] if disconnect else [True, False])
    if disconnect:
        assert any(call[:2] == ("log", "ERROR") and "watchdog/receive, EOFError" in call[2]
                   for call in bridge.calls)
    else:
        assert [call.args[0] for call in client.request.call_args_list][-2:] == ["mute", "shutdown"]


@pytest.mark.parametrize(("scenario", "outcome", "retry_requests"), [
    ("recovers", "success", 1),
    ("task_reappears", "success", 1),
    ("dies_again", "game_exited", 1),
    ("stale_observation", "game_start_timeout", 0),
    ("stopped", "stopped", 0),
    ("cold", "success", 0),
])
def test_app_startup_recovers_only_after_confirmed_task_loss(entry, device, monkeypatch, scenario, outcome, retry_requests):
    from module.game import adb as adb_backend
    from module.game import adb_ready

    now = 200.0

    def sleep(seconds):
        nonlocal now
        now += seconds

    clock = SimpleNamespace(monotonic=lambda: now, sleep=sleep)
    monkeypatch.setattr(adb_backend, "time", clock)
    monkeypatch.setattr(adb_ready, "time", clock)
    monkeypatch.setattr(entry, "time", SimpleNamespace(monotonic=clock.monotonic, time=lambda: now))
    monkeypatch.setattr(adb_ready, "wait_for_game", wait_for_game_frames)
    monkeypatch.setattr(adb_ready, "_load_template", lambda name: name)
    monkeypatch.setattr(adb_ready, "_match", lambda image, name, template: (1, 1) if name == "main" else None)
    controller = AdbGameController(SimpleNamespace(ui_profile="touch_720", adb_tap_ms=None), logger=log)
    monkeypatch.setattr(controller, "_capture_virtual", lambda pixels, fresh: (9, object()))
    monkeypatch.setattr(module.game, "get_game_controller", lambda backend: controller)

    bridge = Bridge()
    client = module.game.adb_transport.ServiceClient.return_value
    client.closed = False
    client.close.side_effect = lambda: setattr(client, "closed", True)
    events = []
    missing_since = None

    def event(name, **fields):
        events.append(dict(event=name, event_seq=len(events) + 1, **fields))

    def respond(command, **params):
        nonlocal missing_since
        if command == "create_display":
            return {"display_id": 65}, None
        if command == "watchdog":
            event("watchdog_started", task=None if scenario == "cold" else {"display_id": 0})
        if command == "launch":
            sleep(2)
            if scenario == "cold":
                event("task_display_changed", to=65)
            else:
                if scenario == "dies_again":
                    event("game_exited", pid=17)
                event("task_display_changed", to=None)
        if command == "status":
            if missing_since is None:
                missing_since = now
            if scenario == "stopped" and now - missing_since >= 1:
                bridge.cancelled = True
            checked = 200000 if scenario == "stale_observation" else round(now * 1000)
            return {"watchdog": {"task": None, "task_checked_ms": checked,
                                 "interactive": True, "keyguard_locked": False}}, None
        if command == "launch_if_missing":
            assert now - missing_since >= 1
            assert params["display_id"] == 65 and not params["wait"]
            event("task_display_changed", to=65)
            if scenario == "dies_again":
                missing_since = None
                event("task_display_changed", to=None)
            return {"launched": scenario != "task_reappears", "seq": 8}, None
        if command == "events":
            return {"events": events[params["after"]:], "event_seq": len(events)}, None
        return {"original_mode": "allowed"}, None

    client.request.side_effect = respond
    task = Mock(return_value=True)
    monkeypatch.setattr(rewards, "run_daily_training", task)
    assert start(entry, "DAILY", bridge) == outcome
    commands = [call.args[0] for call in client.request.call_args_list]
    assert commands.count("launch") == 1
    assert commands.count("launch_if_missing") == retry_requests
    assert commands[-1] == "shutdown" and commands.count("shutdown") == 1
    assert task.call_count == (outcome == "success")
    assert ("cleaning",) in bridge.calls
    if scenario == "stale_observation":
        assert 380 <= now < 381
    elif scenario == "dies_again":
        assert now < 210


@pytest.fixture(scope="module")
def monthly_startup_frames():
    root = ROOT / "assets" / "touch_720" / "images" / "screen"
    positions = {
        "monthly_card": (575, 48),
        "monthly_card_claim": (691, 338),
        "monthly_card_reward": (606, 316),
        "monthly_card_prompt": (561, 673),
        "main": (14, 48),
    }
    with_title = ("monthly_card", "monthly_card_prompt")
    scenes = {
        "unrelated": ("monthly_card_reward",),
        "claim": (*with_title, "monthly_card_claim"),
        "animation": with_title,
        "reward": (*with_title, "monthly_card_reward"),
        "main": ("main",),
    }
    frames = {}
    for scene, templates in scenes.items():
        frame = Image.new("RGB", (1280, 720))
        for name in templates:
            with Image.open(root / f"{name}.png") as template:
                frame.paste(template, positions[name])
        frames[scene] = frame.tobytes()
    return frames


@pytest.mark.parametrize(("scenario", "expected"), [
    ("black", "virtual_display_black"), ("no_first_frame", "frame_timeout"),
    ("cached_black", "frame_timeout"), ("issue_stall", "frame_timeout"),
    ("slow_new_frames", "virtual_display_black"), ("missing_evidence", "virtual_display_black"),
    ("short_black", "success"), ("late_receipt", "success"), ("sdk_loading", "success"),
    ("content_between_black", "success"), ("snapshot_error", "success"), ("sample_error", "success"),
    ("unavailable_capture", "game_start_timeout"),
    ("manual_login", "manual_action_required"), ("locked_then_ready", "success"),
    ("task_moved", "success"), ("stale_watchdog", "game_start_timeout"),
    ("static_text", "game_start_timeout"), ("no_snapshot", "game_start_timeout"),
    ("old_service", "game_start_timeout"), ("old_service_ready", "success"),
    ("game_exited", "game_exited"), ("stop", "stopped"),
])
def test_virtual_display_startup_health(entry, device, monkeypatch, monthly_startup_frames, scenario, expected):
    from module.game import adb, adb_ready

    started = 200.0
    now = started

    def sleep(seconds):
        nonlocal now
        now += seconds

    clock = SimpleNamespace(monotonic=lambda: now, sleep=sleep, time=lambda: now)
    for owner in (adb, adb_ready, entry):
        monkeypatch.setattr(owner, "time", clock)
    monkeypatch.setattr(adb_ready, "wait_for_game", wait_for_game_frames)
    controller = AdbGameController(SimpleNamespace(ui_profile="touch_720", adb_tap_ms=None), logger=log)
    monkeypatch.setattr(module.game, "get_game_controller", lambda backend: controller)
    bridge = Bridge()
    task = Mock(return_value=True)
    monkeypatch.setattr(rewards, "run_daily_training", task)
    client = module.game.adb_transport.ServiceClient.return_value
    legacy = scenario in ("old_service", "old_service_ready")
    client.hello = {"features": ["keep_awake"] + ([] if legacy else ["startup_snapshot"])}
    client.closed = False
    client.close.side_effect = lambda: setattr(client, "closed", True)
    events = []
    commands = []
    last_seq = 0
    last_image_at = None
    black = bytes(1280 * 720 * 3)
    # 一个极小的亮点也可能是静止 SDK 页的文字。缩略图可能完全漏掉它。
    static = bytearray(black)
    static[3:6] = b'\xff\xff\xff'
    main = monthly_startup_frames["main"]
    watch_task = dict(task_id=355, stack_id=355, display_id=65, visible=True,
                      top_activity="com.miHoYo.hkrpg/com.mihoyo.combosdk.ComboSDKActivity")

    def emit(name, **fields):
        events.append(dict(event=name, event_seq=len(events) + 1, **fields))

    def respond(command, **params):
        nonlocal last_seq, last_image_at
        elapsed = now - started
        commands.append(command)
        if command == "create_display":
            return {"display_id": 65}, None
        if command == "launch":
            emit("task_display_changed", to=65)
        off_target = scenario == "task_moved" and 25 <= elapsed < 55
        locked = scenario == "locked_then_ready" and 25 <= elapsed < 55
        sdk = scenario in ("sdk_loading", "manual_login") and 5 <= elapsed < 20
        if command == "events":
            if len(events) == 1 and (off_target or sdk):
                emit("task_display_changed" if off_target else "sdk_window_shown", to=0)
            if len(events) == 2 and scenario == "manual_login" and elapsed >= 15:
                emit("manual_action_required")
            if len(events) == 2 and scenario in ("task_moved", "sdk_loading") and not (off_target or sdk):
                emit("task_display_changed" if scenario == "task_moved" else "sdk_window_gone", to=65)
            if scenario == "game_exited" and elapsed >= 15 and len(events) == 1:
                emit("task_display_changed", to=None)
                emit("game_exited", pid=123)
            result = {"events": events[params["after"]:], "event_seq": len(events)}
            if params.get("startup") and not legacy and scenario != "no_snapshot":
                if scenario == "snapshot_error":
                    raise module.game.adb_transport.AdbError("internal", "设备诊断不可用")
                checked = int(now * 1000) if scenario != "stale_watchdog" else int(started * 1000)
                result["startup"] = {
                    "device_ms": int(now * 1000), "display_id": 65,
                    "watchdog": {"task": dict(watch_task, display_id=0 if off_target else 65),
                                 "pid": 123, "target_display_id": 65, "task_checked_ms": checked,
                                 "interactive": not locked, "keyguard_locked": locked,
                                 "sdk_window": "sdk/Login" if sdk else None},
                    "frame": {"seq": last_seq, "capturing": True,
                              "age_ms": -1 if last_image_at is None else round((now - last_image_at) * 1000)},
                }
            return result, None
        if command == "startup_evidence" and scenario == "missing_evidence":
            raise module.game.adb_transport.AdbError("unsupported", "ROM 无此诊断")
        if command == "status":
            return {"watchdog": {"task": None, "task_checked_ms": int(now * 1000),
                                 "interactive": True, "keyguard_locked": False}}, None
        if command == "launch_if_missing":
            if scenario == "game_exited":
                emit("game_exited", pid=124)
            return {"launched": True, "seq": last_seq}, None
        if command == "frame":
            sleep(.65)
            if scenario == "stop" and elapsed >= 15:
                bridge.cancelled = True
            if scenario == "no_first_frame" or (scenario == "late_receipt" and 12 <= elapsed < 24):
                raise module.game.adb_transport.AdbError("timeout", "暂时无新帧")
            frozen = scenario in ("cached_black", "static_text") or (scenario == "issue_stall" and 10 <= elapsed < 113)
            if scenario == "slow_new_frames" and last_image_at is not None:
                frozen = now - last_image_at < 8
            if not frozen or last_image_at is None:
                last_seq += 1
                last_image_at = now
            if scenario == "unavailable_capture":
                raise module.game.adb_transport.AdbError("timeout", "输入后的截图不可用，生产端仍在出帧")
            ready_at = {"short_black": 22, "late_receipt": 32, "sdk_loading": 25, "old_service_ready": 25,
                        "content_between_black": 64, "snapshot_error": 59, "sample_error": 59,
                        "task_moved": 62, "locked_then_ready": 62}.get(scenario, 999)
            visible = scenario == "static_text" or (scenario == "content_between_black" and 26 <= elapsed <= 36)
            pixels = main if elapsed >= ready_at else static if visible else black
            return {"seq": last_seq, "display_id": 65, "crop": params["crop"], "encoding": "rgb"}, pixels
        return {"original_mode": "allowed"}, None

    if scenario == "sample_error":
        monkeypatch.setattr(Image.Image, "getextrema", Mock(side_effect=ValueError("像素统计不可用")))
    client.request.side_effect = respond
    assert start(entry, "DAILY", bridge) == expected
    assert task.call_count == int(expected == "success")
    assert not {"tap", "focus", "touch", "swipe"}.intersection(commands)
    assert commands.count("launch") == 1 and commands.count("shutdown") == 1
    if expected in {"frame_timeout", "virtual_display_black"}:
        assert 30 <= now - started < 80
        assert commands.count("startup_evidence") == 1
    elif expected == "game_start_timeout":
        assert 180 <= now - started < 182
    if legacy:
        assert all(not call.kwargs.get("startup") for call in client.request.call_args_list)


@pytest.mark.parametrize(("scenario", "outcome", "expected"), [
    ("animated", "success", ["claim", "reward"]),
    ("late_receipt", "success", ["claim", "reward"]),
    ("retry", "success", ["claim", "claim", "reward"]),
    ("already_claimed", "success", ["reward"]),
    ("blocked", "game_start_timeout", ["claim", "claim"]),
    ("deadline", "game_start_timeout", []),
    ("stopped", "stopped", []),
])
def test_app_handles_monthly_card_before_running(
    entry, device, monkeypatch, monthly_startup_frames, scenario, outcome, expected,
):
    from module.game import adb, adb_ready

    now = 200.0

    def sleep(seconds):
        nonlocal now
        now += seconds

    clock = SimpleNamespace(monotonic=lambda: now, sleep=sleep, time=lambda: now)
    for clock_owner in (adb, adb_ready, entry):
        monkeypatch.setattr(clock_owner, "time", clock)
    monkeypatch.setattr(adb_ready, "wait_for_game", wait_for_game_frames)
    device["start_game_timeout"] = 12 / 60
    controller = AdbGameController(SimpleNamespace(ui_profile="touch_720", adb_tap_ms=None), logger=log)
    monkeypatch.setattr(module.game, "get_game_controller", lambda backend: controller)
    bridge = Bridge()
    client = module.game.adb_transport.ServiceClient.return_value
    client.closed = False
    client.close.side_effect = lambda: setattr(client, "closed", True)

    if scenario in {"deadline", "stopped"}:
        inputs = controller.get_input_handler()
        click = inputs.mouse_click
        display_available = controller._display_available

        def check_display():
            if scenario == "deadline":
                sleep(12)
            else:
                bridge.cancelled = True
            return display_available()

        def click_after_check(x, y):
            with monkeypatch.context() as patch:
                patch.setattr(controller, "_display_available", check_display)
                return click(x, y)

        monkeypatch.setattr(inputs, "mouse_click", click_after_check)

    taps = []
    events = []
    seq = 0
    claimed_at = None
    receipt_delay = 6.0 if scenario == "late_receipt" else 3.5
    scene = None
    closed = False

    def respond(command, **params):
        nonlocal seq, scene, claimed_at, closed
        if command == "create_display":
            return {"display_id": 65}, None
        if command == "launch":
            events.append({"event": "task_display_changed", "to": 65, "event_seq": 1})
        if command == "events":
            return {"events": events[params["after"]:], "event_seq": len(events)}, None
        if command == "frame":
            seq += 1
            if seq == 1:
                scene = "unrelated"
            elif closed:
                scene = "main"
            elif scenario == "already_claimed" or (claimed_at is not None and now - claimed_at >= receipt_delay):
                scene = "reward"
            elif claimed_at is None or now - claimed_at < 1.5:
                scene = "claim"
            else:
                scene = "animation"
                if seq % 2 == 0:
                    raise module.game.adb_transport.AdbError("timeout", "测试漏帧")
            return {
                "seq": seq, "display_id": 65, "crop": params["crop"], "encoding": "rgb",
                "timestamp_comparable": True, "image_ns": round(now * 1e9) + 1,
            }, monthly_startup_frames[scene]
        if command == "tap":
            assert (params["x"], params["y"]) == (641, 687)
            taps.append(scene)
            if scene == "claim":
                if scenario == "blocked" or (scenario == "retry" and len(taps) == 1):
                    return {"delivered": False}, None
                claimed_at = now
            elif scene == "reward":
                closed = True
            return {"delivered": True, "input_ns": round(now * 1e9)}, None
        return {"original_mode": "allowed"}, None

    client.request.side_effect = respond
    task = Mock(return_value=True)
    monkeypatch.setattr(rewards, "run_daily_training", task)
    assert start(entry, "DAILY", bridge) == outcome
    assert taps == expected
    assert task.call_count == (outcome == "success")
    assert any(call[0] == "gameReady" for call in bridge.calls) == (outcome == "success")


@pytest.mark.parametrize("instance_override", [False, True])
def test_progress_is_reported_at_each_write_and_the_setter_is_restored(entry, device, monkeypatch, instance_override):
    def set_value(key, value):
        device[key] = value

    if instance_override:
        monkeypatch.setitem(vars(cfg), "set_value", set_value)
    else:
        monkeypatch.delitem(vars(cfg), "set_value", raising=False)
        monkeypatch.setattr(type(cfg), "set_value", lambda self, key, value: set_value(key, value))
    original = cfg.set_value
    bridge = Bridge()
    remaining = [["拟造花萼（金）", "以太之蕾", 1]]

    def run(*, on_summary):
        assert bridge.progress is None
        cfg.set_value("unrelated", True)
        assert bridge.progress is None
        for key, value in (
            ("power_plan", remaining), ("last_run_timestamp", 1762900000.5), ("echo_of_war_timestamp", 1762900100),
        ):
            cfg.set_value(key, value)
            assert bridge.progress[key] == value
        assert bridge.calls.count(("progress",)) == 3
        return True

    monkeypatch.setattr(power, "run_standalone", run)

    assert start(entry, "POWER", bridge, power_plan=[["拟造花萼（金）", "回忆之蕾", 1], *remaining]) == "success"
    assert bridge.calls.count(("progress",)) == 4
    assert cfg.set_value == original
    assert ("set_value" in vars(cfg)) == instance_override


def test_routine_reports_each_step_with_its_reason_and_returns_the_progress(entry, device, monkeypatch):
    def routine(*, on_summary, on_step):
        on_step("清体力", "started", None)
        device["power_plan"] = []
        device["last_run_timestamp"] = 1762900000.5
        on_step("清体力", "succeeded", "已完成 1 次挑战")
        on_step("日常领奖", "started", None)
        log.error("邮件失败：未确认邮箱附件状态")
        log.error("日常领奖未完成")
        on_step("日常领奖", "failed", None)
        on_summary("已完成 1 次挑战")
        return False

    monkeypatch.setattr(rewards, "routine", routine)
    bridge = Bridge()

    assert start(entry, "ROUTINE", bridge, power_plan=[["拟造花萼（金）", "回忆之蕾", 1]]) == "task_failed"
    assert bridge.steps == [
        ("清体力", "started", None), ("清体力", "succeeded", "已完成 1 次挑战"),
        ("日常领奖", "started", None), ("日常领奖", "failed", "邮件失败：未确认邮箱附件状态"),
    ]
    assert bridge.summary is None
    assert bridge.progress == {"power_plan": [], "last_run_timestamp": 1762900000.5, "echo_of_war_timestamp": 0}
    # 进度在清理之前交回，固定配置也已写入。
    assert bridge.calls.index(("progress",)) < bridge.calls.index(("cleaning",))
    assert device["control_backend"] == "adb" and device["power_enable"] is False


@pytest.mark.parametrize(("task", "target", "result"), [
    ("DAILY", (rewards, "run_daily_training"), True),
    ("POWER", (power, "run_standalone"), True),
    ("POWER", (power, "run_standalone"), False),
])
def test_single_tasks_report_one_step_around_the_windows_entry(entry, device, monkeypatch, task, target, result):
    def run(*, on_summary):
        if result:
            on_summary("每日实训活跃度 500/500")
        else:
            log.error("触屏清体力：未能确认当前开拓力")
        return result

    monkeypatch.setattr(*target, run)
    bridge = Bridge()

    assert start(entry, task, bridge) == ("success" if result else "task_failed")
    name = entry.SINGLE_STEPS[task]
    detail = "每日实训活跃度 500/500" if result else "触屏清体力：未能确认当前开拓力"
    assert bridge.steps == [(name, "started", None), (name, "succeeded" if result else "failed", detail)]
    assert bridge.summary == (detail if result else None)


def test_android_entry_exports_debug_and_traceback_and_restores_log_levels(entry, device, monkeypatch):
    from PIL import Image
    from module.game import adb_ready
    from module.ocr.ocr import OCR
    from tasks.base.task_steps import GameRecoveryError

    original_level = log.logger.level
    original_handlers = tuple(log.logger.handlers)
    handler_levels = [handler.level for handler in original_handlers]

    monkeypatch.setattr(adb_ready.ImageUtils, "scale_and_match_template", lambda *_: (0.45, (0, 0)))

    def fail(*, on_summary):
        adb_ready._match(Image.new("RGB", (1280, 720)), "menu", None)
        OCR.log_results(SimpleNamespace(logger=log), [{"txt": "委托"}])
        raise GameRecoveryError("委托失败后无法回到可操作界面")

    monkeypatch.setattr(rewards, "run_daily_training", fail)
    bridge = Bridge()

    assert start(entry, "DAILY", bridge) == "runtime_error"
    diagnostics = [call[2] for call in bridge.calls if call[:2] == ("log", "DEBUG")]
    assert len(diagnostics) == 1
    assert "ADB 启动模板 menu" in diagnostics[0] and "相似度=0.450 阈值=0.90" in diagnostics[0]
    assert "OCR识别结果: ['委托']" in diagnostics[0]
    assert any(call[:2] == ("log", "ERROR") and "Traceback (most recent call last):" in call[2]
               for call in bridge.calls)
    assert log.logger.level == original_level
    assert tuple(log.logger.handlers) == original_handlers
    assert [handler.level for handler in log.logger.handlers] == handler_levels


def test_config_write_warning_reaches_the_app_and_allows_the_task_to_continue(entry, device, monkeypatch):
    from module.overview.readings import save_reading

    continued = Mock()

    def task(*, on_summary):
        config = SimpleNamespace(set_value=Mock(side_effect=OSError("配置暂时不可写")))
        save_reading(config, "overview_power", 120)
        continued()
        return True

    monkeypatch.setattr(rewards, "run_daily_training", task)
    bridge = Bridge()

    assert start(entry, "DAILY", bridge) == "success"
    continued.assert_called_once_with()
    assert bridge.steps == [("每日实训", "started", None), ("每日实训", "succeeded", None)]
    warnings = [call[2] for call in bridge.calls if call[:2] == ("log", "WARNING")]
    assert len(warnings) == 1
    assert "无法保存总览读数 overview_power，本次任务继续" in warnings[0]
    assert "OSError: 配置暂时不可写" in warnings[0]
    assert not any(call[:2] == ("log", "ERROR") for call in bridge.calls)


def test_settings_that_do_not_match_report_no_progress(entry, device):
    bridge = Bridge()
    assert entry.run(str(ROOT), "token", 29, "10", "Redmi", False, "DAILY", "{}", False, True, "zh_CN", bridge) == "runtime_error"
    assert bridge.progress is None
    assert ("cleaning",) in bridge.calls


def test_stop_before_the_task_keeps_the_progress_report(entry, device, monkeypatch):
    from utils.pause import RunStopRequested

    def stopped(*, on_summary):
        raise RunStopRequested()

    monkeypatch.setattr(rewards, "run_daily_training", stopped)
    bridge = Bridge()
    assert start(entry, "DAILY", bridge) == "stopped"
    assert bridge.steps == [("每日实训", "started", None)]
    assert bridge.progress is not None
