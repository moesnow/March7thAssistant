from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
from PIL import Image
import pytest

from tasks.activity import journey_highlights_notification as journey
from utils.pause import RunStopRequested


class Calendar:
    """在完整游戏帧内绘制固定总览和可滚动列表，保留右侧进度列。"""

    def __init__(self, width=1920, height=1080, content_height=1800):
        self.size = width, height
        self.left = int(width * 375 / 1920)
        self.top = int(height * 142 / 1080)
        self.list_top = int(height * 335 / 1080)
        self.width = int(width * 1460 / 1920)
        self.viewport = int(height * 655 / 1080)
        rng = np.random.default_rng(1449)
        self.header = rng.integers(0, 256, (int(height * 193 / 1080), self.width, 3), dtype=np.uint8)
        self.content = rng.integers(0, 256, (int(height * content_height / 1080), self.width, 3), dtype=np.uint8)
        self.offset = 0
        self.offsets = [0]
        self.screenshot = None

    def take_screenshot(self, crop):
        frame = Image.new("RGB", self.size)
        frame.paste(Image.fromarray(self.header), (self.left, self.top))
        frame.paste(Image.fromarray(self.content[self.offset:self.offset + self.viewport]), (self.left, self.list_top))
        x, y, w, h = [int(size * ratio) for size, ratio in zip(self.size * 2, crop)]
        self.screenshot = frame.crop((x, y, x + w, y + h))
        return self.screenshot, (x, y, w, h), 1

    def drag_mouse(self, *_args):
        self.offset = min(self.offset + int(self.size[1] * 430 / 1080), len(self.content) - self.viewport)
        self.offsets.append(self.offset)
        return True


@pytest.fixture
def calendar(monkeypatch):
    def setup(**kwargs):
        game = Calendar(**kwargs)
        monkeypatch.setattr(journey, "auto", game)
        monkeypatch.setattr(journey, "screen", SimpleNamespace(change_to=Mock()))
        monkeypatch.setattr(journey, "time", SimpleNamespace(sleep=Mock()))
        monkeypatch.setattr("tasks.base.list_drag.time", SimpleNamespace(sleep=Mock()))
        return game

    return setup


@pytest.mark.parametrize("width,height", [(1920, 1080), (1280, 720)])
def test_complete_calendar_keeps_summary_right_column_and_last_page(calendar, monkeypatch, width, height):
    game = calendar(width=width, height=height)
    notify = Mock()
    monkeypatch.setattr(journey.Base, "send_notification_with_screenshot", notify)

    journey.send_journey_highlights_notification()

    notify.assert_called_once()
    image = notify.call_args.kwargs["screenshot"]
    assert image.size == (game.width, len(game.header) + len(game.content))
    np.testing.assert_array_equal(np.asarray(image), np.vstack([game.header, game.content]))
    assert game.offsets[-1] == game.offsets[-2] == len(game.content) - game.viewport
    assert len(game.offsets) > 3


def test_short_final_scroll_is_stitched_before_confirming_bottom(calendar):
    game = calendar(content_height=1100)

    image = journey.take_journey_highlights_screenshot()

    assert game.offsets == [0, 430, 445, 445]
    np.testing.assert_array_equal(np.asarray(image), np.vstack([game.header, game.content]))


def test_scroll_limit_does_not_send_a_truncated_calendar(calendar, monkeypatch):
    game = calendar(content_height=5000)
    notify = Mock()
    monkeypatch.setattr(journey.Base, "send_notification_with_screenshot", notify)

    journey.send_journey_highlights_notification()

    assert len(game.offsets) == journey.MAX_SCROLLS + 1
    notify.assert_not_called()


@pytest.mark.parametrize("failure", ["anchor", "drag", "screenshot", "stop"])
def test_failed_capture_does_not_send_partial_image(calendar, monkeypatch, failure):
    game = calendar()
    notify = Mock()
    monkeypatch.setattr(journey.Base, "send_notification_with_screenshot", notify)
    drag = game.drag_mouse
    capture = game.take_screenshot

    def take_screenshot(crop):
        if failure == "screenshot" and game.offset:
            raise RuntimeError("截图暂时不可用")
        return capture(crop)

    def fail_after_first_drag(*args):
        drag(*args)
        if failure == "anchor":
            game.content[:] = 0
        elif failure == "drag":
            return False
        elif failure == "stop":
            raise RunStopRequested()
        return True

    game.drag_mouse = fail_after_first_drag
    game.take_screenshot = take_screenshot

    if failure == "stop":
        with pytest.raises(RunStopRequested):
            journey.send_journey_highlights_notification()
    else:
        journey.send_journey_highlights_notification()

    assert len(game.offsets) == 2
    notify.assert_not_called()
