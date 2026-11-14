"""Registry startup regressions, runnable without a Windows host."""
import ast
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def registry(monkeypatch):
    winreg = MagicMock()
    winreg.HKEY_CURRENT_USER = 1
    winreg.REG_DWORD = 4
    monkeypatch.setitem(sys.modules, 'winreg', winreg)
    spec = importlib.util.spec_from_file_location('test_starrail_registry', ROOT / 'utils/registry/star_rail_setting.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, winreg


def test_registry_created_after_module_import_is_detected(registry):
    module, reg = registry
    reg.OpenKey.side_effect = FileNotFoundError
    with pytest.raises(OSError, match='Registry key path not found'):
        module.get_auto_battle_open_setting()
    reg.OpenKey.side_effect = None
    reg.QueryValueEx.return_value = (1, reg.REG_DWORD)
    assert module.get_auto_battle_open_setting() == 1
    assert reg.OpenKey.call_args.args[1] == module.registry_key_path_cn


def test_registry_path_permission_error_is_not_reported_as_missing(registry):
    module, reg = registry
    reg.OpenKey.side_effect = PermissionError('denied')
    with pytest.raises(PermissionError):
        module.get_registry_key_path()


def test_registry_read_closes_handle_when_value_missing(registry):
    module, reg = registry
    reg.QueryValueEx.side_effect = FileNotFoundError
    assert module.read_registry_value(1, 'some-key', 'missing') is None
    reg.CloseKey.assert_called_once_with(reg.OpenKey.return_value)


def _battle_method():
    tree = ast.parse((ROOT / 'tasks/game/starrailcontroller.py').read_text(encoding='utf-8'))
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'StarRailController')
    node = next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == 'change_auto_battle')
    code = compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), '<controller>', 'exec')
    ns = {'get_auto_battle_open_setting': MagicMock(side_effect=OSError('missing'))}
    exec(code, ns)
    return ns['change_auto_battle']


def test_missing_registry_battle_check_does_not_abort_start():
    controller = MagicMock()
    _battle_method()(controller, True)
    controller.log_error.assert_called_once()


def test_account_commands_use_argument_array_and_report_failure():
    spec = importlib.util.spec_from_file_location('test_gameaccount', ROOT / 'utils/registry/gameaccount.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with patch.object(module.subprocess, 'run') as run:
        run.return_value = types.SimpleNamespace(returncode=1, stderr='access denied')
        with pytest.raises(OSError, match='access denied'):
            module.gamereg_import('a path & test.reg')
        assert run.call_args.args[0] == ['reg', 'import', 'a path & test.reg']


def test_registry_write_closes_handle_when_write_denied(registry):
    module, reg = registry
    reg.SetValueEx.side_effect = PermissionError('denied')
    with pytest.raises(OSError, match='denied'):
        module.write_registry_value(1, 'some-key', 'value', 1, 4)
    reg.CloseKey.assert_called_once_with(reg.CreateKey.return_value)


def test_account_uid_is_redetected_after_first_game_start():
    spec = importlib.util.spec_from_file_location('test_gameaccount_late', ROOT / 'utils/registry/gameaccount.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.sys = types.SimpleNamespace(platform='win32')
    module.winreg = MagicMock()
    module.winreg.EnumValue.return_value = (module.uid_key, 123456, 4)
    with patch.object(module, 'get_reg_path', side_effect=[None, module.reg_path_cn]):
        assert module.gamereg_uid() is None
        assert module.gamereg_uid() == 123456


def test_account_export_rechecks_path_and_errors_when_missing():
    spec = importlib.util.spec_from_file_location('test_gameaccount_export', ROOT / 'utils/registry/gameaccount.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.sys = types.SimpleNamespace(platform='win32')
    with patch.object(module, 'get_reg_path', return_value=None), patch.object(module.subprocess, 'run') as run:
        with pytest.raises(FileNotFoundError):
            module.gamereg_export('test.reg')
        run.assert_not_called()
