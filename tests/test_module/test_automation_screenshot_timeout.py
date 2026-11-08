"""截图重试时限仅作用于当前上下文，普通任务仍按原策略重试。"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def capture(monkeypatch):
    import module.automation.automation as module

    automation = object.__new__(module.Automation)
    automation.window_title = "test-game"
    automation.logger = Mock()
    monkeypatch.setattr(automation, "_is_debug_enabled", lambda: False)
    clock = SimpleNamespace(now=0.0)
    sleep = Mock(side_effect=lambda seconds: setattr(clock, "now", clock.now + seconds))
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: clock.now, sleep=sleep))
    screenshot = Mock()
    monkeypatch.setattr(module.Screenshot, "take_screenshot", screenshot)
    return SimpleNamespace(
        module=module, automation=automation, clock=clock,
        sleep=sleep, screenshot=screenshot, result=("image", (0, 0, 1920, 1080), 1),
    )


@pytest.mark.parametrize("failure", [False, OSError("截图暂时不可用")])
def test_zero_timeout_tries_once_and_restores_default(capture, failure):
    capture.screenshot.side_effect = [failure, False, capture.result]
    with capture.module.screenshot_retry_timeout(0):
        with pytest.raises(RuntimeError, match="截图"):
            capture.automation.take_screenshot()
    capture.sleep.assert_not_called()
    assert capture.screenshot.call_count == 1

    # 离开上下文后，普通任务能等待并重试成功。
    assert capture.automation.take_screenshot() == capture.result
    capture.sleep.assert_called_once_with(1)
    assert capture.screenshot.call_count == 3


def test_default_timeout_still_waits_sixty_seconds(capture):
    capture.screenshot.return_value = False
    with pytest.raises(RuntimeError, match="截图超时"):
        capture.automation.take_screenshot()
    assert capture.clock.now == 60


def test_timeout_contexts_are_nested_and_thread_local(capture):
    from concurrent.futures import ThreadPoolExecutor

    capture.screenshot.return_value = False
    with capture.module.screenshot_retry_timeout(2):
        with capture.module.screenshot_retry_timeout(0):
            with pytest.raises(RuntimeError):
                capture.automation.take_screenshot()
        with pytest.raises(RuntimeError):
            capture.automation.take_screenshot()
        assert capture.clock.now == 2
        # GUI 的单次截图设置不能影响其他线程的正常重试时限。
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(capture.module._screenshot_retry_timeout.get).result() == 60
