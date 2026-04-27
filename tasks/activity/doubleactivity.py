from module.automation import auto
from module.logger import log
from .activitytemplate import ActivityTemplate
from tasks.power.power import Power


class DoubleActivity(ActivityTemplate):
    def __init__(self, name, enabled, instance_type, instance_names):
        super().__init__(name, enabled)
        self.instance_type = instance_type
        self.instance_names = instance_names
        
    def _get_reward_count(self):
        auto.find_element("奖励剩余次数", "text", max_retries=10, crop=(960.0 / 1920, 125.0 / 1080, 940.0 / 1920, 846.0 / 1080), include=True)
        for box in auto.ocr_result:
            text = box[1][0]
            if "/" in text:
                if text.split("/")[0].isdigit():
                    return int(text.split("/")[0])
        return 0

    def _run_instances(self, reward_count):
        if reward_count == 0:
            return True

        # 使用培养目标的副本配置（如果启用）
        instance_type, instance_name = self.get_build_target_instance(
            self.instance_type,
            self.instance_names[self.instance_type]
        )
        
        processed_count = Power.process(instance_type, instance_name, planned_attempts=reward_count)
        if isinstance(processed_count, int):
            if processed_count > 0:
                return True
            if processed_count == 0:
                log.info(f"{self.name}未执行副本，可能是体力不足，跳过重试")
                return True
        log.warning(f"{self.name}副本执行失败，Power.process返回值异常：{processed_count}")
        return False

    def run(self):
        reward_count = self._get_reward_count()
        if reward_count == 0:
            return True

        log.info(f"{self.name}剩余次数：{reward_count}")
        return self._run_instances(reward_count)
