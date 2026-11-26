from types import SimpleNamespace
from unittest.mock import Mock, call

import numpy as np
from PIL import Image
import pytest

from module.automation import automation
from module.automation.input_base import limit_input_deadline
from module.localization import tr
from tasks.touch import ornament, power, rewards
from tasks.power import readout, supplement
from tasks.power.policy import plan_paid_batch
from utils.pause import RunStopRequested


@pytest.fixture(autouse=True)
def recorded_power(monkeypatch):
    monkeypatch.setattr(power, "save_reading", Mock())


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


def test_ornament_inventory_combines_split_ocr_in_screen_order(monkeypatch):
    monkeypatch.setattr(power.auto, "take_screenshot", Mock(return_value=(Image.new("RGB", (40, 20)), None, 1)))
    ocr = Mock(return_value=[_line("／１２", 32, 0), _line("１０", 0, 4)])
    monkeypatch.setattr(readout.ocr, "recognize_multi_lines", ocr)
    assert readout.read_immersifier_stock(power.auto, ornament.INDEX_IMMERSIFIERS) == 10
    ocr.assert_called_once()


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


@pytest.mark.parametrize(
    "start_page, target_page, panel_delay, missed, deadline, stop, expected_drags, expected_error",
    [
        (0, 0, 1.2, (), None, False, [], None),
        (1, 0, 0, (), None, False, [True, True, True, False, False], None),
        (0, 1, 0, (1,), None, False, [True, True], None),
        (0, 0, 300, (), None, False, [], "未能确认侵蚀隧洞列表"),
        (0, 1, 0, (), 1, False, [True], "生存索引查找副本超时"),
        (0, 1, 0, (), None, True, [True], None),
    ],
    ids=["late-panel", "target-above-viewport", "missed-drag", "panel-never-switched",
         "deadline-during-drag", "stop-during-drag"],
)
def test_touch_power_reentry_search(monkeypatch, start_page, target_page, panel_delay, missed, deadline, stop,
                                    expected_drags, expected_error):
    name = "密伶之径"
    page = start_page
    now = 0.0
    drags = []
    visible = []
    auto = Mock()
    nav = Mock()

    def sleep(seconds):
        nonlocal now
        now += seconds

    def capture(*, crop):
        nonlocal visible
        assert crop == power.INDEX_ROWS
        if now < panel_delay:
            visible = [_line("角色培养", 130, 45), _line("进入", 640, 59), _line("隧洞遗器推荐", 130, 245)]
            hue = 0
        else:
            title = name if page == target_page else "霜风之径"
            visible = [_line(title, 130, 45), _line("进入", 640, 59)]
            hue = 60 + page * 60
        auto.screenshot = Image.new("RGB", (60, 40), (hue,) * 3)
        return auto.screenshot, (438, 170, 730, 453), 1

    def read():
        auto.ocr_result = visible

    def drag(start, end, *_):
        nonlocal page
        down = end[1] < start[1]
        drags.append(down)
        if len(drags) not in missed:
            page = min(2, max(0, page + (1 if down else -1)))
        return True

    auto.take_screenshot = capture
    auto.perform_ocr = read
    auto.drag_mouse = drag
    auto.calculate_text_position.return_value = (1098, 238)
    clock = SimpleNamespace(monotonic=lambda: now, sleep=sleep)
    monkeypatch.setattr(power, "auto", auto)
    monkeypatch.setattr(power, "screen", nav)
    monkeypatch.setattr(power, "time", clock)
    monkeypatch.setattr("tasks.base.list_drag.time", clock)
    monkeypatch.setattr("utils.wait.time", clock)

    def check_stop():
        if stop and drags:
            raise RunStopRequested()

    monkeypatch.setattr(power.pause_ctl, "check_stop", check_stop)
    with limit_input_deadline(deadline):
        if stop:
            with pytest.raises(RunStopRequested):
                power._reenter_instance(power.CAVERN, name)
        elif expected_error:
            with pytest.raises(power.PowerError, match=expected_error):
                power._reenter_instance(power.CAVERN, name)
        else:
            power._reenter_instance(power.CAVERN, name)

    if stop or expected_error:
        auto.click_element_with_pos.assert_not_called()
    else:
        auto.calculate_text_position.assert_called_once_with(_line("进入", 640, 59)[0], False)
        auto.click_element_with_pos.assert_called_once_with((1098, 238))
    nav.change_to.assert_called_once_with("guide3", max_recursion=1)
    assert drags == expected_drags


@pytest.mark.parametrize(("kind", "name"), [
    (power.ECHO, "铁骸的锈冢"),
    (power.CAVERN, "密伶之径"),
    (power.CRIMSON_CALYX, "支援舱段"),
    (power.ORNAMENT, "浴火钢心"),
])
def test_touch_entry_confirms_the_target_title_after_transition(monkeypatch, kind, name):
    """副本图标不可靠时，等待转场并处理传送提示，只识别一次确认成功的副本名。"""
    auto = Mock()
    nav = Mock(current_screen=None)
    enter = Mock()
    confirm = Mock(return_value=True)
    attempts = 0
    now = 0.0
    title = power.get_raw_instance_names()[kind][name] if kind == power.CRIMSON_CALYX else name
    crop = power.ORNAMENT_TITLE if kind == power.ORNAMENT else power.INSTANCE_TITLE

    def locate(text, mode, **kwargs):
        nonlocal attempts
        assert mode == "text", "进入副本应直接读取副本标题"
        if text == title:
            assert kwargs["crop"] == crop
            attempts += 1
            return attempts >= 3
        assert kwargs["crop"] == power.DIALOG
        return attempts == 1

    def sleep(seconds):
        nonlocal now
        now += seconds

    auto.find_element.side_effect = locate
    monkeypatch.setattr(power, "auto", auto)
    monkeypatch.setattr(power, "screen", nav)
    monkeypatch.setattr(power, "_click_instance_entry", enter)
    monkeypatch.setattr(power, "_click_text", confirm)
    monkeypatch.setattr("utils.wait.time", SimpleNamespace(monotonic=lambda: now, sleep=sleep))

    power._enter_instance(kind, name)

    assert attempts == 3
    assert nav.current_screen == power.INSTANCES[kind][0]
    enter.assert_called_once_with(kind, name)
    confirm.assert_called_once_with("确认", power.DIALOG_CONFIRM)
    nav.check_screen.assert_not_called()


@pytest.mark.parametrize("stop", [False, True], ids=["title-unavailable", "user-stop"])
def test_touch_entry_does_not_accept_an_unconfirmed_title(monkeypatch, stop):
    auto = Mock()
    nav = Mock(current_screen=None)
    enter = Mock()
    now = 0.0

    def sleep(seconds):
        nonlocal now
        now += seconds

    def locate(*args, **kwargs):
        if stop:
            raise RunStopRequested()
        return None

    auto.find_element.side_effect = locate
    monkeypatch.setattr(power, "auto", auto)
    monkeypatch.setattr(power, "screen", nav)
    monkeypatch.setattr(power, "_click_instance_entry", enter)
    monkeypatch.setattr(power, "ENTRY_TIMEOUT", 2)
    monkeypatch.setattr("utils.wait.time", SimpleNamespace(monotonic=lambda: now, sleep=sleep))

    error = RunStopRequested if stop else power.PowerError
    with pytest.raises(error):
        power._enter_instance(power.ECHO, "铁骸的锈冢")

    assert nav.current_screen is None
    enter.assert_called_once_with(power.ECHO, "铁骸的锈冢")
    auto.click_element.assert_not_called()
    auto.click_element_with_pos.assert_not_called()


@pytest.mark.parametrize(("requested", "available", "stock", "batch"), [
    (6, 174, 10, (6, 0, 6)),
    (6, 174, 4, (6, 80, 4)),
    (6, 94, 0, (2, 80, 0)),
    (6, 39, 0, (0, 0, 0)),
    (2, 0, 6, (2, 0, 2)),
])
def test_ornament_batch_uses_immersifiers_first_and_fits_the_budget(requested, available, stock, batch):
    assert plan_paid_batch(requested, available, 40, immersifiers=stock) == batch


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
def test_ornament_final_batch_skips_result_balance_and_exits(monkeypatch, waves):
    config = SimpleNamespace(
        borrow_enable=False, instance_team_enable=False, use_reserved_trailblaze_power=False, use_fuel=False,
        power_plan=[[power.ORNAMENT, "浴火钢心", waves]], power_plan_keep=False, power_plan_continue=False,
        instance_names_challenge_count={}, set_value=Mock(),
    )
    monkeypatch.setattr(power, "cfg", config)
    monkeypatch.setattr(ornament, "cfg", config)
    monkeypatch.setattr(ornament, "screen", Mock())
    monkeypatch.setattr(power, "_select_category", Mock())
    monkeypatch.setattr(power, "_supplement", Mock())
    monkeypatch.setattr(power, "_enter_instance", Mock())
    monkeypatch.setattr(power, "_wait_battle", Mock())
    read_waves = Mock(side_effect=power.PowerError("结算波次 OCR 不可用"))
    monkeypatch.setattr(power, "read_number", read_waves)
    monkeypatch.setattr(ornament, "_start_challenge", Mock())
    monkeypatch.setattr(power, "_set_challenge_waves", Mock())
    stock = Mock(return_value=waves - 1)
    monkeypatch.setattr(ornament, "read_immersifier_stock", stock)
    balance = Mock(side_effect=[181, power.PowerError("读数失败")])
    monkeypatch.setattr(power, "read_power", balance)
    exit_result = Mock(return_value="main")
    monkeypatch.setattr(power, "_exit_result", exit_result)
    ornament.screen.change_to.side_effect = RuntimeError("重复截图失败")

    assert power.run()
    ornament.screen.change_to.assert_not_called()
    read_waves.assert_not_called()
    stock.assert_called_once_with(ornament.auto, ornament.INDEX_IMMERSIFIERS)
    balance.assert_called_once_with(ornament.INDEX_POWER)
    exit_result.assert_called_once_with(power.INSTANCES[power.ORNAMENT][0])
    config.set_value.assert_called_once_with("power_plan", [])


@pytest.mark.parametrize("use_fuel", [False, True], ids=["no-supplement", "supplement-entry-miss"])
def test_touch_power_plan_records_the_selected_batch_on_victory(monkeypatch, use_fuel):
    cfg = SimpleNamespace(
        power_plan=[[power.GOLDEN_CALYX, "回忆之蕾", 4]], power_plan_keep=False,
        power_plan_continue=False, instance_names_challenge_count={}, set_value=Mock(),
        use_reserved_trailblaze_power=False, use_fuel=use_fuel,
    )
    read_waves = Mock(side_effect=power.PowerError("结算波次 OCR 不可用"))
    start = Mock(return_value=(4, False))
    monkeypatch.setattr(power, "cfg", cfg)
    monkeypatch.setattr(power, "screen", Mock(check_screen=Mock(return_value=True)))
    monkeypatch.setattr(power, "auto", Mock(find_element=Mock(return_value=None)))
    monkeypatch.setattr(power, "_select_category", Mock())
    monkeypatch.setattr(power, "_enter_instance", Mock())
    monkeypatch.setattr(power, "_start_challenge", start)
    monkeypatch.setattr(power, "_wait_battle", Mock())
    monkeypatch.setattr(power, "_exit_result", Mock(return_value="main"))
    power.screen.change_to.side_effect = RuntimeError("重复截图失败")
    monkeypatch.setattr(power, "read_number", read_waves)
    balance = Mock(side_effect=[86, power.PowerError("余额读数失败")])
    monkeypatch.setattr(power, "read_power", balance)

    summary = Mock()
    assert power.run(on_summary=summary)
    power.screen.change_to.assert_not_called()
    summary.assert_called_once_with(tr("已完成 {count} 次挑战").format(count=4))
    cfg.set_value.assert_called_once_with("power_plan", [])
    start.assert_called_once()
    power._exit_result.assert_called_once_with("calyx")
    balance.assert_called_once_with()
    read_waves.assert_not_called()
    assert power.screen.check_screen.call_args_list == ([call("guide3")] * 3 if use_fuel else [])
    power.auto.click_element_with_pos.assert_not_called()


def test_touch_power_supplement_keeps_the_callers_frame_retry_window(monkeypatch):
    entry = (1720 / 1920, 55 / 1080, 0, 0)
    reserve = supplement._crop((528, 327, 0, 0))
    page = "guide3"
    now = 0.0
    frame = Image.new("RGB", (1280, 720))
    capture = object.__new__(automation.Automation)
    capture.window_title = "test-game"
    capture.logger = Mock()
    capture._is_debug_enabled = lambda: False

    def sleep(seconds):
        nonlocal now
        now += seconds

    def screenshot(*_args, **_kwargs):
        if page == "supplement" and now < 3:
            return False
        return frame, (0, 0, 1280, 720), 1

    def find(target, kind, **_kwargs):
        capture.take_screenshot()
        if kind == "crop" or page == "supplement":
            return target

    def click(target):
        nonlocal page
        if target == entry:
            page = "supplement"
        elif target == "取消":
            page = "guide3"

    clock = SimpleNamespace(monotonic=lambda: now, sleep=sleep)
    auto = Mock(find_element=Mock(side_effect=find), click_element_with_pos=Mock(side_effect=click))
    stock = Mock(return_value=0)
    cfg = SimpleNamespace(
        power_plan=[[power.GOLDEN_CALYX, "回忆之蕾", 3]], power_plan_keep=False, power_plan_continue=False,
        instance_names_challenge_count={}, set_value=Mock(), use_reserved_trailblaze_power=True, use_fuel=False,
    )
    monkeypatch.setattr(automation, "time", clock)
    monkeypatch.setattr(automation, "get_control_backend", lambda _cfg: "adb")
    monkeypatch.setattr(automation.Screenshot, "take_screenshot", screenshot)
    monkeypatch.setattr(supplement, "time", clock)
    monkeypatch.setattr(supplement, "read_number", stock)
    monkeypatch.setattr(power, "cfg", cfg)
    monkeypatch.setattr(power, "auto", auto)
    monkeypatch.setattr(power, "screen", Mock(check_screen=Mock(side_effect=lambda target: target == page)))
    monkeypatch.setattr(power, "read_power", Mock(return_value=34))
    monkeypatch.setattr(power, "_select_category", Mock())
    monkeypatch.setattr(power, "_enter_instance", Mock())
    monkeypatch.setattr(power, "_start_challenge", Mock(return_value=(3, False)))
    monkeypatch.setattr(power, "_wait_battle", Mock())
    monkeypatch.setattr(power, "_exit_result", Mock(return_value="main"))

    assert power.run()
    assert auto.click_element_with_pos.call_args_list == [call(entry), call(reserve), call("取消")]
    assert stock.call_args.args[1] == supplement._crop((492, 364, 72, 26))
    cfg.set_value.assert_called_once_with("power_plan", [])
    assert page == "guide3"


@pytest.mark.parametrize("supplement_mode", ["disabled", "success", "entry-miss"])
def test_touch_ornament_repeats_mixed_payment_and_keeps_unfunded_plan(monkeypatch, supplement_mode):
    instance_type, name = power.ORNAMENT, "浴火钢心"
    next_item = [power.GOLDEN_CALYX, "回忆之蕾", 1]
    config = SimpleNamespace(
        borrow_enable=False, instance_team_enable=False, use_reserved_trailblaze_power=False,
        use_fuel=supplement_mode != "disabled",
        power_plan=[[instance_type, name, 15], next_item], power_plan_keep=False, power_plan_continue=False,
        instance_names_challenge_count={instance_type: 6}, set_value=Mock(),
    )
    for module in (power, ornament):
        monkeypatch.setattr(module, "cfg", config)
        monkeypatch.setattr(module, "screen", Mock(current_screen=power.INSTANCES[instance_type][0]))
    monkeypatch.setattr(power, "_select_category", Mock())
    monkeypatch.setattr(power, "_enter_instance", Mock())
    monkeypatch.setattr(power, "_wait_battle", Mock())
    exit_result = Mock()
    monkeypatch.setattr(power, "_exit_result", exit_result)
    initial_power = 114 if supplement_mode == "success" else 174
    balance = Mock(side_effect=[initial_power, power.PowerError("重复读余额")])
    stock = Mock(side_effect=[10, power.PowerError("重复读库存")])
    fill = Mock(return_value=174)
    click = Mock(return_value=True)
    select = Mock()
    plan_batch = Mock(wraps=plan_paid_batch)
    monkeypatch.setattr(power, "read_power", balance)
    monkeypatch.setattr(power, "auto", Mock(click_element=Mock(return_value=True), find_element=Mock(return_value=False)))
    if supplement_mode == "success":
        monkeypatch.setattr(power, "_supplement", fill)
    monkeypatch.setattr(power, "_click_text", click)
    monkeypatch.setattr(power, "_set_challenge_waves", select)
    monkeypatch.setattr(ornament, "read_immersifier_stock", stock)
    monkeypatch.setattr(ornament, "_start_challenge", Mock(return_value=True))
    monkeypatch.setattr(ornament, "plan_paid_batch", plan_batch)

    assert power.run()
    assert config.set_value.call_args_list == [
        call("power_plan", [[instance_type, name, remaining], next_item]) for remaining in (9, 3, 1)
    ]
    assert plan_batch.call_args_list == [
        call(6, 174, 40, immersifiers=10),
        call(6, 174, 40, immersifiers=4),
        call(3, 94, 40, immersifiers=0),
        call(1, 14, 40, immersifiers=0),
    ]
    assert [args.args[0] for args in select.call_args_list] == [6, 2]
    click.assert_called_once_with("再来一次", power.REPEAT)
    balance.assert_called_once_with(ornament.INDEX_POWER)
    power.save_reading.assert_called_once_with(config, "overview_power", 14)
    stock.assert_called_once_with(ornament.auto, ornament.INDEX_IMMERSIFIERS)
    assert exit_result.call_count == 2
    assert fill.call_args_list == (
        [call(114, plus=(1510, 55), power_crop=ornament.INDEX_POWER)]
        if supplement_mode == "success" else []
    )
    assert power.screen.check_screen.call_args_list == ([call("guide3")] * 3 if supplement_mode == "entry-miss" else [])


@pytest.mark.parametrize("ocr_error", [False, True])
def test_unreadable_ornament_stock_uses_power_and_keeps_running_the_plan(monkeypatch, ocr_error):
    next_item = [power.GOLDEN_CALYX, "回忆之蕾", 1]
    config = SimpleNamespace(
        borrow_enable=False, instance_team_enable=False, use_reserved_trailblaze_power=False, use_fuel=False,
        power_plan=[[power.ORNAMENT, "浴火钢心", 1], next_item], power_plan_keep=False, power_plan_continue=False,
        instance_names_challenge_count={}, set_value=Mock(),
    )
    for module in (power, ornament):
        monkeypatch.setattr(module, "cfg", config)
    monkeypatch.setattr(ornament.auto, "take_screenshot", Mock(return_value=(Image.new("RGB", (70, 35)), None, 1)))
    recognition = Mock(return_value=[_line("174/300", 0, 0)],
                       side_effect=RuntimeError("OCR 执行失败") if ocr_error else None)
    monkeypatch.setattr(readout.ocr, "recognize_multi_lines", recognition)
    monkeypatch.setattr(readout.time, "sleep", Mock())
    monkeypatch.setattr(power, "_select_category", Mock())
    monkeypatch.setattr(power, "_enter_instance", Mock())
    monkeypatch.setattr(power, "_exit_result", Mock(return_value="main"))
    monkeypatch.setattr(power, "_set_challenge_waves", Mock())
    monkeypatch.setattr(power, "_wait_battle", Mock())
    monkeypatch.setattr(power, "read_power", Mock(side_effect=[45, 10]))
    monkeypatch.setattr(power, "_start_challenge", Mock(return_value=(1, False)))
    monkeypatch.setattr(ornament, "_start_challenge", Mock(return_value=True))

    assert power.run()
    assert recognition.call_count == (1 if ocr_error else 3)
    assert config.set_value.call_args_list == [call("power_plan", [next_item]), call("power_plan", [])]


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


@pytest.mark.parametrize("code", ["frame_clock_unavailable", "frame_timeout"])
def test_battle_resumes_after_temporary_frame_failure(monkeypatch, code):
    monkeypatch.setattr(power, "ensure_double_speed", Mock(return_value=True))
    poll = Mock(side_effect=[power.AdbError(code, "frame"),
                             ("battle", True), ("victory", None)])
    tap = Mock()
    monkeypatch.setattr(power, "_observe_battle", poll)
    monkeypatch.setattr(power, "_tap", tap)
    monkeypatch.setattr(power.time, "sleep", Mock())
    power._wait_battle()
    assert poll.call_count == 3
    tap.assert_not_called()


@pytest.mark.parametrize("code,polls", [("frame_timeout", 16), ("disconnected", 1), ("invalid_response", 1)])
def test_battle_reports_persistent_or_fatal_frame_failure(monkeypatch, code, polls):
    now = 0.0

    def sleep(_seconds):
        nonlocal now
        now += 1

    failure = power.AdbError(code, "frame")
    poll = Mock(side_effect=failure)
    tap = Mock()
    monkeypatch.setattr(power, "_observe_battle", poll)
    monkeypatch.setattr(power, "_tap", tap)
    monkeypatch.setattr(power.time, "monotonic", lambda: now)
    monkeypatch.setattr(power.time, "sleep", sleep)

    with pytest.raises(power.AdbError) as error:
        power._wait_battle(repeated=True)
    assert error.value is failure
    assert poll.call_count == polls
    tap.assert_not_called()


@pytest.mark.parametrize("code,recovered", [("frame_clock_unavailable", True), ("frame_timeout", True),
                                               ("disconnected", False)])
def test_speed_probe_recovers_transient_frame_errors(monkeypatch, code, recovered):
    speed = Mock(side_effect=power.AdbError(code, "frame"))
    observe = Mock(side_effect=[("battle", True), ("victory", None)])
    monkeypatch.setattr(power, "ensure_double_speed", speed)
    monkeypatch.setattr(power, "_observe_battle", observe)
    monkeypatch.setattr(power, "game_option_enabled", lambda *_: True)
    monkeypatch.setattr(power.time, "sleep", Mock())
    if recovered:
        power._wait_battle()
    else:
        with pytest.raises(power.AdbError) as error:
            power._wait_battle()
        assert error.value.code == code
    speed.assert_called_once_with(power.auto)
    assert observe.call_count == (2 if recovered else 1)


@pytest.mark.parametrize("saw_speed", [False, True])
def test_touch_repeat_requires_battle_evidence_without_observing_pause(monkeypatch, saw_speed):
    now = 0.0
    stale_results = ["victory", *(["occluded"] * 4), "victory"]
    next_battle = ["battle", "victory"] if saw_speed else []
    frames = iter(stale_results + next_battle)
    frame = None

    def sleep(seconds):
        nonlocal now
        now += seconds

    def find(target, *_args, **_kwargs):
        nonlocal frame
        if target == f"{power.IMAGES}/victory.png":
            frame = next(frames, "victory")
            return frame == "victory"
        return False

    auto = Mock(find_element=Mock(side_effect=find))
    monkeypatch.setattr(power, "auto", auto)
    monkeypatch.setattr(power, "_check_popup", Mock())
    monkeypatch.setattr(power, "battle_speed_visible", lambda _: frame == "battle")
    monkeypatch.setattr(power, "game_option_enabled", lambda *_args: False)
    monkeypatch.setattr(power, "ENTRY_TIMEOUT", 6)
    monkeypatch.setattr(power.time, "monotonic", lambda: now)
    monkeypatch.setattr(power.time, "sleep", sleep)
    if saw_speed:
        power._wait_battle(repeated=True)
        assert sum(check.args[0] == f"{power.IMAGES}/victory.png" for check in auto.find_element.call_args_list) == 8
    else:
        with pytest.raises(power.PowerError, match="未确认再来一次的结算"):
            power._wait_battle(repeated=True)
    auto.click_element.assert_not_called()


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


@pytest.mark.parametrize("planned,available", [(2, 53), (None, 23)])
@pytest.mark.parametrize("first_defeat", [False, True])
def test_repeat_stops_at_plan_count_or_calculated_budget(monkeypatch, planned, available, first_defeat):
    navigate = Mock()
    start = Mock(return_value=(1, False))
    wait = Mock(side_effect=([power.BattleDefeat("挑战失败")] if first_defeat else []) + [None, None])
    click = Mock(return_value=True)
    exit_result = Mock()
    monkeypatch.setattr(power, "screen", navigate)
    monkeypatch.setattr(power, "_select_category", Mock())
    monkeypatch.setattr(power, "cfg", SimpleNamespace(use_reserved_trailblaze_power=False, use_fuel=False,
                                                       instance_names_challenge_count={power.GOLDEN_CALYX: 1}))
    balance = Mock(side_effect=[available, power.PowerError("重复读余额")])
    monkeypatch.setattr(power, "read_power", balance)
    monkeypatch.setattr(power, "_enter_instance", Mock())
    monkeypatch.setattr(power, "_start_challenge", start)
    monkeypatch.setattr(power, "_wait_battle", wait)
    monkeypatch.setattr(power, "_click_text", click)
    monkeypatch.setattr(power, "_exit_result", exit_result)

    settlements = Mock()
    assert list(power._run_instance(power.GOLDEN_CALYX, "回忆之蕾", planned, on_settlement=settlements)) == [1, 1]
    assert settlements.call_args_list == [call(1, None)] * 2
    power.save_reading.assert_called_once_with(power.cfg, "overview_power", available - 20)
    balance.assert_called_once_with()
    assert start.call_args_list == [
        call(power.GOLDEN_CALYX, "回忆之蕾", 1, borrow_for_daily=False, practice=False,
             world_team=False, team_failure=None),
    ] * (1 + first_defeat)
    assert wait.call_args_list == [call(repeated=False, instance_screen="calyx", verify_team=False)] * (1 + first_defeat) + [
        call(repeated=True, instance_screen="calyx", verify_team=False),
    ]
    click.assert_called_once_with("再来一次", power.REPEAT)
    exit_result.assert_called_once_with("calyx")
    navigate.change_to.assert_called_once_with("main", max_recursion=1)


@pytest.mark.parametrize("planned", [None, 1])
def test_echo_without_weekly_rewards_only_fights_for_an_explicit_plan(monkeypatch, planned):
    enter = Mock()
    start = Mock(return_value=(1, False))
    supplement = Mock()
    config = SimpleNamespace(instance_names_challenge_count={}, save_timestamp=Mock())
    monkeypatch.setattr(power, "cfg", config)
    monkeypatch.setattr(power, "screen", Mock())
    monkeypatch.setattr(power, "_select_category", Mock())
    monkeypatch.setattr(power, "_read_echo_rewards", Mock(return_value=0))
    balance = Mock(side_effect=power.PowerError("余额读数失败"))
    monkeypatch.setattr(power, "read_power", balance)
    monkeypatch.setattr(power, "_supplement", supplement)
    monkeypatch.setattr(power, "_enter_instance", enter)
    monkeypatch.setattr(power, "_start_challenge", start)
    monkeypatch.setattr(power, "_wait_battle", Mock())
    monkeypatch.setattr(power, "_exit_result", Mock())

    assert list(power._run_instance(power.ECHO, "毁灭的开端", planned)) == ([1] if planned else [])
    balance.assert_not_called()
    supplement.assert_not_called()
    power.save_reading.assert_not_called()
    if planned:
        start.assert_called_once_with(power.ECHO, "毁灭的开端", 1, borrow_for_daily=False, practice=True,
                                      world_team=False, team_failure=None)
        config.save_timestamp.assert_called_once_with("echo_of_war_timestamp")
    else:
        enter.assert_not_called()
        start.assert_not_called()
        config.save_timestamp.assert_called_once_with("echo_of_war_timestamp")


@pytest.mark.parametrize("planned", [None, 3])
def test_echo_single_challenge_deducts_one_paid_wave_and_respects_weekly_rewards(monkeypatch, planned):
    config = SimpleNamespace(instance_names_challenge_count={}, save_timestamp=Mock(),
                             instance_team_enable=False, borrow_enable=False)
    confirm_practice = Mock()
    auto = Mock()
    auto.find_element.side_effect = lambda target, *_args, **_kwargs: None if target == "挑战次数" else ((1700, 970), (1780, 1010))
    monkeypatch.setattr(power, "cfg", config)
    monkeypatch.setattr(power, "auto", auto)
    monkeypatch.setattr(power, "screen", Mock())
    monkeypatch.setattr(power.time, "sleep", Mock())
    monkeypatch.setattr(power, "_select_category", Mock())
    quota = Mock(side_effect=[2, power.PowerError("结算后不应再识别额度")])
    monkeypatch.setattr(power, "_read_echo_rewards", quota)
    monkeypatch.setattr(power, "_supplement", lambda value, **_kwargs: value)
    balance = Mock(side_effect=[60, power.PowerError("重复读余额")])
    monkeypatch.setattr(power, "read_power", balance)
    monkeypatch.setattr(power, "_enter_instance", Mock())
    monkeypatch.setattr(power, "_wait_battle", Mock())
    monkeypatch.setattr(power, "_click_text", Mock(return_value=True))
    monkeypatch.setattr(power, "_exit_result", Mock())
    monkeypatch.setattr(power, "_confirm_echo_practice", confirm_practice)

    assert list(power._run_instance(power.ECHO, "毁灭的开端", planned)) == [1] * (planned or 2)
    balance.assert_called_once_with()
    quota.assert_called_once_with()
    assert [lookup.args[0] for lookup in auto.find_element.call_args_list] == ["挑战次数"] + ["开始挑战"] * (planned or 2)
    assert confirm_practice.call_args_list == ([call(required=True)] if planned else [])
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

    warning = Mock()
    monkeypatch.setattr(rewards.log, "warning", warning)
    monkeypatch.setattr(rewards.screen, "check_screen", Mock(return_value=False))
    dispatch.side_effect = rewards.RewardError("x")
    assert rewards.claim()
    warning.assert_called_once_with("委托奖励待核对：x")


@pytest.mark.parametrize("popup_visible", [False, True])
def test_reward_failure_only_dismisses_a_recognized_popup_then_continues(monkeypatch, popup_visible):
    monkeypatch.setattr(rewards, "cfg", SimpleNamespace(
        reward_dispatch_enable=True, reward_mail_enable=True, reward_assist_enable=False,
        reward_srpass_enable=False, reward_message_enable=False,
    ))
    calls = Mock()
    calls.dispatch.side_effect = rewards.RewardError("委托回执超时")
    calls.check_screen.return_value = popup_visible
    monkeypatch.setattr(rewards, "claim_dispatch", calls.dispatch)
    monkeypatch.setattr(rewards, "claim_mail", calls.mail)
    monkeypatch.setattr(rewards, "screen", SimpleNamespace(check_screen=calls.check_screen))
    monkeypatch.setattr(rewards, "_close_item_reward", calls.close)

    assert rewards.claim()

    expected = [call.dispatch(), call.check_screen("item_reward")]
    if popup_visible:
        expected.append(call.close())
    assert calls.mock_calls == [*expected, call.mail()]


def test_routine_joins_the_power_and_reward_summaries(monkeypatch):
    monkeypatch.setattr(rewards, "cfg", SimpleNamespace(power_enable=True, daily_enable=False, echo_of_war_enable=False, reward_enable=False))
    monkeypatch.setattr(power, "run", lambda *, borrow_for_daily, on_summary: on_summary("power") or True)
    monkeypatch.setattr(rewards.daily, "support_demand", Mock(return_value=power.SupportDemand()))
    monkeypatch.setattr(rewards.daily, "run", lambda *, complete_training, full_run, on_summary: on_summary("rewards") or True)
    monkeypatch.setattr(rewards.screen, "change_to", Mock())
    summary = Mock()
    assert rewards.routine(on_summary=summary)
    summary.assert_called_once_with(tr("；").join(("power", "rewards")))


def routine_steps(monkeypatch, *, claim=True):
    monkeypatch.setattr(rewards, "cfg", SimpleNamespace(power_enable=True, daily_enable=True, echo_of_war_enable=False, reward_enable=True))
    monkeypatch.setattr(rewards.daily, "support_demand", Mock(return_value=power.SupportDemand()))
    monkeypatch.setattr(rewards, "claim", Mock(return_value=claim))
    monkeypatch.setattr(rewards.screen, "change_to", Mock())
    monkeypatch.setattr(rewards.log, "error", Mock())
    received = []

    def run_power(*, borrow_for_daily, on_summary):
        received.append(on_summary)
        return on_summary is None or on_summary("power") or True

    def run_daily(*, complete_training, full_run, on_summary):
        received.append(on_summary)
        return on_summary is None or on_summary("daily") or True

    monkeypatch.setattr(power, "run", run_power)
    monkeypatch.setattr(rewards.daily, "run", run_daily)
    return received


def test_routine_reports_steps_with_their_own_summaries_and_continues_after_a_failure(monkeypatch):
    routine_steps(monkeypatch, claim=False)
    events = []
    summary = Mock()

    assert rewards.routine(on_summary=summary, on_step=lambda *event: events.append(event)) is False
    assert events == [
        ("查询支援实训", "started", None), ("查询支援实训", "succeeded", None),
        ("清体力", "started", None), ("清体力", "succeeded", "power"),
        ("日常领奖", "started", None), ("日常领奖", "failed", None),
        ("每日实训", "started", None), ("每日实训", "succeeded", "daily"),
    ]
    summary.assert_called_once_with(tr("；").join(("power", "daily")))


def test_routine_returns_final_failure_without_extra_navigation(monkeypatch):
    routine_steps(monkeypatch, claim=True)
    monkeypatch.setattr(rewards.daily, "run", Mock(return_value=False))
    rewards.screen.change_to.side_effect = RuntimeError("不应回主界面")
    assert rewards.routine(full_run=True) is False
    rewards.screen.change_to.assert_not_called()


def test_routine_step_summaries_do_not_need_the_joined_summary(monkeypatch):
    routine_steps(monkeypatch)
    events = []

    assert rewards.routine(on_step=lambda *event: events.append(event)) is True
    assert ("清体力", "succeeded", "power") in events
    assert ("每日实训", "succeeded", "daily") in events


def test_routine_without_callbacks_asks_for_no_summaries(monkeypatch):
    received = routine_steps(monkeypatch)

    assert rewards.routine() is True
    assert received == [None, None]


def test_standalone_entries_pass_the_summary_callback_through(monkeypatch):
    monkeypatch.setattr(rewards.daily, "support_demand", Mock(return_value="demand"))
    run_power = Mock(return_value=True)
    run_daily = Mock(return_value=True)
    monkeypatch.setattr(power, "run", run_power)
    monkeypatch.setattr(rewards.daily, "run", run_daily)
    summary = Mock()

    assert power.run_standalone(on_summary=summary) is True
    assert rewards.run_daily_training(on_summary=summary) is True
    assert power.run_standalone() is True
    assert rewards.run_daily_training() is True
    assert run_power.call_args_list == [
        call(borrow_for_daily="demand", on_summary=summary), call(borrow_for_daily="demand", on_summary=None),
    ]
    assert run_daily.call_args_list == [
        call(complete_training=True, on_summary=summary), call(complete_training=True, on_summary=None),
    ]


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
    monkeypatch.setattr(rewards, "find_thread_title", Mock(return_value="超时会话"))
    monkeypatch.setattr(rewards, "_open_unread_message", Mock(side_effect=[True, False]))
    rewards.auto.find_element.return_value = None
    monkeypatch.setattr(rewards, "drag_list", Mock(return_value=True))
    finish = Mock(side_effect=[rewards.MessageTimeout("超时"), True])
    monkeypatch.setattr(rewards, "_finish_message", finish)
    notify = Mock()
    monkeypatch.setattr(rewards, "notify_reward", notify)
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


@pytest.mark.parametrize("select_team", [False, True])
def test_fixed_challenge_reuses_start_button_until_the_team_changes(monkeypatch, select_team):
    monkeypatch.setattr(power, "cfg", SimpleNamespace(instance_team_enable=select_team, borrow_enable=False))
    auto = Mock()
    button = ((1700, 970), (1780, 1010))
    auto.find_element.return_value = button
    auto.take_screenshot.return_value = (Image.new("RGB", (110, 40)), None, 1)
    monkeypatch.setattr(power, "auto", auto)
    monkeypatch.setattr(power.time, "sleep", Mock())
    read_ocr = Mock(side_effect=[[_line("挑战次数5", 0, 0)], [_line("来", 0, 0), _line("×50", 40, 0)]])
    monkeypatch.setattr(readout.ocr, "recognize_multi_lines", read_ocr)
    selected_start = ((1710, 970), (1790, 1010))
    select = Mock(return_value=selected_start)
    monkeypatch.setattr(power, "_select_team", select)
    click = Mock(return_value=True)
    monkeypatch.setattr(power, "_click_text", click)

    assert power._start_challenge(power.GOLDEN_CALYX, "回忆之蕾", 5) == (5, False)
    auto.take_screenshot.assert_not_called()
    read_ocr.assert_not_called()
    assert sum(args.args[0] == (1821 / 1920, 866 / 1080, 0, 0)
               for args in auto.click_element.call_args_list) == 4
    assert [lookup.args[0] for lookup in auto.find_element.call_args_list] == ["开始挑战"]
    assert select.call_count == int(select_team)
    click.assert_called_once_with("挑战", power.CHALLENGE)
    auto.click_element_with_pos.assert_called_once_with(selected_start if select_team else button)


def test_sms_pending_thread_accepts_sticker_reply(monkeypatch):
    sticker = ((609, 510), (632, 528))
    auto = Mock()
    auto.find_element.side_effect = [None, [], sticker, None, None, None]
    monkeypatch.setattr(rewards, "auto", auto)
    monkeypatch.setattr(rewards, "_message_pending", Mock(side_effect=[True, False, False, False]))
    monkeypatch.setattr(rewards.time, "sleep", Mock())

    rewards._finish_message()

    auto.click_element_with_pos.assert_called_once_with(sticker, offset=(55, 62))


@pytest.mark.parametrize("stocks,after", [([630], 620), ([630], 380), ([0, 7], 440)])
def test_supplement_uses_maximum_and_accepts_the_actual_balance(monkeypatch, stocks, after):
    cfg = SimpleNamespace(use_reserved_trailblaze_power=True, use_fuel=True)
    auto = Mock()
    auto.find_element.side_effect = lambda label, *_args, **_kwargs: label if label != "获得物品" else None
    read = Mock(side_effect=stocks)
    monkeypatch.setattr(supplement, "read_number", read)
    navigate = Mock(check_screen=Mock(return_value=True))
    read_balance = Mock(return_value=after)
    assert supplement.supplement(auto, navigate, cfg, 320, Mock(return_value="入口"),
                                 read_balance, return_screen="guide3") == after
    assert read.call_count == len(stocks)
    read_balance.assert_called_once_with()
    assert auto.click_element_with_pos.call_args_list.count(call("确认")) == 2
    navigate.check_screen.assert_called_once_with("guide3")


@pytest.mark.parametrize("after", [80, power.PowerError("未能确认当前开拓力")])
def test_supplement_reuses_previous_budget_without_resending_unconfirmed_exchange(monkeypatch, after):
    cfg = SimpleNamespace(use_reserved_trailblaze_power=True, use_fuel=False)
    auto = Mock()
    auto.find_element.side_effect = lambda label, *_args, **_kwargs: label if label != "获得物品" else None
    screen = Mock(check_screen=Mock(return_value=True))
    read_balance = Mock(side_effect=[after])
    stock = Mock(side_effect=[30])
    monkeypatch.setattr(supplement, "read_number", stock)

    assert supplement.supplement(auto, screen, cfg, 80, Mock(return_value="入口"), read_balance,
                                 return_screen="guide3") == 80
    assert auto.click_element_with_pos.call_args_list.count(call("确认")) == 2
    read_balance.assert_called_once_with()
    stock.assert_called_once()
    screen.check_screen.assert_called_once_with("guide3")


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


@pytest.mark.parametrize("later_match", [False, True])
def test_touch_support_logs_read_names_before_finishing_the_search(monkeypatch, later_match):
    from tasks.power import policy
    from tasks.touch import support

    frame = Image.new("RGB", (96, 500))
    auto = Mock(take_screenshot=Mock(return_value=(frame, None, 1)))
    readings = iter(["持明上网", "小三月", "持明上網" if later_match else "小三月"])
    confirm = Mock()

    def find(target, kind, **_kwargs):
        assert kind == "text"
        if target == "解除支援":
            return confirm.called
        if target == "持明上網":
            read_name = next(readings)
            auto.ocr_result = [_line(read_name, 0, 0)]
            return target in read_name
        return target == "支援角色" or target == "开始挑战"

    auto.find_element.side_effect = find
    log = Mock()
    tap = Mock()
    monkeypatch.setattr(support, "auto", auto)
    monkeypatch.setattr(policy, "log", log)
    monkeypatch.setattr(support, "cfg", SimpleNamespace(borrow_friends=[("Cyrene", "持明上網")], borrow_scroll_times=2))
    monkeypatch.setattr(support, "_click_text", Mock(return_value=True))
    monkeypatch.setattr(support, "_portrait_rows", Mock(side_effect=[[70, 180], [70]]))
    monkeypatch.setattr(support, "drag_list", Mock(return_value=True))
    monkeypatch.setattr(support, "changed_ratio", Mock(return_value=0.5))
    monkeypatch.setattr(support, "_tap", tap)
    monkeypatch.setattr(support, "_confirm_standard_team", confirm)

    assert support.borrow() is later_match
    assert next(readings, None) is None
    assert log.info.call_args_list == [
        call("找到支援角色「昔涟」，你填的好友名字是「持明上網」，小助手读到的是「持明上网」。"),
        call("找到支援角色「昔涟」，你填的好友名字是「持明上網」，小助手读到的是「小三月」。"),
    ]
    assert log.warning.call_count == int(not later_match)
    if later_match:
        tap.assert_called_once_with(124, (round(support.PORTRAITS[1] * 720) + 70) * 1.5)
        confirm.assert_called_once_with("昔涟")
    else:
        tap.assert_called_once_with(1848, 55)
        confirm.assert_not_called()
