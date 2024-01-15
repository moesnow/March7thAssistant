from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.config_manager import config
from managers.logger_manager import logger
from managers.translate_manager import _
from module.automation.screenshot import Screenshot
from tasks.base.base import Base
import time


class PureFiction:
    @staticmethod
    def wait_fight():
        logger.info(_("进入战斗"))
        time.sleep(2)

        def check_fight():
            if auto.find_element("./assets/images/purefiction/prepare_fight.png", "image", 0.9, crop=(64 / 1920, 277 / 1080, 167 / 1920, 38 / 1080)):
                return 1
            elif auto.find_element("./assets/images/purefiction/back.png", "image", 0.9):
                if auto.find_element("./assets/images/purefiction/fail.png", "image", 0.9):
                    auto.click_element("./assets/images/purefiction/back.png", "image", 0.9)
                    return 3
                else:
                    auto.click_element("./assets/images/purefiction/back.png", "image", 0.9)
                    return 2
            elif config.auto_battle_detect_enable and auto.find_element("./assets/images/share/base/not_auto.png", "image", 0.95, crop=(0.0 / 1920, 903.0 / 1080, 144.0 / 1920, 120.0 / 1080)):
                logger.info(_("尝试开启自动战斗"))
                auto.press_key("v")
            return False

        result = auto.retry_with_timeout(lambda: check_fight(), 30 * 60, 1)

        if not result:
            logger.error(_("战斗超时"))
            raise Exception(_("战斗超时"))

        return result

    @staticmethod
    def start_fight(count, boss_count, team=None, switch_team=False):
        for i in range(count):
            logger.info(_("进入第{i}间").format(i=i + 1))
            auto.press_key("w", 3.5)

            def use_technique(team):
                last_index = None
                for index, character in enumerate(team):
                    if character[1] > 0:
                        auto.press_key(f"{index+1}")
                        time.sleep(1)
                        for i in range(character[1]):
                            auto.press_key(config.get_value("hotkey_technique"))
                            time.sleep(1)
                    elif character[1] == -1:
                        last_index = index

                return last_index

            # 释放秘技
            if team:
                last_index = use_technique(team)
            elif switch_team:
                last_index = use_technique(config.get_value("purefiction_team" + str(2 - i)))
            else:
                last_index = use_technique(config.get_value("purefiction_team" + str(i + 1)))
            # 切换到开怪角色
            if last_index is not None:
                auto.press_key(f"{last_index+1}")
                time.sleep(1)

            for i in range(boss_count):
                logger.info(_("挑战第{i}个boss").format(i=i + 1))

                # 适配近战角色开怪
                if boss_count == 2:
                    if i == 0:
                        auto.press_key("a", 1)
                    elif i == 1:
                        auto.press_key("d", 2)

                # 开怪
                auto.press_key(config.get_value("hotkey_technique"))
                for i in range(3):
                    auto.press_mouse()

                result = PureFiction.wait_fight()

                if result == 3:
                    return False
                elif result == 4:
                    return True
            time.sleep(1)
        return True

    @staticmethod
    def click_message_box():
        if auto.find_element("空白", "text", max_retries=20, crop=(12.0 / 1920, 731.0 / 1080, 1904.0 / 1920, 280.0 / 1080), include=True):
            time.sleep(1)
            auto.press_key("esc")
            time.sleep(1)

    @staticmethod
    def select_characters(team_config, team_image_path):
        if auto.click_element(team_image_path, "image", 0.8, max_retries=10, crop=(592.0 / 1920, 556.0 / 1080, 256.0 / 1920, 424.0 / 1080)):
            time.sleep(1)
            auto.take_screenshot(crop=(30 / 1920, 115 / 1080, 530 / 1920, 810 / 1080))
            for character in team_config:
                if not auto.click_element(f"./assets/images/share/character/{character[0]}.png", "image", 0.8, max_retries=10, take_screenshot=False):
                    auto.click_element("等级", "text", include=True, action="move")
                    auto.mouse_scroll(30, -1)
                    time.sleep(1)
                    auto.click_element("角色列表", "text", include=True, action="move")
                    if not auto.click_element(f"./assets/images/share/character/{character[0]}.png", "image", 0.8, max_retries=10, take_screenshot=False):
                        return False
                    else:
                        auto.click_element("等级", "text", include=True, action="move")
                        auto.mouse_scroll(30, 1)
                        time.sleep(1)
                        auto.click_element("角色列表", "text", include=True, action="move")
                time.sleep(0.5)
            return True
        return False

    @staticmethod
    def select_buff():
        if auto.click_element("./assets/images/purefiction/plus.png", "image", 0.8, max_retries=10, crop=(1661.0 / 1920, 522.0 / 1080, 218.0 / 1920, 274.0 / 1080)):
            if auto.click_element("./assets/images/purefiction/choose.png", "image", 0.8, max_retries=10):
                if auto.click_element("./assets/images/purefiction/confirm.png", "image", 0.8, max_retries=10):
                    if auto.click_element("./assets/images/purefiction/plus.png", "image", 0.8, max_retries=10, crop=(1659.0 / 1920, 808.0 / 1080, 238.0 / 1920, 140.0 / 1080)):
                        if auto.click_element("./assets/images/purefiction/choose.png", "image", 0.8, max_retries=10):
                            auto.click_element("./assets/images/purefiction/confirm.png",
                                               "image", 0.8, max_retries=10)
                            return True
        return False

    @staticmethod
    def configure_teams():
        if auto.find_element("./assets/images/forgottenhall/team1.png", "image", 0.8, max_retries=10, crop=(592.0 / 1920, 556.0 / 1080, 256.0 / 1920, 424.0 / 1080)):
            auto.click_element("./assets/images/forgottenhall/reset.png", "image", 0.8, max_retries=10,
                               crop=(617.0 / 1920, 432.0 / 1080, 1294.0 / 1920, 510.0 / 1080))
            time.sleep(0.5)
            if PureFiction.select_characters(config.purefiction_team1, "./assets/images/forgottenhall/team1.png"):
                if PureFiction.select_characters(config.purefiction_team2, "./assets/images/forgottenhall/team2.png"):
                    if PureFiction.select_buff():
                        if auto.click_element("./assets/images/purefiction/start.png", "image", 0.8, max_retries=10, crop=(1546 / 1920, 962 / 1080, 343 / 1920, 62 / 1080)):
                            return True
        return False

    @staticmethod
    def change_to(number, max_retries=4):
        # crop = (0, 0, 1, 900 / 1080)
        crop = (331.0 / 1920, 97.0 / 1080, 1562.0 / 1920, 798.0 / 1080)
        window = Screenshot.get_window(config.game_title_name)
        left, top, width, height = Screenshot.get_window_region(window)

        for i in range(max_retries):
            result = auto.find_element(number, "text", max_retries=4, crop=crop, relative=True)
            if result:
                return (result[0][0] + width * crop[0], result[0][1] + height * crop[1])

        return False

    @staticmethod
    def check_star(top_left):
        window = Screenshot.get_window(config.game_title_name)
        left, top, width, height = Screenshot.get_window_region(window)
        crop = (top_left[0] / width, top_left[1] / height, 120 / 1920, 120 / 1080)
        count = auto.find_element("./assets/images/purefiction/star.png",
                                  "image_count", 0.6, crop=crop, pixel_bgr=[95, 198, 255])
        return count if count is not None and 0 <= count <= 3 else None

    @staticmethod
    def run():
        # 记录层数
        max_level = 0
        # auto.mouse_scroll(20, 1)
        # time.sleep(1)
        for i in range(config.purefiction_level[0], config.purefiction_level[1] + 1):
            # 选择关卡
            top_left = PureFiction.change_to(f"{i:02}")
            if not top_left:
                logger.error(_("切换关卡失败"))
                break
            logger.debug(_("选择关卡:{top_left}").format(top_left=top_left))
            # 判断星数
            star_count = PureFiction.check_star(top_left)
            if star_count == 3:
                logger.info(_("第{i}层已满星").format(i=f"{i:02}"))
                continue
            else:
                logger.info(_("第{i}层星数{star_count}").format(i=i, star_count=star_count))
                auto.click_element(f"{i:02}", "text", max_retries=20, crop=(
                    331.0 / 1920, 97.0 / 1080, 1562.0 / 1920, 798.0 / 1080))

            logger.info(_("开始挑战第{i}层").format(i=f"{i:02}"))
            # 选择角色
            if not PureFiction.configure_teams():
                logger.error(_("配置队伍失败，请检查是否在设置中配置好两个队伍！！！"))
                break

            # 点击弹出框
            PureFiction.click_message_box()
            # 判断关卡BOSS数量
            # boss_count = 2 if i in range(1, 6) else 1
            boss_count = 1
            if not PureFiction.start_fight(2, boss_count):
                logger.info(_("挑战失败"))
                break
            else:
                logger.info(_("挑战成功"))
                max_level = i

            # 进入虚构叙事关卡选择界面
            time.sleep(2)
            if not auto.find_element("./assets/images/screen/purefiction/purefiction.png", "image", 0.8, max_retries=10):
                # if not auto.find_element("虚构叙事", "text", max_retries=10):
                logger.error(_("界面不正确，尝试切换到虚构叙事界面"))
                screen.change_to('purefiction')

        if max_level > 0:
            # screen.change_to('memory_of_chaos')
            # 领取星琼
            if auto.click_element("./assets/images/share/base/RedExclamationMark.png", "image", 0.9, max_retries=5, crop=(1775.0 / 1920, 902.0 / 1080, 116.0 / 1920, 110.0 / 1080)):
                time.sleep(1)
                while auto.click_element("./assets/images/forgottenhall/receive.png", "image", 0.9, crop=(1081.0 / 1920, 171.0 / 1080, 500.0 / 1920, 736.0 / 1080)):
                    auto.click_element("./assets/images/zh_CN/base/click_close.png",
                                       "image", 0.9, max_retries=10)
                    time.sleep(1)
                Base.send_notification_with_screenshot(
                    _("🎉虚构叙事已通关{max_level}层🎉").format(max_level=max_level))
                auto.press_key("esc")
                time.sleep(1)
            else:
                logger.error(_("领取星琼失败"))
                Base.send_notification_with_screenshot(
                    _("🎉虚构叙事已通关{max_level}层🎉\n领取星琼失败").format(max_level=max_level))

    @staticmethod
    def prepare():
        flag = False
        screen.change_to('guide4')
        guide4_crop = (231.0 / 1920, 420.0 / 1080, 450.0 / 1920, 536.0 / 1080)
        if auto.click_element("虚构叙事", "text", max_retries=10, crop=guide4_crop):
            time.sleep(1)
            auto.find_element("虚构叙事", "text", max_retries=10, crop=(
                689.0 / 1920, 285.0 / 1080, 970.0 / 1920, 474.0 / 1080), include=True)
            for box in auto.ocr_result:
                text = box[1][0]
                if "/12" in text:
                    logger.info(_("星数：{text}").format(text=text))
                    if text.split("/")[0] == "12":
                        logger.info(_("虚构叙事未刷新"))
                        return True
                    else:
                        break
            if auto.click_element("传送", "text", max_retries=10, need_ocr=False):
                if auto.click_element("虚构叙事", "text", max_retries=20, include=True, action="move", crop=(0.0 / 1920, 1.0 / 1080, 552.0 / 1920, 212.0 / 1080)):
                    # if auto.click_element("./assets/images/screen/purefiction/purefiction.png", "image", 0.8, max_retries=10, action="move"):
                    flag = True

        if not flag:
            screen.change_to('menu')
            return False

        # 刷新后打开会出现本期buff的弹窗
        time.sleep(2)
        if auto.click_element("./assets/images/purefiction/start_story.png", "image", 0.8):
            auto.click_element("虚构叙事", "text", max_retries=10, include=True, action="move", crop=(
                0.0 / 1920, 1.0 / 1080, 552.0 / 1920, 212.0 / 1080))
            # auto.click_element("./assets/images/screen/purefiction/purefiction.png",
            #                    "image", 0.8, max_retries=10, action="move")

        PureFiction.run()

        return True

    @staticmethod
    def start():
        logger.hr(_("准备虚构叙事"), 0)

        if PureFiction.prepare():
            config.save_timestamp("purefiction_timestamp")

        logger.hr(_("完成"), 2)
