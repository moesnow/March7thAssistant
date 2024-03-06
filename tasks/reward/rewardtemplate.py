from abc import ABC, abstractmethod
from managers.screen import screen
from managers.automation import auto
from managers.logger import logger


class RewardTemplate(ABC):
    def __init__(self, name, enabled, screen):
        self.name = name
        self.enabled = enabled
        self.screen = screen

    def start(self):
        if not self.enabled:
            logger.info(f"{self.name}未开启")
            return

        logger.hr(f"检测到{self.name}奖励")
        self.prepare()
        self.run()
        logger.info(f"{self.name}奖励完成")

    def prepare(self):
        screen.change_to(self.screen)

    @abstractmethod
    def run(self):
        pass
