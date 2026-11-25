import logging
from io import StringIO
from unittest.mock import patch

import pytest

from utils.logger import coloredformatter
from utils.logger.colorcodefilter import ColorCodeFilter
from utils.logger.coloredformatter import ColoredFormatter


class TestColoredFormatter:
    def _format(self, ansi_supported):
        formatter = ColoredFormatter('%(asctime)s | %(levelname)s | %(message)s')
        record = logging.LogRecord('test', logging.INFO, __file__, 1, '消息内容', None, None)
        with patch.object(coloredformatter, 'ANSI_SUPPORTED', ansi_supported):
            return formatter.format(record)

    def test_colors_when_supported(self):
        text = self._format(True)
        assert '\033[92m' in text
        assert '\033[0m' in text
        assert 'INFO' in text

    def test_strips_colors_when_unsupported(self):
        text = self._format(False)
        assert '\033' not in text
        assert 'INFO' in text
        assert '消息内容' in text

    def test_strips_message_colors_when_unsupported(self):
        formatter = ColoredFormatter('%(levelname)s | %(message)s')
        record = logging.LogRecord('test', logging.INFO, __file__, 1, '\033[91m红色\033[0m消息', None, None)
        with patch.object(coloredformatter, 'ANSI_SUPPORTED', False):
            text = formatter.format(record)
        assert '\033' not in text
        assert '红色消息' in text

    def test_formatting_the_same_record_twice_keeps_its_level(self):
        formatter = ColoredFormatter('%(levelname)s | %(message)s')
        record = logging.LogRecord('test', logging.WARNING, __file__, 1, '检查 %s', ('进度',), None)
        with patch.object(coloredformatter, 'ANSI_SUPPORTED', True):
            first = formatter.format(record)
            assert formatter.format(record) == first
        assert record.levelname == 'WARNING'
        assert record.getMessage() == '检查 进度'

    @pytest.mark.parametrize('console_first', [True, False])
    def test_console_file_and_later_handlers_format_independently(self, console_first):
        logger = logging.Logger('formatter-order')
        streams = [StringIO() for _ in range(3)]
        formatters = [ColoredFormatter('%(levelname)s | %(message)s'),
                      ColorCodeFilter('%(levelname)s | %(message)s'),
                      logging.Formatter('%(levelname)s | %(message)s')]
        handlers = [logging.StreamHandler(stream) for stream in streams]
        for handler, formatter in zip(handlers, formatters):
            handler.setFormatter(formatter)
        logger.handlers = (handlers[:2] if console_first else handlers[1::-1]) + handlers[2:]

        with patch.object(coloredformatter, 'ANSI_SUPPORTED', True):
            logger.warning('无法保存 %s，完成 %d%%', 'overview_power', 50)

        assert '\033[93mWARNING\033[0m' in streams[0].getvalue()
        expected = 'WARNING | 无法保存 overview_power，完成 50%\n'
        assert streams[1].getvalue() == expected
        assert streams[2].getvalue() == expected
