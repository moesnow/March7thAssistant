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


@pytest.fixture(autouse=True)
def recorded_power(monkeypatch):
    monkeypatch.setattr(power, "save_reading", Mock())


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
    power.save_reading.assert_called_once_with(config,"overview_power",0)


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
    power.save_reading.assert_called_once_with(config,"overview_power",20)


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

def test_two_wave_batch_uses_progress_and_visible_target_or_stock():
    from tasks.power.fuel_ticket_ui import stock_reading, count_plus
    b=FuelTicketBatch(CRIMSON_CALYX,RED_NAME,2,20,2)
    pre=changed(changed(changed(confirmation(),"刷取次数1","刷取次数2"),"10","20"),"1","2")
    assert confirm_dialog(pre,b,DISPLAY)
    assert not confirm_dialog(pre,BATCH,DISPLAY)
    assert count_plus(confirmation()+words(("24+今",.701,.546))) == (.698,.546)
    assert count_plus(confirmation()) == (.698,.546)
    assert count_plus(words(("+",.62,.704))) is None
    actual=words(("1039/1000",.692,.061),("103/300",.879,.061),
        ("快速刷取",.50,.248),("刷取次数",.475,.313),("2/2",.54,.314),
        ("欢愉之蕾·拟造花萼（赤）",.381,.393),
        ("第2次刷取",.254,.494),("消耗",.674,.493),("10",.726,.494),
        ("欢愉之蕾·拟造花萼（赤）",.381,.58),("关闭",.402,.756),("再来一次",.619,.756))
    after=stock_reading(actual)
    assert after==(1039,103)
    assert receipt_dialog(actual,b,DISPLAY,before_stock=(1041,123),after_stock=after).completed==2
    assert receipt_dialog(actual,b,DISPLAY,before_stock=(1041,122),after_stock=after).completed==2
    # Stock OCR is supplemental when the completed progress and reward name agree.
    assert receipt_dialog(actual,b,DISPLAY).completed==2
    hidden=[w for w in actual if w.text!="欢愉之蕾·拟造花萼（赤）"]
    assert receipt_dialog(hidden,b,DISPLAY,before_stock=(1041,123),after_stock=after).completed==2
    for before in (None,(1040,123),(1041,125),(1041,121)):
        assert receipt_dialog(hidden,b,DISPLAY,before_stock=before,after_stock=after) is None
    assert receipt_dialog(changed(actual,"2/2","1/2"),b,DISPLAY,before_stock=(1041,123),after_stock=after) is None
    assert receipt_dialog(changed(actual,"10","30"),b,DISPLAY,before_stock=(1041,123),after_stock=after) is None
    assert receipt_dialog(changed(actual,"欢愉之蕾·拟造花萼（赤）","毁灭之蕾·拟造花萼（赤）"),b,DISPLAY,before_stock=(1041,123),after_stock=after) is None


def test_power_plan_batch_only_decrements_verified_count(monkeypatch):
    quick=Mock()
    config,battle=configure(monkeypatch,quick)
    config.fuel_ticket_batch_enable=True
    quick.run_batch.side_effect=[2,1]
    assert power.Power.execute_power_plan()
    assert quick.run_batch.call_args_list==[
        call(GOLDEN_CALYX,"回忆之蕾",30,3),call(GOLDEN_CALYX,"回忆之蕾",10,1)]
    assert config.set_value.call_args_list==[
        call("power_plan",[[GOLDEN_CALYX,"回忆之蕾",1]]),call("power_plan",[])]
    battle.prepare_instance.assert_not_called()


@pytest.mark.parametrize("balance,stock,requested,expected", [
    (92,1039,9,9), (300,100,30,24), (92,4,9,4),
    (92,1039,3,3), (92,1,9,1),
])
def test_prepare_max_batch_without_plus_ocr(monkeypatch,balance,stock,requested,expected):
    from tasks.power import fuel_ticket_ui as ui
    from tasks.power.fuel_ticket import plan_fuel_ticket_batch
    screen=ui.PCFuelTicketScreen(Mock(), Mock(), DISPLAY, sleep=lambda _: None)
    image=Image.new("RGB",(1920,1080))
    base=confirmation()+words((f"{stock}/1000",.692,.061),(f"{balance}/300",.879,.061),
                              ("24+今",.701,.546))
    selected=changed(changed(changed(base,"刷取次数1",f"刷取次数{expected}"),
                             "10",str(expected*10)),"1",str(expected))
    frames=iter([[],base,selected])
    screen._frame=lambda: (image,(0,0),1,next(frames))
    monkeypatch.setattr(ui,"entry_button",lambda *a: Word("进入",.8,.4))
    monkeypatch.setattr(ui,"ticket_icon",lambda *a:(.74,.4))
    screen._click=Mock(return_value=True)
    batch=plan_fuel_ticket_batch(CRIMSON_CALYX,RED_NAME,requested,balance,balance//10,enabled=True)
    screen.batch=batch
    assert screen.prepare(batch)
    assert screen.batch.waves==expected
    assert screen._click.call_count==expected  # entry + N-1 slider clicks, no submit


@pytest.mark.parametrize("count", [9,24])
def test_large_receipt_only_visible_rows_needed(count):
    batch=FuelTicketBatch(CRIMSON_CALYX,RED_NAME,count,count*10,count)
    visible=words(("快速刷取",.50,.248),("刷取次数",.475,.313),(f"{count}/{count}",.54,.314),
        ("第4次刷取",.254,.494),("消耗",.674,.493),("10",.726,.494),
        ("欢愉之蕾·拟造花萼（赤）",.381,.58),("关闭",.402,.756),("再来一次",.619,.756))
    receipt=receipt_dialog(visible,batch,DISPLAY)
    assert (receipt.completed,receipt.spent_tickets,receipt.spent_power)==(count,count,count*10)
    assert receipt_dialog(changed(visible,f"{count}/{count}",f"{count-1}/{count}"),batch,DISPLAY) is None


def test_batch_budget_shadows_and_relics(monkeypatch):
    from tasks.power.fuel_ticket import plan_fuel_ticket_batch
    assert plan_fuel_ticket_batch(STAGNANT_SHADOW,"虚影",30,300,100,enabled=True).waves==8
    for category in ("侵蚀隧洞","饰品提取","历战余响"):
        assert plan_fuel_ticket_batch(category,"任意",30,300,100,enabled=True) is None


def test_count_and_power_can_confirm_when_coupon_digit_unreadable():
    batch=FuelTicketBatch(CRIMSON_CALYX,RED_NAME,9,90,9)
    pre=changed(changed([w for w in confirmation() if w.text!="1"],"刷取次数1","刷取次数9"),"10","90")
    pre+=words(("1039/1000",.692,.061),("92/300",.879,.061))
    assert confirm_dialog(pre,batch,DISPLAY)
    assert confirm_dialog(changed(pre,"90","80"),batch,DISPLAY) is None
    assert confirm_dialog(pre+words(("8",.54,.64)),batch,DISPLAY) is None
