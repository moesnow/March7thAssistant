"""星启编队、节点推进及虚构叙事最终结算。"""

from itertools import count
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from tests.test_tasks.test_purefiction_settlement import challenge


@pytest.fixture
def stellar(challenge, monkeypatch):
    runner = challenge.instance.stellar
    runner.enabled = True
    runner.challenge.level_range = (runner.highest_level, runner.highest_level)
    runner.challenge.team1 = [[f'character{i}', 0] for i in range(4)]
    runner.challenge.team2 = [[f'character{i}', 0] for i in range(4, 8)]
    runner.team3 = [[f'character{i}', 0] for i in range(8, 12)]
    clock = count()
    globals_ = runner.run.__func__.__globals__
    monkeypatch.setitem(globals_, 'time', SimpleNamespace(sleep=Mock(), monotonic=lambda: next(clock)))
    return SimpleNamespace(runner=runner, globals=globals_, context=challenge,
                           auto=challenge.automation, cfg=globals_['cfg'])


def test_regular_mode_accepts_locked_mode_selector(stellar):
    stellar.auto.find_element.side_effect = None
    stellar.auto.find_element.return_value = False
    stellar.auto.click_element.side_effect = None
    stellar.auto.click_element.return_value = False
    stellar.runner.ensure_mode(False)
    stellar.auto.click_element.assert_not_called()


def test_switch_checks_mode_after_click_and_retries(stellar):
    state = {'mode': '常规模式', 'clicks': 0}
    stellar.auto.find_element.side_effect = lambda target, *args, **kwargs: target == state['mode']

    def click(target, *args, **kwargs):
        state['clicks'] += 1
        if state['clicks'] == 2:
            state['mode'] = '星启模式'
        return True

    stellar.auto.click_element.side_effect = click
    stellar.runner.ensure_mode(True)
    assert state == {'mode': '星启模式', 'clicks': 2}
    assert {c.args[0] for c in stellar.auto.click_element.call_args_list} == {'常规模式'}


def test_missing_stellar_unlock_stops_after_finite_retries(stellar):
    stellar.auto.find_element.side_effect = None
    stellar.auto.find_element.return_value = False
    stellar.auto.click_element.side_effect = None
    stellar.auto.click_element.return_value = False
    with pytest.raises(RuntimeError, match='是否已解锁'):
        stellar.runner.ensure_mode(True)
    stellar.auto.click_element.assert_not_called()


def test_visible_stellar_selector_with_failed_click_does_not_run_regular_logic(stellar):
    stellar.auto.find_element.side_effect = lambda target, *args, **kwargs: target == '星启模式'
    stellar.auto.click_element.side_effect = None
    stellar.auto.click_element.return_value = False
    with pytest.raises(RuntimeError, match='无法确认常规模式'):
        stellar.runner.ensure_mode(False)
    assert stellar.auto.click_element.call_count == 5


@pytest.mark.parametrize('bad_team', [[], [[f'character{i}', 0] for i in range(8, 13)], [['same', 0]] * 4])
def test_incomplete_or_duplicate_third_team_fails_before_game_actions(stellar, bad_team):
    stellar.runner.team3 = bad_team
    with pytest.raises(ValueError):
        stellar.runner.validate_teams()
    stellar.auto.find_element.assert_not_called()
    stellar.auto.click_element.assert_not_called()


def test_duplicate_across_teams_is_rejected(stellar):
    stellar.runner.team3[0] = stellar.runner.challenge.team1[0]
    with pytest.raises(ValueError, match='重复'):
        stellar.runner.validate_teams()


def test_teams_are_validated_only_when_stellar_is_enabled(stellar):
    stellar.runner.validate_teams()
    stellar.runner.enabled = False
    stellar.runner.team3 = []
    stellar.runner.validate_teams()


@pytest.mark.parametrize('members', [1, 2, 3])
def test_short_teams_are_accepted_and_techniques_use_compacted_slots(stellar, monkeypatch, members):
    owner = stellar.runner.challenge
    owner.team1 = owner.team1[:members]
    owner.team2 = owner.team2[:members]
    stellar.runner.team3 = stellar.runner.team3[:members]
    stellar.runner.validate_teams()
    team = stellar.runner.team3
    team[-1][1] = -1
    globals_ = owner.use_technique_and_attack_monster.__func__.__globals__
    monkeypatch.setitem(globals_, 'time', SimpleNamespace(sleep=Mock()))
    owner.use_technique_and_attack_monster(team)
    keys = [c.args[0] for c in stellar.auto.press_key.call_args_list]
    assert str(members) in keys
    assert not set(map(str, range(members + 1, 5))).intersection(keys)


def test_node_controls_use_window_size_and_ocr_anchor(stellar, monkeypatch):
    monkeypatch.setattr(stellar.runner, '_node', lambda number: ((700, 500), (730, 520)))
    monkeypatch.setattr(stellar.runner, '_window_region', lambda: (100, 50, 1280, 720))
    stellar.runner._click_node_control(3)
    stellar.auto.click_element_with_pos.assert_called_once_with(((1092, 542), (1092, 542)))


















@pytest.mark.parametrize('mode', ['虚构叙事', '混沌回忆'])
def test_stellar_configures_three_teams_then_buffs_for_modes_that_need_them(stellar, monkeypatch, mode):
    stellar.runner.challenge.name = mode
    controls = Mock()
    monkeypatch.setattr(stellar.runner, '_click_node_control', controls)
    select = Mock(return_value=True)
    stellar.runner.challenge.select_buff_effect = Mock(return_value=True)
    monkeypatch.setattr(stellar.globals['BaseChallenge'], 'select_characters', select)
    stellar.auto.find_element.side_effect = None
    stellar.auto.find_element.return_value = True
    stellar.auto.click_element.side_effect = None
    stellar.auto.click_element.return_value = True
    stellar.runner._prepare_teams()
    assert select.call_args_list == [
        call(stellar.runner.challenge, team, None, switch_team=False)
        for team in (stellar.runner.challenge.team1, stellar.runner.challenge.team2, stellar.runner.team3)
    ]
    expected = [call(1), call(2), call(3)]
    if mode == '虚构叙事':
        expected += [call(1, buff=True), call(2, buff=True), call(3, buff=True)]
    assert controls.call_args_list == expected
    assert stellar.runner.challenge.select_buff_effect.call_count == (3 if mode == '虚构叙事' else 0)






def test_chaos_stellar_starts_with_button_label_from_screenshot(stellar, monkeypatch):
    owner = stellar.runner.challenge
    owner.name = '混沌回忆'
    owner.use_technique_and_attack_monster = Mock()
    for name in ('ensure_mode', '_open_highest_level', '_prepare_teams', '_wait_ready', '_wait_node_end'):
        monkeypatch.setattr(stellar.runner, name, Mock())
    stellar.auto.click_element.side_effect = lambda targets, *args, **kwargs: '「混沌回忆」' in targets
    stellar.runner.run()
    stellar.runner._wait_ready.assert_called_once_with(1)
    assert owner.use_technique_and_attack_monster.call_count == 3


def test_chaos_closes_each_node_popup_three_times_before_using_techniques(stellar, monkeypatch):
    owner = stellar.runner.challenge
    owner.name = '混沌回忆'
    events = []
    for name in ('ensure_mode', '_open_highest_level', '_prepare_teams'):
        monkeypatch.setattr(stellar.runner, name, Mock())
    monkeypatch.setattr(stellar.runner, '_ready', Mock(return_value=True))
    clicks = Mock(side_effect=lambda *args: events.append('dismiss') or True)
    monkeypatch.setattr(stellar.runner, '_click_ratio', clicks)
    owner.use_technique_and_attack_monster = Mock(side_effect=lambda team: events.append(team))

    def finish_node(number):
        if number < 3:
            stellar.runner._wait_ready(number + 1)
            return None
        return False

    monkeypatch.setattr(stellar.runner, '_wait_node_end', finish_node)
    stellar.auto.click_element.side_effect = None
    stellar.auto.click_element.return_value = True
    stellar.runner.run()
    assert events == [
        'dismiss', 'dismiss', 'dismiss', owner.team1,
        'dismiss', 'dismiss', 'dismiss', owner.team2,
        'dismiss', 'dismiss', 'dismiss', stellar.runner.team3,
    ]
    assert clicks.call_args_list == [call(0.5, 0.97)] * 9


def test_stellar_character_search_scrolls_list_instead_of_enemy_level(stellar, monkeypatch):
    owner = stellar.runner.challenge
    monkeypatch.setitem(owner.select_characters.__func__.__globals__, 'time', SimpleNamespace(sleep=Mock()))
    state = {'cursor_in_list': False, 'scrolled': False}
    list_crop = (30 / 1920, 115 / 1080, 530 / 1920, 810 / 1080)

    def click(target, *args, **kwargs):
        if target.endswith('/DanHeng.png'):
            assert kwargs.get('crop') == list_crop
            assert kwargs.get('take_screenshot') is True
            return state['scrolled']
        if target == '等级':
            # 全屏 OCR 会先命中右侧敌人的“等级：95”。
            state['cursor_in_list'] = kwargs.get('crop') == list_crop
        return True

    def scroll(lines, direction, *args):
        assert state['cursor_in_list'], '滚轮不能落在右侧敌人区域'
        state['scrolled'] = direction == -1

    stellar.auto.click_element.side_effect = click
    stellar.auto.mouse_scroll.side_effect = scroll
    assert owner.select_characters([['DanHeng', 0]], None, switch_team=False)
    assert stellar.auto.mouse_scroll.call_args_list == [call(19, -1, False), call(19, 1, False)]


@pytest.mark.parametrize('number,button', [(1, '前往节点二'), (2, '前往节点三')])
def test_node_results_click_only_expected_next_button_and_wait_for_ready(stellar, monkeypatch, number, button):
    state = {'ready': False, 'clicks': 0}
    monkeypatch.setattr(stellar.runner, '_ready', lambda: state['ready'])
    stellar.auto.find_element.side_effect = lambda target, *args, **kwargs: target == button

    def click(target, *args, **kwargs):
        assert target == button
        state['clicks'] += 1
        state['ready'] = state['clicks'] == 2
        return True

    stellar.auto.click_element.side_effect = click
    stellar.runner._wait_node_end(number)
    assert state == {'ready': True, 'clicks': 2}


def test_unknown_intermediate_settlement_is_not_treated_as_completion(stellar):
    stellar.auto.find_element.side_effect = lambda target, *args, **kwargs: isinstance(target, list)
    with pytest.raises(RuntimeError, match='前往节点二'):
        stellar.runner._wait_node_end(1)
    stellar.auto.click_element.assert_not_called()


@pytest.mark.parametrize('title,button', [
    ('战斗失败', '返回忘却之庭'),
    ('挑战失败', '返回虚构叙事'),
    ('挑战失败', '返回末日幻影'),
])
def test_failure_handler_accepts_different_failure_titles_and_return_buttons(stellar, title, button):
    stellar.auto.find_element.side_effect = lambda target, *args, **kwargs: kwargs.get('include') and target in title
    stellar.auto.click_element.side_effect = lambda target, *args, **kwargs: kwargs.get('include') and target in button
    assert stellar.runner._return_after_failure() is True
    stellar.auto.click_element.assert_called_once_with(
        '返回', 'text', max_retries=5, crop=(0.2, 0.75, 0.6, 0.25), include=True)
    assert stellar.runner.result is False
    assert stellar.runner.challenge.max_level == 0
    stellar.cfg.save_timestamp.assert_not_called()


def test_failure_with_missing_return_button_stops_instead_of_advancing(stellar):
    stellar.auto.find_element.side_effect = None
    stellar.auto.find_element.return_value = True
    stellar.auto.click_element.side_effect = None
    stellar.auto.click_element.return_value = False
    with pytest.raises(RuntimeError, match='未能点击返回按钮'):
        stellar.runner._return_after_failure()
    assert stellar.runner.result is None


@pytest.mark.parametrize('failed_node', [1, 2, 3])
def test_failure_at_any_chaos_node_returns_without_starting_later_teams(stellar, monkeypatch, failed_node):
    owner = stellar.runner.challenge
    owner.name = '混沌回忆'
    owner.return_to_stage_list = None
    for name in ('ensure_mode', '_open_highest_level', '_prepare_teams', '_wait_ready'):
        monkeypatch.setattr(stellar.runner, name, Mock())
    owner.use_technique_and_attack_monster = Mock()

    def find(target, *args, **kwargs):
        number = owner.use_technique_and_attack_monster.call_count
        if target == '失败':
            return number == failed_node
        return target == ('前往节点二' if number == 1 else '前往节点三')

    stellar.auto.find_element.side_effect = find
    stellar.auto.click_element.side_effect = None
    stellar.auto.click_element.return_value = True
    assert stellar.runner.run() is False
    assert owner.use_technique_and_attack_monster.call_count == failed_node
    assert stellar.runner.result is False
    assert owner.max_level == 0
    assert stellar.auto.click_element.call_args.args[0] == '返回'
    stellar.cfg.save_timestamp.assert_not_called()


@pytest.mark.parametrize('succeeded', [True, False])
def test_node_three_reuses_native_fight_result_and_return_confirmation(stellar, succeeded):
    stellar.runner.challenge.check_fight = Mock(return_value=succeeded)
    stellar.runner.challenge.return_to_stage_list = Mock()
    assert stellar.runner._wait_node_end(3) is succeeded
    stellar.runner.challenge.check_fight.assert_called_once_with(30 * 60, final=True)
    stellar.runner.challenge.return_to_stage_list.assert_called_once()
    assert stellar.runner.result is succeeded
    assert stellar.runner.challenge.max_level == (4 if succeeded else 0)
    stellar.auto.click_element.assert_not_called()
    stellar.auto.find_element.assert_not_called()
    stellar.auto.press_key.assert_not_called()
    stellar.cfg.save_timestamp.assert_not_called()


@pytest.mark.parametrize('failed', [True, False])
def test_final_result_uses_native_failure_image_without_ocr_titles(stellar, failed):
    def find(target, find_type, *args, **kwargs):
        if find_type == 'text':
            return False
        if target.endswith('/back.png'):
            return True
        if target.endswith('/fail.png'):
            return failed
        return False

    stellar.auto.find_element.side_effect = find
    stellar.runner.challenge.return_to_stage_list = Mock()
    assert stellar.runner._wait_node_end(3) is (not failed)
    assert stellar.runner.result is (not failed)
    assert stellar.runner.challenge.max_level == (0 if failed else 4)
    stellar.runner.challenge.return_to_stage_list.assert_called()


def test_unconfirmed_other_challenge_return_still_preserves_screen(stellar):
    stellar.runner.challenge.return_to_stage_list = None
    with pytest.raises(SystemExit) as stopped:
        stellar.runner._finish_settlement(True)
    assert stopped.value.code == 0
    assert stellar.runner.result is None
    stellar.auto.click_element.assert_not_called()


def test_failed_return_does_not_record_clear_or_collect_rewards(stellar):
    stellar.runner.challenge.return_to_stage_list = Mock(side_effect=RuntimeError('未返回关卡列表'))
    with pytest.raises(RuntimeError, match='未返回关卡列表'):
        stellar.runner._finish_settlement(True)
    assert stellar.runner.result is None
    assert stellar.runner.challenge.max_level == 0
    stellar.cfg.save_timestamp.assert_not_called()


@pytest.mark.parametrize('succeeded', [True, False])
def test_runs_teams_in_order_and_returns_before_native_cleanup(stellar, monkeypatch, succeeded):
    owner = stellar.runner.challenge
    owner.prepare = Mock(return_value=True)
    owner.start_challenges = Mock(return_value=True)
    events = []
    owner.return_to_stage_list = Mock(side_effect=lambda: events.append('returned'))
    owner.collect_rewards = Mock(side_effect=lambda: events.append('cleanup'))
    owner.use_technique_and_attack_monster = Mock()
    for name in ('ensure_mode', '_open_highest_level', '_prepare_teams', '_wait_ready'):
        monkeypatch.setattr(stellar.runner, name, Mock())
    visited = []

    def wait(number):
        visited.append(number)
        if number == 3:
            return stellar.runner._finish_settlement(succeeded)

    monkeypatch.setattr(stellar.runner, '_wait_node_end', wait)
    stellar.auto.click_element.side_effect = None
    stellar.auto.click_element.return_value = True
    owner.run()
    assert visited == [1, 2, 3]
    assert owner.use_technique_and_attack_monster.call_args_list == [
        call(team) for team in (owner.team1, owner.team2, stellar.runner.team3)
    ]
    owner.start_challenges.assert_not_called()
    owner.stellar.ensure_mode.assert_called_once_with(True)
    owner.collect_rewards.assert_called_once()
    assert events == ['returned', 'cleanup']
    assert stellar.runner.result is succeeded
    assert owner.max_level == (4 if succeeded else 0)
    stellar.cfg.save_timestamp.assert_not_called()


def test_regular_mode_never_enters_stellar(stellar):
    owner = stellar.runner.challenge
    owner.stellar.enabled = False
    owner.prepare = Mock(return_value=True)
    owner.start_challenges = Mock()
    owner.collect_rewards = Mock()
    owner.stellar.ensure_mode = Mock()
    owner.stellar.run = Mock()
    owner.run()
    owner.start_challenges.assert_called_once()
    owner.collect_rewards.assert_called_once()
    owner.stellar.ensure_mode.assert_called_once_with(False)
    owner.stellar.run.assert_not_called()


def test_locked_stellar_mode_does_not_fall_back_to_regular(stellar):
    owner = stellar.runner.challenge
    owner.prepare = Mock(return_value=True)
    owner.start_challenges = Mock()
    owner.collect_rewards = Mock()
    stellar.auto.find_element.side_effect = None
    stellar.auto.find_element.return_value = False
    with pytest.raises(RuntimeError, match='是否已解锁'):
        owner.run()
    owner.start_challenges.assert_not_called()
    owner.collect_rewards.assert_not_called()


def test_range_below_highest_only_runs_selected_regular_levels(stellar):
    owner = stellar.runner.challenge
    owner.level_range = (1, 2)
    owner.prepare = Mock(return_value=True)
    owner.start_challenges = Mock(return_value=True)
    owner.collect_rewards = Mock()
    owner.stellar.ensure_mode = Mock()
    owner.stellar.run = Mock()
    owner.run()
    owner.stellar.ensure_mode.assert_called_once_with(False)
    owner.stellar.run.assert_not_called()
    owner.start_challenges.assert_called_once()
    owner.collect_rewards.assert_called_once()


@pytest.mark.parametrize('third_team', [[], [['character0', 0]], [['unknown', 99]], 'invalid'])
def test_regular_only_range_ignores_third_team_until_last_level_is_selected(stellar, third_team):
    owner = stellar.runner.challenge
    owner.level_range = [1, 3]
    stellar.runner.team3 = third_team
    owner.prepare = Mock(return_value=True)
    owner.start_challenges = Mock(return_value=True)
    owner.collect_rewards = Mock()
    stellar.runner.ensure_mode = Mock()
    stellar.runner.run = Mock()
    owner.run()
    owner.start_challenges.assert_called_once()
    stellar.runner.run.assert_not_called()
    assert stellar.runner.team3 == third_team
    owner.level_range = [1, 4]
    with pytest.raises(ValueError):
        stellar.runner.validate_teams()


def test_regular_only_range_rejects_duplicate_active_teams(stellar):
    owner = stellar.runner.challenge
    owner.level_range = [1, 3]
    owner.team2[0] = owner.team1[0]
    with pytest.raises(ValueError, match='重复'):
        stellar.runner.validate_teams()


@pytest.mark.parametrize('highest,first,last', [(12, 7, 12), (4, 3, 4), (4, 4, 4), (4, 1, 2)])
def test_range_routing_keeps_selected_bounds_and_collects_once(stellar, highest, first, last):
    runner, owner = stellar.runner, stellar.runner.challenge
    runner.highest_level = highest
    owner.level_range = [first, last]
    events = []
    runner.ensure_mode = Mock(side_effect=lambda mode: events.append(('mode', mode)))

    def regular():
        events.append(('regular', owner.level_range))
        owner.max_level = min(last, highest - 1)
        return True

    owner.start_challenges = Mock(side_effect=regular)

    def run_stellar():
        events.append('stellar')
        owner.max_level = highest
        return True

    runner.run = Mock(side_effect=run_stellar)
    owner.collect_rewards = Mock(side_effect=lambda: events.append('rewards'))
    runner.run_selected_levels()
    expected = []
    if first < highest:
        expected += [('mode', False), ('regular', (first, min(last, highest - 1)))]
    if last == highest:
        expected.append('stellar')
    assert events == expected + ['rewards']
    assert owner.level_range == [first, last]
    assert owner.max_level == last


def test_regular_failure_stops_before_stellar_and_restores_range(stellar):
    owner = stellar.runner.challenge
    owner.level_range = [1, 4]
    owner.start_challenges = Mock(return_value=False)
    owner.collect_rewards = Mock()
    stellar.runner.ensure_mode = Mock()
    stellar.runner.run = Mock()
    assert stellar.runner.run_selected_levels() is False
    assert owner.level_range == [1, 4]
    stellar.runner.run.assert_not_called()
    owner.collect_rewards.assert_called_once()


def test_regular_exception_restores_range_without_starting_stellar(stellar):
    owner = stellar.runner.challenge
    owner.level_range = [1, 4]
    owner.start_challenges = Mock(side_effect=RuntimeError('战斗异常'))
    owner.collect_rewards = Mock()
    stellar.runner.ensure_mode = Mock()
    stellar.runner.run = Mock()
    with pytest.raises(RuntimeError, match='战斗异常'):
        stellar.runner.run_selected_levels()
    assert owner.level_range == [1, 4]
    owner.collect_rewards.assert_not_called()
    stellar.runner.run.assert_not_called()


@pytest.mark.parametrize('levels', [(3, 2), (0, 4), (1, 5), (True, 4), (1,), None])
def test_invalid_range_is_rejected_before_ui_actions(stellar, levels):
    stellar.runner.challenge.level_range = levels
    with pytest.raises(ValueError, match='关卡范围'):
        stellar.runner.run_selected_levels()
    stellar.auto.click_element.assert_not_called()
