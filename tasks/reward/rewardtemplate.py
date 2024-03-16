from abc import ABC, abstractmethod
from module.screen import screen
from module.automation import auto
from module.logger import log


class RewardTemplate(ABC):
    def __init__(self, name, enabled, screen):
        self.name = name
        self.enabled = enabled
        self.screen = screen

    def start(self):
        if not self.enabled:
            log.info(f"{self.name}未开启")
            return

        log.hr(f"检测到{self.name}奖励", 1)
        self.prepare()
        self.run()
        log.hr(f"{self.name}奖励完成", 2)

    def prepare(self):
        screen.change_to(self.screen)

    @abstractmethod
    def run(self):
        pass
