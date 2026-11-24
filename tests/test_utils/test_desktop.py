# coding:utf-8
"""utils/desktop.py 测试。"""
import os
import threading

import pytest

from utils import desktop


def test_open_path_uses_startfile_on_win32(monkeypatch):
    calls = []
    monkeypatch.setattr(desktop.sys, 'platform', 'win32')
    # os.startfile 仅存在于 Windows：在 Linux/macOS 上补桩测试 win32 分支时需 raising=False
    monkeypatch.setattr(desktop.os, 'startfile', lambda path: calls.append(path), raising=False)
    desktop.open_path("./logs")
    assert calls == [os.path.abspath("./logs")]


def test_open_path_does_not_call_the_shell_on_the_calling_thread(monkeypatch):
    threads = []
    monkeypatch.setattr(desktop.sys, 'platform', 'win32')
    monkeypatch.setattr(desktop.os, 'startfile', lambda path: threads.append(threading.get_ident()), raising=False)
    desktop.open_path("./logs")
    assert len(threads) == 1 and threads[0] != threading.get_ident()


def test_open_path_reports_shell_errors(monkeypatch):
    def missing(path):
        raise FileNotFoundError(path)

    monkeypatch.setattr(desktop.sys, 'platform', 'win32')
    monkeypatch.setattr(desktop.os, 'startfile', missing, raising=False)
    with pytest.raises(FileNotFoundError):
        desktop.open_path("./logs")


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
    assert calls == [desktop.paths.logs_dir()]
