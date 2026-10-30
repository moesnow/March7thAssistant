"""奖励收集的中断边界；所有输入、截图和 OCR 均为替身。"""
import math
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.test_tasks.test_currency_wars_settlement import load_currency_wars


@pytest.fixture
def reward():
    module = load_currency_wars()
    module.np = SimpleNamespace(sqrt=math.sqrt,
        linspace=lambda a,b,n,endpoint=False:[a+(b-a)*i/n for i in range(n)])
    auto = module.auto
    auto.is_rgb_ratio_above_threshold.return_value = False
    auto.input_handler.is_background = True
    auto.input_handler.mouse_up.return_value = None
    auto.get_single_line_text.return_value = None
    auto.find_element.side_effect = lambda target,kind,**kwargs:target if kind == 'crop' else None
    auto.click_element_with_pos.return_value = True
    auto.mouse_up.side_effect = AssertionError('释放动作不应停在暂停入口')
    return SimpleNamespace(module=module, auto=auto, war=module.CurrencyWars())


def test_no_rewards_sends_no_mouse_input(reward):
    r = reward
    r.auto.is_rgb_ratio_above_threshold.return_value = True
    assert r.war.collect_reward() is True
    r.auto.click_element_with_pos.assert_not_called()
    r.auto.input_handler.mouse_up.assert_not_called()


def test_background_sweep_releases_between_short_batches(reward):
    r = reward
    batches, current = [], []
    def click(_pos, action='click'):
        current.append(action)
        return True
    def release():
        batches.append(current[:])
        current.clear()
    r.auto.click_element_with_pos.side_effect = click
    r.auto.input_handler.mouse_up.side_effect = release
    assert r.war.collect_reward() is True
    assert len(batches) > 1
    assert all(batch[0] == 'down' and 1 <= batch.count('move') <= 8 for batch in batches)
    assert all(batch.count('down') == 1 for batch in batches)


def test_foreground_sweep_keeps_single_hold(reward):
    r = reward
    r.auto.input_handler.is_background = False
    assert r.war.collect_reward() is True
    actions = [c.kwargs['action'] for c in r.auto.click_element_with_pos.call_args_list]
    assert actions.count('down') == 1
    r.auto.input_handler.mouse_up.assert_called_once()


@pytest.mark.parametrize('failure', ['down', 'move', 'release'])
def test_interruption_stops_sweep_and_defers_followup_actions(reward, failure):
    r = reward
    calls = []
    def click(_pos, action='click'):
        calls.append(action)
        return action != failure
    r.auto.click_element_with_pos.side_effect = click
    if failure == 'release':
        r.auto.input_handler.mouse_up.return_value = False
    assert r.war.collect_reward() is False
    assert calls.count('down') == 1
    if failure == 'move': assert calls.count('move') == 1
    r.auto.input_handler.mouse_up.assert_called_once()
    r.auto.get_single_line_text.assert_not_called()
    r.auto.click_element.assert_not_called()


def test_exception_during_movement_still_releases(reward):
    r = reward
    def click(_pos, action='click'):
        if action == 'move':raise RuntimeError('injected failure')
        return True
    r.auto.click_element_with_pos.side_effect = click
    with pytest.raises(RuntimeError):r.war.collect_reward()
    r.auto.input_handler.mouse_up.assert_called_once()


def test_missing_path_position_releases_and_does_not_advance(reward):
    r = reward
    calls = []
    def find(target,kind,**kwargs):
        calls.append(target)
        return target if len(calls) == 1 else None
    r.auto.find_element.side_effect = find
    assert r.war.collect_reward() is False
    r.auto.input_handler.mouse_up.assert_called_once()
    r.auto.get_single_line_text.assert_not_called()


def test_stage_does_not_buy_or_manage_characters_after_incomplete_collection(reward, monkeypatch):
    r = reward
    r.auto.find_element.side_effect = lambda target,*args,**kwargs:(
        ((1,2),(3,4)) if isinstance(target,str) and target.endswith('/exit.png') else None)
    r.auto.click_element.return_value = False
    r.war.click_origin = Mock()
    r.war.check_festival_star_popup = Mock()
    r.war.identify_current_stage = Mock()
    r.war.need_exit = False
    r.war.collect_reward = Mock(return_value=False)
    r.war.check_box = Mock()
    r.war.check_character_status = Mock()
    r.war.buy_experience = Mock()
    monkeypatch.setattr(r.module.time, 'monotonic', Mock(side_effect=[0,8]))
    assert r.war.check_main_screen() is True
    r.war.collect_reward.assert_called_once()
    r.war.check_box.assert_not_called()
    r.war.check_character_status.assert_not_called()
    r.war.buy_experience.assert_not_called()
