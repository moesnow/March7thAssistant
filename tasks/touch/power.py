"""触屏 720p 生存索引副本。"""
from datetime import date
import sys
import re
import time

import numpy as np
import cv2
from PIL import Image

from module.automation import auto
from module.automation.automation import screenshot_retry_timeout
from module.config import cfg
from module.game.adb_transport import AdbError
from module.localization import get_raw_instance_names, tr
from module.logger import log
from module.screen import screen
from tasks.base.list_drag import changed_ratio, drag_list
from tasks.power.instance import Instance
from tasks.power.battle import ensure_double_speed
from tasks.power.policy import (
    BATTLE_TIMEOUT, ENTRY_TIMEOUT, DEFEAT_RETRIES, CAVERN, CRIMSON_CALYX, ECHO, GOLDEN_CALYX,
    INSTANCE_LIMITS, ORNAMENT, STAGNANT_SHADOW, BattleDefeat, PowerError, RelicBagFull,
    SupportDemand, batch_limit, check_balance, normalize as _normalize, parse_power, run_plan,
)
from tasks.power.readout import read_number
from tasks.power.supplement import supplement
from utils.game_options import game_option_enabled
from utils.image_utils import ImageUtils
from utils.wait import wait_until


MAX_WAVES = 24
_INSTANCE_SCREENS = {
    GOLDEN_CALYX: "calyx", CRIMSON_CALYX: "calyx", STAGNANT_SHADOW: "stagnant_shadow",
    CAVERN: "cavern", ECHO: "echo", ORNAMENT: "ornament",
}
INSTANCES = {kind: (_INSTANCE_SCREENS[kind], *limits) for kind, limits in INSTANCE_LIMITS.items()}
IMAGES = "./assets/touch_720/images/power"
INDEX_CATEGORY = (177 / 1920, 255 / 1080, 449 / 1920, 680 / 1080)
INDEX_ROWS = (658 / 1920, 256 / 1080, 1095 / 1920, 679 / 1080)
ECHO_REWARDS = (884 / 1920, 327 / 1080, 101 / 1920, 60 / 1080)
ECHO_PRACTICE_NOTICE = (410 / 1920, 493 / 1080, 1100 / 1920, 69 / 1080)
DIALOG_CONFIRM = (990 / 1920, 665 / 1080, 460 / 1920, 80 / 1080)
POWER_VALUE = (1555 / 1920, 32 / 1080, 143 / 1920, 45 / 1080)
INSTANCE_TITLE = (1204 / 1920, 105 / 1080, 645 / 1920, 68 / 1080)
ORNAMENT_TITLE = (755 / 1920, 111 / 1080, 576 / 1920, 59 / 1080)
WAVE_COUNT = (1455 / 1920, 810 / 1080, 175 / 1920, 50 / 1080)
CHALLENGE_COST = (1285 / 1920, 953 / 1080, 75 / 1920, 64 / 1080)
CAVERN_CHALLENGE_COST = (1405 / 1920, 953 / 1080, 75 / 1920, 64 / 1080)
ECHO_CHALLENGE_COST = (1349 / 1920, 953 / 1080, 144 / 1920, 64 / 1080)
CHALLENGE = (1392 / 1920, 950 / 1080, 461 / 1920, 76 / 1080)
START_CHALLENGE = (1410 / 1920, 946 / 1080, 420 / 1920, 80 / 1080)
TEAM_TABS = (531 / 1920, 14 / 1080, 861 / 1920, 86 / 1080)
BATTLE_CONTROLS = (1665 / 1920, 30 / 1080, 210 / 1920, 63 / 1080)
RESULT_TITLE = (754 / 1920, 109 / 1080, 411 / 1920, 253 / 1080)
RESULT_COUNT = (1135 / 1920, 861 / 1080, 257 / 1920, 48 / 1080)
REPEAT_COST = (1091 / 1920, 917 / 1080, 85 / 1920, 61 / 1080)
REPEAT = (1180 / 1920, 911 / 1080, 290 / 1920, 74 / 1080)
EXIT = (414 / 1920, 906 / 1080, 1075 / 1920, 87 / 1080)
DIALOG = (259 / 1920, 226 / 1080, 1399 / 1920, 505 / 1080)
SUPPLEMENT_CANCEL = (474 / 1920, 740 / 1080, 450 / 1920, 79 / 1080)


def _read_number(crop, parse, error):
    return read_number(auto, crop, parse, error)


def read_power(crop=POWER_VALUE):
    return _read_number(crop, parse_power, "未能确认当前开拓力")


def _read_echo_rewards():
    def parse(text):
        match = re.fullmatch(r"([0-3])/3", _normalize(text))
        return int(match[1]) if match else None

    return _read_number(ECHO_REWARDS, parse, "未能确认历战余响的剩余奖励次数")


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
        start, end = (bottom, top) if instance_type in (STAGNANT_SHADOW, CAVERN, ECHO) else (top, bottom)
        if not drag_list(auto, start, end, crop=INDEX_CATEGORY):
            raise PowerError("无法拖动生存索引分类")
        if not _click_text(instance_type, INDEX_CATEGORY):
            raise PowerError(f"未找到生存索引里的{instance_type}")
    time.sleep(0.5)


def find_instance_entry(lines, name, instance_type=None):
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
    # 历战余响的进入按钮在掉落物一行，其余副本和标题同一行。
    button_offset = 73 if instance_type == ECHO else 0
    for name_y in sorted(names):
        matches = [button for button in buttons if abs(button[0] - name_y - button_offset) <= 35]
        if len(matches) == 1:
            return matches[0][1:]
    return None


def _click_instance_entry(instance_type, name):
    # 历战余响和饰品提取列表顶部有固定横幅，缩短手势以保留相邻页面的重叠。
    drag_end = 490 if instance_type in (ECHO, ORNAMENT) else 405
    for _ in range(12):
        before, _, _ = auto.take_screenshot(crop=INDEX_ROWS)
        auto.perform_ocr()
        if entry := find_instance_entry(auto.ocr_result, name, instance_type):
            box, label = entry
            if label == "追踪":
                raise PowerError(f"指定副本未解锁：{name}")
            if not auto.click_element_with_pos(auto.calculate_text_position(box, False)):
                raise PowerError(f"无法点击 {name} 的进入按钮")
            return
        if not drag_list(auto, (1100 / 1920, 814 / 1080), (1100 / 1920, drag_end / 1080),
                         crop=INDEX_ROWS, end_pause=0.2, settle=0.4):
            raise PowerError("生存索引列表未稳定")
        if changed_ratio(before, auto.screenshot) <= 0.01:
            break
    raise PowerError(f"生存索引未找到 {name} 的进入按钮")


def _enter_instance(instance_type, name):
    _click_instance_entry(instance_type, name)
    instance_screen, _, _ = INSTANCES[instance_type]
    def ready():
        if screen.check_screen(instance_screen):
            return True
        if auto.find_element(("是否传送", "是否切换", "不再弹出"), "text", include=True, crop=DIALOG):
            _click_text("确认", DIALOG_CONFIRM)
        return False

    if not wait_until(ready, ENTRY_TIMEOUT, 0.6):
        raise PowerError(f"未能进入指定副本 {name}")
    title = get_raw_instance_names()[instance_type][name] if instance_type == CRIMSON_CALYX else name
    crop = ORNAMENT_TITLE if instance_type == ORNAMENT else INSTANCE_TITLE
    if not auto.find_element(title, "text", include=True, crop=crop,
                             max_retries=6, retry_delay=0.3):
        raise PowerError(f"未确认进入指定副本 {name}")


def _supplement(power, *, plus=(1720, 55), power_crop=POWER_VALUE):
    def open_dialog():
        _tap(*plus)
        return True

    return supplement(auto, screen, cfg, power, open_dialog, lambda: read_power(power_crop), return_screen="guide3")


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


def _set_challenge_waves(waves, limit, *, crop=WAVE_COUNT, minus=1270, y=866):
    for _ in range(limit + 1):
        selected = _read_waves(crop, "挑战次数")
        if selected == waves:
            return
        _tap(1821 if selected < waves else minus, y)
        time.sleep(0.22)
    raise PowerError(f"无法把挑战次数设为 {waves}")


def _confirm_echo_practice(*, required):
    if not auto.find_element("次数已耗尽", "text", include=True, crop=ECHO_PRACTICE_NOTICE,
                             max_retries=8, retry_delay=0.3):
        if required:
            raise PowerError("未确认历战余响的无奖励挑战提示")
        return
    if not _click_text("确认", DIALOG_CONFIRM):
        raise PowerError("无法确认历战余响的无奖励挑战")
    log.info("已确认本场历战余响无挑战奖励")


def _start_challenge(instance_type, name, waves, *, borrow_for_daily=False, practice=False):
    _, cost, limit = INSTANCES[instance_type]
    if not practice:
        has_wave_selector = instance_type != ECHO or auto.find_element("挑战次数", "text", include=True, crop=WAVE_COUNT)
        if has_wave_selector:
            _set_challenge_waves(waves, limit)
        cost_crop = {CAVERN: CAVERN_CHALLENGE_COST, ECHO: ECHO_CHALLENGE_COST}.get(instance_type, CHALLENGE_COST)
        if _read_cost(cost_crop) != waves * cost or read_power() < waves * cost:
            raise PowerError("挑战消耗与已确认的波次或开拓力不符")
    if not _click_text("挑战", CHALLENGE):
        raise PowerError("未找到副本的挑战按钮")
    if practice:
        _confirm_echo_practice(required=True)
    if not auto.find_element("开始挑战", "text", crop=START_CHALLENGE, max_retries=18, retry_delay=0.4):
        _check_popup()
        raise PowerError("未进入副本编队页")
    if cfg.instance_team_enable:
        _select_team(instance_type, name)
    borrowed = False
    if cfg.borrow_enable and (cfg.borrow_character_enable or borrow_for_daily):
        from tasks.touch import support

        borrowed = support.borrow()
    time.sleep(0.6)
    if not _click_text("开始挑战", START_CHALLENGE):
        raise PowerError("无法开始挑战")
    return borrowed


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
    if "持有数量已达上限" in text:
        raise RelicBagFull("遗器背包已满")
    if any(message in text for message in ("无法战斗状态", "长时间未操作", "是否切换")):
        raise PowerError("检测到阻止挑战的弹窗，请检查游戏画面")


def _heal_teams():
    screen.change_to("main", max_recursion=1)
    _tap(170, 173)
    time.sleep(0.8)
    if not auto.find_element(("导航", "星轨航图", "地图"), "text", include=True, max_retries=4, retry_delay=0.3):
        raise PowerError("未确认已进入地图")
    for name in ("SpaceAnchor1", "SpaceAnchor2"):
        frame, _, _ = auto.take_screenshot()
        pixels = cv2.cvtColor(np.asarray(frame), cv2.COLOR_RGB2BGR)
        template = ImageUtils.read_image(f"./assets/images/share/power/space_anchor/{name}.png", cv2.IMREAD_UNCHANGED)
        if template is None:
            continue
        template = cv2.resize(template, None, fx=2 / 3, fy=2 / 3, interpolation=cv2.INTER_AREA)
        if template.shape[2] == 4:
            mask, template = template[:, :, 3], template[:, :, :3].copy()
        else:
            mask = None
        score, (x, y) = ImageUtils.scale_and_match_template(pixels, template, mask=mask)
        matched = score is not None and (score <= 3000000 if mask is not None else score >= 0.88)
        if matched:
            height, width = template.shape[:2]
            _tap((x + width / 2) * 1.5, (y + height / 2) * 1.5)
            if _click_text("传送", (0.70, 0.80, 0.28, 0.20), retries=4):
                screen.wait_for_screen_change("main", max_recursion=0)
                return
    # 地图已打开但找不到锚点时，从地图的关闭按钮返回。
    if auto.find_element(("导航", "星轨航图"), "text", include=True):
        _tap(1848, 55)
    raise PowerError("当前地图未找到可传送的恢复锚点")


def _clean_full_bag():
    if not getattr(cfg, "relic_bag_cleanup_enable", False):
        _click_text("取消", (0.25, 0.60, 0.24, 0.23), retries=3)
        return False
    if not _click_text("确认", DIALOG_CONFIRM):
        return False
    header = (0.025, 0.01, 0.30, 0.10)
    if not auto.find_element("遗器分解", "text", crop=header, max_retries=8, retry_delay=0.3):
        return False
    if not _click_text("筛选", (0.01, 0.84, 0.55, 0.16)):
        return False
    if not _click_text("4星及以下", (0.05, 0.13, 0.9, 0.73)):
        return False
    if not _click_text("确认", (0.51, 0.63, 0.48, 0.37)):
        return False
    if not auto.find_element("遗器分解", "text", crop=header, max_retries=8, retry_delay=0.3):
        return False
    if not _click_text("分解", (0.73, 0.85, 0.25, 0.15)):
        return False
    if not auto.find_element(("确认分解", "是否分解", "以下遗器"), "text", include=True, crop=DIALOG):
        return False
    if auto.find_element(("五星", "5星", "5 星", "高稀有度"), "text", include=True, crop=DIALOG):
        return False
    if not _click_text("确认", (0.51, 0.63, 0.32, 0.24)):
        return False
    if not auto.find_element("获得物品", "text", max_retries=8, retry_delay=0.3):
        return False
    _tap(960, 854)
    if auto.find_element("遗器分解", "text", crop=header, max_retries=6, retry_delay=0.3):
        _tap(1848, 55)
    if auto.find_element("遗器", "text", crop=header, max_retries=6, retry_delay=0.3):
        _tap(1848, 55)
    screen.change_to("main", max_recursion=1)
    return True


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
    deadline = time.monotonic() + ENTRY_TIMEOUT
    detect_auto = game_option_enabled(cfg, "auto_battle_detect_enable")
    speed_confirmed = False
    next_speed_check = 0.0
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
            state, status = _observe_battle(glyph, allow_team=not saw_battle and instance_screen != "ornament",
                                            check_popups=check_popups)
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
            if detect_auto and not confirmed_auto:
                log.warning("战斗已结算，未截到确认自动战斗开启的画面")
            return
        if state == "defeat":
            _exit_result(instance_screen)
            screen.change_to("main", max_recursion=0)
            raise BattleDefeat("副本挑战失败，已退出关卡")
        if state == "battle":
            left_result = True
            if not saw_battle:
                saw_battle = True
                deadline = time.monotonic() + BATTLE_TIMEOUT
            if detect_auto and not speed_confirmed and time.monotonic() >= next_speed_check:
                speed_confirmed = ensure_double_speed(auto)
                next_speed_check = time.monotonic() + 3
            if detect_auto and not confirmed_auto:
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
        time.sleep(0.45)
    raise PowerError("等待战斗结算超时" if saw_battle else "等待进入战斗超时")


def _run_instance(instance_type, name, planned, *, borrow_for_daily=False, on_settlement=None):
    instance_screen, cost, _ = INSTANCES[instance_type]
    limit = batch_limit(cfg, instance_type)
    demand = borrow_for_daily if isinstance(borrow_for_daily, SupportDemand) else SupportDemand(borrow_for_daily)

    if instance_type == ORNAMENT:
        from tasks.touch import ornament

        yield from ornament.run_instance(name, planned, limit, demand, on_settlement)
        return

    _select_category(instance_type)
    is_echo = instance_type == ECHO
    quota = _read_echo_rewards() if is_echo else None
    if quota == 0:
        cfg.save_timestamp("echo_of_war_timestamp")
        if planned is None:
            screen.change_to("main", max_recursion=1)
            return
    power = read_power()
    if quota != 0:
        power = _supplement(power)
        if power < cost:
            log.info("开拓力不足，结束本副本项")
            screen.change_to("main", max_recursion=1)
            if on_settlement is not None:
                on_settlement(0, power)
            return
    if getattr(cfg, "tp_before_instance", False):
        _heal_teams()
        _select_category(instance_type)
    _enter_instance(instance_type, name)
    remaining = planned
    previous = 0
    borrowed = False
    retries = 0
    cleaned = False
    while remaining is None or remaining > 0:
        practice = quota == 0
        waves = limit if remaining is None else min(remaining, limit)
        if practice:
            waves = 1
        else:
            waves = min(waves, power // cost)
            if is_echo:
                waves = min(waves, quota)
        if not waves:
            break
        if is_echo and not practice and not previous and not auto.find_element("挑战次数", "text", include=True, crop=WAVE_COUNT):
            waves = 1

        started = time.monotonic()
        repeated = False
        try:
            if previous == waves and (not demand.pending or borrowed):
                try:
                    repeated = practice or _read_cost(REPEAT_COST) == waves * cost
                except PowerError:
                    repeated = False
                if repeated:
                    if not _click_text("再来一次", REPEAT):
                        _check_popup()
                        raise PowerError("无法点击再来一次")
                    if practice:
                        _confirm_echo_practice(required=True)
            if not repeated:
                if previous:
                    _exit_result(instance_screen)
                    if screen.current_screen != instance_screen:
                        _select_category(instance_type)
                        _enter_instance(instance_type, name)
                borrowed = _start_challenge(instance_type, name, waves, borrow_for_daily=demand.pending, practice=practice)
            _wait_battle(repeated=repeated, instance_screen=instance_screen)
        except BattleDefeat:
            _select_category(instance_type)
            after = read_power()
            check_balance(power, after, 0, time.monotonic() - started)
            if retries >= DEFEAT_RETRIES:
                raise
            retries += 1
            log.warning(f"已确认战败且未扣费，重试 {retries}/{DEFEAT_RETRIES}")
            power, previous = after, 0
            _enter_instance(instance_type, name)
            continue
        except RelicBagFull:
            if cleaned or not _clean_full_bag():
                raise
            cleaned = True
            _select_category(instance_type)
            power, previous = read_power(), 0
            _enter_instance(instance_type, name)
            continue

        completed = 1 if waves == 1 else _read_waves(RESULT_COUNT, "上轮挑战波次")
        if completed > waves:
            raise PowerError("实际结算次数超过已选波次")
        demand.won(borrowed)
        yield completed
        after = read_power()
        if completed != waves:
            raise PowerError(f"实际结算 {completed}/{waves} 次，已保留确认的进度")
        check_balance(power, after, 0 if practice else waves * cost, time.monotonic() - started)
        power, previous, retries = after, waves, 0
        if remaining is not None:
            remaining -= completed
        if on_settlement is not None:
            on_settlement(completed, power)
        log.info(f"已结算 {completed} 次，剩余开拓力 {power}/300")

        if is_echo and not practice:
            _exit_result(instance_screen)
            previous = 0
            _select_category(instance_type)
            quota = _read_echo_rewards()
            if quota == 0:
                cfg.save_timestamp("echo_of_war_timestamp")
                if planned is None:
                    break
            if remaining is None or remaining > 0:
                _enter_instance(instance_type, name)

    if previous:
        _exit_result(instance_screen)
    screen.change_to("main", max_recursion=1)


def run_weekly_echo(*, borrow_for_daily=False):
    if date.today().isoweekday() < cfg.echo_of_war_start_day_of_week:
        log.info(f"历战余响设为周{cfg.echo_of_war_start_day_of_week}开始，跳过本次")
        return True
    name = cfg.instance_names.get(ECHO)
    if name == "无":
        return True
    with screenshot_retry_timeout(5):
        try:
            if name not in get_raw_instance_names()[ECHO]:
                raise PowerError("未配置有效的历战余响副本名称")
            for _ in _run_instance(ECHO, name, None, borrow_for_daily=borrow_for_daily):
                pass
        except PowerError as error:
            log.error(f"触屏历战余响：{error}")
            return False
    return True


def _run(borrow_for_daily, on_settlement=None):
    demand = borrow_for_daily if isinstance(borrow_for_daily, SupportDemand) else SupportDemand(borrow_for_daily)

    def run_instance(instance_type, name, planned):
        return _run_instance(instance_type, name, planned, borrow_for_daily=demand, on_settlement=on_settlement)

    plan = cfg.power_plan
    if plan:
        complete = run_plan(cfg, plan, run_instance)
        if not complete or sys.platform == "android" or not getattr(cfg, "power_plan_continue", True):
            return True

    instance_type = cfg.instance_type
    if not isinstance(instance_type, str) or instance_type not in INSTANCES:
        raise PowerError(f"触屏清体力暂不支持 {instance_type}")
    name = cfg.instance_names.get(instance_type)
    if name == "无":
        log.info(f"{instance_type}未开启")
        return True
    if name not in get_raw_instance_names()[instance_type]:
        raise PowerError(f"未配置有效的{instance_type}副本名称")
    for _ in run_instance(instance_type, name, None):
        pass
    return True


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


def run_standalone():
    from tasks.touch import daily

    return run(borrow_for_daily=daily.support_demand())
