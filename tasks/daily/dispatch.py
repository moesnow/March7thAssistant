from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.config_manager import config
from managers.logger_manager import logger
from managers.translate_manager import _
import time


class Dispatch:
    @staticmethod
    def get_reward():
        if not config.dispatch_enable:
            logger.info(_("探索派遣未开启"))
            return False
        screen.change_to('menu')

        if auto.find_element("./assets/images/dispatch/dispatch_reward.png", "image", 0.95):
            logger.hr(_("检测到探索派遣奖励"), 2)
            screen.change_to('dispatch')

            Dispatch._perform_dispatches()

            screen.change_to('menu')
            logger.info(_("探索派遣奖励完成"))

    @staticmethod
    def _perform_dispatches():
        width, height = auto.get_image_info("./assets/images/dispatch/reward.png")
        offset = (-2 * width, 2 * height)

        for i in range(config.dispatch_count):
            logger.info(_("正在进行第{number}次委托").format(number=i + 1))

            if not Dispatch.perform_dispatch_and_check(offset, crop=(0.18, 0.15, 0.41, 0.09)):
                break

            if not Dispatch.perform_dispatch_and_check(offset, crop=(0.18, 0.25, 0.26, 0.55)):
                break

            auto.click_element("./assets/images/dispatch/receive.png", "image", 0.95, max_retries=10)
            auto.click_element("./assets/images/dispatch/again.png", "image", 0.95, max_retries=10)
            time.sleep(4)

    @staticmethod
    def perform_dispatch_and_check(offset, crop):
        if not Dispatch._click_complete_dispatch(offset, crop=crop):
            logger.warning(_("未检测到已完成的委托"))
            return False
        time.sleep(0.5)
        return True

    @staticmethod
    def _click_complete_dispatch(offset, crop=None):
        return auto.click_element("./assets/images/dispatch/reward.png", "image", 0.9,
                                  max_retries=10, offset=offset, crop=crop)
