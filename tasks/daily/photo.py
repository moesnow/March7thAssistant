from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.config_manager import config
from managers.logger_manager import logger
from managers.translate_manager import _
import time


class Photo:
    @staticmethod
    def photograph():
        try:
            flag = False
            logger.hr(_("准备拍照"), 2)
            screen.change_to('camera')
            time.sleep(1)
            for i in range(10):
                auto.press_key('f')
                if auto.find_element("./assets/images/screen/photo_preview.png", "image", 0.9):
                    flag = True
                    break
            logger.info(_("拍照完成"))
            return flag
        except Exception as e:
            logger.error(_("拍照失败: {error}").format(error=e))
            return False
