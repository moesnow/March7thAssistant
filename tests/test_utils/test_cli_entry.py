# coding:utf-8
"""utils/cli_entry.py 非提权入口测试：提权运行（用假启动器代替 UAC）、跟随输出、控制指令、状态查询。"""
import io
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from utils import cli_entry, runs
from utils.admin import ERROR_CANCELLED
from utils.pause import CONTROL_FILE_ENV, PauseController, read_state

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    saved = os.environ.pop(CONTROL_FILE_ENV, None)
    yield tmp_path
    os.environ.pop(CONTROL_FILE_ENV, None)
    if saved is not None:
        os.environ[CONTROL_FILE_ENV] = saved


class _PopenProcess:
    """把 subprocess.Popen 包装成与 utils.admin.ElevatedProcess 相同的接口。"""

    def __init__(self, popen):
        self.popen = popen
        self.pid = popen.pid

    def poll(self, timeout=0):
        try:
            return self.popen.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    def close(self):
        pass


# 假的「管理员进程」：按命令行里的 --run-id 写运行日志与运行记录，然后以指定退出码结束
_FAKE_WORKER = r"""
import json, os, sys, time
args = sys.argv[1:]
run_id = args[args.index("--run-id") + 1]
exit_code = int(os.environ.get("FAKE_EXIT", "0"))
runs_dir = os.path.join("logs", "runs")
os.makedirs(runs_dir, exist_ok=True)
with open(os.path.join(runs_dir, run_id + ".log"), "a", encoding="utf-8", newline="") as f:
    for line in ("开始执行 " + " ".join(args), "第二行输出"):
        f.write(line + "\n"); f.flush(); time.sleep(0.2)
record = {"run_id": run_id, "status": "success" if exit_code == 0 else "failed", "exit_code": exit_code,
          "error": None if exit_code == 0 else "模拟失败", "pid": os.getpid(), "pid_create_time": None}
with open(os.path.join(runs_dir, run_id + ".json"), "w", encoding="utf-8") as f:
    json.dump(record, f)
sys.exit(exit_code)
"""


def _fake_launcher(exit_code, captured=None):
    def launch(cmd):
        if captured is not None:
            captured.append(cmd)
        env = dict(os.environ, FAKE_EXIT=str(exit_code))
        return _PopenProcess(subprocess.Popen([sys.executable, "-c", _FAKE_WORKER, *cmd[1:]], env=env))
    return launch


class TestWorkerCommand:
    def test_source_mode(self, workdir):
        cmd = cli_entry.worker_command(["daily", "--json", "--detach", "--after-finish", "None"], "20261030-000001-aaaa")
        assert cmd[0] == sys.executable
        assert cmd[1] == os.path.abspath("main.py")
        assert cmd[2:] == ["daily", "--after-finish", "None", "--run-id", "20261030-000001-aaaa", "--non-interactive"]

    def test_non_interactive_not_duplicated(self, workdir):
        cmd = cli_entry.worker_command(["daily", "--non-interactive"], "20261030-000001-aaaa")
        assert cmd.count("--non-interactive") == 1

    def test_frozen_mode_uses_assistant_exe(self, tmp_path, monkeypatch):
        (tmp_path / "March7th Assistant.exe").write_bytes(b"")
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "m7a.exe"))
        cmd = cli_entry.worker_command(["power"], "20261030-000001-aaaa")
        assert cmd[0] == str(tmp_path / "March7th Assistant.exe")
        assert cmd[1:] == ["power", "--run-id", "20261030-000001-aaaa", "--non-interactive"]

    def test_frozen_mode_falls_back_to_self(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "m7a.exe"))
        assert cli_entry.worker_command(["power"], "20261030-000001-aaaa")[0] == str(tmp_path / "m7a.exe")


class TestRunTaskElevated:
    def test_follows_output_and_returns_exit_code(self, workdir):
        out = io.StringIO()
        captured = []
        code = cli_entry.run_task_elevated(["daily"], launcher=_fake_launcher(7, captured), out=out, poll_interval=0.05)
        assert code == 7
        text = out.getvalue()
        assert "开始执行" in text and "daily --run-id" in text and "第二行输出" in text
        assert "运行结束：失败（退出码 7）" in text
        assert "错误：模拟失败" in text
        assert "--non-interactive" in captured[0]

    def test_json_output_is_last_line(self, workdir):
        out = io.StringIO()
        code = cli_entry.run_task_elevated(["power"], json_output=True, launcher=_fake_launcher(0), out=out, poll_interval=0.05)
        assert code == 0
        last = out.getvalue().strip().splitlines()[-1]
        assert last.isascii()
        assert json.loads(last)["status"] == "success"

    def test_uac_cancelled(self, workdir):
        def cancelled(cmd):
            error = OSError("操作已被用户取消。")
            error.winerror = ERROR_CANCELLED
            raise error

        out = io.StringIO()
        assert cli_entry.run_task_elevated(["daily"], launcher=cancelled, out=out) == runs.EXIT_ELEVATION_FAILED
        assert "已取消管理员授权" in out.getvalue()

    def test_detach_returns_immediately(self, workdir):
        class _Started:
            pid = 4321

            def close(self):
                pass

        out = io.StringIO()
        code = cli_entry.run_task_elevated(["main"], json_output=True, detach=True, launcher=lambda cmd: _Started(), out=out)
        assert code == 0
        info = json.loads(out.getvalue().strip().splitlines()[-1])
        assert info["pid"] == 4321 and runs.is_valid_run_id(info["run_id"])
        assert "--follow" in out.getvalue()

    def test_worker_without_record(self, workdir):
        def no_record(cmd):
            return _PopenProcess(subprocess.Popen([sys.executable, "-c", "raise SystemExit(1)"]))

        out = io.StringIO()
        assert cli_entry.run_task_elevated(["daily"], launcher=no_record, out=out, poll_interval=0.05) == 1
        assert "没有生成运行记录" in out.getvalue()

    def test_abnormal_exit_code_maps_to_failure(self):
        assert cli_entry._normalize_exit_code(0xC000013A) == runs.EXIT_FAILED
        assert cli_entry._normalize_exit_code(None) == runs.EXIT_FAILED
        assert cli_entry._normalize_exit_code(4) == 4


def _write_record(run_id, **fields):
    os.makedirs(runs.runs_dir(), exist_ok=True)
    record = {"run_id": run_id, "status": runs.STATUS_SUCCESS, "exit_code": 0, "pid": os.getpid(),
              "pid_create_time": runs.process_create_time(os.getpid()),
              "log_file": runs.run_file(run_id, ".log")}
    record.update(fields)
    with open(runs.run_file(run_id, ".json"), "w", encoding="utf-8") as f:
        json.dump(record, f)
    return record


class TestFollowAndResolve:
    def test_resolve_latest_and_invalid(self, workdir):
        assert cli_entry.resolve_run("latest") == (None, "还没有任何运行记录")
        _write_record("20261030-000001-aaaa")
        _write_record("20261030-000002-bbbb")
        assert cli_entry.resolve_run("latest")[0]["run_id"] == "20261030-000002-bbbb"
        assert "无效的运行编号" in cli_entry.resolve_run("../etc")[1]
        assert "找不到运行记录" in cli_entry.resolve_run("20261030-000003-cccc")[1]

    def test_resolve_current_prefers_lock_then_running_record(self, workdir):
        assert cli_entry.resolve_run("current")[0] is None
        _write_record("20261030-000001-aaaa", status=runs.STATUS_RUNNING)
        assert cli_entry.resolve_run("current")[0]["run_id"] == "20261030-000001-aaaa"

    def test_follow_finished_run(self, workdir):
        _write_record("20261030-000001-aaaa", status=runs.STATUS_FAILED, exit_code=1, error="找不到游戏")
        with open(runs.run_file("20261030-000001-aaaa", ".log"), "w", encoding="utf-8") as f:
            f.write("".join(f"第{i}行\n" for i in range(100)))
        out = io.StringIO()
        assert cli_entry.follow_command("latest", out=out) == 1
        text = out.getvalue()
        assert "省略前 60 行" in text and "第99行" in text and "第10行\n" not in text
        assert "错误：找不到游戏" in text

    def test_follow_running_until_done(self, workdir):
        run_id = "20261030-000001-aaaa"
        _write_record(run_id, status=runs.STATUS_RUNNING, exit_code=None)
        log_path = runs.run_file(run_id, ".log")
        open(log_path, "w", encoding="utf-8").close()

        def finish_later():
            time.sleep(0.4)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("任务完成\n")
            _write_record(run_id, status=runs.STATUS_SUCCESS, exit_code=0)

        threading.Thread(target=finish_later).start()
        out = io.StringIO()
        assert cli_entry.follow_command(run_id, out=out, poll_interval=0.05) == 0
        assert "任务完成" in out.getvalue()
        assert "运行结束：成功" in out.getvalue()

    def test_summary_mentions_unavailable_lock(self, workdir):
        _write_record("20261030-000001-aaaa", lock=runs.LOCK_UNAVAILABLE, lock_error="logs\\runs\\active.json：拒绝访问")
        out = io.StringIO()
        assert cli_entry.follow_command("latest", out=out) == 0
        assert "运行锁不可用" in out.getvalue() and "拒绝访问" in out.getvalue()

    def test_follow_aborted_run(self, workdir):
        _write_record("20261030-000001-aaaa", status=runs.STATUS_RUNNING, exit_code=None, pid=999999999)
        out = io.StringIO()
        assert cli_entry.follow_command("latest", out=out) == 1
        assert "异常结束" in out.getvalue()


class _LogStub:
    def warning(self, *args, **kwargs):
        pass


class TestControl:
    @pytest.fixture
    def running(self, workdir, monkeypatch):
        # 控制器的播报日志换成桩：真实日志模块会在临时目录里初始化配置
        from utils import pause as pause_mod
        monkeypatch.setattr(pause_mod, "log", _LogStub())
        run_id = "20261030-000001-aaaa"
        control = runs.run_file(run_id, ".control")
        _write_record(run_id, status=runs.STATUS_RUNNING, exit_code=None, control_file=control)
        ctl = PauseController()
        ctl.start(control)
        yield run_id, control, ctl
        ctl.stop()

    def test_pause_then_resume(self, running):
        run_id, control, ctl = running
        out = io.StringIO()
        assert cli_entry.control_command(run_id, "pause", out=out, wait_seconds=1) == 0
        # 没有任务线程走到卡点：回执停在「暂停中」，同样视为已收到
        assert "将在下一步操作前暂停" in out.getvalue()
        assert ctl.is_paused()
        assert cli_entry.control_command(run_id, "resume", out=out, wait_seconds=2) == 0
        assert "任务已恢复运行" in out.getvalue()
        assert not ctl.is_paused()

    def test_stop_acknowledged(self, running):
        run_id, control, ctl = running
        out = io.StringIO()
        assert cli_entry.control_command("current", "stop", json_output=True, out=out, wait_seconds=1) == 0
        assert ctl.stop_requested
        result = json.loads(out.getvalue().strip().splitlines()[-1])
        assert result["acknowledged"] and result["state"] == "stopping"

    def test_rejects_finished_run_and_bad_action(self, workdir):
        _write_record("20261030-000001-aaaa")
        out = io.StringIO()
        assert cli_entry.control_command("20261030-000001-aaaa", "pause", out=out) == 1
        assert "已经结束" in out.getvalue()
        assert cli_entry.control_command("20261030-000001-aaaa", "jump", out=out) == 1

    def test_no_ack_without_worker(self, workdir):
        _write_record("20261030-000001-aaaa", status=runs.STATUS_RUNNING, exit_code=None,
                      control_file=runs.run_file("20261030-000001-aaaa", ".control"))
        out = io.StringIO()
        assert cli_entry.control_command("20261030-000001-aaaa", "pause", out=out, wait_seconds=0.3) == 1
        assert "尚未回执" in out.getvalue()
        assert read_state(runs.run_file("20261030-000001-aaaa", ".control")) is None


def _run_main(*args):
    env = dict(os.environ, MARCH7TH_CONFIG_READONLY="1")
    return subprocess.run([sys.executable, str(REPO / "main.py"), *args], capture_output=True, timeout=120, env=env)


class TestReadOnlyCommands:
    """查询类命令无需管理员权限、不运行任务、不改动配置。"""

    def test_version(self):
        result = _run_main("--version")
        assert result.returncode == 0
        assert result.stdout.decode("utf-8").strip() == cli_entry.read_version()

    def test_list_json(self):
        result = _run_main("--list", "--json")
        assert result.returncode == 0
        tasks = json.loads(result.stdout)
        assert {"id": "daily"}.items() <= next(t for t in tasks if t["id"] == "daily").items()

    def test_status_json(self):
        config = REPO / "config.yaml"
        before = config.read_bytes() if config.exists() else None
        result = _run_main("--status")
        assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
        assert result.stdout.isascii()
        status = json.loads(result.stdout)
        for key in ("version", "install_dir", "first_run_completed", "game_path_exists", "active_run",
                    "recent_runs", "runs_dir", "install_registry", "agent_skill"):
            assert key in status
        assert status["install_dir"] == str(REPO)
        after = config.read_bytes() if config.exists() else None
        assert before == after

    def test_rejects_invalid_run_id(self):
        result = _run_main("daily", "--run-id", "../x")
        assert result.returncode == runs.EXIT_USAGE
