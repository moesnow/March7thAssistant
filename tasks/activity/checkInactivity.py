import time
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.translate_manager import _
from .activitytemplate import ActivityTemplate


class CheckInActivity(ActivityTemplate):
    RECEIVE_PATH = "./assets/images/zh_CN/activity/double/receive.png"
    RECEIVE_FIN_PATH = "./assets/images/zh_CN/activity/double/receive_fin.png"
    CLOSE_PATH = "./assets/images/zh_CN/base/click_close.png"
    IMAGE_SIMILARITY_THRESHOLD = 0.9

    def _has_reward(self):
        return auto.find_element(CheckInActivity.RECEIVE_PATH, "image", CheckInActivity.IMAGE_SIMILARITY_THRESHOLD) or \
            auto.find_element(CheckInActivity.RECEIVE_FIN_PATH, "image", CheckInActivity.IMAGE_SIMILARITY_THRESHOLD)

    def _has_reward(self):
        while auto.click_element(CheckInActivity.RECEIVE_PATH, "image", CheckInActivity.IMAGE_SIMILARITY_THRESHOLD) or \
                auto.click_element(CheckInActivity.RECEIVE_FIN_PATH, "image", CheckInActivity.IMAGE_SIMILARITY_THRESHOLD):
            auto.click_element(CheckInActivity.CLOSE_PATH, "image", CheckInActivity.IMAGE_SIMILARITY_THRESHOLD, max_retries=10)
            time.sleep(1)

    def run(self):
        if self._has_reward():
            logger.hr(_("检测到{name}奖励").format(name=self.name), 2)
            self._collect_rewards()
            logger.info(_("领取{name}奖励完成").format(name=self.name))
