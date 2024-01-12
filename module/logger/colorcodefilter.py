import logging


class ColorCodeFilter(logging.Formatter):
    def format(self, record):
        log_message = record.getMessage()
        record.msg = self._remove_color_codes(log_message)
        record.levelname = self._remove_color_codes(record.levelname)
        return super().format(record)

    def _remove_color_codes(self, message):
        import re
        color_pattern = re.compile(r'\033\[[0-9;]+m')
        return color_pattern.sub('', message)
