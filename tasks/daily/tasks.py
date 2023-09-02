from managers.automation_manager import auto
from managers.ocr_manager import ocr
import time
import json


class Tasks:
    def __init__(self, config_example_path):
        self.crop = (243.0 / 1920, 377.0 / 1080, 1428.0 / 1920, 528.0 / 1080)
        self.task_mappings = self._default_config(config_example_path)
        self.daily_tasks = {task: False for task in self.task_mappings.values()}

    def _default_config(self, config_example_path):
        try:
            with open(config_example_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except FileNotFoundError:
            exit(1)

    def start(self):
        self.detect()
        self.scroll()
        self.detect()
        return self.daily_tasks

    def detect(self):
        auto.take_screenshot(crop=self.crop)
        result = ocr.recognize_multi_lines(auto.screenshot)
        for box in result:
            text = box[1][0]
            for keyword, task_name in self.task_mappings.items():
                if keyword in text:

                    self.daily_tasks[task_name] = True
                    break

    def scroll(self):
        auto.click_element("./assets/images/quest/activity.png", "image", 0.95, crop=self.crop)
        auto.mouse_scroll(18, -1)
        time.sleep(0.5)
