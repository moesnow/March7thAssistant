from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.config_manager import config
from managers.translate_manager import _
from tasks.base.base import Base
import time


class Power:
    @staticmethod
    def start():
        logger.hr(_("开始清体力"), 0)
        Power.instance()
        logger.hr(_("完成"), 2)

    @staticmethod
    def power():
        screen.change_to('map')
        try:
            result = auto.get_single_line_text(crop=(1588.0 / 1920, 35.0 / 1080, 198.0 / 1920, 56.0 / 1080), blacklist=['+'])

            power_mapping = {
                '/': lambda r: int(r.split('/')[0]) if 0 <= int(r.split('/')[0]) <= config.power_total else -1,
                'default': lambda r: -1
            }

            trailblaze_power = power_mapping.get('/', power_mapping['default'])(result)
        except Exception as e:
            logger.error(_("获取开拓力失败: {error}").format(error=e))
            trailblaze_power = -1

        logger.info(_("🟣开拓力: {power}").format(power=trailblaze_power))
        return trailblaze_power

    @staticmethod
    def wait_fight():
        logger.info(_("等待战斗"))
        time.sleep(10)

        def check_fight():
            return auto.find_element("./assets/images/fight/fight_again.png", "image", 0.9)
        if not auto.retry_with_timeout(check_fight, 600, 1):
            logger.error(_("战斗超时"))
            raise Exception(_("战斗超时"))
        logger.info(_("战斗完成"))

    @staticmethod
    def borrow_character():
        if not config.borrow_character_enable:
            logger.debug(_("支援角色未开启"))
            return True
        if not auto.click_element("支援", "text", max_retries=10, crop=(1670 / 1920, 700 / 1080, 225 / 1920, 74 / 1080)):
            logger.error(_("找不到支援按钮"))
            return False
        # 等待界面加载
        time.sleep(0.5)
        if not auto.find_element("支援列表", "text", max_retries=10, crop=(234 / 1920, 78 / 1080, 133 / 1920, 57 / 1080)):
            logger.error(_("未进入支援列表"))
            return False
        try:
            for name in config.borrow_character:
                if auto.click_element("./assets/images/character/" + name + ".png", "image", 0.8, max_retries=1, scale_range=(0.8, 1.2), crop=(57 / 1920, 143 / 1080, 140 / 1920, 814 / 1080)):
                    if not auto.click_element("入队", "text", max_retries=10, crop=(1518 / 1920, 960 / 1080, 334 / 1920, 61 / 1080)):
                        logger.error(_("找不到入队按钮"))
                        return False
                    # 等待界面加载
                    time.sleep(0.5)
                    result = auto.find_element(("解除支援", "取消"), "text", max_retries=10, include=True)
                    if result:
                        if auto.matched_text == "解除支援":
                            return True
                        elif auto.matched_text == "取消":
                            auto.click_element_with_pos(result)
                            auto.find_element("支援列表", "text", max_retries=10, crop=(234 / 1920, 78 / 1080, 133 / 1920, 57 / 1080))
                            continue
                    else:
                        return False
            if config.borrow_force == True:
                if not auto.click_element("入队", "text", max_retries=10, crop=(1518 / 1920, 960 / 1080, 334 / 1920, 61 / 1080)):
                    logger.error(_("找不到入队按钮"))
                    return False
                result = auto.find_element(("解除支援", "取消"), "text", max_retries=10, include=True)
                if result:
                    if auto.matched_text == "解除支援":
                        return True
                    elif auto.matched_text == "取消":
                        auto.click_element_with_pos(result)
                        auto.find_element("支援列表", "text", max_retries=10, crop=(234 / 1920, 78 / 1080, 133 / 1920, 57 / 1080))
                        auto.press_key("esc")
                else:
                    return False
        except Exception as e:
            logger.warning(_("选择支援角色出错： {e}").format(e=e))

        auto.press_key("esc")
        if auto.find_element("解除支援", "text", max_retries=2, crop=(1670 / 1920, 700 / 1080, 225 / 1920, 74 / 1080)):
            return True
        else:
            return False

    @staticmethod
    def run_instances(number):
        if config.instance_team_enable:
            Base.change_team(config.instance_team_number)

        screen.change_to('guide3')
        auto.click_element(config.instance_type, "text", max_retries=10, crop=(
            262.0 / 1920, 289.0 / 1080, 422.0 / 1920, 624.0 / 1080), take_screenshot=False)
        # 截图过快会导致结果不可信
        time.sleep(1)

        if config.instance_type == "侵蚀隧洞":
            # 兼容旧设置
            instance_name = config.instance_name
            if "·" in instance_name:
                instance_name = instance_name.split("·")[0]

            crop = (686.0 / 1920, 287.0 / 1080, 980.0 / 1920, 650.0 / 1080)
            # 第一页
            if not auto.click_element("传送", "min_distance_text", crop=crop, include=True, source=instance_name):
                auto.click_element("./assets/images/screen/guide/guide3_40power.png", "image", max_retries=10)
                auto.mouse_scroll(18, -1)
                # 第二页
                if not auto.click_element("传送", "min_distance_text", crop=crop, include=True, source=instance_name):
                    auto.mouse_scroll(6, -1)
                    # 第三页
                    if not auto.click_element("传送", "min_distance_text", crop=crop, include=True, source=instance_name):
                        return False
            if not auto.find_element(instance_name, "text", max_retries=10, include=True, crop=(1189.0 / 1920, 102.0 / 1080, 712.0 / 1920, 922.0 / 1080)):
                Base.send_notification_with_screenshot(_("⚠️侵蚀隧洞未完成⚠️"))
                return False
            if auto.click_element("挑战", "text", max_retries=10, need_ocr=False):
                Power.borrow_character()
                if auto.click_element("开始挑战", "text", max_retries=10, crop=(1518 / 1920, 960 / 1080, 334 / 1920, 61 / 1080)):
                    for i in range(number - 1):
                        Power.wait_fight()
                        logger.info(_("第{number}次副本完成").format(number=i + 1))
                        auto.click_element("./assets/images/fight/fight_again.png", "image", 0.9, max_retries=10)
                    Power.wait_fight()
                    logger.info(_("第{number}次副本完成").format(number=number))

                    # 速度太快，点击按钮无效
                    time.sleep(1)
                    auto.click_element("./assets/images/fight/fight_exit.png", "image", 0.9, max_retries=10)
                    logger.info(_("副本任务完成"))

        elif config.instance_type == "其他":
            pass

    @staticmethod
    def instance():
        number = Power.power() // config.power_need
        if number < 1:
            logger.info(_("🟣开拓力 < {power_need}").format(power_need=config.power_need))
            return False

        logger.hr(_("开始刷副本，总计{number}次").format(number=number), 2)
        Power.run_instances(number)
