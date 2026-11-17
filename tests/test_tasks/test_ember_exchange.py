from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tasks.base import task_steps
from tasks.daily import ember_exchange
from tasks.daily.ember_exchange import EmberExchange
from utils import wait
from utils.pause import RunStopRequested


@pytest.mark.parametrize(
    ("entry_pages", "animation_exit", "fault", "expected_inputs"),
    [
        pytest.param(["legacy"], None, None, ["商店", "兑换商店", "余烬兑换"], id="legacy-shop"),
        pytest.param(["recommended"], None, None, ["商店", "常驻商店", "兑换商店", "余烬兑换"], id="new-shop"),
        pytest.param(["recommended"], None, "frame", ["商店", "常驻商店", "兑换商店", "余烬兑换"], id="transient-frame"),
        pytest.param(["animation"], "recommended", None,
                     ["商店", "esc", "常驻商店", "兑换商店", "余烬兑换"], id="esc-reveals-shop"),
        pytest.param(["animation", "recommended"], "menu", None,
                     ["商店", "esc", "商店", "常驻商店", "兑换商店", "余烬兑换"], id="esc-returns-to-menu"),
        pytest.param(["menu", "recommended"], None, None,
                     ["商店", "商店", "常驻商店", "兑换商店", "余烬兑换"], id="click-missed"),
        pytest.param(["animation"] * 3, "menu", "unavailable", ["商店", "esc"] * 3, id="entry-budget-exhausted"),
        pytest.param(["animation"], None, "stop", ["商店"], id="user-stop"),
    ],
)
def test_ember_exchange_shop_navigation(monkeypatch, entry_pages, animation_exit, fault, expected_inputs):
    page = "menu"
    inputs = []
    pages_after_click = iter(entry_pages)
    screen = SimpleNamespace(current_screen=None)
    time_now = 0.0
    frame_failed = False
    stop_requested = False
    texts = {
        "menu": {"商店"},
        "recommended": {"常驻商店"},
        "regular": {"常驻商店", "兑换商店"},
        "exchange": {"兑换商店", "余烬兑换"},
        "legacy": {"兑换商店"},
        "legacy_tabs": {"兑换商店", "余烬兑换"},
    }

    def sleep(seconds):
        nonlocal time_now
        time_now += seconds

    def check_screen(target, **kwargs):
        if page == target:
            screen.current_screen = target
            return True
        return False

    def change_to_main(target, **kwargs):
        nonlocal page
        assert target == "main"
        page = "main"

    def check_stop():
        if stop_requested:
            raise RunStopRequested()

    def find_element(target, kind, *args, **kwargs):
        nonlocal frame_failed, stop_requested
        if kind == "image":
            assert target == EmberExchange.UNDERLINED_EMBER_TAB_IMAGE
            return page == "ember"
        if target == EmberExchange.SHOP_ENTRY_TEXTS and fault == "frame" and not frame_failed:
            frame_failed = True
            raise RuntimeError("截图暂时不可用")
        if page == "animation" and fault == "stop":
            stop_requested = True
            check_stop()
        targets = (target,) if isinstance(target, str) else target
        return next((text for text in targets if text in texts.get(page, ())), None)

    def click(text):
        nonlocal page
        inputs.append(text)
        if text == "商店":
            page = next(pages_after_click)
        elif text == "常驻商店":
            page = "regular"
        elif text == "兑换商店":
            page = "legacy_tabs" if page == "legacy" else "exchange"
        elif text == "余烬兑换":
            page = "legacy_ember" if page == "legacy_tabs" else "ember"
        # 输入返回失败时，仍以随后画面反映的实际变化为准。
        return False

    def press_key(key):
        nonlocal page
        assert key == "esc"
        inputs.append(key)
        page = animation_exit if page == "animation" else "menu"

    def purchase(item):
        assert page in {"ember", "legacy_ember"}
        assert inputs == expected_inputs
        return EmberExchange.RESULT_SUCCESS

    clock = SimpleNamespace(monotonic=lambda: time_now, sleep=sleep)
    monkeypatch.setattr(ember_exchange, "time", clock)
    monkeypatch.setattr(wait, "time", clock)
    screen.check_screen = check_screen
    screen.change_to = Mock(side_effect=change_to_main)
    monkeypatch.setattr(ember_exchange, "screen", screen)
    monkeypatch.setattr(task_steps, "screen", screen)
    monkeypatch.setattr(ember_exchange, "pause_ctl", SimpleNamespace(check_stop=check_stop))
    monkeypatch.setattr(ember_exchange, "auto", SimpleNamespace(
        find_element=find_element, click_element_with_pos=click, press_key=press_key, take_screenshot=Mock(),
        is_rgb_ratio_above_threshold=lambda *args, **kwargs: page == "legacy_ember",
    ))

    item = EmberExchange.ITEMS[0]
    cfg = SimpleNamespace(get_value={item.enable_key: True}.get, save_timestamp=Mock(), refresh_hour=4)
    monkeypatch.setattr(ember_exchange, "cfg", cfg)
    monkeypatch.setattr(ember_exchange.Date, "is_next_month_x_am", Mock(return_value=True))
    purchase_item = Mock(side_effect=purchase)
    monkeypatch.setattr(EmberExchange, "_purchase_item", purchase_item)
    next_step = Mock(return_value=True)
    steps = [("余烬兑换", EmberExchange.start), ("后续日常任务", next_step)]

    if fault == "stop":
        with pytest.raises(RunStopRequested):
            task_steps.run_steps(steps)
        assert inputs == expected_inputs
        screen.change_to.assert_not_called()
        next_step.assert_not_called()
        purchase_item.assert_not_called()
        cfg.save_timestamp.assert_not_called()
    elif fault == "unavailable":
        assert task_steps.run_steps(steps) is False
        assert inputs == expected_inputs
        assert time_now < 60
        assert page == "main"
        next_step.assert_called_once_with()
        purchase_item.assert_not_called()
        cfg.save_timestamp.assert_not_called()
    else:
        assert task_steps.run_steps(steps) is True
        assert page == "main"
        next_step.assert_called_once_with()
        purchase_item.assert_called_once_with(item)
        cfg.save_timestamp.assert_called_once_with(item.timestamp_key)
