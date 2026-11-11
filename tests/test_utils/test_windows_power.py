from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from utils import windows_power


@pytest.fixture
def power(monkeypatch):
    api = Mock()
    api.PowerCreateRequest.return_value = 123
    monkeypatch.setattr(windows_power, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(windows_power, "_kernel32", lambda: api)
    monkeypatch.setattr(windows_power.ctypes, "get_last_error", lambda: 5, raising=False)
    monkeypatch.setattr(windows_power.ctypes, "WinError", lambda code: OSError(code, "测试错误"), raising=False)
    return windows_power.WindowsSystemPowerRequest(), api, Mock()


def test_only_requests_system_power_and_releases_once(power):
    request, api, log = power
    request.acquire(log)
    request.acquire(log)
    context = api.PowerCreateRequest.call_args.args[0]._obj
    assert (context.version, context.flags) == (0, 1)
    assert context.reason.simple == "三月七助手正在执行游戏任务"

    request.release(log)
    request.release(log)
    assert api.mock_calls[1:] == [
        call.PowerSetRequest(123, 1),
        call.PowerClearRequest(123, 1),
        call.CloseHandle(123),
    ]
    log.warning.assert_not_called()


def test_failed_request_closes_handle_and_can_retry(power):
    request, api, log = power
    api.PowerSetRequest.return_value = False
    request.acquire(log)
    request.release(log)

    api.CloseHandle.assert_called_once_with(123)
    api.PowerClearRequest.assert_not_called()
    log.warning.assert_called_once()

    api.PowerSetRequest.return_value = True
    request.acquire(log)
    request.release(log)
    api.PowerClearRequest.assert_called_once_with(123, 1)


def test_clear_failure_still_closes_handle(power):
    request, api, log = power
    request.acquire(log)
    api.PowerClearRequest.return_value = False
    request.release(log)

    api.CloseHandle.assert_called_once_with(123)
    log.warning.assert_called_once()


def test_non_windows_leaves_native_api_unused(power, monkeypatch):
    request, api, log = power
    monkeypatch.setattr(windows_power.sys, "platform", "linux")
    request.acquire(log)
    request.release(log)

    assert not api.mock_calls
