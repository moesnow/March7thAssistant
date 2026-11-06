# coding:utf-8
"""utils/uac_free.py 测试：开关状态判断、注册参数、通过计划任务启动并按运行记录跟踪（mock 计划任务接口）。"""
import json
import os
import sys

import pytest

import utils.schedule as schedule
from utils import runs, uac_free
from utils.pause import CONTROL_FILE_ENV


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    saved = os.environ.pop(CONTROL_FILE_ENV, None)
    yield tmp_path
    os.environ.pop(CONTROL_FILE_ENV, None)
    if saved is not None:
        os.environ[CONTROL_FILE_ENV] = saved


@pytest.fixture
def fake_task(monkeypatch):
    """假的计划任务：get_task_info 返回 info（None 表示不存在）"""
    # 状态判断与宿主平台无关：显式走 Windows 分支，保证非 Windows 平台也能测到
    monkeypatch.setattr(uac_free, "IS_WINDOWS", True)
    holder = {"info": None}
    monkeypatch.setattr(schedule, "get_task_info", lambda name: holder["info"])
    return holder


def _info_for_this_install(**fields):
    program, arguments = uac_free.task_action()
    info = {"enabled": True, "path": program, "arguments": arguments, "working_dir": os.getcwd(), "last_result": 0}
    info.update(fields)
    return info


def _write_record(run_id, **fields):
    os.makedirs(runs.runs_dir(), exist_ok=True)
    record = {"run_id": run_id, "status": runs.STATUS_RUNNING, "exit_code": None, "pid": os.getpid(),
              "pid_create_time": runs.process_create_time(os.getpid())}
    record.update(fields)
    with open(runs.run_file(run_id, ".json"), "w", encoding="utf-8") as f:
        json.dump(record, f)


class TestTaskAction:
    def test_source_mode_runs_main_py(self, workdir):
        program, arguments = uac_free.task_action()
        assert program == sys.executable
        assert arguments.endswith(uac_free.ARGS_PLACEHOLDER)
        assert os.path.abspath("main.py") in arguments

    def test_frozen_mode_runs_assistant_exe(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "March7th Launcher.exe"))
        # 图形界面（Launcher）与 m7a.exe 在同一目录，得到同一个管理员进程
        assert uac_free.task_action() == (str(tmp_path / "March7th Assistant.exe"), uac_free.ARGS_PLACEHOLDER)


class TestState:
    def test_off_when_task_missing(self, workdir, fake_task):
        assert uac_free.state() == (uac_free.STATE_OFF, None)
        assert uac_free.is_enabled() is False

    def test_on_for_this_install(self, workdir, fake_task):
        fake_task["info"] = _info_for_this_install()
        assert uac_free.state()[0] == uac_free.STATE_ON
        assert uac_free.is_enabled() is True

    def test_path_compare_ignores_case(self, workdir, fake_task):
        info = _info_for_this_install()
        fake_task["info"] = dict(info, path=info["path"].upper(), arguments=info["arguments"].upper())
        assert uac_free.state()[0] == uac_free.STATE_ON

    def test_other_install(self, workdir, fake_task):
        fake_task["info"] = _info_for_this_install(path="D:\\Other\\March7th Assistant.exe")
        state, info = uac_free.state()
        assert state == uac_free.STATE_OTHER and info["path"] == "D:\\Other\\March7th Assistant.exe"

    def test_disabled(self, workdir, fake_task):
        fake_task["info"] = _info_for_this_install(enabled=False)
        assert uac_free.state()[0] == uac_free.STATE_DISABLED

    def test_read_failure_counts_as_off(self, workdir, fake_task, monkeypatch):
        def broken(name):
            raise OSError("服务不可用")

        monkeypatch.setattr(schedule, "get_task_info", broken)
        assert uac_free.state() == (uac_free.STATE_OFF, None)

    def test_non_windows(self, monkeypatch):
        monkeypatch.setattr(uac_free, "IS_WINDOWS", False)
        assert uac_free.state() == (uac_free.STATE_OFF, None)
        assert uac_free.enable() is False
        assert uac_free.disable() is False


class TestEnableDisable:
    def test_enable_registers_on_demand_task(self, workdir, fake_task, monkeypatch):
        created = {}

        def _create(**kwargs):
            created.update(kwargs)
            fake_task["info"] = _info_for_this_install()

        monkeypatch.setattr(schedule, "create_on_demand_task", _create)
        monkeypatch.setattr(uac_free, "current_user_sid", lambda: "S-1-5-21-1-2-3-1001")
        assert uac_free.enable() is True
        program, arguments = uac_free.task_action()
        assert created["task_name"] == uac_free.TASK_NAME
        assert (created["program_path"], created["program_args"]) == (program, arguments)
        assert created["working_dir"] == os.getcwd()
        assert created["sddl"] == uac_free.task_sddl("S-1-5-21-1-2-3-1001")

    def test_enable_requires_worker_program(self, tmp_path, fake_task, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "March7th Launcher.exe"))
        monkeypatch.setattr(schedule, "create_on_demand_task", lambda **kwargs: pytest.fail("不应注册"))
        assert uac_free.enable() is False

    def test_disable_deletes_task(self, workdir, fake_task, monkeypatch):
        fake_task["info"] = _info_for_this_install()
        deleted = []

        def _delete(name):
            deleted.append(name)
            fake_task["info"] = None

        monkeypatch.setattr(schedule, "delete_task", _delete)
        assert uac_free.disable() is True
        assert deleted == [uac_free.TASK_NAME]

    def test_sddl_lets_user_read_and_run_only(self):
        sddl = uac_free.task_sddl("S-1-5-21-1-2-3-1001")
        assert sddl.startswith("D:P")
        assert "(A;;FRFX;;;S-1-5-21-1-2-3-1001)" in sddl
        assert "(A;;FA;;;SY)" in sddl and "(A;;FA;;;BA)" in sddl


class _FakeComError(Exception):
    def __init__(self, hresult, strerror, excepinfo=None):
        super().__init__(hresult, strerror, excepinfo, None)
        self.hresult = hresult
        self.strerror = strerror
        self.excepinfo = excepinfo


class TestDescribeError:
    def test_uses_excepinfo_scode_and_text(self):
        error = _FakeComError(-2147352567, "发生意外。", (0, None, "任务被禁用。", None, 0, -2147216602))
        assert uac_free.describe_error(error) == "任务被禁用。（0x80041326）"

    def test_looks_up_text_when_excepinfo_has_none(self, monkeypatch):
        monkeypatch.setattr(uac_free, "_system_message", lambda code: "拒绝访问。")
        error = _FakeComError(-2147352567, "发生意外。", (0, None, None, None, 0, -2147024891))
        assert uac_free.describe_error(error) == "拒绝访问。（0x80070005）"

    def test_plain_exception(self):
        assert uac_free.describe_error(OSError("服务不可用")) == "服务不可用"


class TestLaunch:
    def test_runs_task_with_args_and_waits_for_record(self, workdir, monkeypatch):
        run_id = "20261101-120000-abcd"
        calls = []

        def _run(name, params):
            calls.append((name, params))
            _write_record(run_id)  # 管理员进程启动后先写运行记录

        monkeypatch.setattr(schedule, "run_task", _run)
        process = uac_free.launch(["--workflow-name", "我的 流程", "--run-id", run_id], run_id, timeout=2)
        assert calls == [(uac_free.TASK_NAME, f'--workflow-name "我的 流程" --run-id {run_id}')]
        assert process.pid == os.getpid()
        assert process.poll(0) is None  # 进程仍在、记录为运行中

    def test_trigger_failure(self, workdir, monkeypatch):
        def _run(name, params):
            raise _FakeComError(-2147352567, "发生意外。", (0, None, "任务被禁用。", None, 0, -2147216602))

        monkeypatch.setattr(schedule, "run_task", _run)
        with pytest.raises(uac_free.LaunchError) as excinfo:
            uac_free.launch(["daily"], "20261101-120000-abcd", timeout=1)
        assert "任务被禁用。（0x80041326）" in str(excinfo.value)

    def test_timeout_reports_last_result(self, workdir, monkeypatch):
        monkeypatch.setattr(schedule, "run_task", lambda name, params: None)
        monkeypatch.setattr(schedule, "get_task_info", lambda name: {"last_result": -2147024894})
        with pytest.raises(uac_free.LaunchError) as excinfo:
            uac_free.launch(["daily"], "20261101-120000-abcd", timeout=0.3, poll_interval=0.05)
        assert "0.3 秒内任务没有开始运行" in str(excinfo.value)
        assert "0x80070002" in str(excinfo.value)


class TestTaskRun:
    def test_poll_returns_record_exit_code(self, workdir):
        run_id = "20261101-120000-abcd"
        _write_record(run_id)
        process = uac_free.TaskRun(runs.load_run(run_id))
        assert process.poll(0.05) is None
        _write_record(run_id, status=runs.STATUS_FAILED, exit_code=4)
        assert process.poll(0) == 4

    def test_dead_worker_counts_as_failure(self, workdir):
        run_id = "20261101-120000-abcd"
        _write_record(run_id, pid=999999999, pid_create_time=None)
        assert uac_free.TaskRun(runs.load_run(run_id)).poll(0) == runs.EXIT_FAILED
