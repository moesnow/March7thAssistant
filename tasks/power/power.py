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
        offset = [(0.27, 0.1), (0, -0.1)]
        try:
            result = auto.get_single_line_text_from_matched_screenshot_region(
                "./assets/images/base/trailblaze_power.png", offset=offset, similarity_threshold=0.7, blacklist=['+'])

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
            return auto.find_element("./assets/images/fight/fight_again.png", "image", 0.95)
        if not auto.retry_with_timeout(check_fight, 600, 1):
            logger.error(_("战斗超时"))
            raise Exception(_("战斗超时"))
        logger.info(_("战斗完成"))

    @staticmethod
    def borrow_character():
        if config.borrow_character_enable:
            if auto.click_element("支援", "text", max_retries=10):
                auto.find_element("入队", "text", max_retries=10)
                try:
                    for name in config.borrow_character:
                        if auto.click_element("./assets/images/character/" + name + ".png", "image", 0.8, max_retries=1, scale_range=(0.8, 1.2)):
                            auto.click_element("入队", "text", max_retries=10)
                            auto.click_element("取消", "text", max_retries=2)
                            return
                    if config.borrow_force == True:
                        auto.click_element("入队", "text", max_retries=10)
                        return
                except Exception as e:
                    logger.warning(_("选择支援角色出错： {e}").format(e=e))
                auto.press_key("esc")

    @staticmethod
    def run_instances(number):
        screen.change_to('guide3')
        auto.click_element(config.instance_type, "text", max_retries=10)
        # 截图过快会导致结果不可信
        time.sleep(1)

        if config.instance_type == "侵蚀隧洞":
            offset = [(2.5, 3), (2, 3)]
            # 第一页
            if not auto.click_text_from_matched_screenshot_region(config.instance_name, offset=offset, target_text="传送"):
                auto.click_element("./assets/images/screen/guide/guide3_40power.png", "image", max_retries=10)
                auto.mouse_scroll(18, -1)
                # 第二页
                if not auto.click_text_from_matched_screenshot_region(config.instance_name, offset=offset, target_text="传送"):
                    auto.mouse_scroll(6, -1)
                    # 第三页
                    if not auto.click_text_from_matched_screenshot_region(config.instance_name, offset=offset, target_text="传送"):
                        return False
            if not auto.find_element(config.instance_name, "text", max_retries=10):
                Base.send_notification_with_screenshot(_("⚠️侵蚀隧洞未完成⚠️"))
                return False
            if auto.click_element("挑战", "text", max_retries=10):
                Power.borrow_character()
                if auto.click_element("开始挑战", "text", max_retries=10):
                    for i in range(number - 1):
                        Power.wait_fight()
                        logger.info(_("第{number}次副本完成").format(number=i + 1))
                        auto.click_element("./assets/images/fight/fight_again.png", "image", 0.95, max_retries=10)
                    Power.wait_fight()
                    logger.info(_("第{number}次副本完成").format(number=number))

                    # 速度太快，点击按钮无效
                    time.sleep(1)
                    auto.click_element("./assets/images/fight/fight_exit.png", "image", 0.95, max_retries=10)
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
