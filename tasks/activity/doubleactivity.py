from abc import abstractmethod
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.translate_manager import _
from .activitytemplate import ActivityTemplate


class DoubleActivity(ActivityTemplate):
    def _get_reward_count(self):
        auto.find_element("双倍奖励剩余次数", "text", max_retries=10, include=True)
        for box in auto.ocr_result:
            text = box[1][0]
            if "/" in text:
                return int(text.split("/")[0])
        return 0

    @abstractmethod
    def _run_instances(self, reward_count):
        pass

    def run(self):
        reward_count = self._get_reward_count()
        if reward_count == 0:
            return

        logger.info(_("{name}剩余次数：{text}").format(name=self.name, text=reward_count))
        self._run_instances(reward_count)
