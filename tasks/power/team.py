"""清体力与历战余响的编队识别和切换。"""

import re
import time

import numpy as np

from module.automation.input_base import input_deadline, input_deadline_reached, limit_input_deadline
from module.logger import log
from tasks.base.list_drag import drag_list
from tasks.base.task_steps import FATAL_GAME_ERRORS, GameRecoveryError
from utils.pause import pause_ctl


TEAM_NUMBER = r"0[1-9]|1[0-9]"
TEAM_TABS = (495 / 1920, 25 / 1080, 930 / 1920, 88 / 1080)
TEAM_ACTIONS = (910 / 1920, 946 / 1080, 960 / 1920, 84 / 1080)
TEAM_ACTIVATE = (1507 / 1920, 946 / 1080, 365 / 1920, 84 / 1080)
ACTIVATION_DIALOG = (425 / 1920, 270 / 1080, 1070 / 1920, 550 / 1080)
ROSTER = (95 / 1920, 715 / 1080, 1665 / 1920, 180 / 1080)
PATHS = ("毁灭", "巡猎", "智识", "同谐", "虚无", "存护", "丰饶", "记忆", "欢愉")
MAX_TEAM_DRAGS = 4
TEAM_SWITCH_TIMEOUT = 26


def _read_tabs(auto, crop):
    frame, _, _ = auto.take_screenshot(crop=crop)
    auto.perform_ocr()
    labels = {}
    highlighted = []
    # 选中标签的数字下有一条连续白线，角色模型和未选中数字不具备这个特征。
    line_top = round(frame.height * (96 / 1080 - crop[1]) / crop[3])
    line_bottom = round(frame.height * (109 / 1080 - crop[1]) / crop[3])
    bright = np.asarray(frame.convert("RGB"))[line_top:line_bottom].min(axis=2) >= 235
    radius = round(frame.width * (30 / 1920) / crop[2])
    for box, (label, _) in auto.ocr_result:
        if not re.fullmatch(TEAM_NUMBER, label):
            continue
        center = round(sum(point[0] for point in box) / len(box))
        if label in labels:
            labels[label] = None
            continue
        labels[label] = auto.calculate_text_position(box, relative=False)
        if radius <= center <= frame.width - radius:
            if (bright[:, center - radius:center + radius].mean(axis=1) >= 0.95).any():
                highlighted.append(label)
    labels = {label: button for label, button in labels.items() if button is not None}
    selected = highlighted[0] if len(highlighted) == 1 and highlighted[0] in labels else None
    return labels, selected


def _choose_tab(auto, label, tabs, selected, deadline, crop):
    previous = selected
    for attempt in range(2):
        if selected == label:
            return True
        if label not in tabs or (attempt and (selected is None or selected != previous)):
            break
        pause_ctl.checkpoint()
        if input_deadline_reached(time.monotonic()):
            break
        auto.click_element_with_pos(tabs[label])
        until = min(deadline, time.monotonic() + 3.5)
        while time.monotonic() < until:
            before = selected
            time.sleep(0.35)
            tabs, selected = _read_tabs(auto, crop)
            if selected == label == before:
                return True
    return False


def _activation_prompt_button(auto, text):
    if auto.find_element("角色命途切换为队伍中预设的命途", "text", include=True, crop=ACTIVATION_DIALOG):
        return auto.find_element(text, "text", take_screenshot=False, need_ocr=False)
    return None


def _wait_activation(auto, label, crop, deadline, *, pending=False):
    confirmed_prompt = False
    while time.monotonic() < deadline:
        button = auto.find_element(("启用队伍", "已启用"), "text", crop=TEAM_ACTIVATE)
        if button:
            enabled = auto.matched_text == "已启用"
            if (enabled or not pending) and _read_tabs(auto, crop)[1] == label:
                return button, enabled
        if pending and not confirmed_prompt:
            confirm = _activation_prompt_button(auto, "确认启用")
            if confirm:
                pause_ctl.checkpoint()
                if input_deadline_reached(time.monotonic()):
                    break
                auto.click_element_with_pos(confirm)
                confirmed_prompt = True
        time.sleep(0.35)
    return None, False


def select_preset(auto, team, *, activate=False, crop=TEAM_TABS):
    """成功返回 None，其他结果返回失败阶段。预览动作只用于有独立启用按钮的页面。"""
    label = str(team).zfill(2)
    if not re.fullmatch(TEAM_NUMBER, label):
        return "队伍编号格式错误"

    deadline = time.monotonic() + TEAM_SWITCH_TIMEOUT
    if caller_deadline := input_deadline.get():
        deadline = min(deadline, caller_deadline)
    with limit_input_deadline(deadline):
        tabs, selected = _read_tabs(auto, crop)
        if label not in tabs:
            time.sleep(0.35)
            tabs, selected = _read_tabs(auto, crop)

        left, right = (675 / 1920, 66 / 1080), (1270 / 1920, 66 / 1080)
        unchanged = 0
        for _ in range(MAX_TEAM_DRAGS):
            if label in tabs or not tabs or min(tabs) <= label <= max(tabs):
                break
            pause_ctl.checkpoint()
            if input_deadline_reached(time.monotonic()):
                break
            start, end = (left, right) if label < min(tabs) else (right, left)
            drag_list(auto, start, end, crop=crop, settle=0.4, text_pattern=TEAM_NUMBER)
            before = tabs
            tabs, selected = _read_tabs(auto, crop)
            unchanged = unchanged + 1 if tabs.keys() == before.keys() else 0
            if unchanged >= 2:
                break

        if activate and label not in tabs and tabs and min(tabs) <= label <= max(tabs):
            alternatives = [number for number in tabs if number != selected]
            if alternatives:
                # 只点击读到的标签，既不按相邻位置猜编号，也不启用预览队伍。
                preview = min(alternatives, key=lambda number: abs(int(number) - int(label)))
                _choose_tab(auto, preview, tabs, selected, deadline, crop)
                until = min(deadline, time.monotonic() + 3)
                while time.monotonic() < until:
                    time.sleep(0.35)
                    tabs, selected = _read_tabs(auto, crop)
                    if label in tabs:
                        break

        if label not in tabs:
            return "未识别到队伍编号"
        if not _choose_tab(auto, label, tabs, selected, deadline, crop):
            return "未确认选中目标队伍"
        if activate:
            button, enabled = _wait_activation(auto, label, crop, min(deadline, time.monotonic() + 4))
            if not button:
                return "未确认目标队伍可启用"
            if not enabled:
                pause_ctl.checkpoint()
                if input_deadline_reached(time.monotonic()):
                    return "切队等待超时"
                auto.click_element_with_pos(button)
                _, enabled = _wait_activation(auto, label, crop, min(deadline, time.monotonic() + 8), pending=True)
                if not enabled:
                    cancel = _activation_prompt_button(auto, "取消启用")
                    if cancel and not input_deadline_reached(time.monotonic()):
                        auto.click_element_with_pos(cancel)
                    return "未确认目标队伍已启用"
        return None


def warn_team_switch(name, team, stage, reason):
    log.warning(f"{name}：未能切换到队伍 {str(team).zfill(2)}（{stage}：{reason}）")


def find_current_team_start(auto, start_crop):
    if not auto.find_element(PATHS, "text", include=True, crop=ROSTER, max_retries=3, retry_delay=0.3):
        return None
    button = auto.find_element("开始挑战", "text", crop=start_crop, max_retries=3, retry_delay=0.3)
    if not button:
        return None
    # 弹窗会压暗编队界面，但底层的「开始挑战」有时仍能被 OCR 读到。
    # 取文字左侧的按钮底色，确认按钮仍处于可操作状态。
    (left, top), (_, bottom) = button
    offset_x, offset_y, _, _ = auto.screenshot_pos
    scale = auto.screenshot_scale_factor
    frame = auto.screenshot
    unit = frame.width / (1920 * start_crop[2])
    x = round((left - offset_x) * scale - 22 * unit)
    y = round(((top + bottom) / 2 - offset_y) * scale)
    pad = max(2, round(5 * unit))
    if pad <= x < frame.width - pad and pad <= y < frame.height - pad:
        pixels = np.asarray(frame.crop((x - pad, y - pad, x + pad, y + pad)).convert("RGB"))
        if np.median(pixels.min(axis=2)) >= 210:
            return button
    return None


def restore_main(screen, name, *, leave_team=None):
    try:
        if leave_team is not None:
            leave_team()
        screen.change_to("main", max_recursion=1)
    except FATAL_GAME_ERRORS:
        raise
    except RuntimeError as error:
        raise GameRecoveryError(f"{name}：退出编队后无法返回主界面：{error}") from error
