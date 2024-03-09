from module.logger import log
from module.automation import auto
from module.notification import notif


class Base:
    @staticmethod
    def send_notification_with_screenshot(message):
        # 日志显示的同时推送消息
        log.info(message)
        screenshot, _, _ = auto.take_screenshot()
        notif.notify(message, screenshot)
