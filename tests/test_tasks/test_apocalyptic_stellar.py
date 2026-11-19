"""末日幻影接通星启配置并保留常规分支。"""

import importlib.util
import sys
from itertools import count
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, call, patch

import pytest

from tests.test_tasks.test_purefiction_settlement import challenge
from utils.pause import RunStopRequested


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
    clock = count()
    module.time = SimpleNamespace(sleep=Mock(), monotonic=lambda: next(clock))
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


@pytest.mark.parametrize(("show_boss_info", "failure"), [
    (True, None), (False, None), (True, "missing"), (True, "late"), (True, "stop")
])
def test_first_stellar_iv_opens_after_skipping_three_stars(apocalyptic, monkeypatch, show_boss_info, failure):
    runner = apocalyptic.stellar
    globals_ = runner.run.__func__.__globals__
    auto = globals_["auto"]
    apocalyptic.level_range = (3, 4)
    apocalyptic.prepare = Mock(return_value=True)
    apocalyptic.find_level = Mock(return_value=(100, 100))
    apocalyptic.judge_stars = Mock(return_value=3)
    apocalyptic.start_challenge = Mock(side_effect=AssertionError("不应重打常规关"))
    apocalyptic.collect_rewards = Mock()
    apocalyptic.use_technique_and_attack_monster = Mock()
    runner._prepare_teams = Mock()
    runner._wait_ready = Mock()
    runner._wait_node_end = Mock(return_value=True)
    runner._window_region = lambda: (0, 0, 1920, 1080)
    page, level, mode = "关卡", 4, "常规模式"
    elapsed = 0
    missed_entry = False
    pending_page = None
    clicks = []

    def sleep(seconds):
        nonlocal elapsed, page, pending_page
        elapsed += seconds
        if pending_page and elapsed >= pending_page[1]:
            page, pending_page = pending_page[0], None

    monkeypatch.setitem(globals_, "time", SimpleNamespace(sleep=sleep, monotonic=lambda: elapsed))

    def find(target, *args, **kwargs):
        nonlocal elapsed, missed_entry
        if page == "关卡":
            if target == "前往挑战" and show_boss_info and not missed_entry:
                missed_entry = True
                return None
            visible = (mode, "前往挑战") if level == 4 else ()
        elif page in ("节点一", "节点二", "节点三"):
            if page == "节点一" and target == ["下一步", "前往编队"]:
                if failure == "missing":
                    return None
                if failure == "late":
                    elapsed += 20
                if failure == "stop":
                    raise RunStopRequested()
            visible = ("首领信息", "星启模式", page, "前往编队" if page == "节点三" else "下一步")
        elif page == "角色列表":
            visible = ("角色列表", "星启模式", "前往挑战")
        else:
            visible = ("编队", "星启模式") if page == "编队" else ()
        for label in ([target] if isinstance(target, str) else target):
            if label in visible:
                auto.matched_text = label
                return label
        return None

    def click(target, *args, **kwargs):
        nonlocal level, mode, page
        if isinstance(target, list):
            assert page == "角色列表" and "前往挑战" in target
            target, page = "开始挑战", "战斗"
        elif target in ("03", "04"):
            assert page == "关卡"
            level = int(target)
        else:
            assert target == "常规模式" and page == "关卡" and level == 4
            mode = "星启模式"
        clicks.append(target)
        return True

    def click_position(button):
        nonlocal page, pending_page
        if page == "关卡":
            assert (level, mode, button) == (4, "星启模式", "前往挑战")
            if show_boss_info:
                pending_page = ("节点一", elapsed + 1.5)
            else:
                page = "编队"
        elif page == "节点一":
            assert button == "下一步"
            page = "节点二"
        elif page == "节点二":
            assert button == "下一步"
            if clicks.count("下一步") == 2:
                page = "节点三"
        elif page == "节点三":
            assert button == "前往编队"
            page = "编队"
        else:
            assert page == "编队" and button == ((1488, 330), (1488, 330))
            button, page = "展开角色列表", "角色列表"
        clicks.append(button)
        return True

    auto.find_element.side_effect = find
    auto.click_element.side_effect = click
    auto.click_element_with_pos.side_effect = click_position

    if failure:
        if failure == "stop":
            with pytest.raises(RunStopRequested):
                apocalyptic.run()
        else:
            with pytest.raises(RuntimeError, match="未进入末日幻影星启三节点编队界面"):
                apocalyptic.run()
        assert clicks == ["03", "04", "常规模式", "前往挑战"]
        runner._prepare_teams.assert_not_called()
        return

    apocalyptic.run()
    # 首领说明路径注入入口漏读、转场回执迟到和一次“下一步”点击未推进。
    intro = ["下一步", "下一步", "下一步", "前往编队"] if show_boss_info else []
    assert clicks == ["03", "04", "常规模式", "前往挑战", *intro, "展开角色列表", "开始挑战"]
    runner._prepare_teams.assert_called_once()
    runner._wait_ready.assert_called_once_with(1)


def test_stellar_iv_reports_locked_difficulty_without_clicking(apocalyptic):
    apocalyptic.prepare = Mock(return_value=True)
    auto = apocalyptic.run.__func__.__globals__["auto"]
    auto.find_element.side_effect = lambda target, *args, **kwargs: target == "未解锁"
    with pytest.raises(RuntimeError, match="请先通关难度 III"):
        apocalyptic.run()
    auto.click_element.assert_not_called()
    auto.click_element_with_pos.assert_not_called()


def test_invalid_stellar_teams_stop_before_entering_game(apocalyptic):
    apocalyptic.stellar.team3 = apocalyptic.team1
    apocalyptic.prepare = Mock()
    with pytest.raises(ValueError, match='重复'):
        apocalyptic.run()
    apocalyptic.prepare.assert_not_called()


def test_regular_clear_confirms_return_from_expanded_settlement(apocalyptic):
    apocalyptic.find_level = Mock(return_value=(100, 100))
    apocalyptic.judge_stars = Mock(return_value=0)
    apocalyptic.start_challenge = Mock(return_value=True)
    apocalyptic.return_to_stage_list = Mock()
    assert apocalyptic.start_challenges() is True
    apocalyptic.return_to_stage_list.assert_called_once_with()


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


@pytest.mark.parametrize('title,succeeded', [('挑战结束', False), ('挑战成功', True), ('挑战失败', False)])
def test_final_stellar_result_uses_settlement_title_without_native_two_node_detection(apocalyptic, title, succeeded):
    auto = apocalyptic.run.__func__.__globals__['auto']
    auto.find_element.side_effect = lambda target, *args, **kwargs: (
        title in target if isinstance(target, list) else target == '失败' and '失败' in title)
    auto.matched_text = title
    apocalyptic.return_to_stage_list = Mock()
    assert apocalyptic.stellar._wait_node_end(3) is succeeded
    apocalyptic.return_to_stage_list.assert_called_once()
    assert apocalyptic.max_level == (4 if succeeded else 0)
    # 不得走普通关两节点的图片判定和点击。
    assert not any(isinstance(c.args[0], str) and c.args[0].endswith(('/next_node.png', '/back.png'))
                   for c in auto.find_element.call_args_list + auto.click_element.call_args_list)


def test_final_stellar_timeout_stops_without_returning_or_recording(apocalyptic):
    auto = apocalyptic.run.__func__.__globals__['auto']
    auto.find_element.side_effect = None
    auto.find_element.return_value = False
    apocalyptic.return_to_stage_list = Mock()
    with pytest.raises(RuntimeError, match='最终结算超时'):
        apocalyptic.check_fight(3, final=True)
    apocalyptic.return_to_stage_list.assert_not_called()
    assert apocalyptic.max_level == 0


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


def test_return_falls_back_to_failure_return_button(apocalyptic):
    globals_ = apocalyptic.run.__func__.__globals__
    screen, auto = globals_['screen'], globals_['auto']
    screen.check_screen.side_effect = [False, True]
    auto.click_element.side_effect = lambda target, *args, **kwargs: target == '返回'
    apocalyptic.return_to_stage_list()
    assert [c.args[0] for c in auto.click_element.call_args_list] == ['返回末日幻影', '返回']
    assert auto.click_element.call_args_list[1].kwargs['include'] is True


def test_quick_unlock_starts_regular_stages_from_three(apocalyptic):
    auto = apocalyptic.run.__func__.__globals__['auto']
    auto.ocr_result = []
    auto.click_element.side_effect = None
    auto.click_element.return_value = True
    auto.find_element.side_effect = lambda target, *args, **kwargs: (
        ((10, 20), (30, 40)) if target == '03' else target in ('日幻影', '选择最高解锁关卡'))
    apocalyptic.level_range = [1, 4]
    assert apocalyptic.prepare() is True
    assert apocalyptic.level_range == [3, 4]
    auto.click_element_with_pos.assert_called_once_with(((10, 20), (10, 20)))


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
        elif target == '前往挑战':
            assert kwargs['crop'] == (0.35, 0.72, 0.30, 0.12)
            return False
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
    clicks = []
    auto.find_element.side_effect = lambda target, *args, **kwargs: state['page'] == 'teams'

    def click(target, *args, **kwargs):
        clicks.append(target)
        if target == '03':
            return True
        if target == '前往挑战':
            assert kwargs['crop'] == (0.35, 0.72, 0.30, 0.12)
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
    assert clicks == ['03', '前往挑战', '下一步', '前往编队']


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
    assert clicked == ['03', '前往挑战', '下一步'] + (['前往编队'] if failed_button == '前往编队' else [])
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
    from PIL import Image
    from tasks.base import list_drag

    auto = apocalyptic.run.__func__.__globals__['auto']
    base_class = apocalyptic.__class__.__mro__[1]
    monkeypatch.setitem(base_class.select_characters.__globals__, 'time', SimpleNamespace(sleep=Mock()))
    apocalyptic.find_node = Mock(return_value=(800, 200))
    monkeypatch.setattr(list_drag, 'time', SimpleNamespace(sleep=Mock()))
    state = {'scrolled': False, 'selected': False, 'fresh': False}
    list_crop = (30 / 1920, 115 / 1080, 530 / 1920, 810 / 1080)

    def click(target, *args, **kwargs):
        if target.endswith('/CastoriceGossamerFlutter.png'):
            assert kwargs.get('crop') == list_crop
            assert kwargs.get('take_screenshot') is True
            if state['scrolled']:
                assert state['fresh']
            state['selected'] = state['scrolled']
            return state['selected']
        return True

    def capture(crop):
        assert crop == list_crop
        state['fresh'] = True
        auto.screenshot = Image.new('RGB', (53, 81))
        return auto.screenshot, crop, 1

    def drag(start, end, duration):
        assert start[0] == end[0] == 430 / 1920
        assert all(list_crop[1] < point[1] < list_crop[1] + list_crop[3] for point in (start, end))
        state.update(scrolled=end[1] < start[1], fresh=False)
        return True

    auto.click_element.side_effect = click
    auto.take_screenshot.side_effect = capture
    auto.drag_mouse.side_effect = drag
    assert apocalyptic.select_characters([['CastoriceGossamerFlutter', 0]], team_name)
    apocalyptic.find_node.assert_called_once_with(node)
    assert state['selected']
    assert auto.drag_mouse.call_args_list == [
        call((430 / 1920, 840 / 1080), (430 / 1920, 350 / 1080), 1.0),
        call((430 / 1920, 350 / 1080), (430 / 1920, 840 / 1080), 1.0),
    ]


def test_missing_regular_team_node_does_not_click_or_scroll(apocalyptic):
    auto = apocalyptic.run.__func__.__globals__['auto']
    apocalyptic.find_node = Mock(return_value=False)
    assert apocalyptic.select_characters([['CastoriceGossamerFlutter', 0]], 'team1') is False
    auto.click_element.assert_not_called()
    auto.drag_mouse.assert_not_called()
