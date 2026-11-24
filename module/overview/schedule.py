"""定时任务的日期和链顺序。运行页传入 Qt 的候选时间构造器以保留时区语义。"""
from datetime import datetime, time, timedelta


def task_trigger_mode(task) -> str:
    mode = str((task or {}).get('trigger_mode', 'time')).strip().lower()
    return 'chain' if mode == 'chain' else 'time'


def task_weekdays(task) -> tuple[int, ...]:
    weekdays = task.get('weekdays')
    if weekdays is None:
        return tuple(range(1, 8))
    if not isinstance(weekdays, (list, tuple, set)):
        return ()
    return tuple(sorted({day for day in weekdays if isinstance(day, int) and not isinstance(day, bool) and 1 <= day <= 7}))


def schedule_time(value):
    try:
        hour, minute, *rest = map(int, value.split(':'))
        if len(rest) > 2:
            return None
        return time(hour, minute, rest[0] if rest else 0, rest[1] * 1000 if len(rest) == 2 else 0)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None


def schedule_weekday_labels() -> tuple[str, ...]:
    from module.localization import tr

    return (tr('周一'), tr('周二'), tr('周三'), tr('周四'), tr('周五'), tr('周六'), tr('周日'))


def format_task_weekdays(task) -> str:
    from module.localization import tr

    weekdays = task_weekdays(task)
    if len(weekdays) == 7:
        return tr('每天')
    if not weekdays:
        return tr('未选择')
    labels = schedule_weekday_labels()
    return '、'.join(labels[day - 1] for day in weekdays)


def schedule_conflict(tasks, clock, weekdays, editing=None):
    from module.localization import tr

    days = set(weekdays)
    if not days:
        return tr("请至少选择一个执行星期")
    for task in tasks:
        if not isinstance(task, dict) or task_trigger_mode(task) != "time":
            continue
        if task is editing or (editing and editing.get("id") and task.get("id") == editing["id"]):
            continue
        overlap = days.intersection(task_weekdays(task))
        if overlap and schedule_time(task.get("time")) == clock:
            return tr("任务“{name}”已占用{days}的 {time}，请调整时间或星期").format(
                name=task.get("name") or tr("未命名"), days=format_task_weekdays({"weekdays": overlap}),
                time=clock.strftime("%H:%M"))
    return ""


def next_occurrence(task, now, make_candidate=None):
    clock = schedule_time(task.get('time', '00:00'))
    weekdays = task_weekdays(task)
    if clock is None or not weekdays:
        return None
    for offset in range(8):
        if make_candidate is None:
            day = now.date() + timedelta(days=offset)
            local = datetime.combine(day, clock, tzinfo=now.tzinfo)
            # 夏令时跳过的墙上时刻按实际 UTC 偏移解析；重复的一小时也按时间戳比较。
            candidate = datetime.fromtimestamp(local.timestamp(), tz=now.tzinfo)
            weekday = day.isoweekday()
        else:
            weekday, candidate = make_candidate(offset, clock)
        if weekday in weekdays and candidate is not None:
            future = candidate.timestamp() > now.timestamp() if make_candidate is None else candidate > now
            if future:
                return candidate
    return None


def next_schedule(tasks, now, occurrence=next_occurrence):
    enabled = [t for t in tasks if isinstance(t, dict) and t.get('enabled', True) and task_trigger_mode(t) == 'time']
    selected = at = None
    for task in enabled:
        candidate = occurrence(task, now)
        if candidate is not None and (at is None or candidate < at):
            selected, at = task, candidate
    return len(enabled), at, selected


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


def following_tasks(task, tasks):
    start_index = find_scheduled_task(task, tasks)
    if start_index >= 0:
        for candidate in tasks[start_index + 1:]:
            if task_trigger_mode(candidate) != 'chain':
                break
            if candidate.get('enabled', True):
                yield candidate
