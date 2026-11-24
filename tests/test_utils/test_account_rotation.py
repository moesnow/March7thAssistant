"""使用假子进程和故障注入测试轮流、通知和账号历史。"""

from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from module.accounts import messages, rotation, status
from module.accounts.files import write_yaml
from module.accounts.runtime import AccountError
from module.accounts.store import AccountStore
from module.overview.history import read_history
from utils import paths, runs
from utils.pause import write_command, _atomic_write_json

A, B = "100000789", "100000456"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_layout", paths.select(tmp_path, tmp_path))
    monkeypatch.delenv("MARCH7TH_CONTROL_FILE", raising=False)
    monkeypatch.delenv("MARCH7TH_CONFIG_READONLY", raising=False)
    monkeypatch.delenv("MARCH7TH_DESKTOP_TWIN", raising=False)
    monkeypatch.setattr(runs, "_current_session", None)
    s = AccountStore(role="ui")
    write_yaml(
        s.index_path,
        {
            "enabled": True,
            "current": A,
            "inherited": A,
            "accounts": [{"uid": A, "name": "虚构甲"}, {"uid": B, "name": "虚构乙"}],
        },
    )
    config = SimpleNamespace(
        control_backend="local",
        notify_merge=True,
        after_finish="None",
        get_value=lambda k: True,
        shared_value=lambda k, d=None: {"game_path": "example", "refresh_hour": 4}.get(k, d),
    )
    args = SimpleNamespace(task="main", workflow_name=None, scheduled=False, account_timeout=1)
    session = runs.RunSession.begin(task="main", capture=False)
    yield s, config, args, session
    session.finish(0)


@pytest.mark.parametrize(
    "outcomes,code",
    [
        (["success", "success"], 0),
        (["failed", "success"], 1),
        (["error", "success"], 1),
        (["timeout", "success"], 1),
        (["skipped", "success"], 1),
        (["failed", "failed"], 1),
        (["stopped", "success"], 6),
    ],
)
@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地客户端轮流运行")
def test_rotation_outcomes_and_cleanup(setup, outcomes, code):
    store, config, args, session = setup
    finish = Mock()
    live = []

    def child(parent, row, task, args):
        live.append(runs.load_run(parent.run_id)["rotation"]["index"])
        assert runs.read_active_run()["run_id"] == parent.run_id
        result = outcomes[len(live) - 1]
        if result == "error":
            raise OSError()
        return result, None

    assert rotation.rotate(session, config, args, store=store, run_child=child, finish=finish) == code
    assert len(live) == (1 if code == 6 else 2)
    assert finish.call_count == (0 if code == 6 else 1)
    rows = runs.load_run(session.run_id)["rotation"]["accounts"]
    assert rows[0]["status"] == ("failed" if outcomes[0] == "error" else outcomes[0])
    assert rows[-1]["status"] == ("stopped" if code == 6 else outcomes[-1])
    session.finish(code)
    assert not runs.read_active_run()


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地客户端轮流运行")
def test_record_failure_and_finalize_failure(setup, monkeypatch):
    store, config, args, session = setup

    def fail_save(path, data):
        if path.endswith(session.run_id + ".json"):
            raise PermissionError()
        return _atomic_write_json(path, data)

    monkeypatch.setattr(runs, "_atomic_write_json", fail_save)
    child = Mock(return_value=("success", None))
    assert (
        rotation.rotate(session, config, args, store=store, run_child=child, finish=Mock(side_effect=OSError))
        == 1
    )
    assert child.call_count == 2 and session._pending["reason"] == "rotation_finish_failed"


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地客户端轮流运行")
def test_lock_busy_and_task_restrictions(setup):
    store, config, args, session = setup
    lock = runs.RunSession.begin(task="daily", capture=False)
    lock.acquire_lock()
    try:
        child = Mock()
        assert rotation.rotate(session, config, args, store=store, run_child=child, finish=Mock()) == 4
        child.assert_not_called()
        for task in ("workflow", "currencywarsloop", "divergenttemp", "notify", "game_update"):
            args.task = task
            with pytest.raises(AccountError) as err:
                rotation.rotate(session, config, args, store=store)
            assert err.value.exit_code == 2
    finally:
        lock.finish(0)


@pytest.mark.parametrize(
    "outcome,expected",
    [
        ("success", "success"),
        ("crash", "failed"),
        ("timeout", "timeout"),
        ("skip", "skipped"),
        ("stop", "stopped"),
        ("pause_stop", "stopped"),
        ("long_pause", "success"),
        ("missing", "failed"),
    ],
)
def test_child_deadline_and_control(setup, outcome, expected):
    store, config, args, session = setup
    session.record["rotation"] = {"merge": True}
    child = runs.new_run_id()
    control = session.record["control_file"]
    tick = [0.0]
    job = Mock(name="fake_job")
    job.name = "fake"
    proc = Mock()
    proc.stdout = StringIO("虚构任务日志\n")
    proc.returncode = None
    proc.pid = 0x7FFFFFFC  # 不存在的进程

    def poll():
        if outcome in ("success", "crash", "missing") and tick[0]:
            proc.returncode = 1 if outcome == "crash" else 0
        if outcome == "long_pause" and tick[0] > 5:
            proc.returncode = 0
        return proc.returncode

    proc.poll.side_effect = poll
    proc.kill.side_effect = lambda: setattr(proc, "returncode", 1)

    def sleep(delay):
        tick[0] += delay
        if outcome == "long_pause":
            write_command(control, "pause" if tick[0] < 5 else "resume")
        if outcome == "skip":
            _atomic_write_json(control + ".skip", {"child_run_id": child})
        if outcome in ("stop", "pause_stop"):
            write_command(control, "stop")

    if outcome == "pause_stop":
        write_command(control, "pause")
    if outcome in ("success", "long_pause"):
        _atomic_write_json(runs.run_file(child, ".json"), {"exit_code": 0, "status": "success"})
    result, reason = rotation._run_child(
        session,
        {"uid": A, "run_id": child},
        "daily",
        args,
        clock=lambda: tick[0],
        sleep=sleep,
        spawn=Mock(return_value=proc),
        job_factory=lambda _: job,
    )
    assert result == expected
    if outcome in ("timeout", "stop", "skip"):
        proc.kill.assert_called_once()
    if outcome == "pause_stop":
        job.close.assert_not_called()


def test_notification_prefix_spool_and_failure_level(setup, monkeypatch):
    store, config, args, session = setup
    from module.notification.notification import Notification

    n = object.__new__(Notification)
    Notification.__init__(n, "测试标题")
    target = Mock(supports_image=False)
    n.set_notifier("example", target)
    session.record["account"] = {"uid": A, "name": "虚构甲"}
    n.notify("第一条")
    assert target.send.call_args.args[:2] == ("测试标题", "【虚构甲】第一条")
    session.record["parent_run_id"] = runs.new_run_id()
    monkeypatch.setenv("M7A_ROTATION_MERGE", "1")
    n.start_batch()
    n.notify("已产生的消息")
    target.send.assert_called_once()
    sink = Mock()
    messages.send_summary(
        {"accounts": [{"name": "虚构甲", "status": "failed", "run_id": session.run_id}]}, True, notifier=sink
    )
    assert sink.notify.call_args.kwargs["level"] == "error"
    assert "已产生的消息" in sink.notify.call_args.kwargs["content"]
    session.record.pop("parent_run_id")
    session.record["account"] = None
    n.flush_batch()
    n.notify("原文")
    assert target.send.call_args.args[:2] == ("测试标题", "原文")


def test_history_isolation_game_days_and_retention(setup, monkeypatch):
    store, config, args, session = setup
    store.update(B, refresh_hour=0)
    now = datetime(2026, 11, 24, 5)

    def write(rid, when, **fields):
        data = dict(
            task="main", status="success", started_at=when.isoformat(), ended_at=when.isoformat(), run_id=rid
        )
        data.update(fields)
        _atomic_write_json(runs.run_file(rid, ".json"), data)

    old = "20261124-020000-0001"
    new = "20261124-030000-0002"
    write(old, now - timedelta(hours=3))
    write(new, now - timedelta(hours=2), account={"uid": B}, status="failed", error="测试失败")
    config.bound_account = A
    config.account_inherited = A
    config.refresh_hour = 4
    assert read_history(now, config).last.id == old
    rows = status.list_accounts(config, store, now=now, logged_uid=A)
    assert rows[0]["week"][-2]["run_id"] == old and rows[0]["week"][-1]["status"] == "none"
    assert rows[1]["week"][-1]["run_id"] == new and "测试失败" in rows[1]["status_text"]
    child = "20261124-033000-0003"
    parent = "20261120-010000-0000"
    write(child, now, parent_run_id=parent)
    write(parent, now, rotation={"accounts": [{"run_id": child}]})
    session.finish(0)
    session_path = Path(runs.run_file(session.run_id, ".json"))
    session_path.unlink(missing_ok=True)
    runs.cleanup_old_runs(1)
    assert runs.load_run(child) and runs.load_run(parent)
    assert not runs.load_run(old)


def test_detail_sidecar_and_skip_target(setup):
    from utils.cli_entry import control_command
    from utils.pause import _read_json

    store, config, args, session = setup
    one = runs.new_run_id()
    session.update_record(rotation={"index": 0, "accounts": [{"status": "running", "run_id": one}]})
    assert control_command(session.run_id, "skip", out=StringIO()) == 0
    assert _read_json(session.record["control_file"] + ".skip") == {"child_run_id": one}
    runs.publish_progress(current_step="power")
    runs.publish_detail(runs.DETAIL_TEXT["instance"], name="虚构副本", index=1, total=3)
    assert runs.load_run(session.run_id)["detail"]["args"]["total"] == 3
    runs.publish_progress(current_step="echo")
    assert runs.load_run(session.run_id)["detail"] is None
    runs.set_after_finish(session.run_id, "None")
    assert runs.effective_after_finish("Shutdown") == "None"
    with pytest.raises(ValueError):
        runs.set_after_finish(session.run_id, "invalid")
    assert not Path(paths.config_path()).exists()


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows Job Object")
def test_parent_grant_requires_real_parent_and_job(setup, monkeypatch):
    import win32api
    import win32job

    store, config, args, session = setup
    parent = runs.new_run_id()
    monkeypatch.setenv(rotation.PARENT_ENV, parent)
    monkeypatch.setenv(rotation.JOB_ENV, "Local\\example")
    monkeypatch.setattr(rotation, "_started_by", lambda pid: pid == 24)

    def awaiting(run_id):
        _atomic_write_json(runs.run_file(parent, ".json"),
                           {"run_id": parent, "rotation": {"index": 0, "accounts": [{"uid": A, "run_id": run_id}]}})

    awaiting(session.run_id)
    monkeypatch.setattr(runs, "read_active_run", lambda: {"run_id": parent, "pid": 25, "rotation": True})
    with pytest.raises(AccountError):
        rotation.join_parent(session)
    monkeypatch.setattr(runs, "read_active_run", lambda: {"run_id": parent, "pid": 24, "rotation": True})
    awaiting(runs.new_run_id())  # 父进程在等另一次子运行
    with pytest.raises(AccountError):
        rotation.join_parent(session)
    awaiting(session.run_id)
    job = Mock()
    monkeypatch.setattr(win32job, "OpenJobObject", lambda *args: job)
    monkeypatch.setattr(win32api, "GetCurrentProcess", lambda: "this process")
    assign = Mock()
    monkeypatch.setattr(win32job, "AssignProcessToJobObject", assign)
    assert rotation.join_parent(session)
    assign.assert_called_once_with(job, "this process")
    job.Close.assert_called_once()
    assert runs.load_run(session.run_id)["parent_run_id"] == parent


CHILD = """
import os, subprocess, sys, time
from module.accounts import rotation
from utils import runs

mode, run_id = sys.argv[1:]
session = runs.RunSession.begin(run_id=run_id, task="daily", capture=False)
code = 1
try:
    rotation.join_parent(session)
    code = 0
    if mode != "finish":
        game = subprocess.Popen([sys._base_executable, "-c", "import time; time.sleep(60)"])
        session.update_record(game=game.pid, me=os.getpid())
        while mode == "hang" or not os.path.exists(os.environ[rotation.CANCEL_ENV]):
            time.sleep(0.05)
        code = runs.EXIT_STOPPED
finally:
    session.finish(code)
raise SystemExit(code)
"""


def real_children(monkeypatch, tmp_path, mode):
    monkeypatch.setenv("M7A_DATA_DIR", str(tmp_path))
    monkeypatch.setenv(paths.SESSION_ENV, "")
    monkeypatch.setattr(rotation, "worker_command",
                        lambda command, run_id: [sys.executable, "-B", "-c", CHILD, mode, run_id])


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows Job Object")
def test_real_children_join_through_the_venv_launcher(setup, monkeypatch, tmp_path):
    """venv 的 python.exe 是启动器，子进程的上一级不是轮流父进程本身。"""
    store, config, args, session = setup
    real_children(monkeypatch, tmp_path, "finish")
    args.account_timeout = 60
    code = rotation.rotate(session, config, args, store=store, finish=Mock())
    rows = runs.load_run(session.run_id)["rotation"]["accounts"]
    assert [(row["status"], row["reason"]) for row in rows] == [("success", None)] * 2
    assert code == runs.EXIT_OK
    assert all(runs.load_run(row["run_id"])["parent_run_id"] == session.run_id for row in rows)


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows Job Object")
@pytest.mark.parametrize("mode", ["stop", "hang"])
def test_stopping_leaves_the_game_unless_the_child_hangs(setup, monkeypatch, tmp_path, mode):
    import threading
    import time

    import psutil

    store, config, args, session = setup
    real_children(monkeypatch, tmp_path, mode)
    monkeypatch.setattr(rotation, "GRACE", 1.5 if mode == "hang" else 20)
    args.account_timeout = 60
    row = {"uid": A, "run_id": runs.new_run_id()}
    session.update_record(rotation={"index": 0, "merge": False, "accounts": [row]})
    assert session.acquire_lock().status == runs.LOCK_ACQUIRED

    def started():
        return (runs.load_run(row["run_id"]) or {}).get("game")

    def stop():
        deadline = time.monotonic() + 30
        while not started() and time.monotonic() < deadline:
            time.sleep(0.05)
        write_command(session.record["control_file"], "stop")

    threading.Thread(target=stop, daemon=True).start()
    try:
        assert rotation._run_child(session, row, "daily", args) == ("stopped", "stopped")
        record = runs.load_run(row["run_id"])
        deadline = time.monotonic() + 5
        while psutil.pid_exists(record["me"]) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not psutil.pid_exists(record["me"])
        assert psutil.pid_exists(record["game"]) is (mode == "stop")
    finally:
        if pid := started():
            try:
                psutil.Process(pid).kill()
            except psutil.Error:
                pass


def test_stored_images_are_bounded_and_single_delivery(setup, monkeypatch):
    from io import BytesIO

    store, config, args, session = setup
    monkeypatch.setenv("M7A_ROTATION_MERGE", "1")
    session.record["parent_run_id"] = runs.new_run_id()
    n = Mock(image_enable=True)
    n._process_image.return_value = BytesIO(b"x" * (messages.IMAGE_BYTES + 1))
    assert messages.collect(n, session.record, "超大图片已略过", object(), "all")
    assert not messages._inbox(session.run_id)["images"]
    n._process_image.return_value = BytesIO(b"fake")
    for _ in range(7):
        messages.collect(n, session.record, "text", object(), "all")
    assert len(messages._inbox(session.run_id)["images"]) == messages.MAX_IMAGES


def test_diagnostics_and_backup_exclude_old_password(setup, tmp_path):
    from utils import data_backup
    import zipfile

    store, config, args, session = setup
    session.finish(0)
    secret = store.root / (A + ".acc")
    secret.write_text("fictional-old-password", encoding="utf-8")
    store.path(A, "state.yaml").parent.mkdir(exist_ok=True)
    write_yaml(store.path(A, "state.yaml"), {"login_status": "expired"})
    store.path(A, "secret.bin").write_bytes(b"fictional-encrypted")
    store.path(A, "login.reg").write_bytes(b"fictional-session-placeholder")
    backup = tmp_path / "backup.zip"
    data_backup.backup(backup)
    with zipfile.ZipFile(backup) as z:
        assert not any(p.endswith(".acc") for p in z.namelist())
        assert f"accounts/{A}/secret.bin" in z.namelist()
    report = tmp_path / "diagnostics.zip"
    Path(session.record["log_file"]).write_text("虚构甲 " + A + "\n", encoding="utf-8")
    data_backup.diagnostics(report)
    with zipfile.ZipFile(report) as z:
        assert not any(p.startswith("accounts/") for p in z.namelist())
        output = b"".join(z.read(p) for p in z.namelist())
        assert b"expired" in output and b"fictional" not in output and A.encode() not in output
        assert "虚构甲".encode() not in output


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地客户端轮流运行")
def test_joined_rotation_uses_two_isolated_plans_and_notices(setup, monkeypatch, tmp_path):
    from module.config.config import Config
    from module.accounts import runtime

    store, config, args, parent = setup
    cfg = object.__new__(Config)
    Config.__init__(
        cfg, "assets/config/version.txt", "assets/config/config.example.yaml", str(tmp_path / "config.yaml")
    )
    cfg.set_values({"control_backend": "local", "auto_update": True, "notify_merge": True})
    store.update(B, plan="independent")
    store.modify(B, "plan.yaml", lambda d: d.update(universe_count=17))
    monkeypatch.setattr(runtime, "server_for_path", lambda _: "cn")
    monkeypatch.setattr(runtime, "check_client", lambda *args, **kwargs: None)
    monkeypatch.setenv("M7A_ROTATION_MERGE", "1")
    seen = []

    def fake_child(session, row, task, args):
        # Each child gets its own Config, simulated client identity, and real storage/record semantics.
        child = runs.RunSession.begin(task=task, run_id=row["run_id"], capture=False)
        child.update_record(parent_run_id=session.run_id)
        monkeypatch.setattr(runtime, "gamereg_uid", lambda _: int(row["uid"]))
        separate = object.__new__(Config)
        Config.__init__(
            separate, "assets/config/version.txt", "assets/config/config.example.yaml", cfg.config_path
        )
        runtime.begin_account_run(separate, row["uid"], task, child)
        runtime.verify_ready(separate)
        seen.append((separate.last_run_timestamp, separate.universe_count))
        separate.save_timestamp("last_run_timestamp")
        messages.collect(Mock(), child.record, "虚构任务已完成", None, "all")
        child.finish(0)
        return "success", None

    sink = Mock()

    def finish(session, config, rotation):
        messages.send_summary(rotation, True, notifier=sink)

    assert rotation.rotate(parent, cfg, args, store=store, run_child=fake_child, finish=finish) == 0
    assert seen == [(0, cfg.universe_count), (0, 17)]
    assert all(store.read(uid, "state.yaml")["last_run_timestamp"] > 0 for uid in (A, B))
    assert cfg.last_run_timestamp == 0
    body = sink.notify.call_args.kwargs["content"]
    assert body.count("虚构任务已完成") == 2 and "虚构甲" in body and "虚构乙" in body


@pytest.mark.parametrize(
    "selector,task,enabled,expected_reason",
    [
        ("虚构乙", "daily", False, "account_unsupported"),
        pytest.param("不存在的虚构名称", "daily", True, "account_not_found",
                     marks=pytest.mark.skipif(sys.platform != "win32", reason="启用轮流后才检查账号身份")),
        pytest.param(B, "currencywarstemp", True, "account_mismatch",
                     marks=pytest.mark.skipif(sys.platform != "win32", reason="启用轮流后才检查账号身份")),
        ("all", "workflow", True, "account_unsupported"),
    ],
)
def test_cli_stops_before_game_imports(tmp_path, selector, task, enabled, expected_reason):
    import json
    import os
    import subprocess
    from utils.cli_entry import worker_args

    assert worker_args(["daily", "--account", selector], runs.new_run_id())[:3] == [
        "daily",
        "--account",
        selector,
    ]
    root = tmp_path / "profile"
    write_yaml(
        root / "config.yaml",
        {"auto_set_game_path_enable": False, "auto_update": True, "control_backend": "local"},
    )
    write_yaml(
        root / "accounts" / "accounts.yaml",
        {"enabled": enabled, "accounts": [{"uid": A, "name": "虚构甲"}, {"uid": B, "name": "虚构乙"}]},
    )
    worker = """
import runpy, sys
from utils import admin
from module.accounts import runtime
admin.is_user_admin = lambda: True
runtime.gamereg_uid = lambda *args: 100000789
runtime.server_for_path = lambda path: "cn"
runtime.running_clients = lambda: []
sys.argv = ["main.py", *sys.argv[1:]]
try:
    runpy.run_path("main.py", run_name="__main__")
finally:
    assert "module.ocr" not in sys.modules
"""
    args = ["--workflow-name", "虚构流程"] if task == "workflow" else [task]
    result = subprocess.run(
        [sys.executable, "-B", "-c", worker, *args, "--account", selector, "--non-interactive", "--json"],
        cwd=Path(__file__).resolve().parents[2],
        timeout=30,
        capture_output=True,
        encoding="utf-8",
        env={**os.environ, "M7A_DATA_DIR": str(root), "M7A_SESSION_LAYOUT": ""},
    )
    assert result.returncode == (1 if expected_reason == "account_mismatch" else 2), result.stderr
    record = json.loads(result.stdout.splitlines()[-1])
    assert record["reason"] == expected_reason and record["error"]
    assert not list((root / "accounts").glob("*/state.yaml"))


@pytest.mark.parametrize("audio", [True, False])
def test_round_tail_plays_one_sound_and_reports_reason(setup, monkeypatch, audio):
    store, config, args, session = setup
    config.get_value = lambda key, default=None: audio if key == "play_audio" else default
    sound = Mock()
    monkeypatch.setattr("tasks.game.play_finish_audio", sound)
    sink = Mock()
    original = messages.send_summary
    monkeypatch.setattr(messages, "send_summary", lambda data, merge: original(data, merge, notifier=sink))
    rotation.finalize(session, config, {"merge": True, "accounts": [
        {"name": "虚构甲", "status": "failed", "reason": "account_login_expired"}]})
    assert sound.call_count == int(audio)
    assert "虚构甲 · 失败（登录过期）" in sink.notify.call_args.kwargs["content"]


def test_account_error_notification_uses_selected_name_and_child_inbox(setup, monkeypatch):
    from module.notification.notification import Notification
    store, config, args, session = setup
    n = object.__new__(Notification)
    Notification.__init__(n, "虚构测试")
    target = Mock(supports_image=False)
    n.set_notifier("example", target)
    error = AccountError("account_no_login", "没有检测到登录")
    messages.notify_account_error(session, B, error, notifier=n)
    assert target.send.call_args.args[1] == "【虚构乙】没有检测到登录"
    monkeypatch.setenv("M7A_ROTATION_MERGE", "1")
    session.update_record(parent_run_id=runs.new_run_id(), account={"uid": B, "name": "虚构乙"})
    messages.notify_account_error(session, B, error, notifier=n)
    assert messages._inbox(session.run_id)["error"] and target.send.call_count == 1


def test_colors_persist_when_renaming_and_reordering(setup):
    store, _, _, _ = setup
    assert [r["color"] for r in store.index()["accounts"]] == [0, 1]
    store.reorder([B, A])
    store.update(A, name="虚构新名")
    assert [r["color"] for r in store.index()["accounts"]] == [1, 0]


def test_cli_default_per_account_timeout_is_eight_hours(tmp_path):
    import os
    import subprocess
    root = tmp_path / "sample"
    write_yaml(root / "config.yaml", {"auto_set_game_path_enable": False, "control_backend": "local"})
    worker = """
import runpy, sys
from utils import admin
from module.accounts import rotation
admin.is_user_admin = lambda: True
def observe(session, config, args):
    assert args.account == "all" and args.account_timeout == 8 * 60 * 60
    print("verified-rotation-timeout")
    return 0
rotation.rotate = observe
sys.argv = ["main.py", "main", "--account", "all", "--non-interactive"]
runpy.run_path("main.py", run_name="__main__")
"""
    result = subprocess.run([sys.executable, "-B", "-c", worker], capture_output=True, text=True, encoding="utf-8",
                            timeout=30, cwd=Path(__file__).resolve().parents[2],
                            env={**os.environ, "M7A_DATA_DIR": str(root), "M7A_SESSION_LAYOUT": ""})
    assert result.returncode == 0 and "verified-rotation-timeout" in result.stdout
