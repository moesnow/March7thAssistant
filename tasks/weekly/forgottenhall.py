from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.config_manager import config
from managers.logger_manager import logger
from managers.translate_manager import _
from tasks.base.base import Base
import time


class ForgottenHall:
    @staticmethod
    def wait_fight(boss_count, max_recursion):
        logger.info(_("等待战斗"))
        time.sleep(10)

        def check_fight():
            if auto.find_element("./assets/images/forgottenhall/prepare_fight.png", "image", 0.95):
                # 正常
                return 1
            elif auto.find_element("./assets/images/forgottenhall/back.png", "image", 0.95):
                logger.info(_("战斗完成"))
                # 挑战失败
                result = auto.find_element("./assets/images/forgottenhall/again.png", "image", 0.95, max_retries=2)
                if result and max_recursion > 0:
                    # 重新挑战
                    logger.info(_("重新挑战"))
                    auto.click_element("./assets/images/forgottenhall/again.png", "image", 0.95, max_retries=10)
                    auto.click_element("./assets/images/forgottenhall/start.png", "image", 0.8, max_retries=10)
                    ForgottenHall.click_message_box()
                    # 重新挑战整间
                    if ForgottenHall.start_fight(boss_count, max_recursion - 1):
                        return 4  # 挑战失败，重试后成功
                    return 3  # 挑战失败，重试后失败
                else:
                    auto.click_element("./assets/images/forgottenhall/back.png", "image", 0.95, max_retries=2)
                    # 等待返回关卡选择界面
                    if result:
                        return 3  # 挑战失败，无重试次数
                    return 2  # 挑战成功
            return False
        result = auto.retry_with_timeout(check_fight, 30 * 60, 1)
        if not result:
            logger.error(_("战斗超时"))
            raise Exception(_("战斗超时"))
        return result

    @staticmethod
    def start_fight(boss_count, max_recursion=config.forgottenhall_retries):
        logger.debug(_("剩余重试次数:{max_recursion}".format(max_recursion=max_recursion)))
        for i in range(2):
            logger.info(_("进入第{i}间").format(i=i + 1))
            auto.press_key("w", 4)

            # 释放秘技
            last_index = None
            for index, character in enumerate(config.get_value("forgottenhall_team" + str(i + 1))):
                if character[1] > 0:
                    auto.press_key(f"{index+1}")
                    time.sleep(1)
                    for i in range(character[1]):
                        auto.press_key("e")
                        time.sleep(1)
                elif character[1] == -1:
                    last_index = index
            # 设置了末位角色
            if last_index is not None:
                auto.press_key(f"{last_index+1}")
                time.sleep(1)

            for i in range(boss_count):
                logger.info(_("挑战第{i}个boss").format(i=i + 1))

                # 开怪
                auto.press_key("e")
                for i in range(3):
                    auto.press_mouse()

                result = ForgottenHall.wait_fight(boss_count, max_recursion)

                if result == 3:
                    return False
                elif result == 4:
                    return True
            time.sleep(1)
        return True

    @staticmethod
    def click_message_box():
        if auto.find_element("./assets/images/forgottenhall/prepare_fight.png", "image", 0.8, max_retries=20):
            time.sleep(3)
            if auto.click_element("./assets/images/forgottenhall/prepare_fight.png", "image", 0.8, max_retries=10):
                time.sleep(2)

    @staticmethod
    def select_characters(team_config, team_image_path):
        if auto.click_element(team_image_path, "image", 0.8, max_retries=10):
            for character in team_config:
                if not auto.click_element(f"./assets/images/character/{character[0]}.png", "image", 0.8, max_retries=10, scale_range=(0.8, 1.2)):
                    return False
            return True
        return False

    @staticmethod
    def configure_teams():
        if auto.find_element("./assets/images/forgottenhall/team1.png", "image", 0.8, max_retries=10):
            if ForgottenHall.select_characters(config.forgottenhall_team1, "./assets/images/forgottenhall/team1.png"):
                if ForgottenHall.select_characters(config.forgottenhall_team2, "./assets/images/forgottenhall/team2.png"):
                    if auto.click_element("./assets/images/forgottenhall/start.png", "image", 0.8, max_retries=10):
                        return True
        return False

    @staticmethod
    def change_to(number):
        # 先向右滚动4次查找，然后向左
        for direction in [-1, 1]:
            for i in range(4):
                if auto.click_element(number, "text", max_retries=1):
                    return True
                auto.mouse_scroll(2, direction)
                # 等待画面完全静止
                time.sleep(2)

    @staticmethod
    def run():
        # 记录层数
        max_level = 0

        for i in range(config.forgottenhall_level[0], config.forgottenhall_level[1] + 1):
            logger.info(_("开始挑战第{i}层").format(i=i))
            # 进入混沌回忆关卡选择界面
            if not auto.find_element("./assets/images/screen/forgottenhall/memory_of_chaos.png", "image", 0.8, max_retries=10):
                # if not auto.find_element("混沌回忆", "text", max_retries=10):
                logger.error(_("界面不正确，尝试切换到混沌回忆界面"))
                if not screen.change_to('memory_of_chaos'):
                    logger.error(_("切换到混沌回忆界面失败"))
                    break
            # 选择关卡
            if not ForgottenHall.change_to(f"{i:02}"):
                logger.error(_("切换关卡失败"))
                break
            # 选择角色
            if not ForgottenHall.configure_teams():
                logger.error(_("配置队伍失败"))
                break
            # 点击弹出框
            ForgottenHall.click_message_box()
            # 判断关卡BOSS数量
            boss_count = 2 if i in range(1, 6) else 1
            if not ForgottenHall.start_fight(boss_count):
                logger.info(_("挑战失败"))
                break
            logger.info(_("挑战成功"))
            # 记录最高层数
            max_level = i

        if max_level > 0:
            screen.change_to('memory_of_chaos')
            Base.send_notification_with_screenshot(_("🎉混沌回忆已通关{max_level}层🎉").format(max_level=max_level))

    @staticmethod
    def prepare():
        if not screen.change_to('memory_of_chaos'):
            logger.error(_("切换到混沌回忆界面失败"))
            return False

        if auto.find_element("./assets/images/forgottenhall/30.png", "image", 0.8, max_retries=8):
            logger.info(_("混沌回忆未刷新"))
            return False

        # 刷新后打开会出现本期buff的弹窗
        if auto.find_element("./assets/images/base/click_close.png", "image", 0.8):
            # 等待不可点击的动画时间
            time.sleep(2)
            auto.click_element("./assets/images/base/click_close.png", "image", 0.8, max_retries=8)

        ForgottenHall.run()

        screen.change_to('main')
        return True

    @staticmethod
    def start():
        logger.hr(_("准备混沌回忆"), 2)

        if ForgottenHall.prepare():
            config.save_timestamp("forgottenhall_timestamp")
            logger.info(_("混沌回忆完成"))
