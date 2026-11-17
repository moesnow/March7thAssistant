from types import SimpleNamespace
from unittest.mock import Mock, call

from PIL import Image
import pytest

from module.localization import tr
from tasks.daily.tasks import Tasks
from tasks.touch import daily


def ocr_line(text, x=0, y=0, width=15):
    return ([(x, y), (x + width, y), (x + width, y + 14), (x, y + 14)], (text, 0.99))


@pytest.mark.parametrize("texts, expected", [
    (["0"], 0), (["100"], 100), (["１００"], 100), (["500"], 500), ([], None),
    (["10"], None), (["500/500"], None), (["100", "200"], None),
])
def test_reads_only_the_activity_badge(texts, expected):
    assert daily.parse_activity([ocr_line(text) for text in texts]) == expected


def test_missing_ocr_results_retry_to_the_bound(monkeypatch):
    frame = Image.new("RGB", (60, 32))
    read = Mock(return_value=False)
    monkeypatch.setattr(daily, "auto", SimpleNamespace(take_screenshot=Mock(return_value=(frame, None, 1))))
    monkeypatch.setattr(daily, "ocr", SimpleNamespace(recognize_multi_lines=read))
    monkeypatch.setattr(daily, "time", SimpleNamespace(sleep=Mock()))

    with pytest.raises(daily.DailyTrainingError, match="当前活跃度"):
        daily.read_activity()

    assert read.call_count == 8


def test_reuses_pc_card_parser_at_720p_without_overwriting_progress_with_clipped_text():
    tasks = Tasks("assets/config/task_mappings.json")
    lines = [
        ocr_line("进度1/1", 20, 10, 70), ocr_line("登录游戏", 20, 50, 80),
        ocr_line("进度20/20", 275, 10, 90), ocr_line("累计消灭20个敌人", 275, 50, 155),
        ocr_line("进度0/120", 530, 10, 90), ocr_line("累计消耗120点开拓", 530, 50, 150),
        ocr_line("力", 530, 73),
    ]
    assert tasks.parse_ocr(lines, x_gap=67, require_status=True)
    assert tasks.parse_ocr([ocr_line("敌人0JhIN")], x_gap=67, require_status=True)
    assert tasks.daily_tasks == {
        "登录游戏": False, "累计消灭20个敌人": False, "累计消耗120点开拓力": True,
    }
    # PC 保留原来的缺进度时按待完成处理以及满活跃度提示提前返回。
    assert tasks.parse_ocr([ocr_line("敌人0JhIN")])
    assert tasks.daily_tasks["累计消灭20个敌人"] is True
    assert not tasks.parse_ocr([ocr_line("本日活跃度已满")])


@pytest.mark.parametrize("reward_enable, quest_enable", [(False, True), (True, False)])
def test_disabling_rewards_preserves_reading_and_prevents_claiming(monkeypatch, reward_enable, quest_enable):
    monkeypatch.setattr(daily, "cfg", SimpleNamespace(reward_enable=reward_enable, reward_quest_enable=quest_enable, daily_enable=True, daily_material_enable=False))
    monkeypatch.setattr(daily, "screen", Mock())
    monkeypatch.setattr(daily, "read_activity", Mock(return_value=100))
    cards = Mock(return_value=(100, True, 0, {}))
    milestones = Mock(return_value={100: ((10, 20), (30, 40))})
    click = Mock()
    monkeypatch.setattr(daily, "scan_cards", cards)
    monkeypatch.setattr(daily, "claimable_milestones", milestones)
    monkeypatch.setattr(daily, "click_milestone", click)

    summary = Mock()
    assert daily.run(complete_training=True, on_summary=summary)

    cards.assert_called_once_with(100, False, read_tasks=False)
    milestones.assert_not_called()
    click.assert_not_called()
    summary.assert_called_once_with(tr("每日实训活跃度 {activity}/{maximum}").format(activity=100, maximum=500))


def test_claiming_multiple_milestones_from_one_popup_does_not_repeat_clicks(monkeypatch):
    button = ((10, 20), (30, 40))
    monkeypatch.setattr(daily, "cfg", SimpleNamespace(
        reward_enable=True, reward_quest_enable=True, save_timestamp=Mock(), notify_template={"DailyPracticeCompleted": "每日实训已完成"},
    ))
    monkeypatch.setattr(daily, "screen", Mock())
    monkeypatch.setattr(daily, "read_activity", Mock(return_value=200))
    monkeypatch.setattr(daily, "scan_cards", Mock(return_value=(200, False, 0, {})))
    monkeypatch.setattr(daily, "time", SimpleNamespace(sleep=Mock()))
    auto = Mock()
    auto.find_element.side_effect = [button, button, None]
    auto.take_screenshot.return_value = (None, None, 1)
    monkeypatch.setattr(daily, "auto", auto)
    notify = Mock()
    monkeypatch.setattr(daily, "notify_reward", notify)

    assert daily.run()

    auto.click_element_with_pos.assert_called_once_with(button)
    auto.click_element.assert_called_once_with(daily.REWARD_CLOSE_CROP, "crop")
    assert [entry.args[0].rsplit("/", 1)[-1] for entry in auto.find_element.call_args_list] == [
        "milestone_ready.png", "item_reward.png", "milestone_ready.png",
    ]
    notify.assert_called_once()


def test_daily_synthesizes_only_when_the_card_is_pending(monkeypatch):
    from tasks.touch import synthesis

    monkeypatch.setattr(daily, "cfg", SimpleNamespace(
        reward_enable=True, reward_quest_enable=True, daily_enable=True, daily_material_enable=True,
    ))
    monkeypatch.setattr(daily, "screen", Mock())
    monkeypatch.setattr(daily, "read_activity", Mock(side_effect=[300, 400]))
    scan = Mock(side_effect=[(300, False, 0, {daily.MATERIAL_TASK: True}), (400, False, 0, {})])
    monkeypatch.setattr(daily, "scan_cards", scan)
    monkeypatch.setattr(daily, "claimable_milestones", Mock(return_value=()))
    synthesize = Mock(return_value=True)
    monkeypatch.setattr(synthesis, "material", synthesize)

    assert daily.run(complete_training=True)
    synthesize.assert_called_once_with()
    assert scan.call_args_list == [call(300, True, read_tasks=True), call(400, True, read_tasks=False)]


def test_completed_500_point_card_with_zero_badge_skips_support_and_synthesis(monkeypatch):
    from tasks.touch import synthesis

    card = Tasks("assets/config/task_mappings.json")
    card.parse_ocr([ocr_line("进度 1/1 完成1次「差分宇宙」或「货币战争」 +500 领取")], require_status=True)
    assert card.claimable == {"完成1次「差分宇宙」或「货币战争」": 500}
    states = daily.TrainingCards({**card.daily_tasks, daily.MATERIAL_TASK: True, daily.SUPPORT_TASK: True}, 500)
    cfg = SimpleNamespace(daily_enable=True, daily_material_enable=True, reward_enable=False, reward_quest_enable=True,
                          save_timestamp=Mock())
    monkeypatch.setattr(daily, "cfg", cfg)
    monkeypatch.setattr(daily, "screen", Mock())
    monkeypatch.setattr(daily, "read_activity", Mock(return_value=0))
    monkeypatch.setattr(daily, "scan_cards", Mock(return_value=(0, True, 0, states)))
    action = Mock()
    monkeypatch.setattr(synthesis, "material", action)
    assert not daily.needs_support()
    assert daily.run(complete_training=True)
    action.assert_not_called()
    cfg.save_timestamp.assert_not_called()


def test_disabling_both_training_options_skips_the_page(monkeypatch):
    cfg = SimpleNamespace(daily_enable=False, reward_enable=True, reward_quest_enable=False)
    monkeypatch.setattr(daily, "cfg", cfg)
    navigate = Mock()
    monkeypatch.setattr(daily, "screen", navigate)
    assert daily.run(complete_training=True)
    navigate.change_to.assert_not_called()


def test_synthesis_rejects_unexpected_quantity_before_consuming_materials(monkeypatch):
    from tasks.touch import synthesis

    monkeypatch.setattr(synthesis, "screen", Mock())
    monkeypatch.setattr(synthesis, "_filter_recipes", Mock())
    monkeypatch.setattr(synthesis, "_read_text", Mock(return_value="合成数量：2"))
    auto = Mock()
    auto.find_element.side_effect = [None, True]
    monkeypatch.setattr(synthesis, "auto", auto)

    with pytest.raises(daily.DailyTrainingError, match="只合成 1 个"):
        synthesis.material()

    auto.click_element.assert_called_once_with(synthesis.CORE, "image", 0.89, crop=synthesis.RECIPES)
