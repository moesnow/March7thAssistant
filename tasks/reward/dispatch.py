import time
from module.automation import auto
from module.config import cfg
from module.logger import log
from .rewardtemplate import RewardTemplate


class Dispatch(RewardTemplate):
    def run(self):
        # 适配低性能电脑，中间的界面不一定加载出了
        auto.find_element("专属材料", "text", max_retries=10, crop=(163 / 1920, 99 / 1080, 1115 / 1920, 118 / 1080))

        if self._perform_dispatches() and "派遣委托或收取1次委托奖励" in cfg.daily_tasks and cfg.daily_tasks["派遣委托或收取1次委托奖励"]:
            cfg.daily_tasks["派遣委托或收取1次委托奖励"] = False
            cfg.save_config()

    def _perform_dispatches(self):
        # 4.0 新界面适配
        if auto.click_element(("领取奖励", "委托派遣中，每小时可持续获得奖励帕！"), "text", max_retries=10, crop=(1194 / 1920, 866 / 1080, 610 / 1920, 156 / 1080), include=True):
            if auto.matched_text == "领取奖励":
                time.sleep(2)
                auto.click_element("./assets/images/zh_CN/base/click_close.png", "image", 0.8, max_retries=10)
                time.sleep(2)
                return True
            else:
                log.info("委托派遣中，目前没有可领取的奖励帕！")
                return False

        log.info("未检测到可领取的委托奖励")
        return False

    #     # 检测一键领取
    #     if auto.click_element("./assets/images/zh_CN/reward/dispatch/one_key_receive.png", "image", 0.9, max_retries=10):
    #         auto.click_element("./assets/images/zh_CN/reward/dispatch/again.png", "image", 0.9, max_retries=10)
    #         time.sleep(4)
    #         return

    #     for i in range(4):
    #         log.info(f"正在进行第{i + 1}次委托")

    #         if not self.perform_dispatch_and_check(crop=(298.0 / 1920, 153.0 / 1080, 1094.0 / 1920, 122.0 / 1080)):
    #             return

    #         if not self.perform_dispatch_and_check(crop=(660 / 1920, 280 / 1080, 170 / 1920, 600 / 1080)):
    #             return

    #         auto.click_element("./assets/images/zh_CN/reward/dispatch/receive.png", "image", 0.9, max_retries=10)
    #         auto.click_element("./assets/images/zh_CN/reward/dispatch/again.png", "image", 0.9, max_retries=10)
    #         time.sleep(4)

    # def perform_dispatch_and_check(self, crop):
    #     if not self._click_complete_dispatch(crop):
    #         log.warning("未检测到已完成的委托")
    #         return False
    #     time.sleep(0.5)
    #     return True

    # def _click_complete_dispatch(self, crop):
    #     # width, height = auto.get_image_info("./assets/images/share/base/RedExclamationMark.png")
    #     # offset = (-2 * width, 2 * height)
    #     offset = (-34, 34)  # 以后改相对坐标偏移
    #     return auto.click_element("./assets/images/share/base/RedExclamationMark.png", "image", 0.9, max_retries=8, offset=offset, crop=crop)
