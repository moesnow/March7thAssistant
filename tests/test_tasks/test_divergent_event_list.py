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
    with pytest.raises(RuntimeError, match="确定"):
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
    frames = iter([[first, last], [moved_first, moved_last][:visible_count], []])

    def find(target, *args, **kwargs):
        if target.endswith("event_option.png"):
            return next(frames)

    auto.find_element.side_effect = find
    auto.click_element.side_effect = lambda target, *args, **kwargs: target == "确定"
    obj.reveal_event_confirm = Mock(side_effect=[False, True])
    obj.process_event()
    assert [call.args[0] for call in auto.click_element_with_pos.call_args_list] == [last, moved_first]
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
    with pytest.raises(RuntimeError, match="确定"):
        obj.check_title()
    assert auto.click_element_with_pos.call_count == len(options)
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


def test_successful_input_without_page_progress_has_a_timeout(event):
    obj, auto = event
    auto.find_element.return_value = ((1680, 880), (1730, 910))
    confirmations = 0

    def click(target, *args, **kwargs):
        nonlocal confirmations
        if target == "确定":
            confirmations += 1
            assert confirmations <= 1, "无进展时继续点击，未执行超时检查"
            return True
        return False

    auto.click_element.side_effect = click
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
