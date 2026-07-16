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

    stub_modules = {
        "module.screen": _stub_module("module.screen", screen=object()),
        "module.automation": _stub_module("module.automation", auto=object()),
        "module.logger": _stub_module("module.logger", log=FakeLog()),
        "module.config": _stub_module("module.config", cfg=cfg),
        "tasks.power.instance": _stub_module("tasks.power.instance", Instance=FakeInstance),
        "tasks.daily.buildtarget": _stub_module("tasks.daily.buildtarget", BuildTarget=FakeBuildTarget),
    }

    power_path = Path(__file__).parents[2] / "tasks" / "power" / "power.py"
    spec = importlib.util.spec_from_file_location("power_plan_under_test", power_path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stub_modules):
        spec.loader.exec_module(module)
    return module


class TestPowerPlanRetention(unittest.TestCase):
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
