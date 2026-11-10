"""任务进程通过本机回环提供实时 ADB 状态。运行记录负责发现端点和查询历史结果。"""
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass, replace
import json
import secrets
import socket
import threading
from typing import Literal

from module.game.adb import AdbGameController, AdbRuntimeStatus
from utils.runs import (
    STATUS_ABORTED, STATUS_INTERRUPTED, STATUS_RUNNING, STATUS_STOPPED, STATUS_SUCCESS,
    RunSession, effective_status, is_valid_run_id, list_run_ids, load_run, read_active_run,
)


_LOOPBACK = "127.0.0.1"
_QUERY_TIMEOUT = 0.1
_SAMPLE_INTERVAL = 1.0
_ENDPOINT = "adb_status_endpoint"
_IDLE = AdbRuntimeStatus(False, None, None, None, None, False, False, 0.0, None, None)
_END_PHASES = {
    STATUS_SUCCESS: "finished",
    STATUS_STOPPED: "stopped",
    STATUS_INTERRUPTED: "stopped",
    STATUS_ABORTED: "aborted",
}


@dataclass(frozen=True)
class AdbRunStatus:
    run_id: str
    phase: Literal["starting", "running", "finished", "failed", "stopped", "aborted"]
    runtime: AdbRuntimeStatus

    @property
    def running(self) -> bool:
        return self.phase in ("starting", "running")


def _encode(runtime):
    return json.dumps(asdict(runtime), ensure_ascii=False).encode("utf-8")


class _StatusServer:
    def __init__(self, controller, interval):
        self._controller = controller
        self._interval = interval
        self._stopped = threading.Event()
        self._socket = None
        self._key = secrets.token_hex(16)
        self.last_error = None
        self._packet = _encode(_IDLE)

    def start(self):
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.bind((_LOOPBACK, 0))
            self._socket.settimeout(_QUERY_TIMEOUT)
            port = self._socket.getsockname()[1]
            threading.Thread(target=self._serve, name="adb-status", daemon=True).start()
            threading.Thread(target=self._sample, name="adb-status-sample", daemon=True).start()
        except (OSError, RuntimeError):
            self.close()
            return None
        return {"port": port, "key": self._key}

    def _serve(self):
        key = self._key.encode("ascii")
        while not self._stopped.is_set():
            try:
                query, address = self._socket.recvfrom(128)
                if secrets.compare_digest(query, key):
                    self._socket.sendto(self._packet, address)
            except OSError:
                # 超时或查询方已退出，下次仍可读取。
                continue

    def _sample(self):
        # 设备连接及取帧会占用控制器锁，采样期间端点仍返回上一份快照。
        while not self._stopped.wait(self._interval):
            try:
                runtime = self._controller.get_runtime_status()
                packet = _encode(runtime)
            except Exception:
                continue
            if runtime.error_code:
                self.last_error = runtime
            self._packet = packet

    def close(self):
        self._stopped.set()
        if self._socket is not None:
            with suppress(OSError):
                self._socket.close()


@contextmanager
def publish_status(controller: AdbGameController, session: RunSession, *, interval=_SAMPLE_INTERVAL):
    """发布本次任务的实时状态，结束时将错误交给既有运行记录。"""
    server = _StatusServer(controller, interval)
    failure = None
    try:
        session.update_record(adb_status_endpoint=server.start())
        yield
    except Exception as error:
        failure = error
        raise
    finally:
        try:
            code, message = None, None
            if failure is not None:
                code, message = getattr(failure, "code", None) or type(failure).__name__, str(failure)
            elif server.last_error is not None:
                code, message = server.last_error.error_code, server.last_error.error_message
            if code:
                # CLI 出错后可能会等待用户关闭。将错误登记到运行记录，界面在此期间也能读取。
                session.update_record(error_code=code, error=message)
                session.note(error=message)
        finally:
            server.close()


def _query(endpoint):
    if not isinstance(endpoint, dict):
        return None
    port, key = endpoint.get("port"), endpoint.get("key")
    if type(port) is not int or not 0 < port < 65536 or not isinstance(key, str):
        return None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(_QUERY_TIMEOUT)
            client.connect((_LOOPBACK, port))
            client.send(key.encode("ascii"))
            return AdbRuntimeStatus(**json.loads(client.recv(65507)))
    except (OSError, TypeError, ValueError):
        return None


def _is_adb_run(record):
    return record is not None and _ENDPOINT in record and is_valid_run_id(record.get("run_id"))


def _latest_adb_run():
    active = read_active_run()
    if active and _is_adb_run(record := load_run(active.get("run_id"))):
        return record

    latest = None
    for run_id in reversed(list_run_ids()):
        # 同一秒内生成的运行编号仅随机后缀不同，进程创建时间能区分这些运行。
        if latest and run_id[:15] != latest["run_id"][:15]:
            break
        record = load_run(run_id)
        if _is_adb_run(record) and (
            latest is None or (record.get("pid_create_time") or 0) > (latest.get("pid_create_time") or 0)
        ):
            latest = record
    return latest


def read_adb_run_status(run_id: str | None = None) -> AdbRunStatus | None:
    """读取指定任务，或优先读取当前持有运行锁的 ADB 任务，再回退到最近一次 ADB 运行。"""
    record = _latest_adb_run() if run_id is None else load_run(run_id)
    if not _is_adb_run(record):
        return None
    run_id = record["run_id"]
    outcome = effective_status(record)
    if outcome == STATUS_RUNNING:
        runtime = _query(record[_ENDPOINT])
        if runtime is not None:
            phase = "running" if runtime.connected or runtime.error_code else "starting"
            return AdbRunStatus(run_id, phase, runtime)
        # 查询期间任务可能刚结束，重读运行记录以区分收尾和暂时没有快照。
        record = load_run(run_id) or record
        outcome = effective_status(record)
        if outcome == STATUS_RUNNING:
            if code := record.get("error_code"):
                return AdbRunStatus(run_id, "running", replace(_IDLE, error_code=code, error_message=record.get("error")))
            return AdbRunStatus(run_id, "starting", _IDLE)

    phase = _END_PHASES.get(outcome, "failed")
    code = record.get("error_code")
    message = record.get("error") if code or phase == "failed" else None
    return AdbRunStatus(run_id, phase, replace(_IDLE, error_code=code, error_message=message))
