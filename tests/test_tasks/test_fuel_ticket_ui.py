"""Geometry fixtures transcribed from PC quick-clear screenshots (no live spending)."""
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from PIL import Image, ImageDraw

from tasks.power.fuel_ticket import FuelTicketBatch
from tasks.power.fuel_ticket_ui import (
    Word, confirm_dialog, entry_button, receipt_dialog, ticket_icon, refine_cost_words,
)
from tasks.power.policy import GOLDEN_CALYX, CRIMSON_CALYX, STAGNANT_SHADOW
from tasks.power import power
from tasks.base.task_steps import GameRecoveryError

RED_NAME = "「世界尽头」酒馆"
DISPLAY = "欢愉之蕾"
BATCH = FuelTicketBatch(CRIMSON_CALYX, RED_NAME, 1, 10, 1)


def words(*rows):
    return [Word(*row) for row in rows]


def test_red_entry_uses_location_and_same_row_name():
    guide = words(
        (DISPLAY,.46,.36),(RED_NAME,.51,.40),("进入",.81,.379),
        ("毁灭之蕾",.46,.53),("渡画泉隐",.51,.57),("进入",.81,.55),
        ("毁灭之蕾",.46,.64),("?鳞渊境",.51,.68),("进入",.81,.665))
    assert entry_button(guide,CRIMSON_CALYX,RED_NAME,DISPLAY).y == .379
    assert entry_button(guide,CRIMSON_CALYX,RED_NAME,"毁灭之蕾") is None
    assert entry_button(guide,CRIMSON_CALYX,"未知位置",DISPLAY) is None
    assert entry_button(guide,CRIMSON_CALYX,"鳞渊境","毁灭之蕾").y == .665


def test_icon_is_row_local_requires_unique_orange_glyph():
    im=Image.new("RGB",(1920,1080),"#eeeeee")
    draw=ImageDraw.Draw(im)
    draw.rectangle((1404,402,1430,418),fill="#f8a738")
    # Another row with an identical icon must not be selected.
    draw.rectangle((1404,580,1430,596),fill="#f8a738")
    entry=Word("进入",.81,.379)
    x,y=ticket_icon(im,entry)
    assert .73<x<.76 and .37<y<.39
    draw.rectangle((1370,402,1390,418),fill="#f8a738")
    assert ticket_icon(im,entry) is None
    assert ticket_icon(Image.new("RGB",(1920,1080),"white"),entry) is None


def confirmation():
    return words(
        ("快速刷取",.50,.24),
        ("是否快速刷取欢愉之蕾·拟造花萼（赤）·难度V？",.50,.39),
        ("刷取次数1",.5,.49),("消耗",.44,.64),("10",.49,.64),
        ("1",.54,.64),("取消",.37,.72),("确认",.62,.72))


def result():
    return words(
        ("快速刷取",.50,.18),("刷取次数",.46,.28),("1/1",.55,.28),
        ("·第1次刷取",.19,.36),("消耗",.71,.36),("10",.79,.36),("1",.845,.36),
        ("欢愉之蕾·拟造花萼（赤）",.34,.48),("关闭",.35,.93),
        ("再来一次",.64,.93))


def changed(rows, old, new):
    return [Word(new,w.x,w.y,w.confidence) if w.text==old else w for w in rows]


def test_confirmation_checks_title_target_count_and_two_visible_costs():
    assert confirm_dialog(confirmation(),BATCH,DISPLAY).text=="确认"
    for old,new in (("刷取次数1","刷取次数2"),("10","20"),("1","2"),
                    ("是否快速刷取欢愉之蕾·拟造花萼（赤）·难度V？",
                     "是否快速刷取毁灭之蕾·拟造花萼（赤）·难度V？")):
        assert confirm_dialog(changed(confirmation(),old,new),BATCH,DISPLAY) is None
    assert confirm_dialog([w for w in confirmation() if w.text!="取消"],BATCH,DISPLAY) is None


def test_result_requires_completed_single_run_target_and_observed_cost():
    r=receipt_dialog(result(),BATCH,DISPLAY)
    assert (r.completed,r.spent_power,r.spent_tickets)==(1,10,1)
    for old,new in (("1/1","0/1"),("1/1","1/2"),("10","30"),("1","3"),
                    ("欢愉之蕾·拟造花萼（赤）","毁灭之蕾·拟造花萼（赤）")):
        assert receipt_dialog(changed(result(),old,new),BATCH,DISPLAY) is None
    assert receipt_dialog(confirmation(),BATCH,DISPLAY) is None
    assert receipt_dialog([w for w in result() if w.text!="关闭"],BATCH,DISPLAY) is None


def configure(monkeypatch, quick, *, balance=30):
    from tasks.power import fuel_ticket_ui
    config=SimpleNamespace(prefer_fuel_tickets=True,
        instance_names_challenge_count={},tp_before_instance=False,
        power_plan=[[GOLDEN_CALYX,"回忆之蕾",3]],power_plan_keep=False,set_value=Mock())
    monkeypatch.setattr(power,"cfg",config)
    monkeypatch.setattr(power.Power,"get",Mock(return_value=balance))
    monkeypatch.setattr(power,"screen",Mock())
    battle=Mock(prepare_instance=Mock(return_value=True),
                select_waves=Mock(side_effect=lambda kind,count:count),
                start_instance=Mock(return_value=False),wait_fight=Mock(return_value=True))
    monkeypatch.setattr(power,"Instance",battle)
    monkeypatch.setattr(fuel_ticket_ui,"PCFuelTicketScreen",Mock(return_value=quick))
    return config,battle


def test_quick_result_commits_before_closing_and_leftover_falls_back(monkeypatch):
    quick=Mock()
    quick.run_one.side_effect=[1,0]
    config,battle=configure(monkeypatch,quick)
    quick.close_receipt.side_effect=lambda: config.set_value.assert_called_once_with(
        "power_plan",[[GOLDEN_CALYX,"回忆之蕾",2]])
    assert power.Power.execute_power_plan()
    assert config.set_value.call_args_list==[
        call("power_plan",[[GOLDEN_CALYX,"回忆之蕾",2]]),call("power_plan",[])]
    assert quick.run_one.call_args_list==[
        call(GOLDEN_CALYX,"回忆之蕾",30),call(GOLDEN_CALYX,"回忆之蕾",20)]
    battle.select_waves.assert_called_once_with(GOLDEN_CALYX,2)
    battle.start_instance.assert_called_once()
    quick.close_receipt.assert_called_once()


def test_unknown_commit_aborts_without_repeating_or_entering_normal_battle(monkeypatch):
    quick=Mock()
    quick.run_one.side_effect=GameRecoveryError("未知结算")
    config,battle=configure(monkeypatch,quick)
    with pytest.raises(GameRecoveryError,match="未知结算"):
        power.Power.execute_power_plan()
    config.set_value.assert_not_called()
    battle.prepare_instance.assert_not_called()
    quick.run_one.assert_called_once()


def test_verified_commit_is_preserved_when_receipt_close_fails(monkeypatch):
    quick=Mock()
    quick.run_one.return_value=1
    quick.close_receipt.side_effect=GameRecoveryError("关闭失败")
    config,battle=configure(monkeypatch,quick)
    with pytest.raises(GameRecoveryError,match="关闭失败"):
        power.Power.execute_power_plan()
    config.set_value.assert_called_once_with("power_plan",[[GOLDEN_CALYX,"回忆之蕾",2]])
    battle.prepare_instance.assert_not_called()


def test_disabled_option_uses_native_power_flow(monkeypatch):
    quick=Mock()
    config,battle=configure(monkeypatch,quick)
    config.prefer_fuel_tickets=False
    assert power.Power.execute_power_plan()
    quick.run_one.assert_not_called()
    battle.select_waves.assert_called_once_with(GOLDEN_CALYX,3)


def test_support_training_uses_one_normal_wave_before_ticket_clears(monkeypatch):
    from tasks.power.policy import SupportDemand
    quick=Mock()
    quick.run_one.side_effect=[1,1]
    config,battle=configure(monkeypatch,quick)
    config.borrow_enable=True
    battle.start_instance.return_value=True
    support=SupportDemand(pending=True)
    assert power.Power.execute_power_plan(support=support)
    assert support.pending is False
    battle.select_waves.assert_called_once_with(GOLDEN_CALYX,1)
    battle.start_instance.assert_called_once()
    assert quick.run_one.call_args_list==[
        call(GOLDEN_CALYX,"回忆之蕾",20),call(GOLDEN_CALYX,"回忆之蕾",10)]
    assert config.set_value.call_args_list==[
        call("power_plan",[[GOLDEN_CALYX,"回忆之蕾",2]]),
        call("power_plan",[[GOLDEN_CALYX,"回忆之蕾",1]]),
        call("power_plan",[])]

def test_cost_crop_recovers_missing_small_number_and_refuses_conflict():
    im=Image.new("RGB",(1920,1080),"white")
    full=confirmation()
    initial=[w for w in full if w.text!="1"]
    def read(crop):
        return words(("消耗",.14,.50),("10",.42,.50),("1",.70,.50))
    refined=refine_cost_words(im,initial,read)
    assert confirm_dialog(refined,BATCH,DISPLAY)
    wrong=changed(initial,"10","20")
    assert confirm_dialog(refine_cost_words(im,wrong,read),BATCH,DISPLAY) is None
