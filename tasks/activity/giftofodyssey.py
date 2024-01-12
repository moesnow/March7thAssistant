from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.translate_manager import _
from managers.config_manager import config
import time


class GiftOfOdyssey:
    RECEIVE_PATH = "./assets/images/activity/giftof/receive.png"
    RECEIVE_FIN_PATH = "./assets/images/activity/giftof/receive_fin.png"
    CLOSE_PATH = "./assets/images/base/click_close.png"
    IMAGE_SIMILARITY_THRESHOLD = 0.9

    @staticmethod
    def get_reward():
        if not config.activity_giftofodyssey_enable:
            return

        screen.change_to('activity')
        if not auto.click_element("巡星之礼", "text", None, crop=(46.0 / 1920, 107.0 / 1080, 222.0 / 1920, 848.0 / 1080)):
            return

        time.sleep(1)
        if GiftOfOdyssey._has_reward():
            logger.hr(_("检测到巡星之礼奖励"), 2)
            GiftOfOdyssey._collect_rewards()
            logger.info(_("领取巡星之礼奖励完成"))

    @staticmethod
    def _has_reward():
        return auto.find_element(GiftOfOdyssey.RECEIVE_PATH, "image", GiftOfOdyssey.IMAGE_SIMILARITY_THRESHOLD) or \
            auto.find_element(GiftOfOdyssey.RECEIVE_FIN_PATH, "image",
                              GiftOfOdyssey.IMAGE_SIMILARITY_THRESHOLD)

    @staticmethod
    def _collect_rewards():
        while auto.click_element(GiftOfOdyssey.RECEIVE_PATH, "image", GiftOfOdyssey.IMAGE_SIMILARITY_THRESHOLD) or \
                auto.click_element(GiftOfOdyssey.RECEIVE_FIN_PATH, "image", GiftOfOdyssey.IMAGE_SIMILARITY_THRESHOLD):
            auto.click_element(GiftOfOdyssey.CLOSE_PATH, "image",
                               GiftOfOdyssey.IMAGE_SIMILARITY_THRESHOLD, max_retries=10)
            time.sleep(1)
