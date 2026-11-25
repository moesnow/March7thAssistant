from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

from PIL import Image
import pytest

from module.automation import automation
from module.automation.input_base import record_input_dispatch
from tasks.base import task_steps
from tasks.daily import daily, ember_exchange, redemption, synthesis
from tasks.daily.ember_exchange import EmberExchange
from tasks.daily.training import DailyTrainingError
from tasks.power import instance, power, readout, supplement
from tasks.power.policy import ECHO, GOLDEN_CALYX, ORNAMENT, PowerError, SupportDemand
from tasks.reward import message, receipt


def ocr_lines(texts):
    return [
        ([(x, 0), (x + 30, 0), (x + 30, 16), (x, 16)], (text, 0.99))
        for x, text in enumerate(texts, 1)
    ]


@pytest.mark.parametrize("name,first,second,offset", [
    ("message_reply", (230, 30), (40, 135), (0, 0)),
    ("message_sticker", (40, 135), (230, 30), (83, 93)),
])
def test_pc_message_clicks_first_detected_option(monkeypatch, name, first, second, offset):
    path = Path(message.Message._REPLY_ASSETS) / f"{name}.png"
    with Image.open(path) as asset:
        template = asset.convert("RGB")
    frame = Image.new("RGB", (380, 220), "black")
    frame.paste(template, first)
    frame.paste(template, second)
    origin = (730, 640)
    monkeypatch.setattr(message.auto, "take_screenshot", Mock(return_value=(frame, (*origin, *frame.size), 1)))
    monkeypatch.setattr(message.auto, "screenshot", frame)
    monkeypatch.setattr(message.auto, "screenshot_pos", (*origin, *frame.size), raising=False)
    monkeypatch.setattr(message.auto, "screenshot_scale_factor", 1, raising=False)
    monkeypatch.setattr(message.auto, "_is_debug_enabled", lambda: False)
    monkeypatch.setattr(automation, "get_ui_profile",
                        lambda _cfg: SimpleNamespace(name="pc_1080", resolve_image_path=lambda path: path))
    click = Mock(return_value=True)
    monkeypatch.setattr(message.auto, "click_element_with_pos", click)

    assert message.Message._reply()
    x, y = origin[0] + first[0], origin[1] + first[1]
    click.assert_called_once_with(((x, y), (x + template.width, y + template.height)), offset=offset)


@pytest.mark.parametrize("texts,expected", [
    (["252/3", "合成数量：1", "84", "+"], True),
    (["4929/3", "合成数量：1", "1643", "+"], True),
    (["164/3", "合成数量：1", "54", "+"], True),
    (["252/3", "合成数量：2", "84", "+"], False),
    (["2/3", "合成数量：1"], False),
    (["252/30", "合成数量：1"], False),
])
def test_pc_training_recipe_keeps_quantity_and_material_boxes_separate(monkeypatch, texts, expected):
    auto = Mock(ocr_result=ocr_lines(texts))
    auto.find_element.return_value = True
    monkeypatch.setattr(synthesis, "auto", auto)
    assert synthesis.Synthesis._verify_training_recipe() is expected


@pytest.fixture
def meter_ocr(monkeypatch):
    recognize = Mock()
    monkeypatch.setattr(readout.ocr, "recognize_multi_lines", recognize)
    monkeypatch.setattr(readout.time, "sleep", Mock())
    monkeypatch.setattr(instance.auto, "take_screenshot", Mock(return_value=(Image.new("RGB", (315, 75)), None, 1)))
    return recognize


@pytest.mark.parametrize("texts,expected", [
    (["300/300", "十"], 300),
    (["127/300十"], 127),
    (["满", "300/300"], 300),
    (["满300/300"], 300),
    (["5", "25/300"], 25),
    (["410", "／300", "十"], 410),
    (["0/300"], 0),
    (["?2301300十"], 230),
])
def test_pc_power_meter_reads_balance_without_gluing_adjacent_digits(monkeypatch, meter_ocr, texts, expected):
    meter_ocr.return_value = ocr_lines(texts)
    monkeypatch.setattr(power, "screen", Mock())
    assert power.Power.get() == expected


def test_map_uses_same_meter_with_plus_read_as_cross(monkeypatch, meter_ocr):
    meter_ocr.return_value = ocr_lines(["127/300", "十"])
    monkeypatch.setattr(power, "screen", Mock())
    assert power.Power.get() == 127


def test_pc_echo_quota_ignores_neighboring_numbers(monkeypatch, meter_ocr):
    meter_ocr.return_value = ocr_lines(["本周剩余奖励次数", "2/3", "14"])
    monkeypatch.setattr(instance.Instance, "select_category", Mock())
    assert instance.Instance.read_echo_rewards() == 2


@pytest.mark.parametrize("waves", [1, 5, 21])
def test_fixed_challenge_starts_at_one_without_reading_wave_or_payment(monkeypatch, meter_ocr, waves):
    plus = ((1810, 875), (1840, 905))
    find = Mock(return_value=plus)
    click = Mock(return_value=True)
    monkeypatch.setattr(instance.auto, "find_element", find)
    monkeypatch.setattr(instance.auto, "click_element_with_pos", click)

    assert instance.Instance.select_waves(GOLDEN_CALYX, waves) == waves
    meter_ocr.assert_not_called()
    assert find.call_count == (0 if waves == 1 else 1)
    assert click.call_args_list == [call(plus)] * (waves - 1)


def test_single_challenge_without_wave_selector_does_not_read_ocr(monkeypatch, meter_ocr):
    monkeypatch.setattr(instance.auto, "find_element", Mock(return_value=None))
    assert instance.Instance.select_waves(ECHO, 3) == 1
    meter_ocr.assert_not_called()


@pytest.mark.parametrize("codes,expected", [([], True), (["USED"], True), (OSError("offline"), False)])
def test_daily_preparation_distinguishes_no_new_codes_from_a_read_failure(monkeypatch, codes, expected):
    cfg = SimpleNamespace(cloud_game_enable=True, already_used_codes=["USED"], reward_enable=True,
                          reward_redemption_code_enable=True, power_enable=False,
                          build_target_enable=False, activity_enable=False)
    monkeypatch.setattr(daily, "cfg", cfg)
    monkeypatch.setattr(redemption, "cfg", cfg)
    monkeypatch.setattr(daily.activity, "start", Mock(return_value=True))
    fetch = Mock(side_effect=codes) if isinstance(codes, Exception) else Mock(return_value=codes)
    monkeypatch.setattr(redemption, "valid_codes_for_server", fetch)
    redeem = Mock()
    monkeypatch.setattr(redemption.Redemption, "start", redeem)
    monkeypatch.setattr(task_steps, "screen", Mock())

    assert daily.Daily.prepare_daily() is expected
    redeem.assert_not_called()


@pytest.mark.parametrize("handled,expected", [(["EXPIRED", "REDEEMED"], True), (["REDEEMED"], False)])
def test_automatic_redemption_requires_a_confirmed_outcome_for_each_code(monkeypatch, handled, expected):
    cfg = SimpleNamespace(cloud_game_enable=True, already_used_codes=[])
    monkeypatch.setattr(redemption, "cfg", cfg)
    codes = ["EXPIRED", "REDEEMED"]
    monkeypatch.setattr(redemption, "valid_codes_for_server", Mock(return_value=codes))

    def redeem(*, codes, send_notification):
        cfg.already_used_codes = handled
        return "REDEEMED" in handled

    monkeypatch.setattr(redemption.Redemption, "start", redeem)
    assert redemption.Redemption.get() is expected


@pytest.mark.parametrize("rewards_ok", [True, False])
def test_pc_daily_claims_regular_rewards_before_training_and_recovers(monkeypatch, rewards_ok):
    calls = Mock()
    calls.rewards.return_value = rewards_ok
    calls.training.return_value = True
    monkeypatch.setattr(daily.reward, "start", calls.rewards)
    monkeypatch.setattr(daily.Daily, "run", calls.training)
    monkeypatch.setattr(task_steps, "screen", SimpleNamespace(change_to=calls.recover))

    assert daily.Daily.run_standalone() is rewards_ok
    expected = ["rewards", "training"] if rewards_ok else ["rewards", "recover", "training"]
    assert [call[0] for call in calls.mock_calls] == expected


def test_standalone_power_still_succeeds_when_optional_support_cards_cannot_be_read(monkeypatch):
    scan = Mock(side_effect=DailyTrainingError("未识别到实训任务卡片"))
    monkeypatch.setattr(daily.Quest, "scan", scan)
    monkeypatch.setattr(daily, "cfg", SimpleNamespace(daily_enable=True, borrow_enable=True, borrow_character_enable=False))
    monkeypatch.setattr(power, "cfg", SimpleNamespace(power_plan=[], instance_type=GOLDEN_CALYX,
                        instance_names={GOLDEN_CALYX: "回忆之蕾"}, build_target_enable=False))
    recover = Mock()
    monkeypatch.setattr(task_steps, "screen", SimpleNamespace(change_to=recover))
    farm = Mock(return_value=4)
    monkeypatch.setattr(power.Power, "process", farm)

    assert power.Power.run(skip_weekly_cleanup=True) is True

    scan.assert_called_once_with(collect=False)
    recover.assert_not_called()
    farm.assert_called_once()
    assert farm.call_args.args == (GOLDEN_CALYX, "回忆之蕾")
    assert not farm.call_args.kwargs["support"].pending


def test_exhausted_ember_quota_is_sold_out(monkeypatch):
    item = EmberExchange.ITEMS[0]
    frame = Mock(ocr_result=ocr_lines(["超值", f"可兑换：0/{item.exchange_limit}"]))
    monkeypatch.setattr(ember_exchange, "auto", frame)
    monkeypatch.setattr(EmberExchange, "_build_item_info_crop", Mock())

    assert EmberExchange._inspect_item_info(item, None, accept_sold_out=True) == {
        "status": EmberExchange.RESULT_SOLD_OUT,
    }


@pytest.mark.parametrize("outcome,expected", [(EmberExchange.RESULT_SOLD_OUT, True), (EmberExchange.RESULT_FAILED, False)])
def test_ember_exchange_keeps_confirmed_progress_and_reports_partial_failure(monkeypatch, outcome, expected):
    items = EmberExchange.ITEMS[:2]
    options = {item.enable_key: True for item in items}
    cfg = SimpleNamespace(get_value=options.get, refresh_hour=4, save_timestamp=Mock())
    monkeypatch.setattr(ember_exchange, "cfg", cfg)
    monkeypatch.setattr(ember_exchange.Date, "is_next_month_x_am", Mock(return_value=True))
    monkeypatch.setattr(EmberExchange, "_navigate_to_ember_exchange", Mock(return_value=True))
    monkeypatch.setattr(EmberExchange, "_restore_main_screen", Mock(return_value=True))
    monkeypatch.setattr(EmberExchange, "_purchase_item", Mock(side_effect=[EmberExchange.RESULT_SUCCESS, outcome]))

    assert EmberExchange.start() is expected
    finished = [call.args[0] for call in cfg.save_timestamp.call_args_list]
    assert finished == [item.timestamp_key for item in (items if expected else items[:1])]


def _receipt_title_fits(crop):
    # 720p 委托的「获得物品」截图中，标题延伸至画面高度的约 22% 处。
    x, y, width, height = crop
    return x <= 0.46 and x + width >= 0.54 and y <= 0.18 and y + height >= 0.22


def test_reward_receipt_can_see_the_full_title(monkeypatch):
    find = Mock(side_effect=lambda target, kind, **kwargs: _receipt_title_fits(kwargs["crop"]))
    monkeypatch.setattr(receipt, "auto", SimpleNamespace(find_element=find))
    receipt.confirm_item_reward("委托奖励")
    assert find.call_args.args == ("获得物品", "text")


@pytest.mark.parametrize("dropped_dismissal,late_receipt,receipt_delay,return_delay,return_screen", [
    (False, False, 0, 0, "map"), (True, False, 0, 0, "map"), (False, True, 0, 0, "guide3"),
    (True, True, 0, 2.5, "guide3"), (False, True, 0, 2.5, "map"), (False, False, 2.5, 0, "map"),
])
def test_power_supplement_closes_visible_reward_and_reads_the_actual_balance_once(
    monkeypatch, dropped_dismissal, late_receipt, receipt_delay, return_delay, return_screen,
):
    original = SimpleNamespace(use_reserved_trailblaze_power=True, use_fuel=False)
    auto = Mock(input_handler=SimpleNamespace(reports_dispatch=True), screenshot=SimpleNamespace(width=1280))
    page = return_screen
    now = 0.0
    receipt_at = 0.0
    return_at = 0.0
    dismissals = 0
    receipt_checks = 0

    def sleep(seconds):
        nonlocal now, page
        now += seconds
        if page == "awaiting_receipt" and now >= receipt_at:
            page = "receipt"
        if page == "transition" and now >= return_at:
            page = return_screen

    def find(text, kind, *_args, crop=None, **kwargs):
        nonlocal receipt_checks
        if kind == "image":
            return ((497, 290), (603, 360))
        if text == "获得物品":
            receipt_checks += 1
            if page == "awaiting_receipt":
                sleep((kwargs["max_retries"] - 1) * kwargs["retry_delay"])
            if page == "receipt" and _receipt_title_fits(crop) and (not late_receipt or receipt_checks > 1):
                return text
            return None
        if text == "开拓力补充":
            return text if page == "supplement" else None
        if text == "取消":
            return text if page == "supplement" else None
        return text

    def click(target):
        nonlocal page, dismissals, receipt_at, return_at
        if target == "入口":
            page = "supplement"
        elif target == "确认":
            if page == "supplement":
                page = "amount"
            elif receipt_delay:
                receipt_at = now + receipt_delay
                page = "awaiting_receipt"
            else:
                page = "receipt"
            record_input_dispatch(supplement.time.monotonic())
        elif target == supplement._crop((640, 569, 0, 0)):
            assert page == "receipt"
            dismissals += 1
            if not dropped_dismissal or dismissals == 2:
                if return_delay:
                    return_at = now + return_delay
                    page = "transition"
                else:
                    page = "supplement"
        elif target == "取消":
            assert page == "supplement"
            page = return_screen
        return target != "确认" or page == "amount"

    auto.find_element.side_effect = find
    auto.click_element_with_pos.side_effect = click
    screen = Mock(check_screen=Mock(side_effect=lambda target: target == page))
    stock = Mock(side_effect=[20])
    monkeypatch.setattr(supplement, "read_number", stock)
    monkeypatch.setattr(supplement, "time", SimpleNamespace(monotonic=lambda: now, sleep=sleep))

    read_balance = Mock(return_value=317)
    assert supplement.supplement(auto, screen, original, 300, Mock(return_value="入口"),
                                 read_balance, return_screen=return_screen, desktop=return_screen == "map") == 317
    assert dismissals == (2 if dropped_dismissal else 1)
    assert page == return_screen
    assert auto.click_element_with_pos.call_args_list.count(call("确认")) == 2
    auto.press_key.assert_not_called()
    read_balance.assert_called_once_with()
    stock.assert_called_once()


@pytest.mark.parametrize("remaining_checks,attempts", [([False], 1), ([True, False], 2), ([True, True, True], 3)])
def test_weekly_divergent_checks_quota_and_keeps_its_retry_budget(monkeypatch, remaining_checks, attempts):
    session = Mock()
    session.check_divergent_universe_score.return_value = False
    session.start.return_value = False
    monkeypatch.setattr(daily, "DivergentUniverse", Mock(return_value=session))
    monkeypatch.setattr(daily, "cfg", SimpleNamespace(weekly_divergent_timestamp=0, refresh_hour=4))
    monkeypatch.setattr(daily.Date, "is_next_mon_x_am", Mock(side_effect=remaining_checks))

    assert daily.Daily._run_weekly_divergent() is (not remaining_checks[-1])
    assert session.start.call_count == attempts


def test_missing_anchors_do_not_abort_when_navigation_is_ready(monkeypatch):
    screen = Mock()
    monkeypatch.setattr(instance, "screen", screen)
    monkeypatch.setattr(instance.Instance, "_detect_space_anchor", Mock(return_value=False))

    instance.Instance.heal_teams()

    assert screen.change_to.call_args_list == [call("map"), call("universe_main"), call("map"), call("main")]


@pytest.mark.parametrize("challenge_screen_ready, start_popup", [(True, False), (True, True), (False, False)])
def test_ornament_missing_optional_preset_resumes_only_on_challenge_screen(monkeypatch, challenge_screen_ready, start_popup):
    auto = Mock()
    start_button = ((1720, 985), (1800, 1005))

    def find(target, kind, *args, **kwargs):
        if kind == "image_count":
            return 0
        if target == "开始挑战":
            if challenge_screen_ready and (start_popup or not auto.click_element_with_pos.called):
                return start_button
            return None
        return start_popup and "仍有角色位空缺" in target

    def click_start(coordinates):
        auto.press_key.assert_called_once_with("esc")
        assert coordinates == start_button
        return True

    auto.click_element.side_effect = lambda target, *_args, **_kwargs: target != "队伍6"
    auto.click_element_with_pos.side_effect = click_start
    auto.find_element.side_effect = find
    monkeypatch.setattr(instance, "auto", auto)
    monkeypatch.setattr(instance, "cfg", SimpleNamespace(instance_team_enable=True, borrow_enable=False))
    monkeypatch.setattr(instance, "time", SimpleNamespace(sleep=Mock()))
    monkeypatch.setattr(instance.Instance, "get_target_team", Mock(return_value=6))
    monkeypatch.setattr(instance, "drag_list", Mock(return_value=False))
    engage = Mock()
    monkeypatch.setattr(instance.Instance, "_engage_ornament_boss", engage)

    def start():
        return instance.Instance.start_instance(ORNAMENT, "浴火钢心", SupportDemand(), practice=False, world_team=False)

    if challenge_screen_ready:
        assert start() is False
        auto.click_element_with_pos.assert_called_once_with(start_button)
        engage.assert_called_once()
    else:
        with pytest.raises(PowerError, match="未能返回饰品提取挑战页"):
            start()
        engage.assert_not_called()
        auto.click_element_with_pos.assert_not_called()
    auto.press_key.assert_called_once_with("esc")
