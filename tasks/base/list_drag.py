"""列表拖动后等待惯性结束，并恢复调用方需要的截图区域。"""
import time
import re

import numpy as np


def _changed(before, after):
    first = np.asarray(before.convert("L"), dtype=np.int16)
    second = np.asarray(after.convert("L"), dtype=np.int16)
    if first.shape != second.shape:
        return 1.0
    return float((np.abs(second - first) > 24).mean())


def drag_list(auto, start, end, *, crop, duration=0.8, settle=1.0, tolerance=0.01, text_pattern=None,
              end_pause=0.0, poll_interval=0.25):
    """只发送一次手势；中断或 16 轮内未静止时返回 False，由调用方重新识别。

    drag_mouse 会截全屏；这里在松手后重新截图，不能复用手势开始时的帧。
    即使输入中断也等待并更新 crop，避免把部分移动当成完整翻页。
    """
    completed = auto.drag_mouse(start, end, duration, end_pause) if end_pause else auto.drag_mouse(start, end, duration)
    time.sleep(settle)
    previous, _, _ = auto.take_screenshot(crop=crop)
    previous = previous.copy()
    previous_text = None
    quiet = 0
    for _ in range(16):
        time.sleep(poll_interval)
        current, _, _ = auto.take_screenshot(crop=crop)
        if text_pattern is None:
            stable = _changed(previous, current) <= tolerance
        else:
            # 忘却之庭的水晶一直在动，只比较关卡数字的位置，避免把动画当成惯性。
            auto.perform_ocr()
            positions = {text: (sum(p[0] for p in box) / len(box), sum(p[1] for p in box) / len(box))
                         for box, (text, _) in auto.ocr_result if re.fullmatch(text_pattern, text)}
            stable = bool(positions) and previous_text is not None and positions.keys() == previous_text.keys()
            if stable:
                stable = all(abs(a - b) <= 2 for text, point in positions.items() for a, b in zip(point, previous_text[text]))
            previous_text = positions
        quiet = quiet + 1 if stable else 0
        previous = current.copy()
        if quiet >= 2:
            return bool(completed)
    return False


def drag_to_edge(auto, start, end, *, crop, max_drags=8, **kwargs):
    """逐页拖到边界；仅在两次拖动前后画面不变时确认到头，始终有上限。"""
    unchanged = 0
    for _ in range(max_drags):
        before, _, _ = auto.take_screenshot(crop=crop)
        before = before.copy()
        if not drag_list(auto, start, end, crop=crop, **kwargs):
            return False
        unchanged = unchanged + 1 if _changed(before, auto.screenshot) <= 0.01 else 0
        if unchanged >= 2:
            return True
    return False
