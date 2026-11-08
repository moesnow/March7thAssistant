"""增益弹窗未展开时不能匹配背景箭头，装配后必须确认弹窗关闭。"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.test_tasks.test_purefiction_settlement import challenge


@pytest.fixture
def buff(challenge, monkeypatch):
    owner = challenge.instance
    globals_ = owner.select_buff_effect.__func__.__globals__
    monkeypatch.setitem(globals_, 'time', SimpleNamespace(sleep=Mock()))
    auto = challenge.automation
    auto.find_element.side_effect = None
    auto.find_element.return_value = False
    auto.click_element.side_effect = None
    auto.click_element.return_value = True
    return SimpleNamespace(owner=owner, auto=auto)


def test_waits_for_dialog_before_clicking_any_option(buff):
    assert buff.owner.select_buff_effect() is False
    buff.auto.click_element.assert_not_called()
    assert buff.auto.find_element.call_args.args[0].endswith('/confirm.png')
    assert buff.auto.find_element.call_args.kwargs['max_retries'] == 10


def test_option_search_excludes_observed_background_false_match(buff):
    buff.auto.find_element.side_effect = [True, False]
    assert buff.owner.select_buff_effect() is True
    choose, confirm = buff.auto.click_element.call_args_list
    assert choose.args[0].endswith('/choose.png')
    assert confirm.args[0].endswith('/confirm.png')
    x, y, width, height = choose.kwargs['crop']
    assert x <= 776 / 1920 <= x + width
    assert y <= 233 / 1080 <= y + height
    assert not (x <= 1598 / 1920 <= x + width and y <= 774 / 1080 <= y + height)
    assert buff.auto.mock_calls[0][0] == 'find_element'
    assert buff.auto.mock_calls[-1][0] == 'find_element'


def test_does_not_click_equip_when_no_option_was_found(buff):
    buff.auto.find_element.return_value = True
    buff.auto.click_element.return_value = False
    assert buff.owner.select_buff_effect() is False
    assert len(buff.auto.click_element.call_args_list) == 1
    assert buff.auto.click_element.call_args.args[0].endswith('/choose.png')


def test_reselects_when_first_equip_click_does_not_close_dialog(buff):
    buff.auto.find_element.side_effect = [True, *([True] * 5), False]
    assert buff.owner.select_buff_effect() is True
    targets = [c.args[0].rsplit('/', 1)[1] for c in buff.auto.click_element.call_args_list]
    assert targets == ['choose.png', 'confirm.png', 'choose.png', 'confirm.png']


def test_stuck_dialog_reports_failure_after_finite_retries(buff):
    buff.auto.find_element.return_value = True
    assert buff.owner.select_buff_effect() is False
    assert buff.auto.click_element.call_count == 6


def test_second_team_equip_failure_is_not_reported_as_success(buff):
    buff.owner.select_buff_effect = Mock(side_effect=[True, False])
    assert buff.owner.select_buff() is False
    assert buff.owner.select_buff_effect.call_count == 2


def test_first_team_failure_does_not_open_second_team_buff(buff):
    buff.owner.select_buff_effect = Mock(return_value=False)
    assert buff.owner.select_buff() is False
    buff.auto.click_element.assert_called_once()
