from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.translate_manager import _
from managers.config_manager import config
from tasks.power.power import Power
import time


class GardenOfPlenty:
    @staticmethod
    def start():
        if config.activity_gardenofplenty_enable:
            screen.change_to('activity')
            if auto.click_element("花藏繁生", "text", None, crop=(46.0 / 1920, 107.0 / 1080, 222.0 / 1920, 848.0 / 1080)):
                time.sleep(1)
                auto.find_element("双倍奖励剩余次数", "text", max_retries=10, include=True)
                for box in auto.ocr_result:
                    text = box[1][0]
                    if "/12" in text:
                        reward_count = int(text.split("/")[0])
                        if reward_count == 0:
                            return
                        else:
                            logger.info(_("花藏繁生剩余次数：{text}").format(text=text))

                            instance_type = config.activity_gardenofplenty_instance_type
                            instance_name = config.instance_names[instance_type]

                            power = Power.power()

                            max_power = reward_count * 10
                            if power > max_power:
                                power = max_power

                            if power // 60 >= 1:
                                logger.hr(
                                    _("开始刷{type} - {name}，总计{number}次").format(type=instance_type, name=instance_name, number=power // 60), 2)
                                Power.run_instances(
                                    instance_type, instance_name, 60, power // 60)
                            if power % 60 >= 10:
                                logger.hr(
                                    _("开始刷{type} - {name}，总计{number}次").format(type=instance_type, name=instance_name, number=1), 2)
                                Power.run_instances(
                                    instance_type, instance_name, power % 60, 1)
