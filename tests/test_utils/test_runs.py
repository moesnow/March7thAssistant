# coding:utf-8
"""utils/runs.py 运行记录、运行锁与输出捕获测试。"""
import io
import json
import logging
import os
import subprocess
import sys
import threading
import time

import pytest

from utils import runs
from utils.pause import CONTROL_FILE_ENV, COMMAND_RESUME, _read_json


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """在临时目录中运行：runs_dir() 相对当前目录；隔离控制文件环境变量。"""
    monkeypatch.chdir(tmp_path)
    saved = os.environ.pop(CONTROL_FILE_ENV, None)
    yield tmp_path
    os.environ.pop(CONTROL_FILE_ENV, None)
    if saved is not None:
        os.environ[CONTROL_FILE_ENV] = saved


def _dead_process():
    """返回一个已退出进程的 (pid, create_time)。"""
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.5)"])
    create_time = runs.process_create_time(proc.pid)
    proc.wait()
    return proc.pid, create_time


def _begin(**kwargs):
    kwargs.setdefault("task", "daily")
    kwargs.setdefault("version", "v0")
    return runs.RunSession.begin(capture=False, **kwargs)


class TestRunId:
    def test_new_run_id_is_valid_and_sortable(self):
        run_id = runs.new_run_id()
        assert runs.is_valid_run_id(run_id)
        assert run_id[:8].isdigit()

    @pytest.mark.parametrize("value", [None, "", "latest", "../20261030-193512-4f2a", "20261030-193512-4F2A",
                                       "20261030-193512-4f2a.json", "2026103-193512-4f2a"])
    def test_rejects_invalid_ids(self, value):
        assert not runs.is_valid_run_id(value)


class TestRunSession:
    def test_begin_writes_running_record(self, workdir):
        session = _begin(argv=["daily", "--non-interactive"], invoker="non_interactive")
        record = runs.load_run(session.run_id)
        assert record["status"] == runs.STATUS_RUNNING
        assert record["task"] == "daily"
        assert record["pid"] == os.getpid()
        assert record["invoker"] == "non_interactive"
        assert record["args"] == ["daily", "--non-interactive"]
        # 独立运行时分配本次运行的控制文件，并重置为「继续」
        assert os.environ[CONTROL_FILE_ENV] == record["control_file"]
        assert _read_json(record["control_file"]) == {"command": COMMAND_RESUME}

    def test_keeps_control_file_injected_by_gui(self, workdir):
        gui_control = str(workdir / "temp" / "pause.json")
        os.environ[CONTROL_FILE_ENV] = gui_control
        session = _begin()
        assert session.record["control_file"] == os.path.abspath(gui_control)

    def test_uses_given_run_id_and_rejects_invalid(self, workdir):
        assert _begin(run_id="20261030-193512-4f2a").run_id == "20261030-193512-4f2a"
        assert runs.is_valid_run_id(_begin(run_id="../../evil").run_id)

    @pytest.mark.parametrize("exit_code, status, reason", [
        (runs.EXIT_OK, runs.STATUS_SUCCESS, None),
        (runs.EXIT_FAILED, runs.STATUS_FAILED, None),
        (runs.EXIT_FIRST_RUN_REQUIRED, runs.STATUS_BLOCKED, runs.REASON_FIRST_RUN_REQUIRED),
        (runs.EXIT_BUSY, runs.STATUS_BLOCKED, runs.REASON_BUSY),
        (runs.EXIT_STOPPED, runs.STATUS_STOPPED, None),
    ])
    def test_finish_maps_exit_code(self, workdir, exit_code, status, reason):
        session = _begin()
        session.finish(exit_code)
        record = runs.load_run(session.run_id)
        assert (record["status"], record["reason"], record["exit_code"]) == (status, reason, exit_code)
        assert record["ended_at"]

    def test_finish_uses_noted_fields_and_runs_once(self, workdir):
        session = _begin()
        session.note(status=runs.STATUS_INTERRUPTED, error="手动强制停止", screenshot=None)
        session.finish(1)
        session.finish(0)  # 第二次调用不生效
        record = runs.load_run(session.run_id)
        assert record["status"] == runs.STATUS_INTERRUPTED
        assert record["error"] == "手动强制停止"
        assert record["exit_code"] == 1

    def test_last_error_log_fills_error_only_on_failure(self, workdir):
        logger = logging.getLogger("test_runs_last_error")
        logger.propagate = False
        failed = _begin()
        handler = failed.error_log_handler()
        logger.addHandler(handler)
        try:
            logger.error("\x1b[91m未找到流程\x1b[0m")
            failed.finish(1)
        finally:
            logger.removeHandler(handler)
        assert runs.load_run(failed.run_id)["error"] == "未找到流程"

        ok = _begin()
        ok.last_error = "中途出现过但已恢复的错误"
        ok.finish(0)
        assert runs.load_run(ok.run_id)["error"] is None

    def test_print_json_on_finish(self, workdir, capsys):
        session = _begin()
        session.print_json = True
        session.finish(0)
        line = capsys.readouterr().out.strip().splitlines()[-1]
        assert line.isascii()
        assert json.loads(line)["status"] == runs.STATUS_SUCCESS

    def test_exit_code_of(self):
        assert runs.exit_code_of(SystemExit()) == 0
        assert runs.exit_code_of(SystemExit(4)) == 4
        assert runs.exit_code_of(SystemExit("message")) == 1


class TestEffectiveStatus:
    def test_running_with_live_process(self):
        record = {"status": runs.STATUS_RUNNING, "pid": os.getpid(), "pid_create_time": runs.process_create_time(os.getpid())}
        assert runs.effective_status(record) == runs.STATUS_RUNNING

    def test_running_with_dead_process_is_aborted(self):
        pid, create_time = _dead_process()
        record = {"status": runs.STATUS_RUNNING, "pid": pid, "pid_create_time": create_time}
        assert runs.effective_status(record) == runs.STATUS_ABORTED

    def test_reused_pid_is_not_alive(self):
        assert not runs.is_process_alive(os.getpid(), runs.process_create_time(os.getpid()) - 100)

    def test_finished_status_unchanged(self):
        assert runs.effective_status({"status": runs.STATUS_FAILED, "pid": 0}) == runs.STATUS_FAILED


class TestRunLock:
    def _info(self, run_id, pid=None, create_time=None):
        pid = pid or os.getpid()
        return {"run_id": run_id, "pid": pid,
                "pid_create_time": create_time if create_time is not None else runs.process_create_time(pid),
                "task": "daily", "workflow": None}

    def test_acquire_and_block_second_run(self, workdir):
        assert runs.acquire_run_lock(self._info("20261030-000001-aaaa")) == (True, None)
        acquired, holder = runs.acquire_run_lock(self._info("20261030-000002-bbbb"))
        assert not acquired
        assert holder["run_id"] == "20261030-000001-aaaa"
        assert runs.read_active_run()["run_id"] == "20261030-000001-aaaa"

    def test_reacquire_by_same_run(self, workdir):
        info = self._info("20261030-000001-aaaa")
        assert runs.acquire_run_lock(info)[0]
        assert runs.acquire_run_lock(info) == (True, None)

    def test_force_takes_over(self, workdir):
        runs.acquire_run_lock(self._info("20261030-000001-aaaa"))
        acquired, holder = runs.acquire_run_lock(self._info("20261030-000002-bbbb"), force=True)
        assert acquired and holder["run_id"] == "20261030-000001-aaaa"
        assert runs.read_active_run()["run_id"] == "20261030-000002-bbbb"
        # 被越过的运行结束时不能删掉别人的锁
        runs.release_run_lock("20261030-000001-aaaa")
        assert runs.read_active_run()["run_id"] == "20261030-000002-bbbb"

    def test_stale_lock_is_replaced(self, workdir):
        pid, create_time = _dead_process()
        runs.acquire_run_lock(self._info("20261030-000001-aaaa", pid, create_time))
        assert runs.read_active_run() is None
        assert runs.acquire_run_lock(self._info("20261030-000002-bbbb")) == (True, None)
        assert runs.read_active_run()["run_id"] == "20261030-000002-bbbb"

    def test_release_only_own_lock(self, workdir):
        runs.acquire_run_lock(self._info("20261030-000001-aaaa"))
        runs.release_run_lock("20261030-000009-ffff")
        assert runs.read_active_run() is not None
        runs.release_run_lock("20261030-000001-aaaa")
        assert runs.read_active_run() is None

    def test_session_finish_releases_lock(self, workdir):
        session = _begin()
        assert session.acquire_lock().status == runs.LOCK_ACQUIRED
        assert runs.load_run(session.run_id)["lock"] == runs.LOCK_ACQUIRED
        session.finish(0)
        assert runs.read_active_run() is None

    def test_session_busy_and_forced(self, workdir):
        runs.acquire_run_lock(self._info("20261030-000001-aaaa"))
        session = _begin()
        busy = session.acquire_lock()
        assert busy.status == runs.LOCK_BUSY and busy.holder["run_id"] == "20261030-000001-aaaa"
        assert not session.lock_held
        forced = session.acquire_lock(force=True)
        assert forced.status == runs.LOCK_FORCED and forced.holder["run_id"] == "20261030-000001-aaaa"
        assert session.lock_held
        assert runs.load_run(session.run_id)["lock"] == runs.LOCK_FORCED


class TestRunLockUnavailable:
    """「锁被占用」与「锁无法读写」分开：只有持有进程确认存活才算占用，读写失败单独报告。"""

    @pytest.fixture(autouse=True)
    def _fast_retry(self, monkeypatch):
        monkeypatch.setattr(runs, "_LOCK_RETRY_DELAY", 0)

    def _info(self, run_id, pid=None, create_time=None):
        return TestRunLock._info(self, run_id, pid, create_time)

    def test_persistent_io_error_is_unavailable(self, workdir, monkeypatch):
        def deny(path, data):
            raise PermissionError(13, "拒绝访问", path)

        monkeypatch.setattr(runs, "_create_exclusive", deny)
        with pytest.raises(runs.RunLockUnavailable, match="active.json"):
            runs.acquire_run_lock(self._info("20261030-000001-aaaa"))

        session = _begin()
        result = session.acquire_lock()
        assert result.status == runs.LOCK_UNAVAILABLE
        assert "拒绝访问" in result.error
        assert not session.lock_held
        record = runs.load_run(session.run_id)
        assert record["lock"] == runs.LOCK_UNAVAILABLE and "拒绝访问" in record["lock_error"]

    def test_transient_error_is_retried(self, workdir, monkeypatch):
        real = runs._create_exclusive
        failures = []

        def flaky(path, data):
            if len(failures) < 2:
                failures.append(1)
                raise PermissionError(13, "共享冲突", path)
            return real(path, data)

        monkeypatch.setattr(runs, "_create_exclusive", flaky)
        assert runs.acquire_run_lock(self._info("20261030-000001-aaaa")) == (True, None)
        assert len(failures) == 2

    def test_unremovable_stale_lock_is_unavailable_not_busy(self, workdir, monkeypatch):
        """陈旧锁删不掉时不能报告成「已有任务在运行」：持有进程早已退出。"""
        pid, create_time = _dead_process()
        runs.acquire_run_lock(self._info("20261030-000001-aaaa", pid, create_time))
        lock_path = os.path.join(runs.runs_dir(), "active.json")
        real_remove = os.remove

        def remove(path, *args, **kwargs):
            if os.path.abspath(path) == lock_path:
                raise PermissionError(13, "拒绝访问", path)
            return real_remove(path, *args, **kwargs)

        monkeypatch.setattr(runs.os, "remove", remove)
        with pytest.raises(runs.RunLockUnavailable):
            runs.acquire_run_lock(self._info("20261030-000002-bbbb"))

    def test_live_holder_still_busy_despite_io_errors(self, workdir, monkeypatch):
        """写锁持续出错，但能读到仍在运行的持有者：照样报告占用，而不是不可用。"""
        runs.acquire_run_lock(self._info("20261030-000001-aaaa"))

        def deny(path, data):
            raise PermissionError(32, "另一个程序正在使用此文件", path)

        monkeypatch.setattr(runs, "_create_exclusive", deny)
        acquired, holder = runs.acquire_run_lock(self._info("20261030-000002-bbbb"))
        assert not acquired and holder["run_id"] == "20261030-000001-aaaa"

    def test_hardlink_unsupported_falls_back_to_exclusive_create(self, workdir, monkeypatch):
        """POSIX 上文件系统不支持硬链接（部分网络盘 / Docker 挂载目录）时改用 O_EXCL 创建。"""
        def no_link(src, dst):
            raise OSError(95, "Operation not supported")

        monkeypatch.setattr(runs.sys, "platform", "linux")
        monkeypatch.setattr(runs.os, "link", no_link)
        assert runs.acquire_run_lock(self._info("20261030-000001-aaaa")) == (True, None)
        assert runs.read_active_run()["run_id"] == "20261030-000001-aaaa"
        acquired, holder = runs.acquire_run_lock(self._info("20261030-000002-bbbb"))
        assert not acquired and holder["run_id"] == "20261030-000001-aaaa"

    def test_idle_continues_when_lock_becomes_unavailable(self, workdir, monkeypatch):
        session = _begin()
        session.acquire_lock()

        def unavailable(info, force=False):
            raise runs.RunLockUnavailable("logs/runs/active.json：磁盘已满")

        errors = []
        with runs.idle_without_run_lock(on_unavailable=errors.append, poll_seconds=0.01):
            monkeypatch.setattr(runs, "acquire_run_lock", unavailable)
        assert errors == ["logs/runs/active.json：磁盘已满"]
        assert not session.lock_held
        assert runs.load_run(session.run_id)["lock"] == runs.LOCK_UNAVAILABLE

    def test_idle_releases_and_reacquires(self, workdir):
        session = _begin()
        session.acquire_lock()
        with runs.idle_without_run_lock(poll_seconds=0.1):
            assert runs.read_active_run() is None
            # 空闲期间别的运行可以取得锁
            assert runs.acquire_run_lock(self._info("20261030-000002-bbbb"))[0]
            threading.Timer(0.3, runs.release_run_lock, args=("20261030-000002-bbbb",)).start()
        # 退出时锁被占用：等对方释放后重新取得
        assert runs.read_active_run()["run_id"] == session.run_id
        assert session.lock_held
        session.finish(0)

    def test_idle_reports_waiting_holder(self, workdir):
        session = _begin()
        session.acquire_lock()
        waited = []
        with runs.idle_without_run_lock(on_wait=waited.append, poll_seconds=0.1):
            runs.acquire_run_lock(self._info("20261030-000002-bbbb"))
            threading.Timer(0.3, runs.release_run_lock, args=("20261030-000002-bbbb",)).start()
        assert [holder["run_id"] for holder in waited] == ["20261030-000002-bbbb"]
        session.finish(0)

    def test_idle_without_session_lock_is_noop(self, workdir):
        _begin()  # 未取得运行锁
        with runs.idle_without_run_lock():
            pass
        assert runs.read_active_run() is None


class TestOutputCapture:
    def test_tee_forwards_and_strips_colors(self):
        original, sink = io.StringIO(), io.StringIO()
        tee = runs._TeeStream(original, sink)
        tee.write("\x1b[92mINFO\x1b[0m | 你好\n")
        tee.flush()
        assert original.getvalue() == "\x1b[92mINFO\x1b[0m | 你好\n"
        assert sink.getvalue() == "INFO | 你好\n"

    def test_tee_without_console(self):
        sink = io.StringIO()
        tee = runs._TeeStream(None, sink)
        assert tee.write("abc") == 3
        assert not tee.isatty()
        assert sink.getvalue() == "abc"

    def test_tee_keeps_log_when_console_cannot_encode(self):
        """控制台编码放不下中文时（英文 Windows 的 cp1252），日志仍要完整留下。

        在进程内用 cp1252 包一层内存流来构造失败场景，不依赖 runner 的语言环境：
        CI（cp1252）、本机（cp936/UTF-8）行为一致，改坏这里任何平台都会报红。
        """
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="cp1252", errors="strict", newline="")
        sink = io.StringIO()
        tee = runs._TeeStream(stream, sink)
        assert tee.write("第一行\n") == 4      # 不把 UnicodeEncodeError 甩给调用方
        assert sink.getvalue() == "第一行\n"    # 控制台侧丢掉，日志侧不能丢

    def test_tee_does_not_swallow_other_stream_errors(self):
        """只兜编码错误：磁盘满、流已关闭这类真失败必须照旧暴露。"""
        class Broken(io.StringIO):
            def write(self, text):
                raise OSError("磁盘已满")

        tee = runs._TeeStream(Broken(), io.StringIO())
        with pytest.raises(OSError):
            tee.write("abc")

    def test_capture_output_writes_log_file(self, tmp_path):
        log_path = str(tmp_path / "runs" / "x.log")
        code = (
            "import sys, logging; from utils.runs import capture_output; "
            f"capture_output({log_path!r}); print('第一行'); "
            "logging.basicConfig(); logging.getLogger().error('第二行'); raise SystemExit(3)"
        )
        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        # 子进程不走 main.py，没有 ensure_utf8_output 兜底：显式钉死编码，
        # 免得用例随 runner 的 ANSI 代码页（cp1252 / cp936 / UTF-8）时红时绿
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        result = subprocess.run([sys.executable, "-c", code], cwd=repo, capture_output=True, timeout=60, env=env)
        assert result.returncode == 3
        with open(log_path, encoding="utf-8") as f:
            content = f.read()
        assert "第一行" in content and "第二行" in content
        assert "\r\n" not in content


class TestHistory:
    def test_recent_runs_newest_first(self, workdir):
        first = _begin()
        first.finish(0)
        time.sleep(1.1)
        second = _begin()
        listed = runs.recent_runs(5)
        assert [record["run_id"] for record in listed] == [second.run_id, first.run_id]
        assert listed[0]["effective_status"] == runs.STATUS_RUNNING
        assert listed[1]["effective_status"] == runs.STATUS_SUCCESS

    def test_cleanup_keeps_latest(self, workdir):
        os.makedirs(runs.runs_dir())
        ids = [f"20261030-0000{i:02d}-aaaa" for i in range(6)]
        for run_id in ids:
            for suffix in (".json", ".log"):
                with open(runs.run_file(run_id, suffix), "w", encoding="utf-8") as f:
                    f.write(json.dumps({"run_id": run_id, "status": runs.STATUS_SUCCESS}) if suffix == ".json" else "")
        runs.cleanup_old_runs(keep=2)
        assert runs.list_run_ids() == ids[-2:]
        assert not os.path.exists(runs.run_file(ids[0], ".log"))

    def test_describe_run(self):
        text = runs.describe_run({"workflow": "清体力", "run_id": "20261030-000001-aaaa", "pid": 1})
        assert "流程「清体力」" in text and "20261030-000001-aaaa" in text
        assert runs.describe_run(None) == "未知运行"
