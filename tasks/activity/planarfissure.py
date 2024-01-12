from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.translate_manager import _
from managers.config_manager import config
from tasks.power.power import Power
import time


class PlanarFissure:
    @staticmethod
    def start():
        if not config.activity_planarfissure_enable:
            return

        screen.change_to('activity')
        if not auto.click_element("位面分裂", "text", None, crop=(46.0 / 1920, 107.0 / 1080, 222.0 / 1920, 848.0 / 1080)):
            return

        time.sleep(1)
        reward_count = PlanarFissure._get_reward_count()
        if reward_count == 0:
            return

        logger.info(_("位面分裂剩余次数：{text}").format(text=reward_count))
        Power.merge("immersifier")

    @staticmethod
    def _get_reward_count():
        auto.find_element("双倍奖励剩余次数", "text", max_retries=10, include=True)
        for box in auto.ocr_result:
            text = box[1][0]
            if "/12" in text:
                return int(text.split("/")[0])
        return 0
