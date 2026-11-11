from unittest.mock import Mock

import pytest

from module.game.adb_transport import AdbError
from tasks.base import task_steps
from utils.pause import RunStopRequested


@pytest.fixture
def journal(monkeypatch):
    """按发生顺序记下错误日志、步骤事件和回主界面。"""
    events = []
    monkeypatch.setattr(task_steps.log, "error", lambda message: events.append(("log", message)))
    monkeypatch.setattr(task_steps.screen, "change_to", lambda *args, **kwargs: events.append(("main",)))
    return events


def broken():
    raise RuntimeError("未确认邮箱附件状态")


def test_reports_each_step_and_continues_after_failures(journal):
    steps = [("委托", lambda: None), ("邮件", broken), ("支援", lambda: False), ("短信", lambda: True)]

    assert task_steps.run_steps(steps, on_step=lambda name, state: journal.append((name, state))) is False
    # 失败时先写原因、再报失败、最后回主界面。
    assert journal == [
        ("委托", "started"), ("委托", "succeeded"),
        ("邮件", "started"), ("log", "邮件失败：未确认邮箱附件状态"), ("邮件", "failed"), ("main",),
        ("支援", "started"), ("log", "支援未完成"), ("支援", "failed"), ("main",),
        ("短信", "started"), ("短信", "succeeded"),
    ]


def test_without_callback_behaves_as_before(journal):
    steps = [("委托", lambda: None), ("邮件", broken), ("支援", lambda: False)]

    assert task_steps.run_steps(steps) is False
    assert journal == [("log", "邮件失败：未确认邮箱附件状态"), ("main",), ("log", "支援未完成"), ("main",)]
    assert task_steps.run_steps([("委托", lambda: None)]) is True


@pytest.mark.parametrize("error", [AdbError("disconnected", "设备已断开"), RunStopRequested()])
def test_fatal_errors_and_stop_requests_end_without_a_result(journal, error):
    def fatal():
        raise error

    later = Mock()
    with pytest.raises(type(error)):
        task_steps.run_steps([("清体力", fatal), ("每日实训", later)],
                             on_step=lambda name, state: journal.append((name, state)))
    assert journal == [("清体力", "started")]
    later.assert_not_called()
