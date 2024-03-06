from managers.screen import screen
from managers.automation import auto
from managers.config import config
from managers.logger import logger
from tasks.power.power import Power
from tasks.power.instance import Instance
import time


class Echoofwar:
    @staticmethod
    def start():
        try:
            logger.hr("准备历战余响", 0)
            screen.change_to('guide3')
            guide3_crop = (262.0 / 1920, 289.0 / 1080, 422.0 / 1920, 624.0 / 1080)
            if auto.click_element("侵蚀隧洞", "text", max_retries=10, crop=guide3_crop):
                auto.mouse_scroll(12, -1)
                # 等待界面完全停止
                time.sleep(1)
                if auto.click_element("历战余响", "text", max_retries=10, crop=guide3_crop):
                    auto.find_element("历战余响", "text", max_retries=10, crop=(682.0 / 1920, 275.0 / 1080, 1002.0 / 1920, 184.0 / 1080), include=True)
                    for box in auto.ocr_result:
                        text = box[1][0]
                        if "/3" in text:
                            logger.info(f"历战余响本周可领取奖励次数：{text}")
                            reward_count = int(text.split("/")[0])
                            if reward_count == 0:
                                logger.hr("完成", 2)
                                config.save_timestamp("echo_of_war_timestamp")
                                return True
                            else:
                                power = Power.get()
                                max_count = power // 30
                                if max_count == 0:
                                    logger.info("🟣开拓力 < 30")
                                    return
                                return Instance.run("历战余响", config.instance_names["历战余响"], 30, min(reward_count, max_count))
            return False
        except Exception as e:
            logger.error(f"历战余响失败: {e}")
            return False
