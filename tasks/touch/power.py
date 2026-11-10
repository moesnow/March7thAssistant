"""触屏 720p 生存索引副本。"""
from functools import partial
import re
import time
import unicodedata

import numpy as np
from PIL import Image

from module.automation import auto
from module.automation.automation import screenshot_retry_timeout
from module.config import cfg
from module.game.adb_transport import AdbError
from module.localization import get_raw_instance_names, tr
from module.logger import log
from module.ocr import ocr
from module.screen import screen
from tasks.base.list_drag import changed_ratio, drag_list
from tasks.power.instance import Instance
from tasks.touch.daily import REWARD_POPUP, REWARD_POPUP_CROP
from utils.wait import wait_until


GOLDEN_CALYX = "拟造花萼（金）"
CRIMSON_CALYX = "拟造花萼（赤）"
STAGNANT_SHADOW = "凝滞虚影"
CAVERN = "侵蚀隧洞"
MAX_WAVES = 24
# 界面、单次开拓力、单批挑战上限。
INSTANCES = {
    GOLDEN_CALYX: ("calyx", 10, MAX_WAVES),
    CRIMSON_CALYX: ("calyx", 10, MAX_WAVES),
    STAGNANT_SHADOW: ("stagnant_shadow", 30, 8),
    CAVERN: ("cavern", 40, 6),
}
IMAGES = "./assets/touch_720/images/power"
INDEX_CATEGORY = (177 / 1920, 255 / 1080, 449 / 1920, 680 / 1080)
INDEX_ROWS = (658 / 1920, 256 / 1080, 1095 / 1920, 679 / 1080)
POWER_VALUE = (1555 / 1920, 32 / 1080, 143 / 1920, 45 / 1080)
INSTANCE_TITLE = (1204 / 1920, 105 / 1080, 645 / 1920, 68 / 1080)
QUICK_REFILL = (1777 / 1920, 754 / 1080, 94 / 1920, 52 / 1080)
WAVE_COUNT = (1455 / 1920, 810 / 1080, 175 / 1920, 50 / 1080)
CHALLENGE_COST = (1285 / 1920, 953 / 1080, 75 / 1920, 64 / 1080)
CAVERN_CHALLENGE_COST = (1405 / 1920, 953 / 1080, 75 / 1920, 64 / 1080)
CHALLENGE = (1392 / 1920, 950 / 1080, 461 / 1920, 76 / 1080)
START_CHALLENGE = (1410 / 1920, 946 / 1080, 420 / 1920, 80 / 1080)
TEAM_TABS = (531 / 1920, 14 / 1080, 861 / 1920, 86 / 1080)
BATTLE_CONTROLS = (1665 / 1920, 30 / 1080, 210 / 1920, 63 / 1080)
RESULT_TITLE = (754 / 1920, 109 / 1080, 411 / 1920, 167 / 1080)
RESULT_COUNT = (1135 / 1920, 861 / 1080, 257 / 1920, 48 / 1080)
REPEAT_COST = (1091 / 1920, 917 / 1080, 85 / 1920, 61 / 1080)
REPEAT = (1180 / 1920, 911 / 1080, 290 / 1920, 74 / 1080)
EXIT = (414 / 1920, 906 / 1080, 1075 / 1920, 87 / 1080)
DIALOG = (259 / 1920, 226 / 1080, 1399 / 1920, 505 / 1080)
SUPPLEMENT_TITLE = (787 / 1920, 267 / 1080, 344 / 1920, 84 / 1080)
SUPPLEMENT_DESCRIPTION = (791 / 1920, 598 / 1080, 335 / 1920, 51 / 1080)
SUPPLEMENT_CANCEL = (474 / 1920, 740 / 1080, 450 / 1920, 79 / 1080)
SUPPLEMENT_CONFIRM = (992 / 1920, 740 / 1080, 450 / 1920, 79 / 1080)
RESERVE_AMOUNT_CONFIRM = (992 / 1920, 812 / 1080, 450 / 1920, 91 / 1080)
FUEL_AMOUNT = (1222 / 1920, 598 / 1080, 60 / 1920, 51 / 1080)


class PowerError(RuntimeError):
    """副本未达到继续消耗开拓力所需的状态。"""


def parse_power(text):
    match = re.fullmatch(r"(\d{1,3})/300", _normalize(text))
    return int(match[1]) if match else None


def _normalize(text):
    return "".join(unicodedata.normalize("NFKC", text).split())


def _read_number(crop, parse, error):
    for _ in range(6):
        frame, _, _ = auto.take_screenshot(crop=crop)
        enlarged = frame.resize((frame.width * 2, frame.height * 2))
        lines = ocr.recognize_multi_lines(enlarged) or []
        text = "".join(text for _, (text, _) in sorted(lines, key=lambda line: line[0][0][0]))
        value = parse(text)
        if value is not None:
            return value
        time.sleep(0.2)
    raise PowerError(error)


def read_power():
    return _read_number(POWER_VALUE, parse_power, "未能确认当前开拓力")


def _read_waves(crop, label):
    def parse(text):
        match = re.fullmatch(rf"{label}:?(\d{{1,2}})", _normalize(text))
        if match and 1 <= int(match[1]) <= MAX_WAVES:
            return int(match[1])
        return None

    return _read_number(crop, parse, f"未能确认{label}")


def _read_cost(crop):
    def parse(text):
        match = re.fullmatch(r"[xX×]?(\d{1,3})", _normalize(text))
        return int(match[1]) if match else None

    return _read_number(crop, parse, "未能确认挑战按钮上的开拓力消耗")


def _tap(x, y):
    if not auto.click_element((x / 1920, y / 1080, 0, 0), "crop"):
        raise PowerError("触屏点按失败")


def _click_text(text, crop, *, retries=8):
    return auto.click_element(text, "text", crop=crop, max_retries=retries, retry_delay=0.3)


def _select_category(instance_type):
    screen.change_to("guide3", max_recursion=1)
    if not _click_text(instance_type, INDEX_CATEGORY, retries=3):
        top = (535 / 1920, 389 / 1080)
        bottom = (535 / 1920, 834 / 1080)
        start, end = (bottom, top) if instance_type in (STAGNANT_SHADOW, CAVERN) else (top, bottom)
        if not drag_list(auto, start, end, crop=INDEX_CATEGORY):
            raise PowerError("无法拖动生存索引分类")
        if not _click_text(instance_type, INDEX_CATEGORY):
            raise PowerError(f"未找到生存索引里的{instance_type}")
    time.sleep(0.5)


def find_instance_entry(lines, name):
    """只选与副本名称（赤萼为地区）属于同一行的按钮。"""
    name = _normalize(name)
    names = []
    buttons = []
    for box, (text, _) in lines:
        x, y = np.mean(box, axis=0)
        if x < 330 and _normalize(text) == name:
            names.append(y)
        elif text in ("进入", "追踪", "传送") and x > 560:
            buttons.append((y, box, text))
    for name_y in sorted(names):
        matches = [button for button in buttons if abs(button[0] - name_y) <= 35]
        if len(matches) == 1:
            return matches[0][1:]
    return None


def _enter_instance(instance_type, name):
    instance_screen, _, _ = INSTANCES[instance_type]
    for _ in range(12):
        before, _, _ = auto.take_screenshot(crop=INDEX_ROWS)
        auto.perform_ocr()
        if entry := find_instance_entry(auto.ocr_result, name):
            box, label = entry
            if label != "进入":
                raise PowerError(f"{name} 当前显示「{label}」，无法直接进入")
            if not auto.click_element_with_pos(auto.calculate_text_position(box, False)):
                raise PowerError(f"无法点击 {name} 的进入按钮")
            screen.wait_for_screen_change(instance_screen, max_recursion=0)
            title = get_raw_instance_names()[instance_type][name] if instance_type == CRIMSON_CALYX else name
            if not auto.find_element(title, "text", include=True, crop=INSTANCE_TITLE,
                                     max_retries=6, retry_delay=0.3):
                raise PowerError(f"未确认进入指定副本 {name}")
            return
        if not drag_list(auto, (1100 / 1920, 814 / 1080), (1100 / 1920, 405 / 1080),
                         crop=INDEX_ROWS, end_pause=0.2, settle=0.4):
            raise PowerError("生存索引列表未稳定")
        if changed_ratio(before, auto.screenshot) <= 0.01:
            break
    raise PowerError(f"生存索引未找到 {name} 的进入按钮")


def _finish_supplement(source):
    # 数量弹窗与首屏「确认」的高度不同，兑换后还可能保留补充首屏。
    time.sleep(0.8)
    reward = auto.find_element(REWARD_POPUP, "image", 0.9, crop=REWARD_POPUP_CROP)
    if not reward and not screen.check_screen("guide3"):
        if not auto.find_element(source, "text", include=True, crop=DIALOG,
                                 max_retries=4, retry_delay=0.3):
            raise PowerError("未确认补充数量弹窗的资源类型")
        if source == "燃料":
            _read_number(FUEL_AMOUNT, lambda text: 1 if _normalize(text) == "1" else None,
                         "未确认只使用 1 个燃料")
        confirm = SUPPLEMENT_CONFIRM if source == "燃料" else RESERVE_AMOUNT_CONFIRM
        if not _click_text("确认", confirm):
            raise PowerError("无法确认补充数量")
        reward = auto.find_element(REWARD_POPUP, "image", 0.9, crop=REWARD_POPUP_CROP,
                                   max_retries=8, retry_delay=0.25)
    if reward:
        _tap(960, 854)
        time.sleep(0.5)
    if auto.find_element("开拓力补充", "text", crop=SUPPLEMENT_TITLE):
        if not _click_text("取消", SUPPLEMENT_CANCEL):
            raise PowerError("无法关闭补充完成后的开拓力弹窗")
    screen.wait_for_screen_change("guide3", max_recursion=0)


def _supplement(power):
    """只选已启用的后备开拓力或燃料，优先后备开拓力。"""
    if power >= 300 or not (cfg.use_reserved_trailblaze_power or cfg.use_fuel):
        return power

    _tap(1720, 55)
    if not auto.find_element("开拓力补充", "text", crop=SUPPLEMENT_TITLE,
                             max_retries=8, retry_delay=0.3):
        raise PowerError("未找到开拓力补充弹窗")
    for enabled, image, label, crop in (
        (cfg.use_reserved_trailblaze_power, "reserve", "取出等量后备开拓力",
         (708 / 1920, 405 / 1080, 164 / 1920, 191 / 1080)),
        (cfg.use_fuel, "fuel", "兑换60开拓力", (880 / 1920, 405 / 1080, 165 / 1920, 191 / 1080)),
    ):
        if not enabled:
            continue
        if not auto.find_element(label, "text", crop=SUPPLEMENT_DESCRIPTION):
            if not auto.click_element(f"{IMAGES}/{image}.png", "image", 0.9, crop=crop):
                raise PowerError("未确认开拓力补充方式")
            if not auto.find_element(label, "text", crop=SUPPLEMENT_DESCRIPTION,
                                     max_retries=5, retry_delay=0.3):
                raise PowerError("开拓力补充方式与配置不符")
        stock_crop = (crop[0] + 17 / 1920, 545 / 1080, 121 / 1920, 39 / 1080)
        stock = _read_number(stock_crop, lambda text: int(text) if text.isdecimal() else None,
                             "未识别到补充资源的库存")
        if not stock:
            continue
        if not _click_text("确认", SUPPLEMENT_CONFIRM):
            raise PowerError("无法确认已选的开拓力补充方式")

        _finish_supplement("后备开拓力" if image == "reserve" else "燃料")
        supplemented = read_power()
        if supplemented <= power:
            raise PowerError("确认补充后，开拓力未确认增加")
        log.info(f"开拓力由 {power} 补充至 {supplemented}")
        return supplemented

    if not _click_text("取消", SUPPLEMENT_CANCEL):
        raise PowerError("无法关闭开拓力补充弹窗")
    screen.wait_for_screen_change("guide3", max_recursion=0)
    return power


def _select_team(instance_type, name):
    team = str(Instance.get_target_team(instance_type, name)).zfill(2)
    if not re.fullmatch(r"0[1-9]|1[0-9]", team):
        raise PowerError(f"队伍编号 {team} 格式错误")
    start, end = (1220 / 1920, 60 / 1080), (678 / 1920, 60 / 1080)
    if int(team) <= 6:
        start, end = end, start
    for _ in range(5):
        if _click_text(team, TEAM_TABS, retries=2):
            time.sleep(0.7)
            log.info(f"已点选队伍 {team}")
            return
        if not drag_list(auto, start, end, crop=TEAM_TABS, settle=0.4):
            break
    raise PowerError(f"未找到队伍 {team}")


def _start_challenge(instance_type, name, waves, *, borrow_for_daily=False):
    _, cost, limit = INSTANCES[instance_type]
    if not auto.find_element(f"{IMAGES}/quick_refill_off.png", "image", 0.90, crop=QUICK_REFILL):
        raise PowerError("请关闭副本界面的「快捷补充开拓力」")
    for _ in range(limit):
        selected = _read_waves(WAVE_COUNT, "挑战次数")
        if selected == waves:
            break
        _tap(1821 if selected < waves else 1270, 866)
        time.sleep(0.22)
    else:
        raise PowerError(f"无法把挑战次数设为 {waves}")
    cost_crop = CAVERN_CHALLENGE_COST if instance_type == CAVERN else CHALLENGE_COST
    if _read_cost(cost_crop) != waves * cost or read_power() < waves * cost:
        raise PowerError("挑战消耗与已确认的波次或开拓力不符")
    if not _click_text("挑战", CHALLENGE):
        raise PowerError("未找到副本的挑战按钮")
    if not auto.find_element("开始挑战", "text", crop=START_CHALLENGE, max_retries=18, retry_delay=0.4):
        _check_popup()
        raise PowerError("未进入副本编队页")
    if cfg.instance_team_enable:
        _select_team(instance_type, name)
    if cfg.borrow_enable and (cfg.borrow_character_enable or borrow_for_daily):
        from tasks.touch import support

        support.borrow()
    time.sleep(0.6)
    if not _click_text("开始挑战", START_CHALLENGE):
        raise PowerError("无法开始挑战")


def _check_popup():
    auto.take_screenshot(crop=DIALOG)
    auto.perform_ocr()
    text = "".join(text for _, (text, _) in auto.ocr_result)
    if any(message in text for message in ("网络连接", "连接断开", "重新登录", "网络错误", "连接超时")):
        raise PowerError("检测到游戏掉线，停止当前清体力")
    if "开拓力补充" in text:
        if _click_text("取消", SUPPLEMENT_CANCEL):
            raise PowerError("已取消非预期的开拓力补充弹窗")
        raise PowerError("检测到非预期的开拓力补充弹窗")
    if any(message in text for message in ("无法战斗状态", "持有数量已达上限", "长时间未操作", "是否切换")):
        raise PowerError("检测到阻止挑战的弹窗，请检查游戏画面")


def _exit_result(instance_screen):
    if not _click_text("退出关卡", EXIT):
        raise PowerError("未找到退出关卡按钮")
    if not wait_until(lambda: any(screen.check_screen(target) for target in (instance_screen, "guide3", "main")), 25, 0.5):
        raise PowerError("退出关卡后未回到副本、生存索引或主界面")
    time.sleep(0.5)


def classify_auto_button(pixels, glyph):
    """同一枚半透明图标的金色和灰色状态，用图标内外的色差判断。"""
    red, green, blue = np.moveaxis(pixels.astype(np.int16), -1, 0)
    gold = (red >= 170) & (green >= 143) & (green - blue >= 32)
    gold_share = gold[glyph].mean()
    contrast = np.median((green - blue)[glyph]) - np.median((green - blue)[~glyph])
    if gold_share - gold[~glyph].mean() >= 0.30 and contrast >= 20:
        return True
    if gold_share < 0.15 and abs(contrast) < 22:
        if np.median(green[glyph]) - np.median(green[~glyph]) >= 35:
            return False
    return None


def _observe_battle(glyph, *, allow_team, check_popups):
    if auto.find_element(f"{IMAGES}/victory.png", "image", 0.88, crop=RESULT_TITLE):
        return "victory", None
    if check_popups:
        if auto.find_element(("挑战失败", "战斗失败"), "text", crop=RESULT_TITLE):
            return "defeat", None
        _check_popup()
    if auto.find_element(f"{IMAGES}/pause.png", "image", 0.86, crop=BATTLE_CONTROLS):
        # 裁剪范围内原生 720p 图标的相对位置。
        pixels = np.asarray(auto.screenshot.convert("RGB"))[7:32, 18:59]
        return "battle", classify_auto_button(pixels, glyph)
    if allow_team and auto.find_element("开始挑战", "text", crop=START_CHALLENGE):
        return "team", None
    return None, None


def _wait_battle(*, repeated=False, instance_screen="calyx"):
    with Image.open(f"{IMAGES}/auto_glyph.png") as image:
        glyph = np.asarray(image.convert("L")) > 0
    deadline = time.monotonic() + 600
    start_deadline = time.monotonic() + 90
    left_result = not repeated
    saw_battle = False
    confirmed_auto = False
    auto_clicks = 0
    off_frames = 0
    team_retries = 0
    next_team_click = time.monotonic() + 3
    next_auto_click = 0.0
    next_popup_check = 0.0
    clock_error_since = None
    while time.monotonic() < deadline:
        check_popups = time.monotonic() >= next_popup_check
        try:
            state, status = _observe_battle(glyph, allow_team=not saw_battle, check_popups=check_popups)
        except AdbError as error:
            if error.code != "frame_clock_unavailable":
                raise
            now = time.monotonic()
            if clock_error_since is None:
                clock_error_since = now
                log.warning("ADB 战斗帧时钟暂不可比，等待可校验的新帧")
            if now - clock_error_since >= 15:
                raise
            off_frames = 0
            time.sleep(0.45)
            continue
        clock_error_since = None
        if check_popups:
            next_popup_check = time.monotonic() + 3

        if state == "victory" and left_result:
            if not confirmed_auto:
                log.warning("战斗已结算，未截到确认自动战斗开启的画面")
            return
        left_result = left_result or state != "victory"
        if state == "defeat":
            _exit_result(instance_screen)
            screen.change_to("main", max_recursion=0)
            raise PowerError("副本挑战失败，已退出关卡")
        if state == "battle":
            saw_battle = True
            if not confirmed_auto:
                off_frames = off_frames + 1 if status is False else 0
                if status is True:
                    confirmed_auto = True
                    log.info("已确认触屏自动战斗开启")
                elif off_frames >= 2 and time.monotonic() >= next_auto_click:
                    if auto_clicks >= 3:
                        raise PowerError("点击触屏自动战斗按钮后未确认开启")
                    _tap(1721, 60)
                    auto_clicks += 1
                    off_frames = 0
                    next_auto_click = time.monotonic() + 2
                    log.info("已点按触屏自动战斗按钮")
        else:
            off_frames = 0
            if state == "team" and time.monotonic() >= next_team_click:
                if team_retries >= 2:
                    raise PowerError("多次点按开始挑战后仍停在编队页")
                if not _click_text("开始挑战", START_CHALLENGE):
                    raise PowerError("编队页开始挑战按钮无法点击")
                log.info("确认仍在编队页，点按开始挑战")
                team_retries += 1
                next_team_click = time.monotonic() + 3
        if not saw_battle and time.monotonic() >= start_deadline:
            raise PowerError("等待进入战斗超时，请检查游戏画面")
        time.sleep(0.45)
    raise PowerError("等待战斗结算超时，请检查游戏画面")


def _run_instance(instance_type, name, planned, *, borrow_for_daily=False, on_settlement=None):
    instance_screen, cost, limit = INSTANCES[instance_type]
    batch_limit = cfg.instance_names_challenge_count.get(instance_type, limit)
    if type(batch_limit) is not int or not 1 <= batch_limit <= limit:
        log.warning(f"{instance_type} 的连续挑战次数无效，使用 {limit}")
        batch_limit = limit

    _select_category(instance_type)
    power = _supplement(read_power())
    remaining = min(planned, power // cost) if planned is not None else power // cost
    log.info(f"{instance_type} · {name}，开拓力 {power}/300，本次最多挑战 {remaining} 次")
    if not remaining:
        log.info("开拓力不足，返回主界面")
        screen.change_to("main", max_recursion=1)
        if on_settlement is not None:
            on_settlement(0, power)
        return

    _enter_instance(instance_type, name)
    previous = 0
    while remaining > 0:
        waves = min(remaining, batch_limit)
        repeated = waves == previous
        if repeated:
            if _read_cost(REPEAT_COST) != waves * cost or not _click_text("再来一次", REPEAT):
                raise PowerError("未确认再来一次的开拓力消耗或按钮")
            log.info(f"再来一次，挑战 {waves} 次")
        else:
            if previous:
                _exit_result(instance_screen)
                if screen.current_screen != instance_screen:
                    _select_category(instance_type)
                    _enter_instance(instance_type, name)
            _start_challenge(instance_type, name, waves, borrow_for_daily=borrow_for_daily)
        _wait_battle(repeated=repeated, instance_screen=instance_screen)

        completed = _read_waves(RESULT_COUNT, "上轮挑战波次")
        available = read_power()
        expected = power - waves * cost
        if completed != waves or not expected <= available <= expected + 2:
            raise PowerError("结算波次或开拓力变化与预期不符，停止重试")
        power = available
        remaining = min(remaining - completed, power // cost)
        previous = waves
        log.info(f"本轮已结算 {completed} 次挑战，剩余开拓力 {power}/300")
        if on_settlement is not None:
            on_settlement(completed, power)
        yield completed
        borrow_for_daily = False

    _exit_result(instance_screen)
    screen.change_to("main", max_recursion=1)
    log.info("开拓力不足，已返回主界面" if power < cost else "已达到本次挑战次数，返回主界面")


def _run(borrow_for_daily, on_settlement=None):
    run_instance = _run_instance if on_settlement is None else partial(_run_instance, on_settlement=on_settlement)
    names = get_raw_instance_names()
    plan = cfg.power_plan
    if not plan:
        instance_type = cfg.instance_type
        if not isinstance(instance_type, str) or instance_type not in INSTANCES:
            log.warning(f"触屏清体力暂不支持 {instance_type}")
            return False
        name = cfg.instance_names.get(instance_type)
        if name == "无":
            log.info(f"{instance_type}未开启")
            return True
        if name not in names[instance_type]:
            raise PowerError(f"未配置有效的{instance_type}副本名称")
        for _ in run_instance(instance_type, name, None, borrow_for_daily=borrow_for_daily):
            pass
        return True

    remaining = list(plan)
    ran = False
    for index, item in enumerate(plan):
        if not isinstance(item, (list, tuple)) or len(item) != 3:
            log.warning(f"体力计划第 {index + 1} 项格式无效，已保留")
            continue
        instance_type, name, count = item
        if (not isinstance(instance_type, str) or instance_type not in INSTANCES
                or not isinstance(name, str) or name not in names[instance_type] or name == "无"
                or type(count) is not int or count <= 0):
            log.warning(f"体力计划第 {index + 1} 项不受触屏模式支持，已保留")
            continue
        ran = True
        for completed in run_instance(instance_type, name, count, borrow_for_daily=borrow_for_daily):
            count -= completed
            borrow_for_daily = False
            if not cfg.power_plan_keep:
                remaining[index] = [instance_type, name, count] if count else None
                cfg.set_value("power_plan", [item for item in remaining if item is not None])
        if count:
            break  # 体力不足，保留该计划和后续项目。
    return ran


def run(*, borrow_for_daily=False, on_summary=None):
    total = 0
    remaining = None

    def record_settlement(completed, power):
        nonlocal total, remaining
        total += completed
        remaining = power

    log.hr("开始触屏清体力", 0)
    with screenshot_retry_timeout(5):
        try:
            succeeded = _run(borrow_for_daily, record_settlement if on_summary is not None else None)
        except PowerError as error:
            log.error(f"触屏清体力：{error}")
            return False
    if succeeded and on_summary is not None and remaining is not None:
        on_summary(tr("已完成 {count} 次挑战，剩余开拓力 {power}/300").format(count=total, power=remaining))
    return succeeded
