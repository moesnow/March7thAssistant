"""差分宇宙的可选决策适配器，所有识别和点击仍复用小助手。"""

import time

from utils.agent_decision import DecisionCancelled, request_decision
from utils.pause import PauseInterrupted


TITLE_CROP = (96 / 1920, 63 / 1080, 142 / 1920, 34 / 1080)


def text_candidates(ocr_result, image_size, area):
    """将选择区域内的 OCR 文本转换为可点击锚点，兼容两张/三张卡片布局。

    同一卡片可能有多个文本锚点，避免额外维护卡片布局识别模板。
    坐标只由识别结果产生，外部程序不能返回任意坐标。
    """
    width, height = image_size
    candidates = []
    for box, (text, confidence) in ocr_result:
        if not isinstance(text, str) or not text.strip() or len(text.strip()) > 1000 or confidence < 0.7:
            continue
        left, right = min(p[0] for p in box) / width, max(p[0] for p in box) / width
        top, bottom = min(p[1] for p in box) / height, max(p[1] for p in box) / height
        if not 0 <= left < right <= 1 or not 0 <= top < bottom <= 1:
            continue
        bounds = [area[0] + left * area[2], area[1] + top * area[3],
                  (right - left) * area[2], (bottom - top) * area[3]]
        candidates.append({"id": f"text-{len(candidates) + 1}", "text": text.strip(), "bounds": bounds})
    return candidates[:80]


def same_choices(previous, current):
    """重抽会保留部分相同文字；同时核对整组选项，容忍 OCR 顺序和小幅定位变化。"""
    remaining = list(current)
    if len(previous) != len(remaining):
        return False
    for old in previous:
        match = next((item for item in remaining if item["text"] == old["text"]
                      and all(abs(a - b) <= .015 for a, b in zip(item["bounds"], old["bounds"]))), None)
        if match is None:
            return False
        remaining.remove(match)
    return True


class DivergentDecision:
    def __init__(self, auto, cfg, log, pause):
        self.auto, self.cfg, self.log, self.pause = auto, cfg, log, pause
        self.history = []

    def choose(self, kind, title, area, confirm, stage):
        """True 表示本轮已处理或界面失效；False 才交回原策略。"""
        generation = self.pause.generation
        try:
            with self.pause.guard_generation(generation):
                return self._choose(kind, title, area, confirm, stage, generation)
        except (DecisionCancelled, PauseInterrupted):
            self.pause.checkpoint()
            return True  # 恢复后重新识别，不补发暂停前的选择或确认。

    def _checkpoint(self, generation):
        self.pause.checkpoint()
        if self.pause.generation != generation:
            raise PauseInterrupted()

    def _observe(self, area):
        self.auto.take_screenshot(area)
        self.auto.perform_ocr()
        return text_candidates(self.auto.ocr_result, self.auto.screenshot.size, area)

    def _choose(self, kind, title, area, confirm, stage, generation):
        self._checkpoint(generation)
        # 与原选择流程相同，等待卡片展开，避免只识别到已出现的标题。
        time.sleep(2)
        self._checkpoint(generation)
        candidates = self._observe(area)
        if not candidates:
            self.log.warning("外部决策未识别到候选文本，使用原有策略")
            return not bool(self.auto.find_element(title, "text", crop=TITLE_CROP, include=False))
        self.log.info(f"等待外部决策：{kind}，{len(candidates)} 个文本锚点")
        request = {
            "task": "divergent", "kind": kind, "stage": stage,
            "context": str(self.cfg.get_value("divergent_decision_context", ""))[:8000],
            "candidates": candidates, "history": self.history[-20:],
        }
        try:
            selected_id = request_decision(
                self.cfg.get_value("divergent_decision_command", []),
                self.cfg.get_value("divergent_decision_timeout", 60), request,
                cancelled=lambda: self.pause.generation != generation or self.pause.is_paused() or self.pause.stop_requested,
            )
        except (OSError, ValueError, TimeoutError) as error:
            self.log.warning(f"外部决策未返回有效结果（{type(error).__name__}），使用原有策略")
            selected_id = None
        self._checkpoint(generation)
        # 等待期间可能重抽、手动换页；不能只依赖标题或某段共用描述。
        if not self.auto.find_element(title, "text", crop=TITLE_CROP, include=False):
            return True
        if not same_choices(candidates, self._observe(area)):
            self.log.info("外部决策等待期间候选项已变化，重新识别")
            return True
        self._checkpoint(generation)
        if selected_id is None:
            return False
        selected = next(candidate for candidate in candidates if candidate["id"] == selected_id)
        bounds = selected["bounds"]
        # 为 OCR 边缘留少量余量，仍限制在当前选择区域内。
        crop = (max(area[0], bounds[0] - .004), max(area[1], bounds[1] - .004),
                min(area[0] + area[2], bounds[0] + bounds[2] + .004) - max(area[0], bounds[0] - .004),
                min(area[1] + area[3], bounds[1] + bounds[3] + .004) - max(area[1], bounds[1] - .004))
        if not self.auto.click_element(selected["text"], "text", crop=crop, include=False):
            return True
        # 复用原流程的选择动画与确认等待，低性能/后台模式同样适用。
        time.sleep(1)
        self._checkpoint(generation)
        if not self.auto.click_element(confirm[0], "text", crop=confirm[1], include=True, max_retries=10):
            raise RuntimeError("外部决策选项已点击，但未能确认选择")
        time.sleep(2)
        self._checkpoint(generation)
        if kind == "station":
            if self.auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9):
                time.sleep(2)
                self._checkpoint(generation)
        self.history.append({"kind": kind, "text": selected["text"]})
        self.log.info(f"外部决策：{kind} → {selected['text']}")
        return True
