from managers.config_manager import config
from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.translate_manager import _
from tasks.base.base import Base
import time


class Quest:
    @staticmethod
    def get_reward():
        screen.change_to('menu')
        if auto.find_element("./assets/images/quest/quest_reward.png", "image", 0.95):
            logger.hr(_("检测到每日实训奖励"), 2)
            screen.change_to('guide2')
            while auto.click_element("./assets/images/quest/receive.png", "image", 0.9, crop=(265.0 / 1920, 394.0 / 1080, 1400.0 / 1920, 504.0 / 1080)):
                time.sleep(1)
            if auto.click_element("./assets/images/quest/gift.png", "image", 0.9, crop=(415.0 / 1920, 270.0 / 1080, 1252.0 / 1920, 114.0 / 1080)):
                auto.click_element("./assets/images/base/click_close.png", "image", 0.9, max_retries=10)
            auto.find_element("./assets/images/screen/guide/guide2.png", "image", 0.9, max_retries=10)

            if auto.find_element("./assets/images/quest/500.png", "image", 0.95, crop=(415.0 / 1920, 270.0 / 1080, 1252.0 / 1920, 114.0 / 1080)):
                config.set_value("daily_tasks", {})
                Base.send_notification_with_screenshot(_("🎉每日实训已完成🎉"))
            else:
                Base.send_notification_with_screenshot(_("⚠️每日实训未完成⚠️"))
            logger.info(_("领取每日实训奖励完成"))
        else:
            logger.info(_("未检测到每日实训奖励"))
