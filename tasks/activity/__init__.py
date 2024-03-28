from module.logger import log
from module.screen import screen
from module.automation import auto
from module.ocr import ocr
from module.config import cfg
from .checkInactivity import CheckInActivity
from .gardenofplenty import GardenOfPlenty
from .realmofthestrange import RealmOfTheStrange
from .planarfissure import PlanarFissure


class ActivityManager:
    def __init__(self):
        self.giftofodyssey = CheckInActivity("巡星之礼", cfg.activity_dailycheckin_enable)
        self.giftofradiance = CheckInActivity("巡光之礼", cfg.activity_dailycheckin_enable)
        self.festivegifts = CheckInActivity("庆典祝礼", cfg.activity_dailycheckin_enable)
        self.gardenofplenty = GardenOfPlenty("花藏繁生", cfg.activity_gardenofplenty_enable, cfg.activity_gardenofplenty_instance_type, cfg.instance_names)
        self.realmofthestrange = RealmOfTheStrange("异器盈界", cfg.activity_realmofthestrange_enable, cfg.instance_names)
        self.realmofthestrange3 = RealmOfTheStrange("异器盈界300%", cfg.activity_realmofthestrange_enable, cfg.instance_names)
        self.planarfissure = PlanarFissure("位面分裂", cfg.activity_planarfissure_enable)
        self.planarfissure3 = PlanarFissure("位面分裂300%", cfg.activity_planarfissure_enable)

        self.activity_functions = {
            "巡星之礼": self.giftofodyssey.start,
            "巡光之礼": self.giftofradiance.start,
            "庆典祝礼": self.festivegifts.start,
            "花藏繁生": self.gardenofplenty.start,
            "异器盈界": self.realmofthestrange.start,
            "异器盈界300%": self.realmofthestrange3.start,
            "位面分裂": self.planarfissure.start,
            "位面分裂300%": self.planarfissure3.start,
        }

    def check_and_run_activities(self):
        log.hr("开始检测活动", 0)

        activity_names = self._get_activity_names()

        if not activity_names:
            log.info("未检测到任何活动")
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

        return [box[1][0] for box in result if len(box[1][0]) >= 4]

    def _finish(self):
        log.hr("完成", 2)


def start():
    if not cfg.activity_enable:
        log.info("活动未开启")
        return

    activity_manager = ActivityManager()
    activity_manager.check_and_run_activities()
