"""触屏战败退出：走日常、历战余响、识别和点击入口，保留战败与后续任务结果。"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from module.automation import automation
from module.automation.input_base import begin_input_dispatch, limit_input_deadline
from tasks.base import task_steps
from tasks.base.task_steps import GameRecoveryError
from tasks.touch import power, rewards
from utils.pause import RunStopRequested


class DefeatDevice:
    """只有战败标题或退出按钮的结果页；输入与转场回执彼此独立。"""

    def __init__(self, mode):
        self.mode = mode
        self.now = 0.0
        self.page = "main"
        self.snapshot_page = self.page
        self.crop = (0, 0, 1, 1)
        self.pending = None
        self.inputs = []
        self.stopped = False
        self.injected = False
        self.battles = 0
        self.current_screen = "main"
        self.auto = object.__new__(automation.Automation)
        self.auto.logger = Mock()
        self.auto._is_debug_enabled = lambda: False
        self.auto.take_screenshot = self.capture
        self.auto.find_image_element = self.match_image
        self.auto.mouse_click = self.click

    def sleep(self, seconds):
        self.now += seconds
        self.settle()

    def settle(self):
        if self.pending is not None and self.now >= self.pending:
            self.pending = None
            self.page = "main"

    def capture(self, crop=(0, 0, 1, 1), *_args):
        self.settle()
        self.snapshot_page = self.page
        self.crop = crop
        if self.page == "defeat" and crop == power.EXIT and not self.injected:
            self.injected = True
            if self.mode == "deadline-during-lookup":
                self.now += 10
            elif self.mode == "stop-during-lookup":
                self.stopped = True
            elif self.mode == "screenshot-miss":
                raise RuntimeError("一帧截图失败")
        x, y, width, height = [round(value * size) for value, size in zip(crop, (1280, 720, 1280, 720))]
        self.auto.screenshot = Image.new("RGB", (max(1, width), max(1, height)))
        self.auto.screenshot_pos = (x, y, width, height)
        self.auto.screenshot_scale_factor = 1
        return self.auto.screenshot, self.auto.screenshot_pos, 1

    def recognize(self, _pixels):
        if self.mode == "ocr-miss" and self.snapshot_page == "defeat" and self.crop == power.EXIT:
            self.mode = "title-only"
            raise RuntimeError("一帧 OCR 失败")
        labels = []
        if self.snapshot_page == "defeat":
            labels.append(("战斗失败", 580, 120, 700, 160))
            if self.mode in ("exit-button", "deadline-during-lookup", "stop-during-lookup"):
                labels.append(("退出关卡", 580, 620, 700, 650))
        x, y, width, height = self.auto.screenshot_pos
        return [
            ([(left - x, top - y), (right - x, top - y), (right - x, bottom - y), (left - x, bottom - y)],
             (label, 0.99))
            for label, left, top, right, bottom in labels
            if x <= left and right <= x + width and y <= top and bottom <= y + height
        ]

    def match_image(self, path, *_args):
        if path.endswith("pause.png") and self.snapshot_page == "battle":
            self.page = "defeat"
            return (0, 0), (20, 20), 1
        return None, None, 0

    def click(self, x, y):
        self.check_stop()
        if not begin_input_dispatch(self.now):
            return False
        self.inputs.append((round(self.now, 2), self.page, x, y))
        if self.mode == "input-unavailable":
            return False
        if self.page == "defeat":
            # 标题只负责确认退出；故障用例即使回执丢失，也可能已经执行。
            if self.pending is None:
                self.pending = self.now + (3.2 if self.mode == "late-receipt" else 0.8)
            return self.mode != "late-receipt"
        raise AssertionError(f"不应在 {self.page} 点击 {x}, {y}")

    def check_stop(self):
        if self.stopped:
            raise RunStopRequested()

    def check_screen(self, target):
        self.settle()
        if self.page == "defeat" and self.mode in ("frame-miss", "frames-unavailable"):
            if self.mode == "frame-miss":
                self.mode = "title-only"
            raise power.AdbError("frame_timeout", "暂时没有新帧")
        if self.page == target:
            self.current_screen = target
            return True
        return False

    def change_to(self, target, **_kwargs):
        self.settle()
        if self.page not in ("main", "echo", "guide3"):
            raise RuntimeError("无法识别当前游戏界面")
        self.page = self.current_screen = target

    def enter(self, *_args, **_kwargs):
        self.page = "echo"

    def start(self, *_args, **_kwargs):
        self.page = "battle"
        self.battles += 1
        return 1, False


@pytest.fixture
def defeat_run(monkeypatch):
    def build(mode):
        device = DefeatDevice(mode)
        config = SimpleNamespace(
            power_enable=True, echo_of_war_enable=True, daily_enable=True, reward_enable=False,
            borrow_enable=False, echo_of_war_start_day_of_week=1, instance_names={power.ECHO: "毁灭的开端"},
            instance_names_challenge_count={}, tp_before_instance=False, save_timestamp=Mock(),
        )
        clock = SimpleNamespace(monotonic=lambda: device.now, sleep=device.sleep)
        for module in (power, rewards):
            monkeypatch.setattr(module, "cfg", config)
            monkeypatch.setattr(module, "screen", device)
        monkeypatch.setattr(task_steps, "screen", device)
        monkeypatch.setattr(power, "auto", device.auto)
        monkeypatch.setattr(automation, "ocr", SimpleNamespace(recognize_multi_lines=device.recognize))
        monkeypatch.setattr(automation, "time", clock)
        monkeypatch.setattr("utils.wait.time", clock)
        monkeypatch.setattr(power, "time", clock)
        monkeypatch.setattr(power, "game_option_enabled", lambda *_args: False)
        monkeypatch.setattr(power.pause_ctl, "check_stop", device.check_stop)
        monkeypatch.setattr(power, "_select_category", Mock())
        monkeypatch.setattr(power, "_enter_instance", device.enter)
        monkeypatch.setattr(power, "_reenter_instance", device.enter)
        monkeypatch.setattr(power, "_start_challenge", device.start)
        power_value = Mock(return_value=90)
        rewards_left = Mock(return_value=3)
        monkeypatch.setattr(power, "read_power", power_value)
        monkeypatch.setattr(power, "_read_echo_rewards", rewards_left)
        monkeypatch.setattr(power, "_supplement", lambda value: value)
        monkeypatch.setattr(power, "run", Mock(return_value=True))
        monkeypatch.setattr(rewards.daily, "support_demand", lambda **_kwargs: power.SupportDemand(False))
        daily = Mock(return_value=True)
        monkeypatch.setattr(rewards.daily, "run", daily)
        steps = []

        def run():
            # 外层截止时间也传到识别和输入，不能在查找后的点击中重新获得时间。
            with limit_input_deadline(5 if mode == "deadline-during-lookup" else None):
                return rewards.routine(on_step=lambda *args: steps.append(args))

        return device, config, power_value, rewards_left, daily, steps, run
    return build


@pytest.mark.parametrize("mode", ["title-only", "exit-button", "ocr-miss", "screenshot-miss", "frame-miss", "late-receipt"])
def test_defeat_is_recorded_but_later_daily_tasks_continue(defeat_run, mode):
    device, config, power_value, rewards_left, daily, steps, run = defeat_run(mode)
    assert run() is False
    assert device.page == "main"
    assert device.battles == 3
    assert len(device.inputs) == 3
    assert ("历战余响", "failed", None) in steps
    assert ("每日实训", "succeeded", None) in steps
    daily.assert_called_once()
    power_value.assert_called_once()
    rewards_left.assert_called_once()
    config.save_timestamp.assert_not_called()


@pytest.mark.parametrize("mode", ["frames-unavailable", "input-unavailable", "deadline-during-lookup"])
def test_unavailable_defeat_exit_stops_clearly_without_advancing_progress(defeat_run, mode):
    device, config, power_value, rewards_left, daily, steps, run = defeat_run(mode)
    with pytest.raises(GameRecoveryError, match="历战余响失败后无法回到可操作界面"):
        run()
    assert device.battles == 1
    assert len(device.inputs) <= (3 if mode == "input-unavailable" else 0)
    assert ("历战余响", "failed", None) in steps
    daily.assert_not_called()
    config.save_timestamp.assert_not_called()
    power_value.assert_called_once()
    rewards_left.assert_called_once()


def test_stop_during_result_lookup_prevents_all_further_input(defeat_run):
    device, config, _power, _rewards, daily, steps, run = defeat_run("stop-during-lookup")
    with pytest.raises(RunStopRequested):
        run()
    assert not device.inputs
    assert device.battles == 1
    assert ("历战余响", "failed", None) not in steps
    daily.assert_not_called()
    config.save_timestamp.assert_not_called()
