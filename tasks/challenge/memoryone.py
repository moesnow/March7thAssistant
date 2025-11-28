import time
from .basechallenge import BaseChallenge
from module.screen import screen
from module.automation import auto
from module.logger import log


class MemoryOne(BaseChallenge):
    def __init__(self, team1, hotkey_technique="e", auto_battle_detect_enable=True) -> None:
        super().__init__("回忆一", None, hotkey_technique, auto_battle_detect_enable)
        self.team1 = team1
        self.success = True

    def run(self, count: int = 1):
        '''
        执行挑战

        count: 挑战次数
        '''
        log.hr(f"准备{self.name}", 0)
        for _ in range(count):
            self.prepare()
            if not self.start_challenges():
                break
        log.hr("完成", 2)
        return True if self.success else False

    def prepare(self):
        '''切换场景并判断是否刷新'''
        screen.change_to('memory')

    def start_challenges(self):
        '''查找关卡并判断星数'''
        auto.mouse_scroll(30, 1, False)
        time.sleep(2)
        level = 1

        if not self.start_challenge(level):
            log.error(f"第{level}层挑战失败")
            self.success = False
            return False

        time.sleep(2)
        screen.wait_for_screen_change('memory')

        return True

    def start_challenge(self, level):
        '''开始挑战'''
        log.info(f"开始挑战第{level:02}层")

        if not auto.click_element(f"{level:02}", "text", max_retries=20, crop=(540.0 / 1920, 406.0 / 1080, 1156.0 / 1920, 516.0 / 1080)):
            log.error("点击关卡失败")
            return False

        # 准备关卡
        if not self.prepare_level():
            log.error("配置队伍失败")
            return False

        if not self.start_level():
            log.error("开始关卡失败")
            return False

        # 开始战斗
        if self.start_battle():
            return True
        else:
            log.error("战斗失败")

        return False

    def prepare_level(self):
        '''配置队伍'''
        if auto.find_element("./assets/images/forgottenhall/team1.png", "image", 0.8, max_retries=10, crop=(592.0 / 1920, 556.0 / 1080, 256.0 / 1920, 424.0 / 1080)):
            auto.click_element("./assets/images/forgottenhall/reset.png", "image", 0.8, max_retries=10, crop=(617.0 / 1920, 432.0 / 1080, 1294.0 / 1920, 510.0 / 1080))
            time.sleep(0.5)
            if not self.select_characters(self.team1, "./assets/images/forgottenhall/team1.png"):
                return False
            return True
        return False

    def start_level(self):
        '''开始关卡'''
        if auto.click_element("./assets/images/forgottenhall/start2.png", "image", 0.8, max_retries=10, crop=(1546 / 1920, 962 / 1080, 343 / 1920, 62 / 1080)):
            self.click_message_box()
            return True
        return False

    def start_battle(self):
        '''开始战斗'''
        self.use_technique_and_attack_monster(self.team1)

        if self.check_fight(30 * 60):
            return True
        else:
            return False

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
                # 挑战失败
                if auto.find_element("./assets/images/forgottenhall/again.png", "image", 0.9):
                    auto.click_element("./assets/images/forgottenhall/back.png", "image", 0.9)
                    return False
                # 整层完成
                else:
                    auto.click_element("./assets/images/forgottenhall/back.png", "image", 0.9)
                    return True
            elif self.auto_battle_detect_enable and auto.find_element("./assets/images/share/base/not_auto.png", "image", 0.9, crop=(0.0 / 1920, 903.0 / 1080, 144.0 / 1920, 120.0 / 1080)):
                log.info("尝试开启自动战斗")
                auto.press_key("v")

            time.sleep(2)

        log.error("战斗超时")
        return False
