from managers.logger import logger
from managers.screen import screen
from managers.automation import auto
from managers.ocr import ocr
from managers.config import config
from .checkInactivity import CheckInActivity
from .gardenofplenty import GardenOfPlenty
from .realmofthestrange import RealmOfTheStrange
from .planarfissure import PlanarFissure


class ActivityManager:
    def __init__(self):
        self.giftofodyssey = CheckInActivity("巡星之礼", config.activity_giftofodyssey_enable)
        self.giftofradiance = CheckInActivity("巡光之礼", config.activity_giftofodyssey_enable)
        self.gardenofplenty = GardenOfPlenty("花藏繁生", config.activity_gardenofplenty_enable, config.activity_gardenofplenty_instance_type, config.instance_names)
        self.realmofthestrange = RealmOfTheStrange("异器盈界", config.activity_realmofthestrange_enable, config.instance_names)
        self.planarfissure = PlanarFissure("位面分裂", config.activity_planarfissure_enable)

        self.activity_functions = {
            "巡星之礼": self.giftofodyssey.start,
            "巡光之礼": self.giftofradiance.start,
            "花藏繁生": self.gardenofplenty.start,
            "异器盈界": self.realmofthestrange.start,
            "位面分裂": self.planarfissure.start,
        }

    def check_and_run_activities(self):
        logger.hr("开始检测活动", 0)

        activity_names = self._get_activity_names()

        if not activity_names:
            logger.info("未检测到任何活动")
            self._finish()
            return

        for activity_name in activity_names:
            func = self.activity_functions.get(activity_name)
            if func:
                func()

        self._finish()

    def _get_activity_names(self):
        screen.change_to('activity')
        screenshot, _, _ = auto.take_screenshot(crop=(46.0 / 1920, 107.0 / 1080, 222.0 / 1920, 848.0 / 1080))
        result = ocr.recognize_multi_lines(screenshot)
        if not result:
            return []

        logger.debug(result)
        return [box[1][0] for box in result if len(box[1][0]) >= 4]

    def _finish(self):
        logger.hr("完成", 2)


def start():
    if not config.activity_enable:
        logger.info("活动未开启")
        return

    activity_manager = ActivityManager()
    activity_manager.check_and_run_activities()
