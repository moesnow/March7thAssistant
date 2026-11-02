"""差分宇宙的可选决策适配器，所有识别和点击仍复用小助手。"""

import time

from utils.agent_decision import DecisionCancelled, request_decision


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


class DivergentDecision:
    def __init__(self, auto, cfg, log, pause):
        self.auto, self.cfg, self.log, self.pause = auto, cfg, log, pause
        self.history = []

    def choose(self, kind, title, area, confirm, stage):
        """True 表示本轮已处理或界面失效；False 才交回原策略。"""
        # 与原选择流程相同，等待卡片展开，避免只识别到已出现的标题。
        time.sleep(2)
        self.auto.take_screenshot(area)
        self.auto.perform_ocr()
        candidates = text_candidates(self.auto.ocr_result, self.auto.screenshot.size, area)
        if not candidates:
            self.log.warning("外部决策未识别到候选文本，使用原有策略")
            return False
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
                cancelled=lambda: self.pause.is_paused() or self.pause.stop_requested,
            )
        except DecisionCancelled:
            self.pause.checkpoint()
            return True  # 恢复后交回主循环重新识别，不采纳暂停前的选择。
        except (OSError, ValueError, TimeoutError):
            self.log.warning("外部决策未返回有效结果，使用原有策略")
            self.pause.checkpoint()
            return not bool(self.auto.find_element(title, "text", crop=TITLE_CROP, include=False))
        if selected_id is None:
            self.pause.checkpoint()
            return not bool(self.auto.find_element(title, "text", crop=TITLE_CROP, include=False))
        self.pause.checkpoint()
        selected = next(candidate for candidate in candidates if candidate["id"] == selected_id)
        # 等待模型期间用户可能换了界面；必须重新识别标题和原位置的文本。
        if not self.auto.find_element(title, "text", crop=TITLE_CROP, include=False):
            return True
        bounds = selected["bounds"]
        # 为 OCR 边缘留少量余量，仍限制在当前选择区域内。
        crop = (max(area[0], bounds[0] - .004), max(area[1], bounds[1] - .004),
                min(area[0] + area[2], bounds[0] + bounds[2] + .004) - max(area[0], bounds[0] - .004),
                min(area[1] + area[3], bounds[1] + bounds[3] + .004) - max(area[1], bounds[1] - .004))
        if not self.auto.click_element(selected["text"], "text", crop=crop, include=False):
            return True
        if not self.auto.click_element(confirm[0], "text", crop=confirm[1], include=False, max_retries=3):
            raise RuntimeError("外部决策选项已点击，但未能确认选择")
        if kind == "station":
            self.auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9)
        self.history.append({"kind": kind, "text": selected["text"]})
        self.log.info(f"外部决策：{kind} → {selected['text']}")
        return True
