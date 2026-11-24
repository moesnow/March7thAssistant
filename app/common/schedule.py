from copy import deepcopy
import ctypes
import re
import shlex
import subprocess
import sys

from PySide6.QtCore import QDateTime, QTime

from module.overview.schedule import (find_scheduled_task, following_tasks, next_occurrence,
                                      schedule_time, task_trigger_mode, task_weekdays,
                                      schedule_weekday_labels, format_task_weekdays)


def parse_schedule_time(value) -> QTime | None:
    clock = schedule_time(value)
    return QTime(clock.hour, clock.minute, clock.second, clock.microsecond // 1000) if clock else None


def milliseconds_to_next_minute(now: QDateTime) -> int:
    current_time = now.time()
    return 60000 - current_time.second() * 1000 - current_time.msec()


def scheduled_task_slot(task, now: QDateTime) -> int | None:
    """只匹配当前分钟内已经到达的计划点，不回看前一分钟。"""
    if now.date().dayOfWeek() not in task_weekdays(task):
        return None
    scheduled_time = parse_schedule_time(task.get('time', '00:00'))
    if scheduled_time is None:
        return None
    current_time = now.time()
    if (scheduled_time.hour(), scheduled_time.minute()) != (current_time.hour(), current_time.minute()):
        return None
    scheduled_at = QDateTime(now)
    scheduled_at.setTime(scheduled_time)
    if scheduled_at <= now:
        return scheduled_at.toSecsSinceEpoch()
    return None


def next_scheduled_datetime(task, now: QDateTime) -> QDateTime | None:
    def candidate(offset, clock):
        day = now.date().addDays(offset)
        at = QDateTime(now)
        at.setDate(day)
        at.setTime(QTime(clock.hour, clock.minute, clock.second, clock.microsecond // 1000))
        return day.dayOfWeek(), at if at.isValid() else None

    return next_occurrence(task, now, candidate)


def task_timeout_seconds(task) -> int:
    try:
        return int(task.get('timeout', 0) or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def scheduled_task_payload(task) -> dict:
    payload = {
        'program': task.get('program', 'self'),
        'args': task.get('args', ''),
        'timeout': task_timeout_seconds(task),
        'name': task.get('name', ''),
        'notify': bool(task.get('notify', False)),
        'post_action': task.get('post_action', 'None'),
        'id': task.get('id'),
        'trigger_mode': task_trigger_mode(task),
    }
    if str(payload['program']).strip().lower() == 'self':
        payload['account'] = task.get('account') or 'all'
    if str(payload['program']).strip().lower() == 'workflow':
        payload['workflow_name'] = task.get('workflow_name', '')
        if task.get('workflow_step_path') not in (None, ''):
            payload['workflow_step_path'] = task.get('workflow_step_path')
    return payload


def task_launch_block_reason(command_or_task, config, *, check_saved_config=False) -> str | None:
    """内置任务和流程共用 CLI 的支持范围，外部程序自行决定能否运行。"""
    from module.config.platform import InvalidGameConnection, get_control_backend, get_ui_profile, read_game_connection_config
    from module.localization import tr
    from utils.tasks import TASK_NAMES, UNSUPPORTED_TASK, task_is_supported

    if isinstance(command_or_task, dict):
        program = str(command_or_task.get('program', '')).strip().lower()
        if program == 'self':
            task_id = str(command_or_task.get('args', '') or '')
            name = command_or_task.get('name') or tr(TASK_NAMES.get(task_id, task_id))
        elif program == 'workflow':
            task_id = 'workflow'
            name = command_or_task.get('name') or command_or_task.get('workflow_name') or command_or_task.get('args')
        else:
            return None
    else:
        task_id = str(command_or_task)
        name = tr(TASK_NAMES.get(task_id, task_id))

    name = name or tr('未命名')
    try:
        if check_saved_config:
            config = read_game_connection_config(config)
        get_control_backend(config)
        get_ui_profile(config)
        if task_is_supported(task_id, config):
            return None
    except InvalidGameConnection as error:
        return f"{tr('未执行')}（{name}）：{error}"
    return f"{tr(UNSUPPORTED_TASK)}（{name}）"


def scheduled_task_chain(task, tasks) -> list:
    return [(deepcopy(candidate), scheduled_task_payload(candidate)) for candidate in following_tasks(task, tasks)]


def split_task_arguments(arguments: str, *, posix=False) -> list[str]:
    if not arguments:
        return []
    if posix or sys.platform != 'win32':
        return shlex.split(arguments)
    from ctypes import wintypes

    def normalize_quotes(match):
        return subprocess.list2cmdline([match.group(1)]) if match.group(1) is not None else match.group(0)

    arguments = re.sub(r'"(?:\\.|[^"\\])*"|\'([^\']*)\'', normalize_quotes, arguments)
    parse_command = ctypes.WinDLL('shell32', use_last_error=True).CommandLineToArgvW
    parse_command.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    parse_command.restype = ctypes.POINTER(wintypes.LPWSTR)
    free_arguments = ctypes.WinDLL('kernel32', use_last_error=True).LocalFree
    free_arguments.argtypes = [wintypes.HLOCAL]
    free_arguments.restype = wintypes.HLOCAL
    argument_count = ctypes.c_int()
    argument_values = parse_command('scheduled-task ' + arguments, ctypes.byref(argument_count))
    if not argument_values:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return [argument_values[index] for index in range(1, argument_count.value)]
    finally:
        free_arguments(ctypes.cast(argument_values, wintypes.HLOCAL))
