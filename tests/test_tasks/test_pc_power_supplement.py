from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from tasks.power import supplement
from utils.pause import RunStopRequested


@pytest.mark.parametrize("source,center,stock", [
    ("后备开拓力", 550, 82),
    ("后备开拓力", 595, 82),
    ("燃料", 640, 7),
    ("燃料", 595, 7),
])
def test_pc_source_and_stock_follow_the_resource_card(monkeypatch, source, center, stock):
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
        return stock

    monkeypatch.setattr(supplement, "read_number", read)
    config = SimpleNamespace(use_reserved_trailblaze_power=True, use_fuel=True)
    result = supplement._prepare_exchange(auto, Mock(), config, lambda: "入口", "map", True)

    assert result == "确认"
    assert crops == [supplement._crop((center - 36, 362, 72, 29))]
    assert taps.call_args_list[0].args == (auto, center, 327)
    assert taps.call_args_list[1].args == (auto, *supplement.PC_MAX_BUTTONS[source])
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


def _exchange_auto():
    auto = Mock(screenshot=SimpleNamespace(width=1280))
    auto.find_element.side_effect = lambda target, kind, *_args, **_kwargs: (
        ((497, 290), (603, 360)) if kind == "image" else target
    )
    return auto


@pytest.mark.parametrize("desktop", [False, True], ids=["touch", "pc"])
@pytest.mark.parametrize("actual", [80, 149, 389])
def test_supplement_reads_only_stock_then_uses_the_actual_balance(monkeypatch, desktop, actual):
    auto = _exchange_auto()
    stock = Mock(side_effect=[159])
    monkeypatch.setattr(supplement, "read_number", stock)
    config = SimpleNamespace(use_reserved_trailblaze_power=True, use_fuel=False)
    screen = Mock(check_screen=Mock(return_value=True))
    read_balance = Mock(return_value=actual)

    assert supplement.supplement(auto, screen, config, 89, lambda: "入口", read_balance,
                                 return_screen="map" if desktop else "guide3", desktop=desktop) == actual
    stock.assert_called_once()
    read_balance.assert_called_once_with()
    buttons = supplement.PC_MAX_BUTTONS if desktop else supplement.TOUCH_MAX_BUTTONS
    assert call(supplement._crop((*buttons["后备开拓力"], 0, 0))) in auto.click_element_with_pos.call_args_list
    assert auto.click_element_with_pos.call_args_list.count(call("确认")) == 2


@pytest.mark.parametrize("desktop", [False, True], ids=["touch", "pc"])
@pytest.mark.parametrize("stock_value", [0, 159], ids=["zero-stock", "not-dispatched"])
def test_no_exchange_dispatch_keeps_the_old_balance_without_reading(monkeypatch, desktop, stock_value):
    auto = _exchange_auto()
    # 控件可见，但输入层未报告最终确认已实际派发。
    auto.input_handler = SimpleNamespace(reports_dispatch=True)
    stock = Mock(side_effect=[stock_value])
    monkeypatch.setattr(supplement, "read_number", stock)
    config = SimpleNamespace(use_reserved_trailblaze_power=True, use_fuel=False)
    read_balance = Mock(side_effect=AssertionError("未发送兑换，不应读取新余额"))

    assert supplement.supplement(auto, Mock(check_screen=Mock(return_value=True)), config, 89,
                                 lambda: "入口", read_balance, return_screen="map" if desktop else "guide3",
                                 desktop=desktop) == 89
    stock.assert_called_once()
    read_balance.assert_not_called()
    assert auto.click_element_with_pos.call_args_list.count(call("确认")) == (0 if stock_value == 0 else 2)


@pytest.mark.parametrize("desktop", [False, True], ids=["touch", "pc"])
@pytest.mark.parametrize("failure", ["cleanup", "balance", "stop-during-balance"])
def test_supplement_failure_keeps_old_resources_without_another_exchange(monkeypatch, desktop, failure):
    auto = _exchange_auto()
    monkeypatch.setattr(supplement, "read_number", Mock(side_effect=[159]))
    config = SimpleNamespace(use_reserved_trailblaze_power=True, use_fuel=False)
    screen = Mock(check_screen=Mock(side_effect=RuntimeError("清理截图失败") if failure == "cleanup" else None,
                                   return_value=True))
    read_balance = Mock(side_effect=RunStopRequested() if failure == "stop-during-balance"
                        else RuntimeError("余额截图失败"))

    def run():
        return supplement.supplement(auto, screen, config, 89, lambda: "入口", read_balance,
                                     return_screen="map" if desktop else "guide3", desktop=desktop)

    if failure == "stop-during-balance":
        with pytest.raises(RunStopRequested):
            run()
    else:
        assert run() == 89
    assert read_balance.call_count == int(failure != "cleanup")
    assert auto.click_element_with_pos.call_args_list.count(call("确认")) == 2
