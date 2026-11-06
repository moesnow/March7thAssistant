"""支援头像仅在原匹配未选到目标时使用角标遮罩重试。"""

from unittest.mock import Mock
from types import SimpleNamespace

import pytest

from tasks.power import character


def test_support_avatar_retries_with_corner_mask(monkeypatch):
    match = ((48, 477), (156, 578))
    find_element = Mock(side_effect=[[], [match]])
    click = Mock()
    monkeypatch.setattr(character.auto, "find_element", find_element)
    monkeypatch.setattr(character.auto, "click_element_with_pos", click)
    monkeypatch.setattr(character.time, "sleep", lambda _: None)

    assert character.Character.find_character_and_click("Cyrene", "", 0, 0, 1920, 1080)
    assert find_element.call_count == 2
    assert find_element.call_args_list[0].kwargs["mask_top_right_ratio"] is None
    assert find_element.call_args_list[1].kwargs["mask_top_right_ratio"] == 0.26
    click.assert_called_once_with(match, (0, 0))


def test_support_avatar_uses_original_match_without_retry(monkeypatch):
    match = ((48, 477), (156, 578))
    find_element = Mock(return_value=[match])
    monkeypatch.setattr(character.auto, "find_element", find_element)
    monkeypatch.setattr(character.auto, "click_element_with_pos", Mock())
    monkeypatch.setattr(character.time, "sleep", lambda _: None)

    assert character.Character.find_character_and_click("Cyrene", "", 0, 0, 1920, 1080)
    find_element.assert_called_once()


def test_support_avatar_retries_after_friend_name_does_not_match(monkeypatch):
    first_match = ((48, 333), (156, 434))
    badge_match = ((48, 477), (156, 578))
    find_element = Mock(side_effect=[[first_match], [badge_match]])
    click_text = Mock(side_effect=[False, True])
    monkeypatch.setattr(character.auto, "find_element", find_element)
    monkeypatch.setattr(character.auto, "click_element", click_text)
    monkeypatch.setattr(character.time, "sleep", lambda _: None)

    assert character.Character.find_character_and_click("Cyrene", "指定好友", 0, 0, 1920, 1080)
    assert find_element.call_count == 2
    assert click_text.call_count == 2
    assert find_element.call_args_list[1].kwargs["mask_top_right_ratio"] == 0.26


def test_support_avatar_still_skips_when_both_matches_fail(monkeypatch):
    find_element = Mock(return_value=[])
    click = Mock()
    monkeypatch.setattr(character.auto, "find_element", find_element)
    monkeypatch.setattr(character.auto, "click_element_with_pos", click)

    assert not character.Character.find_character_and_click("Cyrene", "", 0, 0, 1920, 1080)
    assert find_element.call_count == 2
    click.assert_not_called()


@pytest.mark.parametrize("still_in_list", [False, True])
def test_interrupted_support_drag_checks_title_before_exiting(monkeypatch, still_in_list):
    monkeypatch.setattr(character, "cfg", SimpleNamespace(game_title_name="test", borrow_scroll_times=2, borrow_friends=[]))
    monkeypatch.setattr(character.Screenshot, "get_window", Mock(return_value=object()))
    monkeypatch.setattr(character.Screenshot, "get_window_region", Mock(return_value=(0, 0, 1920, 1080)))
    monkeypatch.setattr(character.Character, "scroll_support_list", Mock(return_value=False))
    find = Mock(return_value=still_in_list)
    monkeypatch.setattr(character.auto, "find_element", find)
    exit_list = Mock()
    monkeypatch.setattr(character.Character, "exit_support_list", exit_list)
    assert character.Character.find_and_select_support("ornament") is False
    find.assert_called_once_with(["支援列表", "支援角色"], "text", crop=(157 / 1920, 22 / 1080, 300 / 1920, 81 / 1080))
    assert exit_list.call_count == int(still_in_list)
