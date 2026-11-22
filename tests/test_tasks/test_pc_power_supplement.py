from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tasks.power import supplement


@pytest.mark.parametrize("source,center,quantity,multiplier", [
    ("后备开拓力", 550, 82, 1),
    ("后备开拓力", 595, 82, 1),
    ("燃料", 640, 7, 60),
    ("燃料", 595, 7, 60),
])
def test_pc_source_and_stock_follow_the_resource_card(monkeypatch, source, center, quantity, multiplier):
    auto = Mock(screenshot=SimpleNamespace(width=1920))
    name = "reserved_trailblaze_power" if source == "后备开拓力" else "fuel"
    auto.find_element.side_effect = lambda path, *_args, **_kwargs: (
        ((center * 1.5 - 53, 438), (center * 1.5 + 53, 544)) if path.endswith(f"/{name}.png") else None
    )
    taps = Mock()
    monkeypatch.setattr(supplement, "_tap", taps)
    monkeypatch.setattr(supplement, "_find_text", lambda *_args, **_kwargs: "确认")
    crops = []

    def read(_auto, crop, _parse, _error):
        crops.append(crop)
        return quantity

    monkeypatch.setattr(supplement, "read_number", read)
    config = SimpleNamespace(use_reserved_trailblaze_power=True, use_fuel=True)
    result = supplement._prepare_exchange(auto, Mock(), config, lambda: "入口", "map", True)

    assert result == ("确认", quantity * multiplier)
    assert crops[0] == supplement._crop((center - 36, 362, 72, 29))
    assert taps.call_args_list[0].args == (auto, center, 327)
    assert auto.click_element_with_pos.call_args_list[-1].args == ("确认",)


def test_pc_only_jade_card_never_sends_exchange_confirmation(monkeypatch):
    auto = Mock()
    auto.find_element.return_value = None
    monkeypatch.setattr(supplement, "_find_text", Mock(return_value="开拓力补充"))
    read = Mock()
    monkeypatch.setattr(supplement, "read_number", read)
    config = SimpleNamespace(use_reserved_trailblaze_power=True, use_fuel=True)

    assert supplement._prepare_exchange(auto, Mock(), config, lambda: "入口", "map", True) is None
    read.assert_not_called()
    auto.click_element_with_pos.assert_called_once_with("入口")


def test_pc_rejects_a_card_without_the_expected_description(monkeypatch):
    auto = Mock(screenshot=SimpleNamespace(width=1920))
    auto.find_element.return_value = ((840, 438), (946, 544))
    monkeypatch.setattr(supplement, "_tap", Mock())
    monkeypatch.setattr(supplement, "_find_text", lambda _auto, text, *_args, **_kwargs: (
        "开拓力补充" if text == "开拓力补充" else None
    ))
    config = SimpleNamespace(use_reserved_trailblaze_power=True, use_fuel=False)

    with pytest.raises(supplement.PowerError, match="未确认开拓力补充方式"):
        supplement._prepare_exchange(auto, Mock(), config, lambda: "入口", "map", True)
    auto.click_element_with_pos.assert_called_once_with("入口")
