"""材料不足时不点击合成，也不能标记本月已完成。"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch


def test_insufficient_resin_materials_preserves_monthly_task():
    auto, cfg, log = Mock(), Mock(), Mock()
    auto.click_element.return_value = True
    auto.find_element.side_effect = lambda target, *args, **kwargs: target in (
        '自塑尘脂', '合成所需材料不足')
    stubs = {}
    for name, members in {
        'module.config': {'cfg': cfg},
        'module.screen': {'screen': Mock()},
        'module.automation': {'auto': auto},
        'module.logger': {'log': log},
        'module.notification.notification': {'NotificationLevel': Mock()},
        'tasks.base.base': {'Base': Mock()},
        'tasks.base.list_drag': {'drag_list': Mock()},
    }.items():
        stub = ModuleType(name)
        stub.__dict__.update(members)
        stubs[name] = stub
    source = Path(__file__).parents[2] / 'tasks/daily/synthesis.py'
    with patch.dict(sys.modules, stubs):
        spec = importlib.util.spec_from_file_location('_resin_regression', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    with patch.object(module.time, 'sleep'):
        assert module.Synthesis.self_molding_resin() is False
    cfg.save_timestamp.assert_not_called()
    log.warning.assert_called_once()
    log.error.assert_not_called()
    assert all('synthesis_button.png' not in str(call.args[0])
               for call in auto.click_element.call_args_list)
