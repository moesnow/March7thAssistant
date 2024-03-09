from module.screen import screen
from module.automation import auto
from module.config import cfg
from module.logger import log
import time


class Photo:
    @staticmethod
    def photograph():
        try:
            flag = False
            log.hr("准备拍照", 2)
            screen.change_to('camera')
            time.sleep(1)
            for i in range(10):
                auto.press_key('f')
                if auto.find_element("./assets/images/screen/photo_preview.png", "image", 0.9):
                    flag = True
                    break
            log.info("拍照完成")
            return flag
        except Exception as e:
            log.error(f"拍照失败: {e}")
            return False
