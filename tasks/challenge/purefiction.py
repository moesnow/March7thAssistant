import time
from tasks.base.base import Base
from module.notification.notification import NotificationLevel
from .basechallenge import BaseChallenge
from module.automation.screenshot import Screenshot
from module.screen import screen
from module.automation import auto
from module.config import cfg
from module.logger import log


class PureFiction(BaseChallenge):
    def __init__(self, team1, team2, level_range=(1, 4), hotkey_technique="e", auto_battle_detect_enable=True) -> None:
        super().__init__("虚构叙事", 12, hotkey_technique, auto_battle_detect_enable)
        self.team1 = team1
        self.team2 = team2
        self.level_range = level_range

    def run(self):
        '''执行挑战'''
        log.hr(f"准备{self.name}", 0)
        if self.prepare():
            self.start_challenges()
            self.collect_rewards()
        log.hr("完成", 2)

    def prepare(self):
        '''切换场景并判断是否刷新'''
        screen.change_to('guide4')

        if not auto.click_element(self.name, "text", max_retries=10, crop=(231.0 / 1920, 420.0 / 1080, 450.0 / 1920, 536.0 / 1080)):
            return False
        time.sleep(1)

        if not auto.find_element(self.name, "text", max_retries=10, crop=(689.0 / 1920, 285.0 / 1080, 970.0 / 1920, 474.0 / 1080), include=True):
            return False
        if self.check_star_in_ocr_results(auto.ocr_result):
            self.save_timestamp_into_config()
            return False

        if not auto.click_element("传送", "text", max_retries=10, need_ocr=False):
            return False

        if not auto.click_element(self.name, "text", max_retries=20, include=True, action="move", crop=(0.0 / 1920, 1.0 / 1080, 552.0 / 1920, 212.0 / 1080)):
            return False

        # 刷新后打开会出现本期buff的弹窗
        time.sleep(2)
        if auto.click_element("./assets/images/purefiction/start_story.png", "image", 0.7):
            auto.click_element(self.name, "text", max_retries=10, include=True, action="move", crop=(0.0 / 1920, 1.0 / 1080, 552.0 / 1920, 212.0 / 1080))

        # 刷新后打开会出现快速解锁弹窗
        time.sleep(2)
        if auto.find_element("选择最高解锁关卡", "text", include=True):
            result = auto.find_element("03", "text")
            auto.click_element_with_pos((result[0], result[0]))

        return True

    def save_timestamp_into_config(self):
        cfg.save_timestamp("purefiction_timestamp")

    def start_challenges(self):
        '''查找关卡并判断星数'''
        for level in range(self.level_range[0], self.level_range[1] + 1):
            # 查找关卡
            top_left = self.find_level(level)
            if not top_left:
                log.error(f"查找第{level}层失败")
                break

            # 判断星数
            stars = self.judge_stars(top_left)
            log.info(f"第{level}层星数{stars}")
            if stars == self.max_star:
                continue

            if not self.start_challenge(level):
                log.error(f"第{level}层挑战失败")
                break

            time.sleep(2)
            screen.wait_for_screen_change('purefiction')

    def find_level(self, level, max_retries=4):
        '''查找关卡'''
        crop = (331.0 / 1920, 97.0 / 1080, 1562.0 / 1920, 798.0 / 1080)
        window = Screenshot.get_window(cfg.game_title_name)
        _, _, width, height = Screenshot.get_window_region(window)

        for _ in range(max_retries):
            result = auto.find_element(f"{level:02}", "text", max_retries=4, crop=crop, relative=True)
            if result:
                return (result[0][0] + width * crop[0], result[0][1] + height * crop[1])

        return False

    def judge_stars(self, top_left):
        '''判断星数'''
        window = Screenshot.get_window(cfg.game_title_name)
        _, _, width, height = Screenshot.get_window_region(window)
        crop = (top_left[0] / width, top_left[1] / height, 120 / 1920, 120 / 1080)
        count = auto.find_element("./assets/images/purefiction/star.png", "image_count", 0.6, crop=crop, pixel_bgr=[95, 198, 255])
        return count if count is not None and 0 <= count <= 3 else None

    def start_challenge(self, level):
        '''开始挑战'''
        # 每个关卡挑战2次，status 用于判断是否交换配队
        for status in [True, False]:
            log.info(f"开始挑战第{level:02}层")

            if not auto.click_element(f"{level:02}", "text", max_retries=20, crop=(331.0 / 1920, 97.0 / 1080, 1562.0 / 1920, 798.0 / 1080)):
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
                if not self.select_buff():
                    return False
                return True
            else:
                auto.click_element("./assets/images/forgottenhall/switch.png", "image", 0.8, max_retries=10, crop=(617.0 / 1920, 432.0 / 1080, 1294.0 / 1920, 510.0 / 1080))
                time.sleep(0.5)
                return True
        return False

    def select_buff(self):
        '''选择增益效果'''
        if auto.click_element("./assets/images/purefiction/plus.png", "image", 0.8, max_retries=10, crop=(1661.0 / 1920, 522.0 / 1080, 218.0 / 1920, 274.0 / 1080)):
            if auto.click_element("./assets/images/purefiction/choose.png", "image", 0.8, max_retries=10):
                if auto.click_element("./assets/images/purefiction/confirm.png", "image", 0.8, max_retries=10):
                    if auto.click_element("./assets/images/purefiction/plus.png", "image", 0.8, max_retries=10, crop=(1659.0 / 1920, 808.0 / 1080, 238.0 / 1920, 140.0 / 1080)):
                        if auto.click_element("./assets/images/purefiction/choose.png", "image", 0.8, max_retries=10):
                            auto.click_element("./assets/images/purefiction/confirm.png", "image", 0.8, max_retries=10)
                            return True
        return False

    def start_level(self):
        '''开始关卡'''
        if auto.click_element("./assets/images/purefiction/start.png", "image", 0.8, max_retries=10, crop=(1546 / 1920, 962 / 1080, 343 / 1920, 62 / 1080)):
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

    def check_fight(self, timeout):
        '''检查战斗是否结束'''
        log.info("进入战斗")
        time.sleep(5)

        start_time = time.monotonic()
        while time.monotonic() - start_time < timeout:
            # 整间完成
            if auto.find_element("./assets/images/purefiction/prepare_fight.png", "image", 50000, crop=(0 / 1920, 0 / 1080, 300.0 / 1920, 300.0 / 1080)):
                return True
            elif auto.find_element("./assets/images/purefiction/back.png", "image", 0.9):
                # 挑战失败
                if auto.find_element("./assets/images/purefiction/fail.png", "image", 0.9):
                    auto.click_element("./assets/images/purefiction/back.png", "image", 0.9)
                    return False
                # 整层完成
                else:
                    auto.click_element("./assets/images/purefiction/back.png", "image", 0.9)
                    return True
            elif self.auto_battle_detect_enable and auto.find_element("./assets/images/share/base/not_auto.png", "image", 0.9, crop=(0.0 / 1920, 903.0 / 1080, 144.0 / 1920, 120.0 / 1080)):
                log.info("尝试开启自动战斗")
                auto.press_key("v")

            time.sleep(2)

        log.error("战斗超时")
        return False

    def collect_rewards(self):
        '''领取奖励'''
        if self.max_level > 0:
            self.save_timestamp_into_config()
            time.sleep(2)
            screen.wait_for_screen_change('purefiction')
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
