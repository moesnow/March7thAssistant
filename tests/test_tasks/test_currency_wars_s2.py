"""货币战争入画奇航的策略、画面判定与流程模拟。"""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image, ImageDraw
import pytest

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


def slot(zone, index, unit=None, *, occupied=False):
    return policy.Slot(zone, index, (735 + index * 140, {"front": 405, "back": 670, "bench": 910}[zone]),
                       occupied or unit is not None, unit)


CORE = policy.Unit("那刻夏", True, False, 2, equipment=0)
BAILU = policy.Unit("白露", False, True, 1)
CER = policy.Unit("刻律德菈", False, True, 1)
FILLER = policy.Unit("瓦尔特", True, True, 1)


def board(*slots, **kwargs):
    defaults = dict(stage="1-3", gold=16, hp=75, used=2, capacity=3, level=3, exp=(0, 4), slots=slots)
    return policy.Board(**(defaults | kwargs))


@pytest.fixture
def world(monkeypatch):
    now = [0.0]
    cfg = SimpleNamespace(currencywars_type="normal", currencywars_rank_difficulty="current",
                          currencywars_fast_mode=False, currencywars_bonus_enable=False,
                          currencywars_strategy="s2_anaxa", save_timestamp=Mock(), currencywars_timestamp=1,
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
    def observe():
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


def test_shop_refuses_conflicting_price_full_bench_and_third_star():
    offers = (policy.Offer("那刻夏", 2, (100, 200), 0), policy.Offer("白露", 2, (400, 200), 1))
    b = board(slot("front", 0, CORE), slot("bench", 0))
    assert policy.shop_purchase(b, offers) == offers[1]
    assert policy.shop_purchase(replace(b, slots=(slot("bench", 0, FILLER),)), offers) is None
    assert policy.shop_purchase(b, (policy.Offer("那刻夏", 1, (100, 200), 0),)) is None
    assert not policy.should_refresh(b, 2, 0)
    assert not policy.should_buy_exp(replace(b, used=3), 4)


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
    full = ten_employee_board(fronts, backs, (sparkle, None))
    plan = policy.deployment(full)
    assert [move[0].unit.name for move in plan] == [FILLER.name, sparkle.name]
    assert plan[0][1].zone == "bench" and plan[1][1].zone == "front"
    for move in plan:
        full = apply_deployment(full, move)
    assert full.used == 10 and full.slots[1].unit == sparkle
    assert policy.deployment(full) == ()


def test_early_replacement_preserves_the_only_frontline_damage_dealer():
    damage = policy.Unit("过渡输出", True, True, 1, output=True)
    sparkle = policy.Unit("花火", True, False, 1)
    robin = policy.Unit("知更鸟", True, False, 1)
    fallback = slot("front", 2, damage)
    rear = slot("back", 0)
    lead = slot("bench", 0, CER)
    before = board(slot("front", 0, sparkle), slot("front", 1, robin), fallback, rear,
                   lead, slot("bench", 1), stage="1-1", used=3, capacity=3)
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


@pytest.mark.parametrize(("other_healer", "hp", "can_move_shielder"), (
    (True, 100, True), (False, 100, False), (True, 30, False),
))
def test_core_can_replace_surplus_sustain_but_preserves_the_needed_healing(other_healer, hp, can_move_shielder):
    shielder = policy.Unit("符玄", True, False)
    front = (shielder, policy.Unit("花火", True, False), policy.Unit("星期日", True, True),
             policy.Unit("知更鸟", True, False))
    rear = (CER, BAILU if other_healer else policy.Unit("后台过渡", False, True),
            *(policy.Unit(f"后台角色{i}", False, True) for i in range(4)))
    full = ten_employee_board(front, rear, (CORE, None), hp=hp)
    moves = policy.deployment(full)
    assert moves[1][0].unit == CORE
    assert (moves[0][0].unit == shielder) is can_move_shielder


def test_shields_do_not_replace_the_only_healing_employee():
    healer = policy.Unit("灵砂", True, True)
    front = (healer, policy.Unit("花火", True, False), policy.Unit("星期日", True, True),
             policy.Unit("知更鸟", True, False))
    rear = (CER, policy.Unit("杰帕德", True, True),
            *(policy.Unit(f"后台角色{i}", False, True) for i in range(4)))
    full = ten_employee_board(front, rear, (CORE, None))
    moves = policy.deployment(full)
    assert moves[0][0].unit != healer and moves[1][0].unit == CORE


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
              slot("bench", 1), used=1, capacity=2, gold=6)
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
    b = board(active, incoming, spare, used=1, capacity=1)
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


def test_shop_buys_the_core_upgrade_before_spending_the_population_budget():
    b = board(slot("front", 0, replace(CORE, stars=1)), slot("back", 0, CER), slot("back", 1),
              slot("bench", 0, policy.Unit("后台候补", False, True)), slot("bench", 1), slot("bench", 2),
              used=2, capacity=2, level=6, gold=12, exp=(32, 36))
    core = policy.Offer(CORE.name, 1, (100, 200), 0)
    healer = policy.Offer(BAILU.name, 2, (400, 200), 1)
    assert policy.should_buy_exp(b, 4)
    assert policy.shop_purchase(b, (healer, core), experience_price=4) == core
    assert policy.shop_purchase(b, (healer,), experience_price=4) is None


def test_full_board_reserves_the_last_bench_slot_for_a_replacement():
    b = board(slot("front", 0, replace(CORE, stars=1)), slot("back", 0, CER), slot("bench", 0),
              used=2, capacity=2)
    sparkle = policy.Offer("花火", 2, (350, 180), 1, front=True)
    core_copy = policy.Offer(CORE.name, 1, (100, 180), 0, front=True)
    assert policy.shop_purchase(b, (sparkle,)) is None
    assert policy.shop_purchase(b, (sparkle, core_copy)) == core_copy
    assert policy.shop_purchase(replace(b, slots=(*b.slots, slot("bench", 1))), (sparkle,)) == sparkle


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


def test_missing_core_refresh_keeps_budget_and_stops():
    b = board(slot("bench", 0))
    assert not policy.should_refresh(replace(b, gold=11), 2, 0)
    assert policy.should_refresh(replace(b, gold=12), 2, 0)
    assert not policy.should_refresh(b, 2, 2)
    assert not policy.should_refresh(replace(b, stage="1-1"), 2, 0)


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
    assert policy.resolve_strategy("default") == policy.STRATEGY_ID


def home():
    return page(Page.HOME, ("开始货币战争", 1600, 972), ("积分", 381, 961))


def mode(*extra):
    return page(Page.MODES, ("标准博弈", 160, 224), ("超频博弈", 160, 420), *extra)


def rank():
    return page(Page.RANK, ("标准博弈", 154, 884), ("1", 545, 963), ("开始对局", 1680, 965))


def battle(auto_on):
    return page(Page.BATTLE, auto_off=not auto_on)


def reconnect_prompt(*, split=False, enabled=True):
    image = CANVAS.copy()
    if enabled:
        ImageDraw.Draw(image).rectangle((1090, 649, 1278, 693), fill="white")
    message = (("失去网络连接，战斗结果同步失败，", 921, 519), ("是否尝试重新连接？", 1004, 548)) if split else (
        ("失去网络连接，战斗结果同步失败，是否尝试重新连接？", 956, 526),
    )
    return Frame(image, labels(("提示", 959, 412), ("取消", 770, 671), ("确认", 1188, 672), *message))


def test_reconnect_modal_uses_native_title_message_and_enabled_confirmation():
    prompt = reconnect_prompt(split=True)
    retained = tuple(label for label in prompt.labels if label.text != "取消")
    overlapping = Frame(prompt.image, retained + labels(
        ("备战阶段", 282, 72), ("1-4", 282, 109), ("收起", 1624, 982), ("刷新", 1630, 488)))
    assert overlapping.page == Page.RECONNECT
    assert overlapping.action_context == (Page.RECONNECT, None, None)
    assert overlapping.reconnect_confirm().point == (1188, 672)
    assert reconnect_prompt(enabled=False).reconnect_confirm() is None
    unrelated = Frame(prompt.image, labels(("提示", 959, 412), ("取消", 770, 671), ("确认", 1188, 672),
                                          ("是否中断挑战并保存当前进度？", 956, 526)))
    assert unrelated.page != Page.RECONNECT
    assert unrelated.reconnect_confirm() is None


@pytest.mark.parametrize("returns_to_world", (False, True))
def test_reconnect_replans_from_recovered_state_without_repeating_the_pending_input(
        monkeypatch, world, returns_to_world):
    before = page(Page.BOARD, stage="1-4", gold=16)
    modal = reconnect_prompt()
    overworld = page(Page.UNKNOWN)
    lobby = home()
    mode_loading = mode(("进行中", 1120, 730), ("标准博弈", 646, 156))
    continuing = mode(("结束并结算", 1340, 962), ("继续对局", 1640, 962), ("标准博弈", 646, 156))
    resumed = page(Page.BOARD, stage="1-4", gold=14)
    old_action = (1420, 765)
    routes = {
        (before, old_action): modal,
        (modal, (1188, 672)): overworld if returns_to_world else resumed,
        (lobby, (1600, 972)): mode_loading,
        (continuing, (1640, 962)): resumed,
    }
    menu_reads = 0

    def capture(state):
        nonlocal menu_reads
        if state.frame is mode_loading:
            menu_reads += 1
            if menu_reads == 3:
                state.frame = continuing

    state = drive(monkeypatch, world, before, lambda s, p: setattr(s, "frame", routes[s.frame, p]),
                  after_capture=capture)
    screen = SimpleNamespace(
        current_screen="main",
        get_current_screen=lambda **kwargs: state.frame is overworld,
        change_to=Mock(side_effect=lambda *a, **k: setattr(state, "frame", lobby)),
    )
    monkeypatch.setattr(task, "screen", screen)

    def prepare(frame):
        if frame is before:
            world.war.stage_refreshes["1-4"] = 1
            world.war.experience_probes.add("1-4")
            world.war.slot_cache["old"] = None
            return world.war._click_to(before, lambda f: old_action, lambda f: f.page == Page.BOARD and f.gold == 14,
                                       "模拟尚未确认的购买回执")
        assert frame is resumed
        assert frame.gold == 14
        assert not world.war.slot_cache
        assert world.war.stage_refreshes == {"1-4": 1}
        assert world.war.experience_probes == {"1-4"}
        return lobby

    monkeypatch.setattr(world.war, "_prepare", prepare)
    assert world.war._play(before) is lobby
    expected = [(Page.BOARD, old_action), (Page.RECONNECT, (1188, 672))]
    if returns_to_world:
        expected += [(Page.HOME, (1600, 972)), (Page.MODES, (1640, 962))]
        assert menu_reads == 3
    assert state.clicks == expected
    assert world.war.network_reconnects == 1


@pytest.mark.parametrize("wrong_mode", (False, True))
def test_reconnect_stops_at_mode_menu_without_the_original_match(monkeypatch, world, wrong_mode):
    modal = reconnect_prompt()
    menu = mode(("继续对局", 1640, 962), ("超频博弈", 646, 156)) if wrong_mode else mode(
        ("进入标准博弈", 1638, 960))
    state = drive(monkeypatch, world, modal, lambda s, _: setattr(s, "frame", menu))
    with pytest.raises(task.CurrencyWarsError, match="未找到同模式续局入口"):
        world.war._recover_network(modal)
    assert state.clicks == [(Page.RECONNECT, (1188, 672))]
    assert world.war.frame is menu


def test_reconnect_uses_the_task_budget_and_a_bounded_native_retry(monkeypatch, world):
    modal = reconnect_prompt()
    state = drive(monkeypatch, world, modal)
    world.war.network_reconnects = task.MAX_RECONNECTS - 1
    with pytest.raises(task.CurrencyWarsError, match="游戏重连后未确认恢复画面"):
        world.war._recover_network(modal)
    assert state.clicks == [(Page.RECONNECT, (1188, 672))] * 2
    with pytest.raises(task.CurrencyWarsError, match="重连次数上限"):
        world.war._recover_network(modal)
    assert state.clicks == [(Page.RECONNECT, (1188, 672))] * 2


def test_network_modal_ends_combat_wait_without_a_combat_input(monkeypatch, world):
    modal = reconnect_prompt()
    state = drive(monkeypatch, world, modal)
    assert world.war._watch_battle(battle(True)) is modal
    assert state.clicks == state.keys == []


def test_stop_during_reconnect_does_not_retry_the_dialog(monkeypatch, world):
    modal = reconnect_prompt()

    def capture(state):
        if state.clicks:
            raise RunStopRequested()

    state = drive(monkeypatch, world, modal, after_capture=capture)
    with pytest.raises(RunStopRequested):
        world.war._recover_network(modal)
    assert state.clicks == [(Page.RECONNECT, (1188, 672))]


def end_match_dialog():
    image = CANVAS.copy()
    ImageDraw.Draw(image).rounded_rectangle((779, 715, 1140, 772), radius=28, fill=(224, 224, 224))
    return Frame(image, labels(
        ("提示", 778, 341), ("选择放弃并结算将直接结算并重置进度。", 958, 412),
        ("确定结束进程吗？", 840, 440), ("放弃并结算", 980, 743),
    ))


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
    with pytest.raises(task.CurrencyWarsReceiptTimeout, match="未确认旧对局已结束"):
        world.war._launch(ongoing, False)
    assert state.clicks == [(Page.MODES, (1397, 961)), (Page.END_MATCH_CONFIRM, (980, 743))]
    assert not state.keys


def test_missing_resume_button_does_not_end_or_start_a_match(monkeypatch, world):
    world.cfg.currencywars_unfinished_match = "resume"
    ongoing = mode(("结束并结算", 1397, 961), ("超频博弈", 670, 155))
    state = drive(monkeypatch, world, ongoing)
    with pytest.raises(task.CurrencyWarsReadTimeout, match="没有可确认的续局入口"):
        world.war._launch(ongoing, False)
    assert not state.clicks and not state.keys


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


@pytest.mark.parametrize("receipt", ("slot", "inventory", None))
def test_item_box_waits_for_a_stable_node_and_requires_a_reward_receipt(monkeypatch, world, receipt):
    header = ("简易武装箱", 1028, 60), ("请选择1个", 1028, 98)
    early = Frame(CANVAS, labels(*header))
    choices = (("生命之花", 1465, 336), ("查看详情", 1474, 392), ("开启", 939, 940))
    ready = Frame(CANVAS, labels(*header, ("1-9", 300, 109), *choices))
    after = page(Page.BOARD, stage="1-9")
    monkeypatch.setattr(ready, "inventory_items", lambda: ((1844, 248),))
    monkeypatch.setattr(after, "inventory_items",
                        lambda: ((1844, 248), (1844, 325)) if receipt == "inventory" else ((1844, 248),))
    monkeypatch.setattr(after, "slot_occupied", lambda _: receipt != "slot")

    def capture(state):
        if world.now[0] > 0 and state.frame is early:
            state.frame = ready

    state = drive(monkeypatch, world, early, lambda s, _: setattr(s, "frame", after), capture)
    if receipt:
        assert world.war._choose(early) is after
    else:
        with pytest.raises(task.CurrencyWarsError, match="未确认可选卡片"):
            world.war._choose(early)
    assert state.clicks == [(Page.CHOICE, (1465, 336))]


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
    before = board(slot("bench", 0), gold=7)
    if confirmed:
        assert world.war._shop(initial, before, 0) == (initial, 0, True)
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
    assert world.war._shop(initial, board(slot("bench", 0)), 0) == (board_receipt, 0, True)
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
                 stage=stage, used=1, capacity=1)
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


def test_auto_toggle_failure_stops_without_toggling_back(monkeypatch, world):
    off = battle(False)
    state = drive(monkeypatch, world, off)
    with pytest.raises(task.CurrencyWarsError, match="左下角 C 仍显示"):
        world.war._watch_battle(off)
    assert state.clicks == [(Page.BATTLE, ui.AUTO_TOGGLE)]
    assert not state.keys


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
    with pytest.raises(task.CurrencyWarsError, match="总时限"):
        world.war.start(weekly=True)
    launch.assert_called_once()


def test_recognized_pages_without_progress_are_bounded(monkeypatch, world):
    frame = page(Page.CHOICE, stage="1-1")
    drive(monkeypatch, world, frame)
    choose = Mock(return_value=frame)
    monkeypatch.setattr(world.war, "_choose", choose)
    with pytest.raises(task.CurrencyWarsError, match="未推进"):
        world.war._play(frame)
    assert choose.call_count == 16


@pytest.mark.parametrize("next_page", (Page.BATTLE, Page.NODE_RESULT, Page.MATCH_RESULT, Page.RECONNECT))
def test_play_allows_battle_settlement_or_reconnect_after_the_preparation_limit(monkeypatch, world, next_page):
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
    if paid:
        assert world.war._play(initial) is home_frame and steps == 22
    else:
        with pytest.raises(task.CurrencyWarsError, match="节点 3-5 多次转场仍未推进"):
            world.war._play(initial)
        assert steps == 16
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


def test_preparation_receipts_do_not_extend_the_match_transition_limit(monkeypatch, world):
    frame = page(Page.BENCH_FULL, stage="3-5")

    def step(f):
        world.war.preparation_progress += 1
        return f

    monkeypatch.setattr(world.war, "_play_step", step)
    with pytest.raises(task.CurrencyWarsError, match="单局转场上限"):
        world.war._play(frame)
    assert world.war.preparation_progress == 250


def test_unready_input_replans_twice_at_most_without_replaying_uncertain_actions(monkeypatch, world):
    frame = page(Page.BOARD, stage="1-2")
    state = drive(monkeypatch, world, frame)
    stale = Mock(side_effect=task.CurrencyWarsActionUnready("前置条件已变化"))
    monkeypatch.setattr(world.war, "_play_step", stale)
    with pytest.raises(task.CurrencyWarsActionUnready, match="前置条件"):
        world.war._play(frame)
    assert stale.call_count == 3
    assert not state.clicks

    ambiguous = Mock(side_effect=task.CurrencyWarsError("已经点击但没有回执"))
    monkeypatch.setattr(world.war, "_play_step", ambiguous)
    with pytest.raises(task.CurrencyWarsError, match="没有回执"):
        world.war._play(frame)
    ambiguous.assert_called_once_with(frame)


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


def test_cross_week_score_mismatch_does_not_save_completion(monkeypatch, world):
    old = home()
    reset = page(Page.HOME, ("0/18000", 318, 1000))
    weekly = page(Page.WEEKLY, ("18000/18000", 273, 740))
    monkeypatch.setattr(weekly, "claim_available", lambda: False)
    state = drive(monkeypatch, world, old, lambda s, _: setattr(s, "frame", weekly))
    world.auto.press_key.side_effect = lambda _: setattr(state, "frame", reset)
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


@pytest.mark.parametrize("return_page", (Page.BOARD, Page.DETAIL))
def test_dreamscape_dance_confirms_two_actual_selections_before_returning(monkeypatch, world, return_page):
    common = labels(("备战阶段", 287, 70), ("1-2", 287, 106), ("梦境交织", 1044, 77),
                    ("选择2个角色进行共舞，为其增加战斗内连携效果", 1044, 136),
                    ("黑天鹅", 928, 357), ("花火", 1165, 357),
                    ("详情", 938, 412), ("详情", 1176, 412), ("确认选择", 1487, 576))
    bright = CANVAS.copy()
    ImageDraw.Draw(bright).rectangle((1428, 561, 1550, 592), fill=(235, 235, 235))
    open_ = Frame(CANVAS, common)
    first = Frame(CANVAS, common + labels(("已选择", 1118, 192)))
    both = Frame(bright, common + labels(("已选择", 1118, 192), ("已选择", 879, 192)))
    ready = page(return_page, stage="1-2")
    state = drive(monkeypatch, world, open_, lambda s, point: setattr(
        s, "frame", {(1165, 357): first, (928, 357): both, (1487, 576): ready}[point]))
    assert open_.page == Page.DANCE
    assert first.employee_event_selected == {"花火"}
    assert first.employee_event_confirm() is None
    assert world.war._play_step(open_) is ready
    assert state.clicks == [(Page.DANCE, p) for p in ((1165, 357), (928, 357), (1487, 576))]


@pytest.mark.parametrize("selection_applies", (True, False))
def test_ranger_appointment_verifies_exactly_one_candidate_before_confirming(monkeypatch, world, selection_applies):
    common = labels(("备战阶段", 322, 69), ("3-5", 322, 107), ("巡海游侠", 1046, 77),
                    ("任命1名角色，使其成为巡海游侠", 1045, 134),
                    ("灵砂", 690, 358), ("花火", 928, 358), ("详情", 699, 411), ("详情", 937, 411),
                    ("确认选择", 1493, 598))
    before = Frame(CANVAS, common)
    assert before.page == Page.RANGER and not before.employee_event_selected
    assert Frame(CANVAS, common[:3] + common[4:]).page != Page.RANGER
    enabled = CANVAS.copy()
    ImageDraw.Draw(enabled).rectangle((1432, 585, 1554, 612), fill=(235, 235, 235))
    selected = Frame(enabled, common + labels(("已选择", 882, 194)))
    after = page(Page.BOARD, stage="3-5")

    def click(state, point):
        if point == (928, 358):
            state.frame = selected if selection_applies else before
        elif point == (1493, 598):
            state.frame = after

    state = drive(monkeypatch, world, before, click)
    if selection_applies:
        assert world.war._play_step(before) is after
        assert state.clicks == [(Page.RANGER, (928, 358)), (Page.RANGER, (1493, 598))]
    else:
        with pytest.raises(task.CurrencyWarsError, match="已尝试 3 次"):
            world.war._play_step(before)
        assert state.clicks == [(Page.RANGER, (928, 358))] * 3


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
def test_rail_catalog_requires_multiple_columns_and_the_unlock_meter(remainder):
    frame = Frame(CANVAS, labels(*RAIL_HEADER, *remainder))
    assert frame.page == Page.RAIL_SHOP
    assert not frame.rail_catalog_ready()


def test_rail_shop_closes_without_repeating_a_free_launch_with_an_unclear_balance(monkeypatch, world):
    initial = Frame(CANVAS, labels(*RAIL_HEADER, ("详情", 1056, 442), ("星穹列车，跃迁！", 1011, 380),
                                   ("0", 1137, 380), ("1", 637, 109)))
    catalog = Frame(CANVAS, labels(*RAIL_HEADER, *RAIL_CATALOG, ("0", 637, 109)))
    ready = page(Page.BOARD, stage=initial.stage)
    routes = {(initial, (1011, 380)): catalog, (catalog, (12, 12)): ready}
    state = drive(monkeypatch, world, initial, lambda s, point: setattr(s, "frame", routes[s.frame, point]))
    assert world.war._rail_shop(initial) is ready
    assert state.clicks == [(Page.RAIL_SHOP, (1011, 380)), (Page.RAIL_SHOP, (12, 12))]
    assert (initial.stage, "开拓商店") in world.war.deferred_operations


@pytest.mark.parametrize("preselected", (False, True))
def test_garden_requires_selected_card_and_enabled_confirm(monkeypatch, world, preselected):
    words = labels(("备战阶段", 282, 72), ("2-3", 281, 108), ("奇兽花园", 1047, 78),
                   ("选择奇美拉", 1046, 135), ("咕噜鱼儿", 499, 402), ("详情", 760, 456),
                   ("我方小队初始能量提升20。", 593, 352), ("急先锋", 896, 403),
                   ("我方全体行动提前100%", 1045, 305), ("详情", 1169, 456), ("看乐子", 1303, 403),
                   ("未完美通关时，获得3次免费刷新。", 1445, 352), ("详情", 1577, 456), ("确认选择", 1492, 599))
    initial = Frame(CANVAS, words)
    canvas = CANVAS.copy()
    draw = ImageDraw.Draw(canvas)
    draw.line((444, 203, 444, 382), fill=(247, 250, 251), width=3)
    draw.line((832, 203, 832, 382), fill=(247, 250, 251), width=3)
    draw.rectangle((1420, 588, 1571, 610), fill=(241, 246, 251))
    selected = Frame(canvas, words)
    after = page(Page.BOARD, stage="2-3")
    assert initial.page == selected.page == Page.GARDEN
    assert initial.board_effect_selected == () and initial.board_effect_confirm() is None
    assert selected.board_effect_selected == ("咕噜鱼儿",) and selected.board_effect_confirm()
    routes = {(initial, (499, 402)): selected, (selected, (1492, 599)): after}
    first = selected if preselected else initial
    state = drive(monkeypatch, world, first, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    assert world.war._play_step(first) is after
    expected = [] if preselected else [(Page.GARDEN, (499, 402))]
    assert state.clicks == expected + [(Page.GARDEN, (1492, 599))]


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
    assert initial.board_effect_selected == () and selected.board_effect_selected == (backup[0],)
    after = page(Page.BOARD, stage=stage)
    routes = {first[1:]: initial, backup[1:]: selected, (1492, 600): after}
    state = drive(monkeypatch, world, initial, lambda st, pt: setattr(st, "frame", routes[pt]))
    assert world.war._choose_board_effect(initial) is after
    assert state.clicks == [
        (Page.GARDEN, first[1:]), (Page.GARDEN, backup[1:]), (Page.GARDEN, (1492, 600)),
    ]


@pytest.mark.parametrize("event", (Page.GARDEN, Page.HACK))
def test_new_single_selection_uses_confirm_state_without_recognizing_outline(monkeypatch, world, event):
    phase = "1-2"
    candidate = Label("已核对的选项", (690, 402))
    cards = ((candidate, "我方小队伤害增幅10%。"),)
    button = Label("确认选择", (1492, 600))
    initial = page(event, stage=phase, board_effect_cards=cards)
    chosen = page(event, stage=phase, board_effect_cards=cards)
    board_after = page(Page.BOARD, stage=phase)
    monkeypatch.setattr(initial, "board_effect_confirm", lambda: None)
    monkeypatch.setattr(chosen, "board_effect_confirm", lambda: button)

    def fail_on_outline(*args, **kwargs):
        pytest.fail("未预选的单选流程无需识别卡片描边")

    monkeypatch.setattr(chosen, "card_outline", fail_on_outline)
    routes = {candidate.point: chosen, button.point: board_after}
    state = drive(monkeypatch, world, initial, lambda st, pt: setattr(st, "frame", routes[pt]))
    assert world.war._choose_board_effect(initial) is board_after
    assert state.clicks == [(event, candidate.point), (event, button.point)]


@pytest.mark.parametrize(("effects", "choice"), (
    (("我方小队生命增幅提升10%。", "我方小队幸运一击率提升10%。"), 1),
    (("我方后台格挡率提高12%。", "消耗10金币，我方小队幸运一击率提升10%。"), 0),
    (("失去5点小队生命值。", "随机移除一名角色。"), None),
))
def test_board_effect_accepts_explicit_team_buffs_and_keeps_cost_checks(monkeypatch, world, effects, choice):
    options = labels(("第一只奇美拉", 575, 402), ("第二只奇美拉", 1018, 402))
    stage = "1-4"
    cards = tuple(zip(options, effects))
    initial = page(Page.GARDEN, stage=stage, board_effect_cards=cards, board_effect_selected=())
    after = page(Page.BOARD, stage=stage)
    confirm = Label("确认选择", (1492, 599))
    if choice is None:
        state = drive(monkeypatch, world, initial)
        with pytest.raises(task.CurrencyWarsError, match="未识别到适用的选项"):
            world.war._choose_board_effect(initial)
        assert state.clicks == []
        return
    option = options[choice]
    selected = page(Page.GARDEN, stage=stage, board_effect_cards=cards, board_effect_selected=(option.text,))
    monkeypatch.setattr(selected, "board_effect_confirm", lambda: confirm)
    routes = {(initial, option.point): selected, (selected, confirm.point): after}
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    assert world.war._choose_board_effect(initial) is after
    assert state.clicks == [(Page.GARDEN, option.point), (Page.GARDEN, confirm.point)]


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
    if preselected is None:
        assert initial.board_effect_selected == ()
    assert selected.board_effect_selected == (option[0],)
    routes = {(initial, option[1:]): selected, (selected, (1492, 599)): after,
              (initial, (1492, 599)): after}
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    assert world.war._play_step(initial) is after
    expected = [] if preselected == 1 else [(Page.HACK, option[1:])]
    assert state.clicks == expected + [(Page.HACK, (1492, 599))]


@pytest.mark.parametrize(("left_effect", "right_effect", "choice"), (
    ("帮助你获得更多银狼LV.999。", "提高隐藏分挡位，获得额外强化。", 0),
    ("敌方全体获得额外强化。", "获得额外强化。", 1),
))
def test_hack_accepts_more_employees_or_reinforcement_without_an_enemy_benefit(
        monkeypatch, world, left_effect, right_effect, choice):
    choices = labels(("左边工具", 674, 402), ("右边工具", 1180, 402))
    cards = tuple(zip(choices, (left_effect, right_effect)))
    initial = page(Page.HACK, stage="1-1", board_effect_cards=cards, board_effect_selected=())
    option = choices[choice]
    selected = page(Page.HACK, stage="1-1", board_effect_cards=cards, board_effect_selected=(option.text,))
    confirm = Label("确认选择", (1492, 599))
    monkeypatch.setattr(selected, "board_effect_confirm", lambda: confirm)
    after = page(Page.BOARD, stage="1-1")
    routes = {(initial, option.point): selected, (selected, confirm.point): after}
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    assert world.war._choose_board_effect(initial) is after
    assert state.clicks == [(Page.HACK, option.point), (Page.HACK, confirm.point)]


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
    b = board(slot("front", 0, CORE), slot("bench", 0), slot("bench", 1), used=3)
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
        f = Frame(view, labels(*words, (f"已选择{int(chosen is not None)}/1", 1683, 924)))
        f.__dict__.update(page=Page.CHOICE, choice="补给阶段", stage=stage)
        if chosen is not None:
            monkeypatch.setattr(f, "choice_confirm", lambda: Label("确认", (1710, 984)))
        return f

    ready, chosen, after = supply(selected), supply(1), page(Page.BOARD, stage=stage)
    assert [equipment for _, equipment, _ in ready.supply_cards] == ["护盾装备", equipment, ""]
    routes = {(ready, (x1, 566)): chosen, (chosen, (1710, 984)): after, (ready, (1710, 984)): after}
    state = drive(monkeypatch, world, ready, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    assert world.war._choose(ready) is after
    expected = [] if selected is not None else [(Page.CHOICE, (x1, 566))]
    assert state.clicks == expected + [(Page.CHOICE, (1710, 984))]


def test_selected_supply_requires_count_and_card_highlight(monkeypatch, world):
    selected = CANVAS.copy()
    ImageDraw.Draw(selected).line((1180, 780, 1442, 780), fill=(250, 250, 250), width=2)
    ImageDraw.Draw(selected).rectangle((1650, 973, 1775, 998), fill=(246, 246, 246))
    f = Frame(selected, labels(("补给阶段", 961, 162), ("那刻夏", 1234, 566),
                               ("已选择1/1", 1692, 925), ("确认", 1712, 985)))
    assert f.page == Page.CHOICE
    assert f.supply_selected_at((1234, 566))
    assert not f.supply_selected_at((990, 566))
    state = drive(monkeypatch, world, f, lambda state, _: setattr(state, "frame", page(Page.BOARD)))
    assert world.war._choose(f).page == Page.BOARD
    assert state.clicks == [(Page.CHOICE, (1712, 985))]


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
    assert after.choice_selected(before, (960, 540))
    assert not after.choice_selected(before, (1460, 540))


def test_selected_investment_with_only_a_white_outline_is_recognized():
    image = CANVAS.copy()
    draw = ImageDraw.Draw(image)
    draw.line((1250, 295, 1250, 790), fill=(255, 255, 255), width=3)
    draw.line((1665, 295, 1665, 790), fill=(255, 255, 255), width=3)
    f = Frame(image, ())
    assert f.choice_selected(f, (1458, 490))
    assert not f.choice_selected(f, (960, 490))


def test_investment_replans_when_the_rest_of_the_cards_slide_in(monkeypatch, world):
    title = ("投资环境", 960, 101)
    early = page(Page.CHOICE, title, ("幻月游戏概念股", 438, 393),
                 ("开局获得装备", 440, 435), choice="投资环境")
    stable = page(Page.CHOICE, title, ("幻月游戏概念股", 438, 393),
                  ("人身意外险", 960, 393), ("人才下沉", 1477, 393), choice="投资环境")
    selected = page(Page.CHOICE, title, choice="投资环境")
    confirm = Label("确认", (960, 984))
    monkeypatch.setattr(selected, "choice_confirm", lambda: confirm)
    monkeypatch.setattr(selected, "choice_selected", lambda before, p: before is stable and p == (960, 393))
    after = page(Page.BOARD)
    frames = iter((early, stable))

    def capture(s):
        s.frame = next(frames, s.frame)

    state = drive(monkeypatch, world, early, lambda s, p: setattr(
        s, "frame", selected if p == (960, 393) else after), capture)
    assert world.war._choose(early) is after
    assert state.clicks == [(Page.CHOICE, (960, 393)), (Page.CHOICE, (960, 984))]


@pytest.mark.parametrize("replaced_columns", (1, 2))
def test_investment_confirmation_recognizes_a_second_same_title_catalog(monkeypatch, world, replaced_columns):
    title = "请选择投资策略"
    card = ("立即补给", 460, 490)
    first = (card, ("获得3金币。", 460, 535), ("短线防御", 960, 490), ("提高10%防御。", 960, 535),
             ("积攒收益", 1460, 490), ("获得2金币。", 1460, 535))
    second = (card, ("获得3金币。", 460, 535), ("长期防御", 960, 490), ("提高20%防御。", 960, 535),
              ("追加资源" if replaced_columns == 2 else "积攒收益", 1460, 490), ("获得2金币。", 1460, 535))
    confirm = Label("确认", (979, 984))
    before = page(Page.CHOICE, *first, choice=title)
    selected = page(Page.CHOICE, *first, choice=title)
    fading = page(Page.CHOICE, *second, choice=title)
    following = page(Page.CHOICE, *second, choice=title)
    for f in (selected, fading):
        monkeypatch.setattr(f, "choice_confirm", lambda: confirm)
        monkeypatch.setattr(f, "choice_selected", lambda *_: True)
    routes = {(before, card[1:]): selected, (selected, confirm.point): fading}
    fading_reads = 0

    def capture(state):
        nonlocal fading_reads
        if state.frame is fading:
            fading_reads += 1
            if fading_reads > 4:
                state.frame = following

    state = drive(monkeypatch, world, before, lambda s, p: setattr(s, "frame", routes[s.frame, p]),
                  after_capture=capture)
    if replaced_columns == 2:
        assert world.war._choose(before) is following
    else:
        with pytest.raises(task.CurrencyWarsError, match="确认后未转场"):
            world.war._choose(before)
    assert state.clicks == [(Page.CHOICE, card[1:]), (Page.CHOICE, confirm.point)]


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
    for f in (selected, following_selected):
        monkeypatch.setattr(f, "choice_confirm", lambda: confirm)
        monkeypatch.setattr(f, "choice_selected", lambda *_: True)
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


def test_duplicate_employee_waits_on_bench_to_merge():
    dupe = replace(CORE, stars=1)
    f = board(slot("front", 0, dupe), slot("front", 1), slot("bench", 0, dupe),
              slot("bench", 1, FILLER), used=1, capacity=3)
    assert policy.deployment(f) == ((f.slots[3], f.slots[1]),)


@pytest.mark.parametrize("balance", (18, 19, 23))
def test_coffee_choice_checks_dialogue_progress_and_the_minimum_gain(monkeypatch, world, balance):
    offer = ("圆硬币咖啡", 1213, 612)
    gain = ("获得5金币。", 1200, 683)
    confirm = ("确认", 1770, 683)
    initial = page(Page.TEA, offer, gain, ("14", 1063, 77), confirm)
    unrelated_gain = page(Page.TEA, offer, gain, ("23", 1063, 77), confirm)
    result = page(Page.TEA, (str(balance), 1063, 77), ("点击空白处继续", 1550, 922))

    intermediate = iter((unrelated_gain, result))
    state = drive(monkeypatch, world, initial, after_capture=lambda s: setattr(s, "frame", next(intermediate, result))
                  if s.clicks else None)
    assert world.war._tea(initial) is result
    assert state.clicks == [(Page.TEA, (1770, 683))]


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


@pytest.mark.parametrize("health", (91, 92, 96))
def test_tea_meal_requires_verified_health_after_the_row_confirmation(monkeypatch, world, health):
    label = ("美餐时间", 1200, 411)
    effect = ("回复20小队生命值", 1240, 480)
    initial = page(Page.TEA, label, effect, tea_hp=72)
    selected = page(Page.TEA, label, effect, ("确认", 1760, 482), tea_hp=72)
    after = page(Page.TEA, ("领取茶歇奖励", 960, 196), ("开启", 960, 981), tea_hp=health)
    state = drive(monkeypatch, world, initial, lambda s, p: setattr(
        s, "frame", selected if p == (1200, 411) else after))
    assert world.war._tea(initial) is after
    assert state.clicks == [(Page.TEA, (1200, 411)), (Page.TEA, (1760, 482))]


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
    monkeypatch.setattr(frame, "slots", lambda: units)
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
    monkeypatch.setattr(after, "slots", lambda: (*field, replace(destination, occupied=True)))
    monkeypatch.setattr(after, "slot_occupied", lambda point: point == destination.point)
    before = page(Page.BOARD, stage="3-6", capacity=(7, 8))
    monkeypatch.setattr(before, "slot_occupied", lambda point: point == source.point)
    state = drive(monkeypatch, world, before)
    world.auto.drag_mouse.side_effect = lambda *args, **kwargs: setattr(state, "frame", after)
    team = board(*field, source, destination, stage="3-6", used=7, capacity=8)
    assert world.war._move(before, team, source, destination) is after
    world.auto.drag_mouse.assert_called_once()
    assert not state.clicks


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
    world.war.halo_candidate = slot("front", 0, CORE), None
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
    for frame in frames:
        monkeypatch.setattr(frame, "halo_portrait_matches", lambda point, _: point == ui.HALO_TARGET)
    state = drive(monkeypatch, world, before, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    if after_status is None:
        with pytest.raises(task.CurrencyWarsError, match="未找到可核验的主角光环"):
            world.war._halo(before)
        assert state.clicks == []
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
    world.war.halo_candidate = slot("front", 0, CORE), None
    cards = (("守阵者", 415, 434), ("获得20%治疗强度和护盾强度，分摊伤害。", 421, 528),
             ("黑洞引力", 1491, 434), ("施放终结技后，使战斗倒计时延后10行动值。", 1501, 530),
             ("1刷新还剩6次", 958, 134), ("刷新", 401, 771))
    before = page(Page.HALO, *cards, halo_gold=4)
    selected = page(Page.HALO, *cards, ("确认", 969, 954), halo_gold=4)
    for f in (before, selected):
        monkeypatch.setattr(f, "halo_portrait_matches", lambda p, _: p == ui.HALO_TARGET)
    monkeypatch.setattr(selected, "halo_effect_selected", lambda i: i == 1)
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


def test_reward_space_only_considers_known_one_star_bench_spares():
    b = board(slot("front", 0, FILLER), slot("bench", 0, CORE), slot("bench", 1, BAILU),
              slot("bench", 2, CER), slot("bench", 3, replace(FILLER, stars=2)),
              slot("bench", 4, policy.Unit("娜塔莎", False, True, 1)),
              slot("bench", 5, FILLER), slot("bench", 6, occupied=True))
    assert policy.disposable_bench(b) == (b.slots[6],)


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


def test_replacement_prompt_preserves_first_halo(monkeypatch, world):
    dialog = Frame(CANVAS, labels(("是否替换该角色原有光环？", 960, 506), ("取消", 763, 672),
                                 ("确认", 1192, 672)))
    assert dialog.page == Page.HALO_REPLACE
    selection = page(Page.HALO)
    world.war.halo_candidate = slot("front", 0, CORE), None
    state = drive(monkeypatch, world, dialog, lambda s, _: setattr(s, "frame", selection))
    assert world.war._cancel_halo_replacement(dialog) == selection
    assert state.clicks == [(Page.HALO_REPLACE, (763, 672))]
    assert CORE.name in world.war.halo_excluded


def test_halo_confirms_name_when_center_art_does_not_match(monkeypatch, world):
    sunday = policy.Unit("星期日", True, True, 1)
    target = slot("front", 3, sunday)
    source = ui.HALO_FRONT[3]
    world.war.halo_candidate = target, None
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
    for f in (empty, filled, settled, selected):
        monkeypatch.setattr(f, "halo_portrait_matches", lambda point, _: point == source)
    monkeypatch.setattr(selected, "halo_effect_selected", lambda index: index == 1)
    routes = {
        (filled, (147, 954)): detail,
        (detail, (1863, 65)): settled,
        (settled, (1480, 436)): selected,
        (selected, (968, 953)): after,
    }
    state = drive(monkeypatch, world, empty, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    world.auto.drag_mouse.side_effect = lambda *a, **k: setattr(state, "frame", filled) or True
    assert world.war._halo(empty) is after
    assert world.auto.drag_mouse.call_count == 1
    assert state.clicks[0:2] == [(Page.HALO, (147, 954)), (Page.HALO_DETAIL, (1863, 65))]


@pytest.mark.parametrize("outcome", ("selected", "unchanged", "wrong_employee"))
def test_halo_reselects_after_the_previous_employee_is_retained(monkeypatch, world, outcome):
    target = slot("front", 2, policy.Unit("花火", True, False, 2))
    source = ui.HALO_FRONT[target.index]
    world.war.halo_candidate = target, None
    effects = (("前台专家", 425, 437), ("获得40%伤害增幅", 411, 532),
               ("乱披风拳法", 1481, 437), ("角色详情", 147, 954))
    previous = page(Page.HALO, *effects, ("确认", 968, 953))
    current = page(Page.HALO, *effects, ("尚未选择主角光环", 954, 890))
    chosen = page(Page.HALO, *effects, ("确认", 968, 953))
    current.image = CANVAS.copy()
    ImageDraw.Draw(current.image).rectangle(ui.HALO_TARGET_FACE, fill=(186, 93, 124))
    chosen.image = current.image.copy()
    name = target.unit.name if outcome == "selected" else "星期日"
    old_detail = page(Page.HALO_DETAIL, (CORE.name, 862, 203))
    new_detail = page(Page.HALO_DETAIL, (name, 862, 203))
    after = page(Page.BOARD)
    for f in (previous, current, chosen):
        monkeypatch.setattr(f, "halo_portrait_matches", lambda point, _: point == source)
    monkeypatch.setattr(previous, "halo_effect_selected", lambda index: index == 1)
    monkeypatch.setattr(chosen, "halo_effect_selected", lambda index: index == 0)
    routes = {
        (previous, (147, 954)): old_detail,
        (old_detail, (1863, 65)): previous,
        (current, (147, 954)): new_detail,
        (new_detail, (1863, 65)): current,
        (current, (425, 437)): chosen,
        (chosen, (968, 953)): after,
    }
    state = drive(monkeypatch, world, previous, lambda s, p: setattr(s, "frame", routes[s.frame, p]))
    if outcome != "unchanged":
        world.auto.drag_mouse.side_effect = lambda *a, **k: setattr(state, "frame", current) or True
    details = [(Page.HALO, (147, 954)), (Page.HALO_DETAIL, (1863, 65))]
    if outcome == "selected":
        assert world.war._halo(previous) is after
        assert state.clicks == details * 2 + [(Page.HALO, (425, 437)), (Page.HALO, (968, 953))]
        assert world.auto.drag_mouse.call_count == 1
    elif outcome == "unchanged":
        with pytest.raises(task.CurrencyWarsError, match="主角光环未确认放入角色"):
            world.war._halo(previous)
        assert state.clicks == details
        assert world.auto.drag_mouse.call_count == 3
    else:
        with pytest.raises(task.CurrencyWarsError, match="光环详情未确认花火"):
            world.war._halo(previous)
        assert state.clicks == details * 2
        assert world.auto.drag_mouse.call_count == 1


@pytest.mark.parametrize("returned_gold", (13, 17))
def test_full_bench_sale_requires_identity_price_and_empty_slot(monkeypatch, world, returned_gold):
    spare = slot("bench", 0, FILLER)
    b = board(slot("front", 0, CORE), spare, gold=12, used=1)
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
    assert policy.deployment(apply_deployment(b, policy.deployment(b)[0])) == ()


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


def test_rank_can_use_the_formal_a7_name_when_the_badge_is_missed():
    frame = Frame(CANVAS, labels(("资本帝王1", 160, 322)))
    assert frame.rank_tier == 7


def test_standard_encounter_uses_the_first_card_and_its_own_two_column_receipt(monkeypatch, world):
    entries = (("遭遇节点", 960, 98), ("遭遇其一", 666, 390), ("遭遇其二", 1252, 390),
               ("选择", 1084, 899))
    initial = page(Page.CHOICE, *entries, choice="遭遇节点")
    chosen = page(Page.CHOICE, *entries, choice="遭遇节点")
    chosen.image = CANVAS.copy()
    draw = ImageDraw.Draw(chosen.image)
    draw.rectangle((486, 370, 491, 690), fill="white")
    draw.rectangle((844, 370, 848, 690), fill="white")
    draw.rectangle((1007, 880, 1164, 920), fill="white")
    assert not initial.choice_confirm() and chosen.choice_confirm()
    assert chosen.choice_selected(initial, (666, 390))
    assert not chosen.choice_selected(initial, (1252, 390))
    after = page(Page.BOARD, stage="1-7")
    routes = {(initial, (666, 390)): chosen, (chosen, (1084, 899)): after}
    state = drive(monkeypatch, world, initial, lambda s, point: setattr(s, "frame", routes[s.frame, point]))
    assert world.war._choose(initial) is after
    assert state.clicks == [(Page.CHOICE, (666, 390)), (Page.CHOICE, (1084, 899))]


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


def test_high_reward_space_preserves_equipment_and_a_spare_healer_when_needed(high_lineup):
    b = board(slot("front", 0, CORE), slot("back", 0, BAILU),
              slot("back", 1, policy.Unit("真珠", False, True, 1, equipment=1)),
              slot("bench", 0, policy.Unit("娜塔莎", False, True, 1, equipment=0)),
              slot("bench", 1, policy.Unit("风堇", False, True, 1, equipment=1)),
              slot("bench", 2, policy.Unit("藿藿", False, True, 1, equipment=0)),
              lineup=high_lineup, stage="3-1", used=3, capacity=3)
    assert policy.disposable_bench(b) == (b.slots[3],)
    without_pearl = replace(b, slots=(*b.slots[:2], *b.slots[3:]), used=2)
    assert policy.disposable_bench(without_pearl) == ()


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
    monkeypatch.setattr(f, "slots", lambda: tuple(slot("back", i, occupied=True) for i in range(11)))
    assert f.capacity == (11, 11)
    bad = Frame(CANVAS, markup)
    monkeypatch.setattr(bad, "read_local", f.read_local)
    monkeypatch.setattr(bad, "slots", lambda: tuple(slot("back", i, occupied=True) for i in range(10)))
    assert bad.capacity != (11, 11)


def test_high_halo_can_spend_a_verified_paid_reroll_below_low_rank_reserve(monkeypatch, world, high_lineup):
    world.war.lineup = high_lineup
    core = slot("front", 0, CORE)
    world.war.halo_candidate = (core, ui.np.zeros((12, 12, 3), dtype=ui.np.uint8))
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
    for current in (before, rolled, selected):
        monkeypatch.setattr(current, "halo_portrait_matches", lambda *_: True)
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


def test_preselected_investment_uses_confirmed_column_not_a_different_preference(monkeypatch, world, high_lineup):
    world.war.lineup = high_lineup
    image = CANVAS.copy()
    draw = ImageDraw.Draw(image)
    draw.rectangle((768, 404, 774, 756), fill=(203, 203, 203))
    draw.rectangle((1146, 404, 1152, 756), fill=(203, 203, 203))
    draw.rectangle((917, 972, 1040, 997), fill=(185, 185, 185))
    frame = Frame(image, labels(("请选择投资策略", 961, 167), ("简单模式", 460, 541),
                                ("敌人难度降低3", 460, 590), ("采购专员·彩", 960, 542),
                                ("每5次刷新", 955, 590), ("确认", 979, 984)))
    assert frame.page == Page.CHOICE
    assert frame.selected_investment_column() == 1
    assert world.war._choice_option(frame).text == "简单模式"
    after = page(Page.BOARD, stage="2-2")
    state = drive(monkeypatch, world, frame, lambda s, _: setattr(s, "frame", after))
    assert world.war._choose(frame) is after
    assert state.clicks == [(Page.CHOICE, (979, 984))]


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
    team = board(*units, stage=stage, used=1, gold=5)
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
def test_uncertain_transition_never_replays_and_fatal_path_saves_evidence(monkeypatch, world, eventual_settlement):
    initial = page(Page.RANK)
    board_frame = page(Page.BOARD, stage="1-2")
    unknown = page(Page.UNKNOWN, stage="1-2")
    result = page(Page.MATCH_RESULT)
    lobby = home()
    actions = []

    def step(frame):
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
    if eventual_settlement:
        assert world.war.start() is False
        assert actions == [Page.BOARD, Page.MATCH_RESULT] and world.war.result is False
        task.save_error_screenshot.assert_not_called()
    else:
        with pytest.raises(task.CurrencyWarsReceiptTimeout, match="后续动画未确认"):
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
    assert world.war._check_weekly_reward(lobby) == (lobby, None, False)
    assert world.war._check_weekly_reward(lobby) == (lobby, None, False)
    assert state.clicks.count((Page.WEEKLY, (1640, 728))) == 1
    assert state.keys == [(Page.WEEKLY, "esc")] * 2
    world.cfg.save_timestamp.assert_not_called()


def test_halo_refresh_timeout_uses_a_confirmed_backup_without_spending_again(monkeypatch, world):
    stage = "2-5"
    world.war.last_result_stage = stage
    world.war.halo_candidate = slot("front", 0, CORE), None
    refresh = ("刷新", 468, 770)
    common = (("闭关", 1480, 435), ("免费刷新还剩2次", 958, 134))
    initial = page(Page.HALO, ("乱披风拳法", 420, 435), refresh, *common, halo_gold=0)
    cards = (("前台专家", 420, 435), ("提高前台强度", 420, 545), *common)
    current = page(Page.HALO, *cards, halo_gold=0)
    selected = page(Page.HALO, *cards, ("确认", 960, 948), halo_gold=0)
    returned = page(Page.BOARD, stage=stage)
    for frame in (initial, current, selected):
        monkeypatch.setattr(frame, "halo_portrait_matches", lambda point, _: point == ui.HALO_TARGET)
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


def test_capture_retries_a_transient_screenshot_timeout_without_input(monkeypatch, world):
    expected = page(Page.BOARD, stage="1-2")
    capture = Mock(side_effect=(RuntimeError("截图超时"), expected))
    monkeypatch.setattr(world.war, "_capture", capture)
    assert world.war._observe() is expected
    assert capture.call_count == 2
    world.auto.click_element_with_pos.assert_not_called()
    world.auto.press_key.assert_not_called()
