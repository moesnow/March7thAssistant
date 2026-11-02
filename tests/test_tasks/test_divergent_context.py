from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock

from PIL import Image
import pytest

from tasks.weekly.divergent_context import DivergentContext, navigation_controls
from tasks.weekly import divergent_decision as decision
from utils.agent_decision import validate_decision_answer


def item(text, y=.3, x=.2):
    return {"id": "text-1", "text": text, "bounds": [x, y, .1, .03]}


def test_context_supplies_image_full_ocr_and_game_recommendation(tmp_path):
    auto = MagicMock()
    auto.screenshot = Image.new("RGB", (800, 600))
    auto.ocr_result = [([[10, 20], [100, 20], [100, 50], [10, 50]], ("队伍详情", .99))]
    auto.find_element.return_value = [((200, 120), (220, 150))]
    context = DivergentContext(auto, tmp_path)
    frame = context.capture("team_setup")
    assert Image.open(frame["image_path"]).size == (800, 600)
    assert frame["ocr"][0]["text"] == "队伍详情"
    assert frame["recommendation_markers"][0]["bounds"] == pytest.approx([.25, .2, .025, .05])
    assert frame["controls"][0]["text"] == "队伍详情"
    for _ in range(7):
        context.capture("exploration_hud")
    packet = context.packet()
    assert packet["observations"][0]["source"] == "team_setup"
    assert packet["inventory_completeness"] == "partial"


def test_navigation_exposes_evidence_not_purchases_or_lineup_edits():
    texts = [item("攻略大全", .05), item("攻略甲"), item("应用并更换队伍"), item("购买"), item("角色加入队伍"), item("分享")]
    root = navigation_controls(texts)
    assert [value["text"] for value in root] == ["攻略大全"]
    inspection = navigation_controls(texts, inspecting=True)
    assert "攻略甲" in [value["text"] for value in inspection]
    assert not any(value["text"] in ("应用并更换队伍", "角色加入队伍", "购买", "分享") for value in inspection)
    assert any(value["id"] == "scroll-down" for value in inspection)


@pytest.mark.parametrize("answer,can_choose,back", [
    ({"action": "inspect", "control_id": "unknown"}, True, False),
    ({"action": "choose", "candidate_id": "a"}, False, True),
    ({"action": "back"}, True, False),
    ({"action": "click", "x": 300}, True, False),
    ({"candidate_id": "a", "memory": {"text": "x" * 17000}}, True, False),
])
def test_actions_cannot_escape_current_controls(answer, can_choose, back):
    request = {"request_id": "r", "candidates": [{"id": "a"}], "controls": [{"id": "view-1"}],
               "can_choose": can_choose, "can_go_back": back}
    with pytest.raises(ValueError):
        validate_decision_answer(request, dict(answer, protocol_version=1, request_id="r"))


class ReplayContext:
    def __init__(self):
        self.view = "choice"
        self.memory = {}
        self.events = []
        self.index = 0

    def capture(self, source, inspecting=False):
        self.index += 1
        ocr = [item("攻略")] if self.view == "choice" else [item("方程详情", .05)]
        controls = [{"id": "view-1", "text": "攻略", "bounds": [.2, .3, .1, .03]}] if self.view == "choice" else []
        return {"id": f"frame-{self.index}", "ocr": ocr, "controls": controls}

    def packet(self):
        return {"agent_memory": self.memory, "inventory_completeness": "partial"}

    def record(self, event):
        self.events.append(event)


@pytest.fixture
def replay(monkeypatch):
    monkeypatch.setattr(decision.time, "sleep", lambda *_: None)
    context = ReplayContext()
    auto = MagicMock()
    auto.screenshot.size = (800, 600)
    auto.ocr_result = [([[10, 20], [100, 20], [100, 50], [10, 50]], ("实际候选", .99))]
    auto.find_element.return_value = True
    def click(text, *args, **kwargs):
        if text == "攻略":
            context.view = "guide"
        return True
    auto.click_element.side_effect = click
    auto.press_key.side_effect = lambda *_: setattr(context, "view", "choice")
    cfg = MagicMock()
    cfg.get_value.side_effect = lambda key, default=None: "command" if key == "divergent_decision_mode" else default
    pause = SimpleNamespace(generation=0, is_paused=lambda: False, stop_requested=False,
                            checkpoint=MagicMock(), guard_generation=lambda *_: nullcontext())
    return decision.DivergentDecision(auto, cfg, MagicMock(), pause, context=context)


def test_agent_can_inspect_then_return_and_choose_with_reason(replay, monkeypatch):
    replies = iter([
        {"action": "inspect", "control_id": "view-1", "reason": "先确认攻略机制"},
        {"action": "back", "memory": {"goal": "符合队伍的方程"}},
        {"action": "choose", "candidate_id": "text-1", "reason": "候选效果补足当前队伍机制",
         "memory": {"goal": "符合队伍的方程", "references": ["frame-1"]}},
    ])
    requests = []
    def provider(command, timeout, request, **kwargs):
        requests.append(request)
        return next(replies)
    monkeypatch.setattr(decision, "request_decision", provider)
    assert replay.choose("blessing", "选择祝福", (.1, .2, .8, .6), ("确认", (.8, .9, .1, .05)), "第一位面")
    assert [request["can_choose"] for request in requests] == [True, False, True]
    replay.auto.press_key.assert_called_once_with("esc")
    assert replay.context.events[-1]["status"] == "confirmed"
    assert "队伍" in replay.context.events[-1]["reason"]
    assert replay.context.memory["references"] == ["frame-1"]


def test_inspection_timeout_returns_before_fallback(replay, monkeypatch):
    monkeypatch.setattr(decision, "request_decision", MagicMock(side_effect=[
        {"action": "inspect", "control_id": "view-1"}, TimeoutError(),
    ]))
    assert not replay.choose("curio", "选择奇物", (.1, .2, .8, .6), ("确认", (.8, .9, .1, .05)), "")
    assert replay.context.view == "choice"
    assert replay.auto.click_element.call_count == 1
    assert replay.context.events[-1]["status"] == "fallback"


def test_failed_return_stops_without_confirming(replay, monkeypatch):
    replay.auto.press_key.side_effect = None
    monkeypatch.setattr(decision, "request_decision", MagicMock(side_effect=[
        {"action": "inspect", "control_id": "view-1"}, {"action": "back"},
    ]))
    with pytest.raises(RuntimeError, match="查看页面|原选择"):
        replay.choose("curio", "选择奇物", (.1, .2, .8, .6), ("确认", (.8, .9, .1, .05)), "")
    assert replay.auto.click_element.call_count == 1
    assert replay.auto.press_key.call_count == 5


def test_prepare_exposes_team_inspection_and_records_plan_without_picking_characters(replay, monkeypatch):
    requests = []
    def provider(command, timeout, request, **kwargs):
        requests.append(request)
        return {"action": "choose", "candidate_id": "continue", "reason": "已读取编队证据",
                "memory": {"goal": "按实际队伍构筑", "uncertainties": []}}
    monkeypatch.setattr(decision, "request_decision", provider)
    replay.prepare((.5, .8, .2, .1))
    assert requests[0]["kind"] == "setup"
    assert any(control["id"] == "open-team" for control in requests[0]["controls"])
    replay.auto.click_element.assert_not_called()
    assert replay.context.events[-1]["status"] == "prepared"
    assert replay.context.memory["goal"] == "按实际队伍构筑"


def test_unconfirmed_choice_does_not_commit_optimistic_memory(replay, monkeypatch):
    replay.context.memory = {"goal": "原构筑"}
    def provider(*args, **kwargs):
        replay.auto.ocr_result = []
        return {"action": "choose", "candidate_id": "text-1", "memory": {"owned": ["尚未获得的物品"]}}
    monkeypatch.setattr(decision, "request_decision", provider)
    assert replay.choose("blessing", "选择祝福", (.1, .2, .8, .6), ("确认", (.8, .9, .1, .05)), "")
    assert replay.context.memory == {"goal": "原构筑"}
    assert not any(event.get("status") == "confirmed" for event in replay.context.events)


def test_pause_while_inspecting_returns_but_discards_old_selection(replay, monkeypatch):
    calls = 0
    def provider(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"action": "inspect", "control_id": "view-1"}
        replay.pause.generation += 1
        raise decision.DecisionCancelled()
    monkeypatch.setattr(decision, "request_decision", provider)
    assert replay.choose("blessing", "选择祝福", (.1, .2, .8, .6), ("确认", (.8, .9, .1, .05)), "")
    assert replay.context.view == "choice"
    assert replay.auto.click_element.call_count == 1
    assert replay.history == []


def test_inspection_and_final_choice_share_one_deadline(replay, monkeypatch):
    clock = [100.0]
    budgets = []
    monkeypatch.setattr(decision.time, "monotonic", lambda: clock[0])
    def provider(command, timeout, request, **kwargs):
        budgets.append(timeout)
        clock[0] += 35
        return {"action": "inspect", "control_id": "view-1"} if len(budgets) == 1 else {"action": "back"}
    monkeypatch.setattr(decision, "request_decision", provider)
    assert not replay.choose("blessing", "选择祝福", (.1, .2, .8, .6), ("确认", (.8, .9, .1, .05)), "")
    assert budgets == [60, 25]
    assert replay.context.view == "choice"
    assert replay.history == []


def test_disconnected_reply_cannot_click_after_provider_return(replay, monkeypatch):
    store = SimpleNamespace(is_current=lambda *_: False)
    monkeypatch.setattr(decision, "AgentSession", lambda: store)
    monkeypatch.setattr(decision, "request_decision", lambda *args, **kwargs: {
        "action": "choose", "candidate_id": "text-1", "_connection_id": "revoked"})
    assert replay.choose("blessing", "选择祝福", (.1, .2, .8, .6), ("确认", (.8, .9, .1, .05)), "")
    replay.auto.click_element.assert_not_called()
    assert replay.history == []
