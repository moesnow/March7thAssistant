"""Safety checks for weekly four-star relic cleanup."""

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
    screen = MagicMock()
    relicset = MagicMock()
    stubs = {
        "module.automation": _stub("module.automation", auto=auto),
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


def test_quick_select_uses_only_four_star_and_checks_empty_selection():
    module, _, _, _ = _load_cleanup()
    cleanup = module.WeeklyRelicCleanup
    with patch.object(cleanup, "_click") as click, patch.object(
        cleanup, "_visible", return_value=True
    ), patch.object(cleanup, "_count", side_effect=[0, 2]):
        assert cleanup._select_for_salvage() == 2
    assert [call.args[0] for call in click.call_args_list] == [
        "快速选择", "4星及以下", "确认"
    ]


def test_quick_select_stops_when_other_relics_are_selected():
    module, _, _, _ = _load_cleanup()
    cleanup = module.WeeklyRelicCleanup
    with patch.object(cleanup, "_click") as click, patch.object(
        cleanup, "_visible", return_value=True
    ), patch.object(cleanup, "_count", return_value=1):
        with pytest.raises(RuntimeError, match="已有其他选中"):
            cleanup._select_for_salvage()
    click.assert_not_called()


def test_cleanup_only_decomposes_when_selected_and_returns_to_main():
    module, _, screen, relicset = _load_cleanup()
    cleanup = module.WeeklyRelicCleanup
    relicset.start_break_down_relicset.return_value = True
    with patch.object(cleanup, "_click"), patch.object(
        cleanup, "_visible", return_value=True
    ), patch.object(cleanup, "_select_for_salvage", return_value=2) as select:
        assert cleanup.run() is True
    assert [call.args[0] for call in screen.change_to.call_args_list] == ["bag_relicset", "main"]
    select.assert_called_once_with()
    relicset.start_break_down_relicset.assert_called_once_with(use_ocr=True)


def test_full_batch_is_followed_by_an_empty_check():
    module, _, _, relicset = _load_cleanup()
    cleanup = module.WeeklyRelicCleanup
    relicset.start_break_down_relicset.return_value = True
    with patch.object(cleanup, "_click"), patch.object(
        cleanup, "_visible", return_value=True
    ), patch.object(cleanup, "_select_for_salvage", side_effect=[500, 0]) as select:
        assert cleanup.run() is True
    assert select.call_count == 2
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
