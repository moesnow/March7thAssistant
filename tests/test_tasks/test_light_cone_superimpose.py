from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tasks.daily import synthesis


pytestmark = pytest.mark.skip(reason="3星光锥自动叠加缺乏维护，已禁用")


CONE = ((200, 300), (240, 340))
AUTO_PLACE = ((1320, 930), (1420, 970))
APPLY = ((1630, 930), (1730, 970))
RECEIPT = ((860, 920), (1010, 970))


@pytest.fixture
def bag(monkeypatch):
    auto = Mock()
    auto.click_element.return_value = True
    auto.click_element_with_pos.return_value = True
    auto.find_element.side_effect = lambda _path, kind, *args, **kwargs: [] if kind == "image_with_multiple_targets" else None
    scroll = Mock(return_value=True)
    log = Mock()
    monkeypatch.setattr(synthesis, "auto", auto)
    monkeypatch.setattr(synthesis, "screen", Mock())
    monkeypatch.setattr(synthesis, "time", SimpleNamespace(sleep=Mock()))
    monkeypatch.setattr(synthesis, "drag_list", scroll)
    monkeypatch.setattr(synthesis, "log", log)
    return SimpleNamespace(auto=auto, scroll=scroll, log=log)


def show_one_cone(bag, *, missing=None):
    candidates = iter([[CONE]])
    controls = {
        "three_rarity.png": CONE,
        "auto_superimpose.png": AUTO_PLACE,
        "superimpose.png": APPLY,
        "close.png": RECEIPT,
    }
    if missing:
        del controls[missing]

    def find(path, kind, *args, **kwargs):
        name = path.rsplit("/", 1)[-1]
        if kind == "image_with_multiple_targets":
            return next(candidates, []) if name == "four.png" else []
        return controls.get(name)

    bag.auto.find_element.side_effect = find


def test_scanning_the_bag_without_candidates_completes_successfully(bag):
    assert synthesis.Synthesis.lc3star_superimpose() is True
    bag.auto.click_element_with_pos.assert_not_called()
    assert bag.scroll.call_count == 5


@pytest.mark.parametrize("missing", [None, "auto_superimpose.png", "superimpose.png", "close.png"])
def test_finishing_the_scan_succeeds_with_or_without_a_superimpose_result(bag, missing):
    show_one_cone(bag, missing=missing)

    assert synthesis.Synthesis.lc3star_superimpose() is True
    bag.auto.press_key.assert_called_once_with("esc", wait_time=3)
    messages = [entry.args[0] for entry in bag.log.info.call_args_list]
    assert ("3星光锥叠加完成，继续查找" in messages) is (missing is None)
    assert bag.scroll.call_count == (5 if missing is None else 6)
    bag.log.error.assert_not_called()


def test_a_failed_click_on_the_known_superimpose_button_returns_failure(bag):
    show_one_cone(bag)
    bag.auto.click_element_with_pos.side_effect = lambda point: point != APPLY

    assert synthesis.Synthesis.lc3star_superimpose() is False
    assert "无法点击叠影" in bag.log.error.call_args.args[0]


def test_sorting_or_scrolling_failure_still_returns_failure(bag):
    bag.scroll.return_value = False
    assert synthesis.Synthesis.lc3star_superimpose() is False
    bag.scroll.assert_called_once()

    bag.scroll.reset_mock()
    bag.auto.click_element.return_value = False
    assert synthesis.Synthesis.lc3star_superimpose() is False
    bag.scroll.assert_not_called()
