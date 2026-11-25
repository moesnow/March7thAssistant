"""使用临时账号、真实运行文件和无游戏的 Qt 主线程检查三个模型。"""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import errno
import os
import sys

import pytest
from PySide6.QtWidgets import QWidget

from module.overview.run_log import LogParser, read_log
from module.accounts.files import write_yaml
from utils import paths, runs
from utils.pause import _atomic_write_json, _read_json

A, B = "100000789", "100000456"


def test_console_and_history_share_incremental_parser(tmp_path):
    text = ("\x1b[36m2026-11-22 14:03:04,105 | DEBUG | 识别\x1b[0m\n+-------+\n| 账 号 |\n+-------+\n"
            "14:04:05 | CRITICAL | 失败\nTraceback\n    stack\n14:05:06 | INFO | 已恢复\n"
            "==========\n---- 任务 ----\n第三方输出\n命令: worker.exe\n最后半行")
    parser = LogParser()
    rules = parser.feed("=====\n-----\n")
    assert all(e.kind == "title" and not e.important for e in rules) and len(rules) == 2
    entries = []
    for char in text:
        entries.extend(parser.feed(char))
    entries.extend(parser.feed("", final=True))
    assert [(e.kind, e.level, e.important) for e in entries[:5]] == [
        ("line", "debug", False), ("title", "info", True), ("line", "error", True),
        ("output", "error", True), ("output", "error", True)]
    assert entries[0].time == "14:03:04" and entries[1].text == "账 号"
    assert [e.important for e in entries[-5:]] == [False, True, True, False, True]
    log = tmp_path / "sample.log"
    log.write_text(text, encoding="utf-8")
    assert read_log(log) == entries
    log.write_text("".join(f"output {i}\n" for i in range(8000)), encoding="utf-8")
    result = read_log(log)
    assert len(result) == 5000 and result[0].text == "output 3000" and result[-1].text == "output 7999"


@pytest.fixture
def host(tmp_path, monkeypatch, qtbot, page_config):
    from app.content.account_model import AccountModel
    from app.content.run_controller import RunController
    from app.content.run_models import RunHistory, ScheduleModel
    from module.accounts.store import AccountStore
    from utils.registry import gameaccount

    monkeypatch.setattr(paths, "_layout", paths.select(tmp_path, tmp_path))
    cfg = page_config("control_backend: local\nauto_set_game_path_enable: false\nafter_finish: Shutdown\n")
    monkeypatch.setattr(cfg, "_account_layer", None)
    monkeypatch.setattr(gameaccount, "gamereg_uid", lambda *_: int(A))
    monkeypatch.setattr("app.content.account_model.running_clients", lambda: [])
    monkeypatch.setattr("module.accounts.runtime.current_login", lambda *_: int(A))
    store = AccountStore(role="ui")
    write_yaml(store.index_path, {"enabled": True, "current": A, "accounts": [
        {"name": "虚构甲", "uid": A}, {"name": "虚构乙", "uid": B, "plan": "independent"}]})
    for uid in (A, B):
        store.path(uid, "login.reg").parent.mkdir(exist_ok=True)
        store.path(uid, "login.reg").write_text("展示占位文件", encoding="utf-8")
    for method in ("_RunController__initShortcut", "_startScheduleTimer", "_initOverlayMonitor"):
        monkeypatch.setattr(RunController, method, lambda self: None)
    window = QWidget()
    qtbot.addWidget(window)
    window._onStartTask = Mock()
    window.accountModel = AccountModel(window, store=store, config=cfg)
    window.runController = RunController(window)
    window.runHistory = RunHistory(window)
    window.scheduleModel = ScheduleModel(window)
    yield window
    window.runController.cleanup()
    cfg.bind_account(None)


def save(rid, **fields):
    record = dict(run_id=rid, task="main", status="running", pid=os.getpid(),
                  pid_create_time=runs.process_create_time(os.getpid()), started_at=datetime.now().isoformat(),
                  control_file=runs.run_file(rid, ".control"), trigger="scheduled")
    record.update(fields)
    _atomic_write_json(runs.run_file(rid, ".json"), record)
    return record


def test_parent_child_history_control_tail_and_stale_pid(host, monkeypatch):
    c, h = host.runController, host.runHistory
    root, child = runs.new_run_id(), runs.new_run_id()
    rotation = {"index": 0, "accounts": [
        {"uid": A, "name": "虚构甲", "status": "running", "run_id": child}, {"uid": B, "name": "虚构乙", "status": "waiting"}]}
    record = save(root, rotation=rotation)
    save(child, account={"uid": A, "name": "虚构甲"}, parent_run_id=root, plan=["power", "daily"], current_step="power",
         detail={"msgid": "第 {index} 次", "args": {"index": 2}})
    log = Path(runs.run_file(root, ".log"))
    log.write_text("12:34:56 | INFO | 启动\n半", encoding="utf-8")
    h.refresh()
    v = c.view()
    assert v.account_index == 1 and v.can_pause and v.can_stop and v.can_skip
    assert v.steps[0].note == "第 2 次" and v.steps[1].status == "pending"
    assert c.skip_account() and _read_json(record["control_file"] + ".skip")["child_run_id"] == child
    assert c.toggle_pause() and _read_json(record["control_file"])["command"] == "pause"
    assert c.set_finish_skipped(True) and runs.effective_after_finish("Shutdown", root) == "None"
    assert c.set_finish_skipped(False) and runs.effective_after_finish("None", root) == "Shutdown"
    with log.open("a", encoding="utf-8") as stream:
        stream.write("行\n")
    h.refresh()
    assert [e.text for e in c.log_entries()] == ["启动", "半行"]
    assert h.days()[0][1][0].id == root and h.days(A)[0][1][0].parent_id == root
    assert h.entry(child).account.uid == A and not h.retry_text(h.entry(child))
    c.setDesktopTwinHosting(True)
    assert not c.view().can_stop and not c.skip_account() and not c._control_remote("stop")
    c.setDesktopTwinHosting(False)
    assert c.stop() and _read_json(record["control_file"])["command"] == "stop"
    h.refresh()
    assert c.view().state == "stopping" and not c.toggle_pause() and not c.skip_account()
    with monkeypatch.context() as restricted:
        restricted.setattr(runs, "process_create_time", lambda _: None)
        assert c._live_record() is None
    record["pid_create_time"] -= 600
    _atomic_write_json(runs.run_file(root, ".json"), record)
    assert not c._control_remote("resume") and not c.skip_account()
    assert _read_json(record["control_file"])["command"] == "stop"


def test_history_filters_retry_account_and_caches_unchanged_records(host, monkeypatch):
    h = host.runHistory
    root, child = runs.new_run_id(), runs.new_run_id()
    save(root, status="failed", rotation={"accounts": [{"uid": B, "name": "虚构乙", "status": "failed",
         "reason": "account_login_expired", "run_id": child}]})
    save(child, status="failed", account={"uid": B, "name": "虚构乙"}, parent_run_id=root,
         steps=[{"id": "power", "status": "failed", "error": "副本失败"}])
    for i in range(298):
        save(f"20261120-010000-{i:04x}", status="success", task="daily")
    h.refresh()
    assert len(list(h.records())) == 300
    assert not h._active_timer.isActive() and "登录过期" in h.entry(root).reason
    entry = h.entry(child)
    if sys.platform == "win32":
        assert h.retry_text(entry) == "重试这一项" and h.retry(entry)
        host._onStartTask.assert_called_once_with({"program": "self", "args": "routine", "retry_step": "power", "account": B})
    else:
        assert not h.retry_text(entry) and not h.retry(entry)
        host._onStartTask.assert_not_called()
    spy = Mock(wraps=runs.load_run)
    monkeypatch.setattr(runs, "load_run", spy)
    h.refresh()
    spy.assert_not_called()


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地多账号生效")
def test_account_binding_state_only_refresh_and_snapshot_failures(host, qtbot, monkeypatch):
    m = host.accountModel
    changes = Mock()
    m.bindingChanged.connect(changes)
    assert m.set_current(B).ok and m.config.bound_account == B and m.editing().uid == B
    changes.reset_mock()
    m.store.modify(B, "state.yaml", lambda state: state.update(last_run_timestamp=123))
    m._files_changed()
    changes.assert_not_called()
    assert m.config.last_run_timestamp == 123
    m.store.modify(B, "plan.yaml", lambda plan: plan.update(power_enable=False))
    m._files_changed()
    changes.assert_called_once()
    assert not m.config.power_enable and m.card()[0] == 1
    from module.accounts.snapshots import SnapshotError
    monkeypatch.setattr("module.accounts.snapshots.switch_login", Mock(side_effect=SnapshotError("game_running", "游戏仍在运行")))
    with qtbot.waitSignal(m.operationFinished, timeout=3000) as result:
        assert m.prepare_login(B).ok
    assert not result.args[0].ok and "游戏" in result.args[0].text
    monkeypatch.setattr("app.content.account_model.running_clients", lambda: [object()])
    assert "下次运行" in m.switch_to(A).text and m.config.bound_account == A
    monkeypatch.setattr(host.runController, "isTaskRunning", lambda: True)
    assert not m.set_enabled(False).ok and not m.delete(A).ok and m.set_current(B).ok


@pytest.mark.skipif(sys.platform != "win32", reason="需要 Windows 本地多账号生效")
def test_schedule_account_parameters_order_and_per_account_timeout(host, monkeypatch):
    from app.content import run_controller as module
    from module.config import cfg
    c, model = host.runController, host.scheduleModel
    tasks = [{"id": "a", "program": "self", "args": "main", "time": "04:15", "name": "虚构计划", "timeout": 5400},
             {"id": "b", "program": "self", "args": "currencywarstemp", "account": B, "trigger_mode": "chain"}]
    cfg.set_value("scheduled_tasks", tasks)
    assert model.items()[0].account_text == "全部账号轮流" and "90" in model.items()[0].detail
    assert model.items()[1].account_text == "虚构乙" and len(model.week()) == 7
    assert c._account_for("main") == A and c._account_for(c._buildScheduledTaskPayload(tasks[1])) == B
    monkeypatch.setattr(module.QProcess, "start", Mock())
    monkeypatch.setattr(c, "_injectPauseControlEnv", Mock())
    timer = Mock()
    monkeypatch.setattr(c, "_armTaskTimeout", timer)
    c.startTask(c._buildScheduledTaskPayload(tasks[0]))
    args = module.QProcess.start.call_args.args[-1]
    assert args[args.index("--account")+1] == "all" and args[args.index("--account-timeout")+1] == "5400"
    assert timer.call_args.args[-1] == 0
    monkeypatch.setattr("app.schedule_dialog.AddEditScheduleDialog.exec", lambda self: True)
    model.duplicate("b", host)
    assert len(model.items()) == 3 and model.items()[2].id != "b" and model.items()[2].account_text == "虚构乙"
    model.move("b", -1)
    assert model.items()[0].id == "b"
    model.set_enabled("b", False)
    assert not model.items()[0].enabled
    model.remove("b")
    assert len(model.items()) == 2
    assert host.accountModel.set_enabled(False).ok
    assert model.items()[-1].account_problem
    assert not c.runScheduledTask(tasks[1], manual=True)


@pytest.mark.parametrize(("source", "mode", "order"), [
    ("a", None, ["a", "b", "c", "copy", "d"]), ("a", "chain", ["a", "b", "c", "copy", "d"]),
    ("b", None, ["a", "b", "copy", "c", "d"]), ("b", "time", ["a", "b", "c", "copy", "d"]),
    ("d", None, ["a", "b", "c", "d", "copy"]), ("gone", None, ["a", "b", "c", "d", "copy"]),
])
def test_copied_schedule_is_confirmed_first_and_never_cuts_a_chain(host, monkeypatch, source, mode, order):
    from PySide6.QtCore import QTime
    from app import schedule_dialog
    from module.config import cfg
    model = host.scheduleModel
    tasks = [{"id": "a", "name": "计划甲", "program": "self", "args": "main", "time": "04:10", "timeout": 90},
             {"id": "b", "name": "计划乙", "program": "self", "args": "fight", "trigger_mode": "chain"},
             {"id": "c", "name": "计划丙", "program": "self", "args": "divergent", "trigger_mode": "chain", "enabled": False},
             {"id": "d", "name": "计划丁", "program": "self", "args": "daily", "time": "05:00"}]
    cfg.set_value("scheduled_tasks", tasks)
    original = next((task for task in tasks if task["id"] == source), tasks[3])
    item_id = original["id"]
    Dialog = schedule_dialog.AddEditScheduleDialog
    accept, message = Mock(), Mock(return_value=Mock())
    monkeypatch.setattr(Dialog.__mro__[1], "accept", accept)
    monkeypatch.setattr(schedule_dialog, "MessageBox", message)
    titles = []

    def answer(dialog, change):
        titles.append((dialog.titleLabel.text(), dialog.name_edit.text()))
        change(dialog)
        dialog.accept()
        return accept.called

    # 取消，或按时计划没改时间就确认，都不会新增
    monkeypatch.setattr(Dialog, "exec", lambda dialog: False)
    model.duplicate(item_id, host)
    if original.get("trigger_mode") != "chain":
        monkeypatch.setattr(Dialog, "exec", lambda dialog: answer(dialog, lambda _: None))
        model.duplicate(item_id, host)
        assert original["name"] in message.call_args.args[1] and original["time"] in message.call_args.args[1]
    assert model._tasks() == tasks and not accept.called

    def change(dialog):
        dialog.time_picker.setTime(QTime(6, 30))
        if mode:
            dialog._set_trigger_mode(mode)
        if source == "gone":
            model.remove(item_id)
            tasks.remove(original)
            order.remove("d")
    monkeypatch.setattr(Dialog, "exec", lambda dialog: answer(dialog, change))
    model.duplicate(item_id, host)
    saved = model._tasks()
    assert ["copy" if task["id"] not in "abcd" else task["id"] for task in saved] == order
    copy = saved.pop(order.index("copy"))
    assert saved == tasks
    assert (copy["name"], copy["time"], copy["args"]) == (f"{original['name']}（副本）", "06:30", original["args"])
    assert copy["timeout"] == original.get("timeout", 0) and copy["enabled"]
    assert set(titles) == {("复制定时计划", copy["name"])}


@pytest.mark.parametrize("finished_in_wait", [False, True])
def test_quit_rechecks_owned_process_after_finished_signal(host, monkeypatch, finished_in_wait):
    from PySide6.QtCore import QProcess
    c = host.runController
    process = Mock()
    process.state.return_value = QProcess.Running
    process.processId.return_value = 123
    c.process = process
    stop = Mock()
    kill = Mock()
    monkeypatch.setattr(c, "stopTask", stop)
    monkeypatch.setattr(c, "_killProcessTree", kill)
    def wait(ms):
        if finished_in_wait:
            c.process = None
        return finished_in_wait
    process.waitForFinished.side_effect = wait
    c.stopOwnedTasksOnExit()
    stop.assert_called_once()
    assert kill.call_count == (0 if finished_in_wait else 1)
    if not finished_in_wait:
        kill.assert_called_with(123)
    c.process = None


def test_restore_shows_updated_run_and_all_buffered_log_lines(host, qtbot, monkeypatch):
    from dataclasses import replace
    from app.run_interface import RunInterface

    page = RunInterface(host)
    host.resize(1200, 640)
    page.resize(host.size())
    host.show()
    panel = page.currentPage.log
    panel.setFilter("all")
    host.showMinimized()
    qtbot.waitUntil(host.isMinimized)
    old = host.runController.view()
    monkeypatch.setattr(host.runController, "view", lambda: replace(old, countdown=87, finish_text="示例操作"))
    host.runController.changed.emit()
    for line in ("恢复前一行", "恢复前二行"):
        host.runController.appendLog(line + "\n")
    assert "恢复前二行" not in panel.view.toPlainText()
    host.showNormal()
    qtbot.waitUntil(lambda: "恢复前二行" in panel.view.toPlainText())
    assert panel.view.toPlainText().count("恢复前一行") == 1
    assert panel.view.toPlainText().count("恢复前二行") == 1
    assert "87" in page.currentPage.card.footLabel.text()


def test_restore_shows_latest_account_name(host, qtbot):
    from app.accounts_interface import AccountsInterface

    page = AccountsInterface(host)
    host.resize(1200, 640)
    page.resize(host.size())
    host.show()
    host.showMinimized()
    qtbot.waitUntil(host.isMinimized)
    host.accountModel.store.update(A, name="恢复后可见")
    host.accountModel.refresh()
    assert "恢复后可见" not in page.detail.header.nameLabel.text()
    host.showNormal()
    qtbot.waitUntil(lambda: page.detail.header.nameLabel.text() == "恢复后可见")


@pytest.mark.parametrize("ok", [True, False])
def test_account_background_feedback_reports_progress_then_result(host, qtbot, monkeypatch, ok):
    import threading
    from app import accounts_interface
    from module.overview.run_data import Outcome

    page = accounts_interface.AccountsInterface(host)
    model = host.accountModel
    calls = []
    for method in ("info", "success", "error"):
        monkeypatch.setattr(accounts_interface.InfoBar, method,
                            lambda title, text, *, kind=method, **kw: calls.append((kind, text)))
    release = threading.Event()
    def operation():
        assert release.wait(3)
        return Outcome(ok, "测试结果")
    try:
        with qtbot.waitSignal(model.operationFinished, timeout=4000):
            assert page._run("账号", model._background, operation)
            assert model.working() and calls == [("info", "正在处理账号操作")]
            release.set()
    finally:
        release.set()
    assert not model.working()
    assert calls == [("info", "正在处理账号操作"), ("success" if ok else "error", "测试结果")]


@pytest.mark.parametrize(("clock", "label"), [("09:30", "今天"), ("07:30", "明天")])
def test_next_schedule_names_game_calendar_day(host, monkeypatch, clock, label):
    model = host.scheduleModel
    monkeypatch.setattr(model, "now", lambda: datetime(2026, 11, 24, 8))
    monkeypatch.setattr(model, "_tasks", lambda: [{"id": "test", "time": clock, "name": "样例计划"}])
    assert model.next_text() == f"下次定时：{label} {clock} 样例计划"


@pytest.mark.parametrize("corruption", ["bad yaml: [", "accounts: []\\ncurrent: []"])
@pytest.mark.parametrize("failure", [PermissionError(), OSError(errno.EROFS, "read-only filesystem")])
def test_account_list_survives_external_damage_and_readonly_directory(host, monkeypatch, corruption, failure):
    model = host.accountModel
    model.store.index_path.write_text(corruption.replace("\\n", "\n"), encoding="utf-8")
    before = model.store.index_path.read_bytes()
    monkeypatch.setattr(model.store, "lock", Mock(side_effect=failure))
    model.refresh()
    assert not model.enabled() and {info.uid for info in model.accounts()} == {A, B}
    assert model.store.index_path.read_bytes() == before
    assert all(info.saved_at for info in model.accounts())


def test_account_list_keeps_other_rows_when_snapshot_date_is_unusable(host):
    model = host.accountModel
    model.store.modify(A, "state.yaml", lambda state: state.update(snapshot_saved_at="无法读取"))
    model.store.path(B, "login.reg").unlink()
    model.refresh()
    assert [(a.uid, a.saved_at) for a in model.accounts()] == [(A, None), (B, None)]


@pytest.mark.parametrize(("platform", "environment", "backend"), [
    ("darwin", {}, "local"), ("linux", {}, "local"),
    ("linux", {"MARCH7TH_DOCKER_STARTED": "1"}, "cloud"),
    ("linux", {"TERMUX_VERSION": "test"}, "adb"),
])
def test_unsupported_host_keeps_single_account_behavior(
        qtbot, monkeypatch, tmp_path, page_config, platform, environment, backend):
    from app import accounts_interface
    from app.content import account_model, run_controller
    from app.overview_model import OverviewModel
    from module.accounts import layers, runtime, status
    from module.accounts.store import AccountStore

    cfg = page_config(f"control_backend: {backend}\nauto_set_game_path_enable: false\n")
    monkeypatch.setattr(cfg, "_account_layer", None)
    monkeypatch.setattr(paths, "_layout", paths.select(tmp_path, tmp_path))
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    for module in (account_model, run_controller, layers, runtime):
        monkeypatch.setattr(module, "sys", SimpleNamespace(platform=platform))
    for method in ("_RunController__initShortcut", "_startScheduleTimer", "_initOverlayMonitor"):
        monkeypatch.setattr(run_controller.RunController, method, lambda self: None)
    monkeypatch.setattr(account_model.gameaccount, "gamereg_uid", Mock(side_effect=AssertionError))
    store = AccountStore()
    write_yaml(store.index_path, {"enabled": True, "current": A, "accounts": [{"uid": A}]})

    def files():
        return {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}

    before = files()
    window = QWidget()
    qtbot.addWidget(window)
    page = accounts_interface.AccountsInterface(window)
    model = window.accountModel
    assert model.readonly() and not model.active() and cfg.bound_account is None
    page.refresh()
    assert "Windows" in model.unsupported_reason() and not page.panel.notice.isHidden()
    assert status.cli_status(cfg)["effective"] is False
    window.runController = controller = run_controller.RunController(window)
    try:
        assert controller._account_for("main") is None and controller._log_overlay is None
        overview = OverviewModel(window, config=cfg)
        assert all(b.id != "start_all" for b in overview.snapshot.greeting.buttons)
        session = Mock()
        runtime.begin_account_run(cfg, None, "daily", session, store=store)
        session.acquire_lock.assert_not_called()
        with pytest.raises(runtime.AccountError) as exc:
            runtime.begin_account_run(cfg, A, "daily", session, store=store)
        assert exc.value.reason == "account_unsupported"
        assert before == files()
        store.index_path.unlink()
        model.refresh()
        page.refresh()
        assert page.stack.currentWidget() is page.empty and "Windows" in page.empty.textLabel.text()
        assert not page.empty.addButton.isEnabled()
    finally:
        controller.cleanup()
