from abc import ABC, abstractmethod
from typing import Optional
from module.automation import auto
from module.logger import log
import time


class BaseChallenge(ABC):
    def __init__(self, name: str, total_star: Optional[int], hotkey_technique: str, auto_battle_detect_enable: bool) -> None:
        self.name = name
        self.total_star = total_star
        self.hotkey_technique = hotkey_technique
        self.auto_battle_detect_enable = auto_battle_detect_enable
        self.max_level = 0
        self.max_star = 3

    @abstractmethod
    def run(self):
        '''执行挑战'''
        pass

    def prepare(self):
        '''切换场景并判断是否刷新'''
        raise NotImplementedError

    def start_challenges(self):
        '''查找关卡并判断星数'''
        raise NotImplementedError

    def start_challenge(self):
        '''开始挑战'''
        raise NotImplementedError

    def prepare_level(self):
        '''配置队伍'''
        raise NotImplementedError

    def start_level(self):
        '''开始关卡'''
        raise NotImplementedError

    def start_battle(self):
        '''开始战斗'''
        raise NotImplementedError

    def check_fight(self):
        '''检查战斗是否结束'''
        raise NotImplementedError

    def collect_rewards(self):
        '''领取奖励'''
        raise NotImplementedError

    def check_star_in_ocr_results(self, ocr_results):
        '''根据星数判断是否刷新'''
        target_format = f"/{self.total_star}"
        for box in ocr_results:
            text = box[1][0]
            if target_format in text:
                log.info(f"星数：{text}")
                current_star, _ = text.split('/')
                if current_star == str(self.total_star):
                    log.info(f"{self.name}未刷新")
                    return True
                else:
                    return False
        return False

    def select_characters(self, team_config, team_image_path):
        '''选择角色'''
        # 切换队伍
        if auto.click_element(team_image_path, "image", 0.8, max_retries=10, crop=(592.0 / 1920, 556.0 / 1080, 256.0 / 1920, 424.0 / 1080)):
            time.sleep(1)
            auto.take_screenshot(crop=(30 / 1920, 115 / 1080, 530 / 1920, 810 / 1080))
            # 选择角色
            for character in team_config:
                scrolling_counter = 0 #统计滚动次数
                max_scroll_times = 4 #最大滚动次数
                scroll_line = 19 #26滚动1页，13滚动半页
                while(not auto.click_element(f"./assets/images/share/character/{character[0]}.png", "image", 0.7, max_retries=10, take_screenshot=False)):
                    if scrolling_counter > max_scroll_times:
                        #滚动超过2页强制结束
                        log.info(f"{character[0]}未找到")
                        return False
                    auto.click_element("等级", "text", include=True, action="move")
                    #，尝试向下滚动
                    auto.mouse_scroll(scroll_line, -1, False)
                    time.sleep(0.5)
                    auto.click_element("角色列表", "text", include=True, action="move")
                    scrolling_counter += 1
                for _ in range(scrolling_counter):
                     # 尝试向上滚动 恢复初始位置
                    auto.click_element("等级", "text", include=True, action="move")
                    auto.mouse_scroll(scroll_line, 1, False)
                    time.sleep(0.5)
                    auto.click_element("角色列表", "text", include=True, action="move")
                time.sleep(0.5)
            return True
        return False

    def click_message_box(self):
        '''等待游戏加载并点击弹窗'''
        if auto.find_element("空白", "text", max_retries=120, crop=(12.0 / 1920, 731.0 / 1080, 1904.0 / 1920, 280.0 / 1080), include=True):
            time.sleep(1)
            # 关闭弹窗
            auto.press_key("esc")
            time.sleep(1)

    def use_technique_and_attack_monster(self, team):
        '''使用秘技并攻击怪物'''
        # 靠近怪物
        auto.press_key("w", 4)

        # 使用秘技
        last_index = None
        for index, (_, count) in enumerate(team, 1):
            if count > 0:
                auto.press_key(str(index))
                time.sleep(1)
                for _ in range(count):
                    auto.press_key(self.hotkey_technique)
                    time.sleep(1)
            elif count == -1:
                last_index = index

        # 切换到开怪角色
        if last_index is not None:
            auto.press_key(str(last_index))
            time.sleep(1)

        # 开怪
        auto.press_key(self.hotkey_technique)
        for _ in range(3):
            auto.press_mouse()
            time.sleep(1)
