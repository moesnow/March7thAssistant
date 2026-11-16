"""PC 副本支援入口、角色识别和退出的回归用例。"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tasks.power import character, instance
from tasks.power.policy import CAVERN, ORNAMENT, SupportDemand


@pytest.mark.parametrize(
    "instance_type, borrow_type, support_crop, retry_crop",
    [
        pytest.param(
            CAVERN, "standard", (966 / 1920, 954 / 1080, 176 / 1920, 60 / 1080),
            (966 / 1920, 946 / 1080, 913 / 1920, 83 / 1080), id="standard",
        ),
        pytest.param(
            ORNAMENT, "ornament", (610 / 1920, 864 / 1080, 184 / 1920, 64 / 1080),
            (610 / 1920, 864 / 1080, 1269 / 1920, 165 / 1080), id="ornament",
        ),
    ],
)
@pytest.mark.parametrize(
    "retry_checks, first_input_delivered, borrowed",
    [
        pytest.param([], True, True, id="first-click-opens-list"),
        pytest.param([("开始挑战", "present"), ("支援", "present")], True, True, id="retry-opens-list"),
        pytest.param([("开始挑战", "present"), ("支援", "present")], False, True, id="first-input-fails"),
        pytest.param([("开始挑战", "missing")], True, False, id="challenge-page-unconfirmed"),
        pytest.param([("开始挑战", "outside")], True, False, id="challenge-label-outside-button-region"),
        pytest.param(
            [("开始挑战", "present"), ("支援", "missing")], True, False, id="support-button-unconfirmed",
        ),
        pytest.param(
            [("开始挑战", "present"), ("支援", "outside")], True, False, id="support-label-outside-button-region",
        ),
        pytest.param(
            [("开始挑战", "present"), ("支援", "present")], True, False, id="retry-does-not-open-list",
        ),
    ],
)
def test_pc_instance_retries_support_only_after_confirming_challenge_page(
    monkeypatch, instance_type, borrow_type, support_crop, retry_crop, retry_checks, first_input_delivered, borrowed,
):
    scale_factor = 0.75 if instance_type == ORNAMENT else 1
    window_left, window_top = 120, 30

    def screen_point(x, y):
        return window_left + int(x / scale_factor), window_top + int(y / scale_factor)

    def text_position(x, y, width, height):
        return screen_point(x, y), screen_point(x + width, y + height)

    title = ("支援列表", "支援角色")
    start = text_position(1720, 985, 80, 20)
    left, top = round(support_crop[0] * 1920), round(support_crop[1] * 1080)
    first_support = text_position(left + 4, top + 6, 40, 20)
    fresh_support = text_position(left + 9, top + 6, 40, 20)
    title_position = text_position(160, 25, 100, 50)
    retry_click = bool(retry_checks) and retry_checks[-1] == ("支援", "present")

    interactions = []
    if instance_type == CAVERN:
        interactions.append(("开始挑战", start))
    interactions.extend([
        ("支援", first_support), (first_support, first_input_delivered),
        (title, title_position if borrowed and not retry_checks else None),
    ])
    wrong_support_x = 1020 if instance_type == ORNAMENT else 1220
    positions = {
        "开始挑战": {"present": start, "outside": text_position(1220, 985, 80, 20)},
        "支援": {"present": fresh_support, "outside": text_position(wrong_support_x, 960, 40, 20)},
    }
    interactions.extend((f"复核{target}", positions[target].get(state)) for target, state in retry_checks)
    if retry_click:
        interactions.extend([(fresh_support, True), (title, title_position if borrowed else None)])
    if borrowed:
        interactions.append(("选择支援角色", True))
    interactions.extend([("开始挑战", start), (start, True), ("开始挑战", None)])
    expected = iter(interactions)

    def observe(target):
        next_target, result = next(expected)
        assert target == next_target
        return result

    def find(target, kind, *_args, **kwargs):
        if isinstance(target, list):
            target = tuple(target)
        if target not in ("开始挑战", "支援", title):
            return None
        assert kind == "text"
        if target == "支援" and kwargs.get("need_ocr") is False:
            assert kwargs.get("take_screenshot") is False
            return observe("复核支援")
        assert kwargs.get("take_screenshot", True) and kwargs.get("need_ocr", True)
        if target == "支援":
            assert kwargs["crop"] == support_crop
        elif target == "开始挑战":
            if kwargs["crop"] == retry_crop:
                auto.screenshot_pos = (
                    *screen_point(round(retry_crop[0] * 1920), round(retry_crop[1] * 1080)),
                    round(retry_crop[2] * 1920), round(retry_crop[3] * 1080),
                )
                auto.screenshot_scale_factor = scale_factor
                return observe("复核开始挑战")
            assert kwargs["crop"] == instance.CHALLENGE
        return observe(target)

    def select_support(kind):
        assert kind == borrow_type
        return observe("选择支援角色")

    config = SimpleNamespace(instance_team_enable=False, borrow_enable=True, borrow_character_enable=True)
    auto = Mock(find_element=Mock(side_effect=find), click_element_with_pos=Mock(side_effect=observe))
    auto.click_element.return_value = True
    monkeypatch.setattr(character, "auto", auto)
    monkeypatch.setattr(instance, "auto", auto)
    monkeypatch.setattr(character, "cfg", config)
    monkeypatch.setattr(instance, "cfg", config)
    monkeypatch.setattr(character.time, "sleep", Mock())
    monkeypatch.setattr(character.Character, "find_and_select_support", select_support)
    engage = Mock()
    monkeypatch.setattr(instance.Instance, "_engage_ornament_boss", engage)

    assert instance.Instance.start_instance(
        instance_type, "测试副本", SupportDemand(), practice=False, world_team=False,
    ) is borrowed
    assert next(expected, None) is None
    assert engage.call_count == int(instance_type == ORNAMENT)


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
