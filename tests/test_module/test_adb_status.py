"""ADB 运行状态通道：任务进程写文件，图形界面读文件。"""
import os
from types import SimpleNamespace

import pytest

from module.game import adb_status
from module.game.adb import AdbRuntimeStatus
from module.game.adb_transport import AdbError
from utils.pause import RunStopRequested


class Controller:
    def __init__(self):
        self.status = AdbRuntimeStatus(True, "4e6780d5", "0.1.1", 44, 44, True, False, 8.3, None, None)
        self.calls = 0

    def get_runtime_status(self):
        self.calls += 1
        if isinstance(self.status, Exception):
            raise self.status
        return self.status


@pytest.fixture
def path(tmp_path):
    return str(tmp_path / "logs" / "adb_status.json")


def test_start_writes_starting_snapshot_before_first_poll(path):
    controller = Controller()
    publisher = adb_status.AdbStatusPublisher(controller, path, interval=60)
    publisher.start()
    try:
        data = adb_status.read_status(path)
        assert (data["running"], data["phase"], data["connected"]) == (True, "starting", False)
        assert data["pid"] == os.getpid()
        assert controller.calls == 0
    finally:
        publisher.stop()


def test_polling_publishes_controller_status(path):
    controller = Controller()
    publisher = adb_status.AdbStatusPublisher(controller, path, interval=0.01)
    publisher.start()
    try:
        deadline = 200
        while deadline and (adb_status.read_status(path) or {}).get("phase") != "running":
            publisher._stop.wait(0.01)
            deadline -= 1
        data = adb_status.read_status(path)
        assert (data["phase"], data["serial"], data["display_id"], data["capture_fps"]) == (
            "running", "4e6780d5", 44, 8.3)
    finally:
        publisher.stop()


def test_stop_keeps_last_error_and_marks_not_running(path):
    controller = Controller()
    controller.status = AdbRuntimeStatus(False, "4e6780d5", None, 44, 0, False, True, 0.0,
                                         "manual_action_required", "游戏需要手动登录")
    publisher = adb_status.AdbStatusPublisher(controller, path, interval=60)
    publisher.start()
    publisher.stop("failed")
    data = adb_status.read_status(path)
    assert (data["running"], data["phase"], data["error_code"]) == (False, "failed", "manual_action_required")
    assert data["connected"] is False and data["display_id"] == 44


def test_status_failures_never_reach_the_task(path):
    controller = Controller()
    controller.status = RuntimeError("boom")
    with adb_status.publish_status(controller, path):
        pass
    assert adb_status.read_status(path)["phase"] == "finished"


@pytest.mark.parametrize("raised, phase, code", [
    (None, "finished", None),
    (SystemExit(0), "finished", None),
    (SystemExit(1), "failed", None),
    (AdbError("service_busy", "设备端服务已被占用"), "failed", "service_busy"),
    (TimeoutError("超时"), "failed", "TimeoutError"),
    (RunStopRequested(), "stopped", None),
    (KeyboardInterrupt(), "stopped", None),
])
def test_publish_status_records_how_the_run_ended(path, raised, phase, code):
    controller = Controller()
    controller.status = AdbRuntimeStatus(False, None, None, None, None, False, False, 0.0, None, None)
    if raised is None:
        with adb_status.publish_status(controller, path):
            pass
    else:
        with pytest.raises(type(raised)):
            with adb_status.publish_status(controller, path):
                raise raised
    data = adb_status.read_status(path)
    assert (data["running"], data["phase"], data["error_code"]) == (False, phase, code)
    if code == "service_busy":
        assert data["error_message"] == "设备端服务已被占用"


def test_killed_writer_is_reported_as_aborted(path, monkeypatch):
    publisher = adb_status.AdbStatusPublisher(Controller(), path, interval=60)
    publisher._publish(publisher._snapshot("running", connected=True, capture_fps=8.0))
    assert adb_status.read_status(path)["running"] is True
    monkeypatch.setattr(adb_status, "is_process_alive", lambda pid, create_time=None: False)
    data = adb_status.read_status(path)
    assert (data["running"], data["phase"], data["connected"], data["capture_fps"]) == (False, "aborted", False, 0.0)


def test_missing_or_broken_file_reads_as_none(tmp_path):
    missing = tmp_path / "missing.json"
    assert adb_status.read_status(str(missing)) is None
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    assert adb_status.read_status(str(broken)) is None
    broken.write_text('{"schema": 999}', encoding="utf-8")
    assert adb_status.read_status(str(broken)) is None


def test_status_file_path_can_be_overridden(monkeypatch):
    monkeypatch.delenv(adb_status.STATUS_FILE_ENV, raising=False)
    assert adb_status.status_file_path() == adb_status.DEFAULT_STATUS_FILE
    monkeypatch.setenv(adb_status.STATUS_FILE_ENV, "custom.json")
    assert adb_status.status_file_path() == "custom.json"


def test_real_controller_status_is_serializable(path):
    """未连接的真实控制器也能发布状态，不会启动设备端服务。"""
    from module.game.adb import AdbGameController
    controller = AdbGameController(SimpleNamespace(adb_path=None, adb_serial=None))
    with adb_status.publish_status(controller, path):
        pass
    data = adb_status.read_status(path)
    assert (data["connected"], data["serial"], data["phase"]) == (False, None, "finished")
