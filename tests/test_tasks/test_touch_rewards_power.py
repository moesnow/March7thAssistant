from types import SimpleNamespace
from unittest.mock import Mock, call

import numpy as np
from PIL import Image
import pytest

from module.localization import tr
from tasks.touch import ornament, power, rewards
from tasks.power import readout, supplement


@pytest.mark.parametrize(("text", "expected"), [
    ("0/300", 0),
    (" ９８ ／ 300 ", 98),
    ("300/300", 300),
    ("2400/300", 2400),
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
    monkeypatch.setattr(readout.ocr, "recognize_multi_lines", Mock(return_value=[_line("240", 32, 0), _line("×", 0, 4)]))
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


def test_echo_entry_uses_button_below_title():
    unrelated = _line("进入", 640, 65)
    title = _line("毁灭的开端", 150, 64)
    entry = _line("进入", 640, 137)

    assert power.find_instance_entry([unrelated, title, entry], "毁灭的开端", power.ECHO) == (entry[0], "进入")


@pytest.mark.parametrize(("text", "waves", "payment"), [
    ("×１", 1, (0, 1)),
    ("2 米 40", 3, (40, 2)),
    ("×240", 6, (240, 0)),
    ("2 米 80", 3, None),
    ("未知", 1, None),
])
def test_ornament_payment_requires_amounts_matching_the_wave_count(text, waves, payment):
    assert ornament.parse_payment(text, waves) == payment


def test_ornament_reduces_waves_from_the_displayed_payment_without_reading_stock(monkeypatch):
    select_waves = Mock()
    amounts = iter(("2 米 80", "2 米 40"))
    read_number = Mock(side_effect=lambda crop, parse, error: parse(next(amounts)))
    monkeypatch.setattr(ornament.auto, "find_element", Mock(return_value=True))
    monkeypatch.setattr(power, "_set_challenge_waves", select_waves)
    monkeypatch.setattr(power, "_read_number", read_number)

    assert ornament._prepare_payment(4, 47) == (3, 40, 2)
    assert [item.args[0] for item in select_waves.call_args_list] == [4, 3]
    assert [item.args[0] for item in read_number.call_args_list] == [ornament.PAYMENT] * 2


def test_ornament_confirms_known_no_save_prompt(monkeypatch):
    auto = Mock()
    auto.find_element.side_effect = lambda text, *args, **kwargs: text == "当前不存在任何存档"
    monkeypatch.setattr(ornament, "auto", auto)
    click = Mock(return_value=True)
    monkeypatch.setattr(power, "_click_text", click)
    engage = Mock()
    monkeypatch.setattr(ornament, "_engage_boss", engage)
    assert ornament._start_challenge()
    assert click.call_args_list == [call("开始挑战", power.START_CHALLENGE), call("确认", power.DIALOG_CONFIRM)]
    engage.assert_called_once_with()


@pytest.mark.parametrize("waves", [1, 3])
def test_ornament_reports_completed_waves_before_rechecking_the_balance(monkeypatch, waves):
    monkeypatch.setattr(ornament, "cfg", SimpleNamespace(borrow_enable=False, instance_team_enable=False))
    monkeypatch.setattr(power, "_select_category", Mock())
    monkeypatch.setattr(power, "_supplement", Mock())
    monkeypatch.setattr(power, "_enter_instance", Mock())
    monkeypatch.setattr(power, "_wait_battle", Mock())
    read_waves = Mock(return_value=3)
    monkeypatch.setattr(power, "_read_waves", read_waves)
    monkeypatch.setattr(ornament, "_start_challenge", Mock())
    monkeypatch.setattr(ornament, "_prepare_payment", Mock(return_value=(waves, 40, waves - 1)))
    balance = Mock(side_effect=[181, 181, power.PowerError("读数失败")])
    monkeypatch.setattr(power, "read_power", balance)

    run = ornament.run_instance("浴火钢心", waves, 3, False, None)
    assert next(run) == waves
    if waves == 1:
        read_waves.assert_not_called()
    else:
        read_waves.assert_called_once_with(power.RESULT_COUNT, "上轮挑战波次")
    assert balance.call_count == 2
    with pytest.raises(power.PowerError, match="读数失败"):
        next(run)
    balance.assert_called_with(ornament.INDEX_POWER)


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
    monkeypatch.setattr(power, "ensure_double_speed", Mock(return_value=True))
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
    monkeypatch.setattr(power, "ensure_double_speed", Mock(return_value=True))
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


def test_repeat_ignores_a_stale_victory_until_battle_is_seen(monkeypatch):
    monkeypatch.setattr(power, "cfg", SimpleNamespace(auto_battle_detect_enable=False))
    monkeypatch.setattr(power.time, "sleep", Mock())
    observe = Mock(side_effect=[("victory", None), (None, None), ("victory", None),
                                ("battle", None), ("victory", None)])
    monkeypatch.setattr(power, "_observe_battle", observe)
    speed = Mock()
    monkeypatch.setattr(power, "ensure_double_speed", speed)
    power._wait_battle(repeated=True)
    assert observe.call_count == 5
    speed.assert_not_called()


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

    settlements = Mock()
    assert list(power._run_instance(power.GOLDEN_CALYX, "回忆之蕾", 2, on_settlement=settlements)) == [1, 1]
    assert settlements.call_args_list == [call(1, 43), call(1, 33)]
    start.assert_called_once_with(power.GOLDEN_CALYX, "回忆之蕾", 1, borrow_for_daily=False, practice=False)
    assert wait.call_args_list == [call(repeated=False, instance_screen="calyx"), call(repeated=True, instance_screen="calyx")]
    click.assert_called_once_with("再来一次", power.REPEAT)
    exit_result.assert_called_once_with("calyx")
    navigate.change_to.assert_called_once_with("main", max_recursion=1)


@pytest.mark.parametrize("planned", [None, 1])
def test_echo_without_weekly_rewards_only_fights_for_an_explicit_plan(monkeypatch, planned):
    enter = Mock()
    start = Mock()
    supplement = Mock()
    config = SimpleNamespace(instance_names_challenge_count={}, save_timestamp=Mock())
    monkeypatch.setattr(power, "cfg", config)
    monkeypatch.setattr(power, "screen", Mock())
    monkeypatch.setattr(power, "_select_category", Mock())
    monkeypatch.setattr(power, "_read_echo_rewards", Mock(return_value=0))
    monkeypatch.setattr(power, "read_power", Mock(return_value=0))
    monkeypatch.setattr(power, "_supplement", supplement)
    monkeypatch.setattr(power, "_enter_instance", enter)
    monkeypatch.setattr(power, "_start_challenge", start)
    monkeypatch.setattr(power, "_wait_battle", Mock())
    monkeypatch.setattr(power, "_exit_result", Mock())

    assert list(power._run_instance(power.ECHO, "毁灭的开端", planned)) == ([1] if planned else [])
    supplement.assert_not_called()
    if planned:
        start.assert_called_once_with(power.ECHO, "毁灭的开端", 1, borrow_for_daily=False, practice=True)
        config.save_timestamp.assert_called_once_with("echo_of_war_timestamp")
    else:
        enter.assert_not_called()
        start.assert_not_called()
        config.save_timestamp.assert_called_once_with("echo_of_war_timestamp")


def test_echo_paid_runs_are_capped_by_the_remaining_weekly_rewards(monkeypatch):
    config = SimpleNamespace(instance_names_challenge_count={}, save_timestamp=Mock())
    start = Mock()
    confirm_practice = Mock()
    monkeypatch.setattr(power, "cfg", config)
    monkeypatch.setattr(power, "screen", Mock())
    monkeypatch.setattr(power, "_select_category", Mock())
    monkeypatch.setattr(power, "_read_echo_rewards", Mock(side_effect=[2, 1, 0]))
    monkeypatch.setattr(power.auto, "find_element", Mock(return_value=False))
    monkeypatch.setattr(power, "_supplement", lambda value: value)
    monkeypatch.setattr(power, "read_power", Mock(side_effect=[91, 61, 31]))
    monkeypatch.setattr(power, "_enter_instance", Mock())
    monkeypatch.setattr(power, "_start_challenge", start)
    monkeypatch.setattr(power, "_wait_battle", Mock())
    monkeypatch.setattr(power, "_read_cost", Mock(return_value=30))
    monkeypatch.setattr(power, "_click_text", Mock(return_value=True))
    monkeypatch.setattr(power, "_exit_result", Mock())
    monkeypatch.setattr(power, "_confirm_echo_practice", confirm_practice)

    assert list(power._run_instance(power.ECHO, "毁灭的开端", None)) == [1, 1]
    assert start.call_args_list == [call(power.ECHO, "毁灭的开端", 1, borrow_for_daily=False, practice=False)] * 2
    confirm_practice.assert_not_called()
    config.save_timestamp.assert_called_once_with("echo_of_war_timestamp")


def test_power_plan_saves_only_confirmed_waves_before_failure(monkeypatch):
    calyx = power.GOLDEN_CALYX
    config = SimpleNamespace(
        power_plan=[[calyx, "回忆之蕾", 3], ["饰品提取", "永恒笑剧", 1]],
        power_plan_keep=False, instance_names_challenge_count={calyx: 2}, set_value=Mock(),
    )

    def fail_after_first_batch(instance_type, name, count, **kwargs):
        assert (instance_type, name, count) == (calyx, "回忆之蕾", 3)
        yield 2
        raise power.PowerError("等待战斗超时")

    monkeypatch.setattr(power, "cfg", config)
    monkeypatch.setattr(power, "_run_instance", fail_after_first_batch)

    assert power.run() is False
    config.set_value.assert_called_once_with("power_plan", [[calyx, "回忆之蕾", 1], config.power_plan[1]])


@pytest.mark.parametrize("succeeded", [True, False])
def test_power_reports_only_a_successful_summary_from_confirmed_settlements(monkeypatch, succeeded):
    def run(_borrow_for_daily, on_settlement):
        on_settlement(1, 43)
        on_settlement(2, 23)
        return succeeded

    monkeypatch.setattr(power, "_run", run)
    summary = Mock()
    assert power.run(on_summary=summary) is succeeded
    if succeeded:
        summary.assert_called_once_with(tr("已完成 {count} 次挑战，剩余开拓力 {power}/300").format(count=3, power=23))
    else:
        summary.assert_not_called()


def test_rewards_reports_completion_with_the_daily_result(monkeypatch):
    monkeypatch.setattr(rewards, "cfg", SimpleNamespace(reward_enable=False))
    daily_summary = tr("每日实训活跃度 {activity}/{maximum}").format(activity=300, maximum=500)

    def run_daily(*, complete_training, on_summary):
        assert complete_training is False
        on_summary(daily_summary)
        return True

    monkeypatch.setattr(rewards.daily, "run", run_daily)
    summary = Mock()
    assert rewards.run(on_summary=summary)
    summary.assert_called_once_with(tr("奖励检查完成，{daily_summary}").format(daily_summary=daily_summary))


def test_claim_collects_rewards_without_opening_daily_training(monkeypatch):
    monkeypatch.setattr(rewards, "cfg", SimpleNamespace(
        reward_dispatch_enable=True, reward_mail_enable=False, reward_assist_enable=False,
        reward_srpass_enable=False, reward_message_enable=False))
    dispatch = Mock()
    monkeypatch.setattr(rewards, "claim_dispatch", dispatch)
    monkeypatch.setattr(rewards.daily, "run", Mock(side_effect=AssertionError))
    assert rewards.claim()
    dispatch.assert_called_once_with()

    monkeypatch.setattr(rewards.screen, "change_to", Mock())
    dispatch.side_effect = rewards.RewardError("x")
    assert not rewards.claim()


def test_routine_joins_the_power_and_reward_summaries(monkeypatch):
    monkeypatch.setattr(rewards, "cfg", SimpleNamespace(power_enable=True, daily_enable=False, echo_of_war_enable=False, reward_enable=False))
    monkeypatch.setattr(power, "run", lambda *, borrow_for_daily, on_summary: on_summary("power") or True)
    monkeypatch.setattr(rewards.daily, "support_demand", Mock(return_value=power.SupportDemand()))
    monkeypatch.setattr(rewards.daily, "run", lambda *, complete_training, full_run, on_summary: on_summary("rewards") or True)
    monkeypatch.setattr(rewards.screen, "change_to", Mock())
    summary = Mock()
    assert rewards.routine(on_summary=summary)
    summary.assert_called_once_with(tr("；").join(("power", "rewards")))


def test_mail_and_assist_without_alert_do_not_click(monkeypatch):
    auto = Mock()
    screen = Mock()
    monkeypatch.setattr(rewards, "auto", auto)
    monkeypatch.setattr(rewards, "screen", screen)
    monkeypatch.setattr(rewards, "menu_alert", Mock(return_value=False))

    rewards.claim_mail()
    rewards.claim_assist()

    assert screen.change_to.call_args_list == [call("menu", max_recursion=1)] * 2
    auto.click_element.assert_not_called()


def test_unread_mail_without_attachments_does_not_click_the_disabled_button(monkeypatch):
    auto = Mock(screenshot=Image.new("RGB", (180, 42), (165, 165, 165)))
    monkeypatch.setattr(rewards, "auto", auto)
    monkeypatch.setattr(rewards, "screen", Mock())
    monkeypatch.setattr(rewards, "menu_alert", Mock(return_value=True))

    rewards.claim_mail()

    auto.click_element_with_pos.assert_not_called()


def test_srpass_opens_a_new_season_before_collecting(monkeypatch):
    auto = Mock()
    auto.click_element.return_value = True
    screen = Mock()
    screen.check_screen.side_effect = [False, False, True]
    monkeypatch.setattr(rewards, "auto", auto)
    monkeypatch.setattr(rewards, "screen", screen)
    monkeypatch.setattr(rewards.time, "sleep", Mock())

    rewards._open_srpass()

    auto.click_element.assert_called_once_with("开启无名勋礼", "text", crop=rewards.SRPASS_OPEN)


@pytest.mark.parametrize("locked", [True, False])
def test_srpass_collects_both_task_groups_with_one_click(monkeypatch, locked):
    auto = Mock()
    auto.find_element.return_value = locked
    monkeypatch.setattr(rewards, "auto", auto)
    monkeypatch.setattr(rewards, "screen", Mock())
    monkeypatch.setattr(rewards, "_open_srpass", Mock())
    collect = Mock()
    monkeypatch.setattr(rewards, "_claim_srpass_tab", collect)
    rewards.claim_srpass()
    assert collect.call_args_list == [call("pass2", "本周及本期任务经验")] + ([call("pass1", "等级奖励")] if locked else [])


def test_message_timeout_recovers_then_collects_next_reward(monkeypatch):
    pending = ((30, 40), (50, 60))
    frame = Image.new("RGB", (128, 80))
    monkeypatch.setattr(rewards, "screen", Mock())
    monkeypatch.setattr(rewards, "auto", Mock(screenshot=frame, take_screenshot=Mock(return_value=(frame, None, 1))))
    monkeypatch.setattr(rewards, "_message_pending", Mock(return_value=pending))
    monkeypatch.setattr(rewards, "_open_unread_message", Mock(side_effect=[True, False]))
    monkeypatch.setattr(rewards, "drag_list", Mock(return_value=True))
    finish = Mock(side_effect=[rewards.MessageTimeout("超时"), True])
    monkeypatch.setattr(rewards, "_finish_message", finish)
    notify = Mock()
    monkeypatch.setattr(rewards.Base, "send_notification_with_screenshot", notify)
    with pytest.raises(rewards.RewardError, match="1 个短信会话超时"):
        rewards.claim_messages()
    assert finish.call_count == 2
    rewards.screen.change_to.assert_any_call("menu", max_recursion=0)
    rewards.screen.change_to.assert_any_call("incoming_message", max_recursion=0)
    notify.assert_called_once()


@pytest.mark.parametrize("theme", [(235, 165, 73), (31, 49, 82)])
def test_red_dot_requires_the_round_marker_on_different_wallpapers(theme):
    from PIL import ImageDraw
    from tasks.reward.menu_alert import red_dot_present

    frame = Image.new("RGB", (40, 40), theme)
    assert not red_dot_present(np.asarray(frame))
    draw = ImageDraw.Draw(frame)
    draw.ellipse((9, 9, 29, 29), fill=(230, 42, 35))
    draw.rectangle((18, 13, 20, 21), fill=(250, 245, 240))
    draw.point((19, 24), fill=(250, 245, 240))
    assert red_dot_present(np.asarray(frame))


@pytest.mark.parametrize("balance, starts", [(301, True), (8, False)])
def test_challenge_checks_cost_without_toggling_quick_refill(monkeypatch, balance, starts):
    monkeypatch.setattr(power, "cfg", SimpleNamespace(instance_team_enable=False, borrow_enable=False))
    auto = Mock()
    monkeypatch.setattr(power, "auto", auto)
    monkeypatch.setattr(power, "_set_challenge_waves", Mock())
    monkeypatch.setattr(power, "_read_cost", Mock(return_value=10))
    monkeypatch.setattr(power, "read_power", Mock(return_value=balance))
    click = Mock(return_value=True)
    monkeypatch.setattr(power, "_click_text", click)
    if starts:
        power._start_challenge(power.GOLDEN_CALYX, "回忆之蕾", 1)
        assert [c.args[0] for c in click.call_args_list] == ["挑战", "开始挑战"]
    else:
        with pytest.raises(power.PowerError, match="开拓力不符"):
            power._start_challenge(power.GOLDEN_CALYX, "回忆之蕾", 1)
        click.assert_not_called()


def test_sms_pending_thread_accepts_sticker_reply(monkeypatch):
    sticker = ((609, 510), (632, 528))
    auto = Mock()
    auto.find_element.side_effect = [None, [], sticker, None, None, None]
    monkeypatch.setattr(rewards, "auto", auto)
    monkeypatch.setattr(rewards, "_message_pending", Mock(side_effect=[True, False, False, False]))
    monkeypatch.setattr(rewards.time, "sleep", Mock())

    rewards._finish_message()

    auto.click_element_with_pos.assert_called_once_with(sticker, offset=(55, 62))


@pytest.mark.parametrize("amounts, increase", [([630, 300, 300], 300), ([0, 7, 5, 5], 300)])
def test_supplement_uses_maximum_even_above_300_and_checks_zero_reserve(monkeypatch, amounts, increase):
    cfg = SimpleNamespace(use_reserved_trailblaze_power=True, use_fuel=True)
    auto = Mock()
    title_reads = iter([True, False])

    def find(label, *args, **kwargs):
        if label == "开拓力补充":
            return next(title_reads)
        return label != "获得物品"

    auto.find_element.side_effect = find
    read = Mock(side_effect=amounts)
    monkeypatch.setattr(supplement, "read_number", read)
    navigate = Mock()
    assert supplement.supplement(auto, navigate, cfg, 320, Mock(return_value=True),
                                 Mock(return_value=320 + increase), return_screen="guide3") == 620
    assert read.call_count == len(amounts)
    confirms = [c for c in auto.click_element.call_args_list if c.args[0] == "确认"]
    assert len(confirms) == 2
    navigate.wait_for_screen_change.assert_called_once_with("guide3", max_recursion=0)


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
