from module.logger import log
from module.automation import auto
from .rewardtemplate import RewardTemplate
import time


class Achievement(RewardTemplate):
    def run(self):
        total_received = 0
        auto.click_element((0, 0, 1, 1), "crop")
        for direction in [1, -1]:
            time.sleep(1.0)
            auto.click_element((602 / 1920, 22 / 1080, 726 / 1920, 78 / 1080), "crop")
            auto.mouse_scroll(12, direction)
            for _ in range(9):
                if not auto.click_element("./assets/images/share/base/RedExclamationMark.png", "image", 0.8, max_retries=2, crop=(602 / 1920, 22 / 1080, 726 / 1920, 78 / 1080)):
                    break
                for _ in range(50):
                    if not auto.click_element("领取", "text", include=True, max_retries=4, retry_delay=0.5, crop=(1672 / 1920, 256 / 1080, 172 / 1920, 96 / 1080)):
                        break
                    auto.click_element("关闭", "text", include=True, max_retries=4, retry_delay=0.5, crop=(554 / 1920, 654 / 1080, 818 / 1920, 220 / 1080))
                    total_received += 1
                    time.sleep(1.0)

        log.info(f"领取了 {total_received}个 成就奖励")
