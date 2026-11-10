"""触屏 720p 拟造花萼（金）。"""
import re
import time
import unicodedata

import numpy as np
from PIL import Image

from module.automation import auto
from module.automation.automation import screenshot_retry_timeout
from module.config import cfg
from module.game.adb_transport import AdbError
from module.localization import get_raw_instance_names
from module.logger import log
from module.ocr import ocr
from module.screen import screen
from tasks.base.list_drag import changed_ratio, drag_list
from tasks.game import wait_until
from tasks.power.instance import Instance


GOLDEN_CALYX = "拟造花萼（金）"
POWER_COST = 10
MAX_WAVES = 24
IMAGES = "./assets/touch_720/images/power"
INDEX_CATEGORY = (177 / 1920, 255 / 1080, 449 / 1920, 680 / 1080)
INDEX_ROWS = (658 / 1920, 256 / 1080, 1095 / 1920, 679 / 1080)
POWER_VALUE = (1555 / 1920, 32 / 1080, 143 / 1920, 45 / 1080)
CALYX_TITLE = (1204 / 1920, 105 / 1080, 645 / 1920, 68 / 1080)
QUICK_REFILL = (1777 / 1920, 754 / 1080, 94 / 1920, 52 / 1080)
WAVE_COUNT = (1455 / 1920, 810 / 1080, 175 / 1920, 50 / 1080)
CHALLENGE_COST = (1285 / 1920, 953 / 1080, 75 / 1920, 64 / 1080)
CHALLENGE = (1392 / 1920, 950 / 1080, 461 / 1920, 76 / 1080)
START_CHALLENGE = (1410 / 1920, 946 / 1080, 420 / 1920, 80 / 1080)
TEAM_TABS = (531 / 1920, 14 / 1080, 861 / 1920, 86 / 1080)
BATTLE_CONTROLS = (1665 / 1920, 30 / 1080, 210 / 1920, 63 / 1080)
RESULT_TITLE = (754 / 1920, 109 / 1080, 411 / 1920, 117 / 1080)
RESULT_COUNT = (1135 / 1920, 861 / 1080, 257 / 1920, 48 / 1080)
REPEAT_COST = (1091 / 1920, 917 / 1080, 85 / 1920, 61 / 1080)
REPEAT = (1180 / 1920, 911 / 1080, 290 / 1920, 74 / 1080)
EXIT = (414 / 1920, 906 / 1080, 1075 / 1920, 87 / 1080)
DIALOG = (259 / 1920, 226 / 1080, 1399 / 1920, 505 / 1080)
SUPPLEMENT_TITLE = (787 / 1920, 267 / 1080, 344 / 1920, 84 / 1080)
SUPPLEMENT_DESCRIPTION = (791 / 1920, 598 / 1080, 335 / 1920, 51 / 1080)
SUPPLEMENT_CANCEL = (474 / 1920, 740 / 1080, 450 / 1920, 79 / 1080)
SUPPLEMENT_CONFIRM = (992 / 1920, 740 / 1080, 450 / 1920, 79 / 1080)


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


def _select_category():
    screen.change_to("guide3", max_recursion=1)
    if not _click_text(GOLDEN_CALYX, INDEX_CATEGORY, retries=3):
        if not drag_list(auto, (535 / 1920, 389 / 1080), (535 / 1920, 834 / 1080), crop=INDEX_CATEGORY):
            raise PowerError("无法拖动生存索引分类")
        if not _click_text(GOLDEN_CALYX, INDEX_CATEGORY):
            raise PowerError("未找到生存索引里的拟造花萼（金）")
    time.sleep(0.5)


def find_calyx_entry(lines, name):
    """选择与副本名同一行的按钮，防止列表边缘的截断行匹配到相邻副本。"""
    names = []
    buttons = []
    for box, (text, _) in lines:
        x, y = np.mean(box, axis=0)
        if text == name and x < 330:
            names.append(y)
        elif text in ("进入", "追踪", "传送") and x > 560:
            buttons.append((y, box, text))
    for name_y in sorted(names):
        matches = [button for button in buttons if abs(button[0] - name_y) <= 35]
        if len(matches) == 1:
            return matches[0][1:]
    return None


def _enter_calyx(name):
    for _ in range(12):
        before, _, _ = auto.take_screenshot(crop=INDEX_ROWS)
        auto.perform_ocr()
        if entry := find_calyx_entry(auto.ocr_result, name):
            box, label = entry
            if label != "进入":
                raise PowerError(f"{name} 当前显示「{label}」，无法直接进入")
            if not auto.click_element_with_pos(auto.calculate_text_position(box, False)):
                raise PowerError(f"无法点击 {name} 的进入按钮")
            screen.wait_for_screen_change("calyx", max_recursion=0)
            if not auto.find_element(name, "text", include=True, crop=CALYX_TITLE,
                                     max_retries=6, retry_delay=0.3):
                raise PowerError(f"未确认进入指定副本 {name}")
            return
        if not drag_list(auto, (1100 / 1920, 814 / 1080), (1100 / 1920, 405 / 1080),
                         crop=INDEX_ROWS, end_pause=0.2, settle=0.4):
            raise PowerError("生存索引列表未稳定")
        if changed_ratio(before, auto.screenshot) <= 0.01:
            break
    raise PowerError(f"生存索引未找到 {name} 的进入按钮")


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

        # 若界面还要求选择数量，按已明确显示的资源类型确认默认数量。
        time.sleep(0.8)
        if not screen.check_screen("guide3"):
            source = "后备开拓力" if image == "reserve" else "燃料"
            if not auto.find_element(source, "text", include=True, crop=DIALOG,
                                     max_retries=4, retry_delay=0.3):
                raise PowerError("未确认补充数量弹窗的资源类型")
            if not _click_text("确认", SUPPLEMENT_CONFIRM):
                raise PowerError("无法确认补充数量")
            screen.wait_for_screen_change("guide3", max_recursion=0)
        supplemented = read_power()
        if supplemented <= power:
            raise PowerError("确认补充后，开拓力未确认增加")
        log.info(f"开拓力由 {power} 补充至 {supplemented}")
        return supplemented

    if not _click_text("取消", SUPPLEMENT_CANCEL):
        raise PowerError("无法关闭开拓力补充弹窗")
    screen.wait_for_screen_change("guide3", max_recursion=0)
    return power


def _select_team(name):
    team = str(Instance.get_target_team(GOLDEN_CALYX, name)).zfill(2)
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


def _start_challenge(name, waves):
    if not auto.find_element(f"{IMAGES}/quick_refill_off.png", "image", 0.90, crop=QUICK_REFILL):
        raise PowerError("请关闭副本界面的「快捷补充开拓力」")
    for _ in range(MAX_WAVES):
        selected = _read_waves(WAVE_COUNT, "挑战次数")
        if selected == waves:
            break
        _tap(1821 if selected < waves else 1270, 866)
        time.sleep(0.22)
    else:
        raise PowerError(f"无法把挑战次数设为 {waves}")
    if _read_cost(CHALLENGE_COST) != waves * POWER_COST or read_power() < waves * POWER_COST:
        raise PowerError("挑战消耗与已确认的波次或开拓力不符")
    if not _click_text("挑战", CHALLENGE):
        raise PowerError("未找到拟造花萼的挑战按钮")
    if not auto.find_element("开始挑战", "text", crop=START_CHALLENGE, max_retries=18, retry_delay=0.4):
        _check_popup()
        raise PowerError("未进入副本编队页")
    if cfg.instance_team_enable:
        _select_team(name)
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


def _exit_result():
    if not _click_text("退出关卡", EXIT):
        raise PowerError("未找到退出关卡按钮")
    if not wait_until(lambda: screen.check_screen("calyx") or screen.check_screen("main"), 25, 0.5):
        raise PowerError("退出关卡后未回到拟造花萼或主界面")
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


def _observe_battle(glyph, *, repeated, check_popups):
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
    if repeated and auto.find_element("开始挑战", "text", crop=START_CHALLENGE):
        return "team", None
    return None, None


def _wait_battle(*, repeated=False):
    with Image.open(f"{IMAGES}/auto_glyph.png") as image:
        glyph = np.asarray(image.convert("L")) > 0
    deadline = time.monotonic() + 600
    start_deadline = time.monotonic() + 90
    left_result = not repeated
    saw_battle = False
    confirmed_auto = False
    auto_clicks = 0
    off_frames = 0
    next_auto_click = 0.0
    next_popup_check = 0.0
    clock_error_since = None
    while time.monotonic() < deadline:
        check_popups = time.monotonic() >= next_popup_check
        try:
            state, status = _observe_battle(glyph, repeated=repeated, check_popups=check_popups)
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
            _exit_result()
            screen.change_to("main", max_recursion=0)
            raise PowerError("拟造花萼挑战失败，已退出关卡")
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
            if state == "team":
                if not _click_text("开始挑战", START_CHALLENGE):
                    raise PowerError("再来一次后无法开始挑战")
                repeated = False
        if not saw_battle and time.monotonic() >= start_deadline:
            raise PowerError("等待进入战斗超时，请检查游戏画面")
        time.sleep(0.45)
    raise PowerError("等待战斗结算超时，请检查游戏画面")


def _run_calyx(name, planned, batch_limit):
    _select_category()
    power = _supplement(read_power())
    remaining = min(planned, power // POWER_COST) if planned is not None else power // POWER_COST
    log.info(f"{GOLDEN_CALYX} · {name}，开拓力 {power}/300，本次最多挑战 {remaining} 次")
    if not remaining:
        log.info("开拓力不足，返回主界面")
        screen.change_to("main", max_recursion=1)
        return

    _enter_calyx(name)
    previous = 0
    while remaining > 0:  # 每次成功结算后按确认的波次扣减，且初始开拓力限制总次数。
        waves = min(remaining, batch_limit)
        repeated = waves == previous
        if repeated:
            if _read_cost(REPEAT_COST) != waves * POWER_COST or not _click_text("再来一次", REPEAT):
                raise PowerError("未确认再来一次的开拓力消耗或按钮")
            log.info(f"再来一次，挑战 {waves} 次")
        else:
            if previous:
                _exit_result()
                if screen.current_screen != "calyx":
                    _select_category()
                    _enter_calyx(name)
            _start_challenge(name, waves)
        _wait_battle(repeated=repeated)

        completed = _read_waves(RESULT_COUNT, "上轮挑战波次")
        available = read_power()
        expected = power - waves * POWER_COST
        if completed != waves or not expected <= available <= expected + 2:
            raise PowerError("结算波次或开拓力变化与预期不符，停止重试")
        power = available
        remaining = min(remaining - completed, power // POWER_COST)
        previous = waves
        log.info(f"本轮已结算 {completed} 次挑战，剩余开拓力 {power}/300")
        yield completed

    _exit_result()
    screen.change_to("main", max_recursion=1)
    log.info("开拓力不足，已返回主界面" if power < POWER_COST else "已达到本次挑战次数，返回主界面")


def _run():
    names = get_raw_instance_names()[GOLDEN_CALYX]
    batch_limit = cfg.instance_names_challenge_count.get(GOLDEN_CALYX, MAX_WAVES)
    if type(batch_limit) is not int or not 1 <= batch_limit <= MAX_WAVES:
        log.warning(f"{GOLDEN_CALYX} 的连续挑战次数无效，使用 {MAX_WAVES}")
        batch_limit = MAX_WAVES

    plan = cfg.power_plan
    if not plan:
        if cfg.instance_type != GOLDEN_CALYX:
            log.warning(f"触屏清体力暂不支持 {cfg.instance_type}")
            return False
        name = cfg.instance_names.get(GOLDEN_CALYX)
        if name == "无":
            log.info(f"{GOLDEN_CALYX}未开启")
            return True
        if name not in names:
            raise PowerError(f"未配置有效的{GOLDEN_CALYX}副本名称")
        for _ in _run_calyx(name, None, batch_limit):
            pass
        return True

    remaining = list(plan)
    ran = False
    for index, item in enumerate(plan):
        if not isinstance(item, (list, tuple)) or len(item) != 3:
            log.warning(f"体力计划第 {index + 1} 项格式无效，已保留")
            continue
        instance_type, name, count = item
        if (instance_type != GOLDEN_CALYX or not isinstance(name, str) or name not in names or name == "无"
                or type(count) is not int or count <= 0):
            log.warning(f"体力计划第 {index + 1} 项不受触屏模式支持，已保留")
            continue
        ran = True
        for completed in _run_calyx(name, count, batch_limit):
            count -= completed
            if not cfg.power_plan_keep:
                remaining[index] = [instance_type, name, count] if count else None
                cfg.set_value("power_plan", [item for item in remaining if item is not None])
        if count:
            break  # 体力不足，保留该计划和后续项目。
    return ran


def run():
    log.hr("开始触屏清体力", 0)
    with screenshot_retry_timeout(5):
        try:
            return _run()
        except PowerError as error:
            log.error(f"触屏清体力：{error}")
            return False
