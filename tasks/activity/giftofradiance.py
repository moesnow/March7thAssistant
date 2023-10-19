from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.translate_manager import _
import time


class GiftOfRadiance:
    @staticmethod
    def get_reward():
        screen.change_to('activity')
        if auto.click_element("巡光之礼", "text", None, crop=(46.0 / 1920, 107.0 / 1080, 222.0 / 1920, 848.0 / 1080)):
            time.sleep(1)
            receive_path = "./assets/images/activity/giftof/receive.png"
            receive_fin_path = "./assets/images/activity/giftof/receive_fin.png"
            if auto.find_element(receive_path, "image", 0.9) or auto.find_element(receive_fin_path, "image", 0.9):
                logger.hr(_("检测到巡光之礼奖励"), 2)
                while auto.click_element(receive_path, "image", 0.9) or auto.click_element(receive_fin_path, "image", 0.9):
                    auto.click_element("./assets/images/base/click_close.png", "image", 0.9, max_retries=10)
                    time.sleep(1)
                logger.info(_("领取巡光之礼奖励完成"))
