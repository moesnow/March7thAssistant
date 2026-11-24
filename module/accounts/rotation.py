"""多账号父进程。每个账号独立记录与截止时间，停止和跳过均先请求子进程收尾。"""

import os
import subprocess
import threading
import time

from utils import runs
from utils.cli_entry import worker_command
from utils.pause import (
    COMMAND_PAUSE,
    COMMAND_STOP,
    CONTROL_FILE_ENV,
    _atomic_write_json,
    _read_json,
    write_command,
)
from .runtime import AccountError, ROTATABLE, require_supported
from .store import AccountStore

PARENT_ENV = "M7A_ROTATION_PARENT"
JOB_ENV = "M7A_ROTATION_JOB"
CANCEL_ENV = "M7A_ROTATION_CANCEL"
GRACE = 8.0


class ChildJob:
    """父进程是唯一长期持有者，父进程消失时由 Windows 结束加入的子进程。

    只管子进程本身。它启动的游戏不进 Job，停止轮流后和单次运行一样留着。
    """

    def __init__(self, child_id):
        import win32job as api

        self.name = "Local\\M7A-rotation-" + child_id
        self.handle = api.CreateJobObject(None, self.name)
        info = api.QueryInformationJobObject(self.handle, api.JobObjectExtendedLimitInformation)
        info["BasicLimitInformation"]["LimitFlags"] |= (
            api.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | api.JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK
        )
        api.SetInformationJobObject(self.handle, api.JobObjectExtendedLimitInformation, info)

    def close(self):
        self.handle.Close()


def _started_by(pid):
    """源码环境里 venv 的 python.exe 只是启动器，解释器是它的子进程，所以往上看两层。"""
    import psutil

    try:
        process = psutil.Process()
        for _ in range(2):
            process = process.parent()
            if process is None:
                return False
            if process.pid == pid:
                return True
    except psutil.Error:
        pass
    return False


def _awaited(parent, run_id):
    """父进程当前在等的是不是这次子运行。"""
    rotation = (runs.load_run(parent) or {}).get("rotation") or {}
    rows, index = rotation.get("accounts") or [], rotation.get("index")
    return isinstance(index, int) and 0 <= index < len(rows) and rows[index].get("run_id") == run_id


def join_parent(session):
    """只有父进程正在等的那次子运行可借用父锁。在加载游戏模块之前加入 Job。"""
    parent = os.getenv(PARENT_ENV)
    if not parent:
        return False
    import win32api
    import win32job

    holder = runs.read_active_run() or {}
    if (
        not runs.is_valid_run_id(parent)
        or holder.get("run_id") != parent
        or not holder.get("rotation")
        or not _awaited(parent, session.run_id)
        or not _started_by(holder.get("pid"))
        or not os.getenv(JOB_ENV)
    ):
        raise AccountError("rotation_parent_lost", "轮流运行的父进程已退出或不持有运行锁")
    try:
        job = win32job.OpenJobObject(win32job.JOB_OBJECT_ASSIGN_PROCESS, False, os.environ[JOB_ENV])
        try:
            win32job.AssignProcessToJobObject(job, win32api.GetCurrentProcess())
        finally:
            job.Close()
    except Exception:
        raise AccountError("rotation_parent_lost", "无法加入轮流进程，当前账号已停止") from None
    session.update_record(parent_run_id=parent, lock="parent")
    return True


def _pump(stream):
    try:
        for line in stream:
            print(line, end="", flush=True)
    except (OSError, ValueError):
        return


def _kill_tree(process):
    """子进程卡住时，连同它启动的辅助程序一起结束，游戏留着。"""
    import psutil

    try:
        members = psutil.Process(process.pid).children(recursive=True)
    except psutil.Error:
        members = []
    process.kill()
    for member in members:
        try:
            if member.name().casefold() != "starrail.exe":
                member.kill()
        except psutil.Error:
            continue
    process.wait(timeout=GRACE)


def _command(control):
    return (_read_json(control) or {}).get("command")


def _requested(control, child_id):
    if _command(control) == COMMAND_STOP:
        return "stopped"
    request = _read_json(control + ".skip") or {}
    if request.get("child_run_id") == child_id:
        return "skipped"
    return None


def _run_child(
    session,
    row,
    task,
    args,
    *,
    clock=time.monotonic,
    sleep=time.sleep,
    spawn=subprocess.Popen,
    job_factory=ChildJob,
):
    child_id = row["run_id"]
    control = session.record["control_file"]
    cancel = runs.run_file(child_id, ".cancel")
    command = [task, "--account", row["uid"], "--after-finish", "None", "--non-interactive"]
    for attr, flag in (("page_task", "--page-task"), ("retry_step", "--retry-step")):
        if value := getattr(args, attr, None):
            command.extend([flag, value])
    if args.scheduled:
        command.append("--scheduled")
    if getattr(args, "startup_task", False):
        command.append("--startup-task")
    while _command(control) == COMMAND_PAUSE:
        _atomic_write_json(control + ".state", {"state": "paused"})
        if cause := _requested(control, child_id):
            return cause, cause
        sleep(0.15)
    if cause := _requested(control, child_id):
        return cause, cause
    job = job_factory(child_id)
    process = pump = None
    try:
        env = {
            **os.environ,
            PARENT_ENV: session.run_id,
            JOB_ENV: job.name,
            CANCEL_ENV: cancel,
            "M7A_ROTATION_MERGE": "1" if session.record["rotation"]["merge"] else "0",
            CONTROL_FILE_ENV: control,
            "MARCH7TH_NO_RUN_IMMEDIATELY": "0",
            "PYTHONUNBUFFERED": "1",
            "MARCH7TH_NON_INTERACTIVE": "1",
        }
        process = spawn(
            worker_command(command, child_id),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        pump = threading.Thread(target=_pump, args=(process.stdout,), daemon=True)
        pump.start()
        remaining = args.account_timeout
        previous = clock()
        paused = False
        cause = None
        while process.poll() is None:
            cause = _requested(control, child_id)
            now = clock()
            if not paused:
                remaining -= now - previous
            previous = now
            paused = _command(control) == COMMAND_PAUSE
            if not cause and remaining <= 0:
                cause = "timeout"
            if cause:
                try:
                    write_command(cancel, COMMAND_STOP)
                except OSError:
                    print("停止指令文件暂时不可写，将在宽限时间后结束子进程", flush=True)
                try:
                    process.wait(timeout=GRACE)
                except subprocess.TimeoutExpired:
                    pass
                break
            sleep(0.1)
        cause = _requested(control, child_id) or cause
        if cause:
            return cause, "account_timeout" if cause == "timeout" else cause
        result = runs.load_run(child_id)
        if not result or result.get("exit_code") is None:
            return "failed", "child_crashed" if process.returncode else "child_record_missing"
        if process.returncode == 0 and result["exit_code"] == 0:
            return "success", None
        partial = any(s.get("status") == "success" for s in (result.get("steps") or []))
        return "partial" if partial else "failed", result.get("reason") or "child_failed"
    finally:
        try:
            if process is not None and process.poll() is None:
                _kill_tree(process)
        finally:
            job.close()
        if pump:
            pump.join(timeout=2)
        if process and process.stdout and (not pump or not pump.is_alive()):
            process.stdout.close()


def finalize(session, config, rotation):
    from module.accounts.messages import send_summary

    try:
        send_summary(rotation, rotation["merge"])
    finally:
        from utils.runs import effective_after_finish

        action = effective_after_finish(config.after_finish, session.run_id)
        if action == "Loop":
            print("多账号轮流不支持循环，本轮结束。", flush=True)
            action = "None"
        if config.get_value("play_audio", False):
            from tasks.game import play_finish_audio

            play_finish_audio()
        if action != "None":
            from tasks import game

            if game.get_game_controller().shutdown(action, on_stopped=game._finish_game_run) is False:
                raise RuntimeError("整轮完成后操作失败")


def rotate(session, config, args, *, store=None, run_child=_run_child, finish=finalize):
    task = "workflow" if args.workflow_name else args.task or "main"
    if task not in ROTATABLE:
        raise AccountError("account_unsupported", "该任务不支持多账号轮流", 2)
    store = store or AccountStore()
    index = store.index()
    require_supported(config, index)
    rows = [
        dict(
            uid=a["uid"],
            name=a["name"],
            status="waiting",
            run_id=None,
            reason=None,
            started_at=None,
            ended_at=None,
        )
        for a in index["accounts"]
        if a["rotate"]
    ]
    if not rows:
        raise AccountError("account_unsupported", "没有参与轮流的账号", 2)
    from utils.console import is_docker_started

    if not config.get_value("auto_update") and not is_docker_started():
        session.note(reason="first_run_required", error="请先在图形界面完成首次使用确认")
        return runs.EXIT_FIRST_RUN_REQUIRED
    rotation = {"index": None, "accounts": rows, "merge": bool(config.notify_merge)}
    session.update_record(rotation=rotation)
    lock = session.acquire_lock()
    if lock.status != runs.LOCK_ACQUIRED:
        session.note(reason="busy", error="未能独占运行锁，本轮未开始")
        return runs.EXIT_BUSY
    stopped = False
    for number, row in enumerate(rows):
        if stopped or _command(session.record["control_file"]) == COMMAND_STOP:
            stopped = True
            row.update(status="stopped", reason="stopped", ended_at=runs._now_iso())
        else:
            rotation["index"] = number
            row.update(status="running", started_at=runs._now_iso(), run_id=runs.new_run_id())
            session.update_record(rotation=rotation)
            try:
                status, reason = run_child(session, row, task, args)
            except Exception as error:
                status, reason = "failed", "child_error"
                print(f"本账号运行失败（{type(error).__name__}），继续下一个账号", flush=True)
            stopped = status == "stopped"
            row.update(status=status, reason=reason, ended_at=runs._now_iso())
        session.update_record(rotation=rotation)
    if stopped or _command(session.record["control_file"]) == COMMAND_STOP:
        _atomic_write_json(session.record["control_file"] + ".state", {"state": "stopping"})
        return runs.EXIT_STOPPED
    try:
        finish(session, config, rotation)
    except Exception as error:
        session.note(reason="rotation_finish_failed", error="轮流运行的汇总或完成后操作失败")
        print(f"轮流运行收尾失败（{type(error).__name__}）", flush=True)
        return runs.EXIT_FAILED
    return runs.EXIT_OK if all(a["status"] == "success" for a in rows) else runs.EXIT_FAILED
