from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.config_manager import config
from managers.logger_manager import logger
from managers.translate_manager import _
from module.automation.screenshot import Screenshot
from tasks.base.base import Base
import time


class GiftOfOdyssey:
    @staticmethod
    def get_reward():
        if not screen.check_screen('activity'):
            screen.change_to('activity')
        if auto.click_element("巡星之礼","text",None,crop=(3.0 / 1920, 81.0 / 1080, 322.0 / 1920, 876.0 / 1080)):
            time.sleep(1)
            if auto.find_element("./assets/images/activity/giftofodyssey.png", "image", 0.9):
                logger.hr(_("检测到巡星之礼奖励"), 2)
                while auto.click_element("./assets/images/activity/giftofodyssey.png", "image", 0.9):
                    auto.click_element("./assets/images/base/click_close.png", "image", 0.9, max_retries=10)
                    time.sleep(1)
                logger.info(_("领取巡星之礼奖励完成"))
            else:
                logger.info(_("未检测到巡星之礼奖励"))