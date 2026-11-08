"""#1175 回归：跨周继续进度时的“当前存档非本周演算进度”确认框。

周期演算每周一 4:00 更新。循环运行跨过这个时间点后，上一次的存档已属于上一周，
点“继续进度”会先弹确认框“当前存档非本周演算进度，进度所在玩法已过期，仍可获得
拟合值和「模拟宇宙」积分，确定继续进度吗？”。旧实现只等关卡界面标记，弹窗会把
原本用于等待关卡界面的 120 次重试耗光，最后误报“重新进入关卡失败”并终止任务。

本用例用模拟的识别/点击接口驱动真实 DivergentUniverse.process_re_enter()，
不依赖游戏窗口与截图。
"""
import importlib.util
import sys
import time
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROMPT_TEXT = "当前存档非本周演算进度"
STAGE_IMAGE = "./assets/images/screen/divergent_universe/stage.png"
# 弹窗“确认”按钮所在区域（取自 #1175 截图，confirm.png 在该区域内匹配度 0.99）
CONFIRM_CROP = (1100 / 1920, 630 / 1080, 280 / 1920, 82 / 1080)
_MODULE = None


def _stub(name, **members):
    module = ModuleType(name)
    for key, value in members.items():
        setattr(module, key, value)
    return module


class _FakeGame:
    """重新进入关卡时的界面状态。"""

    def __init__(self, stale_cycle_dialog=False, stage_ready_after=0, confirm_works=True):
        self.dialog_visible = stale_cycle_dialog
        self.confirm_works = confirm_works
        self.stage_ready_after = stage_ready_after  # 查询多少次之后关卡界面才出现
        self.stage_queries = 0
        self.stage_seen = False
        self.prompt_probes = 0
        self.confirm_clicks = []

    def query_stage(self):
        self.stage_queries += 1
        visible = self.stage_queries > self.stage_ready_after and not self.dialog_visible
        self.stage_seen = self.stage_seen or visible
        return visible

    def query_prompt(self):
        self.prompt_probes += 1
        return self.dialog_visible

    def click_confirm(self, crop):
        self.confirm_clicks.append(crop)
        if self.confirm_works:
            self.dialog_visible = False
        return self.confirm_works


class _FakeAuto:
    def __init__(self, game):
        self.game = game

    def press_key(self, key, *args, **kwargs):
        return True

    def click_element(self, target, find_type=None, threshold=None, *args, **kwargs):
        if find_type == "text" and target in ("暂离", "继续进度"):
            return True
        if find_type == "image" and isinstance(target, str) and target.endswith("zh_CN/base/confirm.png"):
            return self.game.click_confirm(kwargs.get("crop"))
        return False

    def find_element(self, target, find_type=None, threshold=None, **kwargs):
        if find_type == "image" and target == STAGE_IMAGE:
            return self.game.query_stage()
        if find_type == "text" and target == PROMPT_TEXT:
            return self.game.query_prompt()
        return False


class _FakeScreen:
    def wait_for_screen_change(self, *args, **kwargs):
        return True

    def change_to(self, *args, **kwargs):
        return None


def _load_divergent():
    """加载一次被测模块；每个用例自己替换它引用的 auto。"""
    global _MODULE
    if _MODULE is None:
        stubs = {
            "module.screen": _stub("module.screen", screen=_FakeScreen()),
            "module.automation": _stub("module.automation", auto=MagicMock()),
            "module.config": _stub("module.config", cfg=MagicMock()),
            "module.logger": _stub("module.logger", log=MagicMock()),
            "module.automation.screenshot": _stub("module.automation.screenshot", Screenshot=MagicMock()),
            "module.notification.notification": _stub("module.notification.notification", NotificationLevel=MagicMock()),
            "tasks.base.base": _stub("tasks.base.base", Base=MagicMock()),
            "tasks.power.power": _stub("tasks.power.power", Power=MagicMock()),
        }
        path = ROOT / "tasks" / "weekly" / "divergent_universe.py"
        spec = importlib.util.spec_from_file_location("divergent_universe_under_test", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, stubs):
            spec.loader.exec_module(module)
        _MODULE = module
    return _MODULE


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """等待关卡界面的循环最多 120 次，测试里不需要真的等。"""
    monkeypatch.setattr(time, "sleep", lambda *args, **kwargs: None)


def test_re_enter_confirms_stale_cycle_prompt():
    """#1175：弹窗出现时点“确认”继续进度，随后正常进入关卡。"""
    game = _FakeGame(stale_cycle_dialog=True)
    module = _load_divergent()
    module.auto = _FakeAuto(game)

    module.DivergentUniverse().process_re_enter()

    assert game.confirm_clicks == [CONFIRM_CROP]
    assert game.dialog_visible is False
    assert game.stage_seen is True


def test_re_enter_without_prompt_is_unchanged():
    """常态路径：不弹窗时既不点确认，也不做多余的弹窗 OCR 探测。"""
    game = _FakeGame()
    module = _load_divergent()
    module.auto = _FakeAuto(game)

    module.DivergentUniverse().process_re_enter()

    assert game.stage_seen is True
    assert game.confirm_clicks == []
    assert game.prompt_probes == 0


def test_re_enter_still_fails_when_prompt_cannot_be_dismissed():
    """弹窗点不掉（例如按钮没点中）时仍然如实报错，不掩盖失败。"""
    game = _FakeGame(stale_cycle_dialog=True, confirm_works=False)
    module = _load_divergent()
    module.auto = _FakeAuto(game)

    with pytest.raises(RuntimeError, match="重新进入关卡失败"):
        module.DivergentUniverse().process_re_enter()
