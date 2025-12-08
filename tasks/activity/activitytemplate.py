import time
from abc import ABC, abstractmethod
from module.screen import screen
from module.automation import auto
from module.logger import log
from module.config import cfg


class ActivityTemplate(ABC):
    def __init__(self, name, enabled):
        self.name = name
        self.enabled = enabled

    def start(self):
        if not self.enabled:
            log.info(f"{self.name}未开启")
            return True

        self.prepare()
        return self.run()

    def prepare(self):
        screen.change_to('activity')
        if not auto.click_element(self.name, "text", None, crop=(53.0 / 1920, 109.0 / 1080, 190.0 / 1920, 846.0 / 1080), include=True):
            return
        time.sleep(1)

    @abstractmethod
    def run(self):
        pass

    @staticmethod
    def get_build_target_instance(default_type, default_name):
        """
        获取培养目标中匹配的副本实例
        
        Args:
            default_type: 默认副本类型
            default_name: 默认副本名称
            
        Returns:
            tuple: (instance_type, instance_name) 副本类型和名称
        """
        if not cfg.build_target_enable:
            return default_type, default_name
            
        from tasks.daily.buildtarget import BuildTarget
        target_instances = BuildTarget.get_target_instances()
        
        for target_type, target_name in target_instances:
            # 精确匹配副本类型
            if target_type == default_type:
                log.info(f"活动使用培养目标副本: {target_type} - {target_name}")
                return target_type, target_name
        
        return default_type, default_name
