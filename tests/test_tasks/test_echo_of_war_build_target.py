import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch


class FakeConfig:
    def __init__(self, build_target_echo_enabled=True):
        self.build_target_enable = True
        self.instance_names = {"历战余响": "默认副本"}
        self.values = {
            "build_target_echo_of_war_enable": build_target_echo_enabled,
        }
        self.saved_timestamps = []

    def get_value(self, key, default=None):
        return self.values.get(key, default)

    def save_timestamp(self, key):
        self.saved_timestamps.append(key)


class FakeLog:
    def hr(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


def _stub_module(name, **attributes):
    module = ModuleType(name)
    for attribute, value in attributes.items():
        setattr(module, attribute, value)
    return module


def _load_echo_module(cfg, reward_text="3/3", power=90, target=("历战余响", "目标副本"), run_result=True):
    class FakeScreen:
        @staticmethod
        def change_to(*args, **kwargs):
            pass

    class FakeAuto:
        ocr_result = [(None, (reward_text, 1.0))]

        @staticmethod
        def click_element(*args, **kwargs):
            return True

        @staticmethod
        def mouse_scroll(*args, **kwargs):
            pass

        @staticmethod
        def find_element(*args, **kwargs):
            return True

    class FakePower:
        @staticmethod
        def get():
            return power

    class FakeInstance:
        calls = []

        @staticmethod
        def run(*args):
            FakeInstance.calls.append(args)
            return run_result

    class FakeBuildTarget:
        @staticmethod
        def get_target_echo_instance():
            return target

    stub_modules = {
        "module.screen": _stub_module("module.screen", screen=FakeScreen()),
        "module.automation": _stub_module("module.automation", auto=FakeAuto()),
        "module.config": _stub_module("module.config", cfg=cfg),
        "module.logger": _stub_module("module.logger", log=FakeLog()),
        "tasks.power.power": _stub_module("tasks.power.power", Power=FakePower),
        "tasks.power.instance": _stub_module("tasks.power.instance", Instance=FakeInstance),
        "tasks.daily.buildtarget": _stub_module("tasks.daily.buildtarget", BuildTarget=FakeBuildTarget),
    }

    echo_path = Path(__file__).parents[2] / "tasks" / "weekly" / "echoofwar.py"
    spec = importlib.util.spec_from_file_location("echo_of_war_under_test", echo_path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stub_modules):
        spec.loader.exec_module(module)
    return module, FakeInstance


def test_build_target_echo_requires_option_and_detected_target():
    cfg = FakeConfig(build_target_echo_enabled=True)
    module, _ = _load_echo_module(cfg)
    assert module.Echoofwar.should_run_for_build_target() is True

    cfg.values["build_target_echo_of_war_enable"] = False
    assert module.Echoofwar.should_run_for_build_target() is False

    cfg.values["build_target_echo_of_war_enable"] = True
    with patch.object(module.BuildTarget, "get_target_echo_instance", return_value=None):
        assert module.Echoofwar.should_run_for_build_target() is False


def test_completes_all_three_rewards_and_records_week_completion():
    cfg = FakeConfig()
    module, instance = _load_echo_module(cfg, reward_text="本周可领取奖励次数：3/3", power=90)

    assert module.Echoofwar.start() is True
    assert instance.calls == [("历战余响", "目标副本", 3, 1)]
    assert cfg.saved_timestamps == ["echo_of_war_timestamp"]


def test_partial_run_does_not_record_week_completion():
    cfg = FakeConfig()
    module, instance = _load_echo_module(cfg, reward_text="3/3", power=60)

    assert module.Echoofwar.start() is True
    assert instance.calls == [("历战余响", "目标副本", 2, 1)]
    assert cfg.saved_timestamps == []


def test_zero_remaining_rewards_skips_battle_and_records_week_completion():
    cfg = FakeConfig()
    module, instance = _load_echo_module(cfg, reward_text="0/3", power=90)

    assert module.Echoofwar.start() is True
    assert instance.calls == []
    assert cfg.saved_timestamps == ["echo_of_war_timestamp"]


def test_reward_count_is_capped_at_three():
    cfg = FakeConfig()
    module, instance = _load_echo_module(cfg, reward_text="5/3", power=180)

    assert module.Echoofwar.start() is True
    assert instance.calls == [("历战余响", "目标副本", 3, 1)]
    assert cfg.saved_timestamps == ["echo_of_war_timestamp"]


def test_build_target_echo_runs_before_all_other_daily_tasks(monkeypatch):
    from tasks.daily import daily as daily_module

    events = []
    cfg = SimpleNamespace(
        reward_enable=True,
        reward_redemption_code_enable=True,
        build_target_enable=True,
        power_enable=True,
        daily_enable=True,
        last_run_timestamp="",
        refresh_hour=4,
        echo_of_war_enable=False,
        echo_of_war_timestamp="",
        echo_of_war_start_day_of_week=1,
    )

    monkeypatch.setattr(daily_module, "cfg", cfg)
    monkeypatch.setattr(daily_module.BuildTarget, "init_build_targets", lambda: events.append("build_target_init"))
    monkeypatch.setattr(daily_module.Echoofwar, "should_run_for_build_target", lambda: True)
    monkeypatch.setattr(daily_module.Echoofwar, "start", lambda: events.append("echo_of_war") or True)
    monkeypatch.setattr(daily_module.Redemption, "get", lambda: events.append("redemption"))
    monkeypatch.setattr(daily_module.Daily, "lookup", lambda: events.append("daily_lookup"))
    monkeypatch.setattr(daily_module.activity, "start", lambda: events.append("activity"))
    monkeypatch.setattr(daily_module.Power, "run", lambda: events.append("power"))
    monkeypatch.setattr(daily_module.Daily, "run", lambda: events.append("daily_run"))
    monkeypatch.setattr(daily_module.Date, "is_next_x_am", lambda *_args: True)
    monkeypatch.setattr(daily_module.Date, "is_next_mon_x_am", lambda *_args: True)

    daily_module.Daily.prepare_daily()

    assert events == [
        "build_target_init",
        "echo_of_war",
        "redemption",
        "daily_lookup",
        "activity",
        "power",
        "daily_run",
    ]
