"""合成回执迟到时只消耗一次，并继续领取实训活跃度和档位奖励。"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

from PIL import Image
import pytest

from module.automation import automation
from module.automation.input_base import begin_input_dispatch, limit_input_deadline
from module.game.adb_transport import AdbError
from module.screen.screen import Screen
from tasks.daily.training import DailyTrainingError, MATERIAL_TASK, TrainingCards
from tasks.reward import quest
from tasks.touch import daily, synthesis
from utils.pause import RunStopRequested


class SynthesisGame:
    """保留实际导航、模板匹配、文字定位和点击层，只替换截图、OCR 与设备派发。"""

    def __init__(self):
        self.now = 100.0
        self.page = "material"
        self.crop = None
        self.inputs = []
        self.confirmations = 0
        self.receipt_delay = 5
        self.dialog_delay = 0
        self.frame_error = None
        self.persistent_frame_error = False
        self.close_error = False
        self.lost_ack = False
        self.stop = False
        self.stop_after_confirm = False
        self.confirm_lookup_delay = 0
        self.stop_at_confirm_lookup = False
        self.direct_reward = False

    def sleep(self, seconds):
        self.now += seconds

    def check_stop(self):
        if self.stop:
            raise RunStopRequested()

    def capture(self, crop=(0, 0, 1, 1), *_args, **_kwargs):
        self.check_stop()
        self.now += 0.05
        if self.page == "waiting" and self.frame_error:
            error = self.frame_error
            if not self.persistent_frame_error:
                self.frame_error = None
            raise error
        if self.page == "opening" and self.now >= self.dialog_at:
            self.page = "confirm"
        if self.page == "waiting" and self.now >= self.reward_at:
            self.page = "reward"
        if self.page == "closing" and self.now >= self.material_at:
            self.page = "material"
        if self.page == "reward" and crop == (0, 0, 1, 1) and self.close_error:
            self.close_error = False
            raise RuntimeError("关闭弹窗时截图暂不可用")
        self.crop = crop
        frame = Image.new("RGB", (1280, 720), (35, 40, 45))
        if self.page == "material":
            asset, point = "material", (80, 20)
        elif self.page == "reward":
            asset, point = "item_reward", (607, 70)
        else:
            asset, point = None, None
        if asset:
            with Image.open(Path("assets/touch_720/images/screen") / f"{asset}.png") as template:
                frame.paste(template, point)
        x, y, width, height = crop
        frame = frame.crop((round(x * 1280), round(y * 720),
                            round((x + width) * 1280), round((y + height) * 720)))
        auto = synthesis.auto
        auto.screenshot = frame
        auto.screenshot_pos = (round(x * 1280), round(y * 720), frame.width, frame.height)
        auto.screenshot_scale_factor = 1
        return frame, auto.screenshot_pos, 1

    def recognize(self, *_args, **_kwargs):
        texts = []
        if self.page == "filter":
            texts = {
                synthesis.FILTER_TITLE: ["筛选规则"], synthesis.FILTER_CLEAR: ["全部清除"],
                synthesis.FILTER_OPTION: ["通用培养材料"], synthesis.FILTER_CONFIRM: ["确认"],
            }.get(self.crop, [])
        elif self.page == "material":
            texts = {
                synthesis.RECIPE_TITLE: ["微光原核"], synthesis.AMOUNT: ["合成数量：1"],
                synthesis.MATERIALS: ["300/3"], synthesis.SYNTHESIZE: ["合成"],
            }.get(self.crop, [])
        elif self.page == "confirm":
            texts = {
                synthesis.DIALOG_CONTENT: ["确认合成", "确认消耗以上物品进行合成微光原核×1吗？"],
                synthesis.DIALOG_CONFIRM: ["确认"],
            }.get(self.crop, [])
            if self.crop == synthesis.DIALOG_CONFIRM:
                self.now += self.confirm_lookup_delay
                self.stop = self.stop_at_confirm_lookup
        synthesis.auto.ocr_result = [
            ([(5, 5), (35, 5), (35, 20), (5, 20)], (text, 0.99)) for text in texts
        ]

    def tap(self, x, y):
        self.check_stop()
        if not begin_input_dispatch(self.now):
            return False
        self.inputs.append((self.page, (x, y)))
        if self.page == "material" and abs(x - 148) < 2 and abs(y - 662) < 2:
            self.page = "filter"
        elif self.page == "filter" and self.crop == synthesis.FILTER_CONFIRM:
            self.page = "material"
        elif self.page == "material" and self.crop == synthesis.SYNTHESIZE:
            self.page = "waiting" if self.direct_reward else ("opening" if self.dialog_delay else "confirm")
            self.dialog_at = self.now + self.dialog_delay
            self.reward_at = self.now + self.receipt_delay
        elif self.page == "confirm" and self.crop == synthesis.DIALOG_CONFIRM:
            self.confirmations += 1
            self.page = "waiting"
            self.reward_at = self.now + self.receipt_delay
            self.stop = self.stop_after_confirm
            return not self.lost_ack
        elif self.page == "reward" and (x, y) == (640, 569):
            self.page = "closing"
            self.material_at = self.now + 0.8
        return True


@pytest.fixture
def game(monkeypatch):
    import importlib
    screen_module = importlib.import_module("module.screen.screen")

    world = SynthesisGame()
    clock = SimpleNamespace(monotonic=lambda: world.now, sleep=world.sleep)
    profile = SimpleNamespace(name="touch_720", resolution=(1280, 720), resolve_image_path=lambda path: path)
    monkeypatch.setattr(automation, "time", clock)
    monkeypatch.setattr(automation, "get_ui_profile", lambda _cfg: profile)
    monkeypatch.setattr(screen_module, "time", clock)
    monkeypatch.setattr(screen_module, "get_ui_profile", lambda _cfg: profile)
    monkeypatch.setattr(synthesis, "time", clock)
    monkeypatch.setattr(synthesis.pause_ctl, "check_stop", world.check_stop, raising=False)
    monkeypatch.setattr(synthesis.auto, "take_screenshot", world.capture)
    monkeypatch.setattr(synthesis.auto, "perform_ocr", world.recognize)
    monkeypatch.setattr(synthesis.auto, "mouse_click", world.tap, raising=False)
    monkeypatch.setattr(synthesis.auto, "_is_debug_enabled", lambda: False)
    monkeypatch.setattr(synthesis.auto, "img_cache", {})
    for name, value in (("screenshot", None), ("screenshot_pos", None), ("screenshot_scale_factor", 1),
                        ("ocr_result", [])):
        monkeypatch.setattr(synthesis.auto, name, value, raising=False)
    nav = object.__new__(Screen)
    Screen.__init__(nav, "assets/touch_720/screens.json", logger=Mock())
    nav.current_screen = "material"
    monkeypatch.setattr(synthesis, "screen", nav)
    return world


@pytest.mark.parametrize("fault", ["delayed", "blank", "dialog_transition", "frame_timeout", "image_error",
                                   "lost_ack", "direct_reward"])
def test_synthesis_waits_for_delayed_receipt_without_repeating_consumption(game, fault):
    if fault == "blank":
        game.receipt_delay = 7
    elif fault == "dialog_transition":
        game.dialog_delay = 4
    elif fault == "frame_timeout":
        game.frame_error = AdbError("frame_timeout", "首帧未就绪")
    elif fault == "image_error":
        game.frame_error = RuntimeError("图像暂不可用")
    elif fault == "lost_ack":
        game.lost_ack = True
    elif fault == "direct_reward":
        game.direct_reward = True

    assert synthesis.material()
    assert game.confirmations == (0 if game.direct_reward else 1)
    assert sum(page == "material" and point[0] > 700 for page, point in game.inputs) == 1
    assert game.page == "material"
    assert game.now < 130


def test_missing_synthesis_receipt_has_a_bounded_failure_without_resending(game):
    game.receipt_delay = float("inf")
    with pytest.raises(DailyTrainingError, match="超时|未出现获得物品"):
        synthesis.material()
    assert game.confirmations == 1
    assert game.now < 140
    assert not any(page == "reward" for page, _ in game.inputs)


def test_persistent_frame_outage_ends_without_resending_synthesis(game):
    game.frame_error = AdbError("frame_timeout", "持续未取得画面")
    game.persistent_frame_error = True
    with pytest.raises(DailyTrainingError, match="超时|未出现获得物品"):
        synthesis.material()
    assert game.confirmations == 1
    assert game.now < 140


def test_synthesis_keeps_confirmed_result_when_cleanup_capture_fails(game):
    game.close_error = True
    assert synthesis.material()
    assert game.confirmations == 1
    assert game.page == "reward"


def test_stop_during_synthesis_receipt_wait_propagates_without_cleanup_inputs(game):
    game.stop_after_confirm = True
    with pytest.raises(RunStopRequested):
        synthesis.material()
    assert game.confirmations == 1
    assert game.inputs[-1][0] == "confirm"


@pytest.mark.parametrize("deadline,lookup_delay", [(None, 100), (120, 21)])
def test_synthesis_does_not_confirm_after_deadline_arrives_during_lookup(game, deadline, lookup_delay):
    game.confirm_lookup_delay = lookup_delay
    with limit_input_deadline(deadline), pytest.raises(DailyTrainingError):
        synthesis.material()
    assert game.confirmations == 0
    assert not any(page == "confirm" for page, _ in game.inputs)


def test_synthesis_does_not_confirm_after_stop_arrives_during_lookup(game):
    game.stop_at_confirm_lookup = True
    with pytest.raises(RunStopRequested):
        synthesis.material()
    assert game.confirmations == 0
    assert not any(page == "confirm" for page, _ in game.inputs)


@pytest.mark.parametrize("error", [None, DailyTrainingError("合成回执漏读"), RuntimeError("截图失败"),
                                    ValueError("识别失败"), AdbError("frame_timeout", "截图暂不可用")])
@pytest.mark.parametrize("activity", [400, 500])
def test_touch_training_claims_after_an_unconfirmed_action(monkeypatch, error, activity):
    config = SimpleNamespace(reward_enable=True, reward_quest_enable=True, daily_enable=True,
                             daily_material_enable=True, notify_template={"DailyPracticeCompleted": "每日实训已完成"})
    monkeypatch.setattr(daily, "cfg", config)
    monkeypatch.setattr(daily, "screen", Mock())
    monkeypatch.setattr(daily, "read_activity", Mock(return_value=400))
    scans = Mock(side_effect=[(400, False, 0, TrainingCards({MATERIAL_TASK: True})),
                              (activity, False, int(activity == 500), TrainingCards({}))])
    action = Mock(return_value=False, side_effect=error)
    milestone = Mock(return_value=True)
    record = Mock()
    monkeypatch.setattr(daily, "scan_cards", scans)
    monkeypatch.setattr(synthesis, "material", action)
    monkeypatch.setattr(daily, "claimable_milestones", Mock(return_value=["last-gift"]))
    monkeypatch.setattr(daily, "click_milestone", milestone)
    monkeypatch.setattr(daily, "record_progress", record)
    monkeypatch.setattr(daily, "notify_reward", Mock())

    assert daily.run(complete_training=True) is (activity == 500)
    action.assert_called_once_with()
    assert scans.call_args_list == [call(400, True, read_tasks=True), call(400, True, read_tasks=False)]
    milestone.assert_called_once_with("last-gift")
    record.assert_called_once_with(config, activity)


@pytest.mark.parametrize("error", [RunStopRequested(), AdbError("service_disconnected", "设备已断开")])
def test_touch_training_propagates_stop_and_unavailable_device(monkeypatch, error):
    monkeypatch.setattr(daily, "cfg", SimpleNamespace(reward_enable=True, reward_quest_enable=True,
                                                     daily_enable=True, daily_material_enable=True))
    monkeypatch.setattr(daily, "screen", Mock())
    monkeypatch.setattr(daily, "read_activity", Mock(return_value=400))
    scans = Mock(return_value=(400, False, 0, TrainingCards({MATERIAL_TASK: True})))
    monkeypatch.setattr(daily, "scan_cards", scans)
    monkeypatch.setattr(synthesis, "material", Mock(side_effect=error))
    rewards = Mock()
    monkeypatch.setattr(daily, "claimable_milestones", rewards)
    with pytest.raises(type(error)):
        daily.run(complete_training=True)
    scans.assert_called_once_with(400, True, read_tasks=True)
    rewards.assert_not_called()


@pytest.mark.parametrize("error", [None, RuntimeError("合成结果漏读")])
def test_pc_training_claims_completed_cards_after_an_unconfirmed_action(monkeypatch, error):
    config = SimpleNamespace(reward_enable=True, reward_quest_enable=True,
                             notify_template={"DailyPracticeCompleted": "每日实训已完成"})
    monkeypatch.setattr(quest, "cfg", config)
    monkeypatch.setattr(quest, "screen", Mock())
    scans = Mock(side_effect=[(400, TrainingCards({MATERIAL_TASK: True}), 0), (500, TrainingCards({}), 1)])
    action = Mock(return_value=False, side_effect=error)
    monkeypatch.setattr(quest.Quest, "scan", scans)
    monkeypatch.setattr(quest, "claimable_milestones", Mock(return_value=[]))
    record = Mock()
    monkeypatch.setattr(quest, "record_progress", record)
    monkeypatch.setattr(quest, "notify_reward", Mock())

    assert quest.Quest.settle(complete=True, actions=[(MATERIAL_TASK, action)])
    action.assert_called_once_with()
    assert scans.call_args_list == [call(True, read_tasks=True), call(True, read_tasks=False)]
    record.assert_called_once_with(config, 500)
