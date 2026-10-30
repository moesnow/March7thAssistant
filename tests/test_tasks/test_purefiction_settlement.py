"""虚构叙事结算：点击后仍停留在结算页时，应重试并确认返回。"""

import importlib.util
import sys
from itertools import count
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def challenge():
    automation = Mock()
    automation.find_element.return_value = False
    automation.click_element.return_value = False
    screen = Mock()
    screen.check_screen.return_value = False
    stubs = {}
    for name, members in {
        'module.screen': {'screen': screen},
        'module.automation': {'auto': automation},
        'module.automation.screenshot': {'Screenshot': Mock()},
        'module.config': {'cfg': Mock()},
        'module.logger': {'log': Mock()},
        'module.notification.notification': {'NotificationLevel': Mock()},
        'tasks.base.base': {'Base': Mock()},
    }.items():
        stub = ModuleType(name)
        stub.__dict__.update(members)
        stubs[name] = stub

    path = Path(__file__).parents[2] / 'tasks/challenge'
    package = ModuleType('_purefiction_settlement_test')
    package.__path__ = [str(path)]
    stubs[package.__name__] = package
    with patch.dict(sys.modules, stubs):
        spec = importlib.util.spec_from_file_location(
            f'{package.__name__}.purefiction', path / 'purefiction.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

    clock = count()
    module.time = SimpleNamespace(sleep=Mock(), monotonic=lambda: next(clock))
    game = SimpleNamespace(page='animation', clicks=0, return_after=2, clickable=True)

    def find_element(target, *args, **kwargs):
        return target.endswith('/back.png') and game.page != 'stages'

    def click_element(target, find_type, *args, **kwargs):
        if game.page == 'stages' or not game.clickable:
            return False
        if target == '返回虚构叙事' or target.endswith('/back.png'):
            game.clicks += 1
            game.page = 'stages' if game.clicks >= game.return_after else 'summary'
            return True
        return False

    automation.find_element.side_effect = find_element
    automation.click_element.side_effect = click_element
    screen.check_screen.side_effect = lambda name: game.page == 'stages'
    return SimpleNamespace(
        instance=module.PureFiction([], []), module=module,
        automation=automation, screen=screen, game=game,
    )


def test_retries_when_first_click_only_reveals_result_summary(challenge):
    # 日志中的返回图片已匹配且点击成功，但随后仍显示“返回虚构叙事”。
    assert challenge.instance.check_fight(30) is True
    assert challenge.game.page == 'stages'
    assert challenge.game.clicks == 2
    challenge.screen.wait_for_screen_change.assert_not_called()


def test_ocr_miss_falls_back_to_return_image(challenge):
    click = challenge.automation.click_element.side_effect
    challenge.automation.click_element.side_effect = (
        lambda target, kind, *args, **kwargs:
        False if kind == 'text' else click(target, kind, *args, **kwargs)
    )
    assert challenge.instance.check_fight(30) is True
    assert challenge.game.page == 'stages'
    assert challenge.game.clicks == 2


@pytest.mark.parametrize('clickable', [True, False])
def test_stuck_settlement_stops_instead_of_reporting_success(challenge, clickable):
    challenge.game.clickable = clickable
    challenge.game.return_after = 99
    with pytest.raises(RuntimeError, match='结算后返回虚构叙事失败'):
        challenge.instance.check_fight(30)
    assert challenge.game.page != 'stages'
    assert challenge.module.time.sleep.call_count == 6  # 战斗等待一次，返回重试五次。
    challenge.screen.change_to.assert_not_called()


def test_failure_is_preserved_after_returning(challenge):
    find = challenge.automation.find_element.side_effect
    challenge.automation.find_element.side_effect = (
        lambda target, *args, **kwargs:
        target.endswith('/fail.png') or find(target, *args, **kwargs)
    )
    assert challenge.instance.check_fight(30) is False
    assert challenge.game.page == 'stages'


def test_already_back_does_not_click_again(challenge):
    challenge.game.page = 'stages'
    challenge.instance.return_to_stage_list()
    challenge.automation.click_element.assert_not_called()


def test_last_retry_is_verified(challenge):
    challenge.game.return_after = 5
    assert challenge.instance.check_fight(30) is True
    assert challenge.game.page == 'stages'
    assert challenge.game.clicks == 5


def test_next_room_does_not_trigger_settlement_return(challenge):
    challenge.automation.find_element.side_effect = (
        lambda target, *args, **kwargs: target.endswith('/prepare_fight.png')
    )
    assert challenge.instance.check_fight(30) is True
    challenge.automation.click_element.assert_not_called()
    challenge.screen.check_screen.assert_not_called()


def test_new_result_screen_uses_return_text_when_old_image_misses(challenge):
    challenge.game.page = 'summary'
    challenge.automation.find_element.side_effect = (
        lambda target, *args, **kwargs: target == '返回虚构叙事' and challenge.game.page == 'summary')
    assert challenge.instance.check_fight(30, final=True) is True
    assert challenge.game.page == 'stages'
    assert challenge.game.clicks == 2
    challenge.automation.press_key.assert_not_called()
    challenge.screen.change_to.assert_not_called()
    challenge.screen.wait_for_screen_change.assert_not_called()


@pytest.mark.parametrize('final', [False, True])
def test_battle_controls_override_false_ready_and_result_matches(challenge, final):
    def find(target, *args, **kwargs):
        if target.endswith('/battle_pause.png'):
            return True
        if target.endswith('/not_auto.png'):
            return False
        pytest.fail(f'战斗进行中不应判定准备或结算画面：{target}')

    challenge.automation.find_element.side_effect = find
    assert challenge.instance.check_fight(8, final=final) is False
    challenge.automation.click_element.assert_not_called()
    challenge.automation.press_key.assert_not_called()
    challenge.screen.check_screen.assert_not_called()
    challenge.screen.change_to.assert_not_called()
    challenge.screen.wait_for_screen_change.assert_not_called()


def test_final_room_does_not_finish_on_false_ready_match_during_animation(challenge):
    calls = 0

    def find(target, *args, **kwargs):
        nonlocal calls
        if target == '返回虚构叙事':
            calls += 1
            return calls >= 3
        # 模拟旧准备图一直会命中；最后一间不得使用它作为结束依据。
        assert not target.endswith('/prepare_fight.png')
        return False

    challenge.automation.find_element.side_effect = find
    assert challenge.instance.check_fight(30, final=True) is True
    assert calls == 3
    assert challenge.game.page == 'stages'
    challenge.screen.change_to.assert_not_called()


def test_two_rooms_wait_for_combat_and_return_before_next_level(challenge):
    owner, auto = challenge.instance, challenge.automation
    state = {'page': 'idle', 'room': 0, 'polls': 0}

    def start(team):
        state.update(page='battle', room=state['room'] + 1, polls=0)

    def find(target, *args, **kwargs):
        if target.endswith('/battle_pause.png') and state['page'] == 'battle':
            state['polls'] += 1
            if state['polls'] <= 2:
                return True
            state['page'] = 'ready' if state['room'] == 1 else 'summary'
        if target == '返回虚构叙事':
            return state['page'] == 'summary'
        # 复现旧图片在第二间战斗时误匹配；不能提前进入全局界面识别。
        return target.endswith('/prepare_fight.png')

    def click(target, *args, **kwargs):
        assert target == '返回虚构叙事' and state['page'] == 'summary'
        state['page'] = 'stages'
        return True

    owner.use_technique_and_attack_monster = Mock(side_effect=start)
    owner.check_fight = Mock(wraps=owner.check_fight)
    auto.find_element.side_effect = find
    auto.click_element.side_effect = click
    challenge.screen.check_screen.side_effect = lambda name: state['page'] == 'stages'
    assert owner.start_battle() is True
    assert state['page'] == 'stages'
    assert [c.kwargs for c in owner.check_fight.call_args_list] == [{'final': False}, {'final': True}]
    assert owner.use_technique_and_attack_monster.call_count == 2
    auto.press_key.assert_not_called()
    challenge.screen.change_to.assert_not_called()
    challenge.screen.wait_for_screen_change.assert_not_called()


def test_return_during_combat_never_invokes_screen_navigation_or_clicks(challenge):
    challenge.automation.find_element.side_effect = lambda target, *args, **kwargs: target.endswith('/battle_pause.png')
    with pytest.raises(RuntimeError, match='结算后返回虚构叙事失败'):
        challenge.instance.return_to_stage_list()
    challenge.screen.check_screen.assert_not_called()
    challenge.screen.change_to.assert_not_called()
    challenge.automation.press_key.assert_not_called()
    challenge.automation.click_element.assert_not_called()


def test_battle_detection_uses_top_right_controls_and_speed_fallback(challenge):
    auto = challenge.automation
    auto.find_element.side_effect = lambda target, *args, **kwargs: target.endswith('/battle_speed.png')
    assert challenge.instance.is_battle_active()
    assert [c.kwargs['crop'] for c in auto.find_element.call_args_list] == [
        (0.95, 0, 0.05, 0.08), (0.83, 0, 0.07, 0.08)]
