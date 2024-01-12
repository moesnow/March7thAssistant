from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.translate_manager import _
from managers.config_manager import config
from tasks.power.power import Power
from tasks.power.instance import Instance
import time


class RealmOfTheStrange:
    @staticmethod
    def start():
        if not config.activity_realmofthestrange_enable:
            return

        screen.change_to('activity')
        if not auto.click_element("异器盈界", "text", None, crop=(46.0 / 1920, 107.0 / 1080, 222.0 / 1920, 848.0 / 1080)):
            return

        time.sleep(1)
        reward_count = RealmOfTheStrange._get_reward_count()
        if reward_count == 0:
            return

        logger.info(_("异器盈界剩余次数：{text}").format(text=reward_count))
        RealmOfTheStrange._run_instances(reward_count)

    @staticmethod
    def _get_reward_count():
        auto.find_element("双倍奖励剩余次数", "text", max_retries=10, include=True)
        for box in auto.ocr_result:
            text = box[1][0]
            if "/3" in text:
                return int(text.split("/")[0])
        return 0

    @staticmethod
    def _run_instances(reward_count):
        instance_type = "侵蚀隧洞"
        instance_name = config.instance_names[instance_type]
        instance_power = 40

        power = min(Power.get(), reward_count * instance_power)

        full_runs = power // instance_power
        if full_runs:
            Instance.run(instance_type, instance_name, instance_power, full_runs)
