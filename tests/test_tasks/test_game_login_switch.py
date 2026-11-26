"""按账号启动、在游戏登录框里切号时的启动流程：切完之前不点进入，也不点「登录其他账号」。"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def startup(monkeypatch):
    import tasks.game as game
    cfg = SimpleNamespace(cloud_game_enable=False, auto_set_resolution_enable=False,
                          auto_battle_detect_enable=False, auto_lower_graphics_enable=False,
                          game_optimization_enable=False, start_game_timeout=1,
                          auto_set_game_path_enable=False, update_via_launcher=False)
    controller = Mock(launch_method="direct", game_path="test/StarRail.exe", process_name="StarRail.exe",
                      launched_new_process=True)
    controller.switch_to_game.return_value = False
    controller.start_game_process.return_value = True
    controller.is_game_running.return_value = False
    controller.get_resolution.return_value = (1920, 1080)
    monkeypatch.setattr(game, "cfg", cfg)
    monkeypatch.setattr(game, "StarRailController", Mock(return_value=controller))
    windows = Mock()
    windows.return_value.process_running.return_value = False
    monkeypatch.setattr(game, "WindowsInputApi", windows)
    monkeypatch.setattr(game, "process_session_id", lambda: 1)
    monkeypatch.setattr(game, "auto", SimpleNamespace(input_handler=SimpleNamespace(is_background=False),
                                                      press_mouse=Mock(), find_element=Mock(return_value=None)))
    monkeypatch.setattr(game.time, "sleep", Mock())
    monkeypatch.setattr(game, "begin_temporary_graphics", Mock())
    monkeypatch.setattr(game, "restore_temporary_graphics", Mock())
    monkeypatch.setattr(game, "screen", Mock(get_current_screen=Mock(return_value=True), current_screen="main"))

    def wait_until(condition, _timeout, *_args):
        # 只有点进入的那一步按轮次重复，其余等待直接成立。
        if condition.__name__ != "check_and_click_enter":
            return True
        return any(condition() for _ in range(10))

    monkeypatch.setattr(game, "wait_until", wait_until)
    return game, controller


def run_with(game, monkeypatch, states):
    steps = iter(states)
    switch = Mock(step=Mock(side_effect=lambda: next(steps, "done")))
    monkeypatch.setattr(game, "game_login_switch", lambda config: switch)
    clicks = []

    def click(target, *_args, **_kwargs):
        clicks.append((switch.step.call_count, target))
        return target.endswith("/click_enter.png")

    game.auto.click_element = Mock(side_effect=click)
    game.start_game()
    return switch, clicks


def test_enter_waits_until_the_switch_is_done(startup, monkeypatch):
    game, _ = startup
    switch, clicks = run_with(game, monkeypatch, ["waiting", "acted", "acted", "waiting", "done"])
    entered = [step for step, target in clicks if target.endswith("/click_enter.png")]
    assert entered == [5]
    assert not any(target.endswith("/login_switch_account.png") for _, target in clicks)
    assert not any(target.endswith("/start_game.png") and step < 5 for step, target in clicks)
    # 切号点了东西的那一轮不再点别的。
    assert not any(step in (2, 3) for step, _ in clicks)
    # 等待的那几轮仍处理热更新确认、重启和协议弹窗。
    waited = {target.rsplit("/", 1)[-1] for step, target in clicks if step in (1, 4)}
    assert waited == {"confirm.png", "restart.png", "agree_update.png"}


def test_no_switch_needed_enters_at_once(startup, monkeypatch):
    game, _ = startup
    switch, clicks = run_with(game, monkeypatch, ["done"])
    assert switch.step.call_count == 1 and clicks[0][1].endswith("/click_enter.png")


def test_switch_failure_keeps_the_game_and_stops(startup, monkeypatch):
    game, controller = startup
    switch = Mock(step=Mock(side_effect=game.AccountError("account_verification", "需要安全验证")))
    monkeypatch.setattr(game, "game_login_switch", lambda config: switch)
    game.auto.click_element = Mock(return_value=False)
    with pytest.raises(game.AccountError) as error:
        game.start_game()
    assert error.value.reason == "account_verification"
    controller.stop_game.assert_not_called()
    assert controller.start_game_process.call_count == 1
