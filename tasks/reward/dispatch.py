import time
from managers.automation_manager import auto
from managers.config_manager import config
from managers.logger_manager import logger
from managers.translate_manager import _
from tasks.reward.rewardtemplate import RewardTemplate


class Dispatch(RewardTemplate):
    def run(self):
        # 适配低性能电脑，中间的界面不一定加载出了
        auto.find_element("专属材料", "text", max_retries=10, crop=(298.0 / 1920, 153.0 / 1080, 1094.0 / 1920, 122.0 / 1080))

        self._perform_dispatches()
        if "派遣1次委托" in config.daily_tasks and config.daily_tasks["派遣1次委托"]:
            config.daily_tasks["派遣1次委托"] = False
            config.save_config()

    def _perform_dispatches(self):
        for i in range(4):
            logger.info(_("正在进行第{number}次委托").format(number=i + 1))

            if not self.perform_dispatch_and_check(crop=(298.0 / 1920, 153.0 / 1080, 1094.0 / 1920, 122.0 / 1080)):
                return

            if not self.perform_dispatch_and_check(crop=(660 / 1920, 280 / 1080, 170 / 1920, 600 / 1080)):
                return

            auto.click_element("./assets/images/dispatch/receive.png", "image", 0.9, max_retries=10)
            auto.click_element("./assets/images/dispatch/again.png", "image", 0.9, max_retries=10)
            time.sleep(4)

    def perform_dispatch_and_check(self, crop):
        if not self._click_complete_dispatch(crop):
            logger.warning(_("未检测到已完成的委托"))
            return False
        time.sleep(0.5)
        return True

    def _click_complete_dispatch(self, crop):
        # width, height = auto.get_image_info("./assets/images/dispatch/reward.png")
        # offset = (-2 * width, 2 * height)
        offset = (-34, 34)  # 以后改相对坐标偏移
        return auto.click_element("./assets/images/dispatch/reward.png", "image", 0.9, max_retries=8, offset=offset, crop=crop)
