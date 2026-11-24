"""合成流程的动画等待改为短稳定时间，后续动作靠自身重试。"""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch


def _load_synthesis(auto, cfg):
    stubs = {}
    for name, members in {
        "module.config": {"cfg": cfg},
        "module.screen": {"screen": Mock()},
        "module.automation": {"auto": auto},
        "module.logger": {"log": Mock()},
        "module.notification.notification": {"NotificationLevel": Mock()},
        "tasks.base.base": {"Base": Mock()},
        "tasks.base.list_drag": {"drag_list": Mock()},
    }.items():
        stub = ModuleType(name)
        stub.__dict__.update(members)
        stubs[name] = stub
    source = Path(__file__).parents[2] / "tasks/daily/synthesis.py"
    with patch.dict(sys.modules, stubs):
        spec = importlib.util.spec_from_file_location("_synthesis_settle", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


def test_material_uses_short_settle_before_retrying_actions():
    auto = Mock()
    auto.click_element.return_value = True
    auto.find_element.return_value = True
    cfg = Mock(daily_material_enable=True)
    module = _load_synthesis(auto, cfg)
    module.Synthesis._verify_training_recipe = Mock(return_value=True)
    sleeps = []

    with patch.object(module.time, "sleep", side_effect=sleeps.append):
        assert module.Synthesis.material() is True

    assert module._SETTLE < 1
    assert sleeps and all(value == module._SETTLE for value in sleeps)


def test_recipe_verification_keeps_its_short_waits_out():
    auto = Mock()
    auto.click_element.return_value = True
    auto.find_element.return_value = True
    cfg = Mock(daily_material_enable=True)
    module = _load_synthesis(auto, cfg)
    module.Synthesis._verify_training_recipe = Mock(return_value=False)
    sleeps = []

    with patch.object(module.time, "sleep", side_effect=sleeps.append):
        assert module.Synthesis.material() is False

    # 配方校验失败只读一次，不应额外引入长等待
    assert all(value <= module._SETTLE for value in sleeps)
