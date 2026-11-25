from io import BytesIO, StringIO
import logging
import sys
from types import SimpleNamespace
from unittest.mock import Mock, call

from PIL import Image
import pytest

from module import config as game_config
from module import game
from module.automation import automation, screenshot
from module.automation.background_input import BackgroundInput, GameWindowLost
from module.automation.windows_input import WINDOW_EXITED, WINDOW_MINIMIZED, WINDOW_MISSING
from module.game.adb import AdbGameController
from module.game.adb_transport import AdbError, RESOLUTION
from module.screen.screen import Screen
from tasks import reward
from tasks.base import task_steps
from tasks.power import readout
from tasks.reward import quest, receipt, rewardtemplate
from tasks.touch import daily, rewards, synthesis
from tasks.weekly import divergent_universe, weekly_reward
from utils import windows_session
from utils.pause import RunStopRequested
from utils.runs import _TeeStream


BUTTON = ((10, 20), (30, 40))


@pytest.mark.parametrize("where, error", [
    ("dispatch", None), ("cleanup", None),
    ("cleanup", AdbError("disconnected", "设备已断开")), ("cleanup", RunStopRequested()),
])
def test_touch_reward_capture_faults_continue_only_with_a_usable_session(monkeypatch, where, error):
    png = BytesIO()
    Image.new("RGB", RESOLUTION).save(png, format="PNG")
    pending = [b"Capturing failed.\n", b"\x89PNG\r\n\x1a\n"] if error is None else [error]
    in_cleanup = False

    def screencap(*args, **kwargs):
        assert args == ("exec-out", "screencap", "-p") and kwargs == {"binary": True}
        if pending and (where == "dispatch" or in_cleanup):
            frame = pending.pop(0)
            if isinstance(frame, BaseException):
                raise frame
            return frame
        return png.getvalue()

    config = SimpleNamespace(
        control_backend="adb", ui_profile="touch_720", power_enable=False, reward_enable=True,
        reward_dispatch_enable=True, reward_assist_enable=True, reward_mail_enable=False,
        reward_srpass_enable=False, reward_message_enable=False,
    )
    controller = AdbGameController(config)
    controller._display_id = 0
    controller._service = SimpleNamespace(adb=SimpleNamespace(run=screencap))
    monkeypatch.setattr(game, "get_game_controller", lambda *_args: controller)
    monkeypatch.setattr(screenshot, "cfg", config)
    monkeypatch.setattr(automation, "cfg", config)
    monkeypatch.setattr(automation, "time", SimpleNamespace(monotonic=automation.time.monotonic, sleep=Mock()))
    monkeypatch.setattr(rewards.auto, "input_handler", SimpleNamespace(is_background=False))
    monkeypatch.setattr(rewards.auto, "_is_debug_enabled", lambda: False)
    monkeypatch.setattr(rewards.auto, "find_text_element", Mock(return_value=(None, None)))
    monkeypatch.setattr(rewards.auto, "find_image_element", Mock(return_value=(None, None, 0)))

    screen = object.__new__(Screen)
    Screen.__init__(screen, "assets/touch_720/screens.json", logger=Mock())

    def check_popup(target):
        nonlocal in_cleanup
        assert target == "item_reward"
        in_cleanup = True
        try:
            return Screen.check_screen(screen, target)
        finally:
            in_cleanup = False

    monkeypatch.setattr(screen, "check_screen", check_popup)
    monkeypatch.setattr(screen, "change_to", Mock())
    monkeypatch.setattr(task_steps, "screen", screen)
    monkeypatch.setattr(rewards, "screen", screen)
    monkeypatch.setattr(rewards, "cfg", config)
    monkeypatch.setattr(rewards, "menu_alert", Mock(return_value=True))
    monkeypatch.setattr(rewards, "_find_support_gift", Mock(return_value=BUTTON))
    click = Mock(return_value=True)
    monkeypatch.setattr(rewards.auto, "click_element_with_pos", click)
    confirm = Mock()
    monkeypatch.setattr(rewards, "_confirm_item_reward", confirm)
    monkeypatch.setattr(rewards, "_close_item_reward", Mock(return_value=True))
    train = Mock(return_value=True)
    monkeypatch.setattr(daily, "run", train)

    if error is not None:
        with pytest.raises(type(error)) as stopped:
            rewards.routine()
        assert stopped.value is error
        if isinstance(error, AdbError):
            assert controller._failure is error
            with pytest.raises(AdbError, match="设备已断开"):
                controller.capture_frame()
        click.assert_not_called()
        train.assert_not_called()
    else:
        assert rewards.routine() is True
        assert controller._failure is None
        assert controller.capture_frame()[0].size == RESOLUTION
        click.assert_called_once_with(BUTTON)
        confirm.assert_called_once_with()
        train.assert_called_once()
    assert not pending


def _ocr_line(text):
    return [([(0, 0), (10, 0), (10, 10), (0, 10)], (text, 0.99))]


@pytest.mark.parametrize("touch", [False, True])
@pytest.mark.parametrize("full_notice, previous_page", [(True, False), (False, False), (False, True)])
def test_delayed_training_badge_checks_the_card_once_and_keeps_confirmed_progress(
    monkeypatch, touch, full_notice, previous_page,
):
    module = daily if touch else quest
    badge_crop = daily.ACTIVITY_CROP if touch else quest.ACTIVITY
    card_crop = daily.CARDS_CROP if touch else quest.CARDS
    badge = Image.new("RGB", (60, 32))
    cards = Image.new("RGB", (600, 240))
    frames = []

    def take_screenshot(crop):
        frames.append(crop)
        if crop == card_crop and not full_notice:
            if previous_page and frames.count(card_crop) == 1:
                return cards, None, 1
            raise RuntimeError("复核回执时截图失败")
        return (badge if crop == badge_crop else cards), None, 1

    def recognize(frame):
        if frame is not cards:
            return _ocr_line("400")
        if previous_page:
            return _ocr_line("万能合成 0/1" if touch else "拍照 0/1")
        return _ocr_line("本日活跃度已满")

    config = SimpleNamespace(
        reward_enable=True, reward_quest_enable=True, daily_enable=True, daily_material_enable=True,
        save_timestamp=Mock(), notify_template={"DailyPracticeCompleted": "实训完成通知"},
    )
    milestone = ((40, 50), (60, 70))
    matches = [BUTTON, None]
    if previous_page:
        matches = [None, BUTTON, milestone]
        if touch:
            matches.append(BUTTON)
        matches.append(None)
    auto = Mock(take_screenshot=Mock(side_effect=take_screenshot), screenshot=cards,
                find_element=Mock(side_effect=matches), click_element_with_pos=Mock(return_value=True))
    monkeypatch.setattr(module, "cfg", config)
    monkeypatch.setattr(module, "auto", auto)
    monkeypatch.setattr(module, "ocr", SimpleNamespace(recognize_multi_lines=recognize))
    monkeypatch.setattr(module, "screen", Mock())
    monkeypatch.setattr(module, "drag_to_edge", Mock(return_value=True))
    monkeypatch.setattr(module, "drag_list", Mock(return_value=True))
    monkeypatch.setattr(module, "changed_ratio", Mock(return_value=1))
    monkeypatch.setattr(module, "time", SimpleNamespace(sleep=Mock()))
    monkeypatch.setattr(readout, "ocr", SimpleNamespace(recognize_multi_lines=recognize))
    monkeypatch.setattr(readout, "time", SimpleNamespace(sleep=Mock()))
    notify = Mock()
    action = Mock()
    monkeypatch.setattr(module, "notify_reward", notify)
    if touch:
        monkeypatch.setattr(synthesis, "material", action)
        assert daily.run(complete_training=True)
    else:
        monkeypatch.setattr(quest, "confirm_item_reward", Mock())
        monkeypatch.setattr(quest, "close_item_reward", Mock(return_value=True))
        assert quest.Quest.settle(complete=True, actions=(("拍照1次", action),))

    assert frames == [badge_crop] + [card_crop] * previous_page + [badge_crop] * (8 if touch else 6) + [card_crop]
    action.assert_not_called()
    assert module.drag_list.call_count == previous_page
    assert auto.find_element.call_args.args[0] == module.RECEIVE_MILESTONE
    assert auto.click_element_with_pos.call_args_list == [call(BUTTON)] + [call(milestone)] * previous_page
    if full_notice:
        config.save_timestamp.assert_called_once_with("last_run_timestamp")
        assert notify.call_args.args == (auto, "实训完成通知")
    else:
        config.save_timestamp.assert_not_called()
        if previous_page:
            assert notify.call_args.args == (auto, "已领取实训奖励，活跃度 400/500")
        else:
            notify.assert_not_called()


def test_closed_stderr_does_not_replace_the_optional_cleanup_error(monkeypatch):
    original = StringIO()
    original.close()
    tee = _TeeStream(original, StringIO())
    logger = logging.Logger("reward-cleanup-test")
    logger.addHandler(logging.StreamHandler(tee))
    auto = Mock(click_element=Mock(side_effect=RuntimeError("关闭已到账弹窗时截图失败")))
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stderr", tee)
        patch.setattr(logging, "raiseExceptions", True)
        patch.setattr(task_steps, "log", logger)
        patch.setattr(receipt, "auto", auto)
        closed = receipt.close_item_reward()

    assert closed is False
    auto.click_element.assert_called_once()


def test_invalid_adb_protocol_response_remains_terminal():
    error = AdbError("invalid_response", "设备端协议响应无效")
    controller = AdbGameController(SimpleNamespace())
    controller._display_id = 7
    controller._service = SimpleNamespace(request=Mock(side_effect=error))
    with pytest.raises(AdbError) as fatal:
        with task_steps.optional_reward("奖励截图"):
            controller.capture_frame()

    assert fatal.value is error
    assert controller._failure is error


@pytest.mark.parametrize("window_problem", [WINDOW_EXITED, WINDOW_MINIMIZED, WINDOW_MISSING])
def test_weekly_reward_diagnostic_distinguishes_exit_from_a_temporary_window(monkeypatch, tmp_path, window_problem):
    monkeypatch.chdir(tmp_path)
    instance = divergent_universe.DivergentUniverse()
    config = SimpleNamespace(control_backend="local", ui_profile="pc_1080", weekly_divergent_timestamp=0,
                             refresh_hour=4, weekly_divergent_bonus_enable=False)
    monkeypatch.setattr(instance, "run", Mock(return_value=True))
    monkeypatch.setattr(divergent_universe.Base, "send_notification_with_screenshot", Mock())
    monkeypatch.setattr(divergent_universe.Date, "is_next_mon_x_am", Mock(return_value=True))
    for module in (game_config, automation, divergent_universe):
        monkeypatch.setattr(module, "cfg", config)
    now = [0.0]
    monkeypatch.setattr(weekly_reward, "time", SimpleNamespace(
        monotonic=lambda: now[0], sleep=lambda seconds: now.__setitem__(0, now[0] + seconds)))
    auto = weekly_reward.auto
    monkeypatch.setattr(auto, "find_element", Mock(return_value=None))
    monkeypatch.setattr(auto, "click_element", Mock(return_value=True))
    monkeypatch.setattr(auto, "perform_ocr", lambda **kwargs: setattr(auto, "ocr_result", []))
    monkeypatch.setattr(auto, "_is_debug_enabled", lambda: False)
    window = object.__new__(BackgroundInput)
    problems = [None, None, window_problem]
    window.window_problem = Mock(side_effect=lambda: problems.pop(0) if problems else None)
    window.release_all = Mock()
    window.logger = None
    window._window_wait_expired = False
    monkeypatch.setattr(auto, "input_handler", window)
    frame = Image.new("RGB", (24, 24))
    capture = Mock(return_value=(frame, (0, 0, 24, 24), 1))
    monkeypatch.setattr(screenshot.Screenshot, "take_screenshot", capture)
    check_score = Mock(side_effect=auto.take_screenshot)
    monkeypatch.setattr(instance, "check_divergent_universe_score", check_score)

    if window_problem == WINDOW_EXITED:
        with pytest.raises(GameWindowLost):
            instance.start()
        assert capture.call_count == 2
        check_score.assert_not_called()
    else:
        assert instance.start() is True
        assert 3 <= capture.call_count < 30
        check_score.assert_called_once_with()

    window.release_all.assert_called_once_with()


@pytest.mark.parametrize("process_running", [False, True])
def test_foreground_rewards_check_game_process_when_the_window_disappears(monkeypatch, process_running):
    config = SimpleNamespace(
        control_backend="local", ui_profile="pc_1080", game_title_name="游戏", game_process_name="StarRail.exe",
        reward_enable=True, reward_dispatch_enable=True, reward_mail_enable=False,
        reward_assist_enable=False, reward_srpass_enable=False, reward_message_enable=False,
        reward_achievement_enable=False, reward_quest_enable=False,
    )
    for module in (automation, screenshot, reward):
        monkeypatch.setattr(module, "cfg", config)
    monkeypatch.setattr(screenshot, "sys", SimpleNamespace(platform="win32"), raising=False)
    lookup = Mock(return_value=process_running)
    monkeypatch.setattr(screenshot, "WindowsInputApi", lambda: SimpleNamespace(process_running=lookup), raising=False)
    monkeypatch.setattr(windows_session, "process_session_id", Mock(return_value=7))
    monkeypatch.setattr(screenshot.Screenshot, "get_window", Mock(return_value=None))
    auto = reward.auto
    monkeypatch.setattr(auto, "input_handler", SimpleNamespace(is_background=False))
    monkeypatch.setattr(auto, "window_title", config.game_title_name)
    screen = object.__new__(Screen)
    Screen.__init__(screen, "assets/config/screens.json", logger=Mock())
    monkeypatch.setattr(rewardtemplate, "screen", screen)

    with automation.screenshot_retry_timeout(0):
        if process_running:
            assert reward.start() is True
        else:
            with pytest.raises(GameWindowLost, match="游戏进程已退出"):
                reward.start()
    lookup.assert_called_once_with(config.game_process_name, session_id=7)
