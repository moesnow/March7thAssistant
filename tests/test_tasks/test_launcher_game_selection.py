"""更新和预下载按启动器选择默认游戏，并保留显式传入的游戏标识。"""
import sys
from types import SimpleNamespace, ModuleType
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize("operation", ["update_via_launcher", "pre_download_via_launcher"])
@pytest.mark.parametrize("title", ["米哈游启动器", "HoYoPlay"])
@pytest.mark.parametrize("game_id", [None, "hkrpg_cn", "hkrpg_global", "hk4e_cn", "nap_cn"])
def test_launcher_game_selection(monkeypatch, operation, title, game_id):
    import tasks.game as game

    monkeypatch.setattr(game, "cfg", SimpleNamespace(
        launcher_path="launcher.exe", launcher_process_name="HYP.exe", launcher_title_name=title))
    monkeypatch.setattr(game.os.path, "exists", lambda _: True)
    monkeypatch.setattr(game.time, "sleep", lambda _: None)
    launcher = Mock()
    controller = Mock(return_value=launcher)
    automation = Mock()
    launcher_module = ModuleType("module.game.launcher")
    launcher_module.LauncherController = controller
    automation_module = ModuleType("module.automation.launcher_automation")
    automation_module.LauncherAutomation = automation
    monkeypatch.setitem(sys.modules, launcher_module.__name__, launcher_module)
    monkeypatch.setitem(sys.modules, automation_module.__name__, automation_module)
    monkeypatch.setattr(game, "_handle_launcher_self_update", Mock(return_value=True))
    monkeypatch.setattr(game, "_click_update_game_and_wait", Mock())
    monkeypatch.setattr(game, "_click_pre_download", Mock(return_value=True))

    if game_id is None:
        getattr(game, operation)()
    else:
        getattr(game, operation)(game_id)

    expected = game_id or ("hkrpg_global" if title == "HoYoPlay" else "hkrpg_cn")
    launcher.start_game_process.assert_called_once_with(f"--game={expected}")
    assert controller.call_args.kwargs["window_name"] == title
    assert automation.call_args.args[0] == title
