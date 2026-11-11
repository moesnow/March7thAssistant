"""触屏位面饰品提取。"""
import time

from module.automation import auto
from module.config import cfg
from module.logger import log
from module.screen import screen
from tasks.base.list_drag import drag_list
from tasks.power.instance import Instance
from tasks.power.policy import parse_ornament_payment as parse_payment
from tasks.touch import power, support
from utils.wait import wait_until


INDEX_POWER = (1350 / 1920, 32 / 1080, 144 / 1920, 45 / 1080)
DETAIL_POWER = (1377 / 1920, 32 / 1080, 149 / 1920, 45 / 1080)
WAVES = (1504 / 1920, 822 / 1080, 174 / 1920, 49 / 1080)
PAYMENT = (1374 / 1920, 958 / 1080, 144 / 1920, 57 / 1080)
REPEAT_PAYMENT = (1040 / 1920, 907 / 1080, 240 / 1920, 84 / 1080)
PRESETS = (448 / 1920, 61 / 1080, 166 / 1920, 49 / 1080)
TEAM_NAMES = (47 / 1920, 140 / 1080, 169 / 1920, 862 / 1080)
ARENA_TITLE = (60 / 1920, 7 / 1080, 131 / 1920, 51 / 1080)
BOSS_NAME = (756 / 1920, 45 / 1080, 462 / 1920, 61 / 1080)


def _prepare_payment(waves, available):
    while waves > 0:
        power._set_challenge_waves(waves, 6, crop=WAVES, minus=1359, y=875)
        # 以开始挑战按钮的实际消耗为准。顶部沉浸器库存不参与调度或结算。
        cost, immersifiers = power._read_number(PAYMENT, lambda text: parse_payment(text, waves),
                                                "未能确认饰品提取的挑战消耗")
        if cost <= available:
            return waves, cost, immersifiers
        waves -= (cost - available + 39) // 40
    return 0, 0, 0


def _start_challenge():
    if not power._click_text("开始挑战", power.START_CHALLENGE):
        raise power.PowerError("无法开始饰品提取")
    if auto.find_element("仍有角色位空缺", "text", include=True, crop=power.DIALOG,
                         max_retries=4, retry_delay=0.3):
        if not power._click_text("确认", power.DIALOG_CONFIRM):
            raise power.PowerError("无法确认饰品提取的空位提示")
    if auto.find_element("当前不存在任何存档", "text", include=True, crop=power.DIALOG,
                         max_retries=3, retry_delay=0.35):
        if not power._click_text("确认", power.DIALOG_CONFIRM):
            raise power.PowerError("无法确认无存档直接挑战")
    if auto.find_element(("请配置出战队伍", "未上阵角色"), "text", include=True):
        return False
    _engage_boss()
    return True


def _arena_visible():
    return auto.find_element("差分宇宙", "text", crop=ARENA_TITLE)


def _engage_boss():
    def ready():
        power._check_popup()
        return _arena_visible() and auto.find_element("等级", "text", include=True, crop=BOSS_NAME)

    if not wait_until(ready, 45, 0.5):
        raise power.PowerError("未进入饰品提取首领场地")
    for _ in range(3):
        if not auto.drag_mouse((369 / 1920, 840 / 1080), (369 / 1920, 698 / 1080), 0.6, 0.45):
            raise power.PowerError("无法操作摇杆接近饰品提取首领")
        if not _arena_visible():
            return
        power._tap(1598, 821)
        time.sleep(2)
        if not _arena_visible():
            return
    raise power.PowerError("接近并攻击首领后仍未进入战斗")


def _select_team(name, team=None):
    if team is None:
        team = Instance.get_target_team(power.ORNAMENT, name)
    team = str(team)
    if not team.isascii() or not team.isdecimal() or not 1 <= int(team) <= 19:
        raise power.PowerError(f"队伍编号 {team} 格式错误")
    label = f"队伍{int(team)}"
    power._tap(822, 775)
    if not power._click_text("预设编队", PRESETS):
        raise power.PowerError("未找到饰品提取的预设编队")
    time.sleep(0.5)
    for _ in range(9):
        if power._click_text(label, TEAM_NAMES, retries=2):
            time.sleep(0.45)
            power._tap(1848, 55)
            screen.wait_for_screen_change("ornament", max_recursion=0)
            log.info(f"已点选饰品提取的{label}")
            return
        if not drag_list(auto, (544 / 1920, 815 / 1080), (544 / 1920, 366 / 1080),
                         crop=TEAM_NAMES, end_pause=0.2, settle=0.4):
            break
    raise power.PowerError(f"饰品提取未找到{label}")


def run_instance(name, planned, batch_limit, borrow_for_daily, on_settlement):
    instance_screen = power.INSTANCES[power.ORNAMENT][0]
    demand = (borrow_for_daily if isinstance(borrow_for_daily, power.SupportDemand)
              else power.SupportDemand(borrow_for_daily))

    def enter():
        power._select_category(power.ORNAMENT)
        power._enter_instance(power.ORNAMENT, name)
        return power.read_power(DETAIL_POWER)

    power._select_category(power.ORNAMENT)
    power._supplement(power.read_power(INDEX_POWER), plus=(1510, 55), power_crop=INDEX_POWER)
    power._enter_instance(power.ORNAMENT, name)
    available = power.read_power(DETAIL_POWER)
    remaining = planned
    previous = 0
    borrowed = False
    retries = 0
    cleaned = False
    while remaining is None or remaining > 0:
        requested = batch_limit if remaining is None else min(batch_limit, remaining)
        started = time.monotonic()
        repeated = False
        try:
            if previous == requested and (not demand.pending or borrowed):
                try:
                    cost, immersifiers = power._read_number(
                        REPEAT_PAYMENT, lambda text: parse_payment(text, requested), "未能确认再来一次费用",
                    )
                except power.PowerError:
                    pass
                else:
                    if cost <= available:
                        if not power._click_text("再来一次", power.REPEAT):
                            power._check_popup()
                            raise power.PowerError("无法点击饰品提取再来一次")
                        waves = requested
                        repeated = True

            if not repeated:
                if previous:
                    power._exit_result(instance_screen)
                    previous = 0
                    if screen.current_screen == instance_screen:
                        available = power.read_power(DETAIL_POWER)
                    else:
                        available = enter()
                waves, cost, immersifiers = _prepare_payment(requested, available)
                if not waves:
                    log.info("饰品提取资源不足，结束本副本项")
                    if on_settlement is not None:
                        on_settlement(0, available)
                    break
                if cfg.instance_team_enable:
                    _select_team(name)
                borrowed = demand.should_borrow(cfg) and support.borrow(ornament=True)
                if _start_challenge() is False:
                    log.info("饰品提取未配置出战队伍，尝试队伍 1")
                    _select_team(name, 1)
                    borrowed = demand.should_borrow(cfg) and support.borrow(ornament=True)
                    if _start_challenge() is False:
                        raise power.PowerError("无法为饰品提取配置队伍 1")
            log.info(f"饰品提取 · {name}，挑战 {waves} 次，使用沉浸器 {immersifiers} 个和开拓力 {cost} 点")
            power._wait_battle(repeated=repeated, instance_screen=instance_screen)
        except power.BattleDefeat:
            power._select_category(power.ORNAMENT)
            after = power.read_power(INDEX_POWER)
            power.check_balance(available, after, 0, time.monotonic() - started)
            if retries >= power.DEFEAT_RETRIES:
                raise
            retries += 1
            log.warning(f"已确认饰品提取战败且未扣费，重试 {retries}/{power.DEFEAT_RETRIES}")
            available, previous = enter(), 0
            continue
        except power.RelicBagFull:
            if cleaned or not power._clean_full_bag():
                raise
            cleaned = True
            available, previous = enter(), 0
            continue

        # 单场只有胜利及奖励，连续挑战还须核对结算波次。
        completed = 1 if waves == 1 else power._read_waves(power.RESULT_COUNT, "上轮挑战波次")
        if completed > waves:
            raise power.PowerError("饰品提取实际结算次数超过已选波次")
        demand.won(borrowed)
        yield completed
        after = power.read_power(INDEX_POWER)
        if completed != waves:
            raise power.PowerError(f"饰品提取实际结算 {completed}/{waves} 次，已保留确认的进度")
        power.check_balance(available, after, cost, time.monotonic() - started)
        log.info(f"饰品提取已结算 {completed} 次，剩余开拓力 {after}/300")
        if on_settlement is not None:
            on_settlement(completed, after)
        if remaining is not None:
            remaining -= completed
        available, previous, retries = after, waves, 0

    if previous:
        power._exit_result(instance_screen)
    screen.change_to("main", max_recursion=1)
