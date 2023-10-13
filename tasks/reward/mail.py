from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.config_manager import config
from managers.logger_manager import logger
from managers.translate_manager import _


class Mail:
    @staticmethod
    def get_reward():
        if not config.mail_enable:
            logger.info(_("邮件奖励未开启"))
            return False

        screen.change_to('mail')
        if auto.click_element("./assets/images/mail/receive_all.png", "image", 0.9):
            auto.click_element("./assets/images/base/click_close.png", "image", 0.9, max_retries=10)
