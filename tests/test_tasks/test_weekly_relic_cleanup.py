"""Safety checks for the weekly smart discard path."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


def _stub(name, **members):
    module = ModuleType(name)
    for key, value in members.items():
        setattr(module, key, value)
    return module


def _load_cleanup():
    auto = MagicMock()
    cfg = MagicMock()
    cfg.get_value.return_value = False
    screen = MagicMock()
    relicset = MagicMock()
    stubs = {
        "module.automation": _stub("module.automation", auto=auto),
        "module.config": _stub("module.config", cfg=cfg),
        "module.logger": _stub("module.logger", log=MagicMock()),
        "module.screen": _stub("module.screen", screen=screen),
        "tasks.power.relicset": _stub("tasks.power.relicset", Relicset=relicset),
    }
    path = Path(__file__).parents[2] / "tasks" / "power" / "weekly_relic_cleanup.py"
    spec = importlib.util.spec_from_file_location("tasks.power.cleanup_under_test", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module, auto, screen, relicset


def _load_relicset():
    auto = MagicMock()
    auto.click_element.return_value = True
    auto.find_element.return_value = True
    stubs = {
        "module.automation": _stub("module.automation", auto=auto),
        "module.logger": _stub("module.logger", log=MagicMock()),
        "module.screen": _stub("module.screen", screen=MagicMock()),
    }
    path = Path(__file__).parents[2] / "tasks" / "power" / "relicset.py"
    spec = importlib.util.spec_from_file_location("tasks.power.relicset_ocr_under_test", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module, auto


def test_smart_discard_clears_then_sets_only_the_two_rules():
    module, auto, _, _ = _load_cleanup()
    cleanup = module.WeeklyRelicCleanup
    with patch.object(cleanup, "_click") as click, patch.object(
        cleanup, "_visible", return_value=True
    ), patch.object(cleanup, "_ensure_protection") as protect, patch.object(
        cleanup, "_count", return_value=0
    ):
        assert cleanup._mark_smart_discard() == 0

    assert [call.args[0] for call in click.call_args_list] == [
        "智能弃置", "全部清除", "不匹配任意推荐角色", "0次"
    ]
    protect.assert_called_once()
    auto.press_key.assert_called_once_with("esc")


def test_smart_discard_confirms_mode_without_toggling_its_radio():
    module, auto, _, _ = _load_cleanup()
    cleanup = module.WeeklyRelicCleanup
    with patch.object(cleanup, "_click") as click, patch.object(
        cleanup, "_visible", return_value=True
    ), patch.object(cleanup, "_ensure_protection"), patch.object(
        cleanup, "_count", return_value=2
    ):
        assert cleanup._mark_smart_discard() == 2
    assert [call.args[0] for call in click.call_args_list] == [
        "智能弃置", "全部清除", "不匹配任意推荐角色", "0次", "确认", "确认弃置"
    ]
    auto.press_key.assert_not_called()


def test_protection_must_be_confirmed_before_discard():
    module, auto, _, _ = _load_cleanup()
    cleanup = module.WeeklyRelicCleanup
    auto.click_element.return_value = True
    with patch.object(cleanup, "_protection_on", side_effect=[False, False]), patch.object(
        cleanup, "_visible", return_value=True
    ):
        with pytest.raises(RuntimeError, match="弃置保护已开启"):
            cleanup._ensure_protection()
    auto.click_element.assert_called_once()


def test_quick_select_includes_discarded_and_four_star_but_not_all_five_star():
    module, _, _, _ = _load_cleanup()
    cleanup = module.WeeklyRelicCleanup
    with patch.object(cleanup, "_click") as click, patch.object(
        cleanup, "_visible", return_value=True
    ), patch.object(cleanup, "_count", side_effect=[1, 2]):
        assert cleanup._select_for_salvage(1, True) == 2
    assert [call.args[0] for call in click.call_args_list] == [
        "快速选择", "全选已弃置", "4星及以下", "确认"
    ]


def test_weekly_cleanup_without_smart_discard_selects_only_four_star():
    module, _, _, relicset = _load_cleanup()
    cleanup = module.WeeklyRelicCleanup

    with patch.object(cleanup, "_click"), patch.object(
        cleanup, "_visible", return_value=True
    ), patch.object(cleanup, "_count", return_value=0), patch.object(
        cleanup, "_mark_smart_discard"
    ) as mark, patch.object(cleanup, "_select_for_salvage", return_value=0) as select:
        assert cleanup.run() is True

    mark.assert_not_called()
    select.assert_called_once_with(0, False)
    relicset.start_break_down_relicset.assert_not_called()

    with patch.object(cleanup, "_click") as click, patch.object(
        cleanup, "_visible", return_value=True
    ), patch.object(cleanup, "_count", side_effect=[0, 2]):
        assert cleanup._select_for_salvage(0, False) == 2
    assert [call.args[0] for call in click.call_args_list] == [
        "快速选择", "4星及以下", "确认"
    ]


def test_quick_select_stops_if_marked_count_does_not_match():
    module, _, _, _ = _load_cleanup()
    cleanup = module.WeeklyRelicCleanup
    with patch.object(cleanup, "_click") as click, patch.object(
        cleanup, "_visible", return_value=True
    ), patch.object(cleanup, "_count", return_value=2):
        with pytest.raises(RuntimeError, match="预计 1，实际 2"):
            cleanup._select_for_salvage(1, True)
    click.assert_not_called()


def test_quick_select_stops_if_it_loses_marked_relics():
    module, _, _, _ = _load_cleanup()
    cleanup = module.WeeklyRelicCleanup
    with patch.object(cleanup, "_click"), patch.object(
        cleanup, "_visible", return_value=True
    ), patch.object(cleanup, "_count", side_effect=[1, 0]):
        with pytest.raises(RuntimeError, match="少于智能弃置数量"):
            cleanup._select_for_salvage(1, True)


def test_cleanup_only_decomposes_when_selected_and_returns_to_main():
    module, _, screen, relicset = _load_cleanup()
    cleanup = module.WeeklyRelicCleanup
    module.cfg.get_value.return_value = True
    relicset.start_break_down_relicset.return_value = True
    with patch.object(cleanup, "_click"), patch.object(cleanup, "_visible", return_value=True), patch.object(
        cleanup, "_count", return_value=0
    ), patch.object(cleanup, "_mark_smart_discard", return_value=1), patch.object(
        cleanup, "_select_for_salvage", return_value=2
    ) as select:
        assert cleanup.run() is True
    assert [call.args[0] for call in screen.change_to.call_args_list] == ["bag_relicset", "main"]
    select.assert_called_once_with(1, True)
    relicset.start_break_down_relicset.assert_called_once_with(use_ocr=True)


def test_full_batch_is_followed_by_an_empty_check():
    module, _, _, relicset = _load_cleanup()
    cleanup = module.WeeklyRelicCleanup
    module.cfg.get_value.return_value = True
    relicset.start_break_down_relicset.return_value = True
    with patch.object(cleanup, "_click"), patch.object(cleanup, "_visible", return_value=True), patch.object(
        cleanup, "_count", return_value=0
    ), patch.object(cleanup, "_mark_smart_discard", return_value=0) as mark, patch.object(
        cleanup, "_select_for_salvage", side_effect=[500, 0]
    ):
        assert cleanup.run() is True
    assert mark.call_count == 2
    relicset.start_break_down_relicset.assert_called_once_with(use_ocr=True)


def test_cleanup_failure_never_decomposes_and_still_exits():
    module, _, screen, relicset = _load_cleanup()
    cleanup = module.WeeklyRelicCleanup
    with patch.object(cleanup, "_click", side_effect=RuntimeError("OCR失败")):
        with pytest.raises(RuntimeError, match="OCR失败"):
            cleanup.run()
    relicset.start_break_down_relicset.assert_not_called()
    screen.change_to.assert_any_call("main")


def test_weekly_decomposition_uses_ocr_without_changing_legacy_path():
    module, auto = _load_relicset()
    with patch.object(module.time, "sleep"):
        assert module.Relicset.start_break_down_relicset(use_ocr=True) is True
    assert [call.args[:2] for call in auto.click_element.call_args_list] == [
        ("分解", "text"), ("确认", "text"), ("点击空白处关闭", "text")
    ]
    auto.reset_mock()
    with patch.object(module.time, "sleep"):
        assert module.Relicset.start_break_down_relicset() is True
    assert all(call.args[1] == "image" for call in auto.click_element.call_args_list)
