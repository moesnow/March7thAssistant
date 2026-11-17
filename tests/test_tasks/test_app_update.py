# coding:utf-8
"""命令行/定时任务更新入口：托盘最小化状态应传递给更新器的回归测试。

GUI 处于托盘最小化状态时通过环境变量 MARCH7TH_START_MINIMIZED_TO_TRAY
告知任务子进程，更新完成后应保持最小化到托盘。
"""
from unittest.mock import Mock

import pytest

from module.update.version_check import VersionCheckError
from tasks.version import app_update


class TestStartMinimizedToTray:
    def test_env_one(self, monkeypatch):
        monkeypatch.setenv("MARCH7TH_START_MINIMIZED_TO_TRAY", "1")
        assert app_update.start_minimized_to_tray() is True

    def test_env_true(self, monkeypatch):
        monkeypatch.setenv("MARCH7TH_START_MINIMIZED_TO_TRAY", "true")
        assert app_update.start_minimized_to_tray() is True

    def test_env_true_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("MARCH7TH_START_MINIMIZED_TO_TRAY", "TRUE")
        assert app_update.start_minimized_to_tray() is True

    def test_env_zero(self, monkeypatch):
        monkeypatch.setenv("MARCH7TH_START_MINIMIZED_TO_TRAY", "0")
        assert app_update.start_minimized_to_tray() is False

    def test_env_missing(self, monkeypatch):
        monkeypatch.delenv("MARCH7TH_START_MINIMIZED_TO_TRAY", raising=False)
        assert app_update.start_minimized_to_tray() is False


def test_detection_failure_returns_nonzero_exit_code(monkeypatch):
    monkeypatch.setattr(app_update, "check_for_update", Mock(side_effect=VersionCheckError("HTTP 403")))
    start_updater = Mock()
    monkeypatch.setattr(app_update.subprocess, "Popen", start_updater)

    with pytest.raises(SystemExit) as error:
        app_update.start()

    assert error.value.code == 1
    start_updater.assert_not_called()
