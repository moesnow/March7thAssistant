from managers.screen import screen
from managers.automation import auto
from managers.config import config
from managers.logger import logger
import time


class Photo:
    @staticmethod
    def photograph():
        try:
            flag = False
            logger.hr("准备拍照", 2)
            screen.change_to('camera')
            time.sleep(1)
            for i in range(10):
                auto.press_key('f')
                if auto.find_element("./assets/images/screen/photo_preview.png", "image", 0.9):
                    flag = True
                    break
            logger.info("拍照完成")
            return flag
        except Exception as e:
            logger.error(f"拍照失败: {e}")
            return False
