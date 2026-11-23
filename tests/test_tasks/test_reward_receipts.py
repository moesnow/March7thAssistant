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
from tasks.reward import assist, dispatch, mail, message, quest, receipt, rewardtemplate, sms
from tasks.touch import daily, rewards, synthesis
from utils.pause import RunStopRequested


BUTTON = ((10, 20), (30, 40))


@pytest.mark.parametrize("entry", ["pc", "touch", "touch_routine"])
@pytest.mark.parametrize("failure, terminal", [
    (RuntimeError("邮箱识别失败"), False),
    (AdbError("frame_timeout", "邮箱截图超时"), False),
    (AdbError("disconnected", "设备已断开"), True),
    (RunStopRequested(), True),
])
def test_mail_failure_isolated_from_later_rewards_and_training(monkeypatch, entry, failure, terminal):
    config = SimpleNamespace(
        reward_enable=True, reward_mail_enable=True, reward_assist_enable=True,
        reward_dispatch_enable=False, reward_srpass_enable=False, reward_message_enable=False,
        reward_achievement_enable=False, reward_quest_enable=True, power_enable=False,
    )
    pages = []
    claims = []

    def change_to(target, **_kwargs):
        if target == "main" and "guide2" not in pages:
            raise RuntimeError("领奖失败后暂时无法直接回到主界面")
        pages.append(target)

    def find(target, *_args, **_kwargs):
        if pages[-1] == "mail":
            raise failure
        return BUTTON

    def click(button):
        claims.append((pages[-1], button))
        return True

    def train(**_kwargs):
        change_to("guide2")
        return True

    screen = SimpleNamespace(change_to=change_to, check_screen=Mock(return_value=False))
    auto = Mock(find_element=Mock(side_effect=find), click_element_with_pos=Mock(side_effect=click))
    warning = Mock()
    monkeypatch.setattr(task_steps, "screen", screen)
    monkeypatch.setattr(task_steps.log, "warning", warning)
    if entry == "pc":
        for module in (reward, rewardtemplate):
            monkeypatch.setattr(module, "screen", screen)
        for module in (mail, assist):
            monkeypatch.setattr(module, "auto", auto)
        monkeypatch.setattr(reward, "cfg", config)
        monkeypatch.setattr(reward, "menu_alert", Mock(return_value=True))
        monkeypatch.setattr(assist, "confirm_item_reward", Mock())
        monkeypatch.setattr(assist, "close_item_reward", Mock())
        monkeypatch.setattr(pc_daily.Daily, "run", train)
        run = pc_daily.Daily.run_standalone
    else:
        monkeypatch.setattr(rewards, "screen", screen)
        monkeypatch.setattr(rewards, "auto", auto)
        monkeypatch.setattr(rewards, "cfg", config)
        monkeypatch.setattr(rewards, "menu_alert", Mock(return_value=True))
        monkeypatch.setattr(rewards, "_find_support_gift", Mock(return_value=BUTTON))
        monkeypatch.setattr(rewards, "_confirm_item_reward", Mock())
        monkeypatch.setattr(rewards, "_close_item_reward", Mock())
        monkeypatch.setattr(daily, "run", train)
        run = rewards.run if entry == "touch" else rewards.routine

    if terminal:
        with pytest.raises(type(failure)) as info:
            run()
        assert info.value is failure
        assert pages == ["menu", "mail"]
        assert not claims
        return

    assert run() is True
    assert pages[:5] == ["menu", "mail", "menu", "visa", "guide2"]
    assert claims == [("visa", BUTTON)]
    assert any("邮件" in args[0] and str(failure) in args[0] for args, _ in warning.call_args_list)


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


@pytest.mark.parametrize("background", [(66, 50, 75), (210, 166, 96)])
def test_pc_mail_recognizes_sparse_gray_text_over_dynamic_background(monkeypatch, background):
    with Image.open("assets/images/zh_CN/reward/mail/receive_all.png") as template:
        strokes = template.convert("L").point(lambda light: 255 if light < 70 else 0)
    image = Image.new("RGB", strokes.size, background)
    image.paste((198, 193, 201), (0, 0), strokes)
    width, height = image.size
    button = ((316, 942), (316 + width, 942 + height))
    auto = Mock(screenshot=image, screenshot_pos=(316, 942, width, height), screenshot_scale_factor=1,
                find_element=Mock(side_effect=[None, button]))
    monkeypatch.setattr(mail, "auto", auto)

    assert mail.Mail("邮件", True, "mail").run() is False
    assert all(match.kwargs["crop"] == mail.RECEIVE_CROP for match in auto.find_element.call_args_list)
    auto.click_element_with_pos.assert_not_called()


@pytest.mark.parametrize("state", ["claim", "running", "panel", "unknown"])
def test_pc_dispatch_waits_for_a_late_claim_button_or_status(monkeypatch, state):
    bottom_frames = 0

    def find_element(target, kind, **kwargs):
        nonlocal bottom_frames
        assert kind == "text"
        if target == "专属材料":
            assert kwargs["max_retries"] == 10
            return None  # 即使标题 OCR 漏识，也继续确认实际委托状态。
        if target == "领取奖励":
            assert kwargs["crop"] == dispatch.RECEIVE_CROP
            bottom_frames += 1
            return BUTTON if state == "claim" and bottom_frames == 10 else None
        if kwargs.get("crop") == dispatch.STATUS_CROP:
            assert target == dispatch.DISPATCH_STATUS
            assert kwargs["max_retries"] > 1
            return BUTTON if state == "panel" else None
        assert target == dispatch.DISPATCH_RUNNING
        assert kwargs["take_screenshot"] is False
        assert kwargs["need_ocr"] is False
        if state == "claim" and bottom_frames == 1:
            return BUTTON if any(label in "未派遣" for label in target) else None
        return BUTTON if state == "running" and bottom_frames == 10 else None

    auto = Mock(find_element=Mock(side_effect=find_element), click_element_with_pos=Mock(return_value=True))
    confirm = Mock()
    close = Mock(return_value=False)
    sleep = Mock()
    monkeypatch.setattr(dispatch, "auto", auto)
    monkeypatch.setattr(dispatch, "confirm_item_reward", confirm)
    monkeypatch.setattr(dispatch, "close_item_reward", close)
    monkeypatch.setattr(dispatch, "time", SimpleNamespace(sleep=sleep))
    monkeypatch.setattr(rewardtemplate, "screen", Mock())
    task = dispatch.Dispatch("委托", True, "dispatch")

    if state == "unknown":
        with pytest.raises(receipt.RewardError, match="未确认委托奖励状态"):
            task.start()
    else:
        assert task.start() is (state == "claim")

    assert bottom_frames == 10
    assert sleep.call_args_list == [call(1)] * 9
    auto.click_element.assert_not_called()
    if state == "claim":
        auto.click_element_with_pos.assert_called_once_with(BUTTON)
        confirm.assert_called_once_with("委托奖励")
        close.assert_called_once_with()
    else:
        auto.click_element_with_pos.assert_not_called()
        confirm.assert_not_called()
        close.assert_not_called()


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


@pytest.mark.parametrize("action_ok", [False, True])
def test_pc_training_does_not_rescan_after_the_last_action_when_collection_is_disabled(monkeypatch, action_ok):
    monkeypatch.setattr(quest, "cfg", SimpleNamespace(reward_enable=False, reward_quest_enable=False))
    monkeypatch.setattr(quest, "screen", Mock())
    scan = Mock(return_value=(400, {"拍照1次": True}, 0))
    monkeypatch.setattr(quest.Quest, "scan", scan)
    photo = Mock(return_value=action_ok)

    assert quest.Quest.settle(complete=True, actions=(("拍照1次", photo),)) is action_ok
    photo.assert_called_once()
    scan.assert_called_once_with(False, read_tasks=True)
    quest.screen.change_to.assert_not_called()


@pytest.mark.parametrize("case", ["milestone", "action_error", "next_action", "return_failed"])
def test_pc_training_returns_to_guide_after_an_action_leaves_the_page(monkeypatch, case):
    config = SimpleNamespace(
        daily_enable=True, daily_material_enable=True, daily_memory_one_enable=False, daily_himeko_try_enable=False,
        reward_enable=True, reward_quest_enable=True, save_timestamp=Mock(),
        notify_template={"DailyPracticeCompleted": "每日实训已完成"},
    )
    page = "guide2"

    def synthesize():
        nonlocal page
        page = "material"
        if case == "action_error":
            raise RuntimeError("合成页面切换失败")
        return False

    def change_page(target, **_kwargs):
        nonlocal page
        assert page == "material"
        if case == "return_failed":
            raise RuntimeError("返回实训页超时")
        page = target

    def photograph():
        assert page == "guide2"
        return True

    def milestone(*_args, **_kwargs):
        assert page == "guide2"
        return BUTTON if auto.click_element_with_pos.call_count == 0 else None

    auto = Mock(find_element=Mock(side_effect=milestone), click_element_with_pos=Mock(return_value=True))
    screen = Mock(change_to=Mock(side_effect=change_page))
    cards = quest.TrainingCards({pc_daily.MATERIAL_TASK: True, "拍照1次": case in ("next_action", "return_failed")})
    scan = Mock(side_effect=[(400, cards, 1), (500, quest.TrainingCards({}), 1)])
    synthesize = Mock(side_effect=synthesize)
    photograph = Mock(side_effect=photograph)
    confirm = Mock()
    notify = Mock()
    monkeypatch.setattr(pc_daily, "cfg", config)
    monkeypatch.setattr(pc_daily.Synthesis, "material", synthesize)
    monkeypatch.setattr(pc_daily.Photo, "photograph", photograph)
    monkeypatch.setattr(quest, "cfg", config)
    monkeypatch.setattr(quest, "auto", auto)
    monkeypatch.setattr(quest, "screen", screen)
    monkeypatch.setattr(quest.Quest, "scan", scan)
    monkeypatch.setattr(quest, "confirm_item_reward", confirm)
    monkeypatch.setattr(quest, "close_item_reward", Mock(return_value=True))
    monkeypatch.setattr(quest, "notify_reward", notify)
    monkeypatch.setattr(quest, "time", SimpleNamespace(sleep=Mock()))

    assert pc_daily.Daily.run() is (case == "next_action")

    synthesize.assert_called_once_with()
    screen.change_to.assert_called_once_with("guide2", max_recursion=1)
    if case == "next_action":
        photograph.assert_called_once_with()
        assert scan.call_args_list == [call(True, read_tasks=True), call(True, read_tasks=False)]
        config.save_timestamp.assert_called_once_with("last_run_timestamp")
        notify.assert_called_once_with(auto, "每日实训已完成")
    else:
        photograph.assert_not_called()
        scan.assert_called_once_with(True, read_tasks=True)
        config.save_timestamp.assert_not_called()
        notify.assert_called_once_with(auto, "已领取实训奖励，活跃度 400/500")
    if case == "return_failed":
        auto.find_element.assert_not_called()
        auto.click_element_with_pos.assert_not_called()
        confirm.assert_not_called()
    else:
        auto.click_element_with_pos.assert_called_once_with(BUTTON)
        confirm.assert_called_once_with("实训档位奖励")


def test_pc_training_reports_pending_claim_failure_without_repeating_the_completed_action(monkeypatch):
    monkeypatch.setattr(quest, "cfg", SimpleNamespace(reward_enable=True, reward_quest_enable=True))
    monkeypatch.setattr(quest, "auto", Mock(find_element=Mock(return_value=None)))
    monkeypatch.setattr(quest, "screen", Mock())
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
    # 平台判断在完整运行计划里（module.overview.plan），这里固定为 Windows。
    monkeypatch.setattr(pc_daily.plan, "sys", SimpleNamespace(platform="win32"))
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
@pytest.mark.parametrize("badge_error", [
    None, daily.DailyTrainingError("未识别活跃度"), RuntimeError("徽标 OCR 异常"),
    AdbError("invalid_response", "实训徽标截图数据无效", frame_only=True),
])
def test_training_collects_visible_milestones_without_card_name_ocr(monkeypatch, touch, badge_error):
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
    badge = Mock(side_effect=badge_error, return_value=100)

    milestone = Mock(side_effect=[BUTTON, None])

    def find_element(target, *_args, **_kwargs):
        if target == module.RECEIVE_MILESTONE:
            return milestone()
        return BUTTON if touch and target == daily.REWARD_POPUP else None

    auto.find_element.side_effect = find_element
    if touch:
        monkeypatch.setattr(daily, "read_activity", badge)
        assert daily.run() is (badge_error is None)
    else:
        monkeypatch.setattr(quest.Quest, "activity", badge)
        claim = Mock()
        monkeypatch.setattr(quest, "confirm_item_reward", claim)
        monkeypatch.setattr(quest, "close_item_reward", Mock(return_value=True))
        assert quest.Quest.settle() is (badge_error is None)
        claim.assert_called_once_with("实训档位奖励")

    auto.click_element_with_pos.assert_called_once_with(BUTTON)
    if badge_error is not None:
        module.screen.change_to.assert_called_with("guide2", max_recursion=1)
    ocr.recognize_multi_lines.assert_not_called()
    notify.assert_called_once()


@pytest.mark.parametrize("touch, expected_crop", [
    (False, (415 / 1920, 270 / 1080, 1252 / 1920, 114 / 1080)),
    (True, (551 / 1920, 237 / 1080, 1193 / 1920, 84 / 1080)),
])
def test_training_waits_for_initial_milestone_after_activity_is_full(monkeypatch, touch, expected_crop):
    module = daily if touch else quest
    frames = iter([None, None, BUTTON, None])
    budgets = []

    def find(target, kind, threshold, *, max_retries, crop, **_kwargs):
        if touch and target == daily.REWARD_POPUP:
            return BUTTON
        assert (target, kind, threshold) == (module.RECEIVE_MILESTONE, "image", 0.9)
        assert crop == expected_crop
        budgets.append(max_retries)
        return next((button for _ in range(max_retries) if (button := next(frames, None))), None)

    auto = Mock(find_element=Mock(side_effect=find), click_element_with_pos=Mock(return_value=True))
    cfg = SimpleNamespace(reward_enable=True, reward_quest_enable=True, save_timestamp=Mock(),
                          notify_template={"DailyPracticeCompleted": "每日实训已完成"})
    monkeypatch.setattr(module, "auto", auto)
    monkeypatch.setattr(module, "cfg", cfg)
    monkeypatch.setattr(module, "screen", Mock())
    monkeypatch.setattr(module, "time", SimpleNamespace(sleep=Mock()))
    monkeypatch.setattr(module, "notify_reward", Mock())
    if touch:
        monkeypatch.setattr(daily, "read_activity", Mock(return_value=500))
        assert daily.run()
        auto.click_element.assert_called_once_with(daily.REWARD_CLOSE_CROP, "crop")
    else:
        claim = Mock()
        monkeypatch.setattr(quest.Quest, "activity", Mock(return_value=500))
        monkeypatch.setattr(quest, "confirm_item_reward", claim)
        monkeypatch.setattr(quest, "close_item_reward", Mock(return_value=True))
        assert quest.Quest.settle()
        claim.assert_called_once_with("实训档位奖励")

    assert budgets == [10, 1]
    auto.click_element_with_pos.assert_called_once_with(BUTTON)
    cfg.save_timestamp.assert_called_once_with("last_run_timestamp")


@pytest.mark.parametrize("touch", [False, True])
def test_training_retains_completed_activity_after_missing_reward_receipt(monkeypatch, touch):
    module = daily if touch else quest
    config = SimpleNamespace(reward_enable=True, reward_quest_enable=True, save_timestamp=Mock())
    auto = Mock(find_element=Mock(side_effect=[BUTTON, None]), click_element_with_pos=Mock(return_value=True))
    warning = Mock()
    monkeypatch.setattr(module, "cfg", config)
    monkeypatch.setattr(module, "auto", auto)
    monkeypatch.setattr(module, "screen", Mock())
    monkeypatch.setattr(task_steps.log, "warning", warning)

    if touch:
        monkeypatch.setattr(daily, "read_activity", Mock(return_value=500))
        run = daily.run
    else:
        monkeypatch.setattr(quest.Quest, "activity", Mock(return_value=500))
        monkeypatch.setattr(quest, "confirm_item_reward", Mock(side_effect=receipt.RewardError("未出现获得物品")))
        run = quest.Quest.settle

    later = Mock()
    assert task_steps.run_steps((("每日实训", run), ("后续任务", later))) is True
    config.save_timestamp.assert_called_once_with("last_run_timestamp")
    auto.click_element_with_pos.assert_called_once_with(BUTTON)
    later.assert_called_once_with()
    assert any("档位奖励" in args[0] for args, _ in warning.call_args_list)


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


@pytest.mark.parametrize("close_sent", [False, True, None])
def test_touch_training_preserves_confirmed_milestone_when_popup_does_not_close(monkeypatch, close_sent):
    auto = Mock()
    auto.find_element.side_effect = [BUTTON, BUTTON]
    auto.click_element.return_value = close_sent
    if close_sent is None:
        auto.click_element.side_effect = RuntimeError("关闭获得物品弹窗时截图失败")
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
    assert screen.wait_for_screen_change.call_count == int(bool(close_sent))
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
