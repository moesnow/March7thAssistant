# coding:utf-8
"""运行记录：为每次任务运行分配编号，落盘完整输出与结构化结果，并提供运行锁。

面向脚本、计划任务与 AI Agent——它们看不到提权后新开的控制台窗口，只能通过文件了解运行情况。
所有文件位于程序目录下的 ``logs/runs/``：

- ``<run_id>.log``：本次运行的完整控制台输出（已去除颜色代码）
- ``<run_id>.json``：运行记录（任务、起止时间、状态、退出码、错误、错误截图等）
- ``<run_id>.control``：暂停 / 继续 / 停止指令文件，协议与图形界面共用（见 utils/pause.py）
- ``active.json``：运行锁，记录当前正在操控游戏的运行；持有进程退出即视为失效

本模块只依赖标准库、psutil 与 utils.pause 的文件协议，不导入配置与日志模块，
可以在未提权的命令行入口中安全使用（不会触发配置写入或日志初始化）。
"""
import json
import logging
import os
import re
import secrets
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime
from typing import NamedTuple, Optional

from utils.pause import CONTROL_FILE_ENV, STATE_FILE_SUFFIX, _atomic_write_json, _read_json, reset_files

# ---------- 退出码约定（--help、AGENTS.md 与 Agent Skill 同步说明）----------
EXIT_OK = 0
EXIT_FAILED = 1                 # 任务失败 / 发生异常
EXIT_USAGE = 2                  # 参数错误（argparse 默认）
EXIT_FIRST_RUN_REQUIRED = 3     # 需要先在图形界面完成首次使用确认
EXIT_BUSY = 4                   # 已有任务在运行，本次未执行
EXIT_ELEVATION_FAILED = 5       # 未获得管理员权限（UAC 被取消或无法启动）
EXIT_STOPPED = 6                # 任务被停止指令（--control <运行编号> stop）中止

# ---------- 运行状态 ----------
STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_BLOCKED = "blocked"          # 未执行：需要首次确认 / 已有任务在运行
STATUS_STOPPED = "stopped"          # 收到停止指令后结束
STATUS_INTERRUPTED = "interrupted"  # Ctrl+C
STATUS_ABORTED = "aborted"          # 仅在读取时推断：记录仍为运行中，但进程已不在（窗口被关闭或进程被结束）

REASON_FIRST_RUN_REQUIRED = "first_run_required"
REASON_BUSY = "busy"

# ---------- 运行锁结果（写入运行记录的 lock 字段）----------
LOCK_ACQUIRED = "acquired"
LOCK_FORCED = "forced"              # 已有任务在运行，按 --force 越过
LOCK_BUSY = "busy"                  # 已有任务在运行（持有进程确认存活），本次不执行
LOCK_UNAVAILABLE = "unavailable"    # 锁文件无法读写，无法判断是否已有任务在运行

# 锁文件读写失败时的重试（Windows 上另一进程正在替换 / 删除同一文件等瞬时占用）
_LOCK_ATTEMPTS = 5
_LOCK_RETRY_DELAY = 0.1

RUN_SCHEMA = 1
# 保留最近多少次运行的记录与输出
KEEP_RUNS = 100

_RUN_ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")
# 控制台颜色等 ANSI 控制序列（日志控制台输出带颜色，写入运行日志时去掉）
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def runs_dir() -> str:
    """运行记录目录（相对程序目录；入口脚本启动时已切换到程序所在目录）。"""
    return os.path.abspath(os.path.join("logs", "runs"))


def new_run_id() -> str:
    """生成运行编号：时间在前，字典序即时间序。"""
    return f"{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"


def is_valid_run_id(run_id) -> bool:
    return isinstance(run_id, str) and bool(_RUN_ID_RE.match(run_id))


def run_file(run_id: str, suffix: str) -> str:
    """运行编号对应的文件路径，suffix 如 ".log" / ".json" / ".control"。"""
    return os.path.join(runs_dir(), f"{run_id}{suffix}")


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ---------- 进程身份 ----------

def process_create_time(pid):
    try:
        import psutil
        return psutil.Process(pid).create_time()
    except Exception:
        return None


def is_process_alive(pid, create_time=None) -> bool:
    """进程是否仍在运行；给出 create_time 时同时校验，避免 PID 被复用后误判。"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        import psutil
        if not psutil.pid_exists(pid):
            return False
        if create_time is None:
            return True
        try:
            actual = psutil.Process(pid).create_time()
        except psutil.AccessDenied:
            return True
        return abs(actual - float(create_time)) < 1.0
    except Exception:
        return False


# ---------- 运行记录读取 ----------

def load_run(run_id):
    """读取运行记录，不存在或损坏时返回 None。"""
    if not is_valid_run_id(run_id):
        return None
    data = _read_json(run_file(run_id, ".json"))
    return data if isinstance(data, dict) else None


def effective_status(record) -> str:
    """运行记录的实际状态：记录为运行中但进程已不在时返回 aborted。"""
    status = record.get("status")
    if status == STATUS_RUNNING and not is_process_alive(record.get("pid"), record.get("pid_create_time")):
        return STATUS_ABORTED
    return status


def list_run_ids() -> list:
    """全部运行编号，按时间升序。"""
    try:
        names = os.listdir(runs_dir())
    except OSError:
        return []
    return sorted(name[:-5] for name in names if name.endswith(".json") and is_valid_run_id(name[:-5]))


def recent_runs(limit: int = 5) -> list:
    """最近的运行记录（新的在前），附带实际状态 effective_status。"""
    records = []
    for run_id in reversed(list_run_ids()):
        record = load_run(run_id)
        if record is None:
            continue
        record["effective_status"] = effective_status(record)
        records.append(record)
        if len(records) >= limit:
            break
    return records


def cleanup_old_runs(keep: int = KEEP_RUNS):
    """只保留最近 keep 次运行的文件；仍在运行中的不删除。"""
    run_ids = list_run_ids()
    if len(run_ids) <= keep:
        return
    for run_id in run_ids[:-keep]:
        record = load_run(run_id)
        if record and effective_status(record) == STATUS_RUNNING:
            continue
        for suffix in (".json", ".log", ".control", ".control" + STATE_FILE_SUFFIX):
            try:
                os.remove(run_file(run_id, suffix))
            except OSError:
                pass


# ---------- 运行锁 ----------

def _lock_path() -> str:
    return os.path.join(runs_dir(), "active.json")


class RunLockUnavailable(Exception):
    """运行锁文件无法读写（瞬时占用已重试），因此无法判断是否已有任务在运行。"""


def _create_exclusive(path: str, data: dict) -> bool:
    """仅在文件不存在时创建（内容先写临时文件，再以不覆盖的方式放到目标位置，读者不会读到半截）。"""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".lock_", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        try:
            if sys.platform == "win32":
                os.rename(tmp_path, path)  # Windows 下目标已存在时失败，不会覆盖
            else:
                _link_or_create(tmp_path, path, data)
            return True
        except FileExistsError:
            return False
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def _link_or_create(tmp_path: str, path: str, data: dict):
    """POSIX：rename 会覆盖已有文件，改用硬链接；文件系统不支持硬链接（部分网络盘、Docker 挂载目录）时改用 O_EXCL 独占创建。"""
    try:
        os.link(tmp_path, path)
    except FileExistsError:
        raise
    except OSError:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        with os.fdopen(fd, "wb") as f:
            f.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))


def read_active_run():
    """当前持有运行锁且进程仍在的运行（锁信息字典），没有则返回 None。"""
    holder = _read_json(_lock_path())
    if isinstance(holder, dict) and is_process_alive(holder.get("pid"), holder.get("pid_create_time")):
        return holder
    return None


def acquire_run_lock(info: dict, force: bool = False):
    """尝试取得运行锁。

    只有持有进程确认仍在运行才算「被占用」；读写锁文件出错（含陈旧锁删不掉）不会被当成被占用。

    :param info: 写入锁文件的信息，至少包含 run_id / pid / pid_create_time。
    :param force: 已有运行持有锁时仍然取得（覆盖锁文件）。
    :return: (是否取得, 持有者信息)：取得时为 None 或被 --force 越过的运行；未取得时为仍在运行的持有者。
    :raises RunLockUnavailable: 锁文件持续无法读写（瞬时占用会先重试）。
    """
    path = _lock_path()
    last_error = None
    for _ in range(_LOCK_ATTEMPTS):
        try:
            if _create_exclusive(path, info):
                return True, None
            holder = _read_json(path)
            alive = isinstance(holder, dict) and is_process_alive(holder.get("pid"), holder.get("pid_create_time"))
            if alive and holder.get("run_id") == info.get("run_id"):
                return True, None
            if alive and not force:
                return False, holder
            if alive and force:
                _atomic_write_json(path, info)
                return True, holder
            # 陈旧锁（持有进程已退出）：确认仍是同一份陈旧内容后再移除，避免误删别人刚取得的锁
            if _read_json(path) == holder:
                os.remove(path)
        except FileNotFoundError:
            # 锁恰好被释放：立即重试
            continue
        except OSError as e:
            last_error = e
            time.sleep(_LOCK_RETRY_DELAY)
    holder = _read_json(path)
    if isinstance(holder, dict) and is_process_alive(holder.get("pid"), holder.get("pid_create_time")):
        return False, holder
    raise RunLockUnavailable(f"{path}：{last_error or '多次尝试仍未能写入'}")


def release_run_lock(run_id: str):
    """释放运行锁（只释放自己持有的）。"""
    path = _lock_path()
    holder = _read_json(path)
    if isinstance(holder, dict) and holder.get("run_id") == run_id:
        try:
            os.remove(path)
        except OSError:
            pass


# ---------- 输出捕获 ----------

class _TeeStream:
    """把写入原样转发给原输出流，同时（去掉颜色代码后）追加到运行日志。"""

    def __init__(self, stream, sink):
        self._stream = stream
        self._sink = sink

    def write(self, text):
        written = len(text)
        if self._stream is not None:
            try:
                written = self._stream.write(text)
            except UnicodeEncodeError:
                # 控制台编码放不下（英文 Windows 的 cp1252、任意非 UTF-8 代码页）：
                # 这一行只能在控制台侧丢掉，但绝不能连累下面的日志——捕获输出本就是来留底的
                written = len(text)
        try:
            self._sink.write(_ANSI_RE.sub("", text))
            if "\n" in text:
                self._sink.flush()
        except Exception:
            pass
        return written

    def flush(self):
        if self._stream is not None:
            self._stream.flush()
        try:
            self._sink.flush()
        except Exception:
            pass

    def isatty(self):
        return bool(self._stream is not None and self._stream.isatty())

    def __getattr__(self, name):
        return getattr(self._stream, name)


def capture_output(log_path: str):
    """把 sys.stdout / sys.stderr 同时写入 log_path。

    必须在导入日志模块之前调用：日志的控制台处理器在创建时就绑定了当时的 sys.stderr。
    """
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    # newline=""：按原样写入换行符，跟随输出时再由调用方终端按平台换行
    sink = open(log_path, "a", encoding="utf-8", errors="replace", newline="")
    sys.stdout = _TeeStream(sys.stdout, sink)
    sys.stderr = _TeeStream(sys.stderr, sink)
    return sink


# ---------- 运行会话 ----------

def _status_for_exit_code(exit_code: int):
    if exit_code == EXIT_OK:
        return STATUS_SUCCESS, None
    if exit_code == EXIT_FIRST_RUN_REQUIRED:
        return STATUS_BLOCKED, REASON_FIRST_RUN_REQUIRED
    if exit_code == EXIT_BUSY:
        return STATUS_BLOCKED, REASON_BUSY
    if exit_code == EXIT_STOPPED:
        return STATUS_STOPPED, None
    return STATUS_FAILED, None


def exit_code_of(exc: SystemExit) -> int:
    """SystemExit 对应的进程退出码（与解释器的处理一致）。"""
    code = exc.code
    if code is None:
        return EXIT_OK
    if isinstance(code, int):
        return code
    return EXIT_FAILED


_current_session = None


class LockResult(NamedTuple):
    """RunSession.acquire_lock 的结果。"""
    status: str                     # LOCK_ACQUIRED / LOCK_FORCED / LOCK_BUSY / LOCK_UNAVAILABLE
    holder: Optional[dict] = None   # busy：仍在运行的持有者；forced：被越过的运行
    error: Optional[str] = None     # unavailable：锁文件无法读写的原因


class RunSession:
    """一次任务运行：负责运行记录的创建与收尾、运行锁的取得与释放。"""

    def __init__(self, record: dict):
        self.record = record
        self.run_id = record["run_id"]
        self._pending = {}
        self._finished = False
        self.lock_held = False
        self.print_json = False
        # 最后一条错误日志：任务失败但调用方没有显式登记错误时，写入运行记录的 error
        self.last_error = None

    @classmethod
    def begin(cls, *, run_id=None, task=None, workflow=None, workflow_step_path=None,
              argv=None, invoker="cli", version=None, capture=True):
        """开始一次运行：分配编号、捕获输出、准备控制文件并写入初始记录。"""
        if not is_valid_run_id(run_id):
            run_id = new_run_id()
        # 运行记录只是附加信息：目录不可写等问题不能影响任务本身运行
        try:
            os.makedirs(runs_dir(), exist_ok=True)
            cleanup_old_runs()
        except Exception:
            pass
        log_path = run_file(run_id, ".log")
        if capture:
            try:
                capture_output(log_path)
            except OSError:
                pass
        # 图形界面会注入自己的控制文件；独立运行时为本次运行分配一个，使命令行也能暂停 / 继续 / 停止
        control_path = os.environ.get(CONTROL_FILE_ENV)
        if not control_path:
            control_path = run_file(run_id, ".control")
            reset_files(control_path)
            os.environ[CONTROL_FILE_ENV] = control_path
        pid = os.getpid()
        record = {
            "schema": RUN_SCHEMA,
            "run_id": run_id,
            "status": STATUS_RUNNING,
            "task": task,
            "workflow": workflow,
            "workflow_step_path": workflow_step_path,
            "args": list(argv or []),
            "invoker": invoker,
            "version": version,
            "pid": pid,
            "pid_create_time": process_create_time(pid),
            "started_at": _now_iso(),
            "ended_at": None,
            "exit_code": None,
            "reason": None,
            "error": None,
            "screenshot": None,
            "lock": None,
            "lock_error": None,
            "log_file": log_path,
            "control_file": os.path.abspath(control_path),
        }
        session = cls(record)
        session._save()
        global _current_session
        _current_session = session
        return session

    def _save(self):
        try:
            _atomic_write_json(run_file(self.run_id, ".json"), self.record)
        except Exception:
            pass

    def note(self, **fields):
        """登记收尾时要写入的字段（status / error / reason / screenshot），以 finish 时为准。"""
        self._pending.update({key: value for key, value in fields.items() if value is not None})

    def error_log_handler(self) -> logging.Handler:
        """日志处理器：记下最后一条错误日志（挂到项目日志器上）。"""
        session = self

        class _LastErrorHandler(logging.Handler):
            def emit(self, record):
                try:
                    session.last_error = _ANSI_RE.sub("", record.getMessage())
                except Exception:
                    pass

        return _LastErrorHandler(level=logging.ERROR)

    def lock_info(self) -> dict:
        return {
            "run_id": self.run_id,
            "pid": self.record["pid"],
            "pid_create_time": self.record["pid_create_time"],
            "task": self.record["task"],
            "workflow": self.record["workflow"],
            "invoker": self.record["invoker"],
            "started_at": self.record["started_at"],
        }

    def acquire_lock(self, force: bool = False) -> "LockResult":
        """取得运行锁，结果同时写入运行记录的 lock / lock_error。

        锁被占用与锁不可用分开处理：前者由调用方拒绝运行；后者无法判断是否已有任务在运行，
        由调用方决定如何处理（main.py 照常运行并给出警告，与引入运行锁之前的行为一致）。
        """
        try:
            acquired, holder = acquire_run_lock(self.lock_info(), force=force)
        except (RunLockUnavailable, OSError) as e:
            result = LockResult(LOCK_UNAVAILABLE, error=str(e))
        else:
            if acquired:
                self.lock_held = True
                result = LockResult(LOCK_FORCED if holder else LOCK_ACQUIRED, holder)
            else:
                result = LockResult(LOCK_BUSY, holder)
        self.record["lock"] = result.status
        self.record["lock_error"] = result.error
        self._save()
        return result

    def release_lock(self):
        try:
            release_run_lock(self.run_id)
        except OSError:
            pass
        self.lock_held = False

    def finish(self, exit_code: int):
        """写入最终结果并释放运行锁（多次调用只生效一次）。"""
        if self._finished:
            return
        self._finished = True
        status, reason = _status_for_exit_code(exit_code)
        status = self._pending.get("status", status)
        error = self._pending.get("error")
        if error is None and status != STATUS_SUCCESS:
            error = self.last_error
        self.record.update({
            "status": status,
            "reason": self._pending.get("reason", reason),
            "error": error,
            "screenshot": self._pending.get("screenshot"),
            "exit_code": exit_code,
            "ended_at": _now_iso(),
        })
        self._save()
        self.release_lock()
        if self.print_json:
            try:
                print(json.dumps(self.record, ensure_ascii=True), flush=True)
            except Exception:
                pass


@contextmanager
def idle_without_run_lock(on_wait=None, on_unavailable=None, poll_seconds: float = 30):
    """长时间空闲等待（如循环模式等待下次运行）期间让出运行锁，结束后重新取得。

    重新取得时若锁被其他运行占用，则等待其结束（首次等待时调用 on_wait(持有者信息)）；
    锁不可用时与首次取得时一样照常继续（调用 on_unavailable(原因)）。
    当前进程没有运行会话或未持有锁时不做任何事。
    """
    session = _current_session
    if session is None or not session.lock_held:
        yield
        return
    session.release_lock()
    try:
        yield
    finally:
        notified = False
        while True:
            result = session.acquire_lock()
            if result.status == LOCK_UNAVAILABLE and on_unavailable is not None:
                try:
                    on_unavailable(result.error)
                except Exception:
                    pass
            if result.status != LOCK_BUSY:
                break
            if not notified and on_wait is not None:
                notified = True
                try:
                    on_wait(result.holder)
                except Exception:
                    pass
            time.sleep(poll_seconds)


def describe_run(info) -> str:
    """一行中文描述某次运行（用于日志与命令行提示）。"""
    if not isinstance(info, dict):
        return "未知运行"
    target = f"流程「{info['workflow']}」" if info.get("workflow") else f"任务 {info.get('task') or 'main'}"
    return f"{target}（运行编号 {info.get('run_id')}，进程 {info.get('pid')}，开始于 {info.get('started_at')}）"
