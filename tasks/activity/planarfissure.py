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
        if config.activity_planarfissure_enable:
            screen.change_to('activity')
            if auto.click_element("位面分裂", "text", None, crop=(46.0 / 1920, 107.0 / 1080, 222.0 / 1920, 848.0 / 1080)):
                time.sleep(1)
                auto.find_element("双倍奖励剩余次数", "text", max_retries=10, include=True)
                for box in auto.ocr_result:
                    text = box[1][0]
                    if "/12" in text:
                        reward_count = int(text.split("/")[0])
                        if reward_count == 0:
                            return
                        else:
                            logger.info(_("位面分裂剩余次数：{text}").format(text=text))
                            Power.merge_immersifier()
