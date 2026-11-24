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
    monkeypatch.setitem(sys.modules, 'module.config', types.SimpleNamespace(cfg=types.SimpleNamespace(game_path='StarRail.exe')))
    spec = importlib.util.spec_from_file_location('test_starrail_registry', ROOT / 'utils/registry/star_rail_setting.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, winreg


@pytest.mark.parametrize(("company", "product", "region"), [
    ("miHoYo", "崩坏：星穹铁道", "cn"),
    ("Cognosphere", "Star Rail", "oversea"),
])
@pytest.mark.parametrize(("prompt_codes", "prompt_names"), [
    ((76, 43), ("space", "h")),
    ((14, 25), ("f1", "f12")),
])
def test_read_game_hotkeys_uses_selected_client_and_decodes_supported_bindings(
    registry, tmp_path, company, product, region, prompt_codes, prompt_names,
):
    module, reg = registry
    data = tmp_path / "StarRail_Data"
    data.mkdir()
    (data / "app.info").write_text(f"{company}\n{product}\n", encoding="utf-8")
    values = {
        "HotkeysSettings_Menu_MazeInteract_Keyboard_h2537131863": prompt_codes[0],
        "HotkeysSettings_Menu_BattleAvatarDetail_Keyboard_h1744695036": prompt_codes[1],
        "HotkeysSettings_Menu_MazeSkill_Keyboard_h1042695892": 76,
        "HotkeysSettings_Maze_Map_Keyboard_h1833719210": 46,
        "HotkeysSettings_Maze_Gacha_Keyboard_h3861591226": 25,
        "HotkeysSettings_Menu_PhoneMessage_Keyboard_h3569468801": 31,
        "HotkeysSettings_Menu_BattleAuto_Keyboard_h3719200595": 70,
    }
    reg.QueryValueEx.side_effect = lambda _key, name: (values[name], reg.REG_DWORD)

    assert module.read_game_hotkeys(str(tmp_path / "StarRail.exe")) == {
        "hotkey_interact": prompt_names[0], "hotkey_character_details": prompt_names[1],
        "hotkey_technique": "space", "hotkey_map": "k", "hotkey_warp": "f12",
        "hotkey_message": "5", "hotkey_auto_battle": ";",
    }
    reg.OpenKey.assert_called_once_with(reg.HKEY_CURRENT_USER, getattr(module, f"registry_key_path_{region}"))
    reg.SetValueEx.assert_not_called()


def test_missing_invalid_and_unknown_values_leave_other_game_hotkeys_available(registry):
    module, reg = registry
    module.registry_path_for_game = MagicMock(return_value=module.registry_key_path_cn)
    reg.QueryValueEx.side_effect = [
        FileNotFoundError(), (76, 3), (2**32 - 1, reg.REG_DWORD),
        PermissionError(), (57, reg.REG_DWORD),
    ]
    names = ("hotkey_technique", "hotkey_map", "hotkey_warp", "hotkey_message", "hotkey_auto_battle")
    assert module.read_game_hotkeys("StarRail.exe", names) == {"hotkey_auto_battle": "v"}

    reg.OpenKey.side_effect = PermissionError()
    assert module.read_game_hotkeys("StarRail.exe") == {}


def test_unsupported_prompt_keys_log_once_per_binding(registry, monkeypatch):
    module, reg = registry
    module.registry_path_for_game = MagicMock(return_value=module.registry_key_path_cn)
    log = MagicMock()
    monkeypatch.setitem(sys.modules, "module.logger", types.SimpleNamespace(log=log))
    values = {
        "HotkeysSettings_Menu_MazeInteract_Keyboard_h2537131863": 110,
        "HotkeysSettings_Menu_BattleAvatarDetail_Keyboard_h1744695036": 65535,
    }
    reg.QueryValueEx.side_effect = lambda _key, name: (values[name], reg.REG_DWORD)
    names = ("hotkey_interact", "hotkey_character_details")

    assert module.read_game_hotkeys("StarRail.exe", names) == {}
    assert module.read_game_hotkeys("StarRail.exe", names) == {}
    assert log.warning.call_count == 2
    assert "交互键 CAPSLOCK" in log.warning.call_args_list[0].args[0]
    assert "角色详情键 键码 65535" in log.warning.call_args_list[1].args[0]


def test_registry_created_after_module_import_is_detected(registry):
    module, reg = registry
    module.registry_path_for_game = MagicMock(return_value=module.registry_key_path_cn)
    reg.OpenKey.side_effect = FileNotFoundError
    with pytest.raises(OSError, match='Registry key path not found'):
        module.get_auto_battle_open_setting()
    reg.OpenKey.side_effect = None
    reg.QueryValueEx.return_value = (1, reg.REG_DWORD)
    assert module.get_auto_battle_open_setting() == 1
    assert reg.OpenKey.call_args.args[1] == module.registry_key_path_cn


def test_registry_path_permission_error_is_not_reported_as_missing(registry):
    module, reg = registry
    module.registry_path_for_game = MagicMock(return_value=module.registry_key_path_cn)
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
    module.winreg.QueryValueEx.return_value = (123456, 4)
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


def test_dual_server_selects_only_configured_game(registry, tmp_path):
    module, reg = registry
    data = tmp_path / 'StarRail_Data'
    data.mkdir()
    (data / 'app.info').write_text('Cognosphere\nStar Rail\n', encoding='utf-8')
    sys.modules['module.config'].cfg.game_path = str(tmp_path / 'StarRail.exe')
    reg.QueryValueEx.return_value = (1, 4)
    assert module.get_auto_battle_open_setting() == 1
    assert all(call.args[1] == module.registry_key_path_oversea for call in reg.OpenKey.call_args_list)
    assert module.get_server_by_registry() == 'global'


def test_unknown_game_never_guesses_registry(registry, tmp_path):
    module, reg = registry
    sys.modules['module.config'].cfg.game_path = str(tmp_path / 'StarRail.exe')
    assert module.get_registry_key_path() is None
    assert module.get_server_by_registry() is None
    reg.OpenKey.assert_not_called()


def test_game_metadata_bom_and_cn(registry, tmp_path):
    module, reg = registry
    data = tmp_path / 'StarRail_Data'
    data.mkdir()
    (data / 'app.info').write_text('miHoYo\n崩坏：星穹铁道\n', encoding='utf-8-sig')
    assert module.registry_path_for_game(str(tmp_path / 'StarRail.exe')) == module.registry_key_path_cn
    assert module.registry_path_for_game(str(tmp_path / 'other.exe')) is None
