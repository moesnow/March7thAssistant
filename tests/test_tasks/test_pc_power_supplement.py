from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

from PIL import Image
import pytest

from module.automation.automation import Automation
from module.automation.input_base import limit_input_deadline
from module.config.platform import get_ui_profile
from tasks.power import supplement
from utils.pause import RunStopRequested


@pytest.mark.parametrize("first_frame_missing", [False, True], ids=["ready", "transient-frame"])
@pytest.mark.parametrize("scene,source,center", [
    ("three-cards-reserve-selected", "后备开拓力", 528),
    ("three-cards-reserve-selected", "燃料", 640),
    ("three-cards-fuel-selected", "后备开拓力", 528),
    ("three-cards-fuel-selected", "燃料", 640),
    ("two-cards-fuel-selected", "燃料", 584),
    ("two-cards-jade-selected", "燃料", 584),
])
def test_touch_real_cards_match_in_both_selection_states(monkeypatch, scene, source, center, first_frame_missing):
    # 只保留真实截图中的资源卡片，按原坐标放回；不将整张游戏截图放入测试。
    frame = Image.new("RGB", (1280, 720), "#e4e4e4")
    with Image.open(Path("tests/fixtures/touch_power") / f"{scene}.png") as cards:
        frame.paste(cards, (470, 268))
    auto = object.__new__(Automation)
    auto.screenshot, auto.screenshot_pos, auto.screenshot_scale_factor = frame, (0, 0, 1280, 720), 1
    auto.img_cache, auto.logger = {}, Mock()
    auto._is_debug_enabled = lambda: False
    frames = iter([Image.new("RGB", frame.size), frame] if first_frame_missing else [frame])

    def capture(*_args):
        auto.screenshot = next(frames, frame)
        return auto.screenshot, auto.screenshot_pos, 1

    auto.take_screenshot = Mock(side_effect=capture)
    auto.click_element_with_pos = Mock()
    profile = get_ui_profile(SimpleNamespace(ui_profile="touch_720"))
    monkeypatch.setattr("module.automation.automation.get_ui_profile", lambda _: profile)
    monkeypatch.setattr(supplement, "_find_text", Mock(return_value="确认"))
    monkeypatch.setattr(supplement, "read_number", Mock(return_value=27))
    monkeypatch.setattr(supplement.time, "sleep", Mock())
    config = SimpleNamespace(use_reserved_trailblaze_power=source == "后备开拓力" or scene.startswith("two-"),
                             use_fuel=source == "燃料")

    assert supplement._prepare_exchange(auto, Mock(), config, lambda: "入口", "guide3", False) == "确认"

    selected = auto.click_element_with_pos.call_args_list[1].args[0]
    assert abs(selected[0][0] - center) <= 3
    assert selected[0][1] == 327
    stock_crop = supplement.read_number.call_args.args[1]
    assert abs((stock_crop[0] + stock_crop[2] / 2) * 1280 - center) <= 3
    assert auto.click_element_with_pos.call_args_list.count(call("确认")) == 1


@pytest.mark.parametrize("desktop", [False, True], ids=["touch", "pc"])
@pytest.mark.parametrize("fault", ["deadline", "stop"])
def test_resource_lookup_never_sends_input_after_deadline_or_stop(monkeypatch, desktop, fault):
    located = False

    def find(target, kind, *_args, **_kwargs):
        nonlocal located
        if kind == "image":
            located = True
            return ((497, 290), (603, 360))
        return target

    def checkpoint():
        if located and fault == "stop":
            raise RunStopRequested()

    auto = Mock(screenshot=SimpleNamespace(width=1280), find_element=Mock(side_effect=find))
    monkeypatch.setattr(supplement, "time", SimpleNamespace(monotonic=lambda: 20 if located else 0))
    monkeypatch.setattr(supplement.pause_ctl, "checkpoint", checkpoint)
    monkeypatch.setattr(supplement, "_find_text", Mock(return_value="开拓力补充"))
    monkeypatch.setattr(supplement, "read_number", Mock())
    config = SimpleNamespace(use_reserved_trailblaze_power=True, use_fuel=False)

    with limit_input_deadline(18):
        with pytest.raises(supplement.PowerError if fault == "deadline" else RunStopRequested):
            supplement._prepare_exchange(auto, Mock(), config, lambda: "入口", "map" if desktop else "guide3", desktop)

    auto.click_element_with_pos.assert_called_once_with("入口")
    supplement.read_number.assert_not_called()


@pytest.mark.parametrize("desktop", [False, True], ids=["touch", "pc"])
@pytest.mark.parametrize("source,center,stock", [
    ("后备开拓力", 550, 82),
    ("后备开拓力", 595, 82),
    ("燃料", 640, 7),
    ("燃料", 595, 7),
])
def test_source_and_stock_follow_the_resource_card(monkeypatch, desktop, source, center, stock):
    auto = Mock(screenshot=SimpleNamespace(width=1920))
    name = ("reserved_trailblaze_power" if desktop else "reserve") if source == "后备开拓力" else "fuel"
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
    result = supplement._prepare_exchange(auto, Mock(), config, lambda: "入口", "map" if desktop else "guide3", desktop)

    assert result == "确认"
    stock_y, stock_height = (362, 29) if desktop else (364, 26)
    assert crops == [supplement._crop((center - 36, stock_y, 72, stock_height))]
    assert taps.call_args_list[0].args == (auto, center, 327)
    buttons = supplement.PC_MAX_BUTTONS if desktop else supplement.TOUCH_MAX_BUTTONS
    assert taps.call_args_list[1].args == (auto, *buttons[source])
    assert auto.click_element_with_pos.call_args_list[-1].args == ("确认",)


@pytest.mark.parametrize("desktop", [False, True], ids=["touch", "pc"])
def test_only_jade_card_never_sends_exchange_confirmation(monkeypatch, desktop):
    auto = Mock()
    auto.find_element.return_value = None
    monkeypatch.setattr(supplement, "_find_text", Mock(return_value="开拓力补充"))
    read = Mock()
    monkeypatch.setattr(supplement, "read_number", read)
    config = SimpleNamespace(use_reserved_trailblaze_power=True, use_fuel=True)

    assert supplement._prepare_exchange(auto, Mock(), config, lambda: "入口", "map" if desktop else "guide3", desktop) is None
    read.assert_not_called()
    auto.click_element_with_pos.assert_called_once_with("入口")


@pytest.mark.parametrize("desktop", [False, True], ids=["touch", "pc"])
def test_rejects_a_card_without_the_expected_description(monkeypatch, desktop):
    auto = Mock(screenshot=SimpleNamespace(width=1920))
    auto.find_element.return_value = ((840, 438), (946, 544))
    monkeypatch.setattr(supplement, "_tap", Mock())
    monkeypatch.setattr(supplement, "_find_text", lambda _auto, text, *_args, **_kwargs: (
        "开拓力补充" if text == "开拓力补充" else None
    ))
    config = SimpleNamespace(use_reserved_trailblaze_power=True, use_fuel=False)

    with pytest.raises(supplement.PowerError, match="未确认开拓力补充方式"):
        supplement._prepare_exchange(auto, Mock(), config, lambda: "入口", "map" if desktop else "guide3", desktop)
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
