import re
import time

from module.automation import auto
from module.config import cfg
from module.localization import get_raw_instance_names
from module.logger import log
from module.screen import screen
from tasks.base.list_drag import changed_ratio, drag_list
from tasks.base.task_steps import FATAL_GAME_ERRORS, GameRecoveryError
from tasks.power.battle import battle_speed_visible, ensure_double_speed
from tasks.power.policy import (
    BATTLE_TIMEOUT, ENTRY_TIMEOUT, CRIMSON_CALYX, ECHO, ORNAMENT,
    InstanceTeamUnavailable, InstanceUnavailable, PowerError, RelicBagFull, parse_echo_rewards,
)
from tasks.power.readout import read_number
from tasks.power.character import CHALLENGE, Character
from tasks.power.relicset import Relicset
from tasks.power.team import TEAM_ACTIONS, find_current_team_start, select_preset, warn_team_switch
from utils.game_options import game_option_enabled
from utils.wait import wait_until


CATEGORY = (262 / 1920, 289 / 1080, 422 / 1920, 624 / 1080)
ENTRY_ROWS = (686 / 1920, 287 / 1080, 980 / 1920, 650 / 1080)
WAVE_SELECTOR = (1160 / 1920, 828 / 1080, 755 / 1920, 104 / 1080)
DIALOG = (245 / 1920, 200 / 1080, 1430 / 1920, 645 / 1080)
INSTANCE_POPUPS = ("开拓力补充", "背包内遗器持有数量已达上限", "长时间未操作", "已处于无法战斗状态")
ORNAMENT_START_POPUPS = ("仍有角色位空缺", "当前不存在任何存档，是否直接开始战斗")
CONFIRM = "./assets/images/zh_CN/base/confirm.png"
FIGHT_AGAIN = "./assets/images/zh_CN/fight/fight_again.png"
FIGHT_FAIL = "./assets/images/zh_CN/fight/fight_fail.png"
FIGHT_EXIT = "./assets/images/zh_CN/fight/fight_exit.png"
PAUSE = "./assets/images/purefiction/battle_pause.png"
AUTO_DISABLED = "./assets/images/share/base/not_auto.png"
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
        names = get_raw_instance_names()[instance_type]
        names = tuple(name for name in (names.values() if instance_type == CRIMSON_CALYX else names)
                      if name not in ("无", "跳过"))

        def list_ready():
            if not auto.find_element(names, "text", crop=ENTRY_ROWS, include=True):
                return False
            return (auto.find_element(("传送", "进入", "追踪"), "text", take_screenshot=False, need_ocr=False)
                    and not auto.find_element(("角色培养", "培养设置"), "text", include=True,
                                              take_screenshot=False, need_ocr=False))

        wait_until(list_ready, 5, 0.5)
        auto.click_element("./assets/images/screen/guide/power.png", "image", max_retries=2)
        is_ornament = instance_type == ORNAMENT
        start = (1125 / 1920, 810 / 1080)
        end = (1125 / 1920, (490 if is_ornament else 410) / 1080)
        unchanged_drags = 0
        for attempt in range(24):
            entry = auto.find_element(
                ("传送", "进入", "追踪"), "min_distance_text", crop=ENTRY_ROWS, include=True,
                source=instance_name, source_type="text",
                position="top_right" if instance_type == CRIMSON_CALYX else "bottom_right",
            )
            if entry:
                if auto.matched_text == "追踪":
                    raise InstanceUnavailable(f"指定副本未解锁：{instance_name}")
                if not auto.click_element_with_pos(entry):
                    raise PowerError(f"无法点击副本入口：{instance_name}")
                break
            # 单次手势可能漏收，连续两次停稳无位移才提前反向。
            search_down = attempt < 12 and unchanged_drags < 2
            drag_start, drag_end = (start, end) if search_down else (end, start)
            before = auto.screenshot.copy()
            if not drag_list(auto, drag_start, drag_end, crop=ENTRY_ROWS, end_pause=0.2, settle=0.45):
                raise PowerError("生存索引列表未稳定")
            if search_down:
                unchanged_drags = unchanged_drags + 1 if changed_ratio(before, auto.screenshot) <= 0.01 else 0
        else:
            raise PowerError(f"未找到指定副本：{instance_name}")

        if instance_type == CRIMSON_CALYX:
            instance_name = get_raw_instance_names()[instance_type][instance_name].replace("2", "")
        title = ((591 / 1920, 98 / 1080, 594 / 1920, 393 / 1080) if is_ornament
                 else (1172 / 1920, 5 / 1080, 742 / 1920, 636 / 1080))
        entry_prompts = (("不再弹出", "是否切换", "是否传送") if instance_type == ECHO
                         else ("是否切换", "是否传送", "不再弹出"))
        echo_checkbox_attempted = False

        def ready():
            nonlocal echo_checkbox_attempted
            if auto.find_element(instance_name, "text", include=True, crop=title):
                return True
            popup = auto.find_element(entry_prompts, "text", include=True, crop=DIALOG)
            if not popup:
                return False
            if instance_type == ECHO and auto.matched_text == "不再弹出":
                if not echo_checkbox_attempted:
                    echo_checkbox_attempted = True
                    if not auto.click_element_with_pos(popup):
                        log.warning("未能勾选历战余响的不再弹出，继续确认剧情提示")
                    time.sleep(0.5)
                confirm = auto.find_element(CONFIRM, "image", 0.9)
                if confirm:
                    auto.click_element_with_pos(confirm)
                else:
                    auto.click_element("确认", "text", include=True, crop=DIALOG)
            else:
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
    def select_waves(instance_type, requested):
        # 从生存索引重新进入副本时，游戏默认选择一场。
        if requested == 1:
            return 1
        plus = auto.find_element("./assets/images/screen/guide/plus.png", "image", 0.82,
                                 crop=WAVE_SELECTOR, max_retries=3, retry_delay=0.3)
        if not plus:
            if instance_type == ECHO:
                return 1
            raise ChallengePageUnavailable("未找到增加连续挑战次数的按钮")
        for _ in range(requested - 1):
            if not auto.click_element_with_pos(plus):
                raise PowerError("无法调整连续挑战次数")
            time.sleep(0.2)
        return requested

    @staticmethod
    def select_world_team(instance_type, name):
        team = Instance.get_target_team(instance_type, name)
        screen.change_to("configure_team")
        reason = select_preset(auto, team, activate=True)
        if reason:
            Instance.check_team_connection()
            warn_team_switch(name, team, "主世界编队", reason)
        else:
            log.info(f"已确认主世界启用队伍 {str(team).zfill(2)}")
        return reason

    @staticmethod
    def leave_challenge_team():
        if auto.find_element(("快速编队", "开始挑战"), "text", crop=TEAM_ACTIONS):
            auto.press_key("esc")
            wait_until(lambda: auto.find_element("挑战", "text", crop=CHALLENGE), 5, 0.35)

    @staticmethod
    def check_team_connection():
        if (auto.find_element("连接中断", "text", crop=DIALOG, include=True)
                and auto.find_element(("尝试重连", "退出游戏"), "text", include=True,
                                      take_screenshot=False, need_ocr=False)):
            raise GameRecoveryError("副本准备期间检测到游戏连接中断")

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
    def start_instance(instance_type, name, support, *, practice, world_team, team_failure=None):
        ornament = instance_type == ORNAMENT
        start_button = None
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
                if team_failure:
                    Instance.check_team_connection()
                Instance.check_popup()
                raise ChallengePageUnavailable("未找到副本的挑战按钮")
            if practice:
                Instance._confirm_practice()
            start_button = auto.find_element("开始挑战", "text", crop=CHALLENGE, max_retries=12, retry_delay=0.3)
            if not start_button and not (cfg.instance_team_enable and auto.find_element(
                "快速编队", "text", crop=TEAM_ACTIONS,
            )):
                if team_failure:
                    Instance.check_team_connection()
                Instance.check_popup()
                raise ChallengePageUnavailable("未进入副本编队")
            if cfg.instance_team_enable and not world_team and team_failure is None:
                team = Instance.get_target_team(instance_type, name)
                reason = select_preset(auto, team)
                if not reason:
                    start_button = auto.find_element("开始挑战", "text", crop=CHALLENGE,
                                                     max_retries=4, retry_delay=0.35)
                    if not start_button:
                        reason = "未确认目标队伍可出战"
                if reason:
                    Instance.check_team_connection()
                    raise TeamPresetUnavailable(f"副本未能使用队伍 {str(team).zfill(2)}（{reason}）")
                log.info(f"已确认副本选中队伍 {str(team).zfill(2)}")

        borrowed = False
        if support.should_borrow(cfg):
            borrowed = Character.borrow("ornament" if ornament else "standard", for_training=support.pending)
            start_button = None
        if team_failure:
            Instance.check_team_connection()
            start_button = find_current_team_start(auto, CHALLENGE)
            if not start_button:
                raise InstanceTeamUnavailable(f"{name}：无法确认当前副本有可出战的队伍，已跳过本项")
            log.info(f"{name}：已确认当前副本编队可出战，继续挑战")
        Instance._click_start_challenge(ornament=ornament, button=start_button, verify_team=bool(team_failure))
        if ornament:
            Instance._engage_ornament_boss()
        return borrowed

    @staticmethod
    def _click_start_challenge(*, ornament, button=None, verify_team=False):
        if button is None:
            button = auto.find_element("开始挑战", "text", crop=CHALLENGE, max_retries=5, retry_delay=0.35)
        if not button:
            Instance.check_popup()
            raise ChallengePageUnavailable("未找到开始挑战按钮")

        popups = INSTANCE_POPUPS + ("连接中断",)
        if ornament:
            popups += ORNAMENT_START_POPUPS
        for _ in range(MAX_START_CLICKS):
            auto.click_element_with_pos(button)
            time.sleep(0.5)
            # 弹窗交给后续流程处理，补点前以最后一帧的按钮位置为准。
            if auto.find_element(popups, "text", crop=DIALOG, include=True):
                return
            button = (find_current_team_start(auto, CHALLENGE) if verify_team else
                      auto.find_element("开始挑战", "text", crop=CHALLENGE, max_retries=2, retry_delay=0.25))
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
        next_popup_check = 0.0
        next_controls = 0.0
        reconnects = 0
        while time.monotonic() < deadline:
            victory = auto.find_element(FIGHT_AGAIN, "image", 0.88)
            if victory and (not repeated or in_battle):
                return True
            awaiting_repeat = repeated and not in_battle
            result_visible = victory or (awaiting_repeat and auto.find_element(
                FIGHT_EXIT, "image", 0.9, take_screenshot=False,
            ))
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
            if result_visible:
                time.sleep(0.55)
                continue

            pause = auto.find_element(PAUSE, "image", 0.88, crop=(0.95, 0, 0.05, 0.09), scale_range=(0.65, 1.05))
            controls_due = now >= next_controls and game_option_enabled(cfg, "auto_battle_detect_enable")
            disabled_auto = controls_due and auto.find_element(
                AUTO_DISABLED, "image", 0.9, crop=(0, 903 / 1080, 144 / 1920, 120 / 1080),
            )
            speed_visible = False
            if not in_battle and not pause and not disabled_auto:
                try:
                    speed_visible = battle_speed_visible(auto)
                except FATAL_GAME_ERRORS:
                    raise
                except RuntimeError as error:
                    log.warning(f"暂时无法识别战斗倍速控件：{error}")
            if pause or disabled_auto or speed_visible:
                if not in_battle:
                    log.info("进入战斗")
                    in_battle = True
                    deadline = now + BATTLE_TIMEOUT
                if controls_due:
                    if disabled_auto:
                        auto.press_key(cfg.get_game_hotkey("hotkey_auto_battle", "v"))
                    if not speed_visible:
                        try:
                            ensure_double_speed(auto)
                        except FATAL_GAME_ERRORS:
                            raise
                        except RuntimeError as error:
                            log.warning(f"暂时无法检测战斗倍速，继续等待本场结算：{error}")
                    next_controls = now + 3
            time.sleep(0.55)
        if repeated and not in_battle:
            raise PowerError("等待进入新战斗超时，未确认再来一次的结算")
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
    """副本编队未能确认所选预设，可以尝试主世界切队。"""


class ChallengePageUnavailable(PowerError):
    """进入副本后未找到开打前所需的界面，尚未发起战斗。"""
