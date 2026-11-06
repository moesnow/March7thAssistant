from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from tasks.challenge import memoryofchaos as module


def ocr_levels(*levels):
    return [([(100 * i, 100), (100 * i + 50, 100), (100 * i + 50, 150), (100 * i, 150)], (f"{level:02}", 1.0))
            for i, level in enumerate(levels)]


@pytest.fixture
def navigation(monkeypatch):
    auto = Mock()
    auto.ocr_result = ocr_levels(10, 11, 12)
    auto.find_element.return_value = False
    drag = Mock(return_value=True)
    sleep = Mock()
    monkeypatch.setattr(module, "auto", auto)
    monkeypatch.setattr(module, "drag_list", drag)
    monkeypatch.setattr(module, "time", SimpleNamespace(sleep=sleep))
    monkeypatch.setattr(module, "cfg", SimpleNamespace(game_title_name="test"))
    monkeypatch.setattr(module.Screenshot, "get_window", Mock(return_value=object()))
    monkeypatch.setattr(module.Screenshot, "get_window_region", Mock(return_value=(0, 0, 1920, 1080)))
    return SimpleNamespace(auto=auto, drag=drag, sleep=sleep, owner=module.MemoryOfChaos([], []))


def test_visible_levels_choose_direction_and_reuse_stable_frame(navigation):
    n = navigation

    def drag(*args, **kwargs):
        assert args[1][0] < args[2][0], "07在10左侧，应向右拖动"
        n.auto.ocr_result = ocr_levels(6, 7, 8)
        return True

    n.drag.side_effect = drag
    n.auto.find_element.side_effect = [False, ((600, 200), (650, 250))]
    assert n.owner.find_level(7) == (1140, 606)
    assert n.auto.find_element.call_args.kwargs["take_screenshot"] is False
    assert n.auto.find_element.call_args.kwargs["need_ocr"] is False
    assert n.drag.call_args.kwargs["duration"] == 0.4
    assert n.drag.call_args.kwargs["end_pause"] == 0.25
    n.sleep.assert_not_called()


def test_missing_level_stops_after_both_boundaries(navigation):
    n = navigation
    assert n.owner.find_level(3) is False
    assert n.drag.call_count == 4, "每侧两次画面不变后应停止，不反复扫完整列表"
    n.sleep.assert_not_called()


def test_interrupted_level_drag_does_not_search_a_partial_frame(navigation):
    n = navigation
    n.drag.return_value = False
    assert n.owner.find_level(3) is False
    n.auto.find_element.assert_called_once()
    n.drag.assert_called_once()


def test_selected_range_does_not_detour_to_level_one(navigation):
    n = navigation
    n.owner.level_range = (7, 8)
    n.owner.find_level = Mock(return_value=(100, 200))
    n.owner.judge_stars = Mock(return_value=3)
    assert n.owner.start_challenges()
    assert n.owner.find_level.call_args_list == [call(7), call(8)]
    n.sleep.assert_not_called()
