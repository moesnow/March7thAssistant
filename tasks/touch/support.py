"""在触屏编队页按已有的支援配置借角色。"""
import json
from pathlib import Path
import time

import cv2
import numpy as np

from module.automation import auto
from module.config import cfg
from module.logger import log
from tasks.base.list_drag import changed_ratio, drag_list
from tasks.touch.power import PowerError, START_CHALLENGE, _click_text, _tap
from utils.image_utils import ImageUtils


BUTTON = (776 / 1920, 945 / 1080, 151 / 1920, 73 / 1080)
HEADER = (364 / 1920, 50 / 1080, 334 / 1920, 62 / 1080)
PORTRAITS = (54 / 1920, 189 / 1080, 144 / 1920, 756 / 1080)
ORNAMENT_BUTTON = (779 / 1920, 839 / 1080, 204 / 1920, 71 / 1080)
ORNAMENT_HEADER = (294 / 1920, 58 / 1080, 174 / 1920, 57 / 1080)
ORNAMENT_PORTRAITS = (54 / 1920, 210 / 1080, 144 / 1920, 735 / 1080)
TEAM_NAMES = (785 / 1920, 595 / 1080, 1049 / 1920, 206 / 1080)
TEAM_FULL = (508 / 1920, 203 / 1080, 907 / 1920, 72 / 1080)
DETAILS = (974 / 1920, 948 / 1080, 424 / 1920, 87 / 1080)
CONFIRM = (1413 / 1920, 949 / 1080, 431 / 1920, 90 / 1080)
CHARACTERS = Path("assets/images/share/character")


def _portrait_rows(pixels, template):
    """返回与 PC 头像同源的触屏列表位置，裁掉等级、命途和入队角标所在的边缘。"""
    height, width = template.shape[:2]
    face = template[round(height * 0.20):round(height * 0.87), round(width * 0.24):round(width * 0.88)]
    candidates = []
    for percent in range(66, 94, 2):
        scale = percent / 100
        portrait = cv2.resize(face, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        h, w = portrait.shape[:2]
        if h > pixels.shape[0] or w > pixels.shape[1]:
            continue
        scores = cv2.matchTemplate(pixels, portrait, cv2.TM_CCOEFF_NORMED)
        while True:
            _, score, _, (_, y) = cv2.minMaxLoc(scores)
            if score < 0.79:
                break
            candidates.append((score, y + h // 2))
            scores[max(0, y - 40):y + 41] = -1
    rows = []
    for _, y in sorted(candidates, reverse=True):
        if all(abs(y - existing) > 45 for existing in rows):
            rows.append(y)
    return rows


def _find_on_page(pixels, targets, top):
    for name, owner, template in targets:
        for offset in _portrait_rows(pixels, template):
            y = top + offset
            owner_area = (134 / 1280, max(top, y - 53) / 720, 245 / 1280, 46 / 720)
            if not owner or auto.find_element(owner, "text", include=True, crop=owner_area):
                return name, y
    return None


def _choose_target(targets, crop):
    pages = max(1, cfg.borrow_scroll_times)
    top = round(crop[1] * 720)
    for page in range(pages):
        frame, _, _ = auto.take_screenshot(crop=crop)
        pixels = cv2.cvtColor(np.asarray(frame), cv2.COLOR_RGB2BGR)
        if target := _find_on_page(pixels, targets, top):
            return target
        if page + 1 == pages:
            break
        if not drag_list(auto, (455 / 1920, 824 / 1080), (455 / 1920, 376 / 1080),
                         crop=crop, end_pause=0.2, settle=0.4):
            break
        if changed_ratio(frame, auto.screenshot) <= 0.01:
            break
    return None


def _preview_target(target, targets, crop, last_slot):
    name, y = target
    _tap(124, y * 1.5)
    if auto.find_element("队伍角色已满", "text", crop=TEAM_FULL, max_retries=2, retry_delay=0.2):
        # 只有游戏确认队伍已满时，才在本次支援预览中让出末位。
        _tap(*last_slot)
        time.sleep(0.4)
        frame, _, _ = auto.take_screenshot(crop=crop)
        pixels = cv2.cvtColor(np.asarray(frame), cv2.COLOR_RGB2BGR)
        same_name = [item for item in targets if item[0] == name]
        target = _find_on_page(pixels, same_name, round(crop[1] * 720))
        if not target:
            raise PowerError("让出编队末位后未能重新定位支援角色")
        _tap(124, target[1] * 1.5)


def _confirm_standard_team(name):
    if not auto.find_element("支援详情", "text", crop=DETAILS, max_retries=6, retry_delay=0.25):
        raise PowerError("未确认支援角色已进入本次编队预览")
    if not auto.find_element(name, "text", crop=TEAM_NAMES):
        raise PowerError("编队中的支援角色与配置不符")
    if not _click_text("确认", CONFIRM):
        raise PowerError("无法确认支援编队")


def borrow(*, ornament=False):
    names = json.loads(Path("assets/config/character_names.json").read_text(encoding="utf-8"))
    targets = []
    for key, owner in cfg.borrow_friends:
        path = CHARACTERS / f"{key}.png"
        if key in names and path.is_file():
            template = ImageUtils.read_image(str(path))
            if template is not None:
                targets.append((names[key], owner, template))
    if not targets:
        log.info("未配置可用的支援角色，跳过借用")
        return False
    button, portraits = (ORNAMENT_BUTTON, ORNAMENT_PORTRAITS) if ornament else (BUTTON, PORTRAITS)
    if auto.find_element("解除支援", "text", crop=button):
        log.info("本次编队已有支援角色")
        return True
    if not _click_text("支援", button, retries=3):
        log.info("当前编队没有支援入口，跳过借用")
        return False
    label, header = ("支援列表", ORNAMENT_HEADER) if ornament else ("支援角色", HEADER)
    if not auto.find_element(label, "text", crop=header, max_retries=8, retry_delay=0.25):
        raise PowerError("未进入触屏支援列表")
    if target := _choose_target(targets, portraits):
        _preview_target(target, targets, portraits, (1166, 775) if ornament else (1712, 570))
        if ornament:
            _tap(1848, 55)
        else:
            _confirm_standard_team(target[0])
        if not auto.find_element("解除支援", "text", crop=button, max_retries=8, retry_delay=0.25):
            raise PowerError("返回编队后未确认借到支援角色")
        log.info(f"已借到支援角色：{target[0]}")
        return True

    _tap(1848, 55)
    if not auto.find_element("开始挑战", "text", crop=START_CHALLENGE, max_retries=6, retry_delay=0.25):
        raise PowerError("关闭支援列表后未回到编队")
    log.info("当前支援列表未找到已配置的角色，跳过借用")
    return False
