from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytest.importorskip("win32gui")
from module.game.epic import EpicLaunchError


def test_scheduled_epic_failure_restores_settings_without_replaying(monkeypatch):
    import tasks.game as game
    controller = Mock(launch_method="epic")
    controller.switch_to_game.return_value = False
    controller.start_game_process.side_effect = EpicLaunchError("Epic 启动[等待游戏]超时")
    monkeypatch.setattr(game, "StarRailController", Mock(return_value=controller))
    monkeypatch.setattr(game, "cfg", SimpleNamespace(cloud_game_enable=False, auto_set_resolution_enable=True,
                                                   auto_battle_detect_enable=True))
    with pytest.raises(EpicLaunchError, match="等待游戏"):
        game.start_game()
    controller.change_resolution.assert_called_once_with(1920, 1080)
    controller.change_auto_hdr.assert_called_once_with("disable")
    controller.change_auto_battle.assert_called_once_with(True)
    controller.start_game_process.assert_called_once()
    controller.restore_resolution.assert_called_once()
    controller.restore_auto_hdr.assert_called_once()
    controller.stop_game.assert_not_called()


def test_manual_epic_launch_only_launches(qapp):
    from app.tools.game_starter import GameLaunchThread, GameStartStatus
    controller = Mock()
    thread = GameLaunchThread(controller, SimpleNamespace(cloud_game_enable=False))
    result = []
    thread.finished_signal.connect(result.append)
    controller.start_game_process.return_value = True
    thread.run()
    assert result == [GameStartStatus.SUCCESS]
    assert controller.method_calls == [("start_game_process", (), {})]
