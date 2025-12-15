from module.screen import screen
from module.automation import auto
from module.config import cfg
from module.logger import log
from tasks.power.power import Power
from tasks.power.instance import Instance
from tasks.daily.buildtarget import BuildTarget
import time


class Echoofwar:
    @staticmethod
    def start():
        try:
            log.hr("准备历战余响", 0)
            screen.change_to('guide3')
            guide3_crop = (262.0 / 1920, 289.0 / 1080, 422.0 / 1920, 624.0 / 1080)
            if auto.click_element("凝滞虚影", "text", max_retries=10, crop=guide3_crop):
                auto.mouse_scroll(12, -1)
                # 等待界面完全停止
                time.sleep(1)
                if auto.click_element("历战余响", "text", max_retries=10, crop=guide3_crop):
                    auto.find_element("历战余响", "text", max_retries=10, crop=(682.0 / 1920, 275.0 / 1080, 1002.0 / 1920, 184.0 / 1080), include=True)
                    for box in auto.ocr_result:
                        text = box[1][0]
                        if "/3" in text:
                            log.info(f"历战余响本周可领取奖励次数：{text}")
                            reward_count = int(text.split("/")[0])
                            if reward_count == 0:
                                log.hr("完成", 2)
                                cfg.save_timestamp("echo_of_war_timestamp")
                                return True
                            else:
                                power = Power.get()
                                max_count = power // 30
                                if max_count == 0:
                                    log.info("开拓力 < 30")
                                    return
                                if cfg.build_target_enable and (target := BuildTarget.get_target_echo_instance()):
                                    instance_name = target[1]
                                else:
                                    instance_name = cfg.instance_names["历战余响"]
                                return Instance.run("历战余响", instance_name, 30, min(reward_count, max_count))
            return False
        except Exception as e:
            log.error(f"历战余响失败: {e}")
            return False
