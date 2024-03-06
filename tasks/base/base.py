from managers.logger import logger
from managers.automation import auto
from managers.notify import notify


class Base:
    @staticmethod
    def send_notification_with_screenshot(message):
        # 日志显示的同时推送消息
        logger.info(message)
        screenshot, _, _ = auto.take_screenshot()
        notify.notify(message, screenshot)
