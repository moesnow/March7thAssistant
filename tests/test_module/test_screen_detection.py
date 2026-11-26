import importlib
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image
import psutil
import pytest

from module.automation.automation import Automation
from module.game.adb import _pixel_crop
from module.screen.screen import Screen


@pytest.fixture
def detection(monkeypatch):
    screen_module = importlib.import_module("module.screen.screen")
    automation_module = importlib.import_module("module.automation.automation")
    config = SimpleNamespace(control_backend="adb", ui_profile="touch_720")
    monkeypatch.setattr(screen_module, "cfg", config)
    monkeypatch.setattr(automation_module, "cfg", config)
    monkeypatch.setattr(screen_module, "time", SimpleNamespace(sleep=lambda _: None))
    monkeypatch.setattr(screen_module.os, "cpu_count", lambda: 4)
    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(available=4 * 1024**3))

    auto = object.__new__(Automation)
    auto.logger = Mock()
    auto.img_cache = {}
    auto._is_debug_enabled = lambda: False
    monkeypatch.setattr(screen_module, "auto", auto)
    screen = object.__new__(Screen)
    screen.__init__("assets/touch_720/screens.json", Mock())
    screen.screen_map = {key: value for key, value in screen.screen_map.items() if key in ("main", "monthly_card", "menu")}
    return screen, auto, config


def test_main_to_menu_does_not_replace_the_frame_while_detection_workers_are_matching(detection):
    screen, auto, _ = detection
    pending, release, finished = Event(), Event(), Event()
    state = "main"
    clicks = []
    crops_during_matching = []

    def capture(crop=(0, 0, 1, 1), *args, **kwargs):
        frame = Image.new("RGB", (1280, 720), (35, 35, 35))
        with Image.open(screen.screen_map[state]["image_path"]) as icon:
            frame.paste(icon, (20, 48) if state == "main" else (1120, 70))
        x, y, width, height = _pixel_crop(crop)
        auto.screenshot = frame.crop((x, y, x + width, y + height))
        auto.screenshot_pos = (x, y, width, height)
        auto.screenshot_scale_factor = 1
        if crop != (0, 0, 1, 1):
            assert (width, height) == (48, 52)
            crops_during_matching.append(not finished.is_set())
            release.set()
            assert finished.wait(2), "识别线程未按期结束"
        return auto.screenshot, auto.screenshot_pos, 1

    def tap(x, y):
        nonlocal state
        assert state == "main" and 20 <= x <= 53 and 48 <= y <= 80
        clicks.append((x, y))
        state = "menu"
        return True

    original_find = auto.find_image_element

    def delayed_find(target, *args, **kwargs):
        if target.endswith("monthly_card.png"):
            pending.set()
            try:
                # 原实现提前返回后，导航会在这里将共享截图换成 48×52，
                # 使仍在识别 131×33 列车补给模板的线程触发 OpenCV 尺寸断言。
                release.wait(0.5)
                return original_find(target, *args, **kwargs)
            finally:
                finished.set()
        if target.endswith("main.png"):
            assert pending.wait(2), "未启动并发识别"
        return original_find(target, *args, **kwargs)

    auto.take_screenshot = capture
    auto.mouse_click = tap
    auto.find_image_element = delayed_find
    try:
        screen.change_to("menu", max_recursion=0)
    finally:
        release.set()
        assert finished.wait(2), "测试结束时仍有识别线程运行"

    assert state == screen.current_screen == "menu"
    assert len(clicks) == 1
    assert not auto.logger.error.call_args_list, auto.logger.error.call_args_list
    assert crops_during_matching == [False]


@pytest.mark.parametrize("backend, profile, level", [
    ("adb", "touch_720", "debug"),
    ("local", "pc_1080", "error"),
    ("cloud", "pc_1080", "error"),
])
def test_unknown_screen_uses_debug_only_for_adb(detection, backend, profile, level):
    screen, auto, config = detection
    config.control_backend, config.ui_profile = backend, profile
    screen._find_screen_image = Mock(return_value=False)
    screen._matches_text_fallback = Mock(return_value=False)
    auto.take_screenshot = Mock()
    assert screen.get_current_screen(autotry=False) is False
    getattr(screen.logger, level).assert_any_call("当前界面：未知")
    if backend == "adb":
        screen.logger.error.assert_not_called()
        with pytest.raises(RuntimeError, match="无法识别当前游戏界面"):
            screen.ensure_current_screen_is_clean(autotry=False)
        screen.logger.error.assert_called_with("无法识别当前游戏界面")
