from managers.translate_manager import _
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.translate_manager import _
from managers.notify_manager import notify
import pygetwindow as gw
from io import BytesIO


class Base:
    @staticmethod
    def send_notification_with_screenshot(message):
        logger.info(message)
        image_io = BytesIO()
        auto.take_screenshot()
        auto.screenshot.save(image_io, format='JPEG')
        notify.notify(message, "", image_io)

    @staticmethod
    def check_and_switch(title):
        def switch_window(title):
            window = gw.getWindowsWithTitle(title)
            if window:
                for w in window:
                    if w.title == title:
                        window[0].restore()
                        window[0].activate()
                        return window[0].isActive
            return False
        return auto.retry_with_timeout(switch_window, 2, 1, title)
