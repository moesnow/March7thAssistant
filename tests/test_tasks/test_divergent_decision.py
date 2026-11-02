from types import SimpleNamespace
from contextlib import nullcontext
from unittest.mock import MagicMock

import pytest

from tasks.weekly import divergent_decision as decision
from utils.agent_decision import DecisionCancelled


AREA = (.1, .2, .8, .6)
CONFIRM = ("确认", (.8, .9, .1, .05))
OCR = [
    ([[20, 20], [120, 20], [120, 50], [20, 50]], ("终结技伤害提高", .98)),
    ([[400, 20], [500, 20], [500, 50], [400, 50]], ("防御提高", .98)),
]


@pytest.fixture
def adapter(monkeypatch, tmp_path):
    monkeypatch.setattr(decision.time, "sleep", lambda *_: None)
    auto = MagicMock()
    auto.ocr_result = OCR
    auto.screenshot.size = (800, 600)
    auto.find_element.return_value = True
    auto.click_element.return_value = True
    cfg = MagicMock()
    cfg.get_value.side_effect = lambda key, default=None: "command" if key == "divergent_decision_mode" else default
    pause = SimpleNamespace(is_paused=lambda: False, stop_requested=False, checkpoint=MagicMock(),
                            generation=0, guard_generation=lambda *_: nullcontext())
    from tasks.weekly.divergent_context import DivergentContext
    return decision.DivergentDecision(auto, cfg, MagicMock(), pause, context=DivergentContext(auto, tmp_path))


def test_two_card_layout_uses_ocr_anchors_without_layout_templates():
    candidates = decision.text_candidates(OCR, (800, 600), AREA)
    assert [candidate["text"] for candidate in candidates] == ["终结技伤害提高", "防御提高"]
    assert candidates[0]["bounds"] == pytest.approx([.12, .22, .1, .03])


def test_low_confidence_and_outside_text_excluded():
    data = OCR + [([[-10, 0], [5, 0], [5, 5], [-10, 5]], ("越界", .99)),
                  ([[0, 0], [5, 0], [5, 5], [0, 5]], ("不确定", .1))]
    assert len(decision.text_candidates(data, (800, 600), AREA)) == 2


def test_scene_validation_tolerates_ocr_order_and_small_jitter():
    previous = decision.text_candidates(OCR, (800, 600), AREA)
    current = [dict(item, bounds=[value + .001 for value in item["bounds"]]) for item in reversed(previous)]
    assert decision.same_choices(previous, current)
    current[0]["text"] = "重抽后的新选项"
    assert not decision.same_choices(previous, current)


def test_choice_is_revalidated_and_confirmed(adapter, monkeypatch):
    backend = MagicMock(return_value="text-1")
    monkeypatch.setattr(decision, "request_decision", backend)
    assert adapter.choose("blessing", "选择祝福", AREA, CONFIRM, "第一位面")
    assert adapter.history == [{"kind": "blessing", "text": "终结技伤害提高"}]
    assert adapter.auto.find_element.call_args.kwargs["include"] is False
    assert adapter.auto.click_element.call_args_list[0].args == ("终结技伤害提高", "text")
    assert adapter.auto.click_element.call_args_list[1].args == ("确认", "text")
    assert backend.call_args.args[2]["stage"] == "第一位面"


@pytest.mark.parametrize("failure", [ValueError(), TimeoutError(), OSError()])
def test_provider_failure_returns_to_original_strategy(adapter, monkeypatch, failure):
    monkeypatch.setattr(decision, "request_decision", MagicMock(side_effect=failure))
    assert not adapter.choose("blessing", "选择祝福", AREA, CONFIRM, "")
    adapter.auto.click_element.assert_not_called()


def test_decline_returns_to_original_strategy(adapter, monkeypatch):
    monkeypatch.setattr(decision, "request_decision", lambda *args, **kwargs: None)
    assert not adapter.choose("blessing", "选择祝福", AREA, CONFIRM, "")
    adapter.auto.click_element.assert_not_called()


def test_changed_screen_discards_response_without_clicking(adapter, monkeypatch):
    monkeypatch.setattr(decision, "request_decision", lambda *args, **kwargs: "text-1")
    adapter.auto.find_element.return_value = False
    assert adapter.choose("station", "选择下一站", AREA, CONFIRM, "")
    adapter.auto.click_element.assert_not_called()


def test_timeout_on_changed_screen_does_not_run_stale_fallback(adapter, monkeypatch):
    monkeypatch.setattr(decision, "request_decision", MagicMock(side_effect=TimeoutError()))
    adapter.auto.find_element.return_value = False
    assert adapter.choose("blessing", "选择祝福", AREA, CONFIRM, "")
    adapter.auto.click_element.assert_not_called()


def test_changed_option_never_clicks_confirm(adapter, monkeypatch):
    monkeypatch.setattr(decision, "request_decision", lambda *args, **kwargs: "text-1")
    adapter.auto.click_element.return_value = False
    assert adapter.choose("blessing", "选择祝福", AREA, CONFIRM, "")
    assert adapter.auto.click_element.call_count == 1
    assert adapter.history == []


def test_failed_confirmation_does_not_double_select(adapter, monkeypatch):
    monkeypatch.setattr(decision, "request_decision", lambda *args, **kwargs: "text-1")
    adapter.auto.click_element.side_effect = [True, False]
    with pytest.raises(RuntimeError, match="未能确认"):
        adapter.choose("blessing", "选择祝福", AREA, CONFIRM, "")
    assert adapter.history == []


def test_pause_cancels_request_and_restarts_observation(adapter, monkeypatch):
    monkeypatch.setattr(decision, "request_decision", MagicMock(side_effect=DecisionCancelled()))
    assert adapter.choose("blessing", "选择祝福", AREA, CONFIRM, "")
    assert adapter.pause.checkpoint.called
    adapter.auto.click_element.assert_not_called()


def test_station_extra_confirmation_only_after_success(adapter, monkeypatch):
    monkeypatch.setattr(decision, "request_decision", lambda *args, **kwargs: "text-1")
    assert adapter.choose("station", "选择下一站", AREA, CONFIRM, "")
    assert adapter.auto.click_element.call_count == 3


def test_opening_animation_settles_before_collecting_text(adapter, monkeypatch):
    state = {"settled": False}
    monkeypatch.setattr(decision.time, "sleep", lambda *_: state.update(settled=True))
    adapter.auto.perform_ocr.side_effect = lambda: setattr(adapter.auto, "ocr_result", OCR if state["settled"] else [])
    monkeypatch.setattr(decision, "request_decision", lambda *args, **kwargs: "text-1")
    assert adapter.choose("equation", "选择方程", AREA, CONFIRM, "")
    assert adapter.history == [{"kind": "equation", "text": "终结技伤害提高"}]


def test_rerolled_cards_with_shared_text_discard_old_decision(adapter, monkeypatch):
    changed = [OCR[0], (OCR[1][0], ("新的另一张祝福", .98))]
    def answer(*args, **kwargs):
        adapter.auto.ocr_result = changed
        return "text-1"
    monkeypatch.setattr(decision, "request_decision", answer)
    assert adapter.choose("blessing", "选择祝福", AREA, CONFIRM, "")
    adapter.auto.click_element.assert_not_called()
    assert adapter.history == []


def test_resume_during_result_checkpoint_discards_old_decision(adapter, monkeypatch):
    adapter.pause.generation = 0
    def answer(*args, **kwargs):
        adapter.pause.checkpoint.side_effect = lambda: setattr(adapter.pause, "generation", 1)
        return "text-1"
    monkeypatch.setattr(decision, "request_decision", answer)
    assert adapter.choose("blessing", "选择祝福", AREA, CONFIRM, "")
    adapter.auto.click_element.assert_not_called()


def test_station_waits_for_delayed_extra_confirmation(adapter, monkeypatch):
    elapsed = [0]
    selected_at = []
    monkeypatch.setattr(decision.time, "sleep", lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds))
    monkeypatch.setattr(decision, "request_decision", lambda *args, **kwargs: "text-1")
    def click(target, *args, **kwargs):
        if target == "确认":
            selected_at.append(elapsed[0])
        if target.endswith("confirm.png"):
            assert selected_at and elapsed[0] - selected_at[-1] >= 2
        return True
    adapter.auto.click_element.side_effect = click
    assert adapter.choose("station", "选择下一站", AREA, CONFIRM, "")
