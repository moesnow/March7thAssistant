from datetime import datetime
import logging
import os

from .coloredformatter import ColoredFormatter
from .titleformatter import TitleFormatter


class Logger:
    _instance = None

    def __new__(cls, level="INFO"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._create_logger(level)
        return cls._instance

    def current_datetime(self):
        return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    def _create_logger(self, level="INFO"):
        self.logger = logging.getLogger('March7thAssistant')
        self.logger.propagate = False
        self.logger.setLevel(level)

        if not os.path.exists("logs"):
            os.makedirs("logs")
        file_handler = logging.FileHandler(f"./logs/{self.current_datetime()}.log", encoding="utf-8")
        file_formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_formatter = ColoredFormatter('%(asctime)s | %(levelname)s | %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        self.logger.hr = TitleFormatter.format_title

        return self.logger

    def get_logger(self):
        return self.logger
