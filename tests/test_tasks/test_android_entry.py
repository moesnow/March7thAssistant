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
from ruamel.yaml import YAML

import module.game
import module.game.adb_ready
import module.game.adb_transport
import module.localization
import module.ocr
from module.config import cfg
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

    def check_before_launch():
        calls = [call for call in request.call_args_list if call.args == ("keep_awake",)]
        assert [call.kwargs for call in calls] == ([] if support == "missing" else [{"on": True}])

    controller.start_game_process.side_effect = check_before_launch
    monkeypatch.setattr(rewards, "run_daily_training", Mock(return_value=True))
    bridge = Bridge()

    assert start(entry, "DAILY", bridge) == "success"
    controller.start_game_process.assert_called_once_with()
    warnings = [call[2] for call in bridge.calls if call[:2] == ("log", "WARNING")]
    assert warnings == {
        "supported": [],
        "missing": ["设备端服务不支持保持系统唤醒"],
        "failed": ["未能保持系统唤醒：无法保持唤醒"],
    }[support]


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
