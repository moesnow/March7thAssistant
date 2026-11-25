"""货币战争入画奇航的策略、画面判定与流程模拟。"""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
import re
import zlib

import numpy as np
from PIL import Image, ImageDraw
import pytest

from module.automation.automation import Automation
from module.automation.input_base import begin_input_dispatch
from module.screen.screen import Screen
from tasks.weekly import currency_wars as task
from tasks.weekly import currency_wars_strategy as policy
from tasks.weekly import currency_wars_ui as ui
from tasks.weekly.currency_wars_ui import Frame, Label, Page
from utils.pause import RunStopRequested

CANVAS = Image.new("RGB", (1920, 1080), (35, 30, 74))


def labels(*entries):
    return tuple(Label(text, (x, y)) for text, x, y in entries)


def page(kind, *entries, **properties):
    frame = Frame(CANVAS, labels(*entries))
    frame.__dict__.update(page=kind, **properties)
    return frame


def enable_investment_confirm(frame):
    x, y = frame.investment_confirm().point
    frame.image = frame.image.copy()
    ImageDraw.Draw(frame.image).rectangle((x - 57, y - 10, x + 57, y + 10), fill=(235, 235, 235))
    return frame


def slot(zone, index, unit=None, *, occupied=False):
    return policy.Slot(zone, index, (735 + index * 140, {"front": 405, "back": 670, "bench": 910}[zone]),
                       occupied or unit is not None, unit)


def halo_selection(target):
    return task.HaloSelection("2-7", ((target, np.zeros((61, 60, 3), dtype=np.uint8)),))


def match_halo_at(monkeypatch, frames, point):
    for frame in frames:
        monkeypatch.setattr(frame, "halo_portrait_scores", lambda points, _: tuple(float(p == point) for p in points))


CORE = policy.Unit("那刻夏", True, False, 2, equipment=0)
BAILU = policy.Unit("白露", False, True, 1)
CER = policy.Unit("刻律德菈", False, True, 1)
FILLER = policy.Unit("瓦尔特", True, True, 1)
EVERNIGHT = policy.Unit("长夜月", True, True, 2, output=True, equipment=0)


def board(*slots, **kwargs):
    defaults = dict(stage="1-3", gold=16, hp=75, used=2, capacity=3, level=3, exp=(0, 4), slots=slots)
    return policy.Board(**(defaults | kwargs))


@pytest.fixture
def world(monkeypatch):
    now = [0.0]
    cfg = SimpleNamespace(currencywars_type="normal", currencywars_rank_difficulty="current",
                          currencywars_fast_mode=False, currencywars_bonus_enable=False,
                          currencywars_strategy=policy.HIGH_ANAXA, save_timestamp=Mock(), currencywars_timestamp=1,
                          refresh_hour=4)
    cfg.get_value = lambda key, default=None: getattr(cfg, key, default)
    fake_auto = Mock()
    fake_auto.find_element.side_effect = lambda target, *args, **kwargs: tuple(
        round(value * scale) for value, scale in zip(target[:2], (1920, 1080))
    )
    monkeypatch.setattr(task, "cfg", cfg)
    monkeypatch.setattr(task, "auto", fake_auto)
    monkeypatch.setattr(task, "get_ui_profile", lambda _: SimpleNamespace(name="pc_1080"))
    monkeypatch.setattr(task, "pause_ctl", Mock())
    monkeypatch.setattr(task, "Base", Mock())
    monkeypatch.setattr(task, "save_error_screenshot", Mock())
    monkeypatch.setattr(task, "time", SimpleNamespace(
        monotonic=lambda: now[0], time=lambda: 1794405000, sleep=lambda seconds: now.__setitem__(0, now[0] + seconds),
    ))
    war = task.CurrencyWars()
    war.mode = "normal"
    return SimpleNamespace(war=war, auto=fake_auto, cfg=cfg, now=now)


def drive(monkeypatch, world, initial, on_click=None, after_capture=None):
    state = SimpleNamespace(frame=initial, clicks=[], keys=[])
    def observe(*, until=None):
        world.war._check_budget()
        if after_capture is not None:
            after_capture(state)
        world.war.frame = state.frame
        return state.frame

    def click(point, *, press_duration):
        state.clicks.append((state.frame.page, point))
        if on_click is not None:
            return on_click(state, point) is not False
        return True

    monkeypatch.setattr(world.war, "_observe", observe)
    world.auto.click_element_with_pos.side_effect = click
    world.auto.press_key.side_effect = lambda key: state.keys.append((state.frame.page, key))
    observe()
    return state


@pytest.mark.parametrize("count", (6, 7, 8, 9))
def test_back_slots_are_read_from_edges_even_with_gaps(count):
    image = CANVAS.copy()
    draw = ImageDraw.Draw(image)
    xs = tuple(round(960 + (i - (count - 1) / 2) * 142) for i in range(count))
    for i, x in enumerate(xs):
        draw.rectangle((x - 59, 598, x + 59, 731), outline=(78, 74, 113), width=2)
        if i in (1, count - 1):
            draw.rectangle((x - 40, 631, x + 40, 700), fill=(220, 181, 128))
            draw.rectangle((x - 10, 632, x + 40, 700), fill=(114, 21, 180))
    frame = Frame(image, ())
    assert frame.back_row() == xs
    assert [s.index for s in frame.slots() if s.zone == "back" and s.occupied] == [1, count - 1]


def test_missing_slot_geometry_is_unknown():
    assert Frame(CANVAS, ()).slots() == ()


def test_black_hole_marker_is_neither_an_employee_nor_a_safe_bench_space():
    image = CANVAS.copy()
    marker = Image.open("assets/images/screen/currency_wars/s2_black_hole_slot.png")
    x, y = ui.BENCH_POINTS[0]
    image.paste(marker, (x - 35, y - 33))
    draw = ImageDraw.Draw(image)
    x2, _ = ui.BENCH_POINTS[1]
    draw.rectangle((x2 - 30, y - 26, x2 - 3, y + 28), fill=(197, 152, 119))
    draw.rectangle((x2 + 4, y - 24, x2 + 29, y + 22), fill=(87, 32, 159))
    frame = Frame(image, ())
    blocked, employee, *empty = frame.bench_slots()
    assert not blocked.occupied and blocked.blocked
    assert employee.occupied and not employee.blocked
    assert board(*frame.bench_slots()).empty_bench == tuple(empty)
    source = slot("front", 0, FILLER)
    assert not policy.can_move(board(source, blocked), source, blocked)


def test_new_black_hole_in_a_pending_bench_destination_prevents_the_drag(monkeypatch, world):
    source = slot("front", 0, FILLER)
    destination = policy.Slot("bench", 0, ui.BENCH_POINTS[0], False)
    b = board(source, destination, used=1)
    initial = page(Page.BOARD, stage=b.stage, capacity=(b.used, b.capacity))
    updated = page(Page.BOARD, stage=b.stage, capacity=(b.used, b.capacity))
    updated.image = CANVAS.copy()
    x, y = destination.point
    updated.image.paste(Image.open("assets/images/screen/currency_wars/s2_black_hole_slot.png"), (x - 35, y - 33))
    for frame in (initial, updated):
        monkeypatch.setattr(frame, "slot_occupied", lambda point: point == source.point)
    reads = 0

    def capture(state):
        nonlocal reads
        reads += 1
        if reads > 1:
            state.frame = updated

    drive(monkeypatch, world, initial, after_capture=capture)
    with pytest.raises(task.CurrencyWarsActionUnready, match="角色移动未确认"):
        world.war._move(initial, b, source, destination)
    world.auto.drag_mouse.assert_not_called()


def test_deployment_lock_badge_keeps_the_slot_occupied_and_is_read_again():
    portrait = CANVAS.copy()
    x, y = ui.BENCH_POINTS[0]
    draw = ImageDraw.Draw(portrait)
    draw.rectangle((x - 30, y - 26, x - 3, y + 28), fill=(197, 152, 119))
    draw.rectangle((x + 4, y - 24, x + 29, y + 22), fill=(87, 32, 159))
    marked = portrait.copy()
    marked.paste(Image.open("assets/images/screen/currency_wars/s2_bench_deployment_lock.png"), (x - 25, y - 98))
    assert Frame(marked, ()).bench_slots()[0].occupied
    assert Frame(marked, ()).bench_slots()[0].blocked
    assert not Frame(portrait, ()).bench_slots()[0].blocked
    assert Frame(CANVAS, labels(("19节点后", 1584, 932), ("解锁上阵", 1673, 933))).employee_deployment_locked()


def test_locked_employee_is_not_a_deployable_output_upgrade_or_bench_replacement():
    locked = replace(slot("bench", 0, CORE), blocked=True)
    low = slot("front", 0, replace(CORE, stars=1))
    damage = slot("bench", 1, policy.Unit("过渡输出", True, True, 1, output=True))
    spare, front = slot("bench", 2), slot("front", 1)
    only_locked = board(low, front, locked, spare, used=1, capacity=1, gold=30)
    assert not only_locked.core_upgraded
    assert not policy.should_buy_exp(only_locked, 4)
    assert policy.stronger_bench_copy(only_locked, low) is None
    assert not policy.can_move(only_locked, locked, front)
    assert policy.overflow_reserves(only_locked) == ()
    needs_damage = board(front, locked, damage, spare, used=0, capacity=1)
    assert policy.deployment(needs_damage) == ((damage, front),)
    unlocked = replace(locked, blocked=False)
    after = replace(only_locked, stage="1-4", slots=(low, front, unlocked, spare))
    assert after.core_upgraded
    assert policy.deployment(after)[1][0] == unlocked


@pytest.mark.parametrize("y", (ui.FRONT_Y, ui.BACK_Y))
def test_field_occupancy_distinguishes_dance_links_from_employee_cards(y):
    x = 1030
    image = CANVAS.copy()
    draw = ImageDraw.Draw(image)
    draw.line((x - 56, y + 20, x + 56, y - 23), fill=(146, 54, 239), width=8)
    assert not Frame(image, ()).slot_occupied((x, y))

    # 卡面颜色集中时，右上站位标记仍可确认该格有角色。
    draw.rectangle((x + 39, y - 52, x + 49, y - 47), fill="white")
    assert Frame(image, ()).slot_occupied((x, y))


def test_reward_orb_search_excludes_round_edges_in_the_consumable_bar():
    image = CANVAS.copy()
    draw = ImageDraw.Draw(image)
    draw.ellipse((1580, 151, 1620, 191), fill=(201, 222, 90), outline="white", width=3)
    draw.ellipse((1390, 276, 1434, 320), fill=(45, 156, 235), outline="white", width=3)
    orbs = Frame(image, ()).reward_orbs()
    assert len(orbs) == 1
    x, y = orbs[0]
    assert abs(x - 1412) <= 5 and abs(y - 298) <= 5


def test_adjacent_card_edges_do_not_create_a_second_back_row_layout():
    image = CANVAS.copy()
    draw = ImageDraw.Draw(image)
    centers = tuple(960 + i * 142 for i in range(-3, 4))
    for x in centers:
        draw.rectangle((x - 65, 598, x + 65, 731), outline=(160, 205, 201), width=2)
    draw.rectangle((centers[-1] - 25, 641, centers[-1], 693), fill=(200, 160, 130))
    frame = Frame(image, ())
    assert frame.back_row() == centers
    assert [s.index for s in frame.slots() if s.zone == "back" and s.occupied] == [6]


def test_hud_prefix_and_point_ratio_have_different_parsers():
    frame = Frame(CANVAS, labels(("i0/3", 935, 258), ("7800/16000", 272, 740)))
    assert frame.capacity == (0, 3)
    assert frame.ratio(ui.WEEKLY_SCORE) == (7800, 16000)


def test_board_scan_keeps_partner_occupied_after_closing_its_detail(monkeypatch, world):
    occupied = slot("back", 6, occupied=True)
    frame = page(Page.BOARD, stage="1-1", capacity=(1, 4), gold=5)
    detail = Frame(CANVAS, labels(("备战阶段", 286, 72), ("1-1", 284, 105), ("杨叔", 1521, 521),
                                 ("后台", 1549, 561), ("大机器人是对的。越大越对。", 1535, 635)))
    assert detail.page == Page.PARTNER_DETAIL
    monkeypatch.setattr(frame, "slots", lambda: (occupied,))
    monkeypatch.setattr(frame, "slot_occupied", lambda point: point == occupied.point)
    monkeypatch.setattr(frame, "card_role", lambda _: (False, True))
    state = drive(monkeypatch, world, frame, lambda s, p: setattr(
        s, "frame", detail if p == occupied.point else frame))
    after, scanned = world.war._read_board(frame)
    assert after is frame and scanned.slots == (occupied,)
    assert world.war._read_board(frame)[1].slots == (occupied,)
    assert state.clicks == [(Page.BOARD, occupied.point), (Page.PARTNER_DETAIL, (12, 12))]


@pytest.mark.parametrize(("name_y", "role_y"), ((230, 270), (268, 308)))
def test_employee_detail_finds_the_name_above_the_role_when_the_panel_moves(name_y, role_y):
    f = Frame(CANVAS, labels(("备战阶段", 470, 45), ("1-2", 470, 76),
                             ("试用", 1469, name_y - 27), ("大丽花", 1534, name_y),
                             ("前后台", 1560, role_y), ("推荐", 1511, 856)))
    assert f.page == Page.DETAIL and f.employee_name() == "大丽花"


def test_capacity_recovers_when_the_person_icon_is_read_as_a_digit(monkeypatch):
    f = Frame(CANVAS, labels(("备战阶段", 285, 71), ("1-1", 285, 110), ("12/3", 950, 258)))
    read = Mock(return_value="2/3")
    monkeypatch.setattr(f, "read_local", read)
    assert f.capacity == (2, 3)
    read.assert_called_once_with(ui.BOARD_CAPACITY_DIGITS, recognition_only=True)


@pytest.mark.parametrize(("whole", "local", "expected"), [
    ("9", "91", 91),
    ("1", "1", 1),
    (None, "2", 2),
    (None, "100", 100),
    ("55", "S", 55),
    ("55", "551", 55),
    (None, "?", None),
])
def test_squad_health_reads_the_complete_number_before_using_the_full_frame(monkeypatch, whole, local, expected):
    values = labels((whole, 1451, 80)) if whole else ()
    frame = Frame(CANVAS, values)
    monkeypatch.setattr(frame, "read_local",
                        lambda area, *, recognition_only=False: local if area == ui.BOARD_HP and recognition_only else None)
    assert frame.squad_health == expected


def test_experience_panel_reads_level_and_slash_from_separate_lines(monkeypatch):
    f = Frame(CANVAS, labels(("购买经验", 296, 861), ("8", 324, 903), ("3672", 294, 942)))
    read = Mock(side_effect=("Lv.9", "36/72"))
    monkeypatch.setattr(f, "read_local", read)
    assert f.level == 9
    assert f.experience == (36, 72)
    assert [args.kwargs for args in read.call_args_list] == [{"recognition_only": True}] * 2


def test_experience_cost_can_be_read_without_the_detection_box(monkeypatch):
    f = page(Page.BENCH_FULL, ("购买经验", 296, 861))
    read = Mock(return_value="4")
    monkeypatch.setattr(f, "read_local", read)
    assert f.experience_cost == 4
    read.assert_called_once_with(ui.BOARD_XP_COST, recognition_only=True)


def test_coin_counter_recognizes_one_line_without_splitting_adjacent_digits(monkeypatch):
    f = Frame(CANVAS, labels(("1", 1642, 917)))
    recognize = Mock(return_value=[(None, ("11", 0.99))])
    from module.ocr import ocr

    monkeypatch.setattr(ocr, "recognize_multi_lines", recognize)
    assert f.gold == 11
    assert recognize.call_args.kwargs == {"recognition_only": True}


def test_coin_counter_tries_the_second_crop_when_the_first_is_uncertain(monkeypatch):
    f = Frame(CANVAS, ())
    read = Mock(side_effect=(None, "4"))
    monkeypatch.setattr(f, "read_local", read)
    assert f.gold == 4
    assert [args.args[0] for args in read.call_args_list] == [ui.BOARD_GOLD_DIGITS, ui.BOARD_GOLD]


def test_coin_counter_crop_keeps_the_hundreds_digit(monkeypatch):
    image = CANVAS.copy()
    ImageDraw.Draw(image).rectangle((1623, 907, 1627, 934), fill="white")
    f = page(Page.BENCH_FULL)
    f.image = image
    from module.ocr import ocr

    def recognize(crop, *, recognition_only):
        assert recognition_only
        return [(None, ("129" if crop[:, :, 0].max() > 220 else "29", 0.99))]

    monkeypatch.setattr(ocr, "recognize_multi_lines", recognize)
    assert f.gold == 129


@pytest.mark.parametrize("coin_left", (1570, 1589))
def test_coin_counter_uses_narrow_ocr_only_at_the_single_digit_icon_position(monkeypatch, coin_left):
    image = CANVAS.copy()
    ImageDraw.Draw(image).rectangle((coin_left, 900, coin_left + 41, 934), fill=(210, 170, 80))
    f = Frame(image, ())
    read = Mock(side_effect=lambda area, **kwargs: "0" if area == ui.BOARD_GOLD_SINGLE else None)
    monkeypatch.setattr(f, "read_local", read)
    assert f.gold == (0 if coin_left == 1589 else None)


def test_employee_detail_sale_quote_is_not_the_covered_balance(monkeypatch):
    f = page(Page.DETAIL, ("+3", 1648, 918), ("出售", 1770, 917))
    read = Mock(return_value="3")
    monkeypatch.setattr(f, "read_local", read)
    assert f.sell_price == 3
    assert f.gold is None
    read.assert_not_called()


def test_employee_detail_sale_quote_recognizes_a_narrow_crop_without_the_coin(monkeypatch):
    f = page(Page.DETAIL, ("出售", 1770, 917))
    read = Mock(return_value="+1")
    monkeypatch.setattr(f, "read_local", read)
    assert f.sell_price == 1
    read.assert_called_once_with(ui.DETAIL_SELL_DIGITS, recognition_only=True)


def test_season_gate_and_battle_conflict():
    labels_ = labels(("零和博弈", 152, 131), ("开始货币战争", 1600, 972))
    assert Frame(CANVAS, labels_).page == Page.UNKNOWN
    frame = Frame(CANVAS, labels(("入画奇航", 152, 131), ("开始货币战争", 1600, 972),
                                  ("我方行动中", 1734, 999)))
    assert frame.page == Page.CONFLICT


def test_final_node_challenge_end_does_not_imply_match_loss():
    f = Frame(CANVAS, labels(("挑战结束", 956, 230), ("前往结算", 960, 895)))
    assert f.page == Page.NODE_RESULT
    f = Frame(CANVAS, labels(("挑战成功", 956, 230), ("对局评价", 960, 375), ("下一步", 960, 895)))
    assert f.page == Page.MATCH_RESULT


def test_halo_and_tea_have_distinct_page_anchors():
    f = Frame(CANVAS, labels(("选择一个角色获得主角光环", 960, 90), ("返回备战界面", 1740, 62)))
    assert f.page == Page.HALO
    f = Frame(CANVAS, labels(("2-6", 906, 57), ("返回备战界面", 1740, 63),
                             ("点击空白处继续", 1562, 925)))
    assert f.page == Page.TEA


def test_tea_reward_anchors_survive_a_fused_stage_icon():
    f = Frame(CANVAS, labels(("M1-5", 896, 62), ("领取茶歇奖励", 960, 195), ("开启", 960, 982)))
    assert f.page == Page.TEA
    assert f.tea_button().text == "开启"


def test_tea_prefers_explicitly_displayed_healing_across_companions():
    controls = (("聊一聊", 386, 837), ("摇一摇", 1552, 837), ("回复20小队生命值", 1546, 770),
                ("100", 994, 82))
    assert Frame(CANVAS, labels(*controls, ("练习作画", 386, 675))).tea_button().text == "摇一摇"
    assert Frame(CANVAS, labels(*controls, ("灌洗小犬", 386, 675))).tea_button().text == "摇一摇"


def test_tea_returns_from_a_coffee_menu_with_only_health_cost_options():
    f = Frame(CANVAS, labels(("亮晶晶咖啡", 1210, 450), ("获得随机星徽，失去8生命值", 1300, 520),
                             ("螺丝钉咖啡", 1210, 613), ("获得随机进阶装备，失去4生命值", 1325, 680),
                             ("返回", 1175, 809)))
    assert f.tea_button().text == "返回"


def test_board_uses_proven_position_and_keeps_healer():
    before = board(slot("front", 0, FILLER), slot("back", 0, BAILU), slot("back", 1),
                   slot("bench", 0, CORE), slot("bench", 1))
    moves = policy.deployment(replace(before, used=3, capacity=3))
    assert moves[0] == (before.slots[0], before.slots[-1])
    assert moves[1] == (before.slots[3], slot("front", 0))
    moved = board(slot("front", 0), slot("back", 0, BAILU), slot("back", 1),
                  slot("bench", 0, CORE), slot("bench", 1, FILLER), used=1)
    assert policy.deployment(moved) == ((moved.slots[3], moved.slots[0]),)


def test_cerydra_prefers_first_back_slot_with_checked_empty_destination():
    before = board(slot("front", 0, CORE), slot("back", 0, BAILU), slot("back", 1, CER),
                   slot("back", 2), slot("bench", 0), used=3)
    assert policy.deployment(before) == ((before.slots[1], before.slots[3]),
                                        (before.slots[2], slot("back", 0)))


def test_refuse_special_object_and_uncertain_occupancy():
    before = board(slot("front", 0, policy.Unit("白厄", True, False)), slot("front", 1, occupied=True),
                   slot("bench", 0, CORE), slot("bench", 1), used=2, capacity=2)
    assert policy.deployment(before) == ()


def ten_employee_board(front, back, bench, **kwargs):
    return board(
        *(slot(zone, index, unit) for zone, row in (("front", front), ("back", back), ("bench", bench))
          for index, unit in enumerate(row)),
        used=10, capacity=10, level=10, **kwargs,
    )


def apply_deployment(board_before, move, *, replacing_same_name=False):
    source, target = move
    assert policy.can_move(board_before, source, target, replacing_same_name=replacing_same_name)
    changed = tuple(
        replace(current, occupied=False, unit=None) if current == source
        else replace(current, occupied=True, unit=source.unit) if current == target
        else current for current in board_before.slots
    )
    used = board_before.used + (source.zone == "bench") - (target.zone == "bench")
    return replace(board_before, slots=changed, used=used)


def test_full_ten_person_team_makes_room_for_priority_assist():
    fronts = (CORE, FILLER, policy.Unit("星期日", True, True, 2), policy.Unit("知更鸟", True, False))
    backs = (CER, BAILU, *(policy.Unit(f"后台角色{i}", False, True) for i in range(4)))
    sparkle = policy.Unit("花火", True, False)
    full = ten_employee_board(fronts, backs, (sparkle, None), lineup=policy.LINEUPS[policy.HIGH_ANAXA])
    plan = policy.deployment(full)
    # 星期日卡面推荐前后台都能站，高人口时攻略让她在后台：她退到后台，换下后台的过渡角色，花火补上她的前台位。
    assert [(source.unit.name, target.zone) for source, target in plan] == [
        ("后台角色0", "bench"), ("星期日", "back"), (sparkle.name, "front")]
    for move in plan:
        full = apply_deployment(full, move)
    assert full.used == 10 and full.slots[2].unit == sparkle and full.slots[6].unit == fronts[2]
    assert policy.deployment(full) == ()


def test_early_replacement_preserves_the_only_frontline_damage_dealer():
    damage = policy.Unit("过渡输出", True, True, 1, output=True)
    sparkle = policy.Unit("花火", True, False, 1)
    robin = policy.Unit("知更鸟", True, False, 1)
    fallback = slot("front", 2, damage)
    rear = slot("back", 0)
    lead = slot("bench", 0, CER)
    before = board(slot("front", 0, sparkle), slot("front", 1, robin), fallback, rear,
                   lead, slot("bench", 1), stage="1-1", used=3, capacity=3, lineup=policy.LINEUPS[policy.HIGH_ANAXA])
    assert not policy.can_move(before, fallback, rear)
    plan = policy.deployment(before)
    assert [source.unit for source, _ in plan] == [robin, CER]
    assert plan[-1][1] == rear
    for move in plan:
        before = apply_deployment(before, move)
    assert before.front_output_count == 1
    assert fallback in before.field


@pytest.mark.parametrize("capacity", (3, 4))
def test_a_deployable_output_can_join_a_support_only_team_at_or_below_capacity(capacity):
    damage = policy.Unit("另一个输出", True, True, 2, output=True)
    front = tuple(slot("front", index, unit) for index, unit in enumerate((
        policy.Unit("花火", True, False), policy.Unit("星期日", True, True),
        policy.Unit("知更鸟", True, False), None,
    )))
    source = slot("bench", 0, damage)
    before = board(*front, slot("back", 0), source, slot("bench", 1, CER), slot("bench", 2),
                   stage="1-1", used=3, capacity=capacity)
    plan = policy.deployment(before)
    assert plan[-1] == (source, front[3])
    for move in plan:
        before = apply_deployment(before, move)
    assert before.front_output_count == 1


def test_employee_output_uses_the_function_badge_in_the_detail_panel(monkeypatch):
    damage = Frame(CANVAS, labels(("输出", 1829, 270), ("前后台", 1557, 270), ("治疗", 1535, 307)))
    support = Frame(CANVAS, labels(("辅助", 1829, 301), ("输出", 1515, 368)))
    missing = Frame(CANVAS, ())
    monkeypatch.setattr(missing, "read_local", lambda area: "输出" if area == ui.DETAIL_FUNCTION else None)
    assert damage.employee_output()
    assert not support.employee_output()
    assert missing.employee_output()


def test_empty_front_slot_can_restore_output_from_the_back_row():
    damage = policy.Unit("双站位输出", True, True, 1, output=True)
    source, target = slot("back", 0, damage), slot("front", 1)
    before = board(slot("front", 0, policy.Unit("花火", True, False)), target, source,
                   used=2, capacity=2)
    assert policy.deployment(before) == ((source, target),)


@pytest.mark.parametrize(("first", "other_rear", "hp"), (
    (policy.Unit("符玄", True, False), BAILU, 100),
    (policy.Unit("符玄", True, False), policy.Unit("后台过渡", False, True), 100),
    (policy.Unit("符玄", True, False), BAILU, 30),
    (policy.Unit("灵砂", True, True), policy.Unit("杰帕德", True, True), 100),
))
def test_core_replaces_a_front_unit_even_if_it_is_the_last_healer_or_shield(first, other_rear, hp):
    """小队掉血来自限定行动内没打完怪物，看的是阵容战斗力，治疗和护盾多一个影响不大。部署不再护着场上最后一名
    治疗或生存角色，生命值低时也不多留：核心照常换下前台第一位上场。"""
    front = (first, policy.Unit("花火", True, False), policy.Unit("星期日", True, True),
             policy.Unit("知更鸟", True, False))
    rear = (CER, other_rear, *(policy.Unit(f"后台角色{i}", False, True) for i in range(4)))
    full = ten_employee_board(front, rear, (CORE, None), hp=hp)
    moves = policy.deployment(full)
    assert moves[0][0].unit == first and moves[1][0].unit == CORE


def test_full_rear_rotation_redeploys_the_same_employee_from_the_buffer():
    front = (CORE, *(policy.Unit(f"前台角色{i}", True, False) for i in range(3)))
    rear = (BAILU, CER, *(policy.Unit(f"后台角色{i}", False, True) for i in range(4)))
    full = ten_employee_board(front, rear, (None,))
    moves = policy.deployment(full)
    assert [(source.unit.name, target.zone, target.index) for source, target in moves] == [
        (BAILU.name, "bench", 0), (CER.name, "back", 0), (BAILU.name, "back", 1),
    ]
    assert policy.deployment(full, overflow=True) == ()
    for move in moves:
        full = apply_deployment(full, move)
    assert full.used == 10 and full.empty_bench and full.slots[4].unit == CER and full.slots[5].unit == BAILU


def test_full_rear_rotation_uses_a_legal_front_position_for_a_flexible_employee():
    lead = replace(CER, front=True)
    front = (CORE, lead, policy.Unit("前台过渡甲", True, False), policy.Unit("前台过渡乙", True, False))
    rear = (BAILU, FILLER, *(policy.Unit(f"后台角色{i}", False, True) for i in range(4)))
    full = ten_employee_board(front, rear, (None,))
    moves = policy.deployment(full)
    assert [source.unit.name for source, _ in moves] == [BAILU.name, lead.name, FILLER.name, BAILU.name]
    for move in moves:
        full = apply_deployment(full, move)
    assert full.used == 10 and full.slots[1].unit == FILLER and full.slots[4].unit == lead
    assert full.slots[5].unit == BAILU and full.empty_bench


def test_population_upgrade_requires_a_distinct_employee_and_an_available_legal_slot():
    b = board(slot("front", 0, CORE), slot("front", 1, FILLER), slot("front", 2, occupied=True),
              slot("front", 3, occupied=True), slot("back", 0, CER), slot("back", 1, BAILU),
              slot("back", 2), slot("bench", 0, replace(CORE, stars=1)),
              slot("bench", 1, policy.Unit("前台候补", True, False)), slot("bench", 2),
              used=6, capacity=6, level=6, exp=(32, 36), gold=12)
    assert not policy.should_buy_exp(b, 4)
    candidate = slot("bench", 1, policy.Unit("后台候补", False, True))
    assert policy.should_buy_exp(replace(b, slots=(*b.slots[:-2], candidate, b.slots[-1])), 4)


def test_shop_can_buy_an_actual_filler_when_only_the_same_name_copy_is_waiting():
    b = board(slot("front", 0, CORE), slot("back", 0), slot("bench", 0, replace(CORE, stars=1)),
              slot("bench", 1), used=1, capacity=2, gold=6, lineup=policy.LINEUPS[policy.HIGH_ANAXA])
    filler = policy.Offer("娜塔莎", 1, (400, 200), 1)
    assert policy.shop_purchase(b, (filler,)) == filler


def test_two_star_core_on_the_bench_does_not_mark_the_field_ready():
    b = board(slot("front", 0, FILLER), slot("front", 1), slot("bench", 0, CORE), slot("bench", 1))
    assert b.core_upgraded and not b.core_ready
    assert not policy.should_refresh(b, 1, 0)
    assert policy.shop_purchase(b, (policy.Offer(CORE.name, 1, (100, 200), 0),)) is None


@pytest.mark.parametrize("stars", (1, 2))
def test_full_team_replaces_the_deployed_core_with_the_highest_confirmed_copy(stars):
    low = replace(CORE, stars=stars)
    high = replace(CORE, stars=3)
    front = (low, *(policy.Unit(f"前台角色{i}", True, False) for i in range(3)))
    rear = (CER, BAILU, *(policy.Unit(f"后台角色{i}", False, True) for i in range(4)))
    current = ten_employee_board(front, rear, (CORE, high, None))
    plan = policy.deployment(current)
    assert [(src.unit.stars, dst.zone, dst.index) for src, dst in plan] == [
        (stars, "bench", 2), (3, "front", 0),
    ]
    assert not policy.can_move(current, *plan[1])
    assert policy.deployment(current, overflow=True) == ()
    after_first = apply_deployment(current, plan[0])
    assert not after_first.core_ready and after_first.used == 9
    result = apply_deployment(after_first, plan[1])
    assert result.used == 10 and result.core_ready and result.slots[0].unit == high
    assert policy.deployment(result) == ()


@pytest.mark.parametrize(("field_stars", "bench_stars", "eligible", "empty"), (
    (1, 2, True, False), (1, 1, True, True), (1, None, True, True),
    (None, 2, True, True), (1, 2, False, True),
))
def test_same_name_core_swap_requires_a_known_upgrade_and_a_free_buffer(field_stars, bench_stars, eligible, empty):
    b = board(slot("front", 0, replace(CORE, stars=field_stars)), slot("back", 0, CER),
              slot("bench", 0, replace(CORE, stars=bench_stars, front=eligible)),
              slot("bench", 1, None if empty else FILLER),
              used=2, capacity=2, level=4, exp=(0, 4))
    assert policy.deployment(b) == ()
    assert not policy.should_buy_exp(b, 4)


@pytest.mark.parametrize(("equipment", "halo", "eligible"), [
    (0, False, True), (1, False, False), (None, False, False), (0, True, True), (1, True, False),
])
def test_normal_core_replacement_requires_gear_and_allows_same_name_halo_inheritance(equipment, halo, eligible):
    active = slot("front", 0, replace(CORE, stars=1, equipment=equipment, has_halo=halo))
    incoming = slot("bench", 0, CORE)
    spare = slot("bench", 1)
    b = board(active, incoming, spare, used=1, capacity=1)
    if eligible:
        assert policy.deployment(b)[0] == (active, spare)
    else:
        assert policy.deployment(b) == ()


def test_halo_holder_is_kept_even_if_a_different_employee_has_higher_priority():
    active = slot("front", 0, replace(FILLER, has_halo=True))
    incoming = slot("bench", 0, policy.Unit("花火", True, False, 2))
    spare = slot("bench", 1)
    b = board(active, incoming, spare, used=1, capacity=1, lineup=policy.LINEUPS[policy.HIGH_ANAXA])
    assert policy.deployment(b) == ()
    assert policy.deployment(replace(b, slots=(replace(active, unit=FILLER), incoming, spare)))


def test_core_swap_rechecks_the_upgrade_before_removing_the_original(world):
    low = replace(CORE, stars=1)
    active, incoming, spare = slot("front", 0, low), slot("bench", 0, CORE), slot("bench", 1)
    b = board(active, incoming, spare, used=1, capacity=1)
    assert world.war._next_deployment(b) == (active, spare)
    stale = replace(b, slots=(active, replace(incoming, unit=low), spare))
    assert world.war._next_deployment(stale) is None


def test_core_swap_replans_and_restores_the_confirmed_copy_after_a_change(world):
    low = replace(CORE, stars=1)
    active, incoming, spare = slot("front", 0, low), slot("bench", 0, CORE), slot("bench", 1)
    b = board(active, incoming, spare, used=1, capacity=1)
    intermediate = apply_deployment(b, world.war._next_deployment(b))
    assert world.war._next_deployment(intermediate) == (incoming, intermediate.slots[0])
    unreadable = replace(incoming, unit=replace(CORE, stars=None))
    changed = replace(intermediate, slots=(intermediate.slots[0], unreadable, intermediate.slots[2]))
    assert world.war._next_deployment(changed) == (intermediate.slots[2], intermediate.slots[0])


def test_rotation_reconciles_the_move_after_an_intervening_overlay(world):
    front = (CORE, *(policy.Unit(f"前台角色{i}", True, False) for i in range(3)))
    rear = (BAILU, CER, *(policy.Unit(f"后台角色{i}", False, True) for i in range(4)))
    current = ten_employee_board(front, rear, (None,))
    first = world.war._next_deployment(current)
    current = apply_deployment(current, first)
    second = world.war._next_deployment(current)
    assert second[0].unit == CER and (second[1].zone, second[1].index) == ("back", 0)
    current = apply_deployment(current, second)
    final = world.war._next_deployment(current)
    assert final[0].unit == BAILU and final[1].index == 1
    current = apply_deployment(current, final)
    assert world.war._next_deployment(current) is None


def test_rotation_discards_a_plan_when_the_spare_slot_is_no_longer_empty(world):
    front = (CORE, *(policy.Unit(f"前台角色{i}", True, False) for i in range(3)))
    rear = (BAILU, CER, *(policy.Unit(f"后台角色{i}", False, True) for i in range(4)))
    current = ten_employee_board(front, rear, (None,))
    assert world.war._next_deployment(current)[0].unit == BAILU
    occupied = slot("bench", 0, occupied=True)
    changed = replace(current, slots=(*current.slots[:-1], occupied))
    assert world.war._next_deployment(changed) is None
    assert world.war.deployment_moves == ()


def test_prepare_inspects_the_existing_shop_before_committing_experience(monkeypatch, world):
    frame = page(Page.BOARD, ("购买经验", 298, 863), stage="1-2", gold=12, experience_cost=4)
    outcome = page(Page.CHOICE)
    current = board(slot("front", 0, replace(CORE, stars=1)), slot("back", 0, CER), slot("back", 1),
                    slot("bench", 0, policy.Unit("后台候补", False, True)), slot("bench", 1), slot("bench", 2),
                    stage="1-2", used=2, capacity=2, level=6, gold=12, exp=(32, 36))
    operations = []
    monkeypatch.setattr(world.war, "_settle_board", lambda f: f)
    monkeypatch.setattr(world.war, "_gather", lambda f: f)
    monkeypatch.setattr(world.war, "_read_board", lambda f: (f, current))

    def shop(f, b, refreshes, *, experience_price):
        assert b is current and experience_price == 4
        operations.append("商店")
        return f, refreshes, False

    def experience(f, b, price):
        assert b is current and price == 4
        operations.append("经验")
        return outcome

    monkeypatch.setattr(world.war, "_shop", shop)
    monkeypatch.setattr(world.war, "_buy_exp", experience)
    assert world.war._prepare(frame) is outcome
    assert operations == ["商店", "经验"]


@pytest.mark.parametrize("expand", (False, True))
def test_high_lineup_stops_cyclic_replacements_and_keeps_preparing(monkeypatch, world, expand):
    stage, fight = "3-3", (1818, 751)
    frame = page(Page.BOARD, ("出战", *fight), ("购买经验", 298, 863), stage=stage, experience_cost=4)
    won = page(Page.MATCH_RESULT, ("对局胜利", 960, 260), ("返回货币战争", 960, 899))
    lobby = home()
    # 不死途和缇宝都在阵容的后台偏好里，缇宝排在前面。
    backup = policy.Unit("不死途", False, True, 2)
    tribbie = policy.Unit("缇宝", False, True, 3)
    initial = board(
        slot("front", 0, CORE), slot("back", 0, BAILU), slot("back", 3, backup), slot("back", 5),
        slot("bench", 2), slot("bench", 3, tribbie), slot("bench", 4), slot("bench", 5),
        stage=stage, used=3, capacity=3, lineup=policy.LINEUPS[policy.HIGH_ANAXA],
    )
    current = initial
    moves = []
    shops = []
    world.cfg.currencywars_strategy = policy.HIGH_ANAXA
    world.cfg.currencywars_type = "overclock"

    def drag(f, team, source, target):
        nonlocal current
        moves.append((source.unit.name, target.zone, target.index))
        current = apply_deployment(team, (source, target))
        if source.unit.name == tribbie.name:
            # 注入不同区域的星级识别冲突，让真实策略在两套阵容间反复换位。
            current = replace(current, slots=tuple(
                replace(s, unit=replace(tribbie, stars=3 if s.zone == "bench" else 1))
                if s.unit and s.unit.name == tribbie.name else s for s in current.slots
            ))
        return f

    def shop(f, team, refreshes, **_):
        shops.append(team)
        return f, refreshes, False

    def buy_exp(f, team, _):
        nonlocal current
        assert team == initial
        current = replace(team, capacity=4, gold=team.gold - 4)
        return f

    monkeypatch.setattr(world.war, "_settle_board", lambda f: f)
    monkeypatch.setattr(world.war, "_collect_preparation_rewards", lambda f: (f, True))
    monkeypatch.setattr(world.war, "_read_board", lambda f: (f, current))
    monkeypatch.setattr(world.war, "_move", drag)
    monkeypatch.setattr(world.war, "_shop", shop)
    monkeypatch.setattr(world.war, "_can_buy_exp", lambda team, _: expand and team.capacity == 3)
    monkeypatch.setattr(world.war, "_buy_exp", buy_exp)
    monkeypatch.setattr(world.war, "_equip", lambda f, _: f)
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))
    routes = {(frame, fight): won, (won, (960, 899)): lobby}
    state = drive(monkeypatch, world, frame, lambda s, point: setattr(s, "frame", routes[s.frame, point]))

    assert world.war.start(resume=True)
    assert shops and shops[0] == initial
    expected = [("不死途", "bench", 2), ("缇宝", "back", 5), ("缇宝", "bench", 3), ("不死途", "back", 3)]
    if expand:
        expected.append(("缇宝", "back", 5))
        assert current.used == current.capacity == 4
    assert moves == expected
    assert state.clicks == [(Page.BOARD, fight), (Page.MATCH_RESULT, (960, 899))]


def test_default_deployment_prioritizes_cost_then_stars_and_keeps_one_legal_front():
    front, back = slot("front", 0), slot("back", 0)
    strongest = slot("bench", 0, replace(BAILU, cost=5, stars=1))
    front_candidate = slot("bench", 1, replace(FILLER, cost=2, stars=2))
    weaker = slot("bench", 2, replace(FILLER, name="其他角色", cost=2, stars=1))
    current = board(front, back, weaker, front_candidate, strongest, used=0)
    assert policy.default_deployment(current, {}, set()) == (front_candidate, front)
    current = apply_deployment(current, (front_candidate, front))
    assert policy.default_deployment(current, {}, set()) == (strongest, back)
    assert policy.default_deployment(current, {}, {(strongest.point, "back")}) == (weaker, back)


def test_default_deployment_uses_one_for_unreadable_cost_or_stars():
    target = slot("front", 0)
    missing = slot("bench", 0, replace(FILLER, stars=None))
    missing_cost = slot("bench", 1, replace(FILLER, stars=3))
    missing_stars = slot("bench", 2, replace(FILLER, cost=2, stars=None))
    current = board(target, missing, missing_cost, missing_stars, used=0)
    assert policy.default_deployment(current, {}, set()) == (missing_stars, target)
    assert policy.default_deployment(current, {}, {(missing_stars.point, "front")}) == (missing_cost, target)
    assert policy.default_priority(missing) == (1, 1)


@pytest.mark.parametrize("zone,y", (("front", ui.FRONT_Y), ("back", ui.BACK_Y), ("bench", ui.BENCH_Y)))
@pytest.mark.parametrize("lift", (0, 12))
def test_board_card_cost_reads_both_ends_of_the_bottom_edge(zone, y, lift):
    image = CANVAS.copy()
    draw = ImageDraw.Draw(image)
    colors = ((128, 131, 148), (44, 130, 121), (89, 112, 226), (143, 109, 248), (209, 170, 79))
    for index, color in enumerate(colors):
        x = 500 + index * 150
        draw.rectangle((x - 41, y + 51 - lift, x + 41, y + 56 - lift), fill=color)
        draw.rectangle((x - 11, y + 41 - lift, x + 11, y + 55 - lift), fill=(255, 227, 145))
    frame = Frame(image, ())
    assert [frame.card_cost(policy.Slot(zone, i, (500 + i * 150, y), True))
            for i in range(len(colors))] == [1, 2, 3, 4, 5]
    assert frame.card_cost(policy.Slot(zone, 5, (1250, y), True)) is None


@pytest.mark.parametrize("used,limit", ((9, 8), (9, 9)))
def test_halo_population_can_exceed_the_number_of_visible_cards(monkeypatch, used, limit):
    image = CANVAS.copy()
    if used > limit:
        ImageDraw.Draw(image).rectangle((904, 233, 1030, 267), fill=(238, 68, 57))
    frame = Frame(image, labels((f"{used}/{limit}", 960, 260)))
    field = (slot("front", 0, CORE), *(slot("back", index, BAILU) for index in range(7)))
    monkeypatch.setattr(frame, "assigned_halo", lambda point: point == field[0].point)
    assert frame.capacity == (used, limit)
    assert frame.field_count_matches(field)
    assert not frame.field_count_matches(field[1:])


def test_halo_population_disambiguates_a_double_digit_crop(monkeypatch):
    frame = Frame(CANVAS, labels(("备战阶段", 470, 45), ("3-5", 470, 78), ("10/10", 960, 260)))
    front = slot("front", 0, CORE)
    field = (front, *(slot("back", index, BAILU) for index in range(8)))
    monkeypatch.setattr(frame, "read_local", lambda area, **_: "0/10" if area == ui.BOARD_CAPACITY_DIGITS else "10/10")
    monkeypatch.setattr(frame, "field_slots", lambda: field)
    monkeypatch.setattr(frame, "assigned_halo", lambda point: point == front.point)
    assert frame.capacity == (10, 10)
    assert frame.field_count_matches(field)


def test_extra_population_halo_can_be_excluded_from_default_selection():
    frame = page(Page.HALO, ("天才医师", 420, 436), ("该角色获得40%治疗强度。", 450, 527),
                 ("高傲巨人", 1480, 436), ("上阵该角色占用2团队规模。", 1480, 553),
                 ("敌人难度+5", 1470, 723))
    assert frame.halo_uses_extra_capacity(1)
    assert not frame.halo_uses_extra_capacity(0)
    assert frame.halo_effect(allow_support=True, allowed=(0,))[1] == 0


def test_default_replaces_lower_stars_and_preserves_equipped_and_halo_slots():
    locked_front = slot("front", 0, replace(FILLER, has_halo=True, equipment=0))
    equipped_front = slot("front", 1, replace(FILLER, name="有装备的角色", equipment=1))
    low = slot("front", 2, replace(CORE, stars=1, equipment=0))
    high = slot("bench", 0, replace(CORE, stars=3, equipment=0))
    extra = slot("bench", 1, replace(BAILU, equipment=0))
    current = board(locked_front, equipped_front, low, high, extra, used=3)
    assert policy.default_deployment(current, {high: low}, set()) == (high, low)
    assert policy.default_deployment(current, {high: locked_front}, set()) is None
    assert policy.default_surplus(current, {high: low}) == (extra,)


@pytest.mark.parametrize("mascot_count", (1, 2))
def test_default_replaces_a_character_without_dragging_peppy(monkeypatch, world, mascot_count):
    world.war.default_strategy = True
    count = 6 + mascot_count
    centers = tuple(round(960 + (i - (count - 1) / 2) * 142) for i in range(count))
    mascot_points = tuple((x, ui.BACK_Y) for x in centers[-mascot_count:])
    outgoing = (centers[-mascot_count - 1], ui.BACK_Y)
    incoming, spare = ui.BENCH_POINTS[:2]
    capacity = 2 + mascot_count
    with Image.open("assets/images/screen/currency_wars/s2_peppy.png") as mascot:
        base = CANVAS.copy()
        draw = ImageDraw.Draw(base)
        for x in centers:
            draw.rectangle((x - 60, 598, x + 60, 731), outline=(120, 170, 176), width=2)
        for x, y in mascot_points:
            base.paste(mascot, (x - 39, y - 33))

    def screenshot(weak, strong, used):
        image = base.copy()
        draw = ImageDraw.Draw(image)
        fx, fy = 745, ui.FRONT_Y
        draw.ellipse((fx - 25, fy - 24, fx + 25, fy + 24), fill=(185, 120, 210))
        for (x, y), cost in ((weak, 2), (strong, 3)):
            if cost == 2:
                draw.rectangle((x - 30, y - 24, x, y + 29), fill=(173, 93, 28))
            else:
                draw.ellipse((x - 28, y - 14, x + 29, y + 23), fill=(57, 199, 144))
            shift = 36 if y == ui.BENCH_Y else 44
            draw.rectangle((x + shift - 3, y - 43, x + shift + 3, y - 38), fill="white")
            draw.rectangle((x - 40, y + 51, x + 38, y + 56), fill=tuple(ui.CARD_COST_PALETTE[cost - 1]))
        frame = Frame(image, labels((f"{used}/{capacity}", 960, 260)))
        frame.__dict__.update(page=Page.BOARD, stage="3-4")
        return frame

    before = screenshot(outgoing, incoming, capacity)
    parked = screenshot(spare, incoming, capacity - 1)
    after = screenshot(spare, outgoing, capacity)
    _, team = world.war._read_default_board(before)
    assert team.used == len(team.field) == capacity
    assert tuple(s.point for s in team.field if s.blocked and s.unit is None) == mascot_points

    state = drive(monkeypatch, world, before)
    routes = {before: (outgoing, spare, parked), parked: (incoming, outgoing, after)}

    def drag(start, end, **_):
        source, target, updated = routes[state.frame]
        assert start == pytest.approx((source[0] / 1920, source[1] / 1080))
        assert end == pytest.approx((target[0] / 1920, target[1] / 1080))
        state.frame = updated
        return True

    world.auto.drag_mouse.side_effect = drag
    assert world.war._prepare_default_team(before) is after
    assert world.auto.drag_mouse.call_count == 2
    assert state.clicks == []


def test_default_sells_surplus_but_keeps_a_candidate_for_the_next_level():
    field = slot("front", 0, replace(CORE, stars=2))
    copy = slot("bench", 0, replace(CORE, stars=1, equipment=0))
    possible = slot("bench", 1, replace(BAILU, equipment=0))
    spare = slot("back", 0)
    current = board(field, spare, copy, possible, used=3, capacity=3)
    assert policy.default_surplus(current, {copy: field}) == (copy,)
    assert policy.default_surplus(current, {copy: field}, make_space=True) == (copy, possible)
    assert policy.default_surplus(replace(current, used=10, capacity=10), {copy: field}) == (copy, possible)


def test_default_dual_role_leaves_the_only_front_slot_for_the_front_only_card():
    front = slot("front", 1)
    back = slot("back", 0)
    flex = slot("bench", 0, replace(FILLER, stars=3))
    fixed = slot("bench", 1, CORE)
    current = board(slot("front", 0, FILLER), front, back, flex, fixed, used=1)
    assert policy.default_deployment(current, {}, set()) == (flex, back)


def test_default_preparation_uses_only_visual_deployment_and_keeps_playing_on_sale_failure(monkeypatch, world):
    world.war.default_strategy = True
    first = slot("front", 0, FILLER)
    target = slot("back", 0)
    candidate = slot("bench", 0, replace(BAILU, stars=2, equipment=0))
    surplus = slot("bench", 1, replace(FILLER, equipment=0))
    current = board(first, target, candidate, surplus, used=1, stage="1-3")
    prepared = apply_deployment(current, (candidate, target))
    before = page(Page.BOARD, stage=current.stage)
    after = page(Page.BOARD, ("出战", 1818, 748), stage=current.stage)
    fighting = battle(True)
    for f, b in ((before, current), (after, prepared)):
        monkeypatch.setattr(f, "slots", lambda b=b: b.slots)
        monkeypatch.setattr(f, "deployed_copy", lambda s, _: first if s is surplus else None)
    monkeypatch.setattr(world.war, "_settle_board", lambda f: f)
    monkeypatch.setattr(world.war, "_gather", lambda f: f)
    monkeypatch.setattr(world.war, "_read_default_board", lambda f, **_: (f, current if f == before else prepared))
    shop = Mock(side_effect=AssertionError("默认策略不应访问商店"))
    detail_scan = Mock(side_effect=AssertionError("部署不应逐张读取详情"))
    monkeypatch.setattr(world.war, "_shop", shop)
    monkeypatch.setattr(world.war, "_read_board", detail_scan)
    sale = Mock(side_effect=task.CurrencyWarsReceiptTimeout("出售未回执"))
    monkeypatch.setattr(world.war, "_sell_reserve", sale)
    state = drive(monkeypatch, world, before, lambda s, _: setattr(s, "frame", fighting))

    def moved(f, b, source, destination, *, named=True):
        assert f is before and b is current and (source, destination) == (candidate, target)
        # 默认阵容按卡位命名，移动时不能与姓名缓存比对。
        assert not named
        state.frame = world.war.frame = after
        return after

    monkeypatch.setattr(world.war, "_move", moved)
    monkeypatch.setattr(after, "inventory_items", lambda: ())
    assert world.war._prepare(before) is fighting
    sale.assert_called_once_with(after, surplus)
    assert state.clicks == [(Page.BOARD, (1818, 748))]
    assert state.keys == []
    shop.assert_not_called()
    detail_scan.assert_not_called()


def test_default_does_not_try_the_other_row_after_the_game_rejects_a_duplicate(monkeypatch, world):
    world.war.default_strategy = True
    front, back = slot("front", 1), slot("back", 0)
    fielded = slot("front", 0, FILLER)
    duplicate = slot("bench", 0, replace(FILLER, name="备战席第 1 格角色", stars=3))
    candidate = slot("bench", 1, CORE)
    current = board(fielded, front, back, duplicate, candidate, used=1)
    before = page(Page.BOARD, stage=current.stage, capacity=(1, 3))
    refused = page(Page.BOARD, ("无法上阵同名角色", 960, 328), stage=current.stage, capacity=(1, 3))
    confirmed = page(Page.CHOICE)
    for f in (before, refused):
        monkeypatch.setattr(f, "slot_occupied", lambda p: p in {s.point for s in current.slots if s.occupied})
        monkeypatch.setattr(f, "deployed_copy", lambda *_: None)
        monkeypatch.setattr(f, "card_stars", lambda s, **kw: s.unit.stars if s.unit else None)
    state = drive(monkeypatch, world, before)
    world.auto.drag_mouse.side_effect = lambda *args, **kwargs: setattr(
        state, "frame", refused if state.frame is before else confirmed) or True
    monkeypatch.setattr(world.war, "_read_default_board", lambda f, **kw: (f, current))
    assert world.war._prepare_default_team(before) is confirmed
    assert world.auto.drag_mouse.call_count == 2
    assert (current.stage, duplicate.point, "front") in world.war.default_deployment_skips
    assert (current.stage, duplicate.point, "back") in world.war.default_deployment_skips


def test_default_deployment_keeps_a_skip_when_input_was_sent_without_receipt(monkeypatch, world):
    world.war.default_strategy = True
    source, target = slot("bench", 0, CORE), slot("front", 0)
    team = board(source, target, stage="1-1", used=0)
    before = page(Page.BOARD, stage=team.stage, capacity=(team.used, team.capacity))
    monkeypatch.setattr(before, "slot_occupied", lambda p: p == source.point)
    monkeypatch.setattr(before, "deployed_copy", lambda *_: None)
    monkeypatch.setattr(before, "card_stars", lambda s, **_: s.unit.stars if s.unit else None)
    monkeypatch.setattr(world.war, "_read_default_board", lambda f, **_: (f, team))
    drive(monkeypatch, world, before)
    world.auto.drag_mouse.return_value = True

    assert world.war._prepare_default_team(before, deploy_only=True) is before
    attempts = world.auto.drag_mouse.call_count
    assert attempts > 0
    assert (team.stage, source.point, target.zone) in world.war.default_deployment_skips
    assert world.war._prepare_default_team(before, deploy_only=True) is before
    assert world.auto.drag_mouse.call_count == attempts


@pytest.mark.parametrize("restore_sent", (False, True))
def test_default_replacement_rechecks_a_parked_front_after_zero_input_restore(monkeypatch, world, restore_sent):
    world.war.default_strategy = True
    outgoing = slot("front", 0, replace(FILLER, back=False, equipment=0))
    incoming = slot("bench", 0, replace(CORE, cost=4))
    spare = slot("bench", 1)
    original = board(outgoing, incoming, spare, stage="1-1", used=1, capacity=1)
    parked = apply_deployment(original, (outgoing, spare))
    stored = replace(spare, occupied=True, unit=outgoing.unit)
    restorable = replace(parked, slots=(replace(outgoing, occupied=False, unit=None),
                                        replace(incoming, blocked=True), stored))
    restored = apply_deployment(restorable, (stored, restorable.slots[0]))

    def frame_of(team, *, unstable=False):
        image = CANVAS.copy()
        visible = next(s for s in team.slots if s.unit is outgoing.unit)
        x, y = visible.point
        draw = ImageDraw.Draw(image)
        draw.rectangle((x - 20, y - 25, x + 12, y + 18), fill=(190, 155, 50))
        draw.rectangle((x - 15, y - 10, x + 21, y + 8), fill=(65, 179, 147))
        frame = Frame(image, ())
        frame.__dict__.update(page=Page.BOARD, stage=team.stage, capacity=(team.used, team.capacity), gold=0)
        monkeypatch.setattr(frame, "slot_occupied", lambda p: any(s.point == p and s.occupied for s in team.slots))
        monkeypatch.setattr(frame, "deployed_copy", lambda *_: None)
        monkeypatch.setattr(frame, "card_equipment", lambda s: s.unit.equipment)
        monkeypatch.setattr(frame, "card_stars", lambda s, **_: (
            4 if unstable and (s.point == incoming.point or not restore_sent) else s.unit.stars))
        return frame

    before = frame_of(original)
    middle = frame_of(parked, unstable=True)
    ready, after = frame_of(restorable), frame_of(restored)
    teams = {before: original, middle: parked, ready: restorable, after: restored}
    monkeypatch.setattr(world.war, "_read_default_board", lambda f, **_: (f, teams[f]))
    state = drive(monkeypatch, world, before)
    drags = []

    def drag(start, end, **_):
        src = tuple(round(value * scale) for value, scale in zip(start, (1920, 1080)))
        dst = tuple(round(value * scale) for value, scale in zip(end, (1920, 1080)))
        drags.append((src, dst))
        if state.frame is before:
            assert (src, dst) == (outgoing.point, spare.point)
            state.frame = middle
        else:
            assert (src, dst) == (spare.point, outgoing.point)
            if state.frame is ready:
                state.frame = after
            else:
                assert restore_sent and state.frame is middle
        return True

    world.auto.drag_mouse.side_effect = drag
    assert world.war._prepare_default_team(before) is middle
    assert drags[0] == (outgoing.point, spare.point)
    assert ((original.stage, spare.point, "front") in world.war.default_deployment_skips) is restore_sent

    state.frame = ready
    attempts = len(drags)
    if restore_sent:
        assert world.war._prepare_default_team(world.war._observe(), deploy_only=True) is ready
        assert len(drags) == attempts
    else:
        assert attempts == 1
        assert world.war._prepare_default_team(world.war._observe(), deploy_only=True) is after
        assert drags == [(outgoing.point, spare.point), (spare.point, outgoing.point)]


def test_default_equipment_visits_each_card_once_by_cost_then_stars_across_both_rows(monkeypatch, world):
    world.war.default_strategy = True
    low = slot("front", 0, FILLER)
    high = slot("back", 0, replace(BAILU, cost=4, stars=1))
    mid = slot("front", 1, replace(CORE, cost=3, stars=3))
    reserve = slot("bench", 0, replace(CER, stars=4))
    full = slot("back", 1, replace(CER, stars=4, equipment=3))
    current = board(low, mid, high, reserve, full)
    screen = page(Page.BOARD, stage=current.stage)
    monkeypatch.setattr(screen, "inventory_items", lambda: ((1844, 240),))
    equip = Mock(return_value=(screen, True))
    monkeypatch.setattr(world.war, "_equip_once", equip)
    assert world.war._equip_board(screen, current) is screen
    assert world.war._equip_board(screen, current) is screen
    assert [call.args[1] for call in equip.call_args_list] == [high, mid, low]


def test_default_opening_waits_for_free_supplies_and_never_clicks_fight_with_an_empty_front(monkeypatch, world):
    world.war.default_strategy = True
    stage = "1-1"
    message = Frame(CANVAS, labels(("提示", 960, 410), ("前台区域无角色，无法出战", 960, 525), ("确认", 977, 672)))
    initial = page(Page.BOARD, ("出战", 1818, 748), stage=stage, capacity=(0, 3), gold=3)
    orbs = page(Page.BOARD, stage=stage, capacity=(0, 3), gold=3)
    collected = page(Page.BOARD, stage=stage, capacity=(0, 3), gold=6)
    monkeypatch.setattr(initial, "opening_orbs", lambda: ())
    monkeypatch.setattr(orbs, "opening_orbs", lambda: ((1430, 481),))
    for f in (initial, orbs, collected):
        monkeypatch.setattr(f, "reward_orbs", lambda: ())
        monkeypatch.setattr(f, "bench_slots", lambda: (slot("bench", 0),))
    assert message.page == Page.EMPTY_FRONT
    state = drive(monkeypatch, world, message, lambda s, _: setattr(s, "frame", initial))
    assert world.war._play_step(message) is initial
    with pytest.raises(task.CurrencyWarsActionUnready, match="前台角色"):
        world.war._finish_preparation(initial, board(stage=stage, used=0))

    def collect(f, find, receipt, *args, **kwargs):
        assert f is orbs and find(f) == ((1344, 481), (1518, 481))
        assert receipt(collected)
        return collected

    state.frame = orbs
    monkeypatch.setattr(world.war, "_drag_to", collect)
    assert world.war._gather(initial) is collected
    assert state.clicks == [(Page.EMPTY_FRONT, (977, 672))]


@pytest.mark.parametrize("outcome", (
    "gift", "purchase", "full_back", "full_bench", "free_refresh", "receipt_lost", "unavailable", "stopped", "timeout",
))
def test_default_opening_fills_the_empty_front_before_fighting(monkeypatch, world, outcome):
    world.cfg.currencywars_strategy = policy.DEFAULT_STRATEGY
    world.cfg.currencywars_time_limit = 1
    stage = "1-1"
    shop_button, refresh_button, fight_button = (1624, 983), (1621, 487), (1818, 751)
    front_offer = policy.Offer(FILLER.name, 1, (739, 194), 1, front=True, back=True)
    expensive_front = policy.Offer("花火", 2, (1008, 194), 2, front=True)
    rear_offer = policy.Offer(BAILU.name, 1, (470, 194), 0, back=True)
    starter_cards = {"gift": replace(FILLER, cost=1), "full_bench": policy.Unit("娜塔莎", False, True, 1)}
    starter = slot("bench", 2, starter_cards.get(outcome))
    full_back = outcome == "full_back"
    back_cards = (CER, BAILU) if full_back else (None, None)
    bench_cards = (None, None) if full_back else (CER, BAILU)
    opening = board(slot("front", 0), *(slot("back", i, card) for i, card in enumerate(back_cards)), slot("back", 2),
                    *(slot("bench", i, card) for i, card in enumerate(bench_cards)), starter,
                    stage=stage, used=2 if full_back else 0, capacity=2 if full_back else 3, gold=3)
    boards = {}

    def board_frame(team):
        frame = page(Page.BOARD, ("商店", *shop_button), ("出战", *fight_button),
                     stage=stage, capacity=(team.used, team.capacity), gold=team.gold)
        boards[frame] = team
        frame.slots = lambda: team.slots
        frame.field_slots = lambda: tuple(s for s in team.slots if s.zone != "bench")
        frame.bench_slots = lambda: tuple(s for s in team.slots if s.zone == "bench")
        frame.slot_occupied = lambda point: any(s.point == point and s.occupied for s in team.slots)
        frame.card_stars = lambda s, **_: s.unit.stars
        frame.card_cost = lambda s: s.unit.cost
        frame.card_equipment = lambda _: 0
        frame.card_role = lambda s: ((False, False) if outcome == "gift" and s == starter
                                     else (s.unit.front, s.unit.back))
        frame.deployed_copy = lambda *_: None
        frame.reward_orbs = frame.opening_orbs = frame.inventory_items = lambda: ()
        return frame

    initial = board_frame(opening)
    # 满备战席先部署一名后台，购买落在刚腾出的备战位。
    shop_team = (apply_deployment(opening, (slot("bench", 0, CER), slot("back", 0)))
                 if outcome == "full_bench" else opening)
    purchase_slot = slot("bench", 0 if outcome == "full_bench" else 2)
    recruited = board_frame(replace(shop_team, gold=2, slots=tuple(
        replace(s, unit=replace(FILLER, cost=1), occupied=True) if s == purchase_slot else s for s in shop_team.slots
    )))
    available = page(Page.SHOP, ("收起", *shop_button), ("刷新", *refresh_button),
                     stage=stage, gold=3, offers=(rear_offer, front_offer, expensive_front), shop_refresh_price=2)
    sold = page(Page.SHOP, ("收起", *shop_button), stage=stage, gold=2, offers=(rear_offer, expensive_front))
    sold.shop_changed = lambda old, column: old is available and column == front_offer.column
    starting_shop = available
    if outcome in ("free_refresh", "unavailable"):
        free = outcome == "free_refresh"
        starting_shop = page(Page.SHOP, ("收起", *shop_button), ("免费刷新" if free else "刷新", *refresh_button),
                             stage=stage, gold=3, offers=(rear_offer, replace(expensive_front, cost=4)),
                             shop_refresh_price=0 if free else 2)
        available.shop_catalog_changed = lambda old: old is starting_shop
    won = page(Page.MATCH_RESULT, ("对局胜利", 960, 260), ("返回货币战争", 960, 899))
    lobby = home()
    moves = []

    def click(state, point):
        current = state.frame
        if current in boards and point == fight_button:
            assert boards[current].front_count == 1
            state.frame = won
            return
        if current in boards and point == shop_button:
            assert boards[current] == shop_team
            if outcome == "stopped":
                task.pause_ctl.checkpoint.side_effect = RunStopRequested()
            elif outcome == "timeout":
                world.now[0] = world.war.deadline
            state.frame = starting_shop
            return
        state.frame = {
            (starting_shop, refresh_button): available,
            (available, front_offer.point): available if outcome == "receipt_lost" else sold,
            (available if outcome == "receipt_lost" else sold, shop_button): recruited,
            (starting_shop, shop_button): initial if outcome == "unavailable" else recruited,
            (won, (960, 899)): lobby,
        }[current, point]

    state = drive(monkeypatch, world, initial, click)

    def deploy(start, end, **_):
        team = boards[state.frame]
        source = next(s for s in team.slots if s.point == (round(start[0] * 1920), round(start[1] * 1080)))
        target = next(s for s in team.slots if s.point == (round(end[0] * 1920), round(end[1] * 1080)))
        moves.append((source.unit.name, target.zone))
        state.frame = board_frame(apply_deployment(team, (source, target)))
        return True

    world.auto.drag_mouse.side_effect = deploy
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))

    if outcome == "unavailable":
        with pytest.raises(task.CurrencyWarsUnavailable, match="重开未完成.*按 ESC 后未确认"):
            world.war.start(resume=True)
        assert state.frame is initial and not moves
        assert state.clicks == [(Page.BOARD, shop_button), (Page.SHOP, shop_button)]
        assert state.keys == [(Page.BOARD, "esc")] * 2
    elif outcome in ("stopped", "timeout"):
        error = RunStopRequested if outcome == "stopped" else task.CurrencyWarsBudgetExceeded
        with pytest.raises(error):
            world.war.start(resume=True)
        assert state.frame is starting_shop and not moves
        assert state.clicks == [(Page.BOARD, shop_button)]
    else:
        assert world.war.start(resume=True)
        assert state.frame is lobby
        expected = {
            "full_back": [(CER.name, "bench"), (FILLER.name, "front")],
            "full_bench": [(CER.name, "back"), (FILLER.name, "front"), (BAILU.name, "back")],
        }.get(outcome, [(FILLER.name, "front"), (CER.name, "back"), (BAILU.name, "back")])
        assert moves == expected
        shop_clicks = [(Page.BOARD, shop_button)]
        if outcome == "free_refresh":
            shop_clicks.append((Page.SHOP, refresh_button))
        shop_clicks.extend(((Page.SHOP, front_offer.point), (Page.SHOP, shop_button)))
        assert state.clicks == [
            *([] if outcome == "gift" else shop_clicks),
            (Page.BOARD, fight_button), (Page.MATCH_RESULT, (960, 899)),
        ]


@pytest.mark.parametrize("outcome", (
    "single", "weekly", "loop",
    "late_front", "later_board", "abandon_returns_original", "abandon_returns_saved",
    "limit", "no_settlement", "stopped", "timeout",
))
def test_default_opening_restart_settles_once_and_plays_the_new_match(monkeypatch, world, outcome):
    world.cfg.currencywars_strategy = policy.DEFAULT_STRATEGY
    world.cfg.currencywars_unfinished_match = "resume"
    world.cfg.currencywars_time_limit = 1
    stage = "1-1"
    shop_button, fight_button = (1624, 983), (1818, 751)

    def preparation(team):
        frame = page(Page.BOARD, ("商店", *shop_button), ("出战", *fight_button),
                     stage=team.stage, capacity=(team.used, team.capacity), gold=team.gold)
        frame.slots = lambda: team.slots
        frame.field_slots = lambda: tuple(s for s in team.slots if s.zone != "bench")
        frame.deployed_copy = lambda *_: None
        return frame

    empty_team = board(slot("front", 0), slot("back", 0), slot("bench", 0, BAILU), slot("bench", 1),
                       stage="2-3" if outcome == "later_board" else stage, used=0, gold=3)
    ready_team = board(slot("front", 0, CORE), slot("back", 0), slot("bench", 0), slot("bench", 1),
                       stage=stage, used=1, gold=3)
    blocked, ready = preparation(empty_team), preparation(ready_team)
    shop = page(Page.SHOP, ("收起", *shop_button), ("刷新", 1621, 487), stage=stage, gold=3,
                shop_refresh_price=2, offers=(policy.Offer(BAILU.name, 2, (470, 194), 0, back=True),))
    lobby = home()
    menu = mode(("进入标准博弈", 1692, 961))
    ranks = rank()
    saved = mode(("继续进度", 1692, 961), ("结束并结算", 1397, 961), ("标准博弈", 646, 156))
    prompt = active_match_exit_dialog()
    abandon_point = (770, 743)
    abandoned = page(Page.MATCH_RESULT, ("对局失败", 960, 233), ("返回货币战争", 960, 899))
    won = page(Page.MATCH_RESULT, ("对局胜利", 960, 233), ("返回货币战争", 960, 899))
    state = SimpleNamespace(frame=lobby, clicks=[], keys=[], launches=[])
    routes = {
        (lobby, (1600, 972)): menu, (menu, (1692, 961)): ranks, (saved, (1692, 961)): ready,
        (blocked, shop_button): shop, (shop, shop_button): blocked,
        (prompt, abandon_point): (prompt if outcome == "no_settlement"
                                  else ready if outcome == "abandon_returns_original"
                                  else lobby if outcome == "abandon_returns_saved" else abandoned),
        (abandoned, (960, 899)): lobby,
        (ready, fight_button): won, (won, (960, 899)): lobby,
    }

    def click(point, *, press_duration):
        state.clicks.append((state.frame, point))
        if state.frame is ranks and point == (1680, 965):
            state.launches.append(world.war.deadline)
            state.frame = blocked if len(state.launches) == 1 or outcome == "limit" else ready
        elif outcome == "abandon_returns_saved" and state.frame is lobby and state.launches:
            assert point == (1600, 972)
            state.frame = saved
        else:
            state.frame = routes[state.frame, point]
        return True

    def press(key):
        assert key == "esc"
        state.keys.append(key)
        assert state.frame is blocked
        state.frame = prompt
        if outcome == "stopped":
            task.pause_ctl.checkpoint.side_effect = RunStopRequested()
        elif outcome == "timeout":
            world.now[0] = world.war.deadline
        return True

    monkeypatch.setattr(world.war, "_capture", lambda: state.frame)
    if outcome == "late_front":
        restart_match = world.war._restart_match

        def restart_with_new_front(frame, **kwargs):
            state.frame = ready
            return restart_match(frame, **kwargs)

        monkeypatch.setattr(world.war, "_restart_match", restart_with_new_front)
    monkeypatch.setattr(world.war, "_read_default_board",
                        lambda f, **_: (f, empty_team if f is blocked else ready_team))
    monkeypatch.setattr(world.war, "_gather", lambda f: f)
    monkeypatch.setattr(world.war, "_equip", lambda f, _: f)
    if outcome == "later_board":
        prepare = world.war._prepare

        def stuck_preparation(f):
            if f is blocked:
                raise task.CurrencyWarsActionUnready("无法完成备战")
            return prepare(f)

        monkeypatch.setattr(world.war, "_prepare", stuck_preparation)
    on_result = Mock()
    monkeypatch.setattr(world.war, "_on_match_result", on_result)
    reward_checks = []

    def rewards(f):
        reward_checks.append(world.war.result)
        return f, (18000 if world.war.result is True else 0, 18000), False

    monkeypatch.setattr(world.war, "_check_weekly_reward", rewards)
    world.auto.click_element_with_pos.side_effect = click
    world.auto.press_key.side_effect = press

    if outcome == "limit":
        with pytest.raises(task.CurrencyWarsUnavailable, match="已达开局重开上限"):
            world.war.start()
        assert state.frame is menu
        assert state.keys == ["esc"] * (task.MAX_MATCH_RESTARTS + 1)
        assert state.clicks.count((prompt, abandon_point)) == task.MAX_MATCH_RESTARTS + 1
        assert state.launches == [60] * (task.MAX_MATCH_RESTARTS + 1)
        assert not reward_checks
        on_result.assert_not_called()
    elif outcome in ("no_settlement", "stopped", "timeout"):
        error = {"no_settlement": task.CurrencyWarsUnavailable, "stopped": RunStopRequested,
                 "timeout": task.CurrencyWarsBudgetExceeded}[outcome]
        with pytest.raises(error):
            world.war.start()
        assert state.frame is prompt and state.keys == ["esc"] and state.launches == [60]
        assert state.clicks.count((prompt, abandon_point)) == (1 if outcome == "no_settlement" else 0)
        assert not reward_checks
        on_result.assert_not_called()
    else:
        assert world.war.start(weekly=outcome == "weekly", loop=outcome == "loop")
        restarted = outcome not in ("late_front", "abandon_returns_original", "abandon_returns_saved")
        escape_count = int(outcome != "late_front")
        assert state.frame is lobby
        assert state.keys == ["esc"] * escape_count and state.launches == [60] * (1 + restarted)
        assert state.clicks.count((prompt, abandon_point)) == int(outcome != "late_front")
        assert state.clicks.count((ready, fight_button)) == 1
        assert reward_checks == ([None, True] if outcome == "weekly" else [True])
        assert world.war._loop_matches == (1 if outcome == "loop" else 0)
        on_result.assert_called_once_with(won)
    assert (blocked, fight_button) not in state.clicks


def test_default_sale_uses_slot_receipt_without_role_name_or_exact_refund(monkeypatch, world):
    world.war.default_strategy = True
    tile = slot("bench", 1, FILLER)
    stage = "1-4"
    before = page(Page.BOARD, stage=stage, gold=None)
    detail = page(Page.DETAIL, ("出售", 1770, 917), stage=stage)
    after = page(Page.BOARD, stage=stage, gold=42)
    monkeypatch.setattr(before, "slot_occupied", lambda point: point == tile.point)
    state = drive(monkeypatch, world, before, lambda s, p: setattr(s, "frame", detail if p == tile.point else after))
    assert world.war._sell_reserve(before, tile) == (after, True)
    assert state.clicks == [(Page.BOARD, tile.point), (Page.DETAIL, (1770, 917))]
    assert world.war.preparation_progress == 1


def test_default_exp_batches_do_not_repeat_after_an_intervening_choice(monkeypatch, world):
    world.war.default_strategy = True
    first = slot("front", 0, FILLER)
    reserve = slot("bench", 1, BAILU)
    current = board(first, reserve, slot("back", 0), used=3, gold=24, exp=(0, 16))
    before = page(Page.BOARD, ("购买经验", 298, 863), stage=current.stage, gold=24, level=5,
                  capacity=(3, 3), experience_cost=4, experience=(0, 16))
    choice = page(Page.GARDEN, stage=current.stage)
    monkeypatch.setattr(before, "deployed_copy", lambda *_: None)
    monkeypatch.setattr(world.war, "_read_default_board", lambda f, **kw: (f, current))
    state = drive(monkeypatch, world, before)

    def press(key):
        state.keys.append(key)
        state.frame = choice

    world.auto.press_key.side_effect = press
    assert world.war._prepare_default_team(before) is choice
    state.frame = before
    assert world.war._prepare_default_team(before) is before
    assert state.keys == ["f"] * policy.experience_purchases(current.exp)


def test_default_closes_shop_opened_by_the_game_without_waiting_for_fight(monkeypatch, world):
    world.war.default_strategy = True
    stage = "1-4"
    ready = page(Page.BOARD, ("出战", 1818, 748), stage=stage)
    opened = page(Page.SHOP, ("收起", 1624, 980), stage=stage)
    fielded = slot("front", 0, CORE)
    monkeypatch.setattr(ready, "slots", lambda: (fielded,))
    state = drive(monkeypatch, world, ready, after_capture=lambda s: setattr(s, "frame", opened))
    assert world.war._finish_preparation(ready, board(fielded, stage=stage)) is opened
    assert state.clicks == []


def test_shop_skips_paid_refresh_while_an_upgrade_can_add_a_legal_employee(monkeypatch, world):
    frame = page(Page.BOARD, stage="1-2")
    shop = page(Page.SHOP, ("刷新", 1620, 486), ("2", 1617, 535), stage="1-2", gold=12, offers=())
    current = board(slot("front", 0, replace(CORE, stars=1)), slot("back", 0, CER), slot("back", 1),
                    slot("bench", 0, policy.Unit("后台候补", False, True)), slot("bench", 1), slot("bench", 2),
                    stage="1-2", used=2, capacity=2, level=6, gold=12, exp=(32, 36))
    state = drive(monkeypatch, world, shop)
    monkeypatch.setattr(world.war, "_open_shop", lambda _: shop)
    monkeypatch.setattr(world.war, "_close_shop", lambda _: frame)
    assert world.war._shop(frame, current, 0, experience_price=4) == (frame, 0, False)
    assert not state.clicks


def test_low_cost_card_uses_stable_name_and_fee_bar_without_coin_icon_ocr(monkeypatch):
    image = CANVAS.copy()
    draw = ImageDraw.Draw(image)
    x = 367 + 269 * 2
    draw.rectangle((x + 152, 293, x + 169, 316), fill=(128, 131, 146))
    f = Frame(image, labels(("那刻夏", x + 55, 310)))
    fallback = Mock(return_value="4")
    monkeypatch.setattr(f, "read_local", fallback)
    assert [(offer.name, offer.cost) for offer in f.offers] == [("那刻夏", 1)]
    fallback.assert_not_called()


@pytest.mark.parametrize("legacy", policy.LEGACY_STRATEGIES)
def test_old_strategy_is_saved_and_used_on_start(monkeypatch, tmp_path, world, legacy):
    from module.config.config import Config

    path = tmp_path / "config.yaml"
    path.write_text(f"currencywars_strategy: {legacy}\ncurrencywars_rank_difficulty: highest\n",
                    encoding="utf-8")
    config = Config.__new__(Config)
    Config.__init__(config, "assets/config/version.txt", "assets/config/config.example.yaml", str(path))
    monkeypatch.setattr(task, "cfg", config)
    lobby = home()
    entered = page(Page.BOARD, stage="1-1")
    monkeypatch.setattr(world.war, "_observe", lambda: lobby)
    monkeypatch.setattr(world.war, "get_reward", lambda f: (f, (18000, 18000), False))

    def launch(frame, resume):
        assert frame is lobby and not resume
        assert f"currencywars_strategy: {policy.HIGH_ANAXA}" in path.read_text(encoding="utf-8")
        assert config.currencywars_rank_difficulty == "highest"
        return entered

    def play(frame):
        assert frame is entered
        assert world.war.lineup is policy.LINEUPS[policy.HIGH_ANAXA]
        world.war.result = True
        return lobby

    monkeypatch.setattr(world.war, "_launch", launch)
    monkeypatch.setattr(world.war, "_play", play)
    assert world.war.start() is True


def test_legacy_migration_write_failure_still_uses_high_anaxa(monkeypatch, world):
    world.cfg.currencywars_strategy = "aglaea"
    world.cfg.set_value = Mock(side_effect=PermissionError("写入失败"))
    lobby = home()
    monkeypatch.setattr(world.war, "_observe", lambda: lobby)
    monkeypatch.setattr(world.war, "_launch", lambda f, resume: f)
    monkeypatch.setattr(world.war, "_play", lambda f: setattr(world.war, "result", True) or f)
    monkeypatch.setattr(world.war, "get_reward", lambda f: (f, (18000, 18000), False))

    assert world.war.start() is True
    assert world.war.lineup is policy.LINEUPS[policy.HIGH_ANAXA]
    world.cfg.set_value.assert_called_once_with("currencywars_strategy", policy.HIGH_ANAXA)
    assert world.cfg.currencywars_strategy == "aglaea"


def test_unknown_strategy_never_reads_or_changes_game_and_keeps_stored_value(world):
    world.cfg.currencywars_strategy = "unknown"
    with pytest.raises(task.CurrencyWarsError, match="策略"):
        world.war.start()
    assert world.cfg.currencywars_strategy == "unknown"
    assert world.auto.mock_calls == []
    assert policy.resolve_strategy("default") == policy.DEFAULT_STRATEGY


def home():
    return page(Page.HOME, ("开始货币战争", 1600, 972), ("积分", 381, 961))


def mode(*extra):
    return page(Page.MODES, ("标准博弈", 160, 224), ("超频博弈", 160, 420), *extra)


def rank():
    return page(Page.RANK, ("标准博弈", 154, 884), ("1", 545, 963), ("开始对局", 1680, 965))


def battle(auto_on):
    return page(Page.BATTLE, auto_off=not auto_on)


@pytest.mark.parametrize(("start_screen", "screens", "keys", "entries", "succeeds"), [
    pytest.param("apocalyptic", ("currency_wars_homepage",), ["esc", "esc"], 1, True, id="from-apocalyptic"),
    pytest.param("main", ("popup", "apocalyptic", "currency_wars_homepage"),
                 ["esc", "f", "esc", "esc", "esc"], 2, True, id="recover-to-apocalyptic"),
    ("main", ("currency_wars_homepage",), ["esc"], 1, True),
    ("main", ("interaction",), ["esc", "f"], 1, True),
    ("main", ("homepage_ocr",), ["esc", "f"], 1, True),
    ("main", ("popup", "currency_wars_homepage"), ["esc", "f", "esc"], 1, True),
    ("main", ("popup", "guide5"), ["esc", "f", "esc"], 2, True),
    ("main", ("popup", "popup", "currency_wars_homepage"), ["esc", "f", "esc", "esc"], 1, True),
    ("main", ("popup", "popup", "popup", "guide5"), ["esc", "f", "esc", "esc", "esc"], 2, True),
    ("main", ("popup", "reward_limit", "currency_wars_homepage"), ["esc", "f", "esc", "esc"], 1, True),
    ("main", ("popup", "guide5", "popup", "guide5", "popup", "currency_wars_homepage"),
     ["esc", "f", "esc", "f", "esc", "f", "esc"], 3, True),
    ("main", ("popup",), ["esc", "f", "esc", "esc", "esc"], 1, False),
    ("main", ("popup", "battle"), ["esc", "f", "esc"], 1, False),
    ("main", ("battle",), ["esc", "f"], 1, False),
    ("main", ("main",), ["esc"], 0, False),
])
def test_homepage_navigation_and_entry_recovery(monkeypatch, world, start_screen, screens, keys, entries, succeeds):
    target = "currency_wars_homepage"
    destinations = iter(screens)
    current_screen = start_screen
    attempted_entries = 0
    sent_keys = []
    unknown = page(Page.UNKNOWN)
    lobby = home()
    frames = {target: lobby, "homepage_ocr": lobby, "battle": battle(auto_on=True),
              "reward_limit": page(Page.REWARD_LIMIT)}

    def press_key(key):
        nonlocal current_screen
        sent_keys.append(key)
        if current_screen == "apocalyptic" and key == "esc":
            current_screen = "main"
        elif current_screen == "main" and key == "esc" and screens[0] != "main":
            current_screen = "menu"
        elif current_screen == "interaction" and key == "f":
            current_screen = target
        elif current_screen in ("popup", "reward_limit") and key == "esc":
            current_screen = next(destinations, current_screen)

    def click_element(label, *_args, **_kwargs):
        nonlocal current_screen, attempted_entries
        if current_screen == "menu" and label.endswith("/enter_guide5.png"):
            current_screen = "guide5"
        elif current_screen == "guide5" and label == "前往参与":
            attempted_entries += 1
            current_screen = next(destinations, target)
        return True

    def find_element(image_path, *_args, **_kwargs):
        definition = navigation.screen_map.get(current_screen)
        return definition is not None and definition["image_path"] == image_path

    def get_current_screen(*, autotry, **_kwargs):
        assert autotry is False
        return current_screen in navigation.screen_map and navigation.check_screen(current_screen)

    navigation = object.__new__(Screen)
    navigation.__init__(config_path="assets/config/screens.json", logger=Mock())
    monkeypatch.setattr(navigation, "get_current_screen", get_current_screen)
    monkeypatch.setitem(Screen.perform_operations.__globals__, "auto", world.auto)
    monkeypatch.setitem(Screen.perform_operations.__globals__, "time", task.time)
    monkeypatch.setattr(task, "screen", navigation)
    monkeypatch.setattr(world.war, "_observe", lambda: frames.get(current_screen, unknown))
    world.auto.find_element.side_effect = find_element
    world.auto.press_key.side_effect = press_key
    world.auto.click_element.side_effect = click_element

    if succeeds:
        launch = Mock(return_value=page(Page.BOARD))

        def finish_match(_):
            world.war.result = True
            return lobby

        monkeypatch.setattr(world.war, "_launch", launch)
        monkeypatch.setattr(world.war, "_play_with_restarts", finish_match)
        monkeypatch.setattr(world.war, "_check_weekly_reward", lambda frame: (frame, (18000, 18000), False))
        assert world.war.start()
        launch.assert_called_once_with(lobby, False)
        assert navigation.current_screen == target
        navigation.logger.error.assert_not_called()
    else:
        with pytest.raises(RuntimeError, match="无法切换到指定游戏界面"):
            world.war._homepage(unknown)
    assert sent_keys == keys
    assert attempted_entries == entries


def test_mode_menu_rejects_conflicting_saved_match_titles():
    saved = mode(("超频博弈", 646, 156), ("标准博弈", 806, 156), ("继续进度", 1692, 961))
    assert saved.unfinished_match
    assert saved.menu_mode is None


@pytest.mark.parametrize("cancel_visible", (False, True))
def test_native_network_prompt_does_not_trigger_input_over_the_shop(monkeypatch, world, cancel_visible):
    shop_labels = labels(("备战阶段", 282, 72), ("1-4", 282, 109), ("收起", 1624, 982), ("刷新", 1630, 488))
    shop = Frame(CANVAS, shop_labels)
    image = CANVAS.copy()
    ImageDraw.Draw(image).rectangle((1090, 649, 1278, 693), fill="white")
    prompt_labels = labels(
        ("提示", 959, 412), ("失去网络连接，战斗结果同步失败，是否尝试重新连接？", 956, 526),
        ("确认", 1188, 672),
    )
    if cancel_visible:
        prompt_labels += labels(("取消", 770, 671))
    prompt = Frame(image, shop_labels + prompt_labels)
    assert shop.page == Page.SHOP
    ready = page(Page.BOARD, stage="1-4")
    won = page(Page.MATCH_RESULT, ("对局胜利", 960, 233), ("返回货币战争", 960, 899))
    lobby = home()
    state = SimpleNamespace(frame=shop, captured=shop, shop_reads=0, clicks=[])

    def capture():
        if state.frame is shop:
            state.shop_reads += 1
        state.captured = prompt if state.frame is shop and 2 <= state.shop_reads <= 7 else state.frame
        return state.captured

    def click(point, *, press_duration):
        state.clicks.append((state.captured, point))
        if state.captured is shop and point == (1624, 982):
            state.frame = ready
        elif state.captured is won and point == (960, 899):
            state.frame = lobby
        return True

    def fight(frame):
        assert frame is ready
        state.frame = won
        return world.war._observe()

    monkeypatch.setattr(world.war, "_capture", capture)
    monkeypatch.setattr(world.war, "_prepare", fight)
    monkeypatch.setattr(world.war, "get_reward", lambda f: (f, (18000, 18000), False))
    world.auto.click_element_with_pos.side_effect = click

    assert world.war.start(resume=True)
    assert state.clicks == [(shop, (1624, 982)), (won, (960, 899))]
    world.auto.press_key.assert_not_called()


def end_match_dialog():
    image = CANVAS.copy()
    ImageDraw.Draw(image).rounded_rectangle((779, 715, 1140, 772), radius=28, fill=(224, 224, 224))
    return Frame(image, labels(
        ("提示", 778, 341), ("选择放弃并结算将直接结算并重置进度。", 958, 412),
        ("确定结束进程吗？", 840, 440), ("放弃并结算", 980, 743),
    ))


def active_match_exit_dialog(*, abandon_enabled=True):
    image = CANVAS.copy()
    draw = ImageDraw.Draw(image)
    if abandon_enabled:
        draw.rounded_rectangle((571, 715, 931, 772), radius=28, fill=(224, 224, 224))
    draw.rounded_rectangle((989, 715, 1349, 772), radius=28, fill=(224, 224, 224))
    return Frame(image, labels(
        ("提示", 778, 341), ("是否中断挑战并保存当前进度？进度将保留至1-6。", 1014, 412),
        ("选择放弃挑战将放弃当前的挑战进度。", 948, 441), ("当前持有金币", 830, 587),
        ("放弃并结算", 770, 743), ("暂时离开", 1188, 744),
    ))


@pytest.mark.parametrize("abandon_enabled", (False, True))
def test_active_match_escape_uses_only_the_left_abandon_button(monkeypatch, world, abandon_enabled):
    prompt = active_match_exit_dialog(abandon_enabled=abandon_enabled)
    assert prompt.page == Page.END_MATCH_CONFIRM
    assert ui.point(prompt.end_match_confirm()) == ((770, 743) if abandon_enabled else None)
    initial = page(Page.BOARD, stage="1-6")
    menu = mode(("进入标准博弈", 1692, 961))

    def click(state, point):
        assert state.frame is prompt and point == (770, 743)
        state.frame = menu

    state = drive(monkeypatch, world, initial, click)

    def press(key):
        state.keys.append((state.frame.page, key))
        state.frame = prompt
        return True

    world.auto.press_key.side_effect = press
    if abandon_enabled:
        assert world.war._restart_match(initial, can_exit=lambda f: f is initial, start_new=False) == (menu, True)
    else:
        with pytest.raises(task.CurrencyWarsUnavailable, match="未确认旧对局已结束"):
            world.war._restart_match(initial, can_exit=lambda f: f is initial, start_new=False)
    assert state.keys == [(Page.BOARD, "esc")]
    assert state.clicks == ([(Page.END_MATCH_CONFIRM, (770, 743))] if abandon_enabled else [])


def test_takeover_cancels_an_open_in_match_exit_prompt(monkeypatch, world):
    prompt = Frame(CANVAS, labels(("提示", 778, 341), ("是否中断挑战并保存当前进度？", 1014, 412)))
    ready = page(Page.BOARD, stage="2-3")
    state = drive(monkeypatch, world, prompt)

    def press(key):
        state.keys.append(key)
        state.frame = ready

    world.auto.press_key.side_effect = press
    assert world.war._enter_with_recovery(prompt, resume=True) is ready
    assert state.keys == ["esc"] and not state.clicks


@pytest.mark.parametrize("explicit_takeover", (False, True))
def test_saved_match_resumes_in_its_own_mode_using_configured_strategy(monkeypatch, world, explicit_takeover):
    world.cfg.currencywars_unfinished_match = "restart" if explicit_takeover else "resume"
    world.cfg.currencywars_strategy = policy.HIGH_ANAXA
    ongoing = mode(("结束并结算", 1397, 961), ("继续进度", 1692, 961), ("超频博弈", 670, 155))
    ready = page(Page.BOARD, stage="3-1")
    lobby = home()
    initial = end_match_dialog() if explicit_takeover else ongoing
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(s, "frame", ready))

    def press(key):
        state.keys.append((state.frame.page, key))
        state.frame = ongoing

    world.auto.press_key.side_effect = press

    def play(frame):
        assert frame is ready
        assert world.war.mode == "overclock"
        assert world.war.lineup is policy.LINEUPS[policy.HIGH_ANAXA]
        world.war.result = True
        return lobby

    monkeypatch.setattr(world.war, "_play", play)
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))
    assert world.war.start(resume=explicit_takeover)
    assert state.clicks == [(Page.MODES, (1692, 961))]
    assert state.keys == ([(Page.END_MATCH_CONFIRM, "esc")] if explicit_takeover else [])


@pytest.mark.parametrize("start_in_battle", (False, True))
def test_takeover_plays_the_current_match_without_visiting_the_menu(monkeypatch, world, start_in_battle):
    world.cfg.currencywars_type = "overclock"
    world.cfg.currencywars_unfinished_match = "restart"
    investment_text = labels(("投资环境", 960, 100), ("经济过热", 438, 392),
                             ("仙舟舰队邀请", 960, 392), ("人身意外险", 1482, 392),
                             ("确认", 1082, 984))
    investment = Frame(CANVAS, investment_text)
    selected = enable_investment_confirm(Frame(CANVAS, investment_text))
    fighting = battle(True)
    result = page(Page.MATCH_RESULT, ("挑战成功", 960, 233), ("返回货币战争", 960, 899))
    lobby = home()
    screen = Mock()
    monkeypatch.setattr(task, "screen", screen)
    monkeypatch.setattr(world.war, "get_reward", lambda f: (f, (18000, 18000), False))

    routes = {
        (investment, (1482, 392)): selected,
        (selected, (1082, 984)): fighting,
        (result, (960, 899)): lobby,
    }
    battle_reads = 0

    def capture(state):
        nonlocal battle_reads
        if state.frame is fighting:
            battle_reads += 1
            if battle_reads >= 4:
                state.frame = result

    state = drive(monkeypatch, world, fighting if start_in_battle else investment,
                  lambda s, point: setattr(s, "frame", routes[s.frame, point]), capture)
    assert world.war.start(resume=True)
    selection = [] if start_in_battle else [(Page.CHOICE, (1482, 392)), (Page.CHOICE, (1082, 984))]
    assert state.clicks == [*selection, (Page.MATCH_RESULT, (960, 899))]
    assert not state.keys
    assert screen.mock_calls == []


@pytest.mark.parametrize("weekly", (False, True))
def test_start_without_takeover_continues_the_active_match(monkeypatch, world, weekly):
    frame = page(Page.CHOICE, choice="投资环境")
    state = drive(monkeypatch, world, frame)
    lobby = home()
    play = Mock(side_effect=lambda _: setattr(world.war, "result", True) or lobby)
    monkeypatch.setattr(world.war, "_play", play)
    monkeypatch.setattr(world.war, "get_reward", lambda f: (f, (18000, 18000), False))
    assert world.war.start(weekly=weekly)
    play.assert_called_once_with(frame)
    assert not state.clicks and not state.keys


@pytest.mark.parametrize("kind", (Page.BATTLE, Page.NODE_RESULT))
def test_start_without_takeover_needs_currency_wars_hud_on_generic_battle_pages(monkeypatch, world, kind):
    frame = page(kind, combat_progress=False)
    state = drive(monkeypatch, world, frame)
    launch = Mock()
    monkeypatch.setattr(world.war, "_launch", launch)

    assert world.war.start() is False
    launch.assert_not_called()
    assert not state.clicks and not state.keys


def test_unreadable_entry_reports_unavailable_after_bounded_observations(monkeypatch, world):
    state = drive(monkeypatch, world, page(Page.UNKNOWN))
    navigation = object.__new__(Screen)
    navigation.__init__(config_path="assets/config/screens.json", logger=Mock())
    identify = Mock(return_value=False)
    monkeypatch.setattr(navigation, "get_current_screen", identify)
    monkeypatch.setitem(Screen.perform_operations.__globals__, "auto", world.auto)
    monkeypatch.setattr(task, "screen", navigation)

    with pytest.raises(task.CurrencyWarsUnavailable, match="多次复核后仍无法确认货币战争入口"):
        world.war.start()
    assert identify.call_count == task.MAX_ENTRY_ATTEMPTS
    assert all(call.kwargs["autotry"] is False for call in identify.call_args_list)
    assert not state.clicks and not state.keys
    world.auto.click_element.assert_not_called()


def test_old_match_settles_before_weekly_run_starts_a_new_match(monkeypatch, world):
    lobby = home()
    ongoing = mode(("超频博弈", 670, 155), ("继续进度", 1692, 961),
                   ("结束并", 1364, 960), ("结算", 1427, 960))
    monkeypatch.setattr(ongoing, "read_local", lambda area: "结束并结算" if area == ui.MODE_END_BUTTON else None)
    prompt = end_match_dialog()
    assert prompt.page == Page.END_MATCH_CONFIRM
    rating = page(Page.MATCH_RESULT, ("挑战失败", 959, 233), ("下一步", 962, 897))
    details = page(Page.MATCH_RESULT, ("对局未完成", 1145, 215), ("下一页", 961, 900))
    finish = page(Page.MATCH_RESULT, ("返回货币战争", 960, 899), ("继续挑战", 1200, 899))
    fresh_menu = mode(("进入标准博弈", 1692, 961))
    difficulty = rank()
    ready = page(Page.CHOICE)
    events = []
    routes = {
        (lobby, (1600, 972)): ongoing,
        (ongoing, (1396, 960)): prompt,
        (prompt, (980, 743)): rating,
        (rating, (962, 897)): details,
        (details, (961, 900)): finish,
        (finish, (960, 899)): fresh_menu,
        (fresh_menu, (1692, 961)): difficulty,
        (difficulty, (1680, 965)): ready,
    }
    state = drive(monkeypatch, world, lobby, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    on_match_result = Mock()
    monkeypatch.setattr(world.war, "_on_match_result", on_match_result)

    def play(frame):
        assert frame is ready and world.war.mode == "normal"
        assert world.war.result is None
        events.append("played")
        world.war.result = True
        return lobby

    def check_weekly_reward(frame):
        assert frame is lobby
        score = 18000 if events else 0
        events.append("reward")
        return frame, (score, 18000), False

    monkeypatch.setattr(world.war, "_play", play)
    monkeypatch.setattr(world.war, "_check_weekly_reward", check_weekly_reward)
    assert world.war.start(weekly=True)
    assert events == ["reward", "played", "reward"]
    assert state.clicks == [(f.page, pt) for f, pt in routes]
    assert not state.keys
    on_match_result.assert_not_called()


def test_unconfirmed_end_match_is_not_repeated_and_does_not_start_a_new_match(monkeypatch, world):
    ongoing = mode(("结束并结算", 1397, 961), ("继续进度", 1692, 961))
    prompt = end_match_dialog()

    def click(state, point):
        if point == (1397, 961):
            state.frame = prompt

    state = drive(monkeypatch, world, ongoing, click)
    world.auto.press_key.side_effect = lambda key: (
        state.keys.append(key), setattr(state, "frame", ongoing))
    with pytest.raises(task.CurrencyWarsUnavailable, match="未确认旧对局已结束"):
        world.war.start()
    assert state.clicks == [(Page.MODES, (1397, 961)), (Page.END_MATCH_CONFIRM, (980, 743))]
    assert not state.keys


@pytest.mark.parametrize("outcome", ("still_saved", "settled", "old_result", "delayed"))
def test_old_match_settlement_keeps_restart_intent(monkeypatch, world, outcome):
    ongoing = mode(("结束并结算", 1397, 961), ("继续进度", 1692, 961), ("标准博弈", 646, 156))
    prompt = end_match_dialog()
    fresh = mode(("进入标准博弈", 1638, 960))
    ranks = rank()
    ready = page(Page.BOARD, stage="1-1")
    old_result = page(Page.MATCH_RESULT, ("对局未完成", 960, 233), ("返回货币战争", 960, 899))
    result = page(Page.MATCH_RESULT, ("对局胜利", 960, 233), ("返回货币战争", 960, 899))
    lobby = home()
    confirmed_at = None
    settled = {"still_saved": ongoing, "old_result": old_result}.get(outcome, fresh)
    routes = {(ongoing, (1397, 961)): prompt, (old_result, (960, 899)): fresh, (fresh, (1638, 960)): ranks,
              (ranks, (1680, 965)): ready, (result, (960, 899)): lobby}

    def click(state, point):
        nonlocal confirmed_at
        if state.frame is prompt and point == (980, 743):
            confirmed_at = world.now[0]
            if outcome != "delayed":
                state.frame = settled
        else:
            state.frame = routes[state.frame, point]

    def capture(state):
        if (outcome == "delayed" and state.frame is prompt and confirmed_at is not None
                and world.now[0] >= confirmed_at + 30):
            state.frame = fresh

    state = drive(monkeypatch, world, ongoing, click, capture)
    monkeypatch.setattr(world.war, "_prepare", lambda f: setattr(state, "frame", result) or result)
    monkeypatch.setattr(world.war, "get_reward", lambda f: (f, (18000, 18000), False))
    expected = [(Page.MODES, (1397, 961)), (Page.END_MATCH_CONFIRM, (980, 743))]
    if outcome == "old_result":
        expected.append((Page.MATCH_RESULT, (960, 899)))
    if outcome == "still_saved":
        with pytest.raises(task.CurrencyWarsUnavailable, match="旧对局结算待核对"):
            world.war.start()
        assert state.frame is ongoing
    else:
        assert world.war.start() is True
        expected.extend([(Page.MODES, (1638, 960)), (Page.RANK, (1680, 965)), (Page.MATCH_RESULT, (960, 899))])
    assert state.clicks == expected
    assert not state.keys


def test_missing_resume_button_does_not_end_or_start_a_match(monkeypatch, world):
    world.cfg.currencywars_unfinished_match = "resume"
    ongoing = mode(("结束并结算", 1397, 961), ("超频博弈", 670, 155))
    state = drive(monkeypatch, world, ongoing)
    with pytest.raises(task.CurrencyWarsReadTimeout, match="没有可确认的续局入口"):
        world.war._launch(ongoing, False)
    assert not state.clicks and not state.keys


def test_unmapped_start_does_not_override_the_restart_setting(monkeypatch, world):
    world.cfg.currencywars_unfinished_match = "restart"
    initial = rank()
    ongoing = mode(("标准博弈", 646, 156), ("继续进度", 1692, 961), ("结束并结算", 1397, 961))
    prompt = end_match_dialog()
    fresh = mode(("进入标准博弈", 1638, 960))
    ready = page(Page.BOARD, stage="1-1")
    routes = {
        (ongoing, (1397, 961)): prompt, (prompt, (980, 743)): fresh,
        (fresh, (1638, 960)): initial, (initial, (1680, 965)): ready,
        (ongoing, (1692, 961)): ready,
    }
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    map_point = world.auto.find_element.side_effect

    def mapping(*args, **kwargs):
        point = map_point(*args, **kwargs)
        if point == (1680, 965) and not state.clicks:
            state.frame = ongoing
            return None
        return point

    world.auto.find_element.side_effect = mapping
    assert world.war._enter_with_recovery(initial, resume=False) is ready
    assert state.clicks == [(frame.page, point) for frame, point in routes if point != (1692, 961)]


def test_unmapped_resume_does_not_accept_an_unrelated_battle(monkeypatch, world):
    world.war.mode = "overclock"
    world.cfg.currencywars_unfinished_match = "resume"
    ongoing = mode(("标准博弈", 646, 156), ("继续进度", 1692, 961))
    unrelated = page(Page.BATTLE, combat_progress=False)
    state = drive(monkeypatch, world, ongoing)
    world.auto.find_element.side_effect = lambda *a, **kw: setattr(state, "frame", unrelated)

    assert world.war._enter_with_recovery(ongoing, resume=False) is None
    assert not state.clicks
    assert world.war.mode == "overclock"
    assert not world.war.mode_confirmed


def test_locked_overclock_stops_without_starting_standard(monkeypatch, world):
    world.war.mode = "overclock"
    state = drive(monkeypatch, world, home(), lambda state, _: setattr(
        state, "frame", mode(("进入标准博弈", 1638, 960))))
    with pytest.raises(task.CurrencyWarsError, match="尚未解锁"):
        world.war._launch(world.war.frame, False)
    assert state.clicks == [(Page.HOME, (1600, 972))] + [(Page.MODES, (160, 420))] * 3


def test_start_click_is_retried_only_while_rank_page_is_visible(monkeypatch, world):
    ready = page(Page.CHOICE)
    counts = []
    def click(state, point):
        if state.frame.page == Page.HOME:
            state.frame = mode(("进入标准博弈", 1638, 960))
        elif state.frame.page == Page.MODES:
            state.frame = rank()
        else:
            counts.append(point)
            if len(counts) == 2:
                state.frame = ready
    state = drive(monkeypatch, world, home(), click)
    assert world.war._launch(world.war.frame, False) == ready
    assert len(counts) == 2
    assert not state.keys


def test_start_never_clicks_loading_screen(monkeypatch, world):
    def click(state, point):
        state.frame = {
            (1600, 972): mode(("进入标准博弈", 1638, 960)),
            (1638, 960): rank(),
            (1680, 965): page(Page.UNKNOWN),
        }[point]
    state = drive(monkeypatch, world, home(), click)
    with pytest.raises(task.CurrencyWarsError, match="未确认开局"):
        world.war._launch(world.war.frame, False)
    assert state.clicks.count((Page.RANK, (1680, 965))) == 1
    assert not state.keys


@pytest.mark.parametrize("read_locally", (False, True))
def test_overclock_starts_when_ocr_reads_the_enemy_rank_with_brackets(monkeypatch, world, read_locally):
    world.war.mode = "overclock"
    rank_labels = labels(("入画奇航", 151, 80), ("超频博弈", 155, 884),
                         ("A8财富造物主", 168, 321), ("[4]", 674, 965), ("开始对局", 1692, 966))
    if not read_locally:
        rank_labels += labels(("[72]", 544, 965))
    initial = Frame(CANVAS, rank_labels)
    if read_locally:
        monkeypatch.setattr(initial, "read_local", lambda area: "[72]" if area == ui.RANK_ENEMY else None)
    ready = page(Page.BOARD)
    state = drive(monkeypatch, world, initial, lambda s, _: setattr(s, "frame", ready))

    assert initial.page == Page.RANK
    assert (initial.rank_tier, initial.enemy_rank, initial.rank_affixes) == (8, 72, 4)
    assert initial.number(ui.RANK_ENEMY, 999) is None
    assert world.war._launch(initial, False) is ready
    assert state.clicks == [(Page.RANK, (1692, 966))]


def test_overclock_starts_on_its_rank_page_and_chooses_lowest(monkeypatch, world):
    world.cfg.currencywars_type = "overclock"
    world.cfg.currencywars_rank_difficulty = "lowest"
    mode_label = ("超频博弈", 154, 884)
    start_label = ("开始对局", 1680, 965)
    upper = page(Page.RANK, mode_label, start_label, enemy_rank=2)
    floor = page(Page.RANK, mode_label, start_label, enemy_rank=1)
    monkeypatch.setattr(upper, "match", lambda *args: (960, 845))
    ready = page(Page.BOARD)

    state = drive(monkeypatch, world, upper, lambda s, p: setattr(
        s, "frame", floor if p == (960, 845) else ready))
    monkeypatch.setattr(world.war, "_play", lambda f: setattr(world.war, "result", f is ready) or home())
    monkeypatch.setattr(world.war, "get_reward", lambda f: (f, (18000, 18000), False))
    assert world.war.start()
    assert state.clicks == [(Page.RANK, (960, 845))] * 4 + [(Page.RANK, (1680, 965))]


@pytest.mark.parametrize("ignored", (0, 4, 8))
def test_lowest_rank_batches_clicks_and_rechecks_real_progress(monkeypatch, world, ignored):
    mode_label = ("标准博弈", 154, 884)
    control = (960, 846)
    levels = tuple(page(Page.RANK, mode_label, enemy_rank=i) for i in range(1, 32))
    for frame in levels:
        monkeypatch.setattr(frame, "match", lambda *_: control)
    captures = []
    start = levels[-1]

    def click(state, point):
        assert point == control
        if len(state.clicks) > ignored:
            state.frame = levels[max(0, state.frame.enemy_rank - 2)]

    state = drive(monkeypatch, world, start, click, lambda s: captures.append(len(s.clicks)))
    assert world.war._select_rank(start, "lowest") is levels[0]
    assert all(click == (Page.RANK, control) for click in state.clicks)
    assert len(state.clicks) == (33 if ignored < 4 else 33 + ignored)
    assert not set(range(1, 33)) & set(captures)
    assert not state.keys


@pytest.mark.parametrize("recovers", (False, True))
def test_lowest_rank_gets_one_retry_after_a_stalled_batch(monkeypatch, world, recovers):
    mode = ("标准博弈", 154, 884)
    frame = page(Page.RANK, mode, enemy_rank=31)
    minimum = page(Page.RANK, mode, enemy_rank=1)
    control = (960, 846)
    monkeypatch.setattr(frame, "match", lambda *_: control)
    state = drive(monkeypatch, world, frame, lambda s, _: setattr(s, "frame", minimum)
                  if recovers and len(s.clicks) == 63 else None)
    if recovers:
        assert world.war._select_rank(frame, "lowest") is minimum
    else:
        with pytest.raises(task.CurrencyWarsReceiptTimeout, match="难度下降"):
            world.war._select_rank(frame, "lowest")
    assert state.clicks == [(Page.RANK, control)] * 66


@pytest.mark.parametrize("selection", ("current", "highest"))
def test_rank_current_keeps_selection_and_highest_uses_its_own_control(monkeypatch, world, selection):
    back = ("返回最高职级", 1380, 960)
    mode_label = ("标准博弈", 154, 884)
    current = page(Page.RANK, mode_label, back, enemy_rank=1)
    highest = page(Page.RANK, mode_label, enemy_rank=67)
    state = drive(monkeypatch, world, current, lambda s, _: setattr(s, "frame", highest))
    target = highest if selection == "highest" else current
    assert world.war._select_rank(current, selection) is target
    assert state.clicks == ([(Page.RANK, back[1:])] if selection == "highest" else [])


@pytest.mark.parametrize("initial,maximum", ((1, 67), (1, 19), (19, 19), (1, 28), (35, 67), (28, 67)))
def test_promotion_preset_selects_a4_6_or_highest_unlocked_before_start(monkeypatch, world, initial, maximum):
    world.cfg.currencywars_type = "overclock"
    world.cfg.currencywars_rank_difficulty = policy.PROMOTION_CAP_DIFFICULTY
    world.war.mode = "overclock"
    start = (1692, 966)
    to_top = (1386, 966)
    # 正式服敌人难度不是每档递增 1。冰钛 5→6→7 分别为 27、28、29。
    ranks = [n for n in range(1, maximum + 1) if n not in (3, 5, 14, 32, 33, 34, 36, 39, 41, 42)]
    frames = {}
    for level in ranks:
        entries = [("超频博弈", 154, 884), ("开始对局", *start)]
        if level != maximum:
            entries.append(("返回最高职级", *to_top))
        frames[level] = page(Page.RANK, *entries, enemy_rank=level)
    arrived = page(Page.CHOICE)
    target = min(maximum, 28)

    def click(state, point):
        level = state.frame.enemy_rank
        if point == start:
            assert level == target
            state.frame = arrived
        elif point == to_top:
            state.frame = frames[maximum]
        else:
            index = ranks.index(level)
            step = 1 if point == ui.RANK_STEP_UP else -1
            assert point in (ui.RANK_STEP_UP, ui.RANK_STEP_DOWN)
            state.frame = frames[ranks[max(0, min(index + step, len(ranks) - 1))]]

    initial_frame = frames[initial]
    state = drive(monkeypatch, world, initial_frame, click)
    assert world.war._launch(initial_frame, False) is arrived
    assert state.clicks.count((Page.RANK, start)) == 1
    if maximum < 28 or initial == 28:
        assert all(point in (to_top, start) for _, point in state.clicks)
    assert not state.keys


def test_promotion_preset_recovers_a_missed_return_button(monkeypatch, world):
    world.war.mode = "overclock"
    mode_label = ("超频博弈", 154, 884)
    to_top = ("返回最高职级", 1386, 966)
    unread = page(Page.RANK, mode_label, enemy_rank=1)
    current = page(Page.RANK, mode_label, to_top, enemy_rank=1)
    unlocked = page(Page.RANK, mode_label, enemy_rank=28)
    state = drive(
        monkeypatch, world, unread, lambda s, _: setattr(s, "frame", unlocked),
        after_capture=lambda s: setattr(s, "frame", current) if s.frame is unread else None,
    )
    assert world.war._select_rank(unread, policy.PROMOTION_CAP_DIFFICULTY) is unlocked
    assert state.clicks == [(Page.RANK, to_top[1:])]


def test_moving_preview_button_is_relocated_then_retried(monkeypatch, world):
    def reveal(y):
        return Frame(CANVAS, labels(("本场对局首领", 585, 201), ("本局奇遇", 1200, 627), ("下一步", 1399, y)))

    moving, settling, stable = (reveal(y) for y in (1012, 996, 984))
    settled = page(Page.CHOICE)
    frames = iter((moving, settling, stable))

    def capture(state):
        state.frame = next(frames, state.frame)

    def click(state, _):
        if len(state.clicks) == 2:
            state.frame = settled
        return False

    state = drive(monkeypatch, world, moving, click, capture)
    frame = world.war._click_to(moving, lambda f: ui.point(f.reveal_button()),
                                lambda f: f.page == Page.CHOICE, "未确认开局预览")
    assert frame is settled
    assert state.clicks == [(Page.REVEAL, (1399, 984))] * 2


@pytest.mark.parametrize("event", (Page.CHOICE, Page.DANCE, Page.HACK))
def test_open_box_yields_to_recognized_overlays_after_held_input(monkeypatch, world, event):
    unopened = page(Page.BOARD, ("开启", 564, 953), stage="1-1")
    choice = page(event)
    state = drive(monkeypatch, world, unopened, lambda s, _: setattr(s, "frame", choice))
    result = world.war._open_box(unopened, unopened.find("开启"))
    assert result is choice
    world.auto.click_element_with_pos.assert_called_once_with((564, 953), press_duration=task.BOX_HOLD)
    assert task.BOX_HOLD > task.CLICK_HOLD


def test_open_box_only_accepts_a_verified_change_on_the_same_board(monkeypatch, world):
    unopened = page(Page.BOARD, ("开启", 564, 953), stage="1-1")
    label_hidden = page(Page.BOARD, stage="1-1")
    state = drive(monkeypatch, world, unopened, lambda s, _: setattr(s, "frame", label_hidden))
    with pytest.raises(task.CurrencyWarsError, match="未确认奖励界面或物品变化"):
        world.war._open_box(unopened, unopened.find("开启"))
    assert state.clicks == [(Page.BOARD, (564, 953))]


def test_box_from_the_last_orb_is_opened_once_it_has_landed(monkeypatch, world):
    """复现 2-5：晶矿最后一颗扫出武装箱，收集回执那一帧箱子还在落位动画中。等箱面稳定后再取基准，照常点击开启。"""
    stage, button = "2-5", (1312, 952)

    def box_screen(brightness):
        frame = page(Page.BOARD, ("开启", *button), stage=stage)
        image = np.array(frame.image)
        x, y = ui.BENCH_POINTS[7]
        image[y - 40:y + 40, x - 40:x + 40] = brightness
        frame.image = Image.fromarray(image)
        return frame

    landing, landed, choice = box_screen(230), box_screen(120), page(Page.CHOICE)
    state = drive(monkeypatch, world, landing, lambda s, _: setattr(s, "frame", choice))
    state.frame = landed
    assert world.war._open_box(landing, landing.find("开启")) is choice
    assert state.clicks == [(Page.BOARD, button)]


def test_emblem_book_reads_the_single_choice_cards_and_prefers_combo(monkeypatch, world):
    frame = Frame(CANVAS, labels(("星徽秘典", 1028, 60), ("请选择1个", 1028, 98), ("1-2", 300, 109),
                                ("仙舟舰队星徽", 594, 335), ("连击星徽", 885, 335),
                                ("查看详情", 601, 391), ("查看详情", 891, 391)))
    ready = page(Page.BOARD, stage="1-2")
    monkeypatch.setattr(frame, "inventory_items", lambda: ())
    monkeypatch.setattr(ready, "inventory_items", lambda: ((1844, 248),))
    state = drive(monkeypatch, world, frame, lambda s, _: setattr(s, "frame", ready))
    assert frame.page == Page.CHOICE
    assert world.war._choose(frame) is ready
    assert state.clicks == [(Page.CHOICE, (885, 335))]


@pytest.mark.parametrize("anaxa", (True, False))
def test_emblem_book_takes_the_dreamscape_emblem_for_anaxa(monkeypatch, world, anaxa):
    """攻略：梦境交织星徽决定能否打出长行动链，连击那刻夏遇到就拿；默认策略仍按通用顺序先拿连击星徽。"""
    frame = Frame(CANVAS, labels(("星徽秘典", 1028, 60), ("请选择1个", 1028, 98), ("1-2", 300, 109),
                                ("梦境交织星徽", 594, 335), ("连击星徽", 885, 335),
                                ("查看详情", 601, 391), ("查看详情", 891, 391)))
    ready = page(Page.BOARD, stage="1-2")
    monkeypatch.setattr(frame, "inventory_items", lambda: ())
    monkeypatch.setattr(ready, "inventory_items", lambda: ((1844, 248),))
    world.war.lineup = policy.LINEUPS[policy.HIGH_ANAXA] if anaxa else None
    world.war.default_strategy = not anaxa
    state = drive(monkeypatch, world, frame, lambda s, _: setattr(s, "frame", ready))
    assert world.war._choose(frame) is ready
    assert state.clicks == [(Page.CHOICE, (594, 335) if anaxa else (885, 335))]


def test_halo_prefers_the_named_halo_when_it_is_offered():
    """攻略首推「逐日」：出现时直接选它，没有指定时照常按增益挑选。"""
    frame = Frame(CANVAS, labels(("逐日", 420, 430), ("那刻夏每次行动后积累追光层数", 420, 520),
                                ("前台专家", 1500, 430), ("前台强度提高20%", 1500, 520)))
    assert frame.halo_effect()[1] == 1
    assert frame.halo_effect(preferred=("逐日",))[1] == 0



@pytest.mark.parametrize("read_card_name", (True, False))
@pytest.mark.parametrize("title", ("简易武装箱", "阿哈·简易武装箱"))
def test_item_box_chooses_a_reward_and_continues_after_returning_to_board(monkeypatch, world, read_card_name, title):
    header = (title, 1028, 60), ("请选择1个", 1028, 98)
    early = Frame(CANVAS, labels(*header))
    name = (("生命之花", 1465, 336),) if read_card_name else ()
    choices = (*name, ("查看详情", 1474, 392))
    ready = Frame(CANVAS, labels(*header, ("1-9", 300, 109), *choices))
    after = page(Page.BOARD, stage="1-9")

    def capture(state):
        if state.frame is early:
            state.frame = ready

    state = drive(monkeypatch, world, early, lambda s, _: setattr(s, "frame", after), capture)
    assert world.war._choose(early) is after
    assert state.clicks == [(Page.CHOICE, (1465, 336) if read_card_name else (1474, 230))]


@pytest.mark.parametrize(("title", "y"), (("选择装备", 40), ("为阿哈选择1件简易装备", 61)))
def test_equipment_reward_title_alone_is_not_a_choice(title, y):
    assert Frame(CANVAS, labels((title, 1028, y))).choice is None


@pytest.mark.parametrize(("reading", "targets"), (
    ("names", ((1174, 336),)),
    ("details", ((1474, 230),)),
    ("prompt", ((593, 230), (883, 230))),
))
def test_aha_equipment_reward_chooses_from_four_cards(monkeypatch, world, reading, targets):
    title = ui.normalized("为「阿哈」选择1件简易装备")
    words = labels((title, 1029, 61), ("备战阶段", 307, 70), ("1-2", 307, 108))
    if reading != "details":
        words += labels(("请选择1个", 1029, 100))
    if reading == "names":
        words += labels(("幸运星", 592, 336), ("折叠小刀", 882, 336), ("轮滑鞋", 1174, 336),
                        ("和平手枪", 1464, 336))
    if reading == "details":
        words += labels(("查看详情", 1474, 392))
    reward = Frame(CANVAS, words)
    ready = page(Page.BOARD, stage="1-2")

    def select(state, point):
        if point == targets[-1]:
            state.frame = ready

    state = drive(monkeypatch, world, reward, select)
    assert reward.page == Page.CHOICE
    assert world.war._play_step(reward) is ready
    assert state.clicks == [(Page.CHOICE, point) for point in targets]
    assert not state.keys


@pytest.mark.parametrize(("reward_ocr", "needs_confirm", "equipment_point"), (
    ("names", False, (1028, 315)),
    ("details", True, (747, 230)),
    ("prompt", False, (1028, 230)),
))
def test_exclusive_endorsement_equipment_reward_resumes_preparation(monkeypatch, world, reward_ocr, needs_confirm,
                                                                equipment_point):
    investment_point = (960, 490)
    confirm_point = (979, 984)
    confirm = labels(("确认", *confirm_point))
    bright = CANVAS.copy()
    ImageDraw.Draw(bright).rectangle((920, 970, 1038, 999), fill=(235, 235, 235))
    stage = labels(("备战阶段", 300, 50), ("1-3", 304, 87))
    investment_words = stage + labels(("请选择投资策略", 960, 100), ("独家代言", *investment_point),
                                      ("选择并获得1件进阶装备。", 960, 545))
    investment = Frame(CANVAS, investment_words)
    chosen = Frame(bright, investment_words + confirm)

    # 用户反馈中标题位于画面顶部。重读时也可能只剩下提示或详情按钮。
    reward_words = stage + labels(("选择装备", 1028, 36 if reward_ocr == "details" else 40),
                                  ("火力风暴潮", 969, 616))
    if reward_ocr != "details":
        reward_words += labels(("请选择1个", 1028, 78))
    if reward_ocr != "prompt":
        reward_words += labels(("查看详情", 747, 372), ("查看详情", 1037, 370), ("查看详情", 1328, 372))
    if reward_ocr == "names":
        reward_words += labels(("行星钻地弹", 738, 313), ("绝对热量", 1028, 315), ("物质分解液", 1320, 315))
    reward = Frame(CANVAS, reward_words)
    selected = Frame(bright, reward_words + confirm)
    ready = Frame(CANVAS, stage + labels(("前台区域", 960, 316), ("后台区域", 960, 576),
                                        ("出战", 1818, 752), ("商店", 1621, 982)))
    result = Frame(CANVAS, labels(("对局胜利", 960, 233), ("返回货币战争", 960, 899)))
    lobby = home()
    routes = {(investment, investment_point): chosen, (chosen, confirm_point): reward,
              (reward, equipment_point): selected if needs_confirm else ready}
    if needs_confirm:
        routes[selected, confirm_point] = ready
    routes[result, (960, 899)] = lobby
    state = drive(monkeypatch, world, investment, lambda s, p: setattr(s, "frame", routes[s.frame, p]))

    def prepare(frame):
        assert frame is ready
        state.frame = result
        return result

    monkeypatch.setattr(world.war, "_prepare", prepare)
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))
    world.cfg.currencywars_time_limit = 1

    assert world.war.start(resume=True) is True
    assert state.frame is lobby
    assert state.clicks == [(frame.page, point) for frame, point in routes]
    assert state.keys == []


@pytest.mark.parametrize("confirmed", (False, True))
def test_purchase_needs_both_gold_delta_and_slot_change(monkeypatch, world, confirmed):
    offer = policy.Offer("那刻夏", 1, (470, 192), 0)
    initial = page(Page.BOARD, ("商店", 1624, 983))
    shop = page(Page.SHOP, ("收起", 1624, 983), gold=7, offers=(offer,))
    bought = page(Page.SHOP, ("收起", 1624, 983), gold=6, offers=())
    monkeypatch.setattr(bought, "shop_changed", lambda old, col: confirmed)
    def click(state, point):
        state.frame = {(Page.BOARD, (1624, 983)): shop,
                       (Page.SHOP, (470, 192)): bought,
                       (Page.SHOP, (1624, 983)): initial}[state.frame.page, point]
    state = drive(monkeypatch, world, initial, click)
    before = board(slot("bench", 0), gold=7, lineup=policy.LINEUPS[policy.HIGH_ANAXA])
    if confirmed:
        assert world.war._shop(initial, before, 0) == (initial, 0, True)
        # 下次读盘时，买前空着的备战格里只多出这一张就按商店的姓名记下。
        assert world.war.purchased_card == task.PurchasedCard("1-3", "那刻夏", frozenset({0}))
    else:
        with pytest.raises(task.CurrencyWarsError, match="未确认扣费"):
            world.war._shop(initial, before, 0)
    assert state.clicks.count((Page.SHOP, (470, 192))) == 1


@pytest.mark.parametrize("credited_gold", (4, 8))
def test_sold_slot_with_unclear_balance_is_checked_on_board_without_repurchase(monkeypatch, world, credited_gold):
    offer = policy.Offer("那刻夏", 1, (470, 192), 0)
    initial = page(Page.BOARD, ("商店", 1624, 983), gold=5)
    shop = page(Page.SHOP, ("收起", 1624, 983), gold=5, offers=(offer,))
    sold = page(Page.SHOP, ("收起", 1624, 983), gold=None, offers=())
    board_receipt = page(Page.BOARD, gold=credited_gold)
    monkeypatch.setattr(sold, "shop_changed", lambda old, col: True)
    monkeypatch.setattr(sold, "shop_slot_empty", lambda col: True)
    routes = {(initial, (1624, 983)): shop, (shop, (470, 192)): sold, (sold, (1624, 983)): board_receipt}
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    assert world.war._shop(initial, board(slot("bench", 0), lineup=policy.LINEUPS[policy.HIGH_ANAXA]), 0) == (board_receipt, 0, True)
    assert state.clicks.count((Page.SHOP, (470, 192))) == 1


@pytest.mark.parametrize(("price", "gold_after", "catalog_changed", "accepted"), (
    (2, 10, True, True), (2, 11, True, True), (2, 17, True, True), (0, 16, True, True),
    (2, 15, False, False), (2, 9, True, False),
))
def test_shop_refresh_verifies_the_catalog_and_accepts_variable_credits(
        monkeypatch, world, price, gold_after, catalog_changed, accepted):
    stage = "1-6"
    button = (1618, 488)
    controls = (("刷新", *button), ("2", 1636, 532)) if price else (("免费刷新", *button),)
    first = page(Page.SHOP, *controls, stage=stage, gold=12, offers=())
    updated = page(Page.SHOP, *controls, stage=stage, gold=gold_after, offers=())
    returned = page(Page.BOARD, stage=stage, gold=gold_after)
    team = board(slot("front", 0, FILLER), slot("bench", 0), slot("bench", 1),
                 stage=stage, used=1, capacity=1, lineup=policy.LINEUPS[policy.HIGH_ANAXA])
    # 只核对一次刷新的回执，是否继续刷新交给策略自身的用例。
    monkeypatch.setattr(task.strategy, "should_refresh", lambda team, price, refreshes, **_: refreshes == used)
    monkeypatch.setattr(updated, "shop_changed", lambda before, column: catalog_changed and before is first)
    monkeypatch.setattr(world.war, "_open_shop", lambda _: first)
    monkeypatch.setattr(world.war, "_settle_shop", lambda frame: frame)
    monkeypatch.setattr(world.war, "_close_shop", lambda _: returned)
    state = drive(monkeypatch, world, first, lambda s, _: setattr(s, "frame", updated))
    used = 1 if price else 0
    if accepted:
        assert world.war._shop(first, team, used) == (returned, used + 1, False)
    else:
        with pytest.raises(task.CurrencyWarsError, match="已尝试 1 次"):
            world.war._shop(first, team, used)
    assert state.clicks == [(Page.SHOP, button)]
    assert world.war.stage_refreshes[stage] == used + 1
    assert ((stage, "商店") in world.war.deferred_operations) is not accepted


def test_shop_refresh_checks_the_displayed_price_again_before_input(monkeypatch, world):
    stage = "1-6"
    button = ("刷新", 1618, 488)
    first = page(Page.SHOP, button, ("2", 1636, 532), stage=stage, gold=12, offers=())
    repriced = page(Page.SHOP, button, ("3", 1636, 532), stage=stage, gold=12, offers=())
    team = board(slot("front", 0, FILLER), slot("bench", 0), slot("bench", 1),
                 stage=stage, used=1, capacity=1)
    monkeypatch.setattr(world.war, "_open_shop", lambda _: first)
    monkeypatch.setattr(world.war, "_settle_shop", lambda frame: frame)
    state = drive(monkeypatch, world, first)
    state.frame = repriced
    with pytest.raises(task.CurrencyWarsActionUnready, match="已尝试 0 次"):
        world.war._shop(first, team, 0)
    assert state.clicks == []
    assert stage not in world.war.stage_refreshes


@pytest.mark.parametrize("fault", ("transient", "unavailable", "action_timeout", "stop", "reply_lost"))
def test_shop_refresh_records_only_dispatched_input(monkeypatch, world, fault):
    stage = "1-6"
    point = (1618, 488)
    before = page(Page.SHOP, ("刷新", *point), stage=stage, gold=12, shop_refresh_price=2)
    updated = page(Page.SHOP, stage=stage, gold=10, shop_catalog_changed=lambda f: f is before)
    state = drive(monkeypatch, world, before,
                  lambda s, _: False if fault == "reply_lost" else setattr(s, "frame", updated))
    reads = 0

    def mapping(*args, **kwargs):
        nonlocal reads
        reads += 1
        if fault == "stop":
            task.pause_ctl.checkpoint.side_effect = RunStopRequested()
        elif fault == "action_timeout":
            world.now[0] += 9
        if fault == "unavailable" or fault == "transient" and reads == 1:
            return None
        return point

    world.auto.find_element.side_effect = mapping
    if fault == "transient":
        assert world.war._refresh_shop(before, 2, 0, stage) == (updated, True)
    else:
        error = {
            "unavailable": task.CurrencyWarsActionUnready, "action_timeout": task.CurrencyWarsActionUnready,
            "stop": RunStopRequested, "reply_lost": task.CurrencyWarsReceiptTimeout,
        }[fault]
        with pytest.raises(error):
            world.war._refresh_shop(before, 2, 0, stage)
    sent = fault in ("transient", "reply_lost")
    assert state.clicks == ([(Page.SHOP, point)] if sent else [])
    assert world.war.stage_refreshes.get(stage, 0) == int(sent)
    assert ((stage, "商店") in world.war.deferred_operations) == (fault == "reply_lost")


@pytest.mark.parametrize("missed_stage", (False, True))
def test_shop_retry_keeps_refresh_budget_after_a_recognition_failure(monkeypatch, world, missed_stage):
    stage = "1-3"
    team = board(slot("front", 0, FILLER), slot("bench", 0), stage=stage, used=1, gold=30, lineup=policy.LINEUPS[policy.HIGH_ANAXA])
    boards, shops = [], []
    for index in range(3):
        gold = team.gold - 2 * index
        boards.append(page(Page.BOARD, ("商店", 1624, 983), ("出战", 1818, 751),
                           stage=stage, gold=gold, capacity=(1, 3)))
        shop = page(Page.SHOP, ("收起", 1624, 983), ("刷新", 1627, 511),
                    stage=None if missed_stage else stage, gold=gold, shop_refresh_price=2)
        shop.image = CANVAS.copy()
        ImageDraw.Draw(shop.image).rectangle((387, 78, 588, 185), fill=(70 * index,) * 3)
        shops.append(shop)
    local_template = ui.template
    failures = []

    def template(path):
        if path == "screen/currency_wars/s2_shop_two_star.png" and not failures:
            failures.append(path)
            raise OSError("暂时无法读取二星模板")
        return local_template(path)

    shops[0].__dict__["offers"] = ()
    monkeypatch.setattr(ui, "template", template)
    # 是否继续刷新交给策略自身的用例，这里只核对识别失败后本节点的刷新次数不丢。
    monkeypatch.setattr(task.strategy, "should_refresh", lambda team, price, refreshes, **_: refreshes < 2)
    monkeypatch.setattr(world.war, "_collect_preparation_rewards", lambda f: (f, True))
    monkeypatch.setattr(world.war, "_read_board", lambda f: (f, replace(team, gold=f.gold)))
    monkeypatch.setattr(world.war, "_equip", lambda f, _: f)
    lobby = home()
    result = page(Page.MATCH_RESULT, ("对局胜利", 960, 233), ("返回货币战争", 960, 899))
    monkeypatch.setattr(world.war, "get_reward", lambda f: (f, (100, 18000), False))
    routes = {(result, (960, 899)): lobby, (boards[-1], (1818, 751)): result}
    routes.update(((f, (1624, 983)), s) for f, s in zip(boards, shops))
    routes.update(((s, (1624, 983)), f) for f, s in zip(boards, shops))
    routes.update(((f, (1627, 511)), s) for f, s in zip(shops, shops[1:]))
    state = drive(monkeypatch, world, boards[0], lambda s, point: setattr(s, "frame", routes[s.frame, point]))
    assert world.war.start(resume=True) is True
    assert len(failures) == 1
    assert state.clicks.count((Page.SHOP, (1627, 511))) == world.war.stage_refreshes[stage] == 2
    assert state.clicks.count((Page.BOARD, (1624, 983))) == 2
    assert set(world.war.stage_refreshes) == {stage}


def test_shop_pending_refresh_is_kept_after_stop(monkeypatch, world):
    stage = "1-6"
    button = (1618, 488)
    shop = page(Page.SHOP, ("刷新", *button), stage=stage, gold=12, shop_refresh_price=2)

    def input_refresh(_state, _point):
        task.pause_ctl.checkpoint.side_effect = RunStopRequested()

    state = drive(monkeypatch, world, shop, input_refresh)
    with pytest.raises(RunStopRequested):
        world.war._refresh_shop(shop, 2, 0, stage)
    assert world.war.stage_refreshes[stage] == 1
    assert (stage, "商店") in world.war.deferred_operations
    assert state.clicks == [(Page.SHOP, button)]


@pytest.mark.parametrize("recognized", (False, True))
def test_movement_waits_for_source_destination_and_deployment_count(monkeypatch, world, recognized):
    a, b = slot("bench", 0, CORE), slot("front", 0)
    first = page(Page.BOARD, stage="1-1", capacity=(0, 3))
    after = page(Page.BOARD, stage="1-1", capacity=(1, 3) if recognized else (0, 3))
    monkeypatch.setattr(first, "slot_occupied", lambda p: p == a.point)
    monkeypatch.setattr(after, "slot_occupied", lambda p: p == b.point)
    state = drive(monkeypatch, world, first)
    world.auto.drag_mouse.side_effect = lambda *args, **kwargs: setattr(state, "frame", after)
    if recognized:
        assert world.war._move(first, board(a, b, stage="1-1", used=0), a, b) == after
    else:
        with pytest.raises(task.CurrencyWarsError, match="角色移动未确认"):
            world.war._move(first, board(a, b, stage="1-1", used=0), a, b)
    assert world.auto.drag_mouse.call_count == 1
    assert state.clicks == []


def test_move_waits_a_bounded_time_if_the_destination_changes_before_input(monkeypatch, world):
    source, target = slot("bench", 0, CORE), slot("front", 0)
    first = page(Page.BOARD, stage="1-1", capacity=(0, 3))
    changed = page(Page.BOARD, stage="1-1", capacity=(0, 3))
    monkeypatch.setattr(first, "slot_occupied", lambda point: point == source.point)
    monkeypatch.setattr(changed, "slot_occupied", lambda point: point in (source.point, target.point))
    drive(monkeypatch, world, first, after_capture=lambda state: setattr(state, "frame", changed))
    with pytest.raises(task.CurrencyWarsActionUnready, match="已尝试 0 次"):
        world.war._move(first, board(source, target, stage="1-1", used=0), source, target)
    world.auto.drag_mouse.assert_not_called()
    assert 8 <= world.now[0] < 9


def test_deployment_reidentifies_the_changed_portrait_before_replanning(monkeypatch, world):
    old, support = slot("bench", 0, FILLER), slot("bench", 1, BAILU)
    target = slot("front", 0)
    team = board(old, support, target, stage="1-1", used=0)
    updated = replace(old, unit=CORE)
    current = replace(team, slots=(updated, support, target))
    deployed = apply_deployment(current, (updated, target))
    image = CANVAS.copy()
    x, y = old.point
    ImageDraw.Draw(image).rectangle((x - 31, y - 31, x + 31, y + 31), fill=(95, 90, 134))

    def preparation(team):
        frame = Frame(image, ())
        frame.__dict__.update(page=Page.BOARD, stage=team.stage, capacity=(team.used, team.capacity), gold=0)
        units = {s.point: s.unit for s in team.slots if s.unit}
        monkeypatch.setattr(frame, "slots", lambda: team.slots)
        monkeypatch.setattr(frame, "slot_occupied", lambda point: point in units)
        monkeypatch.setattr(frame, "card_role", lambda slot: (units[slot.point].front, units[slot.point].back))
        monkeypatch.setattr(frame, "card_stars", lambda slot: units[slot.point].stars)
        return frame

    changed, landed = preparation(current), preparation(deployed)
    detail = page(Page.DETAIL, (CORE.name, 1610, 228), ("前台", 1575, 279), stage=team.stage)
    support_detail = page(Page.DETAIL, (BAILU.name, 1610, 228), ("后台", 1575, 279), stage=team.stage)
    monkeypatch.setattr(detail, "employee_output", lambda **_: True)
    monkeypatch.setattr(support_detail, "employee_output", lambda **_: False)
    routes = {(changed, old.point): detail, (detail, (12, 12)): changed,
              (changed, support.point): support_detail, (support_detail, (12, 12)): changed}
    state = drive(monkeypatch, world, changed, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    for candidate in (old, support):
        portrait = np.broadcast_to(CANVAS.getpixel(candidate.point), (12, 12, 3)).astype(np.int16)
        world.war.slot_cache[(candidate.zone, candidate.index)] = (portrait, candidate.unit.name, False)

    with pytest.raises(task.CurrencyWarsActionUnready, match="瓦尔特.*卡位肖像已变化") as error:
        world.war._move(changed, team, old, target)
    world.auto.drag_mouse.assert_not_called()
    assert not state.clicks

    recovered = world.war._recover_deployment(team, error.value)
    frame, board_now = world.war._read_board(recovered)
    source, destination = world.war._next_deployment(board_now)
    assert (source.unit.name, destination.point) == (CORE.name, target.point)
    world.auto.drag_mouse.side_effect = lambda *_, **__: setattr(state, "frame", landed) or True
    assert world.war._move(frame, board_now, source, destination) is landed
    assert state.clicks == [(Page.BOARD, old.point), (Page.DETAIL, (12, 12))]
    world.auto.drag_mouse.assert_called_once()


@pytest.mark.parametrize("outcome", ("swap", "stale", "no_receipt"))
def test_core_swap_rechecks_both_stars_and_never_duplicates_an_unconfirmed_move(monkeypatch, world, outcome):
    active = slot("front", 0, replace(CORE, stars=1))
    incoming, spare = slot("bench", 0, CORE), slot("bench", 1)
    b = board(active, incoming, spare, used=1, capacity=1)
    first, second = policy.deployment(b)
    middle = apply_deployment(b, first)
    final = apply_deployment(middle, second)

    def image(team):
        frame = page(Page.BOARD, stage=team.stage, capacity=(team.used, team.capacity))
        occupancy = {s.point: s.unit.stars for s in team.slots if s.unit}
        monkeypatch.setattr(frame, "slot_occupied", lambda p: p in occupancy)
        monkeypatch.setattr(frame, "card_stars", lambda s: occupancy.get(s.point))
        return frame

    before, after_first, after_second = map(image, (b, middle, final))
    changed = image(replace(b, slots=(active, replace(incoming, unit=active.unit), spare)))
    state = drive(monkeypatch, world, before)
    world.war.deployment_moves = (first, second)
    if outcome == "stale":
        state.frame = changed
        with pytest.raises(task.CurrencyWarsActionUnready, match="已尝试 0 次"):
            world.war._move(before, b, *first)
        world.auto.drag_mouse.assert_not_called()
        assert 8 <= world.now[0] < 9
        return

    world.auto.drag_mouse.side_effect = lambda *a, **kw: setattr(state, "frame", after_first) or True
    assert world.war._move(before, b, *first) is after_first
    if outcome == "swap":
        world.auto.drag_mouse.side_effect = lambda *a, **kw: setattr(state, "frame", after_second) or True
        assert world.war._move(after_first, middle, *second) is after_second
        assert world.auto.drag_mouse.call_count == 2
    else:
        world.auto.drag_mouse.side_effect = None
        with pytest.raises(task.CurrencyWarsError, match="已尝试 3 次"):
            world.war._move(after_first, middle, *second)
        assert world.auto.drag_mouse.call_count == 4 and state.frame is after_first
        assert not state.clicks


def test_same_name_move_rechecks_gear_and_halo_before_any_input(monkeypatch, world):
    active = slot("front", 0, replace(CORE, stars=1))
    incoming, spare = slot("bench", 0, CORE), slot("bench", 1)
    b = board(active, incoming, spare, used=1, capacity=1)
    frame = page(Page.BOARD, stage=b.stage, capacity=(1, 1))
    monkeypatch.setattr(frame, "slot_occupied", lambda point: point in {active.point, incoming.point})
    monkeypatch.setattr(frame, "card_stars", lambda slot: slot.unit.stars)
    state = drive(monkeypatch, world, frame)
    for halo, equipped in ((True, 0), (False, 1)):
        world.war.deployment_moves = () if halo else policy.deployment(b)
        monkeypatch.setattr(frame, "assigned_halo", lambda _: halo)
        monkeypatch.setattr(frame, "card_equipment", lambda slot: equipped if slot == active else 0)
        with pytest.raises(task.CurrencyWarsActionUnready):
            world.war._move(frame, b, active, spare)
    world.auto.drag_mouse.assert_not_called()
    assert not state.clicks


def test_same_name_replacement_confirms_halo_after_the_new_copy_lands(monkeypatch, world):
    active = slot("front", 0, replace(CORE, stars=1, has_halo=True))
    incoming, spare = slot("bench", 0, CORE), slot("bench", 1)
    b = board(active, incoming, spare, used=1, capacity=1)
    first, second = policy.deployment(b)
    world.war.deployment_moves = (first, second)
    world.war.held_deployment = first

    def frame_of(team, *, halo=False):
        frame = page(Page.BOARD, stage=team.stage, capacity=(team.used, team.capacity))
        occupants = {s.point: s.unit.stars for s in team.slots if s.unit}
        monkeypatch.setattr(frame, "slot_occupied", lambda point: point in occupants)
        monkeypatch.setattr(frame, "card_stars", lambda s: occupants.get(s.point))
        monkeypatch.setattr(frame, "assigned_halo", lambda point: halo and point == active.point)
        monkeypatch.setattr(frame, "slot_portrait_matches", lambda *_: True)
        return frame

    middle = apply_deployment(b, first, replacing_same_name=True)
    final = apply_deployment(middle, second)
    before = frame_of(b, halo=True)
    waiting = frame_of(final)
    confirmed = frame_of(final, halo=True)
    benched = frame_of(middle)

    def next_observation(state):
        if state.frame is waiting:
            state.frame = confirmed if observed_missing else waiting
            observed_missing.append(state.frame)
        return state.frame

    observed_missing = []
    state = drive(monkeypatch, world, before, after_capture=next_observation)
    world.auto.drag_mouse.side_effect = lambda *a, **k: setattr(state, "frame", benched) or True
    assert world.war._move(before, b, *first) is benched
    world.war.deployment_moves = (second,)
    world.auto.drag_mouse.side_effect = lambda *a, **k: setattr(state, "frame", waiting) or True
    assert world.war._move(benched, middle, *second) is confirmed
    assert observed_missing == [waiting, confirmed]
    assert world.auto.drag_mouse.call_count == 2


@pytest.mark.parametrize("replaced", (False, True))
@pytest.mark.parametrize("result_page", (Page.BOARD, Page.BENCH_FULL))
def test_overflow_move_verifies_source_refilled_by_waiting_employee(monkeypatch, world, replaced, result_page):
    source, destination = slot("bench", 2, FILLER), slot("back", 4)
    first = page(Page.BENCH_FULL, stage="3-3", capacity=(8, 9))
    after = page(result_page, stage="3-3", capacity=(9, 9))
    if replaced:
        after.image = Image.new("RGB", CANVAS.size, (180, 170, 160))
    monkeypatch.setattr(first, "slot_occupied", lambda p: p == source.point)
    monkeypatch.setattr(after, "slot_occupied", lambda p: p in (source.point, destination.point))
    state = drive(monkeypatch, world, first)
    world.auto.drag_mouse.side_effect = lambda *args, **kwargs: setattr(state, "frame", after)
    b = board(source, destination, stage="3-3", used=8, capacity=9)
    if replaced:
        assert world.war._move(first, b, source, destination) is after
    else:
        with pytest.raises(task.CurrencyWarsError, match="角色移动未确认"):
            world.war._move(first, b, source, destination)
    assert world.war.preparation_progress == int(replaced)
    world.auto.drag_mouse.assert_called_once()


@pytest.mark.parametrize("same_portrait", (False, True))
def test_regular_deployment_verifies_the_target_portrait_if_the_bench_slot_is_refilled(
        monkeypatch, world, same_portrait):
    source, destination = slot("bench", 0, CORE), slot("front", 0)
    a, b = source.point, destination.point
    first = page(Page.BOARD, stage="1-1", capacity=(0, 3))
    after = page(Page.BOARD, stage="1-1", capacity=(1, 3))
    first.image = CANVAS.copy()
    draw = ImageDraw.Draw(first.image)
    draw.rectangle((a[0] - 23, a[1] - 27, a[0] + 22, a[1] + 12), fill=(227, 165, 83))
    draw.ellipse((a[0] - 18, a[1] - 21, a[0] + 8, a[1] + 2), fill=(32, 189, 232))
    after.image = CANVAS.copy()
    ImageDraw.Draw(after.image).rectangle((a[0] - 32, a[1] - 33, a[0] + 32, a[1] + 32), fill=(181, 45, 198))
    if same_portrait:
        after.image.paste(first.image.crop((a[0] - 24, a[1] - 30, a[0] + 24, a[1] + 16)),
                          (b[0] - 20, b[1] - 43))
    monkeypatch.setattr(first, "slot_occupied", lambda point: point == a)
    monkeypatch.setattr(after, "slot_occupied", lambda point: point in (a, b))
    state = drive(monkeypatch, world, first)
    world.auto.drag_mouse.side_effect = lambda *args, **kwargs: setattr(state, "frame", after)
    team = board(source, destination, stage="1-1", used=0, capacity=3)
    if same_portrait:
        assert world.war._move(first, team, source, destination) is after
    else:
        with pytest.raises(task.CurrencyWarsError, match="角色移动未确认"):
            world.war._move(first, team, source, destination)
    assert world.auto.drag_mouse.call_count == 1


def test_battle_toggles_once_and_never_acts_on_transient_board(monkeypatch, world):
    off, on, false_board = battle(False), battle(True), page(Page.BOARD)
    end = page(Page.NODE_RESULT)
    frames = iter((off, on, false_board, on, on, end))
    state = drive(monkeypatch, world, off)
    def observe():
        state.frame = world.war.frame = next(frames)
        return state.frame
    monkeypatch.setattr(world.war, "_observe", observe)
    assert world.war._watch_battle(off) == end
    assert state.clicks == [(Page.BATTLE, ui.AUTO_TOGGLE)]
    assert not state.keys
    world.auto.drag_mouse.assert_not_called()


def test_auto_off_uses_the_project_c_template_with_the_battle_hud():
    image = CANVAS.copy()
    with Image.open("assets/images/share/base/not_auto.png") as mark:
        image.paste(mark.convert("RGB"), (16, 913))
    frame = Frame(image, labels(("1-434%", 750, 27)))
    assert frame.auto_off and frame.page == Page.BATTLE
    assert Frame(image, ()).page == Page.UNKNOWN


@pytest.mark.parametrize("hud", (
    (("3-51%", 752, 27),),
    (("3-5", 726, 27), ("1%", 785, 28)),
    (("3-5", 726, 27), ("12％", 785, 28)),
))
def test_battle_progress_is_recognized_during_animations_without_visible_controls(hud):
    frame = Frame(CANVAS, labels(*hud))
    assert frame.combat_progress and frame.page == Page.BATTLE
    assert not frame.auto_off
    conflict = Frame(CANVAS, labels(*hud, ("出战", 1818, 751)))
    assert conflict.page == Page.CONFLICT


def test_a_stage_number_alone_or_separated_hud_text_is_not_a_battle():
    assert Frame(CANVAS, labels(("3-5", 726, 27))).page == Page.UNKNOWN
    assert Frame(CANVAS, labels(("3-5", 726, 27), ("1%", 784, 150))).page == Page.UNKNOWN


@pytest.mark.parametrize(("entries", "expected"), (
    ((("备战阶段", 469, 46), ("2-6", 468, 77), ("6/6", 959, 262),
      ("前台区域", 974, 315), ("后台区域", 976, 575),
      ("商店", 1624, 982), ("出战", 1816, 752)), Page.BOARD),
    ((("3-5", 726, 27), ("1%", 785, 28)), Page.BATTLE),
    ((("我方行动中", 1790, 999),), Page.BATTLE),
    ((("返回货币战争", 1700, 795),), Page.MATCH_RESULT),
    ((("3-5", 726, 27),), Page.UNKNOWN),
))
def test_capture_uses_confirmed_page_anchors_when_battle_templates_fail(monkeypatch, world, entries, expected):
    def unavailable(path):
        assert path in ("share/base/not_auto.png", "screen/currency_wars/s2_auto_button.png",
                        "forgottenhall/pause.png")
        raise OSError("无法读取战斗模板")

    monkeypatch.setattr(ui, "template", unavailable)
    capture = Mock(side_effect=lambda: Frame(CANVAS, labels(*entries)))
    monkeypatch.setattr(world.war, "_capture", capture)

    assert world.war._observe().page == expected
    assert capture.call_count == (task.MAX_CAPTURE_ATTEMPTS if expected == Page.UNKNOWN else 1)


def test_combat_checks_pause_template_when_the_auto_button_template_fails(monkeypatch):
    image = CANVAS.copy()
    pause = ui.template("forgottenhall/pause.png")
    image.paste(Image.fromarray(pause), ui.AUTO_CONTROLS[:2])
    template = ui.template

    def unavailable(path):
        if path == "screen/currency_wars/s2_auto_button.png":
            raise OSError("无法读取自动战斗按钮模板")
        return template(path)

    monkeypatch.setattr(ui, "template", unavailable)
    assert Frame(image, ()).page == Page.BATTLE


def test_unknown_auto_status_keeps_retry_delay_while_battle_continues(monkeypatch, world):
    def unavailable(path):
        assert path == "share/base/not_auto.png"
        raise OSError("无法读取自动战斗状态模板")

    monkeypatch.setattr(ui, "template", unavailable)
    off = battle(False)
    unreadable = [Frame(CANVAS, labels(("3-5", 726, 27), ("1%", 785, 28))) for _ in range(2)]
    result = page(Page.NODE_RESULT)
    pending = iter((off, *unreadable, off, off, result))
    monkeypatch.setattr(world.war, "_capture", lambda: next(pending))

    assert world.war._watch_battle(off) is result
    world.auto.click_element_with_pos.assert_called_once_with(ui.AUTO_TOGGLE, press_duration=task.CLICK_HOLD)
    world.auto.press_key.assert_not_called()
    world.auto.drag_mouse.assert_not_called()


def test_missing_c_frames_cannot_shorten_the_auto_retry_delay(monkeypatch, world):
    off = battle(False)
    missed = Frame(CANVAS, labels(("3-5", 726, 27), ("1%", 785, 28)))
    assert missed.page == Page.BATTLE and missed.auto_off is False
    result = page(Page.NODE_RESULT)
    clicks = []

    def capture(state):
        if len(clicks) == 2:
            state.frame = result
        else:
            state.frame = missed if 2 <= world.now[0] <= 3 else off

    state = drive(monkeypatch, world, off, lambda *_: clicks.append(world.now[0]), capture)
    assert world.war._watch_battle(off) is result
    assert clicks[1] - clicks[0] == task.AUTO_RETRY_SECONDS
    assert state.clicks == [(Page.BATTLE, ui.AUTO_TOGGLE)] * 2


def test_one_c_match_cannot_enable_auto_during_a_transition(monkeypatch, world):
    off, on = battle(False), battle(True)
    end = page(Page.NODE_RESULT)
    frames = iter((page(Page.UNKNOWN), on, end))
    state = drive(monkeypatch, world, off)
    monkeypatch.setattr(world.war, "_observe", lambda: next(frames))
    assert world.war._watch_battle(off) is end
    assert not state.keys and not state.clicks


def test_c_match_only_allows_the_auto_button_in_battle(monkeypatch, world):
    off = battle(False)
    state = drive(monkeypatch, world, off)
    with pytest.raises(task.CurrencyWarsError, match="只开启游戏自动战斗"):
        world.war._tap(off, (1700, 940), enable_auto=True)
    assert not state.clicks


def test_auto_toggle_retries_only_while_the_game_still_shows_auto_off(monkeypatch, world):
    off = battle(False)
    result = page(Page.NODE_RESULT)

    def click(state, _):
        if len(state.clicks) == 2:
            state.frame = result

    state = drive(monkeypatch, world, off, click)
    assert world.war._watch_battle(off) is result
    assert state.clicks == [(Page.BATTLE, ui.AUTO_TOGGLE)] * 2
    assert world.now[0] >= 13
    assert not state.keys


def test_auto_retry_limit_survives_the_next_battle_watch_window(monkeypatch, world):
    off = battle(False)
    state = drive(monkeypatch, world, off)
    monkeypatch.setattr(task, "BATTLE_SECONDS", 15)

    assert world.war._watch_battle(off) is off
    assert world.war._watch_battle(off) is off
    assert state.clicks == [(Page.BATTLE, ui.AUTO_TOGGLE)] * task.MAX_AUTO_ATTEMPTS

    assert world.war._watch_battle(page(Page.NODE_RESULT)).page == Page.NODE_RESULT
    assert world.war._watch_battle(off) is off
    assert state.clicks == [(Page.BATTLE, ui.AUTO_TOGGLE)] * (2 * task.MAX_AUTO_ATTEMPTS)


def test_auto_already_on_waits_until_budget_with_zero_input(monkeypatch, world):
    on = battle(True)
    state = drive(monkeypatch, world, on)
    world.war.deadline = 8
    with pytest.raises(task.CurrencyWarsError, match="总时限"):
        world.war._watch_battle(on)
    assert not state.clicks and not state.keys
    world.auto.drag_mouse.assert_not_called()


def test_stop_inside_battle_keeps_current_page(monkeypatch, world):
    on = battle(True)
    state = drive(monkeypatch, world, on)
    task.pause_ctl.checkpoint.side_effect = RunStopRequested()
    with pytest.raises(RunStopRequested):
        world.war._watch_battle(on)
    assert not state.clicks and not state.keys


def test_weekly_matches_use_one_deadline_and_stop_after_three_launches(monkeypatch, world):
    frame = home()
    drive(monkeypatch, world, frame)
    launch_deadlines = []
    monkeypatch.setattr(world.war, "_launch", lambda f, r: launch_deadlines.append(world.war.deadline) or f)
    monkeypatch.setattr(world.war, "_play", lambda f: setattr(world.war, "result", True) or f)
    scores = iter((0, 6000, 12000, 18000))
    monkeypatch.setattr(world.war, "get_reward", lambda f: (f, (next(scores), 18000), False))
    assert world.war.start(weekly=True)
    assert launch_deadlines == [task.TASK_SECONDS] * 3


def test_elapsed_first_weekly_match_cannot_reset_total_deadline(monkeypatch, world):
    frame = home()
    drive(monkeypatch, world, frame)
    launch = Mock(return_value=frame)
    monkeypatch.setattr(world.war, "_launch", launch)
    monkeypatch.setattr(world.war, "get_reward", lambda f: (f, (0, 18000), False))

    def play(f):
        world.now[0] = task.TASK_SECONDS
        return f

    monkeypatch.setattr(world.war, "_play", play)
    with pytest.raises(task.CurrencyWarsBudgetExceeded, match="总时限"):
        world.war.start(weekly=True)
    launch.assert_called_once()


@pytest.mark.parametrize(("minutes", "expected"), [(120, 7200), (30, 1800), (0, None), (-5, None)])
def test_task_limit_minutes_map_to_seconds(minutes, expected):
    assert task.task_limit_seconds(minutes) == expected


@pytest.mark.parametrize("minutes", (None, "bad", float("inf")))
def test_task_limit_seconds_defaults_to_four_hours_for_missing_or_invalid_values(minutes):
    assert task.task_limit_seconds(minutes) == 4 * 60 * 60


def test_currency_wars_time_limit_zero_runs_without_a_deadline(monkeypatch, world):
    frame = home()
    drive(monkeypatch, world, frame)
    world.cfg.currencywars_time_limit = 0
    deadlines = []
    monkeypatch.setattr(world.war, "_launch", lambda f, r: deadlines.append(world.war.deadline) or f)
    monkeypatch.setattr(world.war, "_play", lambda f: setattr(world.war, "result", True) or f)
    scores = iter((0, 18000))
    monkeypatch.setattr(world.war, "get_reward", lambda f: (f, (next(scores), 18000), False))

    assert world.war.start(weekly=True) is True
    assert deadlines == [None]


def test_recognized_pages_can_continue_after_more_than_sixteen_steps(monkeypatch, world):
    frame = page(Page.CHOICE, stage="1-1")
    next_frame = home()
    drive(monkeypatch, world, frame)
    choose = Mock(side_effect=[frame] * 20 + [next_frame])
    monkeypatch.setattr(world.war, "_choose", choose)
    assert world.war._play(frame) is next_frame
    assert choose.call_count == 21


@pytest.mark.parametrize("next_page", (Page.BATTLE, Page.NODE_RESULT, Page.MATCH_RESULT))
def test_play_allows_battle_or_settlement_after_the_preparation_limit(monkeypatch, world, next_page):
    preparation = page(Page.BOARD, stage="3-5")
    next_frame = page(next_page)
    home = page(Page.HOME)
    play = Mock(side_effect=[preparation] * 15 + [next_frame, home])
    monkeypatch.setattr(world.war, "_play_step", play)
    assert world.war._play(preparation) is home
    assert play.call_count == 17


@pytest.mark.parametrize("paid", (True, False))
def test_same_node_watchdog_distinguishes_experience_credit_from_an_overlay(monkeypatch, world, paid):
    stage = "3-5"
    initial = page(Page.BENCH_FULL, ("购买经验", 298, 864), stage=stage, gold=75, level=9,
                   experience=(68, 72), experience_cost=4, capacity=(9, 9))
    after = (page(Page.BENCH_FULL, stage=stage, gold=71, level=9, experience=(70, 72), capacity=(9, 9))
             if paid else page(Page.CHOICE, stage=stage))
    team = board(stage=stage, gold=75, used=9, capacity=9, level=9, exp=(68, 72))
    home_frame = page(Page.HOME)
    state = drive(monkeypatch, world, initial)
    world.auto.press_key.side_effect = lambda key: (
        state.keys.append((state.frame.page, key)), setattr(state, "frame", after)
    )
    steps = 0

    def step(frame):
        nonlocal steps
        steps += 1
        if steps == 11:
            return world.war._buy_exp(frame, team, 4)
        return home_frame if steps == 22 else frame

    monkeypatch.setattr(world.war, "_play_step", step)
    assert world.war._play(initial) is home_frame and steps == 22
    assert state.keys == [(Page.BENCH_FULL, "f")] and not state.clicks
    assert world.war.preparation_progress == int(paid)


def test_full_bench_experience_batch_uses_f_without_ocr_between_inputs(monkeypatch, world):
    stage = "3-5"
    xp = ("购买经验", 298, 864)
    initial = page(Page.BOARD, xp, stage=stage, gold=50, level=7, experience=(64, 72), experience_cost=4,
                   capacity=(9, 9))
    first_receipt = page(Page.BOARD, xp, stage=stage, gold=46, level=None, experience=(68, 72), experience_cost=4,
                         capacity=(9, 9))
    leveled = page(Page.BOARD, stage=stage, gold=42, level=None, experience=None, capacity=(9, 10))
    team = board(slot("front", 0, CORE), slot("back", 0), slot("bench", 0, BAILU), stage=stage, gold=50,
                 used=9, capacity=9, level=7, exp=(64, 72))
    monkeypatch.setattr(world.war, "_read_board", lambda f, **kwargs: (f, team))
    observations = []

    def capture(s):
        observations.append(len(s.keys))

    state = drive(monkeypatch, world, initial, after_capture=capture)

    def press(key):
        state.keys.append((state.frame.page, key))
        state.frame = first_receipt if len(state.keys) == 1 else leveled

    world.auto.press_key.side_effect = press
    assert world.war._free_reward_slot(initial) is leveled
    assert state.keys == [(Page.BOARD, "f")] * 2 and not state.clicks
    assert 1 not in observations and observations.count(2) >= 2
    assert world.war.preparation_progress == 1
    assert (stage, "经验") not in world.war.deferred_operations


@pytest.mark.parametrize(("gold", "exp", "accepted"), (
    (46, (68, 72), False), (45, (70, 72), False), (47, (70, 72), True), (56, (70, 72), True),
))
def test_experience_receipt_checks_the_budget_and_experience_gain(monkeypatch, world, gold, exp, accepted):
    stage = "3-5"
    xp = ("购买经验", 298, 864)
    initial = page(Page.BOARD, xp, stage=stage, gold=50, level=7, experience=(68, 72), experience_cost=4,
                   capacity=(9, 9))
    receipt = page(Page.BOARD, xp, stage=stage, gold=gold, level=9, experience=exp, experience_cost=4,
                   capacity=(9, 9))
    team = board(stage=stage, gold=50, used=9, capacity=9, level=7, exp=(68, 72))
    state = drive(monkeypatch, world, initial)
    world.auto.press_key.side_effect = lambda key: (
        state.keys.append((state.frame.page, key)), setattr(state, "frame", receipt)
    )
    if accepted:
        assert world.war._buy_exp(initial, team, 4) is receipt
    else:
        with pytest.raises(task.CurrencyWarsError, match="已尝试 1 次"):
            world.war._buy_exp(initial, team, 4)
    assert state.keys == [(Page.BOARD, "f")] and not state.clicks
    assert world.war.preparation_progress == int(accepted)


@pytest.mark.parametrize("experience_after", (None, (22, 48)))
def test_unreadable_experience_uses_one_budgeted_f_probe(monkeypatch, world, experience_after):
    stage = "2-3"
    xp = ("购买经验", 298, 864)
    initial = page(Page.BOARD, xp, stage=stage, gold=40, level=7, experience=None, experience_cost=4,
                   capacity=(7, 7))
    updated = page(Page.BOARD, xp, ("获得经验4", 298, 814), stage=stage, gold=36, level=7,
                   experience=experience_after, experience_cost=4, capacity=(7, 7))
    team = board(slot("front", 0, CORE), slot("back", 0), slot("bench", 0, BAILU), stage=stage,
                 gold=40, used=7, capacity=7, level=7, exp=None)
    state = drive(monkeypatch, world, initial)
    world.auto.press_key.side_effect = lambda key: (
        state.keys.append((state.frame.page, key)), setattr(state, "frame", updated)
    )
    assert world.war._can_buy_exp(team, 4)
    assert not world.war._can_buy_exp(replace(team, gold=3), 4)
    assert world.war._buy_exp(initial, team, 4) is updated
    assert state.keys == [(Page.BOARD, "f")] and not state.clicks
    assert world.war.preparation_progress == 1
    assert not world.war._can_buy_exp(replace(team, gold=36), 4)
    if experience_after is not None:
        assert world.war._can_buy_exp(replace(team, gold=36, exp=experience_after), 4)


def test_an_experience_batch_can_stop_between_f_inputs(monkeypatch, world):
    stage = "3-5"
    frame = page(Page.BOARD, ("购买经验", 298, 864), stage=stage, gold=50, level=9,
                 experience=(64, 72), experience_cost=4, capacity=(9, 9))
    team = board(stage=stage, gold=50, used=9, capacity=9, level=9, exp=(64, 72))
    state = drive(monkeypatch, world, frame)
    original_check = world.war._check_budget

    def check():
        if state.keys:
            raise RunStopRequested()
        original_check()

    monkeypatch.setattr(world.war, "_check_budget", check)
    with pytest.raises(RunStopRequested):
        world.war._buy_exp(frame, team, 4)
    assert state.keys == [(Page.BOARD, "f")] and not state.clicks


def test_preparation_receipts_can_continue_past_the_old_transition_limit(monkeypatch, world):
    frame = page(Page.BENCH_FULL, stage="3-5")
    lobby = home()

    def step(f):
        world.war.preparation_progress += 1
        return lobby if world.war.preparation_progress == 260 else f

    monkeypatch.setattr(world.war, "_play_step", step)
    assert world.war._play(frame) is lobby
    assert world.war.preparation_progress == 260


@pytest.mark.parametrize("failure", (
    task.CurrencyWarsActionUnready, task.CurrencyWarsReceiptTimeout, task.CurrencyWarsError, ValueError,
))
def test_play_replans_from_fresh_frames_after_local_failures(monkeypatch, world, failure):
    frame = page(Page.CHOICE, stage="1-2")
    lobby = home()
    state = drive(monkeypatch, world, frame)
    step = Mock(side_effect=[failure("模拟识别或动作失败")] * 4 + [lobby])
    monkeypatch.setattr(world.war, "_play_step", step)
    assert world.war._play(frame) is lobby
    assert step.call_count == 5
    assert not state.clicks


@pytest.mark.parametrize("transition", (
    "result", "result_after_escape", "result_after_unmapped_abandon", "result_after_failed_abandon",
    "loss_after_failed_abandon", "fight_confirm", "already_open_exit",
    "failed_escape", "late_shop", "board_advanced",
))
def test_stuck_preparation_respects_late_original_match_updates(monkeypatch, world, transition):
    stage = "3-7"
    blocked = page(Page.BOARD, ("出战", 1818, 751), stage=stage, capacity=(1, 3))
    blocked.field_slots = lambda: (slot("front", 0, CORE), slot("back", 0))
    confirm_point, return_point = (963, 694), (960, 899)
    fight_confirm = page(Page.CONFIRM_FIGHT, ("确认", *confirm_point), stage=stage)
    prompt = active_match_exit_dialog()
    resumed = page(Page.BOARD, stage=stage, capacity=(1, 4))
    resumed.field_slots = blocked.field_slots
    shop = page(Page.SHOP, ("收起", 1624, 983), stage=stage)
    wins = transition != "loss_after_failed_abandon"
    result = page(Page.MATCH_RESULT, ("对局胜利" if wins else "对局失败", 960, 233),
                  ("返回货币战争", *return_point))
    lobby = home()
    menu = mode(("进入标准博弈", 1692, 961))
    routes = {
        (fight_confirm, confirm_point): resumed,
        (shop, (1624, 983)): resumed,
        (result, return_point): lobby,
        (lobby, (1600, 972)): menu,
    }
    state = SimpleNamespace(frame=blocked, clicks=[], keys=[], advances=0, receipts=[])
    def prepare(frame):
        if frame is blocked:
            world.war.stage_refreshes[stage] = 2
            world.war.deferred_operations.add((stage, "商店"))
            raise task.CurrencyWarsActionUnready("备战画面未更新")
        assert frame is resumed
        state.receipts.append((world.war.stage_refreshes.get(stage), (stage, "商店") in world.war.deferred_operations))
        state.frame = result
        return world.war._observe()

    def advance_existing_team():
        state.advances += 1
        if state.advances == task.MAX_PREPARATION_FALLBACKS:
            if transition == "result":
                state.frame = result
            elif transition == "fight_confirm":
                state.frame = fight_confirm
            elif transition == "already_open_exit":
                state.frame = prompt
            elif transition == "late_shop":
                state.frame = shop
            elif transition == "board_advanced":
                state.frame = resumed
        return blocked

    original_find = world.auto.find_element.side_effect

    def find(target, *args, **kwargs):
        point = original_find(target, *args, **kwargs)
        if transition == "result_after_unmapped_abandon" and state.frame is prompt and point == (770, 743):
            state.frame = result
            return None
        return point

    def click(point, *, press_duration):
        state.clicks.append((state.frame, point))
        if transition in ("result_after_failed_abandon", "loss_after_failed_abandon") and state.frame is prompt:
            assert point == (770, 743)
            state.frame = result
            return False
        state.frame = routes[state.frame, point]
        return True

    def press(key):
        state.keys.append((state.frame.page, key))
        if transition == "result_after_escape":
            state.frame = result
        elif (state.frame is blocked and transition in ("result_after_unmapped_abandon",
                                                        "result_after_failed_abandon", "loss_after_failed_abandon")):
            state.frame = prompt
        elif transition == "failed_escape" and state.frame is blocked:
            state.frame = prompt
            return False
        elif state.frame is prompt:
            state.frame = resumed
        return True

    on_result = Mock()
    launched = Mock(return_value=lobby)
    rewards = Mock(side_effect=lambda f: (f, (18000, 18000), False))
    monkeypatch.setattr(world.war, "_capture", lambda: state.frame)
    monkeypatch.setattr(world.war, "_prepare", prepare)
    monkeypatch.setattr(world.war, "_advance_existing_team", advance_existing_team)
    monkeypatch.setattr(world.war, "_on_match_result", on_result)
    monkeypatch.setattr(world.war, "_enter_with_recovery", launched)
    monkeypatch.setattr(world.war, "_check_weekly_reward", rewards)
    world.auto.find_element.side_effect = find
    world.auto.click_element_with_pos.side_effect = click
    world.auto.press_key.side_effect = press

    assert world.war.start(resume=True) is wins
    on_result.assert_called_once_with(result)
    rewards.assert_called_once_with(lobby)
    launched.assert_not_called()
    assert state.advances == task.MAX_PREPARATION_FALLBACKS
    expected_keys = {
        "result_after_escape": [(Page.BOARD, "esc")],
        "result_after_unmapped_abandon": [(Page.BOARD, "esc")],
        "result_after_failed_abandon": [(Page.BOARD, "esc")],
        "loss_after_failed_abandon": [(Page.BOARD, "esc")],
        "already_open_exit": [(Page.END_MATCH_CONFIRM, "esc")],
        "failed_escape": [(Page.BOARD, "esc"), (Page.END_MATCH_CONFIRM, "esc")],
    }
    assert state.keys == expected_keys.get(transition, [])
    expected = {
        "fight_confirm": [(fight_confirm, confirm_point)],
        "late_shop": [(shop, (1624, 983))],
        "result_after_failed_abandon": [(prompt, (770, 743))],
        "loss_after_failed_abandon": [(prompt, (770, 743))],
    }
    assert state.clicks == [*expected.get(transition, ()), (result, return_point)]
    resumes_board = ("fight_confirm", "already_open_exit", "failed_escape", "late_shop", "board_advanced")
    assert state.receipts == ([(2, True)] if transition in resumes_board else [])


def test_preexisting_in_match_exit_prompt_is_cancelled_after_blocked_choice(monkeypatch, world):
    stage = "2-3"
    initial = page(Page.CHOICE, stage=stage, choice="遭遇节点")
    prompt = active_match_exit_dialog()
    ready = page(Page.BOARD, stage=stage)
    return_point = (960, 899)
    won = page(Page.MATCH_RESULT, ("对局胜利", 960, 233), ("返回货币战争", *return_point))
    lobby = home()
    state = SimpleNamespace(frame=initial, clicks=[], keys=[])

    def choose(frame):
        state.frame = prompt
        raise task.CurrencyWarsPageBlocked(frame, "遭遇选择未确认")

    def press(key):
        state.keys.append((state.frame, key))
        if state.frame is prompt and key == "esc":
            state.frame = ready

    def prepare(frame):
        assert frame is ready
        state.frame = won
        return world.war._observe()

    def click(point, *, press_duration):
        state.clicks.append((state.frame, point))
        if state.frame is won and point == return_point:
            state.frame = lobby
        return True

    launched = Mock(return_value=lobby)
    rewards = Mock(side_effect=lambda f: (f, (18000, 18000), False))
    monkeypatch.setattr(world.war, "_capture", lambda: state.frame)
    monkeypatch.setattr(world.war, "_choose", choose)
    monkeypatch.setattr(world.war, "_prepare", prepare)
    monkeypatch.setattr(world.war, "_enter_with_recovery", launched)
    monkeypatch.setattr(world.war, "_check_weekly_reward", rewards)
    world.auto.press_key.side_effect = press
    world.auto.click_element_with_pos.side_effect = click

    assert world.war.start(resume=True)
    assert state.keys == [(prompt, "esc")]
    assert state.clicks == [(won, return_point)]
    launched.assert_not_called()
    rewards.assert_called_once_with(lobby)


@pytest.mark.parametrize("response", ("board", "quit_prompt", "unchanged", "flicker", "stop", "budget"))
def test_play_tries_one_escape_at_a_blocked_choice_page(monkeypatch, world, response):
    stage = "2-3"
    initial = page(Page.CHOICE, stage=stage, choice="遭遇节点")
    ready = page(Page.BOARD, stage=stage, capacity=(1, 3))
    ready.field_slots = lambda: (slot("front", 0, CORE), slot("back", 0))
    lobby = home()
    state = drive(monkeypatch, world, initial)
    failure = task.CurrencyWarsPageBlocked(initial, "遭遇选择未确认")
    world.war.deadline = 60

    def step(f):
        if f is initial:
            world.war.stage_refreshes[stage] = 1
            raise failure
        assert f is ready
        assert world.war.stage_refreshes[stage] == 1
        assert (stage, "晶矿") in world.war.deferred_operations
        return lobby

    def press(key):
        assert key == "esc"
        state.keys.append(key)
        if response == "board":
            state.frame = ready
        elif response == "quit_prompt":
            state.frame = active_match_exit_dialog()
        elif response == "flicker":
            state.frame = page(Page.CHOICE, choice="遭遇节点")
        elif response == "stop":
            task.pause_ctl.checkpoint.side_effect = RunStopRequested()
        elif response == "budget":
            world.now[0] = 60
        return True

    monkeypatch.setattr(world.war, "_play_step", step)
    world.auto.press_key.side_effect = press
    if response == "board":
        assert world.war._play(initial) is lobby
    else:
        expected = {"quit_prompt": task.CurrencyWarsRestartRequested, "unchanged": task.CurrencyWarsUnavailable,
                    "flicker": task.CurrencyWarsUnavailable, "stop": RunStopRequested,
                    "budget": task.CurrencyWarsBudgetExceeded}[response]
        with pytest.raises(expected) as caught:
            world.war._play(initial)
        if response in ("unchanged", "flicker"):
            assert caught.value is failure
        elif response == "quit_prompt":
            assert caught.value.frame.page == Page.END_MATCH_CONFIRM
    assert state.keys == ["esc"] and not state.clicks


@pytest.mark.parametrize("title", ("投资环境", "请选择投资策略", "补给阶段"))
def test_exhausted_mandatory_choice_keeps_the_choice_error(monkeypatch, world, title):
    initial = page(Page.CHOICE, choice=title)
    blocked = task.CurrencyWarsPageBlocked(initial, f"{title}仍无法提交")
    drive(monkeypatch, world, initial)
    monkeypatch.setattr(world.war, "_play_step", Mock(side_effect=blocked))
    with pytest.raises(task.CurrencyWarsUnavailable, match="仍无法提交"):
        world.war._play(initial)
    world.auto.press_key.assert_not_called()


def test_node_number_flicker_does_not_reset_choice_failure_limit(monkeypatch, world):
    stage = "2-3"
    visible = page(Page.CHOICE, stage=stage, choice="遭遇节点")
    missed = page(Page.CHOICE, choice="遭遇节点")
    ready = page(Page.BOARD, stage=stage, capacity=(1, 3))
    ready.field_slots = lambda: (slot("front", 0, CORE), slot("back", 0))
    lobby = home()
    state = drive(monkeypatch, world, visible)
    failures = []

    def step(frame):
        if frame is ready:
            return lobby
        failures.append(frame)
        state.frame = missed if frame is visible else visible
        if len(failures) > task.MAX_PAGE_FAILURES:
            raise RunStopRequested()
        raise task.CurrencyWarsActionUnready("遭遇选择未确认")

    def press(key):
        state.keys.append(key)
        state.frame = ready
        return True

    monkeypatch.setattr(world.war, "_play_step", step)
    world.auto.press_key.side_effect = press
    assert world.war._play(visible) is lobby
    assert len(failures) == task.MAX_PAGE_FAILURES
    assert state.keys == ["esc"]


def test_escape_recovery_preserves_terminal_disconnect_reason(monkeypatch, world):
    initial = page(Page.CHOICE, choice="遭遇节点", stage="2-3")
    state = SimpleNamespace(frame=initial)
    monkeypatch.setattr(world.war, "_capture", lambda: state.frame)
    monkeypatch.setattr(world.war, "_choose", Mock(side_effect=task.CurrencyWarsPageBlocked(initial, "遭遇选择未确认")))

    def press(key):
        assert key == "esc"
        state.frame = page(Page.DISCONNECTED)
        return True

    world.auto.press_key.side_effect = press
    with pytest.raises(task.CurrencyWarsUnavailable, match="未确认云游戏连接恢复"):
        world.war.start(resume=True)
    world.auto.press_key.assert_called_once_with("esc")
    world.auto.click_element_with_pos.assert_not_called()


@pytest.mark.parametrize("unreadable_last_frame", (False, True))
def test_native_exit_cancel_has_a_local_limit_without_task_deadline(monkeypatch, world, unreadable_last_frame):
    world.cfg.currencywars_time_limit = 0
    initial = page(Page.CHOICE, choice="遭遇节点", stage="2-3")
    prompt = active_match_exit_dialog()
    state = SimpleNamespace(frame=initial, attempts=0)
    monkeypatch.setattr(world.war, "_capture", lambda: state.frame)

    def choose(frame):
        state.frame = prompt
        raise task.CurrencyWarsPageBlocked(frame, "遭遇选择未确认")

    def press(key):
        assert key == "esc" and state.frame is prompt
        state.attempts += 1
        if state.attempts > 2:
            raise RunStopRequested()
        if state.attempts == 2 and unreadable_last_frame:
            state.frame = page(Page.UNKNOWN)
        return False

    monkeypatch.setattr(world.war, "_choose", choose)
    world.auto.press_key.side_effect = press
    with pytest.raises(task.CurrencyWarsUnavailable, match="无法取消局内退局弹窗"):
        world.war.start(resume=True)
    assert state.attempts == 2
    world.auto.click_element_with_pos.assert_not_called()


def test_preparation_failure_can_use_the_visible_fight_button(monkeypatch, world):
    frame = page(Page.BOARD, ("出战", 1817, 751), stage="1-2", capacity=(1, 2))
    monkeypatch.setattr(frame, "slots", lambda: (slot("front", 0, CORE),))
    fighting = battle(True)
    lobby = home()
    prep = Mock(side_effect=task.CurrencyWarsReadTimeout("未能核对部署人数"))
    monkeypatch.setattr(world.war, "_prepare", prep)
    monkeypatch.setattr(world.war, "_watch_battle", lambda _: lobby)
    state = drive(monkeypatch, world, frame, lambda s, _: setattr(s, "frame", fighting))
    assert world.war._play(frame) is lobby
    assert prep.call_count == 2
    assert state.clicks == [(Page.BOARD, (1817, 751))]


def test_takeover_reopens_normal_preparation_when_no_existing_employee_can_fight(monkeypatch, world):
    stage = "1-1"
    shop_point = (1624, 983)
    fight_point = (1818, 751)
    offer = policy.Offer(CORE.name, 1, (470, 192), 0, front=True)
    front, rear, reserve = slot("front", 0), slot("back", 0), slot("bench", 0)

    def preparation(cells, used, gold):
        frame = page(Page.BOARD, ("商店", *shop_point), ("出战", *fight_point),
                     stage=stage, capacity=(used, 2), gold=gold)
        monkeypatch.setattr(frame, "field_slots", lambda: cells[:2])
        monkeypatch.setattr(frame, "slots", lambda: cells)
        monkeypatch.setattr(frame, "slot_occupied", lambda point: any(s.point == point and s.occupied for s in cells))
        monkeypatch.setattr(frame, "card_role", lambda _: (True, False))
        monkeypatch.setattr(frame, "card_stars", lambda *args, **kwargs: 1)
        return frame

    initial = preparation((front, rear, reserve), 0, 10)
    recruited = preparation((front, rear, replace(reserve, occupied=True)), 0, 9)
    deployed = preparation((replace(front, occupied=True), rear, reserve), 1, 9)
    shop = page(Page.SHOP, ("收起", *shop_point), stage=stage, gold=10, offers=(offer,))
    sold = page(Page.SHOP, ("收起", *shop_point), stage=stage, gold=9, offers=())
    empty_shop = page(Page.SHOP, ("收起", *shop_point), stage=stage, gold=9, offers=())
    monkeypatch.setattr(sold, "shop_changed", lambda older, column: older is shop and column == 0)
    detail = page(Page.DETAIL, (CORE.name, 1610, 228), ("前台", 1575, 279), stage=stage)
    fighting = battle(True)
    won = page(Page.MATCH_RESULT, ("对局胜利", 960, 233), ("返回货币战争", 960, 899))
    lobby = home()
    initial_reads = 0

    def read_initial_slots():
        nonlocal initial_reads
        initial_reads += 1
        if initial_reads <= 2:
            raise task.CurrencyWarsReadTimeout("短暂未识别棋盘卡位")
        return front, rear, reserve

    monkeypatch.setattr(initial, "slots", read_initial_slots)
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))
    world.cfg.currencywars_fast_mode = True
    monkeypatch.setattr(task, "TASK_SECONDS", 25)
    routes = {(initial, shop_point): shop, (shop, offer.point): sold, (sold, shop_point): recruited,
              (recruited, reserve.point): detail, (detail, (12, 12)): recruited,
              (deployed, shop_point): empty_shop, (empty_shop, shop_point): deployed,
              (deployed, fight_point): fighting, (won, (960, 899)): lobby}

    def capture(state):
        if state.frame is fighting and world.now[0] >= 2:
            state.frame = won

    state = drive(monkeypatch, world, initial, lambda s, p: setattr(s, "frame", routes[s.frame, p]), capture)

    def deploy(source, destination, **kwargs):
        assert state.frame is recruited
        assert source == (reserve.point[0] / 1920, reserve.point[1] / 1080)
        assert destination == (front.point[0] / 1920, front.point[1] / 1080)
        state.frame = deployed
        return True

    world.auto.drag_mouse.side_effect = deploy
    assert world.war.start(resume=True) is True
    assert initial_reads > 2
    assert state.clicks.count((Page.SHOP, offer.point)) == 1
    assert state.clicks.count((Page.BOARD, fight_point)) == 1
    assert all(page != Page.BATTLE for page, _ in state.clicks)
    world.auto.drag_mouse.assert_called_once()


@pytest.mark.parametrize("over_capacity", (False, True))
def test_takeover_bounds_unplayable_preparation_and_keeps_the_board(monkeypatch, world, over_capacity):
    stage = "1-1"
    cells = (slot("front", 0, occupied=over_capacity), slot("back", 0, occupied=over_capacity))
    used = 2 if over_capacity else 0
    initial = page(Page.BOARD, ("出战", 1818, 751), stage=stage, capacity=(used, 1), gold=0)
    monkeypatch.setattr(initial, "field_slots", lambda: cells)
    monkeypatch.setattr(initial, "slots", lambda: cells)
    monkeypatch.setattr(initial, "card_role", lambda _: (False, False))
    monkeypatch.setattr(initial, "card_stars", lambda *args, **kwargs: None)
    monkeypatch.setattr(task, "TASK_SECONDS", 25)
    state = drive(monkeypatch, world, initial)

    with pytest.raises(task.CurrencyWarsUnavailable, match="1-1.*重开未完成"):
        world.war.start(resume=True)

    assert world.now[0] < task.TASK_SECONDS
    assert state.frame is initial and not state.clicks
    assert state.keys == [(Page.BOARD, "esc")] * 2
    world.auto.drag_mouse.assert_not_called()


@pytest.mark.parametrize("recovers", (True, False))
def test_takeover_rechecks_zero_input_deployment_after_the_first_fallback(monkeypatch, world, recovers):
    stage = "1-1"
    fight = (1818, 751)
    source, target, rear = slot("bench", 0, CORE), slot("front", 0), slot("back", 0)
    team = board(target, rear, source, stage=stage, gold=0, used=0)
    deployed = apply_deployment(team, (source, target))

    def preparation(current, flicker=False):
        image = CANVAS.copy()
        if flicker:
            x, y = target.point
            ImageDraw.Draw(image).rectangle((x - 19, y - 9, x + 19, y + 9), fill=(70, 65, 109))
        frame = Frame(image, labels(("出战", *fight)))
        frame.__dict__.update(page=Page.BOARD, stage=stage, gold=0, capacity=(current.used, current.capacity))
        monkeypatch.setattr(frame, "field_slots", lambda: current.slots[:2])
        monkeypatch.setattr(frame, "slots", lambda: current.slots)
        monkeypatch.setattr(frame, "slot_occupied", lambda p: any(s.point == p and s.occupied for s in current.slots))
        monkeypatch.setattr(frame, "deployed_copy", lambda *_: None)
        return frame

    still, flickering = preparation(team), preparation(team, flicker=True)
    ready, fighting, lobby = preparation(deployed), battle(True), home()
    won = page(Page.MATCH_RESULT, ("对局胜利", 960, 233), ("返回货币战争", 960, 899))
    recovered = False
    misses = []
    recover = world.war._recover_default_board

    def recover_board(stage, operation, error):
        nonlocal recovered
        if operation == "上阵":
            assert isinstance(error, task.CurrencyWarsActionUnready)
            assert "已尝试 0 次" in str(error)
            misses.append(error)
            recovered = recovers
        return recover(stage, operation, error)

    def read_team(frame, **_):
        return frame, deployed if frame is ready else team

    def capture(state):
        if state.frame in (still, flickering):
            state.frame = still if recovered or state.frame is flickering else flickering
        elif state.frame is fighting:
            state.frame = won

    monkeypatch.setattr(world.war, "_read_board", read_team)
    monkeypatch.setattr(world.war, "_read_default_board", read_team)
    monkeypatch.setattr(world.war, "_collect_preparation_rewards", lambda f: (f, True))
    monkeypatch.setattr(world.war, "_equip", lambda f, _: f)
    monkeypatch.setattr(world.war, "_recover_default_board", recover_board)
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))
    monkeypatch.setattr(task, "TASK_SECONDS", 90)
    routes = {(ready, fight): fighting, (won, (960, 899)): lobby}
    state = drive(monkeypatch, world, still, lambda s, p: setattr(s, "frame", routes[s.frame, p]), capture)

    def drag(start, end, **_):
        assert recovered and state.frame is still
        assert start == (source.point[0] / 1920, source.point[1] / 1080)
        assert end == (target.point[0] / 1920, target.point[1] / 1080)
        state.frame = ready
        return True

    world.auto.drag_mouse.side_effect = drag
    if recovers:
        assert world.war.start(resume=True) is True
        assert len(misses) == 1
        world.auto.drag_mouse.assert_called_once()
        assert state.clicks.count((Page.BOARD, fight)) == 1
    else:
        with pytest.raises(task.CurrencyWarsUnavailable, match="1-1.*重开未完成"):
            world.war.start(resume=True)
        assert misses and not state.clicks
        assert state.keys == [(Page.BOARD, "esc")] * 2
        world.auto.drag_mouse.assert_not_called()
    assert world.now[0] < task.TASK_SECONDS


def test_visible_fight_remains_usable_when_only_the_deployment_count_raises(monkeypatch, world):
    frame = page(Page.BOARD, ("出战", 1817, 751), stage="1-2")
    monkeypatch.setattr(frame, "field_slots", lambda: (slot("front", 0, CORE),))

    def unreadable(_):
        raise RuntimeError("读取部署人数失败")

    monkeypatch.setattr(Frame, "capacity", property(unreadable))
    fighting = battle(True)
    state = drive(monkeypatch, world, frame, lambda s, _: setattr(s, "frame", fighting))
    assert world.war._advance_existing_team() is fighting
    assert state.clicks == [(Page.BOARD, (1817, 751))]


@pytest.fixture
def fuel_ticket_reward(monkeypatch, world):
    monkeypatch.setattr(task, "TASK_SECONDS", 60)
    monkeypatch.setattr(task.screen, "change_to", Mock())
    lobby = home()
    pending = page(Page.WEEKLY, ("18000/18000", 273, 740), claim_available=lambda: True)
    credited = page(Page.WEEKLY, ("18000/18000", 273, 740), claim_available=lambda: False)
    receipt = page(Page.REWARD_RECEIPT, ("点击空白处关闭", 960, 910))
    partial = page(Page.REWARD_RECEIPT, ("点击空白处关闭", 960, 910))
    message = ("背包内助燃券持有数量已达上限。", 956, 580)
    limit = Frame(CANVAS, labels(message, ("清理", 774, 708), ("前往使用", 1188, 708), ("X", 1462, 378)))
    missing_button = Frame(CANVAS, labels(message, ("前往使用", 1188, 708), ("X", 1462, 378)))
    destroy_labels = labels(("提示", 959, 331), ("此次销毁将无物品返还，销毁物品如下：", 953, 418),
                            ("已销毁的物品无法复原", 960, 686), ("取消", 770, 754), ("确认", 1187, 754))
    confirmation = Frame(CANVAS, destroy_labels)
    missing_confirmation = Frame(CANVAS, destroy_labels[:-1])
    unknown = page(Page.UNKNOWN, ("确认清理", 960, 708))
    result = page(Page.MATCH_RESULT, ("对局胜利", 960, 233), ("返回货币战争", 960, 899))
    ready = page(Page.BOARD, stage="3-7")
    scene = SimpleNamespace(flow="auto", fault=None, cleaned=False, confirm=False, confirmed=False,
                            release=None, misses=0, following=[])

    def click(state, point):
        if state.frame is lobby and point == (381, 961):
            state.frame = pending
        elif state.frame is pending and point == (1640, 728):
            if scene.cleaned:
                state.frame = pending if scene.fault == "reclaim_stalls" else receipt
            else:
                state.frame = partial if scene.flow == "after_receipt" else limit
        elif state.frame is partial and point == (960, 910):
            state.frame = limit
        elif state.frame is limit and point == (774, 708):
            assert not scene.cleaned
            scene.cleaned = True
            target = pending if scene.flow == "reclaim" else receipt
            if scene.confirm:
                state.frame = confirmation
                return
            if scene.fault in ("late_receipt", "transition"):
                scene.release = (world.now[0] + (11 if scene.fault == "late_receipt" else 2), target)
                state.frame = limit if scene.fault == "late_receipt" else unknown
            elif scene.fault == "persistent_limit":
                pass
            elif scene.fault == "unknown_confirmation":
                state.frame = unknown
            else:
                state.frame = target
            if scene.fault == "missing_input_receipt":
                raise OSError("清理已送达，但输入回执丢失")
        elif state.frame is confirmation and point == (1187, 754):
            assert not scene.confirmed
            scene.confirmed = True
            if scene.fault != "confirmation_stalls":
                state.frame = pending if scene.flow == "reclaim" else receipt
            if scene.fault == "missing_confirmation_receipt":
                raise OSError("销毁确认已送达，但输入回执丢失")
        elif state.frame is receipt and point == (960, 910):
            state.frame = credited
        elif state.frame is limit and point == (1462, 378):
            state.frame = pending
        elif state.frame is result and point == (960, 899):
            state.frame = lobby
        else:
            pytest.fail(f"非预期输入：{state.frame.page} {point}")

    state = drive(monkeypatch, world, lobby, click)
    # 保留任务的真实观察重试、导航、输入与回执处理，只替换游戏提供的画面。
    monkeypatch.setattr(world.war, "_observe", task.CurrencyWars._observe.__get__(world.war))

    def capture():
        if scene.release and world.now[0] >= scene.release[0]:
            state.frame = scene.release[1]
            scene.release = None
        if state.frame is limit:
            if scene.fault == "persistent_capture" or scene.fault == "capture_once" and not scene.misses:
                scene.misses += 1
                raise OSError("截图暂不可用")
            if scene.fault == "ocr_once" and not scene.misses:
                scene.misses += 1
                raise task.CurrencyWarsReadTimeout("OCR 识别暂时失败")
            if scene.fault == "button_once" and not scene.misses:
                scene.misses += 1
                return missing_button
        if state.frame is confirmation and scene.fault == "confirmation_button_once" and not scene.misses:
            scene.misses += 1
            return missing_confirmation
        return state.frame

    monkeypatch.setattr(world.war, "_capture", capture)

    def map_point(target, *args, **kwargs):
        point = tuple(round(value * scale) for value, scale in zip(target[:2], (1920, 1080)))
        if point == (774, 708):
            if scene.fault == "mapping_once" and not scene.misses:
                scene.misses += 1
                return None
            if scene.fault == "timeout_in_mapping":
                world.now[0] = world.war.deadline
            if scene.fault == "stop_in_mapping":
                task.pause_ctl.checkpoint.side_effect = RunStopRequested("用户停止")
        if point == (1187, 754):
            if scene.fault == "confirmation_timeout_in_mapping":
                world.now[0] = world.war.deadline
            if scene.fault == "confirmation_stop_in_mapping":
                task.pause_ctl.checkpoint.side_effect = RunStopRequested("用户停止")
        return point

    world.auto.find_element.side_effect = map_point
    world.auto.press_key.side_effect = lambda key: (
        state.keys.append((state.frame.page, key)), setattr(state, "frame", lobby))

    def run(entry="weekly"):
        if entry != "weekly":
            state.frame = ready

            def finish_battle(frame):
                assert frame is ready
                state.frame = result
                return result

            monkeypatch.setattr(world.war, "_prepare", finish_battle)
        if entry == "full":
            from tasks.daily import daily
            monkeypatch.setattr(daily, "CurrencyWars", lambda: world.war)
            monkeypatch.setattr(daily.plan, "select_steps", lambda order, cfg, actions, **kwargs: [
                ("货币战争", actions["currencywars"]),
                ("后续任务", lambda: scene.following.append(True)),
            ])
            return daily.Daily.start()
        return world.war.start(weekly=entry == "weekly", loop=entry == "loop", resume=entry == "resume")

    scene.state, scene.run = state, run
    return scene


@pytest.mark.parametrize("entry", ("weekly", "single", "loop", "resume", "full"))
@pytest.mark.parametrize("flow", ("auto", "reclaim", "after_receipt"))
@pytest.mark.parametrize("confirmation", (False, True))
def test_fuel_ticket_limit_cleans_and_finishes_reward(world, fuel_ticket_reward, entry, flow, confirmation):
    scene = fuel_ticket_reward
    scene.flow = flow
    scene.confirm = confirmation
    assert scene.run(entry)
    assert scene.state.clicks.count((Page.REWARD_LIMIT, (774, 708))) == 1
    assert scene.state.clicks.count((Page.WEEKLY, (1640, 728))) == (2 if flow == "reclaim" else 1)
    assert not any(point in ((1462, 378), (1188, 708)) for _, point in scene.state.clicks)
    assert scene.confirmed is confirmation
    assert sum(point == (1187, 754) for _, point in scene.state.clicks) == int(confirmation)
    assert not world.war.weekly_reward_pending
    world.cfg.save_timestamp.assert_called_once_with("currencywars_timestamp")
    assert sum(call.args[0] == "货币战争奖励已领取"
               for call in task.Base.send_notification_with_screenshot.call_args_list) == 1
    if entry == "full":
        assert scene.following == [True]
    if entry != "weekly":
        assert world.war.result is True


@pytest.mark.parametrize("fault", (
    "capture_once", "ocr_once", "button_once", "mapping_once", "late_receipt", "transition", "missing_input_receipt",
))
def test_fuel_ticket_reward_recovers_local_faults(world, fuel_ticket_reward, fault):
    scene = fuel_ticket_reward
    scene.fault = fault
    assert scene.run()
    assert scene.state.clicks.count((Page.REWARD_LIMIT, (774, 708))) == 1
    assert scene.state.clicks.count((Page.WEEKLY, (1640, 728))) == 1
    assert not world.war.weekly_reward_pending
    world.cfg.save_timestamp.assert_called_once_with("currencywars_timestamp")


@pytest.mark.parametrize("fault", ("confirmation_button_once", "missing_confirmation_receipt", "confirmation_stalls"))
def test_fuel_ticket_reward_confirmation_is_bounded(world, fuel_ticket_reward, fault):
    scene = fuel_ticket_reward
    scene.confirm = True
    scene.fault = fault
    assert scene.run() is (fault != "confirmation_stalls")
    assert scene.state.clicks.count((Page.REWARD_LIMIT, (774, 708))) == 1
    assert sum(point == (1187, 754) for _, point in scene.state.clicks) == 1
    assert world.war.weekly_reward_pending is (fault == "confirmation_stalls")
    assert world.cfg.save_timestamp.call_count == int(fault != "confirmation_stalls")


@pytest.mark.parametrize("fault,exception", (
    ("confirmation_timeout_in_mapping", task.CurrencyWarsBudgetExceeded),
    ("confirmation_stop_in_mapping", RunStopRequested),
))
def test_fuel_ticket_reward_confirmation_honors_stop_and_budget(world, fuel_ticket_reward, fault, exception):
    scene = fuel_ticket_reward
    scene.confirm = True
    scene.fault = fault
    with pytest.raises(exception):
        scene.run()
    assert scene.cleaned and not scene.confirmed
    assert len(scene.state.clicks) == 3
    world.cfg.save_timestamp.assert_not_called()


def test_unrelated_destruction_confirmation_is_not_accepted(monkeypatch, world):
    confirmation = Frame(CANVAS, labels(
        ("此次销毁将无物品返还，销毁物品如下：", 953, 418),
        ("已销毁的物品无法复原", 960, 686), ("取消", 770, 754), ("确认", 1187, 754)))
    state = drive(monkeypatch, world, confirmation)
    world.war._check_weekly_reward(confirmation)
    assert state.clicks == state.keys == []
    world.cfg.save_timestamp.assert_not_called()


@pytest.mark.parametrize("fault", ("persistent_limit", "unknown_confirmation", "reclaim_stalls"))
def test_fuel_ticket_reward_failure_stays_pending_without_repeated_cleanup(world, fuel_ticket_reward, fault):
    scene = fuel_ticket_reward
    scene.fault = fault
    if fault == "reclaim_stalls":
        scene.flow = "reclaim"
    assert not scene.run()
    assert scene.state.clicks.count((Page.REWARD_LIMIT, (774, 708))) == 1
    assert scene.state.clicks.count((Page.WEEKLY, (1640, 728))) == (2 if fault == "reclaim_stalls" else 1)
    assert world.war.weekly_reward_pending
    assert world.now[0] < 60
    world.cfg.save_timestamp.assert_not_called()


@pytest.mark.parametrize("fault,exception", (
    ("persistent_capture", task.CurrencyWarsUnavailable),
    ("timeout_in_mapping", task.CurrencyWarsBudgetExceeded),
    ("stop_in_mapping", RunStopRequested),
))
def test_fuel_ticket_reward_stops_before_further_input(monkeypatch, world, fuel_ticket_reward, fault, exception):
    scene = fuel_ticket_reward
    scene.fault = fault
    monkeypatch.setattr(task, "TASK_SECONDS", 30)
    with pytest.raises(exception):
        scene.run()
    assert scene.state.clicks == [(Page.HOME, (381, 961)), (Page.WEEKLY, (1640, 728))]
    world.cfg.save_timestamp.assert_not_called()


def test_failed_reward_does_not_write_completed_timestamp(monkeypatch, world):
    lobby = home()
    weekly = page(Page.WEEKLY, ("18000/18000", 273, 740))
    monkeypatch.setattr(weekly, "claim_available", lambda: True)
    limit = page(Page.REWARD_LIMIT)
    state = drive(monkeypatch, world, lobby, lambda state, p: setattr(
        state, "frame", weekly if p == (381, 961) else limit))
    with pytest.raises(task.CurrencyWarsError, match="助燃券已达上限"):
        world.war.get_reward(lobby)
    assert state.clicks.count((Page.WEEKLY, (1640, 728))) == 1
    world.cfg.save_timestamp.assert_not_called()
    assert not state.keys


@pytest.mark.parametrize("layout", ("confirm", "right_confirm", "close", "close_without_ocr"))
def test_full_weekly_score_with_unresolved_reward_limit_does_not_start_a_match(monkeypatch, world, layout):
    lobby = home()
    weekly = page(Page.WEEKLY, ("18000/18000", 273, 740), claim_available=lambda: True)
    message = ("背包内助燃券持有数量已达上限。", 956, 526 if layout == "right_confirm" else 580)
    if layout in ("confirm", "right_confirm"):
        close_point = (1188, 672) if layout == "right_confirm" else (960, 724)
        x, y = close_point
        image = CANVAS.copy()
        ImageDraw.Draw(image).rectangle((x - 107, y - 26, x + 107, y + 27), fill="white")
        limit = Frame(image, labels(("提示", 960, 412), message, ("确认", *close_point)))
    else:
        close_point = (1462, 378 if layout == "close" else 379)
        close = (("X", *close_point),) if layout == "close" else ()
        limit = Frame(CANVAS, labels(message, ("清理", 774, 708), ("前往使用", 1188, 708), *close))
    assert limit.page == Page.REWARD_LIMIT
    routes = {(lobby, (381, 961)): weekly}
    if layout in ("confirm", "right_confirm"):
        routes[weekly, (1640, 728)] = limit
    else:
        receipt = page(Page.REWARD_RECEIPT, ("点击空白处关闭", 960, 910))
        routes[weekly, (1640, 728)] = receipt
        routes[receipt, (960, 910)] = limit
        routes[limit, (774, 708)] = limit
    routes[limit, close_point] = weekly
    state = drive(monkeypatch, world, lobby, lambda s, point: setattr(s, "frame", routes[s.frame, point]))
    world.auto.press_key.side_effect = lambda key: setattr(state, "frame", lobby)

    assert world.war.start(weekly=True) is False
    assert world.war.weekly_score == (18000, 18000)
    assert world.war.weekly_reward_pending
    assert state.frame is lobby
    assert state.clicks == [(f.page, point) for f, point in routes]
    world.cfg.save_timestamp.assert_not_called()


def test_full_home_score_prevents_start_when_the_reward_entry_cannot_be_read(monkeypatch, world):
    lobby = page(Page.HOME, ("开始货币战争", 1600, 972), ("18000/18000", 196, 961))
    state = drive(monkeypatch, world, lobby)

    assert world.war.start(weekly=True) is False
    assert world.war.weekly_score == (18000, 18000)
    assert world.war.weekly_reward_pending
    assert state.clicks == state.keys == []
    world.cfg.save_timestamp.assert_not_called()


@pytest.mark.parametrize("checkpoint", (Page.WEEKLY, Page.REWARD_RECEIPT))
def test_weekly_start_uses_the_open_points_page_when_home_entry_is_unreadable(monkeypatch, world, checkpoint):
    lobby = Frame(CANVAS, labels(("入画奇航", 150, 80), ("开始货币战争", 1600, 972), ("18000/18000", 196, 961)))
    points = labels(("积分奖励", 145, 330), ("18000/18000", 273, 740))
    pending = Frame(CANVAS, points)
    credited = Frame(CANVAS, points)
    monkeypatch.setattr(pending, "claim_available", lambda: True)
    monkeypatch.setattr(credited, "claim_available", lambda: False)
    receipt = Frame(CANVAS, points + labels(("点击空白处关闭", 960, 910)))
    initial = pending if checkpoint == Page.WEEKLY else receipt
    assert initial.page == checkpoint and lobby.page == Page.HOME
    routes = {(pending, (1640, 728)): receipt, (receipt, (960, 910)): credited}
    state = drive(monkeypatch, world, initial, lambda s, point: setattr(s, "frame", routes[s.frame, point]))

    def press(key):
        state.keys.append((state.frame.page, key))
        state.frame = lobby

    world.auto.press_key.side_effect = press

    assert world.war.start(weekly=True)
    expected = [(Page.WEEKLY, (1640, 728))] if checkpoint == Page.WEEKLY else []
    assert state.clicks == [*expected, (Page.REWARD_RECEIPT, (960, 910))]
    assert state.keys == [(Page.WEEKLY, "esc")]
    assert not world.war.weekly_reward_pending
    world.cfg.save_timestamp.assert_called_once_with("currencywars_timestamp")


def test_flow_from_menu_to_weekly_reward_with_game_auto(monkeypatch, world):
    lobby = home()
    ready = page(Page.BOARD, ("出战", 1818, 748), stage="1-1")
    off, on = battle(False), battle(True)
    intermediate = page(Page.NODE_RESULT, ("挑战结束", 960, 230), ("前往结算", 959, 895))
    result = page(Page.MATCH_RESULT, ("挑战成功", 959, 233), ("下一步", 960, 895))
    stats = page(Page.MATCH_RESULT, ("返回货币战争", 960, 895))
    pending = page(Page.WEEKLY, ("15000/15000", 273, 740))
    claimed = page(Page.WEEKLY, ("15000/15000", 273, 740))
    receipt = page(Page.REWARD_RECEIPT, ("点击空白处关闭", 964, 851))
    monkeypatch.setattr(pending, "claim_available", lambda: True)
    monkeypatch.setattr(claimed, "claim_available", lambda: False)
    monkeypatch.setattr(world.war, "_gather", lambda f: f)
    monkeypatch.setattr(world.war, "_equip", lambda f, _: f)
    monkeypatch.setattr(world.war, "_read_board", lambda f: (
        f, board(slot("front", 0, CORE), stage=f.stage, gold=0, used=1, capacity=3)))
    monkeypatch.setattr(ready, "number", lambda *a, **k: 4)
    routes = {
        (lobby, (1600, 972)): mode(("进入标准博弈", 1638, 960)),
        (lobby, (381, 961)): pending, (ready, (1818, 748)): off, (off, ui.AUTO_TOGGLE): on,
        (intermediate, (959, 895)): result, (result, (960, 895)): stats, (stats, (960, 895)): lobby,
        (pending, (1640, 728)): receipt, (receipt, (964, 851)): claimed,
    }
    def click(state, point):
        if state.frame.page == Page.MODES:
            state.frame = rank()
        elif state.frame.page == Page.RANK:
            state.frame = ready
        else:
            state.frame = routes[state.frame, point]
    def capture(state):
        if state.frame == on:
            state.frame = intermediate
    state = drive(monkeypatch, world, lobby, click, capture)
    world.auto.press_key.side_effect = lambda key: (
        state.keys.append((state.frame.page, key)), setattr(state, "frame", lobby))
    assert world.war.start()
    assert world.war.result is True
    assert [p for p in state.clicks if p[0] == Page.BATTLE] == [(Page.BATTLE, ui.AUTO_TOGGLE)]
    assert state.keys == [(Page.WEEKLY, "esc")]
    world.cfg.save_timestamp.assert_called_once_with("currencywars_timestamp")


@pytest.mark.parametrize("after_reset", [False, True])
def test_full_run_uses_existing_currency_wars_weekly_timestamp(monkeypatch, world, after_reset):
    from tasks.daily import daily

    cfg = world.cfg
    cfg.currencywars_enable = True
    cfg.asset_manager_enable = False
    cfg.weekly_divergent_enable = False
    cfg.fight_enable = False
    cfg.universe_enable = False
    for mode in ("forgottenhall", "purefiction", "apocalyptic"):
        setattr(cfg, f"{mode}_enable", False)
        setattr(cfg, f"{mode}_timestamp", 0)
    monkeypatch.setattr(daily, "cfg", cfg)
    due = Mock(return_value=after_reset)
    monkeypatch.setattr(daily.Date, "is_next_mon_x_am", due)
    monkeypatch.setattr(daily, "run_steps", lambda steps: [name for name, _ in steps])

    assert ("货币战争" in daily.Daily.start()) is after_reset
    due.assert_called_once_with(cfg.currencywars_timestamp, cfg.refresh_hour)


@pytest.mark.parametrize("remaining_rewards", (False, True))
def test_weekly_reward_keeps_receipt_when_score_and_tier_readback_fail(monkeypatch, world, remaining_rewards):
    lobby = home()
    pending = page(Page.WEEKLY, ("18000/18000", 273, 740), claim_available=lambda: True)
    receipt = page(Page.REWARD_RECEIPT, ("点击空白处关闭", 960, 910))
    after = page(Page.WEEKLY)
    for frame in (after, lobby):
        monkeypatch.setattr(frame, "ratio", Mock(side_effect=OSError("积分 OCR 失败")))
    monkeypatch.setattr(after, "claim_available", Mock(side_effect=OSError("已领奖档位识别失败")))
    monkeypatch.setattr(after, "claim_button_visible", lambda: remaining_rewards, raising=False)
    routes = {(lobby, (381, 961)): pending, (pending, (1640, 728)): receipt, (receipt, (960, 910)): after}
    state = drive(monkeypatch, world, lobby, lambda s, point: setattr(s, "frame", routes[s.frame, point]))
    world.auto.press_key.side_effect = lambda _: setattr(state, "frame", lobby)

    assert world.war.start(weekly=True) is not remaining_rewards
    assert state.clicks == [(f.page, point) for f, point in routes]
    assert world.war.weekly_score == (18000, 18000)
    assert world.war.weekly_reward_pending is remaining_rewards
    task.Base.send_notification_with_screenshot.assert_called_once_with(
        "货币战争奖励已领取", task.NotificationLevel.ALL, receipt.image,
    )
    assert world.cfg.save_timestamp.call_count == int(not remaining_rewards)
    after.ratio.assert_not_called()
    after.claim_available.assert_not_called()
    lobby.ratio.assert_not_called()


@pytest.mark.parametrize("still_available", (False, True))
def test_weekly_reward_navigation_recovery_keeps_the_claim_interlock(monkeypatch, world, still_available):
    lobby = home()
    pending = page(Page.WEEKLY, ("18000/18000", 273, 740), claim_available=lambda: True)
    receipt = page(Page.REWARD_RECEIPT, ("点击空白处关闭", 960, 910))
    after = page(Page.WEEKLY, ("18000/18000", 273, 740), claim_available=lambda: still_available)
    routes = {(lobby, (381, 961)): pending, (pending, (1640, 728)): receipt, (receipt, (960, 910)): after}
    state = drive(monkeypatch, world, lobby, lambda s, point: setattr(s, "frame", routes[s.frame, point]))
    world.auto.press_key.side_effect = lambda _: setattr(state, "frame", lobby)
    go_back = world.war._go_back

    def fail_first_return(frame, target):
        monkeypatch.setattr(world.war, "_go_back", go_back)
        raise task.CurrencyWarsReceiptTimeout("暂未返回")

    monkeypatch.setattr(world.war, "_go_back", fail_first_return)
    assert world.war.start(weekly=True) is not still_available
    assert state.clicks == [(f.page, point) for f, point in routes]
    task.Base.send_notification_with_screenshot.assert_called_once_with(
        "货币战争奖励已领取", task.NotificationLevel.ALL, receipt.image,
    )
    assert world.cfg.save_timestamp.call_count == int(not still_available)


def test_cross_week_reset_does_not_save_completion(monkeypatch, world):
    old = home()
    reset = page(Page.HOME, ("0/18000", 318, 1000))
    weekly = page(Page.WEEKLY, ("18000/18000", 273, 740))
    monkeypatch.setattr(weekly, "claim_available", lambda: False)
    state = drive(monkeypatch, world, old, lambda s, _: setattr(s, "frame", weekly))
    world.auto.press_key.side_effect = lambda _: setattr(state, "frame", reset)
    from utils.date import Date

    monkeypatch.setattr(Date, "is_next_mon_x_am", lambda *_: state.frame is reset)
    with pytest.raises(task.CurrencyWarsError, match="跨周重置"):
        world.war.get_reward(old)
    world.cfg.save_timestamp.assert_not_called()


def test_s2_opening_boss_and_partner_reveal_needs_both_anchors():
    signed = (("本场对局首领", 585, 201), ("本局奇遇", 1200, 627), ("下一步", 1400, 982))
    full = Frame(CANVAS, labels(*signed))
    assert full.page == Page.REVEAL
    assert full.reveal_button().point == (1400, 982)
    assert Frame(CANVAS, labels(signed[0], signed[2])).page == Page.UNKNOWN


def test_partner_detail_uses_carried_equipment_captions_in_the_shifted_layout():
    board_words = (("备战阶段", 468, 45), ("1-1", 467, 80), ("佩佩", 1522, 409), ("日后台", 1538, 449))
    equipment = (("携带装备", 1452, 635), ("特殊角色携带的装备无法拆除", 1528, 671))
    assert Frame(CANVAS, labels(*board_words, *equipment)).page == Page.PARTNER_DETAIL
    assert Frame(CANVAS, labels(*board_words, equipment[0])).page != Page.PARTNER_DETAIL


def test_equipment_recipe_screen_and_slot_postcondition():
    visible = labels(("那刻夏", 1538, 230), ("推荐光环", 1019, 402), ("推荐装备", 1019, 588),
                     ("合成", 1169, 908))
    before = Frame(CANVAS, visible)
    assert before.page == Page.EQUIPMENT
    assert before.equipment_action().text == "合成"
    assert not before.equipment_changed(before)
    after_image = CANVAS.copy()
    draw = ImageDraw.Draw(after_image)
    draw.rectangle((1619, 789, 1673, 842), fill=(224, 207, 111))
    draw.rectangle((1621, 803, 1649, 831), fill=(153, 29, 174))
    assert Frame(after_image, visible).equipment_changed(before)


def test_equipment_panel_is_recognized_when_full_frame_ocr_omits_the_name():
    detail = (("备战阶段", 467, 55), ("3-4", 467, 82), ("后台", 1550, 270),
              ("速度", 1590, 375), ("推荐", 1512, 818))
    panel = (("推荐光环", 1020, 404), ("推荐装备", 1020, 592))
    opened = Frame(CANVAS, labels(*detail, *panel))
    assert opened.employee_name() is None
    assert opened.page == Page.EQUIPMENT
    assert Frame(CANVAS, labels(*detail, panel[0])).page == Page.DETAIL


def test_unchanged_employee_detail_can_skip_unavailable_recommendation(monkeypatch, world):
    target = slot("back", 1, BAILU)
    before = page(Page.BOARD, stage="3-4")
    detail = page(Page.DETAIL, ("白露", 1535, 231), ("推荐", 1512, 818), stage="3-4")
    after = page(Page.BOARD, stage="3-4")
    monkeypatch.setattr(before, "slot_occupied", lambda point: point == target.point)
    routes = {(before, target.point): detail, (detail, (1512, 818)): detail, (detail, (12, 12)): after}
    state = drive(monkeypatch, world, before, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    assert world.war._equip_once(before, target) == (after, False)
    assert state.clicks == [(Page.BOARD, target.point)] + [(Page.DETAIL, (1512, 818))] * 3 + [
        (Page.DETAIL, (12, 12)),
    ]


@pytest.mark.parametrize("materials_spent", (False, True))
def test_craft_without_equipping_confirms_materials_after_returning_to_board(monkeypatch, world, materials_spent):
    unit = policy.Unit("万敌", True, True, 2)
    target = slot("back", 3, unit)
    before = page(Page.BOARD, stage="3-1")
    detail = page(Page.DETAIL, ("万敌", 1520, 231), ("推荐", 1512, 818), stage="3-1")
    craft = page(Page.EQUIPMENT, ("万敌", 1520, 231), ("合成", 1306, 909), stage="3-1")
    craft.image = CANVAS.copy()
    ImageDraw.Draw(craft.image).rectangle((1270, 897, 1342, 921), fill=(155, 153, 152))
    updated = page(Page.EQUIPMENT, ("万敌", 1520, 231), stage="3-1")
    after = page(Page.BOARD, stage="3-1")
    items = ((1844, 248), (1844, 325), (1844, 402))
    monkeypatch.setattr(before, "inventory_items", lambda: items)
    monkeypatch.setattr(after, "inventory_items", lambda: items[:1] if materials_spent else items)
    monkeypatch.setattr(before, "slot_occupied", lambda point: point == target.point)
    monkeypatch.setattr(after, "slot_occupied", lambda point: point == target.point)
    monkeypatch.setattr(after, "slot_portrait_matches", lambda point, _: point == target.point)
    routes = {(before, target.point): detail, (detail, (1512, 818)): craft,
              (craft, (1306, 909)): updated, (updated, (12, 12)): after}
    state = drive(monkeypatch, world, before, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    assert world.war._equip_once(before, target) == (after, materials_spent)
    assert world.war.equipment_deferred_stage == (None if materials_spent else "3-1")
    assert state.clicks == [(Page.BOARD, target.point), (Page.DETAIL, (1512, 818)),
                            (Page.EQUIPMENT, (1306, 909)), (Page.EQUIPMENT, (12, 12))]


@pytest.mark.parametrize("has_receipt", (True, False))
def test_equipment_keeps_the_same_recipe_when_ocr_misses_it_or_reorders_the_row(monkeypatch, world, has_receipt):
    target = slot("back", 0, CER)
    stage = "2-5"
    name = ("刻律德菈", 1520, 231)
    equip = ("合成", 1034, 908)
    other = ("合成", 1170, 909)
    initial = page(Page.BOARD, stage=stage)
    detail = page(Page.DETAIL, name, ("推荐", 1512, 818), stage=stage)
    menu = page(Page.EQUIPMENT, name, equip, other, stage=stage)
    unread = page(Page.EQUIPMENT, name, other, stage=stage)
    reordered = page(Page.EQUIPMENT, name, equip, ("合成", 1170, 907), stage=stage)
    worn = page(Page.EQUIPMENT, name, other, stage=stage)
    worn.image = CANVAS.copy()
    ImageDraw.Draw(worn.image).rectangle((1706, 793, 1756, 840), fill=(233, 151, 133))
    ImageDraw.Draw(worn.image).rectangle((1720, 805, 1743, 828), fill=(172, 220, 206))
    changed = page(Page.EQUIPMENT, name, equip, other, stage=stage)
    changed.image = CANVAS.copy()
    ImageDraw.Draw(changed.image).rectangle((983, 818, 1084, 885), fill=(216, 164, 113))
    after = page(Page.BOARD, stage=stage)
    assert reordered.equipment_action().point == (1170, 907)
    monkeypatch.setattr(initial, "slot_occupied", lambda point: point == target.point)
    monkeypatch.setattr(after, "slot_occupied", lambda point: point == target.point)
    monkeypatch.setattr(after, "slot_portrait_matches", lambda point, _: point == target.point)
    routes = {(initial, target.point): detail, (detail, (1512, 818)): menu,
              (reordered, equip[1:]): worn if has_receipt else changed,
              (worn, (12, 12)): after, (changed, (12, 12)): after}
    menu_scans = 0

    def capture(s):
        nonlocal menu_scans
        if s.frame is menu:
            menu_scans += 1
            if menu_scans > 1:
                s.frame = unread
        elif s.frame is unread:
            s.frame = reordered

    state = drive(monkeypatch, world, initial, lambda s, p: setattr(s, "frame", routes[s.frame, p]),
                  after_capture=capture)
    assert world.war._equip_once(initial, target) == (after, has_receipt)
    assert world.war.equipment_deferred_stage == (None if has_receipt else stage)
    assert [point for page_kind, point in state.clicks if page_kind == Page.EQUIPMENT] == [equip[1:], (12, 12)]


@pytest.mark.parametrize("same_recipe", (True, False))
def test_team_equipment_compares_recipe_pixels_and_only_recovers_before_input(monkeypatch, world, same_recipe):
    from tasks.weekly.currency_wars_equipment import Equipment

    target = slot("back", 0, CER)
    stage = "1-9"
    action = ("合成", 1170, 720)
    text = (("刻律德菈", 1546, 232), action)
    board_before = page(Page.BOARD, stage=stage)
    before = page(Page.EQUIPMENT, *text, stage=stage)
    fresh = page(Page.EQUIPMENT, *text, stage=stage)
    fresh.image = CANVAS.copy()
    if not same_recipe:
        ImageDraw.Draw(fresh.image).rectangle((1105, 625, 1228, 692), fill="white")
    worn = page(Page.EQUIPMENT, ("刻律德菈", 1546, 232), stage=stage)
    after = page(Page.BOARD, stage=stage)
    recipe = Equipment("电磁弹射器", ("和平手枪", "轮滑鞋"), (1147, 656))
    monkeypatch.setattr(before, "equipment_option", lambda _: recipe)
    monkeypatch.setattr(fresh, "equipment_option", lambda _: Equipment(None, (None, "轮滑鞋"), (1147, 656)))
    monkeypatch.setattr(worn, "equipment_changed", lambda _: True)
    monkeypatch.setattr(world.war, "_open_equipment", lambda *_: before)
    monkeypatch.setattr(world.war, "_return_from_equipment", lambda f: after if f in (fresh, worn) else f)
    state = drive(monkeypatch, world, fresh, lambda s, _: setattr(s, "frame", worn))
    assert world.war._equip_once(board_before, target, preferred=recipe) == (after, same_recipe)
    assert state.clicks == ([(Page.EQUIPMENT, action[1:])] if same_recipe else [])


def test_high_equipment_summary_counts_rescans_and_confirmed_updates(monkeypatch, world, high_lineup):
    stage = "2-4"
    target = slot("front", 0, CORE)
    team = board(target, stage=stage, used=1, lineup=high_lineup)
    fight = ("出战", 1818, 750)
    employee = ("那刻夏", 1538, 230)
    recommendation = ("推荐", 1512, 818)
    action = ("合成", 1170, 720)
    ready = page(Page.BOARD, fight, stage=stage)
    rescanning = page(Page.BOARD, fight, stage=stage)
    detail = page(Page.DETAIL, employee, recommendation, stage=stage)
    other_detail = page(Page.DETAIL, employee, recommendation, stage=stage)
    menu = page(Page.EQUIPMENT, employee, action, stage=stage)
    equipped = page(Page.EQUIPMENT, employee, stage=stage)
    no_options = page(Page.EQUIPMENT, employee, stage=stage)
    battle = page(Page.BATTLE)
    for frame in (ready, rescanning):
        monkeypatch.setattr(frame, "inventory_equipment", lambda: (((1844, 248), "生命之环"),))
        monkeypatch.setattr(frame, "slot_occupied", lambda point: point == target.point)
    monkeypatch.setattr(equipped, "equipment_changed", lambda before: before is menu)
    monkeypatch.setattr(task, "perf_counter", Mock(side_effect=(10, 12.5)))
    debug = Mock()
    monkeypatch.setattr(task.log, "debug", debug)
    routes = {
        (ready, target.point): detail,
        (detail, recommendation[1:]): menu,
        (menu, (12, 12)): ready,
        (menu, action[1:]): equipped,
        (equipped, (12, 12)): rescanning,
        (rescanning, target.point): other_detail,
        (other_detail, recommendation[1:]): no_options,
        (no_options, (12, 12)): rescanning,
        (rescanning, fight[1:]): battle,
    }
    state = drive(monkeypatch, world, ready, lambda s, p: setattr(s, "frame", routes[s.frame, p]))

    assert world.war._finish_preparation(ready, team) is battle
    # 唯一要看的推荐页正是首选，就地配装，不再关页重开；配装后下一轮照常复查。
    assert state.clicks == [
        (Page.BOARD, target.point), (Page.DETAIL, recommendation[1:]), (Page.EQUIPMENT, action[1:]),
        (Page.EQUIPMENT, (12, 12)), (Page.BOARD, target.point), (Page.DETAIL, recommendation[1:]),
        (Page.EQUIPMENT, (12, 12)), (Page.BOARD, fight[1:]),
    ]
    messages = [call.args[0] for call in debug.call_args_list]
    assert "2-4那刻夏的推荐页正是本轮首选，就地配装" in messages
    assert [message for message in messages if "全队配装" in message] == [
        "货币战争 标准博弈 2-4 全队配装扫描 2 轮（打开推荐页 2 次），确认装备更新或扣料 1 次，用时 2.50 秒",
    ]


@pytest.mark.parametrize(("saved_mode", "configured_mode", "stage", "fast_mode", "scan"), [
    ("normal", "overclock", "2-7", True, True),
    ("normal", "overclock", "2-5", True, False),
    ("overclock", "normal", "2-5", True, True),
    ("overclock", "normal", "2-7", True, False),
    ("normal", "normal", "2-4", False, True),
    ("overclock", "overclock", "2-4", False, True),
    (None, "normal", "2-5", True, True),
    (None, "overclock", "2-7", True, True),
    (None, "normal", "2-4", True, False),
])
def test_high_fast_mode_only_checks_equipment_at_possible_boss_stages(
    monkeypatch, world, high_lineup, saved_mode, configured_mode, stage, fast_mode, scan,
):
    fight, recommend, resume = (1818, 750), (1512, 818), (1692, 961)
    target = slot("front", 0, CORE)
    team = board(target, stage=stage, gold=0, used=1, capacity=3, lineup=high_lineup)
    ready = page(Page.BOARD, ("出战", *fight), stage=stage, capacity=(1, 3), gold=0)
    detail = page(Page.DETAIL, (CORE.name, 1538, 230), ("推荐", *recommend), stage=stage)
    equipment = page(Page.EQUIPMENT, (CORE.name, 1538, 230), stage=stage)
    fighting, lobby = battle(True), home()
    world.cfg.currencywars_strategy = policy.HIGH_ANAXA
    world.cfg.currencywars_type = configured_mode
    world.cfg.currencywars_fast_mode = fast_mode
    monkeypatch.setattr(ready, "inventory_equipment", lambda: (((1844, 248), "生命之环"),))
    monkeypatch.setattr(ready, "slot_occupied", lambda point: point == target.point)
    monkeypatch.setattr(world.war, "_read_board", lambda frame: (frame, team))
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda frame: (frame, (18000, 18000), False))

    def win_battle(frame):
        assert frame is fighting
        world.war.result = True
        return lobby

    monkeypatch.setattr(world.war, "_watch_battle", win_battle)
    routes = {(ready, target.point): detail, (detail, recommend): equipment,
              (equipment, (12, 12)): ready, (ready, fight): fighting}
    initial = ready
    expected = []
    if saved_mode:
        initial = mode(("继续进度", *resume), ("结束并结算", 1397, 961), (ui.MODE_NAMES[saved_mode], 670, 155))
        routes[initial, resume] = ready
        expected.append((Page.MODES, resume))
    if scan:
        expected.extend(((Page.BOARD, target.point), (Page.DETAIL, recommend), (Page.EQUIPMENT, (12, 12))))
    expected.append((Page.BOARD, fight))
    state = drive(monkeypatch, world, initial, lambda s, point: setattr(s, "frame", routes[s.frame, point]))

    assert world.war.start(resume=True)
    assert world.war.mode == (saved_mode or configured_mode)
    assert world.war.mode_confirmed == bool(saved_mode)
    assert state.clicks == expected
    assert not state.keys



@pytest.mark.parametrize(("same_employee", "worn"), ((True, False), (True, True), (False, False)))
def test_equipment_receipt_timeout_rechecks_the_board_without_repeating_input(monkeypatch, world, same_employee, worn):
    stage = "2-5"
    target = slot("back", 1, BAILU)
    initial = page(Page.BOARD, stage=stage, capacity=(4, 4))
    menu = page(Page.EQUIPMENT, ("白露", 1540, 231), ("穿戴", 1170, 720), stage=stage)
    after = page(Page.BOARD, stage=stage, capacity=(4, 4))
    monkeypatch.setattr(after, "slot_occupied", lambda point: point == target.point)
    monkeypatch.setattr(after, "slot_portrait_matches", lambda *_: same_employee)
    monkeypatch.setattr(initial, "card_equipment", lambda _: 0)
    monkeypatch.setattr(after, "card_equipment", lambda _: int(worn))
    monkeypatch.setattr(world.war, "_open_equipment", lambda *_: menu)
    routes = {(1170, 720): menu, (12, 12): after}
    state = drive(monkeypatch, world, menu, lambda s, p: setattr(s, "frame", routes[p]))
    if same_employee:
        assert world.war._equip_once(initial, target) == (after, worn)
        assert world.war.equipment_deferred_stage == (None if worn else stage)
    else:
        with pytest.raises(task.CurrencyWarsEquipmentReplan, match="需要重读备战"):
            world.war._equip_once(initial, target)
        assert world.war.equipment_deferred_stage == stage
    assert state.clicks == [(Page.EQUIPMENT, (1170, 720)), (Page.EQUIPMENT, (12, 12))]


def test_uncertain_equipment_does_not_retry_on_the_same_node(monkeypatch, world, high_lineup):
    before = page(Page.BOARD, stage="2-5")
    team = board(slot("front", 0, CORE), stage="2-5", lineup=high_lineup)
    world.war.equipment_deferred_stage = "2-5"
    attempt = Mock(return_value=before)
    monkeypatch.setattr(world.war, "_equip_team", attempt)
    assert world.war._equip(before, team) is before
    attempt.assert_not_called()
    assert world.war._equip(before, replace(team, stage="2-6")) is before
    attempt.assert_called_once()



@pytest.mark.parametrize("next_page", (Page.BOARD, Page.UNKNOWN))
def test_optional_equipment_recovers_from_navigation_timeout_only_on_a_known_page(monkeypatch, world,
                                                                                high_lineup, next_page):
    stage = "1-9"
    before = page(Page.BOARD, stage=stage)
    menu = page(Page.EQUIPMENT, stage=stage)
    recovered = page(next_page, stage=stage)
    team = board(slot("front", 0, CORE), stage=stage, lineup=high_lineup)
    monkeypatch.setattr(world.war, "_equip_team", Mock(side_effect=task.CurrencyWarsReceiptTimeout("推荐仍开着")))
    state = drive(monkeypatch, world, menu)
    closes = 0

    def close(frame):
        nonlocal closes
        assert frame is menu
        closes += 1
        if closes == 1:
            raise task.CurrencyWarsReceiptTimeout("正在动画")
        state.frame = recovered
        return recovered

    monkeypatch.setattr(world.war, "_return_from_equipment", close)
    if next_page == Page.BOARD:
        assert world.war._equip(before, team) is recovered
        assert world.war.equipment_deferred_stage == stage
    else:
        with pytest.raises(task.CurrencyWarsError, match="无法识别当前页面"):
            world.war._equip(before, team)
    assert closes == 2
    assert not state.clicks


def test_equipment_replan_reaches_battle_without_reusing_the_old_team(monkeypatch, world, high_lineup):
    stage = "1-9"
    current = page(Page.BOARD, ("出战", 1818, 750), stage=stage)
    team = board(slot("front", 0, CORE), stage=stage, used=1, capacity=1, gold=0, lineup=high_lineup)
    lobby = home()
    seen = []

    def equip(_, __):
        assert not seen
        seen.append("旧装备面板")
        world.war.equipment_deferred_stage = stage
        raise task.CurrencyWarsEquipmentReplan("卡位已变化")

    def play_battle(frame):
        assert frame.page == Page.BATTLE
        return lobby

    monkeypatch.setattr(world.war, "lineup", high_lineup)
    monkeypatch.setattr(world.war, "_settle_board", lambda f: f)
    monkeypatch.setattr(world.war, "_read_board", lambda f: (f, team))
    monkeypatch.setattr(world.war, "_gather", lambda f: f)
    monkeypatch.setattr(world.war, "_equip_team", equip)
    monkeypatch.setattr(world.war, "_watch_battle", play_battle)
    state = drive(monkeypatch, world, current, lambda s, _: setattr(s, "frame", page(Page.BATTLE)))
    assert world.war._play(current) is lobby
    assert state.clicks == [(Page.BOARD, (1818, 750))]
    assert seen == ["旧装备面板"]


def test_equipment_full_checks_all_three_slots_and_detects_game_refusal():
    image = CANVAS.copy()
    draw = ImageDraw.Draw(image)
    for x in (1646, 1731):
        draw.rectangle((x - 23, 796, x + 8, 835), fill=(234, 162, 63))
    assert not Frame(image.copy(), ()).equipment_full()
    draw.rectangle((1795, 796, 1828, 836), fill=(235, 139, 24))
    f = Frame(image, labels(("当前装备不符合穿戴条件", 960, 305)))
    assert f.equipment_full()
    assert f.equipment_refused()


def test_black_market_interrupts_a_board_read_and_closes_without_a_purchase(monkeypatch, world):
    market = Frame(CANVAS, labels(("黑市主理人", 1031, 75), ("轮换商品", 901, 159),
                                 ("招牌商品", 1305, 159), ("详情", 777, 481), ("详情", 1025, 481)))
    assert market.page == Page.BLACK_MARKET and market.stage is None
    assert Frame(CANVAS, labels(("黑市主理人", 165, 247))).page == Page.UNKNOWN
    before = page(Page.BOARD, stage="3-4", capacity=(10, 10))
    after = page(Page.BOARD, stage="3-4", capacity=(10, 10), gold=12)
    calls = 0

    def capture(state):
        nonlocal calls
        calls += 1
        if calls > 1 and state.frame is before:
            state.frame = market

    state = drive(monkeypatch, world, before, lambda s, _: setattr(s, "frame", after), after_capture=capture)
    assert world.war._read_board(before) == (market, None)
    assert world.war._play_step(market) is after
    assert state.clicks == [(Page.BLACK_MARKET, (12, 12))]


def test_late_reveal_interrupts_shop_and_returns_control_to_state_machine(monkeypatch, world):
    ready = page(Page.BOARD, ("商店", 1624, 983))
    reveal = page(Page.REVEAL, ("本局奇遇", 793, 484), ("点击空白处继续", 958, 704))
    state = drive(monkeypatch, world, ready, lambda s, _: setattr(s, "frame", reveal))
    assert world.war._shop(ready, board(slot("bench", 0)), 0) == (reveal, 0, False)
    assert state.clicks == [(Page.BOARD, (1624, 983))]
    assert not world.war.deferred_operations


def svarog_modification(stage=None, *, read_controls=True, costs=(0, 0, 0)):
    words = [("机心巧匠", 1046, 79), ("请选择1个强化效果", 1046, 141)]
    if stage:
        words.extend((("备战阶段", 287, 70), (stage, 287, 106), ("机心巧匠", 130, 331),
                      ("商店", 1624, 982), ("出战", 1818, 751)))
    if read_controls:
        words.extend((("反击模组", 516, 376), ("导弹模组", 918, 376), ("响指模组", 1308, 376)))
        words.append(("确认选择", 1492, 585))
        words.extend((str(cost), x, 375) for cost, x in zip(costs, (815, 1212, 1609)))
        words.extend(("详情", x, 426) for x in (650, 1046, 1444))
    return Frame(CANVAS, labels(*words))


def test_svarog_modification_is_identified_without_a_node():
    pending = svarog_modification()
    assert pending.page is Page.SVAROG_MODIFICATION
    assert pending.stage is None


def test_svarog_bond_in_sidebar_keeps_the_normal_preparation_page():
    normal = Frame(CANVAS, labels(("机心巧匠", 130, 331), ("备战阶段", 287, 70), ("1-2", 287, 106),
                                  ("前台区域", 974, 315), ("后台区域", 976, 575),
                                  ("商店", 1624, 982), ("出战", 1818, 751)))
    assert normal.page is Page.BOARD


@pytest.mark.parametrize("strategy", (policy.DEFAULT_STRATEGY, policy.HIGH_ANAXA))
def test_svarog_modification_resumes_preparation_after_deployment_and_at_the_next_node(monkeypatch, world, strategy):
    world.cfg.currencywars_strategy = strategy
    world.cfg.currencywars_fast_mode = True
    clara = policy.Unit("克拉拉", True, True, stars=1, output=True, cost=5)
    reserve, target = slot("bench", 0, clara), slot("front", 0)
    before = board(reserve, target, stage="1-2", used=0, gold=0)
    deployed = apply_deployment(before, (reserve, target))

    def preparation(team):
        frame = page(Page.BOARD, ("出战", 1818, 751), stage=team.stage, gold=team.gold,
                     capacity=(team.used, team.capacity), slots=lambda: team.slots)
        occupied = {s.point for s in team.slots if s.occupied}
        monkeypatch.setattr(frame, "slot_occupied", occupied.__contains__)
        return frame

    initial, ready = preparation(before), preparation(deployed)
    after_node = replace(deployed, stage="1-3")
    ready_next = preparation(after_node)
    teams = {initial: before, ready: deployed, ready_next: after_node}
    monkeypatch.setattr(world.war, "_read_default_board", lambda f, **_: (f, teams[f]))
    monkeypatch.setattr(world.war, "_read_board", lambda f, **_: (f, teams[f]))
    monkeypatch.setattr(world.war, "_card_stars", lambda *_: clara.stars)
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))
    monkeypatch.setattr(world.war, "_notify", Mock())
    monkeypatch.setattr(task, "TASK_SECONDS", 40)

    first, following = svarog_modification("1-2"), svarog_modification("1-3")
    transient = Frame(CANVAS, ())
    node_result = Frame(CANVAS, labels(("挑战成功", 960, 233), ("继续挑战", 960, 899)))
    result = Frame(CANVAS, labels(("对局胜利", 960, 233), ("返回货币战争", 960, 899)))
    lobby = home()
    state = SimpleNamespace(frame=initial, clicks=[], unreadable=0)

    def capture():
        if state.frame is transient:
            state.unreadable += 1
            if state.unreadable == 3:
                state.frame = ready_next
        return state.frame

    def click(point, *, press_duration):
        state.clicks.append((state.frame, point))
        if state.frame in (first, following) and point[1] != 585:
            assert any(abs(point[0] - x) < 188 for x in (650, 1046, 1444)) and 177 < point[1] < 397
            return True
        state.frame = {
            (first, (1492, 585)): ready,
            (ready, (1818, 751)): node_result,
            (node_result, (960, 899)): following,
            (following, (1492, 585)): transient,
            (ready_next, (1818, 751)): result,
            (result, (960, 899)): lobby,
        }[state.frame, point]
        # 确认回执暂未返回时，游戏可能已经进入下一页。
        return state.frame is not transient

    def deploy(source, destination, **kwargs):
        assert state.frame is initial
        assert source == (reserve.point[0] / 1920, reserve.point[1] / 1080)
        assert destination == (target.point[0] / 1920, target.point[1] / 1080)
        state.frame = first
        return True

    monkeypatch.setattr(world.war, "_capture", capture)
    world.auto.click_element_with_pos.side_effect = click
    world.auto.drag_mouse.side_effect = deploy

    assert world.war.start(resume=True) is True
    assert state.frame is lobby and state.unreadable == 3
    assert [frame for frame, _ in state.clicks] == [first, first, ready, node_result, following, following,
                                                   ready_next, result]
    world.auto.drag_mouse.assert_called_once()
    world.auto.press_key.assert_not_called()
    task.save_error_screenshot.assert_not_called()


def test_svarog_modification_chooses_a_free_offer_on_the_four_card_layout(monkeypatch, world):
    current = Frame(CANVAS, labels(
        ("机心巧匠", 1046, 79), ("请选择1个强化效果", 1046, 141), ("确认选择", 1492, 585),
        ("反击强化Lv2", 528, 376), ("弹仓扩容", 809, 376), ("响指模组", 1108, 376), ("战备升级", 1405, 376),
        ("2", 714, 375), ("1", 1014, 375), ("0", 1310, 375), ("0", 1609, 375),
        *(("详情", x, 426) for x in (600, 898, 1194, 1492)),
    ))
    ready = page(Page.BOARD, stage="2-5")

    def click(state, point):
        if point == (1492, 585):
            assert len(state.clicks) == 2
            state.frame = ready
        else:
            assert 1060 < point[0] < 1625 and 177 < point[1] < 397

    state = drive(monkeypatch, world, current, click)
    assert world.war._play_step(current) is ready
    assert len(state.clicks) == 2


def test_svarog_modification_locates_four_prices_from_coin_icons_when_ocr_misses_the_columns(monkeypatch):
    image = CANVAS.copy()
    draw = ImageDraw.Draw(image)
    for x in (687, 984, 1281, 1578):
        draw.ellipse((x - 14, 363, x + 14, 390), fill=(224, 173, 70))
    current = Frame(image, svarog_modification(read_controls=False).labels)
    prices = {714: "0", 1014: "2", 1310: "0", 1609: "0"}

    def read_price(area, *, recognition_only):
        x1, y1, x2, y2 = area
        assert recognition_only and y1 <= 375 < y2
        return next((price for x, price in prices.items() if x1 <= x < x2), None)

    monkeypatch.setattr(current, "read_local", read_price)
    assert current.page is Page.SVAROG_MODIFICATION
    assert [(card.point[0], price) for card, price in current.svarog_offers] == [
        (600, 0), (897, 2), (1194, 0), (1491, 0),
    ]


def test_svarog_modification_uses_the_confirmed_layout_when_card_and_button_text_are_unreadable(monkeypatch, world):
    current = svarog_modification(read_controls=False)
    monkeypatch.setattr(current, "read_local", lambda *_, **__: None)
    ready = page(Page.BOARD, stage="2-5")
    routes = {(1444, 285): current, (1492, 585): ready}
    state = drive(monkeypatch, world, current, lambda s, point: setattr(s, "frame", routes[point]))

    assert world.war._play_step(current) is ready
    assert state.clicks == [(Page.SVAROG_MODIFICATION, point) for point in routes]


def test_svarog_modification_replans_if_the_clicked_card_is_later_found_to_cost_gold(monkeypatch, world):
    unclear = svarog_modification(read_controls=False)
    monkeypatch.setattr(unclear, "read_local", lambda *_, **__: None)
    prices = svarog_modification(costs=(0, 2, 2))
    ready = page(Page.BOARD)
    routes = {(unclear, (1444, 285)): prices, (prices, (650, 285)): prices, (prices, (1492, 585)): ready}
    state = drive(monkeypatch, world, unclear, lambda s, point: setattr(s, "frame", routes[s.frame, point]))

    assert world.war._play_step(unclear) is ready
    assert state.clicks == [(frame.page, point) for frame, point in routes]


def test_svarog_takeover_never_confirms_an_old_paid_selection_after_a_lost_free_card_tap(monkeypatch, world):
    catalogue = svarog_modification("2-5", costs=(0, 2, 1))

    def selected(x):
        image = CANVAS.copy()
        draw = ImageDraw.Draw(image)
        draw.line((x - 95, 396, x + 95, 396), fill="white", width=3)
        draw.rectangle((1301, 556, 1684, 614), fill="white")
        return Frame(image, catalogue.labels)

    paid, free = selected(1046), selected(650)
    result = Frame(CANVAS, labels(("对局胜利", 960, 233), ("返回货币战争", 960, 899)))
    lobby = home()
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))
    monkeypatch.setattr(world.war, "_notify", Mock())
    routes = {(free, (1492, 585)): result, (result, (960, 899)): lobby}

    def click(state, point):
        if state.frame is paid:
            assert point == (650, 285)
            if len(state.clicks) == 2:
                state.frame = free
            return True
        state.frame = routes[state.frame, point]
        return True

    state = drive(monkeypatch, world, paid, click)

    assert world.war.start(resume=True) is True
    assert state.frame is lobby
    assert state.clicks == [
        (Page.SVAROG_MODIFICATION, (650, 285)),
        (Page.SVAROG_MODIFICATION, (650, 285)),
        (Page.SVAROG_MODIFICATION, (1492, 585)),
        (Page.MATCH_RESULT, (960, 899)),
    ]


@pytest.mark.parametrize("fault", ("input", "prices", "stage"))
def test_svarog_modification_recovers_from_local_faults_in_the_same_run(monkeypatch, world, fault):
    current = svarog_modification("3-4")
    alternate = svarog_modification("3-3") if fault == "stage" else svarog_modification("3-4", costs=(1, 2, 3))
    result = Frame(CANVAS, labels(("对局胜利", 960, 233), ("返回货币战争", 960, 899)))
    lobby = home()
    recovered = False
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))
    monkeypatch.setattr(world.war, "_notify", Mock())
    monkeypatch.setattr(task, "TASK_SECONDS", 12 if fault == "stage" else 60)

    def capture(state):
        if fault == "stage" and state.frame in (current, alternate):
            state.frame = alternate if state.frame is current else current
        if fault == "prices" and state.frame is alternate and world.now[0] >= 9:
            state.frame = current

    def click(state, point):
        nonlocal recovered
        if state.frame is result:
            assert point == (960, 899)
            state.frame = lobby
        elif fault == "input" and world.now[0] < 6:
            return False
        elif point == (1492, 585):
            assert recovered
            state.frame = result
        else:
            recovered = True

    state = drive(monkeypatch, world, alternate if fault == "prices" else current, click, capture)

    assert world.war.start(resume=True) is True
    assert recovered and state.frame is lobby
    assert state.keys == []
    task.save_error_screenshot.assert_not_called()


@pytest.mark.parametrize("outcome", ("unavailable", "stopped", "timed_out"))
def test_svarog_modification_has_a_bounded_end_and_checks_for_stop_before_confirm(monkeypatch, world, outcome):
    current = svarog_modification()
    state = drive(monkeypatch, world, current)

    def checkpoint():
        if outcome == "stopped" and state.clicks:
            raise RunStopRequested

    task.pause_ctl.checkpoint.side_effect = checkpoint
    if outcome == "stopped":
        with pytest.raises(RunStopRequested):
            world.war._play_step(current)
        assert len(state.clicks) == 1 and state.clicks[0][1] != (1492, 585)
    elif outcome == "timed_out":
        world.war.deadline = 10
        with pytest.raises(task.CurrencyWarsBudgetExceeded, match="总时限"):
            world.war._play_step(current)
        assert len(state.clicks) == 6
    else:
        with pytest.raises(task.CurrencyWarsUnavailable, match="已保留当前现场"):
            world.war._play_step(current)
        assert len(state.clicks) == 12
    assert state.frame is current


@pytest.mark.parametrize("return_page", (Page.BOARD, Page.DETAIL))
def test_dreamscape_dance_confirms_two_actual_selections_before_returning(monkeypatch, world, return_page):
    common = labels(("备战阶段", 287, 70), ("1-2", 287, 106), ("梦境交织", 1044, 77),
                    ("选择2个角色进行共舞，为其增加战斗内连携效果", 1044, 136),
                    ("黑天鹅", 928, 357), ("花火", 1165, 357),
                    ("详情", 938, 412), ("详情", 1176, 412), ("确认选择", 1487, 576))
    bright = CANVAS.copy()
    ImageDraw.Draw(bright).rectangle((1310, 550, 1670, 601), fill=(235, 235, 235))
    open_ = Frame(CANVAS, common)
    first = Frame(CANVAS, common + labels(("已选择", 1118, 192)))
    both = Frame(bright, common + labels(("已选择", 1118, 192), ("已选择", 879, 192)))
    ready = page(return_page, stage="1-2")
    world.war.lineup = policy.LINEUPS[policy.HIGH_ANAXA]
    state = drive(monkeypatch, world, open_, lambda s, point: setattr(
        s, "frame", {(1165, 357): first, (928, 357): both, (1487, 576): ready}[point]))
    assert open_.page == Page.DANCE
    assert first.employee_event_selected == {"花火"}
    assert first.employee_event_confirm() is None
    assert world.war._play_step(open_) is ready
    assert state.clicks == [(Page.DANCE, p) for p in ((1165, 357), (928, 357), (1487, 576))]


def test_dreamscape_dance_pairs_anaxa_with_sparkle_first(monkeypatch, world):
    """攻略：梦境交织指定那刻夏与花火共舞，先于阵容一般顺序里排在前面的白露。"""
    common = labels(("备战阶段", 287, 70), ("1-2", 287, 106), ("梦境交织", 1044, 77),
                    ("选择2个角色进行共舞，为其增加战斗内连携效果", 1044, 136),
                    ("白露", 690, 357), ("那刻夏", 928, 357), ("花火", 1165, 357),
                    ("详情", 700, 412), ("详情", 938, 412), ("详情", 1176, 412), ("确认选择", 1487, 576))
    bright = CANVAS.copy()
    ImageDraw.Draw(bright).rectangle((1310, 550, 1670, 601), fill=(235, 235, 235))
    open_ = Frame(CANVAS, common)
    first = Frame(CANVAS, common + labels(("已选择", 879, 192)))
    both = Frame(bright, common + labels(("已选择", 879, 192), ("已选择", 1118, 192)))
    ready = page(Page.BOARD, stage="1-2")
    world.war.lineup = policy.LINEUPS[policy.HIGH_ANAXA]
    state = drive(monkeypatch, world, open_, lambda s, point: setattr(
        s, "frame", {(928, 357): first, (1165, 357): both, (1487, 576): ready}[point]))
    assert world.war._play_step(open_) is ready
    assert state.clicks == [(Page.DANCE, p) for p in ((928, 357), (1165, 357), (1487, 576))]



@pytest.mark.parametrize("entry", ("single", "loop", "takeover", "daily"))
@pytest.mark.parametrize("ocr_seconds", (0.2, 2.25))
def test_dreamscape_dance_ignores_bright_employee_tab_behind_confirmation(monkeypatch, world, entry, ocr_seconds):
    stage = "2-3"
    confirm, settlement = (1487, 576), (960, 899)
    left, right = (928, 358), (1166, 359)
    common = labels(("备战阶段", 316, 70), (stage, 316, 106), ("梦境交织", 1045, 77),
                    ("选择2个角色进行共舞，为其增加战斗内连携效果", 1045, 136),
                    ("大丽花", *left), ("黑天鹅", *right), ("详情", 936, 412), ("详情", 1174, 412))
    overlaid = CANVAS.copy()
    ImageDraw.Draw(overlaid).rectangle((1404, 569, 1629, 602), fill=(205, 205, 205))
    waiting = labels(("请选择2名共舞的角色", 1492, 521), ("确订", 1460, 577), ("角色赋能", 1516, 585))
    before = Frame(overlaid, common + waiting)
    first_badge = labels(("已选择", 878, 192))
    first = Frame(overlaid, common + waiting + first_badge)
    enabled = CANVAS.copy()
    ImageDraw.Draw(enabled).rectangle((1310, 550, 1670, 601), fill=(235, 235, 235))
    both = Frame(enabled, common + first_badge + labels(("已选择", 1118, 192)))
    won = page(Page.MATCH_RESULT, ("对局胜利", 960, 233), ("返回货币战争", *settlement))
    lobby, modes = home(), mode(("进入超频博弈", 1638, 960))
    rank_page = page(Page.RANK, ("开始对局", 1680, 965), rank_mode="overclock", enemy_rank=1)
    routes = {(lobby, (1600, 972)): modes, (modes, (1638, 960)): rank_page, (rank_page, (1680, 965)): before,
              (before, left): first, (first, right): both, (both, confirm): won, (won, settlement): lobby}
    world.cfg.currencywars_type = "overclock"
    world.cfg.currencywars_rank_difficulty = "lowest"
    world.cfg.currencywars_strategy = "default"
    world.cfg.currencywars_time_limit = 1
    state = SimpleNamespace(frame=before if entry == "takeover" else lobby, clicks=[])

    def capture():
        if state.frame.page == Page.DANCE:
            world.now[0] += ocr_seconds
        return state.frame

    def click(point, *, press_duration):
        state.clicks.append((state.frame.page, point))
        state.frame = routes[state.frame, point]
        return True

    monkeypatch.setattr(world.war, "_capture", capture)
    world.auto.click_element_with_pos.side_effect = click
    monkeypatch.setattr(world.war, "get_reward", lambda f: (
        f, (18000 if world.war.result else 15000, 18000), False))
    assert before.page is Page.DANCE

    if entry == "daily":
        from tasks.daily import daily

        monkeypatch.setattr(daily, "CurrencyWars", lambda: world.war)
        assert daily.Daily._run_currency_wars()
    else:
        assert world.war.start(resume=entry == "takeover", loop=entry == "loop")

    assert state.clicks[-4:] == [(Page.DANCE, left), (Page.DANCE, right), (Page.DANCE, confirm),
                                 (Page.MATCH_RESULT, settlement)]
    world.auto.press_key.assert_not_called()
    assert state.frame is lobby and world.war.result is True


def test_dreamscape_dance_uses_card_locations_when_names_and_badges_are_unreadable(monkeypatch, world):
    common = labels(("备战阶段", 287, 70), ("1-2", 287, 106), ("梦境交织", 1044, 77),
                    ("选择2个角色进行共舞", 1044, 136),
                    ("详情", 938, 412), ("详情", 1176, 412), ("确认选择", 1487, 576))
    bright = CANVAS.copy()
    ImageDraw.Draw(bright).rectangle((1310, 550, 1670, 601), fill=(235, 235, 235))
    initial = Frame(CANVAS, common)
    confirmed = Frame(bright, common)
    ready = page(Page.BOARD, stage="1-2")
    routes = {(938, 355): initial, (1176, 355): confirmed, (1487, 576): ready}
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(s, "frame", routes[p]))

    assert world.war._play_step(initial) is ready
    assert state.clicks == [(Page.DANCE, point) for point in routes]


@pytest.mark.parametrize("details", ((938,), ()), ids=("one-missing", "both-missing"))
def test_dreamscape_dance_uses_distinct_names_when_details_are_unreadable(monkeypatch, world, details):
    common = labels(("备战阶段", 287, 70), ("1-2", 287, 106), ("梦境交织", 1044, 77),
                    ("选择2个角色进行共舞", 1044, 136), ("黑天鹅", 928, 357), ("花火", 1165, 357),
                    *(("详情", x, 412) for x in details))
    confirm = (1487, 576)
    confirm_text = labels(("确认选择", *confirm))
    first_badge = labels(("已选择", 1118, 192))
    image = CANVAS.copy()
    ImageDraw.Draw(image).rectangle((1310, 550, 1670, 601), fill=(235, 235, 235))
    initial = Frame(CANVAS, common + confirm_text)
    first = Frame(CANVAS, common + confirm_text + first_badge)
    both = Frame(image, common + first_badge + labels(("已选择", 879, 192)))
    won = page(Page.MATCH_RESULT, ("对局胜利", 960, 233), ("返回货币战争", 960, 899))
    state = SimpleNamespace(frame=initial, clicks=[])
    routes = {(1165, 357): first, (928, 357): both, confirm: won, (960, 899): home()}

    def click(point, *, press_duration):
        state.clicks.append(point)
        state.frame = routes[point]
        return True

    monkeypatch.setattr(world.war, "_capture", lambda: state.frame)
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))
    monkeypatch.setattr(world.war, "_notify", Mock())
    monkeypatch.setattr(task, "TASK_SECONDS", 22)
    world.auto.click_element_with_pos.side_effect = click

    assert world.war.start(resume=True) is True
    assert state.clicks == list(routes)


def test_dreamscape_dance_does_not_treat_duplicate_labels_as_two_card_slots(monkeypatch, world):
    initial = Frame(CANVAS, labels(
        ("备战阶段", 287, 70), ("1-2", 287, 106), ("梦境交织", 1044, 77), ("选择2个角色进行共舞", 1044, 136),
        ("黑天鹅", 928, 357), ("天鹅", 962, 359), ("详情", 938, 412), ("详情", 944, 413), ("确认选择", 1487, 576),
    ))
    monkeypatch.setattr(world.war, "_capture", lambda: initial)
    monkeypatch.setattr(world.war, "_notify", Mock())
    monkeypatch.setattr(task, "TASK_SECONDS", 22)

    with pytest.raises(task.CurrencyWarsUnavailable, match="未确认两个共舞候选卡位"):
        world.war.start(resume=True)
    world.auto.click_element_with_pos.assert_not_called()


@pytest.mark.parametrize("receipt", ("complete", "missing_badge", "disabled_button"))
def test_dreamscape_dance_rechecks_selection_and_button_when_confirm_text_is_unreadable(monkeypatch, world, receipt):
    common = labels(("备战阶段", 287, 70), ("1-2", 287, 106), ("梦境交织", 1044, 77),
                    ("选择2个角色进行共舞", 1044, 136), ("黑天鹅", 928, 357), ("花火", 1165, 357),
                    ("详情", 938, 412), ("详情", 1176, 412))
    confirm = (1487, 576)
    confirm_text = labels(("确认选择", *confirm))
    first_badge = labels(("已选择", 1118, 192))
    second_badge = labels(("已选择", 879, 192))
    image = CANVAS.copy()
    if receipt != "disabled_button":
        ImageDraw.Draw(image).rectangle((1310, 550, 1670, 601), fill=(235, 235, 235))
    initial = Frame(CANVAS, common + confirm_text)
    first = Frame(CANVAS, common + confirm_text + first_badge)
    picked = Frame(image, common + first_badge + (second_badge if receipt != "missing_badge" else ()))
    ambiguous = Frame(image, common + first_badge)
    won = page(Page.MATCH_RESULT, ("对局胜利", 960, 233), ("返回货币战争", 960, 899))
    routes = {(1165, 357): first, (928, 357): picked, confirm: won, (960, 899): home()}
    state = SimpleNamespace(frame=initial, clicks=[])
    picked_reads = 0

    def capture():
        nonlocal picked_reads
        if receipt == "complete" and state.frame is picked:
            picked_reads += 1
            if picked_reads == 2:
                return ambiguous
        return state.frame

    def click(point, *, press_duration):
        if point == confirm:
            assert picked_reads >= 4
        state.clicks.append(point)
        state.frame = routes[point]
        return True

    monkeypatch.setattr(world.war, "_capture", capture)
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))
    monkeypatch.setattr(world.war, "_notify", Mock())
    monkeypatch.setattr(task, "TASK_SECONDS", 22)
    world.auto.click_element_with_pos.side_effect = click

    assert picked.page == Page.DANCE
    if receipt == "complete":
        assert world.war.start(resume=True) is True
        assert state.clicks == list(routes)
    else:
        with pytest.raises(task.CurrencyWarsUnavailable, match="未确认两个共舞卡位已选中及按钮可用"):
            world.war.start(resume=True)
        assert state.clicks == [(1165, 357), (928, 357)]


def replay_dreamscape_dance(monkeypatch, world, initial, on_click, *, before_capture=None, ocr_seconds=0.2,
                            refuse_input=False):
    state = SimpleNamespace(frame=initial, pending=[], clicks=[])
    world.cfg.currencywars_time_limit = 1
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))
    monkeypatch.setattr(world.war, "_notify", Mock())
    world.auto.input_handler.reports_dispatch = True

    def screenshot():
        world.now[0] += 0.05
        if before_capture is not None and before_capture(state) is False:
            return False
        state.capture = state.pending.pop(0) if state.pending else state.frame
        world.auto.screenshot = state.capture.image
        return True

    def ocr(*, raise_on_error):
        world.now[0] += ocr_seconds if state.capture.page == Page.DANCE else 0.2
        world.auto.ocr_result = [([label.point], (label.text, label.confidence)) for label in state.capture.labels]

    def click(point, *, press_duration):
        if refuse_input or not begin_input_dispatch(world.now[0]):
            return False
        state.clicks.append(point)
        on_click(state, point)
        return True

    world.auto.take_screenshot.side_effect = screenshot
    world.auto.perform_ocr.side_effect = ocr
    world.auto.click_element_with_pos.side_effect = click
    return state


DANCE_CARD_POINTS = ((690, 357), (928, 357), (1166, 358))
DANCE_CONFIRM_POINT = (1492, 576)


def dance_dialog(*chosen, enabled=False, stage="1-3", cards=True):
    common = labels(("备战阶段", 316, 70), (stage, 316, 106), ("梦境交织", 1045, 77),
                    ("选择2个角色进行共舞，为其增加战斗内连携效果", 1045, 136),
                    ("确认选择", *DANCE_CONFIRM_POINT), ("出战", 1790, 751))
    if cards:
        common += labels(*((name, *point) for name, point in zip(("白露", "那刻夏", "花火"), DANCE_CARD_POINTS)),
                         *(("详情", x + 9, 412) for x, _ in DANCE_CARD_POINTS))
    common += labels(*(("已选择", point[0] - 48, 194) for point in chosen))
    image = CANVAS.copy()
    if enabled:
        ImageDraw.Draw(image).rectangle((1310, 550, 1670, 601), fill=(235, 235, 235))
    elif len(chosen) < 2:
        common += labels(("请选择2名共舞的角色", 1492, 521))
    return Frame(image, common)


@pytest.mark.parametrize("entry", ("late_receipts", "takeover_one", "takeover_two"))
def test_dreamscape_dance_replays_three_candidates_and_preserves_current_selections(monkeypatch, world, entry):
    bailu, anaxa, sparkle = DANCE_CARD_POINTS
    initial = dance_dialog()
    already_one = dance_dialog(bailu)
    picked_anaxa = dance_dialog(anaxa)
    both = dance_dialog(anaxa, bailu if entry == "takeover_one" else sparkle, enabled=True)
    won = page(Page.MATCH_RESULT, ("对局胜利", 960, 233), ("返回货币战争", 960, 899))
    # 淡出时只读到了共舞标题和确认字样，仍需要等待真实后续页面。
    fading = Frame(both.image, tuple(label for label in both.labels if label.text in ("梦境交织", "确认选择")))

    def click(state, point):
        if point == anaxa:
            state.frame = both if state.frame is already_one else picked_anaxa
            if entry == "late_receipts":
                state.pending[:] = [initial, initial]
        elif point == sparkle:
            state.frame = both
        elif point == DANCE_CONFIRM_POINT:
            state.pending[:] = [fading]
            state.frame = won
        else:
            assert point == (960, 899)
            state.frame = Frame(CANVAS, home().labels + labels(("入画奇航", 160, 110)))

    start = {"late_receipts": initial, "takeover_one": already_one, "takeover_two": both}[entry]
    state = replay_dreamscape_dance(monkeypatch, world, start, click, ocr_seconds=2.25)
    chosen = {"late_receipts": [anaxa, sparkle], "takeover_one": [anaxa], "takeover_two": []}[entry]
    assert world.war.start(resume=True)
    assert state.clicks == [*chosen, DANCE_CONFIRM_POINT, (960, 899)]
    world.auto.press_key.assert_not_called()


@pytest.mark.parametrize(("fault", "diagnosis"), (
    ("no_candidates", "未确认两个共舞候选卡位"),
    ("wrong_stage", "选卡未派发"),
    ("slow_frame", "选卡未派发"),
    ("input_refused", "选卡未派发"),
    ("missing_receipt", "点选已派发但未确认选中"),
    ("gray_confirm", "确认键持续不可用"),
    ("confirm_refused", "确认输入未派发"),
    ("stuck_confirm", "确认已派发但未转场"),
    ("popup_limit", "点选已派发但未确认选中"),
    ("no_capture", "点选期间画面持续不可用"),
    ("task_limit", "货币战争已到达任务总时限"),
    ("stop", None),
))
def test_dreamscape_dance_reports_the_blocked_phase_and_sends_no_background_input(monkeypatch, world, fault, diagnosis):
    _, anaxa, sparkle = DANCE_CARD_POINTS
    confirm = DANCE_CONFIRM_POINT
    first = dance_dialog(anaxa)
    both = dance_dialog(anaxa, sparkle)
    selected = dance_dialog(anaxa, sparkle, enabled=True)
    initial = dance_dialog(cards=fault != "no_candidates")
    if fault in ("confirm_refused", "stuck_confirm"):
        initial = selected
    if fault == "popup_limit":
        monkeypatch.setattr(task, "DANCE_SECONDS", 1)

    def capture(state):
        if world.auto.take_screenshot.call_count > 1:
            if fault == "wrong_stage":
                state.frame = dance_dialog(stage="1-4")
            if fault == "no_capture":
                return False

    def click(state, point):
        if fault == "gray_confirm":
            state.frame = first if point == anaxa else both
        elif fault in ("task_limit", "stop"):
            state.frame = first

    ocr_seconds = {"slow_frame": 10.1, "popup_limit": 0.55}.get(fault, 0.2)
    state = replay_dreamscape_dance(monkeypatch, world, initial, click, before_capture=capture, ocr_seconds=ocr_seconds,
                                    refuse_input=fault in ("input_refused", "confirm_refused"))
    if fault in ("task_limit", "stop"):
        map_point = world.auto.find_element.side_effect

        def interrupt_after_mapping(*args, **kwargs):
            point = map_point(*args, **kwargs)
            if state.clicks:
                if fault == "task_limit":
                    world.now[0] = world.war.deadline
                else:
                    task.pause_ctl.checkpoint.side_effect = RunStopRequested
            return point

        world.auto.find_element.side_effect = interrupt_after_mapping

    error = {"task_limit": task.CurrencyWarsBudgetExceeded, "stop": RunStopRequested}.get(fault, task.CurrencyWarsUnavailable)
    with pytest.raises(error, match=diagnosis) as failure:
        world.war.start(resume=True)
    expected = {"missing_receipt": [anaxa, sparkle], "gray_confirm": [anaxa, sparkle], "stuck_confirm": [confirm],
                "popup_limit": [anaxa], "task_limit": [anaxa], "stop": [anaxa]}.get(fault, [])
    assert state.clicks == expected
    if error == task.CurrencyWarsUnavailable:
        assert failure.value.preserve_game
        assert f"选卡派发 {len([point for point in expected if point != confirm])} 次" in str(failure.value)
        assert f"确认派发 {expected.count(confirm)} 次" in str(failure.value)
    world.auto.press_key.assert_not_called()


@pytest.mark.parametrize("read_card_names", (True, False))
def test_ranger_appointment_falls_back_to_a_card_and_confirms_without_badge(monkeypatch, world, read_card_names):
    common = labels(("备战阶段", 322, 69), ("3-5", 322, 107), ("巡海游侠", 1046, 77),
                    ("任命1名角色，使其成为巡海游侠", 1045, 134),
                    ("详情", 699, 411), ("详情", 937, 411))
    if read_card_names:
        common += labels(("灵砂", 690, 358), ("花火", 928, 358))
    before = Frame(CANVAS, common)
    assert before.page == Page.RANGER
    assert Frame(CANVAS, common[:3] + common[4:]).page != Page.RANGER
    after = page(Page.BOARD, stage="3-5")

    def click(state, point):
        if point == (1492, 598):
            state.frame = after

    world.war.lineup = policy.LINEUPS[policy.HIGH_ANAXA]
    state = drive(monkeypatch, world, before, click)
    assert world.war._play_step(before) is after
    assert state.clicks == [(Page.RANGER, (928, 358) if read_card_names else (699, 355)),
                            (Page.RANGER, (1492, 598))]


RAIL_HEADER = (("备战阶段", 284, 70), ("2-4", 283, 106), ("开拓商店", 1048, 76))
RAIL_CATALOG = (("累计消耗解锁", 1552, 333), ("0/500", 1552, 408),
                ("详情", 556, 442), ("详情", 806, 442), ("详情", 1056, 442), ("详情", 1306, 442))


@pytest.mark.parametrize("offer", ("全部刷新", "三月七"))
def test_rail_shop_confirms_free_launch_then_closes_the_paid_catalog(monkeypatch, world, offer):
    initial = Frame(CANVAS, labels(*RAIL_HEADER, ("详情", 1056, 442), ("星穹列车，跃迁！", 1011, 380),
                                   ("0", 1137, 380), ("0", 637, 109)))
    catalog = Frame(CANVAS, labels(*RAIL_HEADER, *RAIL_CATALOG, (offer, 493, 382), ("0", 637, 109)))
    ready = page(Page.BOARD, stage="2-4")
    state = drive(monkeypatch, world, initial, lambda s, point: setattr(
        s, "frame", catalog if point == (1011, 380) else ready))
    assert initial.page == Page.RAIL_SHOP
    assert world.war._rail_shop(initial) is ready
    assert state.clicks == [(Page.RAIL_SHOP, (1011, 380)), (Page.RAIL_SHOP, (12, 12))]


@pytest.mark.parametrize("remainder", (RAIL_CATALOG[:2] + RAIL_CATALOG[4:],
                                       RAIL_CATALOG[2:],
                                       RAIL_CATALOG + (("星穹列车，跃迁！", 1011, 380),)))
def test_rail_catalog_requires_multiple_columns_and_the_unlock_panel(remainder):
    frame = Frame(CANVAS, labels(*RAIL_HEADER, *remainder))
    assert frame.page == Page.RAIL_SHOP
    assert not frame.rail_catalog_ready()


@pytest.mark.parametrize("price", (0, 15))
def test_rail_launch_checks_the_local_title_and_free_price(monkeypatch, price):
    frame = Frame(CANVAS, labels(*RAIL_HEADER, ("详情", 1056, 442), ("星弯列车，跃迁！", 1012, 382),
                                 (str(price), 1137, 380)))
    monkeypatch.setattr(frame, "read_local", lambda area: "星穹列车，跃迁！" if area == ui.RAIL_LAUNCH else None)
    assert ui.point(frame.rail_launch()) == ((1012, 380) if price == 0 else None)


@pytest.mark.parametrize("missed", ("累计消耗解锁", "0/500"))
def test_rail_shop_uses_the_catalog_receipt_despite_missing_numbers_or_labels(monkeypatch, world, missed):
    initial = Frame(CANVAS, labels(*RAIL_HEADER, ("详情", 1056, 442), ("星穹列车，跃迁！", 1011, 380),
                                   ("0", 1137, 380)))
    catalog = Frame(CANVAS, labels(*RAIL_HEADER, *(entry for entry in RAIL_CATALOG if entry[0] != missed)))
    ready = page(Page.BOARD, stage=initial.stage)
    routes = {(initial, (1011, 380)): catalog, (catalog, (12, 12)): ready}
    state = drive(monkeypatch, world, initial, lambda s, point: setattr(s, "frame", routes[s.frame, point]))
    assert world.war._rail_shop(initial) is ready
    assert state.clicks == [(Page.RAIL_SHOP, (1011, 380)), (Page.RAIL_SHOP, (12, 12))]
    assert (initial.stage, "开拓商店") in world.war.deferred_operations


@pytest.mark.parametrize(("entry", "fault", "launches", "closes", "keys"), (
    ("single", "lost_launch", [(1011, 380), (1046, 260)], 1, []),
    ("loop", "late_catalog", [(1011, 380)], 1, []),
    ("takeover", "board", [(1011, 380)], 0, []),
    ("daily", "lost_close", [(1011, 380)], 2, []),
    ("takeover", "escape", [(1011, 380)], 2, ["esc", "esc"]),
))
def test_rail_shop_recovers_through_the_task_entry(monkeypatch, world, entry, fault, launches, closes, keys):
    free = Frame(CANVAS, labels(*RAIL_HEADER, ("详情", 1056, 442), ("星穹列车，跃迁！", 1011, 380),
                               ("0", 1137, 380), ("0", 637, 109)))
    unknown = Frame(CANVAS, labels(("2-4", 283, 106)))
    loading = Frame(CANVAS, labels(*RAIL_HEADER, ("详情", 1056, 442)))
    monkeypatch.setattr(loading, "read_local", lambda _area: None)
    catalog = Frame(CANVAS, labels(*RAIL_HEADER, *RAIL_CATALOG, ("0", 637, 109)))
    ready = page(Page.BOARD, stage=free.stage)
    exit_prompt = active_match_exit_dialog()
    result = page(Page.MATCH_RESULT, ("对局胜利", 960, 233), ("返回货币战争", 960, 899))
    lobby, modes = home(), mode(("进入超频博弈", 1638, 960))
    rank_page = page(Page.RANK, ("开始对局", 1680, 965), rank_mode="overclock", enemy_rank=1)
    routes = {(lobby, (1600, 972)): modes, (modes, (1638, 960)): rank_page, (rank_page, (1680, 965)): free,
              (result, (960, 899)): lobby}
    state = SimpleNamespace(frame=free if entry == "takeover" else lobby, after=None, resume_at=None)
    world.cfg.currencywars_type = "overclock"
    world.cfg.currencywars_rank_difficulty = "lowest"
    world.cfg.currencywars_time_limit = 1
    launch_points, close_points, keys_sent = [], [], []

    def capture():
        if state.resume_at is not None and world.now[0] >= state.resume_at:
            state.frame, state.resume_at = state.after, None
        return state.frame

    def click(point, *, press_duration):
        if state.frame is free:
            launch_points.append(point)
            if fault == "lost_launch" and len(launch_points) == 1:
                state.frame, state.after, state.resume_at = unknown, free, world.now[0] + 1
                return False
            if fault == "late_catalog":
                state.frame, state.after, state.resume_at = loading, catalog, world.now[0] + 12
            else:
                state.frame = ready if fault == "board" else catalog
        elif state.frame is catalog:
            close_points.append(point)
            if fault != "escape" and (fault != "lost_close" or len(close_points) > 1):
                state.frame = ready
        else:
            state.frame = routes[state.frame, point]
        return True

    def press(key):
        keys_sent.append(key)
        assert fault == "escape"
        assert state.frame in (catalog, exit_prompt)
        state.frame = exit_prompt if state.frame is catalog else ready
        return True

    def prepare(frame):
        assert frame is ready
        state.frame = result
        return result

    monkeypatch.setattr(world.war, "_capture", capture)
    monkeypatch.setattr(world.war, "_prepare", prepare)
    monkeypatch.setattr(world.war, "_check_weekly_reward",
                        lambda f: (f, (18000 if world.war.result else 15000, 18000), False))
    world.auto.click_element_with_pos.side_effect = click
    world.auto.press_key.side_effect = press
    if entry == "daily":
        from tasks.daily import daily

        monkeypatch.setattr(daily, "CurrencyWars", lambda: world.war)
        assert daily.Daily._run_currency_wars()
    else:
        assert world.war.start(resume=entry == "takeover", loop=entry == "loop")
    assert world.war.result is True and state.frame is lobby
    assert launch_points == launches and close_points == [(12, 12)] * closes and keys_sent == keys


@pytest.mark.parametrize(("fault", "error", "clicks", "keys"), (
    ("free", task.CurrencyWarsUnavailable, [(1011, 380), (1046, 260)], []),
    ("priced", task.CurrencyWarsUnavailable, [], []),
    ("catalog", task.CurrencyWarsUnavailable, [(12, 12), (12, 12)], ["esc"]),
    ("budget", task.CurrencyWarsBudgetExceeded, [(1011, 380)], []),
    ("stopped", RunStopRequested, [(1011, 380)], []),
))
def test_rail_shop_stops_within_the_operation_budget(monkeypatch, world, fault, error, clicks, keys):
    price = "15" if fault == "priced" else "0"
    free = Frame(CANVAS, labels(*RAIL_HEADER, ("详情", 1056, 442), ("星穹列车，跃迁！", 1011, 380),
                               (price, 1137, 380), ("0", 637, 109)))
    catalog = Frame(CANVAS, labels(*RAIL_HEADER, *RAIL_CATALOG))
    initial = catalog if fault == "catalog" else free
    world.cfg.currencywars_time_limit = 5
    monkeypatch.setattr(world.war, "_capture", lambda: initial)
    locate = world.auto.find_element.side_effect

    def locate_then_interrupt(*args, **kwargs):
        point = locate(*args, **kwargs)
        if point == (1046, 260):
            if fault == "budget":
                world.now[0] = world.war.deadline
            if fault == "stopped":
                task.pause_ctl.checkpoint.side_effect = RunStopRequested
        return point

    world.auto.find_element.side_effect = locate_then_interrupt
    with pytest.raises(error) as raised:
        world.war.start(resume=True)
    if error == task.CurrencyWarsUnavailable:
        assert "开拓商店" in str(raised.value) and raised.value.preserve_game
        assert world.now[0] < 45
    assert [call.args[0] for call in world.auto.click_element_with_pos.call_args_list] == clicks
    assert [call.args[0] for call in world.auto.press_key.call_args_list] == keys


@pytest.mark.parametrize("preselected", (False, True))
def test_garden_picks_its_preference_despite_a_preexisting_outline(monkeypatch, world, preselected):
    words = labels(("备战阶段", 282, 72), ("2-3", 281, 108), ("奇兽花园", 1047, 78),
                   ("选择奇美拉", 1046, 135), ("咕噜鱼儿", 499, 402), ("详情", 760, 456),
                   ("我方小队初始能量提升20。", 593, 352), ("急先锋", 896, 403),
                   ("我方全体行动提前100%", 1045, 305), ("详情", 1169, 456), ("看乐子", 1303, 403),
                   ("未完美通关时，获得3次免费刷新。", 1445, 352), ("详情", 1577, 456), ("确认选择", 1492, 599))
    initial = Frame(CANVAS, words)
    if preselected:
        initial.image = CANVAS.copy()
        ImageDraw.Draw(initial.image).rectangle((852, 182, 1240, 427), outline="white", width=3)
    after = page(Page.BOARD, stage="2-3")
    assert initial.page == Page.GARDEN
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(s, "frame", after) if p == (1492, 599) else None)
    assert world.war._play_step(initial) is after
    assert state.clicks == [(Page.GARDEN, (499, 402)), (Page.GARDEN, (1492, 599))]


@pytest.mark.parametrize("hovered", (0, 1))
def test_garden_hover_is_not_a_selection_and_uses_confirmed_backup(monkeypatch, world, hovered):
    stage = "1-2"
    first = ("看乐子", 488, 404)
    backup = ("胶糖卷", 1304, 403)
    third = ("车厘比斯", 908, 403)
    words = labels(("备战阶段", 323, 72), (stage, 323, 109), ("奇兽花园", 1047, 77),
                   ("选择奇美拉", 1046, 136), ("确认选择", 1492, 600), first, backup, third,
                   ("获得3次免费刷新。", 627, 352), ("我方小队前/后台强度提升20%。", 1434, 351),
                   ("失去队友并回复生命值。", 1035, 352),
                   ("详情", 761, 456), ("详情", 1169, 456), ("详情", 1577, 456))

    def card(index, *, ready):
        image = CANVAS.copy()
        draw = ImageDraw.Draw(image)
        for edge in ui.GARDEN_COLUMNS[index]:
            draw.line((edge, 182, edge, 426), fill="white", width=2)
        if ready:
            draw.rectangle((1420, 588, 1571, 612), fill="white")
        else:
            draw.rectangle((1313, 525, 1659, 565), fill=(201, 97, 82))
        return Frame(image, words if ready else words + labels(("请选择奇美拉", 1492, 546)))

    initial = card(hovered, ready=False)
    selected = card(2, ready=True)
    assert initial.page == selected.page == Page.GARDEN
    after = page(Page.BOARD, stage=stage)
    routes = {
        (initial, first[1:]): initial, (initial, (1492, 600)): initial,
        (initial, backup[1:]): selected, (selected, (1492, 600)): after,
    }
    state = drive(monkeypatch, world, initial, lambda st, pt: setattr(st, "frame", routes[st.frame, pt]))
    assert world.war._choose_board_effect(initial) is after
    assert state.clicks == [
        (Page.GARDEN, first[1:]), (Page.GARDEN, (1492, 600)),
        (Page.GARDEN, backup[1:]), (Page.GARDEN, (1492, 600)),
    ]


@pytest.mark.parametrize(("event", "header", "point"), (
    (Page.GARDEN, (("奇兽花园", 1047, 78), ("选择奇美拉", 1046, 135)), (638, 399)),
    (Page.HACK, (("我来当（？）策划", 1047, 78), ("请选择一个骇入效果", 1047, 135)), (790, 399)),
))
def test_board_single_choice_uses_card_and_confirm_positions_when_ocr_misses_them(
        monkeypatch, world, event, header, point):
    initial = Frame(CANVAS, labels(*header))
    board_after = page(Page.BOARD, stage="1-2")
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(s, "frame", board_after)
                  if p == (1492, 599) else None)
    assert initial.page == event
    assert world.war._choose_board_effect(initial) is board_after
    assert state.clicks == [(event, point), (event, (1492, 599))]


@pytest.mark.parametrize(("effects", "choice"), (
    (("我方小队生命增幅提升10%。", "我方小队幸运一击率提升10%。"), 1),
    (("我方后台格挡率提高12%。", "消耗10金币，我方小队幸运一击率提升10%。"), 0),
    (("失去5点小队生命值。", "随机移除一名角色。"), 0),
))
def test_board_effect_prefers_a_benefit_and_can_choose_when_all_cards_have_costs(monkeypatch, world, effects, choice):
    options = labels(("第一只奇美拉", 575, 402), ("第二只奇美拉", 1018, 402))
    stage = "1-4"
    cards = tuple(zip(options, effects))
    initial = page(Page.GARDEN, stage=stage, board_effect_cards=cards)
    after = page(Page.BOARD, stage=stage)
    confirm = (1492, 599)
    option = options[choice]
    routes = {(initial, option.point): initial, (initial, confirm): after}
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    assert world.war._choose_board_effect(initial) is after
    assert state.clicks == [(Page.GARDEN, option.point), (Page.GARDEN, confirm)]


@pytest.mark.parametrize("preselected", (None, 0, 1))
def test_hack_effect_selects_a_confirmed_benefit_with_partial_labels_or_preselection(monkeypatch, world, preselected):
    stage = "1-6"
    option = ("破解芯片LV.2", 1166, 392)
    other = ("炫酷墨镜LV.2", 655, 391)
    words = labels(("备战阶段", 324, 72), (stage, 320, 110), ("我来当（？）策划", 1047, 78),
                   ("请选择一个骇入效果", 1047, 135), ("确认选择", 1492, 599),
                   option, ("弱化节点，降低敌人属性。", 1290, 354), ("详情", 1452, 449))
    if preselected == 0:
        words += labels(other, ("提高敌人难度。", 747, 354), ("详情", 941, 450))

    def selected_card(index):
        image = CANVAS.copy()
        draw = ImageDraw.Draw(image)
        for edge in ui.HACK_COLUMNS[1 if index is None else index]:
            draw.line((edge, 253, edge, 413), fill="white", width=2)
        draw.rectangle((1420, 588, 1571, 610), fill="white")
        if index is None:
            draw.rectangle((1320, 529, 1655, 560), fill=(201, 97, 82))
        return Frame(image, words)

    initial = selected_card(preselected)
    selected = selected_card(1)
    after = page(Page.BOARD, stage=stage)
    assert initial.page == selected.page == Page.HACK
    routes = {(initial, option[1:]): selected, (selected, (1492, 599)): after,
              (initial, (1492, 599)): after}
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    assert world.war._play_step(initial) is after
    assert state.clicks == [(Page.HACK, option[1:]), (Page.HACK, (1492, 599))]


@pytest.mark.parametrize(("left_effect", "right_effect", "choice"), (
    ("帮助你获得更多银狼LV.999。", "提高隐藏分挡位，获得额外强化。", 0),
    ("敌方全体获得额外强化。", "获得额外强化。", 1),
))
def test_hack_accepts_more_employees_or_reinforcement_without_an_enemy_benefit(
        monkeypatch, world, left_effect, right_effect, choice):
    choices = labels(("左边工具", 674, 402), ("右边工具", 1180, 402))
    cards = tuple(zip(choices, (left_effect, right_effect)))
    initial = page(Page.HACK, stage="1-1", board_effect_cards=cards)
    option = choices[choice]
    confirm = (1492, 599)
    after = page(Page.BOARD, stage="1-1")
    routes = {(initial, option.point): initial, (initial, confirm): after}
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    assert world.war._choose_board_effect(initial) is after
    assert state.clicks == [(Page.HACK, option.point), (Page.HACK, confirm)]


def test_plane_reveal_can_follow_boss_and_partner_reveal():
    prelude = Frame(CANVAS, labels(("本场对局首领", 585, 201), ("本局奇遇", 1200, 627), ("下一步", 1400, 982)))
    planes = Frame(CANVAS, labels(("位面", 444, 345), ("位面", 960, 372), ("点击空白处继续", 959, 960)))
    assert prelude.page == planes.page == Page.REVEAL
    assert prelude.reveal_kind != planes.reveal_kind


def test_partner_reveal_recognizes_the_continue_prompt_with_its_first_glyph_occluded():
    prompt = ("击空白处继续", 969, 704)
    frame = Frame(CANVAS, labels(("备战阶段", 285, 70), ("2-1", 284, 108),
                                 ("本局奇遇", 793, 483), ("姬奇猫", 584, 610), prompt))
    assert frame.page == Page.REVEAL
    assert frame.reveal_kind == "奇遇说明"
    assert frame.reveal_button().point == prompt[1:]
    assert Frame(CANVAS, labels(prompt)).reveal_kind is None


@pytest.mark.parametrize(("title", "narrow", "wide", "expected"), (
    ("本局奇遇", "点击空白处继续", None, Page.REVEAL),
    ("本局奇遇", "点击空白处继续头", "点击空白处继续", Page.REVEAL),
    ("本局奇遇", "白处继续", "空白处继续", Page.UNKNOWN),
    ("其它提示", None, "点击空白处继续", Page.UNKNOWN),
))
def test_partner_reveal_uses_a_local_full_prompt_when_the_global_text_is_clipped(
        monkeypatch, title, narrow, wide, expected):
    frame = Frame(CANVAS, labels(("备战阶段", 469, 70), ("3-1", 465, 110),
                                 (title, 794, 484), ("周天鸽", 620, 608), ("白处继续", 997, 736)))
    monkeypatch.setattr(frame, "capacity", (7, 7))
    read = Mock(side_effect=(narrow, wide))
    monkeypatch.setattr(frame, "read_local", read)
    assert frame.page == expected
    if expected == Page.REVEAL:
        assert frame.reveal_kind == "奇遇说明" and frame.reveal_button().text == "点击空白处继续"
    if title != "本局奇遇":
        read.assert_not_called()
    elif narrow == "点击空白处继续":
        read.assert_called_once_with(ui.PARTNER_REVEAL_CONTINUE, recognition_only=True)
    else:
        assert read.call_count == 2
        read.assert_called_with(ui.PARTNER_REVEAL_CONTINUE_WIDE, recognition_only=False)


def test_priced_recruitment_requires_a_named_card_and_confirms_bench_change(monkeypatch, world):
    words = labels(("4费聘用书", 1024, 61), ("请选择1个", 1024, 99), ("3-1", 282, 105),
                   ("黄泉", 538, 382), ("希露瓦", 818, 382), ("风堇", 1344, 382))
    first = Frame(CANVAS, words)
    after = page(Page.BOARD, stage="3-1")
    monkeypatch.setattr(after, "slot_occupied", lambda point: point == (565, 912))
    state = drive(monkeypatch, world, first, lambda s, _: setattr(s, "frame", after))
    assert Frame(CANVAS, words[:1]).choice is None
    assert first.page == Page.CHOICE
    assert world.war._choose(first) is after
    assert state.clicks == [(Page.CHOICE, (1344, 382))]


@pytest.mark.parametrize(("left_effect", "preferred"), (
    ("我方小队速度增幅提高10%。", "打通上下游·金"),
    ("消耗5金币，使我方速度增幅提高10%。", "空仓"),
))
def test_investment_scores_speed_and_does_not_treat_consumables_as_a_charge(world, left_effect, preferred):
    frame = page(Page.CHOICE, ("打通上下游·金", 460, 490), (left_effect, 470, 535), ("空仓", 960, 490),
                 ("获得1件随机的简易装备。", 955, 535), ("备战席没有装备（消耗品除外）则获得2经验值。", 955, 567),
                 ("爆晶矿·金", 1460, 490), ("30%概率获得一个战利品晶矿。", 1464, 535),
                 choice="请选择投资策略")
    assert world.war._choice_option(frame).text == preferred


@pytest.mark.parametrize("right_effect, preferred", (
    ("获得进阶装备，并提升伤害。", "人才大礼包+"),
    ("消耗5金币，获得进阶装备。", "黄金大饭店星徽套组"),
))
def test_bubble_wolf_investment_reads_the_card_row_and_scores_both_gold_cards(world, right_effect, preferred):
    frame = Frame(CANVAS, labels(
        ("请选择投资策略", 960, 100), ("选择一个", 515, 248), ("两个都带走", 1184, 248),
        ("黄金大饭店星徽套组", 514, 570), ("获得1个黄金大饭店星徽", 500, 614),
        ("人才大礼包+", 1006, 570), ("获得2金币。", 1000, 614),
        ("前段发力", 1408, 570), (right_effect, 1401, 614),
    ))

    assert frame.page == Page.CHOICE
    assert frame.investment_titles() == ("黄金大饭店星徽套组", "人才大礼包+", "前段发力")
    option = world.war._choice_option(frame)
    assert option.text == preferred
    assert option.point[1] == 570


def test_bubble_wolf_refreshes_both_gold_cards_with_the_shared_button(monkeypatch, world):
    common = (("请选择投资策略", 960, 100), ("两个都带走", 1184, 248),
              ("彩卡", 514, 570), ("消耗金币", 514, 615), ("刷新次数0", 526, 841))
    before = Frame(CANVAS, labels(*common, ("金卡甲", 1006, 570), ("扣除金币", 1000, 614),
                                  ("金卡乙", 1408, 570), ("损失生命值", 1400, 614), ("刷新次数1", 1218, 841)))
    after = Frame(CANVAS, labels(*common, ("获得装备", 1006, 570), ("获得2件简易装备", 1000, 614),
                                 ("前段发力", 1408, 570), ("后台强度提高", 1400, 614), ("刷新次数0", 1218, 841)))
    state = drive(monkeypatch, world, before, lambda s, _: setattr(s, "frame", after))

    assert world.war._refresh_unusable_investments(before) is after
    assert state.clicks == [(Page.CHOICE, (1135, 841))]


@pytest.mark.parametrize(("title", "title_y", "effect_y", "marker_x", "preferred", "preferred_effect"), (
    ("投资环境", 393, 433, 1160, "连击概念股", "开局时获得连击角色和初始简易装备"),
    ("请选择投资策略", 490, 540, 1122, "全速推进", "速度增幅提高10%，并获得额外金币"),
))
@pytest.mark.parametrize(("catalog_effect", "picks_new"), (
    ("获得一个奇遇伙伴。", True),
    ("消耗5金币，获得一个奇遇伙伴。", False),
    ("只有3个备战席位置，获得3件简易装备。", False),
    ("交换你的小队生命值和金币。", False),
    (None, False),
))
def test_investment_catalog_priority_selects_only_readable_safe_cards(
        world, title, title_y, effect_y, marker_x, preferred, preferred_effect, catalog_effect, picks_new):
    badge = Image.open("assets/images/screen/currency_wars/new.png").convert("RGB")
    image = CANVAS.copy()
    image.paste(badge, (marker_x, 221))
    text = [(preferred, 460, title_y), (preferred_effect, 460, effect_y), ("新投资", 960, title_y)]
    if catalog_effect:
        text.append((catalog_effect, 960, effect_y))
    frame = Frame(image, labels(*text))
    frame.__dict__["choice"] = title

    assert frame.uncollected_investment_columns == {1}
    assert world.war._choice_option(frame).text == preferred
    world.cfg.currencywars_investment_priority = "catalog"
    assert world.war._choice_option(frame).text == ("新投资" if picks_new else preferred)


def test_investment_catalog_falls_back_to_strategy_without_a_badge(world):
    world.cfg.currencywars_investment_priority = "catalog"
    frame = page(Page.CHOICE, ("有备无患", 460, 490), ("获得1件简易装备。", 460, 540),
                 ("全速推进", 960, 490), ("速度增幅提高10%，并获得额外金币。", 960, 540),
                 choice="请选择投资策略")
    assert world.war._choice_option(frame).text == "全速推进"


@pytest.mark.parametrize("preset", (policy.DEFAULT_STRATEGY, policy.HIGH_ANAXA))
@pytest.mark.parametrize("paired", (False, True))
def test_uncollected_all_employee_promotion_is_not_selected(world, preset, paired):
    world.war.default_strategy = preset == policy.DEFAULT_STRATEGY
    world.war.lineup = policy.LINEUPS.get(preset)
    effect = "场上的所有角色会永久升级成比自身高1费的随机角色，获得3个拆装扳手。"
    if paired:
        words = (("选择一个", 515, 248), ("两个都带走", 1184, 248),
                 ("特战资金", 514, 570), ("获得6金币。", 514, 610),
                 ("马上到账", 1005, 570), ("获得额外金币。", 1005, 610),
                 ("全员晋升", 1409, 570), (effect, 1409, 610))
        uncollected = {1, 2}
    else:
        words = (("全员晋升", 460, 490), (effect, 460, 540),
                 ("特战资金", 1460, 490), ("获得6金币。", 1460, 540))
        uncollected = {0}
    frame = page(Page.CHOICE, *words, choice="请选择投资策略", uncollected_investment_columns=uncollected)
    for priority in ("strategy", "catalog"):
        world.cfg.currencywars_investment_priority = priority
        assert world.war._choice_option(frame).text == "特战资金"


def test_investment_fallback_avoids_blacklisted_position_when_other_titles_are_unreadable(monkeypatch, world):
    title = "请选择投资策略"
    frame = page(Page.CHOICE, ("全员晋升", 960, 490), choice=title)
    selected = enable_investment_confirm(page(Page.CHOICE, ("全员晋升", 960, 490), choice=title))
    after = page(Page.BOARD)
    left, middle, right, confirm = (460, 490), (960, 490), (1460, 490), (960, 984)

    def click(state, point):
        if point == right:
            state.frame = selected
        elif point == confirm:
            assert state.frame is selected
            state.frame = after

    state = drive(monkeypatch, world, frame, click)
    assert world.war._choose(frame) is after
    assert [point for _, point in state.clicks] == [left] * 4 + [right, confirm]
    assert all(point != middle for _, point in state.clicks)


@pytest.mark.parametrize("configured", ("strategy", "catalog"))
@pytest.mark.parametrize("title,y", (("投资环境", 393), ("请选择投资策略", 490)))
def test_default_always_selects_uncollected_investment_even_without_the_title(
        monkeypatch, world, configured, title, y):
    world.war.default_strategy = True
    world.cfg.currencywars_investment_priority = configured
    option = page(Page.CHOICE, ("连击概念股", 460, y), ("获得简易装备", 460, y + 50),
                  ("确认", 960, 984), choice=title, uncollected_investment_columns={2})
    selected = enable_investment_confirm(page(Page.CHOICE, ("确认", 960, 984), choice=title))
    after = page(Page.BOARD)
    refresh = Mock(side_effect=AssertionError("默认策略不刷新投资"))
    monkeypatch.setattr(world.war, "_refresh_unusable_investments", refresh)
    routes = {(option, (1460, y)): selected, (selected, (960, 984)): after}
    state = drive(monkeypatch, world, option, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    assert world.war._choose(option) is after
    assert state.clicks == [(Page.CHOICE, (1460, y)), (Page.CHOICE, (960, 984))]
    refresh.assert_not_called()


@pytest.mark.parametrize("preselected", (False, True))
def test_catalog_investment_environment_reselects_and_confirms_without_outline(monkeypatch, world, preselected):
    world.cfg.currencywars_investment_priority = "catalog"
    badge = Image.open("assets/images/screen/currency_wars/new.png").convert("RGB")
    image = CANVAS.copy()
    image.paste(badge, (1150, 216))
    text = labels(("投资环境", 960, 100), ("连击概念股", 460, 393), ("开局获得简易装备", 460, 433),
                  ("新环境", 960, 393), ("获得一个奇遇伙伴", 960, 433), ("确认", 979, 984))
    if preselected:
        draw = ImageDraw.Draw(image)
        for x in (460 - 234, 460 + 234):
            draw.line((x, 406, x, 755), fill="white")
    first = Frame(image, text)
    selected = enable_investment_confirm(Frame(image, text))
    after = page(Page.BOARD)
    state = drive(monkeypatch, world, first, lambda s, pt: setattr(
        s, "frame", selected if pt == (960, 393) else after))

    assert world.war._choose(state.frame) is after
    assert state.clicks == [(Page.CHOICE, (960, 393)), (Page.CHOICE, (979, 984))]


def test_investment_recognizes_team_energy_with_an_amount_between_the_words(world):
    frame = page(Page.CHOICE, ("招财狗", 462, 490), ("获得一个佩佩。战斗胜利后，", 470, 534),
                 ("若未损失小队生命值，则每有", 470, 558), ("一个佩佩就会为你提供1金币。", 470, 582),
                 ("正能量", 1460, 490), ("进入战斗时，我方小队恢复等", 1456, 534),
                 ("同于能量上限20%的能量。", 1456, 558), choice="请选择投资策略")
    assert world.war._choice_option(frame).text == "正能量"


@pytest.mark.parametrize("consumed", (False, True))
def test_investment_redraw_recovers_to_a_safe_card_when_the_quota_is_unclear(monkeypatch, world, consumed):
    common = (("未知策略二", 960, 490), ("消耗金币", 960, 535), ("刷新次数1", 977, 856),
              ("未知策略三", 1460, 490), ("损失生命值", 1460, 535), ("刷新次数1", 1477, 856))
    before = page(Page.CHOICE, *common, ("未知策略一", 460, 490), ("扣除金币", 460, 535),
                  ("刷新次数1", 477, 856), choice="请选择投资策略")
    after = page(Page.CHOICE, *common, ("正能量", 460, 490), ("我方小队恢复等同于能量上限20%的能量。", 460, 535),
                 ("刷新次数0" if consumed else "刷新次数1", 477, 856), choice="请选择投资策略")
    state = drive(monkeypatch, world, before, lambda s, _: setattr(s, "frame", after))
    assert world.war._refresh_unusable_investments(before) is after
    assert world.war._choice_option(after).text == "正能量"
    assert state.clicks == [(Page.CHOICE, (389, 856))]


def test_sparkle_variant_is_not_the_combo_support():
    variant = policy.Offer("火花", 1, (100, 180), 0)
    support = policy.Offer("花火", 2, (350, 180), 1)
    b = board(slot("front", 0, CORE), slot("bench", 0), slot("bench", 1), used=3, lineup=policy.LINEUPS[policy.HIGH_ANAXA])
    assert policy.shop_purchase(b, (variant, support)) == support
    assert policy.shop_purchase(b, (variant,)) is None


@pytest.mark.parametrize(("employee", "equipment", "selected"), (
    ("过渡角色", "常规装备", None),
    ("那刻夏", "常规装备", None),
    ("过渡角色", "常规装备", 0),
))
def test_supply_fallback_uses_a_verified_employee_equipment_column(monkeypatch, world, employee, equipment, selected):
    stage = "3-2"
    x0, x1, x2 = ui.SUPPLY_CENTERS[:3]
    words = (("补给阶段", 961, 162), ("后排角色", x0 - 70, 566), ("护盾装备", x0, 698),
             (employee, x1 - 74, 566), (equipment, x1, 698), ("少读装备的卡", x2 - 60, 566))
    image = CANVAS.copy()
    ImageDraw.Draw(image).rectangle((x1 + 97, 309, x1 + 113, 324), fill="white")

    def supply(chosen):
        view = image.copy()
        if chosen is not None:
            x = ui.SUPPLY_CENTERS[chosen]
            ImageDraw.Draw(view).line((x - 129, 778, x + 129, 778), fill="white", width=3)
        f = Frame(view, labels(*words, (f"已选择{int(chosen is not None)}/1", 1683, 924), ("确认", 1710, 984)))
        f.__dict__.update(page=Page.CHOICE, choice="补给阶段", stage=stage)
        return f

    ready, chosen, after = supply(selected), supply(1), page(Page.BOARD, stage=stage)
    assert [equipment for _, equipment, _ in ready.supply_cards()] == ["护盾装备", equipment, ""]
    routes = {(ready, (x1, 566)): chosen, (chosen, (1710, 984)): after, (ready, (1710, 984)): after}
    state = drive(monkeypatch, world, ready, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    assert world.war._choose(ready) is after
    selection = [(Page.CHOICE, (x1, 566))] if selected is None else []
    assert state.clicks == [*selection, (Page.CHOICE, (1710, 984))]


def test_supply_can_choose_and_confirm_without_count_card_text_or_confirm_ocr(monkeypatch, world):
    header = ("补给阶段", 961, 162)
    initial = Frame(CANVAS, labels(header, ("3-2", 470, 76)))
    unread = page(Page.UNKNOWN)
    selected = Frame(CANVAS, labels(header))
    after = page(Page.BOARD, stage="3-3")
    observations = iter((unread, selected, selected, after))
    state = drive(monkeypatch, world, initial, after_capture=lambda s: setattr(
        s, "frame", next(observations, after)) if s.clicks else None)
    assert world.war._choose(initial) is after
    assert state.clicks == [(Page.CHOICE, (960, 566)), (Page.CHOICE, (1692, 984))]


@pytest.mark.parametrize("first_confirm_lost", (False, True))
def test_takeover_confirms_already_selected_supply_with_unreadable_count(monkeypatch, world, first_confirm_lost):
    confirm = (1692, 984)
    image = CANVAS.copy()
    draw = ImageDraw.Draw(image)
    for x in ui.SUPPLY_CENTERS:
        draw.line((x - 129, 778, x + 129, 778), fill="white", width=3)
    draw.rectangle((confirm[0] - 57, 973, confirm[0] + 57, 996), fill="white")
    ready = Frame(image, labels(("补给阶段", 961, 162), ("确认", *confirm), ("3-2", 470, 76)))
    result = page(Page.MATCH_RESULT, ("挑战成功", 960, 233), ("返回货币战争", 960, 899))
    lobby = home()
    confirm_attempts = []

    def click(state, point):
        if state.frame is ready:
            assert point == confirm
            confirm_attempts.append(world.now[0])
            if first_confirm_lost and len(confirm_attempts) == 1:
                return False
            state.frame = result
        else:
            assert (state.frame, point) == (result, (960, 899))
            state.frame = lobby

    assert ready.supply_selection() is None
    assert all(ready.supply_card_selected(x) for x in ui.SUPPLY_CENTERS)
    monkeypatch.setattr(task, "TASK_SECONDS", 35)
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))
    state = drive(monkeypatch, world, ready, click)

    assert world.war.start(resume=True) is True
    assert state.clicks == [(Page.CHOICE, confirm)] * (1 + first_confirm_lost) + [(Page.MATCH_RESULT, (960, 899))]
    if first_confirm_lost:
        assert confirm_attempts[1] - confirm_attempts[0] >= 4


def test_supply_takes_two_distinct_cards_when_only_the_preferred_card_is_readable(monkeypatch, world):
    supply = Frame(CANVAS, labels(("补给阶段", 961, 162), ("那刻夏", 960, 567), ("增幅装备", 960, 697)))
    won = page(Page.MATCH_RESULT, ("挑战成功", 960, 233), ("返回货币战争", 960, 899))
    lobby = home()
    selected = set()
    world.cfg.currencywars_strategy = "default"
    monkeypatch.setattr(task, "TASK_SECONDS", 45)
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))

    def click(state, point):
        if state.frame is won:
            assert point == (960, 899)
            state.frame = lobby
        elif point == (1692, 984):
            if len(selected) == 2:
                state.frame = won
        else:
            assert point[0] in ui.SUPPLY_CENTERS and point[1] == 566
            selected.symmetric_difference_update((point[0],))

    assert supply.page == Page.CHOICE and supply.supply_selection() is None
    state = drive(monkeypatch, world, supply, click)

    assert world.war.start(resume=True) is True
    assert selected == {960, 605}
    card_clicks = [point for _, point in state.clicks if point[1] == 566]
    assert card_clicks == [(960, 566), (605, 566)]


def test_supply_selects_the_displayed_number_of_cards(monkeypatch, world):
    def supply(selected):
        return Frame(CANVAS, labels(("补给阶段", 961, 162), (f"已选择{selected}/2", 1683, 924)))

    initial, first, both = (supply(count) for count in range(3))
    result = page(Page.BOARD)
    routes = {(960, 566): first, (605, 566): both, (1692, 984): result}
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(s, "frame", routes[p]))

    assert world.war._choose(initial) is result
    assert state.clicks == [(Page.CHOICE, point) for point in routes]


@pytest.mark.parametrize(("required", "late_layout"), ((1, False), (2, False), (2, True)))
def test_four_card_supply_selects_the_displayed_count_without_card_ocr(monkeypatch, world, required, late_layout):
    centers = (428, 783, 1137, 1492)
    image = CANVAS.copy()
    fill = ImageDraw.Draw(image)
    for x in centers:
        fill.rectangle((x - 135, 293, x + 135, 595), fill=(16, 16, 20))

    def supply(selected=()):
        current = image.copy()
        draw = ImageDraw.Draw(current)
        for x in selected:
            draw.line((x - 129, 778, x + 129, 778), fill="white", width=3)
        return Frame(current, labels(("补给阶段", 961, 162), (f"已选择{len(selected)}/{required}", 1683, 924)))

    initial = supply()
    result = page(Page.BOARD)
    selected = set()

    def click(state, point):
        x, y = point
        if point == (1692, 984) and len(selected) == required:
            state.frame = result
        elif x in centers and y == 566:
            selected.symmetric_difference_update((x,))
            state.frame = supply(selected)

    state = drive(monkeypatch, world, initial, click)
    if late_layout:
        # 首帧只有标题和计数。新画面认出四列后，按新布局选卡。
        loading = Frame(CANVAS, initial.labels)
        assert world.war._choose(loading) is initial
        assert state.clicks == []
    assert world.war._choose(initial) is result
    assert len(selected) == required
    assert len(state.clicks) == required + 1
    assert state.clicks[-1] == (Page.CHOICE, (1692, 984))


@pytest.mark.parametrize("centers", ((428, 783, 1137, 1492), ui.SUPPLY_CENTERS))
def test_supply_layout_can_use_equipment_text_when_card_edges_are_unreadable(centers):
    x = centers[1]
    f = Frame(CANVAS, labels(("补给阶段", 961, 162), ("那刻夏", x - 85, 566), ("轮滑鞋", x + 10, 698)))
    assert f.supply_layout == centers
    assert [card[0].point for card in f.supply_cards()] == [(x, 566)]


def test_supply_with_incomplete_or_temporarily_unreadable_count_waits_to_confirm(monkeypatch, world):
    header = ("补给阶段", 961, 162)
    partial = Frame(CANVAS, labels(header, ("已选择1/2", 1683, 924)))
    unread = Frame(CANVAS, labels(header))
    complete = Frame(CANVAS, labels(header, ("已选择2/2", 1683, 924)))
    result = page(Page.BOARD)
    state = drive(monkeypatch, world, partial)

    with pytest.raises(task.CurrencyWarsUnavailable, match="1/2"):
        world.war._choose(partial)
    assert state.clicks and (Page.CHOICE, (1692, 984)) not in state.clicks
    state.clicks.clear()
    state.frame = unread
    with pytest.raises(task.CurrencyWarsUnavailable, match="已选张数"):
        world.war._choose(unread)
    assert state.clicks == []

    state.frame = complete
    world.auto.click_element_with_pos.side_effect = lambda *args, **kwargs: setattr(state, "frame", result)
    assert world.war._choose(complete) is result
    world.auto.click_element_with_pos.assert_called_with((1692, 984), press_duration=task.CLICK_HOLD)


def test_supply_retries_a_card_when_fresh_count_and_selection_are_unchanged(monkeypatch, world):
    header = ("补给阶段", 961, 162)
    frames = [Frame(CANVAS, labels(header, (f"已选择{selected}/3", 1683, 924))) for selected in range(4)]
    result = page(Page.BOARD)
    retry_count = []

    def click(state, point):
        if point == (1692, 984):
            assert state.frame is frames[3]
            state.frame = result
        elif point == (960, 566):
            retry_count.append(world.now[0])
            if len(retry_count) == 2:
                state.frame = frames[1]
        else:
            state.frame = frames[frames.index(state.frame) + 1]

    state = drive(monkeypatch, world, frames[0], click)
    assert world.war._choose(frames[0]) is result
    assert state.clicks == [(Page.CHOICE, point) for point in (
        (960, 566), (960, 566), (605, 566), (1315, 566), (1692, 984),
    )]
    assert retry_count[1] - retry_count[0] >= 4


@pytest.mark.parametrize("stopped", (False, True))
def test_supply_progresses_when_known_multi_select_count_becomes_unreadable(monkeypatch, world, stopped):
    header = ("补给阶段", 961, 162)
    cards = (("那刻夏", 960, 566), ("白露", 605, 566))
    confirm = (1710, 984)
    initial = Frame(CANVAS, labels(header, *cards, ("已选择0/2", 1683, 924)))
    result = page(Page.MATCH_RESULT, ("对局胜利", 960, 233), ("返回货币战争", 960, 899))
    lobby = home()
    reads = 0
    selected = set()

    def capture(state):
        nonlocal reads
        reads += 1
        if reads >= 3 and state.frame not in (result, lobby):
            image = CANVAS.copy()
            draw = ImageDraw.Draw(image)
            for x in selected:
                draw.line((x - 129, 778, x + 129, 778), fill="white", width=3)
            if len(selected) == 2:
                draw.rectangle((confirm[0] - 57, 973, confirm[0] + 57, 996), fill="white")
            state.frame = Frame(image, labels(header, *cards, ("确认", *confirm)))

    def click(state, point):
        if state.frame is result:
            state.frame = lobby
        elif point == confirm and len(selected) == 2:
            state.frame = result
        elif point in ((960, 566), (605, 566)):
            selected.symmetric_difference_update((point[0],))
            if stopped:
                task.pause_ctl.checkpoint.side_effect = RunStopRequested()

    monkeypatch.setattr(task, "TASK_SECONDS", 25)
    monkeypatch.setattr(world.war, "get_reward", lambda f: (f, (100, 18000), False))
    state = drive(monkeypatch, world, initial, click, capture)
    if stopped:
        with pytest.raises(RunStopRequested):
            world.war.start(resume=True)
        assert state.clicks == [(Page.CHOICE, (960, 566))]
    else:
        assert world.war.start(resume=True) is True
        assert state.clicks == [(Page.CHOICE, (960, 566)), (Page.CHOICE, (605, 566)),
                                (Page.CHOICE, confirm), (Page.MATCH_RESULT, (960, 899))]


@pytest.mark.parametrize("next_page", (Page.BOARD, Page.BATTLE))
def test_supply_never_confirms_if_selecting_the_card_already_left_the_popup(monkeypatch, world, next_page):
    initial = Frame(CANVAS, labels(("补给阶段", 961, 162)))
    after = page(next_page, stage="3-3")
    state = drive(monkeypatch, world, initial, lambda s, _: setattr(s, "frame", after))
    assert world.war._choose(initial) is after
    assert state.clicks == [(Page.CHOICE, (960, 566))]


@pytest.mark.parametrize("receipt", ("stable", "retry_lost", "missing_border", "unreadable"))
def test_supply_retries_lost_input_only_after_confirming_the_unselected_card(monkeypatch, world, receipt):
    header = labels(("补给阶段", 961, 162), ("3-2", 470, 76))
    initial = Frame(CANVAS, header)
    result = page(Page.MATCH_RESULT, ("对局胜利", 960, 233), ("返回货币战争", 960, 899))
    lobby = home()
    card_clicks = []
    selected = set()
    views = {}

    def capture(state):
        if len(card_clicks) < len(ui.SUPPLY_CENTERS) or state.frame in (result, lobby):
            return
        key = frozenset(selected)
        if key not in views:
            image = CANVAS.copy()
            draw = ImageDraw.Draw(image)
            for x in selected:
                if receipt == "missing_border" and x == 1670:
                    continue
                draw.line((x - 129, 778, x + 129, 778), fill="white", width=3)
            count = () if receipt == "unreadable" else labels((f"已选择{len(selected)}/3", 1683, 924))
            views[key] = Frame(image, (*header, *count))
        state.frame = views[key]

    def click(state, point):
        if state.frame is result:
            assert point == (960, 899)
            state.frame = lobby
        elif point == (1692, 984):
            if len(selected) == 3:
                state.frame = result
        else:
            x, y = point
            assert y == 566 and x in ui.SUPPLY_CENTERS
            card_clicks.append(x)
            if len(card_clicks) <= 3 or receipt == "retry_lost" and x == 960:
                return False
            selected.symmetric_difference_update((x,))

    monkeypatch.setattr(task, "TASK_SECONDS", 120)
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))
    state = drive(monkeypatch, world, initial, click, capture)
    first_pass = [960, 605, 1315, 250, 1670]
    if receipt in ("stable", "retry_lost"):
        assert world.war.start(resume=True) is True
        retried = [960] if receipt == "stable" else [960, 605]
        assert card_clicks == [*first_pass, *retried]
        assert selected == {250, retried[-1], 1670}
        assert state.clicks[-2:] == [(Page.CHOICE, (1692, 984)), (Page.MATCH_RESULT, (960, 899))]
    else:
        with pytest.raises(task.CurrencyWarsUnavailable, match="多次复核补给"):
            world.war.start(resume=True)
        assert card_clicks == first_pass
        assert selected == {250, 1670}


def test_investment_confirmation_requires_an_enabled_button():
    text = labels(("请选择投资策略", 960, 160), ("确认", 979, 984))
    before = Frame(CANVAS, text)
    assert before.choice_confirm() is None
    chosen = CANVAS.copy()
    draw = ImageDraw.Draw(chosen)
    draw.rectangle((916, 971, 1042, 1002), fill=(236, 235, 226))
    draw.rectangle((770, 270, 1150, 590), fill=(110, 135, 205))
    after = Frame(chosen, text)
    assert after.choice_confirm() is not None


@pytest.mark.parametrize("confirm_x, read_button", ((979, True), (960, False)))
def test_investment_submits_an_enabled_confirm_before_clicking_a_card(monkeypatch, world, confirm_x, read_button):
    bright = CANVAS.copy()
    ImageDraw.Draw(bright).rectangle((914, 970, 1044, 999), fill=(235, 235, 235))
    words = labels(("请选择投资策略", 960, 100), ("全速推进", 460, 490), ("获得5金币。", 460, 535))
    if read_button:
        words += labels(("确认", confirm_x, 984))
    frame = Frame(bright, words)
    ready = page(Page.BOARD, stage="2-2")
    state = drive(monkeypatch, world, frame, lambda s, _: setattr(s, "frame", ready))

    assert world.war._play_step(frame) is ready
    assert state.clicks == [(Page.CHOICE, (confirm_x, 984))]


def test_investment_replans_when_the_rest_of_the_cards_slide_in(monkeypatch, world):
    title = ("投资环境", 960, 101)
    early = page(Page.CHOICE, title, ("幻月游戏概念股", 438, 393),
                 ("开局获得装备", 440, 435), choice="投资环境")
    stable = page(Page.CHOICE, title, ("幻月游戏概念股", 438, 393),
                  ("人身意外险", 960, 393), ("人才下沉", 1477, 393), choice="投资环境")
    selected = enable_investment_confirm(page(Page.CHOICE, title, ("确认", 1082, 984), choice="投资环境"))
    after = page(Page.BOARD)
    frames = iter((early, stable))

    def capture(s):
        s.frame = next(frames, s.frame)

    state = drive(monkeypatch, world, early, lambda s, p: setattr(
        s, "frame", selected if p == (960, 393) else after), capture)
    assert world.war._choose(early) is after
    assert state.clicks == [(Page.CHOICE, (960, 393)), (Page.CHOICE, (1082, 984))]


@pytest.mark.parametrize("replaced_columns", (1, 2))
def test_investment_confirmation_recognizes_a_second_same_title_catalog(monkeypatch, world, replaced_columns):
    title = "请选择投资策略"
    card = ("立即补给", 460, 490)
    first = (card, ("获得3金币。", 460, 535), ("短线防御", 960, 490), ("提高10%防御。", 960, 535),
             ("积攒收益", 1460, 490), ("获得2金币。", 1460, 535))
    second = (card, ("获得3金币。", 460, 535), ("长期防御", 960, 490), ("提高20%防御。", 960, 535),
              ("追加资源" if replaced_columns == 2 else "积攒收益", 1460, 490), ("获得2金币。", 1460, 535))
    confirm = ("确认", 979, 984)
    before = page(Page.CHOICE, *first, choice=title)
    selected = enable_investment_confirm(page(Page.CHOICE, *first, confirm, choice=title))
    following = page(Page.CHOICE, *second, confirm, choice=title)
    following_selected = enable_investment_confirm(page(Page.CHOICE, *second, confirm, choice=title))
    after = page(Page.BOARD)
    routes = {
        (before, card[1:]): selected, (selected, confirm[1:]): following,
        (following, card[1:]): following_selected, (following_selected, confirm[1:]): after,
    }
    state = drive(monkeypatch, world, before, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    expected = [(Page.CHOICE, card[1:]), (Page.CHOICE, confirm[1:])]
    if replaced_columns == 2:
        assert world.war._choose(before) is following
        assert state.clicks == expected
    else:
        assert world.war._choose(before) is after
        assert state.clicks == expected * 2


def test_random_environment_can_replace_three_cards_with_a_single_same_title_card(monkeypatch, world):
    title = "投资环境"
    random = ("随机环境", 440, 394)
    invitation = ("星徽邀请", 960, 393)
    old_words = (random, ("开局额外获得6金币。", 440, 438), ("原中间卡", 960, 394),
                 ("进入其它环境。", 960, 435), ("原右卡", 1460, 395), ("进入其它环境。", 1460, 436))
    new_words = (invitation, ("获得一个星徽。", 962, 434))
    before, selected = (page(Page.CHOICE, *old_words, choice=title) for _ in range(2))
    following, following_selected = (page(Page.CHOICE, *new_words, choice=title) for _ in range(2))
    confirm = Label("确认", (960, 984))
    old_image = CANVAS.copy()
    for x in ui.INVESTMENT_CENTERS:
        ImageDraw.Draw(old_image).rectangle((x - 160, 180, x + 160, 382), fill=(210, 194, 211))
    for f in (before, selected):
        f.image = old_image
    enable_investment_confirm(selected)
    enable_investment_confirm(following_selected)
    after = page(Page.BOARD, stage="1-1")
    routes = {(before, random[1:]): selected, (selected, confirm.point): following,
              (following, invitation[1:]): following_selected, (following_selected, confirm.point): after}
    state = drive(monkeypatch, world, before, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    assert world.war._choose(before) is following
    assert world.war._choose(following) is after
    assert state.clicks == [(Page.CHOICE, point) for point in
                            (random[1:], confirm.point, invitation[1:], confirm.point)]


def test_timed_shop_uses_its_own_hud_and_waits_for_the_actual_return(monkeypatch, world):
    timer = ("剩余时间", 295, 76)
    shop = (("免费刷新", 1618, 490), ("收起", 1623, 982))
    timed = Frame(CANVAS, labels(timer, *shop, ("50", 294, 109)))
    assert timed.page == Page.TIMED_SHOP
    assert Frame(CANVAS, labels(timer)).page == Page.UNKNOWN
    after = page(Page.BOARD, stage="3-1")

    def capture(state):
        if world.now[0] >= 48:
            state.frame = after

    state = drive(monkeypatch, world, timed, after_capture=capture)
    assert world.war._play_step(timed) is after
    assert state.clicks == state.keys == []


def test_forced_shop_refresh_reads_as_an_open_shop_without_a_refresh_price():
    """奇遇「菇菇兔」每 4 秒强制刷新商店、共 7 次：刷新按钮换成「自动刷新」和次数，仍是打开的商店，但不能手动刷新。"""
    header = (("备战阶段", 282, 72), ("3-6", 282, 109), ("收起", 1624, 982))
    forced = Frame(CANVAS, labels(*header, ("自动刷新", 1630, 488), ("0/7", 1630, 530)))
    assert forced.page == Page.SHOP and forced.shop_auto_refreshing
    assert forced.shop_refresh_price is None
    normal = Frame(CANVAS, labels(*header, ("刷新", 1630, 488)))
    assert normal.page == Page.SHOP and not normal.shop_auto_refreshing


def test_shop_waits_out_forced_refreshes_before_reading_offers(monkeypatch, world):
    """强制刷新期间商品每 4 秒变一次：不读也不点，刷完再按常规核对商品，不走异常恢复。"""
    stage = "3-6"
    forced = page(Page.SHOP, stage=stage, gold=33, shop_auto_refreshing=True)
    after = page(Page.SHOP, stage=stage, gold=33, shop_auto_refreshing=False)

    def capture(state):
        state.frame = after if world.now[0] >= 28 else forced

    state = drive(monkeypatch, world, forced, after_capture=capture)
    debug = Mock()
    monkeypatch.setattr(task.log, "debug", debug)
    assert world.war._settle_shop(forced) is after
    assert world.now[0] >= 28
    assert state.clicks == state.keys == []
    assert any("商店正在强制刷新" in call.args[0] for call in debug.call_args_list)


def test_duplicate_employee_waits_on_bench_to_merge():
    dupe = replace(CORE, stars=1)
    f = board(slot("front", 0, dupe), slot("front", 1), slot("bench", 0, dupe),
              slot("bench", 1, FILLER), used=1, capacity=3)
    assert policy.deployment(f) == ((f.slots[3], f.slots[1]),)


def test_coffee_waits_for_dialogue_to_advance_even_with_an_unreadable_balance(monkeypatch, world):
    offer = ("圆硬币咖啡", 1213, 612)
    gain = ("获得5金币。", 1200, 683)
    initial = page(Page.TEA, offer, gain)
    unrelated_gain = page(Page.TEA, offer, gain, ("23", 1063, 77))
    result = page(Page.TEA, ("点击空白处继续", 1550, 922))

    intermediate = iter((unrelated_gain, unrelated_gain, result))
    state = drive(monkeypatch, world, initial, after_capture=lambda s: setattr(s, "frame", next(intermediate, result))
                  if s.clicks else None)
    assert world.war._tea(initial) is result
    assert state.clicks == [(Page.TEA, (1213, 612)), (Page.TEA, (1762, 684))]


def test_wangwangdan_choice_uses_the_confirm_in_its_own_row(monkeypatch, world):
    effect = ("后续敌人星级降低。", 1260, 604)
    initial = page(Page.TEA, ("使出苍龙濯世吧！！！", 1270, 532), effect, ("返回", 1190, 730))
    selected = page(Page.TEA, ("使出苍龙灌世吧！！！", 1270, 532), effect,
                    ("确认", 1762, 604), ("返回", 1190, 730))
    after = page(Page.TEA, ("点击空白处继续", 1492, 922), ("这下轻松啦！", 1260, 530))
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(
        s, "frame", selected if p == (1270, 532) else after))
    assert world.war._tea(initial) == after
    assert state.clicks == [(Page.TEA, (1270, 532)), (Page.TEA, (1762, 604))]


def dragon_cleanse_dialog(centers, *, selected=False, read_names=True, read_confirm=True):
    image = CANVAS.copy()
    draw = ImageDraw.Draw(image)
    draw.rectangle((380, 30, 1710, 437), fill=(31, 31, 37))
    entries = [
        ("备战阶段", 322, 71), ("1-9", 322, 108), ("苍龙濯世", 1046, 59),
        ("汪汪丹会帮你冲洗掉一个敌人词缀。", 1046, 100),
        ("请选择一个词缀", 1492, 462), ("后台区域", 981, 575),
        ("选择主角", 1808, 751), ("商店", 1624, 982),
    ]
    if read_confirm:
        entries.append(("确认选择", 1492, 516))
    for index, x in enumerate(centers):
        draw.rectangle((x - 149, 136, x + 149, 405), fill=(129, 37, 49))
        draw.rectangle((x - 149, 136, x + 149, 180), fill=(18, 17, 21))
        if selected and not index:
            draw.rectangle((x - 149, 136, x + 149, 405), outline=(235, 88, 95), width=3)
        if read_names:
            entries.append((("榜样激励", "永久创伤")[index], x, 159))
    draw.rounded_rectangle((1302, 487, 1682, 545), radius=28,
                           fill=(238, 242, 250) if selected else (61, 64, 103))
    return Frame(image, labels(*entries))


@pytest.mark.parametrize(("centers", "read_controls", "preselected", "from_tea"), (
    ((1046,), True, False, True),
    ((888, 1204), False, False, False),
    ((1046,), True, True, False),
))
def test_dragon_cleanse_removes_one_affix_and_resumes_the_same_node(
        monkeypatch, world, centers, read_controls, preselected, from_tea):
    pending = dragon_cleanse_dialog(centers, read_names=read_controls, read_confirm=read_controls)
    selected = dragon_cleanse_dialog(centers, selected=True, read_names=read_controls, read_confirm=read_controls)
    tea_option = ("使出苍龙濯世吧！！！", 1270, 532)
    tea = page(Page.TEA, tea_option, stage="1-8")
    tea_selected = page(Page.TEA, tea_option, ("确认", 1762, 604), stage="1-8")
    unreadable = Frame(CANVAS, ())
    ready = Frame(CANVAS, labels(("备战阶段", 322, 71), ("1-9", 322, 108),
                                ("前台区域", 970, 315), ("后台区域", 981, 575),
                                ("出战", 1818, 751), ("商店", 1624, 982)))
    result = Frame(CANVAS, labels(("对局胜利", 960, 233), ("返回货币战争", 960, 899)))
    lobby = home()
    assert pending.page == selected.page == Page.DRAGON_CLEANSE
    assert pending.stage == selected.stage == ready.stage == "1-9"
    assert ready.page == Page.BOARD

    initial = tea if from_tea else selected if preselected else pending
    state = SimpleNamespace(frame=initial, clicks=[], unreadable_frames=0)

    def capture():
        if state.frame is unreadable:
            state.unreadable_frames += 1
            if state.unreadable_frames > 2:
                state.frame = ready
        return state.frame

    def click(point, *, press_duration):
        frame = state.frame
        state.clicks.append((frame.page, point))
        if frame is tea:
            assert point == tea_option[1:]
            state.frame = tea_selected
        elif frame is tea_selected:
            assert point == (1762, 604)
            state.frame = pending
        elif frame is pending:
            x, y = point
            assert abs(x - centers[0]) < 100 and 136 < y < 405
            state.frame = selected
        elif frame is selected:
            assert point[0] == 1492 and abs(point[1] - 516) <= 2
            state.frame = unreadable
        elif frame is ready:
            assert point == (1818, 751)
            state.frame = result
        else:
            assert frame is result and point == (960, 899)
            state.frame = lobby
        return True

    def prepare(frame):
        assert frame is ready
        return world.war._advance_board(frame, frame.board_advance)

    monkeypatch.setattr(world.war, "_capture", capture)
    monkeypatch.setattr(world.war, "_prepare", prepare)
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))
    world.auto.click_element_with_pos.side_effect = click

    assert world.war.start(resume=True) is True
    assert state.frame is lobby and state.unreadable_frames == 3
    assert [kind for kind, _ in state.clicks] == (
        [Page.TEA] * (2 if from_tea else 0)
        + [Page.DRAGON_CLEANSE] * (1 if preselected else 2)
        + [Page.BOARD, Page.MATCH_RESULT]
    )
    world.auto.press_key.assert_not_called()


@pytest.mark.parametrize("read_confirm", (True, False))
def test_dragon_cleanse_confirms_when_only_affix_is_unselectable(monkeypatch, world, read_confirm):
    template = dragon_cleanse_dialog((), selected=True, read_confirm=read_confirm)
    image = template.image.copy()
    ImageDraw.Draw(image).rectangle((897, 136, 1195, 405), fill=(68, 70, 77))
    initial = Frame(image, (*template.labels, *labels(("吸星魔王", 1046, 157), ("已禁用", 1046, 375))))
    assert initial.page == Page.DRAGON_CLEANSE
    assert not initial.dragon_affixes
    assert initial.dragon_confirm() is not None
    ready = page(Page.BOARD, stage="1-9")
    state = drive(monkeypatch, world, initial, lambda s, _: setattr(s, "frame", ready))

    assert world.war._play_step(initial) is ready
    assert state.clicks == [(Page.DRAGON_CLEANSE, (1492, 516))]
    assert not state.keys


def test_dragon_cleanse_name_outside_dialog_keeps_the_board():
    frame = Frame(CANVAS, labels(("备战阶段", 322, 71), ("1-9", 322, 108),
                                 ("苍龙濯世", 110, 210), ("前台区域", 970, 315),
                                 ("后台区域", 981, 575), ("选择主角", 1808, 751),
                                 ("商店", 1624, 982)))
    assert frame.page == Page.BOARD


@pytest.mark.parametrize(("centers", "outcome"), (((), "no_cards"), ((1046,), "no_receipt"),
                                                   ((1046,), "stopped"), ((1046,), "timed_out")))
def test_dragon_cleanse_never_confirms_an_unselected_affix(monkeypatch, world, centers, outcome):
    initial = dragon_cleanse_dialog(centers)
    world.war.deadline = 60

    def click(_, point):
        assert abs(point[0] - centers[0]) < 100 and 136 < point[1] < 405
        if outcome == "stopped":
            task.pause_ctl.checkpoint.side_effect = RunStopRequested()
        elif outcome == "timed_out":
            world.now[0] = world.war.deadline
        return False

    state = drive(monkeypatch, world, initial, click)
    error = {"stopped": RunStopRequested, "timed_out": task.CurrencyWarsBudgetExceeded}.get(
        outcome, task.CurrencyWarsUnavailable,
    )
    with pytest.raises(error):
        world.war._play_step(initial)
    if outcome == "no_cards":
        assert not state.clicks
    elif outcome == "no_receipt":
        assert 1 <= len(state.clicks) <= 3
    else:
        assert len(state.clicks) == 1
    assert state.frame is initial and not state.keys


DRAGON_BOND_CHOICES = (("召唤", 688, 352), ("治疗", 927, 352), ("连击", 1167, 352), ("反击", 1408, 352))


def dragon_bond_dialog(*, stage="3-1", selected=None, outline=False, enabled=False):
    image = CANVAS.copy()
    draw = ImageDraw.Draw(image)
    if outline:
        draw.rectangle((1056, 173, 1277, 375), outline=(245, 245, 222), width=3)
    if selected is not None:
        x = next(x for name, x, _ in DRAGON_BOND_CHOICES if name == selected)
        draw.rectangle((x - 100, 182, x + 100, 326), fill=(211, 185, 113))
    if enabled:
        draw.rounded_rectangle((1304, 571, 1680, 623), radius=26, fill=(229, 231, 245))
    return Frame(image, labels(
        ("备战阶段", 323, 71), (stage, 323, 109), ("双龙吟", 1046, 78), ("请选择一个羁绊加入", 1046, 135),
        *DRAGON_BOND_CHOICES, ("确认选择", 1492, 598), ("出战", 1818, 750),
    ))


def test_dragon_bond_outline_and_background_fight_do_not_count_as_selection():
    overlay = dragon_bond_dialog(outline=True)
    assert overlay.page == Page.DRAGON_BOND
    assert not overlay.dragon_bond_selected(overlay.dragon_bond_card("连击"))
    assert overlay.dragon_bond_confirm() is None
    confirmed = dragon_bond_dialog(selected="连击", enabled=True)
    assert confirmed.dragon_bond_selected(confirmed.dragon_bond_card("连击"))
    assert not confirmed.dragon_bond_selected(confirmed.dragon_bond_card("治疗"))
    assert confirmed.dragon_bond_confirm().point == (1492, 598)

    board_with_bond = Frame(CANVAS, labels(
        ("备战阶段", 323, 71), ("3-1", 323, 109), ("双龙吟", 142, 250), ("前台区域", 960, 315),
        ("后台区域", 960, 575), ("商店", 1624, 982), ("出战", 1818, 750),
    ))
    assert board_with_bond.page == Page.BOARD


@pytest.mark.parametrize(("entry", "fault", "target", "clicks"), (
    ("single", "late_confirmation", "连击", [(1167, 352), (1167, 352), (1492, 598)]),
    ("loop", "closed_on_choice", "连击", [(1167, 352)]),
    ("takeover", "preselected", "连击", [(1492, 598)]),
    ("daily", "partial_wrong_selection", "治疗", [(927, 352), (1492, 598)]),
    ("single", "lost_default_choice", None, [(927, 352), (927, 352), (1492, 598)]),
    ("loop", "closed_on_choice", None, [(1167, 352)]),
    ("takeover", "unlabeled_confirm", None, [(1492, 597)]),
    ("daily", "missing_cards", None, [(686, 352), (1492, 598)]),
))
def test_dragon_bond_recovers_to_preparation_through_the_task_entry(monkeypatch, world, entry, fault, target, clicks):
    default = target is None
    stage = "3-5" if default else "3-1"
    overlay = dragon_bond_dialog(stage=stage, outline=fault == "late_confirmation",
                                 selected="连击" if fault == "partial_wrong_selection" else None,
                                 enabled=fault == "partial_wrong_selection")
    if fault == "lost_default_choice":
        overlay = Frame(overlay.image, (*overlay.labels, Label("治疗", (130, 420))))
    if fault == "missing_cards":
        overlay = Frame(overlay.image, tuple(label for label in overlay.labels if label.text not in ui.DRAGON_BOND_NAMES))
    partial = Frame(overlay.image, tuple(label for label in overlay.labels if label.text != "双龙吟"))
    assert partial.page == Page.DRAGON_BOND
    selected = dragon_bond_dialog(stage=stage, selected=target, enabled=True)
    if fault == "unlabeled_confirm":
        selected = Frame(selected.image, tuple(
            label for label in selected.labels if label.text not in (*ui.DRAGON_BOND_NAMES, "确认选择")
        ))
    awaiting_button = dragon_bond_dialog(stage=stage, selected=target)
    ready = Frame(CANVAS, labels(
        ("备战阶段", 323, 71), (stage, 323, 109), ("前台区域", 960, 315), ("后台区域", 960, 575),
        ("连击", 132, 418), ("1/2", 132, 449), ("商店", 1624, 982), ("出战", 1818, 750),
    ))
    source = slot("bench", 0, policy.Unit("备战第1格", True, True))
    destination = slot("front", 0)
    team = board(source, destination, stage=stage, used=0)
    before_move = board_screen(CANVAS, (source, destination), stage=stage)
    before_move.capacity = (0, 3)
    won = page(Page.MATCH_RESULT, ("对局胜利", 960, 233), ("返回货币战争", 960, 899))
    mode_name, mode_button = ("normal", "进入标准博弈") if default else ("overclock", "进入超频博弈")
    lobby, modes = home(), mode((mode_button, 1638, 960))
    rank_page = page(Page.RANK, ("开始对局", 1680, 965), rank_mode=mode_name, enemy_rank=1)
    entered = {"single": before_move, "loop": overlay, "takeover": selected, "daily": partial}[entry]
    routes = {(lobby, (1600, 972)): modes, (modes, (1638, 960)): rank_page, (rank_page, (1680, 965)): entered,
              (ready, (1818, 750)): won, (won, (960, 899)): lobby}
    initial = entered if entry == "takeover" else lobby
    state = SimpleNamespace(frame=initial, clicks=[], after=None, resume_at=None)
    world.cfg.currencywars_time_limit = 1
    world.cfg.currencywars_type = mode_name
    world.cfg.currencywars_rank_difficulty = "lowest"
    if default:
        world.cfg.currencywars_strategy = policy.DEFAULT_STRATEGY
    elif target != "连击":
        lineup = replace(policy.LINEUPS[policy.HIGH_ANAXA], dragon_bond=target)
        monkeypatch.setitem(policy.LINEUPS, policy.HIGH_ANAXA, lineup)

    def capture():
        if state.resume_at is not None and world.now[0] >= state.resume_at:
            state.frame, state.resume_at = state.after, None
        return state.frame

    def click(point, *, press_duration):
        if state.frame is overlay:
            state.clicks.append(point)
            if fault in ("late_confirmation", "lost_default_choice") and len(state.clicks) == 1:
                return False
            if fault == "closed_on_choice":
                state.frame = ready
            else:
                state.frame, state.after, state.resume_at = awaiting_button, selected, world.now[0] + 1
        elif state.frame is selected:
            state.clicks.append(point)
            state.after, state.resume_at = ready, world.now[0] + 9
        else:
            state.frame = routes[state.frame, point]
            if state.frame is partial:
                state.after, state.resume_at = overlay, world.now[0] + 1
        return True

    def prepare(frame):
        if frame is before_move:
            if default:
                return world.war._prepare_default_team(frame, deploy_only=True)
            return world.war._move(frame, team, source, destination)
        assert frame is ready
        return world.war._advance_board(frame, frame.board_advance)

    monkeypatch.setattr(world.war, "_capture", capture)
    monkeypatch.setattr(world.war, "_prepare", prepare)
    monkeypatch.setattr(world.war, "_check_weekly_reward",
                        lambda f: (f, (18000 if world.war.result else 15000, 18000), False))
    world.auto.click_element_with_pos.side_effect = click
    world.auto.drag_mouse.side_effect = lambda *_args, **_kwargs: setattr(state, "frame", overlay) or True
    if entry == "daily":
        from tasks.daily import daily

        monkeypatch.setattr(daily, "CurrencyWars", lambda: world.war)
        assert daily.Daily._run_currency_wars()
    else:
        assert world.war.start(resume=entry == "takeover", loop=entry == "loop")
    assert state.clicks == clicks and state.frame is lobby and world.war.result is True
    assert world.auto.drag_mouse.call_count == int(entry == "single")
    world.auto.press_key.assert_not_called()


@pytest.mark.parametrize(("fault", "error", "clicks"), (
    ("double_label", task.CurrencyWarsUnavailable, []),
    ("low_confidence", task.CurrencyWarsUnavailable, []),
    ("missing_heading", task.CurrencyWarsUnavailable, []),
    ("no_receipt", task.CurrencyWarsUnavailable, [(1492, 598)]),
    ("wrong_node", task.CurrencyWarsUnavailable, [(1492, 598)]),
    ("lost_page", task.CurrencyWarsUnavailable, [(1492, 598)]),
    ("stopped", RunStopRequested, [(1167, 352)]),
    ("deadline", task.CurrencyWarsBudgetExceeded, [(1167, 352)]),
))
def test_dragon_bond_keeps_the_scene_when_an_operation_cannot_continue(monkeypatch, world, fault, error, clicks):
    confirmed = fault in ("no_receipt", "wrong_node", "lost_page")
    frame = dragon_bond_dialog(selected="连击" if confirmed else None, enabled=confirmed)
    if fault in ("no_receipt", "wrong_node", "lost_page", "stopped", "deadline"):
        world.cfg.currencywars_strategy = policy.DEFAULT_STRATEGY
    if fault == "double_label":
        frame = Frame(frame.image, (*frame.labels, Label("连击", (685, 352))))
    if fault == "low_confidence":
        frame = Frame(frame.image, tuple(replace(label, confidence=0.6) if label.text == "连击" else label
                                         for label in frame.labels))
    if fault == "missing_heading":
        frame = Frame(frame.image, tuple(label for label in frame.labels if label.text not in (
            "双龙吟", "请选择一个羁绊加入",
        )))
    state = SimpleNamespace(frame=frame)
    world.cfg.currencywars_time_limit = 1
    monkeypatch.setattr(world.war, "_capture", lambda: state.frame)
    monkeypatch.setattr(task, "MATCH_UNIDENTIFIED_SECONDS", 1)

    def click(point, *, press_duration):
        if fault == "wrong_node":
            state.frame = page(Page.BOARD, stage="3-2")
        if fault == "lost_page":
            state.frame = Frame(CANVAS, ())
        return True

    locate = world.auto.find_element.side_effect

    def locate_then_interrupt(*args, **kwargs):
        point = locate(*args, **kwargs)
        if world.auto.click_element_with_pos.called:
            if fault == "stopped":
                task.pause_ctl.checkpoint.side_effect = RunStopRequested
            if fault == "deadline":
                world.now[0] = world.war.deadline
        return point

    world.auto.find_element.side_effect = locate_then_interrupt
    world.auto.click_element_with_pos.side_effect = click
    with pytest.raises(error) as raised:
        world.war.start(resume=True)
    if error == task.CurrencyWarsUnavailable:
        assert raised.value.preserve_game and world.now[0] < 30
    assert [call.args[0] for call in world.auto.click_element_with_pos.call_args_list] == clicks
    world.auto.press_key.assert_not_called()
    world.auto.drag_mouse.assert_not_called()


def test_tea_meal_continues_when_ocr_misses_the_card_name_and_health(monkeypatch, world):
    label = ("美餐时间", 1200, 411)
    effect = ("回复20小队生命值", 1240, 480)
    initial = page(Page.TEA, effect, ("返回", 1175, 605))
    selected = page(Page.TEA, label, effect, ("确认", 1760, 482))
    after = page(Page.TEA, ("领取茶歇奖励", 960, 196), ("开启", 960, 981))
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(
        s, "frame", selected if p == (1200, 409) else after))
    assert world.war._tea(initial) is after
    assert state.clicks == [(Page.TEA, (1200, 409)), (Page.TEA, (1760, 482))]


@pytest.fixture
def tea_menu():
    return Frame(CANVAS, labels(("M1-8", 895, 62), ("幕后茶歇", 960, 164), ("返回备战界面", 1741, 63),
                                ("享用茶歇", 1535, 647), ("回复20小队生命值", 1535, 783),
                                ("聊一聊", 386, 837), ("摇一摇", 1534, 838)))


def test_tea_after_two_missed_shakes_opens_chat_and_continues_match(monkeypatch, world, tea_menu):
    reward = Frame(CANVAS, labels(("领取茶歇奖励", 960, 196), ("开启", 960, 981)))
    next_board = page(Page.BOARD, stage="1-9")
    routes = {(386, 837): reward, (960, 981): next_board}
    state = drive(monkeypatch, world, tea_menu,
                  lambda s, point: setattr(s, "frame", routes.get(point, tea_menu)))

    assert world.war._tea(tea_menu) is reward
    assert world.war._tea(reward) is next_board
    assert state.clicks == [(Page.TEA, point) for point in ((1534, 838), (1534, 838), (386, 837), (960, 981))]


def test_tea_waits_for_late_receipt_when_shake_temporarily_disappears_from_ocr(monkeypatch, world, tea_menu):
    missing = Frame(CANVAS, tuple(label for label in tea_menu.labels if label.text != "摇一摇"))
    dialogue = Frame(CANVAS, labels(("M1-8", 895, 62), ("返回备战界面", 1741, 63),
                                    ("点击空白处继续", 1534, 922)))

    def capture(state):
        if state.clicks:
            state.frame = dialogue if world.now[0] >= 18 else missing

    state = drive(monkeypatch, world, tea_menu, after_capture=capture)
    assert world.war._tea(tea_menu) is dialogue
    assert state.clicks == [(Page.TEA, (1534, 838))]


@pytest.mark.parametrize("unchanged", (False, True))
def test_tea_requires_visual_confirmation_to_try_chat_when_shake_ocr_is_missing(monkeypatch, world, tea_menu, unchanged):
    image = CANVAS.copy()
    if not unchanged:
        image.paste((218, 218, 218), (1515, 829, 1554, 848))
    missing = Frame(image, tuple(label for label in tea_menu.labels if label.text != "摇一摇"))
    reward = Frame(CANVAS, labels(("领取茶歇奖励", 960, 196), ("开启", 960, 981)))
    state = drive(monkeypatch, world, tea_menu, lambda s, point: setattr(
        s, "frame", missing if point == (1534, 838) else reward))
    world.war.deadline = 60

    if unchanged:
        assert world.war._tea(tea_menu) is reward
        assert state.clicks == [(Page.TEA, (1534, 838)), (Page.TEA, (386, 837))]
    else:
        with pytest.raises(task.CurrencyWarsUnavailable, match="幕后茶歇多次复核后仍无法推进"):
            world.war._tea(tea_menu)
        assert state.clicks == [(Page.TEA, (1534, 838))]


def test_tea_recognizes_the_existing_shake_fallback_without_ocr_labels(monkeypatch, world, tea_menu):
    unreadable = Frame(CANVAS, tuple(label for label in tea_menu.labels if label.text not in ("摇一摇", "聊一聊")))
    reward = Frame(CANVAS, labels(("领取茶歇奖励", 960, 196), ("开启", 960, 981)))
    state = drive(monkeypatch, world, unreadable, lambda s, point: setattr(s, "frame", reward))

    assert world.war._tea(unreadable) is reward
    assert state.clicks == [(Page.TEA, (1534, 837))]


def test_tea_opening_does_not_depend_on_the_background_stage_ocr(monkeypatch, world, tea_menu):
    misread = Frame(CANVAS, tea_menu.labels)
    corrected = Frame(CANVAS, tea_menu.labels)
    misread.__dict__["stage"] = "1-7"
    corrected.__dict__["stage"] = "1-8"
    reward = Frame(CANVAS, labels(("领取茶歇奖励", 960, 196), ("开启", 960, 981)))
    state = drive(monkeypatch, world, corrected, lambda s, point: setattr(s, "frame", reward))

    assert world.war._tea(misread) is reward
    assert state.clicks == [(Page.TEA, (1534, 838))]


def test_tea_retries_shake_when_its_control_recovers_without_any_previous_input(monkeypatch, world, tea_menu):
    shake_only = Frame(CANVAS, tuple(label for label in tea_menu.labels if label.text not in ("聊一聊", "享用茶歇")))
    unreadable = Frame(CANVAS, tuple(label for label in shake_only.labels if label.text != "摇一摇"))
    reward = Frame(CANVAS, labels(("领取茶歇奖励", 960, 196), ("开启", 960, 981)))

    def capture(state):
        if not state.clicks:
            state.frame = shake_only if world.now[0] >= 13 else unreadable

    state = drive(monkeypatch, world, shake_only, lambda s, point: setattr(s, "frame", reward), after_capture=capture)
    assert world.war._tea(shake_only) is reward
    assert state.clicks == [(Page.TEA, (1534, 838))]


def test_tea_unavailable_is_reported_when_shake_and_chat_both_leave_the_same_menu(monkeypatch, world, tea_menu):
    state = drive(monkeypatch, world, tea_menu)
    world.war.deadline = 60

    with pytest.raises(task.CurrencyWarsUnavailable, match="幕后茶歇多次复核后仍无法推进"):
        world.war._play(tea_menu)
    assert state.clicks == [(Page.TEA, point) for point in ((1534, 838), (1534, 838), (386, 837), (386, 837))]


def test_tea_does_not_reopen_the_same_chat_after_returning_from_costly_choices(monkeypatch, world, tea_menu):
    coffee_menu = Frame(CANVAS, labels(("M1-8", 895, 62), ("返回备战界面", 1741, 63),
                                     ("亮晶晶咖啡", 1210, 450), ("获得随机星徽，失去8生命值", 1300, 520),
                                     ("返回", 1175, 809)))
    routes = {(386, 837): coffee_menu, (1175, 809): tea_menu}
    state = drive(monkeypatch, world, tea_menu,
                  lambda s, point: setattr(s, "frame", routes.get(point, tea_menu)))
    world.war.deadline = 60

    with pytest.raises(task.CurrencyWarsUnavailable, match="幕后茶歇返回菜单后仍无法继续"):
        world.war._play(tea_menu)
    assert state.clicks == [(Page.TEA, point) for point in (
        (1534, 838), (1534, 838), (386, 837), (1175, 809), (1534, 838), (1534, 838),
    )]


@pytest.mark.parametrize("recovers", (False, True))
def test_tea_bounds_the_wait_for_unreadable_controls(monkeypatch, world, recovers):
    unreadable = Frame(CANVAS, labels(("M1-8", 895, 62), ("返回备战界面", 1741, 63)))
    reward = Frame(CANVAS, labels(("领取茶歇奖励", 960, 196), ("开启", 960, 981)))

    def capture(state):
        if recovers and world.now[0] >= 20:
            state.frame = reward

    state = drive(monkeypatch, world, unreadable, after_capture=capture)
    world.war.deadline = 60
    if recovers:
        assert world.war._tea(unreadable) is reward
    else:
        with pytest.raises(task.CurrencyWarsUnavailable, match="幕后茶歇持续未识别到可继续的控件"):
            world.war._play(unreadable)
    assert state.clicks == [(Page.TEA, (1534, 922))] * 2


@pytest.fixture
def treasury():
    image = CANVAS.copy()
    ImageDraw.Draw(image).rectangle((1303, 482, 1680, 540), fill="white")
    return Frame(image, labels(
        ("备战阶段", 323, 70), ("3-6", 322, 108), ("珠珠鱼宝库", 1047, 60),
        ("刷新宝库或者拿走全部奖励", 1046, 100), ("刷新", 1174, 510), ("全部拿走", 1492, 510),
        ("后台区域", 971, 576), ("开启宝库", 1816, 752), ("商店", 1624, 982),
    ))


@pytest.mark.parametrize("signals", (
    (("珠珠鱼宝库", 1047, 60),),
    (("珠珠鱼的幸运宝库！", 1047, 60),),
    (("刷新宝库或者拿走全部奖励", 1046, 100),),
    (("刷新", 1174, 510),),
))
def test_treasury_layers_take_priority_over_visible_board_controls(treasury, signals):
    background = treasury.texts((0, 542, 1920, 1080)) + treasury.texts(ui.BOARD_STAGE)
    background += labels(("前台区域", 974, 315))
    claim = labels(("全部拿走", 1492, 510))
    assert Frame(CANVAS, background).page is Page.BOARD
    assert Frame(treasury.image, background + claim + labels(*signals)).page is Page.TREASURY


def test_closing_shop_on_treasure_node_opens_and_claims_the_treasury(monkeypatch, world, treasury):
    common = labels(("备战阶段", 469, 46), ("2-6", 468, 77), ("6/6", 959, 262),
                    ("前台区域", 974, 315), ("后台区域", 976, 575), ("开启宝库", 1816, 752))
    shop = Frame(CANVAS, common + labels(("收起", 1624, 982), ("刷新", 1617, 486)))
    closed = Frame(CANVAS, common + labels(("商店", 1624, 982)))
    opened = Frame(treasury.image, tuple(
        replace(label, text="2-6") if label.text == "3-6" else label for label in treasury.labels
    ))
    next_node = Frame(CANVAS, labels(
        ("备战阶段", 469, 46), ("2-7", 468, 77), ("前台区域", 974, 315),
        ("后台区域", 976, 575), ("商店", 1624, 982), ("出战", 1816, 752),
    ))
    routes = {(shop, (1624, 982)): closed, (closed, (1816, 752)): opened, (opened, (1492, 510)): next_node}
    state = drive(monkeypatch, world, shop, lambda s, p: setattr(s, "frame", routes[s.frame, p]))

    assert shop.page == Page.SHOP
    assert closed.page == Page.BOARD
    assert world.war._play_step(shop) is closed
    assert world.war._finish_preparation(closed, board(stage="2-6", used=6, capacity=6)) is opened
    assert world.war._play_step(opened) is next_node
    assert state.clicks == [(Page.SHOP, (1624, 982)), (Page.BOARD, (1816, 752)), (Page.TREASURY, (1492, 510))]
    assert not state.keys


@pytest.mark.parametrize(("fault", "claim_attempts", "error"), (
    ("late_receipt", 1, None),
    ("lost_click", 2, None),
    ("unchanged", 2, task.CurrencyWarsUnavailable),
    ("missing_receipt", 1, task.CurrencyWarsUnavailable),
    ("deadline", 1, task.CurrencyWarsBudgetExceeded),
    ("stopped", 1, RunStopRequested),
))
def test_treasury_claim_during_takeover(monkeypatch, world, treasury, fault, claim_attempts, error):
    missing_button = Frame(treasury.image, tuple(label for label in treasury.labels if label.text != "全部拿走"))
    unknown = Frame(treasury.image, treasury.texts((0, 542, 1920, 1080)))
    result = Frame(CANVAS, labels(("对局胜利", 960, 233), ("返回货币战争", 960, 899)))
    lobby = Frame(CANVAS, labels(("入画奇航", 164, 79), ("开始货币战争", 1600, 972)))
    state = SimpleNamespace(frame=missing_button if fault == "late_receipt" else treasury, claims=0)
    claim_point = (1492, 510)
    monkeypatch.setattr(world.war, "_notify", Mock())
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))
    monkeypatch.setattr(task, "TASK_SECONDS", 45)

    def capture():
        if fault == "late_receipt":
            if state.frame is missing_button and world.now[0] >= 1:
                state.frame = treasury
            if state.frame is unknown and world.now[0] >= 14:
                state.frame = result
        return state.frame

    def click(point, *, press_duration):
        if state.frame is result and point == (960, 899):
            state.frame = lobby
            return True
        assert state.frame is treasury and point == claim_point
        state.claims += 1
        if fault in ("late_receipt", "missing_receipt"):
            state.frame = unknown
        if fault == "lost_click":
            if state.claims == 1:
                return False
            state.frame = result
        return True

    def locate(target, *_args, **_kwargs):
        point = tuple(round(value * scale) for value, scale in zip(target[:2], (1920, 1080)))
        if fault == "deadline" and state.claims == 1:
            world.now[0] = world.war.deadline
        return point

    def checkpoint():
        if fault == "stopped" and state.claims == 1:
            raise RunStopRequested()

    monkeypatch.setattr(world.war, "_capture", capture)
    world.auto.find_element.side_effect = locate
    world.auto.click_element_with_pos.side_effect = click
    task.pause_ctl.checkpoint.side_effect = checkpoint

    if error is None:
        assert world.war.start(resume=True)
        assert state.frame is lobby
    else:
        with pytest.raises(error) as raised:
            world.war.start(resume=True)
        if error is task.CurrencyWarsUnavailable:
            assert raised.value.preserve_game
            assert "珠珠鱼宝库" in str(raised.value)
            assert world.now[0] < task.TASK_SECONDS
        assert state.frame is (unknown if fault == "missing_receipt" else treasury)

    assert state.claims == claim_attempts
    assert [call.args[0] for call in world.auto.click_element_with_pos.call_args_list] == (
        [claim_point] * claim_attempts + ([(960, 899)] if error is None else [])
    )
    world.auto.press_key.assert_not_called()
    world.auto.drag_mouse.assert_not_called()


def test_start_advances_counted_skip_without_spending_again_when_the_count_changes(monkeypatch, world):
    stage, skip_point = "2-1", (1816, 751)
    common = (("备战阶段", 471, 46), (stage, 469, 78), ("商店", 1624, 982),
              ("前台区域", 974, 314), ("后台区域", 961, 576))
    before = Frame(CANVAS, labels(*common, ("跳过(2/2)", *skip_point)))
    consumed = Frame(CANVAS, labels(*common, ("跳过(1/2)", *skip_point)))
    won = page(Page.MATCH_RESULT, ("对局胜利", 960, 260), ("返回货币战争", 960, 899))
    lobby = home()
    team = board(stage=stage)
    world.cfg.currencywars_strategy = "default"
    monkeypatch.setattr(world.war, "_settle_board", lambda f: f)
    monkeypatch.setattr(world.war, "_collect_preparation_rewards", lambda f: (f, True))
    monkeypatch.setattr(world.war, "_prepare_default_team", lambda f: f)
    monkeypatch.setattr(world.war, "_read_default_board", lambda f: (f, team))
    monkeypatch.setattr(world.war, "_equip", lambda f, _: f)
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))
    receipt_at = None

    def click(state, point):
        nonlocal receipt_at
        if state.frame is before and point == skip_point:
            state.frame = consumed
            receipt_at = world.now[0] + 4
        else:
            assert state.frame is won and point == (960, 899)
            state.frame = lobby

    def capture(state):
        if state.frame is consumed and world.now[0] >= receipt_at:
            state.frame = won

    assert before.page is Page.BOARD and consumed.page is Page.BOARD
    state = drive(monkeypatch, world, before, click, capture)
    assert world.war.start(resume=True)
    assert state.clicks == [(Page.BOARD, skip_point), (Page.MATCH_RESULT, (960, 899))]


def test_shifted_board_during_shop_animation_is_not_ready():
    common = (("备战阶段", 472, 46), ("1-9", 472, 78), ("6/6", 960, 259),
              ("商店", 1624, 982), ("选择主角", 1817, 750), ("幕后茶歇", 1260, 92))
    shifted = Frame(CANVAS, labels(*common, ("前台区域", 975, 332), ("后台区域", 963, 584)))
    settled = Frame(CANVAS, labels(*common, ("前台区域", 975, 315), ("日后台区域", 963, 577)))
    assert shifted.page == Page.UNKNOWN
    assert settled.page == Page.BOARD


@pytest.mark.parametrize(("caption", "used", "extra", "expected"), [
    (("前台区域", 973, 316), 8, (), Page.BOARD),
    (("前台区", 961, 316), 8, (), Page.BOARD),
    (("前台区", 961, 334), 8, (), Page.UNKNOWN),
    (("前台区域", 973, 316), 7, (), Page.UNKNOWN),
    (("前台区域", 973, 316), 8, (("备战阶段", 950, 370),), Page.UNKNOWN),
    (("前台区域", 973, 316), 8, (("备战席已满，需要售卖备战区角色才可开启晶矿", 955, 299),), Page.UNKNOWN),
])
def test_board_recovers_an_obscured_row_caption_only_with_matching_layout(monkeypatch, caption, used, extra, expected):
    common = (("备战阶段", 470, 46), ("3-6", 470, 79), ("商店", 1624, 983), ("出战", 1819, 751))
    frame = Frame(CANVAS, labels(*common, caption, *extra))
    frame.__dict__["capacity"] = (used, 8)
    units = tuple(slot(zone, index, occupied=True) for zone in ("front", "back") for index in range(4))
    monkeypatch.setattr(frame, "field_slots", lambda: units)
    assert frame.page is expected


def test_deployment_accepts_the_verified_board_even_when_dance_covers_the_rear_caption(monkeypatch, world):
    common = (("备战阶段", 470, 46), ("3-6", 470, 79), ("商店", 1624, 983), ("出战", 1819, 751),
              ("前台区", 962, 316))
    source, destination = slot("bench", 3, FILLER), slot("back", 3)
    field = tuple(slot("front", i, occupied=True) for i in range(4)) + tuple(
        slot("back", i, occupied=True) for i in range(3)
    )
    after = Frame(CANVAS, labels(*common, ("后台", 934, 576)))
    after.__dict__["capacity"] = (8, 8)
    monkeypatch.setattr(after, "field_slots", lambda: (*field, replace(destination, occupied=True)))
    monkeypatch.setattr(after, "slot_occupied", lambda point: point == destination.point)
    before = page(Page.BOARD, stage="3-6", capacity=(7, 8))
    monkeypatch.setattr(before, "slot_occupied", lambda point: point == source.point)
    state = drive(monkeypatch, world, before)
    world.auto.drag_mouse.side_effect = lambda *args, **kwargs: setattr(state, "frame", after)
    team = board(*field, source, destination, stage="3-6", used=7, capacity=8)
    assert world.war._move(before, team, source, destination) is after
    world.auto.drag_mouse.assert_called_once()
    assert not state.clicks


@pytest.mark.parametrize("failure", ("population_ocr", "bench_template"))
def test_start_resumes_an_obscured_board_when_local_recognition_fails(monkeypatch, world, failure):
    from module.ocr import ocr

    image = CANVAS.copy()
    draw = ImageDraw.Draw(image)
    for x in (605, 747, 889, 1031, 1173, 1315):
        draw.rectangle((x - 59, 598, x + 59, 731), outline=(78, 74, 113), width=2)
    draw.rectangle((715, 382, 745, 423), fill=(220, 184, 147))
    draw.rectangle((746, 382, 770, 423), fill=(93, 60, 11))
    board_texts = labels(("备战阶段", 470, 46), ("3-6", 470, 79), ("商店", 1624, 983),
                         ("出战", 1819, 751), ("前台区域", 973, 316), ("1/3", 960, 259))
    result = page(Page.MATCH_RESULT, ("挑战成功", 960, 230), ("返回货币战争", 958, 890))
    lobby = home()
    current = None
    clicks = []

    def click(point, **_):
        nonlocal current
        clicks.append(point)
        current = {(1819, 751): result, (958, 890): lobby}[point]
        return True

    template = ui.template

    def load_template(path):
        if failure == "bench_template" and path.endswith("s2_bench_deployment_lock.png"):
            raise FileNotFoundError(path)
        return template(path)

    recognizer = Mock(side_effect=RuntimeError("局部 OCR 推理失败")) if failure == "population_ocr" else Mock(
        return_value=[]
    )
    monkeypatch.setattr(ocr, "recognize_multi_lines", recognizer)
    monkeypatch.setattr(ui, "template", load_template)
    monkeypatch.setattr(world.war, "_capture", lambda: current or Frame(image, board_texts))
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (1, 2), False))
    monkeypatch.setattr(task, "TASK_SECONDS", 20)
    world.cfg.currencywars_strategy = "default"
    world.auto.click_element_with_pos.side_effect = click

    assert world.war.start(resume=True)
    assert world.war.result is True
    assert clicks == [(1819, 751), (958, 890)]
    assert world.now[0] < 20
    task.save_error_screenshot.assert_not_called()
    world.auto.drag_mouse.assert_not_called()
    if failure == "population_ocr":
        assert recognizer.call_count > 1


def test_unreadable_reward_close_template_keeps_a_possible_overlay_unconfirmed(monkeypatch):
    frame = Frame(CANVAS, labels(("获得物品", 960, 300), ("入画奇航", 145, 75),
                                 ("开始货币战争", 1600, 940)))
    monkeypatch.setattr(frame, "match", Mock(side_effect=FileNotFoundError("click_close.png")))
    assert frame.page == Page.UNKNOWN


def test_halo_avoids_basic_attack_priority_and_limits_extra_difficulty():
    f = Frame(CANVAS, labels(("乱披风拳法", 420, 435), ("普攻伤害增幅", 415, 510),
                             ("闪耀蓝星", 1490, 436), ("获得15%前/后台强度", 1496, 542),
                             ("敌人难度+3", 1499, 722)))
    assert f.halo_effect() is None
    assert f.halo_effect(max_difficulty=2) is None
    assert f.halo_effect(max_difficulty=3)[1:] == (1, f.find("闪耀蓝星"))


def test_halo_requires_the_card_title_within_its_title_band():
    title = ("毒药专家", 420, 435)
    other = (("鸟", 420, 402), ("额外受到真实伤害", 420, 546))
    f = Frame(CANVAS, labels(title, *other))
    assert f.halo_effect()[2] == f.halo_title_label(0)
    assert f.halo_effect()[2].text == title[0]
    assert Frame(CANVAS, labels(*other)).halo_effect() is None


def test_halo_refresh_uses_count_and_coins_despite_effect_description_ocr_variation(monkeypatch, world):
    controls = (("刷新", 468, 770), ("自我拷贝·过载", 421, 434), ("闭关", 1486, 434))
    before = page(Page.HALO, *controls, ("1刷新还剩6次", 958, 134), ("所需节占数", 1535, 747), halo_gold=38)
    ready = page(Page.HALO, *controls, ("1刷新还剩6次", 958, 134), ("所需共占数", 1535, 747), halo_gold=38)
    updated_counters = page(Page.HALO, *controls, ("1刷新还剩5次", 958, 134), halo_gold=37)
    after = page(Page.HALO, ("1刷新还剩5次", 958, 134), ("前台专家", 419, 433), halo_gold=37)
    updating = iter((updated_counters, after))

    def capture(s):
        if s.frame is before:
            s.frame = ready
        elif s.clicks:
            s.frame = next(updating, s.frame)

    state = drive(monkeypatch, world, before, after_capture=capture)
    assert world.war._refresh_halo(before, before.halo_refresh_status()) is after
    assert state.clicks == [(Page.HALO, (468, 770))]


@pytest.mark.parametrize(("previous_status", "old_balance"), (("1刷新还剩1次", 29), ("后续刷新费用2", 30)))
def test_halo_refresh_handles_discount_to_regular_price(monkeypatch, world, previous_status, old_balance):
    before = page(Page.HALO, ("刷新", 1552, 774), ("社交达人", 1480, 435), (previous_status, 953, 135),
                  halo_gold=old_balance)
    after = page(Page.HALO, ("如履添翼", 1480, 436), ("后续刷新费用2", 951, 135), halo_gold=28)
    state = drive(monkeypatch, world, before, lambda s, _: setattr(s, "frame", after))
    assert world.war._refresh_halo(before, before.halo_refresh_status(), 1) is after
    assert state.clicks == [(Page.HALO, (1552, 774))]


@pytest.mark.parametrize(("gold", "status", "after_status", "cost"), (
    (0, "免费刷新还剩2次", "免费刷新还剩1次", 0),
    (4, "0刷新还剩1次", "1刷新还剩6次", 0),
    (5, "1刷新还剩2次", None, 1),
    (6, "1刷新还剩2次", "1刷新还剩1次", 1),
    (6, "后续刷新费用2", None, 2),
    (7, "后续刷新费用2", "后续刷新费用2", 2),
    (4, "0刷新还剩0次", None, 0),
    (None, "0刷新还剩1次", None, 0),
))
def test_halo_applies_the_gold_reserve_only_to_confirmed_paid_refreshes(
        monkeypatch, world, gold, status, after_status, cost):
    world.war.halo_candidate = halo_selection(slot("front", 0, CORE))
    right = ("闭关", 1480, 435)
    refresh = ("刷新", 468, 770)
    before = page(Page.HALO, ("乱披风拳法", 420, 435), right, refresh, (status, 958, 134), halo_gold=gold)
    after = page(Page.BOARD)
    routes = {}
    frames = [before]
    if after_status is not None:
        effects = (("前台专家", 420, 435), ("提高前台强度", 420, 545), right, (after_status, 958, 134))
        rolled = page(Page.HALO, *effects, halo_gold=gold - cost)
        chosen = page(Page.HALO, *effects, ("确认", 960, 948), halo_gold=gold - cost)
        monkeypatch.setattr(chosen, "halo_effect_selected", lambda index: index == 0)
        frames.extend((rolled, chosen))
        routes = {(before, refresh[1:]): rolled, (rolled, (420, 435)): chosen, (chosen, (960, 948)): after}
    match_halo_at(monkeypatch, frames, ui.HALO_TARGET)
    state = drive(monkeypatch, world, before, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    if after_status is None:
        routes.update({(before, right[1:]): before, (before, (969, 954)): after})
        assert world.war._halo(before) is after
        assert state.clicks == [(Page.HALO, right[1:]), (Page.HALO, (969, 954))]
    else:
        assert world.war._halo(before) is after
        assert state.clicks == [(Page.HALO, point) for point in (refresh[1:], (420, 435), (960, 948))]


@pytest.mark.parametrize("outcome", ("exhausted", "extra_credit", "price_changed", "unexpected_charge", "no_effect"))
def test_free_halo_refresh_uses_a_verified_quota_and_never_repeats_an_uncertain_charge(monkeypatch, world, outcome):
    refresh = ("刷新", 468, 770)
    title = ("闭关", 420, 435)
    before = page(Page.HALO, refresh, title, ("免费刷新还剩1次", 958, 134), halo_gold=3)
    gold_after = {"extra_credit": 9, "unexpected_charge": 2}.get(outcome, 3)
    after = page(Page.HALO, refresh, ("前台专家", 420, 435), ("免费刷新还剩0次", 958, 134),
                 halo_gold=gold_after)
    state = drive(monkeypatch, world, before,
                  lambda s, _: setattr(s, "frame", after) if outcome != "no_effect" else None)
    if outcome == "price_changed":
        state.frame = page(Page.HALO, refresh, title, ("后续刷新费用2", 958, 134), halo_gold=3)
        with pytest.raises(task.CurrencyWarsActionUnready, match="已尝试 0 次"):
            world.war._refresh_halo(before, before.halo_refresh_status())
        assert state.clicks == []
    elif outcome == "unexpected_charge":
        with pytest.raises(task.CurrencyWarsError, match="已尝试 1 次"):
            world.war._refresh_halo(before, before.halo_refresh_status())
        assert state.clicks == [(Page.HALO, refresh[1:])]
    elif outcome == "no_effect":
        with pytest.raises(task.CurrencyWarsReceiptTimeout, match="已尝试 1 次"):
            world.war._refresh_halo(before, before.halo_refresh_status())
        assert state.clicks == [(Page.HALO, refresh[1:])]
    else:
        assert world.war._refresh_halo(before, before.halo_refresh_status()) is after
        assert state.clicks == [(Page.HALO, refresh[1:])]


def test_halo_reads_the_real_free_caption_and_rejects_conflicting_quotes():
    free = ("免费刷新还剩6次", 960, 136)
    numeric = ("0刷新还剩6次", 961, 140)
    paid = ("后续刷新费用2", 951, 132)
    assert Frame(CANVAS, labels(free)).halo_refresh_status() == (0, 6)
    assert Frame(CANVAS, labels(free, numeric)).halo_refresh_status() == (0, 6)
    assert Frame(CANVAS, labels(free, paid)).halo_refresh_status() is None
    assert Frame(CANVAS, labels(free, ("1刷新还剩6次", 957, 132))).halo_refresh_status() is None


def test_halo_accepts_observed_lucky_hit_or_safe_two_star_shop_effect():
    left = ("光环辐射", 420, 434)
    right = ("未来增援", 1490, 434)
    f = Frame(CANVAS, labels(left, ("提供20%幸运一击率", 419, 544),
                             right, ("商店内概率刷出2星的该角色", 1470, 524)))
    assert f.halo_effect()[2].text == "光环辐射"
    g = Frame(CANVAS, labels(left, ("敌人难度+5", 420, 715),
                             right, ("商店内概率刷出2星的该角色", 1470, 524)))
    assert g.halo_effect()[2].text == "未来增援"


def test_halo_uses_a_safe_support_effect_when_paid_refresh_would_spend_the_reserve(monkeypatch, world):
    world.war.halo_candidate = halo_selection(slot("front", 0, CORE))
    cards = (("守阵者", 415, 434), ("获得20%治疗强度和护盾强度，分摊伤害。", 421, 528),
             ("黑洞引力", 1491, 434), ("施放终结技后，使战斗倒计时延后10行动值。", 1501, 530),
             ("1刷新还剩6次", 958, 134), ("刷新", 401, 771))
    before = page(Page.HALO, *cards, halo_gold=4)
    selected = page(Page.HALO, *cards, halo_gold=4)
    match_halo_at(monkeypatch, (before, selected), ui.HALO_TARGET)
    after = page(Page.BOARD)
    assert before.halo_effect() is None
    assert before.halo_effect(allow_support=True)[2].text == "黑洞引力"
    routes = {(before, (1491, 434)): selected, (selected, (969, 954)): after}
    state = drive(monkeypatch, world, before, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    assert world.war._halo(before) is after
    assert state.clicks == [(Page.HALO, (1491, 434)), (Page.HALO, (969, 954))]


@pytest.mark.parametrize("size", (32, 38, 52))
def test_existing_halo_requires_cyan_marker_in_its_own_slot(size):
    image = CANVAS.copy()
    asset = Image.open("assets/images/screen/currency_wars/s2_halo_assigned.png")
    image.paste(asset.resize((size, size)), (1030 - size // 2, 317 - size // 2))
    f = Frame(image, ())
    assert f.assigned_halo((1030, 405))
    assert not f.assigned_halo((888, 405))


def test_forced_overflow_reserves_prioritize_a_deployed_duplicate_and_keep_core():
    ling = policy.Unit("灵砂", True, True, 2)
    topaz = policy.Unit("托帕&账账", True, True, 2)
    b = board(slot("front", 0, ling), slot("bench", 0, topaz), slot("bench", 1, ling),
              slot("bench", 2, CORE), slot("bench", 3, policy.Unit("星神★阿哈", True, False, 2)))
    assert policy.overflow_reserves(b) == (b.slots[2], b.slots[1])


def test_overflow_does_not_count_a_red_locked_slot_as_a_character():
    image = CANVAS.copy()
    draw = ImageDraw.Draw(image)
    for x in range(1144, 1202, 4):
        draw.rectangle((x, 636, x + 1, 696), fill=(121, 40, 75))
    f = Frame(image, labels(("备战席已满，请出售角色或提升等级", 960, 535)))
    assert f.bench_overflow
    assert not f.slot_occupied((1173, 667))


@pytest.mark.parametrize("known_name", (True, False))
def test_replacement_prompt_preserves_first_halo(monkeypatch, world, known_name):
    dialog = Frame(CANVAS, labels(("是否替换该角色原有光环？", 960, 506), ("取消", 763, 672),
                                 ("确认", 1192, 672)))
    assert dialog.page == Page.HALO_REPLACE
    selection = page(Page.HALO)
    target = slot("front", 0, CORE if known_name else None, occupied=True)
    world.war.halo_candidate = halo_selection(target)
    key = target.unit.name if known_name else (world.war.halo_candidate.stage, target.point)
    state = drive(monkeypatch, world, dialog, lambda s, _: setattr(s, "frame", selection))
    assert world.war._cancel_halo_replacement(dialog) == selection
    assert state.clicks == [(Page.HALO_REPLACE, (763, 672))]
    assert key in world.war.halo_excluded


@pytest.mark.parametrize(("kind", "next_kind", "close_point"), (
    (Page.BLACK_MARKET, Page.BOARD, (12, 12)),
    (Page.HALO_REPLACE, Page.HALO, (763, 672)),
))
@pytest.mark.parametrize("disappears", (True, False))
def test_event_overlay_tries_escape_once_when_safe_close_has_no_receipt(
        monkeypatch, world, kind, next_kind, close_point, disappears):
    overlay = page(kind, ("取消", 763, 672))
    after = page(next_kind, stage="3-4")
    state = drive(monkeypatch, world, overlay)

    def escape(key):
        state.keys.append((state.frame.page, key))
        if disappears:
            state.frame = after

    world.auto.press_key.side_effect = escape
    if disappears:
        assert world.war._play_step(overlay) is after
    else:
        with pytest.raises(task.CurrencyWarsUnavailable, match="已保留当前现场"):
            world.war._play_step(overlay)
    assert state.clicks == [(kind, close_point)] * 2
    assert state.keys == [(kind, "esc")]


@pytest.mark.parametrize("from_fallback", (False, True))
def test_halo_confirms_name_when_center_art_does_not_match(monkeypatch, world, from_fallback):
    sunday = policy.Unit("星期日", True, True, 1)
    target = slot("front", 3, sunday)
    source = ui.HALO_FRONT[3]
    if not from_fallback:
        world.war.halo_candidate = halo_selection(target)
    title = ("强化激素", 1480, 436)
    effects = (title, ("获得40%伤害增幅", 1460, 529), ("全勤底薪", 420, 436),
               ("敌人难度+3", 430, 722))
    empty = page(Page.HALO, *effects)
    filled = page(Page.HALO, *effects, ("尚未选择主角光环", 954, 890), ("角色详情", 147, 954))
    settled = page(Page.HALO, *effects, ("尚未选择主角光环", 954, 890), ("角色详情", 147, 954))
    settled.image = CANVAS.copy()
    ImageDraw.Draw(settled.image).rectangle(ui.HALO_TARGET_FACE, fill=(202, 178, 108))
    detail = Frame(CANVAS, labels(("星期日", 862, 203), ("前后台", 890, 243), ("角色详情", 962, 967)))
    selected = page(Page.HALO, *effects, ("确认", 968, 953))
    selected.image = settled.image.copy()
    after = page(Page.BOARD)
    match_halo_at(monkeypatch, (empty, filled, settled, selected), source)
    monkeypatch.setattr(selected, "halo_effect_selected", lambda index: index == 1)
    routes = {
        (filled, (147, 954)): detail,
        (detail, (1863, 65)): settled,
        (settled, (1480, 436)): selected,
        (selected, (968, 953)): after,
    }
    initial = empty
    if from_fallback:
        initial = page(Page.BOARD, ("选择主角", 1818, 750), stage="2-1")
        routes[initial, (1818, 750)] = empty
        named_board = board(target, stage=initial.stage)
        unnamed = replace(target, unit=replace(target.unit, name="前台第 4 格角色"))
        detailed_read = Mock(return_value=(initial, named_board))
        monkeypatch.setattr(world.war, "_read_board", detailed_read)
        monkeypatch.setattr(world.war, "_read_default_board",
                            Mock(return_value=(initial, board(unnamed, stage=initial.stage))))
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    world.auto.drag_mouse.side_effect = lambda *a, **k: setattr(state, "frame", filled) or True
    if from_fallback:
        assert world.war._advance_existing_team() is empty
    assert world.war._halo(empty) is after
    if from_fallback:
        detailed_read.assert_called_once_with(initial, front_only=True)
    assert world.auto.drag_mouse.call_count == 1
    offset = int(from_fallback)
    assert state.clicks[offset:offset + 2] == [(Page.HALO, (147, 954)), (Page.HALO_DETAIL, (1863, 65))]


@pytest.mark.parametrize("outcome", ("selected", "unchanged", "wrong_employee", "unread_name"))
def test_halo_reselects_after_the_previous_employee_is_retained(monkeypatch, world, outcome):
    target = slot("front", 2, policy.Unit("花火", True, False, 2))
    source = ui.HALO_FRONT[target.index]
    world.war.halo_candidate = halo_selection(target)
    effects = (("前台专家", 425, 437), ("获得40%伤害增幅", 411, 532),
               ("乱披风拳法", 1481, 437), ("角色详情", 147, 954), ("返回备战界面", 1772, 66))
    previous = page(Page.HALO, *effects, ("确认", 968, 953))
    current = page(Page.HALO, *effects, ("尚未选择主角光环", 954, 890))
    chosen = page(Page.HALO, *effects, ("确认", 968, 953))
    current.image = CANVAS.copy()
    ImageDraw.Draw(current.image).rectangle(ui.HALO_TARGET_FACE, fill=(186, 93, 124))
    chosen.image = current.image.copy()
    name = target.unit.name if outcome == "selected" else "星期日"
    old_detail = page(Page.HALO_DETAIL, (CORE.name, 862, 203))
    new_detail = page(Page.HALO_DETAIL) if outcome == "unread_name" else page(Page.HALO_DETAIL, (name, 862, 203))
    after = page(Page.BOARD)
    preview = page(Page.BOARD, ("返回主角选择", 1788, 66), stage="2-7")
    match_halo_at(monkeypatch, (previous, current, chosen), source)
    monkeypatch.setattr(previous, "halo_effect_selected", lambda index: index == 1)
    monkeypatch.setattr(chosen, "halo_effect_selected", lambda index: index == 0)
    routes = {
        (previous, (147, 954)): old_detail,
        (old_detail, (1863, 65)): previous,
        (current, (147, 954)): new_detail,
        (current, (1772, 66)): preview,
        (new_detail, (1863, 65)): current,
        (current, (425, 437)): chosen,
        (chosen, (968, 953)): after,
    }
    state = drive(monkeypatch, world, previous, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    if outcome != "unchanged":
        world.auto.drag_mouse.side_effect = lambda *a, **k: setattr(state, "frame", current) or True
    details = [(Page.HALO, (147, 954)), (Page.HALO_DETAIL, (1863, 65))]
    if outcome in ("selected", "unread_name"):
        assert world.war._halo(previous) is after
        assert state.clicks == details * 2 + [(Page.HALO, (425, 437)), (Page.HALO, (968, 953))]
        assert world.auto.drag_mouse.call_count == 1
    elif outcome == "unchanged":
        with pytest.raises(task.CurrencyWarsError, match="主角光环未确认放入角色"):
            world.war._halo(previous)
        assert state.clicks == details
        assert world.auto.drag_mouse.call_count == 3
    else:
        assert world.war._halo(previous) is preview
        assert state.clicks == details * 2 + [(Page.HALO, (1772, 66))]
        assert world.auto.drag_mouse.call_count == 1


def test_halo_sees_the_landed_portrait_even_if_the_caption_is_unreadable(monkeypatch, world):
    world.war.default_strategy = True
    world.war.halo_candidate = halo_selection(slot("front", 0, CORE))
    effects = (("前台专家", 420, 436), ("获得40%伤害增幅", 420, 532))
    empty = page(Page.HALO, *effects)
    landed = page(Page.HALO, *effects)
    landed.image = CANVAS.copy()
    ImageDraw.Draw(landed.image).rectangle((944, 421, 980, 461), fill=(210, 165, 150))
    match_halo_at(monkeypatch, (empty, landed), ui.HALO_FRONT[0])
    returned = page(Page.BOARD)

    def click(state, point):
        assert state.frame is landed
        if point == (969, 954):
            state.frame = returned

    state = drive(monkeypatch, world, empty, click)
    world.auto.drag_mouse.side_effect = lambda *a, **k: setattr(state, "frame", landed) or True
    assert world.war._halo(empty) is returned
    assert world.auto.drag_mouse.call_count == 1
    assert state.clicks == [(Page.HALO, (420, 436)), (Page.HALO, (969, 954))]


@pytest.mark.parametrize(("entry", "outcome"), (
    ("single", "resampled"), ("loop", "resampled"), ("takeover", "resampled"), ("daily", "resampled"),
    ("takeover", "fixed"), ("takeover", "unavailable"), ("takeover", "budget"), ("takeover", "stopped"),
))
def test_halo_recovers_from_an_ambiguous_portrait_in_the_same_run(monkeypatch, world, entry, outcome):
    stage = "2-7"
    front, backup = slot("front", 0, CORE), slot("front", 1, FILLER)
    team = board(front, backup, stage=stage)
    rng = np.random.default_rng(1373)
    old, fresh, alternate = rng.integers(24, 232, size=(3, 61, 60, 3), dtype=np.uint8)
    open_point, back_point, effect_point, confirm_point = (1790, 66), (1772, 66), (420, 436), (969, 954)

    def preview(portrait):
        f = page(Page.BOARD, ("返回主角选择", *open_point), stage=stage, capacity=(2, 4), gold=3)
        f.image = CANVAS.copy()
        for (x, y), card in ((front.point, portrait), (backup.point, alternate)):
            f.image.paste(Image.fromarray(card), (x - 30, y - 31))
        return f

    def halo(first, second, *, placed=None):
        captions = labels(("选择一个角色获得主角光环", 960, 90), ("返回备战界面", *back_point),
                          ("前台专家", *effect_point), ("获得40%伤害增幅", 420, 532))
        image = CANVAS.copy()
        for (x, y), portrait in zip((*ui.HALO_FRONT[:2], ui.HALO_TARGET), (first, second, placed)):
            if portrait is not None:
                tile = ui.cv2.resize(portrait.astype(np.float32), (42, 46), interpolation=ui.cv2.INTER_AREA)
                image.paste(Image.fromarray(tile.astype(np.uint8)), (x - 21, y - 23))
        return Frame(image, captions)

    before, reread = preview(old), preview(fresh)
    ambiguous, correct = halo(old, old), halo(fresh, alternate)
    landed = halo(fresh, alternate, placed=fresh if outcome == "resampled" else alternate)
    result = page(Page.MATCH_RESULT, ("对局胜利", 962, 241), ("返回货币战争", 962, 893))
    lobby, modes, ready = home(), mode(("进入标准博弈", 1638, 960)), rank()
    routes = {(lobby, (1600, 972)): modes, (modes, (1638, 960)): ready, (ready, (1680, 965)): before,
              (result, (962, 893)): lobby, (before, open_point): ambiguous,
              (reread, open_point): correct, (landed, effect_point): landed, (landed, confirm_point): result}
    visited = []
    drags = []

    def read_board(f, *, front_only):
        assert front_only
        visited.append(f)
        return f, team

    def click(state, point):
        if state.frame is ambiguous and point == back_point:
            state.frame = reread if visited and outcome == "resampled" else before
        else:
            if state.frame is landed:
                expected = backup if outcome == "fixed" else front
                assert world.war.halo_candidate.cards[0][0] == expected
            state.frame = routes[state.frame, point]

    def drag(start, end, **_):
        assert tuple(round(p * size) for p, size in zip(end, (1920, 1080))) == ui.HALO_TARGET
        drags.append(tuple(round(p * size) for p, size in zip(start, (1920, 1080))))
        if outcome == "budget":
            world.now[0] = world.war.deadline
        elif outcome == "stopped":
            task.pause_ctl.checkpoint.side_effect = RunStopRequested
        elif outcome == "resampled" or (outcome == "fixed" and len(drags) == 2):
            state.frame = landed
        return True

    state = drive(monkeypatch, world, ambiguous if entry == "takeover" else lobby, click)
    monkeypatch.setattr(world.war, "_read_board", read_board)
    monkeypatch.setattr(world.war, "get_reward",
                        lambda f: (f, (18000 if world.war.result else 0, 18000), False))
    world.auto.drag_mouse.side_effect = drag

    if entry == "daily":
        from tasks.daily import daily

        monkeypatch.setattr(daily, "CurrencyWars", lambda: world.war)
        assert daily.Daily._run_currency_wars()
    elif outcome in ("resampled", "fixed"):
        assert world.war.start(resume=entry == "takeover", loop=entry == "loop")
    else:
        errors = {"unavailable": task.CurrencyWarsUnavailable, "budget": task.CurrencyWarsBudgetExceeded,
                  "stopped": RunStopRequested}
        with pytest.raises(errors[outcome]):
            world.war.start(resume=True)

    back_count = (1 if outcome == "resampled" else 2) + (entry == "takeover")
    assert state.clicks.count((Page.HALO, back_point)) == back_count
    assert visited == ([before, reread] if outcome == "resampled" else [before] * 3)
    assert drags == list(ui.HALO_FRONT[:2 if outcome in ("fixed", "unavailable") else 1])
    finished = outcome in ("resampled", "fixed")
    submissions = [point for page_, point in state.clicks if page_ == Page.HALO and point != back_point]
    assert submissions == ([effect_point, confirm_point] if finished else [])
    assert state.frame is (lobby if finished else ambiguous)
    assert task.save_error_screenshot.call_count == (outcome in ("unavailable", "budget"))


def mentor_dialog(candidates, *, selected=False, read_names=True, read_confirm=True, confirm_y=493, warning=False):
    image = CANVAS.copy()
    draw = ImageDraw.Draw(image)
    entries = [("从师", 960, 66), ("请选择1名角色作为师父，受益于其羁绊效果", 960, 103),
               ("备战阶段", 291, 75), ("1-9", 291, 108), ("商店", 1620, 982), ("出战", 1818, 750)]
    card_shift = round((confirm_y - 493) * 0.58)
    for name, x in candidates:
        draw.rectangle((x - 78, 294 + card_shift, x + 77, 316 + card_shift), fill=(37, 151, 170))
        if read_names:
            entries.append((name, x, 331 + card_shift))
    if read_confirm:
        entries.append(("确认选择", 1492, confirm_y))
    if warning and not selected:
        entries.append(("请选择一名角色", 1492, confirm_y - 53))
    draw.rectangle((1359, confirm_y - 19, 1625, confirm_y + 19),
                   fill=(233, 227, 206) if selected else (111, 111, 111))
    if not selected:
        # 未选中时仍显示白色按钮文案，点亮与否由文字两侧的底色决定。
        draw.rectangle((1450, confirm_y - 8, 1534, confirm_y + 8), fill=(235, 235, 235))
    return Frame(image, labels(*entries))


@pytest.mark.parametrize(("names", "centers", "read_names"), (
    (("忘归人", "大丽花", "火花", "罗刹"), (605, 836, 1065, 1299), False),
    (("火花", "绯英", "星神★阿哈", "真珠", "星期日"), (383, 637, 890, 1143, 1394), True),
))
def test_halo_mentor_reads_the_visible_cards_and_the_enabled_confirm(names, centers, read_names):
    candidates = tuple(zip(names, centers))
    frame = mentor_dialog(candidates, read_names=read_names)
    assert frame.page == Page.HALO_MENTOR
    assert frame.action_context == (Page.HALO_MENTOR, None, None)
    assert tuple(card.point[0] for card in frame.mentor_candidates) == centers
    assert tuple(card.text for card in frame.mentor_candidates) == (names if read_names else ("候选角色",) * len(names))
    assert frame.mentor_confirm() is None

    selected = mentor_dialog(candidates, selected=True, read_confirm=False)
    assert selected.page == Page.HALO_MENTOR
    assert ui.point(selected.mentor_confirm()) == (1492, 493)

    effect = Frame(CANVAS, labels(("选择一个角色获得主角光环", 960, 90), ("从师", 420, 436),
                                 ("使角色受益于师父的非独立羁绊效果", 420, 536)))
    assert effect.page == Page.HALO


@pytest.mark.parametrize("confirm_y", (493, 537))
def test_halo_mentor_falls_back_on_both_layouts_without_names_or_confirm_ocr(confirm_y):
    candidates = (("流萤", 544), ("景元", 825), ("长夜月", 1105), ("爻光", 1387), ("瓦尔特", 1616))
    frame = mentor_dialog(candidates, read_names=False, read_confirm=False, confirm_y=confirm_y, warning=True)
    assert frame.page == Page.HALO_MENTOR
    assert frame.mentor_confirm() is None
    assert [(card.text, card.point[0]) for card in frame.mentor_candidates] == [
        ("候选角色", x) for _, x in candidates
    ]

    selected = mentor_dialog(candidates, selected=True, read_names=False, read_confirm=False, confirm_y=confirm_y)
    assert selected.page == Page.HALO_MENTOR
    assert ui.point(selected.mentor_confirm()) == (1492, confirm_y)
    assert [card.point[0] for card in selected.mentor_candidates] == [x for _, x in candidates]


@pytest.mark.parametrize("entry", ("single", "loop", "daily"))
def test_halo_mentor_waits_through_intermediate_board_and_recovers_missing_inputs(monkeypatch, world, entry):
    stage = "1-9"
    choose, effect, submit, fight = (1818, 750), (420, 436), (969, 954), (1818, 750)
    before = page(Page.BOARD, ("选择主角", *choose), stage=stage)
    team = board(slot("front", 0, CORE), stage=stage)
    halo = page(Page.HALO, ("从师", *effect), ("受益于其羁绊效果", 420, 537), ("乱披风拳法", 1490, 436))
    match_halo_at(monkeypatch, (halo,), ui.HALO_TARGET)
    transient = page(Page.BOARD, ("出战", *fight), stage=stage)
    names = (("火花", 383), ("绯英", 637), ("星神★阿哈", 890), ("真珠", 1143), ("星期日", 1394))
    mentor = mentor_dialog(names, read_names=False)
    selected = mentor_dialog(names, selected=True, read_confirm=False)
    ready = page(Page.BOARD, ("出战", *fight), stage=stage)
    result = page(Page.MATCH_RESULT, ("对局胜利", 962, 241), ("返回货币战争", 962, 893))
    lobby, modes, rank_page = home(), mode(("进入标准博弈", 1638, 960)), rank()
    routes = {(lobby, (1600, 972)): modes, (modes, (1638, 960)): rank_page,
              (rank_page, (1680, 965)): before, (before, choose): halo, (halo, effect): halo,
              (halo, submit): transient, (ready, fight): result, (result, (962, 893)): lobby}
    first, second = (card.point for card in mentor.mentor_candidates[:2])
    confirm = (1492, 493)
    reveal_at = None
    misses = []
    prepared = []

    def prepare(frame):
        prepared.append(frame)
        if frame is before:
            return world.war._enter_halo(frame, team)
        assert frame is ready
        return world.war._advance_board(frame, frame.board_advance)

    def click(state, point):
        nonlocal reveal_at
        if state.frame is mentor:
            if point == first:
                misses.append(point)
                return False
            assert point == second
            state.frame = selected
        elif state.frame is selected:
            assert point == confirm
            if point not in misses:
                misses.append(point)
                return False
            state.frame = ready
        else:
            state.frame = routes[state.frame, point]
            if state.frame is transient:
                reveal_at = world.now[0] + 1.2

    def capture(state):
        if state.frame is transient and world.now[0] >= reveal_at:
            state.frame = mentor

    state = drive(monkeypatch, world, lobby, click, capture)
    monkeypatch.setattr(world.war, "_prepare", prepare)
    monkeypatch.setattr(world.war, "get_reward", lambda f: (
        f, (18000 if world.war.result else 15000, 18000), False))

    if entry == "daily":
        from tasks.daily import daily

        monkeypatch.setattr(daily, "CurrencyWars", lambda: world.war)
        assert daily.Daily._run_currency_wars()
    else:
        assert world.war.start(loop=entry == "loop")
    assert prepared == [before, ready]
    assert state.clicks[3:] == [(Page.BOARD, choose), (Page.HALO, effect), (Page.HALO, submit),
                                (Page.HALO_MENTOR, first), (Page.HALO_MENTOR, second),
                                (Page.HALO_MENTOR, confirm), (Page.HALO_MENTOR, confirm),
                                (Page.BOARD, fight), (Page.MATCH_RESULT, (962, 893))]
    assert state.frame is lobby and world.war.result is True
    assert world.war._loop_matches == (1 if entry == "loop" else 0)


@pytest.mark.parametrize("entry", ("single", "loop", "takeover", "daily"))
@pytest.mark.parametrize("portrait_matches", (True, False))
def test_second_halo_uses_occupied_front_slot_when_name_is_unreadable(monkeypatch, world, entry, portrait_matches):
    stage, choose = "2-5", (1816, 751)
    option, confirm, finish = (420, 436), (969, 954), (960, 899)
    holder = slot("front", 0, replace(CORE, has_halo=True))
    unnamed = slot("front", 1, occupied=True)
    team = board(holder, unnamed, stage=stage, used=2, capacity=2, gold=0)
    before = page(Page.BOARD, ("选择主角", *choose), stage=stage, capacity=(2, 2))
    ready = page(Page.BOARD, ("出战", *choose), stage=stage, capacity=(2, 2))
    for f in (before, ready):
        monkeypatch.setattr(f, "assigned_halo", lambda point: point == holder.point)
        monkeypatch.setattr(f, "slot_occupied", lambda point: point in (holder.point, unnamed.point))
    effect = (("前台专家", *option), ("获得40%伤害增幅", 420, 537), ("乱披风拳法", 1490, 436))
    empty = page(Page.HALO, *effect)
    placed = page(Page.HALO, *effect, ("确认", *confirm))
    placed.image = CANVAS.copy()
    x1, y1, x2, y2 = ui.HALO_TARGET_FACE
    ImageDraw.Draw(placed.image).rectangle((x1, y1, (x1 + x2) // 2, y2), fill=(186, 93, 124))
    assert not empty.halo_target_present() and placed.halo_target_present()
    match_halo_at(monkeypatch, (empty, placed), ui.HALO_FRONT[1] if portrait_matches else None)
    won = page(Page.MATCH_RESULT, ("对局胜利", 960, 260), ("返回货币战争", *finish))
    lobby, modes = home(), mode(("进入超频博弈", 1638, 960))
    rank_page = page(Page.RANK, ("开始对局", 1680, 965), rank_mode="overclock", enemy_rank=1)
    world.cfg.currencywars_type = "overclock"
    world.cfg.currencywars_rank_difficulty = "lowest"
    routes = {(lobby, (1600, 972)): modes, (modes, (1638, 960)): rank_page,
              (rank_page, (1680, 965)): before, (before, choose): empty, (placed, option): placed,
              (placed, confirm): ready, (ready, choose): won, (won, finish): lobby}
    state = drive(monkeypatch, world, before if entry == "takeover" else lobby,
                  lambda s, point: setattr(s, "frame", routes[s.frame, point]))

    def drag(start, end, **_):
        assert (start, end) == tuple((x / 1920, y / 1080) for x, y in (ui.HALO_FRONT[1], ui.HALO_TARGET))
        state.frame = placed
        return True

    world.auto.drag_mouse.side_effect = drag
    monkeypatch.setattr(world.war, "_settle_board", lambda f: f)
    monkeypatch.setattr(world.war, "_collect_preparation_rewards", lambda f: (f, True))
    monkeypatch.setattr(world.war, "_read_board", lambda f, **_: (f, team))
    monkeypatch.setattr(world.war, "_equip", lambda f, _: f)
    monkeypatch.setattr(world.war, "get_reward", lambda f: (
        f, (18000 if world.war.result else 15000, 18000), False))
    if entry == "daily":
        from tasks.daily import daily

        monkeypatch.setattr(daily, "CurrencyWars", lambda: world.war)
        assert daily.Daily._run_currency_wars()
    else:
        assert world.war.start(resume=entry == "takeover", loop=entry == "loop")
    assert state.frame is lobby and world.war.result is True
    assert world.war._loop_matches == (1 if entry == "loop" else 0)
    assert world.auto.drag_mouse.call_count == 1
    assert not state.keys
    assert state.clicks[-5:] == [(Page.BOARD, choose), (Page.HALO, option), (Page.HALO, confirm),
                                 (Page.BOARD, choose), (Page.MATCH_RESULT, finish)]


def test_halo_mentor_takeover_confirms_an_existing_selection(monkeypatch, world):
    frame = mentor_dialog((), selected=True, read_confirm=False)
    ready = page(Page.BOARD, ("出战", 1818, 750), stage="1-9")
    result = page(Page.MATCH_RESULT, ("对局胜利", 962, 241), ("返回货币战争", 962, 893))
    lobby = home()
    routes = {(frame, (1492, 493)): ready, (ready, (1818, 750)): result, (result, (962, 893)): lobby}
    state = drive(monkeypatch, world, frame, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    monkeypatch.setattr(world.war, "_prepare", lambda f: world.war._advance_board(f, f.board_advance))
    monkeypatch.setattr(world.war, "get_reward", lambda f: (f, (18000, 18000), False))

    assert world.war.start(resume=True)
    assert state.clicks == [(Page.HALO_MENTOR, (1492, 493)), (Page.BOARD, (1818, 750)),
                            (Page.MATCH_RESULT, (962, 893))]


def test_halo_mentor_tries_fixed_card_when_name_and_color_are_missing(monkeypatch, world):
    initial = mentor_dialog((), warning=True, confirm_y=537)
    selected = mentor_dialog((), selected=True, confirm_y=537)
    ready = page(Page.BOARD, stage="1-9")
    assert initial.page == Page.HALO_MENTOR
    card = initial.mentor_candidates[0].point
    assert card[0] == 625 and initial.mentor_confirm() is None
    routes = {(initial, card): selected, (selected, (1492, 537)): ready}
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    assert world.war._halo_mentor(initial) is ready
    assert state.clicks == [(Page.HALO_MENTOR, card), (Page.HALO_MENTOR, (1492, 537))]
    assert not state.keys


@pytest.mark.parametrize(("outcome", "error"), (("unavailable", task.CurrencyWarsUnavailable),
                                                ("budget", task.CurrencyWarsBudgetExceeded),
                                                ("stopped", RunStopRequested)))
def test_halo_mentor_preserves_terminal_states(monkeypatch, world, outcome, error):
    frame = mentor_dialog((("忘归人", 605), ("大丽花", 836), ("火花", 1065), ("罗刹", 1299)))
    world.cfg.currencywars_time_limit = 1

    def click(_, point):
        assert point[0] in (605, 836, 1065)
        if outcome == "budget":
            world.now[0] = world.war.deadline
        elif outcome == "stopped":
            task.pause_ctl.checkpoint.side_effect = RunStopRequested
        return False

    state = drive(monkeypatch, world, frame, click)
    with pytest.raises(error):
        world.war.start(resume=True)
    count = 3 if outcome == "unavailable" else 1
    assert state.clicks == [(Page.HALO_MENTOR, card.point) for card in frame.mentor_candidates[:count]]
    assert state.frame is frame
    assert task.save_error_screenshot.call_count == (outcome != "stopped")


@pytest.mark.parametrize("returned_gold", (13, 17))
def test_full_bench_sale_requires_identity_price_and_empty_slot(monkeypatch, world, returned_gold):
    spare = slot("bench", 0, FILLER)
    b = board(slot("front", 0, CORE), spare, gold=12, used=1, lineup=policy.LINEUPS[policy.HIGH_ANAXA])
    initial = page(Page.BOARD, stage=b.stage, gold=12)
    detail = page(Page.DETAIL, ("瓦尔特", 1538, 231), ("出售", 1768, 915), stage=b.stage, sell_price=1)
    after = page(Page.BOARD, stage=b.stage, gold=returned_gold)
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(
        s, "frame", detail if p == spare.point else after))
    monkeypatch.setattr(initial, "slot_occupied", lambda p: p == spare.point)
    monkeypatch.setattr(world.war, "_read_board", lambda f, **kwargs: (f, b))
    assert world.war._free_reward_slot(initial) == after
    assert state.clicks == [(Page.BOARD, spare.point), (Page.DETAIL, (1768, 915))]
    assert world.war.preparation_progress == 1


def test_full_bench_waits_for_entry_and_closes_the_automatically_opened_shop(monkeypatch, world):
    stage = "3-3"
    initial = page(Page.BENCH_FULL, ("备战阶段", 958, 504), stage=stage, gold=129, capacity=(8, 8))
    shop = page(Page.BENCH_FULL, ("收起", 1623, 982), ("免费刷新", 1617, 486), stage=stage, gold=129)
    closed = page(Page.BENCH_FULL, ("商店", 1623, 982), stage=stage, gold=129, capacity=(8, 8))
    read_board = Mock()
    monkeypatch.setattr(world.war, "_read_board", read_board)

    def observe(s):
        if s.frame is initial:
            s.frame = shop

    state = drive(monkeypatch, world, initial, lambda s, _: setattr(s, "frame", closed), after_capture=observe)
    assert world.war._free_reward_slot(initial) is closed
    assert state.clicks == [(Page.BENCH_FULL, (1623, 982))]
    read_board.assert_not_called()


def test_full_bench_replans_when_shop_interrupts_a_sale_without_a_receipt(monkeypatch, world):
    spare = slot("bench", 0, FILLER)
    b = board(slot("front", 0, CORE), spare, stage="3-3", gold=12, used=1, capacity=1)
    initial = page(Page.BENCH_FULL, stage=b.stage, gold=12)
    detail = page(Page.DETAIL, ("瓦尔特", 1538, 231), ("出售", 1768, 915), stage=b.stage)
    shop = page(Page.BENCH_FULL, ("收起", 1623, 982), ("刷新", 1617, 486), stage=b.stage, gold=12)
    closed = page(Page.BENCH_FULL, ("商店", 1623, 982), stage=b.stage, gold=12)
    for f in (initial, shop):
        monkeypatch.setattr(f, "slot_occupied", lambda p: p == spare.point)
    monkeypatch.setattr(world.war, "_read_board", lambda f, **kwargs: (f, b))
    routes = {(initial, spare.point): detail, (detail, (1768, 915)): shop, (shop, (1623, 982)): closed}
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    assert world.war._free_reward_slot(initial) is closed
    assert state.clicks == [(Page.BENCH_FULL, spare.point), (Page.DETAIL, (1768, 915)), (Page.BENCH_FULL, (1623, 982))]
    assert world.war.preparation_progress == 0


def test_overflow_sale_without_receipt_continues_using_a_different_reserve(monkeypatch, world):
    stage = "3-3"
    jiaoqiu = slot("bench", 0, policy.Unit("椒丘", False, True, 1, equipment=0))
    spare = slot("bench", 1, FILLER)
    team = board(slot("front", 0, CORE), jiaoqiu, spare, stage=stage, gold=12, used=1, capacity=1)
    initial = page(Page.BENCH_FULL, stage=stage, gold=12, capacity=(1, 1))
    uncertain = page(Page.BENCH_FULL, stage=stage, gold=None, capacity=(1, 1))
    for frame in (initial, uncertain):
        monkeypatch.setattr(frame, "slot_occupied", lambda p: p in (jiaoqiu.point, spare.point))
    first = page(Page.DETAIL, ("椒丘", 1538, 231), ("出售", 1768, 915), stage=stage)
    second = page(Page.DETAIL, ("瓦尔特", 1538, 231), ("出售", 1768, 915), stage=stage)
    prepared = page(Page.BOARD, stage=stage, gold=None)
    result = page(Page.MATCH_RESULT, ("挑战成功", 960, 233), ("返回货币战争", 960, 899))
    lobby = home()
    routes = {
        (initial, jiaoqiu.point): first,
        (first, (1768, 915)): uncertain,
        (uncertain, spare.point): second,
        (second, (1768, 915)): prepared,
        (result, (960, 899)): lobby,
    }
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    monkeypatch.setattr(world.war, "_read_board", lambda f, **kwargs: (f, replace(team, gold=f.gold)))
    monkeypatch.setattr(world.war, "_prepare", lambda _: setattr(state, "frame", result) or result)
    monkeypatch.setattr(world.war, "get_reward", lambda f: (f, (18000, 18000), False))
    assert world.war.start(resume=True)
    assert state.clicks == [
        (Page.BENCH_FULL, jiaoqiu.point), (Page.DETAIL, (1768, 915)),
        (Page.BENCH_FULL, spare.point), (Page.DETAIL, (1768, 915)),
        (Page.MATCH_RESULT, (960, 899)),
    ]
    assert state.frame is lobby


@pytest.mark.parametrize("outcome", ("balance_changed", "replay_applied", "replay_not_applied"))
def test_overflow_sale_replay_requires_a_fresh_unchanged_board(monkeypatch, world, outcome):
    stage = "3-3"
    spare = slot("bench", 0, FILLER)
    team = board(slot("front", 0, CORE), spare, stage=stage, gold=12, used=1, capacity=1)
    initial = page(Page.BENCH_FULL, stage=stage, gold=12, capacity=(1, 1))
    checked = page(Page.BENCH_FULL, stage=stage, gold=13 if outcome == "balance_changed" else 12, capacity=(1, 1))
    detail = page(Page.DETAIL, ("瓦尔特", 1538, 231), ("出售", 1768, 915), stage=stage)
    prepared = page(Page.BOARD, stage=stage)
    for frame in (initial, checked):
        monkeypatch.setattr(frame, "slot_occupied", lambda p: p == spare.point)
    reads = []
    sales = 0

    def read_board(frame, **kwargs):
        reads.append(frame)
        return frame, replace(team, gold=frame.gold)

    def click(state, point):
        nonlocal sales
        if point == spare.point:
            state.frame = detail
        else:
            sales += 1
            state.frame = prepared if sales == 2 and outcome == "replay_applied" else checked

    state = drive(monkeypatch, world, initial, click)
    monkeypatch.setattr(world.war, "_read_board", read_board)
    monkeypatch.setattr(world.war, "_read_default_board", read_board)
    assert world.war._free_reward_slot(initial) is checked
    assert sales == 1
    if outcome == "replay_applied":
        assert world.war._free_reward_slot(checked) is prepared
        assert sales == 2
    else:
        if outcome == "replay_not_applied":
            assert world.war._free_reward_slot(checked) is checked
        with pytest.raises(task.CurrencyWarsBenchBlocked):
            world.war._free_reward_slot(checked)
        assert sales == (1 if outcome == "balance_changed" else 2)
    assert reads[:2] == [initial, checked]
    assert state.clicks.count((Page.DETAIL, (1768, 915))) == sales


@pytest.mark.parametrize("transition_first", (False, True))
def test_gather_yields_to_investment_even_with_the_bench_full_toast(monkeypatch, world, transition_first):
    stage = "3-1"
    toast = ("备战席已满，需要售卖备战区角色才可开启晶矿", 966, 300)
    frame = page(Page.BOARD, stage=stage, gold=55)
    transition = page(Page.UNKNOWN, toast, stage=stage)
    investment = page(Page.CHOICE, toast, choice="请选择投资策略")
    monkeypatch.setattr(frame, "reward_orbs", lambda: ((1410, 311),))
    state = drive(monkeypatch, world, frame, after_capture=lambda s: setattr(s, "frame", investment))
    drag = Mock(return_value=transition if transition_first else investment)
    free_slot = Mock()
    monkeypatch.setattr(world.war, "_drag_to", drag)
    monkeypatch.setattr(world.war, "_free_reward_slot", free_slot)
    assert world.war._gather(frame) is investment
    assert not state.clicks
    drag.assert_called_once()
    free_slot.assert_not_called()


@pytest.mark.parametrize("is_final", (False, True))
def test_optional_ore_cannot_block_a_confirmed_final_boss_with_full_deployment(monkeypatch, world, is_final):
    stage = "3-5" if is_final else "2-5"
    frame = page(Page.BOARD, ("首领", 1355, 94), ("出战", 1817, 751), stage=stage, capacity=(10, 10))
    blocked = page(Page.BOARD, ("备战席已满，需要售卖备战区角色才可开启晶矿", 966, 300), stage=stage)
    monkeypatch.setattr(frame, "reward_orbs", lambda: ((1410, 311),))
    monkeypatch.setattr(frame, "slots", lambda: (slot("front", 0, CORE),))
    state = drive(monkeypatch, world, frame)
    monkeypatch.setattr(world.war, "_drag_to", lambda *args, **kwargs: blocked)
    monkeypatch.setattr(world.war, "_free_reward_slot", Mock(side_effect=task.CurrencyWarsBenchBlocked("备战席已满")))
    if is_final:
        assert world.war._gather(frame) is frame
    else:
        with pytest.raises(task.CurrencyWarsBenchBlocked):
            world.war._gather(frame)
    assert not state.clicks


def test_shop_also_recognizes_free_refresh_button():
    f = Frame(CANVAS, labels(("备战阶段", 285, 72), ("3-1", 287, 109), ("收起", 1621, 982),
                             ("免费刷新", 1617, 487)))
    assert f.page == Page.SHOP


def test_hidden_claim_button_requires_checkmarks_for_earned_tiers():
    image = CANVAS.copy()
    badge = Image.open("assets/images/screen/currency_wars/s2_points_claimed.png")
    xs = (158, 330, 505, 679, 853, 1028, 1202, 1376, 1550, 1725)
    tiers = tuple((str(i * 1600), x, 591) for i, x in enumerate(xs, start=1))
    for x in xs:
        image.paste(badge, (x - 24, 493))
    words = labels(("积分奖励", 133, 344), ("16000/16000", 275, 744), *tiers)
    assert Frame(image, words).claim_available() is False
    image.paste((35, 30, 74), (829, 483, 884, 545))
    assert Frame(image, words).claim_available() is None


@pytest.fixture
def high_lineup():
    return policy.LINEUPS[policy.HIGH_ANAXA]


def test_high_strategy_buys_third_auxiliary_copy_before_population(high_lineup):
    healer = replace(BAILU, equipment=0)
    main = replace(CORE, equipment=1)
    rear = slot("back", 0, healer)
    pair = slot("bench", 0, healer)
    b = board(slot("front", 0, main), rear, slot("back", 1), pair, slot("bench", 1),
              slot("bench", 2, CER), lineup=high_lineup, stage="2-3", gold=14, used=2, capacity=2, level=5,
              exp=(0, 8), final_node="3-7")
    third = policy.Offer("白露", 2, (601, 180), 0, back=True)
    unrelated = policy.Offer("花火", 2, (846, 180), 1, front=True)
    assert policy.should_buy_exp(b, 4)
    assert policy.shop_purchase(b, (unrelated, third), experience_price=4) == third
    full = replace(b, slots=tuple(s for s in b.slots if s != slot("bench", 1)))
    assert policy.has_merge_pair(full)
    assert policy.shop_purchase(full, (unrelated, third), experience_price=4) == third
    assert policy.shop_purchase(full, (replace(third, cost=5),)) is None
    merged = replace(rear, unit=replace(healer, stars=2))
    updated = replace(b, slots=(b.slots[0], merged, *b.slots[2:3], slot("bench", 0), *b.slots[4:]))
    assert policy.shop_purchase(updated, (third,)) is None
    assert not policy.has_merge_pair(updated)


@pytest.mark.parametrize("stars,gear,blocked,swap", [(2, 0, False, True), (None, 0, False, False),
                                                     (2, 0, True, False), (2, 1, False, False)])
def test_high_auxiliary_replacement_is_bounded_by_position_and_gear(world, high_lineup, stars, gear, blocked, swap):
    support = slot("back", 0, replace(BAILU, equipment=gear))
    copy = replace(slot("bench", 0, replace(BAILU, stars=stars, equipment=0)), blocked=blocked)
    scratch = slot("bench", 1)
    b = board(slot("front", 0, CORE), support, copy, scratch,
              lineup=high_lineup, stage="2-2", used=2, capacity=2, final_node="3-7")
    first = world.war._next_deployment(b)
    if not swap:
        assert first is None
        return
    assert first == (support, scratch)
    moved = apply_deployment(b, first)
    assert world.war._next_deployment(moved) == (copy, replace(support, occupied=False, unit=None))
    lost = replace(copy, occupied=False, unit=None)
    moved = replace(moved, slots=(moved.slots[0], moved.slots[1], lost, moved.slots[3]))
    assert world.war._next_deployment(moved) == (moved.slots[3], moved.slots[1])


def test_high_refresh_budgets_for_incomplete_team_after_two_star_core(high_lineup):
    b = board(slot("front", 0, CORE), slot("back", 0, CER), slot("bench", 0), slot("bench", 1),
              lineup=high_lineup, stage="2-5", used=2, capacity=2, level=10, gold=11, final_node="3-7")
    assert policy.should_refresh(b, 2, 2, experience_price=4)
    assert not policy.should_refresh(b, 2, 6, experience_price=4)
    assert policy.should_refresh(replace(b, gold=0), 0, 0)
    assert not policy.should_refresh(replace(b, gold=0), 2, 0)
    assert policy.should_refresh(replace(b, gold=4, hp=35, stage="3-7"), 2, 5)
    assert not policy.should_refresh(replace(b, gold=4, hp=90, stage="2-5"), 2, 0)


def test_critical_late_team_can_search_for_an_immediate_upgrade_before_population(high_lineup):
    core = slot("front", 0, CORE)
    reserve_core = slot("bench", 0, CORE)
    healer = slot("back", 0, BAILU)
    one_star = replace(CORE, stars=1)
    b = board(core, healer, slot("back", 1), reserve_core, slot("bench", 1, one_star),
              slot("bench", 2, one_star), slot("bench", 3, CER), slot("bench", 4), slot("bench", 5),
              lineup=high_lineup, stage="3-4", final_node="3-7", used=2, capacity=2, level=8,
              exp=(66, 72), gold=10, hp=22)
    assert policy.should_buy_exp(b, 4)
    assert policy.should_refresh(b, 2, 7, experience_price=4)
    assert not policy.should_refresh(b, 2, 8, experience_price=4)
    assert not policy.should_refresh(replace(b, stage="2-4"), 2, 0, experience_price=4)


def test_high_full_bench_makes_room_for_a_pending_support_and_future_merges(high_lineup):
    core = replace(CORE, stars=3, equipment=3)
    hanya = policy.Unit("寒鸦", False, True, 1, equipment=0)
    spare = replace(FILLER, equipment=0)
    front = slot("front", 0, core)
    healer = slot("back", 0, BAILU)
    guard = slot("back", 1, policy.Unit("符玄", False, True, 1, equipment=0))
    support = slot("bench", 0, hanya)
    disposable = slot("bench", 1, spare)
    bench = (support, disposable, slot("bench", 2, replace(spare, name="万敌")))
    b = board(front, healer, guard, *bench, lineup=high_lineup, stage="3-4", final_node="3-7",
              used=3, capacity=3, gold=18, hp=65)
    assert policy.should_make_shop_space(b)
    assert not policy.should_make_shop_space(replace(b, gold=1))
    assert not policy.should_make_shop_space(replace(b, lineup=None))
    assert not policy.should_make_shop_space(replace(b, slots=(front, healer, guard, support)))
    freed = replace(b, slots=(front, healer, guard, support, slot("bench", 1), slot("bench", 2)))
    assert not policy.should_make_shop_space(freed)
    assert policy.deployment(freed)[0] == (guard, slot("bench", 1))


def test_high_moves_other_damage_away_from_auto_support_target(high_lineup):
    other = policy.Unit("卡芙卡", True, True, 2, True)
    front = slot("front", 0, CORE), slot("front", 1, other)
    rear = slot("back", 0, CER), slot("back", 1, BAILU), slot("back", 2)
    b = board(*front, *rear, slot("bench", 0), lineup=high_lineup, stage="2-4", used=4, capacity=5,
              final_node="3-7")
    assert policy.deployment(b) == ((front[1], rear[2]),)
    # 前台空出的位置由攻略要求前期站前台的刻律德菈补上。
    assert policy.deployment(apply_deployment(b, policy.deployment(b)[0])) == (
        (rear[0], replace(front[1], occupied=False, unit=None)),)


@pytest.mark.parametrize("selected", (policy.HIGH_ANAXA,))
@pytest.mark.parametrize("rear_open", (False, True))
def test_anaxa_uses_evernight_to_fill_the_back_but_not_the_fourth_front_slot(selected, rear_open):
    # 没有花火，还没到停搜升级：要有能上场的候补才升人口，长夜月不算第四个前台候补。
    front = (slot("front", 0, CORE), slot("front", 1, policy.Unit("知更鸟", True, False)),
             slot("front", 2, policy.Unit("星期日", True, True)), slot("front", 3))
    rear = slot("back", 1, None if rear_open else BAILU)
    bench = slot("bench", 0, EVERNIGHT)
    used = 4 + int(not rear_open)
    b = board(*front, slot("back", 0, CER), rear, bench, slot("bench", 1),
              lineup=policy.LINEUPS.get(selected), used=used, capacity=used + 1, stage="1-5")
    # 前台第四格由攻略要求前期站前台的刻律德菈补上；后台有空位时先让长夜月上场。
    expected = ((bench, rear),) if rear_open else ((b.slots[4], front[3]),)
    assert policy.deployment(b) == expected
    assert policy.deployment(b, overflow=True) == (((bench, rear),) if rear_open else ())
    assert policy.should_buy_exp(replace(b, capacity=used), 4) is rear_open


@pytest.mark.parametrize("selected", (policy.HIGH_ANAXA,))
@pytest.mark.parametrize("other_output", (False, True))
def test_anaxa_moves_existing_front_evernight_back_when_another_output_is_ready(selected, other_output):
    source = slot("front", 0, EVERNIGHT)
    other = slot("front", 1, CORE if other_output else policy.Unit("花火", True, False))
    target = slot("back", 1)
    b = board(source, other, slot("back", 0, BAILU), target, slot("bench", 0),
              lineup=policy.LINEUPS.get(selected), used=3, capacity=3)
    assert policy.deployment(b) == (((source, target),) if other_output else ())


@pytest.mark.parametrize("selected", (policy.HIGH_ANAXA,))
def test_anaxa_can_still_purchase_evernight_for_backline_healing(selected):
    b = board(slot("front", 0, CORE), slot("back", 0), slot("bench", 0),
              lineup=policy.LINEUPS.get(selected), used=1, capacity=3)
    offer = policy.Offer(EVERNIGHT.name, 3, (601, 194), 0, front=True, back=True)
    assert policy.shop_purchase(b, (offer,)) == offer
    assert EVERNIGHT.name in b.healers


def test_default_can_still_deploy_dual_role_evernight_in_front():
    main, front, reserve = slot("front", 0, CORE), slot("front", 1), slot("bench", 0, EVERNIGHT)
    b = board(main, front, reserve, used=1, capacity=2)
    assert policy.default_deployment(b, {}, set()) == (reserve, front)
    assert policy.can_move(b, reserve, front)


def test_anaxa_front_fallback_prefers_another_confirmed_dual_role_character():
    front = slot("front", 0)
    support = slot("back", 1, policy.Unit("星期日", True, True))
    b = board(front, slot("back", 0, EVERNIGHT), support, used=2, capacity=2)
    assert policy.anaxa_front_fallback(b) == (support, front)


@pytest.mark.parametrize("selected", (policy.HIGH_ANAXA,))
@pytest.mark.parametrize("shop_has_core", (False, True))
def test_anaxa_checks_the_shop_before_frontline_evernight_fallback(monkeypatch, world, selected, shop_has_core):
    world.cfg.currencywars_strategy = selected
    front, rear, bench = slot("front", 0), slot("back", 0, EVERNIGHT), slot("bench", 0)
    current = board(front, rear, bench, stage="1-2", used=1, capacity=3, lineup=policy.LINEUPS.get(selected))
    fight = (1818, 751)
    frame = page(Page.BOARD, ("出战", *fight), stage=current.stage)
    won = page(Page.MATCH_RESULT, ("对局胜利", 960, 260), ("返回货币战争", 960, 899))
    lobby = home()
    routes = {(frame, fight): won, (won, (960, 899)): lobby}
    state = drive(monkeypatch, world, frame, lambda s, point: setattr(s, "frame", routes[s.frame, point]))
    operations = []

    def shop(f, team, refreshes, **_):
        nonlocal current
        operations.append("商店")
        offer = policy.Offer(CORE.name, 1, (601, 194), 0, front=True)
        if shop_has_core and team == initial:
            assert policy.shop_purchase(team, (offer,)) == offer
            current = replace(team, slots=(front, rear, slot("bench", 0, CORE)), gold=team.gold - offer.cost)
            return f, refreshes, True
        return f, refreshes, False

    def move(f, team, source, target):
        nonlocal current
        operations.append(source.unit.name)
        current = apply_deployment(team, (source, target))
        return f

    initial = current
    monkeypatch.setattr(world.war, "_settle_board", lambda f: f)
    monkeypatch.setattr(world.war, "_collect_preparation_rewards", lambda f: (f, True))
    monkeypatch.setattr(world.war, "_read_board", lambda f: (f, current))
    monkeypatch.setattr(world.war, "_shop", shop)
    monkeypatch.setattr(world.war, "_move", move)
    monkeypatch.setattr(world.war, "_equip", lambda f, _: f)
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))

    assert world.war.start(resume=True)
    assert operations == (["商店", CORE.name, "商店"] if shop_has_core else ["商店", EVERNIGHT.name])
    assert current.slots[0].unit == (CORE if shop_has_core else EVERNIGHT)
    assert current.slots[1].unit == (EVERNIGHT if shop_has_core else None)
    assert state.frame is lobby


def test_high_places_main_damage_in_first_front_slot_without_selling():
    lineup = policy.LINEUPS[policy.HIGH_FIREFLY]
    firefly = policy.Unit("流萤", True, False, 2, True)
    support = policy.Unit("星期日", True, True, 2)
    b = board(slot("front", 0, support), slot("front", 1, firefly), slot("back", 0, CER),
              slot("bench", 0), lineup=lineup, stage="2-4", used=3, capacity=3, final_node="3-7")
    plan = policy.deployment(b)
    assert [src.unit.name for src, _ in plan] == ["星期日", "流萤", "星期日"]
    for move in plan:
        assert policy.can_move(b, *move)
        b = apply_deployment(b, move)
    assert b.slots[0].unit == firefly and b.slots[1].unit == support


def test_high_equipment_compares_speed_startup_and_material_conflict(high_lineup):
    from tasks.weekly.currency_wars_equipment import Equipment, EquipmentOption, equipment_order

    core = slot("front", 0, CORE)
    support = slot("back", 0, policy.Unit("寒鸦", False, True, 2))
    healer = slot("back", 1, BAILU)
    b = board(core, support, healer, lineup=high_lineup, stage="2-5", hp=95, final_node="3-7")
    main_dps = EquipmentOption(core, Equipment("火力风暴潮", ("折叠小刀", "轮滑鞋")), ("火力风暴潮",))
    boots = EquipmentOption(support, Equipment("反重力皮靴", ("轮滑鞋", "轮滑鞋")), ())
    damage_reducing = EquipmentOption(healer, Equipment("痛觉阻断芯片", ("生命之花", "量产型装甲")), ())
    assert equipment_order(b, (main_dps, boots, damage_reducing))[0] == boots
    assert equipment_order(replace(b, hp=37), (main_dps, boots, damage_reducing))[0] == damage_reducing
    assert equipment_order(b, (main_dps, replace(boots, worn=("反重力皮靴",))))[0] == main_dps
    sail = replace(boots, action=Equipment("蓄能帆"), worn=("蓄能帆",))
    assert equipment_order(b, (main_dps, sail)) == (main_dps,)


def test_current_rank_does_not_use_enemy_difficulty_to_infer_tier():
    current = Frame(CANVAS, labels(("A6投资大师", 130, 321), ("43", 546, 965), ("3", 670, 967),
                                    ("A8财富造物主", 135, 510)))
    assert (current.rank_tier, current.enemy_rank, current.rank_affixes) == (6, 43, 3)


@pytest.mark.parametrize("mode_words,expected", (
    ((("标准博弈", 159, 892), ("晋升赛难度将大幅提升", 322, 892)), "normal"),
    ((("标准博弈晋升赛难度将大幅提升", 271, 884),), "normal"),
    ((("标准博弈晋升赛难度将大幅提升", 271, 884), ("超频博弈", 155, 866)), None),
    ((("晋升赛难度将大幅提升", 266, 884),), None),
))
def test_promotion_rank_accepts_the_joined_mode_text_without_mixing_modes(mode_words, expected):
    frame = Frame(CANVAS, labels(("入画奇航", 150, 80), ("A6投资大师", 140, 322),
                                 ("通关晋升赛后可晋升至下一职级", 924, 416),
                                 ("58", 546, 964), ("3", 674, 965), ("开始对局", 1692, 966),
                                 *mode_words))
    assert frame.rank_mode == expected
    if expected:
        assert frame.page == Page.RANK and frame.rank_promotion
        assert frame.enemy_rank == 58
    else:
        assert frame.page == Page.UNKNOWN


def test_timed_gift_overlay_is_not_a_reward_orb():
    image = CANVAS.copy()
    icon = Image.open("assets/images/screen/currency_wars/s2_timed_gift.png")
    image.paste(icon, (1350, 139))
    draw = ImageDraw.Draw(image)
    draw.ellipse((1390, 212, 1430, 252), fill=(201, 152, 90), outline="white", width=3)
    draw.ellipse((1502, 331, 1546, 375), fill=(45, 156, 235), outline="white", width=3)
    orbs = Frame(image, ()).reward_orbs()
    assert len(orbs) == 1
    assert abs(orbs[0][0] - 1524) <= 5 and abs(orbs[0][1] - 353) <= 5


def test_high_deploys_the_core_without_removing_the_only_backline_healer(high_lineup):
    pearl = policy.Unit("真珠", False, True, 1, equipment=0)
    wan = policy.Unit("瓦尔特", True, True, 1, True, 0)
    moon = policy.Unit("长夜月", True, True, 1, True, 0)
    b = board(slot("front", 0, wan), slot("front", 1, moon), slot("front", 2),
              slot("back", 0, pearl), slot("back", 1), slot("bench", 0, CORE), slot("bench", 1),
              lineup=high_lineup, stage="1-1", used=3, capacity=3, final_node="3-7")
    planned = policy.deployment(b)
    assert planned[0] == (b.slots[0], b.slots[6])
    assert planned[1] == (b.slots[5], replace(b.slots[0], occupied=False, unit=None))
    for move in planned:
        b = apply_deployment(b, move)
    assert b.slots[3].unit == pearl


def test_high_unit_can_be_both_damage_and_support():
    f = Frame(CANVAS, labels(("输出", 1775, 269), ("辅助", 1832, 269)))
    assert f.employee_output(allow_dual=True)


def test_a_confirmed_merge_wait_is_bounded_and_does_not_buy_again(monkeypatch, world, high_lineup):
    rear = slot("back", 0, BAILU)
    dupe = slot("bench", 0, BAILU)
    b = board(rear, dupe, lineup=high_lineup)
    unchanged = page(Page.BOARD, stage=b.stage)
    updated = page(Page.BOARD, stage=b.stage)
    for f in (unchanged, updated):
        monkeypatch.setattr(f, "slot_occupied", lambda p: True)
    monkeypatch.setattr(unchanged, "card_stars", lambda s: 1)
    monkeypatch.setattr(updated, "card_stars", lambda s: 2 if s == rear else 1)
    state = drive(monkeypatch, world, unchanged, after_capture=lambda s: setattr(s, "frame", updated)
                  if world.now[0] >= 0.7 else None)
    assert world.war._verify_merge(b, "白露") is updated
    assert not state.clicks and not state.keys
    state.frame = unchanged
    monkeypatch.setattr(updated, "card_stars", lambda s: 1)
    assert world.war._verify_merge(b, "白露") is updated
    assert not state.clicks and world.now[0] < 7


def test_high_investment_prefers_verified_reduction_over_restricting_the_bench(world, high_lineup):
    world.war.lineup = high_lineup
    frame = page(Page.CHOICE, ("节省工位", 465, 408), ("只有3个备战席位置，获得3件简易装备", 460, 510),
                 ("钻石商人", 962, 408), ("升到9级时，获得财富宝钻", 962, 510),
                 ("简单模式", 1458, 408), ("敌人难度降低3，最多降低至0", 1457, 515),
                 choice="请选择投资策略")
    assert world.war._choice_option(frame).text == "简单模式"


def test_high_late_investment_favors_frontline_startup_over_delayed_damage(world, high_lineup):
    world.war.lineup = high_lineup
    world.war.last_result_stage = "3-2"
    world.war.last_board = board(hp=28)
    f = page(Page.CHOICE, ("延迟收益", 459, 540),
             ("在战斗开始60行动值后，我方小队伤害增幅提高40%。", 460, 582),
             ("全队的希望", 960, 540),
             ("前台1号位的我方角色获得15%伤害增幅和15%生命增幅。", 960, 582),
             ("长期主义+", 1460, 540),
             ("进入新节点时，每次获得9金币。", 1460, 582), choice="请选择投资策略")
    assert world.war._choice_option(f).text == "全队的希望"


def test_rank_result_allows_same_next_button_on_the_promotion_page(monkeypatch, world):
    step = ("下一步", 959, 895)
    first = page(Page.MATCH_RESULT, ("对局胜利", 653, 242), step)
    promotion = page(Page.MATCH_RESULT, ("晋升成功", 959, 242), step)
    lobby = home()
    routes = {first: promotion, promotion: lobby}
    state = drive(monkeypatch, world, first, lambda s, _: setattr(s, "frame", routes[s.frame]))
    assert world.war._result_page(first) is promotion
    assert world.war._result_page(promotion) is lobby
    assert world.war.result is True and len(state.clicks) == 2


@pytest.mark.parametrize("has_next_page", (False, True))
def test_match_result_with_continue_button_returns_home_and_checks_rewards(monkeypatch, world, has_next_page):
    title = ("对局胜利", 960, 233)
    buttons = (("返回货币战争", 960, 899), ("继续挑战", 1200, 899))
    finish = Frame(CANVAS, labels(title, *buttons))
    rating = Frame(CANVAS, labels(title, *buttons, ("下一页", 840, 955)))
    lobby = home()
    points = page(Page.WEEKLY, ("18000/18000", 273, 740), claim_available=lambda: False)
    routes = {
        (rating, (840, 955)): finish,
        (finish, (960, 899)): lobby,
        (lobby, (381, 961)): points,
    }
    state = drive(monkeypatch, world, rating if has_next_page else finish,
                  lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    world.auto.press_key.side_effect = lambda key: setattr(state, "frame", lobby)

    assert world.war.start(weekly=True)
    assert world.war.result is True
    assert state.clicks == [(f.page, p) for f, p in routes if has_next_page or f is not rating]
    world.cfg.save_timestamp.assert_called_once_with("currencywars_timestamp")


@pytest.mark.parametrize("return_recovers", (False, True))
def test_match_result_ignores_continue_when_return_button_is_unreadable(monkeypatch, world, return_recovers):
    title = ("对局胜利", 960, 233)
    continue_challenge = ("继续挑战", 1200, 899)
    unreadable = Frame(CANVAS, labels(title, continue_challenge))
    readable = Frame(CANVAS, labels(title, continue_challenge, ("返回货币战争", 960, 899)))
    lobby = home()
    points = page(Page.WEEKLY, ("18000/18000", 273, 740), claim_available=lambda: False)
    routes = {(readable, (960, 899)): lobby, (lobby, (381, 961)): points}

    def capture(state):
        if return_recovers and state.frame is unreadable and world.now[0] >= 0.6:
            state.frame = readable

    state = drive(monkeypatch, world, unreadable, lambda s, p: setattr(s, "frame", routes[s.frame, p]), capture)
    world.auto.press_key.side_effect = lambda key: setattr(state, "frame", lobby)
    if return_recovers:
        assert world.war.start(weekly=True)
        assert state.clicks == [(f.page, point) for f, point in routes]
        world.cfg.save_timestamp.assert_called_once_with("currencywars_timestamp")
    else:
        with pytest.raises(task.CurrencyWarsUnavailable, match="已确认整局胜利，未识别结算操作，周奖励待核对"):
            world.war.start(weekly=True)
        assert state.frame is unreadable and not state.clicks and not state.keys
        assert world.war.weekly_reward_pending
        world.cfg.save_timestamp.assert_not_called()
    assert world.war.result is True


def test_node_result_still_uses_continue_challenge(monkeypatch, world):
    node = Frame(CANVAS, labels(("挑战结束", 960, 233), ("继续挑战", 960, 899)))
    result = Frame(CANVAS, labels(("对局胜利", 960, 233), ("返回货币战争", 960, 899)))
    lobby = home()
    points = page(Page.WEEKLY, ("18000/18000", 273, 740), claim_available=lambda: False)
    routes = {(node, (960, 899)): result, (result, (960, 899)): lobby, (lobby, (381, 961)): points}
    state = drive(monkeypatch, world, node, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    world.auto.press_key.side_effect = lambda key: setattr(state, "frame", lobby)

    assert node.page == Page.NODE_RESULT
    assert world.war.start(resume=True)
    assert world.war.result is True
    assert state.clicks == [(f.page, point) for f, point in routes]


def test_promotion_result_keeps_victory_when_rating_automatically_advances(monkeypatch, world):
    initial = Frame(CANVAS, labels(("挑战成功", 959, 234), ("小队生命值28", 961, 297),
                                   ("对局评价", 746, 376), ("B", 748, 555)))
    promoted = Frame(CANVAS, labels(("职级提升", 960, 191), ("资本帝王1", 960, 774),
                                    ("下一步", 961, 949)))
    final = Frame(CANVAS, labels(("返回货币战争", 960, 900)))
    assert initial.page == promoted.page == final.page == Page.MATCH_RESULT
    assert promoted.promoted_rank == 7
    matches = []
    monkeypatch.setattr(world.war, "_on_match_result", lambda frame: matches.append(frame))
    first = True

    def capture(state):
        nonlocal first
        if first:
            first = False
        elif state.frame is initial:
            state.frame = promoted

    state = drive(monkeypatch, world, initial, lambda s, _: setattr(s, "frame", final), capture)
    assert world.war._result_page(initial) is final
    assert state.clicks == [(Page.MATCH_RESULT, (961, 949))]
    assert world.war.result is True and matches == [initial]


def test_promotion_result_requires_a_rank_in_its_own_panel_and_standard_mode(world):
    naked = Frame(CANVAS, labels(("职级提升", 960, 191), ("下一步", 961, 949)))
    assert naked.page == Page.UNKNOWN
    promoted = Frame(CANVAS, labels(("职级提升", 960, 191), ("财富造物主1", 960, 774), ("下一步", 961, 949)))
    assert promoted.promoted_rank == 8
    world.war.mode = "overclock"
    world.war._record_match_result(promoted)
    assert world.war.result is None
    world.war.mode = "normal"
    world.war._record_match_result(promoted)
    assert world.war.result is True


def test_promotion_failure_detail_settles_the_loss_and_returns_home(monkeypatch, world):
    rating = Frame(CANVAS, labels(("挑战失败", 962, 289), ("对局评价", 960, 376),
                                  ("下一步", 962, 897)))
    loss = Frame(CANVAS, labels(("晋升失败", 547, 200), ("我的阵容", 822, 396),
                                ("标准博弈", 414, 480), ("下一页", 961, 900)))
    return_page = Frame(CANVAS, labels(("返回货币战争", 960, 900)))
    lobby = home()
    assert rating.page == loss.page == Page.MATCH_RESULT
    assert loss.result_heading == "晋升失败"
    pages = {rating: loss, loss: return_page, return_page: lobby}
    state = drive(monkeypatch, world, rating, lambda s, _: setattr(s, "frame", pages[s.frame]))
    assert world.war._play(rating) is lobby
    assert world.war.result is False
    assert [point for _, point in state.clicks] == [(962, 897), (961, 900), (960, 900)]


@pytest.mark.parametrize("won", (True, False))
def test_match_heading_without_buttons_preserves_outcome_after_battle(monkeypatch, world, won):
    fighting = battle(True)
    heading = Frame(CANVAS, labels(("对局胜利" if won else "对局失败", 960, 233)))
    final = Frame(CANVAS, labels(("返回货币战争", 960, 899)))
    lobby = home()
    assert heading.page is Page.MATCH_RESULT
    assert Frame(CANVAS, labels(("挑战成功" if won else "挑战失败", 960, 233))).page is Page.UNKNOWN
    reads = 0

    def capture(state):
        nonlocal reads
        reads += 1
        if reads == 3:
            state.frame = heading
        elif reads == 4:
            state.frame = final

    state = drive(monkeypatch, world, fighting, lambda s, point: setattr(s, "frame", lobby), capture)
    record = Mock()
    monkeypatch.setattr(world.war, "_on_match_result", record)
    monkeypatch.setattr(world.war, "get_reward", lambda f: (f, (18000, 18000), False))

    assert world.war.start(resume=True) is won
    assert world.war.result is won
    record.assert_called_once_with(heading)
    assert state.clicks == [(Page.MATCH_RESULT, (960, 899))]


def test_rank_can_use_the_formal_a7_name_when_the_badge_is_missed():
    frame = Frame(CANVAS, labels(("资本帝王1", 160, 322)))
    assert frame.rank_tier == 7


def test_standard_encounter_tries_the_left_card_and_confirm_when_ocr_misses_both(monkeypatch, world):
    initial = Frame(CANVAS, labels(("遭遇节点", 960, 154)))
    after = page(Page.BOARD, stage="1-7")
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(s, "frame", after)
                  if p == (1083, 900) else None)
    assert world.war._choose(initial) is after
    assert state.clicks == [(Page.CHOICE, (666, 390)), (Page.CHOICE, (1083, 900))]


def test_high_budget_preserves_population_for_a_ready_key_support(high_lineup):
    sunset = policy.Unit("星期日", True, True, 2)
    b = board(slot("front", 0, CORE), slot("front", 1), slot("back", 0, BAILU),
              slot("bench", 0, sunset), slot("bench", 1), slot("bench", 2),
              lineup=high_lineup, stage="1-7", gold=13, used=2, capacity=2, level=5,
              exp=(0, 8), final_node="3-7")
    assert policy.should_buy_exp(b, 4)
    assert not policy.should_refresh(b, 2, 0, experience_price=4)
    assert policy.should_refresh(b, 0, 0, experience_price=4)
    stranger = replace(b.slots[3], unit=policy.Unit("托帕&账账", True, False, 1))
    no_support = replace(b, slots=(*b.slots[:3], stranger, *b.slots[4:]))
    no_support = replace(no_support, slots=(replace(no_support.slots[0], unit=replace(CORE, stars=1)),
                                          *no_support.slots[1:]))
    assert policy.should_refresh(no_support, 2, 0, experience_price=4)


@pytest.mark.parametrize(("stage", "expected"), (("1-3", False), ("1-4", True)))
def test_anaxa_buys_no_experience_before_1_4(stage, expected):
    """攻略：1-1 至 1-3 不买经验，1-4 起再按经验条升人口。"""
    b = board(slot("front", 0, CORE), slot("back", 0), slot("bench", 0, BAILU),
              lineup=policy.LINEUPS[policy.HIGH_ANAXA], stage=stage, used=1, capacity=1, level=3, exp=(0, 4), gold=20)
    assert policy.should_buy_exp(b, 4) is expected


@pytest.mark.parametrize(("level", "hp", "bought"), ((8, 75, False), (9, 75, True), (8, 40, True)))
def test_anaxa_chases_a_three_star_core_only_from_level_9(level, hp, bought):
    """攻略：追三星排在上人口和补关键辅助之后，九级前二星那刻夏就够用；小队扛不住时照常补强。"""
    b = board(slot("front", 0, CORE), slot("bench", 0), slot("bench", 1),
              lineup=policy.LINEUPS[policy.HIGH_ANAXA], stage="2-1", used=1, capacity=1, level=level, hp=hp)
    offer = policy.Offer(CORE.name, 1, (470, 194), 0, front=True)
    skipped = {}
    assert (policy.shop_purchase(b, (offer,), skipped=skipped) == offer) is bought
    assert (skipped.get(offer) == "已达到当前阶段星级目标") is not bought


@pytest.mark.parametrize(("bench", "hp", "refresh"), (
    ((), 100, False),
    ((CORE,), 100, False),
    ((CORE, replace(CORE, stars=1)), 100, True),
    ((), 40, True),
))
def test_anaxa_refreshes_for_a_three_star_only_two_copies_short(bench, hp, refresh):
    """九级起也只在离三星差两张以内时为三星刷新：三星要九张一星卡，后期商店很少再出一费卡，同名卡见到照买。
    小队扛不住时照常追星补强。"""
    crow = policy.Unit("寒鸦", False, True, 2)
    field = (slot("front", 0, CORE), slot("front", 1, replace(SPARKLE, stars=2)), slot("back", 0, replace(CER, stars=2)),
             slot("back", 1, replace(SUNDAY, stars=2)), slot("back", 2, crow), slot("back", 3, BAILU))
    spare = tuple(slot("bench", index, unit) for index, unit in enumerate(bench))
    b = board(*field, *spare, *(slot("bench", index) for index in range(len(bench), 4)),
              lineup=policy.LINEUPS[policy.HIGH_ANAXA], stage="3-3", used=6, capacity=6, level=9, exp=(0, 72),
              gold=40, hp=hp)
    assert policy.should_refresh(b, 2, 0, experience_price=4) is refresh


SPARKLE = policy.Unit("花火", True, False, 1)
SUNDAY = policy.Unit("星期日", True, True, 1)
ROBIN = policy.Unit("知更鸟", True, False, 1)
GUIDE_FIELD = (slot("front", 0, CORE), slot("front", 1, SPARKLE), slot("front", 2, ROBIN),
               slot("back", 0, CER), slot("back", 1, SUNDAY), slot("back", 2, BAILU))


@pytest.mark.parametrize(("fifth_rear", "victim"), (
    (policy.Unit("寒鸦", False, True, 2), "白露"),
    # 没有寒鸦时白露是四连击的第四人，换下她会熄灭四连击，昔涟改换下不在连击里的缇宝。
    (policy.Unit("缇宝", False, True, 1), "缇宝"),
))
def test_key_support_takes_the_seat_of_a_spare_combo_member(fifth_rear, victim):
    """复现 2026-11-21 难度 89 的 3-5、3-6：八人口满编，3-5 买到的昔涟在备战席坐了两场。换下白露要扣连击分，
    可那刻夏、刻律德菈、星期日、寒鸦仍点亮四连击。攻略在寒鸦、风堇到场后让白露退场，九人口前台有昔涟。"""
    field = (slot("front", 0, replace(CORE, equipment=2)), slot("front", 1, replace(SPARKLE, stars=2)),
             slot("front", 2, replace(ROBIN, stars=2)), slot("front", 3),
             slot("back", 0, replace(CER, stars=2)), slot("back", 1, BAILU), slot("back", 2, replace(SUNDAY, stars=2)),
             slot("back", 3, policy.Unit("风堇", False, True, 1)), slot("back", 4, fifth_rear), slot("back", 5))
    full = board(*field, slot("bench", 0, policy.Unit("昔涟", True, False, 1)), slot("bench", 1),
                 lineup=policy.LINEUPS[policy.HIGH_ANAXA], stage="3-6", used=8, capacity=8, level=8, hp=25)

    moves = policy.deployment(full)
    assert [(source.unit.name, target.zone, target.index) for source, target in moves] == [
        (victim, "bench", 1), ("昔涟", "front", 3)]
    for move in moves:
        full = apply_deployment(full, move)
    assert policy.deployment(full) == ()


@pytest.mark.parametrize(("second", "lead", "mover"), (
    (replace(SUNDAY, stars=2), CER, "星期日"),
    # 没有星期日时，攻略要求前期站前台的刻律德菈补上：排在她前面的前台角色还坐不满前台。
    (policy.Unit("缇宝", False, True, 1), CER, "刻律德菈"),
    # 后台只剩卡面推荐后台的角色时照推荐站位，前台空着。
    (policy.Unit("缇宝", False, True, 1), policy.Unit("不死途", False, True, 1), None),
))
def test_anaxa_fills_an_empty_front_seat_from_the_back(second, lead, mover):
    """复现 2026-11-21 难度 89 第七轮 3-7：九人口满编，没有昔涟，前台只坐了那刻夏、花火、知更鸟，第四格整局空着，
    前台少一人，出战就少一人。卡面标记是游戏推荐：后台有推荐也能站前台的星期日时把她挪上去。"""
    rear = (slot("back", 0, lead), slot("back", 1, second), slot("back", 2, BAILU),
            slot("back", 3, policy.Unit("千冶·刃", False, True, 1)), slot("back", 4, policy.Unit("风堇", False, True, 1)),
            slot("back", 5, policy.Unit("寒鸦", False, True, 1)))
    field = (slot("front", 0, replace(CORE, equipment=3)), slot("front", 1, SPARKLE), slot("front", 2, ROBIN),
             slot("front", 3), *rear)
    full = board(*field, slot("bench", 0), slot("bench", 1), lineup=policy.LINEUPS[policy.HIGH_ANAXA],
                 stage="3-7", used=9, capacity=9, level=9, hp=34)
    moves = policy.deployment(full)
    assert [(source.unit.name, target) for source, target in moves] == ([(mover, field[3])] if mover else [])
    for move in moves:
        full = apply_deployment(full, move)
    assert policy.deployment(full) == ()


def settle_deployment(current):
    """按部署方案逐步执行，直到不再有移动。"""
    for _ in range(6):
        moves = policy.deployment(current)
        if not moves:
            return current
        for move in moves:
            current = apply_deployment(current, move)
    raise AssertionError("部署没有收敛")


def zone_names(current, zone):
    return [s.unit.name for s in sorted(current.slots, key=lambda s: s.index) if s.zone == zone and s.unit]


def test_anaxa_front_follows_the_guide_from_four_to_six_members():
    """复现 2026-11-21 难度 89 第七轮 1-3～1-7：二星星期日顶掉知更鸟后进了后台，1-3 前台只剩那刻夏；之后前台一直缺一两人。
    攻略让刻律德菈前期和星期日一起站前台、开局给那刻夏挂军功，白露留后台；花火到场按五人口过渡换下知更鸟；
    六人口知更鸟回来时刻律德菈让出前台，回后台一号位。"""
    lineup = policy.LINEUPS[policy.HIGH_ANAXA]
    b = board(slot("front", 0, CORE), slot("front", 1, ROBIN), slot("front", 2), slot("front", 3),
              slot("back", 0, CER), slot("back", 1, BAILU), slot("back", 2), slot("back", 3),
              slot("bench", 0, replace(SUNDAY, stars=2)), slot("bench", 1),
              lineup=lineup, stage="1-3", used=4, capacity=4, level=4)

    # 星期日直接上前台，不先进后台再挪。
    assert [(source.unit.name, target.zone) for source, target in policy.deployment(b)] == [
        ("知更鸟", "bench"), ("星期日", "front")]
    b = settle_deployment(b)
    assert zone_names(b, "front") == ["那刻夏", "刻律德菈", "星期日"] and zone_names(b, "back") == ["白露"]
    b = settle_deployment(replace(b, capacity=5, level=5))
    assert zone_names(b, "front") == ["那刻夏", "刻律德菈", "星期日", "知更鸟"] and zone_names(b, "back") == ["白露"]
    empty_bench = next(s for s in b.slots if s.zone == "bench" and not s.occupied)
    b = settle_deployment(replace(b, slots=tuple(replace(s, occupied=True, unit=SPARKLE) if s == empty_bench else s
                                                 for s in b.slots)))
    assert zone_names(b, "front") == ["那刻夏", "刻律德菈", "星期日", "花火"] and zone_names(b, "back") == ["白露"]
    b = settle_deployment(replace(b, capacity=6, level=6))
    assert zone_names(b, "front") == ["那刻夏", "知更鸟", "星期日", "花火"]
    assert zone_names(b, "back") == ["刻律德菈", "白露"]
    assert next(s for s in b.slots if s.zone == "back" and s.index == 0).unit == CER


@pytest.mark.parametrize("stage", ("2-2", "2-4"))
def test_cerydra_yields_the_front_by_guide_order_regardless_of_stars_and_gear(stage):
    """复现 2026-11-22 难度 89 的 2-2～2-6：刻律德菈二星、穿了三件装备，按星级和装备加分算，前台优先级高过一星的知更鸟、
    星期日，一直守在前台第 4 格，星期日在后台；2-4 买到的昔涟在备战席坐到 2-6。攻略前台顺序是那刻夏、花火、知更鸟、
    昔涟、星期日，最后才是刻律德菈：排在她前面的角色坐得满前台时，她回后台一号位，不看星级和装备。"""
    front = (slot("front", 0, replace(CORE, equipment=3)), slot("front", 1, replace(SPARKLE, stars=2)),
             slot("front", 2, ROBIN), slot("front", 3, replace(CER, stars=2, equipment=3)))
    rear = [slot("back", 0, BAILU), slot("back", 1, SUNDAY), *(slot("back", index) for index in range(2, 6))]
    bench = [slot("bench", index) for index in range(9)]
    used = 6
    if stage == "2-4":
        # 2-2 升到七人口后放进后台的云璃、2-4 买到的昔涟，备战席另有等合成的星期日和花火。
        rear[2] = slot("back", 2, policy.Unit("云璃", True, True, 1, output=True))
        bench[:3] = (slot("bench", 0, SUNDAY), slot("bench", 1, SPARKLE),
                     slot("bench", 2, policy.Unit("昔涟", True, False, 1)))
        used = 7
    b = board(*front, *rear, *bench, lineup=policy.LINEUPS[policy.HIGH_ANAXA], stage=stage,
              used=used, capacity=used, level=used, hp=100)

    b = settle_deployment(b)
    if stage == "2-2":
        assert zone_names(b, "front") == ["那刻夏", "花火", "知更鸟", "星期日"]
        assert zone_names(b, "back") == ["刻律德菈", "白露"]
    else:
        assert zone_names(b, "front") == ["那刻夏", "花火", "知更鸟", "昔涟"]
        assert zone_names(b, "back") == ["刻律德菈", "星期日", "白露"]
        assert "云璃" in zone_names(b, "bench")
    assert next(s for s in b.slots if s.zone == "back" and s.index == 0).unit.name == "刻律德菈"


def test_front_only_key_support_moves_a_flexible_filler_back():
    """九人口满编时补位的星期日坐着前台，买到只能站前台的昔涟：星期日退到后台，换下多出来的连击角色白露，
    昔涟补上前台，阵容与攻略九人口一致。"""
    front = (slot("front", 0, replace(CORE, equipment=3)), slot("front", 1, SPARKLE), slot("front", 2, ROBIN),
             slot("front", 3, replace(SUNDAY, stars=2)))
    rear = (slot("back", 0, CER), slot("back", 1, policy.Unit("寒鸦", False, True, 1)),
            slot("back", 2, policy.Unit("风堇", False, True, 1)), slot("back", 3, policy.Unit("千冶·刃", False, True, 1)),
            slot("back", 4, BAILU), slot("back", 5))
    bench = (slot("bench", 0, policy.Unit("昔涟", True, False, 1)), slot("bench", 1))
    full = board(*front, *rear, *bench, lineup=policy.LINEUPS[policy.HIGH_ANAXA], stage="3-5",
                 used=9, capacity=9, level=9, hp=55)
    moves = policy.deployment(full)
    assert [(source.unit.name, target.zone, target.index) for source, target in moves] == [
        ("白露", "bench", 1), ("星期日", "back", 4), ("昔涟", "front", 3)]
    for move in moves:
        full = apply_deployment(full, move)
    assert policy.deployment(full) == ()


def test_anaxa_stops_searching_once_the_core_sparkle_and_combo_are_in_place():
    """攻略：那刻夏二星、花火、四连击都到位就停搜升级。之后只在新开人口位时为还没有的关键辅助刷新，九级起再追星；
    缺花火时照常搜，小队扛不住时照常追星补强。"""
    settled = board(*GUIDE_FIELD, *(slot("bench", index) for index in range(4)),
                    lineup=policy.LINEUPS[policy.HIGH_ANAXA], stage="2-3", used=6, capacity=6, level=6,
                    exp=(0, 36), gold=30)
    assert policy.search_settled(settled)
    assert not policy.should_refresh(settled, 2, 0, experience_price=4)
    assert not policy.should_refresh(settled, 0, 0, experience_price=4)
    opened = replace(settled, capacity=7, slots=(*settled.slots, slot("back", 3)))
    assert policy.should_refresh(opened, 2, 0, experience_price=4)
    assert policy.should_refresh(replace(settled, level=9), 2, 0, experience_price=4)
    no_sparkle = replace(settled, used=5, slots=(GUIDE_FIELD[0], slot("front", 1), *settled.slots[2:]))
    assert not policy.search_settled(no_sparkle)
    assert policy.should_refresh(no_sparkle, 2, 0, experience_price=4)
    assert not policy.search_settled(replace(settled, hp=40))
    assert policy.should_refresh(replace(settled, hp=40), 2, 0, experience_price=4)


def test_anaxa_counts_a_one_star_core_as_settled_from_the_second_plane():
    """核心迟迟升不了二星时，第二位面起一星那刻夏在场也算停搜：不再为它反复刷新，见到同名卡照买。第一位面照常找二星。"""
    b = board(slot("front", 0, replace(CORE, stars=1)), *GUIDE_FIELD[1:], *(slot("bench", index) for index in range(4)),
              lineup=policy.LINEUPS[policy.HIGH_ANAXA], stage="2-3", used=6, capacity=6, level=6, exp=(0, 36), gold=30)
    assert policy.search_settled(b)
    assert not policy.should_refresh(b, 2, 0, experience_price=4)
    copy = policy.Offer(CORE.name, 1, (470, 194), 0, front=True)
    assert policy.shop_purchase(b, (copy,), experience_price=4) == copy
    early = replace(b, stage="1-5")
    assert not policy.search_settled(early)
    assert policy.should_refresh(early, 2, 0, experience_price=4)


@pytest.mark.parametrize(("core", "hp", "limit"), ((None, 75, 2), (replace(CORE, stars=1), 75, 6), (None, 40, 6)))
def test_anaxa_refreshes_at_most_twice_per_node_while_the_core_is_missing(core, hp, limit):
    """一张那刻夏都没有时搜牌命中率低，每节点最多刷两次，省下的钱先升人口；已有那刻夏或小队扛不住时照常找。"""
    b = board(slot("front", 0, FILLER), slot("back", 0, CER), slot("back", 1, SUNDAY), slot("back", 2, BAILU),
              slot("bench", 0, core), slot("bench", 1), slot("bench", 2), lineup=policy.LINEUPS[policy.HIGH_ANAXA],
              stage="1-5", used=4, capacity=4, level=4, exp=(0, 16), gold=30, hp=hp)
    assert policy.should_refresh(b, 2, limit - 1, experience_price=4)
    assert not policy.should_refresh(b, 2, limit, experience_price=4)


def test_anaxa_levels_up_once_settled_even_without_a_ready_bench_card():
    """停搜升级：到位后直接升人口，新开的位置再找关键辅助补上；没到位时仍要有能上场的候补才升。"""
    settled = board(*GUIDE_FIELD, slot("bench", 0), lineup=policy.LINEUPS[policy.HIGH_ANAXA],
                    stage="2-3", used=6, capacity=6, level=6, exp=(28, 36), gold=30)
    assert policy.should_buy_exp(settled, 4)
    unsettled = replace(settled, slots=(GUIDE_FIELD[0], slot("front", 1, FILLER), *settled.slots[2:]))
    assert not policy.should_buy_exp(unsettled, 4)


def test_anaxa_buys_a_missing_key_support_on_sight_once_settled():
    """停搜后，攻略九人口的关键辅助（如昔涟）见到就买，满编、候补多也不暂缓；其他没设星级目标的角色照旧暂缓。"""
    reserves = tuple(slot("bench", index, policy.Unit(name, False, True, 1))
                     for index, name in enumerate(("缇宝", "白露", "刻律德菈", "星期日", "寒鸦")))
    b = board(*GUIDE_FIELD, *reserves, slot("bench", 5), slot("bench", 6), lineup=policy.LINEUPS[policy.HIGH_ANAXA],
              stage="3-4", used=6, capacity=6, level=8, exp=(0, 60), gold=30)
    cyrene = policy.Offer("昔涟", 4, (1280, 194), 3, front=True)
    deathless = policy.Offer("不死途", 4, (1549, 194), 4, back=True)
    skipped = {}
    assert policy.shop_purchase(b, (deathless, cyrene), experience_price=4, skipped=skipped) == cyrene
    assert skipped[deathless] == "已满编且候补较多，暂缓未设追星目标的角色"


def test_lineup_never_buys_copies_of_off_roster_cards():
    """阵容外的卡会立即出售，场上那张也不为它买同名卡。没设星级目标的阵容角色只补能立即合成的第三张。"""
    lingsha = policy.Unit("灵砂", True, True, 1)
    b = board(slot("front", 0, CORE), slot("back", 0, lingsha), slot("bench", 0), slot("bench", 1), slot("bench", 2),
              lineup=policy.LINEUPS[policy.HIGH_ANAXA], stage="1-2", used=2, capacity=3, gold=13)
    copy = policy.Offer("灵砂", 1, (470, 194), 0, back=True)
    skipped = {}
    assert policy.shop_purchase(b, (copy,), skipped=skipped) is None
    assert skipped[copy] == "阵容外角色不买同名卡"
    tribbie = policy.Unit("缇宝", False, True, 1)
    single = replace(b, gold=20, slots=(b.slots[0], slot("back", 0, tribbie), *b.slots[2:]))
    offer = policy.Offer("缇宝", 4, (470, 194), 0, back=True)
    skipped = {}
    assert policy.shop_purchase(single, (offer,), skipped=skipped) is None
    assert skipped[offer] == "未设追星目标，只在能立即合成时补买"
    pair = replace(single, slots=(*single.slots[:2], slot("bench", 0, tribbie), *single.slots[3:]))
    assert policy.has_merge_pair(pair)
    assert policy.shop_purchase(pair, (offer,)) == offer


@pytest.mark.parametrize("core_stars", (1, 2))
def test_anaxa_fillers_skip_front_slots_the_core_guards(core_stars):
    """二星那刻夏在前台、连击辅助在场时，部署不让阵容外的输出上前台。补位只看后台空位，免得买下就卖；
    核心还没二星时前台空位照常补。"""
    field = (slot("front", 0, replace(CORE, stars=core_stars)), *GUIDE_FIELD[1:], slot("front", 3))
    b = board(*field, slot("bench", 0), slot("bench", 1), lineup=policy.LINEUPS[policy.HIGH_ANAXA],
              stage="2-1", used=6, capacity=7, level=7, gold=20, hp=100)
    herta = policy.Offer("大黑塔", 2, (742, 194), 1, front=True, back=False)
    skipped = {}
    assert (policy.shop_purchase(b, (herta,), skipped=skipped) == herta) is (core_stars == 1)
    assert (skipped.get(herta) == "过渡角色没有可部署的空位") is (core_stars == 2)
    topaz = policy.Offer("托帕&账账", 1, (473, 194), 0, back=True)
    skipped = {}
    assert policy.shop_purchase(replace(b, slots=(*b.slots, slot("back", 3))), (herta, topaz), skipped=skipped) == topaz
    assert (skipped[herta] == "过渡角色没有可部署的空位") is (core_stars == 2)


def test_off_roster_bench_keeps_one_filler_only_in_the_first_plane():
    """阵容外的卡立即出售。第一位面留一张最能补位的过渡卡；特殊对象、带装备或星级未读清的卡不在此出售。"""
    filler = slot("bench", 0, policy.Unit("瓦尔特", True, True, 1, equipment=0))
    stronger = slot("bench", 1, policy.Unit("海瑟音", True, True, 2, equipment=0))
    kept = (slot("bench", 2, replace(BAILU, equipment=0)),
            slot("bench", 3, policy.Unit("星神★阿哈", True, True, 1, equipment=0)),
            slot("bench", 4, policy.Unit("托帕&账账", True, False, 1, equipment=1)),
            slot("bench", 5, policy.Unit("灵砂", True, True, None, equipment=0)))
    team = board(slot("front", 0, CORE), filler, stronger, *kept, lineup=policy.LINEUPS[policy.HIGH_ANAXA],
                 stage="1-4", used=1, capacity=1)
    assert policy.off_roster_bench(team) == (filler,)
    assert policy.off_roster_bench(replace(team, stage="2-1")) == (filler, stronger)
    assert policy.off_roster_bench(replace(team, lineup=None)) == ()


def test_shop_no_longer_buys_off_roster_healers_just_for_healing():
    """复现 2026-11-21 难度 89 第 10 局 1-7：5/5 满编、生命值不到 55 时，商店按「补一名生存角色」买下阵容外的治疗，
    部署不让它上场，随即卖掉，卖了再买（这个节点 7 次）。小队掉血来自限定行动内没打完怪物，治疗多一个影响不大：
    商店不再为凑治疗或生存位买阵容外角色，场上没有治疗时也不买；有空位时只当普通过渡卡补人数。"""
    healers = (policy.Offer("灵砂", 1, (473, 194), 0, front=True, back=True),
               policy.Offer("娜塔莎", 2, (742, 194), 1, back=True),
               policy.Offer("罗刹", 3, (1011, 194), 2, back=True))
    bench = tuple(slot("bench", index) for index in range(3))
    five = (slot("front", 0, CORE), slot("front", 1, SPARKLE), slot("back", 0, CER), slot("back", 1, SUNDAY),
            slot("back", 2, BAILU))
    full = board(*five, *bench, lineup=policy.LINEUPS[policy.HIGH_ANAXA], stage="2-4",
                 used=5, capacity=5, level=5, exp=(0, 20), gold=17, hp=48)
    skipped = {}
    assert policy.shop_purchase(full, healers, experience_price=4, skipped=skipped) is None
    assert skipped == dict.fromkeys(healers, "本轮无需该角色补阵")
    no_healer = replace(full, slots=(*five[:4], slot("back", 2, FILLER), *bench))
    assert policy.shop_purchase(no_healer, healers, experience_price=4) is None

    open_rear = replace(full, used=4, slots=(*five[:4], slot("back", 2), *bench))
    assert policy.shop_purchase(open_rear, healers, experience_price=4) == healers[0]


def test_two_sustain_cards_do_not_keep_swapping_places():
    """复现 2026-11-21 难度 89 第 3 局 1-9：满编、生命值 48 时部署为凑两名生存角色，把场上的长夜月换成备战席的
    灵砂，下一轮又换回来，两次拖动都等到时限才暂缓部署。部署不再为凑生存角色换人，两张卡都留在原位。"""
    evernight = policy.Unit("长夜月", True, True, 1, equipment=0)
    lingsha = policy.Unit("灵砂", True, True, 1, equipment=0)
    hanya = policy.Unit("寒鸦", False, True, 1)
    field = (slot("front", 0, CORE), slot("front", 1, SPARKLE), slot("back", 0, CER), slot("back", 1, SUNDAY),
             slot("back", 2, hanya))
    team = board(*field, slot("back", 3, evernight), slot("bench", 0, lingsha), slot("bench", 1),
                 lineup=policy.LINEUPS[policy.HIGH_ANAXA], stage="1-9", used=6, capacity=6, level=6, gold=5, hp=48)
    assert policy.deployment(team) == ()
    swapped = replace(team, slots=(*field, slot("back", 3, lingsha), slot("bench", 0, evernight), slot("bench", 1)))
    assert policy.deployment(swapped) == ()


def test_preparation_sells_an_off_roster_bench_card_right_away(monkeypatch, world):
    """阵容外的卡不占备战席：部署之后、商店之前，已读出姓名的阵容外角色直接出售。"""
    stage = "2-1"
    stranger = slot("bench", 0, policy.Unit("海瑟音", True, True, 1, equipment=0))
    team = board(slot("front", 0, CORE), slot("back", 0, CER), stranger, slot("bench", 1),
                 lineup=policy.LINEUPS[policy.HIGH_ANAXA], stage=stage, used=2, capacity=2, gold=0)
    cleared = replace(team, slots=(*team.slots[:2], slot("bench", 0), slot("bench", 1)))
    frame = page(Page.BOARD, ("出战", 1818, 750), stage=stage, gold=0, capacity=(2, 2))
    current, sold = [team], []

    def sell(f, target, *, identified=False):
        sold.append((target.unit.name, identified))
        current[0] = cleared
        return f

    world.war.lineup = team.lineup
    monkeypatch.setattr(world.war, "_settle_board", lambda f: f)
    monkeypatch.setattr(world.war, "_collect_preparation_rewards", lambda f: (f, True))
    monkeypatch.setattr(world.war, "_read_board", lambda f, **_: (f, current[0]))
    monkeypatch.setattr(world.war, "_sell_for_space", sell)
    monkeypatch.setattr(world.war, "_shop_needs_visit", lambda *_: False)
    monkeypatch.setattr(world.war, "_finish_preparation", lambda f, b: f)
    drive(monkeypatch, world, frame)

    assert world.war._prepare(frame) is frame
    assert sold == [("海瑟音", True)]



def test_halo_reselection_tutorial_is_recognized_by_text_and_highlight(monkeypatch, world):
    markup = (("备战阶段", 469, 46), ("2-1", 471, 78), ("提示：现在你可以重选主角光", 460, 240),
              ("环。", 315, 277), ("5/6", 960, 262), ("出战", 1818, 750))
    image = CANVAS.copy()
    ImageDraw.Draw(image).line((19, 120, 231, 120), fill=(62, 248, 245), width=3)
    initial = Frame(image, labels(*markup))
    assert initial.page == Page.HALO_TIP
    assert Frame(CANVAS, labels(*markup)).page != Page.HALO_TIP
    tutorial = Frame(CANVAS, labels(("2-1主角光环与奇遇详情", 632, 64),
                                    ("前往重选会同时重选主角角色和光环。", 992, 213),
                                    ("重选主角", 836, 711)))
    detail = Frame(CANVAS, labels(("2-1", 509, 63), ("主角光环与奇遇详情", 650, 64), ("重选主角", 836, 711)))
    after = page(Page.BOARD, stage="2-1")
    routes = {(initial, (125, 170)): tutorial, (tutorial, (992, 213)): detail, (detail, (1862, 65)): after}
    state = drive(monkeypatch, world, initial, lambda s, point: setattr(s, "frame", routes[s.frame, point]))
    assert world.war._play_step(initial) is tutorial
    assert world.war._play_step(tutorial) is detail
    assert world.war._play_step(detail) is after
    assert [point for _, point in state.clicks] == [(125, 170), (992, 213), (1862, 65)]


def test_core_pair_can_use_the_last_bench_slot_when_an_ungeared_filler_can_make_space(high_lineup):
    low = replace(CORE, stars=1, equipment=2)
    filler = replace(FILLER, equipment=0)
    b = board(slot("front", 0, low), slot("back", 0, BAILU),
              slot("bench", 0, filler), slot("bench", 1),
              lineup=high_lineup, stage="1-5", gold=9, used=2, capacity=2)
    copy = policy.Offer(CORE.name, 1, (500, 194), 0, True)
    assert policy.shop_purchase(b, (copy,)) == copy
    geared = replace(b, slots=(*b.slots[:2], replace(b.slots[2], unit=replace(filler, equipment=1)), b.slots[3]))
    assert policy.shop_purchase(geared, (copy,)) is None


@pytest.mark.parametrize("debug_enabled", (False, True))
def test_high_preparation_diagnoses_skipped_purchase_and_retained_bench(
    monkeypatch, world, high_lineup, debug_enabled,
):
    stage, shop_button, fight_button = "2-4", (1624, 983), (1818, 751)
    team = board(slot("front", 0, CORE), slot("back", 0, BAILU),
                 slot("bench", 0, replace(CORE, stars=1)),
                 slot("bench", 1, policy.Unit("知更鸟", True, False, 2, equipment=0)),
                 slot("bench", 2), replace(slot("bench", 3, occupied=True), blocked=True),
                 slot("bench", 4, occupied=True),
                 lineup=high_lineup, stage=stage, gold=2, used=2, capacity=2, level=9)
    initial = page(Page.BOARD, ("商店", *shop_button), ("出战", *fight_button), stage=stage, gold=2)
    shop = page(Page.SHOP, ("收起", *shop_button), ("那刻夏1", 470, 310), ("花火4", 730, 310),
                ("真珠3", 990, 310), stage=stage, gold=2, shop_refresh_price=None)
    fighting = battle(True)
    routes = {(initial, shop_button): shop, (shop, shop_button): initial, (initial, fight_button): fighting}
    world.war.lineup = high_lineup
    monkeypatch.setattr(world.war, "_read_board", lambda f: (f, team))
    monkeypatch.setattr(world.war, "_next_deployment", lambda _: None)
    monkeypatch.setattr(task.log.logger, "isEnabledFor", lambda _: debug_enabled)
    debug = Mock()
    monkeypatch.setattr(task.log, "debug", debug)

    def click(state, point):
        state.frame = routes[state.frame, point]

    state = drive(monkeypatch, world, initial, click)
    assert world.war._prepare(initial) is fighting
    assert state.clicks == [(Page.BOARD, shop_button), (Page.SHOP, shop_button), (Page.BOARD, fight_button)]
    messages = [call.args[0] for call in debug.call_args_list]
    shop_logs = [msg for msg in messages if "商店，本轮" in msg]
    bench_logs = [msg for msg in messages if "备战席商店腾位筛选" in msg]
    if debug_enabled:
        assert len(shop_logs) == 1
        assert "那刻夏（1 星，1 金）保留最后一格" in shop_logs[0]
        assert "花火（1 星，4 金）报价不符合购买规则" in shop_logs[0]
        assert "真珠（1 星，3 金）金币不足" in shop_logs[0]
        assert bench_logs and "知更鸟（常规清理仅考虑一星卡）" in bench_logs[0]
        assert "第 4 格（卡位不可用）" in bench_logs[0]
        assert "第 5 格（占用对象未确认）" in bench_logs[0]
    else:
        assert not shop_logs and not bench_logs


def test_high_star_count_ignores_the_glow_joining_two_stars():
    image = CANVAS.copy()
    draw = ImageDraw.Draw(image)
    x, y = 888, 405
    draw.rectangle((x - 16, y + 36, x + 16, y + 40), fill=(226, 177, 100))
    for dx in (-9, 9):
        draw.polygon([(x + dx, y + 31), (x + dx + 7, y + 38),
                      (x + dx, y + 45), (x + dx - 7, y + 38)], fill=(252, 212, 122))
    candidate = policy.Slot("front", 1, (x, y), True)
    frame = Frame(image, ())
    assert frame.card_stars(candidate, separate_glow=True) == 2



def test_high_star_count_does_not_add_another_color_to_the_same_star_row():
    image = CANVAS.copy()
    draw = ImageDraw.Draw(image)
    x, y = 745, 405
    for dx, color in ((-11, (150, 223, 255)), (7, (150, 223, 255)), (24, (250, 211, 120))):
        draw.polygon([(x + dx, y + 32), (x + dx + 6, y + 38),
                      (x + dx, y + 44), (x + dx - 6, y + 38)], fill=color)
    frame = Frame(image, ())
    assert frame.card_stars(policy.Slot("front", 0, (x, y), True), separate_glow=True) == 2


@pytest.mark.parametrize("identifier,core,cost", [
    (policy.HIGH_FIREFLY, "流萤", 2),
    (policy.HIGH_SERVAL, "希露瓦", 4),
])
def test_high_candidates_use_their_own_core_and_live_catalog_cost(identifier, core, cost):
    lineup = policy.LINEUPS[identifier]
    b = board(slot("front", 0, CORE), slot("front", 1), slot("bench", 0), slot("bench", 1),
              lineup=lineup, stage="2-2", used=1, capacity=2, gold=16)
    assert not b.core_ready
    candidate = policy.Offer(core, cost, (500, 194), 0, True)
    assert policy.shop_purchase(b, (candidate,)) == candidate
    assert policy.shop_purchase(b, (replace(candidate, cost=1),)) is None
    actual = replace(b, slots=(replace(b.slots[0], unit=policy.Unit(core, True, False, 2, True)), *b.slots[1:]))
    assert actual.core_ready


@pytest.mark.parametrize("caption,expected", [
    ("1刷新还剩8次", (1, 8)),
    ("免费刷新还剩10次", (0, 10)),
    ("1刷新还剩100次", None),
])
def test_halo_reads_high_rank_refresh_quota(caption, expected):
    frame = Frame(CANVAS, labels((caption, 960, 135)))
    assert frame.halo_refresh_status() == expected


def test_high_reward_space_treats_off_roster_healers_as_ordinary_reserves(high_lineup):
    b = board(slot("front", 0, CORE), slot("back", 0, BAILU),
              slot("back", 1, policy.Unit("真珠", False, True, 1, equipment=1)),
              slot("bench", 0, policy.Unit("娜塔莎", False, True, 1, equipment=0)),
              slot("bench", 1, policy.Unit("风堇", False, True, 1, equipment=1)),
              slot("bench", 2, policy.Unit("藿藿", False, True, 1, equipment=0)),
              lineup=high_lineup, stage="3-1", used=3, capacity=3)
    # 治疗多一个影响不大：阵容外的娜塔莎、藿藿不再留作生存候补，场上有几名治疗都可以腾位；风堇是阵容角色。
    assert policy.disposable_bench(b) == (b.slots[3], b.slots[5])
    without_pearl = replace(b, slots=(*b.slots[:2], *b.slots[3:]), used=2)
    assert policy.disposable_bench(without_pearl) == (without_pearl.slots[2], without_pearl.slots[4])


def test_two_star_shop_offer_uses_displayed_quote_and_considers_existing_core(monkeypatch, high_lineup):
    image = CANVAS.copy()
    marker = Image.open("assets/images/screen/currency_wars/s2_shop_two_star.png")
    image.paste(marker, (1262, 69))
    f = Frame(image, labels(("那刻夏", 1244, 310)))
    monkeypatch.setattr(f, "read_local", lambda *_args, **_kwargs: "3")
    assert len(f.offers) == 1
    offer = f.offers[0]
    assert offer.cost == 3 and offer.stars == 2 and offer.column == 3
    b = board(slot("front", 0, replace(CORE, stars=1, equipment=0)), slot("back", 0, BAILU),
              slot("bench", 0), slot("bench", 1), stage="3-2", used=2, capacity=2,
              gold=7, lineup=high_lineup, final_node="3-7")
    assert policy.shop_purchase(b, (offer,)) == offer
    assert policy.shop_purchase(b, (replace(offer, cost=1),)) is None
    assert policy.shop_purchase(replace(b, gold=2), (offer,)) is None
    assert not policy.merge_purchase(b, offer)
    no_price = Frame(image, labels(("那刻夏", 1244, 310)))
    monkeypatch.setattr(no_price, "read_local", lambda *_args, **_kwargs: None)
    assert not no_price.offers


@pytest.mark.parametrize("names,expected", [
    (("遭遇其二", "遭遇其三"), "遭遇其二"),
    (("遭遇其4", "遭遇其3"), "遭遇其3"),
    (("随机事件", "未知遭遇"), None),
])
def test_encounter_picks_the_lowest_visible_difficulty(world, names, expected):
    frame = page(Page.CHOICE, (names[0], 666, 390), (names[1], 1252, 390), choice="遭遇节点")
    assert (world.war._choice_option(frame) or Label("", (0, 0))).text == (expected or "")


def test_wide_population_crop_only_overrides_when_board_matches(monkeypatch):
    markup = labels(("备战阶段", 465, 45), ("3-7", 465, 79), ("111/11", 938, 261))
    f = Frame(CANVAS, markup)
    monkeypatch.setattr(f, "read_local", lambda area, **_: "11/11" if area[0] == 860 else "1/11")
    monkeypatch.setattr(f, "field_slots", lambda: tuple(slot("back", i, occupied=True) for i in range(11)))
    assert f.capacity == (11, 11)
    bad = Frame(CANVAS, markup)
    monkeypatch.setattr(bad, "read_local", f.read_local)
    monkeypatch.setattr(bad, "field_slots", lambda: tuple(slot("back", i, occupied=True) for i in range(10)))
    assert bad.capacity != (11, 11)


def test_high_halo_can_spend_a_verified_paid_reroll_below_low_rank_reserve(monkeypatch, world, high_lineup):
    world.war.lineup = high_lineup
    core = slot("front", 0, CORE)
    world.war.halo_candidate = halo_selection(core)
    price = ("1刷新还剩8次", 960, 135)
    refresh = ("刷新", 471, 772)
    left = ("苦战寻宝", 420, 435)
    right = ("风眼骑士", 1501, 436)
    fixed = (right, ("自伤", 1501, 478), ("敌人难度+5", 1515, 626))
    before = page(Page.HALO, price, refresh, left, *fixed, ("获得20%治疗强度", 419, 506),
                  ("敌人难度+5", 438, 626), halo_gold=4)
    new = ("前台专家", 420, 435)
    rolled = page(Page.HALO, ("1刷新还剩7次", 960, 135), refresh, new, *fixed,
                  ("前台强度提高", 419, 506), halo_gold=3)
    confirm = ("确认", 970, 954)
    selected = page(Page.HALO, new, *fixed, confirm, halo_gold=3)
    after = page(Page.BOARD, stage="1-9")
    match_halo_at(monkeypatch, (before, rolled, selected), ui.HALO_TARGET)
    monkeypatch.setattr(selected, "halo_effect_selected", lambda i: i == 0)
    monkeypatch.setattr(selected, "enabled_button", lambda label: label)
    routes = {(before, refresh[1:]): rolled, (rolled, new[1:]): selected, (selected, confirm[1:]): after}
    state = drive(monkeypatch, world, before, lambda st, point: setattr(st, "frame", routes[st.frame, point]))
    assert world.war._halo(before) is after
    assert [point for _, point in state.clicks] == [refresh[1:], new[1:], confirm[1:]]


@pytest.mark.parametrize("lift", (0, 12))
def test_front_card_star_recognizes_the_raised_position(lift):
    image = CANVAS.copy()
    card = slot("front", 0, CORE)
    x, y = card.point
    draw = ImageDraw.Draw(image)
    for dx in (-8, 8):
        center = x + dx, y + 39 - lift
        draw.polygon([(center[0], center[1] - 6), (center[0] + 6, center[1]),
                      (center[0], center[1] + 6), (center[0] - 6, center[1])], fill=(65, 224, 246))
    frame = Frame(image, ())
    assert frame.card_stars(card) == 2
    assert frame.card_stars(card, separate_glow=True) == 2


@pytest.mark.parametrize("icon", ("s2_wrench.png", "s2_precision_wrench.png"))
def test_both_disassembly_wrenches_are_recognized(icon):
    image = CANVAS.copy()
    image.paste(Image.open(f"assets/images/screen/currency_wars/{icon}"), (1818, 138))
    point = Frame(image, ()).disassembly_tool()
    assert point and 1818 < point[0] < 1880 and 138 < point[1] < 190
    assert Frame(CANVAS, ()).disassembly_tool() is None


@pytest.mark.parametrize("high", [False, True])
def test_same_name_replacement_can_recover_gear_even_with_a_halo(monkeypatch, world, high_lineup, high):
    lineup = high_lineup if high else None
    world.war.lineup = lineup
    unit = BAILU if high else replace(CORE, stars=1)
    source = slot("back" if high else "front", 0, replace(unit, equipment=1, has_halo=not high))
    target = slot("bench", 0, replace(unit, stars=2, equipment=0))
    other = slot("front", 0, CORE) if high else slot("back", 0, CER)
    b = board(other, source, target, slot("bench", 1), lineup=lineup, used=2, capacity=2)
    old = page(Page.BOARD, stage=b.stage, capacity=(2, 2))
    new = page(Page.BOARD, stage=b.stage, capacity=(2, 2))
    for frame in (old, new):
        monkeypatch.setattr(frame, "disassembly_tool", lambda: (1844, 163))
        monkeypatch.setattr(frame, "slot_occupied", lambda _: True)
        monkeypatch.setattr(frame, "assigned_halo", lambda _: not high)
        monkeypatch.setattr(frame, "slot_portrait_matches", lambda *_: True)
        monkeypatch.setattr(frame, "card_stars", lambda s, **_: s.unit.stars)
    monkeypatch.setattr(old, "inventory_items", lambda: ())
    monkeypatch.setattr(new, "inventory_items", lambda: ((1844, 248),))
    monkeypatch.setattr(old, "card_equipment", lambda s: s.unit.equipment)
    monkeypatch.setattr(new, "card_equipment", lambda _: 0)
    state = drive(monkeypatch, world, old)
    world.auto.drag_mouse.side_effect = lambda *_args, **_kwargs: setattr(state, "frame", new)
    assert world.war._disassemble_for_upgrade(old, b) is new
    world.auto.drag_mouse.assert_called_once()
    assert world.war._disassemble_for_upgrade(new, b) is None
    world.war.disassembly_attempted.clear()
    without_copy = replace(b, slots=tuple(slot for slot in b.slots if slot != target))
    assert world.war._disassemble_for_upgrade(old, without_copy) is None
    world.auto.drag_mouse.assert_called_once()


@pytest.mark.parametrize("outcome", ("retry", "delayed", "changed_tool", "partial_transfer", "locked_target"))
def test_start_recovers_disassembly_only_on_an_unchanged_board(monkeypatch, world, high_lineup, outcome):
    stage = "2-5"
    wrench = (1844, 163)
    flower = policy.Unit("花火", True, True, 1, equipment=2)
    source = slot("front", 1, flower)
    target = slot("bench", 0, replace(flower, stars=2, equipment=0))
    team = board(slot("front", 0, CORE), source, target, slot("bench", 1),
                 stage=stage, gold=0, used=2, capacity=2, lineup=high_lineup)
    before = page(Page.BOARD, stage=stage, capacity=(2, 2))
    received = page(Page.BOARD, stage=stage, capacity=(2, 2))
    changed = page(Page.BOARD, stage=stage, capacity=(2, 2))
    won = page(Page.MATCH_RESULT, ("对局胜利", 960, 260), ("返回货币战争", 960, 899))
    lobby = home()
    if outcome == "changed_tool":
        changed.image = CANVAS.copy()
        ImageDraw.Draw(changed.image).rectangle((1862, 187, 1868, 194), fill="white")
    if outcome == "locked_target":
        changed.__dict__["locked_bench_slots"] = frozenset((target.point,))
    for current, gear, inventory in (
        (before, 2, ()), (received, 0, ((1844, 248), (1844, 325))),
        (changed, 1 if outcome == "partial_transfer" else 2,
         ((1844, 248),) if outcome == "partial_transfer" else ()),
    ):
        monkeypatch.setattr(current, "disassembly_tool", lambda: wrench)
        monkeypatch.setattr(current, "slot_occupied", lambda _: True)
        monkeypatch.setattr(current, "slot_portrait_matches", lambda *_: True)
        monkeypatch.setattr(current, "card_stars", lambda s, **_: s.unit.stars)
        monkeypatch.setattr(current, "card_equipment", lambda s, amount=gear: amount if s == source else 0)
        monkeypatch.setattr(current, "inventory_items", lambda items=inventory: items)
        # 卡面中心在动画中变化，肖像模板和格位仍然可辨认。
        monkeypatch.setattr(current, "same_control", lambda *_: False)
    world.cfg.currencywars_strategy = policy.HIGH_ANAXA
    monkeypatch.setattr(task, "TASK_SECONDS", 30)
    monkeypatch.setattr(world.war, "_settle_board", lambda f: f)
    monkeypatch.setattr(world.war, "_collect_preparation_rewards", lambda f: (f, True))
    monkeypatch.setattr(world.war, "_read_board", lambda f: (f, team))
    monkeypatch.setattr(world.war, "_next_deployment", lambda b: None)
    monkeypatch.setattr(world.war, "_shop", lambda f, *_a, **_kw: (f, 0, False))
    monkeypatch.setattr(world.war, "_stable_preparation", lambda *_: world.war.frame)
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))
    finished = []
    delayed_at = None

    def capture(state):
        if delayed_at is not None and world.now[0] >= delayed_at and state.frame is before:
            state.frame = received

    def click(state, point):
        assert state.frame is won and point == (960, 899)
        state.frame = lobby

    state = drive(monkeypatch, world, before, click, capture)

    def finish(f, _):
        finished.append(f)
        state.frame = won
        return won

    def drag(start, end, **_):
        nonlocal delayed_at
        assert start == (wrench[0] / 1920, wrench[1] / 1080)
        assert end == (source.point[0] / 1920, source.point[1] / 1080)
        if outcome == "retry" and world.auto.drag_mouse.call_count == 2:
            state.frame = received
        elif outcome == "delayed":
            delayed_at = world.now[0] + 1
        elif outcome in ("changed_tool", "partial_transfer", "locked_target"):
            state.frame = changed
        return True

    world.auto.drag_mouse.side_effect = drag
    monkeypatch.setattr(world.war, "_finish_preparation", finish)
    assert world.war.start(resume=True)
    assert world.auto.drag_mouse.call_count == (2 if outcome == "retry" else 1)
    assert finished == [received if outcome in ("retry", "delayed") else changed]


@pytest.mark.parametrize(("title", "fallback"), (
    ("投资环境", (960, 393)),
    ("请选择投资策略", (960, 490)),
))
@pytest.mark.parametrize("enabled_column", (2, None))
def test_investment_uses_layout_when_ocr_misses_cards_and_bounds_retries(
        monkeypatch, world, title, fallback, enabled_column):
    frame = page(Page.CHOICE, ("确认", 960, 984), choice=title)
    selected = enable_investment_confirm(page(Page.CHOICE, choice=title))
    after = page(Page.BOARD)

    def click(state, point):
        if state.frame is selected and point == (960, 984):
            state.frame = after
        elif enabled_column is not None and point == (ui.INVESTMENT_CENTERS[enabled_column], fallback[1]):
            state.frame = selected

    state = drive(monkeypatch, world, frame, click)
    expected = [(Page.CHOICE, fallback)] * 3 + [
        (Page.CHOICE, (x, fallback[1])) for x in ui.INVESTMENT_CENTERS
    ]
    if enabled_column is not None:
        assert world.war._choose(frame) is after
        expected.append((Page.CHOICE, (960, 984)))
    else:
        with pytest.raises(task.CurrencyWarsUnavailable, match="多次尝试后仍无法提交"):
            world.war._choose(frame)
    assert state.clicks == expected


@pytest.mark.parametrize("entry", ("single", "loop", "takeover", "daily"))
def test_investment_fixed_card_recovers_in_the_same_run_after_delayed_enable(monkeypatch, world, entry):
    texts = labels(("请选择投资策略", 960, 100), ("选择一个", 515, 248),
                   ("黄金大饭店星徽套组", 515, 570), ("获得1个星徽。", 500, 614))
    frame = Frame(CANVAS, texts)
    bright = CANVAS.copy()
    ImageDraw.Draw(bright).rectangle((904, 973, 1016, 995), fill=(235, 235, 235))
    selected = Frame(bright, texts)
    result = page(Page.MATCH_RESULT, ("对局胜利", 962, 241), ("返回货币战争", 962, 893))
    lobby = home()
    modes = mode(("进入标准博弈", 1638, 960))
    ready = rank()
    routes = {(lobby, (1600, 972)): modes, (modes, (1638, 960)): ready,
              (ready, (1680, 965)): frame, (selected, (960, 984)): result, (result, (962, 893)): lobby}
    enabled_at = None

    def click(state, point):
        nonlocal enabled_at
        if state.frame is frame:
            if point == (1409, 420):
                enabled_at = world.now[0] + 0.5
        else:
            state.frame = routes[state.frame, point]

    def capture(state):
        if enabled_at is not None and state.frame is frame and world.now[0] >= enabled_at:
            state.frame = selected

    state = drive(monkeypatch, world, frame if entry == "takeover" else lobby, click, capture)
    monkeypatch.setattr(world.war, "get_reward", lambda f: (
        f, (18000 if world.war.result else 15000, 18000), False))

    if entry == "daily":
        from tasks.daily import daily

        monkeypatch.setattr(daily, "CurrencyWars", lambda: world.war)
        assert daily.Daily._run_currency_wars()
    else:
        assert world.war.start(resume=entry == "takeover", loop=entry == "loop")
    expected = [(515, 570)] * 3 + [(514, 420), (1005, 420), (1409, 420), (960, 984)]
    assert [point for page_, point in state.clicks if page_ == Page.CHOICE] == expected
    assert world.war.result is True and state.frame is lobby
    assert world.war._loop_matches == (1 if entry == "loop" else 0)
    task.save_error_screenshot.assert_not_called()


@pytest.mark.parametrize("outcome, exception", (
    ("unavailable", task.CurrencyWarsUnavailable), ("budget", task.CurrencyWarsBudgetExceeded),
    ("stop", RunStopRequested),
))
def test_investment_fixed_card_recovery_preserves_terminal_states(monkeypatch, world, outcome, exception):
    frame = Frame(CANVAS, labels(("请选择投资策略", 960, 100), ("选择一个", 515, 248)))
    world.cfg.currencywars_time_limit = 1

    def click(state, point):
        if point != (514, 420):
            return
        if outcome == "budget":
            world.now[0] = world.war.deadline
        elif outcome == "stop":
            task.pause_ctl.checkpoint.side_effect = RunStopRequested

    state = drive(monkeypatch, world, frame, click)
    with pytest.raises(exception):
        world.war.start(resume=True)
    expected = [(1005, 420)] * 3 + [(514, 420)]
    if outcome == "unavailable":
        expected.extend(((1005, 420), (1409, 420)))
    assert state.clicks == [(Page.CHOICE, point) for point in expected]
    assert state.frame is frame
    assert task.save_error_screenshot.call_count == (0 if outcome == "stop" else 1)


@pytest.mark.parametrize("late_receipt", (False, True))
def test_buy_timeout_reconciles_actual_shop_and_finishes_without_a_second_purchase(monkeypatch, world, late_receipt):
    stage = "1-2"
    offer = policy.Offer("那刻夏", 1, (470, 192), 0)
    units = (slot("front", 0, FILLER), slot("bench", 0))
    initial = page(Page.BOARD, ("商店", 1624, 983), ("出战", 1818, 751), stage=stage, capacity=(1, 3), gold=5)
    shop = page(Page.SHOP, ("收起", 1624, 983), stage=stage, gold=5, offers=(offer,))
    sold = page(Page.SHOP, ("收起", 1624, 983), stage=stage, gold=None, offers=())
    returned = page(Page.BOARD, *[(label.text, *label.point) for label in initial.labels],
                    stage=stage, capacity=(1, 3), gold=4 if late_receipt else 5)
    for f in (initial, returned):
        monkeypatch.setattr(f, "slots", lambda: units)
    monkeypatch.setattr(sold, "shop_changed", lambda f, col: f is shop)
    monkeypatch.setattr(sold, "shop_slot_empty", lambda col: col == 0)
    team = board(*units, stage=stage, used=1, gold=5, lineup=policy.LINEUPS[policy.HIGH_ANAXA])
    monkeypatch.setattr(world.war, "_read_board", lambda f: (f, replace(team, gold=f.gold)))
    battle_frame = battle(True)
    end = page(Page.MATCH_RESULT, ("挑战成功", 960, 230), ("返回货币战争", 958, 890))
    lobby = home()
    routes = {(initial, (1624, 983)): shop, (shop, offer.point): shop, (shop, (1624, 983)): returned,
              (sold, (1624, 983)): returned, (returned, (1818, 751)): battle_frame, (end, (958, 890)): lobby}
    sent_at = None

    def click(state, point):
        nonlocal sent_at
        if (state.frame, point) == (shop, offer.point):
            sent_at = world.now[0]
        state.frame = routes[state.frame, point]

    def capture(state):
        if late_receipt and sent_at is not None and state.frame == shop and world.now[0] - sent_at > 9:
            state.frame = sold
        if state.frame is battle_frame:
            state.frame = end

    # The receipt is checked while input is still forbidden. For the late success,
    # return immediately to the board with a shop catalogue now containing no offers.
    def opened(frame):
        if late_receipt and frame is returned:
            return sold
        return original_open(frame)

    original_open = world.war._open_shop
    monkeypatch.setattr(world.war, "_open_shop", opened)
    monkeypatch.setattr(world.war, "_settle_shop", lambda f: f)
    state = drive(monkeypatch, world, initial, click, capture)
    assert world.war._play(initial) is lobby and world.war.result is True
    assert state.clicks.count((Page.SHOP, offer.point)) == 1
    assert (Page.BOARD, (1818, 751)) in state.clicks
    assert all(page != Page.BATTLE for page, _ in state.clicks)
    assert ((stage, "商店") in world.war.deferred_operations) == (not late_receipt)


def test_shop_purchase_interrupted_by_supply_is_not_repeated_after_return(monkeypatch, world):
    stage = "1-2"
    shop_button, offer_point, supply_button, fight_button, return_button = (
        (1624, 983), (470, 192), (1692, 984), (1818, 751), (960, 899)
    )
    offer = policy.Offer("那刻夏", 1, offer_point, 0)
    units = (slot("front", 0, FILLER), slot("bench", 0))
    initial = page(Page.BOARD, ("商店", *shop_button), ("出战", *fight_button), stage=stage, gold=9,
                   capacity=(1, 3))
    shop = page(Page.SHOP, ("收起", *shop_button), stage=stage, gold=9, offers=(offer,))
    supply = Frame(CANVAS, labels(("补给阶段", 961, 162), ("已选择1/1", 1683, 924), (stage, 470, 76)))
    result = page(Page.MATCH_RESULT, ("挑战成功", 960, 233), ("返回货币战争", *return_button))
    team = board(*units, stage=stage, used=1, gold=9, lineup=policy.LINEUPS[policy.HIGH_ANAXA])
    lobby = home()
    state = SimpleNamespace(frame=initial, clicks=[])
    routes = {(initial, shop_button): shop, (shop, offer_point): supply, (supply, supply_button): initial,
              (initial, fight_button): result, (result, return_button): lobby}

    def click(point, *, press_duration):
        action = state.frame, point
        state.clicks.append(action)
        state.frame = routes[action]
        return True

    monkeypatch.setattr(initial, "slots", lambda: units)
    monkeypatch.setattr(world.war, "_read_board", lambda f: (f, team))
    monkeypatch.setattr(world.war, "_capture", lambda: state.frame)
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))
    monkeypatch.setattr(world.war, "_notify", Mock())
    monkeypatch.setattr(task, "TASK_SECONDS", 25)
    world.auto.click_element_with_pos.side_effect = click

    assert world.war.start(resume=True) is True
    assert state.clicks == list(routes)
    assert (stage, "商店") in world.war.deferred_operations


def test_uncertain_experience_is_deferred_after_actual_board_read_with_no_second_f(monkeypatch, world):
    stage = "2-1"
    units = (slot("front", 0, CORE),)
    controls = (("出战", 1818, 751), ("购买经验", 296, 866))
    initial = page(Page.BOARD, *controls, stage=stage, capacity=(1, 3), gold=17,
                   level=3, experience=(0, 4), experience_cost=4)
    deducted = page(Page.BOARD, *controls, stage=stage, capacity=(1, 3), gold=13,
                    level=3, experience=(0, 4), experience_cost=4)
    team = board(*units, stage=stage, used=1, gold=17)
    for frame in (initial, deducted):
        monkeypatch.setattr(frame, "slots", lambda: units)
    monkeypatch.setattr(world.war, "_read_board", lambda f: (f, replace(team, gold=f.gold, exp=f.experience)))
    monkeypatch.setattr(world.war, "_can_buy_exp", lambda *_: True)
    entered = battle(True)
    state = drive(monkeypatch, world, initial, lambda s, _: setattr(s, "frame", entered))
    world.auto.press_key.side_effect = lambda key: (
        state.keys.append((state.frame.page, key)), setattr(state, "frame", deducted)
    )
    assert world.war._prepare(initial) is entered
    assert state.keys == [(Page.BOARD, "f")] and state.clicks == [(Page.BOARD, (1818, 751))]
    assert (stage, "经验") in world.war.deferred_operations


@pytest.mark.parametrize("expanded", (False, True))
def test_late_partial_experience_receipt_does_not_start_another_batch(monkeypatch, world, expanded):
    stage = "2-1"
    units = (slot("front", 0, CORE),)
    controls = (("出战", 1818, 751), ("购买经验", 296, 866))
    initial = page(Page.BOARD, *controls, stage=stage, capacity=(1, 1), gold=50,
                   level=7, experience=(64, 72), experience_cost=4)
    partial = page(Page.BOARD, *controls, stage=stage, capacity=(1, 1), gold=53,
                   level=7, experience=(68, 72), experience_cost=4)
    leveled = page(Page.BOARD, *controls, stage=stage, capacity=(1, 2), gold=55,
                   level=8, experience=(0, 80), experience_cost=4)
    for frame in (initial, partial, leveled):
        monkeypatch.setattr(frame, "slots", lambda: units)
    entered = battle(True)
    receipt_at = None

    def capture(state):
        if state.frame is initial and receipt_at is not None and world.now[0] >= receipt_at:
            state.frame = leveled if expanded else partial

    state = drive(monkeypatch, world, initial, lambda s, _: setattr(s, "frame", entered), capture)
    monkeypatch.setattr(world.war, "_read_board", lambda f: (f, board(
        *units, stage=stage, used=f.capacity[0], capacity=f.capacity[1], gold=f.gold, level=f.level, exp=f.experience,
    )))
    monkeypatch.setattr(world.war, "_can_buy_exp", lambda board, _: board.used == board.capacity)

    def press(key):
        nonlocal receipt_at
        state.keys.append((state.frame.page, key))
        if len(state.keys) == 2:
            receipt_at = world.now[0] + 1
        elif len(state.keys) > 2:
            state.frame = leveled
        return True

    world.auto.press_key.side_effect = press
    assert world.war._prepare(initial) is entered
    assert state.keys == [(Page.BOARD, "f")] * 2
    assert state.clicks == [(Page.BOARD, (1818, 751))]
    assert world.war.preparation_progress == 1
    assert ((stage, "经验") in world.war.deferred_operations) is not expanded


def test_high_experience_interrupted_by_supply_is_not_repeated_after_return(monkeypatch, world):
    stage = "2-6"
    world.cfg.currencywars_strategy = policy.HIGH_ANAXA
    units = (slot("front", 0, CORE), slot("back", 0, BAILU), slot("back", 1), slot("bench", 0, CER))
    initial = page(Page.BOARD, ("购买经验", 298, 864), ("出战", 1818, 751), stage=stage, gold=60,
                   capacity=(2, 2), level=4, experience=(0, 4), experience_cost=4)
    team = board(*units, stage=stage, gold=60, used=2, capacity=2, level=4, exp=(0, 4),
                 lineup=policy.LINEUPS[policy.HIGH_ANAXA])
    supply = Frame(CANVAS, labels(("补给阶段", 961, 162), ("已选择1/1", 1683, 924), (stage, 470, 76)))
    result = page(Page.MATCH_RESULT, ("挑战成功", 960, 233), ("返回货币战争", 960, 899))
    lobby = home()
    state = SimpleNamespace(frame=initial, keys=[], clicks=[])
    routes = {(supply, (1692, 984)): initial, (initial, (1818, 751)): result, (result, (960, 899)): lobby}

    def press(key):
        state.keys.append((state.frame, key))
        state.frame = supply
        return True

    def click(point, *, press_duration):
        action = state.frame, point
        state.clicks.append(action)
        state.frame = routes[action]
        return True

    monkeypatch.setattr(initial, "slots", lambda: units)
    monkeypatch.setattr(world.war, "_read_board", lambda f: (f, team))
    monkeypatch.setattr(world.war, "_capture", lambda: state.frame)
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))
    monkeypatch.setattr(world.war, "_notify", Mock())
    monkeypatch.setattr(task, "TASK_SECONDS", 25)
    world.auto.press_key.side_effect = press
    world.auto.click_element_with_pos.side_effect = click

    assert world.war.start(resume=True) is True
    assert state.keys == [(initial, "f")]
    assert state.clicks == list(routes)
    assert (stage, "经验") in world.war.deferred_operations


@pytest.mark.parametrize("same_team", (True, False))
def test_unconfirmed_optional_box_degrades_only_with_a_consistent_board(monkeypatch, world, same_team):
    stage = "1-2"
    units = (slot("front", 0, CORE), slot("bench", 0))
    frame = page(Page.BOARD, ("出战", 1818, 751), ("开启", 735, 940), stage=stage,
                 capacity=(1 if same_team else 2, 3), gold=0)
    monkeypatch.setattr(frame, "slots", lambda: units)
    monkeypatch.setattr(frame, "bench_slots", lambda: units[1:])
    open_box = Mock(side_effect=task.CurrencyWarsReceiptTimeout("开启尚无回执"))
    monkeypatch.setattr(world.war, "_open_box", open_box)
    monkeypatch.setattr(world.war, "_read_board", lambda f: (f, board(*units, stage=stage, gold=0, used=1)))
    entered = battle(True)
    state = drive(monkeypatch, world, frame, lambda s, _: setattr(s, "frame", entered))
    if same_team:
        assert world.war._prepare(frame) is entered
        assert state.clicks == [(Page.BOARD, (1818, 751))]
    else:
        with pytest.raises(task.CurrencyWarsReadTimeout, match="无法核对可继续"):
            world.war._prepare(frame)
        assert not state.clicks
    open_box.assert_called_once()
    assert not state.keys


def test_incomplete_replacement_can_put_back_the_verified_held_employee(monkeypatch, world):
    stage = "2-1"
    source = slot("front", 0, replace(CORE, stars=1))
    held = slot("bench", 1, source.unit)
    target = replace(source, occupied=False, unit=None)
    initial = page(Page.BOARD, stage=stage, capacity=(0, 4))
    restored = page(Page.BOARD, stage=stage, capacity=(1, 4))
    monkeypatch.setattr(initial, "slots", lambda: (held, target))
    monkeypatch.setattr(initial, "slot_occupied", lambda p: p == held.point)
    monkeypatch.setattr(restored, "slot_occupied", lambda p: p == target.point)
    monkeypatch.setattr(restored, "slot_portrait_matches", lambda p, _: p == target.point)
    active = board(held, target, stage=stage, used=0, capacity=4)
    monkeypatch.setattr(world.war, "_read_board", lambda f: (f, active))
    world.war.held_deployment = (source, replace(held, occupied=False, unit=None))
    state = drive(monkeypatch, world, initial)
    world.auto.drag_mouse.side_effect = lambda *a, **kw: setattr(state, "frame", restored)
    assert world.war._recover_deployment(active, task.CurrencyWarsReceiptTimeout("新角色无回执")) is restored
    world.auto.drag_mouse.assert_called_once()
    assert world.war.held_deployment is None
    assert (stage, "部署") in world.war.deferred_operations


@pytest.mark.parametrize("eventual_settlement", (False, True))
def test_uncertain_transition_never_replays_and_budget_expiry_saves_evidence(monkeypatch, world, eventual_settlement):
    initial = page(Page.RANK)
    board_frame = page(Page.BOARD, stage="1-2")
    unknown = page(Page.UNKNOWN, stage="1-2")
    result = page(Page.MATCH_RESULT)
    lobby = home()
    actions = []
    original_step = world.war._play_step

    def step(frame):
        if frame.page == Page.UNKNOWN:
            return original_step(frame)
        actions.append(frame.page)
        if frame.page == Page.BOARD:
            state.frame = unknown
            raise task.CurrencyWarsReceiptTimeout("后续动画未确认")
        assert frame.page == Page.MATCH_RESULT
        world.war.result = False
        return lobby

    def capture(state):
        if eventual_settlement and state.frame is unknown and world.now[0] >= 3:
            state.frame = result

    state = drive(monkeypatch, world, initial, after_capture=capture)
    monkeypatch.setattr(world.war, "_launch", lambda f, resume: board_frame)
    monkeypatch.setattr(world.war, "_play_step", step)
    monkeypatch.setattr(world.war, "get_reward", lambda f: (f, (18000, 18000), False))
    monkeypatch.setattr(task, "TASK_SECONDS", 45)
    if eventual_settlement:
        assert world.war.start() is False
        assert actions == [Page.BOARD, Page.MATCH_RESULT] and world.war.result is False
        task.save_error_screenshot.assert_not_called()
    else:
        with pytest.raises(task.CurrencyWarsBudgetExceeded, match="总时限"):
            world.war.start()
        assert actions == [Page.BOARD] and world.war.result is None
        task.save_error_screenshot.assert_called_once()
    assert not state.clicks and not state.keys


def test_successive_standard_runs_follow_updated_rank_with_full_weekly_score(monkeypatch, world):
    world.cfg.currencywars_rank_difficulty = "highest"
    world.cfg.currencywars_strategy = policy.HIGH_ANAXA
    lobby = home()
    modes = mode(("进入标准博弈", 1638, 960))
    start_button = ("开始对局", 1680, 965)
    outcomes = ("晋升失败", "晋升成功", "挑战成功")
    difficulties = (72, 72, 67)
    ranks = tuple(page(Page.RANK, ("标准博弈", 154, 884), start_button, enemy_rank=difficulty)
                  for difficulty in difficulties)
    boards = tuple(page(Page.BOARD, stage="1-1") for _ in outcomes)
    results = tuple(page(Page.MATCH_RESULT, (heading, 962, 241), ("返回货币战争", 962, 893))
                    for heading in outcomes)
    started = []
    settled = []

    def click(state, _):
        if state.frame is lobby:
            state.frame = modes
        elif state.frame is modes:
            state.frame = ranks[len(started)]
        elif state.frame.page == Page.RANK:
            assert state.frame is ranks[len(started)]
            started.append(state.frame.enemy_rank)
            state.frame = boards[len(started) - 1]
        else:
            assert state.frame is results[len(settled) - 1]
            state.frame = lobby

    def finish_battle(frame):
        assert frame is boards[len(started) - 1]
        state.frame = results[len(started) - 1]
        return state.frame

    state = drive(monkeypatch, world, lobby, click)
    monkeypatch.setattr(world.war, "_prepare", finish_battle)
    monkeypatch.setattr(world.war, "_on_match_result", lambda f: settled.append(world.war.result))
    weekly = Mock(side_effect=lambda f: (f, (18000, 18000), False))
    monkeypatch.setattr(world.war, "get_reward", weekly)

    assert [world.war.start() for _ in outcomes] == [False, True, True]
    assert started == list(difficulties)
    assert settled == [False, True, True]
    assert weekly.call_count == len(outcomes) and not state.keys


def test_weekly_uncertain_claim_returns_home_and_does_not_claim_twice(monkeypatch, world):
    lobby = home()
    weekly = page(Page.WEEKLY, ("18000/18000", 273, 740))
    monkeypatch.setattr(weekly, "claim_available", lambda: True)

    def click(state, point):
        if point == (381, 961):
            state.frame = weekly

    state = drive(monkeypatch, world, lobby, click)
    world.auto.press_key.side_effect = lambda key: (
        state.keys.append((state.frame.page, key)), setattr(state, "frame", lobby)
    )
    assert world.war._check_weekly_reward(lobby) == (lobby, (18000, 18000), False)
    assert world.war._check_weekly_reward(lobby) == (lobby, (18000, 18000), False)
    assert world.war.weekly_reward_pending
    assert state.clicks.count((Page.WEEKLY, (1640, 728))) == 1
    assert state.keys == [(Page.WEEKLY, "esc")] * 2
    world.cfg.save_timestamp.assert_not_called()


def test_halo_refresh_timeout_uses_a_confirmed_backup_without_spending_again(monkeypatch, world):
    stage = "2-5"
    world.war.last_result_stage = stage
    world.war.halo_candidate = halo_selection(slot("front", 0, CORE))
    refresh = ("刷新", 468, 770)
    common = (("闭关", 1480, 435), ("免费刷新还剩2次", 958, 134))
    initial = page(Page.HALO, ("乱披风拳法", 420, 435), refresh, *common, halo_gold=0)
    cards = (("前台专家", 420, 435), ("提高前台强度", 420, 545), *common)
    current = page(Page.HALO, *cards, halo_gold=0)
    selected = page(Page.HALO, *cards, ("确认", 960, 948), halo_gold=0)
    returned = page(Page.BOARD, stage=stage)
    match_halo_at(monkeypatch, (initial, current, selected), ui.HALO_TARGET)
    monkeypatch.setattr(selected, "halo_effect_selected", lambda i: i == 0)
    routes = {
        (initial, refresh[1:]): current, (current, (420, 435)): selected, (selected, (960, 948)): returned,
    }
    state = drive(monkeypatch, world, initial, lambda s, point: setattr(s, "frame", routes[s.frame, point]))
    assert world.war._halo(initial) is returned
    assert state.clicks == [(Page.HALO, point) for point in (refresh[1:], (420, 435), (960, 948))]
    assert (stage, "光环刷新") in world.war.deferred_operations


def test_result_without_a_button_observes_game_auto_advance(monkeypatch, world):
    first = page(Page.NODE_RESULT, ("挑战结束", 962, 236))
    result = page(Page.MATCH_RESULT, ("挑战失败", 962, 236), ("下一页", 963, 890))
    state = drive(monkeypatch, world, first, after_capture=lambda s: setattr(s, "frame", result)
                  if world.now[0] >= 1 else None)
    assert world.war._result_page(first) is result
    assert world.war.result is False
    assert not state.clicks and not state.keys


def test_drag_uses_the_verified_frame_geometry_without_an_unchecked_recapture(world):
    frame = page(Page.BOARD, stage="1-2")
    world.war.frame = frame
    automation = object.__new__(Automation)
    automation.screenshot = frame.image
    automation.screenshot_pos = (40, 50, 1920, 1080)
    automation.screenshot_scale_factor = 1
    automation.take_screenshot = Mock(side_effect=RuntimeError("验证后的棋盘已被下一帧遮挡"))
    automation.mouse_drag = Mock(return_value=True)
    world.auto.drag_mouse.side_effect = automation.drag_mouse

    assert world.war._drag(frame, (750, 405), (900, 405))
    automation.take_screenshot.assert_not_called()
    automation.mouse_drag.assert_called_once_with(790, 455, 940, 455, 0.5, 0.10)


def test_match_recognition_window_restarts_after_a_confirmed_page(monkeypatch, world):
    active = page(Page.BOARD, stage="1-2")
    unknown = page(Page.UNKNOWN)
    conflict = page(Page.CONFLICT)
    world.war.in_match = True
    world.war.frame = active
    monkeypatch.setattr(task, "MATCH_UNIDENTIFIED_SECONDS", 5)
    capture = Mock(side_effect=(unknown, active, conflict, unknown, conflict))
    monkeypatch.setattr(world.war, "_capture", capture)

    assert world.war._observe() is unknown
    world.now[0] = 4
    assert world.war._observe() is active
    world.now[0] = 5
    assert world.war._observe() is conflict
    world.now[0] = 9
    assert world.war._observe() is unknown
    world.now[0] = 10
    with pytest.raises(task.CurrencyWarsUnavailable, match="对局画面持续无法识别"):
        world.war._observe()
    world.auto.click_element_with_pos.assert_not_called()


def test_unknown_match_screen_gets_one_escape_at_the_recognition_limit(monkeypatch, world):
    initial = page(Page.CHOICE, stage="1-2", choice="补给阶段")
    unknown = page(Page.UNKNOWN)
    ready = page(Page.BOARD, stage="1-2", capacity=(1, 3))
    ready.field_slots = lambda: (slot("front", 0, CORE), slot("back", 0))
    lobby = home()
    world.war.frame = initial
    world.war.in_match = True
    world.war.deadline = 60
    current = initial
    keys = []
    monkeypatch.setattr(task, "MATCH_UNIDENTIFIED_SECONDS", 2)
    monkeypatch.setattr(world.war, "_capture", lambda: current)

    def step(f):
        nonlocal current
        if f is ready:
            return lobby
        current = unknown
        return world.war._expect(lambda frame: frame is ready, 10, "识别失败")

    def press(key):
        nonlocal current
        keys.append(key)
        current = ready

    monkeypatch.setattr(world.war, "_play_step", step)
    world.auto.press_key.side_effect = press
    assert world.war._play(initial) is lobby
    assert keys == ["esc"]


@pytest.mark.parametrize("source", ("battle", "node_result", "combat_conflict", "late_combat_conflict"))
def test_unreadable_combat_or_settlement_never_sends_escape(monkeypatch, world, source):
    unreadable = page(Page.UNKNOWN)
    combat_conflict = Frame(CANVAS, labels(("2-3", 726, 26), ("2%", 773, 28), ("出战", 1818, 750)))
    assert combat_conflict.page == Page.CONFLICT and combat_conflict.combat_buttons
    if source == "battle":
        initial = battle(True)
    elif source == "node_result":
        initial = page(Page.NODE_RESULT, ("挑战结束", 958, 232))
    else:
        initial = page(Page.CHOICE, choice="遭遇节点", stage="2-3")
        if source == "combat_conflict":
            unreadable = combat_conflict
        monkeypatch.setattr(world.war, "_choose", lambda frame: world.war._expect(
            lambda f: f.page == Page.BOARD, 10, "局内页面仍有冲突",
        ))
    recognition_limit = 2
    monkeypatch.setattr(task, "MATCH_UNIDENTIFIED_SECONDS", recognition_limit)
    captures = iter((initial,))
    limit_reached = False

    def capture():
        nonlocal limit_reached
        if frame := next(captures, None):
            return frame
        if source == "late_combat_conflict":
            if limit_reached:
                return combat_conflict
            since = world.war.unidentified_since
            limit_reached = since is not None and world.now[0] - since >= recognition_limit
        return unreadable

    monkeypatch.setattr(world.war, "_capture", capture)

    with pytest.raises(task.CurrencyWarsUnavailable, match="对局画面持续无法识别"):
        world.war.start(resume=True)
    world.auto.press_key.assert_not_called()
    world.auto.click_element_with_pos.assert_not_called()


@pytest.mark.parametrize("source", ("board", "confirm", "skip"))
def test_unreadable_first_frame_after_fight_input_never_sends_escape(monkeypatch, world, source):
    stage = "2-3"
    fight = "跳过(1/1)" if source == "skip" else "出战"
    press_point = (963, 694) if source == "confirm" else (1818, 751)
    if source == "confirm":
        initial = page(Page.CONFIRM_FIGHT, ("确认", *press_point), stage=stage)
    else:
        initial = page(Page.BOARD, (fight, *press_point), stage=stage)
        monkeypatch.setattr(world.war, "_prepare", lambda f: world.war._advance_board(f, f.board_advance))
    state = SimpleNamespace(frame=initial, clicks=[])
    monkeypatch.setattr(task, "MATCH_UNIDENTIFIED_SECONDS", 2)
    monkeypatch.setattr(world.war, "_capture", lambda: state.frame)

    def click(point, *, press_duration):
        state.clicks.append(point)
        state.frame = page(Page.UNKNOWN)
        return True

    world.auto.click_element_with_pos.side_effect = click
    with pytest.raises(task.CurrencyWarsUnavailable, match="对局画面持续无法识别"):
        world.war.start(resume=True)
    assert state.clicks == [press_point]
    world.auto.press_key.assert_not_called()


def issue_1398_board(monkeypatch, fault=None, advance="选择主角"):
    # #1398 附件裁取的棋盘原像素。固定可见的 OCR 文字，不依赖测试机安装识别模型。
    image = CANVAS.copy()
    with Image.open("tests/test_tasks/fixtures/currency_wars_1398_board.webp") as crop:
        image.paste(crop, (513, 212))
    if fault == "extra_card":
        # 模拟未收录的特殊图案：真实角色纹理被计成第七人，HUD 仍然是 6/7。
        image.paste(image.crop((824, 328, 952, 474)), (681, 328))
    elif fault == "missing_rows":
        ImageDraw.Draw(image).rectangle((375, 589, 1550, 621), fill=(39, 38, 78))
    frame = Frame(image, labels(("备战阶段", 410, 57), ("2-5", 450, 82), ("6/7", 958, 259),
                                ("前台区域", 966, 315), ("后台区域", 966, 577), ("商店", 1624, 982),
                                (advance, 1818, 751)))
    monkeypatch.setattr(frame, "read_local", lambda *_, **__: None)
    return frame


def test_issue_1398_star_is_not_a_seventh_employee_or_a_drop_target(monkeypatch):
    frame = issue_1398_board(monkeypatch)
    assert frame.page == Page.BOARD and frame.stage == "2-5" and frame.capacity == (6, 7)
    field = frame.field_slots()
    assert frame.front_markers == {(745, ui.FRONT_Y)}
    assert [(s.index, s.occupied, s.blocked) for s in field if s.zone == "front"] == [
        (0, False, True), (1, True, False), (2, True, False), (3, True, False),
    ]
    assert sum(s.occupied for s in field if s.zone == "back") == 3
    assert frame.field_count_matches(field)


def test_new_front_marker_blocks_a_pending_drag(monkeypatch, world):
    source = policy.Slot("bench", 0, ui.BENCH_POINTS[0], True, CORE)
    destination = policy.Slot("front", 0, (745, ui.FRONT_Y), False)
    b = board(source, destination, used=1)
    initial = page(Page.BOARD, stage=b.stage, capacity=(b.used, b.capacity))
    changed = issue_1398_board(monkeypatch)
    changed.__dict__.update(page=Page.BOARD, stage=b.stage, capacity=initial.capacity)
    for f in (initial, changed):
        monkeypatch.setattr(f, "slot_occupied", lambda p: p == source.point)
    state = drive(monkeypatch, world, initial)
    state.frame = changed
    with pytest.raises(task.CurrencyWarsActionUnready, match="已尝试 0 次"):
        world.war._move(initial, b, source, destination)
    world.auto.drag_mouse.assert_not_called()

    rear = slot("back", 0, policy.Unit("灵活输出", True, True, 1, output=True))
    next_front = slot("front", 1)
    assert policy.deployment(board(replace(destination, blocked=True), next_front, rear, used=1)) == (
        (rear, next_front),)


@pytest.mark.parametrize(("fault", "advance", "outcome"), (
    ("extra_card", "选择主角", "restart"), ("missing_rows", "选择主角", "restart"),
    ("extra_card", "出战", "restart"), ("extra_card", "出战", "fight_works"),
    ("missing_rows", "选择主角", "limit"), ("extra_card", "选择主角", "late_prompt"),
))
def test_stalled_board_settles_old_match_before_entering_new_one(monkeypatch, world, fault, advance, outcome):
    blocked = issue_1398_board(monkeypatch, fault, advance)
    field = blocked.field_slots()
    assert blocked.page == Page.BOARD and blocked.capacity == (6, 7)
    assert sum(s.occupied for s in field) == (7 if fault == "extra_card" else 0)
    assert not blocked.field_count_matches(field)
    prompt = active_match_exit_dialog()
    lost = page(Page.MATCH_RESULT, ("对局失败", 960, 233), ("返回货币战争", 960, 899))
    fresh = mode(("进入超频博弈", 1638, 960))
    ranks = page(Page.RANK, ("开始对局", 1680, 965), rank_mode="overclock", enemy_rank=28)
    new = page(Page.BOARD, ("出战", 1818, 751), stage="1-1")
    won = page(Page.MATCH_RESULT, ("对局胜利", 960, 233), ("返回货币战争", 960, 899))
    lobby = home()
    transition = page(Page.UNKNOWN)
    state = SimpleNamespace(frame=blocked, events=[], prompt_at=None)
    routes = {(prompt, (770, 743)): lost, (lost, (960, 899)): fresh, (fresh, (1638, 960)): ranks,
              (ranks, (1680, 965)): new, (new, (1818, 751)): won, (won, (960, 899)): lobby}
    prepare = world.war._prepare

    def click(point, *, press_duration):
        state.events.append((state.frame, point))
        if state.frame is blocked and point == (1818, 751) and advance == "出战":
            if outcome == "fight_works":
                state.frame = won
        else:
            state.frame = routes[state.frame, point]
        return True

    def prepare_match(f):
        if f is not new:
            return prepare(f)
        if outcome == "limit":  # 已识别并进入 1-1；之后这局也卡在同一节点。
            state.frame = blocked
            return blocked
        return world.war._advance_board(f, f.board_advance)

    def press(key):
        assert state.frame is blocked and key == "esc" and world.now[0] >= task.STALLED_LAYOUT_SECONDS
        state.events.append((state.frame, key))
        state.frame = transition if outcome == "late_prompt" else prompt
        state.prompt_at = world.now[0] + 1
        return True

    def capture():
        if state.frame is transition and world.now[0] >= state.prompt_at:
            state.frame = prompt
        return state.frame

    monkeypatch.setattr(world.war, "_capture", capture)
    monkeypatch.setattr(world.war, "_collect_preparation_rewards", lambda f: (f, True))
    monkeypatch.setattr(world.war, "_prepare", prepare_match)
    monkeypatch.setattr(world.war, "_check_weekly_reward", lambda f: (f, (18000, 18000), False))
    world.cfg.currencywars_type = "overclock"
    world.auto.click_element_with_pos.side_effect = click
    world.auto.press_key.side_effect = press
    if outcome == "limit":
        with pytest.raises(task.CurrencyWarsUnavailable, match="已达对局重开上限"):
            world.war.start(resume=True, loop=True)
        restart = [(blocked, "esc"), (prompt, (770, 743)), (lost, (960, 899)),
                   (fresh, (1638, 960)), (ranks, (1680, 965))]
        assert state.events == restart * task.MAX_MATCH_RESTARTS + restart[:3]
        assert state.frame is fresh and world.war.result is None
    else:
        assert world.war.start(resume=True, loop=True)
        if outcome == "fight_works":
            assert state.events == [(blocked, (1818, 751)), (won, (960, 899))]
        else:
            tried = [(blocked, (1818, 751))] * (2 if advance == "出战" else 0)
            assert state.events == [*tried, (blocked, "esc"), *routes.keys()]
        assert state.frame is lobby and world.war.result is True and world.war._loop_matches == 1


@pytest.mark.parametrize("when", (
    "early", "late", "before_key", "flicker_before_key", "existing_prompt", "failed_key", "foreign_after_key",
))
def test_recovered_or_unowned_board_is_never_abandoned(monkeypatch, world, when):
    blocked = issue_1398_board(monkeypatch, "extra_card")
    ready = issue_1398_board(monkeypatch)
    prompt, foreign, menu, lobby = active_match_exit_dialog(), end_match_dialog(), mode(), home()
    state = SimpleNamespace(frame=blocked, keys=[], flicker_at=None, unreadable_seen=False)
    restart = world.war._restart_match

    def capture():
        if state.flicker_at is not None:
            if not state.unreadable_seen:
                state.unreadable_seen = True
                return page(Page.UNKNOWN)
            if world.now[0] >= state.flicker_at + 3:
                state.frame = ready
        if (state.frame is blocked and when in ("early", "late")
                and world.now[0] >= (0.5 if when == "early" else 25)):
            state.frame = ready
        return state.frame

    def prepare_or_continue(f):
        if f is not ready:
            f, _ = world.war._board_layout(f)
        assert f is ready
        state.frame = lobby
        return lobby

    def before_restart(frame, **kwargs):
        if when == "before_key":
            state.frame = ready
        elif when == "flicker_before_key":
            state.flicker_at = world.now[0]
        elif when == "existing_prompt":
            state.frame = prompt
        return restart(frame, **kwargs)

    def press(key):
        state.keys.append((state.frame, key))
        if state.frame is prompt:
            state.frame = ready
            return True
        if when == "foreign_after_key":
            state.frame = {blocked: foreign, foreign: menu, menu: lobby}[state.frame]
            return True
        assert state.frame is blocked and when == "failed_key"
        state.frame = prompt  # 后端报告未送达，屏幕恰好出现退出弹窗；不得据以弃局。
        return False

    monkeypatch.setattr(world.war, "_capture", capture)
    monkeypatch.setattr(world.war, "_restart_match", before_restart)
    monkeypatch.setattr(world.war, "_prepare", prepare_or_continue)
    world.auto.press_key.side_effect = press
    assert world.war._play_with_restarts(blocked) is lobby
    if when == "failed_key":
        assert state.keys == [(blocked, "esc"), (prompt, "esc")]
    elif when == "foreign_after_key":
        assert state.keys == [(f, "esc") for f in (blocked, foreign, menu)]
    else:
        assert state.keys == ([(prompt, "esc")] if when == "existing_prompt" else [])
    world.auto.click_element_with_pos.assert_not_called()


def test_layout_recovers_after_two_unrelated_preparation_fallbacks(monkeypatch, world):
    ready = issue_1398_board(monkeypatch)
    blocked = issue_1398_board(monkeypatch, "extra_card")
    lobby = home()
    state = SimpleNamespace(frame=ready, fallbacks=0)

    def prepare(frame):
        if state.fallbacks < 3:
            raise task.CurrencyWarsActionUnready("普通备战暂未完成")
        assert frame is ready
        return lobby

    def advance():
        state.fallbacks += 1
        state.frame = blocked if state.fallbacks == 2 else ready
        return state.frame

    monkeypatch.setattr(world.war, "_capture", lambda: state.frame)
    monkeypatch.setattr(world.war, "_prepare", prepare)
    monkeypatch.setattr(world.war, "_advance_existing_team", advance)
    restart = Mock(side_effect=AssertionError("棋盘已经恢复，不应进入弃局流程"))
    monkeypatch.setattr(world.war, "_restart_match", restart)
    assert world.war._play_with_restarts(ready) is lobby
    assert state.fallbacks == 3
    restart.assert_not_called()


@pytest.mark.parametrize("condition", ("pending_fight", "banner", "shop", "preview", "combat",
                                       "unknown", "conflict", "result", "missing_action", "missing_capacity",
                                       "missing_shop_anchor", "unreadable_field"))
def test_partial_board_evidence_never_authorizes_conflict_restart(monkeypatch, world, condition):
    frame = issue_1398_board(monkeypatch, "extra_card")
    world.war.in_match = True
    assert world.war._conflicted_board_key(frame) == ("2-5", (6, 7), "选择主角")
    if condition == "pending_fight":
        world.war._battle_entry_stage = "2-5"
    elif condition == "preview":
        monkeypatch.setattr(frame, "halo_preview", lambda: True)
    elif condition == "result":
        world.war.result = True
    elif condition == "missing_shop_anchor":
        frame.labels = tuple(label for label in frame.labels if label.text != "商店")
    elif condition == "unreadable_field":
        monkeypatch.setattr(frame, "field_slots", Mock(side_effect=ValueError("画面不可读")))
    elif condition in ("unknown", "conflict"):
        frame.__dict__["page"] = Page.UNKNOWN if condition == "unknown" else Page.CONFLICT
    else:
        field, value = {"banner": ("preparation_banner", True), "shop": ("shop_open", True),
                        "combat": ("combat_buttons", True), "missing_action": ("board_advance", None),
                        "missing_capacity": ("capacity", None)}[condition]
        frame.__dict__[field] = value
    assert world.war._conflicted_board_key(frame) is None


@pytest.mark.parametrize("source", ("unknown", "unverified_board"))
def test_unverified_frame_escape_cannot_authorize_abandon(monkeypatch, world, source):
    initial = page(Page.UNKNOWN) if source == "unknown" else page(Page.BOARD, stage="2-3", capacity=(2, 3))
    if source == "unverified_board":
        initial.field_slots = lambda: (slot("front", 0, CORE), slot("back", 0))
        assert not world.war._restartable_board(initial)
    prompt = active_match_exit_dialog()
    state = drive(monkeypatch, world, initial)

    def press(key):
        state.keys.append(key)
        state.frame = prompt
        return True

    world.auto.press_key.side_effect = press
    failure = task.CurrencyWarsPageBlocked(initial, "对局画面持续无法识别")
    assert world.war._escape_blocked_page(failure, set()) is prompt
    assert state.keys == ["esc"] and not state.clicks


def test_capture_retries_a_transient_screenshot_timeout_without_input(monkeypatch, world):
    expected = page(Page.BOARD, stage="1-2")
    capture = Mock(side_effect=(RuntimeError("截图超时"), expected))
    monkeypatch.setattr(world.war, "_capture", capture)
    assert world.war._observe() is expected
    assert capture.call_count == 2
    world.auto.click_element_with_pos.assert_not_called()
    world.auto.press_key.assert_not_called()


@pytest.mark.parametrize("current_match", ("playing", "entry_sent", None))
def test_observation_preserves_the_first_result_only_for_the_current_match(monkeypatch, world, current_match):
    result = Frame(CANVAS, labels(("对局胜利", 960, 233)))
    detail = Frame(CANVAS, labels(("返回货币战争", 960, 899)))
    monkeypatch.setattr(world.war, "_capture", Mock(side_effect=(result, detail)))
    world.war.in_match = current_match == "playing"
    world.war.mode_confirmed = current_match == "entry_sent"

    assert world.war._observe() is result
    assert world.war._observe() is detail
    assert world.war.result is (True if current_match else None)


@pytest.mark.parametrize("readiness", (False, True))
def test_observation_recaptures_after_screenshot_ocr_and_first_page_failures(monkeypatch, world, readiness):
    class BrokenPage:
        @property
        def page(self):
            raise ValueError("模板读取失败")

    expected = page(Page.BOARD, stage="1-2")
    world.auto.screenshot = CANVAS
    world.auto.ocr_result = ()
    world.auto.take_screenshot.side_effect = (RuntimeError("截图超时"), True, True, True, True)
    world.auto.perform_ocr.side_effect = (RuntimeError("OCR 推理失败"), None, None, None)
    parse = Mock(side_effect=(BrokenPage(), page(Page.UNKNOWN), expected))
    monkeypatch.setattr(ui.Frame, "from_ocr", parse)

    if readiness:
        assert task.CurrencyWars.game_screen_ready()
    else:
        assert world.war._observe() is expected
    assert world.auto.take_screenshot.call_count == task.MAX_CAPTURE_ATTEMPTS
    assert all(call.kwargs == {"raise_on_error": True} for call in world.auto.perform_ocr.call_args_list)
    world.auto.click_element_with_pos.assert_not_called()


def test_start_reports_persistent_game_capture_failure_after_retries(monkeypatch, world):
    capture = Mock(side_effect=RuntimeError("截图超时"))
    monkeypatch.setattr(world.war, "_capture", capture)
    with pytest.raises(task.CurrencyWarsUnavailable, match="连续无法获取或识别游戏画面"):
        world.war.start()
    assert capture.call_count == 5
    task.save_error_screenshot.assert_called_once()


def test_entry_can_continue_when_launch_receipt_arrived_after_the_timeout(monkeypatch, world):
    lobby = home()
    started = page(Page.BOARD, stage="1-1")
    state = drive(monkeypatch, world, lobby)

    def launch(*_):
        state.frame = started
        raise task.CurrencyWarsReceiptTimeout("未确认开局")

    monkeypatch.setattr(world.war, "_launch", Mock(side_effect=launch))
    assert world.war._enter_with_recovery(lobby, resume=False) is started
    world.war._launch.assert_called_once()


@pytest.mark.parametrize("won", (True, False))
def test_unreadable_reward_transition_preserves_the_verified_match_result(monkeypatch, world, won):
    result = page(Page.MATCH_RESULT, ("挑战成功" if won else "挑战失败", 960, 233), ("返回货币战争", 960, 899))
    lobby = home()
    unknown = page(Page.UNKNOWN)
    state = drive(monkeypatch, world, result, lambda s, _: setattr(s, "frame", lobby))

    def get_reward(_):
        state.frame = unknown
        raise task.CurrencyWarsReceiptTimeout("领奖未确认")

    monkeypatch.setattr(world.war, "get_reward", Mock(side_effect=get_reward))
    assert world.war.start(resume=True) is won
    assert world.war.result is won
    outcome = "胜利" if won else "战败"
    task.Base.send_notification_with_screenshot.assert_called_once_with(
        f"货币战争已结算（{outcome}），周奖励待核对",
        task.NotificationLevel.ALL if won else task.NotificationLevel.ERROR, result.image,
    )
    world.war.get_reward.assert_called_once()
    world.cfg.save_timestamp.assert_not_called()


def test_reward_timeout_records_pending_after_the_match_was_decided(monkeypatch, world):
    result = page(Page.MATCH_RESULT, ("挑战成功", 960, 233), ("返回货币战争", 960, 899))
    lobby = home()
    drive(monkeypatch, world, result, lambda s, _: setattr(s, "frame", lobby))
    logger = Mock()
    monkeypatch.setattr(task, "log", logger)
    get_reward = Mock(side_effect=task.CurrencyWarsBudgetExceeded("总时限"))
    monkeypatch.setattr(world.war, "get_reward", get_reward)

    with pytest.raises(task.CurrencyWarsBudgetExceeded, match="总时限"):
        world.war.start(resume=True)
    assert world.war.result is True
    logger.warning.assert_any_call("货币战争已确认整局胜利，本次领奖仍待核对：总时限")
    world.cfg.save_timestamp.assert_not_called()


@pytest.mark.parametrize("fault", ("exception", "unreadable"))
def test_weekly_read_recovers_on_the_open_points_page(monkeypatch, world, fault):
    lobby = home()
    weekly = page(Page.WEEKLY, ("18000/18000", 273, 740))
    errors_remaining = 2
    retry_at = None

    def claim_available():
        nonlocal errors_remaining, retry_at
        if fault == "exception" and errors_remaining:
            errors_remaining -= 1
            raise OSError("暂时无法识别领奖状态")
        if retry_at is None:
            retry_at = world.now[0] + 7.1
        return False if fault == "exception" or world.now[0] >= retry_at else None

    monkeypatch.setattr(weekly, "claim_available", claim_available)
    recover = Mock(wraps=world.war._recover_weekly_reward)
    monkeypatch.setattr(world.war, "_recover_weekly_reward", recover)
    state = drive(monkeypatch, world, lobby, lambda s, _: setattr(s, "frame", weekly))
    world.auto.press_key.side_effect = lambda key: setattr(state, "frame", lobby)
    assert world.war.start(weekly=True)
    assert state.clicks == [(Page.HOME, (381, 961))]
    assert recover.call_count == (1 if fault == "unreadable" else 0)
    world.cfg.save_timestamp.assert_called_once_with("currencywars_timestamp")


def test_weekly_claim_retries_coordinate_mapping_before_any_input(monkeypatch, world):
    lobby = home()
    pending = page(Page.WEEKLY, ("18000/18000", 273, 740), claim_available=lambda: True)
    credited = page(Page.WEEKLY, ("18000/18000", 273, 740), claim_available=lambda: False)
    state = drive(monkeypatch, world, pending, lambda s, _: setattr(s, "frame", credited))
    world.auto.press_key.side_effect = lambda _: setattr(state, "frame", lobby)
    world.auto.find_element.side_effect = (None, (1640, 728))

    assert world.war.start(weekly=True)
    assert state.clicks == [(Page.WEEKLY, (1640, 728))]
    assert not world.war.reward_state.claim_sent
    assert not world.war.weekly_reward_pending
    world.cfg.save_timestamp.assert_called_once_with("currencywars_timestamp")


def test_transition_wait_preserves_a_result_heading_shown_without_buttons(monkeypatch, world):
    detail = Frame(CANVAS, labels(("返回货币战争", 960, 899)))
    result = Frame(CANVAS, labels(("对局胜利", 960, 233)))
    lobby = home()
    assert result.page == detail.page == Page.MATCH_RESULT

    def capture(state):
        if state.frame is result:
            state.frame = lobby
        elif world.now[0] > 0 and state.frame is detail:
            state.frame = result

    state = drive(monkeypatch, world, detail, after_capture=capture)
    monkeypatch.setattr(world.war, "get_reward", lambda f: (f, (18000, 18000), False))
    assert world.war.start(resume=True)
    assert world.war.result is True
    assert state.clicks == [(Page.MATCH_RESULT, (960, 899))]


def test_timestamp_write_failure_keeps_the_confirmed_weekly_score_and_match_result(monkeypatch, world):
    result = page(Page.MATCH_RESULT, ("挑战成功", 960, 233), ("返回货币战争", 960, 899))
    lobby = home()
    weekly = page(Page.WEEKLY, ("18000/18000", 273, 740), claim_available=lambda: False)
    routes = {(result, (960, 899)): lobby, (lobby, (381, 961)): weekly}
    state = drive(monkeypatch, world, result, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    world.auto.press_key.side_effect = lambda key: setattr(state, "frame", lobby)
    world.cfg.save_timestamp.side_effect = OSError("暂时无法写入配置")
    logger = Mock()
    monkeypatch.setattr(task, "log", logger)

    assert world.war.start(weekly=True)
    assert world.war.result is True
    logger.warning.assert_called_once_with("货币战争周积分与奖励已核对，写入完成时间失败：暂时无法写入配置")
    world.cfg.save_timestamp.assert_called_once_with("currencywars_timestamp")


def portraits(*cards):
    """在卡位中心绘制可区分的纹理肖像。cards 为 (卡位, 随机种子[, 亮度偏移])。"""
    image = CANVAS.copy()
    for point, seed, *shift in cards:
        x, y = point
        patch = np.random.default_rng(seed).integers(40, 216, (61, 60, 3)).astype(np.int16)
        patch = np.clip(patch + (shift[0] if shift else 0), 0, 255).astype(np.uint8)
        image.paste(Image.fromarray(patch), (x - 30, y - 31))
    return image


def board_screen(image, slots, *extra, stage="2-5", gold=10, **properties):
    """真实卡位读取所需的棋盘帧：肖像来自图像，占用、站位标记和星级按给定卡位返回。"""
    used = sum(s.occupied for s in slots if s.zone != "bench")
    frame = Frame(image, labels(*extra))
    frame.__dict__.update(page=Page.BOARD, stage=stage, capacity=(used, used), gold=gold, **properties)
    occupied = {s.point for s in slots if s.occupied}
    frame.slots = lambda: slots
    frame.slot_occupied = lambda point: point in occupied
    frame.card_role = lambda _: (True, True)
    frame.card_stars = lambda *_, **__: 1
    frame.assigned_halo = lambda _: False
    return frame


def employee(name, role="前台", stage="2-5"):
    detail = page(Page.DETAIL, (name, 1610, 228), (role, 1575, 279), stage=stage)
    detail.employee_output = lambda **_: False
    return detail


def test_board_scan_keeps_an_unreadable_name_until_the_card_changes(monkeypatch, world):
    trailblazer = slot("bench", 2, occupied=True)
    original = board_screen(portraits((trailblazer.point, 7)), (trailblazer,))
    replaced = board_screen(portraits((trailblazer.point, 8)), (trailblazer,))
    detail = employee("星", "前后台")
    # 单字的开拓者名不符合角色名规则，读详情后仍无法得到姓名。
    detail.employee_name = lambda **_: None
    current = [original]
    state = drive(monkeypatch, world, original,
                  lambda s, p: setattr(s, "frame", detail if p == trailblazer.point else current[0]))

    for _ in range(3):
        after, scanned = world.war._read_board(state.frame)
        assert after is original and scanned.slots == (trailblazer,)
    assert state.clicks == [(Page.BOARD, trailblazer.point), (Page.DETAIL, (12, 12))]

    current[0] = state.frame = replaced
    after, scanned = world.war._read_board(replaced)
    assert after is replaced and scanned.slots == (trailblazer,)
    assert state.clicks[2:] == [(Page.BOARD, trailblazer.point), (Page.DETAIL, (12, 12))]


def test_board_scan_reuses_a_known_card_after_a_brightness_shift_without_waiting(monkeypatch, world):
    flower = slot("front", 0, occupied=True)
    clean = board_screen(portraits((flower.point, 11)), (flower,))
    brighter = board_screen(portraits((flower.point, 11, 40)), (flower,))
    detail = employee("花火")
    state = drive(monkeypatch, world, clean, lambda s, p: setattr(s, "frame", detail if p == flower.point else clean))
    assert world.war._read_board(clean)[1].slots[0].unit.name == "花火"
    clicks, started = list(state.clicks), world.now[0]

    state.frame = brighter
    after, scanned = world.war._read_board(brighter)
    assert after is brighter and scanned.slots[0].unit.name == "花火"
    assert state.clicks == clicks and world.now[0] == started


@pytest.mark.parametrize("both_new", (False, True))
def test_board_scan_names_a_just_bought_card_without_reopening_its_detail(monkeypatch, world, both_new):
    """刚买下的卡落在买前空着的备战格。只多出这一张、且本局读过这名角色时沿用商店里的姓名和站位，不再打开详情；
    多出不止一张时照常逐张读详情。"""
    flower = slot("front", 0, occupied=True)
    bench = (slot("bench", 0, occupied=both_new), slot("bench", 1, occupied=True))
    before = board_screen(portraits((flower.point, 11)), (flower, slot("bench", 0), slot("bench", 1)))
    after = board_screen(portraits((flower.point, 11), (bench[0].point, 31), (bench[1].point, 21)), (flower, *bench))
    details = {flower.point: employee("花火"), bench[0].point: employee("知更鸟"), bench[1].point: employee("花火")}
    current = [before]
    state = drive(monkeypatch, world, before, lambda s, p: setattr(s, "frame", details.get(p, current[0])))
    world.war._read_board(before)
    assert state.clicks == [(Page.BOARD, flower.point), (Page.DETAIL, (12, 12))]

    world.war.purchased_card = task.PurchasedCard("2-5", "花火", frozenset({0, 1}))
    current[0] = state.frame = after
    _, scanned = world.war._read_board(after)
    names = [(s.zone, s.index, s.unit.name) for s in scanned.slots if s.unit]
    expected = [("front", 0, "花火"), *([("bench", 0, "知更鸟")] if both_new else []), ("bench", 1, "花火")]
    assert names == expected
    reads = [(Page.BOARD, bench[0].point), (Page.DETAIL, (12, 12)), (Page.BOARD, bench[1].point), (Page.DETAIL, (12, 12))]
    assert state.clicks[2:] == (reads if both_new else [])
    assert world.war.purchased_card is None


@pytest.mark.parametrize("outcome", ("settled", "changed", "budget", "stopped"))
def test_board_scan_waits_for_a_closing_shop_before_reopening_a_known_card(monkeypatch, world, outcome):
    flower = slot("front", 0, occupied=True)
    clean = board_screen(portraits((flower.point, 11)), (flower,))
    # 收起商店时，滑走的商品卡还盖在前台卡位上。
    covered = board_screen(portraits((flower.point, 11), ((flower.point[0], flower.point[1] - 8), 99)), (flower,))
    changed = board_screen(portraits((flower.point, 12)), (flower,))
    detail = employee("花火")
    after_close = {"settled": clean, "changed": changed, "budget": clean, "stopped": clean}[outcome]
    current = [clean]
    state = drive(monkeypatch, world, clean,
                  lambda s, p: setattr(s, "frame", detail if p == flower.point else current[0]))
    world.war._read_board(clean)
    assert state.clicks == [(Page.BOARD, flower.point), (Page.DETAIL, (12, 12))]

    current[0] = state.frame = after_close
    if outcome == "budget":
        world.war.deadline = world.now[0]
        with pytest.raises(task.CurrencyWarsBudgetExceeded):
            world.war._read_board(covered)
    elif outcome == "stopped":
        task.pause_ctl.checkpoint.side_effect = RunStopRequested
        with pytest.raises(RunStopRequested):
            world.war._read_board(covered)
    else:
        after, scanned = world.war._read_board(covered)
        assert after is after_close and scanned.slots[0].unit.name == "花火"
    reopened = [(Page.BOARD, flower.point), (Page.DETAIL, (12, 12))] if outcome == "changed" else []
    assert state.clicks[2:] == reopened


def test_interrupted_stash_move_only_forgets_its_two_slots(monkeypatch, world):
    """暂存这一步被打断（如商店自动弹出）时，最多只有两端的卡变了：只作废这两格的姓名，其余卡位不整盘重认。"""
    stage = "2-4"
    source, spare = slot("front", 0, CORE), slot("bench", 1)
    frame = page(Page.BOARD, stage=stage, capacity=(1, 4))
    for key in (("front", 0), ("front", 1), ("back", 0), ("bench", 1), ("bench", 2)):
        world.war.slot_cache[key] = task.SlotIdentity(np.zeros((12, 12, 3), np.int16), "角色", False)
    world.war.held_deployment = (source, spare)
    monkeypatch.setattr(world.war, "_stable_preparation", lambda *_: frame)
    monkeypatch.setattr(world.war, "_read_board", lambda f: (f, None))
    error = task.CurrencyWarsActionUnready("暂存角色的布阵计划需要重读")
    assert world.war._recover_deployment(board(source, spare, stage=stage), error) is frame
    assert sorted(world.war.slot_cache) == [("back", 0), ("bench", 2), ("front", 1)]


@pytest.mark.parametrize(("operation", "kept"), (("武装箱", True), ("晶矿", True), ("商店", True), ("经验", True),
                                                 ("备战腾位", True), ("拆装", True), ("部署", False)))
def test_preparation_recovery_keeps_confirmed_names_unless_cards_may_have_moved(monkeypatch, world, operation, kept):
    frame = page(Page.BOARD, stage="2-3", capacity=(1, 4))
    world.war.slot_cache[("front", 0)] = task.SlotIdentity(np.zeros((12, 12, 3), np.int16), "花火", False)
    monkeypatch.setattr(world.war, "_stable_preparation", lambda *_: frame)
    assert world.war._recover_preparation("2-3", operation, task.CurrencyWarsReceiptTimeout("回执未确认")) is frame
    assert bool(world.war.slot_cache) is kept


def test_play_step_recovery_keeps_confirmed_names(monkeypatch, world):
    before = page(Page.HALO, stage="1-6")
    world.war.slot_cache[("bench", 2)] = task.SlotIdentity(np.zeros((12, 12, 3), np.int16), None, False)
    world.war.deployment_moves = ((slot("bench", 0, CORE), slot("front", 0)),)
    state = drive(monkeypatch, world, page(Page.BOARD, stage="1-6"))
    assert world.war._recover_play_step(before, task.CurrencyWarsActionUnready("光环点选后未转场")) is state.frame
    assert ("bench", 2) in world.war.slot_cache and world.war.deployment_moves == ()


def test_halo_identity_recheck_only_forgets_front_names(monkeypatch, world):
    target = slot("front", 0, CORE)
    world.war.halo_candidate = halo_selection(target)
    for key in (("front", 0), ("front", 1), ("back", 0), ("bench", 2)):
        world.war.slot_cache[key] = task.SlotIdentity(np.zeros((12, 12, 3), np.int16), "角色", False)
    halo = page(Page.HALO, stage="2-7")
    returned = page(Page.BOARD, stage="2-7")
    monkeypatch.setattr(world.war, "_return_halo_board", lambda _: returned)
    assert world.war._recover_halo_identity(halo, (0.5,), "身份未确认") is returned
    assert sorted(world.war.slot_cache) == [("back", 0), ("bench", 2)]


def stock(frame, *items, worn=None):
    """给棋盘帧的物品栏画出按名称区分的图标，并设置卡面装备数。不在图鉴里的物品（如羁绊徽章）按名称识别为 None。
    超过六件的物品和游戏一样依次排到左侧扩列。"""
    points = tuple((ui.INVENTORY_COLUMNS[index // 6], 248 + 77 * (index % 6)) for index in range(len(items)))
    image = np.array(frame.image)
    for (x, y), item in zip(points, items):
        image[y - 24:y + 24, x - 24:x + 24] = np.random.default_rng(zlib.crc32(item.encode())).integers(30, 226, (48, 48, 3))
    frame.image = Image.fromarray(image)
    frame.inventory_items = lambda: points[:6]
    frame.spare_inventory_items = lambda: points[6:]
    frame.inventory_equipment = lambda: tuple(zip(points[:6], (item if item in ui.ITEMS else None for item in items)))
    frame.card_equipment = lambda s: (worn or {}).get(s.point, 0)
    frame.slot_occupied = lambda point: True
    return frame


def test_anaxa_equipment_reopens_only_after_new_materials_arrive(monkeypatch, world):
    stage = "2-5"
    core, support, full = slot("front", 0, CORE), slot("back", 0, CER), slot("front", 1, FILLER)
    team = board(core, support, full, stage=stage, used=3, capacity=3, lineup=policy.LINEUPS[policy.HIGH_ANAXA])
    menu = page(Page.EQUIPMENT, stage=stage)
    screens = []
    opened = []

    def screen(*items):
        frame = stock(page(Page.BOARD, stage=stage, capacity=(3, 3)), *items, worn={full.point: 3})
        screens.append(frame)
        return frame

    def open_equipment(frame, s):
        opened.append(s.unit.name)
        return menu

    monkeypatch.setattr(world.war, "_open_equipment", open_equipment)
    state = drive(monkeypatch, world, menu, lambda s, _: setattr(s, "frame", screens[-1]))
    debug = Mock()
    monkeypatch.setattr(task.log, "debug", debug)

    for items, expected in (
            (("折叠小刀", "生命之花"), ["那刻夏", "刻律德菈"]),
            (("折叠小刀", "生命之花"), []),
            (("折叠小刀",), []),
            (("折叠小刀", "生命之花", "和平手枪"), ["那刻夏", "刻律德菈"]),
    ):
        opened.clear()
        current = screen(*items)
        state.frame = current
        assert world.war._equip_board(current, team) is current
        assert opened == expected
    skips = [call.args[0] for call in debug.call_args_list if "配装跳过" in call.args[0]]
    assert skips[0] == "货币战争 标准博弈 2-5 配装跳过：瓦尔特（装备已满）"
    assert "那刻夏（物品栏没有新增装备）" in skips[1] and "刻律德菈（物品栏没有新增装备）" in skips[1]


def test_high_equipment_rescan_skips_teammates_already_without_options(monkeypatch, world, high_lineup):
    stage = "2-4"
    core, healer = slot("front", 0, CORE), slot("back", 0, BAILU)
    team = board(core, healer, stage=stage, used=2, lineup=high_lineup)
    fight, recommend, action = (1818, 750), (1512, 818), (1170, 720)
    ready = stock(page(Page.BOARD, ("出战", *fight), stage=stage), "生命之花", "轮滑鞋", "量产型装甲")
    # 合成用掉一件材料。剩余两件时仍会继续扫描，只剩一件简易材料会留给后续奖励。
    rescanning = stock(page(Page.BOARD, ("出战", *fight), stage=stage), "生命之花", "量产型装甲",
                       worn={core.point: 1})
    for frame in (ready, rescanning):
        frame.slot_occupied = lambda point: point in (core.point, healer.point)
    core_detail = page(Page.DETAIL, ("那刻夏", 1538, 230), ("推荐", *recommend), stage=stage)
    healer_detail = page(Page.DETAIL, ("白露", 1538, 230), ("推荐", *recommend), stage=stage)
    core_menu = page(Page.EQUIPMENT, ("那刻夏", 1538, 230), ("合成", *action), stage=stage)
    healer_menu = page(Page.EQUIPMENT, ("白露", 1538, 230), stage=stage)
    equipped = page(Page.EQUIPMENT, ("那刻夏", 1538, 230), stage=stage)
    core_detail_again = page(Page.DETAIL, ("那刻夏", 1538, 230), ("推荐", *recommend), stage=stage)
    no_options = page(Page.EQUIPMENT, ("那刻夏", 1538, 230), stage=stage)
    battle_page = page(Page.BATTLE)
    equipped.equipment_changed = lambda before: before is core_menu
    routes = {
        (ready, core.point): core_detail, (core_detail, recommend): core_menu, (core_menu, (12, 12)): ready,
        (ready, healer.point): healer_detail, (healer_detail, recommend): healer_menu,
        (healer_menu, (12, 12)): ready, (core_menu, action): equipped, (equipped, (12, 12)): rescanning,
        (rescanning, core.point): core_detail_again, (core_detail_again, recommend): no_options,
        (no_options, (12, 12)): rescanning, (rescanning, fight): battle_page,
    }
    state = drive(monkeypatch, world, ready, lambda s, p: setattr(s, "frame", routes[s.frame, p]))

    assert world.war._finish_preparation(ready, team) is battle_page
    assert state.clicks == [
        (Page.BOARD, core.point), (Page.DETAIL, recommend), (Page.EQUIPMENT, (12, 12)),
        (Page.BOARD, healer.point), (Page.DETAIL, recommend), (Page.EQUIPMENT, (12, 12)),
        (Page.BOARD, core.point), (Page.DETAIL, recommend), (Page.EQUIPMENT, action), (Page.EQUIPMENT, (12, 12)),
        (Page.BOARD, core.point), (Page.DETAIL, recommend), (Page.EQUIPMENT, (12, 12)),
        (Page.BOARD, fight),
    ]


def unwanted_shop(stage, *, gold, empty=(2, 3, 4)):
    offers = (policy.Offer("罗刹", 3, (473, 194), 0, False, True), policy.Offer("桂乃芬", 2, (742, 194), 1, True, True))
    shop = page(Page.SHOP, ("收起", 1623, 982), stage=stage, gold=gold, offers=offers, shop_refresh_price=2)
    shop.shop_slot_empty = lambda column: column in empty
    return shop


def preparation_board(stage, gold, *, bench=True):
    return board(slot("front", 0, CORE), slot("back", 0, CER), *((slot("bench", 0),) if bench else ()),
                 stage=stage, used=2, capacity=2, level=4, gold=gold, exp=(0, 20))


@pytest.mark.parametrize(("second_gold", "empty", "reopened"), (
    (10, (2, 3, 4), False),
    (10, (2, 3), True),
    (1, (2, 3, 4), False),
))
def test_prepare_does_not_reopen_a_fully_read_shop_that_would_not_act(monkeypatch, world, second_gold, empty,
                                                                       reopened):
    stage = "2-5"
    frame = page(Page.BOARD, ("出战", 1818, 750), stage=stage, gold=10, experience_cost=4)
    teams = iter((preparation_board(stage, 10), preparation_board(stage, second_gold)))
    current = [None]
    opened = []
    monkeypatch.setattr(world.war, "_settle_board", lambda f: f)
    monkeypatch.setattr(world.war, "_collect_preparation_rewards", lambda f: (f, True))

    def read(f):
        return f, current[0]

    def open_shop(f):
        opened.append(current[0].gold)
        return unwanted_shop(stage, gold=current[0].gold, empty=empty)

    monkeypatch.setattr(world.war, "_read_board", read)
    monkeypatch.setattr(world.war, "_open_shop", open_shop)
    monkeypatch.setattr(world.war, "_settle_shop", lambda f: f)
    monkeypatch.setattr(world.war, "_close_shop", lambda f: frame)
    monkeypatch.setattr(world.war, "_finish_preparation", lambda f, b: f)
    for _ in range(2):
        current[0] = next(teams)
        assert world.war._prepare(frame) is frame
    assert opened == ([10, second_gold] if reopened else [10])


def test_shop_catalog_after_a_purchase_decides_whether_to_reopen(world):
    stage = "1-5"
    sparkle = policy.Offer("花火", 2, (742, 194), 1, True, True)
    rest = policy.Offer("黑天鹅", 3, (473, 194), 0, False, True)
    shop = page(Page.SHOP, stage=stage, shop_refresh_price=2)
    shop.shop_slot_empty = lambda column: column > 1
    after = board(slot("front", 0, CORE), slot("back", 0, CER), slot("bench", 0, replace(FILLER, name="花火")),
                  slot("bench", 1), stage=stage, used=2, capacity=3, level=4, gold=8, exp=(0, 20), lineup=policy.LINEUPS[policy.HIGH_ANAXA])

    world.war._remember_catalog(shop, stage, (rest, sparkle), 0, sold=sparkle)
    assert world.war.shop_catalog.offers == (rest,)
    assert not world.war._shop_needs_visit(after, 0, 4)
    assert world.war._shop_needs_visit(after, 1, 4)
    assert world.war._shop_needs_visit(replace(after, stage="1-6"), 0, 4)
    world.war._remember_catalog(shop, stage, (rest, sparkle), 0)
    assert world.war._shop_needs_visit(replace(after, slots=after.slots[:2] + (slot("bench", 0), slot("bench", 1))),
                                       0, 4)


@pytest.mark.parametrize("fault", ("none", "box_receipt", "card_replaced"))
def test_node_preparation_reads_each_card_once_across_the_halo_return(monkeypatch, world, fault):
    """复现 2-5：认人、收起商店、光环返回后第二遍备战。只有真正换过的卡才重开详情。"""
    stage, fight = "2-5", (1818, 750)
    flower, core = slot("front", 0, occupied=True), slot("front", 1, occupied=True)
    trailblazer, spare = slot("bench", 2, occupied=True), slot("bench", 3)
    layout = (flower, core, trailblazer, spare)
    seeds = {flower.point: 11, core.point: 12, trailblazer.point: 7}

    def screen(*overlay, replaced=False):
        cards = [(point, 8 if replaced and point == trailblazer.point else seed) for point, seed in seeds.items()]
        return board_screen(portraits(*cards, *overlay), layout, ("出战", *fight), stage=stage, experience_cost=4)

    clean = screen()
    # 收起商店的首帧：商品卡从前台卡位上滑过。
    covered = screen(((flower.point[0], flower.point[1] - 8), 99), ((core.point[0], core.point[1] - 8), 98))
    renewed = screen(replaced=True)
    details = {flower.point: employee("花火"), core.point: employee("那刻夏"), trailblazer.point: employee("星", "前后台")}
    details[trailblazer.point].employee_name = lambda **_: None
    battle_page = page(Page.BATTLE)
    shop = unwanted_shop(stage, gold=10)
    boards = [clean]
    opened_shop = []

    def click(state, point):
        if state.frame.page == Page.BOARD and point in details:
            state.frame = details[point]
        elif state.frame.page == Page.DETAIL:
            state.frame = boards[-1]
        elif point == fight:
            state.frame = battle_page
        else:
            raise AssertionError((state.frame.page, point))

    def open_shop(f):
        opened_shop.append(f.stage)
        state.frame = shop
        return shop

    def close_shop(f):
        state.frame = boards[-1]
        return covered

    state = drive(monkeypatch, world, clean, click)
    monkeypatch.setattr(world.war, "_gather", lambda f: f)
    monkeypatch.setattr(world.war, "_open_shop", open_shop)
    monkeypatch.setattr(world.war, "_settle_shop", lambda f: f)
    monkeypatch.setattr(world.war, "_close_shop", close_shop)
    assert world.war._prepare(clean) is battle_page
    first_pass = [(Page.BOARD, flower.point), (Page.DETAIL, (12, 12)), (Page.BOARD, core.point),
                  (Page.DETAIL, (12, 12)), (Page.BOARD, trailblazer.point), (Page.DETAIL, (12, 12)),
                  (Page.BOARD, fight)]
    assert state.clicks == first_pass and opened_shop == [stage]

    second = renewed if fault == "card_replaced" else clean
    boards.append(second)
    state.frame = second
    if fault == "box_receipt":
        boxes = iter((ui.Label("开启", (1188, 952)),))
        monkeypatch.setattr(world.war, "_box_button", lambda f: next(boxes, None))

        def failed_box(f, box):
            raise task.CurrencyWarsReceiptTimeout("武装箱开启后未确认奖励界面")

        monkeypatch.setattr(world.war, "_open_box", failed_box)
    assert world.war._prepare(second) is battle_page
    reread = [(Page.BOARD, trailblazer.point), (Page.DETAIL, (12, 12))] if fault == "card_replaced" else []
    assert state.clicks[len(first_pass):] == [*reread, (Page.BOARD, fight)]
    assert opened_shop == [stage]


@pytest.mark.parametrize(("entry", "fault"), (
    ("single", "none"), ("loop", "none"), ("takeover", "none"), ("daily", "none"),
    ("takeover", "step_failure"), ("loop", "step_failure"), ("takeover", "budget"), ("takeover", "stopped"),
))
def test_anaxa_node_reads_each_card_once_through_the_task_entry(monkeypatch, world, entry, fault):
    """从任务入口跑完一个节点：认人、商店收起、提示弹层返回后的第二遍备战，再到整局结算。"""
    stage, fight, settlement, tip = "2-5", (1818, 750), (960, 899), (125, 170)
    # 那刻夏已在前台首位，不需要先调位。
    core, flower = slot("front", 0, occupied=True), slot("front", 1, occupied=True)
    trailblazer, spare = slot("bench", 2, occupied=True), slot("bench", 3)
    layout = (core, flower, trailblazer, spare)
    cards = ((core.point, 12), (flower.point, 11), (trailblazer.point, 7))
    clean = board_screen(portraits(*cards), layout, ("出战", *fight), stage=stage, experience_cost=4)
    covered = board_screen(portraits(*cards, ((flower.point[0], flower.point[1] - 8), 99)), layout,
                           ("出战", *fight), stage=stage, experience_cost=4)
    details = {flower.point: employee("花火"), core.point: employee("那刻夏"), trailblazer.point: employee("星", "前后台")}
    details[trailblazer.point].employee_name = lambda **_: None
    notice = page(Page.HALO_TIP, stage=stage)
    won = page(Page.MATCH_RESULT, ("对局胜利", 960, 233), ("返回货币战争", *settlement))
    lobby, modes = home(), mode(("进入超频博弈", 1638, 960))
    rank_page = page(Page.RANK, ("开始对局", 1680, 965), rank_mode="overclock", enemy_rank=1)
    routes = {(lobby, (1600, 972)): modes, (modes, (1638, 960)): rank_page, (rank_page, (1680, 965)): clean,
              (notice, tip): clean, (won, settlement): lobby}
    world.cfg.currencywars_type = "overclock"
    world.cfg.currencywars_rank_difficulty = "lowest"
    world.cfg.currencywars_strategy = policy.HIGH_ANAXA
    shop = unwanted_shop(stage, gold=10)
    fights = []
    shops = []

    def click(state, point):
        current = state.frame
        if current.page == Page.BOARD and point in details:
            state.frame = details[point]
        elif current.page == Page.DETAIL:
            state.frame = clean
        elif current.page == Page.BOARD and point == fight:
            fights.append(current.stage)
            state.frame = notice if len(fights) == 1 else won
        else:
            state.frame = routes[current, point]

    def open_shop(f):
        shops.append(f.stage)
        state.frame = shop
        return shop

    def close_shop(f):
        state.frame = clean
        if fault == "budget":
            world.now[0] = world.war.deadline
        elif fault == "stopped":
            task.pause_ctl.checkpoint.side_effect = RunStopRequested
        return covered

    play_step = world.war._play_step
    failures = []

    def flaky_step(frame):
        # 提示弹层第一次处理时抛出局部故障，走通用的现场恢复。
        if fault == "step_failure" and frame.page == Page.HALO_TIP and not failures:
            failures.append(frame.page)
            raise task.CurrencyWarsActionUnready("提示弹层暂未确认")
        return play_step(frame)

    state = drive(monkeypatch, world, clean if entry == "takeover" else lobby, click)
    monkeypatch.setattr(world.war, "_gather", lambda f: f)
    monkeypatch.setattr(world.war, "_open_shop", open_shop)
    monkeypatch.setattr(world.war, "_settle_shop", lambda f: f)
    monkeypatch.setattr(world.war, "_close_shop", close_shop)
    monkeypatch.setattr(world.war, "_play_step", flaky_step)
    monkeypatch.setattr(world.war, "get_reward", lambda f: (f, (18000 if world.war.result else 15000, 18000), False))
    reads = [(Page.BOARD, core.point), (Page.DETAIL, (12, 12)), (Page.BOARD, flower.point),
             (Page.DETAIL, (12, 12)), (Page.BOARD, trailblazer.point), (Page.DETAIL, (12, 12))]

    if fault in ("budget", "stopped"):
        with pytest.raises(task.CurrencyWarsBudgetExceeded if fault == "budget" else RunStopRequested):
            world.war.start(resume=True)
        assert state.clicks == reads and shops == [stage] and not fights
        return
    if entry == "daily":
        from tasks.daily import daily

        monkeypatch.setattr(daily, "CurrencyWars", lambda: world.war)
        assert daily.Daily._run_currency_wars()
    else:
        assert world.war.start(resume=entry == "takeover", loop=entry == "loop")
    board_clicks = [click for click in state.clicks if click[0] in (Page.BOARD, Page.DETAIL)]
    assert board_clicks == [*reads, (Page.BOARD, fight), (Page.BOARD, fight)]
    assert shops == [stage] and fights == [stage, stage]
    assert failures == ([Page.HALO_TIP] if fault == "step_failure" else [])
    assert state.frame is lobby and world.war.result is True and not state.keys


def test_default_board_fallback_neither_checks_nor_writes_real_names(monkeypatch, world):
    """连击那刻夏卡在出战前时会借用默认阵容补前台，默认棋盘按卡位命名，不能与姓名缓存比对或写入缓存。"""
    placeholder = policy.Unit("备战席第 1 格角色", True, True, 1)
    source, target = slot("bench", 0, placeholder), slot("front", 0)
    team = board(source, target, stage="1-1", used=0, capacity=1)
    before = page(Page.BOARD, stage="1-1", capacity=(0, 1))
    after = page(Page.BOARD, stage="1-1", capacity=(1, 1))
    monkeypatch.setattr(before, "slot_occupied", lambda point: point == source.point)
    monkeypatch.setattr(after, "slot_occupied", lambda point: point == target.point)
    monkeypatch.setattr(after, "slot_portrait_matches", lambda *_: True)
    world.war.slot_cache[("bench", 0)] = task.SlotIdentity(np.zeros((12, 12, 3), np.int16), "那刻夏", True)
    world.war.slot_cache[("front", 0)] = task.SlotIdentity(np.zeros((12, 12, 3), np.int16), "花火", False)
    state = drive(monkeypatch, world, before)
    world.auto.drag_mouse.side_effect = lambda *_, **__: setattr(state, "frame", after) or True

    assert world.war._move(before, team, source, target, named=False) is after
    assert world.auto.drag_mouse.call_count == 1
    assert ("bench", 0) not in world.war.slot_cache and ("front", 0) not in world.war.slot_cache


GUINAIFEN = policy.Unit("桂乃芬", True, True, 1)
# 1-1 换人场景：桂乃芬先回备战席，再让刻律德菈上后台第 1 格。
SWAP_SEEDS = {"那刻夏": 31, "桂乃芬": 32, "长夜月": 33, "刻律德菈": 34}
SWAP_ROLES = {31: (True, False), 32: (True, True), 33: (True, True), 34: (False, True)}


def swap_screen(cards, *, capacity=None, fight=(1818, 750), stage="1-1"):
    """cards 为 (卡位, 角色名[, 亮度偏移])。卡位按 slot() 的几何，占用、站位和人口按给定卡片返回。"""
    places = (("front", 0), ("front", 1), ("front", 2), ("back", 0), ("back", 1), ("bench", 0), ("bench", 1))
    taken = {(zone, index): (name, *shift) for (zone, index), name, *shift in cards}
    layout = tuple(slot(zone, index, occupied=(zone, index) in taken) for zone, index in places)
    seeds = {s.point: SWAP_SEEDS[taken[s.zone, s.index][0]] for s in layout if s.occupied}
    image = portraits(*((s.point, seeds[s.point], *taken[s.zone, s.index][1:]) for s in layout if s.occupied))
    frame = board_screen(image, layout, ("出战", *fight), stage=stage, gold=0, experience_cost=4)
    if capacity is not None:
        frame.capacity = capacity
    frame.card_role = lambda s: SWAP_ROLES[seeds[s.point]]
    return frame


def test_move_keeps_a_known_card_whose_portrait_only_brightened(monkeypatch, world):
    """拖动前的核对与读盘一致：卡面抬起或变亮只改变缩略图，仍按已认出的角色移动。"""
    source, destination = slot("front", 1, GUINAIFEN), slot("bench", 1)
    team = board(slot("front", 0, CORE), source, slot("bench", 0, CER), destination, stage="1-1", used=2, capacity=2)
    normal = swap_screen(((("front", 0), "那刻夏"), (("front", 1), "桂乃芬"), (("bench", 0), "刻律德菈")),
                         capacity=(2, 2))
    lifted = swap_screen(((("front", 0), "那刻夏"), (("front", 1), "桂乃芬", 30), (("bench", 0), "刻律德菈")),
                         capacity=(2, 2))
    moved = swap_screen(((("front", 0), "那刻夏"), (("bench", 0), "刻律德菈"), (("bench", 1), "桂乃芬")),
                        capacity=(1, 2))
    mark = normal.slot_mark(source.point)
    world.war.slot_cache[("front", 1)] = task.SlotIdentity(
        task.cv2.resize(mark, (12, 12)).astype(np.int16), "桂乃芬", False, mark.copy())
    assert world.war._cached_identity(lifted, source) is not None
    state = drive(monkeypatch, world, lifted)
    world.auto.drag_mouse.side_effect = lambda *_, **__: setattr(state, "frame", moved) or True

    assert world.war._move(lifted, team, source, destination) is moved
    assert world.auto.drag_mouse.call_count == 1
    world.auto.park_mouse.assert_called_once_with((12 / 1920, 12 / 1080))
    assert world.war.slot_cache[("bench", 1)].name == "桂乃芬" and ("front", 1) not in world.war.slot_cache


def test_confirmed_move_names_the_destination_even_when_the_card_size_changes(monkeypatch, world):
    """备战席和场上的卡面大小不同。原位已空、目标格新占用时，落下的就是拖动的那张卡，不必回头重读详情。"""
    source, destination = slot("bench", 0, CER), slot("back", 0)
    team = board(slot("front", 0, CORE), source, destination, stage="1-1", used=1, capacity=2)
    before = swap_screen(((("front", 0), "那刻夏"), (("bench", 0), "刻律德菈")), capacity=(1, 2))
    # 上场后的卡面与备战席的肖像对不上（另一组纹理和亮度）。
    after = swap_screen(((("front", 0), "那刻夏"), (("back", 0), "长夜月", 60)), capacity=(2, 2))
    state = drive(monkeypatch, world, before)
    world.auto.drag_mouse.side_effect = lambda *_, **__: setattr(state, "frame", after) or True

    assert world.war._move(before, team, source, destination) is after
    assert world.war.slot_cache[("back", 0)].name == "刻律德菈"


@pytest.mark.parametrize("origin", ("moved", "read", "earlier_stage"))
def test_card_moved_this_node_takes_its_settled_portrait_instead_of_a_reread(monkeypatch, world, origin):
    """复现 new4 1-2：花火拖到前台后，回执那帧还在落位动画中，记下的卡面之后对不上。本节点拖动过的这一格稳定后
    沿用拖动时确认的姓名并更新卡面，不重开详情；读详情得来或上一节点拖动的记录对不上时仍照常重读。"""
    stage, target = "1-2", slot("front", 1)
    landing = swap_screen(((("front", 0), "那刻夏"), (("front", 1), "长夜月")), capacity=(2, 2), stage=stage)
    rested = swap_screen(((("front", 0), "那刻夏"), (("front", 1), "桂乃芬")), capacity=(2, 2), stage=stage)
    mark = landing.slot_mark(target.point)
    entry = task.SlotIdentity(task.cv2.resize(mark, (12, 12)).astype(np.int16), "桂乃芬", False, mark.copy())
    world.war.slot_cache[("front", 1)] = entry
    if origin != "read":
        world.war.moved_identities[("front", 1)] = ("1-1" if origin == "earlier_stage" else stage), entry
    drive(monkeypatch, world, rested)
    assert world.war._cached_identity(rested, target) is None

    frame, _ = world.war._settle_identities(rested, rested.slots())

    assert frame is rested
    refreshed = world.war._cached_identity(rested, target)
    if origin == "moved":
        assert refreshed is not None and refreshed.name == "桂乃芬"
        assert ("front", 1) not in world.war.moved_identities
    else:
        assert refreshed is None


def test_confirmed_move_is_marked_for_a_settled_portrait_refresh(monkeypatch, world):
    """拖动确认后记下的卡位同时登记为本节点刚挪入，供之后卡面稳定时更新。"""
    source, destination = slot("bench", 0, CER), slot("back", 0)
    team = board(slot("front", 0, CORE), source, destination, stage="1-1", used=1, capacity=2)
    before = swap_screen(((("front", 0), "那刻夏"), (("bench", 0), "刻律德菈")), capacity=(1, 2))
    after = swap_screen(((("front", 0), "那刻夏"), (("back", 0), "刻律德菈")), capacity=(2, 2))
    state = drive(monkeypatch, world, before)
    world.auto.drag_mouse.side_effect = lambda *_, **__: setattr(state, "frame", after) or True

    assert world.war._move(before, team, source, destination) is after
    stage, entry = world.war.moved_identities[("back", 0)]
    assert stage == "1-1" and entry is world.war.slot_cache[("back", 0)]
    world.war._reset_match_state()
    assert not world.war.moved_identities


def test_card_dragged_again_in_the_same_node_waits_for_its_landing_to_finish(monkeypatch, world):
    """复现 2026-11-21 五次「部署暂缓：角色移动未确认（……已尝试 0 次）」：刚拖入一格的卡接着又要挪，读盘那帧卡面
    还在落位动画中，取作拖动基准后每帧都对不上，等满时限也没拖。先等这张卡的卡面稳定再取基准，照常拖动。"""
    stage = "1-3"
    source, destination = slot("front", 1, GUINAIFEN), slot("bench", 1)
    team = board(slot("front", 0, CORE), source, slot("bench", 0, CER), destination, stage=stage, used=2, capacity=2)
    cards = ((("front", 0), "那刻夏"), (("bench", 0), "刻律德菈"))
    landing = swap_screen((*cards, (("front", 1), "桂乃芬", 60)), capacity=(2, 2), stage=stage)
    rested = swap_screen((*cards, (("front", 1), "桂乃芬")), capacity=(2, 2), stage=stage)
    moved = swap_screen((*cards, (("bench", 1), "桂乃芬")), capacity=(1, 2), stage=stage)
    mark = landing.slot_mark(source.point)
    entry = task.SlotIdentity(task.cv2.resize(mark, (12, 12)).astype(np.int16), "桂乃芬", False, mark.copy())
    world.war.slot_cache[("front", 1)] = entry
    world.war.moved_identities[("front", 1)] = stage, entry

    def settle(state):
        if state.frame is landing:
            state.frame = rested

    state = drive(monkeypatch, world, landing, after_capture=settle)
    world.auto.drag_mouse.side_effect = lambda *_, **__: setattr(state, "frame", moved) or True

    assert world.war._move(landing, team, source, destination) is moved
    assert world.auto.drag_mouse.call_count == 1
    assert world.war.slot_cache[("bench", 1)].name == "桂乃芬"


@pytest.mark.parametrize("delivered", (True, False))
def test_drag_parks_the_pointer_only_after_a_delivered_drag(monkeypatch, world, delivered):
    frame = page(Page.BOARD, stage="1-1")
    drive(monkeypatch, world, frame)
    world.auto.drag_mouse.return_value = delivered
    assert world.war._drag(frame, (735, 910), (735, 405)) is delivered
    world.auto.drag_mouse.assert_called_once_with((735 / 1920, 910 / 1080), (735 / 1920, 405 / 1080),
                                                  duration=0.5, end_pause=0.10, take_screenshot=False)
    assert world.auto.park_mouse.call_count == int(delivered)


def test_preparation_parks_the_pointer_once_per_node_before_reading_the_board(monkeypatch, world):
    """节点结算、节点说明的按钮落在备战席卡片上。每个节点第一次备战前把指针移到左上角，等卡片落回再读棋盘。"""
    rest = (12 / 1920, 12 / 1080)
    events = []
    drive(monkeypatch, world, page(Page.BOARD, stage="1-5"))
    world.auto.park_mouse.side_effect = lambda point: events.append(("移开指针", point, world.now[0])) or True

    def settle(frame):
        events.append(("读棋盘", frame.stage, world.now[0]))
        return page(Page.SHOP, stage=frame.stage)

    monkeypatch.setattr(world.war, "_settle_board", settle)
    for stage in ("1-5", "1-5", "1-6"):
        world.war._prepare(page(Page.BOARD, stage=stage))
    world.war._reset_match_state()
    world.war._prepare(page(Page.BOARD, stage="1-6"))

    assert [event[:2] for event in events] == [
        ("移开指针", rest), ("读棋盘", "1-5"), ("读棋盘", "1-5"),
        ("移开指针", rest), ("读棋盘", "1-6"), ("移开指针", rest), ("读棋盘", "1-6"),
    ]
    assert events[1][2] - events[0][2] == pytest.approx(task.POINTER_SETTLE_SECONDS)


@pytest.mark.parametrize("failure", ("window", "stopped"))
def test_pointer_parking_failure_keeps_preparing_but_a_stop_request_ends_it(monkeypatch, world, failure):
    frame, settled = page(Page.BOARD, stage="2-1"), page(Page.SHOP, stage="2-1")
    drive(monkeypatch, world, frame)
    world.auto.park_mouse.side_effect = (RuntimeError("无法获取游戏窗口尺寸") if failure == "window"
                                         else RunStopRequested())
    monkeypatch.setattr(world.war, "_settle_board", lambda f: settled)
    if failure == "stopped":
        with pytest.raises(RunStopRequested):
            world.war._prepare(frame)
    else:
        assert world.war._prepare(frame) is settled
    assert world.war.pointer_parked_stage == "2-1"


def test_unsent_held_move_keeps_confirmed_names_and_replans_once(monkeypatch, world):
    """暂存这一步还没拖动就失败时角色仍在原位：只作废对不上的那格，本节点保留一次重新规划。"""
    stage = "1-1"
    frame = page(Page.BOARD, ("出战", 1818, 750), stage=stage, gold=0, capacity=(2, 2))
    team = board(slot("front", 0, CORE), slot("front", 1, GUINAIFEN), slot("back", 0), slot("bench", 0, CER),
                 slot("bench", 1), stage=stage, used=2, capacity=2, gold=0, lineup=policy.LINEUPS[policy.HIGH_ANAXA])
    benched = board(slot("front", 0, CORE), slot("front", 1), slot("back", 0), slot("bench", 0, CER),
                    slot("bench", 1, GUINAIFEN), stage=stage, used=1, capacity=2, gold=0, lineup=policy.LINEUPS[policy.HIGH_ANAXA])
    deployed = board(slot("front", 0, CORE), slot("front", 1), slot("back", 0, CER), slot("bench", 0),
                     slot("bench", 1, GUINAIFEN), stage=stage, used=2, capacity=2, gold=0, lineup=policy.LINEUPS[policy.HIGH_ANAXA])
    for key in (("front", 0), ("front", 1), ("bench", 0)):
        world.war.slot_cache[key] = task.SlotIdentity(np.zeros((12, 12, 3), np.int16), "那刻夏", False)
    moves = []
    current = [team]

    def move(f, b, source, destination, **_):
        moves.append((source.unit.name, destination.zone))
        if len(moves) == 1:
            world.war.slot_cache.pop((source.zone, source.index), None)
            raise task.CurrencyWarsActionUnready(f"{source.unit.name}移动前待核对的卡位肖像已变化")
        current[0] = benched if source.unit.name == "桂乃芬" else deployed
        return f

    monkeypatch.setattr(world.war, "_settle_board", lambda f: f)
    monkeypatch.setattr(world.war, "_collect_preparation_rewards", lambda f: (f, True))
    monkeypatch.setattr(world.war, "_read_board", lambda f: (f, current[0]))
    monkeypatch.setattr(world.war, "_stable_preparation", lambda *_: frame)
    monkeypatch.setattr(world.war, "_move", move)
    monkeypatch.setattr(world.war, "_finish_preparation", lambda f, b: f)
    world.war.deployment_history.clear()
    drive(monkeypatch, world, frame)

    assert world.war._prepare(frame) is frame
    assert moves[:3] == [("桂乃芬", "bench"), ("桂乃芬", "bench"), ("刻律德菈", "back")]
    assert set(world.war.slot_cache) == {("front", 0), ("bench", 0)}
    assert world.war.deployment_replan_stage == stage


def test_level_up_replans_a_deferred_deployment(monkeypatch, world):
    """部署暂缓后买经验升到更高人口，备战席上的角色按新棋盘补上。"""
    stage = "1-1"
    frame = page(Page.BOARD, ("购买经验", 297, 862), ("出战", 1818, 750), stage=stage, gold=4, experience_cost=4,
                 capacity=(3, 3))
    upgraded = page(Page.BOARD, ("购买经验", 297, 862), ("出战", 1818, 750), stage=stage, gold=0,
                    experience_cost=4, capacity=(3, 4), experience=(0, 6))
    full = board(slot("front", 0, CORE), slot("front", 1), slot("back", 0, CER), slot("back", 1, EVERNIGHT),
                 slot("bench", 1, GUINAIFEN), stage=stage, used=3, capacity=3, level=3, gold=4, exp=(0, 4))
    room = replace(full, capacity=4, level=4, gold=0, exp=(0, 6))
    boards = {frame: full, upgraded: room}
    moves = []
    world.war.deferred_operations.add((stage, "部署"))
    monkeypatch.setattr(world.war, "_settle_board", lambda f: f)
    monkeypatch.setattr(world.war, "_collect_preparation_rewards", lambda f: (f, True))
    monkeypatch.setattr(world.war, "_read_board", lambda f: (f, boards[f]))
    monkeypatch.setattr(world.war, "_can_buy_exp", lambda b, price: b is full)
    monkeypatch.setattr(world.war, "_buy_exp", lambda f, b, price: upgraded)
    monkeypatch.setattr(world.war, "_move", lambda f, b, source, destination, **_: moves.append(
        (source.unit.name, destination.zone, destination.index)) or f)
    monkeypatch.setattr(world.war, "_finish_preparation", lambda f, b: f)
    drive(monkeypatch, world, frame)

    world.war._prepare(frame)
    assert moves and moves[0] == ("桂乃芬", "front", 1)
    assert (stage, "部署") not in world.war.deferred_operations


@pytest.mark.parametrize(("core_worn", "hp", "final_node", "expected", "reason"), (
    (2, 100, None, ["刻律德菈", "那刻夏"], "那刻夏未配满"),
    (3, 100, None, ["刻律德菈"], "留到最终节点或生命值低于 80 再配"),
    # 难度 89 开局生命值就是 80，掉到 80 以下才给其余角色配装。
    (3, 80, None, ["刻律德菈"], "留到最终节点或生命值低于 80 再配"),
    (3, 79, None, ["刻律德菈", "瓦尔特"], None),
    (3, 100, "2-5", ["刻律德菈", "瓦尔特"], None),
    # 那刻夏的推荐页可能整局配不上第三件，生命值偏低或到了最终节点就不再等她穿满。
    (2, 79, None, ["刻律德菈", "瓦尔特", "那刻夏"], None),
    (2, 100, "2-5", ["刻律德菈", "瓦尔特", "那刻夏"], None),
))
def test_anaxa_equipment_holds_other_units_until_the_final_node_or_low_hp(monkeypatch, world, core_worn, hp,
                                                                          final_node, expected, reason):
    """平时只给攻略的配装优先角色（那刻夏、昔涟、刻律德菈）配装，其余上阵角色留到最终节点或小队生命值低于 80 时再配：
    物品栏每变一次就要重开全队推荐页，多数一无所获。复现 2026-11-21 难度 89：那刻夏从 1-9 起停在两件，其余角色整局
    写「那刻夏未配满」，生命值从 1-5 起就低于 80，最终节点只剩 3 时物品栏还有十一件没用。"""
    stage = "2-5"
    core, support, other = slot("front", 0, CORE), slot("back", 0, CER), slot("front", 1, FILLER)
    team = board(core, support, other, stage=stage, used=3, capacity=3, hp=hp, final_node=final_node)
    frame = stock(page(Page.BOARD, stage=stage, capacity=(3, 3)), "轮滑鞋", "生命之花", worn={core.point: core_worn})
    frame.slot_occupied = lambda point: True
    opened = []
    menu = page(Page.EQUIPMENT, stage=stage)
    monkeypatch.setattr(world.war, "_open_equipment", lambda f, s: opened.append(s.unit.name) or menu)
    monkeypatch.setattr(world.war, "_return_from_equipment", lambda f: frame)
    drive(monkeypatch, world, frame)
    debug = Mock()
    monkeypatch.setattr(task.log, "debug", debug)
    assert policy.EQUIPMENT_FOCUS[policy.HIGH_ANAXA] == {"那刻夏", "昔涟", "刻律德菈"}
    world.war.equipment_focus = policy.EQUIPMENT_FOCUS[policy.HIGH_ANAXA]
    world.war.lineup = policy.LINEUPS[policy.HIGH_ANAXA]

    world.war._equip_board(frame, replace(team, lineup=world.war.lineup))
    assert sorted(opened) == expected
    skips = " ".join(call.args[0] for call in debug.call_args_list if "配装跳过" in call.args[0])
    assert ("瓦尔特（" in skips) is (reason is not None)
    assert reason is None or f"瓦尔特（{reason}）" in skips


def test_anaxa_equipment_moves_on_to_other_units_once_the_core_fills_up(monkeypatch, world):
    """小队生命值低于 80 时，同一遍配装里先配那刻夏，后面的角色接着配，不必等下一节点。"""
    stage = "2-5"
    core, other = slot("front", 0, CORE), slot("front", 1, FILLER)
    team = board(core, other, stage=stage, used=2, capacity=2, hp=79, lineup=policy.LINEUPS[policy.HIGH_ANAXA])
    before = stock(page(Page.BOARD, stage=stage, capacity=(2, 2)), "轮滑鞋", "生命之花", worn={core.point: 2})
    filled = stock(page(Page.BOARD, stage=stage, capacity=(2, 2)), "生命之花", worn={core.point: 3})
    opened = []
    menu = page(Page.EQUIPMENT, stage=stage)
    monkeypatch.setattr(world.war, "_open_equipment", lambda f, s: opened.append(s.unit.name) or menu)
    monkeypatch.setattr(world.war, "_return_from_equipment", lambda f: filled)
    drive(monkeypatch, world, before)
    world.war.equipment_focus = policy.EQUIPMENT_FOCUS[policy.HIGH_ANAXA]

    assert world.war._equip_board(before, team) is filled
    assert opened == ["那刻夏", "瓦尔特"]


def test_equipment_memo_compares_unrecognized_items_by_image(monkeypatch, world):
    """羁绊徽章等认不出名字的物品不影响记录：物品栏只少不多时不再打开推荐页，新增物品后才重新检查。"""
    stage = "2-5"
    core = slot("front", 0, CORE)
    team = board(core, stage=stage, used=1, capacity=1, lineup=policy.LINEUPS[policy.HIGH_ANAXA])
    menu = page(Page.EQUIPMENT, stage=stage)
    screens, opened = [], []
    monkeypatch.setattr(world.war, "_open_equipment", lambda f, s: opened.append(s.unit.name) or menu)
    state = drive(monkeypatch, world, menu, lambda s, _: setattr(s, "frame", screens[-1]))

    for items, expected in ((("追击星徽", "生命之花"), 1), (("追击星徽", "生命之花"), 1), (("生命之花",), 1),
                            (("生命之花", "连击星徽"), 2)):
        screens.append(stock(page(Page.BOARD, stage=stage, capacity=(1, 1)), *items))
        state.frame = screens[-1]
        world.war._equip_board(screens[-1], team)
        assert len(opened) == expected


def test_equipment_memo_logs_why_it_reopens_the_menu(monkeypatch, world):
    """记录没沿用时写明原因：卡面件数变化、扩列区域变化，或第几件物品对不上，便于从实机日志定位。"""
    stage = "2-4"
    core = slot("front", 0, CORE)
    team = board(core, stage=stage, used=1, capacity=1, lineup=policy.LINEUPS[policy.HIGH_ANAXA])
    menu = page(Page.EQUIPMENT, stage=stage)
    screens, opened = [], []
    monkeypatch.setattr(world.war, "_open_equipment", lambda f, s: opened.append(s.unit.name) or menu)
    state = drive(monkeypatch, world, menu, lambda s, _: setattr(s, "frame", screens[-1]))
    debug = Mock()
    monkeypatch.setattr(task.log, "debug", debug)

    def equip(*items, worn=0):
        frame = stock(page(Page.BOARD, stage=stage, capacity=(1, 1)), *items, worn={core.point: worn})
        screens.append(frame)
        state.frame = frame
        world.war._equip_board(frame, team)

    equip("生命之花", "追击星徽")
    equip("生命之花", "追击星徽")
    equip("生命之花", "追击星徽", worn=1)
    equip("生命之花", "追击星徽", "以太钻头", worn=1)
    equip("以太钻头", "连击星徽", worn=1)

    rechecks = [call.args[0] for call in debug.call_args_list if "配装记录未沿用" in call.args[0]]
    assert rechecks[:2] == [
        f"{stage}那刻夏的配装记录未沿用：卡面装备从 0 件变为 1 件，重新打开推荐页",
        f"{stage}那刻夏的配装记录未沿用：物品栏第 3 件没有对应（记录里的物品已对完；记录 2 件，现在 3 件），重新打开推荐页",
    ]
    assert len(rechecks) == 3 and re.fullmatch(
        rf"{stage}那刻夏的配装记录未沿用：物品栏第 2 件没有对应（最高相似度 -?0\.\d\d；记录 3 件，现在 2 件），重新打开推荐页",
        rechecks[2])
    assert len(opened) == 4


def test_equipment_memo_follows_items_that_move_out_of_the_expansion_column(monkeypatch, world):
    """复现 new4 1-6：超过六件时第七件排在左侧扩列。别人用掉一件后它挪进右列，没有新物品，不必重开推荐页；扩列真来了新物品才重开。"""
    stage = "1-6"
    core = slot("front", 0, CORE)
    team = board(core, stage=stage, used=1, capacity=1, lineup=policy.LINEUPS[policy.HIGH_ANAXA])
    menu = page(Page.EQUIPMENT, stage=stage)
    screens, opened = [], []
    monkeypatch.setattr(world.war, "_open_equipment", lambda f, s: opened.append(s.unit.name) or menu)
    state = drive(monkeypatch, world, menu, lambda s, _: setattr(s, "frame", screens[-1]))
    debug = Mock()
    monkeypatch.setattr(task.log, "debug", debug)
    seven = ("轮滑鞋", "折叠小刀", "生命之花", "幸运星", "光能电池", "以太钻头", "追击星徽")

    for items, expected in ((seven, 1), (seven[1:], 1), ((*seven[1:], "量产型装甲"), 2)):
        screens.append(stock(page(Page.BOARD, stage=stage, capacity=(1, 1)), *items))
        state.frame = screens[-1]
        world.war._equip_board(screens[-1], team)
        assert len(opened) == expected

    assert screens[0].spare_inventory_items() == ((1766, 248),) and screens[1].spare_inventory_items() == ()
    rechecks = [call.args[0] for call in debug.call_args_list if "配装记录未沿用" in call.args[0]]
    assert len(rechecks) == 1 and "物品栏第 7 件没有对应" in rechecks[0]


def test_orb_blocked_by_a_full_bench_waits_for_a_free_slot_instead_of_another_sweep(monkeypatch, world):
    """复现 new4 2-5：装角色的晶矿在备战席满时开不了。挡下一次后先腾位，腾位这一步没空出格子时不再重扫，
    空出格子后再收它。"""
    stage, orb = "2-5", (1481, 297)

    def screen(orbs, *, bench_free=False, toast=False):
        extra = (("备战席已满，需要售卖备战区角色才可开启晶矿", 960, 300),) if toast else ()
        frame = page(Page.BOARD, *extra, stage=stage, gold=18, capacity=(9, 9))
        frame.reward_orbs = lambda: orbs
        frame.opening_orbs = frame.inventory_items = lambda: ()
        frame.bench_slots = lambda: tuple(policy.Slot("bench", i, ui.BENCH_POINTS[i], not (bench_free and i == 8))
                                          for i in range(9))
        return frame

    full, toast, freed, done = screen((orb,)), screen((orb,), toast=True), screen((orb,), bench_free=True), screen(())
    shown = []

    def toast_fades(state):
        if state.frame is toast:
            if shown:
                state.frame = full
            shown.append(True)

    state = drive(monkeypatch, world, full, after_capture=toast_fades)

    def drag(*_, **__):
        shown.clear()
        state.frame = done if world.war.frame is freed else toast
        return True

    frees = []

    def free(frame, **_):
        frees.append(world.auto.drag_mouse.call_count)
        state.frame = freed if len(frees) >= 2 else full
        return world.war._observe()

    world.auto.drag_mouse.side_effect = drag
    monkeypatch.setattr(world.war, "_free_reward_slot", free)

    assert world.war._gather(full) is done
    assert world.auto.drag_mouse.call_count == 2
    assert frees == [1, 1]
    assert world.war.blocked_orbs[stage] == []


def test_orb_hit_that_drops_a_box_is_confirmed_without_waiting(monkeypatch, world):
    """复现 2026-11-21 第 11 局 1-9：这一下扫出武装箱，奖励区的晶矿还在，金币、物品和角色都没变，等满时限后
    本节点的晶矿记为暂缓。备战席新出现的「开启」也算收集回执，接着再扫，扫空后交回开箱。"""
    stage, orb = "1-9", (1315, 286)

    def screen(orbs, *boxes):
        frame = page(Page.BOARD, *(("开启", x, 952) for x in boxes), stage=stage, gold=16, capacity=(5, 5))
        frame.reward_orbs = lambda: orbs
        frame.opening_orbs = frame.inventory_items = lambda: ()
        return frame

    full, dropped, emptied = screen((orb,)), screen((orb,), 813), screen((), 813, 1063)
    state = drive(monkeypatch, world, full)

    def drag(*_, **__):
        state.frame = dropped if state.frame is full else emptied
        return True

    world.auto.drag_mouse.side_effect = drag
    assert world.war._gather(full) is emptied
    assert world.auto.drag_mouse.call_count == 2
    assert (stage, "晶矿") not in world.war.deferred_operations


def test_spare_inventory_column_is_read_with_the_same_item_frames():
    """物品超过六件时向左扩列。扩列物品与右列一样有贯穿整格的上下边框，空格只有底纹。"""
    def board_with(spare):
        image = CANVAS.copy()
        draw = ImageDraw.Draw(image)
        for x, y in (*((1844, 248 + 77 * row) for row in range(6)), *spare):
            draw.rectangle((x - 34, y - 35, x + 34, y + 35), fill=(150, 140, 190))
        return Frame(image, ())

    main = tuple((1844, 248 + 77 * row) for row in range(6))
    assert board_with(()).inventory_items() == main and board_with(()).spare_inventory_items() == ()
    crowded = board_with(((1766, 248), (1766, 325)))
    assert crowded.inventory_items() == main
    assert crowded.spare_inventory_items() == ((1766, 248), (1766, 325))


def test_shop_reads_a_price_whose_coin_icon_is_read_as_a_question_mark():
    x = 367 + 269 * 3
    frame = page(Page.SHOP, ("飞霄", x + 90, 306), ("?3", x + 225, 306), stage="3-1")
    assert [(offer.name, offer.cost, offer.column) for offer in frame.offers] == [("飞霄", 3, 3)]


@pytest.mark.parametrize(("labels", "expected"), (
    ((("昔涟", 90), ("h", 180), ("4", 225)), ("昔涟", 4)),
    ((("姬子·启行", 90), ("12", 225)), ("姬子·启行", 2)),
    ((("千冶·刃1", 90), ("2", 225)), ("千冶·刃", 2)),
    ((("飞霄Y3", 120),), ("飞霄", 3)),
    ((("刃1", 90), ("3", 225)), ("刃", 3)),
    ((("银狼LV.999", 90), ("3", 225)), ("银狼LV.999", 3)),
))
def test_shop_drops_a_coin_icon_read_as_a_letter_or_digit_after_the_name(labels, expected):
    """复现 2026-11-21 难度 89 第七轮 3-5：报价前的金币图标读成 h 粘在名字后，「昔涟h」对不上阵容，
    这个节点没买关键辅助昔涟，还把她刷掉了。之前几局也有「寒鸦1」「刻律德菈2」「昔涟1」。"""
    x = 367 + 269 * 2
    frame = page(Page.SHOP, *((text, x + dx, 306) for text, dx in labels), stage="3-5")
    assert [(offer.name, offer.cost) for offer in frame.offers] == [expected]


def test_shop_reads_the_zone_squares_at_the_top_right_of_each_card():
    """复现 2026-11-21 第 1 局 2-2：卡面右上角上下两枚方块，实心表示能上前台、后台。旧取样框压在方块右缘和下方的
    「试用」角标上，只能上前台的椒丘读成站位不明，按后台补位买下后随即卖掉；能上前后台的卡也只读出前台。"""
    image = CANVAS.copy()
    draw = ImageDraw.Draw(image)
    cards = (("飞霄", 3, True, False, True), ("赛飞儿", 3, False, True, True), ("景元", 1, True, True, False),
             ("黑天鹅", 1, True, False, False), ("火花", 1, True, True, False))
    entries = []
    for index, (name, cost, front, back, trial) in enumerate(cards):
        x = 367 + 269 * index
        for filled, top in ((front, 76), (back, 94)):
            square = (x + 209, top, x + 222, top + 13)
            if filled:
                draw.rectangle(square, fill=(242, 242, 242))
            else:
                draw.rectangle(square, fill=(18, 18, 22), outline=(168, 168, 168), width=2)
        if trial:
            # 「试用」角标：红底白字，在两枚方块下方。
            draw.rectangle((x + 195, 117, x + 240, 140), fill=(214, 48, 52))
            for left in (x + 200, x + 218):
                draw.rectangle((left, 121, left + 14, 135), outline=(255, 255, 255), width=2)
        entries += [(name, x + 90, 306), (f"?{cost}", x + 225, 306)]
    frame = Frame(image, labels(*entries))
    assert [(offer.name, offer.front, offer.back) for offer in frame.offers] == [
        ("飞霄", True, False), ("赛飞儿", False, True), ("景元", True, True), ("黑天鹅", True, False),
        ("火花", True, True)]


def test_auto_opened_shop_is_remembered_before_closing(monkeypatch, world):
    """奖励节点自动展开的商店先记下稳定的商品，备战时按当前阵容复算，不需要购买就不再打开。"""
    stage = "2-5"
    shop = unwanted_shop(stage, gold=10)
    closed = page(Page.BOARD, stage=stage)
    monkeypatch.setattr(world.war, "_settle_shop", lambda f: f)
    monkeypatch.setattr(world.war, "_close_shop", lambda f: closed)
    drive(monkeypatch, world, shop)

    assert world.war._play_step(shop) is closed
    assert world.war.shop_catalog.stage == stage and [o.name for o in world.war.shop_catalog.offers] == ["罗刹", "桂乃芬"]
    assert not world.war._shop_needs_visit(preparation_board(stage, 10), 0, 4)


@pytest.mark.parametrize(("entry", "fault"), (
    ("single", "none"), ("loop", "none"), ("takeover", "none"), ("daily", "none"),
    ("takeover", "step_failure"), ("loop", "step_failure"), ("takeover", "budget"), ("takeover", "stopped"),
))
def test_anaxa_swap_survives_a_lifted_card_through_the_task_entry(monkeypatch, world, entry, fault):
    """复现 1-1：最后一张详情关闭时前台卡面变亮（指针停留等）。读盘按肖像认出同一张卡，换人计划照常执行，不清空姓名重读、不暂缓部署。"""
    stage, fight, settlement = "1-1", (1818, 750), (960, 899)
    start = ((("front", 0), "那刻夏"), (("front", 1), "桂乃芬"), (("back", 1), "长夜月"), (("bench", 0), "刻律德菈"))
    clean = swap_screen(start)
    lifted = swap_screen((*start[:1], (("front", 1), "桂乃芬", 30), *start[2:]))
    benched = swap_screen(((("front", 0), "那刻夏"), (("back", 1), "长夜月"), (("bench", 0), "刻律德菈"),
                           (("bench", 1), "桂乃芬")), capacity=(2, 3))
    # 攻略要求刻律德菈前期站前台：换下桂乃芬后她补前台空位。
    deployed = swap_screen(((("front", 0), "那刻夏"), (("front", 2), "刻律德菈"), (("back", 1), "长夜月"),
                            (("bench", 1), "桂乃芬")))
    details = {SWAP_SEEDS[name]: employee(name, role, stage)
               for name, role in (("那刻夏", "前台"), ("桂乃芬", "前后台"), ("长夜月", "前后台"), ("刻律德菈", "后台"))}
    won = page(Page.MATCH_RESULT, ("对局胜利", 960, 233), ("返回货币战争", *settlement))
    lobby, modes = home(), mode(("进入超频博弈", 1638, 960))
    rank_page = page(Page.RANK, ("开始对局", 1680, 965), rank_mode="overclock", enemy_rank=1)
    routes = {(lobby, (1600, 972)): modes, (modes, (1638, 960)): rank_page, (rank_page, (1680, 965)): clean,
              (won, settlement): lobby}
    world.cfg.currencywars_type = "overclock"
    world.cfg.currencywars_rank_difficulty = "lowest"
    world.cfg.currencywars_strategy = policy.HIGH_ANAXA
    reads, fights, failures = [], [], []
    boards = [clean]

    def seat(frame, point):
        return next((SWAP_SEEDS[name] for (zone, index), name, *_ in start if slot(zone, index).point == point), None)

    def click(state, point):
        current = state.frame
        if current.page == Page.BOARD and point == fight:
            fights.append(current.stage)
            state.frame = won
        elif current.page == Page.BOARD and current in (clean, lifted) and (seed := seat(current, point)):
            reads.append(point)
            state.frame = details[seed]
        elif current.page == Page.DETAIL:
            if len(reads) == 4 and boards[-1] is clean:
                # 关闭最后一张详情时前台卡面变亮。
                boards.append(lifted)
                if fault == "budget":
                    world.now[0] = world.war.deadline
                elif fault == "stopped":
                    task.pause_ctl.checkpoint.side_effect = RunStopRequested
            state.frame = boards[-1]
        else:
            state.frame = routes[current, point]

    def drag(*_, **__):
        boards.append(benched if boards[-1] is lifted else deployed)
        state.frame = boards[-1]
        return True

    play_step = world.war._play_step

    def flaky_step(frame):
        if fault == "step_failure" and frame.page == Page.BOARD and not failures:
            failures.append(frame.page)
            raise task.CurrencyWarsActionUnready("备战页暂未确认")
        return play_step(frame)

    state = drive(monkeypatch, world, clean if entry == "takeover" else lobby, click)
    world.auto.drag_mouse.side_effect = drag
    warnings = Mock()
    monkeypatch.setattr(task.log, "warning", warnings)
    monkeypatch.setattr(world.war, "_gather", lambda f: f)
    monkeypatch.setattr(world.war, "_play_step", flaky_step)
    monkeypatch.setattr(world.war, "get_reward", lambda f: (f, (18000 if world.war.result else 15000, 18000), False))
    first_reads = [slot("front", 0).point, slot("front", 1).point, slot("back", 1).point, slot("bench", 0).point]

    if fault in ("budget", "stopped"):
        with pytest.raises(task.CurrencyWarsBudgetExceeded if fault == "budget" else RunStopRequested):
            world.war.start(resume=True)
        assert reads == first_reads and world.auto.drag_mouse.call_count == 0 and not fights
        return
    if entry == "daily":
        from tasks.daily import daily

        monkeypatch.setattr(daily, "CurrencyWars", lambda: world.war)
        assert daily.Daily._run_currency_wars()
    else:
        assert world.war.start(resume=entry == "takeover", loop=entry == "loop")
    assert reads == first_reads
    assert world.auto.drag_mouse.call_count == 2 and boards[-1] is deployed
    # 节点开始备战前移开一次指针，两次拖动后各移开一次。
    assert world.auto.park_mouse.call_count == 3
    assert fights == [stage] and failures == ([Page.BOARD] if fault == "step_failure" else [])
    assert not any("部署暂缓" in str(call.args[0]) for call in warnings.call_args_list)
    assert state.frame is lobby and world.war.result is True


def draw_card_items(image, point, count, *, badge=False):
    """按实机布局在卡片下方画装备图标：每件约 38 像素宽、带金框，按件数居中，整组随透视偏移。"""
    x, y = point
    center = x + (x - 960) * 0.04
    draw = ImageDraw.Draw(image)
    for k in range(count):
        left = round(center + (k - (count - 1) / 2) * 41.5 - 19)
        draw.rectangle((left, y + 60, left + 37, y + 95), fill=(150, 40, 60), outline=(232, 186, 70), width=2)
    if badge and count:
        # 「0」角标压住第一件的左下角和一段底边。
        left = round(center - (count - 1) / 2 * 41.5 - 19)
        draw.rectangle((left - 2, y + 80, left + 14, y + 99), fill=(20, 20, 30))
    return image


@pytest.mark.parametrize("badge", (False, True))
@pytest.mark.parametrize("count", (0, 1, 2, 3))
@pytest.mark.parametrize("point", ((745, 405), (605, 667), (1386, 667), (1065, 912)))
def test_card_equipment_counts_centered_icons_by_their_gold_frames(point, count, badge):
    """实机上 2 件被读成 3 件、1 件被读成 2 件。图标按件数居中，按卡片正下方金框的总宽度计数。"""
    x, y = point
    image = CANVAS.copy()
    # 金色卡框的底边不算装备；相邻卡位穿满三件也不能算到这张卡上。
    ImageDraw.Draw(image).rectangle((x - 60, y + 60, x + 60, y + 63), fill=(232, 186, 70))
    draw_card_items(image, (x + 142, y), 3)
    draw_card_items(image, point, count, badge=badge)
    assert Frame(image, ()).card_equipment(policy.Slot("back", 0, point, True)) == count


def draw_role_squares(image, point, front, back):
    """按 2026-11-22 实机画面在卡面右上角画两个站位方块，上前台、下后台，整组随透视向画面中间偏。推荐的站位是实心方块：
    卡站在推荐区时白色，站到另一区时红色；不推荐的站位是空心框。"""
    x, y = point
    left = x + 38 - round((x - 888) * 0.015)
    tops = (y - 58, y - 47) if y == ui.BACK_Y else (y - 55, y - 43)
    draw = ImageDraw.Draw(image)
    draw.rectangle((left - 8, y - 62, left + 18, y - 26), fill=(7, 7, 7))
    for top, style in zip(tops, (front, back)):
        box = (left, top, left + 10, top + 8)
        if style == "hollow":
            draw.rectangle(box, outline=(96, 96, 96))
        else:
            draw.rectangle(box, fill={"white": (236, 236, 236), "red": (255, 98, 98)}[style])
    return image


@pytest.mark.parametrize(("point", "front", "back", "expected"), (
    # 刻律德菈站在前台第 4 格：推荐的后台方块变红，前台是空心框。
    ((1173, ui.FRONT_Y), "hollow", "red", (False, True)),
    # 只能站前台的角色放在后台：推荐的前台方块变红。
    ((747, ui.BACK_Y), "red", "hollow", (True, False)),
    # 站在推荐区的卡照旧是白色实心方块。
    ((888, ui.FRONT_Y), "white", "hollow", (True, False)),
    ((889, ui.BACK_Y), "white", "white", (True, True)),
))
def test_card_role_reads_the_red_square_of_a_card_outside_its_recommended_zone(point, front, back, expected):
    """复现 2026-11-22 难度 89 的 2-4～2-6：站在前台的刻律德菈卡面上，推荐后台的方块是红色的。原来只认白色方块，把她读成
    前后台都不能站：退不回后台，也不能给买到的昔涟让位，昔涟一直坐在备战席。"""
    image = draw_role_squares(CANVAS.copy(), point, front, back)
    zone = "back" if point[1] == ui.BACK_Y else "front"
    assert Frame(image, ()).card_role(policy.Slot(zone, 0, point, True)) == expected


@pytest.mark.parametrize("outcome", ("topped_up", "late_receipt", "lost_again"))
def test_lost_experience_press_is_topped_up_once_in_the_same_node(monkeypatch, world, outcome):
    """实机 1-6：按 F 6 次只到账 5 次，没扣费的那次在本节点按现场经验补买一次；迟到的回执或再次漏按仍暂缓。"""
    stage = "1-6"
    units = (slot("front", 0, CORE),)
    controls = (("出战", 1818, 751), ("购买经验", 296, 866))
    initial = page(Page.BOARD, *controls, stage=stage, capacity=(1, 1), gold=36, level=6,
                   experience=(14, 36), experience_cost=4)
    partial = page(Page.BOARD, *controls, stage=stage, capacity=(1, 1), gold=16, level=6,
                   experience=(34, 36), experience_cost=4)
    leveled = page(Page.BOARD, *controls, stage=stage, capacity=(1, 2), gold=12, level=7,
                   experience=(2, 48), experience_cost=4)
    for frame in (initial, partial, leveled):
        monkeypatch.setattr(frame, "slots", lambda: units)
    entered = battle(True)
    late_at = None

    def capture(state):
        if state.frame is partial and late_at is not None and world.now[0] >= late_at:
            state.frame = leveled

    state = drive(monkeypatch, world, initial, lambda s, _: setattr(s, "frame", entered), capture)
    monkeypatch.setattr(world.war, "_read_board", lambda f: (f, board(
        *units, stage=stage, used=f.capacity[0], capacity=f.capacity[1], gold=f.gold, level=f.level, exp=f.experience,
    )))
    monkeypatch.setattr(world.war, "_can_buy_exp", lambda b, _: b.level == 6)

    def press(key):
        nonlocal late_at
        state.keys.append((state.frame.page, key))
        if len(state.keys) == 5:
            state.frame = partial
        elif len(state.keys) == 6 and outcome == "late_receipt":
            # 漏掉的那次在收回执后才生效：额外等待期间画面变化，不补买。
            late_at = world.now[0] + 1.2
        elif len(state.keys) == 7 and outcome == "topped_up":
            state.frame = leveled
        return True

    world.auto.press_key.side_effect = press
    assert world.war._prepare(initial) is entered
    assert state.keys == [(Page.BOARD, "f")] * (6 if outcome == "late_receipt" else 7)
    assert state.clicks == [(Page.BOARD, (1818, 751))]
    assert ((stage, "经验") in world.war.deferred_operations) is (outcome != "topped_up")


@pytest.mark.parametrize(("labels", "stored"), (
    ((("星", 90), ("?3", 225)), True),
    # 单字角色「刃」不是开拓者，没读成商品时照常重开核对。
    ((("刃", 90), ("?3", 225)), False),
    ((("3", 225),), False),
))
def test_shop_record_treats_a_single_character_name_as_the_player_trailblazer(world, labels, stored):
    """开拓者显示玩家自定的名字（这个账号是「星」）。单字名除「刃」外按开拓者处理，商店照常记录；只读到价格的栏仍要重开核对。"""
    stage = "2-5"
    x = 367 + 269 * 3
    shop = unwanted_shop(stage, gold=18, empty=(2, 4))
    shop.labels = shop.labels + tuple(Label(text, (x + offset, 306)) for text, offset in labels)
    world.war._remember_catalog(shop, stage, shop.offers, 0)
    assert (world.war.shop_catalog is not None) is stored


def test_single_character_blade_is_read_as_a_character():
    """「刃」是单字名的角色：商店按商品读出，详情页读出姓名；其他单字名仍是玩家自定的开拓者名，读不出。"""
    x = 367 + 269 * 2
    shop = page(Page.SHOP, ("刃", x + 90, 306), ("?3", x + 225, 306), stage="2-5")
    assert [(offer.name, offer.cost, offer.column) for offer in shop.offers] == [("刃", 3, 2)]
    assert page(Page.DETAIL, ("刃", 1610, 228), ("前后台", 1575, 279)).employee_name() == "刃"
    assert page(Page.DETAIL, ("星", 1610, 228), ("前后台", 1575, 279)).employee_name() is None
    assert page(Page.DETAIL, ("千冶·刃", 1610, 228), ("后台", 1575, 279)).employee_name() == "千冶·刃"


def test_sold_reserve_forgets_the_slot_name(monkeypatch, world):
    """出售后腾出的备战位可能马上放进新卡，旧姓名不再沿用。"""
    tile = slot("bench", 1, FILLER)
    stage = "2-5"
    before = page(Page.BOARD, stage=stage, gold=10)
    detail = page(Page.DETAIL, ("出售", 1770, 917), stage=stage)
    after = page(Page.BOARD, stage=stage, gold=11)
    monkeypatch.setattr(before, "slot_occupied", lambda point: point == tile.point)
    for key, name in ((("bench", 1), "瓦尔特"), (("bench", 0), "那刻夏")):
        world.war.slot_cache[key] = task.SlotIdentity(np.zeros((12, 12, 3), np.int16), name, False)
    drive(monkeypatch, world, before, lambda s, p: setattr(s, "frame", detail if p == tile.point else after))
    assert world.war._sell_reserve(before, tile) == (after, True)
    assert set(world.war.slot_cache) == {("bench", 0)}
