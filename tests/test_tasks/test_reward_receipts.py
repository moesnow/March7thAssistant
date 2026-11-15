from time import monotonic
from types import SimpleNamespace
from unittest.mock import Mock, call

from PIL import Image
import pytest

from module.game.adb_transport import AdbError
from module.notification.notification import NotificationLevel
from tasks import reward
from tasks.base import task_steps
from tasks.reward import assist, quest, receipt, rewardtemplate
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
    popup = Mock(side_effect=(BUTTON, None))
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

    popup.assert_called_once()
    auto.click_element.assert_called_once_with(daily.REWARD_CLOSE_CROP, "crop")
    notify.assert_called_once_with(auto, "处理了 1 个短信会话，领取 1 次奖励")


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
