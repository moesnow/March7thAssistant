from abc import ABC, abstractmethod
from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.translate_manager import _


class RewardTemplate(ABC):
    def __init__(self, name, enabled, screen):
        self.name = name
        self.enabled = enabled
        self.screen = screen

    def start(self):
        if not self.enabled:
            logger.info(_("{name}未开启").format(name=self.name))
            return

        logger.hr(_("检测到{name}奖励").format(name=self.name), 2)
        self.prepare()
        self.run()
        logger.info(_("{name}奖励完成").format(name=self.name))

    def prepare(self):
        screen.change_to(self.screen)

    @abstractmethod
    def run(self):
        pass
