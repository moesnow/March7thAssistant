"""通过共享培养目标入口注入手机页面、迟到回执和局部识别故障。"""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
from PIL import Image
import pytest

from module.automation.input_base import input_deadline_reached
from module.connection_values import build_target_supported
from module.content_samples import SampleConfig
from module.content_visibility import Visibility
from module.game.adb_transport import AdbError
from module.overview import plan
from module.settings_registry import find_setting
from tasks.daily import buildtarget as shared
from tasks.power.policy import CAVERN, CRIMSON_CALYX, ECHO, GOLDEN_CALYX, ORNAMENT
from tasks.touch import buildtarget as touch, power, rewards
from utils.pause import RunStopRequested


TARGETS = [(CRIMSON_CALYX, "收容舱段"), (CAVERN, "漂泊之径"), (ORNAMENT, "浴火钢心")]
DROPS = json.loads(Path("assets/config/instance_drops.json").read_text(encoding="utf-8"))


def line(text, x=600, y=40):
    return [(x, y), (x + 40, y), (x + 40, y + 18), (x, y + 18)], (text, 0.99)


class MobileUI:
    def __init__(self, *, fault="", targets=TARGETS):
        self.fault, self.targets = fault, targets
        self.now = 0
        self.page, self.offset, self.selected = "list", 0, 0
        self.ready_at = 0
        self.ocr_result = []
        self.inputs, self.navigation = [], []
        self.misses = 0
        self.screenshot_scale_factor = 1
        self.screenshot_pos = (438, 255, 730, 368)

    def check_stop(self):
        if self.fault in ("stop-after-lookup", "stop-in-detail-lookup") and self.misses:
            raise RunStopRequested()

    def change_to(self, target, **_):
        self.check_stop()
        self.navigation.append(target)
        self.page = "list"

    def sleep(self, seconds):
        self.now += seconds

    def take_screenshot(self, crop=(0, 0, 1, 1)):
        if self.fault == "full-frame-once" and crop == (0, 0, 1, 1) and not self.misses:
            self.misses += 1
            raise AdbError("frame_timeout", "目标页首帧暂时不可用")
        pixels = np.zeros((368, 730, 3), dtype=np.uint8)
        for slot, index in enumerate(range(self.offset, min(len(self.targets), self.offset + 3))):
            y = (40, 170, 300)[slot]
            # 行纹理随副本移动，供实际 OpenCV 翻页锚点匹配。
            texture = np.random.default_rng(index).integers(0, 255, (76, 730, 3), dtype=np.uint8)
            pixels[y - 25:y + 51] = texture
        self.screenshot = Image.fromarray(pixels)
        self.screenshot_pos = (438, 255, 730, 368)
        return self.screenshot, self.screenshot_pos, 1

    def visible_positions(self):
        return [((600, y), (640, y + 18)) for y in (40, 170, 300)[:len(self.targets) - self.offset]]

    def perform_ocr(self):
        if self.fault == "ocr-once" and not self.misses:
            self.misses += 1
            self.ocr_result = []
        else:
            self.ocr_result = [line("进入", y=pos[0][1]) for pos in self.visible_positions()]

    def calculate_text_position(self, box, relative):
        dx, dy = (0, 0) if relative else self.screenshot_pos[:2]
        return (box[0][0] + dx, box[0][1] + dy), (box[2][0] + dx, box[2][1] + dy)

    def is_text_match(self, text, targets, include):
        return text in targets, text

    def find_element(self, target, kind, *_args, crop=None, **_):
        self.now += 0.02
        if self.fault == "frame-once" and isinstance(target, (tuple, list)) and "挑战" in target and not self.misses:
            self.misses += 1
            raise AdbError("frame_timeout", "暂时无帧")
        if self.fault == "deadline-after-lookup" and target == "培养目标":
            self.now += 100
        if self.fault == "stop-after-lookup" and target == "培养目标":
            self.misses += 1
        if target == "培养目标":
            return ((150, 180), (260, 211)) if crop == touch.TARGET_ENTRY else None
        if kind == "image":
            if str(target).endswith("/power.png"):
                if self.fault == "disconnected":
                    raise AdbError("disconnected", "设备已断开")
                if self.fault == "power-icon-missed-after-scroll" and self.offset > 0:
                    return None
                return ((874, 290), (897, 315)) if self.page == "list" else None
            if "drop_modal" in str(target):
                if self.page != "modal" or self.now < self.ready_at:
                    return None
                if str(target).endswith("drop_modal_panel.png"):
                    return ((166, 167), (196, 237))
                small = self.targets[self.selected][0] == CRIMSON_CALYX
                if str(target).endswith("drop_modal_close.png") and small:
                    return ((1040, 184), (1076, 217))
                if str(target).endswith("drop_modal_close2.png") and not small:
                    return ((1214, 19), (1251, 55))
                return None
        if isinstance(target, (tuple, list)) and "挑战" in target:
            if self.page == "instance" and self.now >= self.ready_at and not (
                    self.fault == "second-unavailable" and self.selected == 1):
                return ((950, 640), (1220, 683))
        if isinstance(target, (tuple, list)) and "进入" in target and self.page == "list":
            x, y, w, h = crop
            if y * 720 > 350 and self.fault in ("deadline-in-detail-lookup", "stop-in-detail-lookup"):
                self.misses += 1
                if self.fault == "deadline-in-detail-lookup":
                    self.now += 100
            return ((x * 1280, y * 720), ((x + w) * 1280, (y + h) * 720))
        if target == "饰品提取" and self.page == "instance" and self.targets[self.selected][0] == ORNAMENT:
            return ((88, 39), (220, 61))
        if target == "拟造花萼" and self.page == "modal":
            self.ocr_result = [line("拟造花萼【收容舱段】")]
            return ((500, 490), (800, 535))
        return None

    def find_image_with_multiple_targets(self, *_args, **_kwargs):
        if self.fault == "template-once" and not self.misses:
            self.misses += 1
            return []
        return [((436, pos[0][1]), (459, pos[1][1])) for pos in self.visible_positions()]

    def get_single_line_text(self, *, crop, **_):
        kind, name = self.targets[self.selected]
        if crop == touch.TARGET_NAME:
            return "丹恒·饮月"
        if crop == touch.INSTANCE_TYPE:
            return "拟造花萼" if kind == CRIMSON_CALYX else kind
        if crop == touch.INSTANCE_TITLE:
            return f"毁灭之蕾·{kind}" if kind == CRIMSON_CALYX else f"{name}·{kind}"
        if crop == touch.ORNAMENT_TITLE:
            return name + " 难度V"
        if crop in (touch.MATERIAL_TITLE, touch.RELIC_TITLE):
            return DROPS[kind][name][0]
        return None

    def click_element(self, target, kind, **_):
        if kind != "crop":
            # 基线的 PC 培养目标裁剪在手机上没有命中。
            return False
        return self.dispatch(target[0] * 1280, target[1] * 720)

    def click_element_with_pos(self, coords):
        return self.dispatch((coords[0][0] + coords[1][0]) / 2, (coords[0][1] + coords[1][1]) / 2)

    def dispatch(self, x, y):
        self.check_stop()
        if input_deadline_reached(self.now):
            return False
        self.inputs.append((round(x), round(y)))
        if x > 1000 and (y < 250 or self.page == "modal"):
            self.page = self.modal_parent if self.page == "modal" else "list"
        elif self.page == "list" and y > 255:
            slot = min(range(len(self.visible_positions())), key=lambda i: abs((40, 170, 300)[i] + 264 - y))
            self.selected = self.offset + slot
            if self.fault == "missed-second-tap" and self.selected == 1 and not self.misses:
                self.misses += 1
                return False
            self.page = "modal" if x < 600 else "instance"
            self.modal_parent = "list"
        elif self.page == "instance" and x in (845, 921):
            self.modal_parent, self.page = "instance", "modal"
        self.ready_at = self.now + (1.5 if self.fault == "late-receipt" else 0)
        # 模拟实际已送达、仅输入回执没有确认，页面仍应继续核对。
        return self.fault != "lost-input-receipt"

    def drag_mouse(self, start, end, *_args):
        self.check_stop()
        if input_deadline_reached(self.now):
            return False
        self.inputs.append("drag")
        if self.page == "list":
            self.offset = min(max(0, self.offset + (2 if end[1] < start[1] else -1)), len(self.targets) - 1)
        return True


@pytest.fixture
def mobile(monkeypatch):
    def install(fault="", scheme="instance", targets=TARGETS):
        ui = MobileUI(fault=fault, targets=targets)
        clock = SimpleNamespace(monotonic=lambda: ui.now, sleep=ui.sleep)
        config = SampleConfig()
        config.set_values({"control_backend": "adb", "ui_profile": "touch_720", "build_target_scheme": scheme})
        monkeypatch.setattr(shared, "cfg", config)
        monkeypatch.setattr(shared, "auto", ui)
        monkeypatch.setattr(shared, "screen", ui)
        monkeypatch.setattr(touch, "auto", ui)
        monkeypatch.setattr(touch, "screen", ui)
        monkeypatch.setattr(touch, "time", clock)
        monkeypatch.setattr("tasks.base.list_drag.time", clock)
        monkeypatch.setattr(touch.pause_ctl, "check_stop", ui.check_stop)
        monkeypatch.setattr(shared.Base, "send_notification_with_screenshot", Mock())
        monkeypatch.setattr(shared.BuildTarget, "_target_instances", {})
        monkeypatch.setattr(shared.BuildTarget, "_initialized", False)
        return ui, config
    return install


@pytest.mark.parametrize("scheme,fault", [
    ("instance", ""), ("drop", ""), ("instance", "ocr-once"), ("drop", "template-once"),
    ("instance", "late-receipt"), ("drop", "late-receipt"),
    ("instance", "lost-input-receipt"), ("drop", "lost-input-receipt"),
    ("instance", "frame-once"), ("instance", "missed-second-tap"),
    ("instance", "full-frame-once"),
])
def test_shared_entry_reads_mobile_targets_and_recovers_local_failures(mobile, scheme, fault):
    ui, _ = mobile(fault, scheme)
    shared.BuildTarget.init_build_targets()
    assert shared.BuildTarget.get_target_instances() == TARGETS
    assert ui.navigation == ["guide3"]
    assert sum(p == (494, 304) for p in ui.inputs) <= 1
    assert ui.now < 300 and ui.page == "list"


@pytest.mark.parametrize("scheme", ["instance", "drop"])
def test_mobile_pagination_keeps_overlapping_rows_once(mobile, scheme):
    targets = [(GOLDEN_CALYX, "回忆之蕾"), (CRIMSON_CALYX, "收容舱段"),
               (CAVERN, "漂泊之径"), (ECHO, "毁灭的开端"), (ORNAMENT, "浴火钢心")]
    ui, _ = mobile(scheme=scheme, targets=targets)
    shared.BuildTarget.init_build_targets()
    assert shared.BuildTarget.get_target_instances() == targets
    assert ui.inputs.count("drag") <= 5


def test_read_target_ornament_after_scroll_without_a_power_icon_match(mobile):
    targets = [(CRIMSON_CALYX, "收容舱段"), (CAVERN, "漂泊之径"),
               (CAVERN, "密伶之径"), (ORNAMENT, "孽果盘生")]
    ui, _ = mobile("power-icon-missed-after-scroll", targets=targets)
    shared.BuildTarget.init_build_targets()
    assert shared.BuildTarget.get_target_instances() == targets
    assert ui.page == "list" and ui.now < 30


def test_unavailable_detail_preserves_confirmed_targets(mobile):
    ui, _ = mobile("second-unavailable")
    shared.BuildTarget.init_build_targets()
    assert shared.BuildTarget.get_target_instances() == TARGETS[:1]
    assert ui.selected == 1 and ui.now < 110


@pytest.mark.parametrize("fault,stopped", [("deadline-after-lookup", False), ("stop-after-lookup", True)])
def test_no_input_after_lookup_exceeds_budget_or_receives_stop(mobile, fault, stopped):
    ui, _ = mobile(fault)
    with pytest.raises(RunStopRequested if stopped else RuntimeError):
        shared.BuildTarget.init_build_targets()
    assert ui.inputs == []


def test_device_disconnect_is_not_reported_as_an_empty_target(mobile):
    ui, _ = mobile("disconnected")
    with pytest.raises(AdbError) as failure:
        shared.BuildTarget.init_build_targets()
    assert failure.value.code == "disconnected"
    assert ui.inputs == [(205, 196)]


@pytest.mark.parametrize("fault,stopped", [("deadline-in-detail-lookup", False), ("stop-in-detail-lookup", True)])
def test_detail_retry_shares_deadline_and_stop_with_input(mobile, fault, stopped):
    ui, _ = mobile(fault)
    if stopped:
        with pytest.raises(RunStopRequested):
            shared.BuildTarget.init_build_targets()
    else:
        shared.BuildTarget.init_build_targets()
        assert shared.BuildTarget.get_target_instances() == TARGETS[:1]
    # 已读取第一行，第二行控件查找期间到期或停止后不再点按。
    assert ui.selected == 0 and ui.misses == 1


@pytest.mark.parametrize("platform,backend,expected", [
    ("win32", "adb", True), ("linux", "adb", True), ("android", "adb", True),
    ("win32", "cloud", False),
])
def test_adb_exposes_and_uses_build_targets(monkeypatch, platform, backend, expected):
    config = SampleConfig()
    config.set_values({"control_backend": backend, "ui_profile": "touch_720"})
    monkeypatch.setattr(sys, "platform", platform)
    assert build_target_supported(config) is expected
    assert ("build_target" in plan.plan_order(config, touch=True)) is expected
    if platform != "android":
        visibility = Visibility.read(config)
        for key in ("build_target_enable", "build_target_scheme", "build_target_ornament_weekly_count",
                    "build_target_use_user_instance_when_only_erosion_and_ornament"):
            assert visibility.setting(find_setting(key)) is expected


@pytest.mark.parametrize("continue_plan", [False, True])
def test_adb_power_uses_shared_target_after_the_power_plan(monkeypatch, continue_plan):
    config = SampleConfig()
    config.set_values({"control_backend": "adb", "ui_profile": "touch_720", "build_target_enable": True,
                       "power_plan": [[GOLDEN_CALYX, "回忆之蕾", 1]], "power_plan_continue": continue_plan})
    monkeypatch.setattr(power, "cfg", config)
    lookup = Mock(return_value=TARGETS[0])
    monkeypatch.setattr(shared.BuildTarget, "get_target_instance", lookup)
    runs = []

    def run(kind, name, planned, **_):
        runs.append((kind, name, planned))
        yield 1

    monkeypatch.setattr(power, "_run_instance", run)
    assert power.run()
    assert runs == [(GOLDEN_CALYX, "回忆之蕾", 1)] + ([(*TARGETS[0], None)] if continue_plan else [])
    assert lookup.call_count == int(continue_plan)


@pytest.mark.parametrize("platform", ["win32", "android"])
def test_adb_weekly_echo_uses_the_target(monkeypatch, platform):
    config = SampleConfig()
    config.set_values({"control_backend": "adb", "ui_profile": "touch_720", "build_target_enable": True,
                       "echo_of_war_start_day_of_week": 1, "instance_names": {ECHO: "不死的神实"}})
    monkeypatch.setattr(power, "cfg", config)
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(shared.BuildTarget, "get_target_echo_instance", Mock(return_value=(ECHO, "毁灭的开端")))
    runs = Mock(return_value=iter(()))
    monkeypatch.setattr(power, "_run_instance", runs)
    assert power.run_weekly_echo()
    assert runs.call_args.args == (ECHO, "毁灭的开端", None)


def test_adb_retry_prepares_targets_before_echo_without_other_tasks(monkeypatch):
    config = SampleConfig()
    config.set_values({"control_backend": "adb", "ui_profile": "touch_720", "build_target_enable": True,
                       "power_enable": True, "echo_of_war_enable": True, "reward_enable": False})
    monkeypatch.setattr(rewards, "cfg", config)
    calls = []
    monkeypatch.setattr(shared.BuildTarget, "init_build_targets", lambda: calls.append("target"))
    monkeypatch.setattr(rewards.daily, "support_demand", lambda **_: power.SupportDemand())
    monkeypatch.setattr(power, "run_weekly_echo", lambda **_: calls.append("echo") or True)
    monkeypatch.setattr(rewards.screen, "change_to", Mock())
    assert rewards.routine(only="echo")
    assert calls == ["target", "echo"]


@pytest.mark.parametrize("fallback", [None, RuntimeError("目标列表暂时不可用")])
def test_unavailable_target_falls_back_to_configured_instance(monkeypatch, fallback):
    config = SampleConfig()
    config.set_values({"control_backend": "adb", "ui_profile": "touch_720", "build_target_enable": True,
                       "power_plan": [], "instance_type": CAVERN, "instance_names": {CAVERN: "漂泊之径"}})
    monkeypatch.setattr(power, "cfg", config)
    lookup = Mock(side_effect=fallback) if isinstance(fallback, Exception) else Mock(return_value=fallback)
    monkeypatch.setattr(shared.BuildTarget, "get_target_instance", lookup)
    run = Mock(return_value=iter(()))
    monkeypatch.setattr(power, "_run_instance", run)
    assert power.run()
    assert run.call_args.args == (CAVERN, "漂泊之径", None)


@pytest.mark.parametrize("use_default,ornament_days,expected", [
    (False, 0, (CAVERN, "漂泊之径")), (False, 7, (ORNAMENT, "浴火钢心")), (True, 7, None),
])
def test_mobile_targets_share_pc_relic_and_ornament_selection(monkeypatch, use_default, ornament_days, expected):
    config = SampleConfig()
    config.set_values({"build_target_ornament_weekly_count": ornament_days,
                       "build_target_use_user_instance_when_only_erosion_and_ornament": use_default})
    monkeypatch.setattr(shared, "cfg", config)
    monkeypatch.setattr(shared.BuildTarget, "_initialized", True)
    monkeypatch.setattr(shared.BuildTarget, "_target_instances", {CAVERN: ["漂泊之径"], ORNAMENT: ["浴火钢心"]})
    assert shared.BuildTarget.get_target_instance() == expected


@pytest.mark.parametrize("original,enlarged,expected,calls", [
    ("月狂獠牙", [], "月狂獠牙", 0),
    ("月狂猿牙", [("月狂獠牙", 0.87)], "月狂獠牙", 1),
    ("月狂猿牙", [("月狂療牙", 0.83), ("月狂猿牙", 0.84)], "月狂猿牙", 2),
])
def test_drop_title_only_rechecks_unknown_text_using_enlarged_pixels(monkeypatch, original, enlarged, expected, calls):
    ui = Mock(screenshot=Image.new("RGB", (480, 45)))
    ui.take_screenshot.return_value = (ui.screenshot, (497, 180, 480, 45), 1)
    ui.get_single_line_text.return_value = original
    monkeypatch.setattr(touch, "auto", ui)
    recognize = Mock(side_effect=enlarged)
    monkeypatch.setattr(touch.ocr, "recognize_single_line", recognize)
    assert touch.TouchDropHandler().read_drop_name(touch.MATERIAL_TITLE) == expected
    assert recognize.call_count == calls
    if calls:
        assert recognize.call_args_list[0].args[0].shape == (90, 960, 3)


def test_stable_rare_character_error_requires_a_unique_drop_name(monkeypatch):
    ui = Mock(screenshot=Image.new("RGB", (480, 45)))
    ui.take_screenshot.return_value = (ui.screenshot, (497, 180, 480, 45), 1)
    ui.get_single_line_text.return_value = "一杯酪配的时代"
    monkeypatch.setattr(touch, "auto", ui)
    monkeypatch.setattr(touch.ocr, "recognize_single_line", Mock(return_value=("一杯酪酊的时代", 0.97)))
    handler = touch.TouchDropHandler()
    assert handler.read_drop_name(touch.MATERIAL_TITLE) == "一杯酩酊的时代"
    assert handler.last_drop_reading["text"] == "一杯酪酊的时代"
    assert handler.last_drop_reading["method"] == "unique_vocabulary"
    # 两个近似候选相差不够时保留原文，交回 PC 的匹配逻辑处理。
    handler._instance_drops.append(("另一种类型", "另一副本", "一杯酪酉的时代"))
    assert handler.read_drop_name(touch.MATERIAL_TITLE) == "一杯酪配的时代"


def test_missing_rare_edge_character_requires_one_unambiguous_completion(monkeypatch):
    ui = Mock(screenshot=Image.new("RGB", (480, 45)))
    ui.take_screenshot.return_value = (ui.screenshot, (497, 180, 480, 45), 1)
    ui.get_single_line_text.return_value = "笑丑面"
    monkeypatch.setattr(touch, "auto", ui)
    monkeypatch.setattr(touch.ocr, "recognize_single_line", Mock(return_value=("笑丑面", 0.99)))
    handler = touch.TouchDropHandler()
    assert handler.read_drop_name(touch.MATERIAL_TITLE) == "嗤笑丑面"
    handler._instance_drops.append(("另一种类型", "另一副本", "嘲笑丑面"))
    assert handler.read_drop_name(touch.MATERIAL_TITLE) == "笑丑面"


def test_drop_title_is_read_after_fade_settles(monkeypatch):
    frames = [Image.new("RGB", (480, 45), color) for color in ("black", "gray", "white", "white", "white")]
    ui = Mock(screenshot=frames[-1])
    ui.take_screenshot.side_effect = [(frame, (497, 180, 480, 45), 1) for frame in frames]
    ui.get_single_line_text.return_value = "叩问天工的名冶"
    monkeypatch.setattr(touch, "auto", ui)
    monkeypatch.setattr(touch.time, "sleep", Mock())
    assert touch.TouchDropHandler().read_drop_name(touch.MATERIAL_TITLE) == "叩问天工的名冶"
    assert ui.take_screenshot.call_count == 5
    ui.get_single_line_text.assert_called_once()
