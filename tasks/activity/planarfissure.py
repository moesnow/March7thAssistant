from tasks.power.power import Power
from .doubleactivity import DoubleActivity
from module.screen import screen
from module.automation import auto
from module.logger import log
from tasks.power.instance import Instance
from tasks.weekly.universe import Universe
import time


class PlanarFissure(DoubleActivity):
    def __init__(self, name, enabled, instance_names):
        super().__init__(name, enabled)
        self.instance_names = instance_names

    def _run_instances(self, reward_count):
        if reward_count == 0:
            return True

        # 使用培养目标的副本配置（如果启用）
        instance_type, instance_name = self.get_build_target_instance(
            "饰品提取",
            self.instance_names["饰品提取"]
        )

        power = Power.get()
        full_runs = power // 40

        screen.change_to('guide3')
        instance_type_crop = (262.0 / 1920, 289.0 / 1080, 422.0 / 1920, 624.0 / 1080)

        auto.click_element(instance_type, "text", crop=instance_type_crop)
        # 等待界面完全停止
        time.sleep(1)

        # 需要判断是否有可用存档
        if auto.find_element("无可用存档", "text", crop=(688.0 / 1920, 289.0 / 1080, 972.0 / 1920, 369.0 / 1080), include=True):
            # 刷差分宇宙存档
            if Universe.start(nums=1, save=False, category="divergent"):
                # 验证存档
                screen.change_to('guide3')
                auto.click_element(instance_type, "text", crop=instance_type_crop)
                # 等待界面完全停止
                time.sleep(1)
                if auto.find_element("无可用存档", "text", crop=(688.0 / 1920, 289.0 / 1080, 972.0 / 1920, 369.0 / 1080), include=True):
                    log.error("暂无可用存档")
                    return True
            else:
                return True

        screen.change_to("guide3")

        immersifier_crop = (1623.0 / 1920, 40.0 / 1080, 162.0 / 1920, 52.0 / 1080)
        text = auto.get_single_line_text(crop=immersifier_crop, blacklist=['+', '米'], max_retries=3)
        if "/12" not in text:
            log.error("沉浸器数量识别失败")
            return True

        immersifier_count = int(text.split("/")[0])
        log.info(f"沉浸器: {immersifier_count}/12")

        count = min(immersifier_count + full_runs, reward_count)

        if count > 0:
            Instance.run("饰品提取", instance_name, 40, count)

        return True
