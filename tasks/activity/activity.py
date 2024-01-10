from tasks.activity.giftofodyssey import GiftOfOdyssey
from tasks.activity.giftofradiance import GiftOfRadiance
from tasks.activity.gardenofplenty import GardenOfPlenty
from tasks.activity.realmofthestrange import RealmOfTheStrange
from tasks.activity.planarfissure import PlanarFissure
from managers.logger_manager import logger
from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.ocr_manager import ocr
from managers.translate_manager import _
from managers.config_manager import config


class Activity():
    @staticmethod
    def start():
        # logger.hr(_("开始检测活动"), 0)
        if config.activity_enable:
            screen.change_to('activity')

            activity_list = []

            auto.take_screenshot(crop=(46.0 / 1920, 107.0 / 1080, 222.0 / 1920, 848.0 / 1080))

            result = ocr.recognize_multi_lines(auto.screenshot)
            if not result:
                logger.info(_("未检测到任何活动"))
                # logger.hr(_("完成"), 2)
                return

            for box in result:
                text = box[1][0]
                if len(text) >= 4:
                    activity_list.append(text)
                    # logger.info(text)

            if "巡星之礼" in activity_list:
                GiftOfOdyssey.get_reward()
            if "巡光之礼" in activity_list:
                GiftOfRadiance.get_reward()
            if "花藏繁生" in activity_list:
                GardenOfPlenty.start()
            if "异器盈界" in activity_list:
                RealmOfTheStrange.start()
            if "位面分裂" in activity_list:
                PlanarFissure.start()

            # logger.hr(_("完成"), 2)
