import time
from abc import ABC, abstractmethod
from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.translate_manager import _


class ActivityTemplate(ABC):
    def __init__(self, name, enabled):
        self.name = name
        self.enabled = enabled

    def start(self):
        if not self.enabled:
            logger.info(_("{name}未开启").format(name=self.name))
            return

        self.prepare()
        self.run()

    def prepare(self):
        screen.change_to('activity')
        if not auto.click_element(self.name, "text", None, crop=(46.0 / 1920, 107.0 / 1080, 222.0 / 1920, 848.0 / 1080)):
            return
        time.sleep(1)

    @abstractmethod
    def run(self):
        pass
