import time
from abc import ABC, abstractmethod
from module.screen import screen
from module.automation import auto
from module.logger import log


class ActivityTemplate(ABC):
    def __init__(self, name, enabled):
        self.name = name
        self.enabled = enabled

    def start(self):
        if not self.enabled:
            log.info(f"{self.name}未开启")
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
