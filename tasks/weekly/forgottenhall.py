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
    def change_to(number):
        for i in range(4):
            if auto.click_element(number, "text", max_retries=1):
                return True
            auto.mouse_scroll(2, -1)
            time.sleep(2)
        for i in range(4):
            if auto.click_element(number, "text", max_retries=1):
                return True
            auto.mouse_scroll(2, 1)
            time.sleep(2)

    @staticmethod
    def select_character():
        auto.find_element("./assets/images/forgottenhall/team1.png", "image", 0.8, max_retries=10)
        auto.click_element("./assets/images/forgottenhall/team1.png", "image", 0.8, max_retries=10)
        for character in config.forgottenhall_team1:
            auto.click_element("./assets/images/character/" + character[0] + ".png", "image", 0.8, max_retries=1, scale_range=(0.8, 1.2))
        auto.click_element("./assets/images/forgottenhall/team2.png", "image", 0.8, max_retries=10)
        for character in config.forgottenhall_team2:
            auto.click_element("./assets/images/character/" + character[0] + ".png", "image", 0.8, max_retries=1, scale_range=(0.8, 1.2))
        auto.click_element("./assets/images/forgottenhall/start.png", "image", 0.8, max_retries=10)

    @staticmethod
    def click_message_box():
        auto.find_element("./assets/images/forgottenhall/prepare_fight.png", "image", 0.8, max_retries=20)
        time.sleep(2)
        auto.click_element("./assets/images/forgottenhall/prepare_fight.png", "image", 0.8, max_retries=10)
        time.sleep(1)

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
                if character[1] == -1:
                    last_index = index
            if last_index is not None:
                auto.press_key(f"{last_index+1}")
                time.sleep(1)

            for i in range(boss_count):
                logger.info(_("挑战第{i}个boss").format(i=i + 1))

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
    def start():
        if not config.forgottenhall_enable:
            logger.info(_("忘却之庭未开启"))
            return False
        logger.hr(_("准备混沌回忆"), 2)
        screen.change_to('memory_of_chaos')
        if not auto.find_element("./assets/images/forgottenhall/30.png", "image", 0.8, max_retries=8):
            if auto.find_element("./assets/images/base/click_close.png", "image", 0.9):
                time.sleep(1)
                auto.click_element("./assets/images/base/click_close.png", "image", 0.9, max_retries=4)
            max_level = 0
            for i in range(config.forgottenhall_level[0], config.forgottenhall_level[1] + 1):
                logger.info(_("开始挑战第{i}层").format(i=i))
                # 进入混沌回忆
                if not auto.find_element("混沌回忆", "text", max_retries=10):
                    logger.error(_("界面不正确，停止挑战"))
                    break
                # 选择关卡
                if not ForgottenHall.change_to(f"{i:02}"):
                    logger.warning(_("切换到关卡失败"))
                    break
                # 选择角色
                ForgottenHall.select_character()
                # 点击弹出框
                ForgottenHall.click_message_box()
                # 战斗
                if i in range(1, 6):
                    boss_count = 2
                else:
                    boss_count = 1
                # 本层挑战成功
                if not ForgottenHall.start_fight(boss_count):
                    logger.info(_("挑战失败"))
                    break
                logger.info(_("挑战成功"))
                max_level = i

            auto.find_element("./assets/images/screen/forgottenhall/memory_of_chaos.png", "image", 0.9, max_retries=8)
            if max_level > 0:
                Base.send_notification_with_screenshot(_("🎉混沌回忆已通关{max_level}层🎉").format(max_level=max_level))
        else:
            logger.info(_("混沌回忆未刷新"))
        screen.change_to('main')
        logger.info(_("混沌回忆完成"))
        config.save_timestamp("forgottenhall_timestamp")
