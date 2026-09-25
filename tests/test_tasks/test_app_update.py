# coding:utf-8
"""命令行/定时任务更新入口：托盘最小化状态应传递给更新器的回归测试。

GUI 处于托盘最小化状态时通过环境变量 MARCH7TH_START_MINIMIZED_TO_TRAY
告知任务子进程，更新完成后应保持最小化到托盘。
"""
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
