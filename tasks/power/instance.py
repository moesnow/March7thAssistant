import re
import time

from module.automation import auto
from module.config import cfg
from module.localization import get_raw_instance_names
from module.logger import log
from module.screen import screen
from tasks.base.list_drag import drag_list
from tasks.base.team import Team
from tasks.power.battle import ensure_double_speed
from tasks.power.policy import (
    BATTLE_TIMEOUT, ENTRY_TIMEOUT, CRIMSON_CALYX, ECHO, INSTANCE_LIMITS, ORNAMENT,
    PowerError, RelicBagFull, parse_challenge_cost, parse_echo_rewards, parse_ornament_payment,
    parse_power, parse_wave_count,
)
from tasks.power.readout import read_number
from tasks.power.character import Character
from tasks.power.relicset import Relicset
from utils.game_options import game_option_enabled
from utils.wait import wait_until


CATEGORY = (262 / 1920, 289 / 1080, 422 / 1920, 624 / 1080)
ENTRY_ROWS = (686 / 1920, 287 / 1080, 980 / 1920, 650 / 1080)
WAVE_SELECTOR = (1160 / 1920, 828 / 1080, 755 / 1920, 104 / 1080)
CHALLENGE_COST = (1210 / 1920, 947 / 1080, 262 / 1920, 78 / 1080)
REPEAT_COST = (1011 / 1920, 923 / 1080, 174 / 1920, 78 / 1080)
CHALLENGE = (1392 / 1920, 946 / 1080, 487 / 1920, 83 / 1080)
TEAM_TABS = (311 / 1920, 12 / 1080, 1376 / 1920, 105 / 1080)
DIALOG = (245 / 1920, 200 / 1080, 1430 / 1920, 645 / 1080)
INSTANCE_POPUPS = ("开拓力补充", "背包内遗器持有数量已达上限", "长时间未操作", "已处于无法战斗状态")
ORNAMENT_START_POPUPS = ("仍有角色位空缺", "当前不存在任何存档，是否直接开始战斗")
CONFIRM = "./assets/images/zh_CN/base/confirm.png"
FIGHT_AGAIN = "./assets/images/zh_CN/fight/fight_again.png"
FIGHT_FAIL = "./assets/images/zh_CN/fight/fight_fail.png"
FIGHT_EXIT = "./assets/images/zh_CN/fight/fight_exit.png"
PAUSE = "./assets/images/purefiction/battle_pause.png"
MAX_START_CLICKS = 5
MAX_RECONNECTS = 3


class Instance:
    @staticmethod
    def get_target_team(instance_type, instance_name):
        for team in cfg.instance_teams:
            if team["instance_name"] == instance_name:
                return team["team_number"]
        return cfg.instance_team_number

    @staticmethod
    def select_category(instance_type):
        screen.change_to("guide3")
        if not auto.click_element(instance_type, "text", crop=CATEGORY):
            if not drag_list(auto, (645 / 1920, 805 / 1080), (645 / 1920, 405 / 1080), crop=CATEGORY):
                raise PowerError("未能滚动生存索引分类")
            if not auto.click_element(instance_type, "text", crop=CATEGORY, max_retries=4, retry_delay=0.3):
                raise PowerError(f"未找到生存索引中的{instance_type}")
        time.sleep(0.6)

    @staticmethod
    def prepare_instance(instance_type, instance_name):
        Instance.select_category(instance_type)
        auto.click_element("./assets/images/screen/guide/power.png", "image", max_retries=2)
        is_ornament = instance_type == ORNAMENT
        for _ in range(12):
            entry = auto.find_element(
                ("传送", "进入", "追踪"), "min_distance_text", crop=ENTRY_ROWS, include=True,
                source=instance_name, source_type="text",
                position="top_right" if instance_type == CRIMSON_CALYX else "bottom_right",
            )
            if entry:
                if auto.matched_text == "追踪":
                    raise PowerError(f"指定副本未解锁：{instance_name}")
                if not auto.click_element_with_pos(entry):
                    raise PowerError(f"无法点击副本入口：{instance_name}")
                break
            if not drag_list(auto, (1125 / 1920, 810 / 1080), (1125 / 1920, (490 if is_ornament else 410) / 1080),
                             crop=ENTRY_ROWS, end_pause=0.2, settle=0.45):
                raise PowerError("生存索引列表未稳定")
        else:
            raise PowerError(f"未找到指定副本：{instance_name}")

        if instance_type == CRIMSON_CALYX:
            instance_name = get_raw_instance_names()[instance_type][instance_name].replace("2", "")
        title = ((591 / 1920, 98 / 1080, 594 / 1920, 393 / 1080) if is_ornament
                 else (1172 / 1920, 5 / 1080, 742 / 1920, 636 / 1080))

        def ready():
            if auto.find_element(instance_name, "text", include=True, crop=title):
                return True
            if auto.find_element(("是否切换", "是否传送", "不再弹出"), "text", include=True, crop=DIALOG):
                auto.click_element(CONFIRM, "image", 0.9)
            return False

        return wait_until(ready, ENTRY_TIMEOUT, 0.8)

    @staticmethod
    def read_echo_rewards():
        Instance.select_category(ECHO)

        quota = read_number(auto, (682 / 1920, 275 / 1080, 1002 / 1920, 184 / 1080), parse_echo_rewards,
                            "未能确认历战余响奖励次数")
        log.info(f"历战余响本周剩余奖励次数：{quota}/3")
        return quota

    @staticmethod
    def read_balance(instance_type, *, result=False):
        if instance_type == ORNAMENT:
            crop = (1496 / 1920, 35 / 1080, 123 / 1920, 54 / 1080)
            if result:
                crop = (1481 / 1920, 35 / 1080, 127 / 1920, 55 / 1080)
        else:
            crop = (1588 / 1920, 22 / 1080, 198 / 1920, 60 / 1080)
        return read_number(auto, crop, parse_power, "未能确认副本界面的开拓力余额")

    @staticmethod
    def _select_waves(instance_type, requested):
        count_crop = ((1490 / 1920, 819 / 1080, 240 / 1920, 65 / 1080) if instance_type == ORNAMENT
                      else (1476 / 1920, 837 / 1080, 156 / 1920, 43 / 1080))

        def parse(text):
            return parse_wave_count(text, "挑战次数", INSTANCE_LIMITS[instance_type][1])

        if not auto.find_element("挑战次数", "text", crop=count_crop, include=True, max_retries=3, retry_delay=0.3):
            if instance_type == ECHO:
                return 1
            if requested == 1:
                return 1
            raise PowerError("未能确认连续挑战次数")
        selected = read_number(auto, count_crop, parse, "未识别当前挑战次数")
        for _ in range(abs(requested - selected)):
            if selected < requested:
                changed = auto.click_element("./assets/images/screen/guide/plus.png", "image", 0.82, crop=WAVE_SELECTOR)
            else:
                point = (1359 / 1920, 875 / 1080, 0, 0) if instance_type == ORNAMENT else (1250 / 1920, 888 / 1080, 0, 0)
                changed = auto.click_element(point, "crop")
            if not changed:
                raise PowerError("无法调整连续挑战次数")
            time.sleep(0.2)
        read_number(auto, count_crop, lambda text: requested if parse(text) == requested else None,
                    f"未确认已选中 {requested} 次挑战")
        return requested

    @staticmethod
    def _read_payment(instance_type, waves, *, repeat=False):
        if instance_type == ORNAMENT:
            crop = REPEAT_COST if repeat else (1350 / 1920, 944 / 1080, 226 / 1920, 76 / 1080)
            return read_number(auto, crop, lambda text: parse_ornament_payment(text, waves),
                               "未能确认饰品提取按钮的费用", retries=3)[0]
        crop = REPEAT_COST if repeat else CHALLENGE_COST

        return read_number(auto, crop, parse_challenge_cost, "未能确认挑战按钮的开拓力费用", retries=3)

    @staticmethod
    def prepare_payment(instance_type, requested, available, *, practice, immersifier_only):
        while requested:
            waves = Instance._select_waves(instance_type, requested)
            if practice:
                # 无奖励提示会在点击挑战后再次确认，绝不代付额外开拓力。
                return 1, 0
            cost = Instance._read_payment(instance_type, waves)
            if instance_type != ORNAMENT and cost != waves * INSTANCE_LIMITS[instance_type][0]:
                raise PowerError(f"挑战费用 {cost} 与已选择的 {waves} 次挑战不符")
            if cost <= (0 if immersifier_only else available):
                return waves, cost
            if instance_type != ORNAMENT:
                return 0, 0
            requested = waves - (cost - (0 if immersifier_only else available) + 39) // 40
        return 0, 0

    @staticmethod
    def repeat_payment(instance_type, waves, practice):
        if practice:
            return None  # 重新进本核对无奖励提示。
        try:
            cost = Instance._read_payment(instance_type, waves, repeat=True)
        except PowerError:
            return None
        if instance_type == ORNAMENT or cost == waves * INSTANCE_LIMITS[instance_type][0]:
            return cost
        return None

    @staticmethod
    def select_world_team(instance_type, name):
        if not Team.change_to(Instance.get_target_team(instance_type, name)):
            raise PowerError(f"主世界未能切换到 {name} 配置的队伍")

    @staticmethod
    def _select_instance_team(team):
        if not re.fullmatch(r"0?[1-9]|1[0-9]", str(team)):
            raise PowerError(f"队伍编号 {team} 格式错误")
        label = str(team).zfill(2)
        left, right = (650 / 1920, 65 / 1080), (1300 / 1920, 65 / 1080)
        for _ in range(5):
            if auto.click_element(label, "text", crop=TEAM_TABS, max_retries=2, retry_delay=0.25):
                time.sleep(0.6)
                log.info(f"副本编队已选择队伍 {label}")
                return True
            start, end = (left, right) if int(team) <= 7 else (right, left)
            if not drag_list(auto, start, end, crop=TEAM_TABS):
                break
        return False

    @staticmethod
    def _select_ornament_team(team):
        if not re.fullmatch(r"0?[1-9]|1[0-9]", str(team)):
            return False
        presets = (6 / 1920, 8 / 1080, 578 / 1920, 168 / 1080)
        team_names = (6 / 1920, 116 / 1080, 300 / 1920, 900 / 1080)
        if not auto.click_element((619 / 1920, 780 / 1080, 77 / 1920, 75 / 1080), "crop"):
            return False

        selected = False
        if auto.click_element("预设编队", "text", crop=presets, max_retries=4, retry_delay=0.3):
            for _ in range(8):
                if auto.click_element(f"队伍{int(team)}", "text", crop=team_names, max_retries=3, retry_delay=0.3):
                    selected = True
                    break
                if not drag_list(auto, (430 / 1920, 850 / 1080), (430 / 1920, 350 / 1080), crop=team_names):
                    break
            auto.press_key("esc")
        elif not auto.find_element("开始挑战", "text", crop=CHALLENGE):
            auto.press_key("esc")

        if not auto.find_element("开始挑战", "text", crop=CHALLENGE, max_retries=8, retry_delay=0.3):
            raise PowerError("退出编队后未能返回饰品提取挑战页")
        return selected

    @staticmethod
    def _confirm_practice():
        if not auto.find_element("次数已耗尽", "text", crop=DIALOG, include=True, max_retries=8, retry_delay=0.3):
            raise PowerError("未确认历战余响的无奖励挑战提示")
        if not auto.click_element(CONFIRM, "image", 0.9):
            raise PowerError("无法确认历战余响无奖励挑战")

    @staticmethod
    def start_instance(instance_type, name, support, *, practice, world_team):
        ornament = instance_type == ORNAMENT
        if ornament:
            if cfg.instance_team_enable:
                team = Instance.get_target_team(instance_type, name)
                if not Instance._select_ornament_team(team):
                    log.warning(f"未选中饰品提取预设队伍 {team}，保留当前编队")
            empty = auto.find_element("./assets/images/share/universe/empty_character_slot.png", "image_count", 0.8,
                                      crop=(624 / 1920, 772 / 1080, 267 / 1920, 91 / 1080), pixel_bgr=[233, 233, 233])
            if empty and empty >= 3 and not Instance._select_ornament_team(1):
                raise PowerError("饰品提取没有可用编队，未能选中队伍 1")
        else:
            if not auto.click_element("挑战", "text", crop=CHALLENGE, max_retries=5, retry_delay=0.35):
                Instance.check_popup()
                raise PowerError("未找到副本的挑战按钮")
            if practice:
                Instance._confirm_practice()
            if not auto.find_element("开始挑战", "text", crop=CHALLENGE, max_retries=12, retry_delay=0.3):
                Instance.check_popup()
                raise PowerError("未进入副本编队")
            if cfg.instance_team_enable and not world_team:
                if not Instance._select_instance_team(Instance.get_target_team(instance_type, name)):
                    # 有些 PC 编队页只给临时队伍。退出后沿用主世界切队，重进并重新核算费用。
                    raise TeamPresetUnavailable("编队页未找到配置的预设队伍")

        borrowed = support.should_borrow(cfg) and Character.borrow("ornament" if ornament else "standard", for_training=support.pending)
        Instance._click_start_challenge(ornament=ornament)
        if ornament:
            Instance._engage_ornament_boss()
        return borrowed

    @staticmethod
    def _click_start_challenge(*, ornament):
        button = auto.find_element("开始挑战", "text", crop=CHALLENGE, max_retries=5, retry_delay=0.35)
        if not button:
            Instance.check_popup()
            raise PowerError("无法开始挑战")

        popups = INSTANCE_POPUPS + ("连接中断",)
        if ornament:
            popups += ORNAMENT_START_POPUPS
        for _ in range(MAX_START_CLICKS):
            auto.click_element_with_pos(button)
            time.sleep(0.5)
            # 弹窗交给后续流程处理，补点前以最后一帧的按钮位置为准。
            if auto.find_element(popups, "text", crop=DIALOG, include=True):
                return
            button = auto.find_element("开始挑战", "text", crop=CHALLENGE, max_retries=2, retry_delay=0.25)
            if not button:
                return
        log.warning(f"已尝试点击开始挑战 {MAX_START_CLICKS} 次，按钮仍可见，等待游戏转场")

    @staticmethod
    def _engage_ornament_boss():
        def ready():
            Instance.check_popup()
            if auto.find_element(ORNAMENT_START_POPUPS, "text", crop=DIALOG, include=True):
                auto.click_element(CONFIRM, "image", 0.9)
            return auto.find_element("./assets/images/purefiction/prepare_fight.png", "image", 200000,
                                     crop=(0, 0, 300 / 1920, 300 / 1080))

        if not wait_until(ready, 45, 0.5):
            raise PowerError("未进入饰品提取首领场地")
        auto.press_key("w", 3)
        for _ in range(3):
            auto.press_mouse()
            time.sleep(0.6)

    @staticmethod
    def check_popup(*, check_disconnect=False) -> bool:
        labels = INSTANCE_POPUPS
        if check_disconnect:
            labels += ("连接中断",)
        found = auto.find_element(labels, "text", crop=DIALOG, include=True, threshold=0.75)
        if not found:
            return False
        label = auto.matched_text
        if label == "连接中断":
            return bool(auto.find_element(("尝试重连", "退出游戏"), "text", include=True,
                                          take_screenshot=False, need_ocr=False))
        if label == "开拓力补充":
            auto.click_element("取消", "text", crop=(0.25, 0.67, 0.24, 0.2), max_retries=4, retry_delay=0.25)
            raise PowerError("检测到非预期开拓力补充，已停止挑战")
        if label == "背包内遗器持有数量已达上限":
            raise RelicBagFull("遗器背包已满")
        if label == "已处于无法战斗状态":
            auto.click_element(CONFIRM, "image", 0.9)
            return False
        raise PowerError("检测到游戏超时弹窗")

    @staticmethod
    def clean_full_bag():
        if not cfg.relic_bag_cleanup_enable:
            auto.press_key("esc")
            return False
        if not auto.click_element(CONFIRM, "image", 0.9):
            return False
        return Relicset.run()

    @staticmethod
    def start_instance_again(practice=False):
        if not auto.click_element(FIGHT_AGAIN, "image", 0.88, max_retries=3, retry_delay=0.3):
            raise PowerError("无法点击再来一次")
        if practice:
            Instance._confirm_practice()

    @staticmethod
    def complete_run(instance_type):
        if not auto.click_element(FIGHT_EXIT, "image", 0.9, max_retries=6, retry_delay=0.35):
            raise PowerError("未找到退出关卡按钮")
        time.sleep(2)
        if screen.check_screen("main"):
            return
        auto.press_key("esc")
        screen.change_to("main", max_recursion=1)

    @staticmethod
    def exit_defeat():
        if not auto.click_element(FIGHT_EXIT, "image", 0.9, max_retries=4, retry_delay=0.3):
            if not auto.click_element(FIGHT_FAIL, "image", 0.9, max_retries=3, retry_delay=0.3):
                raise PowerError("已战败，未能退出关卡")
        time.sleep(1.5)
        screen.change_to("main", max_recursion=1)

    @staticmethod
    def wait_fight(*, repeated=False):
        deadline = time.monotonic() + ENTRY_TIMEOUT
        in_battle = False
        left_result = not repeated
        next_popup_check = 0.0
        next_controls = 0.0
        reconnects = 0
        while time.monotonic() < deadline:
            victory = auto.find_element(FIGHT_AGAIN, "image", 0.88)
            if victory and left_result:
                return True
            if auto.find_element(FIGHT_FAIL, "image", 0.9, take_screenshot=False):
                return False
            now = time.monotonic()
            if now >= next_popup_check:
                next_popup_check = now + 2
                if Instance.check_popup(check_disconnect=True):
                    if reconnects >= MAX_RECONNECTS:
                        raise PowerError("游戏连接中断，重连失败，已中止当前战斗")
                    reconnects += 1
                    log.warning(f"战斗中检测到游戏连接中断，尝试重连（{reconnects}/{MAX_RECONNECTS}）")
                    if not auto.click_element("尝试重连", "text", include=True,
                                              take_screenshot=False, need_ocr=False):
                        auto.click_element(CONFIRM, "image", 0.9, take_screenshot=False)
                    time.sleep(5)
                    continue
            if auto.find_element(PAUSE, "image", 0.88, crop=(0.95, 0, 0.05, 0.09), scale_range=(0.65, 1.05)):
                left_result = True
                if not in_battle:
                    log.info("进入战斗")
                    in_battle = True
                    deadline = now + BATTLE_TIMEOUT
                if now >= next_controls and game_option_enabled(cfg, "auto_battle_detect_enable"):
                    if auto.find_element("./assets/images/share/base/not_auto.png", "image", 0.9,
                                         crop=(0, 903 / 1080, 144 / 1920, 120 / 1080)):
                        auto.press_key(cfg.get_value("hotkey_auto_battle", "v"))
                    ensure_double_speed(auto)
                    next_controls = now + 3
            time.sleep(0.55)
        raise PowerError("战斗结算超时" if in_battle else "等待进入战斗超时")

    @staticmethod
    def heal_teams():
        log.hr("正在寻找传送锚点", 2)
        screen.change_to("map")
        if not Instance._detect_space_anchor():
            log.info("当前地图未找到传送锚点，传送至模拟宇宙再试")
            screen.change_to("universe_main")
            screen.change_to("map")
            if not Instance._detect_space_anchor():
                log.warning("未找到可传送的恢复锚点，继续准备副本")
        screen.change_to("main")

    @staticmethod
    def _detect_space_anchor():
        for name in ("SpaceAnchor1", "SpaceAnchor2"):
            if auto.click_element(f"./assets/images/share/power/space_anchor/{name}.png", "image", 3000000, max_retries=2):
                if auto.click_element("传送", "text", max_retries=10):
                    return True
        return False


class TeamPresetUnavailable(PowerError):
    """当前编队界面不提供所选预设。"""
