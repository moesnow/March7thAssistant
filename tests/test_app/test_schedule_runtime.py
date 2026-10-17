from copy import deepcopy
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

if sys.platform != 'win32':
    pytest.skip('GUI 测试仅在 Windows 平台运行', allow_module_level=True)

from PySide6.QtCore import QDateTime, QPoint, QProcess, QTime, QTimer, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout
from qfluentwidgets import ScrollArea

from app import log_interface
from app.log_interface import LogInterface


@pytest.fixture
def schedule_runtime(qtbot, monkeypatch):
    interface = LogInterface.__new__(LogInterface)
    ScrollArea.__init__(interface)
    qtbot.addWidget(interface)
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
    interface.clearLog = Mock()
    interface.logs = []
    interface.appendLog.side_effect = interface.logs.append
    settings = {'scheduled_tasks': []}
    monkeypatch.setattr(log_interface.cfg, 'get_value', lambda key, default=None: deepcopy(settings.get(key, default)))
    monkeypatch.setattr(log_interface.cfg, 'set_value', Mock())
    monkeypatch.setattr(log_interface.notif, 'notify', Mock())

    def start_task(payload):
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
    monkeypatch.setattr(log_interface, 'QDateTime', SimpleNamespace(currentDateTime=lambda: clock.now))
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
    monkeypatch.setattr(schedule_runtime, '_updateScheduleStatusLabel', Mock())
    schedule_runtime._checkScheduledTime()
    schedule_runtime.startTask.assert_not_called()


@pytest.mark.parametrize('conflict_mode', ['skip', 'stop'])
def test_conflict_policy_is_preserved(schedule_runtime, monkeypatch, conflict_mode):
    schedule_runtime.settings.update(scheduled_tasks=[scheduled_task()], scheduled_on_conflict=conflict_mode)
    schedule_runtime.process = SimpleNamespace(state=lambda: QProcess.Running)
    schedule_runtime.stopTask = Mock()
    now = QDateTime.fromString('2026-10-17T04:00:10', 'yyyy-MM-ddTHH:mm:ss')
    monkeypatch.setattr(log_interface, 'QDateTime', SimpleNamespace(currentDateTime=lambda: now))
    monkeypatch.setattr(QTime, 'currentTime', lambda: now.time())
    schedule_runtime._checkScheduledTime()
    schedule_runtime.startTask.assert_not_called()
    assert schedule_runtime.stopTask.called == (conflict_mode == 'stop')


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

    def launch(payload):
        if payload['id'] == 'child':
            start_child(payload)
        else:
            LogInterface.startTask(schedule_runtime, payload)

    schedule_runtime.startTask.side_effect = launch
    schedule_runtime.runScheduledTask(root, tasks=[root, child])
    qtbot.waitUntil(lambda: schedule_runtime.startTask.call_count == 2)
    assert schedule_runtime._pending_task_meta['id'] == 'child'
    assert schedule_runtime._timeout_timer is None


def test_starting_new_task_cancels_pending_system_action(schedule_runtime, tmp_path):
    schedule_runtime._schedulePostAction('Shutdown')
    timer = schedule_runtime._pending_post_action_timer
    LogInterface.startTask(schedule_runtime, scheduled_task(program=str(tmp_path / 'missing.exe')))
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
    get_value = Mock(wraps=log_interface.cfg.get_value)
    monkeypatch.setattr(log_interface.cfg, 'get_value', get_value)
    schedule_runtime._checkScheduledTime()
    task_list_reads = [call for call in get_value.call_args_list if call.args[0] == 'scheduled_tasks']
    assert len(task_list_reads) == 1


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows 外部程序参数')
def test_external_launch_preserves_windows_argument_paths(schedule_runtime, monkeypatch):
    class RecordingProcess(QProcess):
        def start(self, program, arguments):
            self.arguments = arguments

    monkeypatch.setattr(log_interface, 'QProcess', RecordingProcess)
    LogInterface.startTask(schedule_runtime, scheduled_task(program=sys.executable, args=r'--config C:\Users\demo\config.yaml'))
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
    schedule_runtime._updateScheduleStatusLabel()
    text = schedule_runtime.scheduleStatusLabel.setText.call_args.args[0]
    assert '10-18' in text and '10:00' in text


@pytest.mark.parametrize('overlay_enabled', [False, True])
def test_log_toolbar_fits_minimum_window_without_wrapping(schedule_runtime, schedule_clock, qtbot, overlay_enabled):
    schedule_runtime.settings['scheduled_tasks'] = [scheduled_task(weekdays=[7])]
    schedule_runtime._overlay_enabled = overlay_enabled
    schedule_runtime._buffered_logs = ''
    schedule_runtime.scrollWidget = QWidget()
    schedule_runtime.vBoxLayout = QVBoxLayout(schedule_runtime.scrollWidget)
    schedule_runtime._LogInterface__initWidget()
    schedule_runtime.resize(888, 592)
    schedule_runtime.show()
    qtbot.waitUntil(lambda: schedule_runtime.buttonWidget.width() > 0)
    label = schedule_runtime.scheduleStatusLabel
    right_edge = label.mapTo(schedule_runtime.viewport(), QPoint(label.width(), 0)).x()
    assert right_edge <= schedule_runtime.viewport().width()
    assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
    assert not label.wordWrap() and '\n' not in label.text()
    assert schedule_runtime.logOverlayLabel.text() == log_interface.tr('在游戏内显示日志')
    assert schedule_runtime.logOverlaySwitch.text == (log_interface.tr('开') if overlay_enabled else log_interface.tr('关'))
    schedule_runtime._setLogOverlaySwitchValue(not overlay_enabled)
    assert schedule_runtime.logOverlaySwitch.text == (log_interface.tr('关') if overlay_enabled else log_interface.tr('开'))
    assert schedule_runtime.manageScheduleButton.text().endswith('(1)')
