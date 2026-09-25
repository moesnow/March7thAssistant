# coding:utf-8
"""utils/desktop.py 测试。"""
import os

from utils import desktop


def test_open_path_uses_startfile_on_win32(monkeypatch):
    calls = []
    monkeypatch.setattr(desktop.sys, 'platform', 'win32')
    monkeypatch.setattr(desktop.os, 'startfile', lambda path: calls.append(path))
    desktop.open_path("./logs")
    assert calls == [os.path.abspath("./logs")]


def test_open_path_uses_open_on_darwin(monkeypatch):
    commands = []
    monkeypatch.setattr(desktop.sys, 'platform', 'darwin')
    monkeypatch.setattr(desktop.os, 'system', lambda cmd: commands.append(cmd) or 0)
    desktop.open_path("./logs")
    assert len(commands) == 1
    assert commands[0].startswith('open "')
    assert commands[0].endswith('"')


def test_open_path_uses_xdg_open_on_linux(monkeypatch):
    commands = []
    monkeypatch.setattr(desktop.sys, 'platform', 'linux')
    monkeypatch.setattr(desktop.os, 'system', lambda cmd: commands.append(cmd) or 0)
    desktop.open_path("./logs")
    assert len(commands) == 1
    assert commands[0].startswith('xdg-open "')


def test_open_log_folder_targets_logs_dir(monkeypatch):
    calls = []
    monkeypatch.setattr(desktop, 'open_path', lambda path: calls.append(path))
    desktop.open_log_folder()
    assert calls == ["./logs"]
