from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.config_manager import config
from managers.logger_manager import logger
from managers.translate_manager import _


class Assist:
    @staticmethod
    def get_reward():
        if not config.assist_enable:
            logger.info(_("支援奖励未开启"))
            return False
        screen.change_to('menu')
        if auto.find_element("./assets/images/menu/assist_reward.png", "image", 0.95):
            logger.hr(_("检测到支援奖励"), 2)
            screen.change_to('visa')
            if auto.click_element("./assets/images/assist/gift.png", "image", 0.9):
                auto.click_element("./assets/images/base/click_close.png", "image", 0.9, max_retries=10)
            logger.info(_("支援奖励完成"))
