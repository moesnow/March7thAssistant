"""Scheduled cleanup of four-star and lower relics."""

import re

from module.automation import auto
from module.logger import log
from module.screen import screen
from .relicset import Relicset


def _crop(x1, y1, x2, y2):
    """Convert a 1920x1080 reference rectangle to Automation's crop format."""
    return (x1 / 1920, y1 / 1080, (x2 - x1) / 1920, (y2 - y1) / 1080)


class WeeklyRelicCleanup:
    BREAK_SCREEN = _crop(75, 35, 300, 105)
    MAX_BATCHES = 7  # 3000-slot inventory, plus a final empty check

    @staticmethod
    def _visible(text, crop, retries=2):
        return bool(auto.find_element(text, "text", max_retries=retries,
                                      crop=crop, include=True))

    @staticmethod
    def _click(text, crop, retries=5):
        if not auto.click_element(text, "text", max_retries=retries,
                                  crop=crop, include=True):
            raise RuntimeError(f"未找到或无法点击：{text}")

    @staticmethod
    def _count(crop):
        label = auto.get_single_line_text(crop=crop, max_retries=3, retry_delay=0.5)
        match = re.search(r"(\d+)\s*/\s*500", label or "")
        if not match:
            raise RuntimeError(f"无法确认已选遗器数量：{label!r}")
        return int(match.group(1))

    @staticmethod
    def _select_for_salvage():
        cls = WeeklyRelicCleanup
        if not cls._visible("遗器分解", cls.BREAK_SCREEN, retries=5):
            raise RuntimeError("无法确认遗器分解页")
        if cls._count(_crop(610, 875, 830, 930)) != 0:
            raise RuntimeError("分解页已有其他选中的遗器，停止清理")

        cls._click("快速选择", _crop(1200, 950, 1430, 1030))
        if not cls._visible("快速选择", _crop(425, 295, 625, 350)):
            raise RuntimeError("未进入快速选择弹窗")
        cls._click("4星及以下", _crop(460, 590, 955, 650))
        cls._click("确认", _crop(775, 725, 1145, 795))
        if not cls._visible("遗器分解", cls.BREAK_SCREEN, retries=5):
            raise RuntimeError("快速选择后未返回遗器分解页")
        return cls._count(_crop(610, 875, 830, 930))

    @staticmethod
    def run():
        """Drain bounded 500-item batches; never complete on an uncertain UI."""
        log.hr("每周清理遗器", 2)
        try:
            screen.change_to("bag_relicset")
            WeeklyRelicCleanup._click("分解", _crop(1130, 945, 1390, 1030))
            if not WeeklyRelicCleanup._visible("遗器分解", WeeklyRelicCleanup.BREAK_SCREEN, retries=5):
                raise RuntimeError("无法进入遗器分解页")

            for batch in range(WeeklyRelicCleanup.MAX_BATCHES):
                count = WeeklyRelicCleanup._select_for_salvage()
                if not count:
                    log.info("没有剩余可分解的遗器")
                    return True
                if not Relicset.start_break_down_relicset(use_ocr=True):
                    raise RuntimeError("遗器分解未完成")
                log.info(f"第 {batch + 1} 批分解了 {count} 件遗器")
                if count < 500:
                    return True
            raise RuntimeError("连续七批仍有待分解遗器，停止清理")
        finally:
            screen.change_to("main")
