"""游戏分辨率检查的判定规则。

模板素材以目标分辨率为基准绘制，`cv2.matchTemplate` 对尺度零容忍，因此只要窗口不小于目标、
且宽高比与目标一致，就能用同一个因子等比缩放到目标坐标系，无需强制用户改分辨率。

按 tests/test_utils/test_registry_startup_crossplatform.py 的做法直接加载模块，
避免为了导入 starrailcontroller 而牵出 cv2 / selenium / onnxruntime 等运行期重依赖。
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def controller_module(monkeypatch):
    """加载 starrailcontroller，用替身顶掉本地游戏控制器与注册表依赖。"""
    local = types.ModuleType("module.game.local")

    class LocalGameController:
        def __init__(self, cfg=None, logger=None):
            self.cfg = cfg
            self.logger = logger

    local.LocalGameController = LocalGameController
    monkeypatch.setitem(sys.modules, "module.game.local", local)

    config = types.ModuleType("module.config.config")
    config.Config = object
    monkeypatch.setitem(sys.modules, "module.config.config", config)

    registry = types.ModuleType("utils.registry.star_rail_setting")
    for name in ("get_game_resolution", "set_game_resolution", "get_auto_battle_open_setting",
                 "get_is_save_battle_speed_setting", "get_user_speed_up_open_setting",
                 "set_auto_battle_open_setting", "set_is_save_battle_speed_setting",
                 "set_user_speed_up_open_setting"):
        setattr(registry, name, lambda *a, **k: None)
    monkeypatch.setitem(sys.modules, "utils.registry.star_rail_setting", registry)

    hdr = types.ModuleType("utils.registry.game_auto_hdr")
    hdr.get_game_auto_hdr = lambda *a, **k: None
    hdr.set_game_auto_hdr = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, "utils.registry.game_auto_hdr", hdr)

    account = types.ModuleType("utils.registry.gameaccount")
    account.gamereg_uid = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, "utils.registry.gameaccount", account)

    spec = importlib.util.spec_from_file_location(
        "test_starrail_controller", ROOT / "tasks/game/starrailcontroller.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_controller(monkeypatch, module, resolutions, screen=(3840, 2160)):
    """构造只带 check_resolution 所需依赖的控制器。"""
    monkeypatch.setattr(module.pause_ctl, "checkpoint", lambda: None)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    errors = []
    queue = list(resolutions)

    def next_resolution():
        return queue.pop(0) if len(queue) > 1 else queue[0]

    controller = types.SimpleNamespace(
        screen_resolution=screen,
        get_resolution=next_resolution,
        log_debug=lambda message: None,
        log_error=lambda message: errors.append(message),
    )
    return controller, errors


@pytest.mark.parametrize("resolution", [
    (1920, 1080),  # 与目标一致
    (2560, 1440),  # 2K 16:9
    (3840, 2160),  # 4K 16:9
    (5120, 2880),  # 5K 16:9
])
def test_larger_16_9_is_accepted(controller_module, monkeypatch, resolution):
    """不小于目标的 16:9 分辨率都能等比缩放，必须放行。"""
    controller, errors = make_controller(monkeypatch, controller_module, [resolution])

    controller_module.StarRailController.check_resolution(controller, 1920, 1080)

    assert errors == []


@pytest.mark.parametrize("resolution", [
    (1366, 768),   # 16:9 但小于目标
    (1600, 900),   # 16:9 但小于目标
    (2560, 1080),  # 21:9
    (3840, 1080),  # 32:9
    (1920, 1200),  # 16:10
    (2560, 1600),  # 16:10 2K
    (2160, 2160),  # 1:1
])
def test_non_matching_resolution_is_rejected(controller_module, monkeypatch, resolution):
    controller, errors = make_controller(monkeypatch, controller_module, [resolution])

    with pytest.raises(controller_module.GameResolutionMismatch):
        controller_module.StarRailController.check_resolution(controller, 1920, 1080)

    assert any(f"{resolution[0]}x{resolution[1]}" in message for message in errors)


def test_integer_aspect_check_matches_float_for_common_resolutions(controller_module, monkeypatch):
    """整数判定与浮点判定对常见 16:9 分辨率给出相同结论。

    用整数乘法只是为了避开 1366/768 这类近似 16:9 的浮点比较歧义，
    并不假设 2560/1440 存在浮点误差——它其实精确等于 1920/1080。
    """
    for width, height in [(2560, 1440), (3840, 2160), (5120, 2880), (7680, 4320)]:
        assert width / height == 1920 / 1080
        controller, errors = make_controller(monkeypatch, controller_module, [(width, height)])
        controller_module.StarRailController.check_resolution(controller, 1920, 1080)
        assert errors == []


def test_touch_profile_target_is_honoured(controller_module, monkeypatch):
    """触屏档目标为 1280x720 时，按同一规则接受更大的 16:9 窗口。"""
    controller, errors = make_controller(monkeypatch, controller_module, [(1920, 1080)])

    controller_module.StarRailController.check_resolution(controller, 1280, 720)

    assert errors == []


def test_error_message_mentions_larger_16_9_support(controller_module, monkeypatch):
    controller, errors = make_controller(monkeypatch, controller_module, [(2560, 1080)])

    with pytest.raises(controller_module.GameResolutionMismatch):
        controller_module.StarRailController.check_resolution(controller, 1920, 1080)

    assert any("16:9" in message for message in errors)


def test_exact_match_still_accepted(controller_module, monkeypatch):
    """回归保护：原有精确相等的路径行为不变。"""
    controller, errors = make_controller(monkeypatch, controller_module, [(1920, 1080)])

    controller_module.StarRailController.check_resolution(controller, 1920, 1080)

    assert errors == []
