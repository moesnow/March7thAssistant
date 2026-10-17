from copy import deepcopy
import ctypes
import re
import shlex
import subprocess
import sys

from PySide6.QtCore import QDateTime, QTime


def task_trigger_mode(task) -> str:
    mode = str((task or {}).get('trigger_mode', 'time')).strip().lower()
    return 'chain' if mode == 'chain' else 'time'


def parse_schedule_time(value) -> QTime | None:
    try:
        scheduled_time = QTime(*map(int, value.split(':')))
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None
    return scheduled_time if scheduled_time.isValid() else None


def milliseconds_to_next_minute(now: QDateTime) -> int:
    current_time = now.time()
    return 60000 - current_time.second() * 1000 - current_time.msec()


def scheduled_task_slot(task, now: QDateTime) -> int | None:
    """只匹配当前分钟内已经到达的计划点，不回看前一分钟。"""
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
    if str(payload['program']).strip().lower() == 'workflow':
        payload['workflow_name'] = task.get('workflow_name', '')
        if task.get('workflow_step_path') not in (None, ''):
            payload['workflow_step_path'] = task.get('workflow_step_path')
    return payload


def find_scheduled_task(task, tasks) -> int:
    task_id = task.get('id')
    if task_id:
        for index, candidate in enumerate(tasks):
            if candidate.get('id') == task_id:
                return index
    for index, candidate in enumerate(tasks):
        if candidate is task:
            return index
    fields = ('name', 'time', 'program', 'args')
    for index, candidate in enumerate(tasks):
        if all(candidate.get(field) == task.get(field) for field in fields):
            return index
    return -1


def scheduled_task_chain(task, tasks) -> list:
    start_index = find_scheduled_task(task, tasks)
    if start_index < 0:
        return []
    chain = []
    for candidate in tasks[start_index + 1:]:
        if task_trigger_mode(candidate) != 'chain':
            break
        if candidate.get('enabled', True):
            metadata = deepcopy(candidate)
            chain.append((metadata, scheduled_task_payload(metadata)))
    return chain


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
