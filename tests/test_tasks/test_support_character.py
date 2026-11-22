"""PC 副本支援入口、角色识别和退出的回归用例。"""

from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image, ImageDraw
import pytest

from tasks.power import character, instance, policy
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
    friend_name = ((156, 491), (252, 516))
    auto = Mock(
        find_element=Mock(side_effect=[[first_match], None, [badge_match], friend_name]),
        ocr_result=[(None, ("另外一位", 0.98))],
    )
    log = Mock()
    monkeypatch.setattr(character, "auto", auto)
    monkeypatch.setattr(policy, "log", log)
    monkeypatch.setattr(character.time, "sleep", lambda _: None)

    search = policy.SupportNameSearch()
    assert character.Character.find_character_and_click("Cyrene", "指定好友", 0, 0, 1920, 1080, name_search=search)
    search.warn_if_unmatched()
    assert auto.find_element.call_count == 4
    assert auto.find_element.call_args_list[2].kwargs["mask_top_right_ratio"] == 0.26
    auto.click_element_with_pos.assert_called_once_with(friend_name)
    log.info.assert_called_once_with("找到支援角色「昔涟」，你填的好友名字是「指定好友」，小助手读到的是「另外一位」。")
    log.warning.assert_not_called()


@pytest.mark.parametrize(
    "read_name, scroll_finished, detail, warn",
    [
        pytest.param("持明上网", True, "小助手读到的是「持明上网」", True, id="mismatch"),
        pytest.param("", True, "小助手没读出这一位的名字", True, id="unreadable"),
        pytest.param("持明上網", True, None, False, id="matching-name-but-click-fails"),
        pytest.param(None, True, None, False, id="missing-portrait"),
        pytest.param("持明上网", False, "小助手读到的是「持明上网」", False, id="interrupted-scroll"),
    ],
)
def test_support_name_tip_requires_a_completed_search_without_a_match(
    monkeypatch, read_name, scroll_finished, detail, warn,
):
    portrait = ((48, 477), (156, 578))
    name_box = ((156, 491), (252, 516))

    def find(target, kind, *_args, **_kwargs):
        if kind == "image_with_multiple_targets":
            return [portrait] if read_name is not None else []
        if target == "持明上網" and read_name == target:
            return name_box
        return None

    auto = Mock(
        find_element=Mock(side_effect=find),
        click_element_with_pos=Mock(return_value=False),
        ocr_result=[(None, (read_name, 0.98))] if read_name else [],
    )
    log = Mock()
    monkeypatch.setattr(character, "auto", auto)
    monkeypatch.setattr(policy, "log", log)
    monkeypatch.setattr(character, "cfg", SimpleNamespace(
        game_title_name="test", borrow_scroll_times=2, borrow_friends=[("Cyrene", "持明上網")],
    ))
    monkeypatch.setattr(character.Screenshot, "get_window", Mock())
    monkeypatch.setattr(character.Screenshot, "get_window_region", Mock(return_value=(0, 0, 1920, 1080)))
    scroll = Mock(return_value=scroll_finished)
    monkeypatch.setattr(character.Character, "scroll_support_list", scroll)
    monkeypatch.setattr(character.Character, "exit_support_list", Mock())

    assert not character.Character.find_and_select_support("standard")
    scroll.assert_called_once()
    if detail:
        log.info.assert_called_once_with(f"找到支援角色「昔涟」，你填的好友名字是「持明上網」，{detail}。")
    else:
        log.info.assert_not_called()
    if warn:
        log.warning.assert_called_once()
        assert "把小助手「支援列表」里填的好友名字改成日志里读到的写法" in log.warning.call_args.args[0]
        assert [entry[0] for entry in log.method_calls] == ["info", "warning"]
    else:
        log.warning.assert_not_called()
    assert auto.click_element_with_pos.call_count == (4 if read_name == "持明上網" else 0)


def test_support_avatar_still_skips_when_both_matches_fail(monkeypatch):
    find_element = Mock(return_value=[])
    click = Mock()
    monkeypatch.setattr(character.auto, "find_element", find_element)
    monkeypatch.setattr(character.auto, "click_element_with_pos", click)

    assert not character.Character.find_character_and_click("Cyrene", "", 0, 0, 1920, 1080)
    assert find_element.call_count == 2
    click.assert_not_called()


@pytest.mark.parametrize("scrollbar", [True, False])
def test_support_list_waits_for_scroll_to_settle_with_animated_banners(monkeypatch, scrollbar):
    thumb_frames = [(100, 230), (130, 260), (130, 225), None, (130, 225), (130, 225), (130, 225)]
    avatar_frames = [80, 100, 130, 130, 130]
    frames = []
    positions = thumb_frames if scrollbar else avatar_frames
    for i, position in enumerate(positions):
        frame = Image.new("L", (544, 770), 30)
        draw = ImageDraw.Draw(frame)
        draw.rectangle((115, 0, 500, 769), fill=50 if i % 2 else 200)
        avatar_y = 130 if scrollbar else position
        draw.rectangle((5, avatar_y, 100, avatar_y + 95), fill=170)
        if scrollbar and position is not None:
            top, bottom = position
            draw.rectangle((534, top, 537, bottom), fill=170)
        frames.append((frame, None, 1))

    auto = Mock()
    auto.drag_mouse.return_value = True
    auto.take_screenshot.side_effect = frames
    monkeypatch.setattr(character, "auto", auto)
    monkeypatch.setattr(character.time, "sleep", Mock())

    assert character.Character.scroll_support_list()
    auto.drag_mouse.assert_called_once()
    assert auto.take_screenshot.call_count == len(frames)


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
