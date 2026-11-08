"""星启编队、节点推进及最终结算。"""

import importlib.util
import sys
from itertools import count
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, call, patch

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


@pytest.fixture
def chaos(stellar):
    # 复用现有隔离环境，加载真正的混沌回忆结算及领奖代码。
    source = stellar.context.module.__dict__
    package = ModuleType('_chaos_settlement_test')
    package.__path__ = [str(Path(__file__).parents[2] / 'tasks/challenge')]
    stubs = {package.__name__: package}
    for name, members in {
        'module.screen': ['screen'],
        'module.automation': ['auto'],
        'module.automation.screenshot': ['Screenshot'],
        'module.config': ['cfg'],
        'module.logger': ['log'],
        'module.notification.notification': ['NotificationLevel'],
        'tasks.base.base': ['Base'],
        f'{package.__name__}.basechallenge': ['BaseChallenge'],
        f'{package.__name__}.stellar': ['StellarChallenge'],
    }.items():
        stub = ModuleType(name)
        stub.__dict__.update({member: source[member] for member in members})
        stubs[name] = stub
    with patch.dict(sys.modules, stubs):
        spec = importlib.util.spec_from_file_location(
            f'{package.__name__}.memoryofchaos', Path(package.__path__[0]) / 'memoryofchaos.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    module.time = stellar.globals['time']
    owner = module.MemoryOfChaos(
        stellar.runner.challenge.team1, stellar.runner.challenge.team2, (12, 12),
        team3=stellar.runner.team3, stellar_enable=True)
    owner.stellar.run = Mock(side_effect=lambda: owner.stellar._wait_node_end(3))
    return SimpleNamespace(owner=owner, module=module, context=stellar.context, auto=stellar.auto)


def test_regular_mode_accepts_locked_mode_selector(stellar):
    stellar.auto.find_element.side_effect = None
    stellar.auto.find_element.return_value = False
    stellar.auto.click_element.side_effect = None
    stellar.auto.click_element.return_value = False
    stellar.runner.ensure_mode(False)
    stellar.auto.click_element.assert_not_called()


def test_regular_mode_clicks_ocr_option_when_both_modes_are_visible(stellar):
    stellar.auto.find_element.side_effect = lambda target, *args, **kwargs: target in ('常规模式', '星启模式')
    stellar.auto.click_element.side_effect = None
    stellar.auto.click_element.return_value = True
    stellar.runner.ensure_mode(False)
    stellar.auto.click_element.assert_called_once_with(
        '常规模式', 'text', crop=(0.55, 0.15, 0.4, 0.25), include=False)


def test_apocalyptic_regular_mode_clicks_option_in_lower_selector(stellar):
    stellar.runner.challenge.name = '末日幻影'
    stellar.auto.find_element.side_effect = lambda target, *args, **kwargs: target in ('常规模式', '星启模式')
    stellar.auto.click_element.side_effect = None
    stellar.auto.click_element.return_value = True
    stellar.runner.ensure_mode(False)
    stellar.auto.click_element.assert_called_once_with(
        '常规模式', 'text', crop=(0.40, 0.65, 0.20, 0.08), include=False)


def test_regular_mode_does_not_accept_visible_option_after_failed_click(stellar):
    stellar.auto.find_element.side_effect = lambda target, *args, **kwargs: target in ('常规模式', '星启模式')
    stellar.auto.click_element.side_effect = None
    stellar.auto.click_element.return_value = False
    with pytest.raises(RuntimeError, match='无法确认常规模式'):
        stellar.runner.ensure_mode(False)
    assert stellar.auto.click_element.call_count == 5


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


def test_highest_level_dismisses_quick_clear_rewards_before_configuring(stellar, monkeypatch):
    state = {'page': 'reward'}
    owner = stellar.runner.challenge
    owner.find_level = Mock(return_value=((1, 1), (2, 2)))
    owner.judge_stars = Mock(return_value=0)
    owner.max_star = 3
    monkeypatch.setattr(stellar.runner, '_node', Mock())

    def find(target, *args, **kwargs):
        if target == '快速通关':
            return state['page'] == 'reward'
        return state['page'] == 'teams' and target in ('编队', '星启模式')

    def click(target, *args, **kwargs):
        if target == '确认':
            state['page'] = 'teams'
        return True

    stellar.auto.find_element.side_effect = find
    stellar.auto.click_element.side_effect = click
    assert stellar.runner._open_highest_level() is True
    stellar.runner._node.assert_has_calls([call(1), call(2), call(3)])


def test_quick_clear_reward_confirmation_failure_stops(stellar):
    owner = stellar.runner.challenge
    owner.find_level = Mock(return_value=((1, 1), (2, 2)))
    owner.judge_stars = Mock(return_value=0)
    owner.max_star = 3
    stellar.auto.find_element.side_effect = lambda target, *args, **kwargs: target == '快速通关'
    stellar.auto.click_element.side_effect = lambda target, *args, **kwargs: target != '确认'
    with pytest.raises(RuntimeError, match='快速通关奖励'):
        stellar.runner._open_highest_level()


def test_apocalyptic_uses_bottom_mode_switch(stellar):
    stellar.runner.challenge.name = '末日幻影'

    def find(target, *args, **kwargs):
        assert kwargs['crop'] == (0.40, 0.65, 0.20, 0.08)
        return target == '星启模式'

    stellar.auto.find_element.side_effect = find
    stellar.runner.ensure_mode(True)


@pytest.mark.parametrize('node', ['节点一', '节点—', '节点二', '节点三'])
@pytest.mark.parametrize('level_opens_details', [False, True])
def test_apocalyptic_opens_node_details_then_real_character_list(stellar, node, level_opens_details):
    stellar.runner.challenge.name = '末日幻影'
    state = {'page': 'overview', 'highest': False}

    def find(target, *args, **kwargs):
        if isinstance(target, list):
            # 详情页节点标题始终 OCR 失败，仍应直接点击“更换编队”。
            assert kwargs['crop'] == (0.20, 0.74, 0.60, 0.07)
            return state['page'] == 'overview' and node in target
        if target == '角色列表':
            return state['page'] == 'teams'
        if target == '星启模式':
            return True
        # 两个页面都有“编队”标题，不能据此跳过“更换编队”。
        return target == '编队' and state['page'] in ('details', 'teams')

    def click(target, *args, **kwargs):
        if target == '04':
            assert state['page'] == 'overview'
            state['highest'] = True
            if level_opens_details:
                state['page'] = 'details'
        elif isinstance(target, list):
            assert state['highest'] and state['page'] == 'overview'
            state['page'] = 'details'
        elif target == '更换编队':
            if state['page'] != 'details':
                return False
            state['page'] = 'teams'
        else:
            pytest.fail(f'意外按钮：{target}')
        return True

    stellar.auto.find_element.side_effect = find
    stellar.auto.click_element.side_effect = click
    stellar.runner._open_highest_level()
    assert state == {'page': 'teams', 'highest': True}


def test_apocalyptic_missing_overview_anchor_never_clicks(stellar):
    stellar.runner.challenge.name = '末日幻影'
    stellar.auto.find_element.side_effect = None
    stellar.auto.find_element.return_value = False
    with pytest.raises(RuntimeError, match='主页的节点入口'):
        stellar.runner._open_highest_level()
    stellar.auto.click_element.assert_not_called()


def test_apocalyptic_stuck_on_details_does_not_start_selecting_characters(stellar):
    stellar.runner.challenge.name = '末日幻影'
    stellar.auto.find_element.side_effect = lambda target, *args, **kwargs: isinstance(target, list)
    stellar.auto.click_element.side_effect = None
    stellar.auto.click_element.return_value = True
    with pytest.raises(RuntimeError, match='未进入末日幻影'):
        stellar.runner._open_highest_level()
    assert stellar.auto.click_element.call_count == 11


@pytest.mark.parametrize('stars,skipped', [(3, True), (2, False), (None, False)])
def test_full_highest_level_is_not_challenged_again(stellar, monkeypatch, stars, skipped):
    owner = stellar.runner.challenge
    monkeypatch.setattr(owner, 'find_level', Mock(return_value=(100, 200)))
    monkeypatch.setattr(owner, 'judge_stars', Mock(return_value=stars))
    monkeypatch.setattr(stellar.runner, 'ensure_mode', Mock())
    if skipped:
        assert stellar.runner.run() is None
        stellar.cfg.save_timestamp.assert_called_once_with('purefiction_timestamp')
        stellar.auto.click_element.assert_not_called()
    else:
        # 未满星或无法判断星数时照常点击最高关进入编队。
        with pytest.raises(RuntimeError, match='点击星启模式最高关失败'):
            stellar.runner.run()
        stellar.cfg.save_timestamp.assert_not_called()
    owner.judge_stars.assert_called_once_with((100, 200))
    assert owner.max_level == 0
    assert stellar.runner.result is None


def test_selected_range_with_full_highest_level_records_run_without_clear(stellar, monkeypatch):
    owner = stellar.runner.challenge
    owner.level_range = (3, 4)
    monkeypatch.setattr(owner, 'start_challenges', Mock(return_value=True))
    monkeypatch.setattr(owner, 'collect_rewards', Mock())
    monkeypatch.setattr(owner, 'find_level', Mock(return_value=(100, 200)))
    monkeypatch.setattr(owner, 'judge_stars', Mock(return_value=3))
    monkeypatch.setattr(stellar.runner, 'ensure_mode', Mock())
    assert stellar.runner.run_selected_levels() is None
    assert stellar.runner.ensure_mode.call_args_list == [call(False), call(True)]
    stellar.cfg.save_timestamp.assert_called_once_with('purefiction_timestamp')
    owner.collect_rewards.assert_called_once()
    assert owner.max_level == 0


@pytest.mark.parametrize('number', [1, 2, 3])
@pytest.mark.parametrize('buff', [False, True])
def test_apocalyptic_slots_scale_without_node_text(stellar, monkeypatch, number, buff):
    stellar.runner.challenge.name = '末日幻影'
    stellar.auto.find_element.side_effect = lambda target, *args, **kwargs: target in ('角色列表', '星启模式')
    monkeypatch.setattr(stellar.runner, '_window_region', lambda: (100, 50, 1280, 720))
    stellar.runner._click_node_control(number, buff=buff)
    x = int(100 + 1280 * (1826 if buff else 1488) / 1920)
    point = (x, int(50 + 720 * (330 + (number - 1) * 216) / 1080))
    stellar.auto.click_element_with_pos.assert_called_once_with((point, point))


def test_apocalyptic_unconfirmed_team_screen_never_clicks_slots(stellar):
    stellar.runner.challenge.name = '末日幻影'
    stellar.auto.find_element.side_effect = lambda target, *args, **kwargs: target == '星启模式'
    with pytest.raises(RuntimeError, match='未确认末日幻影星启角色列表'):
        stellar.runner._click_node_control(1)
    stellar.auto.click_element_with_pos.assert_not_called()


def test_apocalyptic_confirms_teams_before_starting_challenge(stellar, monkeypatch):
    owner = stellar.runner.challenge
    owner.name = '末日幻影'
    state = {'page': 'teams'}
    for name in ('ensure_mode', '_open_highest_level', '_prepare_teams', '_wait_ready', '_wait_node_end'):
        monkeypatch.setattr(stellar.runner, name, Mock())
    owner.use_technique_and_attack_monster = Mock()

    def find(target, *args, **kwargs):
        return target in ({'角色列表', '星启模式'} if state['page'] == 'teams' else {'当前队伍'})

    def click(target, *args, **kwargs):
        if target == '确认':
            assert state['page'] == 'teams'
            state['page'] = 'details'
        else:
            assert '前往挑战' in target and state['page'] == 'details'
            state['page'] = 'battle'
        return True

    stellar.auto.find_element.side_effect = find
    stellar.auto.click_element.side_effect = click
    stellar.runner.run()
    assert state['page'] == 'battle'
    assert owner.use_technique_and_attack_monster.call_count == 3


def test_apocalyptic_failed_confirmation_does_not_start_challenge(stellar, monkeypatch):
    stellar.runner.challenge.name = '末日幻影'
    for name in ('ensure_mode', '_open_highest_level', '_prepare_teams'):
        monkeypatch.setattr(stellar.runner, name, Mock())
    stellar.auto.find_element.side_effect = None
    stellar.auto.find_element.return_value = True
    stellar.auto.click_element.side_effect = None
    stellar.auto.click_element.return_value = False
    with pytest.raises(RuntimeError, match='确认末日幻影星启编队失败'):
        stellar.runner.run()
    assert [c.args[0] for c in stellar.auto.click_element.call_args_list] == ['确认']


@pytest.mark.parametrize('mode', ['虚构叙事', '混沌回忆', '末日幻影'])
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
    if mode in ('虚构叙事', '末日幻影'):
        expected += [call(1, buff=True), call(2, buff=True), call(3, buff=True)]
    assert controls.call_args_list == expected
    assert stellar.runner.challenge.select_buff_effect.call_count == (3 if mode in ('虚构叙事', '末日幻影') else 0)


def test_apocalyptic_equips_three_buffs_before_confirming_and_starting(stellar, monkeypatch):
    owner = stellar.runner.challenge
    owner.name = '末日幻影'
    events = []
    for name in ('ensure_mode', '_open_highest_level', '_wait_ready', '_wait_node_end'):
        monkeypatch.setattr(stellar.runner, name, Mock())
    monkeypatch.setattr(stellar.runner, '_click_node_control',
                        lambda number, *, buff=False: events.append(('buff' if buff else 'team', number)))
    monkeypatch.setattr(stellar.globals['BaseChallenge'], 'select_characters', Mock(return_value=True))
    owner.select_buff_effect = Mock(side_effect=lambda: events.append('equipped') or True)
    owner.use_technique_and_attack_monster = Mock()
    monkeypatch.setattr(stellar.runner, '_confirm_apocalyptic_teams', lambda: events.append('confirm'))
    stellar.auto.find_element.side_effect = None
    stellar.auto.find_element.return_value = True

    def click(target, *args, **kwargs):
        if isinstance(target, list) and '前往挑战' in target:
            events.append('start')
        return True

    stellar.auto.click_element.side_effect = click
    stellar.runner.run()
    assert events == [
        ('team', 1), ('team', 2), ('team', 3),
        ('buff', 1), 'equipped', ('buff', 2), 'equipped', ('buff', 3), 'equipped',
        'confirm', 'start',
    ]


@pytest.mark.parametrize('failed_node', [1, 2, 3])
def test_apocalyptic_buff_failure_stops_before_confirming_or_starting(stellar, monkeypatch, failed_node):
    owner = stellar.runner.challenge
    owner.name = '末日幻影'
    for name in ('ensure_mode', '_open_highest_level', '_click_node_control', '_confirm_apocalyptic_teams'):
        monkeypatch.setattr(stellar.runner, name, Mock())
    monkeypatch.setattr(stellar.globals['BaseChallenge'], 'select_characters', Mock(return_value=True))
    owner.select_buff_effect = Mock(side_effect=[True] * (failed_node - 1) + [False])
    owner.use_technique_and_attack_monster = Mock()
    stellar.auto.find_element.side_effect = None
    stellar.auto.find_element.return_value = True
    stellar.auto.click_element.side_effect = None
    stellar.auto.click_element.return_value = True
    with pytest.raises(RuntimeError, match=f'节点{failed_node}装配增益失败'):
        stellar.runner.run()
    stellar.runner._confirm_apocalyptic_teams.assert_not_called()
    owner.use_technique_and_attack_monster.assert_not_called()
    assert not any(isinstance(c.args[0], list) for c in stellar.auto.click_element.call_args_list)


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


@pytest.mark.parametrize('switch_team', [False, True])
def test_stellar_character_search_scrolls_list_instead_of_enemy_level(stellar, monkeypatch, switch_team):
    from PIL import Image
    from tasks.base import list_drag

    owner = stellar.runner.challenge
    monkeypatch.setitem(owner.select_characters.__func__.__globals__, 'time', SimpleNamespace(sleep=Mock()))
    monkeypatch.setattr(list_drag, 'time', SimpleNamespace(sleep=Mock()))
    state = {'scrolled': False, 'fresh': False}
    list_crop = (30 / 1920, 115 / 1080, 530 / 1920, 810 / 1080)

    def click(target, *args, **kwargs):
        if target.endswith('/DanHeng.png'):
            assert kwargs.get('crop') == list_crop
            assert kwargs.get('take_screenshot') is True
            if state['scrolled']:
                assert state['fresh'], '拖动后必须重新截取列表，不能复用全屏缓存'
            return state['scrolled']
        return True

    def capture(crop):
        assert crop == list_crop
        state['fresh'] = True
        stellar.auto.screenshot = Image.new('RGB', (53, 81))
        return stellar.auto.screenshot, crop, 1

    def drag(start, end, duration):
        assert start[0] == end[0] == 430 / 1920
        assert all(list_crop[1] < point[1] < list_crop[1] + list_crop[3] for point in (start, end))
        state.update(scrolled=end[1] < start[1], fresh=False)
        return True

    stellar.auto.click_element.side_effect = click
    stellar.auto.take_screenshot.side_effect = capture
    stellar.auto.drag_mouse.side_effect = drag
    assert owner.select_characters([['DanHeng', 0]], './assets/images/forgottenhall/team1.png', switch_team=switch_team)
    assert stellar.auto.drag_mouse.call_args_list == [
        call((430 / 1920, 840 / 1080), (430 / 1920, 350 / 1080), 1.0),
        call((430 / 1920, 350 / 1080), (430 / 1920, 840 / 1080), 1.0),
    ]


@pytest.mark.parametrize('failed_drag', [1, 2])
def test_character_drag_interruption_stops_before_next_selection(stellar, monkeypatch, failed_drag):
    from PIL import Image
    from tasks.base import list_drag

    owner = stellar.runner.challenge
    monkeypatch.setitem(owner.select_characters.__func__.__globals__, 'time', SimpleNamespace(sleep=Mock()))
    monkeypatch.setattr(list_drag, 'time', SimpleNamespace(sleep=Mock()))
    selected = []
    drags = []

    def capture(crop):
        stellar.auto.screenshot = Image.new('RGB', (53, 81))
        return stellar.auto.screenshot, crop, 1

    def click(target, *args, **kwargs):
        if target.endswith('/DanHeng.png'):
            if drags:
                selected.append(target)
            return bool(drags)
        assert not target.endswith('/March7th.png'), '中断后不应继续选下一个角色'
        return True

    def drag(*args):
        drags.append(args)
        return len(drags) != failed_drag

    stellar.auto.take_screenshot.side_effect = capture
    stellar.auto.click_element.side_effect = click
    stellar.auto.drag_mouse.side_effect = drag
    assert owner.select_characters([['DanHeng', 0], ['March7th', 0]], None, switch_team=False) is False
    assert len(drags) == failed_drag
    assert len(selected) == failed_drag - 1


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


@pytest.mark.parametrize('return_kind', ['text', 'image'])
def test_chaos_final_settlement_returns_then_uses_existing_rewards_and_timestamp(chaos, return_kind):
    owner, auto, game = chaos.owner, chaos.auto, chaos.context.game
    events = []
    original_click = auto.click_element.side_effect

    def find(target, kind, *args, **kwargs):
        # 没有“挑战成功”或满星标识，准备图片即使命中也不能提前结束。
        if target == '返回忘却之庭':
            return return_kind == 'text' and game.page != 'stages'
        return target.endswith('/prepare_fight.png') or (
            return_kind == 'image' and target.endswith('/back.png') and game.page != 'stages')

    def click(target, kind, *args, **kwargs):
        if target == '返回忘却之庭' and return_kind == 'text':
            return original_click('返回虚构叙事', kind, *args, **kwargs)
        if target.endswith('/RedExclamationMark.png'):
            assert game.page == 'stages'
            events.append('rewards')
            return True
        if target.endswith('/receive.png'):
            if 'receive' in events:
                return False
            events.append('receive')
            return True
        return original_click(target, kind, *args, **kwargs)

    auto.find_element.side_effect = find
    auto.click_element.side_effect = click
    chaos.module.cfg.notify_template = {'LevelCleared': '{name} {level}'}
    chaos.module.cfg.save_timestamp.side_effect = lambda key: events.append('timestamp')
    assert owner.stellar.run_selected_levels() is True
    assert game.page == 'stages'
    assert game.clicks == 2  # 第一次只跳过动画，第二次才真正退出。
    assert owner.max_level == 12
    assert owner.stellar.result is True
    chaos.module.cfg.save_timestamp.assert_called_once_with('forgottenhall_timestamp')
    assert events == ['timestamp', 'rewards', 'receive']


def test_chaos_final_failure_returns_without_recording_clear(chaos):
    owner, auto, game = chaos.owner, chaos.auto, chaos.context.game

    def find(target, kind, *args, **kwargs):
        # 失败结算同样带有返回入口，只能靠标题区分结果。
        return game.page != 'stages' and target in ('返回忘却之庭', '失败')

    auto.find_element.side_effect = find
    assert owner.stellar.run_selected_levels() is False
    assert game.page == 'stages'
    assert owner.max_level == 0
    assert owner.stellar.result is False
    chaos.module.cfg.save_timestamp.assert_not_called()
    assert not any(c.args[0].endswith('/RedExclamationMark.png')
                   for c in auto.click_element.call_args_list)


@pytest.mark.parametrize('clickable', [True, False])
def test_chaos_failed_return_does_not_record_or_collect(chaos, clickable):
    chaos.context.game.clickable = clickable
    chaos.context.game.return_after = 99
    with pytest.raises(RuntimeError, match='结算后返回混沌回忆失败'):
        chaos.owner.stellar.run_selected_levels()
    assert chaos.owner.max_level == 0
    assert chaos.owner.stellar.result is None
    chaos.module.cfg.save_timestamp.assert_not_called()
    assert not any(c.args[0].endswith('/RedExclamationMark.png')
                   for c in chaos.auto.click_element.call_args_list)


def test_chaos_final_timeout_ignores_prepare_image_and_does_not_exit_program(chaos):
    chaos.auto.find_element.side_effect = lambda target, *args, **kwargs: target.endswith('/prepare_fight.png')
    with pytest.raises(RuntimeError, match='最终结算超时'):
        chaos.owner.check_fight(3, final=True)
    chaos.auto.click_element.assert_not_called()
    chaos.module.cfg.save_timestamp.assert_not_called()


@pytest.mark.parametrize('failure_image', [None, 'again.png', 'pause.png'])
def test_chaos_regular_settlement_keeps_original_result(chaos, failure_image):
    chaos.auto.find_element.side_effect = lambda target, *args, **kwargs: (
        target.endswith('/back.png') or (failure_image and target.endswith('/' + failure_image)))
    assert chaos.owner.check_fight(3) is (failure_image is None)


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
