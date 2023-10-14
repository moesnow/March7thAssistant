from managers.config_manager import config
from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.translate_manager import _
from tasks.base.base import Base
import time


class Quest:
    @staticmethod
    def get_reward():
        screen.change_to('guide2')
        # 领取活跃度
        while auto.click_element("./assets/images/quest/receive.png", "image", 0.9, crop=(265.0 / 1920, 394.0 / 1080, 1400.0 / 1920, 504.0 / 1080)):
            time.sleep(0.5)
        # 领取奖励
        if auto.click_element("./assets/images/quest/gift.png", "image", 0.9, max_retries=10, crop=(415.0 / 1920, 270.0 / 1080, 1252.0 / 1920, 114.0 / 1080)):
            auto.click_element("./assets/images/base/click_close.png", "image", 0.9, max_retries=10)
        auto.find_element("./assets/images/screen/guide/guide2.png", "image", 0.9, max_retries=10)
        # 判断完成
        if auto.find_element("./assets/images/quest/500.png", "image", 0.95, crop=(415.0 / 1920, 270.0 / 1080, 1252.0 / 1920, 114.0 / 1080)):
            config.set_value("daily_tasks", {})
            Base.send_notification_with_screenshot(_("🎉每日实训已完成🎉"))
        else:
            Base.send_notification_with_screenshot(_("⚠️每日实训未完成⚠️"))
