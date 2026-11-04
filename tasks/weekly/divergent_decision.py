"""差分宇宙的可选决策适配器，所有识别和点击仍复用小助手。"""

import time

from utils.agent_decision import DecisionCancelled, request_action as request_decision
from utils.pause import PauseInterrupted
from utils.agent_session import AgentSession, decision_mode


TITLE_CROP = (96 / 1920, 63 / 1080, 142 / 1920, 34 / 1080)


def text_candidates(ocr_result, image_size, area, limit=80):
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
    return candidates[:limit]


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
    def __init__(self, auto, cfg, log, pause, context=None, *, session=None):
        self.auto, self.cfg, self.log, self.pause = auto, cfg, log, pause
        # 复用安装路径与队列对象；有效性仍在每个输入卡点实时读取。
        self._session = session if session is not None else AgentSession()
        self.history = []
        self.team_region = None
        from tasks.weekly.divergent_context import DivergentContext
        self.context = context or DivergentContext(auto)

    def capture_context(self, source):
        return self.context.capture(source)

    def prepare(self, team_region=None):
        """在开始对局前给 Agent 一次读取编队/攻略并形成计划的机会。"""
        self.team_region = team_region
        generation = self.pause.generation
        try:
            with self.pause.guard_generation(generation):
                answer = self._exchange("setup", None, (0, 0, 1, 1), None, "准备对局",
                                        [{"id": "continue", "text": "读取完成，开始对局"}], generation)
                self._checkpoint(generation)
                if answer.get("memory"):
                    self.context.memory = answer["memory"]
                self.context.record({"status": "prepared", "answer": answer})
        except (DecisionCancelled, PauseInterrupted):
            self.pause.checkpoint()
        except (OSError, ValueError, TimeoutError) as error:
            self.log.warning(f"Agent 对局准备未完成（{type(error).__name__}），后续仍可读取证据")

    def choose(self, kind, title, area, confirm, stage):
        """True 表示本轮已处理或界面失效；False 才交回原策略。"""
        generation = self.pause.generation
        try:
            with self.pause.guard_generation(generation):
                return self._choose(kind, title, area, confirm, stage, generation)
        except (DecisionCancelled, PauseInterrupted):
            self.pause.checkpoint()
            return True  # 恢复后重新识别，不补发暂停前的选择或确认。

    def _checkpoint(self, generation, answer=None):
        self.pause.checkpoint()
        self._validate_input(generation, answer)

    def _validate_input(self, generation, answer):
        if self.pause.generation != generation:
            raise PauseInterrupted()
        if answer and answer.get("_connection_id") and not self._session.is_current(answer["_connection_id"]):
            raise DecisionCancelled()

    def _input(self, generation, answer, method, *args, **kwargs):
        if answer and answer.get("_connection_id"):
            # 后台输入在等待用户鼠标、重试和实际按下前都有卡点；
            # 在这些卡点重新验证接管，清理时的松键/松鼠标不受阻。
            with self.pause.guard_generation(generation, validate=lambda: self._validate_input(generation, answer)):
                return method(*args, **kwargs)
        return method(*args, **kwargs)

    def _observe(self, area):
        self.auto.take_screenshot(area)
        self.auto.perform_ocr()
        return text_candidates(self.auto.ocr_result, self.auto.screenshot.size, area)

    def _restore_choice(self, title, area, candidates, generation, root_view):
        # 仅回退本会话打开的查看页面；不从原选择页发送 Esc。
        def root_visible(frame):
            header = lambda item: item["bounds"][1] < .25 and len(item["text"]) <= 12 and any(
                word in item["text"] for word in ("攻略", "队伍", "编队", "角色", "祝福", "方程", "奇物"))
            original_headers = [item for item in root_view if header(item)]
            for item in frame["ocr"]:
                if header(item) and not any(same_choices([item], [old]) for old in original_headers):
                    return False
            if title is None:
                return bool(self.auto.find_element("./assets/images/screen/divergent_universe/start.png", "image", .9))
            return bool(self.auto.find_element(title, "text", crop=TITLE_CROP, include=False)) and same_choices(candidates, self._observe(area))
        current = self.context.capture("return_check")
        if root_visible(current):
            return
        for _ in range(5):
            self._checkpoint(generation)
            self.auto.press_key("esc")
            time.sleep(.5)
            self._checkpoint(generation)
            current = self.context.capture("return_result")
            if root_visible(current):
                return
        raise RuntimeError("查看构筑后未能确认返回原选择界面，停止操作并保留现场")

    def _exchange(self, kind, title, area, confirm, stage, candidates, generation):
        timeout = self.cfg.get_value("divergent_decision_timeout", 60)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 300:
            raise ValueError("外部决策超时配置无效")
        deadline = time.monotonic() + timeout
        inspecting = False
        root_view = None
        def restore(expected_generation):
            nonlocal inspecting
            try:
                self._restore_choice(title, area, candidates, expected_generation, root_view)
            except RuntimeError:
                inspecting = False  # 已保留现场，不再重复发送返回操作。
                raise
            inspecting = False
        try:
            for _ in range(12):
                self._checkpoint(generation)
                frame = self.context.capture("inspection" if inspecting else "choice", inspecting)
                if not inspecting:
                    root_view = frame["ocr"]
                    if kind == "setup" and self.team_region is not None:
                        # 复用原 choose_team 已使用的编队区域；仅打开详情，不选择角色。
                        frame["controls"].append({"id": "open-team", "text": "查看当前编队",
                                                  "kind": "region", "bounds": list(self.team_region)})
                request = {
                    "task": "divergent", "kind": kind, "stage": stage,
                    "context": str(self.cfg.get_value("divergent_decision_context", ""))[:8000],
                    "candidates": candidates, "history": self.history[-20:],
                    "build_state": self.context.packet(), "controls": frame["controls"],
                    "current_observation_id": frame["id"], "can_choose": not inspecting,
                    "can_go_back": inspecting,
                    "instructions": "读取队伍、已有构筑和推荐证据，自行取舍；可查看控件、返回，或选择候选。说明理由与参考来源，未知信息不要猜测。",
                }
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("查看与决策总等待超时")
                cancelled = lambda: self.pause.generation != generation or self.pause.is_paused() or self.pause.stop_requested
                if decision_mode(self.cfg) == "connected":
                    answer = self._session.request(min(timeout, remaining), request, cancelled=cancelled)
                else:
                    answer = request_decision(self.cfg.get_value("divergent_decision_command", []), min(timeout, remaining),
                                              request, cancelled=cancelled)
                # 兼容已有只返回 ID 的适配器。
                if answer is None or isinstance(answer, str):
                    answer = {"action": "choose" if answer else "decline", "candidate_id": answer}
                self._checkpoint(generation, answer)
                if answer.get("memory") and answer["action"] != "choose":
                    self.context.memory = answer["memory"]
                action = answer["action"]
                if action in ("choose", "decline"):
                    if inspecting:
                        restore(generation)
                    self.context.record({"status": "proposed", "kind": kind, "stage": stage,
                                         "observation_id": frame["id"], "answer": answer})
                    return answer
                if action == "back":
                    restore(generation)
                    continue
                control = next(item for item in frame["controls"] if item["id"] == answer["control_id"])
                self._checkpoint(generation, answer)
                fresh = self.context.capture("navigation_check", inspecting)
                if not same_choices(frame["ocr"], fresh["ocr"]):
                    continue
                self._checkpoint(generation, answer)
                if control.get("kind") == "scroll":
                    position = self.auto.find_element((.6, .6, .01, .01), "crop")
                    if position:
                        self._input(generation, answer, self.auto.mouse_move, *position[0])
                        self._input(generation, answer, self.auto.mouse_scroll, 5, control["direction"], False)
                        time.sleep(.5)
                    continue
                bounds = control["bounds"]
                self._checkpoint(generation, answer)
                crop = (max(0, bounds[0] - .004), max(0, bounds[1] - .004),
                        min(1 - max(0, bounds[0] - .004), bounds[2] + .008),
                        min(1 - max(0, bounds[1] - .004), bounds[3] + .008))
                if control.get("kind") == "region":
                    opened = self._input(generation, answer, self.auto.click_element, bounds, "crop")
                else:
                    opened = self._input(generation, answer, self.auto.click_element, control["text"], "text", crop=crop, include=False)
                if opened:
                    inspecting = True
                    time.sleep(.7)
            raise TimeoutError("查看步骤已达上限")
        finally:
            if inspecting and not self.pause.stop_requested:
                # 暂停后使用新观察返回，绝不执行暂停前的选择。
                for _ in range(3):
                    self.pause.checkpoint()
                    current = self.pause.generation
                    try:
                        with self.pause.guard_generation(current):
                            restore(current)
                    except PauseInterrupted:
                        continue  # 返回过程中再次暂停，恢复后重新确认页面。
                    break
                else:
                    raise RuntimeError("返回选择页时多次被暂停打断，停止操作并保留现场")

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
        answer = None
        try:
            answer = self._exchange(kind, title, area, confirm, stage, candidates, generation)
            selected_id = answer.get("candidate_id") if answer["action"] == "choose" else None
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
            self.context.record({"status": "fallback", "kind": kind, "stage": stage})
            return False
        selected = next(candidate for candidate in candidates if candidate["id"] == selected_id)
        self._checkpoint(generation, answer)
        bounds = selected["bounds"]
        # 为 OCR 边缘留少量余量，仍限制在当前选择区域内。
        crop = (max(area[0], bounds[0] - .004), max(area[1], bounds[1] - .004),
                min(area[0] + area[2], bounds[0] + bounds[2] + .004) - max(area[0], bounds[0] - .004),
                min(area[1] + area[3], bounds[1] + bounds[3] + .004) - max(area[1], bounds[1] - .004))
        if not self._input(generation, answer, self.auto.click_element, selected["text"], "text", crop=crop, include=False):
            return True
        # 复用原流程的选择动画与确认等待，低性能/后台模式同样适用。
        time.sleep(1)
        self._checkpoint(generation, answer)
        if not self._input(generation, answer, self.auto.click_element, confirm[0], "text", crop=confirm[1], include=True, max_retries=10):
            raise RuntimeError("外部决策选项已点击，但未能确认选择")
        time.sleep(2)
        self._checkpoint(generation)
        if kind == "station":
            self._checkpoint(generation, answer)
            if self._input(generation, answer, self.auto.click_element, "./assets/images/zh_CN/base/confirm.png", "image", 0.9):
                time.sleep(2)
                self._checkpoint(generation)
        self.history.append({"kind": kind, "text": selected["text"]})
        if answer and answer.get("memory"):
            self.context.memory = answer["memory"]
        self.context.record({"status": "confirmed", "kind": kind, "stage": stage,
                             "text": selected["text"], "reason": (answer or {}).get("reason", ""),
                             "memory": self.context.memory})
        self.log.info(f"外部决策：{kind} → {selected['text']}")
        if answer and answer.get("reason"):
            self.log.info(f"Agent 取舍依据：{answer['reason']}")
        return True
