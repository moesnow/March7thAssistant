from types import SimpleNamespace
from unittest.mock import Mock, call

import numpy as np
from PIL import Image
import pytest

from tasks.touch import power, rewards


@pytest.mark.parametrize(("text", "expected"), [
    ("0/300", 0),
    (" ９８ ／ 300 ", 98),
    ("300/300", 300),
    ("2400/300", None),
    ("12/12", None),
    ("2301300", None),
    ("680 0/300", None),
    ("", None),
])
def test_parse_power_requires_valid_meter(text, expected):
    assert power.parse_power(text) == expected


def _line(text, x, y):
    return ([(x, y), (x + 40, y), (x + 40, y + 18), (x, y + 18)], (text, 0.98))


def test_repeat_cost_combines_split_ocr_in_screen_order(monkeypatch):
    monkeypatch.setattr(power.auto, "take_screenshot", Mock(return_value=(Image.new("RGB", (40, 20)), None, 1)))
    monkeypatch.setattr(power.ocr, "recognize_multi_lines", Mock(return_value=[_line("240", 32, 0), _line("×", 0, 4)]))
    assert power._read_cost(power.REPEAT_COST) == 240


def test_crimson_calyx_uses_location_when_buds_have_the_same_name():
    first_button = _line("进入", 640, 56)
    second_button = _line("进入", 640, 156)
    lines = [
        _line("毁灭之蕾", 130, 42), _line("渡画泉隐", 155, 70), first_button,
        _line("毁灭之蕾", 130, 142), _line("鳞渊境", 155, 170), second_button,
    ]

    assert power.find_instance_entry(lines, "鳞渊境") == (second_button[0], "进入")


def test_calyx_button_requires_same_row():
    top = _line("进入", 640, 56)
    next_row = _line("进入", 640, 161)
    title = _line("以太之蕾", 130, 148)

    assert power.find_instance_entry([top, title, next_row], "以太之蕾") == (next_row[0], "进入")
    assert power.find_instance_entry([top, title], "以太之蕾") is None
    assert power.find_instance_entry([top, title, next_row], "回忆之蕾") is None


@pytest.mark.parametrize(("foreground", "background", "expected"), [
    ((247, 231, 153), (37, 42, 51), True),
    ((185, 168, 101), (93, 85, 70), True),
    ((155, 155, 155), (40, 45, 49), False),
    ((210, 179, 103), (208, 177, 102), None),
    ((100, 100, 100), (90, 90, 90), None),
])
def test_auto_state_checks_glyph_against_scene(foreground, background, expected):
    with Image.open(f"{power.IMAGES}/auto_glyph.png") as image:
        glyph = np.asarray(image) > 0
    pixels = np.empty((*glyph.shape, 3), dtype=np.uint8)
    pixels[:] = background
    pixels[glyph] = foreground
    assert power.classify_auto_button(pixels, glyph) is expected


def test_battle_waits_for_comparable_frame_without_replaying_input(monkeypatch):
    poll = Mock(side_effect=[power.AdbError("frame_clock_unavailable", "clock"),
                             ("battle", True), ("victory", None)])
    tap = Mock()
    monkeypatch.setattr(power, "_observe_battle", poll)
    monkeypatch.setattr(power, "_tap", tap)
    monkeypatch.setattr(power.time, "sleep", Mock())
    power._wait_battle()
    assert poll.call_count == 3
    tap.assert_not_called()


def test_battle_retries_start_only_after_team_page_persists(monkeypatch):
    now = 0.0

    def sleep(seconds):
        nonlocal now
        now += seconds

    poll = Mock(side_effect=[("team", None)] * 10 + [("battle", True), ("victory", None)])
    click = Mock(return_value=True)
    monkeypatch.setattr(power, "_observe_battle", poll)
    monkeypatch.setattr(power, "_click_text", click)
    monkeypatch.setattr(power.time, "monotonic", lambda: now)
    monkeypatch.setattr(power.time, "sleep", sleep)

    power._wait_battle()

    click.assert_called_once_with("开始挑战", power.START_CHALLENGE)
    assert poll.call_args.kwargs["allow_team"] is False


def test_support_gift_requires_box_and_ribbon():
    with Image.open(f"{rewards.IMAGE_ROOT}/gift_shape.png") as image:
        glyph = np.asarray(image)
    pixels = np.zeros((96, 200, 3), dtype=np.uint8)
    pixels[:, 20:28] = (248, 231, 163)
    assert rewards.find_support_gift(pixels, glyph) is None

    height, width = glyph.shape
    pixels[25:25 + height, 120:120 + width][glyph > 0] = (248, 231, 163)
    box = rewards.find_support_gift(pixels, glyph)
    assert box and box[0] == (120, 25)


def test_zero_power_returns_to_main_without_entering_calyx(monkeypatch):
    navigate = Mock()
    enter = Mock()
    monkeypatch.setattr(power, "screen", navigate)
    monkeypatch.setattr(power, "_select_category", Mock())
    monkeypatch.setattr(power, "read_power", Mock(return_value=9))
    monkeypatch.setattr(power, "cfg", SimpleNamespace(use_reserved_trailblaze_power=False, use_fuel=False,
                                                       instance_names_challenge_count={power.GOLDEN_CALYX: 1}))
    monkeypatch.setattr(power, "_enter_instance", enter)

    assert list(power._run_instance(power.GOLDEN_CALYX, "回忆之蕾", 2)) == []
    enter.assert_not_called()
    navigate.change_to.assert_called_once_with("main", max_recursion=1)


def test_repeat_stops_at_configured_count(monkeypatch):
    navigate = Mock()
    start = Mock()
    wait = Mock()
    click = Mock(return_value=True)
    exit_result = Mock()
    monkeypatch.setattr(power, "screen", navigate)
    monkeypatch.setattr(power, "_select_category", Mock())
    monkeypatch.setattr(power, "cfg", SimpleNamespace(use_reserved_trailblaze_power=False, use_fuel=False,
                                                       instance_names_challenge_count={power.GOLDEN_CALYX: 1}))
    monkeypatch.setattr(power, "read_power", Mock(side_effect=[53, 43, 33]))
    monkeypatch.setattr(power, "_enter_instance", Mock())
    monkeypatch.setattr(power, "_start_challenge", start)
    monkeypatch.setattr(power, "_wait_battle", wait)
    monkeypatch.setattr(power, "_read_waves", Mock(return_value=1))
    monkeypatch.setattr(power, "_read_cost", Mock(return_value=10))
    monkeypatch.setattr(power, "_click_text", click)
    monkeypatch.setattr(power, "_exit_result", exit_result)

    assert list(power._run_instance(power.GOLDEN_CALYX, "回忆之蕾", 2)) == [1, 1]
    start.assert_called_once_with(power.GOLDEN_CALYX, "回忆之蕾", 1, borrow_for_daily=False)
    assert wait.call_args_list == [call(repeated=False, instance_screen="calyx"), call(repeated=True, instance_screen="calyx")]
    click.assert_called_once_with("再来一次", power.REPEAT)
    exit_result.assert_called_once_with("calyx")
    navigate.change_to.assert_called_once_with("main", max_recursion=1)


def test_power_plan_saves_only_confirmed_waves_before_failure(monkeypatch):
    calyx = power.GOLDEN_CALYX
    config = SimpleNamespace(
        power_plan=[[calyx, "回忆之蕾", 3], ["饰品提取", "永恒笑剧", 1]],
        power_plan_keep=False, instance_names_challenge_count={calyx: 2}, set_value=Mock(),
    )

    def fail_after_first_batch(instance_type, name, count, *, borrow_for_daily):
        assert (instance_type, name, count) == (calyx, "回忆之蕾", 3)
        yield 2
        raise power.PowerError("等待战斗超时")

    monkeypatch.setattr(power, "cfg", config)
    monkeypatch.setattr(power, "_run_instance", fail_after_first_batch)

    assert power.run() is False
    config.set_value.assert_called_once_with("power_plan", [[calyx, "回忆之蕾", 1], config.power_plan[1]])


def test_mail_and_assist_without_alert_do_not_click(monkeypatch):
    auto = Mock()
    screen = Mock()
    monkeypatch.setattr(rewards, "auto", auto)
    monkeypatch.setattr(rewards, "screen", screen)
    monkeypatch.setattr(rewards, "_has_alert", Mock(return_value=False))

    rewards.claim_mail()
    rewards.claim_assist()

    assert screen.change_to.call_args_list == [call("menu", max_recursion=1)] * 2
    auto.click_element.assert_not_called()


def test_sms_pending_thread_accepts_sticker_reply(monkeypatch):
    sticker = ((609, 510), (632, 528))
    auto = Mock()
    auto.find_element.side_effect = [None, [], sticker, None, None, None]
    monkeypatch.setattr(rewards, "auto", auto)
    monkeypatch.setattr(rewards, "_message_pending", Mock(side_effect=[True, False, False, False]))
    monkeypatch.setattr(rewards.time, "sleep", Mock())

    rewards._finish_message()

    auto.click_element_with_pos.assert_called_once_with(sticker, offset=(55, 62))


@pytest.mark.parametrize("reserved, second_confirm", [
    (True, power.RESERVE_AMOUNT_CONFIRM),
    (False, power.SUPPLEMENT_CONFIRM),
])
def test_supplement_uses_the_correct_quantity_dialog(monkeypatch, reserved, second_confirm):
    monkeypatch.setattr(power, "cfg", SimpleNamespace(
        use_reserved_trailblaze_power=reserved, use_fuel=not reserved,
    ))
    monkeypatch.setattr(power, "_tap", Mock())
    read_number = Mock(side_effect=[32, 1])
    monkeypatch.setattr(power, "_read_number", read_number)
    monkeypatch.setattr(power, "read_power", Mock(return_value=262))
    monkeypatch.setattr(power.time, "sleep", Mock())
    auto = Mock()
    auto.find_element.side_effect = [True, True, None, True, True, False]
    monkeypatch.setattr(power, "auto", auto)
    navigate = Mock()
    navigate.check_screen.return_value = False
    monkeypatch.setattr(power, "screen", navigate)
    click = Mock(return_value=True)
    monkeypatch.setattr(power, "_click_text", click)

    assert power._supplement(202) == 262
    assert click.call_args_list == [
        call("确认", power.SUPPLEMENT_CONFIRM), call("确认", second_confirm),
    ]
    assert read_number.call_count == (1 if reserved else 2)


def test_support_portrait_match_keeps_rows_separate():
    import cv2
    from tasks.touch.support import _portrait_rows

    template = cv2.imread("assets/images/share/character/Cyrene.png")
    portrait = cv2.resize(template, None, fx=0.76, fy=0.76)
    pixels = np.zeros((500, 96, 3), dtype=np.uint8)
    h, w = portrait.shape[:2]
    for top in (40, 220):
        pixels[top:top + h, 6:6 + w] = portrait

    rows = sorted(_portrait_rows(pixels, template))

    assert len(rows) == 2
    assert abs((rows[1] - rows[0]) - 180) <= 2
