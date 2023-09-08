from managers.screen_manager import screen
from managers.config_manager import config
from managers.logger_manager import logger
from managers.automation_manager import auto
from managers.translate_manager import _
from tasks.base.base import Base
from tasks.base.subprocess import Subprocess


class Universe:
    @staticmethod
    def start():
        logger.hr(_("准备模拟宇宙"), 2)

        screen.change_to('universe_main')
        screen.change_to('main')

        universe_command = config.universe_command + (" --bonus=1" if config.universe_bonus_enable else "")
        if Subprocess.run(universe_command, config.universe_timeout * 3600):
            screen.change_to('universe_main')

            if auto.click_element("./assets/images/universe/universe_reward.png", "image", 0.9):
                if auto.click_element("./assets/images/universe/one_key_receive.png", "image", 0.9, max_retries=10):
                    if auto.find_element("./assets/images/base/click_close.png", "image", 0.9, max_retries=10):
                        Base.send_notification_with_screenshot(_("🎉模拟宇宙奖励已领取🎉"))
                        auto.click_element("./assets/images/base/click_close.png", "image", 0.9, max_retries=10)

            logger.info(_("模拟宇宙完成"))
            config.save_timestamp("universe_timestamp")
        else:
            Base.send_notification_with_screenshot(_("⚠️模拟宇宙未完成⚠️"))
            logger.info(_("模拟宇宙失败"))
