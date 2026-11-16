from time import monotonic
from types import SimpleNamespace
from unittest.mock import Mock, call

from PIL import Image
import pytest

from module.game.adb_transport import AdbError
from module.notification.notification import NotificationLevel
from tasks import reward
from tasks.base import task_steps
from tasks.daily import daily as pc_daily, redemption, synthesis as pc_synthesis
from tasks.reward import assist, mail, message, quest, receipt, rewardtemplate, sms
from tasks.touch import daily, rewards, synthesis


BUTTON = ((10, 20), (30, 40))


@pytest.mark.parametrize("has_red_dot", [False, True])
def test_pc_sms_opens_only_with_a_menu_red_dot(monkeypatch, has_red_dot):
    config = SimpleNamespace(
        reward_enable=True, reward_message_enable=True, reward_dispatch_enable=False, reward_mail_enable=False,
        reward_assist_enable=False, reward_srpass_enable=False, reward_achievement_enable=False, reward_quest_enable=False,
    )
    auto = Mock(find_element=Mock(return_value=BUTTON if has_red_dot else None))

    def change_screen(target, **_kwargs):
        if target == "incoming_message" and not has_red_dot:
            raise RuntimeError("没有待处理短信时，快捷键无法打开短信界面")

    screen = Mock(change_to=Mock(side_effect=change_screen))
    read_messages = Mock()
    monkeypatch.setattr(reward, "cfg", config)
    monkeypatch.setattr(reward, "auto", auto)
    monkeypatch.setattr(reward, "screen", screen)
    monkeypatch.setattr(rewardtemplate, "screen", screen)
    monkeypatch.setattr(task_steps, "screen", screen)
    monkeypatch.setattr(reward.Message, "run", read_messages)

    assert reward.start()

    auto.find_element.assert_called_once_with(
        "./assets/images/share/menu/message_reward.png", "image", 3000000,
        crop=(1263 / 1920, 52 / 1080, 642 / 1920, 982 / 1080),
    )
    if has_red_dot:
        assert screen.change_to.call_args_list == [call("menu"), call("incoming_message")]
        read_messages.assert_called_once_with()
    else:
        screen.change_to.assert_called_once_with("menu")
        read_messages.assert_not_called()


def test_touch_srpass_keeps_the_claim_when_the_popup_is_only_read_once(monkeypatch):
    popup = iter((BUTTON, None))
    claim_button = Mock(return_value=BUTTON)

    def find_element(target, *_args, **_kwargs):
        if target == "一键领取":
            return claim_button()
        if target == daily.REWARD_POPUP:
            return next(popup)
        return None

    auto = Mock(find_element=Mock(side_effect=find_element))
    auto.click_element.side_effect = lambda target, *_args, **_kwargs: target in ("无名勋礼", daily.REWARD_CLOSE_CROP)
    monkeypatch.setattr(rewards, "auto", auto)
    monkeypatch.setattr(rewards, "screen", Mock())
    monkeypatch.setattr(rewards, "time", SimpleNamespace(monotonic=monotonic, sleep=Mock()))

    rewards.claim_srpass()

    claim_button.assert_called_once()
    auto.click_element_with_pos.assert_called_once_with(BUTTON)
    auto.click_element.assert_any_call(daily.REWARD_CLOSE_CROP, "crop")
    rewards.screen.change_to.assert_any_call("pass1", max_recursion=1)


def test_touch_sms_counts_reward_from_the_first_detected_popup(monkeypatch):
    pending = iter((BUTTON, None))
    popup = Mock(side_effect=(BUTTON, None, None))
    frame = Image.new("RGB", (64, 48))

    def find_element(target, *_args, **_kwargs):
        if target.endswith("message_pending.png"):
            return next(pending)
        return popup() if target == daily.REWARD_POPUP else None

    auto = Mock(
        screenshot=frame, take_screenshot=Mock(return_value=(frame, None, 1)),
        find_element=Mock(side_effect=find_element),
    )
    monkeypatch.setattr(rewards, "auto", auto)
    monkeypatch.setattr(rewards, "screen", Mock())
    monkeypatch.setattr(rewards, "drag_list", Mock(return_value=True))
    notify = Mock()
    monkeypatch.setattr(rewards, "notify_reward", notify)

    rewards.claim_messages()

    assert popup.call_count == 3  # 到账一次，点关闭后确认已离开弹窗。
    auto.click_element.assert_called_once_with(daily.REWARD_CLOSE_CROP, "crop")
    notify.assert_called_once_with(auto, "处理了 1 个短信会话，领取 1 次奖励")


@pytest.mark.parametrize("touch", [False, True])
def test_sms_does_not_count_an_unclosed_popup_again(monkeypatch, touch):
    module = rewards if touch else message
    auto = Mock(find_element=Mock(return_value=BUTTON), click_element=Mock(return_value=False))
    notify = Mock()
    monkeypatch.setattr(module, "auto", auto)
    monkeypatch.setattr(module, "screen", Mock())
    monkeypatch.setattr(module, "notify_reward", notify)
    if touch:
        rewards.claim_messages()
        auto.click_element.assert_called_once_with(daily.REWARD_CLOSE_CROP, "crop")
    else:
        close = Mock(return_value=False)
        monkeypatch.setattr(message, "close_item_reward", close)
        message.Message("短信", True, "incoming_message").run()
        close.assert_called_once()
    notify.assert_called_once_with(auto, "处理了 1 个短信会话，领取 1 次奖励")


@pytest.mark.parametrize("miss_first", [False, True])
def test_touch_sms_keeps_thread_identity_after_the_list_moves(monkeypatch, miss_first):
    old_row = ((67, 100), (89, 120))
    moved_row = ((67, 210), (89, 230))
    outside_marker_column = ((160, 100), (182, 120))
    frame = Image.new("RGB", (371, 516))
    auto = Mock()
    auto.take_screenshot.return_value = (frame, (40, 92, *frame.size), 1)
    marker_matches = [outside_marker_column, moved_row, old_row]
    attempts = 2 if miss_first else 1
    auto.find_element.side_effect = [marker_matches] * attempts + [old_row]

    def recognize():
        auto.ocr_result = [] if miss_first and auto.perform_ocr.call_count == 1 else [
            ("different", ("正常会话", 1)), ("timeout", ("超时会话", 1)),
        ]

    auto.perform_ocr.side_effect = recognize
    auto.calculate_text_position.side_effect = [((104, 100), (158, 120)), ((104, 210), (158, 230))]
    monkeypatch.setattr(rewards, "auto", auto)
    monkeypatch.setattr(sms, "time", SimpleNamespace(sleep=Mock()))

    assert rewards._open_unread_message({"超时会话"})
    auto.click_element_with_pos.assert_called_once_with(old_row, offset=(24, 0))
    assert auto.take_screenshot.call_args_list == [call(crop=rewards.MESSAGE_LIST)] * attempts
    assert all(item.kwargs["take_screenshot"] is False for item in auto.find_element.call_args_list[:attempts])
    assert auto.perform_ocr.call_count == attempts


@pytest.mark.parametrize("has_blocked_marker", [False, True])
def test_sms_does_not_rescan_when_visible_threads_are_known_blocked_or_absent(monkeypatch, has_blocked_marker):
    markers = Mock(return_value=[BUTTON] if has_blocked_marker else [])
    titles = Mock(return_value=[(((35, 20), (75, 40)), "超时会话")])
    monkeypatch.setattr(sms, "find_thread_markers", markers)
    monkeypatch.setattr(sms, "read_thread_titles", titles)

    assert sms.first_unblocked_thread(Mock(), rewards.MESSAGE_LIST, rewards.MESSAGE_PENDING,
                                      (("message_thread.png", 0.89),), {"超时会话"}) is None

    markers.assert_called_once()
    assert titles.call_count == int(has_blocked_marker)


@pytest.mark.parametrize("touch", [False, True])
@pytest.mark.parametrize("miss_first", [False, True])
def test_sms_recovers_timeout_identity_on_a_fresh_frame(monkeypatch, touch, miss_first):
    module = rewards if touch else message
    row = ((100, 160), (124, 181)) if touch else ((335, 285), (360, 306))
    crop = rewards.MESSAGE_LIST if touch else message.Message._LIST
    bounds = rewards.MESSAGE_PENDING if touch else (325 / 1920, 275 / 1080, 90 / 1920, 40 / 1080)
    frame = Image.new("RGB", (round(crop[2] * 1920), round(crop[3] * 1080)))
    origin = (round(crop[0] * 1920), round(crop[1] * 1080), *frame.size)
    events = []
    auto = Mock(calculate_crop_with_pos=Mock(return_value=bounds))

    def capture(**_kwargs):
        events.append("capture")
        return frame.copy(), origin, 1

    def find(_target, mode, *_args, **kwargs):
        if mode == "image_with_multiple_targets":
            assert kwargs["take_screenshot"] is False
            events.append("marker")
            return [row]
        return row

    def recognize():
        events.append("ocr")
        auto.ocr_result = [] if miss_first and events.count("ocr") == 1 else [(None, ("超时会话", 1))]

    auto.take_screenshot.side_effect = capture
    auto.find_element.side_effect = find
    auto.perform_ocr.side_effect = recognize
    auto.calculate_text_position.return_value = ((row[1][0] + 5, row[0][1]), (row[1][0] + 45, row[1][1]))
    monkeypatch.setattr(module, "auto", auto)
    monkeypatch.setattr(module, "screen", Mock())
    monkeypatch.setattr(module, "notify_reward", Mock())
    monkeypatch.setattr(module, "close_sms_receipt", Mock(return_value=False))
    monkeypatch.setattr(sms, "time", SimpleNamespace(sleep=Mock()))

    if touch:
        finish = Mock(side_effect=[rewards.MessageTimeout("超时"), True])
        next_thread = Mock(return_value=True)
        monkeypatch.setattr(rewards, "_finish_message", finish)
        monkeypatch.setattr(rewards, "_message_pending", Mock(return_value=row))
        monkeypatch.setattr(rewards, "_open_unread_message", next_thread)
        run = rewards.claim_messages
    else:
        session = message.Message("短信", True, "incoming_message")
        finish = Mock(side_effect=[None, True])
        next_thread = Mock(return_value=row)
        monkeypatch.setattr(session, "_finish", finish)
        monkeypatch.setattr(message, "first_unblocked_thread", next_thread)
        run = session.run

    with pytest.raises(receipt.RewardError, match="1 个短信会话超时"):
        run()

    assert events == ["capture", "marker", "ocr"] * (2 if miss_first else 1)
    assert next_thread.call_args.args[-1] == {"超时会话"}
    assert finish.call_count == 2
    module.notify_reward.assert_called_once_with(auto, "处理了 1 个短信会话，领取 1 次奖励")


def test_sms_timeout_identity_propagates_disconnect():
    auto = Mock(take_screenshot=Mock(side_effect=AdbError("disconnected", "连接断开")))

    with pytest.raises(AdbError, match="连接断开"):
        sms.find_thread_title(auto, rewards.MESSAGE_LIST, rewards.MESSAGE_PENDING, "message_pending.png", 0.9)

    auto.take_screenshot.assert_called_once_with(crop=rewards.MESSAGE_LIST)
    auto.perform_ocr.assert_not_called()


@pytest.mark.parametrize("template_matches", [False, True])
@pytest.mark.parametrize("color, expected", [((255, 208, 130), True), ((100, 100, 100), False)])
def test_pc_mail_distinguishes_enabled_and_disabled_button(monkeypatch, template_matches, color, expected):
    image = Image.new("RGB", (80, 60), color)
    if not expected:
        image.paste((185, 185, 185), (10, 20, 24, 40))
    matches = [BUTTON] if template_matches else [None, BUTTON]
    auto = Mock(screenshot=image, screenshot_pos=(0, 0, 80, 60),
                screenshot_scale_factor=1, find_element=Mock(side_effect=matches))
    confirm = Mock()
    monkeypatch.setattr(mail, "auto", auto)
    monkeypatch.setattr(mail, "confirm_item_reward", confirm)
    monkeypatch.setattr(mail, "close_item_reward", Mock())

    assert mail.Mail("邮件", True, "mail").run() is expected
    assert auto.find_element.call_args_list[0].args[2] == 0.8
    assert auto.find_element.call_count == len(matches)
    auto.take_screenshot.assert_not_called()
    if expected:
        auto.click_element_with_pos.assert_called_once_with(BUTTON)
        confirm.assert_called_once_with("邮件奖励", notify=True)
    else:
        auto.click_element_with_pos.assert_not_called()
        confirm.assert_not_called()


def test_pc_mail_fallback_does_not_treat_unknown_color_as_no_attachments(monkeypatch):
    auto = Mock(screenshot=Image.new("RGB", (80, 60), (210, 68, 73)), screenshot_pos=(0, 0, 80, 60),
                screenshot_scale_factor=1, find_element=Mock(side_effect=[None, BUTTON]))
    monkeypatch.setattr(mail, "auto", auto)

    with pytest.raises(receipt.RewardError, match="未确认邮箱的全部领取按钮状态"):
        mail.Mail("邮件", True, "mail").run()
    auto.click_element_with_pos.assert_not_called()


def test_sms_can_stop_after_receipt_if_popup_visibility_check_fails():
    close = Mock(return_value=True)
    visible = Mock(side_effect=RuntimeError("截图或 OCR 失败"))
    assert sms.close_sms_receipt(close, visible) is False
    close.assert_called_once_with()
    visible.assert_called_once_with()


def test_pc_sms_rejects_an_ocr_error_as_confirmation_of_popup_close(monkeypatch):
    auto = Mock(perform_ocr=Mock(side_effect=RuntimeError("OCR 不可用")))
    close = Mock(return_value=True)
    monkeypatch.setattr(message, "auto", auto)

    assert sms.close_sms_receipt(close, message.Message._receipt_visible) is False
    auto.take_screenshot.assert_called_once_with(crop=receipt.ITEM_POPUP)
    auto.perform_ocr.assert_called_once_with(raise_on_error=True)
    auto.find_element.assert_not_called()


def test_pc_training_does_not_rescan_after_the_last_action_when_collection_is_disabled(monkeypatch):
    monkeypatch.setattr(quest, "cfg", SimpleNamespace(reward_enable=False, reward_quest_enable=False))
    scan = Mock(return_value=(400, {"拍照1次": True}, 0))
    monkeypatch.setattr(quest.Quest, "scan", scan)
    photo = Mock(return_value=True)

    assert quest.Quest.settle(complete=True, actions=(("拍照1次", photo),))
    photo.assert_called_once()
    scan.assert_called_once_with(False, read_tasks=True)


def test_pc_training_reports_pending_claim_failure_without_repeating_the_completed_action(monkeypatch):
    monkeypatch.setattr(quest, "cfg", SimpleNamespace(reward_enable=True, reward_quest_enable=True))
    monkeypatch.setattr(quest, "auto", Mock(click_element=Mock(return_value=False)))
    scan = Mock(side_effect=[(400, {"拍照1次": True}, 0), quest.DailyTrainingError("任务卡片领取按钮无法点击")])
    monkeypatch.setattr(quest.Quest, "scan", scan)
    photo = Mock(return_value=True)

    assert quest.Quest.settle(complete=True, actions=(("拍照1次", photo),)) is False
    photo.assert_called_once()
    assert scan.call_args_list == [call(True, read_tasks=True), call(True, read_tasks=False)]


def test_pc_training_recipe_checks_amount_without_reading_the_already_selected_title(monkeypatch):
    auto = Mock(ocr_result=[(None, ("合成数量:1", 1)), (None, ("30/3", 1))])
    monkeypatch.setattr(pc_synthesis, "auto", auto)

    assert pc_synthesis.Synthesis._verify_training_recipe()
    auto.find_element.assert_not_called()


def test_redemption_keeps_confirmed_success_when_mail_fails(monkeypatch):
    auto = Mock(matched_text="兑换成功")
    cfg = Mock(already_used_codes=[])
    monkeypatch.setattr(redemption, "cfg", cfg)
    monkeypatch.setattr(redemption, "auto", auto)
    monkeypatch.setattr(redemption, "get_game_controller", Mock())
    monkeypatch.setattr(redemption, "screen", Mock())
    monkeypatch.setattr(redemption, "time", SimpleNamespace(sleep=Mock()))
    monkeypatch.setattr(redemption.reward, "start_specific", Mock(side_effect=receipt.RewardError("邮件待领取")))

    assert redemption.Redemption.start(codes=["TEST_REDEMPTION"])
    cfg.set_value.assert_called_once_with("already_used_codes", ["TEST_REDEMPTION"])


def test_headless_desktop_extra_is_skipped_in_full_run(monkeypatch):
    monkeypatch.setattr(pc_daily, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(pc_daily, "cfg", SimpleNamespace(control_backend="cloud"))
    monkeypatch.setattr(pc_daily, "cloud_game", Mock(is_headless=Mock(return_value=True)))
    action = Mock()

    assert task_steps.run_steps((("锄大地", lambda: pc_daily._run_desktop_extra("锄大地", action)),))
    action.assert_not_called()


@pytest.mark.parametrize("touch", [False, True])
def test_visible_support_gift_is_used_with_unreadable_title(monkeypatch, touch):
    popup = daily.REWARD_POPUP if touch else "获得物品"
    gift = "./assets/images/share/reward/assist/gift.png"
    auto = Mock(find_element=Mock(side_effect=lambda target, *_args, **_kwargs: BUTTON if target in (gift, popup) else None))
    if touch:
        monkeypatch.setattr(rewards, "auto", auto)
        monkeypatch.setattr(rewards, "screen", Mock())
        monkeypatch.setattr(rewards, "_find_support_gift", Mock(return_value=BUTTON))
        monkeypatch.setattr(rewards, "menu_alert", Mock(return_value=True))
        rewards.claim_assist()
    else:
        monkeypatch.setattr(assist, "auto", auto)
        monkeypatch.setattr(receipt, "auto", auto)
        handler = assist.Assist("支援礼盒", enabled=True, screen="visa")
        monkeypatch.setattr(handler, "prepare", Mock())
        assert handler.start()

    auto.click_element_with_pos.assert_called_once_with(BUTTON)
    assert all(entry.args[0] != "支援角色" for entry in auto.find_element.call_args_list)


@pytest.mark.parametrize("touch", [False, True])
@pytest.mark.parametrize("missing_badge", [False, True])
def test_training_collects_visible_milestones_without_card_name_ocr(monkeypatch, touch, missing_badge):
    module = daily if touch else quest
    auto = Mock()
    frame = Image.new("RGB", (60, 40))
    auto.screenshot = frame
    auto.take_screenshot.return_value = (frame, None, 1)
    monkeypatch.setattr(module, "auto", auto)
    monkeypatch.setattr(module, "cfg", SimpleNamespace(reward_enable=True, reward_quest_enable=True))
    monkeypatch.setattr(module, "screen", Mock())
    monkeypatch.setattr(module, "drag_to_edge", Mock(return_value=True))
    monkeypatch.setattr(module, "drag_list", Mock(return_value=True))
    monkeypatch.setattr(module, "time", SimpleNamespace(sleep=Mock()))
    ocr = Mock()
    monkeypatch.setattr(module, "ocr", ocr)
    notify = Mock()
    monkeypatch.setattr(module, "notify_reward", notify)
    badge = Mock(side_effect=daily.DailyTrainingError("未识别活跃度")) if missing_badge else Mock(return_value=100)

    if touch:
        milestone = Mock(side_effect=[BUTTON] + [None] * 4)
        def find_element(target, *_args, **_kwargs):
            if target.endswith("milestone_ready.png"):
                return milestone()
            return BUTTON if target == daily.REWARD_POPUP else None

        auto.find_element.side_effect = find_element
        monkeypatch.setattr(daily, "read_activity", badge)
        assert daily.run() is not missing_badge
        auto.click_element_with_pos.assert_called_once_with(BUTTON)
    else:
        auto.find_element.return_value = None
        auto.click_element.side_effect = [True, False]
        monkeypatch.setattr(quest.Quest, "activity", badge)
        claim = Mock()
        monkeypatch.setattr(quest, "confirm_item_reward", claim)
        monkeypatch.setattr(quest, "close_item_reward", Mock(return_value=True))
        assert quest.Quest.settle() is not missing_badge
        claim.assert_called_once_with("实训档位奖励")

    ocr.recognize_multi_lines.assert_not_called()
    notify.assert_called_once()


def test_touch_synthesis_preserves_confirmed_result_when_popup_does_not_close(monkeypatch):
    auto = Mock()
    auto.find_element.return_value = BUTTON
    auto.click_element.side_effect = [True, False]
    monkeypatch.setattr(synthesis, "auto", auto)
    monkeypatch.setattr(synthesis, "screen", Mock())
    monkeypatch.setattr(synthesis, "_filter_recipes", Mock())
    monkeypatch.setattr(synthesis, "_read_text", Mock(side_effect=["合成数量：1", "3/3"]))

    assert synthesis.material()

    synthesis.screen.wait_for_screen_change.assert_not_called()
    auto.click_element.assert_called_with(daily.REWARD_CLOSE_CROP, "crop")


def test_touch_training_preserves_confirmed_milestone_when_page_return_fails(monkeypatch):
    auto = Mock()
    auto.find_element.side_effect = [BUTTON, BUTTON]
    screen = Mock()
    screen.wait_for_screen_change.side_effect = RuntimeError("返回实训超时")
    notify = Mock()
    monkeypatch.setattr(daily, "cfg", SimpleNamespace(reward_enable=True, reward_quest_enable=True))
    monkeypatch.setattr(daily, "auto", auto)
    monkeypatch.setattr(daily, "screen", screen)
    monkeypatch.setattr(daily, "time", SimpleNamespace(sleep=Mock()))
    monkeypatch.setattr(daily, "read_activity", Mock(return_value=200))
    monkeypatch.setattr(daily, "scan_cards", Mock(return_value=(200, False, 0, {})))
    monkeypatch.setattr(daily, "notify_reward", notify)

    assert daily.run()

    auto.click_element_with_pos.assert_called_once_with(BUTTON)
    screen.wait_for_screen_change.assert_called_once_with("guide2", max_recursion=0)
    notify.assert_called_once_with(auto, "已领取实训奖励，活跃度 200/500", crop=daily.REWARD_REPORT_CROP)


@pytest.mark.parametrize("failure", [RuntimeError("本地截图失败"), AdbError("frame_timeout", "触屏截图超时")])
def test_receipt_notification_falls_back_to_text_when_a_screenshot_fails(monkeypatch, failure):
    auto = Mock()
    auto.take_screenshot.side_effect = failure
    notify = Mock()
    monkeypatch.setattr(receipt, "auto", auto)
    monkeypatch.setattr(receipt, "notif", SimpleNamespace(notify=notify))

    receipt.confirm_item_reward("邮件奖励", notify=True)

    auto.find_element.assert_called_once()
    notify.assert_called_once_with(content="邮件奖励已领取", level=NotificationLevel.ALL)
