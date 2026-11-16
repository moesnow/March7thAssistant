import time

from module.game.adb_transport import AdbError
from tasks.base.task_steps import FATAL_GAME_ERRORS
from utils.wait import wait_until


def find_thread_markers(automation, crop, marker_crop, templates):
    frame, (left, top, _, _), scale = automation.take_screenshot(crop=crop)
    x, y, width, height = marker_crop
    unit_x = frame.width / scale / crop[2]
    unit_y = frame.height / scale / crop[3]
    x1 = round(left + (x - crop[0]) * unit_x)
    y1 = round(top + (y - crop[1]) * unit_y)
    x2 = round(x1 + width * unit_x)
    y2 = round(y1 + height * unit_y)
    markers = []
    for template, threshold in templates:
        matches = automation.find_element(template, "image_with_multiple_targets", threshold, take_screenshot=False) or []
        markers.extend(box for box in matches if x1 <= box[0][0] and box[1][0] <= x2
                       and y1 <= box[0][1] and box[1][1] <= y2)
    return markers


def read_thread_titles(automation):
    """从刚定位短信图标的同一帧读取会话标题。"""
    automation.perform_ocr()
    return [
        (automation.calculate_text_position(box, False), "".join(text.split()))
        for box, (text, _) in automation.ocr_result
        if text.strip()
    ]


def thread_title(titles, marker):
    (left, top), (right, bottom) = marker
    center = (top + bottom) / 2
    row = []
    for ((x1, y1), (x2, y2)), text in titles:
        text_center = (y1 + y2) / 2
        gap = max(left - x2, x1 - right)
        if gap >= 0 and abs(text_center - center) <= bottom - top:
            row.append((gap, abs(text_center - center), text_center, x1, text))
    if not row:
        return None
    _, _, line_center, _, _ = min(row)
    # 取标记同一行的文字，标记可能在名称任一侧。仍无法区分的同名行一并避开。
    return "｜".join(text for _, _, y, _, text in sorted(row, key=lambda line: line[3])
                    if abs(y - line_center) <= (bottom - top) / 2)


def find_thread_title(automation, crop, marker_crop, template, threshold):
    """超时后仍在原会话时，从新画面的同一帧复核标记和标题。"""
    for attempt in range(2):
        if attempt:
            time.sleep(0.25)
        markers = find_thread_markers(automation, crop, marker_crop, ((template, threshold),))
        if len(markers) == 1 and (title := thread_title(read_thread_titles(automation), markers[0])):
            return title
    return None


def first_unblocked_thread(automation, crop, marker_crop, templates, blocked_titles):
    for attempt in range(2):
        if attempt:
            time.sleep(0.25)
        markers = find_thread_markers(automation, crop, marker_crop, templates)
        if not markers:
            return None
        titles = read_thread_titles(automation)
        unresolved = False
        for marker in markers:
            title = thread_title(titles, marker)
            if not title:
                unresolved = True
            elif title not in blocked_titles:
                return marker
        if not unresolved:
            return None
    return None


def close_sms_receipt(close, is_visible):
    """到账只计一次。关闭后等待弹窗离开，再处理下一条会话。"""
    clear_frames = 0

    def popup_gone():
        nonlocal clear_frames
        clear_frames = 0 if is_visible() else clear_frames + 1
        return clear_frames == 2

    try:
        return close() is not False and wait_until(popup_gone, 2, 0.25)
    except Exception as error:
        if isinstance(error, FATAL_GAME_ERRORS) and not (isinstance(error, AdbError) and error.code == "frame_timeout"):
            raise
        return False
