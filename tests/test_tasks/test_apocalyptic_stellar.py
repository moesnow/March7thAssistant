"""末日幻影接通星启配置并保留常规分支。"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, call, patch

import pytest

from tests.test_tasks.test_purefiction_settlement import challenge


@pytest.fixture
def apocalyptic(challenge):
    source = challenge.module
    package_name = source.__package__
    package = ModuleType(package_name)
    stubs = {package_name: package}
    for name, members in {
        f'{package_name}.basechallenge': {'BaseChallenge': source.BaseChallenge},
        f'{package_name}.stellar': {'StellarChallenge': source.StellarChallenge},
        'tasks.base.base': {'Base': source.Base},
        'module.notification.notification': {'NotificationLevel': source.NotificationLevel},
        'module.automation.screenshot': {'Screenshot': source.Screenshot},
        'module.screen': {'screen': source.screen},
        'module.automation': {'auto': source.auto},
        'module.config': {'cfg': source.cfg},
        'module.logger': {'log': source.log},
    }.items():
        stub = ModuleType(name)
        stub.__dict__.update(members)
        stubs[name] = stub
    path = Path(__file__).parents[2] / 'tasks/challenge/apocalyptic.py'
    with patch.dict(sys.modules, stubs):
        spec = importlib.util.spec_from_file_location(f'{package_name}.apocalyptic', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    module.time = SimpleNamespace(sleep=Mock())
    return module.Apocalyptic([['one', 0]], [['two', 0]], level_range=(4, 4),
                              team3=[['three', -1]], stellar_enable=True)


def test_stellar_configuration_runs_shared_flow_instead_of_native(apocalyptic):
    apocalyptic.prepare = Mock(return_value=True)
    apocalyptic.start_challenges = Mock()
    apocalyptic.collect_rewards = Mock()
    apocalyptic.stellar.run = Mock()
    apocalyptic.run()
    apocalyptic.stellar.run.assert_called_once()
    assert apocalyptic.stellar.highest_level == 4
    assert apocalyptic.stellar.team3 == [['three', -1]]
    apocalyptic.start_challenges.assert_not_called()
    apocalyptic.collect_rewards.assert_called_once()


def test_invalid_stellar_teams_stop_before_entering_game(apocalyptic):
    apocalyptic.stellar.team3 = apocalyptic.team1
    apocalyptic.prepare = Mock()
    with pytest.raises(ValueError, match='重复'):
        apocalyptic.run()
    apocalyptic.prepare.assert_not_called()


def test_disabled_stellar_keeps_native_flow(apocalyptic):
    apocalyptic.stellar.enabled = False
    apocalyptic.prepare = Mock(return_value=True)
    apocalyptic.start_challenges = Mock()
    apocalyptic.collect_rewards = Mock()
    apocalyptic.stellar.run = Mock()
    apocalyptic.stellar.ensure_mode = Mock()
    apocalyptic.run()
    apocalyptic.stellar.ensure_mode.assert_called_once_with(False)
    apocalyptic.start_challenges.assert_called_once()
    apocalyptic.collect_rewards.assert_called_once()
    apocalyptic.stellar.run.assert_not_called()


@pytest.mark.parametrize('title,succeeded', [('挑战结束', False), ('挑战成功', True)])
def test_final_stellar_result_returns_without_native_two_node_detection(apocalyptic, title, succeeded):
    auto = apocalyptic.run.__func__.__globals__['auto']
    auto.find_element.side_effect = lambda target, *args, **kwargs: isinstance(target, list) and title in target
    auto.matched_text = title
    apocalyptic.check_fight = Mock(side_effect=AssertionError('不得走原生两节点结算'))
    apocalyptic.return_to_stage_list = Mock()
    assert apocalyptic.stellar._wait_node_end(3) is succeeded
    apocalyptic.return_to_stage_list.assert_called_once()
    assert apocalyptic.max_level == (4 if succeeded else 0)


def test_stellar_returns_before_collecting_rewards_even_with_zero_score(apocalyptic):
    apocalyptic.prepare = Mock(return_value=True)
    events = []
    apocalyptic.return_to_stage_list = Mock(side_effect=lambda: events.append('return'))
    apocalyptic.stellar.run = Mock(side_effect=lambda: apocalyptic.stellar._finish_settlement(False))
    apocalyptic.collect_rewards = Mock(side_effect=lambda: events.append('rewards'))
    apocalyptic.run()
    assert events == ['return', 'rewards']
    assert apocalyptic.max_level == 0


def test_stuck_return_stops_before_recording_result_or_collecting_rewards(apocalyptic):
    apocalyptic.prepare = Mock(return_value=True)
    apocalyptic.return_to_stage_list = Mock(side_effect=RuntimeError('返回失败'))
    apocalyptic.stellar.run = Mock(side_effect=lambda: apocalyptic.stellar._finish_settlement(True))
    apocalyptic.collect_rewards = Mock()
    with pytest.raises(RuntimeError, match='返回失败'):
        apocalyptic.run()
    assert apocalyptic.stellar.result is None
    assert apocalyptic.max_level == 0
    apocalyptic.collect_rewards.assert_not_called()


def test_returns_using_screenshot_button_and_retries_until_home(apocalyptic):
    globals_ = apocalyptic.run.__func__.__globals__
    screen, auto = globals_['screen'], globals_['auto']
    screen.check_screen.side_effect = [False, False, True]
    auto.click_element.side_effect = None
    auto.click_element.return_value = True
    apocalyptic.return_to_stage_list()
    assert auto.click_element.call_count == 2
    assert all(c.args[0] == '返回末日幻影' for c in auto.click_element.call_args_list)


def test_return_timeout_is_reported_instead_of_collecting_on_result_screen(apocalyptic):
    globals_ = apocalyptic.run.__func__.__globals__
    screen = globals_['screen']
    screen.check_screen.side_effect = None
    screen.check_screen.return_value = False
    with pytest.raises(RuntimeError, match='结算后返回末日幻影失败'):
        apocalyptic.return_to_stage_list()


@pytest.mark.parametrize('has_rewards', [True, False])
def test_zero_score_still_checks_existing_rewards_without_recording_clear(apocalyptic, has_rewards):
    globals_ = apocalyptic.run.__func__.__globals__
    auto, config, base = globals_['auto'], globals_['cfg'], globals_['Base']
    apocalyptic.stellar.result = False
    received = []

    def click(target, *args, **kwargs):
        if target.endswith('/RedExclamationMark.png'):
            return has_rewards
        if target.endswith('/receive.png'):
            received.append(target)
            return len(received) == 1
        return True

    auto.click_element.side_effect = click
    apocalyptic.collect_rewards()
    assert received == (['./assets/images/forgottenhall/receive.png'] * 2 if has_rewards else [])
    config.save_timestamp.assert_not_called()
    base.send_notification_with_screenshot.assert_not_called()
    if not has_rewards:
        globals_['log'].error.assert_not_called()


def test_unfinished_stellar_run_does_not_collect_rewards(apocalyptic):
    auto = apocalyptic.run.__func__.__globals__['auto']
    apocalyptic.collect_rewards()
    auto.click_element.assert_not_called()


@pytest.mark.parametrize('via_node', [False, True])
def test_regular_stage_opens_updated_entry_then_next_and_team_setup(apocalyptic, via_node):
    auto = apocalyptic.run.__func__.__globals__['auto']
    state = {'page': 'overview', 'selected': False}

    def find(target, *args, **kwargs):
        assert target == '角色列表'
        return state['page'] == 'teams'

    def click(target, *args, **kwargs):
        if target == '03':
            assert kwargs['crop'] == (0.20, 0.87, 0.60, 0.06)
            state['selected'] = True
        elif target == '更换编队':
            assert state['selected']
            x, y, width, height = kwargs['crop']
            button_y = 869 / 1080 if state['page'] == 'details' else 737 / 1080
            assert x <= 1700 / 1920 <= x + width and y <= button_y <= y + height
            if via_node and state['page'] == 'overview':
                return False
            state['page'] = 'intro'
        elif target == '下一步':
            assert state['page'] == 'intro'
            state['page'] = 'team_entry'
        elif target == '前往编队':
            assert state['page'] == 'team_entry'
            state['page'] = 'teams'
        elif isinstance(target, list):
            assert via_node and state['page'] == 'overview'
            assert set(target) == {'节点一', '节点—', '节点二'}
            state['page'] = 'details'
        else:
            pytest.fail(f'意外的按钮：{target}')
        return True

    auto.find_element.side_effect = find
    auto.click_element.side_effect = click
    assert apocalyptic._open_regular_teams(3)
    assert state == {'page': 'teams', 'selected': True}


def test_unplayed_regular_stage_can_use_go_to_challenge_entry(apocalyptic):
    auto = apocalyptic.run.__func__.__globals__['auto']
    state = {'page': 'overview'}
    auto.find_element.side_effect = lambda target, *args, **kwargs: state['page'] == 'teams'

    def click(target, *args, **kwargs):
        if target == '03':
            return True
        if target == '前往挑战':
            state['page'] = 'intro'
            return True
        if target == '下一步':
            assert state['page'] == 'intro'
            state['page'] = 'team_entry'
            return True
        if target == '前往编队':
            assert state['page'] == 'team_entry'
            state['page'] = 'teams'
            return True
        return False

    auto.click_element.side_effect = click
    assert apocalyptic._open_regular_teams(3)


@pytest.mark.parametrize('failed_button', ['下一步', '前往编队'])
def test_missing_required_intermediate_step_stops_before_selecting_characters(apocalyptic, failed_button):
    auto = apocalyptic.run.__func__.__globals__['auto']
    auto.find_element.side_effect = None
    auto.find_element.return_value = False
    clicked = []

    def click(target, *args, **kwargs):
        clicked.append(target)
        return target != failed_button

    auto.click_element.side_effect = click
    apocalyptic.prepare_level = Mock()
    assert apocalyptic.start_challenge(3) is False
    assert clicked == ['03', '更换编队', '下一步'] + (['前往编队'] if failed_button == '前往编队' else [])
    apocalyptic.prepare_level.assert_not_called()


def test_missing_regular_stage_entry_stops_before_configuring_teams(apocalyptic):
    auto = apocalyptic.run.__func__.__globals__['auto']
    auto.find_element.side_effect = None
    auto.find_element.return_value = False
    auto.click_element.side_effect = lambda target, *args, **kwargs: target == '03'
    apocalyptic.prepare_level = Mock()
    assert apocalyptic.start_challenge(3) is False
    apocalyptic.prepare_level.assert_not_called()


@pytest.mark.parametrize('has_confirm', [False, True])
def test_regular_start_confirms_updated_team_before_go_to_challenge(apocalyptic, has_confirm):
    auto = apocalyptic.run.__func__.__globals__['auto']
    clicks = []

    def click(target, *args, **kwargs):
        clicks.append(target)
        if target == '确认':
            return has_confirm
        return target == '前往挑战'

    auto.click_element.side_effect = click
    auto.find_element.side_effect = None
    auto.find_element.return_value = False
    apocalyptic.click_message_box = Mock()
    assert apocalyptic.start_level()
    assert clicks == ['确认', '前往挑战']
    apocalyptic.click_message_box.assert_called_once()


@pytest.mark.parametrize('team_name,node', [('team1', '节点一'), ('team2', '节点二')])
def test_regular_character_search_scrolls_left_list_and_refreshes_after_scroll(apocalyptic, monkeypatch, team_name, node):
    auto = apocalyptic.run.__func__.__globals__['auto']
    base_class = apocalyptic.__class__.__mro__[1]
    monkeypatch.setitem(base_class.select_characters.__globals__, 'time', SimpleNamespace(sleep=Mock()))
    apocalyptic.find_node = Mock(return_value=(800, 200))
    state = {'cursor_in_list': False, 'scrolled': False, 'selected': False}
    list_crop = (30 / 1920, 115 / 1080, 530 / 1920, 810 / 1080)

    def click(target, *args, **kwargs):
        if target.endswith('/CastoriceGossamerFlutter.png'):
            assert kwargs.get('crop') == list_crop
            assert kwargs.get('take_screenshot') is True
            state['selected'] = state['scrolled']
            return state['selected']
        if target == '等级':
            assert kwargs.get('action') == 'move'
            # 全屏等级识别会命中日志里的右侧敌人 (861, 214)。
            state['cursor_in_list'] = kwargs.get('crop') == list_crop
        return True

    def scroll(lines, direction, *args):
        assert state['cursor_in_list'], '不能在右侧敌人区域滚动'
        state['scrolled'] = direction == -1

    auto.click_element.side_effect = click
    auto.mouse_scroll.side_effect = scroll
    assert apocalyptic.select_characters([['CastoriceGossamerFlutter', 0]], team_name)
    apocalyptic.find_node.assert_called_once_with(node)
    assert state['selected']
    assert auto.mouse_scroll.call_args_list == [call(19, -1, False), call(19, 1, False)]


def test_missing_regular_team_node_does_not_click_or_scroll(apocalyptic):
    auto = apocalyptic.run.__func__.__globals__['auto']
    apocalyptic.find_node = Mock(return_value=False)
    assert apocalyptic.select_characters([['CastoriceGossamerFlutter', 0]], 'team1') is False
    auto.click_element.assert_not_called()
    auto.mouse_scroll.assert_not_called()
