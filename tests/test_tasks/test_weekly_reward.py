"""复现两个差分宇宙入口的积分面板、弹窗、导航与实际输入回执。"""

from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image, ImageDraw
import pytest

from tasks.weekly import divergent_universe as divergent
from tasks.weekly import universe
from tasks.weekly import weekly_reward as reward
from utils.pause import RunStopRequested


def ocr_rows(*entries):
    return [([(x - 20, y - 10), (x + 20, y - 10), (x + 20, y + 10), (x - 20, y + 10)],
             (text, 0.99)) for text, x, y in entries]


@pytest.fixture
def scene(monkeypatch):
    canvas = Image.new("RGB", (1920, 1080), (35, 30, 74))
    pending = canvas.copy()
    ImageDraw.Draw(pending).rectangle(reward.WEEKLY_CLAIM, fill=(244, 184, 65))
    claimed = canvas.copy()
    mark = Image.open("assets/images/screen/currency_wars/s2_points_claimed.png").convert("RGB")
    tiers = tuple((str(index * 3000), 150 + (index - 1) * 300, 590) for index in range(1, 7))
    for _, x, _ in tiers:
        claimed.paste(mark, (x - mark.width // 2, 517 - mark.height // 2))
    points = (("积分奖励", 145, 330), ("18000/18000", 273, 740))
    frames = {
        "pending": (pending, ocr_rows(*points, ("一键领取", 1640, 728))),
        "claimed": (claimed, ocr_rows(*points, *tiers)),
        "receipt": (canvas, ocr_rows(("点击空白处关闭", 960, 910))),
        "partial": (canvas, ocr_rows(("点击空白处关闭", 960, 910))),
        "limit": (canvas, ocr_rows(("背 包 内助燃券持有数量已达上限。", 956, 580),
                                 ("清理", 774, 708), ("前往使用", 1188, 708))),
        "destroy": (canvas, ocr_rows(("此次销毁将无物品返还，销毁物品如下：", 953, 418),
                                   ("已销毁的物品无法复原", 960, 686), ("取消", 770, 754), ("确认", 1187, 754))),
        "other": (canvas, ocr_rows(("背包内遗器持有数量已达上限。", 956, 580), ("清理", 774, 708))),
        "unknown": (canvas, ocr_rows(("确认清理", 960, 708))),
    }
    state = SimpleNamespace(page="pending", flow="auto", fault=None, cleaned=False, confirmed=False,
                            now=0.0, misses=0, release=None, clicks=[], keys=[], frames=frames)
    auto = Mock()
    auto.input_handler = SimpleNamespace(reports_dispatch=False)
    config = SimpleNamespace(
        universe_bonus_enable=False, weekly_divergent_bonus_enable=False, weekly_divergent_timestamp=1,
        refresh_hour=4, save_timestamp=Mock(), get_game_hotkey=lambda _, default: default,
        notify_template={"SimulatedUniverseRewardClaimed": "模拟宇宙奖励已领取",
                         "SimulatedUniverseCompleted": "模拟宇宙已完成"},
    )

    def sleep(seconds):
        state.now += seconds
        if state.release and state.now >= state.release[0]:
            state.page = state.release[1]
            state.release = None

    def screenshot(*args, **kwargs):
        if state.fault == "persistent_capture" or state.fault == "capture_once" and not state.misses:
            state.misses += 1
            raise OSError("截图暂时不可用")
        auto.screenshot = frames[state.page][0]
        return True

    def ocr(**kwargs):
        if state.fault == "ocr_once" and not state.misses:
            state.misses += 1
            raise OSError("OCR 暂时不可用")
        auto.ocr_result = frames[state.page][1]

    def find(target, *args, **kwargs):
        if not isinstance(target, tuple):
            return None
        x, y = round(target[0] * 1920), round(target[1] * 1080)
        if (x, y) == (774, 708):
            if state.fault == "mapping_once" and not state.misses:
                state.misses += 1
                return None
            if state.fault == "deadline_map":
                state.now = 75
            if state.fault == "stop_map":
                reward.pause_ctl.checkpoint.side_effect = RunStopRequested()
        return ((x, y), (x, y))

    def click(pos, **kwargs):
        point = pos[0]
        state.clicks.append((state.page, point))
        if state.page == "pending" and point == (1640, 728):
            if state.cleaned:
                state.page = "receipt"
            elif state.flow == "normal":
                state.page = "receipt"
            else:
                state.page = "partial" if state.flow == "after_receipt" else "limit"
        elif state.page == "limit" and point == (774, 708):
            assert not state.cleaned
            state.cleaned = True
            if state.fault == "persistent_limit":
                pass
            else:
                state.page = "unknown" if state.fault == "unknown_confirmation" else "destroy"
        elif state.page == "destroy" and point == (1187, 754):
            assert not state.confirmed
            state.confirmed = True
            target = {"auto": "claimed", "receipt": "receipt", "reclaim": "pending",
                      "after_receipt": "receipt"}[state.flow]
            if state.fault in ("late_receipt", "transition"):
                state.release = (state.now + (11 if state.fault == "late_receipt" else 2), target)
                state.page = "destroy" if state.fault == "late_receipt" else "unknown"
            elif state.fault != "persistent_confirm":
                state.page = target
            if state.fault == "missing_ack":
                raise OSError("输入已送达，回执丢失")
        elif state.page == "partial" and point == (960, 910):
            state.page = "limit"
        elif state.page == "receipt" and point == (960, 910):
            state.page = "claimed"
        else:
            pytest.fail(f"非预期输入：{state.page} {point}")
        return True

    def open_points(*args, **kwargs):
        assert args[0] == "./assets/images/share/base/RedExclamationMark.png"
        state.page = "pending"
        return True

    auto.take_screenshot.side_effect = screenshot
    auto.perform_ocr.side_effect = ocr
    auto.find_element.side_effect = find
    auto.click_element.side_effect = open_points
    auto.click_element_with_pos.side_effect = click
    auto.press_key.side_effect = state.keys.append
    notify = Mock()
    for module in (divergent, universe, reward):
        monkeypatch.setattr(module, "auto", auto)
    for module in (divergent, universe):
        monkeypatch.setattr(module, "cfg", config)
        monkeypatch.setattr(module, "screen", Mock())
        monkeypatch.setattr(module.Base, "send_notification_with_screenshot", notify)
        monkeypatch.setattr(module, "time", SimpleNamespace(sleep=sleep))
    monkeypatch.setattr(reward, "time", SimpleNamespace(sleep=sleep, monotonic=lambda: state.now))
    monkeypatch.setattr(reward, "pause_ctl", Mock())
    monkeypatch.setattr(reward, "log", Mock())
    monkeypatch.setattr(reward, "save_error_screenshot", Mock())

    def run(entry):
        if entry == "builtin":
            return divergent.DivergentUniverse().get_reward()
        if entry == "thirdparty":
            universe.Universe.get_reward("divergent")
            return "esc" in state.keys
        return reward.claim_weekly_reward()

    state.run, state.notify, state.auto, state.config, state.sleep = run, notify, auto, config, sleep
    return state


@pytest.mark.parametrize("entry", ("builtin", "thirdparty"))
@pytest.mark.parametrize("flow", ("normal", "auto", "receipt", "reclaim", "after_receipt"))
def test_all_universe_entries_share_the_complete_reward_flow(scene, entry, flow):
    scene.flow = flow
    assert scene.run(entry)
    assert scene.page == "claimed"
    assert sum(point == (1640, 728) for _, point in scene.clicks) == (2 if flow == "reclaim" else 1)
    assert sum(point == (774, 708) for _, point in scene.clicks) == int(flow != "normal")
    assert sum(point == (1187, 754) for _, point in scene.clicks) == int(flow != "normal")
    assert scene.keys == ["esc"]
    assert sum(call.args[0] == "模拟宇宙奖励已领取" for call in scene.notify.call_args_list) == 1


@pytest.mark.parametrize("entry", ("builtin", "thirdparty"))
@pytest.mark.parametrize("fault", ("capture_once", "ocr_once", "mapping_once", "late_receipt", "transition", "missing_ack"))
def test_universe_reward_local_faults_recover_in_the_same_call(scene, entry, fault):
    scene.fault = fault
    assert scene.run(entry)
    assert scene.page == "claimed"
    assert sum(point == (774, 708) for _, point in scene.clicks) == 1
    assert sum(point == (1187, 754) for _, point in scene.clicks) == 1


@pytest.mark.parametrize("entry", ("builtin", "thirdparty"))
@pytest.mark.parametrize("fault", ("persistent_limit", "persistent_confirm", "unknown_confirmation", "persistent_capture"))
def test_universe_reward_failure_is_bounded_and_not_reported_as_claimed(scene, entry, fault):
    scene.fault = fault
    assert not scene.run(entry)
    assert not scene.keys
    assert sum(point == (774, 708) for _, point in scene.clicks) <= 1
    assert sum(point == (1187, 754) for _, point in scene.clicks) <= 1
    assert scene.now < 76
    assert not any(call.args[0] == "模拟宇宙奖励已领取" for call in scene.notify.call_args_list)
    scene.config.save_timestamp.assert_not_called()


@pytest.mark.parametrize("entry", ("builtin", "thirdparty"))
@pytest.mark.parametrize("fault", ("deadline_map", "stop_map"))
def test_universe_reward_stops_before_dispatch_after_mapping(scene, entry, fault):
    scene.fault = fault
    if fault == "stop_map":
        with pytest.raises(RunStopRequested):
            scene.run(entry)
    else:
        assert not scene.run(entry)
    assert scene.clicks == [("pending", (1640, 728))]
    assert not scene.keys
    scene.config.save_timestamp.assert_not_called()


@pytest.mark.parametrize("page", ("destroy", "other", "unknown"))
def test_unrelated_dialogs_do_not_start_cleanup(scene, page):
    scene.page = page
    assert not scene.run("direct")
    assert not scene.clicks


def test_empty_weekly_reward_page_is_not_reported_as_a_new_claim(scene):
    scene.page = "claimed"
    assert not scene.run("direct")
    assert not scene.clicks


def test_divergent_keeps_match_result_and_checks_score_after_reward_failure(scene, monkeypatch):
    task = divergent.DivergentUniverse()
    task.run = Mock(return_value=True)
    task.process_ornament = Mock()
    monkeypatch.setattr(divergent, "claim_weekly_reward", Mock(side_effect=RuntimeError("领奖识别失败")))
    monkeypatch.setattr(divergent.Date, "is_next_mon_x_am", lambda *args: True)
    scene.auto.get_single_line_text.return_value = "18000/18000"
    assert task.start()
    scene.config.save_timestamp.assert_called_once_with("weekly_divergent_timestamp")
    task.process_ornament.assert_not_called()


def test_universe_attempts_ornament_after_confirmed_reward_exit_fails(scene, monkeypatch):
    scene.config.universe_bonus_enable = True
    monkeypatch.setattr(scene.auto, "press_key", Mock(side_effect=OSError("退出积分页失败")))
    ornament = Mock()
    monkeypatch.setattr(universe.Universe, "process_ornament", ornament)
    universe.Universe.get_reward("divergent")
    ornament.assert_called_once_with()
    assert any(call.args[0] == "模拟宇宙奖励已领取" for call in scene.notify.call_args_list)


def test_universe_keeps_match_completion_when_reward_is_unreadable(scene, monkeypatch):
    monkeypatch.setattr(universe, "claim_weekly_reward", Mock(side_effect=RuntimeError("领奖识别失败")))
    universe.Universe.finalize_simulation(True, "universe")
    scene.config.save_timestamp.assert_called_once_with("universe_timestamp")
    scene.notify.assert_called_once_with("模拟宇宙已完成", universe.NotificationLevel.ALL)
