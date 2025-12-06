from module.logger import log
from module.automation import auto
from module.notification import notif
from module.notification.notification import NotificationLevel


class Base:
    @staticmethod
    def send_notification_with_screenshot(message, level=NotificationLevel.ERROR):
        # 日志显示的同时推送消息
        log.info(message)
        screenshot, _, _ = auto.take_screenshot()
        notif.notify(content=message, image=screenshot, level=level)
