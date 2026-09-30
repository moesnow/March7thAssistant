"""Weekly relic cleanup using the game's smart discard and quick select UI."""

import re

from module.automation import auto
from module.config import cfg
from module.logger import log
from module.screen import screen
from .relicset import Relicset


def _crop(x1, y1, x2, y2):
    """Convert a 1920x1080 reference rectangle to Automation's crop format."""
    return (x1 / 1920, y1 / 1080, (x2 - x1) / 1920, (y2 - y1) / 1080)


class WeeklyRelicCleanup:
    PROTECTION_ON = "./assets/images/share/relicset/discard_protection_on.png"
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
    def _protection_on():
        return bool(auto.find_element(WeeklyRelicCleanup.PROTECTION_ON, "image", 0.88,
                                      max_retries=2, crop=_crop(1375, 640, 1515, 725),
                                      scale_range=(0.6, 1.05)))

    @staticmethod
    def _ensure_protection():
        if WeeklyRelicCleanup._protection_on():
            return
        if not WeeklyRelicCleanup._visible("弃置保护", _crop(1295, 655, 1415, 704)):
            raise RuntimeError("无法确认弃置保护控件")
        # Only the switch is located by its fixed position; all text targets use OCR.
        if not auto.click_element(_crop(1415, 665, 1475, 698), "crop"):
            raise RuntimeError("无法开启弃置保护")
        if not WeeklyRelicCleanup._protection_on():
            raise RuntimeError("无法确认弃置保护已开启")

    @staticmethod
    def _mark_smart_discard():
        cls = WeeklyRelicCleanup
        cls._click("智能弃置", _crop(570, 945, 805, 1030))
        if not cls._visible("待弃置遗器", _crop(425, 295, 615, 345)):
            raise RuntimeError("未进入智能弃置弹窗")

        cls._click("全部清除", _crop(570, 725, 935, 795))
        cls._click("不匹配任意推荐角色", _crop(465, 450, 950, 510))
        cls._click("0次", _crop(465, 570, 950, 630))
        cls._ensure_protection()

        count = cls._count(_crop(605, 302, 830, 350))
        if count == 0:
            log.info("智能弃置没有找到新的五星遗器")
            auto.press_key("esc")
            return 0

        cls._click("确认", _crop(985, 725, 1355, 795))
        if not cls._visible("批量弃置", _crop(755, 310, 930, 360), retries=5):
            raise RuntimeError("未出现批量弃置确认弹窗")
        # The action button itself identifies the selected mode. Clicking an
        # already selected radio could deselect it, as in the smart dialog.
        if not cls._visible("确认弃置", _crop(985, 790, 1355, 855)):
            raise RuntimeError("批量弃置模式未选中")
        cls._click("确认弃置", _crop(985, 790, 1355, 855))
        if not cls._visible("遗器分解", cls.BREAK_SCREEN, retries=5):
            raise RuntimeError("确认弃置后未返回遗器分解页")
        log.info(f"智能弃置已标记 {count} 件遗器")
        return count

    @staticmethod
    def _select_for_salvage(expected_selected, include_discarded):
        cls = WeeklyRelicCleanup
        if not cls._visible("遗器分解", cls.BREAK_SCREEN, retries=5):
            raise RuntimeError("无法确认遗器分解页")
        selected = cls._count(_crop(610, 875, 830, 930))
        if selected != expected_selected:
            raise RuntimeError(
                f"智能弃置后已选数量异常：预计 {expected_selected}，实际 {selected}，停止清理"
            )

        cls._click("快速选择", _crop(1200, 950, 1430, 1030))
        if not cls._visible("快速选择", _crop(425, 295, 625, 350)):
            raise RuntimeError("未进入快速选择弹窗")
        if include_discarded:
            cls._click("全选已弃置", _crop(460, 415, 955, 475))
        cls._click("4星及以下", _crop(460, 590, 955, 650))
        cls._click("确认", _crop(775, 725, 1145, 795))
        if not cls._visible("遗器分解", cls.BREAK_SCREEN, retries=5):
            raise RuntimeError("快速选择后未返回遗器分解页")
        selected = cls._count(_crop(610, 875, 830, 930))
        if selected < expected_selected:
            raise RuntimeError(
                f"快速选择后已选数量少于智能弃置数量：{selected} < {expected_selected}，停止清理"
            )
        return selected

    @staticmethod
    def run():
        """Drain bounded 500-item batches; never complete on an uncertain UI."""
        smart_discard = cfg.get_value("weekly_relic_smart_discard_enable", False)
        log.hr("每周清理遗器", 2)
        try:
            screen.change_to("bag_relicset")
            WeeklyRelicCleanup._click("分解", _crop(1130, 945, 1390, 1030))
            if not WeeklyRelicCleanup._visible("遗器分解", WeeklyRelicCleanup.BREAK_SCREEN, retries=5):
                raise RuntimeError("无法进入遗器分解页")

            for batch in range(WeeklyRelicCleanup.MAX_BATCHES):
                if WeeklyRelicCleanup._count(_crop(610, 875, 830, 930)) != 0:
                    raise RuntimeError("分解页已有其他选中的遗器，停止清理")
                marked_count = WeeklyRelicCleanup._mark_smart_discard() if smart_discard else 0
                count = WeeklyRelicCleanup._select_for_salvage(marked_count, smart_discard)
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
