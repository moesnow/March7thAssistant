from collections import deque
from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image
import pytest

from tasks.base import list_drag


CROP = (0.1, 0.2, 0.3, 0.4)
START, END = (0.2, 0.7), (0.2, 0.3)


class ListScreen:
    def __init__(self, frames, completed=True):
        self.frames = deque(Image.new("RGB", (30, 40), color) for color in frames)
        self.screenshot = None
        self.crops = []
        self.completed = completed
        self.drags = 0

    def drag_mouse(self, *args):
        self.drags += 1
        self.screenshot = Image.new("RGB", (192, 108), "red")
        return self.completed

    def take_screenshot(self, crop):
        self.crops.append(crop)
        if len(self.frames) > 1:
            self.screenshot = self.frames.popleft()
        else:
            self.screenshot = self.frames[0]
        self.screenshot_pos = crop
        return self.screenshot, crop, 1


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    monkeypatch.setattr(list_drag, "time", SimpleNamespace(sleep=Mock()))


def test_waits_through_inertia_and_restores_cropped_cache():
    auto = ListScreen(["black", "white", "black", "white", "white", "white"])
    assert list_drag.drag_list(auto, START, END, crop=CROP)
    assert len(auto.crops) == 6
    assert auto.screenshot.size == (30, 40)
    assert auto.screenshot.getpixel((0, 0)) == (255, 255, 255)
    assert auto.screenshot_pos == CROP
    assert auto.crops == [CROP] * 6
    assert list_drag.time.sleep.call_args_list[0].args == (1.0,)


def test_fast_list_pause_and_polling_preserve_stability_checks():
    auto = ListScreen(["black"])
    auto.drag_mouse = Mock(wraps=auto.drag_mouse)
    assert list_drag.drag_list(auto, START, END, crop=CROP, duration=0.4, end_pause=0.25,
                              settle=0.05, poll_interval=0.1)
    auto.drag_mouse.assert_called_once_with(START, END, 0.4, 0.25)
    assert [call.args[0] for call in list_drag.time.sleep.call_args_list] == [0.05, 0.1, 0.1]


def test_partial_drag_refreshes_but_never_reports_success_or_replays():
    auto = ListScreen(["black", "white", "white", "white"], completed=False)
    assert list_drag.drag_list(auto, START, END, crop=CROP) is False
    assert auto.drags == 1
    assert auto.screenshot.getpixel((0, 0)) == (255, 255, 255)


def test_scene_that_keeps_moving_stops_at_limit():
    auto = ListScreen(["black", "white"] * 10)
    assert list_drag.drag_list(auto, START, END, crop=CROP) is False
    assert len(auto.crops) == 17


@pytest.mark.parametrize("offsets,expected", [([20, 10, 0, 0, 0], True), ([20, 10] * 8, False), ([None] * 16, False)])
def test_level_numbers_must_settle_even_with_an_animated_background(offsets, expected):
    auto = ListScreen(["black", "white"] * 10)
    positions = iter(offsets)

    def ocr():
        offset = next(positions)
        auto.ocr_result = [] if offset is None else [
            ([(offset, 0), (offset + 4, 0), (offset + 4, 5), (offset, 5)], ("01", 1.0))]

    auto.perform_ocr = ocr
    assert list_drag.drag_list(auto, START, END, crop=CROP, text_pattern=r"\d{2}") is expected


@pytest.mark.parametrize("last_page,limit,expected,drags", [(3, 8, True, 5), (20, 4, False, 4)])
def test_edge_requires_unchanged_pages_and_has_a_limit(last_page, limit, expected, drags):
    auto = ListScreen(["black"])

    def drag(*args):
        auto.drags += 1
        shade = min(auto.drags, last_page) * 40
        auto.frames = deque([Image.new("RGB", (30, 40), (shade, shade, shade))])
        return True

    auto.drag_mouse = drag
    assert list_drag.drag_to_edge(auto, START, END, crop=CROP, max_drags=limit) is expected
    assert auto.drags == drags


def test_interrupted_edge_search_does_not_continue():
    auto = ListScreen(["black", "white"], completed=False)
    assert list_drag.drag_to_edge(auto, START, END, crop=CROP) is False
    assert auto.drags == 1


def test_memory_first_level_is_checked_after_the_last_allowed_group(monkeypatch):
    from tasks.challenge import memoryone

    calls = []
    auto = SimpleNamespace(find_element=lambda *args, **kwargs: len(calls) == 4,
                           drag_mouse=lambda *args, **kwargs: calls.append(kwargs) or True)
    monkeypatch.setattr(memoryone, "auto", auto)
    assert memoryone.MemoryOne.scroll_to_first_level()
    assert len(calls) == 4 and all(call["repeats"] == 3 for call in calls)


def test_memory_checks_once_after_each_drag_group(monkeypatch):
    from tasks.challenge import memoryone

    events = []

    def find(*args, **kwargs):
        assert kwargs.get("take_screenshot", True) and kwargs.get("need_ocr", True)
        events.append("check")
        return "drag" in events

    def drag(*args, **kwargs):
        assert kwargs["repeats"] == 3
        events.extend(["drag"] * 3)
        return True

    monkeypatch.setattr(memoryone, "auto", SimpleNamespace(find_element=find, drag_mouse=drag))
    assert memoryone.MemoryOne.scroll_to_first_level()
    assert events == ["check", "drag", "drag", "drag", "check"]


def test_memory_missing_first_level_has_a_group_limit(monkeypatch):
    from tasks.challenge import memoryone

    auto = Mock()
    auto.find_element.return_value = False
    auto.drag_mouse.return_value = True
    monkeypatch.setattr(memoryone, "auto", auto)
    assert memoryone.MemoryOne.scroll_to_first_level() is False
    assert auto.drag_mouse.call_count == 4
    assert auto.find_element.call_count == 5


def test_memory_already_at_first_level_does_not_drag(monkeypatch):
    from tasks.challenge import memoryone

    auto = Mock()
    auto.find_element.return_value = True
    monkeypatch.setattr(memoryone, "auto", auto)
    assert memoryone.MemoryOne.scroll_to_first_level()
    auto.drag_mouse.assert_not_called()
    auto.find_element.assert_called_once()


def test_memory_first_level_interruption_does_not_open_a_stage(monkeypatch):
    from tasks.challenge import memoryone

    auto = Mock()
    auto.find_element.return_value = False
    monkeypatch.setattr(memoryone, "auto", auto)
    auto.drag_mouse.return_value = False
    obj = memoryone.MemoryOne([])
    obj.start_challenge = Mock()
    assert obj.start_challenges() is False
    assert obj.success is False
    obj.start_challenge.assert_not_called()
    auto.drag_mouse.assert_called_once()
    auto.take_screenshot.assert_called_once()
