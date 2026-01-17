from module.screen import screen
from module.automation import auto
from module.config import cfg
from module.logger import log
from module.notification.notification import NotificationLevel
from tasks.base.base import Base
from utils.date import Date
from typing import Literal, Tuple, Optional
import numpy as np
import time
import os
import re


class CurrencyWarsCharacter:
    def __init__(self, name: Optional[str], pos: Literal["forward", "backward", "all", None] = "None", level: int = 1, money: int = 1):
        self.name = name  # 角色名称
        self.pos = pos  # 角色站位
        self.level = level  # 角色等级
        self.money = money  # 角色投资金额


class CurrencyWars:
    def __init__(self):
        self.screenshot = None  # 任务截图
        self.peipei_count: int = 0  # 佩佩和叽米
        self.diamond_count: int = 0  # 财富宝钻
        self.current_level: int = 0  # 当前可部署角色等级
        self.current_stage: str = "0-0"  # 当前关卡阶段
        self.result: Optional[bool] = None  # 对局结果
        self.need_exit: bool = False  # 是否需要退出
        self.forward_characters: list[CurrencyWarsCharacter] = []  # 存储前台角色
        self.backward_characters: list[CurrencyWarsCharacter] = []  # 存储后台角色
        self.prepare_characters: list[CurrencyWarsCharacter] = []  # 存储备战席角色
        self.zone_name_localization = {
            "forward": "前台",
            "backward": "后台",
            "prepare": "备战席"
        }
        self.pos_name_localization = {
            "forward": "前台",
            "backward": "后台",
            "all": "前后台"
        }
        self.character_info_cache: dict[str, CurrencyWarsCharacter] = {}  # 角色信息缓存,key为角色名

        self.forward_pos = [
            (684.0 / 1920, 324.0 / 1080, 123.0 / 1920, 145.0 / 1080),
            (825.0 / 1920, 328.0 / 1080, 125.0 / 1920, 139.0 / 1080),
            (967.0 / 1920, 326.0 / 1080, 127.0 / 1920, 142.0 / 1080),
            (1109.0 / 1920, 327.0 / 1080, 129.0 / 1920, 140.0 / 1080)
        ]

        self.backward_pos_6 = [
            (543.0 / 1920, 594.0 / 1080, 124.0 / 1920, 148.0 / 1080),
            (686.0 / 1920, 594.0 / 1080, 125.0 / 1920, 147.0 / 1080),
            (824.0 / 1920, 598.0 / 1080, 127.0 / 1920, 141.0 / 1080),
            (967.0 / 1920, 598.0 / 1080, 128.0 / 1920, 141.0 / 1080),
            (1105.0 / 1920, 599.0 / 1080, 134.0 / 1920, 140.0 / 1080),
            (1246.0 / 1920, 598.0 / 1080, 139.0 / 1920, 140.0 / 1080)
        ]
        self.backward_pos_7 = [
            (482.0 / 1920, 601.0 / 1080, 109.0 / 1920, 135.0 / 1080),
            (619.0 / 1920, 600.0 / 1080, 116.0 / 1920, 137.0 / 1080),
            (759.0 / 1920, 601.0 / 1080, 120.0 / 1920, 137.0 / 1080),
            (896.0 / 1920, 600.0 / 1080, 126.0 / 1920, 138.0 / 1080),
            (1037.0 / 1920, 601.0 / 1080, 131.0 / 1920, 138.0 / 1080),
            (1175.0 / 1920, 600.0 / 1080, 137.0 / 1920, 138.0 / 1080),
            (1314.0 / 1920, 600.0 / 1080, 138.0 / 1920, 134.0 / 1080)
        ]
        self.backward_pos_8 = [
            (400.0 / 1920, 596.0 / 1080, 121.0 / 1920, 140.0 / 1080),
            (549.0 / 1920, 600.0 / 1080, 114.0 / 1920, 136.0 / 1080),
            (690.0 / 1920, 601.0 / 1080, 115.0 / 1920, 133.0 / 1080),
            (830.0 / 1920, 601.0 / 1080, 118.0 / 1920, 133.0 / 1080),
            (972.0 / 1920, 602.0 / 1080, 120.0 / 1920, 133.0 / 1080),
            (1107.0 / 1920, 601.0 / 1080, 130.0 / 1920, 136.0 / 1080),
            (1244.0 / 1920, 600.0 / 1080, 142.0 / 1920, 138.0 / 1080),
            (1389.0 / 1920, 601.0 / 1080, 135.0 / 1920, 135.0 / 1080)
        ]
        self.backward_pos_9 = [
            (347.0 / 1920, 605.0 / 1080, 94.0 / 1920, 126.0 / 1080),
            (485.0 / 1920, 605.0 / 1080, 103.0 / 1920, 128.0 / 1080),
            (625.0 / 1920, 606.0 / 1080, 103.0 / 1920, 124.0 / 1080),
            (763.0 / 1920, 606.0 / 1080, 111.0 / 1920, 126.0 / 1080),
            (903.0 / 1920, 607.0 / 1080, 116.0 / 1920, 124.0 / 1080),
            (1038.0 / 1920, 600.0 / 1080, 131.0 / 1920, 139.0 / 1080),
            (1178.0 / 1920, 604.0 / 1080, 132.0 / 1920, 131.0 / 1080),
            (1318.0 / 1920, 602.0 / 1080, 135.0 / 1920, 131.0 / 1080),
            (1455.0 / 1920, 599.0 / 1080, 146.0 / 1920, 137.0 / 1080)
        ]
        self.backward_pos = None

        self.prepare_pos = [
            (382.0 / 1920, 846.0 / 1080, 115.0 / 1920, 134.0 / 1080),
            (508.0 / 1920, 844.0 / 1080, 113.0 / 1920, 137.0 / 1080),
            (631.0 / 1920, 845.0 / 1080, 117.0 / 1920, 137.0 / 1080),
            (755.0 / 1920, 844.0 / 1080, 119.0 / 1920, 137.0 / 1080),
            (880.0 / 1920, 844.0 / 1080, 116.0 / 1920, 136.0 / 1080),
            (1004.0 / 1920, 844.0 / 1080, 118.0 / 1920, 137.0 / 1080),
            (1129.0 / 1920, 843.0 / 1080, 119.0 / 1920, 135.0 / 1080),
            (1254.0 / 1920, 842.0 / 1080, 118.0 / 1920, 138.0 / 1080),
            (1377.0 / 1920, 842.0 / 1080, 119.0 / 1920, 138.0 / 1080)
        ]

    def start(self):
        log.hr('准备货币战争', '0')
        if self.run():
            Base.send_notification_with_screenshot("货币战争已完成", NotificationLevel.ALL, self.screenshot)
            self.screenshot = None
        else:
            Base.send_notification_with_screenshot("货币战争未完成", NotificationLevel.ERROR, self.screenshot)
            self.screenshot = None
        has_reward = self.get_reward()
        if Date.is_next_mon_x_am(cfg.currencywars_timestamp, cfg.refresh_hour):
            self.check_currency_wars_score()
        if has_reward and cfg.currencywars_bonus_enable:
            self.process_ornament()
        log.hr("完成", 2)

    def check_currency_wars_score(self) -> bool:
        """
        检查货币战争积分，达到 18000 时记录时间戳
        """
        screen.wait_for_screen_change("currency_wars_homepage")
        score_pos = (217.0 / 1920, 977.0 / 1080, 196.0 / 1920, 40.0 / 1080)
        score = auto.get_single_line_text(score_pos)
        if not score:
            log.warning("未识别到货币战争积分")
            return False

        score_parts = score.split('/')
        if len(score_parts) == 2 and score_parts[0].isdigit() and score_parts[1].isdigit() and score_parts[1] == "18000":
            log.info(f"货币战争积分：{score_parts[0]} / {score_parts[1]}")
            if score_parts[0] == "18000":
                cfg.save_timestamp("currencywars_timestamp")
                log.info("已达到最高积分 18000，记录时间")
                return True
        else:
            log.warning(f"无法解析货币战争积分: {score}")
        return False

    def run(self) -> bool:
        if self.start_war(cfg.currencywars_type):
            return self.loop()
        return False

    def get_reward(self):
        log.info("开始领取奖励")
        if auto.find_element("./assets/images/share/base/RedExclamationMark.png", "image", 0.9, crop=(28.0 / 1920, 880.0 / 1080, 435.0 / 1920, 175.0 / 1080)):
            if auto.click_element("积分", 'text', crop=(28.0 / 1920, 880.0 / 1080, 435.0 / 1920, 175.0 / 1080), include=True):
                if auto.click_element("./assets/images/zh_CN/universe/one_key_receive.png", "image", 0.9, max_retries=10):
                    if auto.find_element("./assets/images/zh_CN/base/click_close.png", "image", 0.8, max_retries=10):
                        time.sleep(2)
                        Base.send_notification_with_screenshot("货币战争奖励已领取", NotificationLevel.ALL)
                        auto.click_element("./assets/images/zh_CN/base/click_close.png", "image", 0.8, max_retries=10)
                        time.sleep(1)
                        auto.press_key("esc")
                        return True
        return False

    def process_ornament(self):
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

        log.hr(f"开始位面饰品快速提取 - {instance_name}", 2)
        screen.change_to("guide3")

        instance_type_crop = (262.0 / 1920, 289.0 / 1080, 422.0 / 1920, 624.0 / 1080)
        if not auto.click_element("饰品提取", "text", crop=instance_type_crop):
            log.info("前往饰品提取失败，结束任务")
            return False
        time.sleep(1)

        extract_crop = (691 / 1920, 285 / 1080, 970 / 1920, 139 / 1080)
        if not auto.click_element("前往提取", "text", crop=extract_crop):
            log.info("前往饰品提取失败，结束任务")
            return False
        time.sleep(1)

        instance_name_crop = (616 / 1920, 418 / 1080, 889 / 1920, 416 / 1080)
        auto.click_element("提取", "text", crop=instance_name_crop, action="move")
        has_found = False
        for i in range(5):
            if auto.click_element(("提取"), "min_distance_text", crop=instance_name_crop, include=True, source=instance_name, source_type="text", position="right"):
                has_found = True
                break
            auto.mouse_scroll(12, -1)
            # 等待界面完全停止
            time.sleep(1)
        if not has_found:
            log.info("未找到指定副本，结束任务")
            auto.press_key("esc")
            return False

        result = auto.find_element("./assets/images/share/power/trailblaze_power/button.png", "image", 0.9, max_retries=10)
        if result:
            auto.click_element_with_pos(result, action="down")
            time.sleep(0.5)
            result = auto.find_element("./assets/images/share/power/trailblaze_power/plus.png", "image", 0.9)
            if result:
                auto.click_element_with_pos(result, action="move")
                time.sleep(0.5)
                auto.mouse_up()
                if auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10):
                    log.info("饰品提取完成，返回主界面")
                    time.sleep(1)
                    auto.press_key("esc")
                    time.sleep(1)
                    auto.press_key("esc")
                    if screen.check_screen("guide3"):
                        return True
            else:
                auto.mouse_up()
        else:
            auto.mouse_up()

        log.info("饰品提取失败，返回主界面")
        time.sleep(1)
        auto.press_key("esc")
        time.sleep(1)
        auto.press_key("esc")
        return False

    def start_war(self, type: Literal["normal", "overclock"] = "normal") -> bool:
        log.info("开始「货币战争」")
        screen.change_to("currency_wars_mode_select")

        if auto.click_element("结束并结算", "text", crop=(1253 / 1920, 915 / 1080, 271 / 1920, 95 / 1080)):
            log.warning("检测到未结算的对局，放弃并结算中")
            if auto.click_element("放弃并结算", "text", max_retries=10, crop=(761 / 1920, 697 / 1080, 399 / 1920, 90 / 1080)):
                self.loop()

        if type == "normal":
            log.info("选择标准博弈")
            screen.change_to("currency_wars_mode_select_normal")
        else:
            log.info("选择超频博弈")
            screen.change_to("currency_wars_mode_select_overclock")

        if not self.choose_level(1):
            log.error("选择关卡失败，结束任务")
            return False

        if not auto.click_element('开始对局', 'text', None, 10):
            log.error("未找到开始对局按钮，结束任务")
            return False

        log.info("开始对局")
        return True

    def choose_level(self, level: int) -> bool:
        """
        选择关卡难度
        """
        log.info("选择关卡")
        # 避免低性能设备加载过慢
        time.sleep(6)  # 等待界面加载
        pos = auto.find_element("./assets/images/screen/currency_wars/level_down.png", "image", 100000)
        for _ in range(40):
            if auto.find_element(f"./assets/images/screen/currency_wars/level_1.png", "image", 0.95, crop=(440.0 / 1920, 892.0 / 1080, 385.0 / 1920, 137.0 / 1080)):
                log.info(f"已选择敌人难度为1的关卡")
                return True
            if pos is None:
                log.error("未找到难度选择按钮，无法选择关卡难度")
                return False
            auto.click_element_with_pos(pos, cnt=10)
        log.error(f"选择敌人难度为1的关卡失败")
        return False

    def loop(self) -> bool:
        """
        货币战争任务主循环
        """
        self.screenshot = None  # 任务截图
        self.result = None  # 重置结果
        self.peipei_count = 0  # 重置佩佩计数
        self.diamond_count = 0  # 重置财富宝钻计数
        self.current_level = 0  # 重置当前可部署角色等级
        self.current_stage = "0-0"  # 重置当前关卡阶段
        self.need_exit = False  # 是否需要退出
        self.forward_characters = []  # 重置前台角色
        self.backward_characters = []  # 重置后台角色
        self.prepare_characters = []  # 重置备战席角色
        self.update_backward()

        start_time = time.monotonic()
        timeout = 60 * 120  # 120分钟超时
        while True:
            # 检查超时
            if time.monotonic() - start_time > timeout:
                log.error("货币战争主循环超时（120分钟），强制退出")
                return False

            try:
                self.check_main_screen()
            except Exception as e:
                log.error(f"货币战争主循环出现异常：{e}，尝试退出")

                # 保存调试截图
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                os.makedirs("./debug", exist_ok=True)
                debug_path = f"./debug/currency_wars_exception_{timestamp}.png"
                auto.take_screenshot()
                auto.screenshot.save(debug_path)
                log.error(f"已保存调试截图至 {debug_path}，请将该截图和日志发送给开发者以便排查问题")

                self.give_up_and_settle()

            self.check_investment_environment()
            self.check_auto_battle()
            self.check_click_continue()
            self.check_supply_phase()
            if self.check_return_home():
                end_time = time.monotonic()
                elapsed_time = end_time - start_time
                minutes = int(elapsed_time // 60)
                seconds = int(elapsed_time % 60)
                log.info(f"本次货币战争用时：{minutes} 分钟 {seconds} 秒")
                return self.result if self.result is not None else False

    def check_main_screen(self):
        """
        检查并处理主界面逻辑
        """
        exit_crop = (3.0 / 1920, 37.0 / 1080, 104.0 / 1920, 57.0 / 1080)
        if auto.find_element("./assets/images/screen/currency_wars/exit.png", "image", 0.9, crop=exit_crop):
            start_time = time.monotonic()
            while time.monotonic() - start_time < 7:
                self.click_origin()
                time.sleep(0.1)
            if auto.find_element("./assets/images/screen/currency_wars/exit.png", "image", 0.9, crop=exit_crop):
                if auto.click_element('收起', 'text', None, 1, crop=(1593.0 / 1920, 959.0 / 1080, 60.0 / 1920, 43.0 / 1080)):
                    time.sleep(2)
                self.check_festival_star_popup()
                if self.need_exit:
                    self.give_up_and_settle()
                    self.need_exit = False
                    return
                self.identify_current_stage()
                self.collect_reward()
                self.check_box()
                self.check_character_status()
                self.buy_experience()
                self.deploy_and_optimize()
                self.sell_characters()
                self.equip_weapons()
                auto.click_element('出战', 'text', None, 10, crop=(1744.0 / 1920, 737.0 / 1080, 165.0 / 1920, 71.0 / 1080))
                time.sleep(2)
                auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9)

    def give_up_and_settle(self):
        """
        放弃并结算：按ESC键并点击放弃并结算按钮
        """
        auto.press_key('esc')
        time.sleep(2)
        auto.click_element('放弃并结算', 'text', include=True)

    def sell_characters(self):
        """
        出售多余角色
        """
        log.info("出售多余角色")
        any_sold = False

        forward_names = set()
        forward_count = 0
        for char in self.forward_characters:
            if char.name:
                forward_names.add(char.name)
                forward_count += 1

        if forward_count == len(self.forward_pos):
            for idx, char in enumerate(self.prepare_characters):
                if char.name and char.pos == "forward" and char.name not in forward_names:
                    log.info(f"出售角色 {char.name}")
                    if self._sell_single_character(idx):
                        # 出售成功，清空该位置的角色信息
                        self.prepare_characters[idx] = CurrencyWarsCharacter(None, None)
                        any_sold = True

        backward_names = set()
        backward_count = 0
        for char in self.backward_characters:
            if char.name:
                backward_names.add(char.name)
                backward_count += 1
        if backward_count == len(self.backward_pos):
            for idx, char in enumerate(self.prepare_characters):
                if char.name and char.pos == "backward" and char.name not in backward_names:
                    log.info(f"出售角色 {char.name}")
                    if self._sell_single_character(idx):
                        # 出售成功，清空该位置的角色信息
                        self.prepare_characters[idx] = CurrencyWarsCharacter(None, None)
                        any_sold = True

        if forward_count == len(self.forward_pos) and backward_count == len(self.backward_pos):
            for idx, char in enumerate(self.prepare_characters):
                if char.name and char.pos == "all" and char.name not in forward_names and char.name not in backward_names:
                    log.info(f"出售角色 {char.name}")
                    if self._sell_single_character(idx):
                        # 出售成功，清空该位置的角色信息
                        self.prepare_characters[idx] = CurrencyWarsCharacter(None, None)
                        any_sold = True

        # 如果有角色出售成功，再执行一次购买经验和部署优化
        if any_sold:
            log.info("检测到角色出售成功，重新执行购买经验和部署优化")
            self.buy_experience()
            self.deploy_and_optimize()

    def _sell_single_character(self, idx: int) -> bool:
        """
        出售单个角色

        参数：
            idx: prepare_characters 中的索引

        返回：
            True 表示出售成功，False 表示出售失败
        """
        position = self.prepare_pos[idx]
        auto.click_element(position, "crop")
        time.sleep(0.5)
        if auto.click_element("出售", "text", crop=(1694.0 / 1920, 896.0 / 1080, 141.0 / 1920, 39.0 / 1080), include=True):
            time.sleep(0.5)
            return True
        self.click_origin()
        return False

    def equip_weapons(self):
        """
        装备武器
        """
        character_groups = [
            (self.forward_characters, self.forward_pos),
            (self.backward_characters, self.backward_pos)
        ]

        for characters, positions in character_groups:
            indexed_chars = [(idx, c) for idx, c in enumerate(characters) if c.name]
            indexed_chars.sort(key=lambda item: (-item[1].money, item[0]))
            for idx, _ in indexed_chars:
                self._equip_single_character(positions[idx])

    def _equip_single_character(self, position):
        """
        为单个角色装备武器
        """
        auto.click_element(position, "crop")
        time.sleep(0.5)
        if auto.click_element("装备推荐", "text", crop=(1403.0 / 1920, 790.0 / 1080, 175.0 / 1920, 57.0 / 1080), include=True):
            time.sleep(0.5)
            while True:
                if auto.click_element(("合成", "穿戴"), "text", crop=(959.0 / 1920, 559.0 / 1080, 420.0 / 1920, 395.0 / 1080), include=True):
                    time.sleep(0.5)
                else:
                    break
        self.click_origin()

    # def buy_characters(self):
    #     """
    #     购买角色
    #     """
    #     pass

    # def check_character_count(self):
    #     """
    #     检查角色数量
    #     """
    #     total_characters = sum(1 for c in self.forward_characters + self.backward_characters + self.prepare_characters if c.name is not None)
    #     return total_characters

    def deploy_and_optimize(self):
        """
        部署并自动调整最优站位：
        - forward/backward 按 money 从高到低填充，遵守 pos 限制
        - forward + backward ≤ limit
        - prepare 放剩余角色
        """

        limit = self.check_character_limit()  # 可部署数量

        # 收集所有角色
        all_chars = []
        for zone in ["forward", "backward", "prepare"]:
            chars = self.__dict__[f"{zone}_characters"]
            pos_list = self.__dict__[f"{zone}_pos"]
            for idx, c in enumerate(chars):
                if c.name:
                    all_chars.append({
                        "c": c,
                        "zone": zone,
                        "idx": idx,
                        "pos_ref": pos_list[idx]
                    })
        # 输出 all_chars
        log.debug("所有角色信息：")
        for item in all_chars:
            log.debug(f"角色 {item['c'].name}: 费用={item['c'].money}, 站位={self.pos_name_localization.get(item['c'].pos, item['c'].pos)}, 区域={self.zone_name_localization[item['zone']]}, 索引={item['idx']}")

        forward_slots = len(self.forward_characters)
        backward_slots = len(self.backward_characters)

        # 先从可前台的角色里选出最多 min(forward_slots, limit) 个：按 money 降序，金额相同 pos 优先级 forward > all，去重按名字
        forward_candidates = [item for item in all_chars if item["c"].pos in ("forward", "all")]
        forward_candidates.sort(key=lambda x: (-x["c"].money, 0 if x["c"].pos == "forward" else 1))
        top_forward: list[dict] = []
        top_forward_names: set[str] = set()
        duplicates_forward: list[dict] = []
        for item in forward_candidates:
            name = item["c"].name
            if name and name not in top_forward_names and len(top_forward) < min(forward_slots, limit):
                top_forward.append(item)
                top_forward_names.add(name)
            elif name in top_forward_names:
                duplicates_forward.append(item)

        # 剩余角色按 money 降序，金额相同 pos 优先级 forward > backward > all，同样去重，重复的放末尾
        pos_priority = {"forward": 0, "backward": 1, "all": 2}
        remaining_pool = [item for item in all_chars if item not in top_forward and item not in duplicates_forward]
        remaining_pool.sort(key=lambda x: (-x["c"].money, pos_priority.get(x["c"].pos, 3)))

        remaining_unique: list[dict] = []
        remaining_names: set[str] = set()
        duplicates_rest: list[dict] = []
        for item in remaining_pool:
            name = item["c"].name
            if name and name not in top_forward_names and name not in remaining_names:
                remaining_unique.append(item)
                remaining_names.add(name)
            else:
                duplicates_rest.append(item)

        # 最终排序：前台唯一 -> 其余唯一 -> 所有重复
        all_chars = top_forward + remaining_unique + duplicates_forward + duplicates_rest

        log.debug("按投资金额排序后的角色信息：")
        for item in all_chars:
            log.debug(f"角色 {item['c'].name}: 费用={item['c'].money}, 站位={self.pos_name_localization.get(item['c'].pos, item['c'].pos)}, 区域={self.zone_name_localization[item['zone']]}, 索引={item['idx']}")

        # 按规则分配 forward/backward/prepare
        used = 0  # forward + backward 已使用数量

        assigned = {"forward": [], "backward": [], "prepare": []}
        used_names = set()  # forward/backward 已分配的名字

        for item in all_chars:
            c = item["c"]
            name = c.name

            # forward
            if ((c.pos in ("forward", "all") or len(top_forward) < min(forward_slots, limit)) and
                len(assigned["forward"]) < forward_slots and
                used < limit and
                    name not in used_names):
                assigned["forward"].append(item)
                used_names.add(name)
                used += 1
                continue

            # backward
            if (c.pos in ("backward", "all") and
                len(assigned["backward"]) < backward_slots and
                used < limit and
                    name not in used_names):
                assigned["backward"].append(item)
                used_names.add(name)
                used += 1
                continue

            assigned["prepare"].append(item)

        log.debug(
            f"计算区域结果: {self.zone_name_localization['forward']}={len(assigned['forward'])}, {self.zone_name_localization['backward']}={len(assigned['backward'])}, {self.zone_name_localization['prepare']}={len(assigned['prepare'])}, total used={used}/{limit}")

        # 无效优化，前台角色放后台不会自动使用技能，保持队伍中有角色空缺即可
        # # 补充逻辑：如果 forward 已满且 used < limit，从 prepare 移动角色到 backward
        # if len(assigned['forward']) == min(forward_slots, limit) and used < limit:
        #     log.debug(f"前台已满({len(assigned['forward'])}个)，但总使用量({used})未达上限({limit})，尝试从备战席补充到后台")
        #     # 从 prepare 中找出不重名的角色
        #     to_move = []
        #     for item in assigned["prepare"]:
        #         if used >= limit:
        #             break
        #         name = item["c"].name
        #         if name and name not in used_names:  # 不重名
        #             to_move.append(item)
        #             used_names.add(name)
        #             used += 1

        #     # 移动到 backward 末尾
        #     if to_move:
        #         assigned["prepare"] = [item for item in assigned["prepare"] if item not in to_move]
        #         assigned["backward"].extend(to_move)
        #         log.debug(f"从备战席移动 {len(to_move)} 个角色到后台: {[item['c'].name for item in to_move]}")
        #         log.debug(
        #             f"调整后区域结果: {self.zone_name_localization['forward']}={len(assigned['forward'])}, {self.zone_name_localization['backward']}={len(assigned['backward'])}, {self.zone_name_localization['prepare']}={len(assigned['prepare'])}, total used={used}/{limit}")

        # 4️⃣ 填充空位
        for zone in ["forward", "backward"]:
            while len(assigned[zone]) < len(self.__dict__[f"{zone}_characters"]):
                assigned[zone].append({"c": CurrencyWarsCharacter(None, None), "zone": "prepare", "idx": None, "pos_ref": None})

        while len(assigned["prepare"]) < len(self.prepare_characters):
            assigned["prepare"].append({"c": CurrencyWarsCharacter(None, None), "zone": "prepare", "idx": None, "pos_ref": None})
        # 显示每个区域的角色
        for zone in ["forward", "backward", "prepare"]:
            names = [item["c"].name for item in assigned[zone]]
            log.debug(f"区域 {self.zone_name_localization[zone]} 角色: {names}")

        # 将已在目标区域的角色提前放置到对应索引，减少后续交换
        for zone in ("forward", "backward"):
            current_zone_list = getattr(self, f"{zone}_characters")
            target_list = assigned[zone]
            for idx, cur_char in enumerate(current_zone_list):
                cur_name = cur_char.name
                if not cur_name:
                    continue
                if target_list[idx]["c"].name == cur_name:
                    continue
                swap_idx = None
                for j in range(len(target_list)):
                    if j == idx:
                        continue
                    if target_list[j]["c"].name == cur_name:
                        swap_idx = j
                        break
                if swap_idx is not None:
                    target_list[idx], target_list[swap_idx] = target_list[swap_idx], target_list[idx]
                    log.debug(f"预先对齐 {self.zone_name_localization[zone]} 索引 {idx}: {cur_name}")

        # 显示每个区域的角色
        for zone in ["forward", "backward", "prepare"]:
            names = [item["c"].name for item in assigned[zone]]
            log.debug(f"区域 {self.zone_name_localization[zone]} 角色: {names}")
        self._log_character_status()

        # 根据计算结果，通过 UI 调用 move_character 来实际交换位置
        # 辅助函数：查找当前角色位置（从目标位置之后开始寻找）
        def _find_current(name: Optional[str], target_zone: Optional[str] = None, target_idx: Optional[int] = None) -> Tuple[Optional[str], Optional[int]]:
            if not name:
                return None, None

            # 构造搜索顺序：从目标位置及之后开始
            zones_order = ["forward", "backward", "prepare"]

            # 如果指定了目标位置，则优先搜索从目标位置之后的位置
            if target_zone is not None:
                target_zone_idx = zones_order.index(target_zone)
                # 重新排列搜索顺序：从目标位置之后开始，然后回到前面
                zones_order = zones_order[target_zone_idx:] + zones_order[:target_zone_idx]

            for z in zones_order:
                lst = getattr(self, f"{z}_characters")

                # 确定起始索引
                start_idx = 0
                if z == target_zone and target_idx is not None:
                    start_idx = target_idx + 1

                # 先搜索从起始索引到末尾
                for idx in range(start_idx, len(lst)):
                    if lst[idx].name == name:
                        return z, idx

                # 如果是目标所在的区域，还要搜索起始索引之前的部分
                if z == target_zone and target_idx is not None:
                    for idx in range(0, target_idx):
                        if lst[idx].name == name:
                            return z, idx

            return None, None

        # 当前已部署数量（forward+backward 非空位计数）
        current_used = sum(1 for c in self.forward_characters if c.name) + sum(1 for c in self.backward_characters if c.name)

        # for zone in ("forward", "backward", "prepare"):
        # prepare 可以跳过排序
        for zone in ("forward", "backward"):
            slot_list = getattr(self, f"{zone}_characters")
            for target_idx in range(len(slot_list)):
                desired = assigned[zone][target_idx]
                desired_name = desired["c"].name

                # 目标应为空，无需移动
                if not desired_name:
                    continue

                # 如果目标位置已经是期望角色则跳过
                cur = slot_list[target_idx]
                if cur.name == desired_name:
                    continue

                # 查找期望角色当前位置
                src_zone, src_idx = _find_current(desired_name, zone, target_idx)
                if src_zone is None:
                    log.error(f"未找到角色 {desired_name} 的当前位置，跳过移动")
                    continue

                target_is_empty = (cur.name is None)
                target_is_forward_backward = (zone in ("forward", "backward"))

                # special case: 源在 prepare，目标为空，但 forward+backward 已达 limit
                if src_zone == "prepare" and target_is_forward_backward and target_is_empty and current_used >= limit:
                    # 在目标位置之后寻找第一个存在的角色作为后备用于交换
                    # 在 forward+backward 两个区间的合并列表中，从目标位置之后寻找第一个存在的角色用于交换
                    f_len = len(self.forward_characters)
                    # b_len = len(self.backward_characters)
                    # 构造合并列表引用
                    combined = list(self.forward_characters) + list(self.backward_characters)
                    # 计算目标在合并列表中的索引
                    if zone == "forward":
                        combined_target_idx = target_idx
                    else:
                        combined_target_idx = f_len + target_idx

                    occ_combined_idx = None
                    # 向后搜索
                    for j in range(combined_target_idx + 1, len(combined)):
                        if combined[j].name:
                            occ_combined_idx = j
                            break

                    # if occ_combined_idx is None:
                    #     for j in range(combined_target_idx - 1, -1, -1):
                    #         if combined[j].name:
                    #             occ_combined_idx = j
                    #             break

                    if occ_combined_idx is None:
                        log.warning(f"没有可用于腾位置的角色，跳过移动 {desired_name}")
                        continue

                    # 将合并索引映射回具体的 zone 和 idx
                    if occ_combined_idx < f_len:
                        occ_zone, occ_idx = "forward", occ_combined_idx
                    else:
                        occ_zone, occ_idx = "backward", occ_combined_idx - f_len

                    # 第一步：把 prepare 中的目标角色与后备已存在的角色交换（可能跨区）
                    if not self.move_character((src_zone, src_idx), (occ_zone, occ_idx)):
                        log.error(f"交换角色失败: {self.zone_name_localization[src_zone]}({src_idx}) <-> {self.zone_name_localization[occ_zone]}({occ_idx})")
                        continue

                    # 重新定位期望角色的位置索引
                    src_zone, src_idx = _find_current(desired_name, zone, target_idx)
                    if src_zone is None:
                        log.error(f"交换后未找到 {desired_name}，跳过")
                        continue

                    # 第二步：将刚放到占位位的角色移动到目标位置（目标为原 zone,target_idx）
                    if not self.move_character((src_zone, src_idx), (zone, target_idx)):
                        log.error(f"交换角色失败: {self.zone_name_localization[src_zone]}({src_idx}) -> {self.zone_name_localization[zone]}({target_idx})")
                        continue

                else:
                    # 一般情况：直接与目标位置交换（无论目标是否为空）
                    if not self.move_character((src_zone, src_idx), (zone, target_idx)):
                        log.error(f"交换角色失败: {self.zone_name_localization[src_zone]}({src_idx}) -> {self.zone_name_localization[zone]}({target_idx})")
                        continue

                # 更新当前已部署计数
                current_used = sum(1 for c in self.forward_characters if c.name) + sum(1 for c in self.backward_characters if c.name)

        self._log_character_status()

        # 检查前台角色数量，如果为0则从后台和备战席查找角色移动到前台
        forward_count = sum(1 for c in self.forward_characters if c.name)
        if forward_count == 0:
            log.info("检测到前台角色为0，尝试从后台和备战席查找角色移动到前台")
            # 先在后台查找
            found = False
            for idx, char in enumerate(self.backward_characters):
                if char.name:
                    log.info(f"从后台找到角色 {char.name}，移动到前台索引0")
                    if self.move_character(("backward", idx), ("forward", 0)):
                        found = True
                        break

            # 如果后台没找到，再在备战席查找
            if not found:
                for idx, char in enumerate(self.prepare_characters):
                    if char.name:
                        log.info(f"从备战席找到角色 {char.name}，移动到前台索引0")
                        if self.move_character(("prepare", idx), ("forward", 0)):
                            break

        log.info("角色移动操作完成")

    def _log_character_status(self):
        """
        输出当前各区域的角色状态日志
        """
        log.debug("当前各区域角色状态：")
        for zone in ["forward", "backward", "prepare"]:
            names = [c.name for c in self.__dict__[f"{zone}_characters"]]
            log.debug(f"区域 {self.zone_name_localization[zone]} 角色: {names}")

    def move_character(self, src: tuple, dst: tuple) -> bool:
        """
        在 UI 上把 `src` 位置的角色拖到 `dst` 位置并在内部列表中交换两者。

        参数格式：`(zone, idx)`，其中 `zone` 为 "forward"、"backward" 或 "prepare"，
        `idx` 为该分区内的位置索引（从 0 开始）。

        返回 True 表示成功，False 表示失败（例如未找到 UI 位置）。
        """

        def _validate_and_get(zone_idx):
            if not (isinstance(zone_idx, tuple) and len(zone_idx) == 2 and isinstance(zone_idx[0], str) and isinstance(zone_idx[1], int)):
                raise TypeError("参数必须为 (zone, idx) 形式")
            zone, idx = zone_idx
            if zone not in ("forward", "backward", "prepare"):
                raise ValueError("zone must be 'forward', 'backward' or 'prepare'")
            pos_list = getattr(self, f"{zone}_pos")
            if idx < 0 or idx >= len(pos_list):
                raise IndexError(f"index {idx} out of range for zone {zone}")
            return zone, idx, pos_list[idx]

        z1, i1, crop_a = _validate_and_get(src)
        z2, i2, crop_b = _validate_and_get(dst)

        pos1 = auto.find_element(crop_a, "crop")
        if not pos1:
            log.error("未找到源位置，无法移动")
            return False
        auto.click_element_with_pos(pos1, action="down")
        time.sleep(0.5)

        pos2 = auto.find_element(crop_b, "crop", None, 10)
        if not pos2:
            auto.mouse_up()
            log.error("未找到目标位置，无法移动")
            return False

        auto.click_element_with_pos(pos2, action="move")
        time.sleep(0.5)
        auto.mouse_up()
        time.sleep(0.5)

        # 在内部数据结构中交换角色对象引用
        list1 = getattr(self, f"{z1}_characters")
        list2 = getattr(self, f"{z2}_characters")
        list1[i1], list2[i2] = list2[i2], list1[i1]

        log.info(f"已移动角色: {list2[i2].name}({self.zone_name_localization[z1]}({i1})) <-> {list1[i1].name}({self.zone_name_localization[z2]}({i2}))")
        self._log_character_status()

        # 检查可能弹出的特殊选择框
        self.check_festival_star_popup()
        return True

    def check_festival_star_popup(self):
        """
        检查是否弹出盛会之星或命运卜者等内容的选择框
        """
        result = auto.get_single_line_text(crop=(936.0 / 1920, 52.0 / 1080, 219.0 / 1920, 53.0 / 1080))
        if result:
            if "盛会之星" in result:
                log.info("检测到盛会之星")
                char_crop = (816.0 / 1920, 165.0 / 1080, 222.0 / 1920, 202.0 / 1080)
                auto.click_element(char_crop, "crop")
                time.sleep(0.5)
                auto.click_element("确认选择", "text", crop=(1428.0 / 1920, 539.0 / 1080, 124.0 / 1920, 46.0 / 1080))
                time.sleep(0.5)
            elif "命运卜者" in result:
                log.info("检测到命运卜者")
                char_crop = (850.0 / 1920, 167.0 / 1080, 395.0 / 1920, 249.0 / 1080)
                auto.click_element(char_crop, "crop")
                time.sleep(0.5)
                char_crop_pos = [
                    (800.0 / 1920, 372.0 / 1080, 25.0 / 1920, 36.0 / 1080),
                    (1208.0 / 1920, 371.0 / 1080, 25.0 / 1920, 36.0 / 1080),
                    (1617.0 / 1920, 373.0 / 1080, 24.0 / 1920, 35.0 / 1080)
                ]
                for pos in char_crop_pos:
                    result = auto.get_single_line_text(crop=pos)
                    if result:
                        # 优先选择0费
                        if result.isdigit() and int(result) == 0:
                            auto.click_element(pos, "crop")
                            time.sleep(0.5)
                            break
                auto.click_element("确认选择", "text", crop=(1329.0 / 1920, 572.0 / 1080, 332.0 / 1920, 55.0 / 1080))
                time.sleep(0.5)

    def identify_current_stage(self):
        """
        识别当前关卡阶段
        """
        stage_crop = (414 / 1920, 56 / 1080, 117 / 1920, 44 / 1080)
        stage_text = auto.get_single_line_text(crop=stage_crop)
        if stage_text and re.match(r"^\d-\d$", stage_text):
            log.hr(f"当前阶段：{stage_text}", 2)
            self.current_stage = stage_text
        else:
            log.warning("未能识别当前货币战争阶段")

    def collect_reward(self):
        """
        收集奖励：模拟连续滑动，经过所有奖励图标
        """
        reward_pos = [
            (1291.0 / 1920, 182.0 / 1080, 23.0 / 1920, 21.0 / 1080),
            (1561.0 / 1920, 181.0 / 1080, 23.0 / 1920, 20.0 / 1080),
            (1569.0 / 1920, 225.0 / 1080, 24.0 / 1920, 23.0 / 1080),
            (1297.0 / 1920, 227.0 / 1080, 24.0 / 1920, 22.0 / 1080),
            (1302.0 / 1920, 275.0 / 1080, 25.0 / 1920, 22.0 / 1080),
            (1580.0 / 1920, 274.0 / 1080, 25.0 / 1920, 23.0 / 1080),
            (1588.0 / 1920, 309.0 / 1080, 26.0 / 1920, 21.0 / 1080),
            (1305.0 / 1920, 308.0 / 1080, 27.0 / 1920, 20.0 / 1080),
            (1311.0 / 1920, 343.0 / 1080, 23.0 / 1920, 21.0 / 1080),
            (1596.0 / 1920, 343.0 / 1080, 27.0 / 1920, 23.0 / 1080),
            (1603.0 / 1920, 378.0 / 1080, 25.0 / 1920, 23.0 / 1080),
            (1315.0 / 1920, 377.0 / 1080, 26.0 / 1920, 22.0 / 1080),
            (1320.0 / 1920, 411.0 / 1080, 24.0 / 1920, 24.0 / 1080),
            (1589.0 / 1920, 413.0 / 1080, 27.0 / 1920, 21.0 / 1080),
            (1551.0 / 1920, 449.0 / 1080, 25.0 / 1920, 22.0 / 1080),
            (1324.0 / 1920, 449.0 / 1080, 24.0 / 1920, 23.0 / 1080)
        ]

        # 提取每个区域的中心点（归一化坐标）
        centers = []
        for x, y, w, h in reward_pos:
            cx = x + w / 2
            cy = y + h / 2
            centers.append((cx, cy))

        # 将归一化坐标转为像素坐标
        def to_pixel(pt):
            return (pt[0] * 1920, pt[1] * 1080)

        def to_norm(px, py):
            return (px / 1920, py / 1080)

        pixel_centers = [to_pixel(c) for c in centers]

        # 生成连续路径：根据距离动态确定插值点数
        path_pixels = []
        base_step_distance = 50  # 每50像素一个插值点

        for i in range(len(pixel_centers) - 1):
            x0, y0 = pixel_centers[i]
            x1, y1 = pixel_centers[i + 1]
            # 计算两点间的欧几里得距离
            distance = np.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
            # 根据距离动态计算插值点数，至少2个点
            steps = max(2, int(distance / base_step_distance))
            for t in np.linspace(0, 1, steps, endpoint=False):
                px = x0 + t * (x1 - x0)
                py = y0 + t * (y1 - y0)
                path_pixels.append((px, py))
        # 添加最后一个点
        path_pixels.append(pixel_centers[-1])

        # 转回归一化坐标，并构造“crop”区域
        def make_crop_box(norm_pt):
            return (norm_pt[0], norm_pt[1], 0.001, 0.001)

        # 开始拖动
        first_norm = to_norm(*path_pixels[0])
        first_crop = make_crop_box(first_norm)
        pos_start = auto.find_element(first_crop, "crop")
        auto.click_element_with_pos(pos_start, action="down")

        # 连续移动
        for px, py in path_pixels[1:]:
            norm_pt = to_norm(px, py)
            crop_box = make_crop_box(norm_pt)
            pos = auto.find_element(crop_box, "crop", take_screenshot=False)
            auto.click_element_with_pos(pos, action="move")

        auto.mouse_up()

    # 识别等级
    def get_level(self):
        """
        识别当前角色等级
        """
        level_crop = (235.0 / 1920, 876.0 / 1080, 125.0 / 1920, 60.0 / 1080)
        result = auto.get_single_line_text(crop=level_crop)
        if result:
            digits = ''.join(filter(str.isdigit, result))
            if digits.isdigit():
                level = int(digits)
                if 3 <= level <= 10:
                    self.current_level = level
                    return True
        return False

    def buy_experience(self):
        """
        购买经验
        """
        if self.current_level == 10:
            log.info("已达最大等级，跳过购买经验")
            return
        previous_money = None
        while True:
            if self.get_level():
                log.debug(f"缓存角色等级信息: 当前等级 {self.current_level}")

            money = self.check_money()
            if money >= 4:
                times = min(money // 4, 10)
                log.info(f"连续购买经验 {times} 次")
                for _ in range(times):
                    auto.press_key("f")
                    time.sleep(0.1)
                time.sleep(2)

                # 检查货币是否有变化
                if previous_money is not None and money == previous_money:
                    log.info("货币数量未变化，停止购买经验")
                    break
                previous_money = money
            else:
                log.info("停止购买经验")
                break

            if auto.find_element("满级", "text", crop=(250.0 / 1920, 841.0 / 1080, 99.0 / 1920, 40.0 / 1080), include=True):
                self.current_level = 10
                log.info("检测到已满级，停止购买经验")
                break

    def check_money(self):
        """
        检查当前货币数量
        """
        money_crop = (1559.0 / 1920, 880.0 / 1080, 127.0 / 1920, 82.0 / 1080)
        money = auto.get_single_line_text(crop=money_crop, blacklist=['V'])
        if money:
            try:
                money_int = int(money)
                log.info(f"当前货币数量:{money_int}")
                return money_int
            except (ValueError, TypeError):
                log.error(f"货币数量识别失败: {money}")
                return 0
        log.warning("未能识别到货币数量")
        return 0

    def check_character_limit(self):
        '''
        检查当前角色上限
        角色上限 = 当前等级 + 财富宝钻数量 = 面板上限 - 佩佩/叽米等特殊角色数量
        '''
        if self.current_level == 10:
            log.debug(f"已达最大等级，角色上限 {10 + self.diamond_count}")
            return 10 + self.diamond_count

        if self.get_level():
            log.debug(f"解析角色上限信息: 当前等级 {self.current_level}，角色上限 {self.current_level + self.diamond_count}")
            return self.current_level + self.diamond_count

        # 备用方案：直接读取角色上限
        limit_crop = (848.0 / 1920, 206.0 / 1080, 231.0 / 1920, 79.0 / 1080)
        limit = auto.get_single_line_text(crop=limit_crop, blacklist=['等级提升', '金币不足'])
        if limit:
            limit = limit.replace("i", "").replace(":", "")
            limit_parts = limit.split('/')
            if len(limit_parts) == 2 and limit_parts[1].isdigit():
                log.debug(f"备用方案解析角色上限信息: 角色上限 {limit_parts[1]}")
                self.current_level = int(limit_parts[1]) - self.peipei_count - self.diamond_count
                return int(limit_parts[1]) - self.peipei_count

        # 如果都无法解析，尝试获取之前缓存的等级信息
        if self.current_level > 0:
            log.debug(f"使用缓存的等级信息，角色上限 {self.current_level + self.diamond_count}")
            return self.current_level + self.diamond_count

        raise ValueError("无法解析角色上限信息")

    def check_box(self):
        """
        检查并处理补给阶段的宝箱
        """
        # 游戏存在bug，点击开启的速度太快无法弹出选择界面 :(
        res = auto.find_element("开启", "text", None, crop=(376.0 / 1920, 839.0 / 1080, 1125.0 / 1920, 148.0 / 1080), include=True)
        start_time = time.monotonic()
        while res:
            # 检查超时（30秒）
            if time.monotonic() - start_time > 30:
                log.error("开启宝箱操作超时，退出循环")
                break

            auto.click_element_with_pos(res, action="down")
            time.sleep(0.2)
            auto.mouse_up()
            time.sleep(2)
            if auto.find_element(('武装箱', '星徽秘典'), "text", None, crop=(1012.0 / 1920, 27.0 / 1080, 173.0 / 1920, 56.0 / 1080), include=True):
                pos = (533.0 / 1920, 135.0 / 1080, 258.0 / 1920, 181.0 / 1080)
                auto.click_element(pos, "crop")
                time.sleep(1)
            # 聘用书坐标尚未经过测试
            if auto.find_element("聘用书", "text", None, crop=(923.0 / 1920, 21.0 / 1080, 168.0 / 1920, 74.0 / 1080), include=True):
                pos = (486.0 / 1920, 159.0 / 1080, 240.0 / 1920, 269.0 / 1080)
                auto.click_element(pos, "crop")
                time.sleep(1)
            res = auto.find_element("开启", "text", None, crop=(376.0 / 1920, 839.0 / 1080, 1125.0 / 1920, 148.0 / 1080), include=True)

    def check_character_status(self):
        """
        检查角色状态
        """
        # 每次检查前重置
        # self.forward_characters = []
        # self.backward_characters = []
        self.prepare_characters = []

        # forward 和 backward 位置检测到空位后，后续默认都为空
        if self.forward_characters == []:
            for pos in self.forward_pos:
                if len(self.forward_characters) > 0 and self.forward_characters[-1].name is None:
                    self.forward_characters.append(CurrencyWarsCharacter(None, None))
                else:
                    self.forward_characters.append(self.check_character_info(pos))

        if self.backward_characters == []:
            for pos in self.backward_pos:
                if len(self.backward_characters) > 0 and self.backward_characters[-1].name is None:
                    self.backward_characters.append(CurrencyWarsCharacter(None, None))
                else:
                    self.backward_characters.append(self.check_character_info(pos))

        # prepare 位置需要全部检测
        for pos in self.prepare_pos:
            self.prepare_characters.append(self.check_character_info(pos))

    def check_character_info(self, pos: Tuple[float, float, float, float]):
        """
        检查并记录角色信息(使用缓存避免重复识别)
        """
        char_name_crop = (1493.0 / 1920, 213.0 / 1080, 299.0 / 1920, 30.0 / 1080)
        char_pos_crop = (1494.0 / 1920, 249.0 / 1080, 35.0 / 1920, 40.0 / 1080)
        char_level_crop = (1566.0 / 1920, 161.0 / 1080, 126.0 / 1920, 25.0 / 1080)
        char_money_crop = (1831.0 / 1920, 188.0 / 1080, 35.0 / 1920, 42.0 / 1080)

        auto.click_element(pos, "crop")
        time.sleep(0.5)
        name = auto.get_single_line_text(crop=char_name_crop)
        if name:
            # 检查缓存中是否已有该角色信息
            if name in self.character_info_cache:
                log.info(f"识别到已知角色：{name}")
                self.click_origin()
                return self.character_info_cache[name]

            # 首次识别该角色,获取完整信息并缓存
            if auto.find_element("./assets/images/screen/currency_wars/pos_forward.png", "image", 0.9, crop=char_pos_crop):
                pos = "forward"
            elif auto.find_element("./assets/images/screen/currency_wars/pos_backward.png", "image", 0.9, crop=char_pos_crop):
                pos = "backward"
            else:
                pos = "all"
            money = auto.get_single_line_text(crop=char_money_crop)
            if not money or not money.isdigit():
                log.error(f"无法识别角色 {name} 的费用信息，默认为 1")
                money = "1"
            log.info(f"识别到角色：{name}，站位：{self.pos_name_localization[pos]}，费用：{money}")

            # 创建角色对象并缓存
            character = CurrencyWarsCharacter(name, pos, money=int(money))
            self.character_info_cache[name] = character

            self.click_origin()
            return character
        return CurrencyWarsCharacter(None, None)

    def click_origin(self):
        """
        点击屏幕原点以取消所有选中状态
        """
        pos = (6.0 / 1920, 5.0 / 1080, 12.0 / 1920, 14.0 / 1080)
        auto.click_element_with_pos(auto.find_element(pos, "crop"))
        time.sleep(0.2)

    def check_auto_battle(self):
        """
        检查并开启自动战斗
        """
        if cfg.auto_battle_detect_enable and auto.find_element("./assets/images/share/base/not_auto.png", "image", 0.9, crop=(0.0 / 1920, 903.0 / 1080, 144.0 / 1920, 120.0 / 1080)):
            log.info("尝试开启自动战斗")
            auto.press_key("v")

    def check_click_continue(self):
        """
        检查并点击继续类别的按钮
        """
        if auto.click_element(("点击空白处继续", "下一步", "继续挑战", "前往结算", "下一页", "确认选择"), 'text', None, include=True):
            log.info(f"检测到{auto.matched_text}按钮，尝试点击")
            if auto.matched_text == "下一页":
                self._check_battle_result()

    def _check_battle_result(self):
        """
        检查并记录对局结果
        """
        for box in auto.ocr_result:
            text = box[1][0]
            if "对局胜利" in text:
                self.result = True
                self.screenshot = auto.screenshot
                return
            elif "对局未完成" in text:
                self.result = False
                self.screenshot = auto.screenshot
                return

    def check_special_characters(self, crop: Tuple[float, float, float, float]):
        """
        检查指定区域是否有佩佩、叽米或财富宝钻，并更新计数

        参数：
            crop: 要检查的区域坐标
        """
        # 孪生姵姵：获得一个姵姵，它看起来和你的佩佩一模一样！
        # 佩佩驾到：获得1个携带着3个永久附着星徽的【佩佩】。
        # 这么大的钻石：佩佩携带【财富宝钻】出现
        # 招财狗：获得一个佩佩
        # 溜佩佩+：什么都没带的佩佩会在你的后排逛街
        # 溜佩佩：什么都没带的佩佩会在你的后排逛街
        # 三星佩佩：获得一个穿戴三个随机星徽的佩佩。
        # 粗星佩佩：获得一个穿戴三个随机星徽的佩佩
        # 星徽大使叽米：超稀有的叽米登场！爆出超多星徽！！
        # 金币大使叽米：超稀有的叽米登场！爆出超多金币！！
        if auto.find_element(('姵姵', '佩佩', '叽米'), 'text', crop=crop, include=True):
            self.peipei_count += 1
            self.update_backward()
        if auto.find_element('财富宝钻', 'text', crop=crop, include=True):
            self.diamond_count += 1
            # 多元化团队：获得2个【财富宝钻】
            if auto.find_element('多元化团队', 'text', crop=crop, include=True):
                self.diamond_count += 1
            self.update_backward()

    def check_investment_environment(self):
        """
        检查并执行投资环境/策略操作
        """
        if auto.find_element(('投资环境', '请选择投资策略'), 'text', None, crop=(850.0 / 1920, 59.0 / 1080, 223.0 / 1920, 77.0 / 1080)):
            log.info(f"检测到{auto.matched_text}界面，尝试选择")
            time.sleep(2)
            button_positions = [
                (725.0 / 1920, 196.0 / 1080, 468.0 / 1920, 670.0 / 1080),
                (202.0 / 1920, 195.0 / 1080, 470.0 / 1920, 672.0 / 1080),
                (1247.0 / 1920, 198.0 / 1080, 465.0 / 1920, 668.0 / 1080),
            ]
            button_positions_click = [
                (765.0 / 1920, 201.0 / 1080, 394.0 / 1920, 271.0 / 1080),
                (267.0 / 1920, 200.0 / 1080, 384.0 / 1920, 269.0 / 1080),
                (1268.0 / 1920, 204.0 / 1080, 387.0 / 1920, 265.0 / 1080),
            ]
            has_choose = False

            # 不方便判断的选项，暂时跳过处理
            # 深井角斗场：本局首次达成5连胜时，获得【财富宝钻】。
            # 佩佩客串：进入5个节点后，阿兰接走佩佩们并留下所有装备。
            # 钻石商人：升到9级时，获得【财富宝钻】。
            # 现金为王：出售场上和备战席的所有角色
            # 降本增效：出售场上和备战席的所有角色
            # 大裁员：出售场上和备战席的所有角色
            # 人力重组：移除场上和备战席的所有角色
            # 节省工位：在接下来3个节点只有3个备战席位置
            # 奋斗协议：购买经验值消耗7点小队生命值而非金币
            black_list = ('深井角斗场', '佩佩客串', '钻石商人', '现金为王', '降本增效', '大裁员', '人力重组', '节省工位', '奋斗协议')
            for pos in button_positions:
                if auto.find_element(black_list, 'text', crop=pos, include=True):
                    log.debug(f"跳过{auto.matched_text}选项")
                    continue
                if auto.click_element("./assets/images/screen/currency_wars/new.png", "image", 0.9, crop=pos):
                    log.info("检测到图鉴未收集选项，尝试点击")
                    has_choose = True
                    self.check_special_characters(pos)
                    break

            if not has_choose:
                for pos in button_positions:
                    if auto.find_element(black_list, 'text', crop=pos, include=True):
                        log.debug(f"跳过{auto.matched_text}选项")
                        continue
                    auto.click_element(button_positions_click[button_positions.index(pos)], 'crop')
                    has_choose = True
                    log.info(f"未检测到图鉴未收集选项，选择第{button_positions.index(pos) + 1}个按钮")
                    break
                self.check_special_characters(button_positions[0])

            if not has_choose:
                log.error("所有选项均不可选，尝试退出")
                auto.click_element(button_positions_click[0], 'crop')
                self.need_exit = True
            time.sleep(1)
            auto.click_element('确认', 'text', None, 10, crop=(738.0 / 1920, 927.0 / 1080, 457.0 / 1920, 123.0 / 1080), include=True)

    def update_backward(self):
        default = 6
        choose = default + self.peipei_count + self.diamond_count
        if choose == 6:
            self.backward_pos = self.backward_pos_6
        elif choose == 7:
            self.backward_pos = self.backward_pos_7[0:7 - self.peipei_count]
        elif choose == 8:
            self.backward_pos = self.backward_pos_8[0:8 - self.peipei_count]
        # 格子最多9个，场上4个佩佩也不会变多
        else:
            self.backward_pos = self.backward_pos_9[0:9 - self.peipei_count]

        # 重置后排角色列表
        self.backward_characters = []

    def check_supply_phase(self):
        """
        检查并执行补给阶段操作
        """
        if auto.find_element(('补给阶段'), 'text', None, crop=(775.0 / 1920, 109.0 / 1080, 368.0 / 1920, 98.0 / 1080)):
            log.info(f"检测到补给阶段界面，尝试选择")
            time.sleep(2)
            button_positions = [
                (262.0 / 1920, 294.0 / 1080, 332.0 / 1920, 487.0 / 1080),
                (616.0 / 1920, 292.0 / 1080, 333.0 / 1920, 489.0 / 1080),
                (971.0 / 1920, 293.0 / 1080, 333.0 / 1920, 488.0 / 1080),
                (1325.0 / 1920, 291.0 / 1080, 333.0 / 1920, 490.0 / 1080),
            ]
            button_positions_click = [
                (297.0 / 1920, 349.0 / 1080, 130.0 / 1920, 241.0 / 1080),
                (651.0 / 1920, 349.0 / 1080, 130.0 / 1920, 242.0 / 1080),
                (1007.0 / 1920, 347.0 / 1080, 130.0 / 1920, 246.0 / 1080),
                (1362.0 / 1920, 346.0 / 1080, 130.0 / 1920, 247.0 / 1080),
            ]
            auto.click_element(button_positions_click[0], 'crop', None, 10)
            log.info("默认选择第一个补给选项")
            time.sleep(1)
            auto.click_element('确认', 'text', None, 10, crop=(1490.0 / 1920, 943.0 / 1080, 403.0 / 1920, 76.0 / 1080), include=True)

    def check_return_home(self) -> bool:
        """
        检查并返回货币战争
        """
        if auto.click_element('返回货币战争', 'text', None, crop=(674.0 / 1920, 852.0 / 1080, 569.0 / 1920, 108.0 / 1080)):
            log.info("检测到货币战争按钮，尝试点击")
            if self.result is not None:
                log.info(f"本次对局结果：{'胜利' if self.result else '失败'}")
            else:
                log.info("本次对局结果：未知")
            time.sleep(2)
            screen.wait_for_screen_change("currency_wars_homepage")
            log.info("已返回货币战争首页")
            return True
        return False
