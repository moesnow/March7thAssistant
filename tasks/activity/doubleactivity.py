from abc import abstractmethod
from module.automation import auto
from module.logger import log
from .activitytemplate import ActivityTemplate


class DoubleActivity(ActivityTemplate):
    def _get_reward_count(self):
        auto.find_element("奖励剩余次数", "text", max_retries=10, crop=(960.0 / 1920, 125.0 / 1080, 940.0 / 1920, 846.0 / 1080), include=True)
        for box in auto.ocr_result:
            text = box[1][0]
            if "/" in text:
                if text.split("/")[0].isdigit():
                    return int(text.split("/")[0])
        return 0

    @abstractmethod
    def _run_instances(self, reward_count):
        pass

    def run(self):
        reward_count = self._get_reward_count()
        if reward_count == 0:
            return True

        log.info(f"{self.name}剩余次数：{reward_count}")
        return self._run_instances(reward_count)
