from types import SimpleNamespace
from unittest.mock import Mock

from tasks.weekly import divergent_universe as module


def setup_list(monkeypatch, visible, completed=True):
    auto = Mock()
    auto.find_element.side_effect = visible
    drag = Mock(return_value=completed)
    monkeypatch.setattr(module, "auto", auto)
    monkeypatch.setattr(module, "drag_list", drag)
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
        _, start, end = call.args
        x, y, width, height = call.kwargs["crop"]
        assert all(x < px < x + width and y < py < y + height for px, py in (start, end))
        assert start[1] > end[1]
    auto.click_element.assert_not_called()


def test_missing_confirmation_stops_at_limit(monkeypatch):
    auto, drag = setup_list(monkeypatch, [False] * 7)
    assert module.DivergentUniverse.reveal_event_confirm() is False
    assert drag.call_count == 6
    auto.click_element.assert_not_called()


def test_interrupted_drag_does_not_replay_or_confirm(monkeypatch):
    auto, drag = setup_list(monkeypatch, [False], completed=False)
    assert module.DivergentUniverse.reveal_event_confirm() is False
    drag.assert_called_once()
    auto.click_element.assert_not_called()


def test_event_does_not_confirm_after_failed_reveal(monkeypatch):
    auto = Mock()
    auto.click_element.return_value = False
    auto.find_element.return_value = [((1360, 782), (1381, 807))]
    monkeypatch.setattr(module, "auto", auto)
    monkeypatch.setattr(module, "time", SimpleNamespace(sleep=Mock()))
    obj = module.DivergentUniverse()
    obj.reveal_event_confirm = Mock(return_value=False)
    obj.process_event()
    assert all(call.args[0] != "确定" for call in auto.click_element.call_args_list)
