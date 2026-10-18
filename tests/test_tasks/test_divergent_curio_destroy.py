"""Replay Curio Destruction states without a game or real input devices."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def task(monkeypatch):
    auto = Mock()
    services = {
        'module.screen': {'screen': Mock()},
        'module.automation': {'auto': auto},
        'module.config': {'cfg': Mock()},
        'module.logger': {'log': Mock()},
        'module.automation.screenshot': {'Screenshot': Mock()},
        'module.notification.notification': {'NotificationLevel': Mock()},
        'tasks.base.base': {'Base': Mock()},
        'utils.date': {'Date': Mock()},
        'tasks.power.power': {'Power': Mock()},
    }
    for name, attributes in services.items():
        module = ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
    path = Path(__file__).resolve().parents[2] / 'tasks/weekly/divergent_universe.py'
    spec = importlib.util.spec_from_file_location('_divergent_curio_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'time', Mock())
    return module.DivergentUniverse(), auto


def ready(auto, leaves=True):
    counts = {}

    def find(target, *args, **kwargs):
        counts[target] = counts.get(target, 0) + 1
        if target in ('奇物损毁', '请选择要摧毁的奇物'):
            return counts[target] == 1 or not leaves
        return True

    auto.find_element.side_effect = find
    auto.get_single_line_text.return_value = '换境桂冠'
    auto.click_element.return_value = True


def test_destroy_title_dispatch(task):
    obj, auto = task

    def recognize(targets, *args, **kwargs):
        if '奇物损毁' not in targets:
            return False
        auto.matched_text = '奇物损毁'
        return True

    auto.find_element.side_effect = recognize
    obj.process_relic_destroy = Mock()
    obj.process_relic_discard = Mock()
    assert obj.check_title()
    obj.process_relic_destroy.assert_called_once()
    obj.process_relic_discard.assert_not_called()


def test_discard_keeps_existing_handler(task):
    obj, auto = task
    auto.find_element.return_value = True
    auto.matched_text = '丢弃奇物'
    obj.process_relic_destroy = Mock()
    obj.process_relic_discard = Mock()
    assert obj.check_title()
    obj.process_relic_discard.assert_called_once()
    obj.process_relic_destroy.assert_not_called()


def test_destroy_single_card_and_actual_button(task):
    obj, auto = task
    ready(auto)
    obj.process_relic_destroy()
    calls = auto.click_element.call_args_list
    assert len(calls) == 2
    assert calls[0].args[1] == 'crop'
    assert calls[1].args == ('摧毁', 'text')
    assert auto.find_element.call_count >= 7


def test_two_card_layout_fallback(task):
    obj, auto = task
    ready(auto)
    auto.get_single_line_text.side_effect = [None, '另一件奇物']
    obj.process_relic_destroy()
    selected = auto.click_element.call_args_list[0].args[0]
    assert selected[0] == 537 / 1920


@pytest.mark.parametrize('missing', ['奇物损毁', '请选择要摧毁的奇物', '摧毁'])
def test_incomplete_context_never_clicks(task, missing):
    obj, auto = task
    auto.find_element.side_effect = lambda target, *a, **kw: target != missing
    with pytest.raises(RuntimeError):
        obj.process_relic_destroy()
    auto.click_element.assert_not_called()


def test_unreadable_card_never_clicks(task):
    obj, auto = task
    ready(auto)
    auto.get_single_line_text.return_value = None
    with pytest.raises(RuntimeError, match='卡片未识别'):
        obj.process_relic_destroy()
    auto.click_element.assert_not_called()


def test_stuck_after_click_stops(task):
    obj, auto = task
    ready(auto, leaves=False)
    with pytest.raises(RuntimeError, match='界面未退出'):
        obj.process_relic_destroy()


def test_one_missing_frame_does_not_report_success(task):
    obj, auto = task
    ready(auto)
    calls = {}

    def alternating(target, *args, **kwargs):
        calls[target] = calls.get(target, 0) + 1
        if target in ('奇物损毁', '请选择要摧毁的奇物'):
            return calls[target] % 2 == 1
        return True

    auto.find_element.side_effect = alternating
    with pytest.raises(RuntimeError, match='界面未退出'):
        obj.process_relic_destroy()


def test_remaining_prompt_prevents_false_completion(task):
    obj, auto = task
    ready(auto)
    counts = {}

    def title_lost(target, *args, **kwargs):
        counts[target] = counts.get(target, 0) + 1
        return target != '奇物损毁' or counts[target] == 1

    auto.find_element.side_effect = title_lost
    with pytest.raises(RuntimeError, match='界面未退出'):
        obj.process_relic_destroy()


@pytest.mark.parametrize('failed_click', [1, 2])
def test_failed_input_is_not_success(task, failed_click):
    obj, auto = task
    ready(auto)
    auto.click_element.side_effect = [False] if failed_click == 1 else [True, False]
    with pytest.raises(RuntimeError):
        obj.process_relic_destroy()
