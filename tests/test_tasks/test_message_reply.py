from unittest.mock import Mock, call

import cv2
import numpy as np
from PIL import Image

from tasks.reward import message


def _canvas_with_sprite(sprite_path, positions, scale, size=(400, 300)):
    template = cv2.imread(sprite_path, cv2.IMREAD_COLOR)
    assert template is not None
    resized = template if scale == 1.0 else cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    canvas = np.full((size[1], size[0], 3), template[0, 0], dtype=np.uint8)
    h, w = resized.shape[:2]
    for x, y in positions:
        canvas[y:y + h, x:x + w] = resized
    return Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)), (w, h)


def _fake_auto(frame):
    auto = Mock()
    auto.take_screenshot.return_value = (frame, (100, 200, frame.width, frame.height), 1.0)
    auto.calculate_text_position.side_effect = lambda box, relative: (
        (box[0][0] + 100, box[0][1] + 200),
        (box[2][0] + 100, box[2][1] + 200),
    )
    auto.click_element_with_pos.return_value = True
    return auto


def test_message_reply_matches_topmost_scaled_reply_without_unpack_crash(monkeypatch):
    frame, (w, h) = _canvas_with_sprite(
        f"{message.Message._REPLY_ASSETS}/message_reply.png",
        positions=[(140, 120), (80, 40)],
        scale=1.5,
    )
    fake_auto = _fake_auto(frame)
    monkeypatch.setattr(message, "auto", fake_auto)

    assert message.Message._reply() is True

    fake_auto.take_screenshot.assert_called_once_with(crop=message.Message._REPLY_CROP)
    box = fake_auto.calculate_text_position.call_args.args[0]
    (x, y), _, (right, bottom), _ = box
    assert abs(x - 80) <= 2 and abs(y - 40) <= 2
    assert abs((right - x) - w) <= 1 and abs((bottom - y) - h) <= 1
    assert fake_auto.click_element_with_pos.call_args == call(
        ((x + 100, y + 200), (right + 100, bottom + 200)),
        offset=(0, 0),
    )


def test_message_reply_falls_back_to_leftmost_sticker_with_offset(monkeypatch):
    frame, (w, h) = _canvas_with_sprite(
        f"{message.Message._REPLY_ASSETS}/message_sticker.png",
        positions=[(220, 70), (60, 90)],
        scale=1.0,
    )
    fake_auto = _fake_auto(frame)
    monkeypatch.setattr(message, "auto", fake_auto)

    assert message.Message._reply() is True

    box = fake_auto.calculate_text_position.call_args.args[0]
    (x, y), _, (right, bottom), _ = box
    assert abs(x - 60) <= 2 and abs(y - 90) <= 2
    assert (right - x) == w and (bottom - y) == h
    assert fake_auto.click_element_with_pos.call_args == call(
        ((x + 100, y + 200), (right + 100, bottom + 200)),
        offset=(83, 93),
    )


def test_message_reply_returns_false_when_no_reply_or_sticker_matches(monkeypatch):
    blank = Image.fromarray(np.full((200, 300, 3), 240, dtype=np.uint8))
    fake_auto = _fake_auto(blank)
    monkeypatch.setattr(message, "auto", fake_auto)

    assert message.Message._reply() is False
    fake_auto.click_element_with_pos.assert_not_called()
