from types import SimpleNamespace
from unittest.mock import Mock, call

from PIL import Image
import pytest

from module.automation.automation import Automation
from module.automation.background_input import GameWindowLost, InputInterrupted
from tasks.power import instance, power, supplement
from tasks.power.policy import (
    CAVERN, ECHO, GOLDEN_CALYX, ORNAMENT, BattleDefeat, InstanceUnavailable, PowerError, RelicBagFull, SupportDemand,
)
from utils.pause import RunStopRequested


@pytest.fixture(autouse=True)
def recorded_power(monkeypatch):
    monkeypatch.setattr(power, "save_reading", Mock())


@pytest.mark.parametrize(
    "old_frames, target_page, missed_drags, expected_drags",
    [
        (1, 0, (), []),
        (11, 0, (), [True, True, True, True, False, False]),
        (0, 1, (1,), [True, True]),
        (0, 2, (1, 3), [True, True, True, True]),
    ],
    ids=["panel-switch", "panel-wait-timeout", "first-drag-missed", "later-drag-missed-after-movement"],
)
def test_pc_instance_entry_search(monkeypatch, old_frames, target_page, missed_drags, expected_drags):
    name = "密伶之径"
    now = 0.0
    page = 0
    row_reads = 0
    entered = False
    texts = []
    drags = []
    auto = Automation.__new__(Automation)
    auto.logger = Mock()
    auto.screenshot_scale_factor = 1
    auto._is_debug_enabled = lambda: False
    auto.click_element = Mock(return_value=True)

    def sleep(seconds):
        nonlocal now
        now += seconds

    def capture(crop=(0, 0, 1, 1), *_args):
        nonlocal row_reads, texts
        if crop == instance.ENTRY_ROWS:
            row_reads += 1
            if row_reads <= old_frames and not drags:
                texts = ["角色培养", "前往", "隧洞遗器推荐", "培养设置"]
            else:
                texts = [name if page == target_page else "霜风之径", "40", "进入"]
        else:
            texts = [name] if entered else []
        auto.screenshot = Image.new("RGB", (30, 40), (page * 60,) * 3)
        auto.screenshot_pos = (686, 287, 980, 650) if crop == instance.ENTRY_ROWS else (0, 0, 1920, 1080)
        return auto.screenshot, auto.screenshot_pos, 1

    def ocr():
        auto.ocr_result = [
            ([(10 + i * 100, 10 + i * 50), (60 + i * 100, 10 + i * 50),
              (60 + i * 100, 30 + i * 50), (10 + i * 100, 30 + i * 50)], (text, 1.0))
            for i, text in enumerate(texts)
        ]

    def drag(_start_x, start_y, _end_x, end_y, *_args):
        nonlocal page
        down = end_y < start_y
        drags.append(down)
        if len(drags) not in missed_drags:
            page = min(2, max(0, page + (1 if down else -1)))
        return True

    def enter(_x, _y):
        nonlocal entered
        entered = True
        return True

    auto.take_screenshot = capture
    auto.perform_ocr = ocr
    auto.mouse_drag = drag
    auto.mouse_click = Mock(side_effect=enter)
    clock = SimpleNamespace(monotonic=lambda: now, sleep=sleep)
    monkeypatch.setattr(instance, "auto", auto)
    monkeypatch.setattr(instance, "screen", Mock())
    monkeypatch.setattr(instance, "time", clock)
    monkeypatch.setattr("tasks.base.list_drag.time", clock)
    monkeypatch.setattr("utils.wait.time", clock)

    assert instance.Instance.prepare_instance(CAVERN, name)
    assert drags == expected_drags
    auto.mouse_click.assert_called_once_with(921, 407)


@pytest.mark.parametrize(
    "clicks_to_enter, ready_at, error, expected_clicks",
    [
        (1, 0, None, 1),
        (3, 0, None, 3),
        (5, 0, None, 5),
        (1, 0.75, None, 1),
        (1, 8, None, 5),
        (None, 0, PowerError("等待进入战斗超时"), 5),
        (1, 0, PowerError("等待进入战斗超时"), 1),
        (None, 0, RunStopRequested(), 1),
        (None, 0, RelicBagFull("遗器背包已满"), 1),
    ],
    ids=["first-click", "retry", "last-click", "transition-during-popup-read", "slow-transition",
         "stuck", "entry-timeout", "user-stop", "bag-full"],
)
def test_pc_power_retries_start_challenge_until_button_disappears(
    monkeypatch, clicks_to_enter, ready_at, error, expected_clicks,
):
    name = "密伶之径"
    auto = Mock()
    now = 0.0
    initial_button_reads = 0

    def sleep(seconds):
        nonlocal now
        now += seconds

    def find(target, kind, *_args, **kwargs):
        nonlocal initial_button_reads
        clicks = auto.click_element_with_pos.call_count
        if clicks and isinstance(error, RunStopRequested):
            raise error
        if kwargs.get("crop") == instance.DIALOG:
            sleep(0.3)
        entered = clicks_to_enter is not None and clicks >= clicks_to_enter and now >= ready_at
        if target == "开始挑战":
            assert kwargs.get("take_screenshot", True)
            if not clicks:
                initial_button_reads += 1
            if entered:
                return None
            return ((1720 + clicks, 985), (1800 + clicks, 1005))
        if target == instance.FIGHT_AGAIN:
            return error is None and entered
        if isinstance(error, RelicBagFull) and "背包内遗器持有数量已达上限" in target:
            auto.matched_text = "背包内遗器持有数量已达上限"
            return True
        return None

    auto.find_element.side_effect = find
    auto.click_element.return_value = True
    auto.click_element_with_pos.return_value = True
    cfg = SimpleNamespace(instance_names_challenge_count={}, tp_before_instance=False,
                          instance_team_enable=False, borrow_enable=False)
    monkeypatch.setattr(instance, "auto", auto)
    monkeypatch.setattr(instance, "cfg", cfg)
    monkeypatch.setattr(instance, "time", SimpleNamespace(monotonic=lambda: now, sleep=sleep))
    monkeypatch.setattr(instance, "battle_speed_visible", Mock(return_value=False))
    monkeypatch.setattr(power, "cfg", cfg)
    monkeypatch.setattr(power.Power, "get", Mock(return_value=65))
    monkeypatch.setattr(instance.Instance, "prepare_instance", Mock(return_value=True))
    monkeypatch.setattr(instance.Instance, "select_waves", Mock(return_value=1))
    monkeypatch.setattr(instance.Instance, "clean_full_bag", Mock(return_value=False))
    finish = Mock()
    monkeypatch.setattr(instance.Instance, "complete_run", finish)

    if error is None:
        assert power.Power.process(CAVERN, name, planned_attempts=1) == 1
        finish.assert_called_once_with(CAVERN)
    else:
        with pytest.raises(type(error), match=str(error) or None):
            power.Power.process(CAVERN, name, planned_attempts=1)
        finish.assert_not_called()
    assert auto.click_element_with_pos.call_args_list == [
        call(((1720 + index, 985), (1800 + index, 1005))) for index in range(expected_clicks)
    ]
    assert initial_button_reads == 1


@pytest.mark.parametrize(
    "button, victory_at, clicks",
    [
        ("尝试重连", 7, ["尝试重连"]),
        ("退出游戏", 7, ["尝试重连", instance.CONFIRM]),
        (None, 4, []),
        ("尝试重连", None, ["尝试重连"] * 3),
    ],
    ids=["reconnect", "confirm-fallback", "title-only", "persistent-disconnect"],
)
def test_wait_fight_limits_reconnects_to_confirmed_dialogs(monkeypatch, button, victory_at, clicks):
    now = 0.0
    auto = Mock()

    def sleep(seconds):
        nonlocal now
        now += seconds

    def find(target, kind, *_args, **kwargs):
        if target == instance.FIGHT_AGAIN:
            return victory_at is not None and now >= victory_at
        if target == instance.PAUSE:
            return True
        if kind != "text" or now < 2:
            return False
        if "连接中断" in target:
            auto.matched_text = "连接中断"
            return True
        assert target == ("尝试重连", "退出游戏")
        assert kwargs["take_screenshot"] is kwargs["need_ocr"] is False
        return button in target

    auto.find_element.side_effect = find
    auto.click_element.side_effect = lambda target, *_args, **_kwargs: target == button or target == instance.CONFIRM
    monkeypatch.setattr(instance, "auto", auto)
    monkeypatch.setattr(instance, "time", SimpleNamespace(monotonic=lambda: now, sleep=sleep))
    monkeypatch.setattr(instance, "game_option_enabled", lambda *_args: False)

    if victory_at is None:
        with pytest.raises(PowerError, match="游戏连接中断"):
            instance.Instance.wait_fight()
    else:
        assert instance.Instance.wait_fight()
    assert [entry.args[0] for entry in auto.click_element.call_args_list] == clicks


@pytest.mark.parametrize("failure", [RuntimeError("截图超时"), GameWindowLost("游戏窗口已关闭"), RunStopRequested()])
def test_pc_wait_fight_recovers_optional_speed_capture_only(monkeypatch, failure):
    victories = iter([False, True])

    def find(target, *_args, **_kwargs):
        if target == instance.FIGHT_AGAIN:
            return next(victories)
        return target == instance.PAUSE

    auto = Mock(find_element=Mock(side_effect=find), take_screenshot=Mock(side_effect=failure))
    monkeypatch.setattr(instance, "auto", auto)
    monkeypatch.setattr(instance, "game_option_enabled", lambda *_args: True)
    monkeypatch.setattr(instance.time, "sleep", Mock())

    if type(failure) is RuntimeError:
        assert instance.Instance.wait_fight()
    else:
        with pytest.raises(type(failure)) as stopped:
            instance.Instance.wait_fight()
        assert stopped.value is failure
    auto.take_screenshot.assert_called_once()
    auto.click_element.assert_not_called()
    auto.press_key.assert_not_called()


def test_exit_after_victory_reuses_the_confirmed_main_screen(monkeypatch):
    auto = Mock()
    screen = Mock()
    screen.change_to.side_effect = RuntimeError("重复截图失败")
    monkeypatch.setattr(instance, "auto", auto)
    monkeypatch.setattr(instance, "screen", screen)
    monkeypatch.setattr(instance, "time", Mock())

    instance.Instance.complete_run(GOLDEN_CALYX)

    screen.check_screen.assert_called_once_with("main")
    screen.change_to.assert_not_called()
    auto.press_key.assert_not_called()


@pytest.mark.parametrize("saw_speed", [False, True])
def test_pc_repeat_requires_battle_evidence_without_observing_pause(monkeypatch, saw_speed):
    now = 0.0
    stale_results = ["victory", "exit", *(["occluded"] * 4), "victory"]
    next_battle = ["battle", "victory"] if saw_speed else []
    frames = iter(stale_results + next_battle)
    frame = None

    def sleep(seconds):
        nonlocal now
        now += seconds

    def find(target, *_args, **_kwargs):
        nonlocal frame
        if target == instance.FIGHT_AGAIN:
            frame = next(frames, "victory")
            return frame == "victory"
        if target == instance.FIGHT_EXIT:
            return frame == "exit"
        return False

    auto = Mock(find_element=Mock(side_effect=find))
    monkeypatch.setattr(instance, "auto", auto)
    monkeypatch.setattr(instance, "battle_speed_visible", lambda _: frame == "battle")
    monkeypatch.setattr(instance, "game_option_enabled", lambda *_args: False)
    monkeypatch.setattr(instance, "ENTRY_TIMEOUT", 6)
    monkeypatch.setattr(instance, "time", SimpleNamespace(monotonic=lambda: now, sleep=sleep))
    if saw_speed:
        assert instance.Instance.wait_fight(repeated=True)
        assert sum(check.args[0] == instance.FIGHT_AGAIN for check in auto.find_element.call_args_list) == 9
    else:
        with pytest.raises(PowerError, match="未确认再来一次的结算"):
            instance.Instance.wait_fight(repeated=True)
    auto.click_element.assert_not_called()


@pytest.mark.parametrize("repeated", [False, True], ids=["first-battle", "repeat"])
@pytest.mark.parametrize("auto_disabled", [True, False], ids=["auto-disabled-hint", "speed-hud"])
def test_pc_battle_hud_confirms_battle_when_pause_is_missing(monkeypatch, repeated, auto_disabled):
    now = 0.0
    enable = Mock()

    def sleep(seconds):
        nonlocal now
        now += seconds

    def find(target, *_args, **_kwargs):
        if target == instance.FIGHT_AGAIN:
            return (repeated and now < 0.5) or (now >= 3 and (enable.called or not auto_disabled))
        if target == instance.AUTO_DISABLED:
            assert not repeated or now >= 0.5
            return auto_disabled and not enable.called
        return False

    def speed_visible(_auto):
        assert not repeated or now >= 0.5
        return not auto_disabled

    monkeypatch.setattr(instance, "auto", Mock(find_element=Mock(side_effect=find), press_key=enable))
    monkeypatch.setattr(instance, "cfg", SimpleNamespace(get_game_hotkey=lambda _key, default: default))
    monkeypatch.setattr(instance, "ENTRY_TIMEOUT", 2)
    monkeypatch.setattr(instance, "time", SimpleNamespace(monotonic=lambda: now, sleep=sleep))
    monkeypatch.setattr(instance, "ensure_double_speed", Mock())
    monkeypatch.setattr(instance, "battle_speed_visible", speed_visible)

    assert instance.Instance.wait_fight(repeated=repeated)
    assert enable.call_args_list == ([call("v")] if auto_disabled else [])


@pytest.mark.parametrize("failure,entries", [("plus", 2), ("challenge", 2), ("team", 2), ("persistent", 3)])
def test_pc_pre_start_recovers_only_by_entering_a_fresh_page(monkeypatch, failure, entries):
    name = "回忆之蕾"
    page = "main"
    entry = 0
    waves = 0
    plus_clicks = []
    plus = ((1610, 860), (1670, 909))
    start = ((1720, 985), (1800, 1005))

    def prepare(*_args):
        nonlocal page, entry, waves
        assert page == "main"
        page = "challenge"
        entry += 1
        waves = 1
        return True

    def change_to(target, *, max_recursion):
        nonlocal page
        assert target == "main" and max_recursion == 1
        assert page in ("challenge", "team")
        page = "main"

    def find(target, *_args, **_kwargs):
        if target == "./assets/images/screen/guide/plus.png":
            assert page == "challenge" and waves == 1
            if failure == "plus" and entry == 1:
                return None
            return plus
        if target == "开始挑战":
            return start if page == "team" and (entry > 1 or failure != "team") else None
        return False

    def click(target, *_args, **_kwargs):
        nonlocal page
        assert target == "挑战" and page == "challenge" and waves == 3
        if failure == "persistent" or (failure == "challenge" and entry == 1):
            return False
        page = "team"
        return True

    def click_position(target):
        nonlocal page, waves
        if target == plus:
            assert page == "challenge"
            plus_clicks.append(entry)
            waves += 1
        else:
            assert target == start and page == "team" and waves == 3
            page = "battle"
        return True

    auto = Mock(find_element=Mock(side_effect=find), click_element=Mock(side_effect=click),
                click_element_with_pos=Mock(side_effect=click_position))
    cfg = SimpleNamespace(instance_names_challenge_count={}, tp_before_instance=False,
                          instance_team_enable=False, borrow_enable=False)
    balance = Mock(return_value=35)
    finish = Mock()
    wait_fight = Mock(return_value=True)
    read_number = Mock(side_effect=PowerError("开打前不应再读费用或波次"))
    plan_batch = Mock(wraps=power.plan_paid_batch)
    monkeypatch.setattr(instance, "auto", auto)
    monkeypatch.setattr(instance, "cfg", cfg)
    monkeypatch.setattr(instance, "time", SimpleNamespace(sleep=Mock()))
    monkeypatch.setattr(instance, "read_number", read_number)
    monkeypatch.setattr(instance.Instance, "prepare_instance", prepare)
    monkeypatch.setattr(instance.Instance, "complete_run", finish)
    monkeypatch.setattr(instance.Instance, "wait_fight", wait_fight)
    monkeypatch.setattr(power, "screen", SimpleNamespace(change_to=change_to))
    monkeypatch.setattr(power, "cfg", cfg)
    monkeypatch.setattr(power, "plan_paid_batch", plan_batch)
    monkeypatch.setattr(power.Power, "get", balance)

    if failure == "persistent":
        with pytest.raises(PowerError, match="未找到副本的挑战按钮"):
            power.Power.process(GOLDEN_CALYX, name, planned_attempts=3)
        wait_fight.assert_not_called()
        finish.assert_not_called()
    else:
        assert power.Power.process(GOLDEN_CALYX, name, planned_attempts=3) == 3
        wait_fight.assert_called_once_with(repeated=False)
        finish.assert_called_once_with(GOLDEN_CALYX)
    expected_entries = range(2 if failure == "plus" else 1, entries + 1)
    assert plus_clicks == [attempt for attempt in expected_entries for _ in range(2)]
    balance.assert_called_once_with(use_supplement=True)
    plan_batch.assert_called_once_with(3, 35, 10, immersifiers=0)
    read_number.assert_not_called()


@pytest.mark.parametrize("use_template", [False, True], ids=["text-fallback", "template"])
@pytest.mark.parametrize("checkbox_delivered", [False, True])
def test_pc_echo_checks_do_not_show_again_before_confirming_the_story_prompt(monkeypatch, use_template, checkbox_delivered):
    name = "毁灭的开端"
    entry = ((1512, 771), (1640, 799))
    checkbox = ((742, 708), (888, 747))
    confirm = ((1053, 773), (1205, 805))
    actions = []
    auto = Mock()

    def find(target, *_args, **_kwargs):
        if target == ("传送", "进入", "追踪"):
            auto.matched_text = "进入"
            return entry
        if target == name:
            return actions.count(confirm) == 2
        if isinstance(target, tuple) and "不再弹出" in target:
            auto.matched_text = target[0]
            return checkbox
        if target == instance.CONFIRM:
            return confirm if use_template else False
        return False

    def click_label(target, *_args, **_kwargs):
        if target == "确认":
            assert actions[:2] == [entry, checkbox]
            actions.append(confirm)
        return True

    def click_position(position):
        actions.append(position)
        return checkbox_delivered if position == checkbox else True

    auto.find_element.side_effect = find
    auto.click_element_with_pos.side_effect = click_position
    auto.click_element.side_effect = click_label
    monkeypatch.setattr(instance, "auto", auto)
    monkeypatch.setattr(instance, "time", SimpleNamespace(sleep=Mock()))
    monkeypatch.setattr(instance.Instance, "select_category", Mock())
    monkeypatch.setattr(instance, "wait_until", lambda ready, *_args: any(ready() for _ in range(3)))

    assert instance.Instance.prepare_instance(ECHO, name)
    assert actions == [entry, checkbox, confirm, confirm]
    assert sum(args.args[0] == "确认" for args in auto.click_element.call_args_list) == (0 if use_template else 2)


@pytest.mark.parametrize("fault,balance,inputs,waves", [
    ("入口漏识别", 34, [], 3),
    ("点击丢失", 34, ["入口", "入口"], 3),
    ("标题漏识别", 34, ["入口", "取消"], 3),
    ("文字完全不可用", 34, ["入口", "副本导航"], 3),
    ("关闭异常", 34, ["入口", "副本导航"], 3),
    ("标题漏识别", 9, ["入口", "取消"], 0),
])
def test_pc_supplement_entry_miss_reuses_the_available_budget(monkeypatch, fault, balance, inputs, waves):
    name = "回忆之蕾"
    actions = []
    dialog = False

    def find(label, kind, *_args, **_kwargs):
        if kind == "image" and fault != "入口漏识别":
            return "入口"
        if label == "取消" and dialog:
            if fault == "关闭异常":
                raise OSError("退出补充弹窗时截图失败")
            if fault == "标题漏识别":
                return "取消"

    def send(control):
        nonlocal dialog
        actions.append(control)
        if control == "入口":
            dialog = fault != "点击丢失"
        else:
            dialog = False
        return fault != "点击丢失"

    def navigate(target):
        nonlocal dialog
        if target == "guide3" and dialog:
            actions.append("副本导航")
            dialog = False

    def prepare(*_args):
        screen.change_to("guide3")
        return True

    auto = Mock(find_element=Mock(side_effect=find), click_element_with_pos=Mock(side_effect=send))
    screen = Mock(check_screen=Mock(side_effect=lambda target: target == "map" and not dialog),
                  get_name=Mock(return_value="地图"), change_to=Mock(side_effect=navigate))
    cfg = SimpleNamespace(use_reserved_trailblaze_power=True, use_fuel=False,
                          instance_names_challenge_count={}, tp_before_instance=False)
    meter = Mock(side_effect=[balance, PowerError("不可重复读取余额")])
    battle = Mock(select_waves=Mock(return_value=3), prepare_instance=Mock(side_effect=prepare),
                  wait_fight=Mock(return_value=True))
    monkeypatch.setattr(power, "auto", auto)
    monkeypatch.setattr(power, "screen", screen)
    monkeypatch.setattr(power, "cfg", cfg)
    monkeypatch.setattr(power, "read_number", meter)
    monkeypatch.setattr(power, "Instance", battle)
    monkeypatch.setattr(supplement.time, "sleep", Mock())

    assert power.Power.process(GOLDEN_CALYX, name, planned_attempts=3) == waves
    if waves:
        battle.select_waves.assert_called_once_with(GOLDEN_CALYX, 3)
        battle.complete_run.assert_called_once_with(GOLDEN_CALYX)
    else:
        battle.prepare_instance.assert_not_called()
    meter.assert_called_once()
    assert actions == inputs
    auto.press_key.assert_not_called()


@pytest.mark.parametrize("fault", ["lookup-timeout", "dispatch-timeout", "user-stop"])
def test_pc_supplement_rechecks_budget_and_stop_after_button_lookup(monkeypatch, fault):
    page = "map"
    now = 0.0
    stop_requested = False
    actions = []

    def find(label, kind, *_args, **_kwargs):
        nonlocal now, stop_requested
        if kind == "image" and label.endswith("/reserved_trailblaze_power.png"):
            return ((497, 290), (603, 360))
        if kind == "image":
            return "入口"
        if kind == "crop":
            return label
        if label == "确认" and page == "amount":
            if fault == "user-stop":
                stop_requested = True
            elif fault == "lookup-timeout":
                now = 19.0
            return "最终确认"
        return label

    def send(control):
        nonlocal now, page
        if control == "最终确认":
            assert fault == "dispatch-timeout"
            now = 19.0
            raise InputInterrupted("后台输入等待已达到任务总时限")
        actions.append(control)
        if control == "入口":
            page = "supplement"
        elif control == "确认":
            page = "amount"
        elif control == "取消":
            page = "supplement" if page == "amount" else "map"

    def checkpoint():
        if stop_requested:
            raise RunStopRequested()

    auto = Mock(find_element=Mock(side_effect=find), click_element_with_pos=Mock(side_effect=send),
                input_handler=SimpleNamespace(reports_dispatch=True), screenshot=SimpleNamespace(width=1280))
    screen = Mock(check_screen=Mock(side_effect=lambda target: target == page))
    cfg = SimpleNamespace(use_reserved_trailblaze_power=True, use_fuel=False,
                          instance_names_challenge_count={}, tp_before_instance=False)
    battle = Mock(select_waves=Mock(return_value=3), prepare_instance=Mock(return_value=True),
                  wait_fight=Mock(return_value=True))
    meter = Mock(side_effect=[34, PowerError("没有提交补充，不应读取余额")])
    monkeypatch.setattr(power, "auto", auto)
    monkeypatch.setattr(power, "screen", screen)
    monkeypatch.setattr(power, "cfg", cfg)
    monkeypatch.setattr(power, "Instance", battle)
    monkeypatch.setattr(power, "read_number", meter)
    stock = Mock(side_effect=[30])
    monkeypatch.setattr(supplement, "read_number", stock)
    monkeypatch.setattr(supplement, "time", SimpleNamespace(monotonic=lambda: now, sleep=Mock()))
    monkeypatch.setattr(supplement.pause_ctl, "checkpoint", checkpoint)

    if fault == "user-stop":
        with pytest.raises(RunStopRequested):
            power.Power.process(GOLDEN_CALYX, "回忆之蕾", planned_attempts=3)
        battle.prepare_instance.assert_not_called()
    else:
        assert power.Power.process(GOLDEN_CALYX, "回忆之蕾", planned_attempts=3) == 3
        battle.complete_run.assert_called_once_with(GOLDEN_CALYX)
    meter.assert_called_once()
    stock.assert_called_once()
    assert actions == ["入口", supplement._crop((550, 327, 0, 0)), "确认",
                       supplement._crop((941, 460, 0, 0))] + ([] if fault == "user-stop" else ["取消", "取消"])


@pytest.mark.parametrize("failure,attempts", [(False, 2), (InstanceUnavailable("未解锁"), 1), (False, 3)])
def test_pc_instance_entry_retries_only_within_budget(monkeypatch, failure, attempts):
    entered = Mock(side_effect=[failure, True] if attempts < 3 else [False] * 3)
    battle = Mock(prepare_instance=entered, select_waves=Mock(return_value=1), wait_fight=Mock(return_value=True))
    monkeypatch.setattr(power, "Instance", battle)
    monkeypatch.setattr(power.Power, "get", Mock(return_value=10))
    monkeypatch.setattr(power, "cfg", SimpleNamespace(instance_names_challenge_count={}, tp_before_instance=False))

    if attempts == 2:
        assert power.Power.process(GOLDEN_CALYX, "回忆之蕾", planned_attempts=1) == 1
    else:
        with pytest.raises(PowerError):
            power.Power.process(GOLDEN_CALYX, "回忆之蕾", planned_attempts=1)
        battle.start_instance.assert_not_called()
    assert entered.call_count == attempts


@pytest.mark.parametrize("instance_type", [ORNAMENT, ECHO])
def test_defeat_retries_stop_without_recording_completion(monkeypatch, instance_type):
    name = "测试副本"
    battle = Mock()
    battle.read_echo_rewards.return_value = 3
    battle.select_waves.return_value = 1
    battle.wait_fight.return_value = False
    balance = Mock(return_value=200)
    stock = Mock(return_value=1)
    monkeypatch.setattr(power, "Instance", battle)
    monkeypatch.setattr(power.Power, "get", balance)
    monkeypatch.setattr(power.Power, "get_immersifier_count", stock)
    monkeypatch.setattr(power, "get_raw_instance_names", lambda: {instance_type: {name: name}})
    monkeypatch.setattr(power, "cfg", SimpleNamespace(
        instance_names_challenge_count={}, tp_before_instance=False, use_reserved_trailblaze_power=True,
    ))

    run = power.Power._run_instance(instance_type, name, 1)
    with pytest.raises(BattleDefeat):
        next(run)
    assert battle.start_instance.call_count == battle.exit_defeat.call_count == 3
    balance.assert_called_once_with(use_supplement=True)
    assert stock.call_count == (1 if instance_type == ORNAMENT else 0)
    power.save_reading.assert_not_called()


def test_pc_power_plan_reuses_budget_for_defeat_retry_same_batch_and_smaller_batch(monkeypatch):
    name = "回忆之蕾"
    later_plan = [CAVERN, "密伶之径", 1]
    cfg = SimpleNamespace(
        power_plan=[[GOLDEN_CALYX, name, 10], later_plan], power_plan_keep=False, power_plan_continue=False,
        instance_names_challenge_count={GOLDEN_CALYX: 4}, tp_before_instance=False, set_value=Mock(),
    )
    forbidden_read = Mock(side_effect=PowerError("重复读数失败"))
    select = Mock(side_effect=lambda _kind, requested: requested)
    balance = Mock(side_effect=[95, PowerError("重复读余额")])
    monkeypatch.setattr(instance, "read_number", forbidden_read)
    monkeypatch.setattr(power, "cfg", cfg)
    monkeypatch.setattr(power.Power, "get", balance)
    monkeypatch.setattr(instance.Instance, "prepare_instance", Mock(return_value=True))
    monkeypatch.setattr(instance.Instance, "select_waves", select)
    monkeypatch.setattr(instance.Instance, "start_instance", Mock(return_value=False))
    monkeypatch.setattr(instance.Instance, "start_instance_again", Mock())
    monkeypatch.setattr(instance.Instance, "wait_fight", Mock(side_effect=[False, True, True, True]))
    monkeypatch.setattr(instance.Instance, "exit_defeat", Mock())
    monkeypatch.setattr(instance.Instance, "complete_run", Mock())

    assert power.Power.run(skip_weekly_cleanup=True, support=SupportDemand())
    assert cfg.set_value.call_args_list == [
        call("power_plan", [[GOLDEN_CALYX, name, remaining], later_plan]) for remaining in (6, 2, 1)
    ]
    assert select.call_args_list == [call(GOLDEN_CALYX, waves) for waves in (4, 4, 1)]
    instance.Instance.start_instance_again.assert_called_once_with()
    instance.Instance.exit_defeat.assert_called_once_with()
    assert instance.Instance.complete_run.call_count == 2
    balance.assert_called_once_with(use_supplement=True)
    forbidden_read.assert_not_called()
    power.save_reading.assert_called_once_with(cfg, "overview_power", 5)


@pytest.mark.parametrize("quota", [1, 0], ids=["rewarded-echo", "practice"])
def test_pc_echo_finishes_without_reading_the_result_meter(monkeypatch, quota):
    battle = Mock()
    battle.read_echo_rewards.side_effect = [quota, PowerError("结算后不应再次读取额度")]
    battle.select_waves.return_value = 1
    map_balance = Mock(return_value=90) if quota else Mock(side_effect=PowerError("地图余额读数失败"))
    config = SimpleNamespace(instance_names_challenge_count={}, tp_before_instance=False, save_timestamp=Mock())
    monkeypatch.setattr(power, "Instance", battle)
    monkeypatch.setattr(power.Power, "get", map_balance)
    monkeypatch.setattr(power, "cfg", config)
    monkeypatch.setattr(power, "screen", Mock())

    assert power.Power.process(ECHO, "毁灭的开端", planned_attempts=1) == 1
    battle.read_echo_rewards.assert_called_once_with()
    assert map_balance.call_count == (1 if quota else 0)
    battle.complete_run.assert_called_once_with(ECHO)
    config.save_timestamp.assert_called_once_with("echo_of_war_timestamp")
    assert power.save_reading.call_args_list == ([call(config, "overview_power", 60)] if quota else [])


def test_pc_immersifier_only_uses_stock_without_reading_power(monkeypatch):
    name = "浴火钢心"
    config = SimpleNamespace(instance_names_challenge_count={ORNAMENT: 1}, tp_before_instance=False)
    monkeypatch.setattr(power, "cfg", config)
    monkeypatch.setattr(power.Power, "get", Mock(side_effect=PowerError("地图余额读数失败")))
    stock = Mock(return_value=1)
    monkeypatch.setattr(power.Power, "get_immersifier_count", stock)
    monkeypatch.setattr(instance.Instance, "prepare_instance", Mock(return_value=True))
    monkeypatch.setattr(instance.Instance, "complete_run", Mock())
    monkeypatch.setattr(instance.Instance, "select_waves", Mock(return_value=1))
    monkeypatch.setattr(instance.Instance, "start_instance", Mock(return_value=False))
    monkeypatch.setattr(instance.Instance, "start_instance_again", Mock())
    monkeypatch.setattr(instance.Instance, "wait_fight", Mock(return_value=True))
    monkeypatch.setattr(power, "screen", Mock())

    assert power.Power.process(ORNAMENT, name, immersifier_only=True) == 1
    instance.Instance.start_instance.assert_called_once()
    instance.Instance.start_instance_again.assert_not_called()
    power.Power.get.assert_not_called()
    stock.assert_called_once_with()
    power.save_reading.assert_not_called()


def test_pc_ornament_mixed_repeat_and_defeat_reuse_the_initial_budget(monkeypatch):
    name = "浴火钢心"
    later_plan = [CAVERN, "密伶之径", 1]
    config = SimpleNamespace(
        power_plan=[[ORNAMENT, name, 15], later_plan], power_plan_keep=False, power_plan_continue=False,
        instance_names_challenge_count={ORNAMENT: 6}, tp_before_instance=False, set_value=Mock(),
    )
    balance = Mock(side_effect=[174, PowerError("重复读余额")])
    stock = Mock(side_effect=[10, PowerError("重复读库存")])
    battle = Mock()
    battle.select_waves.side_effect = lambda _kind, waves: waves
    battle.wait_fight.side_effect = [True, False, True, True]
    plan_batch = Mock(wraps=power.plan_paid_batch)
    monkeypatch.setattr(power, "cfg", config)
    monkeypatch.setattr(power, "Instance", battle)
    monkeypatch.setattr(power, "plan_paid_batch", plan_batch)
    monkeypatch.setattr(power.Power, "get", balance)
    monkeypatch.setattr(power.Power, "get_immersifier_count", stock)

    assert power.Power.run(skip_weekly_cleanup=True, support=SupportDemand())
    assert plan_batch.call_args_list == [
        call(6, 174, 40, immersifiers=10),
        call(6, 174, 40, immersifiers=4),
        call(6, 174, 40, immersifiers=4),
        call(3, 94, 40, immersifiers=0),
        call(1, 14, 40, immersifiers=0),
    ]
    assert battle.select_waves.call_args_list == [call(ORNAMENT, waves) for waves in (6, 6, 2)]
    battle.start_instance_again.assert_called_once_with()
    battle.exit_defeat.assert_called_once_with()
    assert config.set_value.call_args_list == [
        call("power_plan", [[ORNAMENT, name, remaining], later_plan]) for remaining in (9, 3, 1)
    ]
    stock.assert_called_once_with()
    balance.assert_called_once_with(use_supplement=True)
    power.save_reading.assert_called_once_with(config, "overview_power", 14)


@pytest.mark.parametrize("entry", ["divergent", "universe"])
def test_universe_bonus_delegates_to_immersifier_only_power_task(monkeypatch, entry):
    from tasks.weekly import divergent_universe as divergent
    from tasks.weekly import universe

    module = divergent if entry == "divergent" else universe
    config = SimpleNamespace(
        weekly_divergent_timestamp=1, refresh_hour=4, weekly_divergent_bonus_enable=True,
        universe_bonus_enable=True, instance_names={ORNAMENT: "浴火钢心"}, build_target_enable=False,
        get_game_hotkey=lambda _name, default: default,
        notify_template={"SimulatedUniverseRewardClaimed": "已领取积分奖励", "SimulatedUniverseCompleted": "已完成"},
    )
    monkeypatch.setattr(power, "cfg", config)
    monkeypatch.setattr(module, "cfg", config)
    monkeypatch.setattr(module.Base, "send_notification_with_screenshot", Mock())
    monkeypatch.setattr(module, "screen", Mock())
    auto = Mock()
    auto.find_element.return_value = False
    auto.click_element.return_value = True
    auto.get_single_line_text.return_value = ""
    monkeypatch.setattr(module, "auto", auto)
    monkeypatch.setattr(power.Power, "process", Mock(return_value=1))

    if entry == "divergent":
        task = divergent.DivergentUniverse()
        monkeypatch.setattr(task, "run", Mock(return_value=True))
        monkeypatch.setattr(task, "get_reward", Mock(return_value=True))
        monkeypatch.setattr(divergent.Date, "is_next_mon_x_am", Mock(return_value=False))
        assert task.start()
    else:
        monkeypatch.setattr(universe, "claim_weekly_reward", Mock(return_value=True))
        monkeypatch.setattr(universe, "time", SimpleNamespace(sleep=Mock()))
        universe.Universe.get_reward("divergent")

    power.Power.process.assert_called_once_with(ORNAMENT, "浴火钢心", immersifier_only=True)
    auto.get_single_line_text.assert_not_called()
