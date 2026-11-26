"""触屏 720p 生存索引副本。"""
from datetime import date
import time

import numpy as np
import cv2
from PIL import Image

from module.automation import auto
from module.automation.automation import screenshot_retry_timeout
from module.automation.input_base import input_deadline, input_deadline_reached, limit_input_deadline
from module.config import cfg
from module.overview.plan import echo_day_due
from module.overview.readings import save_reading
from module.game.adb_transport import AdbError
from module.localization import get_raw_instance_names, tr
from module.logger import log
from module.screen import screen
from tasks.base.list_drag import changed_ratio, drag_list
from tasks.base.task_steps import FATAL_GAME_ERRORS, GameRecoveryError
from tasks.power.instance import Instance, TeamPresetUnavailable
from tasks.power.battle import battle_speed_visible, ensure_double_speed
from tasks.power.policy import (
    remaining_plan,
    BATTLE_TIMEOUT, ENTRY_TIMEOUT, DEFEAT_RETRIES, CAVERN, CRIMSON_CALYX, ECHO, GOLDEN_CALYX,
    INSTANCE_LIMITS, ORNAMENT, STAGNANT_SHADOW, BattleDefeat, InstanceTeamUnavailable, PowerError, RelicBagFull,
    SupportDemand, batch_limit, normalize as _normalize,
    parse_echo_rewards, parse_power, run_plan,
)
from tasks.power.readout import read_number
from tasks.power.supplement import supplement
from tasks.power.team import TEAM_ACTIONS, find_current_team_start, restore_main, select_preset, warn_team_switch
from utils.game_options import game_option_enabled
from utils.image_utils import ImageUtils
from utils.pause import pause_ctl
from utils.wait import wait_until


_INSTANCE_SCREENS = {
    GOLDEN_CALYX: "calyx", CRIMSON_CALYX: "calyx", STAGNANT_SHADOW: "stagnant_shadow",
    CAVERN: "cavern", ECHO: "echo", ORNAMENT: "ornament",
}
INSTANCES = {kind: (_INSTANCE_SCREENS[kind], *limits) for kind, limits in INSTANCE_LIMITS.items()}
IMAGES = "./assets/touch_720/images/power"
INDEX_CATEGORY = (177 / 1920, 255 / 1080, 449 / 1920, 680 / 1080)
INDEX_ROWS = (658 / 1920, 256 / 1080, 1095 / 1920, 679 / 1080)
INSTANCE_ENTRY_LABELS = frozenset(("进入", "追踪", "传送"))
INSTANCE_LIST_READY_TIMEOUT = 15
INSTANCE_SEARCH_TIMEOUT = 180
ECHO_REWARDS = (884 / 1920, 327 / 1080, 101 / 1920, 60 / 1080)
ECHO_PRACTICE_NOTICE = (410 / 1920, 493 / 1080, 1100 / 1920, 69 / 1080)
DIALOG_CONFIRM = (990 / 1920, 665 / 1080, 460 / 1920, 80 / 1080)
POWER_VALUE = (1555 / 1920, 32 / 1080, 143 / 1920, 45 / 1080)
INSTANCE_TITLE = (1204 / 1920, 105 / 1080, 645 / 1920, 68 / 1080)
ORNAMENT_TITLE = (755 / 1920, 111 / 1080, 576 / 1920, 59 / 1080)
WAVE_COUNT = (1455 / 1920, 810 / 1080, 175 / 1920, 50 / 1080)
CHALLENGE = (1392 / 1920, 950 / 1080, 461 / 1920, 76 / 1080)
START_CHALLENGE = (1410 / 1920, 946 / 1080, 420 / 1920, 80 / 1080)
MENU_TEAM = (1120 / 1920, 389 / 1080, 645 / 1920, 633 / 1080)
BATTLE_CONTROLS = (1665 / 1920, 30 / 1080, 210 / 1920, 63 / 1080)
RESULT_TITLE = (754 / 1920, 109 / 1080, 411 / 1920, 253 / 1080)
REPEAT = (1180 / 1920, 911 / 1080, 290 / 1920, 74 / 1080)
EXIT = (414 / 1920, 906 / 1080, 1075 / 1920, 87 / 1080)
DIALOG = (259 / 1920, 226 / 1080, 1399 / 1920, 505 / 1080)
SUPPLEMENT_CANCEL = (474 / 1920, 740 / 1080, 450 / 1920, 79 / 1080)
TRANSIENT_FRAME_ERRORS = ("frame_clock_unavailable", "frame_timeout")
DEFEAT_TITLES = ("挑战失败", "战斗失败")


def _read_number(crop, parse, error):
    return read_number(auto, crop, parse, error)


def read_power(crop=POWER_VALUE):
    value = _read_number(crop, parse_power, "未能确认当前开拓力")
    save_reading(cfg, "overview_power", value)
    return value


def _read_echo_rewards():
    return _read_number(ECHO_REWARDS, parse_echo_rewards, "未能确认历战余响的剩余奖励次数")


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
        elif text in INSTANCE_ENTRY_LABELS and x > 560:
            buttons.append((y, box, text))
    # 历战余响的进入按钮在掉落物一行，其余副本和标题同一行。
    button_offset = 73 if instance_type == ECHO else 0
    for name_y in sorted(names):
        matches = [button for button in buttons if abs(button[0] - name_y - button_offset) <= 35]
        if len(matches) == 1:
            return matches[0][1:]
    return None


def _check_instance_search_deadline():
    pause_ctl.check_stop()
    if input_deadline_reached(time.monotonic()):
        raise PowerError("生存索引查找副本超时")


def _find_instance_entry_in_list(instance_type, name):
    catalog = get_raw_instance_names()[instance_type]
    titles = tuple({_normalize(title) for title in (catalog.values() if instance_type == CRIMSON_CALYX else catalog)}
                   - {"无", "跳过"})

    def list_ready():
        auto.take_screenshot(crop=INDEX_ROWS)
        auto.perform_ocr()
        texts = {_normalize(text) for _, (text, _) in auto.ocr_result}
        return (
            bool(texts & INSTANCE_ENTRY_LABELS)
            and not any("角色培养" in text or "培养设置" in text or "隧洞遗器推荐" in text for text in texts)
            and any(title in text for text in texts for title in titles)
        )

    # 低帧率设备点完分类后可能还在显示培养目标，等右栏出现当前分类的副本再翻页。
    _check_instance_search_deadline()
    wait_time = min(INSTANCE_LIST_READY_TIMEOUT, input_deadline.get() - time.monotonic())
    ready = wait_until(list_ready, wait_time, 0.5)
    _check_instance_search_deadline()
    if not ready:
        raise PowerError(f"未能确认{instance_type}列表")

    if entry := find_instance_entry(auto.ocr_result, name, instance_type):
        return entry

    # 历战余响和饰品提取有固定横幅，缩短手势以保留相邻页面的重叠。
    upper_y = 490 if instance_type in (ECHO, ORNAMENT) else 405
    bottom = (1100 / 1920, 814 / 1080)
    top = (1100 / 1920, upper_y / 1080)
    for start, end in ((bottom, top), (top, bottom)):
        unchanged = 0
        for _ in range(12):
            _check_instance_search_deadline()
            before = auto.screenshot
            stable = drag_list(auto, start, end, crop=INDEX_ROWS, end_pause=0.2, settle=0.4)
            _check_instance_search_deadline()
            if not stable:
                raise PowerError("生存索引列表未稳定")

            auto.perform_ocr()
            if entry := find_instance_entry(auto.ocr_result, name, instance_type):
                return entry
            # 手势可能漏收，连续两次无位移才结束本方向查找。
            unchanged = unchanged + 1 if changed_ratio(before, auto.screenshot) <= 0.01 else 0
            if unchanged >= 2:
                break
    return None


def _click_instance_entry(instance_type, name):
    with limit_input_deadline(time.monotonic() + INSTANCE_SEARCH_TIMEOUT):
        entry = _find_instance_entry_in_list(instance_type, name)
        _check_instance_search_deadline()
        if not entry:
            raise PowerError(f"生存索引未找到 {name} 的进入按钮")
        box, label = entry
        if label == "追踪":
            raise PowerError(f"指定副本未解锁：{name}")
        if not auto.click_element_with_pos(auto.calculate_text_position(box, False)):
            _check_instance_search_deadline()
            raise PowerError(f"无法点击 {name} 的进入按钮")


def _enter_instance(instance_type, name):
    _click_instance_entry(instance_type, name)
    instance_screen, _, _ = INSTANCES[instance_type]
    title = get_raw_instance_names()[instance_type][name] if instance_type == CRIMSON_CALYX else name
    crop = ORNAMENT_TITLE if instance_type == ORNAMENT else INSTANCE_TITLE

    def ready():
        # 与桌面版一致，直接用副本名称确认进入，避开左上标题的动态背景。
        if auto.find_element(title, "text", include=True, crop=crop):
            screen.current_screen = instance_screen
            return True
        if auto.find_element(("是否传送", "是否切换", "不再弹出"), "text", include=True, crop=DIALOG):
            _click_text("确认", DIALOG_CONFIRM)
        return False

    if not wait_until(ready, ENTRY_TIMEOUT, 0.6):
        raise PowerError(f"未能进入指定副本 {name}")


def _reenter_instance(instance_type, name):
    _select_category(instance_type)
    _enter_instance(instance_type, name)


def _supplement(power, *, plus=(1720, 55), power_crop=POWER_VALUE):
    def locate_entry():
        x, y = plus
        return auto.find_element((x / 1920, y / 1080, 0, 0), "crop")

    return supplement(auto, screen, cfg, power, locate_entry, lambda: read_power(power_crop),
                      return_screen="guide3")


def _select_team(instance_type, name):
    team = Instance.get_target_team(instance_type, name)
    reason = select_preset(auto, team)
    if not reason:
        button = auto.find_element("开始挑战", "text", crop=START_CHALLENGE, max_retries=4, retry_delay=0.35)
        if not button:
            reason = "未确认目标队伍可出战"
    if reason:
        _check_popup(fatal_disconnect=True)
        raise TeamPresetUnavailable(f"副本未能使用队伍 {str(team).zfill(2)}（{reason}）")
    log.info(f"已确认副本选中队伍 {str(team).zfill(2)}")
    return button


def _select_world_team(instance_type, name):
    team = Instance.get_target_team(instance_type, name)
    screen.change_to("menu")
    opened = _click_text("编队", MENU_TEAM, retries=3)
    if not opened and screen.check_screen("menu"):
        drag_list(auto, (1690 / 1920, 949 / 1080), (1690 / 1920, 510 / 1080),
                  crop=MENU_TEAM, settle=0.45)
        opened = _click_text("编队", MENU_TEAM, retries=3)
    if (opened
            and auto.find_element("快速编队", "text", crop=TEAM_ACTIONS, max_retries=7, retry_delay=0.35)):
        reason = select_preset(auto, team, activate=True)
        _check_popup(fatal_disconnect=True)
        if auto.find_element("快速编队", "text", crop=TEAM_ACTIONS, max_retries=3, retry_delay=0.3):
            _tap(1848, 55)
            wait_until(lambda: screen.check_screen("main") or screen.check_screen("menu"), 6, 0.35)
    else:
        _check_popup(fatal_disconnect=True)
        reason = "未确认进入队伍页"
    if reason:
        warn_team_switch(name, team, "主世界编队", reason)
    else:
        log.info(f"已确认主世界启用队伍 {str(team).zfill(2)}")
    restore_main(screen, name)
    return reason


def _leave_challenge_team(instance_screen):
    if auto.find_element(("快速编队", "开始挑战"), "text", crop=TEAM_ACTIONS):
        _tap(1848, 55)
        wait_until(lambda: screen.check_screen(instance_screen) or screen.check_screen("main"), 6, 0.35)


def _set_challenge_waves(waves, *, y=866, allow_no_selector=False):
    # 生存索引发起的新挑战默认选择一场。
    if waves == 1:
        return 1
    if allow_no_selector and not auto.find_element("挑战次数", "text", include=True, crop=WAVE_COUNT):
        return 1
    for _ in range(waves - 1):
        _tap(1821, y)
        time.sleep(0.22)
    return waves


def _confirm_echo_practice(*, required):
    if not auto.find_element("次数已耗尽", "text", include=True, crop=ECHO_PRACTICE_NOTICE,
                             max_retries=8, retry_delay=0.3):
        if required:
            raise PowerError("未确认历战余响的无奖励挑战提示")
        return
    if not _click_text("确认", DIALOG_CONFIRM):
        raise PowerError("无法确认历战余响的无奖励挑战")
    log.info("已确认本场历战余响无挑战奖励")


def _start_challenge(instance_type, name, waves, *, borrow_for_daily=False, practice=False,
                     world_team=False, team_failure=None):
    if not practice:
        waves = _set_challenge_waves(waves, allow_no_selector=instance_type == ECHO)
    if not _click_text("挑战", CHALLENGE):
        if team_failure:
            _check_popup(fatal_disconnect=True)
            raise InstanceTeamUnavailable(f"{name}：未确认副本挑战按钮，已跳过本项")
        raise PowerError("未找到副本的挑战按钮")
    if practice:
        _confirm_echo_practice(required=True)
    start_button = auto.find_element("开始挑战", "text", crop=START_CHALLENGE, max_retries=18, retry_delay=0.4)
    if not start_button and not (cfg.instance_team_enable and auto.find_element("快速编队", "text", crop=TEAM_ACTIONS)):
        _check_popup(fatal_disconnect=bool(team_failure))
        if team_failure:
            raise InstanceTeamUnavailable(f"{name}：未确认进入副本编队，已跳过本项")
        raise PowerError("未进入副本编队页")
    if cfg.instance_team_enable and not world_team and team_failure is None:
        start_button = _select_team(instance_type, name)
    borrowed = False
    if cfg.borrow_enable and (cfg.borrow_character_enable or borrow_for_daily):
        from tasks.touch import support

        borrowed = support.borrow()
        start_button = None
    if team_failure:
        _check_popup(fatal_disconnect=True)
        start_button = find_current_team_start(auto, START_CHALLENGE)
        if not start_button:
            raise InstanceTeamUnavailable(f"{name}：无法确认当前副本有可出战的队伍，已跳过本项")
        log.info(f"{name}：已确认当前副本编队可出战，继续挑战")
    else:
        time.sleep(0.6)
    started = (auto.click_element_with_pos(start_button) if start_button is not None
               else _click_text("开始挑战", START_CHALLENGE))
    if not started:
        raise PowerError("无法开始挑战")
    return waves, borrowed


def _check_popup(*, fatal_disconnect=False):
    auto.take_screenshot(crop=DIALOG)
    auto.perform_ocr()
    text = "".join(text for _, (text, _) in auto.ocr_result)
    if any(message in text for message in ("网络连接", "连接断开", "重新登录", "网络错误", "连接超时", "连接中断")):
        if fatal_disconnect:
            raise GameRecoveryError("副本开打前检测到游戏连接中断")
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
    return screen.current_screen


def _exit_defeat(instance_screen):
    """战败页可能先显示点击继续，退出后保留战败结果交给上层处理。"""
    deadline = time.monotonic() + 30
    attempts = 0
    next_attempt = 0.0
    with limit_input_deadline(deadline):
        while not input_deadline_reached(time.monotonic()):
            pause_ctl.check_stop()
            try:
                for target in ("main", instance_screen, "guide3"):
                    if screen.check_screen(target):
                        if target != "main":
                            screen.change_to("main", max_recursion=0)
                        return
                if attempts < 3 and time.monotonic() >= next_attempt:
                    point = auto.find_element("退出关卡", "text", crop=EXIT)
                    if not point:
                        # 桌面版同样兼容点击战败标题关闭结果页。只对新画面确认的战败页操作。
                        point = auto.find_element(DEFEAT_TITLES, "text", crop=RESULT_TITLE)
                    pause_ctl.check_stop()
                    if input_deadline_reached(time.monotonic()):
                        break
                    if point:
                        attempts += 1
                        # 输入回执缺失也先等转场，不立即改点或重发。
                        auto.click_element_with_pos(point)
                        next_attempt = time.monotonic() + 5
            except FATAL_GAME_ERRORS as error:
                if not isinstance(error, AdbError) or error.code not in TRANSIENT_FRAME_ERRORS:
                    raise
                log.warning(f"暂时无法确认战败退出画面，等待恢复：{error}")
            except Exception as error:
                log.warning(f"暂时无法确认战败退出画面，等待恢复：{error}")
            time.sleep(0.5)
    raise PowerError("已确认战败，未能返回可操作界面")


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


def _observe_battle(glyph, *, allow_team, check_popups, awaiting_repeat_transition=False):
    if auto.find_element(f"{IMAGES}/victory.png", "image", 0.88, crop=RESULT_TITLE):
        return "victory", None
    if check_popups:
        if auto.find_element(DEFEAT_TITLES, "text", crop=RESULT_TITLE):
            return "defeat", None
        _check_popup()
    if auto.find_element(f"{IMAGES}/pause.png", "image", 0.86, crop=BATTLE_CONTROLS):
        # 裁剪范围内原生 720p 图标的相对位置。
        pixels = np.asarray(auto.screenshot.convert("RGB"))[7:32, 18:59]
        return "battle", classify_auto_button(pixels, glyph)
    if allow_team and auto.find_element("开始挑战", "text", crop=START_CHALLENGE):
        return "team", None
    if awaiting_repeat_transition and battle_speed_visible(auto):
        return "battle", None
    return None, None


def _wait_battle(*, repeated=False, instance_screen="calyx", verify_team=False):
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
    frame_error_since = None
    while time.monotonic() < deadline:
        check_popups = time.monotonic() >= next_popup_check
        try:
            state, status = _observe_battle(glyph, allow_team=not saw_battle and instance_screen != "ornament",
                                            check_popups=check_popups, awaiting_repeat_transition=not left_result)
        except AdbError as error:
            if error.code not in TRANSIENT_FRAME_ERRORS:
                raise
            now = time.monotonic()
            if frame_error_since is None:
                frame_error_since = now
                log.warning(f"暂时无法取得可用的 ADB 战斗画面，等待恢复：{error}")
            if now - frame_error_since >= 15:
                raise
            off_frames = 0
            time.sleep(0.45)
            continue
        frame_error_since = None
        if check_popups:
            next_popup_check = time.monotonic() + 3

        if state == "victory" and left_result:
            if detect_auto and not confirmed_auto:
                log.warning("战斗已结算，未截到确认自动战斗开启的画面")
            return
        if state in ("battle", "team"):
            left_result = True
        if state == "defeat":
            _exit_defeat(instance_screen)
            raise BattleDefeat("副本挑战失败，已退出关卡")
        if state == "battle":
            if not saw_battle:
                saw_battle = True
                deadline = time.monotonic() + BATTLE_TIMEOUT
            if detect_auto and not speed_confirmed and time.monotonic() >= next_speed_check:
                try:
                    speed_confirmed = ensure_double_speed(auto)
                except AdbError as error:
                    if error.code not in TRANSIENT_FRAME_ERRORS:
                        raise
                    log.warning("暂时无法检测战斗倍速，继续等待本场结算")
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
                with limit_input_deadline(deadline):
                    if verify_team:
                        _check_popup(fatal_disconnect=True)
                        button = find_current_team_start(auto, START_CHALLENGE)
                        if not button or input_deadline_reached(time.monotonic()):
                            next_team_click = time.monotonic() + 3
                            continue
                        clicked = auto.click_element_with_pos(button)
                    else:
                        clicked = _click_text("开始挑战", START_CHALLENGE)
                    if not clicked:
                        raise PowerError("编队页开始挑战按钮无法点击")
                    log.info("确认仍在编队页，点按开始挑战")
                    team_retries += 1
                next_team_click = time.monotonic() + 3
        time.sleep(0.45)
    if repeated and not left_result:
        raise PowerError("等待进入新战斗超时，未确认再来一次的结算")
    raise PowerError("等待战斗结算超时" if saw_battle else "等待进入战斗超时")


def _run_instance(instance_type, name, planned, *, borrow_for_daily=False, on_settlement=None):
    """逐批挑战。结束时记下剩余的开拓力，总览从这个数估算恢复。"""
    balance = []
    try:
        yield from _run_batches(instance_type, name, planned, balance, borrow_for_daily=borrow_for_daily,
                                on_settlement=on_settlement)
    finally:
        if balance:
            save_reading(cfg, "overview_power", balance[-1])


def _run_batches(instance_type, name, planned, balance, *, borrow_for_daily=False, on_settlement=None):
    instance_screen, cost, _ = INSTANCES[instance_type]
    limit = batch_limit(cfg, instance_type)
    demand = borrow_for_daily if isinstance(borrow_for_daily, SupportDemand) else SupportDemand(borrow_for_daily)

    if instance_type == ORNAMENT:
        from tasks.touch import ornament

        yield from ornament.run_instance(name, planned, limit, demand, on_settlement, balance)
        return

    _select_category(instance_type)
    is_echo = instance_type == ECHO
    quota = _read_echo_rewards() if is_echo else None
    if quota == 0:
        cfg.save_timestamp("echo_of_war_timestamp")
        if planned is None:
            screen.change_to("main", max_recursion=1)
            return
    power = 0
    if quota != 0:
        power = read_power()
        power = _supplement(power)
        if power < cost:
            log.info("开拓力不足，结束本副本项")
            screen.change_to("main", max_recursion=1)
            if on_settlement is not None:
                on_settlement(0, power)
            return
    team_failure = None
    world_team = False
    if getattr(cfg, "tp_before_instance", False):
        if cfg.instance_team_enable:
            team_failure = _select_world_team(instance_type, name)
            world_team = team_failure is None
        _heal_teams()
        _select_category(instance_type)

    def enter(*, reselect=False):
        try:
            if reselect:
                _reenter_instance(instance_type, name)
            else:
                _enter_instance(instance_type, name)
        except PowerError as error:
            if team_failure:
                _check_popup(fatal_disconnect=True)
                restore_main(screen, name)
                raise InstanceTeamUnavailable(f"{name}：未确认进入原定副本，已跳过本项（{error}）") from error
            raise

    enter()
    remaining = planned
    previous = 0
    borrowed = False
    retries = 0
    cleaned = False
    completed = 0
    while remaining is None or remaining > 0:
        from utils.runs import DETAIL_TEXT, publish_detail
        practice = quota == 0
        total = planned or completed + (min(quota, power // cost) if is_echo else power // cost)
        if total > completed:
            publish_detail(DETAIL_TEXT["instance"], name=name, index=completed + 1, total=total)
        waves = limit if remaining is None else min(remaining, limit)
        if practice:
            waves = 1
        else:
            waves = min(waves, power // cost)
            if is_echo:
                waves = min(waves, quota)
        if not waves:
            break
        repeated = False
        try:
            if previous == waves and (not demand.pending or borrowed):
                if not _click_text("再来一次", REPEAT):
                    _check_popup()
                    raise PowerError("无法点击再来一次")
                if practice:
                    _confirm_echo_practice(required=True)
                repeated = True
            if not repeated:
                if previous:
                    _exit_result(instance_screen)
                    enter(reselect=True)
                waves, borrowed = _start_challenge(
                    instance_type, name, waves, borrow_for_daily=demand.pending, practice=practice,
                    world_team=world_team, team_failure=team_failure,
                )
            _wait_battle(repeated=repeated, instance_screen=instance_screen, verify_team=bool(team_failure))
        except TeamPresetUnavailable as error:
            log.info(f"{name}：{error}，改用主世界切队")
            restore_main(screen, name, leave_team=lambda: _leave_challenge_team(instance_screen))
            team_failure = _select_world_team(instance_type, name)
            world_team = team_failure is None
            previous = 0
            enter(reselect=True)
            continue
        except InstanceTeamUnavailable:
            restore_main(screen, name, leave_team=lambda: _leave_challenge_team(instance_screen))
            raise
        except BattleDefeat:
            if retries >= DEFEAT_RETRIES:
                raise
            retries += 1
            log.warning(f"已确认战败，重试 {retries}/{DEFEAT_RETRIES}")
            previous = 0
            enter(reselect=True)
            continue
        except RelicBagFull:
            if cleaned or not _clean_full_bag():
                raise
            cleaned = True
            previous = 0
            enter(reselect=True)
            continue

        demand.won(borrowed)
        completed += waves
        yield waves
        log.info(f"已结算 {waves} 次")
        previous, retries = waves, 0
        if remaining is not None:
            remaining -= waves
        if not practice:
            power -= waves * cost
            balance.append(power)
        if on_settlement is not None:
            on_settlement(waves, None)
        if is_echo and not practice:
            quota -= waves
            if quota == 0:
                cfg.save_timestamp("echo_of_war_timestamp")
            _exit_result(instance_screen)
            previous = 0
            if quota == 0 and planned is None:
                break
            if remaining != 0 and (quota == 0 or power >= cost):
                enter(reselect=True)

    exit_screen = _exit_result(instance_screen) if previous else None
    if exit_screen != "main":
        screen.change_to("main", max_recursion=1)


def run_weekly_echo(*, borrow_for_daily=False):
    if not echo_day_due(cfg, date.today()):
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

    plan = remaining_plan(cfg)
    if plan:
        complete = run_plan(cfg, plan, run_instance)
        if not complete or not getattr(cfg, "power_plan_continue", True):
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
    if succeeded and on_summary is not None:
        if remaining is not None:
            on_summary(tr("已完成 {count} 次挑战，剩余开拓力 {power}/300").format(count=total, power=remaining))
        elif total:
            on_summary(tr("已完成 {count} 次挑战").format(count=total))
    return succeeded


def run_standalone(*, on_summary=None):
    from tasks.touch import daily

    return run(borrow_for_daily=daily.support_demand(), on_summary=on_summary)
