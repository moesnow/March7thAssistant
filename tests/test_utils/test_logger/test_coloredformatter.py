import logging
from unittest.mock import patch

from utils.logger import coloredformatter
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
