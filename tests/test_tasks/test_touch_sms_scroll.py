"""短信联系人展开后的分页扫描，走实际任务、查找和拖动流程。"""
from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image
import pytest

from module.automation.input_base import begin_input_dispatch, limit_input_deadline
from tasks.base import list_drag
from tasks.touch import daily, rewards
from utils.pause import RunStopRequested


CONTACT = ((91, 110), (109, 130))
THREAD = ((67, 400), (89, 420))
PENDING = ((67, 200), (89, 220))


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class MessageList:
    """只替换设备画面和输入；每次识别均读取当前列表页。"""

    def __init__(self, clock, target_page=2, bottom=2, miss_first=False, stop_after_drag=False):
        self.clock = clock
        self.target_page = target_page
        self.bottom = bottom
        self.miss_first = miss_first
        self.stop_after_drag = stop_after_drag
        self.page = 0
        self.current = "丹恒"
        self.expanded = False
        self.hidden_done = False
        self.popup = False
        self.finished = []
        self.inputs = []
        self.drags = 0
        self.marker_misses = 0
        self.screenshot = self.frame()

    def frame(self):
        shade = 40 * (self.page % 5)
        return Image.new("RGB", (371, 516), (shade, shade, shade))

    def take_screenshot(self, **_kwargs):
        if self.stop_after_drag and self.drags:
            raise RunStopRequested()
        self.screenshot = self.frame()
        return self.screenshot, (40, 92, *self.screenshot.size), 1

    def find_element(self, target, _mode, *_args, **kwargs):
        for attempt in range(kwargs.get("max_retries", 1)):
            found = None
            if target == daily.REWARD_POPUP:
                found = THREAD if self.popup else None
            elif target.endswith("message_pending.png"):
                found = PENDING if self.current is not None else None
            elif target.endswith("message_thread.png"):
                if self.expanded and not self.hidden_done and self.page == self.target_page:
                    if self.miss_first and self.marker_misses == 0:
                        self.marker_misses += 1
                    else:
                        found = THREAD
            elif target.endswith("message_alert.png"):
                found = CONTACT if self.page == 0 and not self.hidden_done else None
            else:
                raise AssertionError(target)
            if found:
                return found
            if attempt + 1 < kwargs.get("max_retries", 1):
                self.clock.sleep(kwargs.get("retry_delay", 1))
        return None

    def click_element_with_pos(self, target, **_kwargs):
        if not begin_input_dispatch(self.clock.monotonic()):
            return False
        self.inputs.append(("click", target))
        if target == CONTACT:
            self.expanded = True
        elif target == THREAD:
            self.current = "三月七"
        else:
            raise AssertionError(target)
        return True

    def click_element(self, target, mode, **_kwargs):
        assert target == daily.REWARD_CLOSE_CROP and mode == "crop"
        self.popup = False
        return True

    def drag_mouse(self, _start, _end, _duration, _end_pause):
        if not begin_input_dispatch(self.clock.monotonic()):
            return False
        self.inputs.append(("drag", self.page))
        self.drags += 1
        self.page = min(self.bottom, self.page + 1)
        return True

    def finish(self):
        assert self.current is not None
        self.finished.append(self.current)
        if self.current == "三月七":
            self.hidden_done = True
        self.current = None
        self.popup = True
        return True


@pytest.fixture
def sms_page(monkeypatch):
    clock = Clock()
    notify = Mock()
    monkeypatch.setattr(rewards, "screen", Mock())
    monkeypatch.setattr(rewards, "time", clock)
    monkeypatch.setattr(list_drag, "time", clock)
    monkeypatch.setattr(rewards, "notify_reward", notify)

    def close_receipt(close, visible):
        return close() is not False and not visible()

    monkeypatch.setattr(rewards, "close_sms_receipt", close_receipt)

    def create(**kwargs):
        auto = MessageList(clock, **kwargs)
        monkeypatch.setattr(rewards, "auto", auto)
        monkeypatch.setattr(rewards, "_finish_message", auto.finish)
        return auto, notify, clock

    return create


@pytest.mark.parametrize("target_page", [1, 2])
@pytest.mark.parametrize("miss_first", [False, True])
def test_sms_scrolls_past_expanded_contact_and_keeps_claimed_rewards(sms_page, target_page, miss_first):
    auto, notify, _clock = sms_page(target_page=target_page, miss_first=miss_first)

    rewards.claim_messages()

    assert auto.finished == ["丹恒", "三月七"]
    assert ("click", THREAD) in auto.inputs
    assert auto.drags == 3  # 找到第二项后，再以一次稳定的底部画面结束。
    assert auto.marker_misses == int(miss_first)
    notify.assert_called_once_with(auto, "处理了 2 个短信会话，领取 2 次奖励")


def test_sms_keeps_unresolved_contact_failure_after_reaching_the_bottom(sms_page):
    auto, notify, _clock = sms_page(target_page=None)

    with pytest.raises(rewards.RewardError, match="联系人有红点"):
        rewards.claim_messages()

    assert auto.drags == 3
    assert auto.finished == ["丹恒"]
    notify.assert_called_once_with(auto, "处理了 1 个短信会话，领取 1 次奖励")


def test_sms_contact_search_has_a_shared_drag_limit(sms_page):
    auto, _notify, _clock = sms_page(target_page=None, bottom=20)

    with pytest.raises(rewards.RewardError, match="联系人有红点"):
        rewards.claim_messages()

    assert auto.drags == 4
    assert [target for kind, target in auto.inputs if kind == "click"] == [CONTACT]


def test_stop_while_waiting_for_the_scrolled_frame_sends_no_further_input(sms_page):
    auto, notify, _clock = sms_page(stop_after_drag=True)

    with pytest.raises(RunStopRequested):
        rewards.claim_messages()

    assert auto.drags == 1
    assert auto.inputs == [("click", CONTACT), ("drag", 0)]
    notify.assert_called_once_with(auto, "处理了 1 个短信会话，领取 1 次奖励")


def test_deadline_during_marker_retries_prevents_contact_click(sms_page):
    auto, notify, clock = sms_page()
    auto.current = None

    with limit_input_deadline(clock.monotonic() + 0.5):
        with pytest.raises(rewards.RewardError, match="无法展开"):
            rewards.claim_messages()

    assert not auto.inputs
    assert auto.drags == 0
    notify.assert_not_called()
