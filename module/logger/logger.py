from datetime import datetime
import logging
import os


class ColoredFormatter(logging.Formatter):
    from colorama import init
    init(autoreset=True)
    COLORS = {
        'DEBUG': '\033[94m',  # 蓝色
        'INFO': '\033[92m',   # 绿色
        'WARNING': '\033[93m',  # 黄色
        'ERROR': '\033[91m',   # 红色
        'CRITICAL': '\033[91m',  # 红色
        'RESET': '\033[0m'   # 重置颜色
    }

    def format(self, record):
        log_level = record.levelname
        color_start = self.COLORS.get(log_level, self.COLORS['RESET'])
        color_end = self.COLORS['RESET']
        record.levelname = f"{color_start}{log_level}{color_end}"
        return super().format(record)


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
        self.logger = logging.getLogger('Automatic_Star_Rail')
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

        self.logger.hr = self._format_title_with_separator  # type: ignore

        return self.logger

    def get_logger(self):
        return self.logger

    def set_level(self, log_level):
        self.logger.setLevel(log_level)

    def custom_len(self, s):
        length = 0
        for char in s:
            # 判断是否是中文字符和全角符号的Unicode范围
            if (ord(char) >= 0x4E00 and ord(char) <= 0x9FFF) or (ord(char) >= 0xFF00 and ord(char) <= 0xFFEF):
                length += 2
            else:
                length += 1
        return length

    def _format_title_with_separator(self, title, level=0):
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

            print(separator)
            print('\n'.join(formatted_title_lines))
            print(separator)
        elif level == 1:
            formatted_title = '=' * half_separator_left + ' ' + title + ' ' + '=' * half_separator_right
            print(f"{formatted_title}")
        elif level == 2:
            formatted_title = '-' * half_separator_left + ' ' + title + ' ' + '-' * half_separator_right
            print(f"{formatted_title}")

    # def hr(self,title, level=0):
    #     return self._format_title_with_separator(title, level)
