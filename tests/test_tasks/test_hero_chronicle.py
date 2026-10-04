"""Exercise book recognition and unread selection without a game or account."""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import cv2
import numpy as np
import pytest
from PIL import Image


@pytest.fixture
def reader(monkeypatch):
    root = Path(__file__).parents[2]
    monkeypatch.chdir(root)
    capture = ModuleType('module.automation.screenshot')
    capture.Screenshot = Mock()
    logger = ModuleType('module.logger')
    logger.log = Mock()
    spec = importlib.util.spec_from_file_location(
        'hero_chronicle_under_test', root / 'tasks/tool/autoplot/_hero_chronicle.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {
        'module.automation.screenshot': capture, 'module.logger': logger,
    }):
        spec.loader.exec_module(module)
    clicks = Mock()
    instance = module.HeroChronicleReader(clicks, 'test-game')
    monkeypatch.setattr(module.time, 'monotonic', lambda: 0)
    return module, instance, clicks


def book_frame(instance, states=None, directory=False):
    frame = np.full((1080, 1920, 3), 255, dtype=np.uint8)

    def paste(name, x, y):
        template = instance.templates[name]
        height, width = template.shape[:2]
        frame[y:y + height, x:x + width] = template

    paste('header', 45, 37)
    if directory:
        paste('directory', 375, 454)
    else:
        paste('return', 1450, 68)
    for y, state in zip((375, 442, 510, 577, 644), states or []):
        paste(state, 938, y - 13)
    return frame


def capture_frame(module, frame, scale=1):
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    module.Screenshot.take_screenshot.return_value = (
        image, (4, 422, 1920, 1080), scale)


def test_skips_read_chapters_and_opens_first_unread(reader):
    module, instance, clicks = reader
    capture_frame(module, book_frame(instance, ['read', 'read', 'unread', 'locked', 'locked']))
    instance.phase = 'chapters'
    assert instance.tick()
    clicks.assert_called_once_with((1280, 510))
    assert instance.current_row == 2
    assert instance.hero == 0


@pytest.mark.parametrize('states', [['read'] * 5, ['locked'] * 5])
def test_hero_without_readable_unread_chapters_is_skipped(reader, states):
    module, instance, clicks = reader
    capture_frame(module, book_frame(instance, states))
    instance.phase = 'chapters'
    assert instance.tick()
    clicks.assert_called_once_with((1510, 85))
    assert instance.hero == 1
    assert instance.stories == 0
    assert not instance.completed


def test_rescans_newly_unlocked_unread_chapter(reader):
    module, instance, clicks = reader
    instance.phase = 'chapters'
    instance.visited = {2}
    capture_frame(module, book_frame(instance, ['read', 'read', 'read', 'unread', 'locked']))
    assert instance.tick()
    clicks.assert_called_once_with((1280, 577))
    assert instance.current_row == 3


def test_mid_book_start_returns_to_full_index_before_selection(reader):
    module, instance, clicks = reader
    capture_frame(module, book_frame(instance, ['read', 'unread', 'locked', 'locked', 'locked']))
    assert instance.tick()
    clicks.assert_called_once_with((1510, 85))
    assert instance.current_row is None
    assert instance.stories == 0


def test_missing_capture_does_not_click(reader):
    module, instance, clicks = reader
    module.Screenshot.take_screenshot.return_value = False
    assert not instance.tick()
    clicks.assert_not_called()


def test_unrelated_screen_does_not_click(reader):
    module, instance, clicks = reader
    capture_frame(module, np.full((1080, 1920, 3), 255, dtype=np.uint8))
    assert not instance.tick()
    clicks.assert_not_called()


def test_completion_requires_all_twelve_heroes(reader):
    module, instance, clicks = reader
    capture_frame(module, book_frame(instance, directory=True))
    instance.hero = 12
    assert instance.tick()
    assert instance.finished and instance.completed
    clicks.assert_not_called()


def test_last_page_without_next_arrow_uses_ending_marker(reader):
    module, instance, clicks = reader
    frame = book_frame(instance)
    ending = instance.templates['ending']
    height, width = ending.shape[:2]
    frame[982:982 + height, 1220:1220 + width] = ending
    cv2.circle(frame, (753, 1019), 6, (140, 140, 140), -1)
    cv2.circle(frame, (780, 1019), 6, (70, 160, 190), 1)
    assert instance.page_dots(frame) == (1, 2)
    capture_frame(module, frame)
    instance.phase = 'reading'
    instance.current_row = 2
    assert instance.tick()
    clicks.assert_called_once_with((1740, 245))
    assert instance.stories == 1
    assert 2 in instance.visited
