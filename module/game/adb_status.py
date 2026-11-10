"""ADB 运行状态通道：任务进程定期把控制器状态写入文件，图形界面读取后展示。

任务进程和图形界面是两个进程，界面拿不到任务进程里的控制器。这里只调用
`AdbGameController.get_runtime_status()`，不参与设备会话的任何决策。

文件内容是一个 JSON 对象，临时文件加 `os.replace` 原子替换：

- `running`：任务进程是否仍在运行。结束时写入最后一份快照，保留最近一次错误。
- `pid`、`create_time`：写入方进程，读取方据此识别被强制结束后留下的旧文件。
- `phase`：`starting`（尚未连上设备）、`running`、`finished`、`failed`、`stopped`。
- 其余字段与 `AdbRuntimeStatus` 一一对应。
"""
from contextlib import contextmanager
from dataclasses import asdict
import json
import os
import tempfile
import threading
import time

from utils.runs import is_process_alive, process_create_time


STATUS_FILE_ENV = "MARCH7TH_ADB_STATUS_FILE"
DEFAULT_STATUS_FILE = os.path.join("logs", "adb_status.json")
STATUS_SCHEMA = 1
POLL_INTERVAL = 1.0

_FIELDS = ("connected", "serial", "service_version", "display_id", "game_display_id",
           "game_running", "sdk_window", "capture_fps", "error_code", "error_message")


def status_file_path() -> str:
    return os.environ.get(STATUS_FILE_ENV) or DEFAULT_STATUS_FILE


def _write(path, data):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=os.path.basename(path) + ".", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False)
        # 读取方只持有文件毫秒级，撞上时稍后重试；仍失败就放弃这一次，下一轮再写。
        for attempt in range(3):
            try:
                os.replace(tmp_path, path)
                return
            except OSError:
                time.sleep(0.03 * (attempt + 1))
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass


class AdbStatusPublisher:
    """后台线程按固定间隔写入状态。任何失败都只影响状态展示，不影响任务。"""

    def __init__(self, controller, path=None, interval=POLL_INTERVAL):
        self._controller = controller
        self._path = path or status_file_path()
        self._interval = interval
        self._stop = threading.Event()
        self._thread = None
        self._pid = os.getpid()
        self._create_time = process_create_time(self._pid)
        self._last = {}
        self._write_lock = threading.Lock()

    def _snapshot(self, phase, running=True, **extra):
        data = {name: None for name in _FIELDS}
        data.update(connected=False, game_running=False, sdk_window=False, capture_fps=0.0)
        data.update(self._last)
        data.update(extra)
        data.update(schema=STATUS_SCHEMA, pid=self._pid, create_time=self._create_time,
                    updated=time.time(), running=running, phase=phase)
        return data

    def _publish(self, data):
        try:
            with self._write_lock:
                _write(self._path, data)
        except Exception:
            pass

    def _poll(self):
        try:
            status = asdict(self._controller.get_runtime_status())
        except Exception:
            return False
        self._last = {name: status.get(name) for name in _FIELDS}
        return True

    def _run(self):
        while not self._stop.wait(self._interval):
            if self._poll():
                phase = "running" if self._last.get("connected") or self._last.get("error_code") else "starting"
                self._publish(self._snapshot(phase))

    def start(self):
        if self._thread is not None:
            return
        # 连接设备期间控制器持有锁，先写一份“正在启动”，界面不必等到连接结束。
        self._publish(self._snapshot("starting"))
        self._thread = threading.Thread(target=self._run, name="adb-status", daemon=True)
        self._thread.start()

    def stop(self, phase="finished", error=None):
        """写入最后一份快照。必须在控制器 close() 之前调用，否则读不到最后的状态。"""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self._poll()
        extra = {"connected": False, "game_running": False, "capture_fps": 0.0}
        if error is not None:
            extra.update(error_code=getattr(error, "code", None) or type(error).__name__,
                         error_message=str(error))
        self._publish(self._snapshot(phase, running=False, **extra))


@contextmanager
def publish_status(controller, path=None):
    """在任务运行期间发布 ADB 状态，退出时记录结束方式和最近一次错误。"""
    publisher = AdbStatusPublisher(controller, path)
    try:
        publisher.start()
    except Exception:
        publisher = None
    try:
        yield publisher
    except SystemExit as exit_request:
        if publisher is not None:
            code = exit_request.code
            publisher.stop("finished" if code in (None, 0) else "failed")
        raise
    except Exception as error:
        if publisher is not None:
            publisher.stop("failed", error)
        raise
    except BaseException:
        # Ctrl+C 和停止指令。
        if publisher is not None:
            publisher.stop("stopped")
        raise
    else:
        if publisher is not None:
            publisher.stop("finished")


def read_status(path=None):
    """读取状态文件。文件不存在或正在被替换时返回 None。

    写入方进程已不存在却仍标记为运行中时，把 `running` 改为 False，`phase` 改为 `aborted`。
    """
    path = path or status_file_path()
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("schema") != STATUS_SCHEMA:
        return None
    if data.get("running"):
        if not is_process_alive(data.get("pid"), data.get("create_time")):
            data.update(running=False, phase="aborted", connected=False, game_running=False, capture_fps=0.0)
    return data
