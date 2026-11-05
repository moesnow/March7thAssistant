import time
import re
from tasks.base.base import Base
from module.notification.notification import NotificationLevel
from .basechallenge import BaseChallenge
from .stellar import StellarChallenge
from module.automation.screenshot import Screenshot
from module.screen import screen
from module.automation import auto
from module.config import cfg
from module.logger import log
from tasks.base.list_drag import drag_list


class MemoryOfChaos(BaseChallenge):
    def __init__(self, team1, team2, level_range=(7, 12), hotkey_technique="e", auto_battle_detect_enable=True, *, team3=None, stellar_enable=False) -> None:
        super().__init__("混沌回忆", 36, hotkey_technique, auto_battle_detect_enable)
        self.team1 = team1
        self.team2 = team2
        self.level_range = level_range
        self.stellar = StellarChallenge(self, 12, team3, stellar_enable)

    def run(self):
        '''执行挑战'''
        self.stellar.validate_teams()
        log.hr(f"准备{self.name}", 0)
        if self.prepare():
            if self.stellar.enabled:
                self.stellar.run_selected_levels()
            else:
                self.stellar.ensure_mode(False)
                self.start_challenges()
                self.collect_rewards()
        log.hr("完成", 2)

    def prepare(self):
        '''切换场景并判断是否刷新'''
        screen.change_to('guide4')

        if not auto.click_element("忘却之庭", "text", max_retries=10, crop=(231.0 / 1920, 420.0 / 1080, 450.0 / 1920, 536.0 / 1080)):
            return False
        time.sleep(1)

        if not auto.find_element(self.name, "text", max_retries=10, crop=(689.0 / 1920, 285.0 / 1080, 970.0 / 1920, 474.0 / 1080), include=True):
            return False
        # 星启模式改在关卡页判断最高关星数（StellarChallenge._open_highest_level）。
        if not self.stellar.enabled and self.check_star_in_ocr_results(auto.ocr_result):
            self.save_timestamp_into_config()
            return False

        if not auto.click_element("传送", "text", max_retries=10, need_ocr=False):
            return False

        time.sleep(4)
        screen.change_to('memory_of_chaos')

        # 等待刷新后首次打开可能会出现的弹窗过程
        time.sleep(2)
        screen.change_to('memory_of_chaos')

        return True

    def save_timestamp_into_config(self):
        cfg.save_timestamp("forgottenhall_timestamp")

    def start_challenges(self):
        '''查找关卡并判断星数'''
        for level in range(self.level_range[0], self.level_range[1] + 1):
            # 查找关卡
            top_left = self.find_level(level)
            if not top_left:
                log.error(f"查找第{level}层失败")
                return False

            # 判断星数
            stars = self.judge_stars(top_left)
            log.info(f"第{level}层星数{stars}")
            if stars == self.max_star:
                continue

            if not self.start_challenge(level):
                log.error(f"第{level}层挑战失败")
                return False

            time.sleep(6)
            screen.wait_for_screen_change('memory_of_chaos')
        return True

    def find_level(self, level, max_retries=4):
        '''查找关卡'''
        crop = (540.0 / 1920, 406.0 / 1080, 1156.0 / 1920, 516.0 / 1080)
        window = Screenshot.get_window(cfg.game_title_name)
        _, _, width, height = Screenshot.get_window_region(window)

        def positions():
            return {int(text): sum(point[0] for point in box) / len(box)
                    for box, (text, _) in auto.ocr_result if re.fullmatch(r"\d{2}", text)}

        for _ in range(max_retries):
            result = auto.find_element(f"{level:02}", "text", crop=crop, relative=True)
            if result:
                return (result[0][0] + width * crop[0], result[0][1] + height * crop[1])

            visible = positions()
            # 按实际可见关卡决定方向，避免目标在左侧却先拖到最右端。
            earlier = level < min(visible) if visible else level <= 6
            boundaries = 0
            for direction in ([1, -1] if earlier else [-1, 1]):
                unchanged = 0
                for _ in range(15):
                    before = positions()
                    start, end = (1785 / 1920, 820 / 1080), (415 / 1920, 820 / 1080)
                    if direction == 1:
                        start, end = end, start
                    if not drag_list(auto, start, end, crop=crop, duration=0.4, end_pause=0.25,
                                     settle=0.05, poll_interval=0.1, text_pattern=r"\d{2}"):
                        return False

                    result = auto.find_element(f"{level:02}", "text", crop=crop, relative=True,
                                               take_screenshot=False, need_ocr=False)
                    if result:
                        return (result[0][0] + width * crop[0], result[0][1] + height * crop[1])
                    after = positions()
                    at_edge = bool(before) and before.keys() == after.keys() and all(abs(before[key] - after[key]) <= 2 for key in before)
                    unchanged = unchanged + 1 if at_edge else 0
                    if unchanged >= 2:
                        boundaries += 1
                        break
            if boundaries == 2:
                return False

        return False

    def judge_stars(self, top_left):
        '''判断星数'''
        window = Screenshot.get_window(cfg.game_title_name)
        _, _, width, height = Screenshot.get_window_region(window)
        crop = (top_left[0] / width, top_left[1] / height, 120 / 1920, 120 / 1080)
        count = auto.find_element("./assets/images/forgottenhall/star.png", "image_count", 0.6, crop=crop, pixel_bgr=[112, 200, 255])
        return count if count is not None and 0 <= count <= 3 else None

    def start_challenge(self, level):
        '''开始挑战'''
        # 每个关卡挑战2次，status 用于判断是否交换配队
        for status in [True, False]:
            log.info(f"开始挑战第{level:02}层")

            if not auto.click_element(f"{level:02}", "text", max_retries=20, crop=(540.0 / 1920, 406.0 / 1080, 1156.0 / 1920, 516.0 / 1080)):
                log.error("点击关卡失败")
                return False

            # 准备关卡
            if not self.prepare_level(status):
                log.error("配置队伍失败")
                return False

            if not self.start_level():
                log.error("开始关卡失败")
                return False

            # 开始战斗
            if self.start_battle(status):
                self.max_level = level
                return True
            else:
                log.error("战斗失败")

        return False

    def prepare_level(self, status):
        '''配置队伍'''
        if auto.find_element("./assets/images/forgottenhall/team1.png", "image", 0.8, max_retries=10, crop=(592.0 / 1920, 556.0 / 1080, 256.0 / 1920, 424.0 / 1080)):
            if status:
                auto.click_element("./assets/images/forgottenhall/reset.png", "image", 0.8, max_retries=10, crop=(617.0 / 1920, 432.0 / 1080, 1294.0 / 1920, 510.0 / 1080))
                time.sleep(0.5)
                if not self.select_characters(self.team1, "./assets/images/forgottenhall/team1.png"):
                    return False
                if not self.select_characters(self.team2, "./assets/images/forgottenhall/team2.png"):
                    return False
                return True
            else:
                auto.click_element("./assets/images/forgottenhall/switch.png", "image", 0.8, max_retries=10, crop=(617.0 / 1920, 432.0 / 1080, 1294.0 / 1920, 510.0 / 1080))
                time.sleep(0.5)
                return True
        return False

    def start_level(self):
        '''开始关卡'''
        if auto.click_element("./assets/images/forgottenhall/start.png", "image", 0.8, max_retries=10, crop=(1546 / 1920, 962 / 1080, 343 / 1920, 62 / 1080)):
            self.click_message_box()
            return True
        return False

    def start_battle(self, status=True):
        '''开始战斗'''
        for i in [1, 2]:
            log.info(f"进入第{i}间")
            self.use_technique_and_attack_monster(getattr(self, f"team{i if status else 3 - i}"))

            if self.check_fight(30 * 60):
                continue
            else:
                return False

        return True

    def check_fight(self, timeout, *, final=False):
        '''检查战斗是否结束'''
        log.info("进入战斗")
        time.sleep(5)

        start_time = time.monotonic()
        while time.monotonic() - start_time < timeout:
            # 星启最后一个节点等待结算返回入口，未打满也算完成。
            if final and (auto.find_element("返回忘却之庭", "text", crop=(0.25, 0.75, 0.5, 0.25), include=True)
                          or auto.find_element("./assets/images/forgottenhall/back.png", "image", 0.9)):
                time.sleep(2)
                # 与前两个节点相同，以结算标题中的“失败”判定挑战失败，失败不能记为通关。
                return not auto.find_element("失败", "text", crop=(0.3, 0.15, 0.4, 0.3), include=True)
            # 整间完成
            elif not final and auto.find_element("./assets/images/purefiction/prepare_fight.png", "image", 200000, crop=(0 / 1920, 0 / 1080, 300.0 / 1920, 300.0 / 1080)):
                return True
            elif not final and auto.find_element("./assets/images/forgottenhall/back.png", "image", 0.9):
                time.sleep(2)
                # 挑战失败
                if auto.find_element("./assets/images/forgottenhall/again.png", "image", 0.9):
                    auto.click_element("./assets/images/forgottenhall/back.png", "image", 0.9)
                    return False
                # 角色无法战斗
                elif auto.find_element("./assets/images/forgottenhall/pause.png", "image", 0.9):
                    auto.click_element("./assets/images/forgottenhall/back.png", "image", 0.9)
                    time.sleep(2)
                    auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10)
                    return False
                # 整层完成
                else:
                    auto.click_element("./assets/images/forgottenhall/back.png", "image", 0.9)
                    return True
            elif self.auto_battle_detect_enable and auto.find_element("./assets/images/share/base/not_auto.png", "image", 0.9, crop=(0.0 / 1920, 903.0 / 1080, 144.0 / 1920, 120.0 / 1080)):
                log.info("尝试开启自动战斗")
                auto.press_key(cfg.get_value("hotkey_auto_battle", "v"))

            time.sleep(2)

        log.error("战斗超时")
        if final:
            raise RuntimeError("等待混沌回忆星启最终结算超时")
        return False

    def return_to_stage_list(self):
        '''退出结算并确认已回到关卡列表'''
        for _ in range(5):
            if screen.check_screen('memory_of_chaos'):
                return
            # 点击可能只跳过结算动画，必须再次确认关卡列表。
            if not auto.click_element("返回忘却之庭", "text", crop=(0.25, 0.75, 0.5, 0.25), include=True):
                auto.click_element("./assets/images/forgottenhall/back.png", "image", 0.9)
            time.sleep(2)
        if screen.check_screen('memory_of_chaos'):
            return
        raise RuntimeError("结算后返回混沌回忆失败")

    def collect_rewards(self):
        '''领取奖励'''
        if self.max_level > 0:
            self.save_timestamp_into_config()
            time.sleep(2)
            screen.wait_for_screen_change('memory_of_chaos')
            # 领取星琼
            if auto.click_element("./assets/images/share/base/RedExclamationMark.png", "image", 0.9, max_retries=5, crop=(1775.0 / 1920, 902.0 / 1080, 116.0 / 1920, 110.0 / 1080)):
                time.sleep(1)

                while auto.click_element("./assets/images/forgottenhall/receive.png", "image", 0.9, crop=(1081.0 / 1920, 171.0 / 1080, 500.0 / 1920, 736.0 / 1080)):
                    auto.click_element("./assets/images/zh_CN/base/click_close.png", "image", 0.9, max_retries=10)
                    time.sleep(1)

                Base.send_notification_with_screenshot(cfg.notify_template['LevelCleared'].format(name=self.name, level=self.max_level), NotificationLevel.ALL)

                auto.press_key("esc")
                time.sleep(1)
            else:
                log.error("领取星琼失败")
                Base.send_notification_with_screenshot(cfg.notify_template['LevelClearedWithIssue'].format(name=self.name, level=self.max_level), NotificationLevel.ERROR)
