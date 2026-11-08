import pytest
from unittest.mock import MagicMock, patch
from collections import deque


class ScreenForTest:
    """Screen 的轻量测试替身，只测试图算法逻辑，不依赖文件/图片/游戏环境。"""

    def __init__(self):
        self.screen_map = {}
        self.current_screen = None
        self.current_screen_threshold = 0
        self.logger = MagicMock()

    def _add_screen(self, id, name, image_path, actions):
        self.screen_map[id] = {'name': name, 'image_path': image_path, 'actions': actions}

    def find_shortest_path(self, start, end):
        if start == end:
            return [end]
        visited = set()
        queue = deque([(start, [])])
        while queue:
            current_screen, path = queue.popleft()
            visited.add(current_screen)
            for action in self.screen_map[current_screen]['actions']:
                next_screen = action["target_screen"]
                if next_screen not in visited:
                    new_path = path + [current_screen]
                    if next_screen == end:
                        return new_path + [end]
                    queue.append((next_screen, new_path))
        return None

    def can_change_from(self, start_screen, target_screen):
        if start_screen not in self.screen_map or target_screen not in self.screen_map:
            return False
        return self.find_shortest_path(start_screen, target_screen) is not None

    def get_switchable_screens(self, start_screen="main", include_start=True):
        if start_screen not in self.screen_map:
            return []
        visited = {start_screen}
        queue = deque([start_screen])
        result = []
        if include_start:
            result.append((start_screen, self.get_name(start_screen)))
        while queue:
            current_screen = queue.popleft()
            for action in self.screen_map[current_screen]['actions']:
                next_screen = action.get("target_screen")
                if next_screen in visited or next_screen not in self.screen_map:
                    continue
                visited.add(next_screen)
                result.append((next_screen, self.get_name(next_screen)))
                queue.append(next_screen)
        return result

    def get_name(self, id):
        return self.screen_map[id]["name"]

    def get_operations(self, current_screen, next_screen):
        return [action["actions_list"] for action in self.screen_map[current_screen]['actions'] if action["target_screen"] == next_screen][0]

    def get_timeout_operations(self, current_screen, next_screen):
        for action in self.screen_map[current_screen]['actions']:
            if action["target_screen"] == next_screen:
                return action.get("actions_list_on_timeout", [])
        return []


def _build_linear_screen():
    """main -> settings -> about，线性链。"""
    s = ScreenForTest()
    s._add_screen("main", "主界面", "main.png", [
        {"target_screen": "settings", "actions_list": "auto.click('settings')"}
    ])
    s._add_screen("settings", "设置", "settings.png", [
        {"target_screen": "main", "actions_list": "auto.click('back')"},
        {"target_screen": "about", "actions_list": "auto.click('about')"}
    ])
    s._add_screen("about", "关于", "about.png", [
        {"target_screen": "settings", "actions_list": "auto.click('back')"}
    ])
    return s


def _build_branch_screen():
    """main -> {a, b}，分支结构。"""
    s = ScreenForTest()
    s._add_screen("main", "主界面", "main.png", [
        {"target_screen": "a", "actions_list": "auto.click('a')"},
        {"target_screen": "b", "actions_list": "auto.click('b')"}
    ])
    s._add_screen("a", "A界面", "a.png", [
        {"target_screen": "main", "actions_list": "auto.click('back')"}
    ])
    s._add_screen("b", "B界面", "b.png", [
        {"target_screen": "main", "actions_list": "auto.click('back')"}
    ])
    return s


def _build_cycle_screen():
    """main -> a -> b -> main，环形结构。"""
    s = ScreenForTest()
    s._add_screen("main", "主界面", "main.png", [
        {"target_screen": "a", "actions_list": "auto.click('a')"}
    ])
    s._add_screen("a", "A界面", "a.png", [
        {"target_screen": "b", "actions_list": "auto.click('b')"}
    ])
    s._add_screen("b", "B界面", "b.png", [
        {"target_screen": "main", "actions_list": "auto.click('back')"}
    ])
    return s


def _build_disconnected_screen():
    """两个互不连通的子图。"""
    s = ScreenForTest()
    s._add_screen("main", "主界面", "main.png", [
        {"target_screen": "a", "actions_list": "auto.click('a')"}
    ])
    s._add_screen("a", "A界面", "a.png", [
        {"target_screen": "main", "actions_list": "auto.click('back')"}
    ])
    s._add_screen("isolated", "孤立界面", "isolated.png", [])
    return s


class TestFindShortestPath:
    def test_same_start_and_end(self):
        s = _build_linear_screen()
        assert s.find_shortest_path("main", "main") == ["main"]

    def test_direct_neighbor(self):
        s = _build_linear_screen()
        assert s.find_shortest_path("main", "settings") == ["main", "settings"]

    def test_two_hops(self):
        s = _build_linear_screen()
        assert s.find_shortest_path("main", "about") == ["main", "settings", "about"]

    def test_reverse_path(self):
        s = _build_linear_screen()
        assert s.find_shortest_path("about", "main") == ["about", "settings", "main"]

    def test_no_path_returns_none(self):
        s = _build_disconnected_screen()
        assert s.find_shortest_path("main", "isolated") is None

    def test_branch_takes_shortest(self):
        s = _build_branch_screen()
        path = s.find_shortest_path("main", "a")
        assert path == ["main", "a"]

    def test_cycle_does_not_loop(self):
        s = _build_cycle_screen()
        path = s.find_shortest_path("main", "main")
        assert path == ["main"]

    def test_cycle_path(self):
        s = _build_cycle_screen()
        path = s.find_shortest_path("main", "b")
        assert path == ["main", "a", "b"]


class TestCanChangeFrom:
    def test_direct_reachable(self):
        s = _build_linear_screen()
        assert s.can_change_from("main", "settings") is True

    def test_indirect_reachable(self):
        s = _build_linear_screen()
        assert s.can_change_from("main", "about") is True

    def test_unreachable(self):
        s = _build_disconnected_screen()
        assert s.can_change_from("main", "isolated") is False

    def test_nonexistent_start(self):
        s = _build_linear_screen()
        assert s.can_change_from("nonexistent", "main") is False

    def test_nonexistent_target(self):
        s = _build_linear_screen()
        assert s.can_change_from("main", "nonexistent") is False

    def test_same_screen(self):
        s = _build_linear_screen()
        assert s.can_change_from("main", "main") is True


class TestGetSwitchableScreens:
    def test_include_start(self):
        s = _build_linear_screen()
        result = s.get_switchable_screens("main", include_start=True)
        ids = [r[0] for r in result]
        assert ids[0] == "main"
        assert "settings" in ids
        assert "about" in ids

    def test_exclude_start(self):
        s = _build_linear_screen()
        result = s.get_switchable_screens("main", include_start=False)
        ids = [r[0] for r in result]
        assert "main" not in ids
        assert "settings" in ids

    def test_nonexistent_screen(self):
        s = _build_linear_screen()
        assert s.get_switchable_screens("nonexistent") == []

    def test_isolated_screen(self):
        s = _build_disconnected_screen()
        result = s.get_switchable_screens("isolated", include_start=True)
        assert len(result) == 1
        assert result[0] == ("isolated", "孤立界面")

    def test_returns_names(self):
        s = _build_linear_screen()
        result = s.get_switchable_screens("main")
        name_map = dict(result)
        assert name_map["main"] == "主界面"
        assert name_map["settings"] == "设置"


class TestGetName:
    def test_existing(self):
        s = _build_linear_screen()
        assert s.get_name("main") == "主界面"
        assert s.get_name("settings") == "设置"

    def test_nonexistent_raises(self):
        s = _build_linear_screen()
        with pytest.raises(KeyError):
            s.get_name("nonexistent")


class TestGetOperations:
    def test_returns_actions_list(self):
        s = _build_linear_screen()
        ops = s.get_operations("main", "settings")
        assert ops == "auto.click('settings')"

    def test_reverse_direction(self):
        s = _build_linear_screen()
        ops = s.get_operations("settings", "main")
        assert ops == "auto.click('back')"


class TestGetTimeoutOperations:
    def test_no_timeout_defined(self):
        s = _build_linear_screen()
        assert s.get_timeout_operations("main", "settings") == []

    def test_with_timeout(self):
        s = ScreenForTest()
        s._add_screen("main", "主界面", "main.png", [
            {"target_screen": "a", "actions_list": "click_a", "actions_list_on_timeout": "retry_a"}
        ])
        s._add_screen("a", "A", "a.png", [])
        assert s.get_timeout_operations("main", "a") == "retry_a"

    def test_nonexistent_target(self):
        s = _build_linear_screen()
        assert s.get_timeout_operations("main", "nonexistent") == []
