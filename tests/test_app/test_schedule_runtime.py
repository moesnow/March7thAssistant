from copy import deepcopy
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from PySide6.QtCore import QDateTime, QPoint, QProcess, QTime, QTimer, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout
from qfluentwidgets import ScrollArea

from app.content import run_controller
from app.content.run_controller import RunController


@pytest.fixture
def schedule_runtime(qtbot, monkeypatch, tmp_path):
    interface = RunController.__new__(RunController)
    from PySide6.QtCore import QObject
    QObject.__init__(interface)
    interface._remote = interface._finish_skipped = False
    interface._account_arg = None
    interface._onReadyRead = Mock()
    interface.process = None
    interface._external_task_active = False
    interface._pause_state = 'running'
    interface._schedule_timer = None
    interface._schedule_running = False
    interface._last_triggered_ts = {}
    interface._pending_task_meta = None
    interface._active_task_chain = []
    interface._suppress_chain_continuation_once = False
    interface._pending_start_task_after_stop = None
    interface._timeout_timer = None
    interface._pending_post_action = None
    interface._pending_post_action_timer = None
    interface._stopped_abnormally = False
    interface._user_initiated_stop = False
    interface._suppress_process_error = False
    interface.appendLog = Mock()
    interface._resetPauseRuntime = Mock()
    interface._hideLogOverlay = Mock()
    interface._perform_post_action = Mock()
    interface.statusLabel = Mock()
    interface.scheduleStatusLabel = Mock()
    interface.manageScheduleButton = Mock()
    interface.stopButton = Mock()
    interface.pauseButton = Mock()
    interface._syncPauseUi = Mock()
    interface.clear_log = Mock()
    interface.logs = []
    interface.appendLog.side_effect = interface.logs.append
    settings = {'scheduled_tasks': []}
    config_path = tmp_path / 'config.yaml'
    config_path.write_text('control_backend: local\n', encoding='utf-8')
    monkeypatch.setattr(run_controller.cfg, 'config_path', str(config_path))
    monkeypatch.setattr(run_controller.cfg, 'get_value', lambda key, default=None: deepcopy(settings.get(key, default)))
    monkeypatch.setattr(run_controller.cfg, 'set_value', Mock())
    monkeypatch.setattr(run_controller.notif, 'notify', Mock())
    monkeypatch.setattr('utils.temporary_graphics.recover_temporary_graphics', Mock())

    def start_task(payload, **kwargs):
        interface.process = SimpleNamespace(state=lambda: QProcess.Running)

    interface.startTask = Mock(side_effect=start_task)
    interface.settings = settings
    yield interface
    interface._schedule_running = False
    if interface._schedule_timer:
        interface._schedule_timer.stop()
    if interface._timeout_timer:
        interface._timeout_timer.stop()
    if interface._pending_post_action_timer:
        interface._pending_post_action_timer.stop()


@pytest.fixture
def schedule_clock(monkeypatch):
    clock = SimpleNamespace(now=QDateTime.fromString('2026-10-17T04:00:10', 'yyyy-MM-ddTHH:mm:ss'))
    monkeypatch.setattr(run_controller, 'QDateTime', SimpleNamespace(currentDateTime=lambda: clock.now))
    monkeypatch.setattr(QTime, 'currentTime', lambda: clock.now.time())
    return clock


def scheduled_task(task_id='root', **overrides):
    task = {'id': task_id, 'name': task_id, 'time': '04:00', 'program': 'self', 'args': 'daily'}
    task.update(overrides)
    return task


def test_chain_uses_enabled_contiguous_children(schedule_runtime):
    root = scheduled_task()
    tasks = [root, scheduled_task('disabled', trigger_mode='chain', enabled=False),
             scheduled_task('child', trigger_mode='chain'), scheduled_task('other'),
             scheduled_task('unrelated', trigger_mode='chain')]
    assert schedule_runtime.runScheduledTask(root, tasks=tasks)
    assert [metadata['id'] for metadata, payload in schedule_runtime._active_task_chain] == ['child']


def test_manual_run_in_trigger_window_is_not_repeated(schedule_runtime, schedule_clock):
    root = scheduled_task()
    schedule_runtime.settings['scheduled_tasks'] = [root]
    schedule_runtime.runScheduledTask(root, tasks=[root], manual=True)
    schedule_runtime.process = None
    schedule_clock.now = schedule_clock.now.addSecs(30)
    schedule_runtime._checkScheduledTime()
    assert schedule_runtime.startTask.call_count == 1


@pytest.mark.parametrize('time_text', ['25:00', '04:90', 'invalid', None])
def test_invalid_schedule_time_is_not_triggered(schedule_runtime, time_text, monkeypatch):
    schedule_runtime.settings['scheduled_tasks'] = [scheduled_task(time=time_text)]
    schedule_runtime._checkScheduledTime()
    schedule_runtime.startTask.assert_not_called()


@pytest.mark.parametrize('conflict_mode', ['skip', 'stop'])
def test_conflict_policy_is_preserved(schedule_runtime, monkeypatch, conflict_mode):
    schedule_runtime.settings.update(scheduled_tasks=[scheduled_task()], scheduled_on_conflict=conflict_mode)
    schedule_runtime.process = SimpleNamespace(state=lambda: QProcess.Running)
    schedule_runtime.stopTask = Mock()
    now = QDateTime.fromString('2026-10-17T04:00:10', 'yyyy-MM-ddTHH:mm:ss')
    monkeypatch.setattr(run_controller, 'QDateTime', SimpleNamespace(currentDateTime=lambda: now))
    monkeypatch.setattr(QTime, 'currentTime', lambda: now.time())
    schedule_runtime._checkScheduledTime()
    schedule_runtime.startTask.assert_not_called()
    assert schedule_runtime.stopTask.called == (conflict_mode == 'stop')


@pytest.mark.parametrize('running', [False, True])
def test_second_plan_of_the_same_minute_is_logged_once(schedule_runtime, schedule_clock, running):
    schedule_runtime.settings.update(scheduled_on_conflict='stop', scheduled_tasks=[
        scheduled_task('off', enabled=False), scheduled_task('first'), scheduled_task('second', time='04:00:05'),
        scheduled_task('child', trigger_mode='chain'), scheduled_task('later', time='05:00')])
    schedule_runtime.stopTask = Mock()
    if running:
        schedule_runtime.process = SimpleNamespace(state=lambda: QProcess.Running)
    schedule_runtime._checkScheduledTime()
    schedule_runtime._checkScheduledTime()
    assert schedule_runtime.startTask.call_count == (not running) and schedule_runtime.stopTask.call_count == running
    assert [line for line in schedule_runtime.logs if '时间相同' in line] == ['计划「second」和「first」时间相同，没有启动\n']
    if running:
        assert schedule_runtime._pending_start_task_after_stop[0]['id'] == 'first'


def test_unsupported_timed_task_cannot_stop_active_task(schedule_runtime, schedule_clock):
    blocked = scheduled_task(args='currencywars', kill_processes=['game.exe'], post_action='Shutdown')
    old = scheduled_task('old')
    schedule_runtime.settings.update(control_backend='adb', scheduled_tasks=[blocked], scheduled_on_conflict='stop')
    schedule_runtime.process = SimpleNamespace(state=lambda: QProcess.Running)
    schedule_runtime._pending_task_meta = old
    schedule_runtime.stopTask = Mock()

    schedule_runtime._checkScheduledTime()
    schedule_runtime._checkScheduledTime()

    schedule_runtime.startTask.assert_not_called()
    schedule_runtime.stopTask.assert_not_called()
    assert schedule_runtime._pending_task_meta is old
    assert schedule_runtime._pending_start_task_after_stop is None
    assert schedule_runtime.settings['scheduled_tasks'] == [blocked]
    assert sum('当前后端不支持，未执行' in line for line in schedule_runtime.logs) == 1


def test_desktop_twin_update_schedule_cannot_stop_active_task(schedule_runtime, schedule_clock, monkeypatch):
    from utils.tasks import supported_tasks

    monkeypatch.setenv('MARCH7TH_DESKTOP_TWIN', '1')
    blocked = scheduled_task(args='app_update', kill_processes=['game.exe'])
    schedule_runtime.settings.update(scheduled_tasks=[blocked], scheduled_on_conflict='stop')
    schedule_runtime.process = SimpleNamespace(state=lambda: QProcess.Running)
    schedule_runtime.stopTask = Mock()

    schedule_runtime._checkScheduledTime()

    schedule_runtime.stopTask.assert_not_called()
    schedule_runtime.startTask.assert_not_called()
    assert schedule_runtime._pending_start_task_after_stop is None
    assert 'app_update' not in supported_tasks(run_controller.cfg)
    assert any('当前后端不支持，未执行' in line for line in schedule_runtime.logs)


@pytest.mark.parametrize('file_contents, message', [
    ('control_backend: adb\n', '当前后端不支持，未执行'),
    ('[\n', '配置加载失败'),
])
def test_time_conflict_checks_disk_before_stopping_active_task(schedule_runtime, schedule_clock, file_contents, message):
    from pathlib import Path

    scheduled = scheduled_task(args='currencywars')
    schedule_runtime.settings.update(control_backend='local', scheduled_tasks=[scheduled], scheduled_on_conflict='stop')
    schedule_runtime.process = SimpleNamespace(state=lambda: QProcess.Running)
    schedule_runtime.stopTask = Mock()
    # 另一进程先改了 YAML，主窗口的文件监听仍在等待重载。
    path = Path(run_controller.cfg.config_path)
    path.write_text(file_contents, encoding='utf-8')

    schedule_runtime._checkScheduledTime()

    schedule_runtime.startTask.assert_not_called()
    schedule_runtime.stopTask.assert_not_called()
    run_controller.cfg.set_value.assert_not_called()
    assert schedule_runtime.settings['control_backend'] == 'local'
    assert schedule_runtime._pending_start_task_after_stop is None
    assert path.read_text(encoding='utf-8') == file_contents
    assert any(message in line for line in schedule_runtime.logs)


@pytest.mark.parametrize('file_contents, overrides', [
    ('ui_profile: touch_720\n', {'MARCH7TH_CLOUD_GAME_ENABLE': 'true'}),
    ('control_backend: adb\n', {'MARCH7TH_DESKTOP_TWIN': '1', 'MARCH7TH_CLOUD_GAME_ENABLE': 'true'}),
])
def test_time_conflict_disk_snapshot_honors_environment(schedule_runtime, schedule_clock, monkeypatch,
                                                         file_contents, overrides):
    from pathlib import Path

    scheduled = scheduled_task(args='currencywars')
    schedule_runtime.settings.update(scheduled_tasks=[scheduled], scheduled_on_conflict='stop')
    schedule_runtime.process = SimpleNamespace(state=lambda: QProcess.Running)
    schedule_runtime.stopTask = Mock()
    Path(run_controller.cfg.config_path).write_text(file_contents, encoding='utf-8')
    for name, value in overrides.items():
        monkeypatch.setenv(name, value)

    schedule_runtime._checkScheduledTime()

    schedule_runtime.stopTask.assert_called_once_with(user_initiated=False)
    assert schedule_runtime._pending_start_task_after_stop is not None


@pytest.mark.parametrize('program, args', [('self', 'currencywars'), ('workflow', '示例流程')])
def test_unsupported_manual_schedule_is_reported_and_retained(schedule_runtime, program, args):
    blocked = scheduled_task(program=program, args=args, kill_processes=['game.exe'], post_action='Shutdown')
    schedule_runtime.settings.update(control_backend='adb', scheduled_tasks=[blocked])

    assert not schedule_runtime.runScheduledTask(blocked, manual=True)

    schedule_runtime.startTask.assert_not_called()
    assert schedule_runtime._pending_task_meta is None
    assert schedule_runtime._active_task_chain == []
    assert schedule_runtime._pending_post_action_timer is None
    assert schedule_runtime.settings['scheduled_tasks'] == [blocked]
    assert any('当前后端不支持，未执行' in line for line in schedule_runtime.logs)


def test_run_now_keyboard_reports_unsupported_schedule(schedule_runtime, qtbot, monkeypatch):
    from app.content.run_models import ScheduleModel
    from app.run.schedule import SchedulePage
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.runController = schedule_runtime
    blocked = scheduled_task(args="currencywars")
    schedule_runtime.settings.update(control_backend="adb", scheduled_tasks=[blocked])
    model = ScheduleModel(parent)
    page = SchedulePage(model, parent)
    outcomes = []
    page.runClicked.connect(lambda rid: outcomes.append(model.run_now(rid)))
    qtbot.keyClick(page.rows[0][0].runButton, Qt.Key.Key_Space)
    assert len(outcomes) == 1 and not outcomes[0].ok
    assert any("当前后端不支持" in text for text in schedule_runtime.logs)
    assert model._tasks() == [blocked]
    schedule_runtime.startTask.assert_not_called()


def test_direct_unsupported_task_cannot_replace_active_task(schedule_runtime):
    schedule_runtime.settings['control_backend'] = 'adb'
    active = SimpleNamespace(state=lambda: QProcess.Running)
    schedule_runtime.process = active
    schedule_runtime.stopTask = Mock()
    started = Mock()
    schedule_runtime.taskStarted.connect(started)

    RunController.startTask(schedule_runtime, 'currencywars')

    schedule_runtime.stopTask.assert_not_called()
    started.assert_not_called()
    assert schedule_runtime.process is active
    assert any('当前后端不支持，未执行' in line for line in schedule_runtime.logs)


@pytest.mark.parametrize('continue_on_failure', [True, False])
def test_unsupported_chain_child_respects_failure_policy(schedule_runtime, monkeypatch, continue_on_failure):
    root = scheduled_task(post_action='Shutdown')
    blocked = scheduled_task('blocked', trigger_mode='chain', args='currencywars',
                             kill_processes=['game.exe'], post_action='Shutdown')
    next_task = scheduled_task('next', trigger_mode='chain')
    tasks = [root, blocked, next_task]
    schedule_runtime.settings.update(control_backend='adb', scheduled_tasks=tasks,
                                     scheduled_chain_continue_on_failure=continue_on_failure)
    kill = Mock()
    monkeypatch.setattr(run_controller.sp, 'run', kill)
    completed = Mock()
    schedule_runtime.taskSequenceFinished.connect(completed)
    assert schedule_runtime.runScheduledTask(root)
    schedule_runtime.process = None

    schedule_runtime._onProcessFinished(0, QProcess.NormalExit)
    if continue_on_failure:
        schedule_runtime.process = None
        schedule_runtime._onProcessFinished(0, QProcess.NormalExit)

    expected = ['root', 'next'] if continue_on_failure else ['root']
    assert [call.args[0]['id'] for call in schedule_runtime.startTask.call_args_list] == expected
    completed.assert_called_once_with(1)
    kill.assert_not_called()
    assert schedule_runtime._pending_post_action_timer is None
    assert schedule_runtime.settings['scheduled_tasks'] == tasks
    assert any('当前后端不支持，未执行（blocked）' in line for line in schedule_runtime.logs)


def test_delayed_replacement_rechecks_backend_before_dispatch(schedule_runtime, schedule_clock):
    pending = scheduled_task(args='currencywars', kill_processes=['game.exe'], post_action='Shutdown')
    schedule_runtime.settings.update(scheduled_tasks=[pending], scheduled_on_conflict='stop')
    schedule_runtime.process = SimpleNamespace(state=lambda: QProcess.Running)
    schedule_runtime.stopTask = Mock()
    schedule_runtime._checkScheduledTime()
    schedule_runtime.stopTask.assert_called_once_with(user_initiated=False)
    assert schedule_runtime._pending_start_task_after_stop is not None

    schedule_runtime.settings['control_backend'] = 'adb'
    schedule_runtime.process = None
    schedule_runtime._onProcessFinished(1, QProcess.NormalExit)

    schedule_runtime.startTask.assert_not_called()
    assert schedule_runtime._pending_start_task_after_stop is None
    assert schedule_runtime._pending_task_meta is None
    assert schedule_runtime._pending_post_action_timer is None
    assert any('当前后端不支持，未执行' in line for line in schedule_runtime.logs)


@pytest.mark.parametrize('program', ['self', 'workflow'])
@pytest.mark.parametrize('reason, status', [
    ('unsupported_backend', 'blocked'),
    ('invalid_game_connection', 'blocked'),
    ('task_failure', 'failed'),
])
def test_scheduled_cli_completion_uses_run_record(schedule_runtime, qtbot, monkeypatch, tmp_path, program, reason, status):
    monkeypatch.chdir(tmp_path)
    from utils import runs
    record_dir = tmp_path / 'userdata' / 'logs' / 'runs'
    monkeypatch.setattr(runs, 'runs_dir', lambda: str(record_dir))
    monkeypatch.setattr(run_controller, 'is_user_admin', lambda: True)
    monkeypatch.setattr(schedule_runtime, '_injectPauseControlEnv', Mock())
    (tmp_path / 'main.py').write_text(
        'import json, sys\n'
        'from pathlib import Path\n'
        'run_id = sys.argv[sys.argv.index("--run-id") + 1]\n'
        f'runs = Path({str(record_dir)!r})\n'
        'runs.mkdir(parents=True)\n'
        f'data = {{"status": {status!r}, "reason": {reason!r}, "error": "child report"}}\n'
        '(runs / (run_id + ".json")).write_text(json.dumps(data), encoding="utf-8")\n'
        'sys.exit(1)\n', encoding='utf-8',
    )
    kill = Mock()
    monkeypatch.setattr(run_controller.sp, 'run', kill)
    schedule_runtime.startTask.side_effect = lambda task: RunController.startTask(schedule_runtime, task)
    root = scheduled_task(program=program, kill_processes=['game.exe'], post_action='Shutdown')

    assert schedule_runtime.runScheduledTask(root)
    qtbot.waitUntil(lambda: schedule_runtime.process is None)

    assert schedule_runtime._pending_task_meta is None
    assert kill.called == (status == 'failed')
    assert bool(schedule_runtime._pending_post_action_timer) == (status == 'failed')
    assert any('child report' in line for line in schedule_runtime.logs) == (status == 'blocked')
    message = '未执行' if status == 'blocked' else '任务已停止'
    assert schedule_runtime._task_status == ('blocked' if status == 'blocked' else 'stopped')


@pytest.mark.parametrize("manual", [False, True])
def test_schedule_origin_reaches_worker_without_changing_elevation(schedule_runtime, monkeypatch, manual):
    monkeypatch.setattr(run_controller, 'is_user_admin', lambda: False)
    task = scheduled_task()
    assert schedule_runtime.runScheduledTask(task, [task], manual=manual)
    args = ['daily']
    schedule_runtime._linkScheduledRun(SimpleNamespace(), args)
    assert ('--scheduled' in args) == (not manual)
    assert ('--run-id' in args) == (sys.platform != 'win32')


@pytest.mark.skipif(sys.platform != "win32", reason="验证 Windows 未提权工作进程的参数")
def test_scheduled_run_id_does_not_bypass_windows_elevation(schedule_runtime, monkeypatch):
    monkeypatch.setattr(run_controller, 'is_user_admin', lambda: False)
    schedule_runtime._pending_task_meta = scheduled_task()
    arguments = ['daily']
    process = SimpleNamespace()

    schedule_runtime._linkScheduledRun(process, arguments)

    assert arguments == ['daily']
    assert not hasattr(process, '_scheduled_run_id')


def test_switch_from_standalone_task_keeps_new_chain(schedule_runtime):
    root = scheduled_task()
    child = scheduled_task('child', trigger_mode='chain')
    schedule_runtime._pending_task_meta = scheduled_task('old')
    schedule_runtime._suppress_chain_continuation_once = True
    schedule_runtime._pending_start_task_after_stop = (root, root, [(child, child)])
    schedule_runtime._onProcessFinished(1, QProcess.CrashExit)
    schedule_runtime.process = None
    schedule_runtime._onProcessFinished(0, QProcess.NormalExit)
    assert [call.args[0]['id'] for call in schedule_runtime.startTask.call_args_list] == ['root', 'child']


def test_replacement_task_does_not_inherit_old_post_action(schedule_runtime):
    root = scheduled_task()
    schedule_runtime._pending_task_meta = scheduled_task('old', post_action='Shutdown')
    schedule_runtime._pending_start_task_after_stop = (root, root, [])
    schedule_runtime._onProcessFinished(1, QProcess.CrashExit)
    assert schedule_runtime.startTask.called
    assert schedule_runtime._pending_post_action_timer is None
    assert schedule_runtime._pending_post_action is None


@pytest.mark.parametrize('continue_on_failure', [True, False])
def test_failed_start_obeys_chain_failure_policy(schedule_runtime, continue_on_failure):
    child = scheduled_task('child', trigger_mode='chain')
    schedule_runtime.settings['scheduled_chain_continue_on_failure'] = continue_on_failure
    schedule_runtime._pending_task_meta = scheduled_task()
    schedule_runtime._active_task_chain = [(child, child)]
    schedule_runtime._onProcessError(QProcess.FailedToStart)
    assert schedule_runtime.startTask.called == continue_on_failure
    if not continue_on_failure:
        assert schedule_runtime._pending_task_meta is None
        assert schedule_runtime._active_task_chain == []


@pytest.mark.parametrize('user_stopped', [True, False])
def test_user_stop_does_not_continue_chain(schedule_runtime, user_stopped):
    child = scheduled_task('child', trigger_mode='chain')
    schedule_runtime._pending_task_meta = scheduled_task()
    schedule_runtime._active_task_chain = [(child, child)]
    schedule_runtime._user_initiated_stop = user_stopped
    schedule_runtime._onProcessFinished(1, QProcess.CrashExit)
    assert schedule_runtime.startTask.called == (not user_stopped)


@pytest.mark.parametrize('existing_path', [False, True])
def test_real_failed_process_start_continues_chain(schedule_runtime, tmp_path, qtbot, existing_path):
    child = scheduled_task('child', trigger_mode='chain')
    failed_program = tmp_path if existing_path else tmp_path / 'missing.exe'
    root = scheduled_task(program=str(failed_program), timeout=30)
    start_child = schedule_runtime.startTask.side_effect

    def launch(payload, **kwargs):
        if payload['id'] == 'child':
            start_child(payload)
        else:
            RunController.startTask(schedule_runtime, payload, **kwargs)

    schedule_runtime.startTask.side_effect = launch
    schedule_runtime.runScheduledTask(root, tasks=[root, child])
    qtbot.waitUntil(lambda: schedule_runtime.startTask.call_count == 2)
    assert schedule_runtime._pending_task_meta['id'] == 'child'
    assert schedule_runtime._timeout_timer is None


def test_starting_new_task_cancels_pending_system_action(schedule_runtime, tmp_path):
    schedule_runtime._schedulePostAction('Shutdown')
    timer = schedule_runtime._pending_post_action_timer
    RunController.startTask(schedule_runtime, scheduled_task(program=str(tmp_path / 'missing.exe')))
    assert schedule_runtime._pending_post_action_timer is None
    assert not timer.isActive()
    schedule_runtime._perform_post_action.assert_not_called()


def test_failed_start_cleans_timeout_and_notifies_completion(schedule_runtime):
    timer = QTimer(schedule_runtime)
    timer.start(30000)
    schedule_runtime._timeout_timer = timer
    schedule_runtime._pending_task_meta = scheduled_task()
    completed = Mock()
    schedule_runtime.taskFinished.connect(completed)
    schedule_runtime._onProcessError(QProcess.FailedToStart)
    assert schedule_runtime._timeout_timer is None
    assert not timer.isActive()
    completed.assert_called_once_with(-1)


def test_old_process_events_do_not_change_new_task(schedule_runtime):
    old_process = QProcess(schedule_runtime)
    schedule_runtime.process = QProcess(schedule_runtime)
    metadata = scheduled_task('new')
    schedule_runtime._pending_task_meta = metadata
    schedule_runtime._onProcessError(QProcess.FailedToStart, old_process)
    schedule_runtime._onProcessFinished(0, QProcess.NormalExit, old_process)
    assert schedule_runtime._pending_task_meta is metadata
    schedule_runtime.startTask.assert_not_called()


def test_canceled_post_action_ignores_queued_timeout(schedule_runtime):
    schedule_runtime._schedulePostAction('Shutdown')
    timer = schedule_runtime._pending_post_action_timer
    schedule_runtime._cancelPendingPostAction()
    timer.timeout.emit()
    schedule_runtime._perform_post_action.assert_not_called()


def test_poll_reads_task_list_once(schedule_runtime, schedule_clock, monkeypatch):
    schedule_runtime.settings['scheduled_tasks'] = [scheduled_task()]
    get_value = Mock(wraps=run_controller.cfg.get_value)
    monkeypatch.setattr(run_controller.cfg, 'get_value', get_value)
    schedule_runtime._checkScheduledTime()
    task_list_reads = [call for call in get_value.call_args_list if call.args[0] == 'scheduled_tasks']
    assert len(task_list_reads) == 1


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows 外部程序参数')
def test_external_launch_preserves_windows_argument_paths(schedule_runtime, monkeypatch):
    class RecordingProcess(QProcess):
        def start(self, program, arguments):
            self.arguments = arguments

    monkeypatch.setattr(run_controller, 'QProcess', RecordingProcess)
    RunController.startTask(schedule_runtime, scheduled_task(program=sys.executable, args=r'--config C:\Users\demo\config.yaml'))
    assert schedule_runtime.process.arguments == ['--config', r'C:\Users\demo\config.yaml']


def test_scheduler_waits_until_next_minute(schedule_runtime, schedule_clock):
    schedule_runtime._startScheduleTimer()
    timer = schedule_runtime._schedule_timer
    assert timer.isSingleShot()
    assert timer.timerType() == Qt.TimerType.PreciseTimer
    assert timer.interval() == 50000
    schedule_runtime.startTask.assert_not_called()


@pytest.mark.parametrize('restart_time', ['04:00:20', '04:00:00', '04:00:59'])
def test_restart_after_update_does_not_repeat_startup_minute(schedule_runtime, schedule_clock, restart_time):
    schedule_clock.now = QDateTime.fromString(f'2026-10-17T{restart_time}', 'yyyy-MM-ddTHH:mm:ss')
    schedule_runtime.settings['scheduled_tasks'] = [scheduled_task(args='app_update')]
    schedule_runtime._startScheduleTimer()
    schedule_clock.now = QDateTime.fromString('2026-10-17T04:01:00', 'yyyy-MM-ddTHH:mm:ss')
    schedule_runtime._onScheduleTimerTimeout()
    schedule_runtime.startTask.assert_not_called()
    schedule_clock.now = schedule_clock.now.addDays(1).addSecs(-60)
    schedule_runtime._onScheduleTimerTimeout()
    schedule_runtime.startTask.assert_called_once()


def test_running_before_deadline_triggers_once_on_minute_change(schedule_runtime, schedule_clock):
    schedule_clock.now = QDateTime.fromString('2026-10-17T03:59:42.300', 'yyyy-MM-ddTHH:mm:ss.zzz')
    schedule_runtime.settings['scheduled_tasks'] = [scheduled_task()]
    schedule_runtime._startScheduleTimer()
    assert schedule_runtime._schedule_timer.interval() == 17700
    schedule_clock.now = schedule_clock.now.addMSecs(17700)
    schedule_runtime._onScheduleTimerTimeout()
    schedule_runtime.startTask.assert_called_once()
    assert schedule_runtime._schedule_timer.interval() == 60000
    schedule_runtime._onScheduleTimerTimeout()
    schedule_runtime.startTask.assert_called_once()


def test_real_qtimer_dispatches_at_minute_change(schedule_runtime, schedule_clock, qtbot):
    schedule_clock.now = QDateTime.fromString('2026-10-17T03:59:59.999', 'yyyy-MM-ddTHH:mm:ss.zzz')
    schedule_runtime.settings['scheduled_tasks'] = [scheduled_task()]
    schedule_runtime._startScheduleTimer()
    schedule_clock.now = schedule_clock.now.addMSecs(1)
    qtbot.waitUntil(lambda: schedule_runtime.startTask.called)
    schedule_runtime.startTask.assert_called_once()


def test_timer_realigns_after_processing_delay(schedule_runtime, schedule_clock):
    schedule_runtime._startScheduleTimer()
    schedule_clock.now = schedule_clock.now.addSecs(50)

    def process_tasks(now):
        schedule_clock.now = now.addMSecs(2500)

    schedule_runtime._checkScheduledTime = Mock(side_effect=process_tasks)
    schedule_runtime._onScheduleTimerTimeout()
    assert schedule_runtime._schedule_timer.interval() == 57500


def test_timer_rechecks_clock_before_dispatch(schedule_runtime, schedule_clock):
    schedule_runtime.settings['scheduled_tasks'] = [scheduled_task()]
    schedule_runtime._startScheduleTimer()
    schedule_clock.now = schedule_clock.now.addSecs(20)
    schedule_runtime._onScheduleTimerTimeout()
    schedule_runtime.startTask.assert_not_called()
    assert schedule_runtime._schedule_timer.interval() == 30000


def test_timer_is_rearmed_after_check_failure(schedule_runtime, schedule_clock):
    schedule_runtime._startScheduleTimer()
    schedule_clock.now = schedule_clock.now.addSecs(50)
    schedule_runtime._checkScheduledTime = Mock(side_effect=RuntimeError('invalid schedule'))
    schedule_runtime._onScheduleTimerTimeout()
    assert schedule_runtime._schedule_timer.isActive()
    assert schedule_runtime._schedule_timer.interval() == 60000
    assert any('invalid schedule' in message for message in schedule_runtime.logs)


def test_disabled_scheduler_does_not_rearm_timer(schedule_runtime, schedule_clock):
    schedule_runtime._startScheduleTimer()
    schedule_runtime._schedule_running = False
    schedule_runtime._schedule_timer.stop()
    schedule_runtime._onScheduleTimerTimeout()
    assert not schedule_runtime._schedule_timer.isActive()
    schedule_runtime.startTask.assert_not_called()


def test_weekday_limits_automatic_trigger_but_not_manual_run(schedule_runtime, schedule_clock):
    root = scheduled_task(weekdays=[1])
    schedule_runtime.settings['scheduled_tasks'] = [root]
    schedule_runtime._checkScheduledTime()
    schedule_runtime.startTask.assert_not_called()
    assert schedule_runtime.runScheduledTask(root, tasks=[root], manual=True)
    schedule_runtime.startTask.assert_called_once()


def test_chain_children_do_not_apply_independent_weekday_filters(schedule_runtime, schedule_clock):
    root = scheduled_task(weekdays=[6])
    child = scheduled_task('child', trigger_mode='chain', weekdays=[1])
    schedule_runtime.settings['scheduled_tasks'] = [root, child]
    schedule_runtime._checkScheduledTime()
    schedule_runtime._onProcessFinished(0, QProcess.NormalExit)
    assert [call.args[0]['id'] for call in schedule_runtime.startTask.call_args_list] == ['root', 'child']


def test_status_label_shows_next_execution_date_for_selected_weekday(schedule_runtime, schedule_clock):
    schedule_runtime.settings['scheduled_tasks'] = [
        scheduled_task('monday', weekdays=[1]),
        scheduled_task('sunday', weekdays=[7], time='10:00'),
    ]
    from app.content.run_models import ScheduleModel
    parent = QWidget()
    parent.runController = schedule_runtime
    model = ScheduleModel(parent)
    model.now = lambda: schedule_clock.now.toPython()
    text = model.next_text()
    assert '明天 10:00' in text


@pytest.mark.parametrize('overlay_enabled', [False, True])
@pytest.mark.skipif(sys.platform != "win32", reason="游戏内日志开关仅在 Windows 可用")
def test_log_toolbar_fits_minimum_window_without_wrapping(schedule_runtime, schedule_clock, qtbot, overlay_enabled):
    schedule_runtime.settings['scheduled_tasks'] = [scheduled_task(weekdays=[7])]
    schedule_runtime._overlay_enabled = overlay_enabled
    from app.run_interface import RunInterface
    from module.overview.run_data import RunView
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.runController = schedule_runtime
    schedule_runtime.view = lambda: RunView()
    schedule_runtime.log_entries = lambda: []
    page = RunInterface(parent)
    page.resize(888, 592)
    page.show()
    label = page.nextLabel
    assert label.mapTo(page, QPoint(label.width(), 0)).x() <= page.width()
    assert not label.wordWrap() and "\n" not in label.text()
    assert page.segment.items["schedule"].text().endswith("1")
    card = page.currentPage.card
    assert card.overlayLabel.text() == run_controller.tr("在游戏内显示日志")
    assert card.overlaySwitch.isChecked() == overlay_enabled
    schedule_runtime.set_overlay(not overlay_enabled)
    page.currentPage.refresh()
    assert card.overlaySwitch.isChecked() != overlay_enabled
