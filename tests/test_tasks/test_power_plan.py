import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch


class FakeConfig:
    def __init__(self, power_plan, keep_plan):
        self.values = {
            "power_plan": power_plan,
            "power_plan_keep": keep_plan,
        }
        self.writes = []

    def get_value(self, key, default=None):
        return self.values.get(key, default)

    def set_value(self, key, value):
        self.values[key] = value
        self.writes.append((key, value))

    def save_timestamp(self, key):
        self.writes.append((key, "now"))


class FakeLog:
    def hr(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


def _stub_module(name, **attributes):
    module = ModuleType(name)
    for attribute, value in attributes.items():
        setattr(module, attribute, value)
    return module


def _load_power_module(cfg):
    class FakeInstance:
        @staticmethod
        def validate_instance(instance_type, instance_name):
            return True

    class FakeBuildTarget:
        pass

    class FakeWeeklyRelicCleanup:
        @staticmethod
        def run():
            return True

    stub_modules = {
        "module.screen": _stub_module("module.screen", screen=object()),
        "module.automation": _stub_module("module.automation", auto=object()),
        "module.logger": _stub_module("module.logger", log=FakeLog()),
        "module.config": _stub_module("module.config", cfg=cfg),
        "tasks.power.instance": _stub_module("tasks.power.instance", Instance=FakeInstance),
        "tasks.daily.buildtarget": _stub_module("tasks.daily.buildtarget", BuildTarget=FakeBuildTarget),
        "tasks.power.weekly_relic_cleanup": _stub_module(
            "tasks.power.weekly_relic_cleanup", WeeklyRelicCleanup=FakeWeeklyRelicCleanup
        ),
    }

    power_path = Path(__file__).parents[2] / "tasks" / "power" / "power.py"
    spec = importlib.util.spec_from_file_location("power_plan_under_test", power_path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stub_modules):
        spec.loader.exec_module(module)
    return module


class TestPowerPlanRetention(unittest.TestCase):
    def test_weekly_cleanup_records_completion_before_power_work(self):
        cfg = FakeConfig([], keep_plan=False)
        cfg.values["break_down_level_four_relicset"] = True
        cfg.refresh_hour = 4
        module = _load_power_module(cfg)

        cfg.values["weekly_relic_cleanup_day_of_week"] = 5
        with patch.object(module.Date, "is_weekly_day_due", return_value=True) as due, patch.object(
            module.WeeklyRelicCleanup, "run", return_value=True
        ) as cleanup, patch.object(module.Power, "preprocess", side_effect=RuntimeError("stop")):
            with self.assertRaisesRegex(RuntimeError, "stop"):
                module.Power.run()

        cleanup.assert_called_once_with()
        due.assert_called_once_with(0, 5, 4)
        self.assertEqual(cfg.writes, [("weekly_relic_cleanup_timestamp", "now")])

    def test_weekly_cleanup_failure_keeps_timestamp_and_skips_power(self):
        cfg = FakeConfig([], keep_plan=False)
        cfg.values["break_down_level_four_relicset"] = True
        cfg.refresh_hour = 4
        module = _load_power_module(cfg)

        with patch.object(module.Date, "is_weekly_day_due", return_value=True), patch.object(
            module.WeeklyRelicCleanup, "run", return_value=False
        ), patch.object(module.Power, "preprocess") as preprocess:
            with self.assertRaisesRegex(RuntimeError, "每周遗器清理未完成"):
                module.Power.run()

        preprocess.assert_not_called()
        self.assertEqual(cfg.writes, [])

    def test_weekly_cleanup_is_skipped_after_this_weeks_run(self):
        cfg = FakeConfig([], keep_plan=False)
        cfg.values["break_down_level_four_relicset"] = True
        cfg.refresh_hour = 4
        module = _load_power_module(cfg)

        with patch.object(module.Date, "is_weekly_day_due", return_value=False), patch.object(
            module.WeeklyRelicCleanup, "run"
        ) as cleanup, patch.object(module.Power, "preprocess", side_effect=RuntimeError("stop")):
            with self.assertRaisesRegex(RuntimeError, "stop"):
                module.Power.run()

        cleanup.assert_not_called()
        self.assertEqual(cfg.writes, [])

    def test_daily_power_stage_does_not_repeat_weekly_check(self):
        cfg = FakeConfig([], keep_plan=False)
        module = _load_power_module(cfg)

        with patch.object(module.Power, "run_weekly_relic_cleanup") as weekly, patch.object(
            module.Power, "preprocess", side_effect=RuntimeError("stop")
        ):
            with self.assertRaisesRegex(RuntimeError, "stop"):
                module.Power.run(skip_weekly_cleanup=True)

        weekly.assert_not_called()

    def test_completed_plan_is_deleted_by_default(self):
        plan = [["侵蚀隧洞", "睿治之径", 2]]
        cfg = FakeConfig(plan, keep_plan=False)
        module = _load_power_module(cfg)

        with patch.object(module.Power, "process", return_value=2):
            self.assertTrue(module.Power.execute_power_plan())
        self.assertEqual(cfg.writes, [("power_plan", [])])

    def test_completed_plan_is_unchanged_when_keep_is_enabled(self):
        plan = [["侵蚀隧洞", "睿治之径", 2]]
        cfg = FakeConfig(plan, keep_plan=True)
        module = _load_power_module(cfg)

        with patch.object(module.Power, "process", return_value=2):
            self.assertTrue(module.Power.execute_power_plan())
        self.assertEqual(cfg.writes, [])
        self.assertEqual(cfg.get_value("power_plan"), plan)


if __name__ == "__main__":
    unittest.main()
