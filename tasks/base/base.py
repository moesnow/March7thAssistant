from managers.translate_manager import _
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.notify_manager import notify
from io import BytesIO


class Base:
    @staticmethod
    def send_notification_with_screenshot(message):
        # 日志显示的同时推送消息
        logger.info(message)
        image_io = BytesIO()
        auto.take_screenshot()
        auto.screenshot.save(image_io, format='JPEG')
        notify.notify(message, "", image_io)
