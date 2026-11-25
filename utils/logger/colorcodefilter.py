import logging
import re


class ColorCodeFilter(logging.Formatter):
    """
    自定义日志格式化器，用于移除日志消息中的ANSI颜色代码。
    这样可以确保日志文本在不支持颜色代码的环境中也能正确显示。
    """

    # 预编译颜色代码的正则表达式，用于匹配ANSI颜色代码
    color_pattern = re.compile(r'\033\[[0-9;]+m')

    def format(self, record):
        """
        重写format方法，用于在格式化日志记录之前移除颜色代码。
        :param record: 日志记录
        :return: 清理颜色代码后的日志字符串
        """
        # 参数只由 logging 替换一次；清理最终输出，不改动后续处理器共用的消息和级别。
        return self._remove_color_codes(super().format(record))

    def _remove_color_codes(self, message):
        """
        使用正则表达式移除字符串中的ANSI颜色代码。
        :param message: 含有颜色代码的字符串
        :return: 清理颜色代码后的字符串
        """
        return self.color_pattern.sub('', message)
