import os
import sys
from unittest.mock import patch

import pytest

from utils import crash_log


@pytest.fixture
def hooks(tmp_path, monkeypatch):
    """隔离全局状态：pytest 自己也在使用 faulthandler 与 sys.excepthook。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(crash_log, "_crash_file", None)
    with patch.object(crash_log.faulthandler, "enable") as enable, \
            patch.object(crash_log.atexit, "register") as register:
        yield enable, register
    if crash_log._crash_file is not None:
        crash_log._crash_file.close()


def read_log():
    with open(crash_log.CRASH_LOG_PATH, encoding="utf-8") as file:
        return file.read()


def test_record_before_enable_is_noop(hooks):
    crash_log.record_crash("anything")

    assert not os.path.exists(crash_log.CRASH_LOG_PATH)


def test_enable_records_start_and_registers_hooks(hooks):
    enable, register = hooks

    crash_log.enable_crash_log()

    assert f"图形界面启动 pid={os.getpid()}" in read_log()
    enable.assert_called_once_with(file=crash_log._crash_file, all_threads=True)
    register.assert_called_once_with(crash_log.record_crash, f"图形界面退出 pid={os.getpid()}")
    assert sys.excepthook is crash_log._excepthook


def test_uncaught_exception_is_recorded_and_still_printed(hooks):
    crash_log.enable_crash_log()

    with patch.object(sys, "__excepthook__") as original:
        try:
            raise ValueError("boom")
        except ValueError:
            sys.excepthook(*sys.exc_info())

    assert "ValueError: boom" in read_log()
    original.assert_called_once()


def test_oversized_log_is_rotated(hooks):
    os.makedirs("logs")
    with open(crash_log.CRASH_LOG_PATH, "w", encoding="utf-8") as file:
        file.write("x" * (crash_log.CRASH_LOG_MAX_BYTES + 1))

    crash_log.enable_crash_log()

    assert os.path.getsize(os.path.join("logs", "crash.1.log")) > crash_log.CRASH_LOG_MAX_BYTES
    assert os.path.getsize(crash_log.CRASH_LOG_PATH) < 200


def test_unwritable_logs_does_not_break_startup(hooks):
    enable, _ = hooks
    with open("logs", "w", encoding="utf-8") as file:
        file.write("")  # 同名文件占位，logs 目录无法创建
    original_hook = sys.excepthook

    crash_log.enable_crash_log()
    crash_log.record_crash("anything")

    enable.assert_not_called()
    assert sys.excepthook is original_hook
