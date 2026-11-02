"""提供可核对的游戏证据与逐节点记录；构筑取舍由外部 Agent 完成。"""

import json
from pathlib import Path
import time
import uuid

from tasks.weekly.divergent_decision import text_candidates


NAVIGATION = frozenset((
    "攻略", "攻略大全", "攻略详情", "查看攻略", "参考攻略", "推荐攻略", "攻略列表",
    "队伍", "队伍详情", "阵容详情", "编队详情", "角色详情", "已获得祝福", "已获祝福",
    "已获得方程", "已获方程", "已获得奇物", "已获奇物", "构筑详情", "查看详情",
))
TABS = frozenset(("方程", "祝福", "奇物", "加权奇物", "详情", "效果", "推荐", "下一页", "上一页"))
BLOCKED = ("购买", "兑换", "消耗", "更换", "编入", "移除", "加入", "替换", "上阵", "出战", "卸下", "解锁",
           "激活", "强化", "重抽", "刷新", "切换", "放弃", "结算", "退出", "分享", "发布", "复制", "删除", "重置")


def navigation_controls(ocr, inspecting=False):
    controls = []
    headings = {item["text"] for item in ocr if item["bounds"][1] < .25}
    readable_list = bool(headings & {"攻略", "攻略大全", "攻略详情", "祝福", "方程", "奇物", "加权奇物"})
    for item in ocr:
        label = item["text"].strip()
        bounds = item["bounds"]
        named = label in NAVIGATION or (inspecting and label in TABS)
        entry = (inspecting and readable_list and .16 < bounds[1] < .85 and len(label) <= 60
                 and not label.isnumeric() and not any(word in label for word in BLOCKED + ("确认", "确定", "应用", "使用", "选择")))
        if named or entry:
            controls.append({"id": f"view-{len(controls) + 1}", "text": label, "bounds": bounds})
    if inspecting and readable_list:
        controls.extend([{"id": "scroll-down", "text": "向下查看", "kind": "scroll", "direction": -1},
                         {"id": "scroll-up", "text": "向上查看", "kind": "scroll", "direction": 1}])
    return controls[:100]


class DivergentContext:
    def __init__(self, auto, directory=None):
        self.auto = auto
        self.directory = Path(directory or "logs/agent_decisions") / uuid.uuid4().hex
        self.frames = []
        self.memory = {}
        self.events = []

    def capture(self, source, inspecting=False):
        self.auto.take_screenshot((0, 0, 1, 1))
        self.auto.perform_ocr()
        width, height = self.auto.screenshot.size
        ocr = text_candidates(self.auto.ocr_result, (width, height), (0, 0, 1, 1), limit=240)
        self.directory.mkdir(parents=True, exist_ok=True)
        frame_id = f"frame-{len(self.frames) + 1}"
        image = self.directory / f"{frame_id}.png"
        self.auto.screenshot.save(image)
        frame = {"id": frame_id, "source": source, "captured_at": time.time(),
                 "image_path": str(image.resolve()), "ocr": ocr,
                 "controls": navigation_controls(ocr, inspecting)}
        # 推荐标记只作为证据，不转换成固定优先级。
        markers = []
        template = "./assets/images/screen/divergent_universe/rec_blessing.png"
        try:
            matches = self.auto.find_element(template, "image_with_multiple_targets", .9,
                                             take_screenshot=False, relative=True)
        except (OSError, ValueError):
            matches = []  # 推荐图标缺失不影响 Agent 阅读画面与物品效果。
        if isinstance(matches, list):
            for match in matches[:12]:
                if isinstance(match, (tuple, list)) and len(match) == 2:
                    left, right = match
                    if all(isinstance(point, (tuple, list)) and len(point) == 2 for point in match):
                        markers.append({"source": "game_recommendation", "bounds": [left[0] / width, left[1] / height,
                                        (right[0] - left[0]) / width, (right[1] - left[1]) / height]})
        frame["recommendation_markers"] = markers
        self.frames.append(frame)
        return frame

    def packet(self):
        # 保留初始编队证据及近期观察；旧帧仍在本地，可由 Agent 按路径读取。
        setup = [frame for frame in self.frames if frame["source"] == "team_setup"][-1:]
        recent = self.frames[-6:]
        return {"observations": setup + [frame for frame in recent if frame not in setup],
                "agent_memory": self.memory, "inventory_completeness": "partial",
                "confirmed_choices": [{key: (str(event[key])[:256] if key == "reason" else event[key])
                                       for key in ("kind", "stage", "text", "reason") if key in event}
                                      for event in self.events if event.get("status") == "confirmed"][-128:],
                "unobserved_fallbacks": sum(event.get("status") == "fallback" for event in self.events),
                "decision_skill": str(Path("assets/agent/skills/march7th-assistant/references/strategy.md").resolve())}

    def record(self, value):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.events.append(value)
        with (self.directory / "decisions.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, ensure_ascii=False) + "\n")
