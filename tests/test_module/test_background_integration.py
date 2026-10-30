"""后台选择、截图来源和启动守卫：所有窗口接口都打桩。"""
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def config(mode='background', cloud=False, protection=False):
    values={'local_control_mode':mode,'cloud_game_enable':cloud,'background_mouse_protection':protection}
    return SimpleNamespace(get_value=lambda key,default=None:values.get(key,default),
                           cloud_game_enable=cloud,game_title_name='game',use_background_screenshot=True)


@pytest.mark.skipif(sys.platform!='win32',reason='本地输入仅限 Windows')
def test_factory_preserves_front_and_selects_background_without_window_calls(monkeypatch):
    from module.game.local import LocalGameController
    from module.automation.background_input import BackgroundInput
    from module.automation.local_input import LocalInput
    control=object.__new__(LocalGameController)
    control.logger=Mock()
    control.window_name,control.process_name='game','StarRail'
    control._config=config('foreground')
    assert isinstance(control.get_input_handler(),LocalInput)
    control._config=config()
    handler=control.get_input_handler()
    assert isinstance(handler,BackgroundInput)
    assert handler._api is None  # 工厂/导入阶段不能查找、激活游戏。
    assert handler.protect_mouse is False
    handler.close()
    control._config=config(protection=True)
    handler=control.get_input_handler()
    assert handler.protect_mouse is True and handler._api is None
    handler.close()


@pytest.mark.skipif(sys.platform!='win32',reason='本地输入仅限 Windows')
def test_background_ready_does_not_relaunch_minimized_game(monkeypatch):
    from module.game.local import LocalGameController
    from module.automation.background_input import InputInterrupted
    control=object.__new__(LocalGameController)
    control._config=config()
    control.get_input_handler=lambda:SimpleNamespace(is_available=lambda:False)
    control.is_game_running=lambda:True
    with pytest.raises(InputInterrupted,match='最小化'):
        control.switch_to_game()
    control.is_game_running=lambda:False
    assert control.switch_to_game() is False


def test_launcher_keeps_own_foreground_handler(monkeypatch):
    import module.automation.launcher_automation as module
    import module.automation.local_input as local
    monkeypatch.setattr(module,'cfg',config())
    handler=Mock()
    factory=Mock(return_value=handler)
    game_factory=Mock(side_effect=AssertionError('launcher must not borrow game HWND'))
    monkeypatch.setattr(local,'LocalInput',factory)
    monkeypatch.setattr(module,'get_game_controller',game_factory)
    launcher=SimpleNamespace(logger=Mock())
    module.LauncherAutomation._init_input(launcher)
    assert launcher.input_handler is handler
    game_factory.assert_not_called()


@pytest.fixture
def capture(monkeypatch):
    if sys.platform!='win32':
        pytest.skip('Windows 截图策略')
    import module.automation.screenshot as module
    import win32gui
    monkeypatch.setattr(module,'cfg',config())
    window=SimpleNamespace(_hWnd=123)
    monkeypatch.setattr(module.Screenshot,'get_window',Mock(return_value=window))
    monkeypatch.setattr(module.Screenshot,'get_window_region',Mock(return_value=(100,200,1920,1080)))
    monkeypatch.setattr(module.Screenshot,'get_window_real_resolution',Mock(return_value=(1920,1080)))
    minimized=Mock(return_value=False)
    monkeypatch.setattr(win32gui,'IsIconic',minimized)
    background=Mock(return_value=None)
    desktop=Mock(side_effect=AssertionError('desktop frame is not a background game frame'))
    monkeypatch.setattr(module.Screenshot,'capture_window_background',background)
    monkeypatch.setattr(module.Screenshot,'capture_screen_with_mss',desktop)
    return SimpleNamespace(module=module,background=background,desktop=desktop,minimized=minimized)


def test_background_capture_never_falls_back_to_desktop(capture):
    c=capture
    assert c.module.Screenshot.take_screenshot('game',use_background_screenshot=False) is False
    c.background.assert_called_once()
    c.desktop.assert_not_called()


def test_minimized_capture_never_attempts_capture(capture):
    c=capture
    c.minimized.return_value=True
    assert c.module.Screenshot.take_screenshot('game') is False
    c.background.assert_not_called()
    c.desktop.assert_not_called()


def test_backend_snapshot_enforces_background_capture_after_setting_changes(capture):
    c=capture
    c.module.cfg=config('foreground')
    assert c.module.Screenshot.take_screenshot('game',require_background=True) is False
    c.background.assert_called_once()
    c.desktop.assert_not_called()


def test_background_autoplot_uses_available_window_and_releases_on_stop(monkeypatch,qapp):
    from tasks.tool.autoplot import _engine as module
    backend=SimpleNamespace(is_background=True,is_available=Mock(return_value=True),release_all=Mock())
    automation=SimpleNamespace(input_handler=backend,_init_input=Mock())
    monkeypatch.setattr(module,'auto',automation)
    monkeypatch.setattr(module,'gw',SimpleNamespace(getActiveWindow=Mock(side_effect=AssertionError('foreground irrelevant'))))
    engine=module.AutoPlot('game')
    engine.start()
    assert engine._is_game_window_active()
    backend.is_available.return_value=False
    assert not engine._is_game_window_active()
    engine.stop()
    backend.release_all.assert_called_once()


def test_game_start_does_not_kill_game_on_input_interruption(monkeypatch):
    import tasks.game as module
    from module.automation.background_input import InputInterrupted
    controller=Mock()
    controller.switch_to_game.side_effect=InputInterrupted('minimized')
    monkeypatch.setattr(module,'cfg',SimpleNamespace(cloud_game_enable=False))
    monkeypatch.setattr(module,'StarRailController',Mock(return_value=controller))
    with pytest.raises(InputInterrupted):module.start_game()
    controller.stop_game.assert_not_called()
    controller.start_game_process.assert_not_called()


def test_cloud_selection_ignores_local_background_setting(monkeypatch):
    import module.game as game
    from module.automation.input_base import background_enabled
    from module.automation.cdp_input import CdpInput
    cfg=config('background',cloud=True)
    assert not background_enabled(cfg)
    monkeypatch.setattr(game,'cfg',cfg)
    assert isinstance(game.get_game_controller().get_input_handler(),CdpInput)
