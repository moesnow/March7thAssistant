"""#1285：掉帧或暂停期间推进区域后，不继续执行旧区域的找门/重进流程。"""
import importlib.util
import itertools
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


STAGE_IMAGE = "./assets/images/screen/divergent_universe/stage.png"
OLD_STAGE = "2/13|第一位面|战斗"


@pytest.fixture
def task(monkeypatch):
    auto = Mock()
    auto.find_element.return_value = False
    auto.click_element.return_value = True
    services = {
        "module.screen": {"screen": Mock()},
        "module.automation": {"auto": auto},
        "module.config": {"cfg": SimpleNamespace(
            cloud_game_enable=False, weekly_divergent_stable_mode=False, game_title_name="test")},
        "module.logger": {"log": Mock()},
        "module.automation.screenshot": {"Screenshot": Mock()},
        "module.notification.notification": {"NotificationLevel": Mock()},
        "tasks.base.base": {"Base": Mock()},
        "utils.date": {"Date": Mock()},
        "tasks.power.power": {"Power": Mock()},
    }
    for name, members in services.items():
        module = ModuleType(name)
        module.__dict__.update(members)
        monkeypatch.setitem(sys.modules, name, module)
    path = Path(__file__).resolve().parents[2] / "tasks/weekly/divergent_universe.py"
    spec = importlib.util.spec_from_file_location("_divergent_stage_recovery_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ticks = itertools.count()
    monkeypatch.setattr(module, "time", SimpleNamespace(sleep=Mock(), monotonic=lambda: next(ticks)))
    module.Screenshot.get_window_region.return_value = (0, 0, 1920, 1080)
    obj = module.DivergentUniverse()
    obj.current_stage = OLD_STAGE
    return obj, auto, module


@pytest.mark.parametrize("texts,changed", [
    (["（3/13）第一位面-异常"] * 3, True),
    (["( 3 / 13 ) 第一位面-异常"] * 3, True),
    (["（2/13）第一位面-战斗"] * 3, False),
    (["（2/13）第一位面-异常"] * 3, False),
    (["（2/13）第三位面-战斗"] * 3, False),
    (["", "（3/13）第一位面-异常", "（3/13）第一位面-异常"], True),
    (["（3/13）第一位面-异常", "", "（3/13）第一位面-异常"], False),
    (["（3/13）第一位面-异常", "（2/13）第一位面-战斗"], False),
    ([None] * 3, False),
    (["（99/13）第一位面-战斗"] * 3, False),
])
def test_re_enter_checks_progress_without_dispatching_new_stage(task, texts, changed):
    obj, auto, _ = task
    obj.wait_stage_after_continue = Mock(return_value=True)
    obj.process_event_stage = Mock()
    auto.get_single_line_text.side_effect = texts

    assert obj.process_re_enter() is changed

    assert obj.current_stage == OLD_STAGE
    obj.process_event_stage.assert_not_called()
    assert 1 <= auto.get_single_line_text.call_count <= 3


@pytest.mark.parametrize("total", [13, 17, 20])
def test_re_enter_accepts_supported_run_lengths(task, total):
    obj, auto, _ = task
    obj.current_stage = f"2/{total}|第一位面|战斗"
    obj.wait_stage_after_continue = Mock(return_value=True)
    auto.get_single_line_text.return_value = f"（3/{total}）第一位面-异常"
    assert obj.process_re_enter() is True


def test_re_enter_without_known_stage_does_not_invent_progress(task):
    obj, auto, _ = task
    obj.current_stage = ""
    obj.wait_stage_after_continue = Mock(return_value=True)
    assert obj.process_re_enter() is False
    auto.get_single_line_text.assert_not_called()


@pytest.mark.parametrize("recovery", [1, 2])
def test_door_recovery_returns_to_main_loop_when_reentered_stage_changed(task, recovery):
    obj, auto, _ = task
    obj.check_click_close = Mock(return_value=False)
    obj.check_title = Mock(return_value=False)
    obj.process_random_door = Mock(return_value=False)
    obj.wait_stage_after_continue = Mock(return_value=True)
    obj.process_leave = Mock()
    auto.get_single_line_text.side_effect = (
        ["（2/13）第一位面-战斗"] * (recovery - 1) + ["（3/13）第一位面-异常"] * 2)

    obj.process_battle_stage_finish()

    assert obj.wait_stage_after_continue.call_count == recovery
    obj.process_leave.assert_not_called()
    assert obj.process_random_door.call_count == (3 if recovery == 1 else 5)
    assert obj.current_stage == OLD_STAGE

    # 退出旧调用栈后，由主循环正常识别和处理新区域。
    auto.find_element.side_effect = lambda target, *args, **kwargs: target == STAGE_IMAGE
    auto.get_single_line_text.side_effect = None
    auto.get_single_line_text.return_value = "（3/13）第一位面-异常"
    obj.process_event_stage = Mock()
    obj.check_stage()
    obj.process_event_stage.assert_called_once()
    assert obj.current_stage == "3/13|第一位面|异常"
    assert obj.stage_finish is False


def test_unchanged_stage_keeps_existing_door_retries_and_failure(task):
    obj, auto, _ = task
    obj.check_click_close = Mock(return_value=False)
    obj.check_title = Mock(return_value=False)
    obj.process_random_door = Mock(return_value=False)
    obj.wait_stage_after_continue = Mock(return_value=True)
    obj.process_leave = Mock()
    auto.get_single_line_text.return_value = "（2/13）第一位面-战斗"

    obj.process_battle_stage_finish()

    assert obj.wait_stage_after_continue.call_count == 2
    assert obj.process_random_door.call_count == 8
    obj.process_leave.assert_called_once()


@pytest.mark.parametrize("title,handler", [
    ("选择站点卡", "process_station_card"),
    ("选择下一站", "process_next_station"),
])
def test_station_selection_stops_old_door_recovery(task, title, handler):
    obj, auto, _ = task
    obj.check_click_close = Mock(return_value=False)
    obj.detect_random_door = Mock(return_value=False)
    obj.process_re_enter = Mock()
    obj.process_leave = Mock()
    setattr(obj, handler, Mock())
    seen = False

    def find(target, *args, **kwargs):
        nonlocal seen
        if isinstance(target, tuple) and title in target and not seen:
            auto.matched_text = title
            seen = True
            return True
        return False

    auto.find_element.side_effect = find
    obj.process_battle_stage_finish()

    assert obj.stage_finish is True
    getattr(obj, handler).assert_called_once()
    obj.detect_random_door.assert_called_once()
    obj.process_re_enter.assert_not_called()
    obj.process_leave.assert_not_called()


def test_reward_title_does_not_mark_stage_finished(task):
    obj, auto, _ = task
    auto.find_element.return_value = True
    auto.matched_text = "愿力满盈"
    obj.process_wish = Mock()
    assert obj.check_title()
    assert obj.stage_finish is False


def test_completed_stage_with_unchanged_label_still_reenters(task):
    obj, auto, _ = task
    obj.stage_finish = True
    auto.find_element.side_effect = lambda target, *args, **kwargs: target == STAGE_IMAGE
    auto.get_single_line_text.return_value = "（2/13）第一位面-战斗"
    obj.process_re_enter = Mock(return_value=False)

    obj.check_stage()

    obj.process_re_enter.assert_called_once()
    assert obj.current_stage == ""


def test_loot_recovery_stops_battle_retry_when_stage_changed(task):
    obj, auto, _ = task
    obj.check_click_close = Mock(return_value=False)
    obj.check_title = Mock(return_value=False)
    obj.process_re_enter = Mock(return_value=True)
    auto.find_element.side_effect = lambda target, *args, **kwargs: (
        target == ("战利品", "混沌药箱") or isinstance(target, str) and target.endswith("/F.png"))
    auto.matched_text = "战利品"

    obj.process_battle_stage()

    obj.process_re_enter.assert_called_once()
    assert obj.process_stage is False


def test_event_recovery_stops_old_event_loop_when_stage_changed(task):
    obj, auto, _ = task
    obj.check_click_close = Mock(return_value=False)
    obj.check_title = Mock(return_value=False)
    obj.check_auto_battle = Mock(return_value=False)
    obj.detect_events = Mock(return_value=[((900, 500), (1020, 650))])
    obj.process_random_door = Mock(return_value=False)
    obj.process_re_enter = Mock(return_value=True)
    obj.process_leave = Mock()
    auto.find_element.side_effect = lambda target, *args, **kwargs: (
        target in ("事件", STAGE_IMAGE) or isinstance(target, str) and target.endswith("/f.png"))

    obj.process_event_stage()

    obj.detect_events.assert_called_once()
    obj.process_re_enter.assert_called_once()
    obj.process_leave.assert_not_called()
