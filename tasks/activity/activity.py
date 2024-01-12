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
        if not config.activity_enable:
            return

        # logger.hr(_("开始检测活动"), 0)

        screen.change_to('activity')

        activity_names = Activity._get_activity_names()

        if not activity_names:
            logger.info(_("未检测到任何活动"))
            return

        activity_functions = {
            "巡星之礼": GiftOfOdyssey.get_reward,
            "巡光之礼": GiftOfRadiance.get_reward,
            "花藏繁生": GardenOfPlenty.start,
            "异器盈界": RealmOfTheStrange.start,
            "位面分裂": PlanarFissure.start,
        }

        for activity_name in activity_names:
            func = activity_functions.get(activity_name)
            if func:
                func()

        # logger.hr(_("完成"), 2)

    @staticmethod
    def _get_activity_names():
        auto.take_screenshot(crop=(46.0 / 1920, 107.0 / 1080, 222.0 / 1920, 848.0 / 1080))
        result = ocr.recognize_multi_lines(auto.screenshot)
        if not result:
            return []

        return [box[1][0] for box in result if len(box[1][0]) >= 4]
