"""ADB 培养目标，桌面 ADB 与安卓 App 共用：沿用 PC 的两种识别方案与副本校验，只适配触屏页面。"""
import re
import time

import cv2
import numpy as np
from PIL import Image

from module.automation import auto
from module.automation.automation import screenshot_retry_timeout
from module.automation.input_base import input_deadline, input_deadline_reached, limit_input_deadline
from module.logger import log
from module.ocr import ocr
from module.screen import screen
from tasks.base.list_drag import changed_ratio, drag_list, drag_to_edge
from tasks.base.task_steps import FATAL_GAME_ERRORS
from tasks.daily.buildtarget import DefaultHandler, DropHandler
from utils.pause import pause_ctl


IMAGES = "./assets/touch_720/images/share/build_target"
PAGE_CROP = (438 / 1280, 255 / 720, 730 / 1280, 368 / 720)
POWER_COLUMN = (865 / 1280, 255 / 720, 40 / 1280, 368 / 720)
ENTRY_COLUMN = (1010 / 1280, 255 / 720, 158 / 1280, 368 / 720)
TARGET_ENTRY = (125 / 1280, 170 / 720, 290 / 1280, 90 / 720)
TARGET_NAME = (140 / 1280, 216 / 720, 230 / 1280, 29 / 720)
CHALLENGE = (920 / 1280, 634 / 720, 335 / 1280, 62 / 720)
INSTANCE_TYPE = (78 / 1280, 15 / 720, 185 / 1280, 45 / 720)
INSTANCE_HEADER = (78 / 1280, 4 / 720, 250 / 1280, 65 / 720)
INSTANCE_TITLE = (804 / 1280, 76 / 720, 450 / 1280, 44 / 720)
ORNAMENT_TITLE = (503 / 1280, 74 / 720, 384 / 1280, 40 / 720)
MATERIAL_TITLE = (497 / 1280, 180 / 720, 480 / 1280, 45 / 720)
RELIC_TITLE = (497 / 1280, 184 / 720, 480 / 1280, 47 / 720)
MATERIAL_BODY = (500 / 1280, 235 / 720, 582 / 1280, 301 / 720)
MODALS = (
    (f"{IMAGES}/drop_modal_close.png", (1033 / 1280, 177 / 720, 50 / 1280, 49 / 720), MATERIAL_TITLE),
    (f"{IMAGES}/drop_modal_close2.png", (1211 / 1280, 15 / 720, 46 / 1280, 48 / 720), RELIC_TITLE),
)
TRANSIENT_FRAME_ERRORS = ("frame_timeout", "frame_clock_unavailable")


def _check():
    pause_ctl.check_stop()
    if input_deadline_reached(time.monotonic()):
        raise RuntimeError("读取培养目标超时，保留已识别的副本")


def _wait(probe, message, timeout=12):
    deadline = min(time.monotonic() + timeout, input_deadline.get() or float("inf"))
    with limit_input_deadline(deadline):
        while time.monotonic() < deadline:
            _check()
            try:
                result = probe()
            except Exception as error:
                if getattr(error, "code", None) not in TRANSIENT_FRAME_ERRORS:
                    raise
                result = None
            _check()
            if result:
                return result
            time.sleep(0.35)
    raise RuntimeError(message)


def _tap(x, y):
    _check()
    # 发出一次点按后由调用处等待画面，不能因输入回执丢失立即重发。
    auto.click_element((x / 1280, y / 720, 0, 0), "crop")


def _list_ready():
    # 列表停在半像素位置时图标会重采样；限制在费用列内匹配，兼容该差异。
    if coords := auto.find_element(f"{IMAGES}/power.png", "image", 0.75, crop=POWER_COLUMN):
        return coords
    return auto.find_element(("进入", "传送"), "text", crop=ENTRY_COLUMN)


def _capture_list():
    return _wait(lambda: auto.take_screenshot(crop=PAGE_CROP), "未取得培养目标列表画面")


def capture_target_page():
    with screenshot_retry_timeout(5):
        return _wait(lambda: auto.take_screenshot(), "未取得培养目标页面截图")[0]


def enter_build_target():
    with limit_input_deadline(time.monotonic() + 40), screenshot_retry_timeout(5):
        screen.change_to("guide3", max_recursion=1)
        coords = _wait(lambda: auto.find_element("培养目标", "text", crop=TARGET_ENTRY), "未能识别培养目标入口")
        _check()
        auto.click_element_with_pos(coords)
        try:
            _wait(_list_ready, "未检测到任何可进入的培养目标副本")
        except FATAL_GAME_ERRORS:
            raise
        except RuntimeError as error:
            log.warning(str(error))
            return False, None
        _check()
        if not drag_to_edge(auto, (750 / 1280, 350 / 720), (750 / 1280, 555 / 720),
                            crop=PAGE_CROP, max_drags=8, duration=0.6, settle=0.4, end_pause=0.2):
            raise RuntimeError("未能返回培养目标列表顶部")
        name = auto.get_single_line_text(crop=TARGET_NAME, max_retries=2, retry_delay=0.3)
        _check()
        return True, name


def _modal():
    # 两种弹窗都用新画面确认关闭按钮，不能仅凭同名物品标题猜测所在页面。
    if not auto.find_element(f"{IMAGES}/drop_modal_panel.png", "image", 0.9,
                             crop=(160 / 1280, 145 / 720, 60 / 1280, 112 / 720)):
        return None
    for path, crop, text_crop in MODALS:
        if coords := auto.find_element(path, "image", 0.8, crop=crop):
            return coords, text_crop
    return None


def _close_modal(coords):
    _check()
    auto.click_element_with_pos(coords)
    _wait(lambda: not _modal(), "材料详情弹窗未关闭")


def _stable_title(crop):
    previous, quiet = None, 0

    def ready():
        nonlocal previous, quiet
        frame, _, _ = auto.take_screenshot(crop=crop)
        quiet = quiet + 1 if previous is not None and changed_ratio(previous, frame) <= 0.005 else 0
        previous = frame.copy()
        return quiet >= 2

    _wait(ready, "掉落物标题在弹窗动画后未稳定", timeout=6)


class _TouchPages:
    PAGE_CROP = PAGE_CROP

    def _iter_scroll_windows(self, crop, capture_items):
        """与 PC 一样用最后一行作翻页锚点，保留重叠，已读副本不重复加入。"""
        seen = set()
        anchor = None
        with limit_input_deadline(time.monotonic() + 300), screenshot_retry_timeout(5):
            try:
                for _ in range(8):
                    _check()
                    frame, _, _ = _capture_list()
                    boundary = 0
                    if anchor is not None:
                        for attempt in range(3):
                            pixels = cv2.cvtColor(np.asarray(frame), cv2.COLOR_RGB2GRAY)
                            matches = cv2.matchTemplate(pixels, anchor, cv2.TM_CCOEFF_NORMED)
                            _, score, _, point = cv2.minMaxLoc(matches)
                            if score >= 0.95:
                                boundary = point[1] + anchor.shape[0]
                                break
                            if attempt == 2:
                                raise RuntimeError("滚动锚点跟踪失败")
                            _check()
                            if not drag_list(auto, (750 / 1280, 350 / 720), (750 / 1280, 390 / 720),
                                             crop=crop, duration=0.5, settle=0.4):
                                raise RuntimeError("培养目标列表拖动后未稳定")
                            frame = auto.screenshot
                    _check()
                    screenshot_pos = auto.screenshot_pos
                    last_pos = None
                    for pos, instance in capture_items(boundary, screenshot_pos):
                        _check()
                        if instance is None:
                            yield None
                            return
                        last_pos = pos
                        if instance not in seen:
                            seen.add(instance)
                            log.info(f"识别到副本: {instance}")
                            yield instance
                    if last_pos is None:
                        if not boundary and _list_ready():
                            raise RuntimeError("未能识别培养目标列表中的副本按钮")
                        return
                    frame, _, _ = _capture_list()
                    top = max(0, int(last_pos[0][1]) - 18)
                    bottom = min(frame.height, int(last_pos[1][1]) + 18)
                    anchor = cv2.cvtColor(np.asarray(frame.crop((0, top, frame.width, bottom))), cv2.COLOR_RGB2GRAY)
                    _check()
                    if not drag_list(auto, (750 / 1280, 555 / 720), (750 / 1280, 365 / 720),
                                     crop=crop, duration=0.6, settle=0.4, end_pause=0.2):
                        raise RuntimeError("培养目标列表拖动后未稳定")
                raise RuntimeError("培养目标列表超过读取页数上限")
            except Exception as error:
                if isinstance(error, FATAL_GAME_ERRORS) and getattr(error, "code", None) not in TRANSIENT_FRAME_ERRORS:
                    raise
                log.warning(f"培养目标读取未完成：{error}")
                yield None


class TouchDefaultHandler(_TouchPages, DefaultHandler):
    def _capture_items_in_window(self, paging_boundary_y, screenshot_pos):
        for attempt in range(3):
            auto.perform_ocr()
            positions = [auto.calculate_text_position(box, True) for box, (text, _) in auto.ocr_result
                         if text in ("进入", "传送") and box[0][1] > paging_boundary_y]
            if positions:
                break
            if attempt < 2:
                _check()
                time.sleep(0.35)
                _capture_list()
        for pos in sorted(positions, key=lambda p: p[0][1]):
            self._open_instance(pos, screenshot_pos)
            instance = self._get_instance_info()
            if instance is None:
                raise RuntimeError("未能获得副本信息")
            self._exit_instance(instance[0])
            yield pos, instance

    @staticmethod
    def _open_instance(pos, screenshot_pos):
        from tasks.touch.power import DIALOG, DIALOG_CONFIRM

        left, top, _, _ = screenshot_pos
        x1, y1 = left + pos[0][0] - 12, top + pos[0][1] - 12
        x2, y2 = left + pos[1][0] + 12, top + pos[1][1] + 12
        button_crop = (x1 / 1280, y1 / 720, (x2 - x1) / 1280, (y2 - y1) / 720)
        taps, retry_at, confirmed = 0, 0, False

        def ready():
            nonlocal taps, retry_at, confirmed
            if auto.find_element(("挑战", "开始挑战"), "text", crop=CHALLENGE):
                return True
            if not confirmed and auto.find_element(("是否传送", "是否切换", "不再弹出"), "text",
                                                   include=True, crop=DIALOG):
                coords = auto.find_element("确认", "text", crop=DIALOG_CONFIRM)
                _check()
                if coords:
                    auto.click_element_with_pos(coords)
                    confirmed = True
            # 返回列表的动画可能仍在吞触摸。等回执后，只在新画面仍有原按钮时补一次。
            # 此处直接复核原行按钮，费用图标的重采样不能阻止已确认目标的点按。
            if taps < 2 and time.monotonic() >= retry_at:
                coords = auto.find_element(("进入", "传送"), "text", crop=button_crop)
                _check()
                if coords:
                    auto.click_element_with_pos(coords)
                    taps += 1
                    retry_at = time.monotonic() + 4
            return False

        _wait(ready, "未能进入培养目标副本详情", timeout=90)

    @staticmethod
    def _get_instance_info():
        # 饰品页左上有「差分宇宙 / 位面饰品提取」两行，不能作为单行读取。
        if auto.find_element("饰品提取", "text", include=True, crop=INSTANCE_HEADER):
            title = auto.get_single_line_text(crop=ORNAMENT_TITLE, max_retries=3, retry_delay=0.3) or ""
            return "饰品提取", re.sub(r"[|｜·]?\s*难度.*$", "", title).strip()
        kind = auto.get_single_line_text(crop=INSTANCE_TYPE, max_retries=3, retry_delay=0.3) or ""
        title = auto.get_single_line_text(crop=INSTANCE_TITLE, max_retries=3, retry_delay=0.3) or ""
        parts = re.split(r"[·•]", title, maxsplit=1)
        if len(parts) != 2:
            return None
        name, title_kind = (part.strip() for part in parts)
        if "拟造花萼" in kind:
            kind = "拟造花萼（赤）" if "赤" in title_kind else "拟造花萼（金）"
            if "赤" in title_kind:
                name = TouchDefaultHandler._calyx_location()
        return kind.strip(), name

    @staticmethod
    def _calyx_location():
        # 和 PC 一样打开掉落材料，从获取途径读取地点，以区分同名赤萼。
        for x in (845, 921):
            _tap(x, 421)
            coords, _ = _wait(_modal, "未找到赤萼材料详情")
            try:
                for page in range(3):
                    _check()
                    if auto.find_element("拟造花萼", "text", include=True, crop=MATERIAL_BODY):
                        lines = [text for _, (text, _) in auto.ocr_result if "拟造花萼" in text]
                        for text in lines:
                            if match := re.search(r"[【（(](.+?)[】）)]", text):
                                return match.group(1)
                    if page < 2:
                        _check()
                        if not drag_list(auto, (930 / 1280, 480 / 720), (930 / 1280, 315 / 720),
                                         crop=MATERIAL_BODY, duration=0.5, settle=0.4):
                            break
            finally:
                _close_modal(coords)
        return None

    @staticmethod
    def _exit_instance(instance_type):
        # 先等待挑战页；同一位置在材料详情里也有关闭按钮。
        _wait(lambda: auto.find_element(("挑战", "开始挑战"), "text", crop=CHALLENGE), "未能回到副本详情")
        _tap(1230, 36)
        _wait(_list_ready, "未能返回培养目标列表", timeout=20)
        screen.current_screen = "guide3"
        return True


class TouchDropHandler(_TouchPages, DropHandler):
    def read_drop_name(self, crop):
        _stable_title(crop)
        name = auto.get_single_line_text(crop=crop, max_retries=3, retry_delay=0.3)
        known = {drop for _, _, drop in self._instance_drops}
        reading = {"original": name, "text": name, "name": name, "method": "ocr", "candidates": []}
        self.last_drop_reading = reading
        if name in known:
            return name
        # 720p 的「獠」等细笔画易被识别成别字，仅在原文不属于掉落物目录时放大复核。
        frame = auto.screenshot.copy()
        for factor in (2, 3):
            _check()
            enlarged = frame.resize((frame.width * factor, frame.height * factor), Image.Resampling.BICUBIC)
            result = ocr.recognize_single_line(np.asarray(enlarged))
            _check()
            if result:
                reading["candidates"].append({"text": result[0], "confidence": result[1], "scale": factor})
            if result and result[0] in known:
                reading.update(text=result[0], name=result[0])
                return result[0]
        # 两次放大仍稳定混淆同一个生僻字时，只接受整个掉落物目录中的唯一近似名称。
        candidates = reading["candidates"]
        if len(candidates) == 2 and candidates[0]["text"] == candidates[1]["text"]:
            text = candidates[0]["text"]
            ranked = sorted(((self._similarity(text, drop), drop) for drop in known), reverse=True)
            # 模型可能直接漏掉生僻的首尾字；至少保留三个字且只缺一个字时检查完整名称。
            completions = [drop for drop in known if len(text) >= 3 and len(drop) == len(text) + 1
                           and (drop.endswith(text) or drop.startswith(text))]
            complete = len(completions) == 1 and ranked and ranked[0][1] == completions[0]
            if (ranked and (ranked[0][0] >= 0.85 or complete)
                    and (len(ranked) == 1 or ranked[0][0] - ranked[1][0] >= 0.1)):
                reading.update(text=text, name=ranked[0][1], method="unique_vocabulary")
                log.debug(f"掉落物文字校正：{text} -> {ranked[0][1]}")
                return ranked[0][1]
        return name

    def _capture_items_in_window(self, paging_boundary_y, screenshot_pos):
        for attempt in range(3):
            _check()
            positions = auto.find_image_with_multiple_targets(f"{IMAGES}/power.png", 0.75, None, relative=True)
            if positions:
                break
            if attempt < 2:
                time.sleep(0.35)
                _capture_list()
        positions = sorted((pos for pos in positions if 425 <= pos[0][0] <= 465 and pos[0][1] > paging_boundary_y),
                           key=lambda pos: pos[0][1])
        _, top, _, _ = screenshot_pos
        for pos in positions:
            _check()
            y = top + (pos[0][1] + pos[1][1]) / 2
            # 物品在同一行的左端，避开右侧进入与快速领取按钮。
            _tap(494, y)
            coords, text_crop = _wait(_modal, "未找到培养目标掉落物详情")
            try:
                name = self.read_drop_name(text_crop)
                instance = self._match_instance(name) if name else None
            finally:
                _close_modal(coords)
            _wait(_list_ready, "未能返回培养目标列表")
            yield pos, (instance[0], instance[1]) if instance else None
