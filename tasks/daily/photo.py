from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.config_manager import config
from managers.logger_manager import logger
from managers.translate_manager import _
import time


class Photo:
    @staticmethod
    def photograph():
        if not config.photo_enable:
            logger.info(_("拍照未开启"))
            return False
        logger.hr(_("准备拍照"), 2)
        screen.change_to('camera')
        time.sleep(1)
        for i in range(10):
            auto.press_key('f')
            if auto.find_element("./assets/images/screen/photo_preview.png", "image", 0.9):
                break
        logger.info(_("拍照完成"))
