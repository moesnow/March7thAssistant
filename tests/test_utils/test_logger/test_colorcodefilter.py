import logging
import sys

import pytest

from utils.logger.colorcodefilter import ColorCodeFilter


class TestColorCodeFilter:
    def test_remove_color_codes(self):
        f = ColorCodeFilter()
        assert f._remove_color_codes("\033[91merror\033[0m") == "error"

    def test_remove_multiple_color_codes(self):
        f = ColorCodeFilter()
        assert f._remove_color_codes("\033[91mhello\033[0m \033[92mworld\033[0m") == "hello world"

    def test_no_color_codes(self):
        f = ColorCodeFilter()
        assert f._remove_color_codes("plain text") == "plain text"

    def test_empty_string(self):
        f = ColorCodeFilter()
        assert f._remove_color_codes("") == ""

    @pytest.mark.parametrize(("message", "args", "expected"), [
        ("无法保存总览读数 %s，本次任务继续", ("overview_power",), "无法保存总览读数 overview_power，本次任务继续"),
        ("完成 %d%%，%s", (50, "\033[91m继续\033[0m"), "完成 50%，继续"),
        ("%(name)s：%(count)d", ({"name": "任务", "count": 3},), "任务：3"),
        (ValueError("\033[91m原始故障\033[0m"), None, "原始故障"),
    ])
    def test_formats_parameters_without_changing_the_shared_record(self, message, args, expected):
        record = logging.LogRecord("test", logging.WARNING, __file__, 1, message, args, None)
        original = record.msg, record.args, record.levelname
        formatter = ColorCodeFilter("%(levelname)s | %(message)s")

        assert formatter.format(record) == f"WARNING | {expected}"
        assert formatter.format(record) == f"WARNING | {expected}"
        assert (record.msg, record.args, record.levelname) == original
        assert logging.Formatter("%(message)s").format(record) == record.getMessage()

    def test_strips_colors_from_exception_and_keeps_the_original_error(self):
        try:
            raise OSError("\033[91m配置暂时不可写\033[0m")
        except OSError:
            record = logging.LogRecord("test", logging.WARNING, __file__, 1,
                                       "无法保存 %s", ("overview_power",), sys.exc_info())

        text = ColorCodeFilter("%(levelname)s | %(message)s").format(record)
        assert "\033" not in text
        assert "WARNING | 无法保存 overview_power" in text
        assert "Traceback (most recent call last):" in text
        assert "OSError: 配置暂时不可写" in text
        assert "\033[91m配置暂时不可写\033[0m" in str(record.exc_info[1])
