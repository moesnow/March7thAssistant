"""界面图导航回归测试：esc 落点会随入口不同而变（#1218）。

游戏里按 esc 是“返回上一级”，返回栈取决于当初是怎么进来的：

- 从 手机菜单 -> 星际和平指南 -> 生存索引，栈是 主界面 / 手机菜单 / 生存索引，
  所以 生存索引 按 esc 回 手机菜单；
- 但从 生存索引 点击副本的“进入/跳转”到达队伍界面后，返回栈是
  主界面 / 生存索引 / 队伍（手机菜单不在栈里）：队伍 按 esc 回 生存索引、
  生存索引 按 esc 直接回 主界面，跳过了手机菜单。

`assets/config/screens.json` 只能描述常态落点（guide3 -esc-> menu），于是第二条
路径下 change_to() 一直等不到 手机菜单，重试预算耗尽后抛“无法切换到指定游戏
界面”，背包遗器已满时的自动分解就此中断。

本用例用真实 screens.json + 模拟返回栈驱动真实 Screen.change_to()，
不依赖游戏窗口与截图。
"""
import importlib.util
import sys
import threading
import time
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
SCREENS_CONFIG = ROOT / "assets" / "config" / "screens.json"

# 从副本队伍界面出发（跳转进入）：返回栈里没有手机菜单，且首次 esc 被浮层吞掉
JUMP_ENTRY_STACK = ["main", "guide3", "configure_team"]
# 从手机菜单进入生存索引：返回栈正常
MENU_ENTRY_STACK = ["main", "menu", "guide3"]


def _stub(name, **members):
    module = ModuleType(name)
    for key, value in members.items():
        setattr(module, key, value)
    return module


class _FakeGame:
    """只实现本用例涉及的返回栈规则（取自 #1218 的复现步骤）。"""

    def __init__(self, back_stack, swallowed_presses=0):
        self.stack = list(back_stack)  # 栈顶即当前界面
        self.swallowed_presses = swallowed_presses
        self.esc_transitions = []

    @property
    def state(self):
        return self.stack[-1]

    def press_esc(self):
        if self.swallowed_presses > 0:
            # 遗器已满提示浮层会吞掉第一次 esc（实测要按两次才能退回上一级）
            self.swallowed_presses -= 1
            return
        before = self.state
        if before == "main":
            self.stack.append("menu")  # 主界面按 esc 是打开手机菜单
        elif len(self.stack) > 1:
            self.stack.pop()
        self.esc_transitions.append((before, self.state))

    def click(self, path):
        if self.state == "menu" and path.endswith("/bag.png"):
            self.stack.append("bag")
        elif self.state == "bag" and path.endswith("/bag_relicset.png"):
            self.stack.append("bag_relicset")
        else:
            return False
        return True


class _FakeAuto:
    """按当前模拟界面回答识别请求，供 Screen 的图片匹配调用。"""

    def __init__(self, screen_map, game):
        self.screen_map = screen_map
        self.game = game
        self.ocr_result = []

    def take_screenshot(self):
        pass

    def perform_ocr(self):
        self.ocr_result = []

    def press_key(self, key, *args, **kwargs):
        self.game.press_esc()

    def click_element(self, target, find_type=None, threshold=None, *args, **kwargs):
        if find_type == "image" and isinstance(target, str):
            return self.game.click(target)
        return False

    def _screen_of(self, image_path):
        for screen_id, definition in self.screen_map.items():
            paths = definition["image_path"]
            if not isinstance(paths, (list, tuple)):
                paths = [paths]
            if image_path in paths:
                return screen_id
        return None

    def find_element(self, image_path, find_type=None, threshold=None, **kwargs):
        if not isinstance(image_path, str):
            return None
        if self._screen_of(image_path) != self.game.state:
            return None
        return 1.0 if find_type == "image_threshold" else True


def _load_screen_module(auto):
    """加载真实的 Screen 类，只替换掉依赖游戏环境的 module.automation。"""
    stubs = {
        "module.automation": _stub("module.automation", auto=auto),
        "module.config": _stub("module.config", cfg=MagicMock()),
        "module.logger": _stub("module.logger", log=MagicMock()),
    }
    spec = importlib.util.spec_from_file_location(
        "screen_under_test", ROOT / "module" / "screen" / "screen.py"
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


def _build_screen(monkeypatch, back_stack, swallowed_presses=0):
    game = _FakeGame(back_stack, swallowed_presses)
    # wait_for_screen_change 每次超时要等 10 秒，测试里不需要真的等
    monkeypatch.setattr(time, "sleep", lambda *args, **kwargs: None)

    module = _load_screen_module(MagicMock())
    screen = module.Screen.__new__(module.Screen)
    screen.screen_map = {}
    screen.current_screen = None
    screen.current_screen_threshold = 0
    screen.wait_screen_change_time = 0.5
    screen.lock = threading.Lock()
    screen.logger = MagicMock()
    screen._setup_screens_from_config(str(SCREENS_CONFIG))

    module.auto = _FakeAuto(screen.screen_map, game)
    return screen, game


def test_relic_bag_navigation_recovers_jump_entry_back_stack(monkeypatch):
    """#1218：跳转进入副本队伍界面后，仍应从队伍界面走到遗器背包。"""
    screen, game = _build_screen(monkeypatch, JUMP_ENTRY_STACK, swallowed_presses=1)

    screen.change_to("bag_relicset")

    assert game.state == "bag_relicset"


def test_relic_bag_navigation_keeps_menu_entry_untouched(monkeypatch):
    """常态路径（手机菜单进入生存索引）不该多按 esc：超时补救只在超时才生效。"""
    screen, game = _build_screen(monkeypatch, MENU_ENTRY_STACK)

    screen.change_to("bag_relicset")

    assert game.state == "bag_relicset"
    assert game.esc_transitions == [("guide3", "menu")]
