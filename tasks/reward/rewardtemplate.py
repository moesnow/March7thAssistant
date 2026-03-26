from abc import ABC, abstractmethod
from module.screen import screen
from module.automation import auto
from module.logger import log


class RewardTemplate(ABC):
    def __init__(self, name: str, enabled: bool, screen_name: str):
        self.name = name
        self.enabled = enabled
        self.screen_name = screen_name

    def start(self):
        if not self.enabled:
            log.info(f"{self.name}未开启")
            return

        log.hr(f"检测到{self.name}奖励", 1)
        self.prepare()
        self.run()
        log.hr(f"{self.name}奖励完成", 2)

    def prepare(self):
        screen.change_to(self.screen_name)

    @abstractmethod
    def run(self):
        pass
