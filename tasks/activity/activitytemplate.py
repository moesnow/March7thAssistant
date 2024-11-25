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
