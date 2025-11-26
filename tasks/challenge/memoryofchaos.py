import time
from tasks.base.base import Base
from .basechallenge import BaseChallenge
from module.automation.screenshot import Screenshot
from module.screen import screen
from module.automation import auto
from module.config import cfg
from module.logger import log


class MemoryOfChaos(BaseChallenge):
    def __init__(self, team1, team2, level_range=(7, 12), hotkey_technique="e", auto_battle_detect_enable=True) -> None:
        super().__init__("混沌回忆", 36, hotkey_technique, auto_battle_detect_enable)
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

        if not auto.click_element("忘却之庭", "text", max_retries=10, crop=(231.0 / 1920, 420.0 / 1080, 450.0 / 1920, 536.0 / 1080)):
            return False
        time.sleep(1)

        if not auto.find_element(self.name, "text", max_retries=10, crop=(689.0 / 1920, 285.0 / 1080, 970.0 / 1920, 474.0 / 1080), include=True):
            return False
        if self.check_star_in_ocr_results(auto.ocr_result):
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
        auto.mouse_scroll(20, 1, False)
        time.sleep(2)
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

            time.sleep(6)
            screen.wait_for_screen_change('memory_of_chaos')

    def find_level(self, level, max_retries=4):
        '''查找关卡'''
        crop = (540.0 / 1920, 406.0 / 1080, 1156.0 / 1920, 516.0 / 1080)
        window = Screenshot.get_window(cfg.game_title_name)
        _, _, width, height = Screenshot.get_window_region(window)

        for _ in range(max_retries):
            result = auto.find_element(f"{level:02}", "text", max_retries=4, crop=crop, relative=True)
            if result:
                return (result[0][0] + width * crop[0], result[0][1] + height * crop[1])

            # 先向右滚动5次查找，然后向左
            for direction in [-1, 1]:
                for _ in range(15):
                    auto.mouse_scroll(2, direction)
                    time.sleep(6)

                    result = auto.find_element(f"{level:02}", "text", max_retries=4, crop=crop, relative=True)
                    if result:
                        return (result[0][0] + width * crop[0], result[0][1] + height * crop[1])

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

    def check_fight(self, timeout):
        '''检查战斗是否结束'''
        log.info("进入战斗")
        time.sleep(5)

        start_time = time.time()
        while time.time() - start_time < timeout:
            # 整间完成
            if auto.find_element("./assets/images/purefiction/prepare_fight.png", "image", 30000, crop=(0 / 1920, 0 / 1080, 300.0 / 1920, 300.0 / 1080)):
                return True
            elif auto.find_element("./assets/images/forgottenhall/back.png", "image", 0.9):
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
                auto.press_key("v")

            # 判断是否有角色无法战斗
            try:
                crop_list = [
                    (253.0 / 1920, 935.0 / 1080, 100.0 / 1920, 50.0 / 1080),
                    (475.0 / 1920, 937.0 / 1080, 104.0 / 1920, 44.0 / 1080),
                    (707.0 / 1920, 937.0 / 1080, 94.0 / 1920, 48.0 / 1080),
                    (931.0 / 1920, 939.0 / 1080, 94.0 / 1920, 50.0 / 1080)
                ]
                for crop in crop_list:
                    text = auto.get_single_line_text(crop=crop)
                    # 角色无法战斗
                    if text == '0':
                        log.info("检测到角色无法战斗")
                        auto.press_key("esc")
                        break
            except Exception as e:
                log.error(f"角色无法战斗检测失败: {e}")

            time.sleep(2)

        log.error("战斗超时")
        return False

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

                Base.send_notification_with_screenshot(cfg.notify_template['LevelCleared'].format(name=self.name, level=self.max_level))

                auto.press_key("esc")
                time.sleep(1)
            else:
                log.error("领取星琼失败")
                Base.send_notification_with_screenshot(cfg.notify_template['LevelClearedWithIssue'].format(name=self.name, level=self.max_level))
