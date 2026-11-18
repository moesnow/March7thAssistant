"""桌面分身资源调节：进程优先级、空闲最小化/还原与界面接入。"""
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from utils import twin_resource


class _FakeProcess:
    def __init__(self, pid, name, nice_calls):
        self.pid = pid
        self.info = {"pid": pid, "name": name}
        self._nice_calls = nice_calls

    def nice(self, value):
        self._nice_calls.append((self.pid, value))


class TestPriority:
    def test_lower_process_priority_uses_below_normal(self, monkeypatch):
        calls = []

        class FakeProc:
            def __init__(self, pid=None):
                calls.append(("init", pid))

            def nice(self, value):
                calls.append(("nice", value))

        monkeypatch.setattr(twin_resource, "_psutil",
                            lambda: SimpleNamespace(Process=FakeProc, BELOW_NORMAL_PRIORITY_CLASS=0x4000))

        assert twin_resource.lower_process_priority(123) is True
        assert calls == [("init", 123), ("nice", 0x4000)]

    def test_lower_process_priority_reports_failure(self, monkeypatch):
        class Broken:
            def __init__(self, pid=None):
                raise OSError("denied")

        monkeypatch.setattr(twin_resource, "_psutil", lambda: SimpleNamespace(Process=Broken))
        assert twin_resource.lower_process_priority() is False

    def test_game_priority_skips_other_names_and_sessions(self, monkeypatch):
        nice_calls = []
        processes = [
            _FakeProcess(1, "StarRail.exe", nice_calls),
            _FakeProcess(2, "other.exe", nice_calls),
            _FakeProcess(3, "starrail.exe", nice_calls),
            _FakeProcess(4, "StarRail.exe", nice_calls),
        ]
        fake_psutil = SimpleNamespace(
            process_iter=lambda attrs: iter(processes),
            BELOW_NORMAL_PRIORITY_CLASS=0x4000,
        )
        monkeypatch.setattr(twin_resource, "_psutil", lambda: fake_psutil)
        monkeypatch.setattr("utils.windows_session.process_session_id",
                            lambda pid=None: 9 if pid == 4 else 2)

        lowered = twin_resource.lower_game_process_priority("StarRail.exe", session_id=2)

        assert lowered == 2
        assert sorted(pid for pid, _ in nice_calls) == [1, 3]

    def test_game_priority_returns_zero_without_name(self):
        assert twin_resource.lower_game_process_priority("", session_id=2) == 0


class TestWindow:
    def _install_fake_win32(self, monkeypatch, titles):
        import types

        states = {"show": [], "foreground": []}

        def enum_windows(callback, extra):
            for hwnd in titles:
                callback(hwnd, extra)

        fake_gui = types.SimpleNamespace(
            EnumWindows=enum_windows,
            IsWindowVisible=lambda hwnd: True,
            GetWindowText=lambda hwnd: titles[hwnd],
            ShowWindow=lambda hwnd, command: states["show"].append((hwnd, command)),
            SetForegroundWindow=lambda hwnd: states["foreground"].append(hwnd),
        )
        fake_con = types.SimpleNamespace(SW_MINIMIZE=6, SW_RESTORE=9)
        monkeypatch.setitem(sys.modules, "win32gui", fake_gui)
        monkeypatch.setitem(sys.modules, "win32con", fake_con)
        return states

    def test_minimize_matches_title_exactly(self, monkeypatch):
        states = self._install_fake_win32(monkeypatch, {10: "崩坏：星穹铁道", 11: "崩坏：星穹铁道 - 其他"})

        assert twin_resource.minimize_game_window("崩坏：星穹铁道") is True
        assert states["show"] == [(10, 6)]

    def test_restore_restores_and_foregrounds(self, monkeypatch):
        states = self._install_fake_win32(monkeypatch, {10: "崩坏：星穹铁道"})

        assert twin_resource.restore_game_window("崩坏：星穹铁道") is True
        assert states["show"] == [(10, 9)]
        assert states["foreground"] == [10]

    def test_missing_window_returns_false(self, monkeypatch):
        self._install_fake_win32(monkeypatch, {10: "其他窗口"})

        assert twin_resource.minimize_game_window("崩坏：星穹铁道") is False
        assert twin_resource.restore_game_window("崩坏：星穹铁道") is False


def test_main_window_pause_and_resume_twin_game(monkeypatch):
    from app import main_window as module

    calls = []
    monkeypatch.setattr(module, "in_desktop_twin", lambda: True)
    monkeypatch.setattr(module.cfg, "get_value", lambda key, default=None: default if default is not None else True)
    monkeypatch.setattr("utils.twin_resource.minimize_game_window", lambda title: calls.append(("min", title)) or True)
    monkeypatch.setattr("utils.twin_resource.restore_game_window", lambda title: calls.append(("restore", title)) or True)

    stub = SimpleNamespace(_twin_game_paused=False, logInterface=Mock(isTaskRunning=Mock(return_value=False)))
    module.MainWindow.pauseTwinGame(stub)
    assert stub._twin_game_paused is True
    assert calls and calls[0][0] == "min"

    module.MainWindow.resumeTwinGame(stub)
    assert stub._twin_game_paused is False
    assert calls[-1][0] == "restore"


def test_main_window_pause_skipped_while_task_runs(monkeypatch):
    from app import main_window as module

    minimize = Mock(return_value=True)
    monkeypatch.setattr(module, "in_desktop_twin", lambda: True)
    monkeypatch.setattr(module.cfg, "get_value", lambda key, default=None: True)
    monkeypatch.setattr("utils.twin_resource.minimize_game_window", minimize)

    stub = SimpleNamespace(_twin_game_paused=False, logInterface=Mock(isTaskRunning=Mock(return_value=True)), _twin_idle_pause_enabled=lambda: True)
    module.MainWindow.pauseTwinGame(stub)

    minimize.assert_not_called()
    assert stub._twin_game_paused is False


def test_log_interface_prepares_twin_game(monkeypatch):
    from app import log_interface as module

    window = Mock()
    monkeypatch.setattr(module, "in_desktop_twin", lambda: True)
    stub = SimpleNamespace(window=lambda: window)

    module.LogInterface._prepareTwinGameForTask(stub)

    window.prepareTwinGameForTask.assert_called_once()
