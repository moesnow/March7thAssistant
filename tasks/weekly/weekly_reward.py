"""积分奖励页共用的领取、助燃券清理与到账核对。"""

from dataclasses import dataclass
from enum import Enum
from functools import cached_property, lru_cache
from pathlib import Path
import re
import time

import cv2
import numpy as np
from PIL import Image

from module.automation import auto
from module.automation.automation import screenshot_retry_timeout
from module.automation.background_input import input_wait_limit
from module.automation.input_base import observe_input_dispatch
from module.logger import log
from tasks.base.task_steps import FATAL_GAME_ERRORS
from utils.pause import pause_ctl
from utils.screenshot_util import save_error_screenshot


WEEKLY_TITLE = (55, 302, 260, 364)
WEEKLY_SCORE = (135, 710, 415, 780)
WEEKLY_CLAIM = (1450, 686, 1840, 765)
REWARD_DISMISS = (535, 625, 1390, 1065)


class RewardPage(Enum):
    UNKNOWN = "未知页面"
    POINTS = "积分奖励"
    RECEIPT = "奖励展示"
    LIMIT = "助燃券容量提示"
    CLEANUP_CONFIRM = "物品销毁确认"
    HOME = "玩法首页"


class WeeklyRewardError(RuntimeError):
    """周期奖励尚未确认处理完毕。"""


@dataclass
class RewardState:
    claim_sent: bool = False
    claim_key: object = None
    cleanup_sent: bool = False
    confirm_sent: bool = False
    retry_sent: bool = False
    receipt: object = None
    notified: bool = False


def fuel_ticket_limit(frame):
    return "背包内助燃券持有数量已达上限" in "".join(
        label.text for label in frame.texts((385, 323, 1540, 650)))


def cleanup_confirmation(frame):
    return ("此次销毁将无物品返还" in "".join(label.text for label in frame.texts((650, 382, 1280, 458)))
            and frame.has("已销毁的物品无法复原", area=(700, 650, 1230, 718), contains=True)
            and frame.find("取消", area=(552, 720, 930, 795)) is not None
            and frame.find("确认", area=(990, 720, 1360, 795)) is not None)


def reward_close(frame):
    if label := frame.find("点击空白处关闭", area=REWARD_DISMISS, contains=True):
        return label.point
    if frame.has("获得物品", "获得奖励", "获得道具", area=(570, 105, 1350, 610)):
        return frame.match("zh_CN/base/click_close.png", REWARD_DISMISS, 0.80)
    return None


def cleanup_button(frame):
    label = frame.find("清理", area=(538, 659, 960, 756))
    return label.point if label else None


def confirmation_button(frame):
    label = frame.find("确认", area=(990, 720, 1360, 795))
    return label.point if label else None


def claim_button_visible(frame):
    text = "".join(label.text for label in sorted(frame.texts(WEEKLY_CLAIM), key=lambda item: item.point[0]))
    patch = frame.crop(WEEKLY_CLAIM)
    yellow = (patch[:, :, 0] > 204) & (patch[:, :, 1] > 141) & (patch[:, :, 2] < 140)
    return "键领取" in text and float(yellow.mean()) > 0.18


def claim_available(frame):
    if frame.claim_button_visible():
        return True
    score = frame.ratio(WEEKLY_SCORE)
    if score is None:
        return None
    tiers = sorted((label.point[0], int(label.text)) for label in frame.texts((72, 562, 1834, 624))
                   if re.fullmatch(r"\d{1,7}", label.text))
    if len(tiers) < 2 or tiers[0][0] > 230 or tiers[-1][0] < 1600 or tiers[-1][1] != score[1]:
        return None
    gaps = np.diff([x for x, _ in tiers])
    if gaps.max() > 1.45 * np.median(gaps) or any(left[1] >= right[1] for left, right in zip(tiers, tiers[1:])):
        return None
    if all(frame.match("screen/currency_wars/s2_points_claimed.png", (x - 40, 481, x + 40, 553), 0.88)
           for x, threshold in tiers if threshold <= score[0]):
        return False
    return None


def collect_weekly_reward(frame, *, state, available, kind, button, credited, remaining, click_to,
                          claim_key=None, on_receipt=None):
    """三个入口共用流程；导航和输入由调用方管理，重试不越过其时间与输入预算。"""
    def mark(field):
        def sent():
            setattr(state, field, True)
            if field == "claim_sent":
                state.claim_key = claim_key
        return sent

    def received(current):
        return kind(current) in (RewardPage.RECEIPT, RewardPage.LIMIT) or credited(current)

    def resolve_limit(current):
        if kind(current) != RewardPage.LIMIT:
            return current
        if state.cleanup_sent:
            raise WeeklyRewardError("清理助燃券后满额提示仍未消失")
        log.info("助燃券持有数量已达上限，尝试清理后继续领取周期奖励")
        current = click_to(
            current, lambda f: button(f, "cleanup"),
            lambda f: kind(f) in (RewardPage.POINTS, RewardPage.RECEIPT, RewardPage.CLEANUP_CONFIRM),
            "助燃券已达上限，未能清理后继续领取周期奖励", seconds=10, attempts=1,
            before_click=mark("cleanup_sent"),
        )
        if kind(current) == RewardPage.CLEANUP_CONFIRM:
            current = click_to(
                current, lambda f: button(f, "confirm"),
                lambda f: kind(f) in (RewardPage.POINTS, RewardPage.RECEIPT),
                "助燃券销毁确认后未返回周期奖励", seconds=10, attempts=1,
                before_click=mark("confirm_sent"),
            )
        if kind(current) == RewardPage.POINTS:
            current = click_to(
                current, lambda f: button(f, "claim"), received,
                "清理助燃券后未确认领取周期奖励", seconds=10, attempts=1,
                before_click=mark("retry_sent"),
            )
        if kind(current) == RewardPage.LIMIT:
            raise WeeklyRewardError("清理助燃券后满额提示仍未消失")
        return current

    if available:
        if state.claim_sent:
            raise WeeklyRewardError("上次领奖尚待核对，保留当前奖励")
        frame = click_to(frame, lambda f: button(f, "claim"), received,
                         "周期积分奖励未确认领取", seconds=12, attempts=1,
                         before_click=mark("claim_sent"))
        frame = resolve_limit(frame)
        state.receipt = frame.image
    elif state.claim_sent and state.claim_key == claim_key:
        state.receipt = state.receipt if state.receipt is not None else frame.image

    claimed = state.receipt is not None
    if claimed and not state.notified and on_receipt is not None:
        state.notified = True
        on_receipt(state.receipt)

    # 普通奖励展示之后还可能出现助燃券提示，清理后最多再关闭一次奖励展示。
    for _ in range(2):
        if kind(frame) != RewardPage.RECEIPT:
            break
        frame = click_to(
            frame, lambda f: button(f, "close"),
            lambda f: kind(f) in (RewardPage.POINTS, RewardPage.LIMIT, RewardPage.HOME),
            "领奖后未确认返回积分页", seconds=12, attempts=2,
        )
        frame = resolve_limit(frame)
    pending = claimed and kind(frame) == RewardPage.POINTS and remaining(frame)
    return frame, claimed, pending


@dataclass(frozen=True)
class _Label:
    text: str
    point: tuple[int, int]


@lru_cache(maxsize=8)
def _template(path):
    return np.asarray(Image.open(Path("assets/images") / path).convert("RGB"))


class RewardFrame:
    """差分宇宙使用相同的 PC 积分面板；坐标统一到 1920×1080。"""
    def __init__(self, image, results):
        self.image = image
        self.labels = tuple(_Label(
            re.sub(r"\s", "", value).replace("／", "/"),
            (round(sum(p[0] for p in box) / len(box) * 1920 / image.width),
             round(sum(p[1] for p in box) / len(box) * 1080 / image.height)),
        ) for box, (value, confidence) in results if box is not None and len(box) and confidence >= 0.52)

    @cached_property
    def pixels(self):
        return np.asarray(self.image.convert("RGB").resize((1920, 1080)))

    def crop(self, area):
        x1, y1, x2, y2 = area
        return self.pixels[y1:y2, x1:x2]

    def texts(self, area):
        x1, y1, x2, y2 = area
        return tuple(label for label in self.labels if x1 <= label.point[0] < x2 and y1 <= label.point[1] < y2)

    def find(self, *targets, area=(0, 0, 1920, 1080), contains=False):
        found = [label for label in self.texts(area)
                 if label.text in targets or contains and any(target in label.text for target in targets)]
        return found[0] if len(found) == 1 else None

    def has(self, *targets, area=(0, 0, 1920, 1080), contains=False):
        return any(label.text in targets or contains and any(target in label.text for target in targets)
                   for label in self.texts(area))

    def ratio(self, area):
        values = {label.text for label in self.texts(area) if re.fullmatch(r"\d{1,7}/\d{1,7}", label.text)}
        if len(values) == 1:
            left, right = map(int, values.pop().split("/"))
            if 0 <= left <= right and right > 0:
                return left, right
        return None

    def match(self, path, area, threshold=0.88):
        source, target = self.crop(area), _template(path)
        height, width = target.shape[:2]
        if source.shape[0] >= height and source.shape[1] >= width:
            _, score, _, (x, y) = cv2.minMaxLoc(cv2.matchTemplate(source, target, cv2.TM_CCOEFF_NORMED))
            if score >= threshold:
                return area[0] + x + width // 2, area[1] + y + height // 2
        return None

    @cached_property
    def page(self):
        if fuel_ticket_limit(self):
            return RewardPage.LIMIT
        if cleanup_confirmation(self):
            return RewardPage.CLEANUP_CONFIRM
        if reward_close(self):
            return RewardPage.RECEIPT
        if self.has("积分奖励", area=WEEKLY_TITLE):
            return RewardPage.POINTS
        return RewardPage.UNKNOWN

    @cached_property
    def available(self):
        return claim_available(self)

    def claim_button_visible(self):
        return claim_button_visible(self)

    def button(self, action):
        if action == "claim" and self.page == RewardPage.POINTS and self.available is True:
            return 1640, 728
        if action == "cleanup" and self.page == RewardPage.LIMIT:
            return cleanup_button(self)
        if action == "confirm" and self.page == RewardPage.CLEANUP_CONFIRM:
            return confirmation_button(self)
        if action == "close" and self.page == RewardPage.RECEIPT:
            return reward_close(self)
        return None


class _RewardControls:
    def __init__(self, timeout):
        self.deadline = time.monotonic() + timeout

    def check(self):
        pause_ctl.checkpoint()
        if time.monotonic() >= self.deadline:
            raise WeeklyRewardError("周期奖励领取已到达总时限，奖励仍待核对")

    def observe(self):
        self.check()
        with screenshot_retry_timeout(max(0, min(3, self.deadline - time.monotonic()))):
            if not auto.take_screenshot():
                raise WeeklyRewardError("未取得周期奖励的新画面")
            auto.perform_ocr(raise_on_error=True)
        self.check()
        return RewardFrame(auto.screenshot, auto.ocr_result)

    def click_to(self, frame, button, after, message, *, seconds=12, attempts=1, before_click=None):
        end = min(self.deadline, time.monotonic() + seconds)
        sent = 0
        last_sent = None
        previous = None
        while time.monotonic() < min(self.deadline, end + (4 if sent else 0)):
            self.check()
            try:
                current = self.observe()
                if after(current):
                    return current
                target = button(current) if frame is not None and current.page == frame.page else None
                if (target is not None and target == previous and sent < attempts and time.monotonic() < end
                        and (last_sent is None or time.monotonic() - last_sent >= 2.2)):
                    x, y = target
                    pos = auto.find_element((x / 1920, y / 1080, 0, 0), "crop",
                                            take_screenshot=False, need_ocr=False)
                    self.check()
                    if pos is not None and time.monotonic() < end:
                        dispatched = False

                        def mark_sent(_now=None):
                            nonlocal sent, last_sent, dispatched
                            if not dispatched:
                                dispatched = True
                                sent += 1
                                last_sent = time.monotonic()
                                if before_click is not None:
                                    before_click()

                        with input_wait_limit(end - time.monotonic(), deadline=end):
                            if getattr(getattr(auto, "input_handler", None), "reports_dispatch", False) is True:
                                with observe_input_dispatch(mark_sent, deadline=end):
                                    auto.click_element_with_pos(pos)
                            else:
                                mark_sent()
                                auto.click_element_with_pos(pos)
                previous = target
            except FATAL_GAME_ERRORS as error:
                if not getattr(error, "frame_only", False):
                    raise
                log.debug(f"周期奖励截图暂时不可用：{error}")
                previous = None
            except Exception as error:
                log.debug(f"周期奖励暂未确认目标或回执：{error}")
                previous = None
            time.sleep(0.35)
        self.check()
        raise WeeklyRewardError(f"{message}（已尝试 {sent} 次）")


def claim_weekly_reward(*, on_receipt=None, timeout=75):
    """积分奖励页打开后调用；成功时已关闭奖励展示，停留在积分页。"""
    controls = _RewardControls(timeout)
    state = RewardState()
    try:
        frame = controls.click_to(
            None, lambda f: None,
            lambda f: f.page == RewardPage.POINTS and f.available is not None,
            "周期积分或领奖状态未识别", seconds=7, attempts=0,
        )
        score = frame.ratio(WEEKLY_SCORE)

        def button(current, action):
            if action == "claim" and current.ratio(WEEKLY_SCORE) != score:
                return None
            return current.button(action)

        _, claimed, pending = collect_weekly_reward(
            frame, state=state, available=frame.available, kind=lambda f: f.page,
            button=button, click_to=controls.click_to,
            credited=lambda f: f.page == RewardPage.POINTS and f.available is False
            and f.ratio(WEEKLY_SCORE) == score,
            remaining=claim_button_visible, claim_key=score, on_receipt=on_receipt,
        )
        if pending:
            raise WeeklyRewardError("周期奖励仍有可领取档位")
        return claimed
    except FATAL_GAME_ERRORS:
        raise
    except Exception as error:
        log.warning(f"周期奖励领取仍待核对：{error}")
        save_error_screenshot(log, propagate_errors=FATAL_GAME_ERRORS)
        return False
