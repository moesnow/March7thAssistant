"""星启模式的三节点编队、战斗与结算处理。"""

import time

from module.automation import auto
from module.automation.screenshot import Screenshot
from module.config import cfg
from module.logger import log
from .basechallenge import BaseChallenge


class StellarChallenge:
    def __init__(self, challenge, highest_level, team3=None, enabled=False):
        self.challenge = challenge
        self.highest_level = highest_level
        self.team3 = team3 or []
        self.enabled = bool(enabled)
        self.result = None

    def validate_teams(self):
        if not self.enabled:
            return
        levels = self.challenge.level_range
        if (not isinstance(levels, (list, tuple)) or len(levels) != 2
                or any(type(level) is not int for level in levels)
                or not 1 <= levels[0] <= levels[1] <= self.highest_level):
            raise ValueError(f"{self.challenge.name}关卡范围需在1至{self.highest_level}之间，且起始值不能大于结束值")
        seen = set()
        teams = (self.challenge.team1, self.challenge.team2)
        if levels[1] == self.highest_level:
            teams += (self.team3,)
        for index, team in enumerate(teams, 1):
            if not isinstance(team, (list, tuple)) or not 1 <= len(team) <= 4:
                raise ValueError(f"星启模式队伍{index}需要配置1至4名角色")
            starters = 0
            for member in team:
                if not isinstance(member, (list, tuple)) or len(member) != 2:
                    raise ValueError(f"星启模式队伍{index}配置格式错误")
                character, technique = member
                if not isinstance(character, str) or not character or technique not in (-1, 0, 1, 2):
                    raise ValueError(f"星启模式队伍{index}的角色或秘技配置无效")
                if character in seen:
                    raise ValueError(f"星启模式不能重复使用角色：{character}")
                seen.add(character)
                starters += technique == -1
            if starters > 1:
                raise ValueError(f"星启模式队伍{index}只能配置一名秘技 / 开怪角色")

    def ensure_mode(self, stellar):
        target, other = ("星启模式", "常规模式") if stellar else ("常规模式", "星启模式")
        crop = (0.55, 0.15, 0.4, 0.25)
        if self.challenge.name == "末日幻影":
            crop = (0.40, 0.65, 0.20, 0.08)
        for attempt in range(5):
            target_visible = auto.find_element(target, "text", crop=crop, include=False)
            other_visible = auto.find_element(other, "text", crop=crop, include=False)
            if target_visible and other_visible:
                # 模式选择菜单同时显示两个选项时，必须点击目标项，不能仅凭文字可见判定已切换。
                if auto.click_element(target, "text", crop=crop, include=False):
                    time.sleep(2)
                    log.info(f"已点击{target}")
                    return
            elif target_visible:
                log.info(f"已确认{target}")
                return
            elif other_visible:
                auto.click_element(other, "text", crop=crop, include=False)
                time.sleep(2)
                continue
            # 切换入口在解锁前不存在；常规模式仍能照常运行。
            if not stellar and attempt == 0 and not target_visible and not other_visible:
                log.info("未发现模式切换入口，按常规模式执行")
                return
            time.sleep(1)
        if (auto.find_element(target, "text", crop=crop, include=False)
                and not auto.find_element(other, "text", crop=crop, include=False)):
            log.info(f"已确认{target}")
            return
        raise RuntimeError(f"无法确认{target}；请检查星启模式是否已解锁及当前画面")

    def _window_region(self):
        window = Screenshot.get_window(cfg.game_title_name)
        return Screenshot.get_window_region(window)

    def _click_ratio(self, x, y):
        left, top, width, height = self._window_region()
        point = (int(left + width * x), int(top + height * y))
        return auto.click_element_with_pos((point, point))

    def _node(self, number):
        name = ("节点一", "节点二", "节点三")[number - 1]
        aliases = [name, "节点—"] if number == 1 else [name]
        result = auto.find_element(aliases, "text", max_retries=3,
                                   crop=(0.34, 0.18, 0.30, 0.63), include=False)
        if not result:
            raise RuntimeError(f"星启编队界面未找到{name}")
        return result

    def _click_node_control(self, number, *, buff=False):
        if self.challenge.name == "末日幻影":
            # 末日幻影编队用数字标记节点，没有“节点一／二／三”文字。
            if not self._apocalyptic_team_screen():
                raise RuntimeError("未确认末日幻影星启角色列表，停止配置队伍")
            x = 1826 / 1920 if buff else 1488 / 1920
            if not self._click_ratio(x, (330 + (number - 1) * 216) / 1080):
                raise RuntimeError(f"点击星启节点{number}的配置入口失败")
            time.sleep(1)
            return
        top_left, bottom_right = self._node(number)
        left, top, width, height = self._window_region()
        # 以节点文字为纵向锚点；偏移取自用户提供的 1920×1080 编队截图。
        # 角色槽和增益按钮都在节点标题下方约 48 像素。
        y = (top_left[1] + bottom_right[1]) / 2 + height * 48 / 1080
        x = left + width * (1826 / 1920 if buff else 1488 / 1920)
        point = (int(x), int(y))
        if not auto.click_element_with_pos((point, point)):
            raise RuntimeError(f"点击星启节点{number}的配置入口失败")
        time.sleep(1)

    def _open_highest_level(self):
        if self.challenge.name == "末日幻影":
            self._open_apocalyptic_teams()
            return
        if not self.challenge.find_level(self.highest_level):
            raise RuntimeError("未找到星启模式最高关")
        if not auto.click_element(f"{self.highest_level:02}", "text", max_retries=5,
                                  crop=(0.17, 0.08, 0.82, 0.82), include=False):
            raise RuntimeError("点击星启模式最高关失败")
        for _ in range(10):
            if auto.find_element("编队", "text", crop=(0, 0, 0.32, 0.16), include=False):
                if not auto.find_element("星启模式", "text", crop=(0.32, 0, 0.3, 0.2), include=False):
                    raise RuntimeError("当前编队界面未确认星启模式")
                for number in (1, 2, 3):
                    self._node(number)
                return
            # 兼容关卡详情中的编队入口。
            auto.click_element(["更换编队", "前往编队", "下一步", "前往挑战"], "text", include=False)
            time.sleep(1)
        raise RuntimeError("未进入星启三节点编队界面")

    def _apocalyptic_team_screen(self):
        return (auto.find_element("角色列表", "text", crop=(0, 0.10, 0.30, 0.08), include=False)
                and auto.find_element("星启模式", "text", crop=(0.32, 0.05, 0.20, 0.10), include=False))

    def _open_apocalyptic_teams(self):
        nodes = ["节点一", "节点—", "节点二", "节点三"]
        node_crop = (0.20, 0.74, 0.60, 0.07)
        # 先用底部节点文字确认主页，避免套用旧版关卡页面的图片和流程。
        if not auto.find_element(nodes, "text", max_retries=5, crop=node_crop, include=False):
            raise RuntimeError("未确认末日幻影星启主页的节点入口")
        if not auto.click_element(f"{self.highest_level:02}", "text", max_retries=5,
                                  crop=(0.20, 0.87, 0.60, 0.06), include=True):
            raise RuntimeError("点击末日幻影星启最高关失败")
        time.sleep(1)
        for _ in range(10):
            if self._apocalyptic_team_screen():
                return
            # 无论进入哪个节点详情，下一步都是更换编队，不再依赖节点标题 OCR。
            if not auto.click_element("更换编队", "text", crop=(0.81, 0.76, 0.15, 0.08), include=False):
                auto.click_element(nodes, "text", crop=node_crop, include=False)
            time.sleep(1)
        raise RuntimeError("未进入末日幻影星启三节点编队界面")

    def _confirm_apocalyptic_teams(self):
        if not self._apocalyptic_team_screen():
            raise RuntimeError("未确认末日幻影星启角色列表，无法确认编队")
        if not auto.click_element("确认", "text", max_retries=5,
                                  crop=(0.77, 0.87, 0.22, 0.08), include=False):
            raise RuntimeError("确认末日幻影星启编队失败")
        for _ in range(10):
            if auto.find_element("当前队伍", "text", crop=(0.36, 0.70, 0.15, 0.07), include=False):
                return
            time.sleep(1)
        raise RuntimeError("确认编队后未返回末日幻影节点详情页")

    def _prepare_teams(self):
        if not auto.click_element("./assets/images/forgottenhall/reset.png", "image", 0.8,
                                  crop=(0.75, 0.015, 0.10, 0.10)):
            # 三节点和编队标题已确认后，点击截图中顶部的清空编队图标。
            if not self._click_ratio(1587 / 1920, 66 / 1080):
                raise RuntimeError("清空星启编队失败")
        time.sleep(0.5)
        for number, team in enumerate((self.challenge.team1, self.challenge.team2, self.team3), 1):
            log.info(f"配置星启节点{number}队伍")
            self._click_node_control(number)
            if not auto.find_element("角色列表", "text", max_retries=5,
                                     crop=(0, 0, 0.32, 0.25), include=False):
                raise RuntimeError(f"节点{number}未打开角色列表")
            if not BaseChallenge.select_characters(self.challenge, team, None, switch_team=False):
                raise RuntimeError(f"星启节点{number}选人失败")
        if self.challenge.name in ("虚构叙事", "末日幻影"):
            for number in (1, 2, 3):
                log.info(f"配置星启节点{number}增益")
                self._click_node_control(number, buff=True)
                if not self.challenge.select_buff_effect():
                    raise RuntimeError(f"星启节点{number}装配增益失败")

    def _ready(self):
        return auto.find_element("./assets/images/purefiction/prepare_fight.png", "image", 200000,
                                 crop=(0, 0, 300 / 1920, 300 / 1080))

    def _wait_ready(self, number, next_button=None):
        deadline = time.monotonic() + 90
        clicks = 0
        while time.monotonic() < deadline:
            if self._ready():
                if self.challenge.name == "混沌回忆":
                    # 准备画面标识可能在节点说明弹窗后方，先点击底部空白再执行秘技。
                    time.sleep(1)
                    for _ in range(3):
                        if not self._click_ratio(0.5, 0.97):
                            raise RuntimeError(f"关闭星启节点{number}说明弹窗失败")
                        time.sleep(0.5)
                log.info(f"已进入星启节点{number}准备画面")
                return
            if auto.find_element("空白", "text", include=True, crop=(0, 0.65, 1, 0.35)):
                auto.press_key("esc")
            elif next_button and clicks < 5 and auto.click_element(next_button, "text", include=False):
                clicks += 1
                log.info(f"点击{next_button}，等待节点准备画面")
            time.sleep(2)
        raise RuntimeError(f"等待星启节点{number}准备画面超时")

    def _return_after_failure(self):
        if not auto.find_element("失败", "text", crop=(0.3, 0.15, 0.4, 0.3), include=True):
            return False
        if not auto.click_element("返回", "text", max_retries=5,
                                  crop=(0.2, 0.75, 0.6, 0.25), include=True):
            raise RuntimeError("星启挑战失败后未能点击返回按钮，已保留画面")
        time.sleep(2)
        log.warning(f"{self.challenge.name}星启挑战失败，已点击返回，结束本次挑战")
        self.result = False
        self.challenge.max_level = 0
        return True

    def _wait_node_end(self, number):
        if number == 3 and self.challenge.name == "虚构叙事" and callable(getattr(self.challenge, 'return_to_stage_list', None)):
            # 虚构叙事最后一节点直接复用原生图片判定及返回流程。
            return self._finish_settlement(self.challenge.check_fight(30 * 60, final=True))
        deadline = time.monotonic() + 30 * 60
        next_button = ("前往节点二", "前往节点三")[number - 1] if number < 3 else None
        unknown_settlement = 0
        while time.monotonic() < deadline:
            if self._return_after_failure():
                return False
            if next_button and auto.find_element(next_button, "text", include=False):
                # 由准备画面确认函数执行点击及有限重试，不把“挑战结束”当作整关结束。
                self._wait_ready(number + 1, next_button)
                return
            if auto.find_element(["挑战结束", "挑战成功", "挑战失败"], "text",
                                 crop=(0.3, 0.15, 0.4, 0.3), include=False):
                if number == 3:
                    return self._finish_settlement(auto.matched_text == "挑战成功")
                unknown_settlement += 1
                if unknown_settlement >= 10:
                    raise RuntimeError(f"星启节点{number}结算后未找到{next_button}，已保留画面")
            if self.challenge.auto_battle_detect_enable and auto.find_element(
                    "./assets/images/share/base/not_auto.png", "image", 0.9,
                    crop=(0, 903 / 1080, 144 / 1920, 120 / 1080)):
                auto.press_key(cfg.get_value("hotkey_auto_battle", "v"))
            time.sleep(2)
        raise RuntimeError(f"星启节点{number}战斗超时，已保留画面")

    def _finish_settlement(self, succeeded):
        return_to_list = getattr(self.challenge, 'return_to_stage_list', None)
        if not callable(return_to_list):
            # 尚未确认最终返回按钮的挑战保留调试画面。
            log.warning(f"{self.challenge.name}星启节点三结算返回流程尚待截图确认，已保留画面。")
            raise SystemExit(0)
        if succeeded:
            log.info(f"{self.challenge.name}星启模式挑战成功")
        else:
            log.warning(f"{self.challenge.name}星启模式挑战失败")
        return_to_list()
        self.result = succeeded
        # 仅成功时接通原生的通关记录及奖励收尾，失败不能被当作通关。
        if succeeded:
            self.challenge.max_level = self.highest_level
        return succeeded

    def run_selected_levels(self):
        '''按起止范围挑战普通关卡，最高关使用星启流程，最后统一领奖'''
        self.validate_teams()
        self.result = None
        self.challenge.max_level = 0
        first, last = self.challenge.level_range
        cleared_level = 0
        if first < self.highest_level:
            self.ensure_mode(False)
            original_range = self.challenge.level_range
            try:
                self.challenge.level_range = (first, min(last, self.highest_level - 1))
                regular_result = self.challenge.start_challenges()
                cleared_level = self.challenge.max_level
            finally:
                self.challenge.level_range = original_range
            if regular_result is False:
                self.challenge.collect_rewards()
                return False
        result = None
        if last == self.highest_level:
            result = self.run()
            self.challenge.max_level = max(cleared_level, self.challenge.max_level)
        self.challenge.collect_rewards()
        return result

    def run(self):
        self.validate_teams()
        self.result = None
        self.challenge.max_level = 0
        self.ensure_mode(True)
        self._open_highest_level()
        self._prepare_teams()
        if self.challenge.name == "末日幻影":
            self._confirm_apocalyptic_teams()
        start_buttons = (["「混沌回忆」", "混沌回忆"] if self.challenge.name == "混沌回忆"
                         else ["进入故事", "开始挑战", "前往挑战"])
        if not auto.click_element(start_buttons, "text", max_retries=5,
                                  crop=(0.75, 0.85, 0.25, 0.15), include=False):
            raise RuntimeError("开始星启挑战失败")
        self._wait_ready(1)
        for number, team in enumerate((self.challenge.team1, self.challenge.team2, self.team3), 1):
            log.info(f"进入星启节点{number}，执行队伍{number}秘技并开怪")
            self.challenge.use_technique_and_attack_monster(team)
            result = self._wait_node_end(number)
            if result is False or number == 3:
                return result
