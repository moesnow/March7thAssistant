from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image
import pytest

from tasks.base import list_drag
from tasks.weekly import divergent_universe as module


def setup_list(monkeypatch, visible, completed=True):
    auto = Mock()
    auto.find_element.side_effect = visible
    drag = auto.drag_mouse
    drag.return_value = completed
    monkeypatch.setattr(module, "auto", auto)
    monkeypatch.setattr(module, "time", SimpleNamespace(sleep=Mock()))
    return auto, drag


def test_visible_confirmation_does_not_drag_or_click(monkeypatch):
    auto, drag = setup_list(monkeypatch, [True])
    assert module.DivergentUniverse.reveal_event_confirm()
    drag.assert_not_called()
    auto.click_element.assert_not_called()


def test_confirmation_is_checked_after_last_allowed_drag(monkeypatch):
    auto, drag = setup_list(monkeypatch, [False] * 6 + [True])
    assert module.DivergentUniverse.reveal_event_confirm()
    assert drag.call_count == 6
    for call in drag.call_args_list:
        start, end = call.args
        x, y, width, height = (1320 / 1920, 170 / 1080, 515 / 1920, 765 / 1080)
        assert all(x < px < x + width and y < py < y + height for px, py in (start, end))
        assert start[1] > end[1]
        assert call.kwargs["end_pause"] > 0
    auto.click_element.assert_not_called()


def test_missing_confirmation_stops_at_limit(monkeypatch):
    auto, drag = setup_list(monkeypatch, [False] * 7)
    assert module.DivergentUniverse.reveal_event_confirm() is False
    assert drag.call_count == 6
    auto.click_element.assert_not_called()


def test_interrupted_drag_does_not_replay_or_confirm(monkeypatch):
    auto, drag = setup_list(monkeypatch, [False], completed=False)
    with pytest.raises(RuntimeError, match="拖动中断"):
        module.DivergentUniverse.reveal_event_confirm()
    drag.assert_called_once()
    auto.take_screenshot.assert_called_once()
    auto.click_element.assert_not_called()


def test_event_does_not_confirm_after_failed_reveal(monkeypatch):
    auto = Mock()
    auto.click_element.return_value = False
    auto.find_element.side_effect = lambda target, *args, **kwargs: (
        [((1360, 782), (1381, 807))] if target.endswith("event_option.png") else None)
    monkeypatch.setattr(module, "auto", auto)
    monkeypatch.setattr(module, "time", SimpleNamespace(sleep=Mock(), monotonic=Mock(return_value=0)))
    obj = module.DivergentUniverse()
    obj.reveal_event_confirm = Mock(return_value=False)
    with pytest.raises(RuntimeError, match="无法确认"):
        obj.process_event()
    assert all(call.args[0] != "确定" for call in auto.click_element.call_args_list)


@pytest.mark.parametrize("text,bottom", [("确定 E", 910), ("确定", 970)])
def test_reveal_accepts_confirmation_supported_by_the_existing_click(monkeypatch, text, bottom):
    auto = Mock()

    def find(target, find_type, crop=(0, 0, 1, 1), include=False, **kwargs):
        matches = target in text if include else target == text
        if matches and (crop[1] + crop[3]) * 1080 >= bottom:
            return ((1680, bottom - 30), (1730, bottom))

    auto.find_element.side_effect = find
    monkeypatch.setattr(module, "auto", auto)
    monkeypatch.setattr(module, "time", SimpleNamespace(sleep=Mock()))
    assert module.DivergentUniverse.reveal_event_confirm()
    auto.drag_mouse.assert_not_called()


def test_animated_background_does_not_hide_a_revealed_confirmation(monkeypatch):
    auto = Mock()
    auto.find_element.side_effect = [None, ((1680, 880), (1730, 910))]
    auto.drag_mouse.return_value = True
    frames = iter(Image.new("RGB", (30, 40), color) for color in ["black", "white"] * 9)
    auto.take_screenshot.side_effect = lambda **kwargs: (next(frames), (0, 0), 1)
    monkeypatch.setattr(module, "auto", auto)
    monkeypatch.setattr(module, "time", SimpleNamespace(sleep=Mock()))
    monkeypatch.setattr(list_drag, "time", SimpleNamespace(sleep=Mock()))
    assert module.DivergentUniverse.reveal_event_confirm()


@pytest.fixture
def event(monkeypatch):
    auto = Mock()
    auto.ocr_result = []
    auto.screenshot = Image.new("RGB", (1920, 1080), "black")
    auto.click_element.return_value = False
    auto.click_element_with_pos.return_value = True
    auto.find_element.return_value = []
    monkeypatch.setattr(module, "auto", auto)
    monkeypatch.setattr(module, "time", SimpleNamespace(sleep=Mock(), monotonic=Mock(return_value=0)))
    return module.DivergentUniverse(), auto


@pytest.mark.parametrize("visible_count", [1, 2])
def test_unavailable_option_falls_back_using_fresh_positions(event, visible_count):
    obj, auto = event
    first, last = ((1360, 450), (1380, 470)), ((1360, 780), (1380, 800))
    moved_first, moved_last = ((1360, 250), (1380, 270)), ((1360, 580), (1380, 600))
    frames = iter([[first, last]] * 2 + [[moved_first, moved_last][:visible_count]] * visible_count + [[]])
    expected = [last, moved_first] if visible_count == 1 else [last, moved_last, moved_first]

    def find(target, *args, **kwargs):
        if target.endswith("event_option.png"):
            return next(frames)

    auto.find_element.side_effect = find
    auto.click_element.side_effect = lambda target, *args, **kwargs: target == "确定"
    obj.reveal_event_confirm = Mock(side_effect=[False] * (len(expected) - 1) + [True])
    obj.process_event()
    assert [call.args[0] for call in auto.click_element_with_pos.call_args_list] == expected
    assert sum(call.args[0] == "确定" for call in auto.click_element.call_args_list) == 1


def test_existing_selection_is_confirmed_before_choosing_another_option(event):
    obj, auto = event
    confirmation = ((1680, 880), (1730, 910))
    pending = True

    def find(target, *args, **kwargs):
        if target == "确定" and pending:
            return confirmation
        if target.endswith("event_option.png"):
            return [((1360, 780), (1380, 800))] if pending else []

    def click(target, *args, **kwargs):
        nonlocal pending
        if target == "确定":
            pending = False
            return True
        return False

    auto.find_element.side_effect = find
    auto.click_element.side_effect = click
    obj.reveal_event_confirm = Mock(return_value=True)
    obj.process_event()
    auto.click_element_with_pos.assert_not_called()


def test_exhausted_options_propagate_failure_through_title_dispatch(event):
    obj, auto = event
    options = [((1360, y), (1380, y + 20)) for y in (250, 450, 650)]

    def find(target, *args, **kwargs):
        if isinstance(target, tuple):
            auto.matched_text = "事件"
            return True
        if target.endswith("event_option.png"):
            return options

    auto.find_element.side_effect = find
    obj.reveal_event_confirm = Mock(return_value=False)
    with pytest.raises(RuntimeError, match="无法确认"):
        obj.check_title()
    assert auto.click_element_with_pos.call_count == len(options) + 1
    assert all(call.args[0] != "确定" for call in auto.click_element.call_args_list)


@pytest.mark.parametrize("failed_action", ["option", "confirmation"])
def test_failed_click_stops_without_selecting_another_option(event, failed_action):
    obj, auto = event
    options = [((1360, 450), (1380, 470)), ((1360, 780), (1380, 800))]
    auto.find_element.side_effect = lambda target, *args, **kwargs: options if target.endswith("event_option.png") else None
    auto.click_element_with_pos.return_value = failed_action != "option"
    obj.reveal_event_confirm = Mock(return_value=True)
    with pytest.raises(RuntimeError, match="点击失败"):
        obj.process_event()
    auto.click_element_with_pos.assert_called_once_with(options[-1])


def test_repeated_dialogue_without_page_progress_has_a_timeout(event):
    obj, auto = event
    auto.click_element.side_effect = lambda target, *args, **kwargs: target.endswith("event_next.png")
    module.time.monotonic.side_effect = [0, 1, 121]
    with pytest.raises(RuntimeError, match="超时"):
        obj.process_event()
    auto.click_element_with_pos.assert_not_called()


@pytest.mark.parametrize("options", [None, []])
def test_non_option_page_returns_without_confirmation_or_drag(event, options):
    obj, auto = event
    auto.find_element.side_effect = lambda target, *args, **kwargs: (
        options if target.endswith("event_option.png") else ((1680, 880), (1730, 910)))
    obj.process_event()
    auto.click_element_with_pos.assert_not_called()
    auto.drag_mouse.assert_not_called()
    assert all(call.args[0] != "确定" for call in auto.click_element.call_args_list)


def test_normal_event_dialogue_and_multiple_selection_pages(event):
    obj, auto = event
    option = ((1360, 780), (1380, 800))
    steps = iter(["event_next.png", "event_choose.png", "options", "options", "event_leave.png", "done"])
    step = ""

    def sleep(seconds):
        nonlocal step
        if seconds == 1:
            step = next(steps)

    def click(target, *args, **kwargs):
        if target == "确定":
            return step == "options"
        return target.endswith(step)

    auto.click_element.side_effect = click
    auto.find_element.side_effect = lambda target, *args, **kwargs: (
        [option] if target.endswith("event_option.png") and step == "options" else None)
    module.time.sleep.side_effect = sleep
    obj.reveal_event_confirm = Mock(return_value=True)
    obj.process_event()
    assert auto.click_element_with_pos.call_count == 2
    assert sum(call.args[0] == "确定" for call in auto.click_element.call_args_list) == 2


class FragmentEvent:
    """只模拟事件选项的余额条件和界面反馈，不连接游戏。"""

    def __init__(self, costs, balance=0, disabled_confirm=False, visible=None, after_drag=None):
        self.costs = costs
        self.balance = balance
        self.disabled_confirm = disabled_confirm
        self.visible = list(range(len(costs))) if visible is None else visible
        self.after_drag = self.visible if after_drag is None else after_drag
        self.selected = None
        self.choices = []
        self.confirmed = []
        self.confirm_clicks = 0
        self.elapsed = 0
        self.drags = 0
        self.done = False
        self.screenshot = Image.new("RGB", (1920, 1080), "black")
        self.ocr_result = []

    def positions(self):
        return [((1360, 220 + row * 210), (1380, 240 + row * 210)) for row in range(len(self.visible))]

    def find_element(self, target, *args, **kwargs):
        self.ocr_result = [
            ([(1400, 200), (1800, 200), (1800, 230), (1400, 230)],
             (f"宇宙碎片 {self.balance}，选项 {self.selected}，费用 {self.costs}", 1.0))]
        if self.done:
            return []
        if isinstance(target, tuple):
            self.matched_text = "事件"
            return ((96, 63), (238, 97))
        if target.endswith("event_option.png"):
            return self.positions()
        if target == "确定" and self.selected is not None:
            if self.balance >= self.costs[self.selected] or self.disabled_confirm:
                return ((1680, 880), (1730, 910))
        return None

    def click_element_with_pos(self, coordinates):
        assert coordinates in self.positions(), "点击了已经失效的选项坐标"
        self.selected = self.visible[self.positions().index(coordinates)]
        self.choices.append(self.selected)
        assert len(self.choices) <= 12, "事件在不可用选项之间无限重试"
        return True

    def click_element(self, target, *args, **kwargs):
        if target != "确定" or not self.find_element(target):
            return False
        self.confirm_clicks += 1
        # 与真实输入层一致，发出了点击不代表按钮生效。
        if self.balance >= self.costs[self.selected]:
            self.balance -= self.costs[self.selected]
            self.confirmed.append(self.selected)
            self.done = True
        return True

    def drag_mouse(self, *args, **kwargs):
        self.drags += 1
        self.visible = self.after_drag
        return True

    def take_screenshot(self, **kwargs):
        return self.screenshot, (0, 0), 1

    def sleep(self, seconds):
        self.elapsed += seconds


def use_fragment_event(monkeypatch, game):
    monkeypatch.setattr(module, "auto", game)
    monkeypatch.setattr(module, "time", SimpleNamespace(sleep=game.sleep, monotonic=lambda: game.elapsed))
    return module.DivergentUniverse()


@pytest.mark.parametrize("balance,expected", [(0, 0), (50, 0), (100, 1), (200, 2)])
@pytest.mark.parametrize("disabled_confirm", [False, True])
def test_fragment_balance_selects_an_affordable_option(monkeypatch, balance, expected, disabled_confirm):
    game = FragmentEvent([0, 100, 200], balance, disabled_confirm)
    obj = use_fragment_event(monkeypatch, game)
    obj.process_event()
    assert game.done
    assert game.confirmed == [expected]
    assert game.balance == balance - game.costs[expected]
    assert len(game.choices) <= len(game.costs) + 1


def test_scrolling_past_unavailable_options_can_reveal_a_free_option(monkeypatch):
    game = FragmentEvent([100, 200, 0], visible=[0, 1], after_drag=[1, 2])
    obj = use_fragment_event(monkeypatch, game)
    obj.process_event()
    assert game.done
    assert game.confirmed == [2]
    assert game.drags > 0


@pytest.mark.parametrize("disabled_confirm", [False, True])
def test_no_affordable_option_stops_title_dispatch(monkeypatch, disabled_confirm):
    game = FragmentEvent([100, 200, 300], balance=50, disabled_confirm=disabled_confirm)
    obj = use_fragment_event(monkeypatch, game)
    with pytest.raises(RuntimeError, match="确认|确定"):
        obj.check_title()
    assert game.confirmed == []
    assert game.balance == 50
    assert set(game.choices) == {0, 1, 2}
    assert len(game.choices) <= 4
    assert game.confirm_clicks <= 4


def test_preselected_unaffordable_option_does_not_block_a_free_option(monkeypatch):
    game = FragmentEvent([0, 100, 200], disabled_confirm=True)
    game.selected = 2
    obj = use_fragment_event(monkeypatch, game)
    obj.process_event()
    assert game.confirmed == [0]
    assert len(game.choices) <= 4


def test_consecutive_event_pages_with_the_same_layout_are_not_unavailable(monkeypatch):
    game = FragmentEvent([0])
    obj = use_fragment_event(monkeypatch, game)
    click = game.click_element

    def next_page(target, *args, **kwargs):
        result = click(target, *args, **kwargs)
        if game.done and len(game.confirmed) == 1:
            game.done = False
            game.costs = [10]
            game.balance = 10
            game.selected = 0
        return result

    game.click_element = next_page
    obj.process_event()
    assert game.confirmed == [0, 0]
    assert game.choices == [0]


def test_changing_text_outside_options_is_not_confirmation_progress(monkeypatch):
    game = FragmentEvent([0, 100, 200], disabled_confirm=True)
    obj = use_fragment_event(monkeypatch, game)
    find = game.find_element
    frames = 0

    def animated_background(target, *args, **kwargs):
        nonlocal frames
        result = find(target, *args, **kwargs)
        frames += 1
        game.ocr_result.append(([(100, 800), (300, 800), (300, 830), (100, 830)], (f"背景字符{frames}", 0.8)))
        return result

    game.find_element = animated_background
    obj.process_event()
    assert game.confirmed == [0]


def test_one_missed_confirmation_frame_does_not_report_progress(event):
    obj, auto = event
    confirmation = ((1680, 880), (1730, 910))
    auto.find_element.side_effect = [None, confirmation, confirmation, confirmation]
    auto.click_element.return_value = True
    assert obj.confirm_event_option() is False
    auto.click_element.assert_called_once()
