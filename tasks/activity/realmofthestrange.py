from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.translate_manager import _
from managers.config_manager import config
from tasks.power.power import Power
import time


class RealmOfTheStrange:
    @staticmethod
    def start():
        if config.activity_realmofthestrange_enable:
            screen.change_to('activity')
            if auto.click_element("异器盈界", "text", None, crop=(46.0 / 1920, 107.0 / 1080, 222.0 / 1920, 848.0 / 1080)):
                time.sleep(1)
                auto.find_element("双倍奖励剩余次数", "text", max_retries=10, include=True)
                for box in auto.ocr_result:
                    text = box[1][0]
                    if "/3" in text:
                        reward_count = int(text.split("/")[0])
                        if reward_count == 0:
                            return
                        else:
                            logger.info(_("异器盈界剩余次数：{text}").format(text=text))

                            instance_type = "侵蚀隧洞"
                            instance_name = config.instance_names[instance_type]

                            power = Power.power()

                            if power < reward_count * 40:
                                logger.hr(
                                    _("开始刷{type} - {name}，总计{number}次").format(type=instance_type, name=instance_name, number=power // 40), 2)
                                Power.run_instances(instance_type, instance_name, 40, power // 40)
                            else:
                                logger.hr(
                                    _("开始刷{type} - {name}，总计{number}次").format(type=instance_type, name=instance_name, number=reward_count), 2)
                                Power.run_instances(instance_type, instance_name, 40, reward_count)
