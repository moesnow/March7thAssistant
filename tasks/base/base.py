from module.logger import log
from module.automation import auto
from module.notification import notif
from module.notification.notification import NotificationLevel


class Base:
    @staticmethod
    def send_notification_with_screenshot(message, level=NotificationLevel.ERROR, screenshot=None):
        # 日志显示的同时推送消息
        message_parts = message.split('\n')
        for part in message_parts:
            if part.strip():  # 确保非空字符串
                log.info(part.strip())
        # log.info(message)
        if screenshot is None:
            screenshot, _, _ = auto.take_screenshot()
        notif.notify(content=message, image=screenshot, level=level)
