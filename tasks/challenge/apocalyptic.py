import time
from tasks.base.base import Base
from module.notification.notification import NotificationLevel
from .basechallenge import BaseChallenge
from .stellar import StellarChallenge
from module.automation.screenshot import Screenshot
from module.screen import screen
from module.automation import auto
from module.config import cfg
from module.logger import log


class Apocalyptic(BaseChallenge):
    def __init__(self, team1, team2, level_range=(1, 4), hotkey_technique="e", auto_battle_detect_enable=True, *, team3=None, stellar_enable=False) -> None:
        super().__init__("末日幻影", 12, hotkey_technique, auto_battle_detect_enable)
        self.team1 = team1
        self.team2 = team2
        self.level_range = level_range
        self.stellar = StellarChallenge(self, 4, team3, stellar_enable)

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

        if not auto.click_element("日幻影", "text", max_retries=10, crop=(274.0 / 1920, 419.0 / 1080, (670.0) / 1920, (419.0 + 322.0) / 1080), include=True):
            return False
        time.sleep(1)

        if not auto.find_element("日幻影", "text", max_retries=10, crop=(689.0 / 1920, 285.0 / 1080, 970.0 / 1920, 474.0 / 1080), include=True):
            return False
        if self.check_star_in_ocr_results(auto.ocr_result):
            self.save_timestamp_into_config()
            return False
        time.sleep(1)
        if not auto.click_element("传送", "text", max_retries=10, need_ocr=False):
            return False
        # 刷新后打开会出现本期buff的弹窗
        time.sleep(2)
        if auto.find_element("已更新", "text", max_retries=10, crop=(0, 0, 1, 1), include=True):
            auto.click_element("前往挑战", "text", max_retries=10, crop=(0, 0, 1, 1), include=True)
            # log.info("当期buff页面,进入游戏 text")
            time.sleep(2)

        if auto.find_element("选择最高解锁关卡", "text", include=True):
            # log.info(f"之前打过，最高记录部分")
            result = auto.find_element("03", "text")
            if result:
                auto.click_element_with_pos((result[0], result[0]))
            time.sleep(2)
        if not auto.click_element("日幻影", "text", max_retries=20, include=True, action="move", crop=(0.0 / 1920, 1.0 / 1080, 552.0 / 1920, 212.0 / 1080)):
            return False
        return True

    def save_timestamp_into_config(self):
        cfg.save_timestamp("apocalyptic_timestamp")

    def start_challenges(self):
        '''查找关卡并判断星数'''
        for level in range(self.level_range[0], self.level_range[1] + 1):
            # 查找关卡
            # log.info(f"查找level:{level}")
            top_left = self.find_level(level)
            if not top_left:
                log.error(f"查找第{level}层失败")
                return False
            # log.info(f"level:{level} | top_left:{top_left}")
            # 判断星数
            stars = self.judge_stars(top_left)
            log.info(f"第{level}层星数{stars}")
            if stars == self.max_star:
                auto.click_element(f"{level:02}", "text", max_retries=20, crop=(330.0 / 1920, 90.0 / 1080, 1562.0 / 1920, 1060.0 / 1080), include=True)
                time.sleep(0.5)
                continue

            if not self.start_challenge(level):
                log.error(f"第{level}层挑战失败")
                return False
            time.sleep(3)
            if auto.find_element("3星通关所有", 'text', include=True):
                auto.click_element("确认", 'text', max_retries=10, include=True)
                auto.press_key("esc")
            time.sleep(2)

            screen.wait_for_screen_change('apocalyptic')
        return True

    def find_level(self, level, max_retries=4):
        '''查找关卡'''
        crop = (330.0 / 1920, 90.0 / 1080, 1562.0 / 1920, 1060.0 / 1080)
        # crop = (331.0 / 1920, 97.0 / 1080, 1562.0 / 1920, 798.0 / 1080)
        window = Screenshot.get_window(cfg.game_title_name)
        _, _, width, height = Screenshot.get_window_region(window)

        for _ in range(max_retries):
            result = auto.find_element(f"{level:02}", "text", max_retries=4, crop=crop, relative=True, include=True)
            if result:
                return (result[0][0] + width * crop[0], result[0][1] + height * crop[1])

        return False

    def find_node(self, string, max_retries=4):
        '''查找结点'''
        crop = (755.0 / 1920, 203.0 / 1080, 1014.0 / 1920, 544.0 / 1080)
        window = Screenshot.get_window(cfg.game_title_name)
        _, _, width, height = Screenshot.get_window_region(window)

        for _ in range(max_retries):
            result = auto.find_element(f"{string}", "text", max_retries=4, crop=crop, relative=True, include=True)
            if result:
                return (result[0][0] + width * crop[0], result[0][1] + height * crop[1])

        return False

    def judge_stars(self, top_left):
        '''判断星数'''
        window = Screenshot.get_window(cfg.game_title_name)
        _, _, width, height = Screenshot.get_window_region(window)
        crop = (top_left[0] / width, top_left[1] / height, 278.0 / 1920, 123.0 / 1080)
        count = auto.find_element("./assets/images/purefiction/star.png", "image_count", 0.5, crop=crop, pixel_bgr=[95, 198, 255])
        # log.info(f"star count:{count}")
        return count if count is not None and 0 <= count <= 3 else None

    def start_challenge(self, level):
        '''开始挑战'''
        # 每个关卡挑战2次，status 用于判断是否交换配队
        for status in [True, False]:
            log.info(f"开始挑战第{level:02}层")
            if not self._open_regular_teams(level):
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
                log.info("战斗完成")
                return True
            else:
                log.error("战斗失败")

        return False

    def _open_regular_teams(self, level):
        '''选中普通关卡后，从主页或节点详情进入两队编队'''
        if not auto.click_element(f"{level:02}", "text", max_retries=5,
                                  crop=(0.20, 0.87, 0.60, 0.06), include=True):
            log.error("点击关卡失败")
            return False
        time.sleep(1)
        for _ in range(10):
            if auto.find_element("角色列表", "text", crop=(0, 0.10, 0.30, 0.15), include=False):
                return True
            # 未挑战关卡的“前往挑战”位于主页下方中央。
            opened = auto.click_element("前往挑战", "text",
                                        crop=(0.35, 0.72, 0.30, 0.12), include=False)
            if not opened:
                # 已挑战关卡可能从右侧“更换编队”进入，或需先打开节点详情。
                opened = auto.click_element("更换编队", "text",
                                            crop=(0.80, 0.64, 0.20, 0.20), include=False)
                if not opened:
                    if auto.click_element(["节点一", "节点—", "节点二"], "text",
                                          crop=(0.20, 0.74, 0.60, 0.08), include=False):
                        time.sleep(1)
                        continue
                    opened = auto.click_element("前往挑战", "text",
                                                crop=(0.80, 0.64, 0.20, 0.30), include=False)
            if opened:
                # 普通关入口仍需依次经过说明页和编队入口，不能直接开始选人。
                for button in ("下一步", "前往编队"):
                    if not auto.click_element(button, "text", max_retries=20,
                                              crop=(0, 0, 1, 1), include=True):
                        log.error(f"末日幻影普通关点击{button}失败")
                        return False
                    time.sleep(1)
                return True
            time.sleep(1)
        log.error("未进入末日幻影普通关两队编队界面")
        return False

    def prepare_level(self, status):
        '''配置队伍'''
        # if auto.find_element("./assets/images/forgottenhall/team1.png", "image", 0.8, max_retries=10, crop=(592.0 / 1920, 556.0 / 1080, 256.0 / 1920, 424.0 / 1080)):
        if auto.find_element("节点一", "text", max_retries=20, crop=(963.0 / 1920, 209.0 / 1080, 798.0 / 1920, 252.0 / 1080), include=True):
            if status:
                auto.click_element("./assets/images/forgottenhall/reset.png", "image", 0.8, max_retries=10, crop=(1280.0 / 1920, 115.0 / 1080, 215.0 / 1920, 59.0 / 1080))
                time.sleep(0.5)
                if not self.select_characters(self.team1, "team1"):
                    return False
                if not self.select_characters(self.team2, "team2"):
                    return False
                if not self.select_buff():
                    log.error("选择buff失败")
                    return False
                return True
            else:
                auto.click_element("./assets/images/forgottenhall/switch.png", "image", 0.8, max_retries=10, crop=(617.0 / 1920, 432.0 / 1080, 1294.0 / 1920, 510.0 / 1080))
                time.sleep(0.5)
                return True
        return False

    def select_characters(self, team_config, team_name):
        '''选择角色'''
        # 切换队伍
        if "team1" in team_name:
            top_left = self.find_node("节点一")
        else:
            top_left = self.find_node("节点二")
        if not top_left:
            log.error(f"没有找到{team_name}对应的节点")
            return False
        # log.info(top_left)
        time.sleep(0.5)
        if auto.click_element('./assets/images/apocalyptic/team.png', "image", 0.5, max_retries=20, crop=(top_left[0] / 1920, top_left[1] / 1080, 792.0 / 1920, 254.0 / 1080)):
            # 列表已打开，复用局部识别、刷新截图和列表内滚动，避免定位到敌人等级。
            if not BaseChallenge.select_characters(self, team_config, None, switch_team=False):
                return False
            auto.click_element("节点一", "text", max_retries=20, crop=(963.0 / 1920, 209.0 / 1080, 798.0 / 1920, 252.0 / 1080), include=True)
            return True
        return False

    def select_buff(self):
        '''选择增益效果'''
        top_left = self.find_node("节点一")
        if auto.click_element("./assets/images/purefiction/plus.png", "image", 0.8, max_retries=10, crop=(top_left[0] / 1920, top_left[1] / 1080, 792.0 / 1920, 254.0 / 1080)):
            if auto.click_element("./assets/images/purefiction/choose.png", "image", 0.8, max_retries=10):
                if auto.click_element("./assets/images/purefiction/confirm.png", "image", 0.8, max_retries=10):
                    top_left = self.find_node("节点二")
                    if auto.click_element("./assets/images/purefiction/plus.png", "image", 0.8, max_retries=10, crop=(top_left[0] / 1920, top_left[1] / 1080, 792.0 / 1920, 254.0 / 1080)):
                        if auto.click_element("./assets/images/purefiction/choose.png", "image", 0.8, max_retries=10):
                            auto.click_element("./assets/images/purefiction/confirm.png", "image", 0.8, max_retries=10)
                            return True
        return False

    def start_level(self):
        '''开始关卡'''
        # 新版编队先确认，再回到节点详情点击前往挑战；旧版可直接前往挑战。
        if auto.click_element("确认", "text", crop=(0.77, 0.87, 0.22, 0.08), include=False):
            time.sleep(1)
        # if auto.click_element("./assets/images/purefiction/start.png", "image", 0.8, max_retries=10, crop=(1546 / 1920, 962 / 1080, 343 / 1920, 62 / 1080)):
        if auto.click_element(f"前往挑战", "text", max_retries=20, crop=(0, 0, 1, 1), include=True):
            if auto.find_element("./assets/images/apocalyptic/warning.png", "image", max_retries=10, threshold=0.9):
                auto.click_element(f"确认", "text", max_retries=20, crop=(0, 0, 1, 1), include=True)
            log.info(f"开始挑战")
            self.click_message_box()
            return True
        return False

    def start_battle(self, status=True):
        '''开始战斗'''
        for i in [1, 2]:
            log.info(f"进入第{i}间")
            self.use_technique_and_attack_monster(getattr(self, f"team{i if status else 3 - i}"))

            if self.check_fight(30 * 60):
                time.sleep(0.5)
                if i == 1:
                    self.click_message_box()
                continue
            else:
                return False

        return True

    def check_fight(self, timeout):
        '''检查战斗是否结束'''
        time.sleep(5)
        start_time = time.monotonic()
        while time.monotonic() - start_time < timeout:
            # 一节点完成
            if auto.find_element("./assets/images/apocalyptic/next_node.png", "image", 0.9):
                # 挑战失败
                if auto.find_element("./assets/images/purefiction/fail.png", "image", 0.9):
                    auto.click_element("./assets/images/apocalyptic/back.png", "image", 0.8, 10)
                    return False
                # 前往下一节点
                else:
                    auto.click_element("./assets/images/apocalyptic/next_node.png", "image", 0.9)
                    return True
            elif auto.find_element("./assets/images/apocalyptic/back.png", "image", 0.8, 10):
                # 挑战失败
                if auto.find_element("./assets/images/purefiction/fail.png", "image", 0.9):
                    auto.click_element("./assets/images/apocalyptic/back.png", "image", 0.8, 10)
                    return False
                else:
                    auto.click_element("挑战结束", "text", max_retries=10, crop=(0, 0, 1, 1), include=True)
                    time.sleep(2)
                    if auto.click_element("./assets/images/apocalyptic/back.png", "image", 0.8, 10):
                        return True
                    else:
                        return False
            elif self.auto_battle_detect_enable and auto.find_element("./assets/images/share/base/not_auto.png", "image", 0.8, crop=(0.0 / 1920, 903.0 / 1080, 144.0 / 1920, 120.0 / 1080)):
                log.info("尝试开启自动战斗")
                auto.press_key(cfg.get_value("hotkey_auto_battle", "v"))

            time.sleep(2)

        log.error("战斗超时")
        return False

    def click_message_box(self):
        '''等待游戏加载并点击弹窗'''
        if auto.find_element("处关闭", "text", max_retries=10, crop=(855.0 / 1920, 784.0 / 1080, 211.0 / 1920, 41.0 / 1080), include=True):            # 关闭弹窗
            auto.press_key("esc")
            time.sleep(1)
        else:
            log.error(f"click error")

    def return_to_stage_list(self):
        '''点击结算返回按钮，回到末日幻影主页'''
        for _ in range(5):
            if screen.check_screen('apocalyptic'):
                return
            auto.click_element("返回末日幻影", "text", crop=(0.5, 0.8, 0.3, 0.12), include=False)
            time.sleep(2)
        if not screen.check_screen('apocalyptic'):
            raise RuntimeError("结算后返回末日幻影失败")

    def collect_rewards(self):
        '''领取奖励'''
        # 星启结束后也可领取之前获得的奖励，零分结算不能记为本次通关。
        if self.max_level <= 0 and not (self.stellar.enabled and self.stellar.result is not None):
            return
        if self.max_level > 0:
            self.save_timestamp_into_config()
        time.sleep(2)
        screen.wait_for_screen_change('apocalyptic')
        # 领取星琼
        if auto.click_element("./assets/images/share/base/RedExclamationMark.png", "image", 0.9, max_retries=5, crop=(24.0 / 1920, 769.0 / 1080, 221.0 / 1920, 138.0 / 1080)):
            time.sleep(1)

            while auto.click_element("./assets/images/forgottenhall/receive.png", "image", 0.9, crop=(1081.0 / 1920, 171.0 / 1080, 500.0 / 1920, 736.0 / 1080)):
                auto.click_element("./assets/images/zh_CN/base/click_close.png", "image", 0.9, max_retries=10)
                time.sleep(1)

            if self.max_level > 0:
                Base.send_notification_with_screenshot(cfg.notify_template['LevelCleared'].format(name=self.name, level=self.max_level), NotificationLevel.ALL)
            else:
                log.info("末日幻影奖励领取完成")

            auto.press_key("esc")
            time.sleep(1)
        elif self.stellar.enabled:
            log.info("末日幻影没有发现可领取的奖励")
        else:
            log.error("领取星琼失败")
            Base.send_notification_with_screenshot(cfg.notify_template['LevelClearedWithIssue'].format(name=self.name, level=self.max_level), NotificationLevel.ERROR)
