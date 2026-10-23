"""主任务入口启用已适配模式的星启流程，忽略其旧的关闭配置。"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch


def test_all_challenges_enable_stellar_despite_legacy_disabled_flags():
    package = '_challenge_manager_stellar_test'
    constructors = {}
    stubs = {}
    for name, class_name in {
        'memoryofchaos': 'MemoryOfChaos', 'memoryone': 'MemoryOne',
        'purefiction': 'PureFiction', 'apocalyptic': 'Apocalyptic',
    }.items():
        stub = ModuleType(f'{package}.{name}')
        constructor = Mock()
        setattr(stub, class_name, constructor)
        constructors[name] = constructor
        stubs[stub.__name__] = stub
    config_module = ModuleType('module.config')
    config = Mock()
    config.get_value.side_effect = lambda key, default=None: False if key.endswith('_stellar_enable') else []
    config_module.cfg = config
    stubs['module.config'] = config_module
    path = Path(__file__).parents[2] / 'tasks/challenge/__init__.py'
    spec = importlib.util.spec_from_file_location(package, path, submodule_search_locations=[str(path.parent)])
    module = importlib.util.module_from_spec(spec)
    stubs[package] = module
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        module.ChallengeManager()
    for name in ('purefiction',):
        assert constructors[name].call_args.kwargs == {
            'team3': [['DanHeng', -1]], 'stellar_enable': True,
        }

    for name in ('memoryofchaos', 'apocalyptic'):
        assert constructors[name].call_args.kwargs == {}
