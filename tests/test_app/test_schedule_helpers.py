import shlex
import subprocess
import sys

import pytest
from PySide6.QtCore import QDateTime

from app.common.schedule import (milliseconds_to_next_minute, scheduled_task_slot, split_task_arguments,
                                 task_weekdays, next_scheduled_datetime)


@pytest.mark.parametrize(('task', 'expected'), [
    ({}, (1, 2, 3, 4, 5, 6, 7)),
    ({'weekdays': None}, (1, 2, 3, 4, 5, 6, 7)),
    ({'weekdays': [5, 1, 3, 1]}, (1, 3, 5)),
    ({'weekdays': []}, ()),
    ({'weekdays': [0, 8, True, '2', 3]}, (3,)),
    ({'weekdays': '1,3,5'}, ()),
])
def test_weekday_selection_is_normalized_and_legacy_defaults_to_daily(task, expected):
    assert task_weekdays(task) == expected


@pytest.mark.parametrize(('current_time', 'weekdays', 'expected'), [
    ('2026-10-19T04:00:10', [1, 3, 5], True),
    ('2026-10-20T04:00:10', [1, 3, 5], False),
    ('2026-10-18T04:00:10', [6, 7], True),
    ('2026-10-18T04:00:10', [], False),
])
def test_automatic_trigger_respects_selected_weekdays(current_time, weekdays, expected):
    now = QDateTime.fromString(current_time, 'yyyy-MM-ddTHH:mm:ss')
    assert (scheduled_task_slot({'time': '04:00', 'weekdays': weekdays}, now) is not None) == expected


@pytest.mark.parametrize(('current_time', 'task_time', 'weekdays', 'expected_time'), [
    ('2026-10-17T04:00:10', '04:00', [1, 3, 5], '2026-10-19T04:00:00'),
    ('2026-10-19T04:00:00', '04:00', [1], '2026-10-26T04:00:00'),
    ('2026-10-18T03:59:59', '04:00', [6, 7], '2026-10-18T04:00:00'),
    ('2026-10-18T04:00:10', '04:00', [6, 7], '2026-10-24T04:00:00'),
    ('2026-10-16T23:59:59', '00:00', [6], '2026-10-17T00:00:00'),
    ('2026-10-17T04:00:10', '04:00', [], None),
])
def test_next_run_accounts_for_weekdays_and_week_boundaries(current_time, task_time, weekdays, expected_time):
    now = QDateTime.fromString(current_time, 'yyyy-MM-ddTHH:mm:ss')
    actual = next_scheduled_datetime({'time': task_time, 'weekdays': weekdays}, now)
    assert (actual.toString('yyyy-MM-ddTHH:mm:ss') if actual else None) == expected_time


@pytest.mark.parametrize(('current_time', 'task_time', 'expected_slot'), [
    ('2026-10-17T04:00:00', '04:00', '2026-10-17T04:00:00'),
    ('2026-10-17T04:00:59', '04:00', '2026-10-17T04:00:00'),
    ('2026-10-17T04:01:00', '04:00', None),
    ('2026-10-17T04:01:01', '04:00', None),
    ('2026-10-17T03:59:59', '04:00', None),
    ('2026-10-18T00:00:00', '23:59', None),
    ('2026-10-18T00:00:00', '00:00', '2026-10-18T00:00:00'),
    ('2026-10-18T04:00:10', '04:00', '2026-10-18T04:00:00'),
    ('2026-10-17T04:00:10', '25:00', None),
])
def test_daily_trigger_window_and_midnight(current_time, task_time, expected_slot):
    now = QDateTime.fromString(current_time, 'yyyy-MM-ddTHH:mm:ss')
    slot = scheduled_task_slot({'time': task_time}, now)
    expected = QDateTime.fromString(expected_slot, 'yyyy-MM-ddTHH:mm:ss').toSecsSinceEpoch() if expected_slot else None
    assert slot == expected


@pytest.mark.parametrize(('current_time', 'expected_delay'), [
    ('2026-10-17T03:59:42.300', 17700),
    ('2026-10-17T04:00:00.000', 60000),
    ('2026-10-17T04:00:00.001', 59999),
    ('2026-10-17T04:00:59.999', 1),
    ('2026-10-17T23:59:40.125', 19875),
])
def test_next_minute_delay_aligns_with_wall_clock(current_time, expected_delay):
    now = QDateTime.fromString(current_time, 'yyyy-MM-ddTHH:mm:ss.zzz')
    assert milliseconds_to_next_minute(now) == expected_delay


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows 命令行参数规则')
@pytest.mark.parametrize('arguments', [
    ['--config', r'C:\Users\demo\config.yaml'],
    ['--config', r'C:\Program Files\demo\config.yaml'],
    ['--output', 'C:\\Program Files\\demo\\'],
    ['--message', 'hello "world"', ''],
    ['--path', r'\\server\shared folder\file.txt'],
])
def test_windows_arguments_preserve_paths_and_quotes(arguments):
    assert split_task_arguments(subprocess.list2cmdline(arguments)) == arguments


def test_internal_workflow_arguments_keep_posix_quoting():
    arguments = [r'C:\Program Files\main.py', '--workflow-name', "workflow's name"]
    assert split_task_arguments(shlex.join(arguments), posix=True) == arguments


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows 命令行参数规则')
@pytest.mark.parametrize(('arguments', 'expected'), [
    ("--title 'hello world'", ['--title', 'hello world']),
    ("--config 'C:\\Program Files\\demo\\config.yaml'", ['--config', r'C:\Program Files\demo\config.yaml']),
    ('--title "it\'s ready"', ['--title', "it's ready"]),
    ('--title \'say "hello"\'', ['--title', 'say "hello"']),
])
def test_windows_arguments_keep_legacy_single_quote_groups(arguments, expected):
    assert split_task_arguments(arguments) == expected
