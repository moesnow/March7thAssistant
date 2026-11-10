"""ADB 运行状态接口与跨进程读取。"""
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
from threading import Event
import time

import pytest

from module.game import adb_status
from module.game.adb import AdbRuntimeStatus
from module.game.adb_transport import AdbError
from utils import runs
from utils.pause import CONTROL_FILE_ENV, RunStopRequested


class Controller:
    status = AdbRuntimeStatus(True, "usb-serial", "0.1.1", 44, 0, True, True, 8.3, None, None)

    def get_runtime_status(self):
        return self.status


@pytest.fixture(autouse=True)
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(CONTROL_FILE_ENV, raising=False)
    monkeypatch.setattr(runs, "_current_session", None)
    yield tmp_path
    monkeypatch.delenv(CONTROL_FILE_ENV, raising=False)


def wait_for_running(timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = adb_status.read_adb_run_status()
        if status is not None and status.phase == "running":
            return status
        time.sleep(0.01)
    pytest.fail("没有收到实时 ADB 运行状态")


def test_status_can_be_read_while_controller_is_blocked():
    polling = Event()
    ready = Event()

    class BlockedController(Controller):
        def get_runtime_status(self):
            polling.set()
            ready.wait(3)
            return self.status

    session = runs.RunSession.begin(capture=False)
    controller = BlockedController()
    with adb_status.publish_status(controller, session, interval=0.01):
        try:
            assert polling.wait(1)
            status = adb_status.read_adb_run_status(session.run_id)
            assert (status.running, status.phase, status.runtime.connected) == (True, "starting", False)
        finally:
            ready.set()
        assert wait_for_running().runtime == controller.status
    session.finish(runs.EXIT_OK)
    status = adb_status.read_adb_run_status(session.run_id)
    assert (status.running, status.phase, status.runtime.connected) == (False, "finished", False)
    assert not Path("logs/adb_status.json").exists()


def test_status_preserves_sampled_device_error_in_run_result():
    session = runs.RunSession.begin(capture=False)
    controller = Controller()
    controller.status = replace(controller.status, connected=False, error_code="disconnected",
                                error_message="设备已断开")
    with adb_status.publish_status(controller, session, interval=0.01):
        assert wait_for_running().runtime == controller.status
    session.finish(runs.EXIT_FAILED)
    status = adb_status.read_adb_run_status()
    assert (status.phase, status.runtime.error_code, status.runtime.error_message) == (
        "failed", "disconnected", "设备已断开",
    )


@pytest.mark.parametrize("raised, exit_code, phase, code", [
    (SystemExit(0), runs.EXIT_OK, "finished", None),
    (SystemExit(1), runs.EXIT_FAILED, "failed", None),
    (AdbError("service_busy", "设备端服务已被占用"), runs.EXIT_FAILED, "failed", "service_busy"),
    (TimeoutError("超时"), runs.EXIT_FAILED, "failed", "TimeoutError"),
    (RunStopRequested(), runs.EXIT_STOPPED, "stopped", None),
    (KeyboardInterrupt(), runs.EXIT_FAILED, "stopped", None),
    (None, runs.EXIT_FAILED, "failed", None),
])
def test_status_uses_existing_run_result(raised, exit_code, phase, code):
    session = runs.RunSession.begin(capture=False)
    with pytest.raises(type(raised)) if raised is not None else nullcontext():
        with adb_status.publish_status(Controller(), session):
            if raised is not None:
                raise raised
            session.last_error = "任务执行失败"
    if isinstance(raised, KeyboardInterrupt):
        session.note(status=runs.STATUS_INTERRUPTED, error="手动强制停止")
    if code:
        pending = adb_status.read_adb_run_status()
        assert (pending.running, pending.runtime.error_code, pending.runtime.error_message) == (True, code, str(raised))
    session.finish(exit_code)
    status = adb_status.read_adb_run_status()
    assert (status.running, status.phase, status.runtime.error_code) == (False, phase, code)
    if code:
        assert status.runtime.error_message == str(raised)
    if raised is None:
        assert status.runtime.error_message == "任务执行失败"


def test_sampling_failure_does_not_affect_task():
    polled = Event()

    class BrokenController:
        def get_runtime_status(self):
            polled.set()
            raise RuntimeError("状态采样失败")

    session = runs.RunSession.begin(capture=False)
    with adb_status.publish_status(BrokenController(), session, interval=0.01):
        assert polled.wait(1)
        assert adb_status.read_adb_run_status().phase == "starting"
    session.finish(runs.EXIT_OK)
    assert adb_status.read_adb_run_status().phase == "finished"


def test_socket_unavailable_does_not_affect_task(monkeypatch):
    def fail_socket(*args):
        raise OSError("socket unavailable")

    monkeypatch.setattr(adb_status.socket, "socket", fail_socket)
    session = runs.RunSession.begin(capture=False)
    with adb_status.publish_status(Controller(), session):
        assert adb_status.read_adb_run_status().phase == "starting"
    session.finish(runs.EXIT_OK)
    assert adb_status.read_adb_run_status().phase == "finished"


def test_current_locked_run_takes_precedence_over_newer_run():
    active = runs.RunSession.begin(run_id="20261110-210000-0001", capture=False)
    other = runs.RunSession.begin(run_id="20261110-210001-0001", capture=False)
    with adb_status.publish_status(Controller(), active):
        assert active.acquire_lock().status == runs.LOCK_ACQUIRED
        with adb_status.publish_status(Controller(), other):
            assert other.acquire_lock().status == runs.LOCK_BUSY
            assert adb_status.read_adb_run_status().run_id == active.run_id
            assert adb_status.read_adb_run_status(other.run_id).run_id == other.run_id
        other.finish(runs.EXIT_BUSY)
        assert adb_status.read_adb_run_status().run_id == active.run_id
    active.finish(runs.EXIT_OK)


def test_read_live_status_from_another_process_then_detect_abort(workdir):
    script = """
import os
import sys
from types import SimpleNamespace
from module.game.adb_status import AdbRuntimeStatus, publish_status
from utils.runs import RunSession

os.chdir(sys.argv[1])
session = RunSession.begin(capture=False)
runtime = AdbRuntimeStatus(True, "child", "0.1.1", 44, 0, True, True, 8.3, None, None)
controller = SimpleNamespace(get_runtime_status=lambda: runtime)
with publish_status(controller, session, interval=0.01):
    sys.stdin.read()
"""
    project = Path(__file__).resolve().parents[2]
    with subprocess.Popen([sys.executable, "-c", script, str(workdir)], cwd=project, stdin=subprocess.PIPE) as worker:
        try:
            status = wait_for_running(timeout=15)
            assert (status.runtime.serial, status.runtime.game_display_id, status.runtime.capture_fps) == ("child", 0, 8.3)
        finally:
            worker.kill()
            worker.wait(timeout=5)
    status = adb_status.read_adb_run_status()
    assert (status.running, status.phase, status.runtime.connected, status.runtime.capture_fps) == (
        False, "aborted", False, 0.0,
    )


def test_legacy_snapshot_and_unrelated_run_are_ignored():
    session = runs.RunSession.begin(capture=False)
    Path("logs/adb_status.json").write_text('{"schema": 1, "phase": "running"}', encoding="utf-8")
    assert adb_status.read_adb_run_status() is None
    assert adb_status.read_adb_run_status(session.run_id) is None
