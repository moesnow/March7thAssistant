from unittest.mock import MagicMock
from utils.logger.logger import Logger


class TestLoggerCustomLen:
    def test_ascii_string(self):
        logger = Logger.__new__(Logger)
        assert logger._custom_len("hello") == 5

    def test_chinese_string(self):
        logger = Logger.__new__(Logger)
        assert logger._custom_len("你好") == 4

    def test_mixed_string(self):
        logger = Logger.__new__(Logger)
        assert logger._custom_len("hello你好") == 9  # 5 + 4

    def test_empty_string(self):
        logger = Logger.__new__(Logger)
        assert logger._custom_len("") == 0

    def test_single_ascii_char(self):
        logger = Logger.__new__(Logger)
        assert logger._custom_len("a") == 1

    def test_single_chinese_char(self):
        logger = Logger.__new__(Logger)
        assert logger._custom_len("你") == 2


class TestLoggerHr:
    def _create_logger(self):
        logger = Logger.__new__(Logger)
        logger.logger_title = MagicMock()
        return logger

    def test_hr_level_0(self):
        logger = self._create_logger()
        logger.hr("测试标题", level=0, write=True)
        logger.logger_title.info.assert_called_once()
        call_args = logger.logger_title.info.call_args[0][0]
        assert "+" in call_args  # 包含分隔符
        assert "测试标题" in call_args

    def test_hr_level_1(self):
        logger = self._create_logger()
        logger.hr("测试标题", level=1, write=True)
        logger.logger_title.info.assert_called_once()
        call_args = logger.logger_title.info.call_args[0][0]
        assert "=" in call_args

    def test_hr_level_2(self):
        logger = self._create_logger()
        logger.hr("测试标题", level=2, write=True)
        logger.logger_title.info.assert_called_once()
        call_args = logger.logger_title.info.call_args[0][0]
        assert "-" in call_args

    def test_hr_no_write(self):
        logger = self._create_logger()
        logger.hr("测试标题", level=0, write=False)
        logger.logger_title.info.assert_not_called()


class TestLoggerCurrentDatetime:
    def test_format(self):
        logger = Logger.__new__(Logger)
        result = logger._current_datetime()
        assert len(result) == 10  # YYYY-MM-DD
        assert result[4] == "-"
        assert result[7] == "-"
