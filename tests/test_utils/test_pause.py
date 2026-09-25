# coding:utf-8
"""utils/pause.py 暂停控制器测试。"""
import threading
import time

import pytest

from utils import pause as pause_mod
from utils.pause import (COMMAND_PAUSE, COMMAND_RESUME, PAUSE_LOG_MESSAGE,
                         RESUME_LOG_MESSAGE, STATE_PAUSED, STATE_PAUSING,
                         STATE_RUNNING, PauseController, read_state,
                         reset_files, write_command)


def _wait_until(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


class _LogStub:
    """记录日志调用顺序的桩。"""

    def __init__(self):
        self.messages = []

    def warning(self, message, *args, **kwargs):
        self.messages.append(message)

    def info(self, message, *args, **kwargs):
        self.messages.append(message)


@pytest.fixture
def control_path(tmp_path):
    return str(tmp_path / "pause.json")


@pytest.fixture
def log_stub(monkeypatch):
    stub = _LogStub()
    monkeypatch.setattr(pause_mod, "log", stub)
    return stub


@pytest.fixture
def controller(control_path, log_stub):
    ctl = PauseController()
    ctl.start(control_path)
    yield ctl
    ctl.stop()


def test_inert_without_control_path(monkeypatch):
    """未提供控制文件路径（独立 CLI / Docker）时功能整体惰性关闭。"""
    monkeypatch.delenv(pause_mod.CONTROL_FILE_ENV, raising=False)
    ctl = PauseController()
    ctl.start()
    assert ctl.enabled is False

    # 即使被请求暂停，卡点也不应阻塞
    ctl.request_pause()
    start = time.monotonic()
    ctl.checkpoint()
    assert time.monotonic() - start < 0.5
    assert ctl.is_paused() is False


def test_start_reads_env_var(monkeypatch, control_path):
    monkeypatch.setenv(pause_mod.CONTROL_FILE_ENV, control_path)
    ctl = PauseController()
    ctl.start()
    try:
        assert ctl.enabled is True
        assert read_state(control_path) == STATE_RUNNING
    finally:
        ctl.stop()


def test_checkpoint_passes_through_when_running(controller):
    start = time.monotonic()
    controller.checkpoint()
    assert time.monotonic() - start < 0.5


def test_checkpoint_blocks_during_pause_and_announces_once(controller, log_stub):
    """暂停中卡点阻塞；暂停风险日志多线程也只播报一次。"""
    controller.request_pause()
    assert read_state(controller._control_path) == STATE_PAUSING

    done = []

    def worker():
        controller.checkpoint()
        done.append(1)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()

    # 已经停住：两个线程都不应完成，并回执 paused
    time.sleep(0.4)
    assert done == []
    assert read_state(controller._control_path) == STATE_PAUSED
    assert log_stub.messages.count(PAUSE_LOG_MESSAGE) == 1

    controller.request_resume()
    for t in threads:
        t.join(timeout=5)
    assert sorted(done) == [1, 1]
    assert RESUME_LOG_MESSAGE in log_stub.messages
    assert read_state(controller._control_path) == STATE_RUNNING


def test_resume_log_precedes_release(controller, log_stub):
    """恢复日志先于卡点放行输出。"""
    controller.request_pause()
    order = []

    stub = log_stub
    original_warning = stub.warning

    def warning_with_order(message, *args, **kwargs):
        order.append(("log", message))
        original_warning(message, *args, **kwargs)

    stub.warning = warning_with_order

    def worker():
        controller.checkpoint()
        order.append(("released", None))

    t = threading.Thread(target=worker)
    t.start()
    _wait_until(lambda: read_state(controller._control_path) == STATE_PAUSED)

    controller.request_resume()
    t.join(timeout=5)
    assert not t.is_alive()
    log_positions = [i for i, item in enumerate(order) if item[0] == "log"]
    release_positions = [i for i, item in enumerate(order) if item[0] == "released"]
    assert log_positions and release_positions
    assert max(log_positions) < min(release_positions)


def test_gui_command_file_roundtrip(controller, control_path):
    """GUI 写指令文件 → watcher 接收 → 卡点阻塞 → 回执 paused。"""
    done = []
    write_command(control_path, COMMAND_PAUSE)

    assert _wait_until(lambda: controller.is_paused())

    def worker():
        controller.checkpoint()
        done.append(1)

    t = threading.Thread(target=worker)
    t.start()
    time.sleep(0.3)
    assert done == []
    assert _wait_until(lambda: read_state(control_path) == STATE_PAUSED)

    write_command(control_path, COMMAND_RESUME)
    t.join(timeout=5)
    assert done == [1]
    assert not controller.is_paused()


def test_reset_files_clears_stale_state(control_path):
    write_command(control_path, COMMAND_PAUSE)
    assert read_state(control_path) is None  # 无回执
    reset_files(control_path)
    assert read_state(control_path) is None


def test_pause_guard_blocks_until_resume(controller, monkeypatch):
    monkeypatch.setattr(pause_mod, "pause_ctl", controller)

    calls = []

    @pause_mod.pause_guard
    def act(value):
        calls.append(value)
        return value

    controller.request_pause()
    result = []

    def worker():
        result.append(act(42))

    t = threading.Thread(target=worker)
    t.start()
    time.sleep(0.3)
    assert calls == []
    controller.request_resume()
    t.join(timeout=5)
    assert calls == [42]
    assert result == [42]
