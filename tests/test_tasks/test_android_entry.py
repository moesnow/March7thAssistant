"""Android 入口脚本里不需要设备的部分：入口对照、设置校验、步骤和进度回报。"""
import ast
from functools import reduce
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
import module.game.adb_frame_health
import module.game.adb_transport
import module.localization
import module.ocr
from module.config import cfg
from module.game.adb import AdbGameController
from module.game.adb_ready import wait_for_game as wait_for_game_frames
from module.logger import log
from tasks.daily.redemption import Redemption
from tasks.touch import power, rewards
from utils.color import green, red, yellow


ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "Android" / "app" / "src" / "main" / "python" / "android_task.py"

# 与 test_cloud_task_mode.py 断言的 Windows 触屏入口相同。
WINDOWS_TARGETS = {
    "daily": "tasks.touch.rewards.run_daily_training",
    "routine": "tasks.touch.rewards.routine",
    "power": "tasks.touch.power.run_standalone",
}
# 兑换码沿用 Windows 的 main.py redemption 子任务。
WINDOWS_REDEEM = "tasks.daily.redemption.Redemption.start"
APP_TASKS = {"ROUTINE": "routine", "DAILY": "daily", "POWER": "power", "REDEEM": "redemption"}
# 界面契约里设置对照表的 37 个键。
SETTING_KEYS = {
    "power_enable", "power_plan", "power_plan_keep", "power_plan_continue", "instance_type", "instance_names",
    "use_reserved_trailblaze_power", "use_fuel", "build_target_enable", "build_target_scheme",
    "build_target_ornament_weekly_count", "build_target_use_user_instance_when_only_erosion_and_ornament",
    "instance_team_enable", "instance_team_number", "instance_teams",
    "borrow_enable", "borrow_character_enable", "borrow_friends", "borrow_scroll_times", "echo_of_war_enable",
    "echo_of_war_start_day_of_week", "tp_before_instance", "relic_bag_cleanup_enable",
    "instance_names_challenge_count", "auto_battle_detect_enable", "reward_enable", "reward_dispatch_enable",
    "reward_mail_enable", "reward_assist_enable", "reward_quest_enable", "reward_srpass_enable",
    "reward_redemption_code_enable", "reward_message_enable", "redemption_code", "already_used_codes",
    "daily_enable", "daily_material_enable",
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


def main_sub_task(action):
    """读出 main.py 里 sub_tasks 对某个子任务的写法，例如 "Redemption.start"。"""
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(target, "id", None) == "sub_tasks" for target in node.targets):
            for key, value in zip(node.value.keys, node.value.values):
                if getattr(key, "value", None) == action:
                    return ast.unparse(value)
    raise AssertionError(f"main.py 的 sub_tasks 里没有 {action}")


def payload(**changes):
    values = dict.fromkeys(SETTING_KEYS, False)
    values.update(changes)
    return json.dumps(values, ensure_ascii=False)


def test_targets_are_the_windows_entries(entry):
    targets = {APP_TASKS[task]: ".".join(target) for task, target in entry.TASK_TARGETS.items()}
    assert targets.pop("redemption") == WINDOWS_REDEEM
    assert WINDOWS_REDEEM.endswith("." + main_sub_task("redemption"))
    assert targets == WINDOWS_TARGETS
    assert {task: path.removeprefix("tasks.touch.") for task, path in targets.items()} == main_touch_actions()
    for module_name, name in entry.TASK_TARGETS.values():
        target = reduce(getattr, name.split("."), importlib.import_module(module_name))
        assert "on_summary" in inspect.signature(target).parameters
    assert "on_step" in inspect.signature(rewards.routine).parameters


def test_single_steps_use_the_routine_step_names(entry):
    from module.overview.plan import STEP_NAMES

    assert entry.SINGLE_STEPS.keys() == entry.TASK_TARGETS.keys() - {"ROUTINE"}
    assert set(entry.SINGLE_STEPS.values()) <= set(STEP_NAMES.values())


def test_setting_keys_match_the_contract_and_exist_in_the_template(entry):
    assert entry.SETTING_KEYS == SETTING_KEYS
    assert len(SETTING_KEYS) == 37
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
    handler.emit(record(logging.ERROR, f"邮件失败：{red('未确认邮箱附件状态')}"))
    handler.emit(record(logging.ERROR, "日常领奖未完成"))
    assert handler.last_error == "邮件失败：未确认邮箱附件状态"
    handler.begin_step("每日实训")
    assert handler.last_error is None
    handler.emit(record(logging.INFO, "=== 开始 ===", section_title=green("开始触屏每日实训")))
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
    for owner in (adb, adb_ready, module.game.adb_frame_health, entry):
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


@pytest.mark.parametrize(("scenario", "outcome", "requests", "gestures"), [
    ("normal", "success", 0, 0), ("short_black", "success", 0, 0),
    ("short_stall", "success", 0, 0), ("sdk_loading", "success", 0, 0),
    ("locked", "success", 0, 0), ("frame_read_error", "success", 0, 0),
    ("snapshot_read_error", "success", 0, 0),
    ("black_recovers", "success", 1, 1), ("stalled_recovers", "success", 1, 1),
    ("api32_black_recovers", "success", 1, 1),
    ("api32_stalled_recovers", "success", 1, 1),
    ("no_first_recovers", "success", 1, 1), ("late_receipt", "success", 1, 1),
    ("injection_denied", "inject_denied", 1, 1),
    ("cancel_denied", "inject_denied", 1, 1),
    ("persistent_black", "virtual_display_black", 1, 1), ("persistent_stall", "frame_timeout", 1, 1),
    ("picture_resumed_during_evidence", "success", 1, 0),
    ("recovery_unavailable", "virtual_display_black", 1, 0),
    ("focus_game", "virtual_display_black", 1, 0), ("focus_other", "virtual_display_black", 1, 0),
    ("focus_unknown", "virtual_display_black", 1, 0),
    ("stop_before_request", "stopped", 0, 0), ("stop_during_recovery", "stopped", 1, 0),
    ("deadline_before_recovery", "game_start_timeout", 0, 0),
    ("deadline_during_recovery", "game_start_timeout", 1, 0),
    ("old_service", "virtual_display_black", 0, 0),
    ("api30", "virtual_display_black", 0, 0), ("api33", "virtual_display_black", 0, 0),
    ("api34", "virtual_display_black", 0, 0),
    ("emulator31", "success", 1, 1),
    ("emulator32", "success", 1, 1),
    ("emulator_cached_loading", "success", 1, 1),
    ("process_unknown", "game_start_timeout", 0, 0),
    ("valid_dark_loading", "game_start_timeout", 0, 0), ("stale_watchdog", "game_start_timeout", 0, 0),
])
def test_app_automatically_recovers_startup_frames_once(
    entry, device, monkeypatch, monthly_startup_frames, record_property, scenario, outcome, requests, gestures,
):
    from module.game import adb, adb_ready, adb_frame_health

    started = now = 200.0
    recovered_at = None
    last_seq = 0
    last_image_at = None

    def sleep(seconds):
        nonlocal now
        now += seconds
        assert now - started < 200, "模拟启动必须在本轮时限内结束"

    clock = SimpleNamespace(monotonic=lambda: now, sleep=sleep, time=lambda: now)
    for owner in (adb, adb_ready, adb_frame_health, entry):
        monkeypatch.setattr(owner, "time", clock)
    monkeypatch.setattr(adb_ready, "wait_for_game", wait_for_game_frames)
    controller = AdbGameController(SimpleNamespace(ui_profile="touch_720", adb_tap_ms=None), logger=log)
    monkeypatch.setattr(module.game, "get_game_controller", lambda backend: controller)
    task = Mock(return_value=True)
    monkeypatch.setattr(rewards, "run_daily_training", task)
    if scenario == "deadline_before_recovery":
        device["start_game_timeout"] = 14 / 60
    elif scenario == "deadline_during_recovery":
        device["start_game_timeout"] = 55 / 60
    bridge = Bridge()
    client = module.game.adb_transport.ServiceClient.return_value
    client.hello = {"features": ["keep_awake", "startup_snapshot"]
                    + ([] if scenario == "old_service" else ["display_focus_recovery"])}
    client.closed = False
    client.close.side_effect = lambda: setattr(client, "closed", True)
    commands, actions, events, recovery_params = [], [], [], []
    black = bytes(1280 * 720 * 3)
    static = bytearray(black)
    static[3:6] = b'\xff\xff\xff'
    main = monthly_startup_frames["main"]
    watch_task = dict(task_id=355, stack_id=355, display_id=65, visible=True,
                      top_activity="com.miHoYo.hkrpg/com.mihoyo.combosdk.ComboSDKActivity")

    def emit(name, **fields):
        events.append(dict(event=name, event_seq=len(events) + 1, **fields))

    def respond(command, **params):
        nonlocal last_seq, last_image_at, recovered_at
        elapsed = now - started
        commands.append(command)
        if command == "create_display":
            return {"display_id": 65}, None
        if command == "launch":
            emit("task_display_changed", to=65)
        sdk = scenario == "sdk_loading" and 5 <= elapsed < 25
        locked = scenario == "locked" and 5 <= elapsed < 30
        if command == "events":
            result = {"events": events[params["after"]:], "event_seq": len(events)}
            if params.get("startup"):
                if scenario == "snapshot_read_error" and elapsed < 28:
                    raise module.game.adb_transport.AdbError("internal", "暂时无法读取启动快照")
                if scenario == "stop_before_request" and elapsed >= 45:
                    bridge.cancelled = True
                result["startup"] = {
                    "device_ms": round(now * 1000), "display_id": 65,
                    "watchdog": {"task": watch_task, "pid": -1 if scenario == "process_unknown" else 123,
                                 "auto_focus": scenario in {"emulator31", "emulator32", "emulator_cached_loading"},
                                 "target_display_id": 65,
                                 "task_checked_ms": round((started if scenario == "stale_watchdog" else now) * 1000),
                                 "interactive": not locked, "keyguard_locked": locked,
                                 "sdk_window": "sdk/Login" if sdk else None},
                    "frame": {"seq": last_seq, "capturing": True,
                              "age_ms": -1 if last_image_at is None else round((now - last_image_at) * 1000)},
                }
            return result, None
        if command == "recover_display_focus":
            if params["phase"] == "apply":
                actions.extend(["DOWN@65", "CANCEL@65"])
                recovered_at = now
                injection = {"down_accepted": None if scenario == "late_receipt" else True, "cancel_accepted": True}
                if scenario == "injection_denied":
                    injection.update(down_accepted=None, down_error="inject_denied: permission denied")
                if scenario == "cancel_denied":
                    injection.update(cancel_accepted=None, cancel_error="inject_denied: permission denied")
                return {"recovery": {"status": "requested", "attempted": True, "injection": injection}}, None
            assert params["phase"] == "prepare"
            recovery_params.append(params)
            assert params["display_id"] == 65 and params["task_id"] == 355
            assert params["reason"] in {"frame_timeout", "virtual_display_black"}
            assert 0 < params["timeout_ms"] <= 15000
            assert params["deadline_ms"] <= round(now * 1000) + params["timeout_ms"]
            if scenario == "recovery_unavailable":
                raise module.game.adb_transport.AdbError("unsupported", "恢复接口不可用")
            if scenario.startswith("focus_"):
                return {"recovery": {"status": scenario, "attempted": False}}, None
            if scenario == "stop_during_recovery":
                bridge.cancelled = True
                return {"recovery": {"status": "prepared", "attempted": False, "attempt_id": 1}}, None
            if scenario == "deadline_during_recovery":
                sleep(params["timeout_ms"] / 1000 + 1.1)
                return {"recovery": {"status": "deadline", "attempted": False}}, None
            if scenario == "picture_resumed_during_evidence":
                recovered_at = now
                return {"recovery": {"status": "picture_resumed", "attempted": False}}, None
            return {"recovery": {"status": "prepared", "attempted": False, "attempt_id": 1}}, None
        if command == "frame":
            sleep(.65)
            frozen = scenario in {"stalled_recovers", "api32_stalled_recovers", "no_first_recovers", "persistent_stall", "valid_dark_loading", "emulator_cached_loading"}
            if scenario == "short_stall":
                frozen = 4 <= elapsed < 10
            if sdk or locked:
                frozen = True
            if recovered_at is not None and scenario != "persistent_stall":
                frozen = False
            if not frozen or last_image_at is None:
                last_seq += 1
                last_image_at = now
            if scenario == "no_first_recovers" and recovered_at is None:
                last_seq, last_image_at = 0, None
                raise module.game.adb_transport.AdbError("timeout", "暂时无首帧")
            if frozen and last_seq < params.get("min_seq", 0):
                raise module.game.adb_transport.AdbError("timeout", "输入后暂时没有新帧")
            if scenario == "frame_read_error" and 10 <= elapsed < 23:
                raise module.game.adb_transport.AdbError("timeout", "截图暂时不可用")
            ready_at = {"normal": 3, "short_black": 22, "short_stall": 20, "sdk_loading": 30,
                        "locked": 33, "frame_read_error": 30, "snapshot_read_error": 30}.get(scenario, 999)
            if recovered_at is not None and scenario not in {"persistent_black", "persistent_stall"}:
                ready_at = recovered_at - started + (9 if scenario == "late_receipt" else 3)
            pixels = main if elapsed >= ready_at else static if scenario in {"valid_dark_loading", "emulator_cached_loading"} else black
            return {"seq": last_seq, "display_id": 65, "crop": params["crop"], "encoding": "rgb"}, pixels
        return {"original_mode": "allowed"}, None

    client.request.side_effect = respond
    sdk = {"api30": 30, "api33": 33, "api34": 34, "api32_black_recovers": 32,
           "api32_stalled_recovers": 32, "emulator32": 32}.get(scenario, 31)
    result = entry.run(str(ROOT), "token", sdk, str(sdk), "startup-test", scenario in {"emulator31", "emulator32", "emulator_cached_loading"}, "DAILY",
                       payload(), False, False, "zh_CN", bridge)
    record_property("scenario_result", json.dumps(dict(scenario=scenario, outcome=result, actions=actions,
                                                       recovery_requests=len(recovery_params), elapsed=round(now - started, 2))))
    assert result == outcome
    assert len(recovery_params) == requests
    assert actions == ["DOWN@65", "CANCEL@65"] * gestures
    assert task.call_count == int(outcome == "success")
    assert commands.count("launch") == 1 and commands.count("shutdown") == 1
    assert not {"tap", "touch", "focus", "swipe"}.intersection(commands)
    if requests:
        expected_reason = "frame_timeout" if scenario in {"stalled_recovers", "api32_stalled_recovers", "no_first_recovers", "persistent_stall", "emulator_cached_loading"} else "virtual_display_black"
        assert recovery_params[0]["reason"] == expected_reason
    if outcome == "game_start_timeout":
        assert 14 <= now - started < 182


@pytest.mark.parametrize(("scenario", "outcome", "gestures"), [
    ("healthy", "success", 0), ("crop_is_black", "success", 0),
    ("runtime_black", "success", 1), ("runtime_stall", "success", 1),
    ("idle_then_stall", "success", 1), ("late_apply_receipt", "success", 1),
    ("runtime_cached_game", "success", 1), ("two_black_episodes", "success", 2),
    ("two_stall_episodes", "success", 2), ("startup_and_runtime", "success", 2),
    ("permanent_black", "virtual_display_black", 1), ("permanent_stall", "frame_timeout", 1),
    ("isolated_black_buffers", "frame_timeout", 3),
    ("brief_healthy_flash", "virtual_display_black", 1),
    ("locked", "success", 0), ("sdk", "success", 0), ("snapshot_error", "success", 0),
    ("lock_before_input_then_resume", "success", 1),
    ("other_window", "virtual_display_black", 0), ("unknown_focus", "virtual_display_black", 0),
    ("stop_during_prepare", "stopped", 0),
    ("deadline_before", "operation_timeout", 0), ("deadline_during", "operation_timeout", 0),
    ("emulator_move_back", "success", 1), ("emulator_runtime_black", "success", 1),
    ("emulator34_runtime_black", "success", 1),
    ("api34_physical", "virtual_display_black", 0),
])
def test_shared_focus_recovery_through_startup_and_runtime_capture(
    entry, device, monkeypatch, monthly_startup_frames, record_property, scenario, outcome, gestures,
):
    from module.automation.input_base import limit_input_deadline
    from module.game import adb, adb_ready, adb_frame_health

    started = now = 200.0
    runtime_at = None
    seq = 0
    image_at = None
    temporary_lock_until = 0
    events, commands, actions, prepares, applied = [], [], [], [], []
    watch_task = dict(task_id=355, stack_id=355, display_id=65, visible=True,
                      top_activity="com.miHoYo.hkrpg/com.mihoyo.combosdk.ComboSDKActivity")
    black = bytes(1280 * 720 * 3)
    main = monthly_startup_frames["main"]
    bridge = Bridge()
    client = module.game.adb_transport.ServiceClient.return_value
    client.hello = {"features": ["keep_awake", "startup_snapshot", "display_focus_recovery"]}
    client.closed = False
    client.close.side_effect = lambda: setattr(client, "closed", True)
    controller = AdbGameController(SimpleNamespace(ui_profile="touch_720", adb_tap_ms=None), logger=log)
    monkeypatch.setattr(module.game, "get_game_controller", lambda backend: controller)
    monkeypatch.setattr(adb_ready, "wait_for_game", wait_for_game_frames)

    def sleep(seconds):
        nonlocal now
        now += seconds
        assert now - started < 300, "故障注入必须在固定轮次内结束"

    clock = SimpleNamespace(monotonic=lambda: now, sleep=sleep, time=lambda: now)
    for owner in (adb, adb_ready, adb_frame_health, entry):
        monkeypatch.setattr(owner, "time", clock)

    def emit(name, **fields):
        events.append(dict(event=name, event_seq=len(events) + 1, **fields))

    def picture():
        if runtime_at is None:
            return scenario == "startup_and_runtime" and not applied
        elapsed = now - runtime_at
        if scenario in {"healthy", "crop_is_black", "snapshot_error", "emulator_move_back"}:
            return False
        if elapsed < 6 or (scenario in {"locked", "sdk"} and elapsed >= 64):
            return False
        runtime_applies = [when for stage, when in applied if stage == "runtime"]
        if not runtime_applies:
            return True
        if scenario in {"permanent_black", "permanent_stall", "isolated_black_buffers"}:
            return True
        if scenario == "brief_healthy_flash":
            return not 4 <= now - runtime_applies[0] < 5
        if scenario in {"two_black_episodes", "two_stall_episodes"} and len(runtime_applies) == 1:
            return now - runtime_applies[0] >= 20
        return now - runtime_applies[-1] < 2

    def respond(command, **params):
        nonlocal seq, image_at, temporary_lock_until
        commands.append((command, params))
        bad = picture()
        elapsed = 0 if runtime_at is None else now - runtime_at
        if command == "create_display":
            return {"display_id": 65}, None
        if command == "launch":
            emit("task_display_changed", to=65)
        if command == "events":
            if scenario == "emulator_move_back" and runtime_at is not None and elapsed >= 6 and len(events) == 1:
                emit("move_back_started", to=65)
                emit("task_display_changed", to=65)
                emit("focus_recovery_needed", reason="move_back", display_id=65, task_id=355, move_generation=1)
            out = {"events": events[params["after"]:], "event_seq": len(events)}
            if params.get("startup"):
                if scenario == "snapshot_error" and elapsed < 14:
                    raise adb.AdbError("internal", "状态查询暂时不可用")
                locked = (scenario == "locked" and 6 <= elapsed < 64) or now < temporary_lock_until
                sdk = scenario == "sdk" and 6 <= elapsed < 64
                full_black = bad and scenario != "runtime_cached_game"
                out["startup"] = {
                    "device_ms": round(now * 1000), "display_id": 65,
                    "watchdog": {"task": watch_task, "pid": 123, "target_display_id": 65,
                                 "task_checked_ms": round(now * 1000), "interactive": not locked,
                                 "keyguard_locked": locked, "sdk_window": "sdk/Login" if sdk else None,
                                 "frames_stalled": scenario == "idle_then_stall" and bad and elapsed >= 16},
                    "frame": {"seq": seq, "age_ms": -1 if image_at is None else round((now - image_at) * 1000),
                              "capturing": True, "black": full_black},
                }
            return out, None
        if command == "recover_display_focus":
            if params["phase"] == "prepare":
                prepares.append((runtime_at is not None, params.copy(), now))
                if scenario == "lock_before_input_then_resume" and len(prepares) == 1:
                    temporary_lock_until = now + 8
                    return {"recovery": {"status": "device_unavailable", "attempted": False}}, None
                if scenario == "stop_during_prepare":
                    bridge.cancelled = True
                if scenario == "deadline_during":
                    sleep(params["timeout_ms"] / 1000 + 1)
                if scenario in {"other_window", "unknown_focus"}:
                    return {"recovery": {"status": "focus_other" if scenario == "other_window" else "focus_unknown"}}, None
                return {"recovery": {"status": "prepared", "attempt_id": len(prepares)}}, None
            assert params["attempt_id"] == len(prepares)
            applied.append(("startup" if runtime_at is None else "runtime", now))
            actions.extend(["DOWN@65", "CANCEL@65"])
            if scenario == "emulator_move_back":
                seq += 1
                image_at = now
                emit("move_back_succeeded", first_frame_seq=seq)
            if scenario == "late_apply_receipt":
                sleep(3)
                raise adb.AdbError("timeout", "恢复回执迟到，操作可能已经生效")
            return {"recovery": {"status": "requested", "attempted": True,
                                 "injection": {"down_accepted": True, "cancel_accepted": True}}}, None
        if command == "frame":
            sleep(.5)
            frozen = bad and scenario in {"runtime_stall", "runtime_cached_game", "two_stall_episodes", "permanent_stall", "startup_and_runtime", "idle_then_stall", "isolated_black_buffers"}
            if scenario == "isolated_black_buffers" and applied and image_at < applied[-1][1] <= now - 1:
                frozen = False
            if not frozen or image_at is None:
                seq += 1
                image_at = now
            if scenario == "emulator_move_back" and applied and not any(event["event"] == "move_back_succeeded" for event in events):
                emit("move_back_succeeded", first_frame_seq=seq)
            if frozen and seq < params.get("min_seq", 0):
                raise adb.AdbError("timeout", "恢复输入后暂时还没有新帧")
            source = black if bad and scenario != "runtime_cached_game" else main
            x, y, width, height = params["crop"]
            if (x, y, width, height) != (0, 0, 1280, 720):
                # 无论局部裁剪是全黑还是没有拿到完整图，健康检测必须依据原帧。
                source = bytes(width * height * 3)
            return {"seq": seq, "display_id": 65, "crop": params["crop"], "encoding": "rgb"}, source
        return {"original_mode": "allowed"}, None

    def task(**kwargs):
        nonlocal runtime_at
        runtime_at = now
        assert controller._startup is None  # 真正通过入口结束启动检查后才注入运行期故障。
        finish = runtime_at + (21 if scenario == "deadline_before" else 26 if scenario == "deadline_during" else 220)
        template = adb_ready._load_template("main")
        with limit_input_deadline(finish):
            if scenario == "idle_then_stall":
                sleep(20)
            for _ in range(280):
                frame = controller.capture_frame(crop=(0, 0, .1, .1))
                if now >= finish:
                    raise adb.AdbError("operation_timeout", "操作超过本轮等待时限")
                runtime_applies = [when for stage, when in applied if stage == "runtime"]
                done = len(runtime_applies) >= (2 if scenario.startswith("two_") else 1)
                if scenario in {"healthy", "crop_is_black", "snapshot_error"}:
                    done = now - runtime_at >= 30
                elif scenario in {"locked", "sdk"}:
                    done = now - runtime_at >= 70
                elif scenario == "brief_healthy_flash":
                    done = False
                if done and not picture():
                    fresh = controller.capture_frame(fresh=True)
                    if fresh and adb_ready._match(fresh[0], "main", template):
                        return True
                sleep(.5)
        raise AssertionError("设备恢复模拟未在固定轮次内结束")

    monkeypatch.setattr(rewards, "run_daily_training", task)
    client.request.side_effect = respond
    emulator = scenario in {"emulator_move_back", "emulator_runtime_black", "emulator34_runtime_black"}
    sdk = 34 if scenario in {"api34_physical", "emulator34_runtime_black"} else 32 if emulator else 31
    result = entry.run(str(ROOT), "token", sdk, str(sdk), "runtime-test", emulator, "DAILY",
                       payload(), False, False, "zh_CN", bridge)
    record_property("scenario_result", json.dumps(dict(scenario="unified_" + scenario, outcome=result,
        actions=actions, prepares=len(prepares), elapsed=round(now - started, 2),
        recovery=[dict(reason=params["reason"], elapsed=round(at - started, 2)) for _, params, at in prepares])))
    assert result == outcome
    assert actions == ["DOWN@65", "CANCEL@65"] * gestures
    assert all(when_runtime for when_runtime, _, _ in prepares) or scenario == "startup_and_runtime"
    assert sum(command == "shutdown" for command, _ in commands) == 1
    dog = next(params for command, params in commands if command == "watchdog")
    assert dog["focus_recovery"] and dog["auto_focus"] == emulator
    if scenario == "emulator_move_back":
        assert prepares[0][1]["reason"] == "move_back"
        assert prepares[0][2] - runtime_at < 8
    if scenario == "lock_before_input_then_resume":
        assert len(prepares) == 2
    if scenario in {"healthy", "crop_is_black"}:
        assert sum(command == "events" and params.get("frame_health", False) for command, params in commands) <= 12


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
            ("already_used_codes", ["ABC123"]),
        ):
            cfg.set_value(key, value)
            assert bridge.progress[key] == value
        assert bridge.calls.count(("progress",)) == 4
        return True

    monkeypatch.setattr(power, "run_standalone", run)

    assert start(entry, "POWER", bridge, power_plan=[["拟造花萼（金）", "回忆之蕾", 1], *remaining]) == "success"
    assert bridge.calls.count(("progress",)) == 5
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

    assert start(entry, "ROUTINE", bridge, power_plan=[["拟造花萼（金）", "回忆之蕾", 1]], already_used_codes=["OLD1"]) == "task_failed"
    assert bridge.steps == [
        ("清体力", "started", None), ("清体力", "succeeded", "已完成 1 次挑战"),
        ("日常领奖", "started", None), ("日常领奖", "failed", "邮件失败：未确认邮箱附件状态"),
    ]
    assert bridge.summary is None
    assert bridge.progress == {
        "power_plan": [], "last_run_timestamp": 1762900000.5, "echo_of_war_timestamp": 0, "already_used_codes": ["OLD1"],
    }
    # 进度在清理之前交回，固定配置也已写入。
    assert bridge.calls.index(("progress",)) < bridge.calls.index(("cleaning",))
    assert device["control_backend"] == "adb" and device["power_enable"] is False


@pytest.mark.parametrize(("task", "target", "result"), [
    ("DAILY", (rewards, "run_daily_training"), True),
    ("POWER", (power, "run_standalone"), True),
    ("POWER", (power, "run_standalone"), False),
    ("REDEEM", (Redemption, "start"), True),
    ("REDEEM", (Redemption, "start"), False),
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


def test_redeem_uses_the_codes_from_the_app(entry, device, monkeypatch):
    seen = []

    def run(*, on_summary):
        seen.append(cfg.redemption_code)
        log.hr("准备使用兑换码", 0)
        log.info(f"开始使用兑换码: {green('ABC123')} (1/2)")
        log.info(f"当前界面: {green('主界面')}")
        log.info(f"兑换码已被使用: {yellow('永远不会抛弃你')} (2/2)")
        on_summary("兑换成功 1 个，兑换码已被使用 1 个")
        return True

    monkeypatch.setattr(Redemption, "start", run)
    bridge = Bridge()

    assert start(entry, "REDEEM", bridge, redemption_code=["ABC123", "永远不会抛弃你"]) == "success"
    assert seen == [["ABC123", "永远不会抛弃你"]]
    assert [call[2] for call in bridge.calls if call[:2] == ("log", "INFO")][-4:] == [
        "准备使用兑换码", "开始使用兑换码: ABC123 (1/2)", "当前界面: 主界面",
        "兑换码已被使用: 永远不会抛弃你 (2/2)",
    ]
    assert bridge.steps == [("兑换码", "started", None), ("兑换码", "succeeded", "兑换成功 1 个，兑换码已被使用 1 个")]


def test_each_run_reads_the_build_target_again(entry, device, monkeypatch):
    # App 进程会连续执行多轮，上一轮读到的培养目标不能留给单独运行的清体力。
    from tasks.daily.buildtarget import BuildTarget

    monkeypatch.setattr(BuildTarget, "_initialized", True)
    monkeypatch.setattr(BuildTarget, "_target_instances", {"侵蚀隧洞": ["睿治之径"]})

    def run(*, on_summary):
        assert not BuildTarget._initialized
        assert BuildTarget._target_instances == {}
        return True

    monkeypatch.setattr(power, "run_standalone", run)
    assert start(entry, "POWER", Bridge()) == "success"


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
        log.debug(f"识别目标: {green('委托')}")
        raise GameRecoveryError(red("委托失败后无法回到可操作界面"))

    monkeypatch.setattr(rewards, "run_daily_training", fail)
    bridge = Bridge()

    assert start(entry, "DAILY", bridge) == "runtime_error"
    diagnostics = [call[2] for call in bridge.calls if call[:2] == ("log", "DEBUG")]
    assert len(diagnostics) == 1
    assert "ADB 启动模板 menu" in diagnostics[0] and "相似度=0.450 阈值=0.90" in diagnostics[0]
    assert "OCR识别结果: ['委托']" in diagnostics[0]
    assert "识别目标: 委托" in diagnostics[0]
    assert all("\033[" not in call[2] for call in bridge.calls if call[0] == "log")
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
