from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.translate_manager import _
from managers.config_manager import config
from tasks.power.power import Power
from tasks.power.instance import Instance
import time


class GardenOfPlenty:
    @staticmethod
    def start():
        if not config.activity_gardenofplenty_enable:
            return

        screen.change_to('activity')
        if not auto.click_element("花藏繁生", "text", None, crop=(46.0 / 1920, 107.0 / 1080, 222.0 / 1920, 848.0 / 1080)):
            return

        time.sleep(1)
        reward_count = GardenOfPlenty._get_reward_count()
        if reward_count == 0:
            return

        logger.info(_("花藏繁生剩余次数：{text}").format(text=reward_count))
        GardenOfPlenty._run_instances(reward_count)

    @staticmethod
    def _get_reward_count():
        auto.find_element("双倍奖励剩余次数", "text", max_retries=10, include=True)
        for box in auto.ocr_result:
            text = box[1][0]
            if "/12" in text:
                return int(text.split("/")[0])
        return 0

    @staticmethod
    def _run_instances(reward_count):
        instance_type = config.activity_gardenofplenty_instance_type
        instance_name = config.instance_names[instance_type]
        instance_power_max = 60
        instance_power_min = 10

        power = min(Power.get(), reward_count * instance_power_min)

        full_runs = power // instance_power_max
        if full_runs:
            Instance.run(instance_type, instance_name, instance_power_max, full_runs)

        partial_run_power = power % instance_power_max
        if partial_run_power >= instance_power_min:
            Instance.run(instance_type, instance_name, partial_run_power, 1)
