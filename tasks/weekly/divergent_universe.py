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
        self.stage_finish: bool = False  # 是否完成当前阶段
        self.unsupported_area: bool = False  # 是否遇到暂不支持区域

    def start(self):
        log.hr('准备差分宇宙', '0')
        if self.run():
            Base.send_notification_with_screenshot("差分宇宙已完成", NotificationLevel.ALL, self.screenshot)
            self.screenshot = None
        else:
            if self.unsupported_area:
                Base.send_notification_with_screenshot("差分宇宙未完成\n遇到暂不支持的区域", NotificationLevel.ERROR, self.screenshot)
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
        检查差分宇宙积分，达到 18000 时记录时间戳
        """
        screen.wait_for_screen_change("divergent_main")

        # 4.2版本周期积分将合并。本期积分奖励已由邮件发放。
        if auto.find_element("奖励已由邮件发放", "text", crop=(33 / 1920, 911 / 1080, 397 / 1920, 103 / 1080), include=True):
            log.info("检测到积分奖励已由邮件发放，跳过积分检查")
            cfg.save_timestamp("weekly_divergent_timestamp")
            return True

        score_pos = (182 / 1920, 977 / 1080, 209 / 1920, 43 / 1080)
        score = auto.get_single_line_text(score_pos)
        if not score:
            log.warning("未识别到差分宇宙积分")
            return False

        score_parts = score.split('/')
        if len(score_parts) == 2 and score_parts[0].isdigit() and score_parts[1].isdigit() and score_parts[1] in ("12000", "14000", "18000"):
            max_score = score_parts[1]
            log.info(f"差分宇宙积分：{score_parts[0]} / {max_score}")
            if score_parts[0] == max_score:
                cfg.save_timestamp("weekly_divergent_timestamp")
                log.info(f"已达到最高积分 {max_score}，记录时间")
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

        if not self.choose_level(int(cfg.weekly_divergent_level), type):
            log.error("选择关卡失败，结束任务")
            return False

        self.choose_team()

        if type == "normal" and int(cfg.weekly_divergent_level) == 6:
            if not auto.click_element("./assets/images/screen/divergent_universe/astronomical.png", "image", 0.9, 10):
                log.error("未找到进入星阶模式按钮，结束任务")
                return False

        if not auto.click_element("./assets/images/screen/divergent_universe/start.png", "image", 0.9, 10):
            log.error("未找到开始对局按钮，结束任务")
            return False
        else:
            time.sleep(1)
            auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=4)

        log.info("开始对局")
        return True

    def choose_level(self, level: int, type: Literal["normal", "cycle"] = "normal") -> bool:
        """
        选择关卡难度
        """
        log.info("选择关卡")

        level_positions = [
            (94 / 1920, 145 / 1080, 67 / 1920, 68 / 1080),
            (93 / 1920, 253 / 1080, 68 / 1920, 68 / 1080),
            (92 / 1920, 362 / 1080, 68 / 1920, 67 / 1080),
            (94 / 1920, 469 / 1080, 67 / 1920, 67 / 1080),
            (93 / 1920, 580 / 1080, 68 / 1920, 64 / 1080),
            (93 / 1920, 689 / 1080, 68 / 1920, 64 / 1080)
        ]

        if type == "cycle" and level == 6:
            log.info("周期演算不开启阈值协议，难度 6 视为难度 5")
            level = 5

        if auto.click_element(level_positions[level - 1], 'crop'):
            log.info(f"已选择难度 {level} 的关卡")
            time.sleep(1)
            if type == "cycle":
                for _ in range(10):
                    if auto.find_element("阈值协议", "text", crop=(1616 / 1920, 822 / 1080, 92 / 1920, 32 / 1080)):
                        auto.click_element((1492 / 1920, 868 / 1080, 75 / 1920, 39 / 1080), "crop")
                        time.sleep(1)
                    else:
                        break
            return True
        return False

    def choose_team(self):
        team_slot_crop = (1098 / 1920, 922 / 1080, 375 / 1920, 96 / 1080)
        if auto.find_element("./assets/images/share/universe/empty_character_slot.png", "image_count", 0.8, crop=team_slot_crop, pixel_bgr=[233, 233, 233]) == 4:
            if auto.click_element("./assets/images/share/universe/empty_character_slot.png", "image", 0.8, crop=team_slot_crop, take_screenshot=False):
                time.sleep(2)
                if auto.click_element("预设编队", "text", max_retries=4, retry_delay=0.5, crop=(6 / 1920, 8 / 1080, 578 / 1920, 168 / 1080)):
                    click_x = auto.screenshot_pos[0] + 260 / auto.screenshot_scale_factor
                    click_y = auto.screenshot_pos[1] + 175 / auto.screenshot_scale_factor
                    time.sleep(1.0)
                    if auto.click_element_with_pos(((click_x, click_y), (click_x, click_y))):
                        time.sleep(1.0)
                        auto.press_key("esc")
            time.sleep(1.0)

    def loop(self) -> bool:
        """
        差分宇宙任务主循环
        """
        self.screenshot = None  # 任务截图
        self.result = None  # 重置结果
        self.current_stage = ""  # 重置当前关卡阶段
        self.process_stage = False  # 重置关卡处理状态
        self.end_loop = False  # 重置结束循环标志
        self.stage_finish = False  # 重置阶段完成标志
        self.unsupported_area = False  # 重置暂不支持区域标志

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

            time.sleep(2)

    def check_stage(self):
        if not auto.find_element("./assets/images/screen/divergent_universe/stage.png", "image", 0.9, crop=(33 / 1920, 52 / 1080, 68 / 1920, 60 / 1080)):
            return

        if result := auto.find_element("./assets/images/screen/divergent_universe/show.png", "image", 0.9, crop=(383 / 1920, 57 / 1080, 71 / 1920, 48 / 1080)):
            auto.press_key_down("alt")
            time.sleep(1)
            auto.click_element_with_pos(result)
            time.sleep(1)
            auto.press_key_up("alt")
            time.sleep(2)

        stage_crop = (57 / 1920, 15 / 1080, 260 / 1920, 27 / 1080)
        stage_text = auto.get_single_line_text(crop=stage_crop)
        if not stage_text:
            return

        stage_pattern = r"[（(]\s*(\d+)\s*/\s*(13|17|20)\s*[)）]\s*第\s*([一二三])\s*位面(?:\s*[-—－]\s*(.+))?"
        keywords = ["战斗", "精英", "事件", "异常", "奖励", "财富", "冒险", "商店", "铸造", "空白", "首领", "休整", "转化"]

        def normalize_station(raw_station):
            station_name = raw_station.strip() if raw_station else "未知"
            if station_name and station_name not in keywords:
                for keyword in keywords:
                    if any(char in keyword for char in station_name):
                        return keyword
            return station_name

        def parse_stage_info(stage_value):
            if not stage_value:
                return None
            stage_info_match = re.match(r"^(\d+)/(\d+)\|第([一二三])位面\|(.+)$", stage_value)
            if not stage_info_match:
                return None
            return stage_info_match.groups()

        # 示例："（1/13）第一位面-战斗"
        stage_match = re.search(
            # r"[（(]\s*(\d+)\s*/\s*(13)\s*[)）]\s*第\s*([^位\s]+)\s*位面(?:\s*[-—－]\s*(.+))?",
            stage_pattern,
            stage_text
        )
        if stage_match:
            current, total, plane, station = stage_match.groups()

            # 修复 OCR 识别错误问题，“第二位面” 在特定场景下小概率会识别成 “第三位面”
            if total == "13":
                if current in ["1", "2", "3", "4"]:
                    plane = "一"
                elif current in ["5", "6", "7", "8", "9"]:
                    plane = "二"
                elif current in ["10", "11", "12", "13"]:
                    plane = "三"

            station = normalize_station(station)

            if station == "未知":
                previous_stage_info = parse_stage_info(self.current_stage)
                if previous_stage_info:
                    prev_current, prev_total, prev_plane, prev_station = previous_stage_info
                    if (current, total, plane) == (prev_current, prev_total, prev_plane):
                        station = prev_station
                        log.debug(f"区域识别为未知且关卡未变化，沿用上一阶段区域：{station}")

                if station == "未知":
                    for retry in range(3):
                        time.sleep(1)
                        retry_stage_text = auto.get_single_line_text(crop=stage_crop)
                        if not retry_stage_text:
                            continue

                        retry_stage_match = re.search(stage_pattern, retry_stage_text)
                        if not retry_stage_match:
                            continue

                        _, _, _, retry_station = retry_stage_match.groups()
                        retry_station = normalize_station(retry_station)
                        if retry_station != "未知":
                            station = retry_station
                            log.debug(f"区域识别重试成功（第 {retry + 1} 次）：{station}")
                            break

            new_stage = f"{current}/{total}|第{plane}位面|{station}"
            if new_stage != self.current_stage:
                self.stage_finish = False
                self.current_stage = new_stage
                log.hr(f"当前阶段 {current}/{total}，第{plane}位面，区域：{station}", 2)
                if "首领" in station or "战斗" in station or "精英" in station or "转化" in station:
                    self.process_battle_stage()
                elif "空白" in station or "休整" in station or "商店" in station or "财富" in station:
                    auto.press_mouse()
                    time.sleep(2)
                    for _ in range(100):
                        if self.check_click_close() or self.check_title():
                            time.sleep(2)
                        else:
                            break
                    auto.press_key("w", 2)
                    self.process_battle_stage_finish()
                elif "事件" in station or "异常" in station or "奖励" in station or "铸造" in station:
                    self.process_event_stage()
                else:
                    log.info("检测到暂不支持的区域类型")
                    self.unsupported_area = True
                    if "冒险" in station:
                        time.sleep(5)
                        if self.check_click_close():
                            log.info("检测到冒险区域且存在教学弹窗，尝试关闭")
                            time.sleep(2)
                            for _ in range(10):
                                if not auto.click_element("关闭", "text", crop=(926 / 1920, 869 / 1080, 65 / 1920, 38 / 1080)):
                                    auto.click_element((1811 / 1920, 461 / 1080, 70 / 1920, 94 / 1080), "crop")
                                    time.sleep(2)
                                else:
                                    time.sleep(2)
                                    break
                            else:
                                if not auto.find_element("./assets/images/screen/divergent_universe/stage.png", "image", 0.9, crop=(33 / 1920, 52 / 1080, 68 / 1920, 60 / 1080)):
                                    log.error("多次尝试关闭冒险教学弹窗失败")
                                    raise Exception("多次尝试关闭冒险教学弹窗失败")
                    self.process_leave()

            elif self.stage_finish:
                # 选中特定 “惊世奇迹” 例如 “财猫面具·破” 以后，存在 bug，虽然不计算区域进度，但是左上角的区域类型不会变化
                # 此时只需要暂离，重新进入，左上角就会显示正确的区域类型
                # 火箭喷射信标也有类似效果
                log.info("发现阶段完成但区域未变化，可能存在区域类型显示错误")
                self.process_re_enter()
                # 避免区域相同 反复重进
                self.current_stage = ""  # 重置当前关卡阶段

            elif self.process_stage:
                if "首领" in station or "战斗" in station or "精英" in station or "转化" in station:
                    self.process_battle_stage_finish()
                if "事件" in station or "异常" in station or "奖励" in station or "铸造" in station:
                    self.process_battle_stage_finish()
            return

    def detect_events(self):
        """使用YOLO检测所有事件目标。"""
        return auto.find_element(
            target={"model_path": "./assets/model/divergent.onnx", "names": ["door", "event"], "target_class": "event"},
            find_type="yolo_with_multiple_targets",
            threshold=0.2
        )

    def find_closest_event(self, events, screen_center_x):
        """从事件列表中找到距离屏幕中心最近的事件。"""
        if not events:
            return None
        closest = None
        min_dist = float('inf')
        for top_left, bottom_right in events:
            center_x = (top_left[0] + bottom_right[0]) // 2
            dist = abs(center_x - screen_center_x)
            if dist < min_dist:
                min_dist = dist
                closest = (top_left, bottom_right)
        return closest

    def calculate_area(self, top_left, bottom_right):
        """根据左上角和右下角坐标计算区域面积。"""
        width = max(0, bottom_right[0] - top_left[0])
        height = max(0, bottom_right[1] - top_left[1])
        return width * height

    def process_event_stage(self):
        stable_mode = cfg.cloud_game_enable or cfg.weekly_divergent_stable_mode
        window = Screenshot.get_window(cfg.game_title_name)
        win_x, _, width, _ = Screenshot.get_window_region(window)
        screen_center_x = win_x + width // 2
        tolerance = width // 12
        fine_tolerance = width // 15
        f_crop = (1078 / 1920, 595 / 1080, 37 / 1920, 37 / 1080)

        event_count = 0
        timeout_retries = 0

        while event_count < 5:
            log.info(f"事件处理第 {event_count + 1}/5 轮（超时重试 {timeout_retries}/3）")

            # 检测所有事件
            time.sleep(4)
            events = self.detect_events()
            if not events:
                log.info("未检测到任何事件，尝试向前移动后重试")
                auto.press_key("w", 1)
                events = self.detect_events()
                if not events:
                    log.info("未检测到任何事件，尝试向前移动后重试")
                    auto.press_key("w", 1)
                    events = self.detect_events()
                    if not events:
                        log.info("未检测到任何事件，事件处理完成")
                        self.process_stage = True
                        return

            event_length = len(events)
            log.info(f"检测到 {event_length} 个事件")

            # 找到距离屏幕中心最近的事件
            closest = self.find_closest_event(events, screen_center_x)
            top_left, bottom_right = closest
            event_center_x = (top_left[0] + bottom_right[0]) // 2

            # 左右移动，将事件对齐到屏幕中心
            if abs(event_center_x - screen_center_x) > tolerance:
                key = "a" if event_center_x < screen_center_x else "d"
                log.debug(f"事件在屏幕{'左边' if key == 'a' else '右边'}，正在调整位置")
                if stable_mode:
                    start_time = time.monotonic()
                    while time.monotonic() - start_time < 10:
                        auto.press_key(key, wait_time=0.15)
                        events = self.detect_events()
                        if not events:
                            break
                        closest = self.find_closest_event(events, screen_center_x)
                        if not closest:
                            break
                        top_left, bottom_right = closest
                        event_center_x = (top_left[0] + bottom_right[0]) // 2
                        if abs(event_center_x - screen_center_x) <= tolerance:
                            log.debug("事件已调整到屏幕中间")
                            break
                else:
                    auto.press_key_down(key)
                    try:
                        start_time = time.monotonic()
                        while time.monotonic() - start_time < 10:
                            time.sleep(0.1)
                            events = self.detect_events()
                            if not events:
                                break
                            closest = self.find_closest_event(events, screen_center_x)
                            if not closest:
                                break
                            top_left, bottom_right = closest
                            event_center_x = (top_left[0] + bottom_right[0]) // 2
                            if abs(event_center_x - screen_center_x) <= tolerance:
                                log.debug("事件已调整到屏幕中间")
                                break
                    finally:
                        auto.press_key_up(key)
            else:
                log.debug("事件已在屏幕中间")

            # 向事件走去，边走边检测F图标和事件位置
            event_interacted = False

            timeout = 60 if stable_mode else 15
            area_growth_ratio = 1.08

            if not stable_mode:
                auto.press_key_down("w")

            area_window_start_time = time.monotonic()
            area_window_start_value = None
            area_window_latest_value = None
            has_f_or_adjusted_in_window = False

            try:
                start_time = time.monotonic()
                while time.monotonic() - start_time < timeout:
                    # 检测F交互图标
                    if auto.find_element("./assets/images/screen/divergent_universe/f.png", "image", 0.9, crop=f_crop):
                        has_f_or_adjusted_in_window = True
                        log.debug("检测到F交互图标")
                        if not stable_mode:
                            auto.press_key_up("w")
                        if auto.find_element("事件", "text", crop=(1205 / 1920, 589 / 1080, 193 / 1920, 49 / 1080), include=True):
                            auto.press_key("f")
                            time.sleep(2)
                            event_start_time = time.monotonic()
                            # for _ in range(100):
                            while time.monotonic() - event_start_time < 30 * 60:  # 最多等待30分钟 应该不会有人战斗能打半小时吧
                                if self.check_click_close() or self.check_title() or self.check_auto_battle():
                                    time.sleep(2)
                                elif auto.find_element("./assets/images/screen/divergent_universe/stage.png", "image", 0.9, crop=(33 / 1920, 52 / 1080, 68 / 1920, 60 / 1080)):
                                    break
                                else:
                                    time.sleep(2)
                            event_interacted = True
                            break
                        else:
                            if not stable_mode:
                                auto.press_key_down("w")
                            time.sleep(0.5)

                    # 细微调整方向
                    events = self.detect_events()
                    if events:
                        closest = self.find_closest_event(events, screen_center_x)
                        if closest:
                            top_left, bottom_right = closest
                            current_area = self.calculate_area(top_left, bottom_right)
                            area_window_latest_value = current_area
                            if area_window_start_value is None:
                                area_window_start_value = current_area

                            event_center_x = (top_left[0] + bottom_right[0]) // 2
                            offset = event_center_x - screen_center_x
                            if abs(offset) > fine_tolerance:
                                adjust_key = "a" if offset < 0 else "d"
                                # has_f_or_adjusted_in_window = True
                                if stable_mode:
                                    auto.press_key_down("w")
                                auto.press_key(adjust_key, wait_time=0.15)
                                if stable_mode:
                                    auto.press_key_up("w")
                            else:
                                if stable_mode:
                                    auto.press_key("w")
                    else:
                        if timeout_retries > 1 and self.detect_random_door:
                            has_f_or_adjusted_in_window = True
                            # 可能将随意门识别成事件了，尝试一次直接找门
                            if self.process_random_door():
                                log.info("中断事件处理，已检测到随意门并成功进入")
                                return

                    if not stable_mode and time.monotonic() - area_window_start_time >= 2:
                        area_growth_ok = (
                            area_window_start_value is not None
                            and area_window_latest_value is not None
                            and area_window_latest_value >= area_window_start_value * area_growth_ratio
                        )
                        log.debug(
                            f"事件区域面积增长检测 - 起始值: {area_window_start_value}, 最新值: {area_window_latest_value}, 增长率: {area_window_latest_value / area_window_start_value if area_window_start_value else 'N/A'}, 是否满足增长条件: {area_growth_ok}")

                        if (not has_f_or_adjusted_in_window) and (not area_growth_ok):
                            log.info("可能遇到可破坏物遮挡，尝试攻击")
                            auto.press_key_up("w")
                            auto.press_mouse()
                            time.sleep(2)
                            has_interaction = False
                            for _ in range(100):
                                if self.check_click_close() or self.check_title():
                                    has_interaction = True
                                    time.sleep(2)
                                else:
                                    break
                            if has_interaction:
                                start_time = time.monotonic()
                            else:
                                start_time += 2

                            auto.press_key_down("w")

                        area_window_start_time = time.monotonic()
                        area_window_start_value = area_window_latest_value
                        has_f_or_adjusted_in_window = False

            finally:
                if not stable_mode:
                    auto.press_key_up("w")

            if event_interacted:
                # 事件交互后视角会变化，且不容易判断是否还有其他事件
                # 重进关卡是最简单粗暴的解决办法，能大大提高稳定性
                log.info("事件交互成功")

                # 如果只有一个事件且检测到了随意门，在非稳定模式下快速的尝试一下直接去找门
                if not stable_mode and event_length == 1:
                    time.sleep(2)  # 事件卡消失要一定时间
                    if self.detect_random_door and self.process_random_door(timeout=10):
                        log.info("中断事件处理，已检测到随意门并成功进入")
                        return

                self.process_re_enter()
                event_count += 1
                timeout_retries = 0
            else:
                timeout_retries += 1
                if timeout_retries >= 3:
                    log.info("事件连续超时3次，尝试离开关卡")
                    self.process_leave()
                    return
                log.info(f"事件超时（第 {timeout_retries}/3 次），重新进入关卡重试")

                if auto.find_element("./assets/images/share/base/F.png", "image", 0.9, crop=(998.0 / 1920, 473.0 / 1080, 392.0 / 1920, 296.0 / 1080)) and auto.find_element(("战利品", "混沌药箱"), "text", crop=(1205 / 1920, 589 / 1080, 193 / 1920, 49 / 1080), include=True):
                    log.info(f"检测到{auto.matched_text}，尝试点击")
                    auto.press_key("f")
                    time.sleep(2)
                    for _ in range(100):
                        if self.check_click_close() or self.check_title():
                            time.sleep(2)
                        else:
                            break

                time.sleep(1)
                auto.press_mouse()
                time.sleep(2)
                for _ in range(100):
                    if self.check_click_close() or self.check_title():
                        time.sleep(2)
                    else:
                        break

                self.process_re_enter()

        log.info("事件处理超过5轮，尝试离开关卡")
        self.process_leave()

    def process_battle_stage(self):
        for _ in range(3):
            time.sleep(2)
            enemy_crop = (675 / 1920, 41 / 1080, 274 / 1920, 37 / 1080)
            auto.press_key_down("w")
            time.sleep(0.2)
            if not cfg.cloud_game_enable and not cfg.weekly_divergent_stable_mode:
                auto.press_key_down("shift")
            start_time = time.monotonic()
            while time.monotonic() - start_time < 3:  # 最多等待3秒
                if auto.find_element("./assets/images/screen/divergent_universe/enemy.png", "image", 0.9, crop=enemy_crop):
                    log.info("检测到敌对目标")
                    break
            else:
                log.info("未检测到敌对目标")
            time.sleep(0.8)
            if cfg.cloud_game_enable or cfg.weekly_divergent_stable_mode:
                time.sleep(0.5)
            auto.press_key_up("w")
            if not cfg.cloud_game_enable and not cfg.weekly_divergent_stable_mode:
                auto.press_key_up("shift")

            if auto.find_element("./assets/images/share/base/F.png", "image", 0.9, crop=(998.0 / 1920, 473.0 / 1080, 392.0 / 1920, 296.0 / 1080)) and auto.find_element(("战利品", "混沌药箱"), "text", crop=(1205 / 1920, 589 / 1080, 193 / 1920, 49 / 1080), include=True):
                log.info(f"检测到{auto.matched_text}，尝试点击")
                auto.press_key("f")
                time.sleep(2)
                for _ in range(100):
                    if self.check_click_close() or self.check_title():
                        time.sleep(2)
                    else:
                        break
                self.process_re_enter()
                continue

            log.info("尝试进入战斗")
            for _ in range(5):
                auto.press_mouse()
                time.sleep(0.5)
                if not auto.find_element("./assets/images/screen/divergent_universe/stage.png", "image", 0.9, crop=(33 / 1920, 52 / 1080, 68 / 1920, 60 / 1080)):
                    break
            for _ in range(100):
                if self.check_click_close() or self.check_title():
                    time.sleep(2)
                else:
                    break

            # 进入战斗失败，尝试重新进入
            if auto.find_element("./assets/images/screen/divergent_universe/stage.png", "image", 0.9, crop=(33 / 1920, 52 / 1080, 68 / 1920, 60 / 1080)):
                auto.press_key("s")
                log.info("尝试进入战斗")
                for _ in range(5):
                    auto.press_mouse()
                    time.sleep(0.5)
                    if not auto.find_element("./assets/images/screen/divergent_universe/stage.png", "image", 0.9, crop=(33 / 1920, 52 / 1080, 68 / 1920, 60 / 1080)):
                        break
                for _ in range(100):
                    if self.check_click_close() or self.check_title():
                        time.sleep(2)
                    else:
                        break
                if auto.find_element("./assets/images/screen/divergent_universe/stage.png", "image", 0.9, crop=(33 / 1920, 52 / 1080, 68 / 1920, 60 / 1080)):
                    self.process_re_enter()
                    continue
            else:
                self.process_stage = True
                return
        log.info("多次尝试进入战斗失败")
        self.process_stage = True

    def process_battle_stage_finish(self):
        time.sleep(2)
        self.process_stage = False

        if auto.find_element("./assets/images/share/base/F.png", "image", 0.9, crop=(998.0 / 1920, 473.0 / 1080, 392.0 / 1920, 296.0 / 1080)) and auto.find_element(("战利品", "混沌药箱"), "text", crop=(1205 / 1920, 589 / 1080, 193 / 1920, 49 / 1080), include=True):
            log.info(f"检测到{auto.matched_text}，尝试点击")
            auto.press_key("f")
            time.sleep(2)
            for _ in range(100):
                if self.check_click_close() or self.check_title():
                    time.sleep(2)
                else:
                    break

        if self.process_random_door():
            return

        if auto.find_element("./assets/images/share/base/F.png", "image", 0.9, crop=(998.0 / 1920, 473.0 / 1080, 392.0 / 1920, 296.0 / 1080)) and auto.find_element(("战利品", "混沌药箱"), "text", crop=(1205 / 1920, 589 / 1080, 193 / 1920, 49 / 1080), include=True):
            log.info(f"检测到{auto.matched_text}，尝试点击")
            auto.press_key("f")
            time.sleep(2)
            for _ in range(100):
                if self.check_click_close() or self.check_title():
                    time.sleep(2)
                else:
                    break
            self.process_re_enter()
            if self.process_random_door():
                return

        auto.press_mouse()
        time.sleep(2)
        for _ in range(100):
            if self.check_click_close() or self.check_title():
                time.sleep(2)
            else:
                break

        if self.process_random_door():
            return

        auto.press_key("a", 0.5)
        time.sleep(0.2)
        auto.press_key("w", 0.5)
        if self.process_random_door():
            return

        auto.press_mouse()
        time.sleep(2)
        for _ in range(100):
            if self.check_click_close() or self.check_title():
                time.sleep(2)
            else:
                break
        self.process_re_enter()
        auto.press_key("w", 2)
        if self.process_random_door():
            return

        auto.press_key("d", 0.5)
        time.sleep(0.2)
        auto.press_key("w", 1)
        time.sleep(0.2)
        auto.press_key("a", 0.5)
        if self.process_random_door():
            return

        auto.press_mouse()
        time.sleep(2)
        for _ in range(100):
            if self.check_click_close() or self.check_title():
                time.sleep(2)
            else:
                break
        self.process_re_enter()
        auto.press_key("w", 2)
        if self.process_random_door(stable_mode=True):
            return

        auto.press_key("a", 0.5)
        time.sleep(0.2)
        auto.press_key("w", 0.5)
        if self.process_random_door(stable_mode=True):
            return

        auto.press_key("d", 0.5)
        time.sleep(0.2)
        auto.press_key("w", 1)
        time.sleep(0.2)
        auto.press_key("a", 0.5)
        if self.process_random_door(stable_mode=True):
            return

        self.process_leave()

    def process_leave(self):
        log.info("尝试离开当前关卡")
        auto.press_key("esc")
        if auto.click_element("结束并结算", "text", max_retries=10, crop=(1238 / 1920, 859 / 1080, 562 / 1920, 165 / 1080)):
            auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10)
        else:
            self.stage_finish = True

    def process_re_enter(self):
        log.info("尝试重新进入当前关卡")
        for _ in range(3):
            auto.press_key("esc")
            if auto.click_element("暂离", "text", max_retries=10, crop=(1238 / 1920, 859 / 1080, 562 / 1920, 165 / 1080)):
                screen.wait_for_screen_change("main")
                if auto.find_element("./assets/images/share/base/F.png", "image", 0.9, crop=(998.0 / 1920, 473.0 / 1080, 392.0 / 1920, 296.0 / 1080)):
                    auto.press_key("f")
                    screen.wait_for_screen_change('divergent_main')
                screen.change_to("divergent_mode_select")
                if auto.click_element("继续进度", "text", crop=(39 / 1920, 215 / 1080, 748 / 1920, 597 / 1080)):
                    if not auto.find_element("./assets/images/screen/divergent_universe/stage.png", "image", 0.9, max_retries=120, crop=(33 / 1920, 52 / 1080, 68 / 1920, 60 / 1080)):
                        raise Exception("重新进入关卡失败")
                    return
                else:
                    raise Exception("未找到继续进度按钮")
        log.error("多次尝试重新进入关卡失败")

    def detect_random_door(self):
        return auto.find_element(
            target={"model_path": "./assets/model/divergent.onnx", "names": ["door", "event"], "target_class": "door"},
            find_type="yolo",
            threshold=0.01
        )
        # LOWER = np.array([112, 82, 174])
        # UPPER = np.array([170, 126, 239])
        # crop = (68 / 1920, 4 / 1080, 1718 / 1920, 818 / 1080)
        # return auto.find_element((LOWER, UPPER), "hsv", crop=crop)
        LOWER = np.array([129, 57, 143])
        UPPER = np.array([174, 163, 229])
        remove_crop = (1494 / 1920, 0 / 1080, 424 / 1920, 268 / 1080)
        auto.fill_crop_with_color(remove_crop, (0, 0, 0))
        return auto.find_element((LOWER, UPPER), "hsv", take_screenshot=False)

    def process_random_door(self, stable_mode=False, timeout=15):
        if cfg.cloud_game_enable or cfg.weekly_divergent_stable_mode:
            stable_mode = True
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

            if stable_mode:
                start_time = time.monotonic()
                while time.monotonic() - start_time < 10:
                    auto.press_key(key, wait_time=0.15)
                    result = self.detect_random_door()
                    if not result:
                        return False
                    top_left, bottom_right = result
                    door_center_x = (top_left[0] + bottom_right[0]) // 2
                    if abs(door_center_x - screen_center_x) <= tolerance:
                        log.debug("随意门已调整到屏幕中间")
                        break
            else:
                auto.press_key_down(key)
                try:
                    start_time = time.monotonic()
                    while time.monotonic() - start_time < 10:
                        time.sleep(0.1)
                        result = self.detect_random_door()
                        if not result:
                            return False
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

        if stable_mode:
            fine_tolerance = width // 15
        else:
            fine_tolerance = width // 12  # 屏幕宽度10%作为容差

        if not stable_mode:
            auto.press_key_down("w")
            # time.sleep(0.2)
            # auto.press_key_down("shift")
        # else:
        #     auto.press_key("w", 1.5)

        if stable_mode:
            timeout = 60

        try:
            start_time = time.monotonic()
            # time.sleep(1)
            while time.monotonic() - start_time < timeout:
                # time.sleep(0.1)

                # 检测F交互图标
                if auto.find_element("./assets/images/screen/divergent_universe/f.png", "image", 0.9, crop=f_crop):
                    log.debug("检测到F交互图标")
                    if not stable_mode:
                        auto.press_key_up("w")
                        # auto.press_key_up("shift")

                    if auto.find_element("./assets/images/screen/divergent_universe/door.png", "image", 0.9, crop=door_crop):
                        auto.press_key("f")
                        auto.press_key("f")
                        auto.press_key("f")
                        auto.press_key("f")
                        auto.press_key("f")
                        time.sleep(2)
                        if auto.find_element("./assets/images/screen/divergent_universe/stage.png", "image", 0.9, crop=(33 / 1920, 52 / 1080, 68 / 1920, 60 / 1080)):
                            return False
                        self.stage_finish = True
                        log.info("成功进入随意门")
                        return True
                    else:
                        if not stable_mode:
                            auto.press_key_down("w")
                            # time.sleep(0.2)
                            # auto.press_key_down("shift")
                        # else:
                        #     auto.press_key("w", 1)
                        time.sleep(0.5)

                # 检测随意门位置，细微调整方向
                result = self.detect_random_door()
                if not result:
                    return False
                top_left, bottom_right = result
                door_center_x = (top_left[0] + bottom_right[0]) // 2
                offset = door_center_x - screen_center_x

                if abs(offset) > fine_tolerance:
                    adjust_key = "a" if offset < 0 else "d"
                    if stable_mode:
                        auto.press_key_down("w")
                    auto.press_key(adjust_key, wait_time=0.15)
                    if stable_mode:
                        auto.press_key_up("w")
                else:
                    if stable_mode:
                        auto.press_key("w")
        finally:
            if not stable_mode:
                auto.press_key_up("w")
                # auto.press_key_up("shift")
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
        mask_crop = (396 / 1920, 519 / 1080, 172 / 1920, 485 / 1080)
        mask_positions = [
            (408 / 1920, 529 / 1080, 147 / 1920, 48 / 1080),
            (411 / 1920, 713 / 1080, 144 / 1920, 50 / 1080),
            (413 / 1920, 900 / 1080, 142 / 1920, 51 / 1080),
        ]
        mask_names = []
        if auto.click_element(("选择一张面具", "确定"), 'text'):
            if auto.matched_text == "选择一张面具":
                if auto.find_element("面具", "text", crop=mask_crop, include=True):
                    for box in auto.ocr_result:
                        text = box[1][0]
                        if text.endswith("面具") and len(text) > 2:
                            log.info(f"检测到面具：{text}")
                            mask_names.append(text)
                    if any(mask_names):
                        for name in mask_names:
                            log.info(f"尝试选择面具：{name}")
                            if auto.click_element(name, "text", crop=mask_crop, include=True):
                                time.sleep(2)
                                return

                # for i, pos in enumerate(mask_positions):
                #     result = auto.get_single_line_text(crop=pos)
                #     if result and result.endswith("面具") and len(result) > 2:
                #         log.info(f"检测到第 {i + 1} 张面具：{result}")
                #         has_mask[i] = True

                # if any(has_mask):
                #     for i, has in enumerate(has_mask):
                #         if has:
                #             log.info(f"尝试选择第 {i + 1} 张面具")
                #             auto.click_element(mask_positions[i], 'crop')
                #             time.sleep(2)
                #             return

                log.info("默认选择中间的面具")
                auto.click_element(mask_positions[1], 'crop')
                time.sleep(2)

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
        # if auto.click_element(("繁育", "巡猎"), "text", 0.9, crop=(274 / 1920, 790 / 1080, 1371 / 1920, 59 / 1080), include=True):
        #     log.info(f"检测到“{auto.matched_text}”选项，尝试点击")
        #     has_choose = True

        # if not has_choose:
        #     if auto.click_element(("欢愉", "智识"), "text", 0.9, crop=(274 / 1920, 790 / 1080, 1371 / 1920, 59 / 1080), include=True):
        #         log.info(f"检测到“{auto.matched_text}”选项，尝试点击")
        #         has_choose = True

        if not has_choose:
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
        # if auto.click_element(("繁育", "巡猎"), "text", 0.9, crop=(274 / 1920, 790 / 1080, 1371 / 1920, 59 / 1080), include=True):
        #     log.info(f"检测到“{auto.matched_text}”选项，尝试点击")
        #     has_choose = True

        # if not has_choose:
        #     if auto.click_element(("欢愉", "智识"), "text", 0.9, crop=(274 / 1920, 790 / 1080, 1371 / 1920, 59 / 1080), include=True):
        #         log.info(f"检测到“{auto.matched_text}”选项，尝试点击")
        #         has_choose = True

        if not has_choose:
            for pos in blessing_positions:
                if auto.click_element("./assets/images/screen/divergent_universe/new_blessing.png", "image", 0.9, crop=pos,):
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
        relic2_positions = [
            (517 / 1920, 242 / 1080, 409 / 1920, 610 / 1080),
            (997 / 1920, 241 / 1080, 405 / 1920, 609 / 1080)
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
            auto.click_element(relic2_positions[0], 'crop')
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
        relic2_positions = [
            (517 / 1920, 242 / 1080, 409 / 1920, 610 / 1080),
            (997 / 1920, 241 / 1080, 405 / 1920, 609 / 1080)
        ]

        log.info("尝试丢弃中间的奇物")
        auto.click_element(relic2_positions[0], 'crop')
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
        station2_positions = [
            (439 / 1920, 432 / 1080, 252 / 1920, 407 / 1080),
            (702 / 1920, 433 / 1080, 253 / 1920, 406 / 1080),
            (965 / 1920, 431 / 1080, 251 / 1920, 404 / 1080),
            (1227 / 1920, 432 / 1080, 253 / 1920, 402 / 1080),
        ]
        re_extract_crop = (560 / 1920, 940 / 1080, 374 / 1920, 56 / 1080)

        for _ in range(5):
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
                "休整": 0,
                "转化": 0,
            }
            disabled_stations = set()

            if cfg.divergent_station_priority_enable:
                custom_priority = cfg.divergent_station_priority
                for name, prio in custom_priority.items():
                    priority_map[name] = prio
                disabled_stations = set(cfg.divergent_station_disabled)
            else:
                priority_map.update({
                    "战斗": 1,
                    "精英": 1,
                    "事件": 2,
                    "奖励": 2,
                    "异常": 2,
                    "铸造": 2,
                    "空白": 3,
                    "商店": 3,
                    "财富": 3,
                })

            # 获取每个站点的优先级，None 的优先级设为最低（优先级最高）
            # 禁用的站点优先级设为极高值（仅在没有重抽次数时才会被选择）
            station_priorities = []
            for tag in station_tags:
                if tag is None:
                    station_priorities.append(float('inf'))
                elif tag in disabled_stations:
                    station_priorities.append(99)
                else:
                    if tag in priority_map:
                        has_priority_station = True
                    station_priorities.append(priority_map.get(tag, 100))

            if not has_priority_station:
                if not auto.find_element("重抽0", "text", crop=re_extract_crop) and not auto.find_element("0", "text", crop=re_extract_crop):
                    auto.click_element(re_extract_crop, 'crop')
                    time.sleep(0.5)
                    if auto.find_element("当前无法重抽", "text", crop=(880 / 1920, 282 / 1080, 157 / 1920, 38 / 1080)):
                        break
                    time.sleep(1)
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
            auto.click_element(("冒险", "铸造"), "text", crop=(59 / 1920, 243 / 1080, 1262 / 1920, 786 / 1080), include=True)
        auto.click_element('确定', 'text', None, 10, crop=(1589 / 1920, 919 / 1080, 73 / 1920, 38 / 1080), include=True)
        time.sleep(2)

    def process_save_management(self):
        time.sleep(2)

    def process_chaos_box(self):
        time.sleep(2)
        if not auto.click_element('获得', 'text', None, 10, crop=(1105 / 1920, 94 / 1080, 702 / 1920, 858 / 1080), include=True):
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
        检查并点击 “点击空白处关闭” 或 “点击领取今日补给” 的按钮
        """
        if auto.click_element(("点击空白处关闭", "点击领取今日补给"), 'text', None, crop=(816 / 1920, 778 / 1080, 284 / 1920, 298 / 1080), include=True):
            log.info(f"检测到 “{auto.matched_text}” 的按钮，尝试点击")
            return True
        return False

    def check_click_return(self):
        """
        检查并点击 “终止战斗并结算” 和 “返回主界面” 的按钮
        """
        if result := auto.find_element(("终止战斗并结算", "返回主界面", "确认结算"), 'text', None, crop=(573 / 1920, 947 / 1080, 792 / 1920, 85 / 1080), include=True):

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
                time.sleep(2)
                auto.click_element_with_pos(result)
                if self.result is not None:
                    log.info(f"本次对局结果：{'成功' if self.result else '失败'}")
                else:
                    log.info("本次对局结果：未知")
                self.end_loop = True

                time.sleep(2)
                for _ in range(30):
                    if auto.click_element("返回主界面", 'text', None, crop=(573 / 1920, 947 / 1080, 792 / 1920, 85 / 1080), include=True):
                        log.info(f"检测到 “返回主界面” 的按钮，尝试点击")
                        time.sleep(2)
                    else:
                        break
                else:
                    log.warning("多次点击返回主界面失败，请确认是否已成功返回主界面")

                # 没有存档会显示一个弹窗，需要点击确认
                auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9)

            elif auto.matched_text == "确认结算":
                log.info(f"检测到 “确认结算” 的按钮，尝试点击")
                auto.click_element_with_pos(result)
                return True

        return False

    def _check_battle_result(self):
        """
        检查并记录对局结果
        """
        time.sleep(2)  # 等待分析报告加载完成后再截图
        if auto.find_element(("探索成功", "探索中断"), 'text', include=True):
            if auto.matched_text == "探索成功":
                self.result = True
                self.screenshot = auto.screenshot
                return
            elif auto.matched_text == "探索中断":
                self.result = False
                self.screenshot = auto.screenshot
                return
