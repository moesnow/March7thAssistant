"""界面等待的轮询行为：命中立即返回，超时按既有语义处理。"""
import importlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def _make_screen():
    screen_module = importlib.import_module("module.screen.screen")
    page = object.__new__(screen_module.Screen)
    page.screen_map = {"target": {"name": "目标界面", "image_path": "", "actions": []}}
    page.current_screen = None
    page.current_screen_threshold = 0
    page.lock = Mock()
    page.logger = Mock()
    page.wait_screen_change_time = 0
    return page, screen_module


def test_wait_returns_on_first_match_without_polling(monkeypatch):
    page, screen_module = _make_screen()
    page.check_screen = Mock(return_value=True)
    sleeps = []
    fake_time = SimpleNamespace(monotonic=screen_module.time.monotonic, sleep=sleeps.append)
    monkeypatch.setattr(screen_module, "time", fake_time)

    page.wait_for_screen_change("target")

    assert page.check_screen.call_count == 1
    assert sleeps == [0]  # 只有成功后的界面稳定等待


def test_wait_polls_at_short_interval(monkeypatch):
    page, screen_module = _make_screen()
    page.check_screen = Mock(side_effect=[False, False, True])
    sleeps = []
    fake_time = SimpleNamespace(monotonic=screen_module.time.monotonic, sleep=sleeps.append)
    monkeypatch.setattr(screen_module, "time", fake_time)

    page.wait_for_screen_change("target")

    assert page.check_screen.call_count == 3
    assert sleeps == [screen_module._SCREEN_POLL_INTERVAL] * 2 + [0]


def test_wait_times_out_and_reports_failure(monkeypatch):
    page, screen_module = _make_screen()
    page.check_screen = Mock(return_value=False)
    monkeypatch.setattr(screen_module, "_SCREEN_WAIT_TIMEOUT", 0.05)
    monkeypatch.setattr(screen_module, "_SCREEN_POLL_INTERVAL", 0.01)
    page.log_and_raise = Mock(side_effect=RuntimeError("无法切换到目标界面"))

    with pytest.raises(RuntimeError, match="无法切换"):
        page.wait_for_screen_change("target", max_recursion=0)

    assert page.check_screen.call_count >= 2
    page.log_and_raise.assert_called_once()
