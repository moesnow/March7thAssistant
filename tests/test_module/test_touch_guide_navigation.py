"""真实五标签导航条取材；六标签用在左端插入一格模拟行动摘要布局。"""
import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image
import psutil
import pytest

from module.automation.automation import Automation
from module.screen.screen import Screen


ROOT = Path(__file__).resolve().parents[2]
TABS = ("guide2", "guide3", "guide5", "guide4", "guide6")


class GuideGame:
    def __init__(self, extra_tab, initial="guide2"):
        self.extra_tab = extra_tab
        self.state = initial
        self.clicks = []

    def frame(self):
        frame = Image.new("RGB", (1280, 720), (35, 35, 35))
        with Image.open(ROOT / f"tests/fixtures/touch_guide_tabs/{self.state}.png") as header:
            frame.paste(header, (90 + 90 * self.extra_tab, 84))
        return frame

    def tap(self, x, y):
        assert 84 <= y < 144, "导航只能点击顶部标签栏"
        index = round((x - 189 - 90 * self.extra_tab) / 90)
        assert 0 <= index < len(TABS), "点中了行动摘要或标签栏之外"
        self.clicks.append((x, y))
        self.state = TABS[index]
        return True


@pytest.fixture
def guide(monkeypatch):
    screen_module = importlib.import_module("module.screen.screen")
    automation_module = importlib.import_module("module.automation.automation")
    config = SimpleNamespace(ui_profile="touch_720", control_backend="adb")
    monkeypatch.setattr(screen_module, "cfg", config)
    monkeypatch.setattr(automation_module, "cfg", config)
    monkeypatch.setattr(screen_module.time, "sleep", lambda *_: None)
    # 导航用例走确定的串行分支，避免后台识别线程越过 fixture 的隔离边界。
    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(available=0))

    def build(extra_tab, initial="guide2"):
        game = GuideGame(extra_tab, initial)
        auto = object.__new__(Automation)
        auto.logger = Mock()
        auto.img_cache = {}
        auto._is_debug_enabled = lambda: False
        auto.mouse_click = game.tap

        def capture(crop=(0, 0, 1, 1), *args, **kwargs):
            image = game.frame()
            x, y, width, height = (round(v * size) for v, size in zip(crop, (1280, 720, 1280, 720)))
            auto.screenshot = image.crop((x, y, x + width, y + height))
            auto.screenshot_pos = (x, y, width, height)
            auto.screenshot_scale_factor = 1
            return auto.screenshot, auto.screenshot_pos, 1

        auto.take_screenshot = capture
        capture()
        monkeypatch.setattr(screen_module, "auto", auto)
        screen = object.__new__(Screen)
        screen.__init__(ROOT / "assets/touch_720/screens.json", Mock())
        return screen, game, auto

    return build


@pytest.mark.parametrize("extra_tab", [False, True], ids=["five-tabs", "six-tabs"])
@pytest.mark.parametrize(("initial", "target"), [
    ("guide2", "guide3"), ("guide3", "guide2"),
    ("guide2", "guide5"), ("guide2", "guide4"), ("guide2", "guide6"),
    ("guide6", "guide3"),
])
def test_navigates_by_tab_icon_in_both_layouts(guide, extra_tab, initial, target):
    screen, game, auto = guide(extra_tab, initial)

    screen.change_to(target, max_recursion=1)

    assert game.state == screen.current_screen == target
    assert len(game.clicks) == (2 if initial == "guide6" else 1)


@pytest.mark.parametrize("extra_tab", [False, True], ids=["five-tabs", "six-tabs"])
@pytest.mark.parametrize("decoy", ["old-icon", "whole-tab"])
def test_selected_tab_matching_ignores_identical_content_and_preserves_the_frame(guide, extra_tab, decoy):
    screen, game, auto = guide(extra_tab, "guide3")
    image = game.frame()
    with Image.open(ROOT / "tests/fixtures/touch_guide_tabs/guide2.png") as header:
        selected_daily = header.crop((49, 0, 149, 60))
        if decoy == "old-icon":
            # 原素材只有图标本体，行动摘要的内容卡片也可能显示同形图标。
            selected_daily = selected_daily.crop((28, 10, 64, 51))
        image.paste(selected_daily, (200, 320))
    auto.screenshot = image

    assert not screen.check_screen("guide2", take_screenshot=False)
    assert screen.check_screen("guide3", take_screenshot=False)
    assert auto.screenshot is image and image.size == (1280, 720)
    auto.take_screenshot = Mock(return_value=(image, (0, 0, 1280, 720), 1))
    screen._reset_screen_state()
    assert screen.get_current_screen(autotry=False)
    assert screen.current_screen == "guide3"
    assert auto.screenshot is image


def test_tab_clicking_ignores_an_identical_icon_outside_the_navigation_bar(guide):
    screen, game, auto = guide(True, "guide2")
    capture = auto.take_screenshot

    def with_decoy(*args, **kwargs):
        result = capture(*args, **kwargs)
        if auto.screenshot.size == (1280, 720):
            with Image.open(ROOT / "assets/touch_720/images/guide/enter_guide3.png") as icon:
                auto.screenshot.paste(icon, (600, 350))
        return result

    auto.take_screenshot = with_decoy
    screen.change_to("guide3", max_recursion=1)

    assert game.state == "guide3"
    assert len(game.clicks) == 1
