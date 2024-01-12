from datetime import datetime
import logging
import os

from .coloredformatter import ColoredFormatter
from .colorcodefilter import ColorCodeFilter


class Logger:
    _instance = None

    def __new__(cls, level="INFO"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._create_logger(level)
            cls._instance._create_logger_title(level)
        return cls._instance

    def current_datetime(self):
        # return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return datetime.now().strftime("%Y-%m-%d")

    def _create_logger(self, level="INFO"):
        self.logger = logging.getLogger('March7thAssistant')
        self.logger.propagate = False
        self.logger.setLevel(level)

        console_handler = logging.StreamHandler()
        console_formatter = ColoredFormatter('%(asctime)s | %(levelname)s | %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        if not os.path.exists("logs"):
            os.makedirs("logs")
        file_handler = logging.FileHandler(f"./logs/{self.current_datetime()}.log", encoding="utf-8")
        file_formatter = ColorCodeFilter('%(asctime)s | %(levelname)s | %(message)s')
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        self.logger.hr = self.format_title

        return self.logger

    def _create_logger_title(self, level="INFO"):
        self.logger_title = logging.getLogger('March7thAssistant_title')
        self.logger_title.propagate = False
        self.logger_title.setLevel(level)

        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger_title.addHandler(console_handler)

        if not os.path.exists("logs"):
            os.makedirs("logs")
        file_handler = logging.FileHandler(f"./logs/{self.current_datetime()}.log", encoding="utf-8")
        file_formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(file_formatter)
        self.logger_title.addHandler(file_handler)

        return self.logger_title

    def get_logger(self):
        return self.logger

    def custom_len(self, s):
        length = 0
        for char in s:
            # 判断是否是中文字符和全角符号的Unicode范围
            if (ord(char) >= 0x4E00 and ord(char) <= 0x9FFF) or (ord(char) >= 0xFF00 and ord(char) <= 0xFFEF):
                length += 2
            else:
                length += 1
        return length

    def format_title(self, title, level=0, write_to_file=True):
        try:
            separator_length = 115
            title_lines = title.split('\n')
            separator = '+' + '-' * separator_length + '+'
            title_length = self.custom_len(title)
            half_separator_left = (separator_length - title_length) // 2
            half_separator_right = separator_length - title_length - half_separator_left

            if level == 0:
                formatted_title_lines = []

                for line in title_lines:
                    title_length_ = self.custom_len(line)
                    half_separator_left_ = (separator_length - title_length_) // 2
                    half_separator_right_ = separator_length - title_length_ - half_separator_left_

                    formatted_title_line = '|' + ' ' * half_separator_left_ + line + ' ' * half_separator_right_ + '|'
                    formatted_title_lines.append(formatted_title_line)

                self.print_title(separator, write_to_file)
                self.print_title('\n'.join(formatted_title_lines), write_to_file)
                self.print_title(separator, write_to_file)
            elif level == 1:
                formatted_title = '=' * half_separator_left + ' ' + title + ' ' + '=' * half_separator_right
                self.print_title(f"{formatted_title}", write_to_file)
            elif level == 2:
                formatted_title = '-' * half_separator_left + ' ' + title + ' ' + '-' * half_separator_right
                self.print_title(f"{formatted_title}", write_to_file)
        except:
            pass

    def print_title(self, title, write_to_file):
        if write_to_file:
            self.logger_title.info(title)
        else:
            print(title)
