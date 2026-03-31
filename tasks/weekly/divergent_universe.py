from module.screen import screen
from module.automation import auto
from module.config import cfg
from module.logger import log
from module.automation.screenshot import Screenshot
from module.notification.notification import NotificationLevel
from tasks.base.base import Base
from utils.date import Date
from typing import Literal, Tuple, Optional
import numpy as np
import time
import os
import re
from tasks.power.instance import Instance


class DivergentUniverse:
    def __init__(self):
        self.screenshot = None  # 任务截图
        self.result: Optional[bool] = None  # 对局结果
        self.current_stage: str = ""  # 当前关卡阶段
        self.process_stage: bool = False  # 是否正在处理关卡中
        self.end_loop: bool = False  # 是否结束主循环

    def start(self):
        log.hr('准备差分宇宙', '0')
        if self.run():
            Base.send_notification_with_screenshot("差分宇宙已完成", NotificationLevel.ALL, self.screenshot)
            self.screenshot = None
        else:
            Base.send_notification_with_screenshot("差分宇宙未完成", NotificationLevel.ERROR, self.screenshot)
            self.screenshot = None
        has_reward = self.get_reward()
        if Date.is_next_mon_x_am(cfg.weekly_divergent_timestamp, cfg.refresh_hour):
            self.check_divergent_universe_score()
        if has_reward and cfg.universe_bonus_enable:
            self.process_ornament()
        log.hr("完成", 2)

    def check_divergent_universe_score(self) -> bool:
        """
        检查差分宇宙积分，达到 14000 时记录时间戳
        """
        screen.wait_for_screen_change("divergent_main")
        score_pos = (182 / 1920, 977 / 1080, 209 / 1920, 43 / 1080)
        score = auto.get_single_line_text(score_pos)
        if not score:
            log.warning("未识别到差分宇宙积分")
            return False

        score_parts = score.split('/')
        if len(score_parts) == 2 and score_parts[0].isdigit() and score_parts[1].isdigit() and score_parts[1] == "14000":
            log.info(f"差分宇宙积分：{score_parts[0]} / {score_parts[1]}")
            if score_parts[0] == "14000":
                cfg.save_timestamp("weekly_divergent_timestamp")
                log.info("已达到最高积分 14000，记录时间")
                return True
        else:
            log.warning(f"无法解析差分宇宙积分: {score}")
        return False

    def run(self) -> bool:
        if self.start_war(cfg.weekly_divergent_type):
            return self.loop()
        return False

    def get_reward(self):
        log.info("开始领取奖励")
        if auto.click_element("./assets/images/share/base/RedExclamationMark.png", "image", 0.9, crop=(0 / 1920, 877.0 / 1080, 422.0 / 1920, 202.0 / 1080)):
            if auto.click_element("./assets/images/zh_CN/universe/one_key_receive.png", "image", 0.9, max_retries=10):
                if auto.find_element("./assets/images/zh_CN/base/click_close.png", "image", 0.8, max_retries=10):
                    time.sleep(2)
                    Base.send_notification_with_screenshot(cfg.notify_template['SimulatedUniverseRewardClaimed'], NotificationLevel.ALL)
                    auto.click_element("./assets/images/zh_CN/base/click_close.png", "image", 0.8, max_retries=10)
                    time.sleep(1)
                    auto.press_key("esc")
                    return True
        return False

    def process_ornament(self):
        screen.change_to("guide3")

        immersifier_crop = (1623.0 / 1920, 40.0 / 1080, 162.0 / 1920, 52.0 / 1080)
        text = auto.get_single_line_text(crop=immersifier_crop, blacklist=['+', '米'], max_retries=3)
        if "/12" not in text:
            log.error("沉浸器数量识别失败")
            return

        immersifier_count = int(text.split("/")[0])
        log.info(f"沉浸器: {immersifier_count}/12")
        if immersifier_count > 0:
            instance_name = cfg.instance_names["饰品提取"]

            # 使用培养目标的副本配置（如果启用）
            try:
                if cfg.build_target_enable:
                    from tasks.daily.buildtarget import BuildTarget
                    target_instances = BuildTarget.get_target_instances()

                    for target_type, target_name in target_instances:
                        # 精确匹配副本类型
                        if target_type == "饰品提取":
                            log.info(f"使用培养目标副本: {target_name}")
                            instance_name = target_name
                            break
            except Exception as e:
                log.error(f"获取培养目标副本失败: {e}")

            Instance.run("饰品提取", instance_name, 40, immersifier_count)

    def start_war(self, type: Literal["normal", "cycle"] = "normal") -> bool:
        log.info("开始「差分宇宙」")
        screen.change_to("divergent_mode_select")

        if auto.click_element("结束并结算", "text", crop=(39 / 1920, 215 / 1080, 748 / 1920, 597 / 1080)):
            log.warning("检测到未结算的对局，放弃并结算中")
            if auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10):
                self.loop()

        if type == "normal":
            log.info("选择常规演算")
            screen.change_to("divergent_mode_select_normal")
        else:
            log.info("选择周期演算")
            screen.change_to("divergent_mode_select_cycle")

        if not self.choose_level(int(cfg.weekly_divergent_level)):
            log.error("选择关卡失败，结束任务")
            return False

        if not auto.click_element("./assets/images/screen/divergent_universe/start.png", "image", 0.9, 10):
            log.error("未找到开始对局按钮，结束任务")
            return False
        else:
            time.sleep(1)
            auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=4)

        log.info("开始对局")
        return True

    def choose_level(self, level: int) -> bool:
        """
        选择关卡难度
        """
        log.info("选择关卡")

        level_positions = [
            (94 / 1920, 145 / 1080, 67 / 1920, 68 / 1080),
            (93 / 1920, 253 / 1080, 68 / 1920, 68 / 1080),
            (92 / 1920, 362 / 1080, 68 / 1920, 67 / 1080),
            (94 / 1920, 469 / 1080, 67 / 1920, 67 / 1080),
            (93 / 1920, 580 / 1080, 68 / 1920, 64 / 1080)
        ]

        if auto.click_element(level_positions[level - 1], 'crop'):
            log.info(f"已选择难度 {level} 的关卡")
            time.sleep(1)
            return True

        return False

    def loop(self) -> bool:
        """
        差分宇宙任务主循环
        """
        self.screenshot = None  # 任务截图
        self.result = None  # 重置结果
        self.current_stage = ""  # 重置当前关卡阶段
        self.process_stage = False  # 重置关卡处理状态
        self.end_loop = False  # 重置结束循环标志

        start_time = time.monotonic()
        timeout = 60 * 120  # 120分钟超时
        while True:
            # 检查超时
            if time.monotonic() - start_time > timeout:
                log.error("差分宇宙主循环超时（120分钟），强制退出")
                return False

            if (
                self.check_stage()
                or self.check_title()
                or self.check_auto_battle()
                or self.check_click_close()
                or self.check_click_return()
            ):
                continue
            elif self.end_loop:
                end_time = time.monotonic()
                elapsed_time = end_time - start_time
                minutes = int(elapsed_time // 60)
                seconds = int(elapsed_time % 60)
                log.info(f"本次差分宇宙用时：{minutes} 分钟 {seconds} 秒")
                time.sleep(4)
                screen.wait_for_screen_change("divergent_main")
                log.info("已返回差分宇宙首页")
                return self.result if self.result is not None else False

    def check_stage(self):
        if not auto.find_element("./assets/images/screen/divergent_universe/stage.png", "image", 0.9):
            return

        stage_crop = (57 / 1920, 15 / 1080, 260 / 1920, 27 / 1080)
        stage_text = auto.get_single_line_text(crop=stage_crop)
        if not stage_text:
            return

        # 示例："（1/13）第一位面-战斗"
        stage_match = re.search(
            # r"[（(]\s*(\d+)\s*/\s*(13)\s*[)）]\s*第\s*([^位\s]+)\s*位面(?:\s*[-—－]\s*(.+))?",
            r"[（(]\s*(\d+)\s*/\s*(13)\s*[)）]\s*第\s*([一二三])\s*位面(?:\s*[-—－]\s*(.+))?",
            stage_text
        )
        if stage_match:
            current, total, plane, station = stage_match.groups()
            station = station.strip() if station else "未知"
            new_stage = f"{current}/{total}|第{plane}位面|{station}"
            if new_stage != self.current_stage:
                self.current_stage = new_stage
                log.hr(f"当前阶段 {current}/{total}，第{plane}位面，区域：{station}", 2)
                if "首领" in station or "战斗" in station or "精英" in station:
                    self.process_battle_stage()
                elif "空白" in station or "休整" in station or "商店" in station or "财富" in station:
                    self.process_battle_stage_finish()
                else:
                    self.process_leave()
            elif self.process_stage:
                if "首领" in station or "战斗" in station or "精英" in station:
                    self.process_battle_stage_finish()
            return

    def process_battle_stage(self):
        time.sleep(2)
        enemy_crop = (675 / 1920, 41 / 1080, 274 / 1920, 37 / 1080)
        auto.press_key_down("w")
        time.sleep(0.2)
        if not cfg.cloud_game_enable and not cfg.weekly_divergent_stable_mode:
            auto.press_key_down("shift")
        start_time = time.monotonic()
        while time.monotonic() - start_time < 3:  # 最多等待3秒
            if auto.find_element("./assets/images/screen/divergent_universe/enemy.png", "image", 0.9, crop=enemy_crop):
                break
        time.sleep(0.8)
        auto.press_key_up("w")
        if not cfg.cloud_game_enable and not cfg.weekly_divergent_stable_mode:
            auto.press_key_up("shift")
        for _ in range(5):
            auto.press_mouse()
            time.sleep(1)
        time.sleep(2)
        self.process_stage = True

    def process_battle_stage_finish(self):
        time.sleep(2)
        self.process_stage = False
        if self.process_random_door():
            return

        auto.press_mouse()
        if self.process_random_door():
            return

        auto.press_key("a", 0.5)
        time.sleep(0.2)
        auto.press_key("w", 0.5)
        if self.process_random_door():
            return

        self.process_re_enter()
        if self.process_random_door():
            return

        auto.press_key("d", 0.5)
        time.sleep(0.2)
        auto.press_key("w", 0.5)
        if self.process_random_door():
            return

        self.process_re_enter()
        if self.process_random_door(stable_mode=True):
            return

        self.process_leave()

    def process_leave(self):
        auto.press_key("esc")
        if auto.click_element("结束并结算", "text", max_retries=10, crop=(1238 / 1920, 859 / 1080, 562 / 1920, 165 / 1080)):
            auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10)

    def process_re_enter(self):
        auto.press_key("esc")
        if auto.click_element("暂离", "text", max_retries=10, crop=(1238 / 1920, 859 / 1080, 562 / 1920, 165 / 1080)):
            screen.wait_for_screen_change("main")
            if auto.find_element("./assets/images/share/base/F.png", "image", 0.9, crop=(998.0 / 1920, 473.0 / 1080, 392.0 / 1920, 296.0 / 1080)):
                auto.press_key("f")
                screen.wait_for_screen_change('divergent_main')
            screen.change_to("divergent_mode_select")
            if auto.click_element("继续进度", "text", crop=(39 / 1920, 215 / 1080, 748 / 1920, 597 / 1080)):
                auto.find_element("./assets/images/screen/divergent_universe/stage.png", "image", 0.9, max_retries=10)
            else:
                raise Exception("未找到继续进度按钮")
        else:
            auto.press_key("esc")

    def detect_random_door(self):
        # LOWER = np.array([112, 82, 174])
        # UPPER = np.array([170, 126, 239])
        # crop = (68 / 1920, 4 / 1080, 1718 / 1920, 818 / 1080)
        # return auto.find_element((LOWER, UPPER), "hsv", crop=crop)
        LOWER = np.array([126, 84, 174])
        UPPER = np.array([170, 127, 228])
        return auto.find_element((LOWER, UPPER), "hsv")

    def process_random_door(self, stable_mode=False):
        window = Screenshot.get_window(cfg.game_title_name)
        win_x, _, width, _ = Screenshot.get_window_region(window)
        screen_center_x = win_x + width // 2
        tolerance = width // 10  # 屏幕宽度10%作为容差

        result = self.detect_random_door()
        if not result:
            log.debug("未检测到随意门")
            return False

        top_left, bottom_right = result
        door_center_x = (top_left[0] + bottom_right[0]) // 2

        if abs(door_center_x - screen_center_x) <= tolerance:
            log.debug("随意门已在屏幕中间")
        else:
            key = "a" if door_center_x < screen_center_x else "d"
            log.debug(f"随意门在屏幕{'左边' if key == 'a' else '右边'}，正在调整位置")

            auto.press_key_down(key)
            try:
                start_time = time.monotonic()
                while time.monotonic() - start_time < 10:
                    time.sleep(0.1)
                    result = self.detect_random_door()
                    if not result:
                        break
                    top_left, bottom_right = result
                    door_center_x = (top_left[0] + bottom_right[0]) // 2
                    if abs(door_center_x - screen_center_x) <= tolerance:
                        log.debug("随意门已调整到屏幕中间")
                        break
            finally:
                auto.press_key_up(key)

        # 向随意门走去，边走边检测F图标和门的位置
        f_crop = (1078 / 1920, 595 / 1080, 37 / 1920, 37 / 1080)
        door_crop = (1146 / 1920, 585 / 1080, 57 / 1920, 57 / 1080)
        # fine_tolerance = width // 40  # 细微调整用更小的容差
        fine_tolerance = width // 10  # 屏幕宽度10%作为容差

        if cfg.cloud_game_enable or cfg.weekly_divergent_stable_mode:
            stable_mode = True

        if not stable_mode:
            auto.press_key_down("w")
        else:
            auto.press_key("w", 2)

        timeout = 15
        if stable_mode:
            timeout = 60

        try:
            start_time = time.monotonic()
            # time.sleep(1)
            while time.monotonic() - start_time < timeout:
                # time.sleep(0.1)

                if stable_mode:
                    auto.press_key("w")

                # 检测F交互图标
                if auto.find_element("./assets/images/screen/divergent_universe/f.png", "image", 0.9, crop=f_crop):
                    log.debug("检测到F交互图标")
                    if not stable_mode:
                        auto.press_key_up("w")

                    if auto.find_element("./assets/images/screen/divergent_universe/door.png", "image", 0.9, crop=door_crop):
                        auto.press_key("f")
                        auto.press_key("f")
                        auto.press_key("f")
                        auto.press_key("f")
                        auto.press_key("f")
                        time.sleep(2)
                        if auto.find_element("./assets/images/screen/divergent_universe/stage.png", "image", 0.9):
                            return False
                        return True
                    else:
                        if not stable_mode:
                            auto.press_key_down("w")
                        # else:
                        #     auto.press_key("w", 1)
                        time.sleep(0.5)

                # 检测随意门位置，细微调整方向
                result = self.detect_random_door()
                if not result:
                    continue
                top_left, bottom_right = result
                door_center_x = (top_left[0] + bottom_right[0]) // 2
                offset = door_center_x - screen_center_x

                if abs(offset) > fine_tolerance:
                    adjust_key = "a" if offset < 0 else "d"
                    auto.press_key(adjust_key, wait_time=0.1)
        finally:
            auto.press_key_up("w")
        return False

    def check_title(self):
        """
        检查当前界面标题，并根据不同标题执行对应的处理函数
        """
        title_crop = (96 / 1920, 63 / 1080, 142 / 1920, 34 / 1080)
        if auto.find_element(("欢愉假面", "选择方程", "选择祝福", "选择奇物", "丢弃奇物", "愿力满盈", "选择下一站", "事件", "选择站点卡", "存档管理", "混沌药箱"), 'text', crop=title_crop, include=True):
            log.info(f"检测到 “{auto.matched_text}” 界面")
            if auto.matched_text == "欢愉假面":
                self.process_mask()
            elif auto.matched_text == "选择方程":
                self.process_equation()
            elif auto.matched_text == "选择祝福":
                self.process_blessing()
            elif auto.matched_text == "选择奇物":
                self.process_relic_selection()
            elif auto.matched_text == "丢弃奇物":
                self.process_relic_discard()
            elif auto.matched_text == "愿力满盈":
                self.process_wish()
            elif auto.matched_text == "选择下一站":
                self.process_next_station()
            elif auto.matched_text == "事件":
                self.process_event()
            elif auto.matched_text == "选择站点卡":
                self.process_station_card()
            elif auto.matched_text == "存档管理":
                self.process_save_management()
            elif auto.matched_text == "混沌药箱":
                self.process_chaos_box()
            return True
        return False

    def process_mask(self):
        """
        处理欢愉假面界面：默认选择中间的面具"""
        mask_positions = [
            (408 / 1920, 529 / 1080, 147 / 1920, 48 / 1080),
            (411 / 1920, 713 / 1080, 144 / 1920, 50 / 1080),
            (413 / 1920, 900 / 1080, 142 / 1920, 51 / 1080),
        ]
        if auto.click_element(("选择一张面具", "确定"), 'text'):
            if auto.matched_text == "选择一张面具":
                for pos in mask_positions:
                    if auto.click_element("战车面具", "text", crop=pos):
                        log.info("检测到战车面具，优先选择")
                        time.sleep(2)
                        return
                log.info("默认选择中间的面具")
                auto.click_element(mask_positions[1], 'crop')

    def process_equation(self):
        """
        处理选择方程界面：优先选择未收集的方程或已展开的方程
        """
        equation_positions = [
            (281 / 1920, 244 / 1080, 417 / 1920, 607 / 1080),
            (753 / 1920, 243 / 1080, 418 / 1920, 609 / 1080),
            (1222 / 1920, 243 / 1080, 418 / 1920, 606 / 1080),
        ]

        has_choose = False

        time.sleep(2)
        for pos in equation_positions:
            if auto.click_element("./assets/images/screen/divergent_universe/new_equation.png", "image", 0.9, crop=pos):
                log.info("检测到 “图鉴未收集” 选项，尝试点击")
                has_choose = True
                break

        if not has_choose:
            for pos in equation_positions:
                if auto.click_element("已展开", "text", crop=pos):
                    log.info("检测到 “已展开” 选项，尝试点击")
                    has_choose = True
                    break

        if not has_choose:
            log.info("未检测到优先可选项，默认选择中间的方程")
            auto.click_element(equation_positions[1], 'crop')
            has_choose = True

        time.sleep(1)
        auto.click_element('确认', 'text', None, 10, crop=(1657 / 1920, 948 / 1080, 99 / 1920, 49 / 1080), include=True)
        time.sleep(2)

    def process_blessing(self):
        """
        处理选择祝福界面：优先选择未收集的祝福或建议选项
        """
        blessing_positions = [
            (280 / 1920, 241 / 1080, 409 / 1920, 611 / 1080),
            (758 / 1920, 242 / 1080, 407 / 1920, 608 / 1080),
            (1236 / 1920, 242 / 1080, 409 / 1920, 610 / 1080),
        ]

        blessing2_positions = [
            (519 / 1920, 241 / 1080, 408 / 1920, 610 / 1080),
            (999 / 1920, 242 / 1080, 405 / 1920, 609 / 1080),
        ]

        has_choose = False

        time.sleep(2)
        for pos in blessing_positions:
            if auto.click_element("./assets/images/screen/divergent_universe/new_blessing.png", "image", 0.9, crop=pos):
                log.info("检测到 “图鉴未收集” 选项，尝试点击")
                has_choose = True
                break

        if not has_choose:
            for pos in blessing_positions:
                if auto.click_element("./assets/images/screen/divergent_universe/rec_blessing.png", "image", 0.9, crop=pos):
                    log.info("检测到建议选项，尝试点击")
                    has_choose = True
                    break

        if not has_choose:
            log.info("未检测到优先可选项，默认选择中间的祝福")
            auto.click_element(blessing2_positions[0], 'crop')
            auto.click_element(blessing_positions[1], 'crop')
            has_choose = True

        time.sleep(1)
        auto.click_element('确认', 'text', None, 10, crop=(1644 / 1920, 934 / 1080, 88 / 1920, 48 / 1080), include=True)
        time.sleep(2)

    def process_relic_selection(self):
        """
        处理选择奇物界面：优先选择未收集的奇物或建议选项
        """
        relic_positions = [
            (281 / 1920, 242 / 1080, 407 / 1920, 610 / 1080),
            (757 / 1920, 242 / 1080, 410 / 1920, 610 / 1080),
            (1235 / 1920, 242 / 1080, 410 / 1920, 610 / 1080),
        ]

        time.sleep(2)
        has_choose = False

        for pos in relic_positions:
            if auto.click_element("./assets/images/screen/divergent_universe/new_relic.png", "image", 0.9, crop=pos):
                log.info("检测到 “图鉴未收集” 选项，尝试点击")
                has_choose = True
                break

        if not has_choose:
            log.info("未检测到优先可选项，默认选择中间的奇物")
            auto.click_element(relic_positions[1], 'crop')
            has_choose = True

        time.sleep(1)
        auto.click_element('确认', 'text', None, 10, crop=(1660 / 1920, 948 / 1080, 93 / 1920, 49 / 1080), include=True)
        time.sleep(2)

    def process_relic_discard(self):
        """
        处理丢弃奇物界面：默认选择中间的奇物进行丢弃
        """
        relic_positions = [
            (281 / 1920, 242 / 1080, 407 / 1920, 610 / 1080),
            (757 / 1920, 242 / 1080, 410 / 1920, 610 / 1080),
            (1235 / 1920, 242 / 1080, 410 / 1920, 610 / 1080),
        ]

        log.info("尝试丢弃中间的奇物")
        auto.click_element(relic_positions[1], 'crop')
        time.sleep(1)
        auto.click_element('丢弃', 'text', None, 10, crop=(1695 / 1920, 948 / 1080, 69 / 1920, 50 / 1080), include=True)
        time.sleep(2)

    def process_wish(self):
        """
        处理愿力满盈界面：优先选择未收集的奇迹或建议选项
        """
        wish_positions = [
            (268 / 1920, 244 / 1080, 406 / 1920, 627 / 1080),
            (756 / 1920, 245 / 1080, 408 / 1920, 624 / 1080),
            (1246 / 1920, 245 / 1080, 406 / 1920, 623 / 1080),
        ]
        wish2_positions = [
            (519 / 1920, 257 / 1080, 392 / 1920, 599 / 1080),
            (1008 / 1920, 258 / 1080, 392 / 1920, 598 / 1080),
        ]

        has_choose = False

        time.sleep(2)
        for pos in wish_positions:
            if auto.click_element("./assets/images/screen/divergent_universe/new_wish.png", "image", 0.9, crop=pos):
                log.info("检测到 “图鉴未收集” 选项，尝试点击")
                has_choose = True
                break

        if not has_choose:
            log.info("未检测到优先可选项，默认选择中间的奇迹")
            auto.click_element(wish2_positions[0], 'crop')
            auto.click_element(wish_positions[1], 'crop')
            has_choose = True

        time.sleep(1)
        auto.click_element('确认', 'text', None, 10, crop=(551 / 1920, 942 / 1080, 805 / 1920, 62 / 1080), include=True)
        time.sleep(2)

    def process_next_station(self):
        # 战斗/精英/事件/异常/奖励/财富/冒险/商店/铸造/空白 奇遇（宝箱/祝福/奇物合成/铸造/惊喜升级） 首领/休整/转化
        station_positions = [
            (570 / 1920, 433 / 1080, 252 / 1920, 403 / 1080),
            (835 / 1920, 432 / 1080, 251 / 1920, 405 / 1080),
            (1097 / 1920, 432 / 1080, 252 / 1920, 405 / 1080),
        ]
        re_extract_crop = (560 / 1920, 940 / 1080, 374 / 1920, 56 / 1080)

        for _ in range(10):
            time.sleep(2)
            has_priority_station = False

            station_tags = []
            for pos in station_positions:
                if auto.find_element(("战斗", "精英", "事件", "异常", "奖励", "财富", "冒险", "商店", "铸造", "空白", "奇遇", "首领", "休整", "转化"), 'text', crop=pos, include=True):
                    station_tags.append(auto.matched_text)
                else:
                    station_tags.append(None)

            log.debug(f"站点卡标签: {station_tags}")

            if not any(station_tags):
                return

            # 根据优先级选择点击哪个站点，若优先级相同，点击中间的站点
            priority_map = {
                "首领": 0,
                "战斗": 1,
                "精英": 2,
                "空白": 3,
                "休整": 4,
                "商店": 5,
                "财富": 6,
                # "异常": 7,
                # "事件": 8,
            }

            # 获取每个站点的优先级，None 的优先级设为最低（优先级最高）
            station_priorities = []
            for tag in station_tags:
                if tag is None:
                    station_priorities.append(float('inf'))
                else:
                    if tag in priority_map:
                        has_priority_station = True
                    station_priorities.append(priority_map.get(tag, 7))  # 其他标签优先级同为 7

            if not has_priority_station:
                if not auto.find_element("0", "text", crop=re_extract_crop, include=True):
                    auto.click_element(re_extract_crop, 'crop')
                    time.sleep(2)
                    auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9)
                    continue
            break

        # 找到最高优先级（最小的优先级值）
        min_priority = min(station_priorities)

        # 找到所有具有最高优先级的站点索引
        best_indices = [i for i, p in enumerate(station_priorities) if p == min_priority]

        # 如果有多个最优选择，选择第一个
        if len(best_indices) > 1:
            # selected_index = best_indices[len(best_indices) // 2]
            selected_index = best_indices[0]
        else:
            selected_index = best_indices[0]

        # auto.click_element(station_positions[selected_index], 'crop')
        auto.click_element(f"{station_tags[selected_index]}", 'text', None, 10, crop=station_positions[selected_index], include=True)
        log.info(f"选择 “{station_tags[selected_index]}” 站点卡")

        time.sleep(1)
        auto.click_element('确定', 'text', None, 10, crop=(561 / 1920, 937 / 1080, 794 / 1920, 60 / 1080), include=True)
        time.sleep(2)

    def process_event(self):
        while True:
            time.sleep(1)
            if auto.click_element("./assets/images/screen/divergent_universe/event_next.png", "image", 0.9):
                continue
            if auto.click_element("./assets/images/screen/divergent_universe/event_choose.png", "image", 0.9):
                continue
            if auto.click_element("./assets/images/screen/divergent_universe/event_leave.png", "image", 0.9):
                continue

            has_confirm = False
            matchs = auto.find_element("./assets/images/screen/divergent_universe/event_option.png", "image_with_multiple_targets", 0.9)
            for match in reversed(matchs):
                auto.click_element_with_pos(match)
                time.sleep(0.5)
                auto.mouse_scroll(20, -1, False)
                time.sleep(0.5)
                if auto.click_element('确定', 'text', None, 4, include=True):
                    has_confirm = True
                    break
            if has_confirm:
                continue
            break

    def process_station_card(self):
        if auto.find_element(("删除", "使其变为【空白】区域"), "text", crop=(110 / 1920, 136 / 1080, 1226 / 1920, 48 / 1080), include=True):
            auto.click_element(("异常", "事件", "奖励", "冒险", "铸造"), "text", crop=(59 / 1920, 243 / 1080, 1262 / 1920, 786 / 1080), include=True)
        auto.click_element('确定', 'text', None, 10, crop=(1589 / 1920, 919 / 1080, 73 / 1920, 38 / 1080), include=True)
        time.sleep(2)

    def process_save_management(self):
        time.sleep(2)

    def process_chaos_box(self):
        time.sleep(2)
        auto.click_element('离开', 'text', None, 10, crop=(1105 / 1920, 94 / 1080, 702 / 1920, 858 / 1080), include=False)
        time.sleep(1)
        auto.click_element('确定', 'text', None, 10, crop=(1105 / 1920, 94 / 1080, 702 / 1920, 858 / 1080), include=False)
        time.sleep(2)

    def check_auto_battle(self):
        """
        检查并开启自动战斗
        """
        if cfg.auto_battle_detect_enable and auto.find_element("./assets/images/share/base/not_auto.png", "image", 0.9, crop=(0.0 / 1920, 903.0 / 1080, 144.0 / 1920, 120.0 / 1080)):
            log.info("尝试开启自动战斗")
            auto.press_key("v")
            return True
        return False

    def check_click_close(self):
        """
        检查并点击 “点击空白处关闭” 的按钮
        """
        if auto.click_element("点击空白处关闭", 'text', None, crop=(820 / 1920, 831 / 1080, 277 / 1920, 245 / 1080), include=True):
            log.info(f"检测到 “点击空白处关闭” 的按钮，尝试点击")
            return True
        return False

    def check_click_return(self):
        """
        检查并点击 “终止战斗并结算” 和 “返回主界面” 的按钮
        """
        if result := auto.find_element(("终止战斗并结算", "返回主界面"), 'text', None, crop=(574 / 1920, 949 / 1080, 790 / 1920, 59 / 1080), include=True):

            if auto.matched_text == "终止战斗并结算":
                log.info(f"检测到 “终止战斗并结算” 的按钮，尝试点击")
                auto.click_element_with_pos(result)
                time.sleep(2)
                if not auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10):
                    auto.press_key("esc")
                return True

            elif auto.matched_text == "返回主界面":
                log.info(f"检测到 “返回主界面” 的按钮，尝试点击")
                self._check_battle_result()
                auto.click_element_with_pos(result)
                if self.result is not None:
                    log.info(f"本次对局结果：{'成功' if self.result else '失败'}")
                else:
                    log.info("本次对局结果：未知")
                self.end_loop = True

        return False

    def _check_battle_result(self):
        """
        检查并记录对局结果
        """
        if auto.find_element(("探索成功", "探索中断"), 'text', include=True):
            if auto.matched_text == "探索成功":
                self.result = True
                self.screenshot = auto.screenshot
                return
            elif auto.matched_text == "探索中断":
                self.result = False
                self.screenshot = auto.screenshot
                return
